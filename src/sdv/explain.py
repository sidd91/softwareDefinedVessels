"""The one sentence per decision, built from the record's own fields (brief: explainability from the binding
constraint; no canned strings). Operator style: one to three short sentences, numbers with units, no semicolons,
nothing about the demo itself.
"""
from __future__ import annotations

LABELS = {"mass": "Mass", "stability": "Stability", "power": "Power", "heat": "Cooling", "line_port": "Port mission line",
          "line_stbd": "Starboard mission line", "mast_mass": "Mast slot weight", "mast_area": "Mast slot area",
          "mast_air_cooling": "Mast air cooling", "flight_deck_drone": "Hangar drone weight", "placement": "Placement"}
UNITS = {"t": "t", "t_eq": "t-eq", "kW": "kW", "kg": "kg", "m2": "m²", "kn": "kn"}
MODE_WORDS = {"fast_charge": "fast charge", "low_power": "low power"}


def n(x: float, digits: int = 3) -> str:
    """A number as an operator reads it: no trailing zeros."""
    if x is None:
        return "?"
    s = f"{x:.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def mode(m: str) -> str:
    return MODE_WORDS.get(m, m.replace("_", " "))


def _over_text(b: dict) -> str:
    over = b["demand"] - b["capacity"]
    if b["unit"] == "t":
        return f"{n(over * 1000, 0)} kg over" if over < 1 else f"{n(over)} t over"
    return f"{n(over)} {UNITS.get(b['unit'], b['unit'])} over"


def _spare_text(b: dict) -> str:
    free = b["capacity"] - b["demand"]
    if b["unit"] == "t" and free < 1:
        return f"{n(free * 1000, 0)} kg spare"
    return f"{n(free)} {UNITS.get(b['unit'], b['unit'])} spare"


def _line(b: dict) -> str:
    u = UNITS.get(b["unit"], b["unit"])
    return f"{n(b['demand'])} {u} against {n(b['capacity'])} {u}"


def d1(r: dict) -> str:
    v = r["verdict"]
    if v == "card-rejected":
        return f"Card rejected: {r['field']}. Previous card kept."
    b = r["binding"]
    label = LABELS.get(b["class"], b["class"])
    if v == "yes":
        out = f"Admitted. {label} is the tightest line: {_line(b)}, {_spare_text(b)}."
        g = r.get("genset", {})
        if g.get("state") == "holds_by_throttling" and g.get("steps"):
            s = g["steps"][0]
            out += f" With one genset down it holds by moving {s['guest']} from {mode(s['from_mode'])} to {mode(s['to_mode'])}, {n(s['frees_kw'])} kW freed."
        return out
    head = f"Refused on {label.lower()}: {_line(b)}, {_over_text(b)}."
    if v == "yes-if":
        o = r["options"][0]
        who = " and ".join(o["remove"])
        verb = "disembarks" if len(o["remove"]) == 1 else "disembark"
        tail = f" Admit if {who} {verb}"
        if o.get("moves"):
            tail += " and " + ", ".join(f"{k.split('.')[0]} moves to {v.replace('_', ' ')}" for k, v in o["moves"].items())
        return head + tail + f", mission value lost {n(o['value_lost'])}."
    if v == "not-now":
        return head + " It fits only in the next installation window."
    return head + " No removal makes it fit."


def d3(r: dict) -> str:
    lim = r["hard_limit"]["when"]
    within = r["hard_limit"]["then"].get("within_min")
    deadline_min = r["deadline_t_s"] / 60
    loser = r["cost_to_loser"]
    lo, hi = loser["minutes_lost"]
    first = (f"{r['proceeds']} recovers first: below {n(lim['value'])} % it must land within {n(within)} min, by minute "
             f"{n(deadline_min, 1)}, so waiting for the leg end is not possible.")
    if loser["open_ended"]:
        kw = r.get("reserved", {}).get(r["proceeds"])
        reserve = f" and {r['proceeds']}'s {n(kw)} kW charge is reserved" if kw else ""
        return first + f" The survey is suspended{reserve}. {loser['guest']}'s leg is aborted with no resume time."
    return first + f" {loser['guest']} holds depth and the survey pauses: {n(lo)} to {n(hi)} survey minutes lost."


def d4(r: dict) -> str:
    b = r["binding"]
    label = LABELS.get(b["class"], b["class"])
    cause = f" ({b['degraded_by'][0].split(':')[0]})" if b.get("degraded_by") else ""
    if r["verdict"] == "hold":
        out = f"Holds: {n(r['load_kw'])} of {n(r['limit_kw'])} kW, {label.lower()} limits{cause}."
        if r.get("armed"):
            a = r["armed"][0]
            out += f" Next step if needed: {a['guest']} {mode(a['from_mode'])} to {mode(a['to_mode'])}, {n(a['frees_kw'])} kW."
        return out
    if r["verdict"] == "unconfirmed":
        return f"Not shed: {n(r['load_kw'])} of {n(r['limit_kw'])} kW rests on a stale feed. Ladder armed."
    s = r["steps"][0]
    kept = r["losses"][s["guest"]]["capability_after"]
    parts = [f"{label} binds{cause}: {n(r['load_kw'])} kW against a {n(r['limit_kw'])} kW limit."]
    for st in r["steps"]:
        parts.append(f"{st['guest']} {mode(st['from_mode'])} to {mode(st['to_mode'])} frees {n(st['frees_kw'])} kW.")
    parts.append(f"Load {n(r['load_after_kw'])} of {n(r['limit_kw'])} kW. {s['guest']} keeps {n(kept * 100, 0)} %.")
    return " ".join(parts)


def d5(r: dict) -> str:
    """Rule R3 by crew level (docs/SCENARIO_C_MEMO.md)."""
    v, crew = r["verdict"], r["crew_aboard"]
    deadline = r["deadline_t_s"] / 60 if r.get("deadline_t_s") is not None else None
    if v == "held":
        return f"Recovery held: {r['deck_evidence']}. G4 must land by minute {n(deadline, 1)}."
    if v == "forbidden":
        return f"Recovery forbidden at {crew} aboard: {r['deck_evidence']}. G4 ditches by minute {n(deadline, 1)} and its rescue capability is lost."
    if v == "cleared":
        return f"Cleared to land: {r['deck_evidence']}. Turning into the wind and clearing the flight deck."
    if v == "confirm":
        return f"Bridge asked to confirm G4's recovery at {crew} aboard, on the {r['deck_evidence']}. G4 must land by minute {n(deadline, 1)}."
    if v == "standing_plan":
        return f"Recovery under the standing plan at {crew} aboard: {r['deck_evidence']}. G4 must land by minute {n(deadline, 1)}."
    if v == "automatic":
        return f"Recovery automatic at {crew} aboard: {r['deck_evidence']}. G4 must land by minute {n(deadline, 1)}."
    return f"R3 at {crew} aboard: {v.replace('_', ' ')}."


def sentence(r: dict) -> str:
    return {"D1": d1, "D2": d1, "D3": d3, "D4": d4, "D5": d5}[r["kind"]](r)
