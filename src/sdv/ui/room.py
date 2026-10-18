"""The room map's data (the /room page): each position aboard as a cell, what is there, what is free under its
limit, and how it may change (as built, in port with a crane, at sea in a window).

    GET /api/room?mission=survey&t=722              one moment of the run (the reference run live, the fixture replay otherwise)
    GET /api/room?case=A5-survey&edit=…&keep=…      a Scenario A case at the pier with the jury's edits, the card held over the
                                                    slot D2 gives it; 422 {refused} for an edit that cannot apply, as /api/admit

Every number is derived from the snapshot (the guests aboard, at sea or alongside) plus config/assumptions.yaml and the
cards, through the engine's own helpers: D2 placement (view._placement, sdv.placement) and view.admit for the pier, so a
slot limit on screen is the one the engine judges against. The page overlays the live modes, activities and the eight
budgets it already receives on /ws onto these cells; nothing is added to the /ws payload or to /api/state.
"""
from __future__ import annotations

import copy

from sdv import loader as Ld
from sdv.ui import view
from sdv.ui.data import Inputs, Moment

SHORT = {"G1": "radio sensor", "G2": "ocean module", "G3": "survey vehicle", "G4": "rescue drone", "G5": "comms node",
         "G6": "desal unit"}
NATIVE_SHORT = {"navigation radar": "radar", "satellite terminal": "SATCOM"}
ORDER = ("mast_free", "bay2", "bay1", "flight_deck", "hangar_roof", "stern_ramp")
WHERE = {"mast_free": "Mast", "bay2": "Bay 2 · 10 ft", "bay1": "Bay 1 · 20 ft", "flight_deck": "Flight deck",
         "hangar_roof": "Hangar roof", "stern_ramp": "Stern ramp"}
# Provenance keys whose `source` names the brief section (or "assumed") behind each budget shown on the page.
SOURCE_KEYS = {"power": "power.guest_reserve_kw", "heat": "heat", "positions": "positions.bay1", "mass": "mass", "data": "data",
               "ship_state": "ship_state", "compute": "compute", "response": "response_time_s", "installation": "installation",
               "headroom": "power.shed_headroom_kw", "hangar_roof": "positions.hangar_roof", "envelope": "envelope"}


def _rng(v) -> str:
    return f"{v[0]}–{v[1]}" if isinstance(v, (list, tuple)) else str(v)


def _kg(t: float) -> float:
    return round(t * 1000, 1)


def _r(x: float, nd: int = 3) -> float:
    return round(x + 0.0, nd)


def sources(A: dict) -> dict:
    """Where each budget's numbers come from, as the provenance block states it (brief section or assumed)."""
    prov = A.get("provenance", {})
    return {k: prov.get(key, {}).get("source", "assumed") for k, key in SOURCE_KEYS.items()}


def as_built(A: dict) -> dict:
    """What never changes: the plant and the hull's budgets."""
    g = A["power"]["gensets"]
    heat = sorted(A["heat"]["capacity_kw_at"].items())
    lines = A["power"]["mission_line_kw"]
    return {
        "gensets": f"{g['count']} × {g['rating_kw']} kW",
        "loop": f"{heat[0][1]} → {heat[1][1]} kW · {heat[0][0]} → {heat[1][0]} °C",
        "loop_degraded_factor": A["heat"]["degraded_factor"],
        "lines": " + ".join(f"{int(v)}" for v in lines.values()) + " kW",
        "mass_t": A["mass"]["margin_t"], "stability_t_eq": A["mass"]["stability_budget_t_eq"],
        "headroom_kw": A["power"]["shed_headroom_kw"],
        "reserve_kw": {**A["power"]["guest_reserve_kw_by_speed"], "one_genset_down": A["power"]["guest_reserve_kw"]["one_genset_down"]},
        "mast_natives": list(A["positions"]["mast_occupied"]),
        "trip_signals": len(A["power"]["trip_confirm"]["signals"]), "trip_needed": A["power"]["trip_confirm"]["needed"],
        "judge_cooling_at_c": A["envelope"]["judge_cooling_at_c"], "envelope_seawater_c": list(A["envelope"]["seawater_c"]),
    }


def window(A: dict) -> str:
    """A.11's at-sea installation window, the one condition set every sea-mutable position shares."""
    sea = A["installation"]["at_sea_crewed"]
    w = sea["window"]
    return (f"at-sea window: sea state ≤ {w['sea_state_max']}, wind ≤ {w['wind_kn_max']} kn, {_rng(w['speed_kn'])} kn, course {w['course']}, "
            f"deck {w['deck']}, survey vehicle not listening · ≤ {sea['max_kg']} kg via {' or '.join(v.replace('_', ' ') for v in sea['via'])}")


def mutability(A: dict, slot: str) -> tuple[str, str]:
    """A position's class and rule: sea-mutable when A.11's at-sea installation comes through it (a window), else
    port-mutable (a crane alongside). Modes and the mission profile change at sea; the plant never changes."""
    inst = A["installation"]
    port, sea = inst["in_port"], inst["at_sea_crewed"]
    if slot in sea["via"]:
        if slot == "flight_deck":
            return "sea", f"changes at sea in a window · drone swap {sea['minutes']['drone_swap']} min, {sea['people']['flight_deck']} people"
        return "sea", f"changes at sea in a window · vehicle swap {sea['minutes']['vehicle_swap']} min, {sea['people']['stern_ramp']} people"
    if slot == "mast_free":
        return "port", f"changes in port · crane alongside · {_rng(port['hours_per_mast_guest'])} h"
    if slot == "hangar_roof":
        return "port", "changes in port · rides with its node, no at-sea rule"
    return "port", f"changes in port · crane {port['crane_t']} t alongside · {_rng(port['hours_per_bay_guest'])} h"


def _part(cards: dict, gid: str, name: str) -> dict:
    return next(p for p in cards[gid]["placement"]["parts"] if p["name"] == name)


def _by_slot(cards: dict, placement: dict) -> dict[str, list[tuple[str, dict, str]]]:
    """slot -> [(guest, part, slot as placed)], Bay 1's halves folded into bay1."""
    out: dict[str, list] = {}
    for key, slot in placement.items():
        if slot is None:
            continue
        gid, name = key.split(".")
        out.setdefault("bay1" if slot == "bay1_half" else slot, []).append((gid, _part(cards, gid, name), slot))
    return out


def _who(cards: dict, gid: str, parts: list[dict]) -> tuple[str, str]:
    """"G5 comms node" where the guest's main part sits; a secondary part placed on its own is named ("G5 antenna")."""
    first = cards[gid]["placement"]["parts"][0]["name"]
    if all(p["name"] != first for p in parts):
        return f"{gid} {parts[0]['name']}", cards[gid]["name"]
    return f"{gid} {SHORT.get(gid, cards[gid]['name'].lower())}", cards[gid]["name"]


def _cell(I: Inputs, cards: dict, slot: str, on: list, situation: str, held: str | None) -> dict:
    A = I.A
    pos = A["positions"]
    cls, rule = mutability(A, slot)
    guests = sorted({g for g, _, _ in on})
    parts_of = {g: [p for gg, p, _ in on if gg == g] for g in guests}
    c = {"id": slot, "where": WHERE[slot], "mutability": cls, "rule": rule, "rule_detail": window(A) if cls == "sea" else "",
         "guests": guests, "held": held in guests,
         "port_only": cls == "port" and situation != "alongside", "parts": {},
         # the guests whose main part sits here: their mode and draw belong to this cell, not to a secondary part's
         "primary": [g for g in guests if any(p["name"] == cards[g]["placement"]["parts"][0]["name"] for p in parts_of[g])]}
    for g in guests:
        c["parts"][g] = [{"name": p["name"], "mass_t": p["mass_t"], "slot": s} for gg, p, s in on if gg == g]
    if guests:
        c["who"], c["who_title"] = _who(cards, guests[0], parts_of[guests[0]])
        if len(guests) > 1:
            c["who"] += " + " + " + ".join(_who(cards, g, parts_of[g])[0] for g in guests[1:])
    else:
        c["who"], c["who_title"] = "free", ""
    if slot == "mast_free":
        p = pos["mast_free"]
        natives = list(pos["mast_occupied"])
        part = on[0][1] if on else None
        used = len(natives) + (1 if part else 0)
        c.update(tag="3 slots", line=p["power_line"], cooling=p["cooling"], natives=[NATIVE_SHORT.get(n, n) for n in natives],
                 limits={"slots_total": 3, "slots_used": used, "slots_free": 3 - used, "max_kg": p["max_kg"], "area_m2": p["area_m2"],
                         "mass_kg": _kg(part["mass_t"]) if part else 0.0, "part_area_m2": part.get("area_m2") if part else None,
                         "air_cooled_max_kw": A["heat"]["air_cooled_max_kw"]})
        what = f"{_kg(part['mass_t']):g} of {p['max_kg']} kg" if part else f"slot free · {p['max_kg']} kg"
        if part and part.get("area_m2") is not None:
            what += f" · {part['area_m2']} of {p['area_m2']} m²"
        what += " · air cooled"
        c.update(what=what, free_k="free slots", free_v=str(3 - used), free_n=3 - used, free_unit="slots")
    elif slot in ("bay1", "bay2"):
        p = pos[slot]
        tonnes = sum(x["mass_t"] for _, x, _ in on)
        halves_used = sum(p["halves"] if s == slot else 1 for g, x, s in on if not x.get("part_of"))
        halves_used = min(halves_used, p["halves"])
        free_t = _r(p["max_t"] - tonnes)
        c.update(tag=f"{p['power_line']} line", line=p["power_line"], cooling=p["cooling"],
                 limits={"max_t": p["max_t"], "mass_t": _r(tonnes), "free_t": free_t, "halves": p["halves"],
                         "halves_used": halves_used, "halves_free": p["halves"] - halves_used})
        pieces = " + ".join(f"{x['name']} {x['mass_t']:.1f}" for _, x, _ in on)
        what = (f"{tonnes:.1f} of {p['max_t']} t" + (f" · {pieces}" if len(on) > 1 else "")) if on else f"{p['max_t']} t · {p['halves']} half" + ("ves" if p["halves"] > 1 else "")
        if on and any(s == "bay1_half" for _, _, s in on):
            what += " · one half"
        halves_free = p["halves"] - halves_used
        free_v = (f"{halves_free} half · " if halves_free else "") + f"{free_t:.1f} t under limit"
        c.update(what=what, free_k="free", free_v=free_v, free_n=free_t, free_unit="t")
    elif slot == "flight_deck":
        p = pos["flight_deck"]
        drone = next((x for _, x, _ in on if x["name"] == "drone"), None)
        hangar = next((x for _, x, _ in on if x["name"] == "hangar"), None)
        drone_kg = _kg(drone["mass_t"]) if drone else 0.0
        c.update(tag=f"{p['power_line']} line", line=p["power_line"], cooling=p["cooling"],
                 limits={"hangar_max_kg": p["hangar_max_kg"], "drone_kg": drone_kg, "free_kg": _r(p["hangar_max_kg"] - drone_kg, 1),
                         "hangar_t": hangar["mass_t"] if hangar else 0.0, "area_m": list(p["area_m"])})
        if drone:
            what = (f"hangar {hangar['mass_t']:.2f} t · " if hangar else "") + f"drone {drone_kg:g} of {p['hangar_max_kg']} kg"
        else:
            what = f"{p['area_m'][0]} × {p['area_m'][1]} m · hangar drone ≤ {p['hangar_max_kg']} kg"
        c.update(what=what, free_k="free", free_v=f"{_r(p['hangar_max_kg'] - drone_kg, 1):g} kg under hangar limit" if drone else "whole deck",
                 free_n=_r(p["hangar_max_kg"] - drone_kg, 1), free_unit="kg")
    elif slot == "hangar_roof":
        p = pos["hangar_roof"]
        part = on[0][1] if on else None
        kg = _kg(part["mass_t"]) if part else 0.0
        mult = A["mass"]["multiplier"]["hangar_roof"]
        c.update(tag=f"×{mult:g}", line=p["power_line"], cooling=p["cooling"],
                 limits={"max_kg": p["max_kg"], "mass_kg": kg, "free_kg": _r(p["max_kg"] - kg, 1), "multiplier": mult})
        c.update(what=(f"{kg:g} of {p['max_kg']} kg" if part else f"{p['max_kg']} kg") + f" · stability ×{mult:g}",
                 free_k="free", free_v=f"{_r(p['max_kg'] - kg, 1):g} kg", free_n=_r(p["max_kg"] - kg, 1), free_unit="kg")
    else:  # stern ramp: a launch and recovery point, held by no guest
        p = pos["stern_ramp"]
        c.update(tag=f"{_rng(p['craft_len_m'])} m", line=None, cooling=None,
                 limits={"max_t": p["max_t"], "craft_len_m": list(p["craft_len_m"])}, users=[],
                 what=f"one craft ≤ {p['max_t']} t · {_rng(p['craft_len_m'])} m", free_k="excludes", free_v="flight deck ops",
                 free_n=None, free_unit="")
    return c


def cells(I: Inputs, cards: dict, guests: list[str], placement: dict, situation: str, held: str | None = None) -> list[dict]:
    by = _by_slot(cards, placement)
    out = [_cell(I, cards, slot, by.get(slot, []), situation, held) for slot in ORDER]
    ramp = next(c for c in out if c["id"] == "stern_ramp")
    ramp["users"] = sorted(g for g in guests if cards[g]["placement"].get("uses_ramp"))
    return out


def _summary(cs: list[dict]) -> dict:
    mast = next(c for c in cs if c["id"] == "mast_free")
    bays = [c for c in cs if c["id"] in ("bay1", "bay2")]
    return {"mast": {"slots_free": mast["limits"]["slots_free"], "slots_total": 3, "natives": mast["natives"],
                     "guest": mast["who"] if mast["guests"] else None},
            "deck": {"halves_total": sum(c["limits"]["halves"] for c in bays), "halves_free": sum(c["limits"]["halves_free"] for c in bays),
                     "bays_free": [c["where"].split(" · ")[0] for c in bays if not c["guests"]]}}


def room(I: Inputs, m: Moment) -> dict:
    """The ship as room at one moment: the guests aboard in the positions D2 gives them, what is free at each."""
    snap = m.snapshot
    guests = list(snap["guests"])
    placement = view._placement(I, guests)
    situation = snap["ship_state"]["situation"]["value"]
    cs = cells(I, I.cards, guests, placement, situation)
    file = view._file(I, m)
    return {"mission": m.mission, "t_s": m.t_s, "situation": situation, "installed": guests, "cells": cs, **_summary(cs),
            "profile": {"id": file.get("id", m.mission), "name": view.mission_name(m.mission, file), "weights": file.get("weights", {}),
                        "mission_critical": list(file.get("mission_critical", []))},
            "as_built": as_built(I.A), "sources": sources(I.A), "route_seawater_c": I.scenario.get("location", {}).get("seawater_c")}


def admission_room(I: Inputs, case_id: str = "A5-survey", edits: dict | None = None, kept: dict | None = None) -> dict:
    """The pier: a Scenario A case's installed guests and the jury's card held over the slot D1's placement gives it,
    on the cards as the jury edited them. A refused edit comes back as view.admit gives it ({refused}) for a 422."""
    out = view.admit(I, case_id, edits, kept)
    if "refused" in out or "error" in out:
        return out
    case = next(c for c in I.cases if f"{c['case']}-{c['file']}" == case_id)
    cards = copy.deepcopy(I.cards)
    for key, value in case["card_edits"].items():
        gid, part, fld = key.split(".")
        _part(cards, gid, part)[fld] = value
    schema = Ld._schema(Ld.ROOT, "manifests/schema.json")
    applied = {**{k: v for k, v in (kept or {}).items() if k not in (edits or {})}, **out["edits"]}
    for target, raw in applied.items():  # the kept edits, then the accepted ones: the cards the verdict was decided on
        cards = view._apply(cards, I, schema, target, raw)[0] or cards
    card_id, installed = case["card"], list(case["installed"])
    placement = dict(out["record"].get("placement") or {})
    cs = cells(I, cards, installed + [card_id], placement, "alongside", held=card_id)
    unplaced = [{"guest": k.split(".")[0], "part": k.split(".")[1], "mass_t": _part(cards, *k.split("."))["mass_t"]}
                for k, v in placement.items() if v is None]
    return {"case": out["case"], "situation": "alongside", "installed": installed, "card": card_id, "cells": cs, **_summary(cs),
            "unplaced": unplaced, "verdict": out["verdict"], "edits": applied, "as_built": as_built(I.A), "sources": sources(I.A),
            "route_seawater_c": I.scenario.get("location", {}).get("seawater_c")}
