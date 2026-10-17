"""D4 degradation and shedding on one snapshot: hold, or walk the precomputed ladder until load is within the limit.

The limit is the snapshot's shed_ceiling_kw: min(power reserve, cooling capacity) - 5 kW headroom. Load is the
ledger's committed draw per guest (the larger of its mode, a reservation from the decision log and a fresh
reading). D4 never acts on a substituted value (docs/STATE_ESTIMATION.md, fallback_policy): when a feed behind the
over-commitment is stale, the ladder stays armed and the record says the fault is unconfirmed.
"""
from __future__ import annotations

from sdv import ledger as Lg
from sdv import loader as Ld

RT = Ld.load_assumptions()["response_time_s"]


def _fresh(field: dict) -> bool:
    return not field.get("stale") and field.get("confidence") != "substituted"


def shed(cards: dict, mission: dict, snap: dict, reservations: dict[str, float] | None = None) -> dict:
    reservations = reservations or {}
    guests = snap["guests"]
    modes = {g: b["mode"]["value"] for g, b in guests.items()}
    kw_actual = {g: b["kw_actual"]["value"] for g, b in guests.items() if _fresh(b["kw_actual"])}
    draws = {g: Lg.committed_kw(cards, g, modes[g], reservations.get(g, 0.0), kw_actual.get(g)) for g in guests}
    load = sum(draws.values())
    cap = {k: v["value"] for k, v in snap["capacity"].items()}
    power, heat = cap["power"]["capacity"], cap["heat"]["capacity"]
    limit = cap["shed_ceiling_kw"]
    binding_cls, binding_cap = ("heat", heat) if heat <= power else ("power", power)
    steps = Lg.ladder(cards, modes, mission, for_shed=True)
    confirmed = [f for f in snap.get("faults", []) if f["state"] == "confirmed"]
    unconfirmed = [f for f in snap.get("faults", []) if f["state"] == "held_stale"]
    stale_inputs = [n for n, f in snap["plant"].items() if f.get("stale")]
    record = {
        "kind": "D4", "tick": snap["run"]["tick"], "t_s": snap["run"]["t_ship_s"], "applies_at_tick": snap["run"]["tick"] + 1,
        "mission": mission["id"], "load_kw": load, "limit_kw": limit, "draws": draws,
        "binding": {"class": binding_cls, "capacity": binding_cap, "demand": load, "free": binding_cap - load, "unit": "kW",
                    "degraded_by": cap[binding_cls]["degraded_by"]},
        "steps": [], "armed": [], "losses": {},
    }
    if confirmed:
        newest = max(confirmed, key=lambda f: f["confirmed_t_s"])
        record.update(raw_event_t_s=newest["raw_event_t_s"], confirmed_t_s=newest["confirmed_t_s"],
                      first_shed_due_t_s=newest["first_shed_due_t_s"], trigger=newest["fault"], trigger_subject=newest["subject"],
                      trigger_injected=newest.get("injected", False))
    t = record["t_s"]
    first_due = record.get("first_shed_due_t_s", t + RT["shed_first_action"])
    full_due = newest["full_sequence_due_t_s"] if confirmed else t + RT["shed_full_sequence"]
    record["first_shed_due_t_s"], record["full_sequence_due_t_s"] = first_due, full_due
    over = load > limit + 1e-9
    acts = over and not unconfirmed and not stale_inputs
    needed = Lg.steps_to_fit(steps, load, limit) if acts else []
    if over and needed is None:
        needed = steps  # every step there is; the record shows what is still over
    # A.8 as priorities: the 5 S steps go together as the first action; a 60 S step goes alone, and the next one
    # only on a later tick, after a fresh reading shows it is still needed (ARCHITECTURE: rechecked after each step).
    first = [s for s in needed if s.response == "shed_first_action"]
    taken = first if first else needed[:1]
    queued = needed[len(taken):]
    due = {"shed_first_action": first_due, "shed_full_sequence": full_due}
    record["verdict"] = "shed" if taken else ("hold" if not over else "unconfirmed")
    record["steps"] = [_step(s, due) for s in taken]
    record["queued"] = [_step(s, due) for s in queued]
    rest = steps[len(taken):]
    record["armed"] = [_step(s, due) for s in rest[:3]]
    record["responses"] = {g: Lg.response_of(cards, g, mission) for g in guests}
    after = load - sum(s.frees_kw for s in taken)
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
