"""D2 placement: put every part of every guest into an allowed position, by enumeration.

Positions and their capacity come from config/assumptions.yaml: Bay 1 has two halves (a whole-bay part takes
both), Bay 2 one, the flight deck holds one guest's drone and hangar, the free mast slot and the hangar roof one
part each. A part with part_of rides with its parent part. A guest with needs_bay_clear may not share a bay.
Bay tonnage limits hold. Mast and roof weight, area and air-cooling limits are ledger lines (src/sdv/ledger.py),
so a breach shows as a binding line with numbers rather than as a missing placement.

Among feasible layouts the rule is lexicographic (WORKLOG DEC-37 port moves; CON-18 stays open for a fuller D2
objective): an installed part is never left without a position (it may move); then most parts placed, fewest
installed parts moved, most parts in a preferred position, then a fixed order. Six guests and six positions give a few thousand layouts at most.
"""
from __future__ import annotations

import itertools

HALF_USE = {"bay1": ("bay1", 2), "bay1_half": ("bay1", 1), "bay2": ("bay2", 1)}


def _parts(cards: dict, guests: list[str]) -> list[tuple[str, dict]]:
    return [(g, p) for g in guests for p in cards[g]["placement"]["parts"]]


def _feasible(A: dict, cards: dict, assign: dict[str, str | None]) -> bool:
    halves = {b: A["positions"][b]["halves"] for b in ("bay1", "bay2")}
    used = {"bay1": 0, "bay2": 0}
    tonnes = {"bay1": 0.0, "bay2": 0.0}
    occupants = {"bay1": set(), "bay2": set()}
    single = {"mast_free": None, "hangar_roof": None}
    deck_guest = None
    for key, slot in assign.items():
        if slot is None:
            continue
        g, name = key.split(".")
        part = next(p for p in cards[g]["placement"]["parts"] if p["name"] == name)
        if part.get("part_of"):
            continue  # rides with its parent; checked below
        if slot in HALF_USE:
            bay, n = HALF_USE[slot]
            used[bay] += n
            tonnes[bay] += part["mass_t"] + sum(c["mass_t"] for c in cards[g]["placement"]["parts"] if c.get("part_of") == name)
            occupants[bay].add(g)
        elif slot in single:
            if single[slot] is not None:
                return False
            single[slot] = key
        elif slot == "flight_deck":
            if deck_guest not in (None, g):
                return False
            deck_guest = g
    for bay in used:
        if used[bay] > halves[bay] or tonnes[bay] > A["positions"][bay]["max_t"] + 1e-9:
            return False
        if len(occupants[bay]) > 1 and any(cards[g]["placement"].get("needs_bay_clear") for g in occupants[bay]):
            return False
    for key, slot in assign.items():
        g, name = key.split(".")
        part = next(p for p in cards[g]["placement"]["parts"] if p["name"] == name)
        if part.get("part_of") and assign.get(f"{g}.{part['part_of']}") != slot:
            return False
    return True


def place(A: dict, cards: dict, guests: list[str], current: dict | None = None) -> dict[str, str | None]:
    """The best layout for these guests; a part with no feasible position is None."""
    current = current or {}
    parts = _parts(cards, guests)
    keys = [f"{g}.{p['name']}" for g, p in parts]
    options = []
    for g, p in parts:
        order = list(dict.fromkeys(p["preferred"] + p["allowed"]))
        options.append(order + [None])
    best, best_score = None, None
    for combo in itertools.product(*options):
        assign = dict(zip(keys, combo))
        if not _feasible(A, cards, assign):
            continue
        unplaced = sum(1 for s in combo if s is None)
        unplaced_installed = sum(1 for k, s in assign.items() if s is None and current.get(k) is not None)
        moved = sum(1 for k, s in assign.items() if k in current and current[k] is not None and s != current[k])
        not_preferred = sum(1 for (g, p), s in zip(parts, combo) if s is not None and s not in p["preferred"])
        rank = tuple(opts.index(s) for opts, s in zip(options, combo))
        score = (unplaced_installed, unplaced, moved, not_preferred, rank)
        if best_score is None or score < best_score:
            best, best_score = assign, score
    return best


def moves(before: dict, after: dict) -> dict[str, str]:
    """Installed parts that change position, ignoring parts that ride with a parent."""
    return {k: v for k, v in after.items() if k in before and before[k] is not None and v != before[k]}
