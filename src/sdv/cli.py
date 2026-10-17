"""The sdv command.

    uv run sdv admit G4 --installed G1,G2,G3 [--mission survey] [--set G4.hangar.mass_t=0.8]

prints the D1 verdict with the binding line, every ledger line, the placement, the ranked yes-if options and the
one-genset-down check, and how long the decision took against its 30 s ceiling. A one-number edit is applied to
the card and the card is re-validated first; a bad edit is refused with the field named.
"""
from __future__ import annotations

import argparse
import copy
import sys
import time

from sdv import admission as Ad
from sdv import loader as Ld
from sdv import records as Rec

UNITS = {"t": "t", "t_eq": "t-eq", "kW": "kW", "kg": "kg", "m2": "m²"}


def _num(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".") if abs(x - round(x)) > 1e-9 else f"{int(round(x))}"


def apply_edit(card: dict, field: str, raw: str) -> dict:
    """field is part.attr (for example hangar.mass_t) or a top-level dotted path on the card."""
    card = copy.deepcopy(card)
    value: object = raw
    try:
        value = float(raw) if any(c in raw for c in ".eE") else int(raw)
    except ValueError:
        pass
    head, _, rest = field.partition(".")
    part = next((p for p in card["placement"]["parts"] if p["name"] == head), None)
    if part is not None and rest:
        part[rest] = value
        return card
    node = card
    keys = field.split(".")
    for k in keys[:-1]:
        node = node[k]
    node[keys[-1]] = value
    return card


def cmd_admit(args) -> int:
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    cards = Ld.load_cards(vocab=vocab)
    missions = Ld.load_missions(cards, vocab)
    if args.mission not in missions:
        print(f"refused: no priority file {args.mission!r} ({', '.join(sorted(missions))})")
        return 2
    installed = [g for g in (args.installed or "").split(",") if g]
    for g in installed + [args.card]:
        if g not in cards:
            print(f"refused: no card {g}")
            return 2
    for edit in args.set or []:
        target, _, raw = edit.partition("=")
        gid, _, fld = target.partition(".")
        edited = apply_edit(cards[gid], fld, raw)
        problems = Ld.check_card(edited, vocab, Ld._schema(Ld.ROOT, "manifests/schema.json"))
        if problems:
            print(f"refused: {gid} edit {target}={raw}: {problems[0]}. Previous card kept.")
            return 2
        cards[gid] = edited
        print(f"edited: {target} = {raw}, card re-validated")
    t0 = time.perf_counter()
    r = Ad.admit(A, cards, installed, args.card, missions[args.mission])
    ms = (time.perf_counter() - t0) * 1000
    b = r.binding
    rec = Rec.from_admission(r, seq=0, tick=0, card_id=args.card, installed=installed, mission=missions[args.mission], cards=cards)
    print(rec["sentence"])
    print(f"VERDICT {r.verdict.upper()} · {args.card} onto {', '.join(installed) or 'an empty ship'} · mission {args.mission}")
    print(f"BINDING {b.cls} {_num(b.demand)} / {_num(b.capacity)} {UNITS.get(b.unit, b.unit)}")
    print("LINES")
    for l in r.lines.values():
        state = "OVER" if l.over else "ok"
        print(f"  {l.cls:18} {_num(l.demand):>9} / {_num(l.capacity):<7} {UNITS.get(l.unit, l.unit):5} {state}")
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdv", description="ArgOS resource governor")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("admit", help="D1: can this card come aboard?")
    a.add_argument("card")
    a.add_argument("--installed", default="")
    a.add_argument("--mission", default="survey")
    a.add_argument("--set", action="append", metavar="Gx.part.field=value")
    a.set_defaults(func=cmd_admit)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
