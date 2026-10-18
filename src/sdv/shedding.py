"""D4 degradation and shedding on one snapshot: hold, or walk the precomputed ladder until the load is within both limits.

Power and cooling are judged on their own lines (A.1, A.2): every guest's committed draw against the guest reserve less
the 5 kW headroom, and the chilled-water guests' draw against the loop's capacity less the headroom. An air-cooled
guest (G1 on the mast) counts on the bus and never on the loop, so with it aboard the two loads differ. The line that
binds is the one with the least spare: a line that is over always names the record (cooling at minute 19, power at
minute 12), and the ladder walks until both lines fit, passing over a step that relieves no line still over (switching
G1 off while only the loop is over would cost its capability for nothing). Load is the ledger's committed draw per guest (the larger of its
mode, a reservation from the decision log and a fresh reading). D4 never acts on a substituted value
(docs/STATE_ESTIMATION.md, fallback_policy.d4): it acts only on a line over on fresh readings, its capacity and every
draw counted on it. A line over on a stand-in (a stale or substituted capacity, a guest's mode or kW stale, substituted
or missing) arms the ladder and the record says the load is unconfirmed, and the ladder walks no step for it. One
stand-in does not hold D4 back: a guest's kW beside its fresh mode. The draw then counts the mode's kW, a lower bound,
so a line over with every mode on it fresh is over for certain and is shed. A guest whose mode is a stand-in leaves its
line unconfirmed. Only the line that binds can hold D4 back: cooling over on fresh chilled-water data is shed while the
bus figure is a stand-in.

The record also carries every guest's envelope draw beside its draw now (envelope), so a hold can say why the envelope
set, every guest at its sustained worst case, does not arise (the brief's explicit minute-12 sequence, R-067).
"""
from __future__ import annotations

from sdv import ledger as Lg
from sdv import loader as Ld

A = Ld.load_assumptions()
RT = A["response_time_s"]
FAULT_LINE = {"genset_trip": "power", "cooling_degraded": "heat"}   # the line a held fault leaves unconfirmed


def fresh(field: dict) -> bool:
    """A reading, not a stand-in: neither stale nor substituted."""
    return not field.get("stale") and field.get("confidence") != "substituted"


_fresh = fresh


def _mode(card: dict, value) -> str:
    """The reported mode, or the card's highest-draw mode when there is none (the estimator's fallback): unknown never
    means standby."""
    if any(m["name"] == value for m in card["modes"]):
        return value
    return max(card["modes"], key=lambda m: m["power_kw"])["name"]


def shed(cards: dict, mission: dict, snap: dict, reservations: dict[str, float] | None = None,
         onset_t_s: float | None = None, mode_changed_t_s: dict | None = None) -> dict:
    """onset_t_s: the first tick of the current over-limit stretch (the core carries it); the A.8 due ticks count from
    the fault when the overload came with it, else from the onset, so a deadline never moves while the load stays over.
    mode_changed_t_s: per guest, the tick its mode last changed between fresh readings (the core carries it, so a mode
    back from its stand-in is no landed step); without it, the snapshot's since_t_s."""
    reservations = reservations or {}
    guests = snap["guests"]
    modes = {g: _mode(cards[g], b["mode"]["value"]) for g, b in guests.items()}
    kw_actual = {g: b["kw_actual"]["value"] for g, b in guests.items() if _fresh(b["kw_actual"])}
    # a guest counts on a stand-in when its mode or kW is not a fresh reading: stale, substituted or missing
    missing = {g for g, b in guests.items() if modes[g] != b["mode"]["value"] or b["kw_actual"]["value"] is None}
    stale = {g for g, b in guests.items() if not (_fresh(b["mode"]) and _fresh(b["kw_actual"]))}
    draws = {g: Lg.committed_kw(cards, g, modes[g], reservations.get(g, 0.0), kw_actual.get(g)) for g in guests}
    on_loop = [g for g in guests if cards[g]["cooling"] == "chilled_water"]
    total = sum(draws.values())
    loop = sum(draws[g] for g in on_loop)
    # A guest whose mode is a fresh reading of one of its card's modes: its draw leaves a stale kW out (the mode's kW, a
    # reservation, a fresh kW), a lower bound of what it commits.
    known = {g for g, b in guests.items() if _fresh(b["mode"]) and modes[g] == b["mode"]["value"]}
    cap = {k: v["value"] for k, v in snap["capacity"].items()}
    headroom = A["power"]["shed_headroom_kw"]
    power_limit, heat_limit = cap["power"]["capacity"] - headroom, cap["heat"]["capacity"] - headroom
    spare = {"heat": heat_limit - loop, "power": power_limit - total}
    over_on = {"heat": loop > heat_limit + 1e-9, "power": total > power_limit + 1e-9}
    held = {FAULT_LINE.get(f["fault"]) for f in snap.get("faults", []) if f["state"] == "held_stale"}
    # Why a line's figures are not all fresh readings, None when they are: the power line counts every guest, the
    # chilled-water line its own.
    why = {}
    for cls, counted in (("heat", set(on_loop)), ("power", set(guests))):
        if not _fresh(snap["capacity"][cls]) or counted & stale:
            why[cls] = "feed stale"
        elif counted & missing:
            why[cls] = "reading missing"
        elif cls in held:
            why[cls] = "fault held while its votes are stale"
        else:
            why[cls] = None
    # A line over while its only stand-ins are kW readings beside fresh modes is over for certain and acted on: every
    # guest on it known, its capacity a fresh reading, no fault on it held while its votes are stale. A guest whose
    # mode is a stand-in, or a stand-in capacity, leaves the line unconfirmed and it waits.
    counted = {"heat": set(on_loop), "power": set(guests)}
    certain = {cls: over_on[cls] and counted[cls] <= known and _fresh(snap["capacity"][cls]) and cls not in held
               for cls in spare}
    acting = [cls for cls in spare if over_on[cls] and (why[cls] is None or certain[cls])]
    # The binding line is the one with the least spare: a line that is over always names the record and, with both
    # over, the more over does. Equal spare binds on cooling, as the shed ceiling min(power, heat) reads it. When D4
    # acts, it is the least spare of the lines it acts on.
    binding_cls = min(acting or spare, key=spare.get)
    load, limit = (loop, heat_limit) if binding_cls == "heat" else (total, power_limit)
    steps = Lg.ladder(cards, modes, mission, for_shed=True)
    confirmed = [f for f in snap.get("faults", []) if f["state"] == "confirmed"]
    record = {
        "kind": "D4", "tick": snap["run"]["tick"], "t_s": snap["run"]["t_ship_s"], "applies_at_tick": snap["run"]["tick"] + 1,
        "mission": mission["id"], "load_kw": load, "limit_kw": limit, "draws": draws,
        "total_kw": total, "loop_kw": loop, "power_limit_kw": power_limit, "heat_limit_kw": heat_limit,
        "on_loop": on_loop, "capacities": {cls: cap[cls] for cls in ("power", "heat")},
        "binding": {"class": binding_cls, "capacity": cap[binding_cls]["capacity"], "demand": load,
                    "free": cap[binding_cls]["capacity"] - load, "unit": "kW", "degraded_by": cap[binding_cls]["degraded_by"]},
        "steps": [], "armed": [], "losses": {},
        "envelope": {g: {"mode": modes[g], "kw": draws[g], "activity": guests[g].get("activity", {}).get("value"),
                         "envelope_mode": Lg.envelope_mode(A, cards[g]), "envelope_kw": Lg.envelope_kw(A, cards[g]),
                         "cooling": cards[g]["cooling"]} for g in guests},
    }
    if confirmed:
        newest = max(confirmed, key=lambda f: f["confirmed_t_s"])
        record.update(raw_event_t_s=newest["raw_event_t_s"], confirmed_t_s=newest["confirmed_t_s"],
                      first_shed_due_t_s=newest["first_shed_due_t_s"], trigger=newest["fault"], trigger_subject=newest["subject"],
                      trigger_injected=newest.get("injected", False))
    t = record["t_s"]
    onset = onset_t_s if onset_t_s is not None else t
    if confirmed and onset <= newest["confirmed_t_s"]:
        first_due, full_due = newest["first_shed_due_t_s"], newest["full_sequence_due_t_s"]
    else:
        first_due, full_due = onset + RT["shed_first_action"], onset + RT["shed_full_sequence"]
    record["first_shed_due_t_s"], record["full_sequence_due_t_s"] = first_due, full_due
    over = over_on["power"] or over_on["heat"]
    # the relieving steps in ladder order, the whole ladder when it cannot fit (the record then shows what is still over).
    # A line on a stand-in has no limit in the walk, so no step is taken for it. A line over for certain walks on its
    # load, every draw on it a lower bound from a fresh mode.
    no_limit = float("inf")
    walks = (lambda cls: why[cls] is None or certain[cls])
    needed = Lg.walk(steps, total, power_limit if walks("power") else no_limit, loop_kw=loop,
                     loop_limit=heat_limit if walks("heat") else no_limit, loop_guests=on_loop)[0] if acting else []
    # A.8 as priorities: the 5 S steps go together as the first action; a 60 S step goes alone, and the next one
    # only on a later tick, after a fresh reading shows it is still needed (ARCHITECTURE: rechecked after each step).
    first = [s for s in needed if s.response == "shed_first_action"]
    taken = first if first else needed[:1]
    queued = needed[len(taken):]
    due = {"shed_first_action": first_due, "shed_full_sequence": full_due}
    record["verdict"] = "shed" if taken else ("hold" if not over else "unconfirmed")
    # The first action is due by the 5 s tick: every 5 S step, and a lone 60 S step when it goes first, on the stretch's
    # first tick or later while no step of the stretch has landed (no guest's fresh mode has changed since the onset,
    # as when D4 was held back by a stand-in). A 60 S step after one has landed is part of the full sequence, due by 60 s.
    changed = {g: (b["mode"].get("since_t_s") if mode_changed_t_s is None else mode_changed_t_s.get(g)) for g, b in guests.items()}
    landed = any(_fresh(b["mode"]) and changed[g] is not None and changed[g] > onset for g, b in guests.items())
    now = dict(due, shed_full_sequence=first_due) if onset == t or not landed else due
    record["steps"] = [_step(s, now) for s in taken]
    record["queued"] = [_step(s, due) for s in queued]
    record["armed"] = [_step(s, due) for s in steps if s not in taken]   # the whole armed ladder, in its order (DEC-61)
    record["responses"] = {g: Lg.response_of(cards, g, mission) for g in guests}
    record["total_after_kw"] = total - sum(s.frees_kw for s in taken)
    record["loop_after_kw"] = loop - sum(s.frees_kw for s in taken if s.guest in on_loop)
    after = record["loop_after_kw"] if binding_cls == "heat" else record["total_after_kw"]
    record["load_after_kw"] = after
    record["free_after_kw"] = limit - after
    for g in guests:
        before = Lg.mode_of(cards[g], modes[g])["capability_retained"]
        mode_after = modes[g]
        for s in taken:
            if s.guest == g:
                mode_after = s.to_mode
        record["losses"][g] = {"mode_before": modes[g], "mode_after": mode_after, "capability_before": before,
                               "capability_after": Lg.mode_of(cards[g], mode_after)["capability_retained"]}
    if over and not taken and why[binding_cls]:
        record["unconfirmed_because"] = why[binding_cls]
    return record


def _step(s: Lg.Step, due: dict) -> dict:
    return {"guest": s.guest, "from_mode": s.from_mode, "to_mode": s.to_mode, "frees_kw": s.frees_kw,
            "cost_per_kw": round(s.price, 4), "capability_lost_pct": round(100 * s.capability_lost, 1),
            "mission_critical": s.mission_critical, "shed": s.shed, "response": s.response, "due_t_s": due[s.response]}
