"""D3: right of way when two guests' conditions on the ship state collide (ceiling 2 s).

Declared objective (README): hard limits first, then mission-weighted value from the priority file;
the cost to the loser is stated. A hard limit is a card line like `when: battery_pct < 20,
then: land within 12 min or ditch`; the guest it forces is never asked to wait for the other activity
to end (`arbitration.wait_for_hard_limit: never`). Without a forcing limit the activity with the
higher mission weight x capability proceeds; ties go to the mission-critical guest, then to the id.

What the loser keeps is the priority file's call: when the loser carries the mission (its weight is at
least the winner's, or it is mission-critical) its activity is *paused* and resumed after the
recovery window; otherwise it is *suspended*, open-ended, and the winner's full need is reserved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .data import mode as mode_of
from .decision import Binding, Decision, fmt
from .priority import is_critical, weight

_WHEN = re.compile(r"^\s*(\w+)\s*(<=|>=|==|!=|<|>)\s*([\w.]+)\s*$")
_WITHIN = re.compile(r"within\s+(\d+(?:\.\d+)?)\s*min")
_OPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def _value(token: str):
    try:
        return float(token)
    except ValueError:
        return token


@dataclass(frozen=True)
class HardLimit:
    guest: str
    when: str
    then: str
    signal: str
    op: str | None
    threshold: object
    within_min: float | None

    def holds(self, state: dict) -> bool:
        """True when the limit is active for this guest state (unknown signal = not active)."""
        if self.signal not in state:
            return False
        v = state[self.signal]
        if self.op is None:
            return bool(v)
        v = _value(str(v)) if not isinstance(v, (int, float)) else v
        return _OPS[self.op](v, self.threshold)


def hard_limits(card: dict) -> list[HardLimit]:
    out = []
    for h in card.get("hard_limits", []):
        m = _WHEN.match(h["when"])
        signal, op, thr = (m.group(1), m.group(2), _value(m.group(3))) if m else (h["when"].strip(), None, None)
        w = _WITHIN.search(h["then"])
        out.append(HardLimit(card["id"], h["when"], h["then"], signal, op, thr, float(w.group(1)) if w else None))
    return out


def active_limits(card: dict, state: dict) -> list[HardLimit]:
    return [h for h in hard_limits(card) if h.holds(state)]


@dataclass
class Party:
    """One side of the conflict: a guest, the activity it wants, and its current state."""
    guest: str
    activity: str
    state: dict = field(default_factory=dict)  # battery_pct, airborne, mode, started_min, ends_min, ...


def _deadline_min(a: dict, party: Party, limit: HardLimit, now_min: float) -> dict:
    """When a 'within N min' limit expires. For the battery rule the clock started when the threshold
    was crossed, dated back from the reported level at the R3 drain rate."""
    crossed = now_min
    if limit.signal == "battery_pct" and limit.op in ("<", "<=") and isinstance(limit.threshold, float):
        drain = float(a["rules"]["r3"]["drain_pct_min"])
        crossed = now_min - (limit.threshold - float(party.state["battery_pct"])) / drain
    deadline = crossed + limit.within_min
    return {"crossed_at_min": round(crossed, 3), "deadline_min": round(deadline, 3), "remaining_min": round(deadline - now_min, 3),
            "if_counted_from_report_min": round(now_min + limit.within_min, 3)}


def _recovery_need_min(a: dict, crew: int) -> dict:
    """Worst-case minutes to recover a drone at this crew level: confirm, clear the deck, approach (R3)."""
    picks = a["transition_picks"]["r3_worst_case"]
    approach = float(a["rules"]["r3"]["approach_min"])
    if crew == 0 or picks["clear_deck_min"].get(crew) is None:
        return {"confirm_min": None, "clear_deck_min": None, "approach_min": approach, "total_min": None}
    c, d = float(picks["confirm_min"][crew]), float(picks["clear_deck_min"][crew])
    return {"confirm_min": c, "clear_deck_min": d, "approach_min": approach, "total_min": c + d + approach}


def decide(a: dict, cards: dict, mission: dict, ship: dict, p1: Party, p2: Party, now_min: float, t_s: float = 0.0) -> Decision:
    forced = {p.guest: [h for h in active_limits(cards[p.guest], {**ship, **p.state}) if h.within_min is not None] for p in (p1, p2)}
    parties = {p.guest: p for p in (p1, p2)}

    def value(p: Party) -> float:
        card = cards[p.guest]
        retained = float(mode_of(card, p.state["mode"])["capability_retained"]) if p.state.get("mode") else 1.0
        return weight(mission, card) * max(retained, 1e-9)

    if forced[p1.guest] and not forced[p2.guest]:
        winner, loser, how = p1, p2, "hard_limit"
    elif forced[p2.guest] and not forced[p1.guest]:
        winner, loser, how = p2, p1, "hard_limit"
    else:
        ranked = sorted((p1, p2), key=lambda p: (-value(p), not is_critical(mission, p.guest), p.guest))
        winner, loser, how = ranked[0], ranked[1], "mission_value"

    wcard, lcard = cards[winner.guest], cards[loser.guest]
    w_weight, l_weight = weight(mission, wcard), weight(mission, lcard)
    loser_carries = l_weight >= w_weight or is_critical(mission, loser.guest)
    outcome = "paused" if loser_carries else "suspended"

    # Cost to the loser, in its own minutes: flown so far + the recovery window + re-settling (A.6).
    window = float(a["arbitration"]["recovery_window_min"])
    started = float(loser.state.get("started_min", now_min))
    ends = loser.state.get("ends_min")
    settle = a["ship_state"]["noise"]["to_quiet_min"]
    flown = now_min - started
    lost_lo, lost_hi = flown + window + settle[0], flown + window + settle[1]
    cost = {"minutes_lost": [round(lost_lo, 2), round(lost_hi, 2)], "open_ended": outcome == "suspended",
            "components": {"flown_min": flown, "paused_min": window, "settle_min": list(settle)},
            "resumes_at_min": None if outcome == "suspended" else round(now_min + window, 2),
            "leg_ends_at_min": None if outcome == "suspended" or ends is None else [round(ends + lost_lo, 2), round(ends + lost_hi, 2)]}

    extras = {"how": how, "winner": winner.guest, "loser": loser.guest, "winner_activity": winner.activity,
              "loser_activity": loser.activity, "loser_outcome": outcome, "cost": cost,
              "weights": {winner.guest: w_weight, loser.guest: l_weight}}
    actions: list[dict] = []
    if how == "hard_limit":
        lim = forced[winner.guest][0]
        dl = _deadline_min(a, winner, lim, now_min)
        need = _recovery_need_min(a, int(ship.get("crew", 14)))
        alt = {"wait_for": f"{loser.guest} {loser.activity} ends at minute {fmt(float(ends))}" if ends is not None else None,
               "feasible": ends is not None and ends + need["total_min"] <= dl["deadline_min"] if need["total_min"] else False}
        binding = Binding("time", f"{winner.guest} {lim.then.split(' or ')[0]}", dl["remaining_min"],
                          need["total_min"] if need["total_min"] is not None else dl["remaining_min"] + 1, "min")
        why = (f"{lim.signal.replace('_', ' ')} {fmt(float(parties[winner.guest].state[lim.signal]))} {lim.op} {fmt(lim.threshold)}, "
               f"must {lim.then.split(' or ')[0]} (by minute {fmt(dl['deadline_min'])}, {fmt(dl['remaining_min'])} min left"
               + (f" against {fmt(need['total_min'])} to confirm, clear the deck and approach" if need["total_min"] else ", nobody aboard to clear the deck")
               + (f"; waiting for the {loser.activity} to end at minute {fmt(float(ends))} is infeasible)" if ends is not None and not alt["feasible"] else ")"))
        extras.update({"hard_limit": {"guest": winner.guest, "when": lim.when, "then": lim.then}, "timing": {**dl, **need}, "alternative": alt})
        verdict = f"{winner.guest} proceeds"
    else:
        binding = Binding("mission_value", f"{winner.guest} vs {loser.guest} weighted capability", value(winner), value(loser), "")
        why = f"mission value {fmt(value(winner))} against {fmt(value(loser))} under {mission['id']}"
        verdict = f"{winner.guest} proceeds"

    if outcome == "paused":
        loser_text = (f"{loser.guest} loses {fmt(lost_lo)} to {fmt(lost_hi)} {lcard['capability']['name'].replace('_', ' ')} minutes: "
                      f"{loser.activity} paused, resumes after the {fmt(window)}-min window at minute {fmt(now_min + window)}"
                      + (f", leg ends about minute {fmt(ends + lost_lo)} to {fmt(ends + lost_hi)}" if ends is not None else "") + ".")
        hold = next((m for m in sorted(lcard["modes"], key=lambda m: m["power_kw"]) if m["power_kw"] > 0), None)
        if hold:
            actions.append({"set_mode": [loser.guest, hold["name"]], "why": f"{loser.guest} holds on {fmt(hold['power_kw'])} kW"})
        extras["reserved_kw"] = 0.0
    else:
        need_kw = max(m["power_kw"] for m in wcard["modes"])
        loser_text = (f"{loser.guest} loses at least {fmt(lost_lo)} to {fmt(lost_hi)} {lcard['capability']['name'].replace('_', ' ')} minutes, "
                      f"open-ended: {loser.activity} suspended, ship free to manoeuvre, {winner.guest}'s {fmt(need_kw)} kW reserved.")
        actions.append({"reserve_kw": [winner.guest, need_kw]})
        extras["reserved_kw"] = need_kw
    actions.append({"request_state": ["course", "free"], "why": f"{winner.guest} {winner.activity}"})
    if ship.get("deck") == "occupied":
        actions.append({"request_state": ["deck", "clear"], "why": f"{winner.guest} {winner.activity}"})
    extras["actions"] = actions
    sentence = f"{winner.guest} proceeds: {why}. {loser_text}"
    return Decision("D3", f"{winner.guest}.{winner.activity} vs {loser.guest}.{loser.activity}", verdict, binding, sentence, t_s=t_s,
                    cost_to_loser=loser_text, options=[{"guest": p.guest, "activity": p.activity, "value": round(value(p), 4),
                                                        "forced": bool(forced[p.guest])} for p in (winner, loser)],
                    mission=mission["id"], extras=extras)
