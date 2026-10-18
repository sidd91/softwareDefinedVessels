"""The tick loop, its logs and replay (docs/STATE_ESTIMATION.md "The clock and the loop", "Replay").

    run = Loop(Simulator("scenario_b", "survey", 0, "default"), mission="survey")
    for out in run.ticks(until=1200): ...           # frame, snapshot, records and commands of each tick

Each tick n: frame n = sim.step(n, commands decided on n - 1, laptop inputs stamped n for the simulator); the
estimator turns it into snapshot n; the core handles the core-only inputs stamped n and runs every decision
snapshot n triggers. Ship time is the tick; wall time appears only in the timing log. A replay reads the frame
log and the input log, never the simulator, and reproduces every snapshot and record byte for byte.
"""
from __future__ import annotations

import copy
import importlib
import json
import math
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sdv.core import Core
from sdv.estimator import Estimator, r1
from sdv.loader import ROOT

SIGNALS = yaml.safe_load((ROOT / "config/signals.yaml").read_text())
EVENTS, FEEDS = SIGNALS["events"], list(SIGNALS["feeds"])
TICKS_PER_S = 12        # demo pacing x12: a ship minute in 5 s


def canonical(obj) -> str:
    """The log serializer of frames, snapshots, records and timing: numbers to 0.1, whole numbers as integers, sorted
    keys, no whitespace. Inputs are logged exact instead."""
    def norm(x):
        if isinstance(x, bool) or x is None or isinstance(x, str):
            return x
        if isinstance(x, (int, float)):
            v = round(float(x), 1)
            return int(v) if v.is_integer() else v
        if isinstance(x, dict):
            return {k: norm(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [norm(v) for v in x]
        return x
    return json.dumps(norm(obj), sort_keys=True, separators=(",", ":"))


def exact(obj) -> str:
    """The input log serializer: sorted keys, no whitespace, every number as it was sent. A juror's weight of 0.24 must
    reach the standby and a replay as 0.24, not canonical's 0.2. A log line read back gives the same input."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _conform(field: str, want, v, guests):
    """One payload value against its events type (config/signals.yaml): the value, a whole-number float in an integer
    field made an integer, or ValueError naming the field."""
    number = isinstance(v, (int, float)) and not isinstance(v, bool)
    if number and isinstance(v, float) and math.isfinite(v) and v.is_integer() and (
            want == "integer" or (isinstance(want, list) and all(isinstance(c, int) for c in want))):
        v = int(v)                          # 6.0 sent for crew level 6 is the level 6
    choices = want if isinstance(want, list) else guests if want == "guest" else FEEDS if want == "feed" else None
    if choices is not None:
        if any(v == c and type(v) is type(c) for c in choices):
            return v
        raise ValueError(f"{field} {v!r} is not one of {', '.join(map(str, choices))}")
    ok = {"string": isinstance(v, str), "object": isinstance(v, dict), "boolean": isinstance(v, bool), "any": True,
          "integer": number and isinstance(v, int),
          "number": number and math.isfinite(v), "number?": v is None or (number and math.isfinite(v))}.get(want, False)
    if not ok:                              # a type the check does not know is refused, never waved through
        what = {"string": "text", "object": "an object", "boolean": "true or false", "integer": "a whole number",
                "number": "a number", "number?": "a number"}.get(want, f"of type {want}")
        raise ValueError(f"{field} {v!r} is not {what}")
    return v


def check_input(inp: dict, guests=()) -> dict:
    """A laptop input against its config/signals.yaml events contract, before the simulator or the estimator sees it:
    {type, injected, payload} as it will be stamped, or ValueError naming the field that breaks the contract."""
    t = inp.get("type")
    try:
        ev = EVENTS.get(t) if isinstance(t, str) else None
        if ev is None or "laptop" not in ev["from"]:
            raise ValueError(f"{t} is not a laptop input")
        if not isinstance(inp.get("payload"), dict):
            raise ValueError("payload is not an object")
        spec, optional, payload = ev["payload"], ev.get("optional", []), inp["payload"]
        extra = sorted(k for k in payload if k not in spec)
        if extra:
            raise ValueError(f"{extra[0]} is not in the contract")
        missing = [k for k in spec if k not in payload and k not in optional]
        if missing:
            raise ValueError(f"{missing[0]} is missing")
        guests = list(guests)
        injected = _conform("injected", "boolean", inp.get("injected", False), guests)
        return {"type": t, "injected": injected, "payload": {k: _conform(k, spec[k], v, guests) for k, v in payload.items()}}
    except ValueError as e:
        raise ValueError(f"input {t!r} refused: {e}") from None


def load_simulator(scenario="scenario_b", mission="survey", seed=0, variant="default"):
    """Siddharth's simulator when SDV_SIM names it (module:Class); until then the labelled scripted plant (tests/support/sim_stub.py, the A.6 drafts)."""
    spec = os.environ.get("SDV_SIM")
    if spec:
        mod, _, cls = spec.partition(":")
        sim = getattr(importlib.import_module(mod), cls or "Simulator")(scenario, mission, seed, variant)
        sim.argos_label = spec
        return sim
    sys.path.insert(0, str(ROOT / "tests/support"))
    import sim_stub
    sim = sim_stub.Simulator(scenario, mission, seed, variant)
    sim.argos_label = "scripted plant · A.6"
    return sim


def scripted_inputs(scenario="scenario_b") -> dict[int, list]:
    """The laptop inputs the Scenario B script plays (the bridge's answer at 540 s)."""
    script = yaml.safe_load((ROOT / "config/signals.yaml").read_text())["baselines"][scenario]["script"]
    return {int(t): [{"t_s": int(t), "type": i["type"], "injected": i["injected"], "payload": i["payload"]} for i in ins]
            for t, ins in script["inputs"].items()}


@dataclass
class TickOut:
    tick: int
    frame: dict
    snapshot: dict
    records: list
    commands: list
    inputs: list = field(default_factory=list)
    standby: str | None = None          # "in step", or the first field where the standby's decision differs
    safety: dict = field(default_factory=dict)   # the 200 MS table built at this tick: request -> row (state, reason)


class Loop:
    def __init__(self, sim, mission="survey", variant="default", scenario="scenario_b", inputs: dict | None = None,
                 log_dir: Path | None = None, seed=0, standby: bool = False):
        self.sim = sim
        self.est = Estimator(scenario, mission, variant, seed)
        self.core = Core(mission)
        # DEC-56: the standby board runs its own estimator and core on the primary's frames and inputs, in lockstep
        self.standby = (Estimator(scenario, mission, variant, seed), Core(mission)) if standby else None
        self.standby_state = "in step" if standby else None
        self.lock = threading.Lock()
        self.inputs = {int(k): list(v) for k, v in (inputs or {}).items()}
        self.tick = -1
        self.commands: list = []
        self.wall: list[dict] = []
        self.logs = None
        if log_dir is not None:     # line-buffered: every tick is on disk when it is written, whatever ends the run
            log_dir.mkdir(parents=True, exist_ok=True)
            self.logs = {k: open(log_dir / f"{k}.jsonl", "w", buffering=1) for k in ("frames", "inputs", "snapshots", "decisions", "timing")}

    def check_input(self, inp: dict) -> dict:
        """The input as it will be stamped, or ValueError naming the field off its contract (check_input)."""
        return check_input(inp, tuple(self.core.cards))

    def add_input(self, inp: dict) -> int:
        """A laptop input arriving now is checked against its contract and stamped with the next tick (the last
        completed tick plus one), after any tick in progress. A safety request is answered at once instead (safety())."""
        inp = self.check_input(inp)
        if inp["type"] == "safety_request":
            self.safety(inp["payload"]["request"], inp["injected"])
            return self.tick
        with self.lock:
            t = self.tick + 1
            self.inputs.setdefault(t, []).append({**inp, "t_s": t})
            return t

    def safety(self, request: str, injected: bool = False) -> list[dict]:
        """A.8 200 ms: answered between ticks from the table built at the last completed tick n, logged with n; its
        commands join the ones decided on n and are applied in frame n + 1. A replay answers it after the decisions of n.
        The latency counts from here, so a wait for the tick in progress is in it."""
        from sdv.safety import REQUESTS
        started = time.perf_counter()
        if request not in REQUESTS:
            raise ValueError(f"no safety request {request!r} ({', '.join(REQUESTS)})")
        with self.lock:
            if self.tick < 0:
                raise RuntimeError("no safety table before the first tick")
            inp = {"t_s": self.tick, "type": "safety_request", "injected": injected, "payload": {"request": request}}
            self.inputs.setdefault(self.tick, []).append(inp)
            k = len(self.core.timing)
            records = self._answer(inp, started)
            if self.logs:
                self.logs["inputs"].write(exact(inp) + "\n")
                for r in records:
                    self.logs["decisions"].write(canonical(r) + "\n")
                for t in self.core.timing[k:]:
                    self.logs["timing"].write(canonical(t) + "\n")
                for f in self.logs.values():
                    f.flush()
            return records

    def _answer(self, inp: dict, started: float | None = None) -> list[dict]:
        records, commands = self.core.safety(inp["payload"]["request"], started)
        self.commands = self.commands + commands
        if self.standby:
            s_recs, s_cmds = self.standby[1].safety(inp["payload"]["request"])
            if self.standby_state == "in step":
                diff = (first_difference([canonical(r) for r in records], [canonical(r) for r in s_recs])
                        or first_difference([canonical(c) for c in commands], [canonical(c) for c in s_cmds]))
                if diff:
                    self.standby_state = f"out of step at tick {inp['t_s']}: {diff}"
        return records

    def step(self) -> TickOut:
        with self.lock:
            return self._step()

    def _step(self) -> TickOut:
        n = self.tick + 1
        t0 = time.perf_counter()
        stamped = self.inputs.get(n, [])
        to_sim = [i for i in stamped if EVENTS[i["type"]]["to"] == "simulator"]
        to_core = [i for i in stamped if EVENTS[i["type"]]["to"] == "core" and i["type"] != "safety_request"]
        replayed_safety = [i for i in stamped if i["type"] == "safety_request"]
        # Every side reads the frame and the core inputs as the logs hold them: the frame canonical, the inputs exact.
        line = canonical(r1(self.sim.step(n, self.commands, to_sim)))
        frame, core_in = json.loads(line), json.loads(exact(to_core))
        snap = self.est.step(frame)
        k = len(self.core.timing)
        records, commands = self.core.decide(snap, core_in)
        if core_in:         # a swap or a profile applied at sea: run.mission names the file in force from snapshot n + 1
            self.est.mission = self.core.mission["id"]
        if self.standby:
            s_snap = self.standby[0].step(json.loads(line))
            s_recs, s_cmds = self.standby[1].decide(s_snap, copy.deepcopy(core_in))
            if core_in:
                self.standby[0].mission = self.standby[1].mission["id"]
            if self.standby_state == "in step":
                diff = (first_difference([canonical(snap)], [canonical(s_snap)])
                        or first_difference([canonical(r) for r in records], [canonical(r) for r in s_recs])
                        or first_difference([canonical(c) for c in commands], [canonical(c) for c in s_cmds]))
                if diff:
                    self.standby_state = f"out of step at tick {n}: {diff}"
        self.commands, self.tick = commands, n
        for i in replayed_safety:              # a replay: the requests logged with n, answered after n's decisions
            records = records + self._answer(i)
        ms = (time.perf_counter() - t0) * 1000
        self.wall.append({"tick": n, "compute_ms": round(ms, 3)})
        if self.logs:
            self.logs["frames"].write(line + "\n")
            for i in stamped:
                self.logs["inputs"].write(exact(i) + "\n")
            self.logs["snapshots"].write(canonical(snap) + "\n")
            for r in records:
                self.logs["decisions"].write(canonical(r) + "\n")
            for t in self.core.timing[k:]:
                self.logs["timing"].write(canonical(t) + "\n")
            self.logs["timing"].write(canonical({"tick": n, "compute_ms": round(ms, 3)}) + "\n")
        return TickOut(n, frame, snap, records, self.commands, stamped, self.standby_state,
                       {k: {x: v[x] for x in ("action", "guest", "state", "reason")} for k, v in self.core.safety_table.items()})

    def ticks(self, until: int, pace: float | None = None):
        """Every tick up to `until`; with pace (ticks per wall second) the loop sleeps to each deadline and logs overruns."""
        start = time.perf_counter()
        first = self.tick + 1
        while self.tick < until:
            out = self.step()
            if pace:
                due = start + (out.tick - first + 1) / pace
                slack = due - time.perf_counter()
                if slack > 0:
                    time.sleep(slack)
                elif self.logs:
                    self.logs["timing"].write(canonical({"tick": out.tick, "overrun_ms": round(-slack * 1000, 3)}) + "\n")
            yield out

    def close(self):
        if self.logs:
            for f in self.logs.values():
                f.close()
            self.logs = None


class _Replay:
    """Plays a frame log back as a simulator: the estimator and the core never know the difference."""
    def __init__(self, frames: list[dict]):
        self.frames = frames

    def step(self, tick, commands, inputs):
        return self.frames[tick]


def replay(log_dir: Path, mission="survey", variant="default") -> tuple[list[str], list[str]]:
    """Re-run the estimator and the core from the frame log and the input log; the canonical snapshots and records."""
    frames = [json.loads(l) for l in (log_dir / "frames.jsonl").read_text().splitlines()]
    inputs: dict[int, list] = {}
    for l in (log_dir / "inputs.jsonl").read_text().splitlines():
        i = json.loads(l)
        inputs.setdefault(i["t_s"], []).append(i)
    loop = Loop(_Replay(frames), mission, variant, inputs=inputs)
    snaps, recs = [], []
    for out in loop.ticks(until=len(frames) - 1):
        snaps.append(canonical(out.snapshot))
        recs += [canonical(r) for r in out.records]
    return snaps, recs


def first_difference(a: list[str], b: list[str]) -> str | None:
    """The first line and field where two canonical logs differ, or None if they are equal."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            dx, dy = json.loads(x), json.loads(y)
            path = _diff(dx, dy, "")
            return f"line {i}: {path}"
    if len(a) != len(b):
        return f"length {len(a)} against {len(b)}"
    return None


def _diff(x, y, path):
    if isinstance(x, dict) and isinstance(y, dict):
        for k in sorted(set(x) | set(y)):
            if x.get(k) != y.get(k):
                return _diff(x.get(k), y.get(k), f"{path}.{k}")
    if isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for i, (p, q) in enumerate(zip(x, y)):
            if p != q:
                return _diff(p, q, f"{path}[{i}]")
    return f"{path}: {json.dumps(x)[:80]} against {json.dumps(y)[:80]}"
