"""Ship state machine (brief Annex A.6).

Seven variables, each with a value set and a transition time taken from `config/assumptions.yaml`
(`ship_state`). A request does not change the state; it schedules the change after the transition time,
drawn once per request from the brief's range with the run's seed, so a replay repeats it exactly.

Rules carried from A.6:
- course: 1-3 min to settle on `steady`; `free` is immediate.
- speed_band: 2-5 min per band crossed.
- noise: 2-4 min to reach `quiet`; leaving quiet is instant.
- deck: clearing takes 3-5 min with 14 aboard, 8-12 with 6; with 0 aboard the deck can only be clear if
  it already is (request refused). Occupying is instant.
- emission: `silent` is instant; leaving silence is a mission decision (allowed, instant, logged).
- genset: trip is instant; restart 5-15 min.
- cooling: a degraded loop is not repaired at sea.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

VARS = ("course", "speed_band", "noise", "deck", "emission", "genset", "cooling")


@dataclass
class Pending:
    var: str
    value: object
    ready_at_s: int
    requested_at_s: int


@dataclass
class ShipFSM:
    spec: dict  # assumptions["ship_state"]
    crew: int
    rng: random.Random
    state: dict = field(default_factory=dict)
    pending: list[Pending] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        defaults = {
            "course": "free",
            "speed_band": "stopped",
            "noise": "normal",
            "deck": "clear",
            "emission": "normal",
            "genset": 2,
            "cooling": "nominal",
        }
        for k, v in defaults.items():
            self.state.setdefault(k, v)
        for var in VARS:
            if self.state[var] not in self.spec[var]["values"]:
                raise ValueError(f"{var}={self.state[var]!r} not in {self.spec[var]['values']}")

    # -- transition times -------------------------------------------------------------------------
    def _minutes(self, lo_hi) -> float:
        lo, hi = lo_hi
        return self.rng.uniform(lo, hi)

    def transition_s(self, var: str, value) -> float | None:
        """Seconds until `value` holds, or None when the transition is not permitted."""
        s, cur = self.spec[var], self.state[var]
        if cur == value:
            return 0.0
        if var == "course":
            return 60 * self._minutes(s["settle_min"]) if value == "steady" else 0.0
        if var == "speed_band":
            order = s["values"]
            bands = abs(order.index(value) - order.index(cur))
            return 60 * bands * self._minutes(s["min_per_band"])
        if var == "noise":
            return 60 * self._minutes(s["to_quiet_min"]) if value == "quiet" else 60 * s["leave_quiet_min"]
        if var == "deck":
            if value == "occupied":
                return 0.0
            rng = s["clear_min"].get(self.crew)
            return None if rng is None else 60 * self._minutes(rng)
        if var == "emission":
            return 60 * s["to_silent_min"] if value == "silent" else 0.0
        if var == "genset":
            return 0.0 if value < cur else 60 * self._minutes(s["restart_min"])
        if var == "cooling":
            return None if (value == "nominal" and not s["repair_at_sea"]) else 0.0
        raise KeyError(var)

    # -- requests and ticking ---------------------------------------------------------------------
    def request(self, var: str, value, now_s: int, source: str = "governor") -> dict:
        """Schedule a change. Returns a record of what was accepted, refused or already true."""
        if var not in VARS:
            raise KeyError(var)
        if value not in self.spec[var]["values"]:
            raise ValueError(f"{var}={value!r} not in {self.spec[var]['values']}")
        dt = self.transition_s(var, value)
        rec = {"t_s": now_s, "var": var, "value": value, "source": source}
        if dt is None:
            rec["result"] = "refused"
            rec["why"] = f"{var} -> {value} not permitted with {self.crew} aboard" if var == "deck" else f"{var} -> {value} not possible at sea"
        elif dt == 0:
            self.state[var] = value
            rec["result"] = "immediate"
        else:
            self.pending = [p for p in self.pending if p.var != var]
            self.pending.append(Pending(var, value, now_s + int(round(dt)), now_s))
            rec["result"] = "scheduled"
            rec["ready_at_s"] = now_s + int(round(dt))
        self.log.append(rec)
        return rec

    def force(self, var: str, value, now_s: int, source: str) -> None:
        """A plant event (trip, fault) that bypasses transition times."""
        self.state[var] = value
        self.pending = [p for p in self.pending if p.var != var]
        self.log.append({"t_s": now_s, "var": var, "value": value, "source": source, "result": "forced"})

    def tick(self, now_s: int) -> list[Pending]:
        done = [p for p in self.pending if p.ready_at_s <= now_s]
        for p in done:
            self.state[p.var] = p.value
            self.log.append({"t_s": now_s, "var": p.var, "value": p.value, "source": "transition", "result": "settled"})
        self.pending = [p for p in self.pending if p.ready_at_s > now_s]
        return done

    def snapshot(self) -> dict:
        return {
            **{k: self.state[k] for k in VARS},
            "pending": [{"var": p.var, "value": p.value, "ready_at_s": p.ready_at_s} for p in self.pending],
            "crew": self.crew,
        }
