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
import time
from pathlib import Path

import jsonschema
import yaml

from . import admission, placement as P
from .data import MANIFESTS, Inputs, load_assumptions, load_cards, load_inputs, load_missions
from .decision import Decision, ceiling_ms, fmt, timed
from .environment import RouteEnvironment
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
    env = s["env"]
    sea = f" sea {env['seawater_c']:g}°C ss{env.get('sea_state', '?')} gust {env.get('gust_kn', env.get('wind_kn')):g}kn" if env.get("source") else ""
    return (f"{s['t_min']:6.2f} min | {ship['speed_band']:7} {ship['course']:6} {ship['noise']:7} deck={ship['deck']:8} "
            f"gen={ship['genset']} cool={ship['cooling']:8} | P {g['power']['committed']:6.1f}/{g['power']['capacity']:5.0f}{reserved}"
            f"  H {g['heat']['committed']:6.1f}/{g['heat']['capacity']:5.1f}{sea} | {guests}{ev}")


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
    if x.get("route"):
        r = x["route"]
        print(f"  on the route ({r['name']}, {r['period']}, Open-Meteo CC BY 4.0): seawater {fmt(r['seawater_c'][0])}-{fmt(r['seawater_c'][1])} °C, "
              f"loop min {fmt(r['loop_min_kw'])} kW ({fmt(r['free_kw'])} kW free; degraded {fmt(r['loop_min_degraded_kw'])} kW), "
              f"sea state max {r['sea_state_max']}, gusts max {fmt(r['gust_kn_max'])} kn")
        for act in r["activities"]:
            if act["closed_h"]:
                print(f"    {act['activity']}: closed {act['closed_h']} h in {act['n_windows']} windows "
                      f"(wind > {act['wind_kn_max']} kn or sea state > {act['sea_state_max']}): first at plan hours {act['windows'][0]}")
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
          installed_placement: dict | None = None, route: str | None = None) -> Decision:
    a, cards, missions = load_assumptions(), load_cards(), load_missions()
    if card_path:
        cards = load_jury_card(card_path, cards)
        card_id = card_id or yaml.safe_load(Path(card_path).read_text())["id"]
    placement = installed_placement or P.default_installed(a, cards, installed)
    env = RouteEnvironment.load(a, route) if route else None
    holder: dict = {}
    with timed(holder):
        d = admission.decide(a, cards, missions[mission], placement, card_id, edits, route=env)
    d.latency_ms, d.ceiling_ms = holder["latency_ms"], ceiling_ms(a, "D1")
    return d


def cmd_admit(args: argparse.Namespace) -> int:
    installed = [g for g in (args.installed or "").split(",") if g]
    d = admit(args.card, installed, args.mission, _parse_edits(args.edit), args.card_file, route=args.route)
    print_admission(d, color=not args.no_color)
    if args.json:
        print(json.dumps(d.as_dict(), indent=2, default=str))
    return 0


def route_for(inputs: Inputs, args) -> RouteEnvironment | None:
    """The mission plan to drive the environment from, when `--env plan` asks for it."""
    plan = getattr(args, "route", None) or inputs.scenario.get("plan")
    return RouteEnvironment.load(inputs.assumptions, plan) if getattr(args, "env", "scenario") == "plan" and plan else None


def run_sim(inputs: Inputs, args, mission: str, sink=None, governor: bool = True):
    gov = Governor(inputs, mission) if governor else None
    sim = Simulator(inputs, seed=args.seed, mission=mission, on_tick=gov.on_tick if gov else None, route=route_for(inputs, args))
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


KEYS = """keys while Scenario B plays (the jury's failures, each lands on the next tick and is recorded):
  g genset trips      r genset restarts     c cooling pump fails     w seawater +3 °C
  b drone reports its battery now           o G5 draws 20 % over its card
  s swap the priority file                  k crew 14 -> 6 -> 0 -> 14
  p pause / resume    h this list"""


class KeyInjector:
    """Turns keypresses into plant events during the paced run. Only active on a terminal; the key map is
    the keyboard stand-in for the board's button and knob (DESIGN_FREEZE delta 10)."""

    def __init__(self, sim, gov, files: list[str], color: bool):
        self.sim, self.gov, self.files, self.color = sim, gov, files, color
        self.fd = None
        self.saved = None
        self.injected: list[dict] = []
        if sys.stdin.isatty():
            import termios
            import tty
            self.fd = sys.stdin.fileno()
            self.saved = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)

    def close(self) -> None:
        if self.saved is not None:
            import termios
            termios.tcflush(self.fd, termios.TCIFLUSH)
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)

    def _keys(self) -> str:
        if self.fd is None:
            return ""
        import select
        out = ""
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if not ch:
                break
            out += ch
        return out

    def event_for(self, key: str) -> dict | None:
        sim = self.sim
        crew_levels = sim.inputs.assumptions["crew"]["levels"]
        if key == "g":
            return {"type": "genset_trip", "gensets_online": 1}
        if key == "r":
            return {"type": "genset_restart", "gensets_online": 2}
        if key == "c":
            return {"type": "cooling_degraded", "factor": sim.inputs.assumptions["heat"]["degraded_factor"], "confirmed": True, "confirmed_by": "plant alarm"}
        if key == "w":
            return {"type": "environment", "seawater_c": round(sim.env["seawater_c"] + 3, 1)}
        if key == "b":
            g = sim.guests.get("G4")
            return {"type": "guest_report", "guest": "G4", "battery_pct": round(g.battery_pct, 1)} if g and g.battery_pct is not None else None
        if key == "o":
            return {"type": "guest_overconsumption", "guest": "G5", "factor": 1.2}
        if key == "s":
            current = self.gov.mission
            return {"type": "priority_swap", "mission": next((f for f in self.files if f != current), self.files[0])}
        if key == "k":
            nxt = crew_levels[(crew_levels.index(sim.fsm.crew) + 1) % len(crew_levels)]
            return {"type": "crew_change", "crew": nxt}
        return None

    def poll(self) -> None:
        for key in self._keys():
            if key == "p":
                self.sim.paused = not self.sim.paused
                print(_c(f"  >> {'paused' if self.sim.paused else 'resumed'} at {self.sim.t_s / 60:.2f} min", BOLD, self.color))
            elif key in ("h", "?"):
                print(_c(KEYS, DIM, self.color))
            elif (e := self.event_for(key)) is not None:
                rec = self.sim.inject(e)
                self.injected.append(rec)
                detail = ", ".join(f"{k}={v}" for k, v in e.items() if k != "type")
                print(_c(f"  >> jury: {e['type']} ({detail}) injected at {self.sim.t_s / 60:.2f} min", BOLD, self.color))


def cmd_demo(args: argparse.Namespace) -> int:
    """Scenario B at demo pace under the first file, the other file's records beside it, then Scenario A."""
    color = not args.no_color
    inputs = load_inputs("scenario-b")
    files = [args.mission, args.swap_to]
    # The brief gives Scenario B 90 s: the pace follows from the minutes shown, unless --speed is forced.
    if args.speed is None:
        args.speed = args.until_min * 60 / args.seconds if args.seconds > 0 else 0.0
    pace = f"minutes 0-{args.until_min:g} in {args.seconds:g} s ({args.speed:.1f} ship-minutes per wall minute)" if args.speed else "flat out"
    print(_c(f"ArgOS demo: Scenario B ({inputs.scenario['location']['name']}, {inputs.scenario['location']['seawater_c']} °C), "
             f"guests {', '.join(inputs.scenario['guests'])}, priority file {files[0]} (then {files[1]}), {pace}", BOLD, color))
    if args.speed and sys.stdin.isatty():
        print(_c(KEYS, DIM, color))

    route = route_for(inputs, args)
    plan_id = args.route or inputs.scenario.get("plan")
    if plan_id:
        rs = RouteEnvironment.load(inputs.assumptions, plan_id).summary()
        print(_c(f"Route {rs['name']} ({rs['period']}, Open-Meteo, cached): seawater {rs['seawater_c'][0]:g}-{rs['seawater_c'][1]:g} °C, "
                 f"loop {rs['cooling_kw_min']:g}-{rs['cooling_kw_max']:g} kW, sea state to {rs['sea_state_max']}, gusts to {rs['gust_kn_max']:g} kn"
                 + ("; environment follows the data" if route else "; Scenario B keeps the brief's 24 °C (--env plan to follow the data)"), DIM, color))
    gov1 = Governor(inputs, files[0])
    sim1 = Simulator(inputs, seed=args.seed, mission=files[0], on_tick=gov1.on_tick, route=route)
    keys = KeyInjector(sim1, gov1, files, color) if args.speed else None

    def sink(s: dict | None) -> None:
        if keys:
            keys.poll()
        if s is None:
            return
        if s["t_s"] % 60 == 0 or any(e.get("injected") for e in s["events"]):
            print(fmt_tick(s))
        for d in s.get("decisions", []):
            if d["verdict"] != "armed":
                print(fmt_decision(d, color))
        for r in s.get("governor_log", []):
            print(_c(f"        priority file {r['result']}: " + (f"{r['from']} -> {r['to']}" if r["result"] == "swapped" else f"{r['field']}: {r['why']}; kept {r['kept']}"), BOLD, color))

    t0 = time.monotonic()
    try:
        h1 = sim1.run(args.until_min, realtime_factor=args.speed, sink=sink)
    finally:
        if keys:
            keys.close()
    print(_c(f"Scenario B shown in {time.monotonic() - t0:.0f} s wall time"
             + (f"; {len(keys.injected)} event(s) injected by the jury" if keys and keys.injected else "") + ".", DIM, color))
    print(_c(f"\nSame events under the {files[1]} file (replayed flat out, the jury's injections included):", BOLD, color))
    gov2 = Governor(inputs, files[1])
    sim2 = Simulator(inputs, seed=args.seed, mission=files[1], on_tick=gov2.on_tick, route=route)
    for e in (keys.injected if keys else []):
        if e["type"] != "priority_swap":
            sim2.events.append(dict(e))
    h2 = sim2.run(args.until_min)
    for key, d1, d2 in pair_decisions(gov1.decisions, gov2.decisions):
        line = f"{key[0] / 60:6.2f} min  {key[1]}"
        if d1:
            line += f"  {gov_file(d1)}: {d1.sentence}"
        if d2:
            line += f"\n             {gov_file(d2)}: {d2.sentence}"
        print(line)
    print(_c(f"\nrun hashes {h1} / {h2}; every decision inside its ceiling: "
             f"{all(d.within_ceiling for d in gov1.decisions + gov2.decisions)}", DIM, color))
    for sim, f in ((sim1, files[0]), (sim2, files[1])):
        write_jsonl(Path("runs") / f"demo_scenario_b_{f}.jsonl", sim)

    print(_c("\nScenario A: the jury's card.", BOLD, color))
    if args.no_prompt:
        d = admit("G4", ["G1", "G2", "G3"], files[0], route=plan_id)
        print_admission(d, color)
        return 0
    _flush_stdin()  # anything typed while Scenario B was playing must not become the first answer
    print(_c("Type: <card> <installed> <mission> [edits]. Example: G4 G1,G2,G3 sar   or   G4 G1,G2,G3 survey G4.hangar.mass_t=0.8", DIM, color))
    while True:
        try:
            line = input("card id or YAML path (blank = G4), installed (blank = G1,G2,G3), mission (blank = survey); q to quit\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.lower() in ("q", "quit", "exit"):
            return 0
        bits = [b.strip() for b in line.split()] + ["", "", ""]
        card, installed, mission = bits[0] or "G4", bits[1] or "G1,G2,G3", bits[2] or files[0]
        edits = _parse_edits([b for b in bits[3:] if "=" in b])
        try:
            path = card if card.endswith((".yaml", ".yml")) else None
            d = admit("" if path else card, installed.split(","), mission, edits, path, route=plan_id)
            print_admission(d, color)
        except Exception as e:  # a bad card or a typo must not end the demo
            print(f"refused: {e.__class__.__name__}: {str(e).splitlines()[0]}")


def cmd_route(args: argparse.Namespace) -> int:
    a, cards = load_assumptions(), load_cards()
    r = RouteEnvironment.load(a, args.plan)
    s = r.summary()
    print(f"{s['name']} ({s['plan']}), {s['period']}, {s['hours']} hours of hourly data; {s['source']}; {s['licence']}, fetched {s['fetched_at_utc']}")
    print(f"  seawater {s['seawater_c'][0]:g}-{s['seawater_c'][1]:g} °C (max at {s['seawater_max_at']}): chilled-water loop {s['cooling_kw_min']:g}-{s['cooling_kw_max']:g} kW"
          f" (brief judges at 30 °C: {cooling_at_30(a):g} kW)")
    print(f"  sea state to {s['sea_state_max']}, wind to {s['wind_kn_max']:g} kn, gusts to {s['gust_kn_max']:g} kn; envelope exceeded: "
          + ", ".join(k for k, v in s["envelope_exceeded"].items() if v) or "none")
    for gid in ([args.card] if args.card else sorted(cards)):
        for act in r.activity_windows(cards[gid]):
            lim = f"wind > {act['wind_kn_max']} kn" if act["wind_kn_max"] else ""
            lim += (" or " if lim and act["sea_state_max"] is not None else "") + (f"sea state > {act['sea_state_max']}" if act["sea_state_max"] is not None else "")
            print(f"  {gid} {act['activity']}: closed {act['closed_h']} h in {act['n_windows']} windows ({lim})" + (f"; e.g. plan hours {act['windows'][:3]}" if act["windows"] else ""))
    for h in (0, 24, 120, 240):
        c = r.at(h)
        print(f"  h{h:>4} {c['time_utc']} {c['waypoint']:>20}: {c['seawater_c']:g} °C, waves {c['wave_m']:g} m (sea state {c['sea_state']}), wind {c['wind_kn']:g} kn, gusts {c['gust_kn']:g} kn")
    return 0


def cooling_at_30(a: dict) -> float:
    from .ledger import cooling_capacity_kw
    return round(cooling_capacity_kw(a, a["envelope"]["judge_cooling_at_c"], False), 1)


def gov_file(d: Decision) -> str:
    return d.mission or "?"


def pair_decisions(a: list[Decision], b: list[Decision]) -> list[tuple]:
    """Match two runs' decisions by (time, kind) so the side-by-side stays aligned when one run has more."""
    def key(d):
        return (d.t_s, d.kind)
    da = {key(d): d for d in a if d.verdict != "armed"}
    db = {key(d): d for d in b if d.verdict != "armed"}
    return [(k, da.get(k), db.get(k)) for k in sorted(set(da) | set(db))]


def _flush_stdin() -> None:
    try:
        import termios
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except Exception:  # not a terminal (tests, pipes): nothing to flush
        pass


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
    s.add_argument("--env", choices=["scenario", "plan"], default="scenario", help="environment from the scenario's constants or from the plan's real data")
    s.add_argument("--route", help="mission plan id (config/plans/); default: the scenario's `plan`")
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
    ad.add_argument("--route", help="mission plan id (config/plans/): adds the real-data lines beside the verdict")
    ad.set_defaults(fn=cmd_admit)

    sim_a = load_assumptions()["sim"]
    d = sub.add_parser("demo", help="the live demo: 90 s of Scenario B under two files, then Scenario A")
    d.add_argument("--mission", default="survey")
    d.add_argument("--swap-to", default="sar")
    d.add_argument("--seed", type=int, default=1)
    d.add_argument("--until-min", type=float, default=sim_a["demo_until_min"], help="ship-minutes of Scenario B to show")
    d.add_argument("--seconds", type=float, default=sim_a["demo_seconds"], help="wall seconds for Scenario B (brief: 90)")
    d.add_argument("--speed", type=float, default=None, help="force a pace in ship-seconds per wall-second; 0 = flat out")
    d.add_argument("--no-prompt", action="store_true", help="run drill A1 instead of asking for a card")
    d.add_argument("--env", choices=["scenario", "plan"], default="scenario", help="Scenario B environment: the brief's constants or the plan's real data")
    d.add_argument("--route", help="mission plan id; default: the scenario's `plan`")
    d.set_defaults(fn=cmd_demo)

    rt = sub.add_parser("route", help="the environment along a mission plan from cached public data")
    rt.add_argument("plan", nargs="?", default="sicily_cable_survey")
    rt.add_argument("--card", help="also list when this card's weather-gated activities are closed")
    rt.set_defaults(fn=cmd_route)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
