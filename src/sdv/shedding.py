"""D4 degradation and shedding on one snapshot: hold, or walk the precomputed ladder until the load is within both limits.

Power and cooling are judged on their own lines (A.1, A.2): every guest's committed draw against the guest reserve less
the 5 kW headroom, and the chilled-water guests' draw against the loop's capacity less the headroom. An air-cooled
guest (G1 on the mast) counts on the bus and never on the loop, so with it aboard the two loads differ. The line that
binds is the one with the least spare: a line that is over always names the record (cooling at minute 19, power at
minute 12), and the ladder walks until both lines fit, passing over a step that relieves no line still over (switching
G1 off while only the loop is over would cost its capability for nothing). Load is the ledger's committed draw per guest (the larger of its
mode, a reservation from the decision log and a fresh reading). D4 never acts on a substituted value
(docs/STATE_ESTIMATION.md, fallback_policy): when a feed behind the over-commitment is stale, the ladder stays armed and
the record says the fault is unconfirmed.

The record also carries every guest's envelope draw beside its draw now (envelope), so a hold can say why the envelope
set, every guest at its sustained worst case, does not arise (the brief's explicit minute-12 sequence, R-067).
"""
from __future__ import annotations

from sdv import ledger as Lg
from sdv import loader as Ld

A = Ld.load_assumptions()
RT = A["response_time_s"]


def _fresh(field: dict) -> bool:
    return not field.get("stale") and field.get("confidence") != "substituted"


def shed(cards: dict, mission: dict, snap: dict, reservations: dict[str, float] | None = None,
         onset_t_s: float | None = None) -> dict:
    """onset_t_s: the first tick of the current over-limit stretch (the core carries it); the A.8 due ticks count from
    the fault when the overload came with it, else from the onset, so a deadline never moves while the load stays over."""
    reservations = reservations or {}
    guests = snap["guests"]
    modes = {g: b["mode"]["value"] for g, b in guests.items()}
    kw_actual = {g: b["kw_actual"]["value"] for g, b in guests.items() if _fresh(b["kw_actual"])}
    draws = {g: Lg.committed_kw(cards, g, modes[g], reservations.get(g, 0.0), kw_actual.get(g)) for g in guests}
    on_loop = [g for g in guests if cards[g]["cooling"] == "chilled_water"]
    total = sum(draws.values())
    loop = sum(draws[g] for g in on_loop)
    cap = {k: v["value"] for k, v in snap["capacity"].items()}
    headroom = A["power"]["shed_headroom_kw"]
    power_limit, heat_limit = cap["power"]["capacity"] - headroom, cap["heat"]["capacity"] - headroom
    # The binding line is the one with the least spare: a line that is over always names the record and, with both
    # over, the more over does. Equal spare binds on cooling, as the shed ceiling min(power, heat) reads it.
    binding_cls = "heat" if heat_limit - loop <= power_limit - total else "power"
    load, limit = (loop, heat_limit) if binding_cls == "heat" else (total, power_limit)
    steps = Lg.ladder(cards, modes, mission, for_shed=True)
    confirmed = [f for f in snap.get("faults", []) if f["state"] == "confirmed"]
    unconfirmed = [f for f in snap.get("faults", []) if f["state"] == "held_stale"]
    stale_inputs = [n for n, f in snap["plant"].items() if f.get("stale")]
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
    over = total > power_limit + 1e-9 or loop > heat_limit + 1e-9
    acts = over and not unconfirmed and not stale_inputs
    # the relieving steps in ladder order, the whole ladder when it cannot fit (the record then shows what is still over)
    needed = Lg.walk(steps, total, power_limit, loop_kw=loop, loop_limit=heat_limit, loop_guests=on_loop)[0] if acts else []
    # A.8 as priorities: the 5 S steps go together as the first action; a 60 S step goes alone, and the next one
    # only on a later tick, after a fresh reading shows it is still needed (ARCHITECTURE: rechecked after each step).
    first = [s for s in needed if s.response == "shed_first_action"]
    taken = first if first else needed[:1]
    queued = needed[len(taken):]
    due = {"shed_first_action": first_due, "shed_full_sequence": full_due}
    record["verdict"] = "shed" if taken else ("hold" if not over else "unconfirmed")
    # On the first tick of an over-limit stretch whatever goes is the first action, due by the 5 s tick; a step taken on
    # a later tick of the same stretch is part of the full sequence, due by the 60 s tick.
    now = {k: (first_due if onset == t else full_due) for k in due}
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
    if unconfirmed or (over and stale_inputs):
        record["unconfirmed_because"] = "feed stale" if stale_inputs else "fault held while its votes are stale"
    return record


def _step(s: Lg.Step, due: dict) -> dict:
    return {"guest": s.guest, "from_mode": s.from_mode, "to_mode": s.to_mode, "frees_kw": s.frees_kw,
            "cost_per_kw": round(s.price, 4), "capability_lost_pct": round(100 * s.capability_lost, 1),
            "mission_critical": s.mission_critical, "shed": s.shed, "response": s.response, "due_t_s": due[s.response]}
