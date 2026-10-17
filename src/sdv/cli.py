"""`sdv`: the one documented command.

    sdv demo                      # Scenario B at demo pace with the governor, both priority files, then Scenario A
    sdv admit G4 --installed G1,G2,G3 [--mission survey] [--edit G4.hangar.mass_t=0.8] [--card jury.yaml]
    sdv sim scenario-b [--mission survey] [--seed 1] [--until-min 21] [--speed 0] [--no-governor]
    sdv replay-check scenario-b   # two runs, decisions included, hashes must match
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

from . import admission, placement as P
from .data import MANIFESTS, Inputs, load_assumptions, load_cards, load_inputs, load_missions
from .decision import Decision, ceiling_ms, fmt, timed
from .governor import Governor
from .plant.sim import Simulator, write_jsonl

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def _c(text: str, code: str, color: bool) -> str:
    return f"{code}{text}{RESET}" if color else text


# -- views ------------------------------------------------------------------------------------------
def fmt_tick(s: dict) -> str:
    g, ship = s["gauges"], s["ship"]
    guests = " ".join(f"{k}:{v['mode']}@{v['actual_kw']:g}kW" for k, v in s["guests"].items())
    ev = ("  <- " + ", ".join(e["type"] for e in s["events"])) if s["events"] else ""
    res = s.get("governor", {}).get("reserved_kw") or {}
    reserved = f" (+{sum(res.values()):g} reserved)" if res else ""
    return (f"{s['t_min']:6.2f} min | {ship['speed_band']:7} {ship['course']:6} {ship['noise']:7} deck={ship['deck']:8} "
            f"gen={ship['genset']} cool={ship['cooling']:8} | P {g['power']['committed']:6.1f}/{g['power']['capacity']:5.0f}{reserved}"
            f"  H {g['heat']['committed']:6.1f}/{g['heat']['capacity']:5.1f} | {guests}{ev}")


def fmt_decision(d: dict, color: bool = False) -> str:
    kind = d["kind"]
    lat = f"{d['latency_ms']:.1f} ms of {d['ceiling_ms'] / 1000:g} s" if d["latency_ms"] else "precomputed"
    head = f"{d['t_s'] / 60:6.2f} min  {kind} {d['verdict']}  [{d.get('mission')}]  {lat}"
    b = d.get("binding")
    bind = f"binding {b['class']}: {fmt(b['demand'])} of {fmt(b['capacity'])} {b['unit']}" if b else ""
    return f"{_c(head, BOLD, color)}\n        {d['sentence']}\n        {_c(bind, DIM, color)}".rstrip()


def print_admission(d: Decision, color: bool = False) -> None:
    x = d.extras
    print(_c(f"D1 {d.verdict.upper()} for {d.subject} under {d.mission}  ({d.latency_ms:.1f} ms of {d.ceiling_ms / 1000:g} s)", BOLD, color))
    print(f"  {d.sentence}")
    print(_c("  ledger at the envelope (both gensets, 200 kW reserve, cooling at 30 °C):", DIM, color))
    for ln in x["lines"]:
        flag = " FAILS" if ln["fails"] else ""
        print(f"    {ln['class']:10} {fmt(ln['demand']):>8} / {fmt(ln['capacity']):<8} {ln['unit']}{flag}")
    print("  placement:", ", ".join(f"{k}={v or 'NONE'}" for k, v in d.placement.items()))
    for r in x["rejected"][:4]:
        print(f"    rejected {r['part']} at {r['slot']}: {r['why']}")
    if x["one_genset_down"]:
        o = x["one_genset_down"]
        print(f"  one genset down: {fmt(o['load_kw'])} of {fmt(o['reserve_kw'])} kW, gate {o['gate_kw']} kW: {o['status']}"
              + (f" -> {o['fix'][0]['sentence']}" if o["fix"] else ""))
    if x["seawater"]:
        t = x["seawater"]
        print(f"  seawater tipping point: {fmt(t['tip_c'])} °C" + (f" (holds at {t['holds_at_c']}, fails at {t['fails_at_c']})" if t["inside_scan"] else " (outside the scan)"))
    for i, o in enumerate(x["yes_if"], 1):
        og = o["one_genset_down"]
        mv = ("; move " + ", ".join(f"{m['part']} {m['from']}->{m['to']}" for m in o["moves"])) if o["moves"] else ""
        print(f"  option {i}: remove {', '.join(o['remove'])}  value lost {fmt(o['value_lost'])}{' (mission-critical)' if o['mission_critical'] else ''}"
              f"{mv}; {fmt(o['mass_after_t'])} t; one genset down {og['status']} at {fmt(og['load_kw'])} kW"
              + (f"; cooling flips at {fmt(o['seawater']['tip_c'])} °C" if o["seawater"] else ""))
    for ne in x["not_enough"]:
        print(f"  not enough: remove {', '.join(ne['remove'])} leaves {fmt(ne['mass_after_t'])} t, still failing {', '.join(ne['still_failing'])}")


# -- commands ----------------------------------------------------------------------------------------
def _parse_edits(items: list[str] | None) -> dict:
    out = {}
    for it in items or []:
        k, v = it.split("=", 1)
        out[k] = yaml.safe_load(v)
    return out


def load_jury_card(path: str, cards: dict) -> dict:
    """A card handed over at the demo: validated against the manifest schema before it is judged."""
    card = yaml.safe_load(Path(path).read_text())
    jsonschema.validate(card, json.loads((MANIFESTS / "schema.json").read_text()))
    cards = dict(cards)
    cards[card["id"]] = card
    return cards


def admit(card_id: str, installed: list[str], mission: str, edits: dict | None = None, card_path: str | None = None,
          installed_placement: dict | None = None) -> Decision:
    a, cards, missions = load_assumptions(), load_cards(), load_missions()
    if card_path:
        cards = load_jury_card(card_path, cards)
        card_id = card_id or yaml.safe_load(Path(card_path).read_text())["id"]
    placement = installed_placement or P.default_installed(a, cards, installed)
    holder: dict = {}
    with timed(holder):
        d = admission.decide(a, cards, missions[mission], placement, card_id, edits)
    d.latency_ms, d.ceiling_ms = holder["latency_ms"], ceiling_ms(a, "D1")
    return d


def cmd_admit(args: argparse.Namespace) -> int:
    installed = [g for g in (args.installed or "").split(",") if g]
    d = admit(args.card, installed, args.mission, _parse_edits(args.edit), args.card_file)
    print_admission(d, color=not args.no_color)
    if args.json:
        print(json.dumps(d.as_dict(), indent=2, default=str))
    return 0


def run_sim(inputs: Inputs, args, mission: str, sink=None, governor: bool = True):
    gov = Governor(inputs, mission) if governor else None
    sim = Simulator(inputs, seed=args.seed, mission=mission, on_tick=gov.on_tick if gov else None)
    h = sim.run(args.until_min, realtime_factor=getattr(args, "speed", 0.0), sink=sink)
    return gov, sim, h


def cmd_sim(args: argparse.Namespace) -> int:
    inputs = load_inputs(args.scenario)
    every = int(args.print_every * 60)
    color = not args.no_color

    def sink(s: dict) -> None:
        if args.quiet:
            return
        if s["events"] or (every and s["t_s"] % every == 0):
            print(fmt_tick(s))
        for d in s.get("decisions", []):
            print(fmt_decision(d, color))
        for r in s.get("governor_log", []):
            print(f"        priority file: {r}")

    gov, sim, h = run_sim(inputs, args, args.mission or "survey", sink, governor=not args.no_governor)
    out = Path(args.out) if args.out else Path("runs") / f"{inputs.scenario['id']}_{args.mission or 'survey'}_s{args.seed}.jsonl"
    write_jsonl(out, sim)
    n = len(gov.decisions) if gov else 0
    print(f"run_hash {h}  ticks {len(sim.snapshots)}  decisions {n}  -> {out}")
    return 0


def cmd_replay_check(args: argparse.Namespace) -> int:
    hashes = [run_sim(load_inputs(args.scenario), args, args.mission or "survey")[2] for _ in range(2)]
    ok = hashes[0] == hashes[1]
    print(f"run 1 {hashes[0]}\nrun 2 {hashes[1]}\n{'IDENTICAL' if ok else 'DIFFERENT'}")
    return 0 if ok else 1


def cmd_demo(args: argparse.Namespace) -> int:
    """Scenario B at demo pace under the first file, the other file's records beside it, then Scenario A."""
    color = not args.no_color
    inputs = load_inputs("scenario-b")
    files = [args.mission, args.swap_to]
    print(_c(f"ArgOS demo: Scenario B ({inputs.scenario['location']['name']}, {inputs.scenario['location']['seawater_c']} °C), "
             f"guests {', '.join(inputs.scenario['guests'])}, priority file {files[0]} (then {files[1]}), "
             f"{args.speed:g} ship-minutes per wall minute", BOLD, color))

    def sink(s: dict) -> None:
        if s["events"] and s["t_s"] % 60 == 0:
            print(fmt_tick(s))
        for d in s.get("decisions", []):
            if d["verdict"] != "armed":
                print(fmt_decision(d, color))

    gov1, sim1, h1 = run_sim(inputs, args, files[0], sink)
    print(_c(f"\nSame events under the {files[1]} file (replayed flat out):", BOLD, color))
    gov2, sim2, h2 = run_sim(inputs, argparse.Namespace(seed=args.seed, until_min=args.until_min, speed=0.0), files[1])
    for d1, d2 in zip([d for d in gov1.decisions if d.verdict != "armed"], [d for d in gov2.decisions if d.verdict != "armed"]):
        print(f"{d1.t_s / 60:6.2f} min  {d1.kind}  {files[0]}: {d1.sentence}\n             {files[1]}: {d2.sentence}")
    print(_c(f"\nrun hashes {h1} / {h2}; every decision inside its ceiling: "
             f"{all(d.within_ceiling for d in gov1.decisions + gov2.decisions)}", DIM, color))
    for sim, f in ((sim1, files[0]), (sim2, files[1])):
        write_jsonl(Path("runs") / f"demo_scenario_b_{f}.jsonl", sim)

    print(_c("\nScenario A: the jury's card.", BOLD, color))
    if args.no_prompt:
        d = admit("G4", ["G1", "G2", "G3"], files[0])
        print_admission(d, color)
        return 0
    while True:
        try:
            line = input("card id or YAML path (blank = G4), installed (blank = G1,G2,G3), mission (blank = survey); q to quit\n> ").strip()
        except EOFError:
            return 0
        if line.lower() in ("q", "quit", "exit"):
            return 0
        bits = [b.strip() for b in line.split()] + ["", "", ""]
        card, installed, mission = bits[0] or "G4", bits[1] or "G1,G2,G3", bits[2] or files[0]
        edits = _parse_edits([b for b in bits[3:] if "=" in b])
        try:
            path = card if card.endswith((".yaml", ".yml")) else None
            d = admit("" if path else card, installed.split(","), mission, edits, path)
            print_admission(d, color)
        except Exception as e:  # a bad card or a typo must not end the demo
            print(f"refused: {e.__class__.__name__}: {str(e).splitlines()[0]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdv", description="ArgOS resource governor for a software-defined vessel")
    p.add_argument("--no-color", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("scenario", help="scenario id (scenario-b) or path to a YAML file")
        sp.add_argument("--seed", type=int, default=1)
        sp.add_argument("--mission", help="priority file id (survey, sar, patrol, disaster_relief)")
        sp.add_argument("--until-min", type=float, default=21.0)

    s = sub.add_parser("sim", help="run the plant with the governor and write a JSONL run")
    common(s)
    s.add_argument("--speed", type=float, default=0.0, help="ship-minutes per wall minute; 0 = flat out, 12 = demo pace")
    s.add_argument("--print-every", type=float, default=1.0, help="print a line every N ship-minutes (0 = events only)")
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--no-governor", action="store_true", help="open loop: plant only")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_sim)

    r = sub.add_parser("replay-check", help="run twice with the governor, compare run hashes")
    common(r)
    r.set_defaults(fn=cmd_replay_check)

    ad = sub.add_parser("admit", help="D1/D2: judge a card against the installed guests at the envelope")
    ad.add_argument("card", nargs="?", default="", help="card id (G1-G6); omit when --card-file is given")
    ad.add_argument("--installed", default="", help="comma-separated guest ids already aboard")
    ad.add_argument("--mission", default="survey")
    ad.add_argument("--edit", action="append", help="live card edit, e.g. G4.hangar.mass_t=0.8 (repeatable)")
    ad.add_argument("--card-file", help="a jury card as YAML, validated against manifests/schema.json")
    ad.add_argument("--json", action="store_true", help="also print the decision record")
    ad.set_defaults(fn=cmd_admit)

    d = sub.add_parser("demo", help="the live demo: Scenario B under two files, then Scenario A")
    d.add_argument("--mission", default="survey")
    d.add_argument("--swap-to", default="sar")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--until-min", type=float, default=20.0)
    d.add_argument("--speed", type=float, default=load_assumptions()["sim"]["demo_speed"])
    d.add_argument("--no-prompt", action="store_true", help="run drill A1 instead of asking for a card")
    d.set_defaults(fn=cmd_demo)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
