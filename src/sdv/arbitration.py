"""D3 right of way: when two guests need ship states that cannot both hold, who proceeds and what the other loses.

Order (brief D3, Scenario B minute 8): hard limits first, then the priority file's weights. The way the loser
yields is computed from the file, never written per file (review design-1):
- the winner's next demand is reserved when its capability weight is at least the loser's, or it is
  mission-critical under the file;
- the loser pauses and resumes when its weight is at least the winner's; otherwise it is suspended, open-ended.
The cost to the loser is in its own units: survey minutes = time already flown on the leg (re-run) + the
recovery window + the time to settle back to quiet (config/signals.yaml derivations.g3_leg,
config/assumptions.yaml ship_state.noise.to_quiet_min).
"""
from __future__ import annotations


def _pred_values(pred):
    if isinstance(pred, dict):
        return ("range", pred.get("min", float("-inf")), pred.get("max", float("inf")))
    if isinstance(pred, list):
        return ("set", set(pred))
    return ("eq", pred)


def _compatible(a, b, tol: float) -> bool:
    """Can one value satisfy both predicates?"""
    ka, kb = _pred_values(a), _pred_values(b)
    if ka[0] == "range" or kb[0] == "range":
        lo_a, hi_a = (ka[1], ka[2]) if ka[0] == "range" else (ka[1] - tol, ka[1] + tol)
        lo_b, hi_b = (kb[1], kb[2]) if kb[0] == "range" else (kb[1] - tol, kb[1] + tol)
        return max(lo_a, lo_b) <= min(hi_a, hi_b)
    sa = ka[1] if ka[0] == "set" else {ka[1]}
    sb = kb[1] if kb[0] == "set" else {kb[1]}
    return bool(sa & sb)


def _requires(cards, gid, activity):
    return next(c["requires"] for c in cards[gid]["conditions"] if c["activity"] == activity)


def conflicts(cards: dict, activities: dict, a: tuple[str, str], b: tuple[str, str], tol: float) -> list[dict]:
    """The ship-state signals on which two guest activities cannot both hold, each with what each side needs."""
    (ga, aa), (gb, ab) = a, b
    ra, rb = _requires(cards, ga, aa), _requires(cards, gb, ab)
    out = []
    for sig in sorted(set(ra) & set(rb)):
        if not _compatible(ra[sig], rb[sig], tol):
            out.append({"signal": sig, ga: ra[sig], gb: rb[sig]})
    for (g1, act1, req1), (g2, act2) in (((ga, aa, ra), (gb, ab)), ((gb, ab, rb), (ga, aa))):
        for sig, val in activities[g2][act2].get("effects", {}).items():
            if sig in req1 and not _compatible(req1[sig], val, tol) and not any(c["signal"] == sig for c in out):
                out.append({"signal": sig, g1: req1[sig], g2: val, "by": f"{g2}.{act2}"})
    for ex in cards[ga].get("relations", {}).get("excludes", []):
        if ex["activity"] == aa and ex["excludes"] == f"{gb}.{ab}":
            out.append({"exclusion": f"{ga}.{aa} excludes {gb}.{ab}"})
    for ex in cards[gb].get("relations", {}).get("excludes", []):
        if ex["activity"] == ab and ex["excludes"] == f"{ga}.{aa}":
            out.append({"exclusion": f"{gb}.{ab} excludes {ga}.{aa}"})
    return out


def _value(snap, name):
    gid, _, key = name.partition(".")
    if key and gid in snap["guests"]:
        return snap["guests"][gid][key]["value"]
    for group in ("ship_state", "plant", "environment", "links", "crew"):
        if name in snap.get(group, {}):
            return snap[group][name]["value"]
    return None


def _limit_active(lim, value):
    op, ref = lim["when"]["op"], lim["when"]["value"]
    if value is None:
        return False
    return {"<": value < ref, "<=": value <= ref, "==": value == ref, "!=": value != ref, ">=": value >= ref, ">": value > ref}[op]


def recovery_lead_s(A: dict, crew: int) -> float:
    """Time a recovery needs before landing: the bridge confirm, clearing the deck and the approach (A.6, R3)."""
    confirm = max(A["crew"]["confirm_s"].get(str(crew)) or [0])
    clear = max(A["ship_state"]["deck"]["clear_min"].get(crew) or [0]) * 60
    return confirm + clear + A["rules"]["r3"]["approach_min"] * 60


def recovery_due(A: dict, cards: dict, snap: dict) -> dict | None:
    """The G4 hard limit that calls for its recovery now, or None: the battery limit at once; a land-by deadline alone
    (endurance) only once the recovery lead time is needed."""
    g4 = snap["guests"].get("G4")
    if not g4 or g4["activity"]["value"] not in ("airborne", "launch_recovery"):
        return None
    t = snap["run"]["t_ship_s"]
    land_by = g4["land_by_t_s"]["value"]
    lead = recovery_lead_s(A, snap["crew"]["crew_aboard"]["value"])
    active = [l for l in cards["G4"].get("hard_limits", []) if _limit_active(l, _value(snap, l["when"]["signal"]))]
    urgent = [l for l in active if l["then"]["action"] == "land_or_ditch"]
    due = [l for l in active if l["then"]["action"] == "land" and land_by is not None and land_by - t <= lead]
    return (urgent or due or [None])[0]


def right_of_way(A: dict, signals: dict, cards: dict, mission: dict, snap: dict) -> dict | None:
    """D3 on one snapshot: G4's recovery against G3's survey leg (Scenario B minute 8), or None if no conflict."""
    g4, g3 = snap["guests"].get("G4"), snap["guests"].get("G3")
    if not g4 or not g3 or g3["activity"]["value"] != "surveying":
        return None
    t = snap["run"]["t_ship_s"]
    land_by = g4["land_by_t_s"]["value"]
    lead = recovery_lead_s(A, snap["crew"]["crew_aboard"]["value"])
    limit = recovery_due(A, cards, snap)
    if limit is None:
        return None
    tol = signals["derivations"]["speed_tolerance_kn"]["value"]
    clash = conflicts(cards, signals["activities"], ("G3", "surveying"), ("G4", "launch_recovery"), tol)
    if not clash:
        return None
    leg = signals["derivations"]["g3_leg"]
    leg_end = g3["leg_started_t_s"]["value"] + leg["leg_length_s"]
    wait_feasible = leg_end <= land_by
    weights = mission["weights"]    # a capability the file leaves out weighs 0, as in D1 and D4
    w_win = weights.get(cards["G4"]["capability"]["name"], 0.0)
    w_lose = weights.get(cards["G3"]["capability"]["name"], 0.0)
    reserve = w_win >= w_lose or "G4" in mission["mission_critical"]
    pause = w_lose >= w_win
    flown_min = g3["leg_flown_s"]["value"] / 60
    window_min = leg["recovery_window_s"] / 60
    settle = A["ship_state"]["noise"]["to_quiet_min"]
    lost = [round(flown_min + window_min + s, 1) for s in settle]
    charge = next(m for m in cards["G4"]["modes"] if m["name"] == "fast_charge")
    record = {
        "kind": "D3", "tick": snap["run"]["tick"], "t_s": t, "applies_at_tick": snap["run"]["tick"] + 1,
        "subject": "G4.launch_recovery against G3.surveying", "mission": mission["id"],
        "proceeds": "G4", "yields": "G3",
        "hard_limit": {"guest": "G4", "when": limit["when"], "then": limit["then"]},
        "deadline_t_s": land_by, "deadline_min": round(land_by / 60, 1), "recovery_lead_s": lead,
        "wait_for_leg_end": "feasible" if wait_feasible else "infeasible", "leg_ends_t_s": leg_end,
        "conflicts": clash,
        "charge_reserved": reserve, "reserved_kw": charge["power_kw"] if reserve else 0,
        "loser": {"guest": "G3", "leg": "paused" if pause else "aborted", "holds": "depth" if pause else "at_sea",
                  "mode": "standby", "survey_minutes_lost": lost, "open_ended": not pause},
        "weights": {"G4": w_win, "G3": w_lose},
    }
    if pause:
        record["loser"]["leg_ends_at_min"] = [round(leg_end / 60 + x, 1) for x in lost]
    else:
        record["loser"]["recovery"] = {"via": "stern_ramp", "after": "G4 landed"}
    return record
