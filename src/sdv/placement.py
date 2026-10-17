"""D2: where each part of each guest goes, by exhaustive enumeration (ceiling 30 s; takes milliseconds).

Positions come from `config/assumptions.yaml` (`positions`), slots a part may use from its card
(`allowed`, `preferred`). A placement maps `"G5.node" -> "bay2"`. Bay 1 is two 10-ft halves: a whole-bay
part excludes the halves and the halves hold one guest each; every other slot holds one guest, whose
parts may share it (the drone and its hangar on the flight deck). A guest with `needs_bay_clear` takes
Bay 1 alone even in a half. Each slot's own limits (tonnes, kilograms, mast area, the 150 kg hangar
limit for a drone, 2 kW of air cooling) are checked here; the ship-wide ledger lines are the
admission's job.

Declared objective: maximise the smallest remaining ledger margin, then the number of parts on their
preferred slot; ties by the sorted placement text so the answer is deterministic.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .ledger import envelope_kw

HALF_OF = {"bay1_half": "bay1"}  # a half slot counts against its bay's limits


def part_key(gid: str, part: dict) -> str:
    return f"{gid}.{part['name']}"


def parts_of(cards: dict, guests: list[str]) -> list[tuple[str, dict]]:
    return [(g, p) for g in guests for p in cards[g]["placement"]["parts"]]


@dataclass
class Rejection:
    part: str
    slot: str
    why: str

    def as_dict(self) -> dict:
        return {"part": self.part, "slot": self.slot, "why": self.why}


def slot_rejections(a: dict, cards: dict, placement: dict[str, str | None]) -> list[Rejection]:
    """Every reason this placement is invalid; empty means valid. Unplaced parts (None) are skipped."""
    pos = a["positions"]
    out: list[Rejection] = []
    by_slot: dict[str, list[tuple[str, dict]]] = {}
    for key, slot in placement.items():
        if slot is None:
            continue
        gid, name = key.split(".")
        part = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == name)
        if slot not in part["allowed"]:
            out.append(Rejection(key, slot, f"{slot} is not an allowed position for {key}"))
        by_slot.setdefault(slot, []).append((gid, part))

    def guests_in(slot):
        return {g for g, _ in by_slot.get(slot, [])}

    # occupancy
    for slot, items in by_slot.items():
        gids = {g for g, _ in items}
        limit = pos["bay1"]["halves"] if slot == "bay1_half" else 1
        if len(gids) > limit:
            out.append(Rejection(slot, slot, f"{slot} holds {limit} guest{'s' if limit > 1 else ''}, {len(gids)} placed: {', '.join(sorted(gids))}"))
    if guests_in("bay1") and guests_in("bay1_half"):
        out.append(Rejection("bay1", "bay1", f"Bay 1 wanted whole by {', '.join(sorted(guests_in('bay1')))} and in halves by {', '.join(sorted(guests_in('bay1_half')))}"))
    for gid in guests_in("bay1_half"):
        if cards[gid]["placement"].get("needs_bay_clear") and len(guests_in("bay1_half")) > 1:
            out.append(Rejection(f"{gid}", "bay1_half", f"{gid} needs the bay clear and shares Bay 1 with {', '.join(sorted(guests_in('bay1_half') - {gid}))}"))
    # per-position limits, halves counted against their bay
    loads: dict[str, list[tuple[str, dict]]] = {}
    for slot, items in by_slot.items():
        loads.setdefault(HALF_OF.get(slot, slot), []).extend(items)
    for position, items in loads.items():
        p = pos[position]
        t = sum(part["mass_t"] for _, part in items)
        if "max_t" in p and t > p["max_t"] + 1e-9:
            out.append(Rejection(position, position, f"{position} takes {p['max_t']} t, {t:g} t placed"))
        if "max_kg" in p and t * 1000 > p["max_kg"] + 1e-9:
            out.append(Rejection(position, position, f"{position} takes {p['max_kg']} kg, {t * 1000:g} kg placed"))
        if "area_m2" in p:
            area = sum(part.get("area_m2", 0) for _, part in items)
            if area > p["area_m2"] + 1e-9:
                out.append(Rejection(position, position, f"{position} has {p['area_m2']} m2, {area:g} m2 placed"))
        if "hangar_max_kg" in p:
            for gid, part in items:
                if part["name"] == "drone" and part["mass_t"] * 1000 > p["hangar_max_kg"] + 1e-9:
                    out.append(Rejection(f"{gid}.drone", position, f"hangar takes {p['hangar_max_kg']} kg, drone is {part['mass_t'] * 1000:g} kg"))
        if p.get("cooling") == "air":
            for gid, part in items:
                card = cards[gid]
                if card.get("cooling") == "air" and envelope_kw(a, card) > a["heat"]["air_cooled_max_kw"] + 1e-9:
                    out.append(Rejection(f"{gid}", position, f"{position} is air cooled to {a['heat']['air_cooled_max_kw']} kW, {gid} draws {envelope_kw(a, card):g} kW"))
    return out


def valid(a: dict, cards: dict, placement: dict) -> bool:
    return not slot_rejections(a, cards, placement)


def enumerate_placements(a: dict, cards: dict, guests: list[str], fixed: dict[str, str] | None = None,
                         movable: set[str] | None = None) -> list[dict[str, str]]:
    """All valid complete placements of `guests`. Parts in `fixed` stay put unless their guest is in
    `movable`; every other part ranges over its card's allowed slots."""
    fixed = fixed or {}
    movable = movable or set()
    keys, choices = [], []
    for gid, part in parts_of(cards, guests):
        k = part_key(gid, part)
        keys.append(k)
        choices.append([fixed[k]] if k in fixed and gid not in movable else list(part["allowed"]))
    out = []
    for combo in itertools.product(*choices):
        pl = dict(zip(keys, combo))
        if valid(a, cards, pl):
            out.append(pl)
    return out


def preferred_count(cards: dict, placement: dict) -> int:
    n = 0
    for key, slot in placement.items():
        gid, name = key.split(".")
        part = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == name)
        n += slot == part["preferred"][0]
    return n


def moves(placement: dict, current: dict) -> list[dict]:
    """Parts that left their current slot (in port: one crane move each, A.11)."""
    return [{"part": k, "from": current[k], "to": v} for k, v in placement.items() if k in current and current[k] is not None and current[k] != v]


def choose(a: dict, cards: dict, placements: list[dict], score) -> dict | None:
    """Best placement by (smallest margin, preferred parts, text); `score(placement)` gives the margin."""
    if not placements:
        return None
    return max(placements, key=lambda pl: (round(score(pl), 9), preferred_count(cards, pl), tuple(sorted(pl.items(), reverse=True))))


def place_as_given(a: dict, cards: dict, installed: dict[str, str], card_id: str) -> tuple[dict[str, str | None], list[Rejection]]:
    """The card's parts on their first free allowed slot, preferred first, installed guests untouched;
    a part with no free slot is left at None. Returns the placement and why each other slot was rejected."""
    placement: dict[str, str | None] = dict(installed)
    rejected: list[Rejection] = []
    for part in cards[card_id]["placement"]["parts"]:
        k = part_key(card_id, part)
        placement[k] = None
        for slot in part["allowed"]:
            trial = {**placement, k: slot}
            why = slot_rejections(a, cards, trial)
            if not why:
                placement[k] = slot
                break
            rejected.append(Rejection(k, slot, why[0].why))
    return placement, rejected


def default_installed(a: dict, cards: dict, guests: list[str]) -> dict[str, str]:
    """A plausible layout for the guests already aboard: each guest in id order on its first free slots."""
    placement: dict[str, str] = {}
    for gid in sorted(guests):
        pl, _ = place_as_given(a, cards, placement, gid)
        placement = {k: v for k, v in pl.items() if v is not None}
    return placement
