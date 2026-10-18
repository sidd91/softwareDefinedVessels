"""The sdv command.

    uv run sdv admit G4 --installed G1,G2,G3 [--mission survey] [--set G4.hangar.mass_t=0.8 | --set G4.consumes.power_kw.peak=40]
    uv run sdv admit G7 --card path/G7.yaml --installed G4,G5 --mission disaster_relief     a card handed over as a file
    uv run sdv run [--mission sar] [--log-dir runs/b-sar]        Scenario B through the loop, one line per decision
    uv run sdv run --safety 300:g3_hold_depth                    a 200 ms safety request after tick 300 (repeatable)
    uv run sdv replay runs/b-sar [--mission sar]                 the logs replayed and compared byte for byte
    uv run sdv kit plan|build|verify|install|rollback            the governor's computers and the Reference Kit
    uv run sdv demo [--port 8000] [--log-dir runs/live]          the screen on the live engine (the one demo command);
                                                                 every run it shows is logged for sdv replay

prints the D1 verdict with the binding line, every ledger line, the placement, the ranked yes-if options and the
one-genset-down check, and how long the decision took against its 30 s ceiling. A one-number edit is applied to
the card and the card is re-validated first; a bad edit is refused with the field named. A card file (--card, or
a path in place of the id) is loaded through the loader: a schema or vocabulary problem is refused with the field
named (exit 2); a card whose activities are not registered in config/signals.yaml is judged on its quantities,
positions and relations, and one line says so. A bad file in manifests/ is reported once at start and skipped.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import time
from pathlib import Path

from sdv import admission as Ad
from sdv import loader as Ld
from sdv import records as Rec

UNITS = {"t": "t", "t_eq": "t-eq", "kW": "kW", "kg": "kg", "m2": "m²", "Mbit/s": "Mbit/s", "cores": "cores"}


def _num(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 1e-9 else f"{int(round(x))}"


class EditError(ValueError):
    """A jury edit that cannot be applied at all (no such field, not a number): the field as typed and the reason.
    A schema problem with the edited card is not this; that is a card-rejected decision."""

    def __init__(self, field: str, reason: str):
        self.field, self.reason = field, reason
        super().__init__(f"{field}: {reason}")


# The power figures a card declares are the rungs of its mode ladder (G4: nominal 10, peak 35 and min 2 kW are the
# charge, fast_charge and standby modes). Editing one moves the rung that drew the old value with it, so the ladder
# follows the card: the envelope draw stays on a mode and the one-genset-down check throttles down a step the card has.
LADDER_RUNGS = ("nominal", "peak", "min")


SHOWN_MAX = 20      # an edit longer than this is never echoed back: "the value given" instead
FIELD_MAX = 40      # a field path longer than this is cut, as the door (sdv.loop) and the operations screen cut one
_DIGITS = re.compile(r"^\s*[+-]?\d+(_\d+)*\s*$")    # what int() reads as a whole number


def shown(raw: str, longest: int = SHOWN_MAX) -> str:
    """An edit as a message may echo it: as typed when short, else its first characters and an ellipsis."""
    return raw if len(raw) <= longest else raw[:longest - 3] + "..."


def _plain(text: str) -> bool:
    """Text the door would quote back whatever its length (sdv.loader.quotable): printable, no colon, semicolon,
    brace, quote or backslash."""
    return Ld.quotable(text, len(text))


def said_field(field: str) -> str | None:
    """A field path or card id as a message may name it, cut past FIELD_MAX, or None when the door would not quote it."""
    return shown(field, FIELD_MAX) if _plain(field) else None


def no_card(gid: str) -> str:
    said = said_field(gid)
    return f"no card {said}" if said else "no such card"


def _echo(target: str, raw: str) -> str:
    """The edit as sdv admit echoes it, " target=value" with each cut when long. A target or a value the door would
    not quote is left out."""
    said = said_field(target)
    if said is None:
        return ""
    return f" {said}={shown(raw)}" if _plain(raw) else f" {said}"


def _number(field: str, raw: str) -> int | float:
    said = repr(raw) if Ld.quotable(raw, SHOWN_MAX) else "the value given"     # the door's rule (sdv.loop._quoted)
    try:
        value = float(raw) if any(c in raw for c in ".eE") else int(raw)
    except ValueError:
        if _DIGITS.match(raw):
            # a whole number past Python's digit limit (4300 digits). Its sign, underscores and leading zeros do not
            # count: 0000...1 is 1. What is still past the limit is far beyond the largest a card may carry, so the
            # loader refuses it as it refuses a 400-digit one (above or below), never "not a number"
            text = raw.strip()
            negative = text.startswith("-")
            digits = text.lstrip("+-").replace("_", "").lstrip("0") or "0"
            if len(digits) <= sys.get_int_max_str_digits():
                return -int(digits) if negative else int(digits)
            return -sys.float_info.max if negative else sys.float_info.max
        raise EditError(field, f"{said} is not a number") from None
    if value != value or value in (float("inf"), float("-inf")):
        raise EditError(field, f"{said} is not a finite number")
    return value


def _child(node, key: str, field: str):
    """One step down a dotted path: a dict by key, a list by index (modes.0) or by the item's name (modes.full)."""
    if isinstance(node, list):
        if key.isdigit() and int(key) < len(node):
            return node[int(key)]
        named = [x for x in node if isinstance(x, dict) and x.get("name") == key]
        if named:
            return named[0]
    elif isinstance(node, dict) and key in node:
        return node[key]
    said = said_field(field)
    raise EditError(field, f"no field {said} on the card" if said else "the card has no such field")


def apply_edit(card: dict, field: str, raw: str) -> dict:
    """One number on a copy of the card. field is part.attr (hangar.mass_t) or a dotted path with list indices or
    names (consumes.power_kw.peak, modes.0.power_kw, modes.full.power_kw, placement.parts.hangar.mass_t). The field
    must exist and hold a number, and raw must be one; otherwise EditError names the field and the reason."""
    card = copy.deepcopy(card)
    value = _number(field, raw)
    keys = field.split(".")
    part = next((p for p in card["placement"]["parts"] if p["name"] == keys[0]), None)
    node = part if part is not None and len(keys) > 1 else card
    for k in (keys[1:-1] if node is part else keys[:-1]):
        node = _child(node, k, field)
    key = keys[-1]
    old = _child(node, key, field)
    if isinstance(old, bool) or not isinstance(old, (int, float)):
        raise EditError(field, f"{said_field(field) or 'the field given'} is not a number on the card")
    node[int(key) if isinstance(node, list) else key] = value
    if node is card["consumes"]["power_kw"] and key in LADDER_RUNGS:
        for m in card["modes"]:  # the ladder follows the card (LADDER_RUNGS)
            if abs(m["power_kw"] - old) < 1e-9:
                m["power_kw"] = value
    return card


def _card_file(args) -> str | None:
    """The card file to admit: --card, or the positional when it is a path rather than an id."""
    if args.card_file:
        return args.card_file
    if args.card and (Path(args.card).suffix in (".yaml", ".yml") or Path(args.card).is_file()):
        return args.card
    return None


def cmd_admit(args) -> int:
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    refused: list[Ld.LoadError] = []
    cards = Ld.load_cards(vocab=vocab, refused=refused)
    for err in refused:
        print(Ld.refusal(err))
    missions = Ld.load_missions(cards, vocab)
    if args.mission not in missions:
        print(f"refused: no priority file {args.mission!r} ({', '.join(sorted(missions))})")
        return 2
    installed = [g for g in (args.installed or "").split(",") if g]
    file, jury = _card_file(args), None
    if file:
        try:
            card = Ld.load_card(Path(file), vocab, allow_unregistered=True)
        except Ld.LoadError as err:
            print(Ld.refusal(err))
            return 2
        jury = card["id"]
        if args.card not in (None, file, jury):
            print(f"refused: {file} is card {jury}, not {args.card}")
            return 2
        cards[jury] = card
        print(f"loaded: {jury} from {file}, card validated")
        if jury not in vocab.activities:
            print(f"{jury} activities not registered: conditions not judged ({len(card.get('conditions', []))} on the card); "
                  "admitted on quantities, positions and relations")
    card_id = jury or args.card
    if not card_id:
        print("refused: no card given (an id such as G4, or --card path.yaml)")
        return 2
    for g in installed + [card_id]:
        if g not in cards:
            print(f"refused: no card {g}")
            return 2
    for edit in args.set or []:
        target, _, raw = edit.partition("=")
        gid, _, fld = target.partition(".")
        if gid not in cards:
            print(f"refused: edit{_echo(target, raw)}: {no_card(gid)}. Previous card kept.")
            return 2
        try:
            edited = apply_edit(cards[gid], fld, raw)
        except EditError as e:
            print(f"refused: {gid} edit{_echo(target, raw)}: {e.reason}. Previous card kept.")
            return 2
        problems = Ld.check_card(edited, vocab, Ld._schema(Ld.ROOT, "manifests/schema.json"), allow_unregistered=gid == jury)
        if problems:
            print(f"refused: {gid} edit{_echo(target, raw)}: {problems[0]}. Previous card kept.")
            return 2
        cards[gid] = edited
        print(f"edited: {shown(target, FIELD_MAX)} = {shown(raw)}, card re-validated")
    t0 = time.perf_counter()
    r = Ad.admit(A, cards, installed, card_id, missions[args.mission])
    ms = (time.perf_counter() - t0) * 1000
    b = r.binding
    rec = Rec.from_admission(r, seq=0, tick=0, card_id=card_id, installed=installed, mission=missions[args.mission], cards=cards)
    print(rec["sentence"])
    print(f"VERDICT {r.verdict.upper()} · {card_id} onto {', '.join(installed) or 'an empty ship'} · mission {args.mission}")
    print(f"BINDING {b.cls} {_num(b.demand)} / {_num(b.capacity)} {UNITS.get(b.unit, b.unit)}")
    print("LINES")
    for l in r.lines.values():
        state = "OVER" if l.over else "ok"
        print(f"  {l.cls:18} {_num(l.demand):>9} / {_num(l.capacity):<7} {UNITS.get(l.unit, l.unit):6} {state}")
    print("PLACEMENT " + ", ".join(f"{k} {v or 'none'}" for k, v in r.placement.items()))
    g = r.genset
    print(f"ONE GENSET DOWN load {_num(g.load_kw)} / reserve {_num(g.reserve_kw)} kW, gate {_num(g.gate_kw)} kW: {g.state.replace('_', ' ')}")
    for s in g.fix[: g.steps_needed]:
        print(f"  throttle {s.guest} {s.from_mode} to {s.to_mode}, frees {_num(s.frees_kw)} kW")
    if r.options:
        print("YES IF")
        for i, o in enumerate(r.options, 1):
            extra = f", moves {o.moves}" if o.moves else ""
            mc = " (mission critical)" if o.mission_critical else ""
            print(f"  {i}. remove {', '.join(o.remove)}{mc}: value lost {_num(o.value_lost)}, mass {_num(o.mass_after_t)} t{extra}")
    if r.seawater_tip_c is not None:
        print(f"SEAWATER TIP {_num(r.seawater_tip_c)} °C")
    print(f"TIME {ms:.1f} ms / 30 s")
    return 0


def _clock(t: float) -> str:
    return f"{int(t) // 60:02d}:{int(t) % 60:02d}"


def _safety_requests(specs: list[str]) -> dict[int, list[str]]:
    """--safety T:request, repeatable: the requests answered from the table of tick T, in the order given."""
    from sdv.safety import REQUESTS
    out: dict[int, list[str]] = {}
    for spec in specs:
        t, _, req = spec.partition(":")
        if not t.strip().isdigit():
            raise ValueError(f"safety request tick {t!r} is not a tick (0 or more)")
        if req not in REQUESTS:
            raise ValueError(f"no safety request {req!r} ({', '.join(REQUESTS)})")
        out.setdefault(int(t), []).append(req)
    return out


def cmd_run(args) -> int:
    from pathlib import Path

    from sdv import loop as L
    try:
        safety = _safety_requests(args.safety or [])
    except ValueError as e:
        print(f"refused: {e}")
        return 2
    late = [t for t in safety if t > args.until]
    if late:
        print(f"refused: safety request tick {late[0]} is after the last tick {args.until}")
        return 2
    sim = L.load_simulator(mission=args.mission, variant=args.variant)
    run = L.Loop(sim, args.mission, args.variant, inputs=L.scripted_inputs() if not args.no_script else {},
                 log_dir=Path(args.log_dir) if args.log_dir else None)
    print(f"RUN scenario_b · file {args.mission} · variant {args.variant} · simulator {sim.argos_label}")
    for out in run.ticks(until=args.until, pace=args.pace or None):
        records = list(out.records)
        for req in safety.get(out.tick, []):        # sent between ticks, as from the screen: logged with this tick
            records += run.safety(req, injected=True)
        for r in records:
            print(f"{_clock(r['t_s'])}  {r['kind']} {r['verdict'].upper():10} {r['sentence']}")
    run.close()
    worst = max(run.core.timing, key=lambda t: t["latency_ms"] / t["ceiling_ms"], default=None)
    if worst:
        print(f"TIME worst {worst['kind']} {worst['latency_ms']:.2f} ms / {worst['ceiling_ms']:.0f} ms")
    if args.log_dir:
        print(f"LOGS {args.log_dir}: frames, inputs, snapshots, decisions, timing")
    return 0


def cmd_replay(args) -> int:
    from pathlib import Path

    from sdv import loop as L
    d = Path(args.log_dir)
    snaps, recs = L.replay(d, args.mission, args.variant)
    a = L.first_difference(d.joinpath("snapshots.jsonl").read_text().splitlines(), snaps)
    b = L.first_difference(d.joinpath("decisions.jsonl").read_text().splitlines(), recs)
    if a or b:
        print(f"REPLAY DIFFERS snapshots {a or 'equal'} · decisions {b or 'equal'}")
        return 1
    print(f"REPLAY EQUAL {len(snaps)} snapshots, {len(recs)} records, byte for byte")
    return 0


def cmd_kit(args) -> int:
    from pathlib import Path

    from sdv import kit as K
    A = Ld.load_assumptions()
    if args.action == "plan":
        print(f"HULL {A['hull']['loa_m']} m · {K.governor_boards(A)} governor boards")
        for d in K.devices(A):
            size = f"{d['storage_gb']} GB" if d["storage_gb"] else "paper"
            print(f"  {d['id']:26} {d['kind']:6} {d['site']:24} {size:>8}  {d['role']}")
        return 0
    if args.action == "build":
        try:
            m = K.build(Path(args.path or "dist/kit"))
        except ValueError as e:
            print(f"REFUSED {e}")
            return 1
        print(f"BUILT {args.path or 'dist/kit'}: {len(m['files'])} files, {m['bytes'] / 1e6:.2f} MB, commit {m['commit']}")
        for d in m["placement"]:
            print(f"  {d['id']:26} {d['holds']}")
        return 0
    if args.action == "verify":
        problems = K.verify(Path(args.path))
        print("VERIFIED every file against the manifest" if not problems else "FAILED " + "; ".join(problems[:5]))
        return 1 if problems else 0
    if args.action == "install":
        r = K.install(Path(args.path), Path(args.root))
        if not r["installed"]:
            print(f"REFUSED kit kept {r['kept']}: " + "; ".join(r["problems"][:5]))
            return 1
        print(f"INSTALLED commit {r['commit']} in {r['slot']}, rollback {r['rollback'] or 'none'}")
        return 0
    if args.action == "rollback":
        slot = K.rollback(Path(args.root))
        print(f"ROLLED BACK to {slot}" if slot else "NOTHING to roll back to")
        return 0 if slot else 1
    return 2


def cmd_demo(args) -> int:
    """The one demo command: the decision engine and the screen, Scenario B on the live tick loop. Every live run
    the screen shows (and each re-run after a jump back or RESTART) is logged under --log-dir for `sdv replay`."""
    from pathlib import Path

    from sdv.ui import server
    print(f"ArgOS screen on http://{args.host}:{args.port}/ ({args.source}); Ctrl+C stops it")
    server.run(args.host, args.port, args.source, Path(args.log_dir) if args.source == "live" else None)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdv", description="ArgOS resource governor")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("admit", help="D1: can this card come aboard?")
    a.add_argument("card", nargs="?", help="a loaded card's id (G4), or the path of a card file")
    a.add_argument("--card", dest="card_file", metavar="path.yaml", help="a card handed over as a file, judged by its id")
    a.add_argument("--installed", default="")
    a.add_argument("--mission", default="survey")
    a.add_argument("--set", action="append", metavar="Gx.part.field=value")
    a.set_defaults(func=cmd_admit)
    r = sub.add_parser("run", help="Scenario B through the tick loop: every decision with its sentence")
    r.add_argument("--mission", default="survey")
    r.add_argument("--variant", default="default")
    r.add_argument("--until", type=int, default=1200, help="last tick (ship seconds)")
    r.add_argument("--pace", type=float, default=0, help="ticks per wall second (12 for the demo); 0 runs unpaced")
    r.add_argument("--log-dir", help="write the frame, input, snapshot, decision and timing logs here")
    r.add_argument("--no-script", action="store_true", help="no scripted laptop inputs (nobody answers the bridge)")
    r.add_argument("--safety", action="append", metavar="T:request",
                   help="a 200 ms safety request answered from tick T's table (r3_hold_landing, g3_hold_depth, g2_stop_winch, g4_return_home)")
    r.set_defaults(func=cmd_run)
    p2 = sub.add_parser("replay", help="re-run a logged run from its frame and input logs and compare")
    p2.add_argument("log_dir")
    p2.add_argument("--mission", default="survey")
    p2.add_argument("--variant", default="default")
    p2.set_defaults(func=cmd_replay)
    dm = sub.add_parser("demo", help="the ArgOS screen on the live engine: Scenario B, the jury's card, the profile builder")
    dm.add_argument("--host", default="127.0.0.1")
    dm.add_argument("--port", type=int, default=8000)
    dm.add_argument("--source", choices=["live", "fixtures"], default="live", help="live tick loop (default) or the recorded fixtures")
    dm.add_argument("--log-dir", default="runs/live",
                    help="live runs are logged here, one directory per run (live-<file>-<n>), replayed with sdv replay")
    dm.set_defaults(func=cmd_demo)
    k = sub.add_parser("kit", help="the governor's computers and the Deployment Reference Kit")
    k.add_argument("action", choices=["plan", "build", "verify", "install", "rollback"])
    k.add_argument("path", nargs="?", help="kit directory (build: output, default dist/kit)")
    k.add_argument("--root", default="kit_slots", help="install and rollback: the device's kit root")
    k.set_defaults(func=cmd_kit)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
