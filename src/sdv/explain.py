"""The one sentence per decision, built from the record's own fields (brief: explainability from the binding
constraint; no canned strings). Operator style: one or two short sentences, the binding numbers first with their
units, no semicolons, nothing about the demo itself. The words below are vocabulary for names in the record (line
classes, units, modes, positions); every number comes from the record.
"""
from __future__ import annotations

LABELS = {"mass": "Mass", "stability": "Stability", "power": "Power", "heat": "Cooling", "line_port": "Port mission line",
          "line_stbd": "Starboard mission line", "mast_mass": "Mast slot weight", "mast_area": "Mast slot area",
          "mast_air_cooling": "Mast air cooling", "flight_deck_drone": "Hangar drone weight", "placement": "Placement",
          "at_sea_lift": "At-sea lift", "r3_lead": "Deck clearing lead"}
UNITS = {"t": "t", "t_eq": "t-eq", "kW": "kW", "kg": "kg", "m2": "m²", "kn": "kn", "min": "min", "h": "h", "halves": "halves"}
SINGULAR = {"halves": "half"}
MODE_WORDS = {"fast_charge": "fast charge", "low_power": "low power"}
POSITIONS = {"bay1": "Bay 1", "bay1_half": "half of Bay 1", "bay2": "Bay 2", "flight_deck": "the flight deck",
             "mast_free": "the free mast slot", "hangar_roof": "the hangar roof", "stern_ramp": "the stern ramp"}
CAPABILITIES = {"sar_air": "air rescue", "seabed_inspection": "seabed inspection", "ocean_data": "ocean data",
                "coastal_connectivity": "coastal connectivity", "passive_rf_detection": "RF detection", "fresh_water": "fresh water"}
TRIGGERS = {"genset_trip": "one genset down", "cooling_degraded": "one chilled-water pump down"}
OPS = {"<": "below", "<=": "at or below", ">": "above", ">=": "at or above"}
ACTIONS = {"land_or_ditch": "land", "land": "land"}
WINS = {"launch_recovery": "recovers first"}
ACTIVITY_NOUNS = {"surveying": "survey"}
WAITS = {"depth": "holds depth", "at_sea": "holds at sea"}


def n(x: float | None, digits: int = 3) -> str:
    """A number as an operator reads it: no trailing zeros."""
    if x is None:
        return "?"
    s = f"{x:.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def mode(m: str) -> str:
    return MODE_WORDS.get(m, m.replace("_", " "))


def minute(t_s: float | None) -> str:
    return n(None if t_s is None else t_s / 60, 1)


def qty(x: float, unit: str) -> str:
    u = UNITS.get(unit, unit)
    if unit in SINGULAR and abs(x) == 1:
        u = SINGULAR[unit]
    return f"{n(x)} {u}"


def _gap(x: float, unit: str) -> str:
    """A small mass gap in kg, as the brief's 35 kg case reads."""
    return qty(x * 1000, "kg") if unit == "t" and abs(x) < 1 else qty(x, unit)


def _line(b: dict) -> str:
    return f"{qty(b['demand'], b['unit'])} against {qty(b['capacity'], b['unit'])}"


def _over(b: dict) -> str:
    return f"{_gap(b['demand'] - b['capacity'], b['unit'])} over"


def _spare(b: dict) -> str:
    return f"{_gap(b['capacity'] - b['demand'], b['unit'])} spare"


def _label(b: dict) -> str:
    return b.get("label") or LABELS.get(b["class"], b["class"])


def _part(p: str) -> str:
    return p.replace(".", " ")


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _move(s: dict, with_kw: bool = True) -> str:
    out = f"{s['guest']} {mode(s['from_mode'])} to {mode(s['to_mode'])}"
    if with_kw and "from_kw" in s and "to_kw" in s:
        out += f", {n(s['from_kw'])} to {n(s['to_kw'])} kW"
    return out


def _window(w: dict, verb: str) -> str:
    k, t = w["kind"], w.get("t_s")
    at = f", minute {minute(t)}" if t is not None else ""
    if k == "port_call":
        days = f", within {n(w['within_days'])} days" if "within_days" in w else ""
        return f"It can {verb} at the next port call{at}{days}."
    if k == "at_sea_window":
        return f"It can {verb} in the next at-sea window{at}."
    if k == "resource_frees":
        when = f", when {w['event']}" if w.get("event") else ""
        return f"It fits from minute {minute(t)}{when}."
    return f"It can {verb} once {w['event']}{at}."


# ------------------------------------------------------------------------------------------------ D1 admission

def _condition(o: dict) -> str:
    who = _and(o["remove"])
    out = f"{who} {'disembarks' if len(o['remove']) == 1 else 'disembark'}"
    if o.get("moves"):
        out += " and " + _and([f"the {_part(p)} moves to {POSITIONS.get(v, v)}" for p, v in o["moves"].items()])
        if o.get("move_hours"):
            lo, hi = o["move_hours"]
            out += f" ({n(lo)} to {n(hi)} h by crane)"
    return out


def _genset(g: dict) -> str:
    if g.get("state") != "holds_by_throttling" or not g.get("steps"):
        return ""
    steps = g["steps"]
    freed = sum(s["frees_kw"] for s in steps)
    moves = _and([f"{s['guest']}{' goes' if i == 0 else ''} from {mode(s['from_mode'])} to {mode(s['to_mode'])}" for i, s in enumerate(steps)])
    return (f" With one genset down {n(g['load_kw'])} kW is over the {n(g['gate_kw'])} kW gate and holds once {moves}, "
            f"{n(freed)} kW freed.")


def d1(r: dict) -> str:
    v = r["verdict"]
    if v == "card-rejected":
        out = f"Card rejected: {r['field']}."
        if r.get("kept_previous"):
            out += f" The previous {r['subject']} card stays in force."
        return out
    b = r["binding"]
    label = _label(b)
    if v == "yes":
        return f"Admitted: {label.lower()} is the tightest line, {_line(b)}, {_spare(b)}." + _genset(r.get("genset", {}))
    if v == "not-now":
        return f"Not now: {label[0].lower() + label[1:]}, {_line(b)}, {_over(b)}. " + _window(r["next_window"], "come aboard")
    head = f"{label} binds: {_line(b)}, {_over(b)}."
    if v == "yes-if":
        o = r["options"][0]
        return head + f" Yes if {_condition(o)}, mission value lost {n(o['value_lost'])}."
    if r.get("card_alone"):
        a = r["card_alone"]
        return head + f" No: even alone, {_label(a).lower()} is {_line(a)}."
    return head + " No removal set fits."


# ------------------------------------------------------------------------------------------------ D2 placement

def d2(r: dict) -> str:
    part, b = r["subject"], r["binding"]
    rejected = r.get("placement_rejected", [])
    if r["verdict"] == "unplaced":
        out = f"{_part(part)} has no position: it needs {qty(b['demand'], b['unit'])} and {qty(b['capacity'], b['unit'])} are free."
        held = [x for x in rejected if x["reason"] == "held"]
        if held:
            first, rest = held[0], held[1:]
            text = f"{POSITIONS.get(first['position'], first['position'])} is held by the {_part(first['held_by'])}"
            text += "".join(f" and {POSITIONS.get(x['position'], x['position'])} by the {_part(x['held_by'])}" for x in rest)
            out += " " + text[0].upper() + text[1:] + "."
        return out
    pos = r["placement"][part]
    out = f"{_part(part)} to {POSITIONS.get(pos, pos)}: {n(b['demand'])} of {qty(b['capacity'], b['unit'])} used, {_spare(b)}."
    if rejected:
        x = rejected[0]
        where = POSITIONS.get(x["position"], x["position"])
        where = where[0].upper() + where[1:]
        if x["reason"] == "held":
            why = f"the {_part(x['held_by'])} holds it"
            if x.get("move_hours"):
                lo, hi = x["move_hours"]
                why += f" and moving it takes {n(lo)} to {n(hi)} h of crane work"
        elif x["reason"] == "over_limit" and x.get("line"):
            why = f"{_label(x['line']).lower()} {_line(x['line'])}, {_over(x['line'])}"
        else:
            why = {"less_preferred": "a lower preference on the card", "not_allowed": "not allowed by the card"}[x["reason"]]
        out += f" {where} rejected: {why}."
    return out


# ------------------------------------------------------------------------------------------------ D3 right of way

def d3(r: dict) -> str:
    lim = r["hard_limit"]
    when, then = lim["when"], lim["then"]
    unit = " %" if when["signal"].endswith("_pct") else ""
    winner_act = r["subject"].split(" against ")[0].partition(".")[2]
    loser_act = r["subject"].split(" against ")[-1].partition(".")[2]
    first = (f"{r['proceeds']} {WINS.get(winner_act, 'goes first')}: {OPS.get(when['op'], when['op'])} {n(when['value'])}{unit} "
             f"it must {ACTIONS.get(then['action'], then['action'].replace('_', ' '))}")
    if then.get("within_min") is not None:
        first += f" within {n(then['within_min'])} min"
    first += f", by minute {minute(r['deadline_t_s'])}"
    if r.get("leg_ends_t_s") is not None and r.get("wait_for_leg_end") == "infeasible":
        first += f", and {r['yields']}'s leg runs to minute {minute(r['leg_ends_t_s'])}"
    loser = r["cost_to_loser"]
    lo, hi = loser["minutes_lost"]
    noun = ACTIVITY_NOUNS.get(loser_act, "working")
    if loser["open_ended"]:
        second = f"{loser['guest']}'s leg is aborted, at least {n(lo)} to {n(hi)} {noun} minutes lost with no resume time"
    else:
        second = f"{loser['guest']} {WAITS.get(loser.get('holds'), 'waits')} and loses {n(lo)} to {n(hi)} {noun} minutes"
        if loser.get("leg_ends_at_min"):
            a, b = loser["leg_ends_at_min"]
            second += f", its leg now ending at minute {n(a, 1)} to {n(b, 1)}"
    reserved = [f"{g}'s {n(kw)} kW charge" for g, kw in r.get("reserved", {}).items() if kw]
    if reserved:
        second += f", and {_and(reserved)} {'is' if len(reserved) == 1 else 'are'} reserved"
    return f"{first}. {second}."


# ------------------------------------------------------------------------------------------------ D4 shedding

def _cause(r: dict) -> str:
    if r.get("trigger") in TRIGGERS:
        return f" with {TRIGGERS[r['trigger']]}"
    by = r.get("binding", {}).get("degraded_by") or []
    return f" with {by[0].split(':')[0]}" if by else ""


def _losses(r: dict) -> str:
    losses = r.get("losses") or {}
    lost = [(g, l) for g, l in losses.items() if l["capability_after"] < l["capability_before"]]
    kept = [g for g, l in losses.items() if l["capability_after"] >= l["capability_before"]]
    parts = [f"{g} loses {n(100 * (l['capability_before'] - l['capability_after']), 0)} %" for g, l in lost]
    if kept:
        parts.append(f"{_and(kept)} nothing")
    return ", ".join(parts)


def _armed(r: dict) -> str:
    if not r.get("armed"):
        return ""
    a = r["armed"][0]
    return f" First armed step: {_move(a)}, frees {n(a['frees_kw'])} kW."


def d4(r: dict) -> str:
    load, limit = n(r["load_kw"]), n(r["limit_kw"])
    if r["verdict"] in ("hold", "unconfirmed"):
        reserved = [f"{g}'s {n(kw)} kW reserved" for g, kw in (r.get("reserved") or {}).items() if kw]
        with_res = f" and {_and(reserved)}" if reserved else ""
        if r["verdict"] == "hold":
            lost = ", no capability lost" if r.get("losses") else ""
            return f"Holds: {load} of {limit} kW{_cause(r)}{with_res}, {len(r['steps'])} steps{lost}." + _armed(r)
        why = f" ({r['unconfirmed_because']})" if r.get("unconfirmed_because") else ""
        return f"Not shed: {load} kW against the {limit} kW limit is not confirmed{why}." + _armed(r)
    label = _label(r["binding"])
    freed = sum(s["frees_kw"] for s in r["steps"])
    steps = _and([_move(s) for s in r["steps"]])
    verb = "frees" if len(r["steps"]) == 1 else "free"
    out = f"{label} binds{_cause(r)}: {load} kW against the {limit} kW limit. "
    out += f"{steps}, {verb} {n(freed)} kW and the load is {n(r['load_after_kw'])} kW"
    losses = _losses(r)
    return out + (f": {losses}." if losses else ".")


# ------------------------------------------------------------------------------------------------ D5 crew policy

HEADS = {"held": "Recovery held", "cleared": "Recovery cleared", "automatic": "Recovery automatic", "forbidden": "Recovery forbidden",
         "standing_plan": "Recovery under the standing plan"}


def d5(r: dict) -> str:
    """Rule R3 by crew level (docs/SCENARIO_C_MEMO.md)."""
    v, crew = r["verdict"], r["crew_aboard"]
    lim = r.get("hard_limit") or {}
    guest = lim.get("guest", "G4")
    at = f" at {n(lim['reading'])} %" if lim.get("reading") is not None else ""
    deadline = r.get("deadline_t_s")
    evidence = r.get("deck_evidence", "")
    sweep = next((e for e in r.get("evidence", []) if e["signal"] == "last_sweep" and isinstance(e["value"], dict)), None)
    if sweep and sweep["value"].get("t_s") is not None and v == "automatic":
        evidence += f" ({n((r['t_s'] - sweep['value']['t_s']) / 60, 0)} min ago)"
    if v == "not-now":
        req = r.get("request", {})
        what = req.get("what", r["subject"])
        dur = f" ({n(req['minutes'])} min)" if req.get("minutes") is not None else ""
        out = f"Not now at {crew} aboard: {what}{dur} waits until {r['next_window'].get('event', 'later')}."
        b = r.get("binding")
        if b:
            out += f" {_label(b)} {_line(b)}, {_over(b)}."
        return out
    if v == "confirm":
        head = f"Bridge asked to confirm {guest}'s recovery at {crew} aboard, on the {evidence}."
    else:
        head = f"{HEADS.get(v, 'R3 ' + v.replace('_', ' '))} at {crew} aboard: {evidence}."
    if deadline is None:
        return head
    if v == "forbidden":
        loss = (r.get("losses") or {}).get(guest)
        cap = CAPABILITIES.get(loss.get("capability"), "") if loss else ""
        tail = f" {guest}{at} ditches by minute {minute(deadline)}"
        if loss and loss["capability_after"] == 0:
            tail += f" and its {cap + ' ' if cap else ''}capability is lost"
        return head + tail + "."
    if v == "held" and r.get("approach_min") is not None:
        start = deadline - 60 * r["approach_min"]
        return head + (f" {guest}{at} must start its {n(r['approach_min'])} min approach by minute {minute(start)} "
                       f"to land by {minute(deadline)}.")
    return head + f" {guest}{at} must land by minute {minute(deadline)}."


def sentence(r: dict) -> str:
    return {"D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5}[r["kind"]](r)
