"""D1 admission: can a guest card come aboard, and if not, what must give way.

Judged at the mission envelope (both gensets, the envelope reserve, cooling at 30 C seawater, brief A.10) on the
ledger's admission view, with D2 placement. Then the one-genset-down check of WORKLOG DEC-35: the raw line
against the one-genset reserve is always reported; the verdict needs the load to fit the gate
min(reserve, cooling at 30 C) - 5 kW, either as it is or by throttle-only steps from the ladder (interruptible,
capability kept above 0, mission-critical last). If neither, the verdict becomes YES-IF.

Verdicts: YES; YES-IF with the minimal removal sets ranked by mission value lost, then size, then id, with
mission-critical guests last; NO when no removal set works. The binding line is the most-over line, or for YES
the tightest ship-wide line (mass, stability, power, heat, the two mission lines); slot limits such as the mast
and the flight-deck drone are placement detail and bind only when over.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from sdv import ledger as Lg
from sdv.placement import moves, place

SHIP_WIDE = ("mass", "stability", "power", "heat", "line_port", "line_stbd")


@dataclass
class GensetCheck:
    load_kw: float
    reserve_kw: float
    gate_kw: float
    holds: bool                     # the raw line: load within the one-genset reserve
    state: str                      # fits, holds_by_throttling, does_not_hold
    fix: list = field(default_factory=list)       # each guest's first step down, in ladder order
    steps_needed: int = 0


@dataclass
class Option:
    remove: list
    value_lost: float
    mission_critical: bool
    mass_after_t: float
    stability_after_t_eq: float
    placement: dict
    moves: dict
    genset: GensetCheck
    seawater_tip_c: float | None


@dataclass
class Admission:
    verdict: str
    binding: Lg.Line | None
    over: list
    lines: dict
    placement: dict
    unplaced: list
    genset: GensetCheck
    seawater_tip_c: float | None
    options: list


def tipping_point_c(A: dict, chilled_kw: float) -> float | None:
    """Seawater temperature at which the chilled-water capacity falls to this load (linear A.2 law)."""
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    if chilled_kw >= c0:
        return None
    return t0 + (c0 - chilled_kw) * (t1 - t0) / (c0 - c1)


def genset_check(A: dict, cards: dict, guests: list[str], mission: dict) -> GensetCheck:
    load = sum(Lg.envelope_kw(A, cards[g]) for g in guests)
    reserve = A["power"]["guest_reserve_kw"]["one_genset_down"]
    gate = min(reserve, Lg.heat_capacity_kw(A, A["envelope"]["judge_cooling_at_c"])) - A["power"]["shed_headroom_kw"]
    modes = {g: Lg.envelope_mode(A, cards[g]) for g in guests}
    first = [s for s in (Lg.next_step(cards, g, m, mission) for g, m in modes.items()) if s]
    first.sort(key=lambda s: s.order_key)
    check = GensetCheck(load, reserve, gate, load <= reserve + 1e-9, "fits")
    if load <= gate + 1e-9:
        return check
    check.fix = first
    running = load
    for i, s in enumerate(first):
        if s.shed or s.capability_lost >= 1.0:
            break
        running -= s.frees_kw
        if running <= gate + 1e-9:
            check.state, check.steps_needed = "holds_by_throttling", i + 1
            return check
    check.state = "does_not_hold"
    return check


def _evaluate(A, cards, guests, mission, current):
    placement = place(A, cards, guests, current)
    lines = Lg.admission_lines(A, cards, guests, placement)
    unplaced = [k for k, v in placement.items() if v is None]
    over = sorted((l for l in lines.values() if l.over), key=lambda l: l.margin)
    return placement, lines, unplaced, over


def _ok(over, unplaced, genset):
    return not over and not unplaced and genset.state != "does_not_hold"


def admit(A: dict, cards: dict, installed: list[str], card_id: str, mission: dict,
          current: dict | None = None) -> Admission:
    """Admit card_id onto a ship carrying installed, under the given priority file."""
    guests = installed + [card_id]
    if current is None:
        current = place(A, cards, installed)
    placement, lines, unplaced, over = _evaluate(A, cards, guests, mission, current)
    genset = genset_check(A, cards, guests, mission)
    chilled = lines["heat"].demand
    tip = tipping_point_c(A, chilled)
    if _ok(over, unplaced, genset):
        binding = min((lines[c] for c in SHIP_WIDE if c in lines), key=lambda l: l.margin)
        return Admission("yes", binding, [], lines, placement, [], genset, tip, [])
    options = []
    weights = mission["weights"]
    for size in range(1, len(installed) + 1):
        for remove in itertools.combinations(installed, size):
            if any(set(o.remove) <= set(remove) for o in options):
                continue  # minimal sets only
            kept = [g for g in guests if g not in remove]
            p2, l2, u2, o2 = _evaluate(A, cards, kept, mission, current)
            g2 = genset_check(A, cards, kept, mission)
            if not _ok(o2, u2, g2):
                continue
            value = sum(weights.get(cards[g]["capability"]["name"], 0.0) for g in remove)
            options.append(Option(sorted(remove), value, any(g in mission["mission_critical"] for g in remove),
                                  l2["mass"].demand, l2["stability"].demand, p2,
                                  moves({k: v for k, v in current.items() if k.split(".")[0] in kept}, p2),
                                  g2, tipping_point_c(A, l2["heat"].demand)))
    options.sort(key=lambda o: (o.mission_critical, round(o.value_lost, 9), len(o.remove), o.remove))
    binding = over[0] if over else None
    return Admission("yes-if" if options else "no", binding, over, lines, placement, unplaced, genset, tip, options)
