"""Deterministic simulator: a seeded 1 Hz loop over an event timeline.

The scenario file is data (`config/scenarios/*.yaml`): guests aboard, location, events with `t_min`.
The genset trip, the drone's battery report, a cooling fault and the priority set are all events or
parameters, never code. Two runs with the same inputs and seed write byte-identical JSONL; the run's
hash is printed so replay can be checked with one command.

Open loop for now: the governor hooks in through `Simulator.on_tick` (gets the tick snapshot, may call
`request_state` / `set_mode`). Without a governor the plant follows the scripted `guest_state` events.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..data import Inputs
from ..ledger import build_lines, gauges
from .fsm import ShipFSM, pins_from_scenario
from .guests import GuestRuntime, default_placement

# Event types the plant understands. Anything else is passed to the governor hook untouched.
PLANT_EVENTS = {"baseline", "guest_report", "guest_state", "guest_mode", "genset_trip", "genset_restart",
                "cooling_degraded", "ship_state", "emission_change", "crew_change", "guest_overconsumption",
                "environment"}


@dataclass
class Simulator:
    inputs: Inputs
    seed: int = 1
    mission: str | None = None
    on_tick: Callable[[dict, "Simulator"], None] | None = None
    rng: random.Random = field(init=False)
    fsm: ShipFSM = field(init=False)
    guests: dict[str, GuestRuntime] = field(init=False)
    env: dict = field(init=False)
    t_s: int = 0
    events: list[dict] = field(default_factory=list)
    applied: list[dict] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)
    paused: bool = False

    def __post_init__(self) -> None:
        a, sc = self.inputs.assumptions, self.inputs.scenario
        self.rng = random.Random(self.seed)
        init = sc.get("initial", {})
        crew = init.get("crew", a["crew"]["levels"][0])
        self.fsm = ShipFSM(a["ship_state"], crew, self.rng, state=dict(init.get("ship_state", {})),
                           pins=pins_from_scenario(sc))
        self.env = {"seawater_c": sc["location"]["seawater_c"], "sea_state": init.get("sea_state", 2),
                    "wind_kn": init.get("wind_kn", 10)}
        self.guests = {}
        for gid in sc["guests"]:
            card = self.inputs.cards[gid]
            g = GuestRuntime(card, init.get("modes", {}).get(gid, card["modes"][0]["name"]),
                             dict(init.get("placement", {}).get(gid, default_placement(card))))
            self.guests[gid] = g
        for gid, b in init.get("battery_pct", {}).items():
            self.guests[gid].battery_pct = float(b)
            self.guests[gid].airborne = bool(init.get("airborne", {}).get(gid, False))
        self.events = sorted((dict(e, t_s=int(round(e["t_min"] * 60))) for e in sc["events"]), key=lambda e: e["t_s"])
        self.mission = self.mission or sc.get("mission")

    # -- governor-facing API ----------------------------------------------------------------------
    def request_state(self, var: str, value, source: str = "governor") -> dict:
        return self.fsm.request(var, value, self.t_s, source)

    def set_mode(self, gid: str, mode: str, source: str = "governor") -> None:
        self.guests[gid].set_mode(mode)
        self.applied.append({"t_s": self.t_s, "type": "guest_mode", "guest": gid, "mode": mode, "source": source})

    def inject(self, event: dict, source: str = "jury") -> dict:
        """An event from outside the scenario file (a keypress, a board button): it fires on the next tick,
        is recorded like a scripted one and marked `injected`, so a replay of the run reproduces it."""
        e = dict(event, t_s=self.t_s, t_min=round(self.t_s / 60, 3), injected=True, source=source)
        self.events.append(e)
        return e

    # -- events -----------------------------------------------------------------------------------
    def _apply(self, e: dict) -> None:
        t = e["type"]
        g = self.guests.get(e.get("guest", ""), None)
        if t == "baseline":
            pass
        elif t == "guest_report":
            if "battery_pct" in e and g:
                g.battery_pct = float(e["battery_pct"])
            if "wind_kn" in e:
                self.env["wind_kn"] = e["wind_kn"]
        elif t == "guest_state" and g:
            state = e["state"]
            if state == "landed_fast_charging":
                g.airborne, g.flags["landed"] = False, True
                g.set_mode("fast_charge")
                self.fsm.force("deck", "occupied", self.t_s, "G4 landed")
            elif state == "airborne":
                g.airborne = True
                g.set_mode("standby")
                self.fsm.force("deck", "clear", self.t_s, f"{g.gid} launched")
            elif state == "on_cradle":
                g.flags["on_cradle"] = True
            else:
                g.flags["state"] = state
        elif t == "guest_mode" and g:
            g.set_mode(e["mode"])
        elif t == "genset_trip":
            self.fsm.force("genset", int(e.get("gensets_online", 1)), self.t_s, "genset trip")
            if e.get("cooling") == "degraded":  # a trip may take cooling with it; it never repairs it (A.6)
                self.fsm.force("cooling", "degraded", self.t_s, "genset trip")
        elif t == "genset_restart":
            self.fsm.force("genset", int(e.get("gensets_online", 2)), self.t_s, "genset restart")
        elif t == "cooling_degraded":
            self.fsm.force("cooling", "degraded", self.t_s, e.get("confirmed_by", "plant alarm"))
        elif t == "ship_state":
            self.fsm.request(e["var"], e["value"], self.t_s, e.get("source", "scenario"))
        elif t == "emission_change":
            self.fsm.request("emission", e["value"], self.t_s, "scenario")
        elif t == "crew_change":
            self.fsm.crew = int(e["crew"])
        elif t == "guest_overconsumption" and g:
            g.over_consumption = float(e.get("factor", 1.15))
        elif t == "environment":
            self.env.update({k: v for k, v in e.items() if k in ("seawater_c", "sea_state", "wind_kn")})
        self.applied.append(dict(e, applied_at_s=self.t_s))

    # -- the loop ---------------------------------------------------------------------------------
    def tick(self) -> dict:
        a = self.inputs.assumptions
        fired = [e for e in self.events if e["t_s"] == self.t_s]
        for e in fired:
            if e["type"] in PLANT_EVENTS:
                self._apply(e)
        self.fsm.tick(self.t_s)
        sim = a.get("sim", {})
        for g in self.guests.values():
            g.tick_battery(1.0, a["rules"]["r3"]["drain_pct_min"], sim.get("g4_charge_pct_min", {}))
        lines = build_lines(a, self.fsm.snapshot(), self.env, self.guests)
        snap = {
            "t_s": self.t_s,
            "t_min": round(self.t_s / 60, 3),
            "mission": self.mission,
            "ship": self.fsm.snapshot(),
            "env": dict(self.env),
            "guests": {gid: g.snapshot() for gid, g in self.guests.items()},
            "gauges": gauges(lines),
            "lines": {k: v.as_dict() for k, v in lines.items()},
            "events": [{k: v for k, v in e.items() if k not in ("t_s",)} for e in fired],
        }
        if self.on_tick:
            self.on_tick(snap, self)
        self.snapshots.append(snap)
        self.t_s += 1
        return snap

    def run(self, until_min: float, realtime_factor: float = 0.0, sink: Callable[[dict], None] | None = None) -> str:
        """Run to `until_min` ship minutes. `realtime_factor` > 0 paces wall time (12 = 12 ship-minutes per
        wall minute); 0 runs flat out. Returns the run hash."""
        end = int(round(until_min * 60))
        t0 = time.monotonic()
        while self.t_s <= end:
            snap = self.tick()
            if sink:
                sink(snap)
            if realtime_factor > 0:
                while self.paused:  # the clock stands still; the sink keeps reading keys
                    time.sleep(0.05)
                    t0 += 0.05
                    if sink:
                        sink(None)
                due = t0 + self.t_s / realtime_factor
                delay = due - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        return self.run_hash()

    def run_hash(self) -> str:
        """Hash of every snapshot, decisions included; wall-time latency fields are left out so two runs
        of the same inputs and seed hash the same (replay is the redundancy check)."""
        h = hashlib.sha256()
        for s in self.snapshots:
            h.update(json.dumps(_strip_timing(s), sort_keys=True).encode())
        return h.hexdigest()[:16]

    def header(self) -> dict:
        return {"scenario": self.inputs.scenario["id"], "seed": self.seed, "mission": self.mission,
                "crew": self.fsm.crew, "inputs": self.inputs.hashes}


TIMING_KEYS = {"latency_ms", "within_ceiling"}


def _strip_timing(obj):
    if isinstance(obj, dict):
        return {k: _strip_timing(v) for k, v in obj.items() if k not in TIMING_KEYS}
    if isinstance(obj, list):
        return [_strip_timing(v) for v in obj]
    return obj


def write_jsonl(path: Path, sim: Simulator) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write(json.dumps({"header": sim.header()}, sort_keys=True) + "\n")
        for s in sim.snapshots:
            f.write(json.dumps(s, sort_keys=True) + "\n")
        decisions = [d for s in sim.snapshots for d in s.get("decisions", [])]
        f.write(json.dumps({"run_hash": sim.run_hash(), "events_applied": sim.applied, "fsm_log": sim.fsm.log,
                            "decisions": decisions}, sort_keys=True) + "\n")
