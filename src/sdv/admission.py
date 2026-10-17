"""D1: admission of a guest card (ceiling 30 s), judged at the mission envelope, not the pier.

Rule (README, DEC-35, DEC-37, DEC-38): the verdict is judged with both gensets, the lower speed-band
reserve (200 kW) and cooling at 30 C, every guest at its sustained envelope draw; it must also survive
one genset down by throttling to the 95 kW gate (the D4 ladder's throttle-only prefix), otherwise the
set does not pass. Verdicts: `yes`, `yes-if` (ranked removal sets, least mission value lost first,
mission-critical last; in port an installed guest may move between bays, each move reported with its
crane time) or `no`. Links are judged at the guests' minimum rates. The seawater temperature at which
the cooling line flips is reported. The binding line is the one with the least margin, and the sentence
is built from its numbers.
"""
from __future__ import annotations

import copy
import itertools
from dataclasses import dataclass, field

from . import placement as P
from . import shedding
from .decision import Binding, Decision, fmt
from .ledger import cooling_capacity_kw, envelope_kw, envelope_mode
from .priority import is_critical, weight

LEDGER = ("mass", "stability", "power", "heat", "line_port", "line_stbd", "satcom", "los_radio", "backbone", "compute")


def apply_edits(cards: dict, edits: dict) -> dict:
    """Live card edits from the jury, e.g. {"G4.hangar.mass_t": 0.8} or {"G4.power_kw.nominal": 12}."""
    cards = copy.deepcopy(cards)
    for key, value in (edits or {}).items():
        gid, *path = key.split(".")
        parts = {p["name"]: p for p in cards[gid]["placement"]["parts"]}
        if path[0] in parts:
            parts[path[0]][path[1]] = value
        else:
            node = cards[gid]["consumes"] if path[0] in cards[gid]["consumes"] else cards[gid]
            for p in path[:-1]:
                node = node[p]
            node[path[-1]] = value
    return cards


def _zone(a: dict, slot: str | None, part: dict) -> str:
    slot = slot or part["preferred"][0]
    return a["positions"][P.HALF_OF.get(slot, slot)].get("zone", "bay")


def _line_of(a: dict, slot: str | None, part: dict) -> str | None:
    slot = slot or part["preferred"][0]
    return a["positions"][P.HALF_OF.get(slot, slot)].get("power_line")


def envelope_lines(a: dict, cards: dict, guests: list[str], placement: dict) -> list[Binding]:
    """The ship-wide ledger at the envelope. Unplaced parts count at their preferred slot."""
    t30 = a["envelope"]["judge_cooling_at_c"]
    mult = a["mass"]["multiplier"]
    mass = stab = power = heat = 0.0
    lines_kw = {k: 0.0 for k in a["power"]["mission_line_kw"]}
    sat = los = bb = cores = 0.0
    for g in guests:
        card = cards[g]
        kw = envelope_kw(a, card)
        power += kw
        if card.get("cooling") == "chilled_water":
            heat += kw
        parts = card["placement"]["parts"]
        for part in parts:
            slot = placement.get(P.part_key(g, part))
            mass += part["mass_t"]
            stab += part["mass_t"] * mult[_zone(a, slot, part)]
        ln = _line_of(a, placement.get(P.part_key(g, parts[0])), parts[0])
        if ln:
            lines_kw[ln] += kw
        c = card["consumes"]
        sat += float(c.get("data_satcom_mbps", {}).get("min", c.get("data_satcom_mbps", {}).get("nominal", 0)))
        los += float(c.get("data_los_radio_mbps", {}).get("min", c.get("data_los_radio_mbps", {}).get("nominal", 0)))
        bb += float(c.get("data_backbone_mbps", {}).get("nominal", 0))
        cores += float(c.get("compute_cores", {}).get("nominal", 0))
    comp = a["compute"]
    out = [
        Binding("mass", "mass margin", float(a["mass"]["margin_t"]), round(mass, 3), "t"),
        Binding("stability", "stability budget", float(a["mass"]["stability_budget_t_eq"]), round(stab, 3), "t_eq"),
        Binding("power", "guest power reserve at the envelope", float(a["power"]["envelope_reserve_kw"]), round(power, 3), "kW"),
        Binding("heat", f"chilled-water loop at {t30} °C", round(cooling_capacity_kw(a, t30, False), 3), round(heat, 3), "kW"),
    ]
    for k, cap in a["power"]["mission_line_kw"].items():
        out.append(Binding(f"line_{k}", f"{k} mission line", float(cap), round(lines_kw[k], 3), "kW"))
    out += [
        Binding("satcom", "SATCOM at guests' minimum rates", float(a["data"]["satcom_envelope_mbps"]), round(sat, 3), "Mbit/s"),
        Binding("los_radio", "line-of-sight radio at guests' minimum rates", float(a["data"]["los_radio_operating_mbps"]), round(los, 3), "Mbit/s"),
        Binding("backbone", "backbone", float(a["data"]["backbone_mbps"]), round(bb, 3), "Mbit/s"),
        Binding("compute", "guest compute", float(comp["nodes"] * comp["cores_per_node"] * comp["guest_share"]), round(cores, 3), "cores"),
    ]
    return out


def failing(lines: list[Binding]) -> list[Binding]:
    return [ln for ln in lines if ln.demand > ln.capacity + 1e-9]


def tightest(lines: list[Binding]) -> Binding:
    return max(lines, key=lambda ln: (ln.demand / ln.capacity if ln.capacity else float("inf"), ln.cls))


def min_margin(lines: list[Binding]) -> float:
    return min((ln.capacity - ln.demand) / ln.capacity for ln in lines if ln.capacity)


def seawater_tip(a: dict, chilled_kw: float) -> dict | None:
    """Seawater temperature at which the loop capacity falls to the chilled load (A.2 curve), with the
    0.1 C scan result when it lies inside the scan."""
    if chilled_kw <= 0:
        return None
    (t0, c0), (t1, c1) = sorted(a["heat"]["capacity_kw_at"].items())
    tip = t0 + (c0 - chilled_kw) * (t1 - t0) / (c0 - c1)
    step, top = a["admission"]["seawater_scan_step_c"], a["admission"]["seawater_scan_max_c"]
    out = {"tip_c": round(tip, 3), "inside_scan": tip <= top}
    if tip <= top:
        holds = int(tip / step + 1e-9) * step
        out.update({"holds_at_c": round(holds, 1), "fails_at_c": round(holds + step, 1)})
    return out


def one_genset_down(a: dict, cards: dict, mission: dict, guests: list[str]) -> dict:
    """DEC-35: the raw one-genset-down line and the throttle-only fix to the 95 kW gate."""
    reserve = float(a["power"]["guest_reserve_kw"]["one_genset_down"])
    gate = a["admission"]["one_genset_down_gate"]["kw"]
    t30 = a["envelope"]["judge_cooling_at_c"]
    pc, hc = shedding.ceilings(a, reserve, cooling_capacity_kw(a, t30, False))
    modes = {g: envelope_mode(a, cards[g]) for g in guests}
    lad = shedding.walk(cards, modes, mission, pc, hc, throttle_only=True, keep_capability=True)
    load = lad.load_before_kw
    status = "holds" if load <= gate + 1e-9 else ("holds by throttling" if lad.holds else "does not hold")
    return {"load_kw": load, "reserve_kw": reserve, "holds": load <= reserve + 1e-9, "short_kw": round(max(load - reserve, 0), 3),
            "spare_kw": round(max(reserve - load, 0), 3), "gate_kw": gate, "status": status, "passes": status != "does not hold",
            "fix": [s.as_dict() for s in lad.steps], "load_after_kw": lad.load_after_kw}


def _lines_dict(lines: list[Binding]) -> list[dict]:
    return [dict(ln.as_dict(), fails=ln.demand > ln.capacity + 1e-9) for ln in lines]


def _passes(a, cards, mission, guests, placement):
    lines = envelope_lines(a, cards, guests, placement)
    if failing(lines):
        return None
    ogd = one_genset_down(a, cards, mission, guests)
    return (lines, ogd) if ogd["passes"] else None


def decide(a: dict, cards: dict, mission: dict, installed: dict[str, str], card_id: str, card_edits: dict | None = None,
           t_s: float = 0.0, allow_moves: bool = True) -> Decision:
    """`installed` maps part keys of the guests already aboard to their slots."""
    cards = apply_edits(cards, card_edits)
    installed_ids = sorted({k.split(".")[0] for k in installed})
    guests = installed_ids + [card_id]
    t30 = a["envelope"]["judge_cooling_at_c"]

    # D2 for the new card, installed guests untouched; then the ledger of the set as given.
    as_given, rejected = P.place_as_given(a, cards, installed, card_id)
    options_pl = [pl for pl in P.enumerate_placements(a, cards, guests, fixed=installed) if all(pl.get(k) for k in as_given)]
    best = P.choose(a, cards, options_pl, lambda pl: min_margin(envelope_lines(a, cards, guests, pl)))
    placement = best or as_given
    lines = envelope_lines(a, cards, guests, placement)
    unplaced = [k for k, v in placement.items() if v is None]
    placement_line = None
    if unplaced:
        part = unplaced[0]
        gid, name = part.split(".")
        want = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == name)["allowed"]
        placement_line = Binding("placement", f"no free position for {part} (allowed: {', '.join(want)})", 0, 1, "position")
    fails = failing(lines) + ([placement_line] if placement_line else [])
    ogd = one_genset_down(a, cards, mission, guests) if not unplaced else None
    chilled = next(ln.demand for ln in lines if ln.cls == "heat")
    # The chilled load does not depend on where parts sit, so the tip is reported as soon as any part of
    # the card is aboard; a card with no position at all only gets tips through its yes-if options.
    card_aboard = any(placement.get(P.part_key(card_id, p)) for p in cards[card_id]["placement"]["parts"])
    tip = seawater_tip(a, chilled) if card_aboard else None

    extras = {"guests": guests, "lines": _lines_dict(lines), "one_genset_down": ogd, "seawater": tip,
              "rejected": [r.as_dict() for r in rejected], "card_edits": card_edits or {}, "yes_if": [], "not_enough": []}

    if not fails and ogd["passes"]:
        binding = tightest(lines)
        sentence = (f"Yes. Binding: {binding.cls}, {fmt(binding.demand)} of {fmt(binding.capacity)} {binding.unit}"
                    f"{' at ' + str(t30) + ' °C' if binding.cls == 'heat' else ''}; {fmt(binding.free)} {binding.unit} free. "
                    + _ogd_sentence(ogd) + _tip_sentence(tip))
        d2 = _d2_sentence(cards, card_id, placement, rejected)
        return Decision("D1", card_id, "yes", binding, sentence + " " + d2, t_s=t_s, placement=placement, mission=mission["id"], extras=extras)

    # yes-if: minimal removal sets of installed guests, without moves first, then with port moves.
    ledger_fails = failing(lines)
    binding = (tightest(ledger_fails) if ledger_fails else placement_line
               or Binding("power", "one genset down", ogd["gate_kw"], ogd["load_kw"], "kW"))
    options = []
    for n in range(1, len(installed_ids) + 1):
        for subset in itertools.combinations(installed_ids, n):
            if any(set(o["remove"]) <= set(subset) for o in options):
                continue
            kept = [g for g in guests if g not in subset]
            fixed = {k: v for k, v in installed.items() if k.split(".")[0] not in subset}
            found = None
            for movable in ([set()] + ([set(kept) - {card_id}] if allow_moves else [])):
                pls = P.enumerate_placements(a, cards, kept, fixed=fixed, movable=movable)
                passing = [(pl, r) for pl in pls if (r := _passes(a, cards, mission, kept, pl))]
                if passing:
                    pl, (lns, og) = max(passing, key=lambda x: (min_margin(x[1][0]), P.preferred_count(cards, x[0]), -len(P.moves(x[0], fixed))))
                    found = (pl, lns, og)
                    break
            if not found:
                if n == 1:
                    lns = envelope_lines(a, cards, kept, {k: v for k, v in placement.items() if k.split(".")[0] in kept})
                    extras["not_enough"].append({"remove": list(subset), "mass_after_t": next(l.demand for l in lns if l.cls == "mass"),
                                                 "still_failing": [l.cls for l in failing(lns)] or ["placement"]})
                continue
            pl, lns, og = found
            mv = P.moves(pl, fixed)
            opt = {"remove": list(subset), "value_lost": round(sum(weight(mission, cards[g]) for g in subset), 6),
                   "mission_critical": any(is_critical(mission, g) for g in subset),
                   "mass_after_t": next(l.demand for l in lns if l.cls == "mass"),
                   "stability_after_t_eq": next(l.demand for l in lns if l.cls == "stability"),
                   "placement": pl, "moves": mv, "one_genset_down": og,
                   "seawater": seawater_tip(a, next(l.demand for l in lns if l.cls == "heat")), "binding_after": tightest(lns).as_dict()}
            if mv:
                h = a["installation"]["in_port"]["hours_per_bay_guest"]
                opt["crane"] = {"moves": len(mv), "hours": h}
            options.append(opt)
    options.sort(key=lambda o: (o["mission_critical"], o["value_lost"], len(o["remove"]), o["remove"]))
    extras["yes_if"] = options
    over = binding.demand - binding.capacity
    head = (f"Binding: {binding.cls}, {fmt(binding.demand)} of {fmt(binding.capacity)} {binding.unit}"
            f"{' at ' + str(t30) + ' °C' if binding.cls == 'heat' else ''}; {fmt(over)} {binding.unit} over"
            if binding.cls != "placement" else f"Binding: placement, {binding.label}")
    others = [f.cls for f in fails if f is not binding]
    if others:
        head += f"; also failing: {', '.join(others)}"
    if not options:
        sentence = f"No. {head}. No removal of installed guests makes the set fit."
        return Decision("D1", card_id, "no", binding, sentence, t_s=t_s, placement=placement, mission=mission["id"], extras=extras)
    opts = "; ".join(_option_text(o) for o in options)
    sentence = f"Yes-if. {head}. In order of mission value lost under {mission['id']}: {opts}."
    return Decision("D1", card_id, "yes-if", binding, sentence, t_s=t_s, placement=placement, options=options, mission=mission["id"], extras=extras)


def _option_text(o: dict) -> str:
    s = f"remove {', '.join(o['remove'])} ({fmt(o['value_lost'])} value lost"
    s += ", mission-critical" if o["mission_critical"] else ""
    if o.get("moves"):
        s += "; " + ", ".join(f"{m['part']} {m['from']} to {m['to']}" for m in o["moves"]) + f", {o['crane']['moves']} crane move {o['crane']['hours'][0]}-{o['crane']['hours'][1]} h"
    s += f"; {fmt(o['mass_after_t'])} t"
    og = o["one_genset_down"]
    s += f"; one genset down {og['status']} at {fmt(og['load_kw'])} kW)"
    return s


def _ogd_sentence(ogd: dict) -> str:
    s = f"One genset down: {fmt(ogd['load_kw'])} of {fmt(ogd['reserve_kw'])} kW, "
    s += "fits as loaded" if ogd["holds"] else f"{fmt(ogd['short_kw'])} kW short as loaded"
    if ogd["status"] == "holds":
        s += "; nothing needed."
    elif ogd["fix"]:
        f = ogd["fix"][0]
        s += (f"; holds by throttling {f['guest']} to {f['to_mode']} ({fmt(f['frees_kw'])} kW freed, {fmt(f['capability_lost_pct'])} % of "
              f"{f['guest']}'s capability lost), automatic within 5 s, no guest switched off.")
    else:
        s += "; does not hold by throttling."
    return s


def _tip_sentence(tip: dict | None) -> str:
    if not tip:
        return ""
    return f" Cooling flips at {fmt(tip['tip_c'])} °C seawater" + (f" (holds at {tip['holds_at_c']}, fails at {tip['fails_at_c']})." if tip["inside_scan"] else ", outside the 12-30 °C envelope.")


def _d2_sentence(cards: dict, card_id: str, placement: dict, rejected: list[P.Rejection]) -> str:
    parts = [f"{k.split('.')[1]} to {v}" for k, v in placement.items() if k.startswith(card_id + ".") and v]
    s = f"Placement: {', '.join(parts)}" if parts else "Placement: none"
    rej = [r for r in rejected if r.part.startswith(card_id + ".")]
    if rej:
        s += "; rejected " + "; ".join(f"{r.slot} because {r.why}" for r in rej[:2])
    return s + "."
