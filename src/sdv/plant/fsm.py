"""Ship state machine (brief Annex A.6).

Seven variables, each with a value set and a transition time taken from `config/assumptions.yaml`
(`ship_state`). A request does not change the state; it schedules the change after the transition time.
Where A.6 gives a range, the duration is the scenario's pin when one exists (`seed_pins`, see
`pins_from_scenario`), otherwise one draw from the run's seed, so a replay repeats it exactly (DEC-52).

Rules carried from A.6:
- course: 1-3 min to settle on `steady`; `free` is immediate.
- speed_band: 2-5 min per band crossed.
- noise: 2-4 min to reach `quiet`; leaving quiet is instant.
- deck: clearing takes 3-5 min with 14 aboard, 8-12 with 6; with 0 aboard the deck can only be clear if
  it already is (request refused). Occupying is instant.
- emission: `silent` is instant; leaving silence is a mission decision (allowed, instant, logged).
  While silent, `forbidden_actions()` lists what A.6 forbids.
- genset: a trip is a confirmed plant event (`force`), never a request; restart 5-15 min.
- cooling: degradation is a confirmed plant event, never a request; a degraded loop is not repaired at sea.
Unknown variable or value names are refused (freeze F2).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

VARS = ("course", "speed_band", "noise", "deck", "emission", "genset", "cooling")

# Scenario `seed_pins` keys -> picker keys (minutes). Other pins (confirm, approach, landing) belong to the
# governor's timeline, not to the plant.
SCENARIO_PINS = {"deck_clear_min": "deck.clear_min"}


def pins_from_scenario(scenario: dict) -> dict[str, float]:
    return {SCENARIO_PINS[k]: float(v) for k, v in scenario.get("seed_pins", {}).items() if k in SCENARIO_PINS}


@dataclass
class Pending:
    var: str
    value: object
    ready_at_s: int
    requested_at_s: int
    pick: str = "seeded"  # "pinned" or "seeded"


@dataclass
class ShipFSM:
    spec: dict  # assumptions["ship_state"]
    crew: int
    rng: random.Random
    state: dict = field(default_factory=dict)
    pins: dict = field(default_factory=dict)
    pending: list[Pending] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    now_s: int = 0
    changed_at_s: dict = field(default_factory=dict)

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
        unknown = set(self.state) - set(VARS)
        if unknown:
            raise KeyError(f"unknown ship-state variable(s) {sorted(unknown)}")
        for k, v in defaults.items():
            self.state.setdefault(k, v)
        for var in VARS:
            if self.state[var] not in self.spec[var]["values"]:
                raise ValueError(f"{var}={self.state[var]!r} not in {self.spec[var]['values']}")
            self.changed_at_s.setdefault(var, self.now_s)
        self._last_pick = "seeded"

    # -- transition times -------------------------------------------------------------------------
    def _minutes(self, key: str, lo_hi) -> float:
        """One duration for an A.6 range: the pin for `key` when given, else a seeded draw."""
        if key in self.pins:
            self._last_pick = "pinned"
            return float(self.pins[key])
        self._last_pick = "seeded"
        lo, hi = lo_hi
        return self.rng.uniform(lo, hi)

    def transition_s(self, var: str, value) -> float | str:
        """Seconds until `value` holds, or a string saying why the transition is not permitted."""
        s, cur = self.spec[var], self.state[var]
        if cur == value:
            return 0.0
        if var == "course":
            return 60 * self._minutes("course.settle_min", s["settle_min"]) if value == "steady" else 0.0
        if var == "speed_band":
            order = s["values"]
            bands = abs(order.index(value) - order.index(cur))
            return 60 * bands * self._minutes("speed_band.min_per_band", s["min_per_band"])
        if var == "noise":
            return 60 * self._minutes("noise.to_quiet_min", s["to_quiet_min"]) if value == "quiet" else 60 * s["leave_quiet_min"]
        if var == "deck":
            if value == "occupied":
                return 0.0
            rng = s["clear_min"].get(self.crew)
            if rng is None:
                return f"deck cannot be cleared with {self.crew} aboard (A.6: uncrewed only if already clear)"
            return 60 * self._minutes("deck.clear_min", rng)
        if var == "emission":
            return 60 * s["to_silent_min"] if value == "silent" else 0.0
        if var == "genset":
            if value < cur:
                return "a genset trip is a confirmed plant event, not a request"
            return 60 * self._minutes("genset.restart_min", s["restart_min"])
        if var == "cooling":
            if value == "nominal" and not s["repair_at_sea"]:
                return "cooling cannot be repaired at sea (A.6)"
            return "cooling degradation is a confirmed plant event, not a request"
        raise KeyError(var)

    # -- requests and ticking ---------------------------------------------------------------------
    def request(self, var: str, value, now_s: int, source: str = "governor") -> dict:
        """Schedule a change. Returns a record of what was accepted, refused or already true."""
        if var not in VARS:
            raise KeyError(var)
        if value not in self.spec[var]["values"]:
            raise ValueError(f"{var}={value!r} not in {self.spec[var]['values']}")
        self.now_s = now_s
        dt = self.transition_s(var, value)
        rec = {"t_s": now_s, "var": var, "value": value, "source": source}
        if isinstance(dt, str):
            rec["result"], rec["why"] = "refused", dt
        elif dt == 0:
            self.pending = [p for p in self.pending if p.var != var]
            self._settle(var, value, now_s)
            rec["result"] = "immediate"
        else:
            self.pending = [p for p in self.pending if p.var != var]
            self.pending.append(Pending(var, value, now_s + int(round(dt)), now_s, self._last_pick))
            rec["result"], rec["ready_at_s"], rec["pick"] = "scheduled", now_s + int(round(dt)), self._last_pick
        self.log.append(rec)
        return rec

    def force(self, var: str, value, now_s: int, source: str) -> None:
        """A confirmed plant event (trip, fault, landing) that bypasses transition times."""
        if var not in VARS:
            raise KeyError(var)
        if value not in self.spec[var]["values"]:
            raise ValueError(f"{var}={value!r} not in {self.spec[var]['values']}")
        self.now_s = now_s
        self._settle(var, value, now_s)
        self.pending = [p for p in self.pending if p.var != var]
        self.log.append({"t_s": now_s, "var": var, "value": value, "source": source, "result": "forced"})

    def _settle(self, var: str, value, now_s: int) -> None:
        if self.state[var] != value:
            self.changed_at_s[var] = now_s
        self.state[var] = value

    def tick(self, now_s: int) -> list[Pending]:
        self.now_s = now_s
        done = sorted((p for p in self.pending if p.ready_at_s <= now_s), key=lambda p: (p.ready_at_s, p.var))
        for p in done:
            self._settle(p.var, p.value, p.ready_at_s)
            self.log.append({"t_s": now_s, "var": p.var, "value": p.value, "source": "transition", "result": "settled"})
        self.pending = [p for p in self.pending if p.ready_at_s > now_s]
        return done

    # -- reads --------------------------------------------------------------------------------------
    def forbidden_actions(self) -> list[str]:
        """What A.6 forbids while in emission silence; empty otherwise."""
        return list(self.spec["emission"]["silent_forbids"]) if self.state["emission"] == "silent" else []

    def snapshot(self) -> dict:
        return {
            **{k: self.state[k] for k in VARS},
            "age_s": {k: self.now_s - self.changed_at_s[k] for k in VARS},
            "pending": [{"var": p.var, "value": p.value, "ready_at_s": p.ready_at_s,
                         "eta_s": p.ready_at_s - self.now_s, "pick": p.pick} for p in self.pending],
            "forbidden_actions": self.forbidden_actions(),
            "crew": self.crew,
        }
