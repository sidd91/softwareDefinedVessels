"""The tick loop, its logs and replay (docs/STATE_ESTIMATION.md "The clock and the loop", "Replay").

    run = Loop(Simulator("scenario_b", "survey", 0, "default"), mission="survey")
    for out in run.ticks(until=1200): ...           # frame, snapshot, records and commands of each tick

Each tick n: frame n = sim.step(n, commands decided on n - 1, laptop inputs stamped n for the simulator); the
estimator turns it into snapshot n; the core handles the core-only inputs stamped n and runs every decision
snapshot n triggers. Ship time is the tick; wall time appears only in the timing log. A replay reads the frame
log and the input log, never the simulator, and reproduces every snapshot and record byte for byte.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sdv.core import Core
from sdv.estimator import Estimator, r1
from sdv.loader import ROOT

EVENTS = yaml.safe_load((ROOT / "config/signals.yaml").read_text())["events"]
TICKS_PER_S = 12        # demo pacing x12: a ship minute in 5 s


def canonical(obj) -> str:
    """The log serializer: numbers to 0.1, whole numbers as integers, sorted keys, no whitespace."""
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


def load_simulator(scenario="scenario_b", mission="survey", seed=0, variant="default"):
    """Siddharth's simulator when SDV_SIM names it (module:Class); until then the labelled test double."""
    spec = os.environ.get("SDV_SIM")
    if spec:
        mod, _, cls = spec.partition(":")
        sim = getattr(importlib.import_module(mod), cls or "Simulator")(scenario, mission, seed, variant)
        sim.argos_label = spec
        return sim
    sys.path.insert(0, str(ROOT / "tests/support"))
    import sim_stub
    sim = sim_stub.Simulator(scenario, mission, seed, variant)
    sim.argos_label = "test double"
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


class Loop:
    def __init__(self, sim, mission="survey", variant="default", scenario="scenario_b", inputs: dict | None = None,
                 log_dir: Path | None = None, seed=0):
        self.sim = sim
        self.est = Estimator(scenario, mission, variant, seed)
        self.core = Core(mission)
        self.inputs = {int(k): list(v) for k, v in (inputs or {}).items()}
        self.tick = -1
        self.commands: list = []
        self.wall: list[dict] = []
        self.logs = None
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            self.logs = {k: open(log_dir / f"{k}.jsonl", "w") for k in ("frames", "inputs", "snapshots", "decisions", "timing")}

    def add_input(self, inp: dict) -> int:
        """A laptop input arriving now is stamped with the next tick (the last completed tick plus one)."""
        t = self.tick + 1
        self.inputs.setdefault(t, []).append({**inp, "t_s": t})
        return t

    def step(self) -> TickOut:
        n = self.tick + 1
        t0 = time.perf_counter()
        stamped = self.inputs.get(n, [])
        to_sim = [i for i in stamped if EVENTS[i["type"]]["to"] == "simulator"]
        to_core = [i for i in stamped if EVENTS[i["type"]]["to"] == "core"]
        frame = r1(self.sim.step(n, self.commands, to_sim))
        snap = self.est.step(frame)
        k = len(self.core.timing)
        records, commands = self.core.decide(snap, to_core)
        self.commands, self.tick = commands, n
        ms = (time.perf_counter() - t0) * 1000
        self.wall.append({"tick": n, "compute_ms": round(ms, 3)})
        if self.logs:
            self.logs["frames"].write(canonical(frame) + "\n")
            for i in stamped:
                self.logs["inputs"].write(canonical(i) + "\n")
            self.logs["snapshots"].write(canonical(snap) + "\n")
            for r in records:
                self.logs["decisions"].write(canonical(r) + "\n")
            for t in self.core.timing[k:]:
                self.logs["timing"].write(canonical(t) + "\n")
            self.logs["timing"].write(canonical({"tick": n, "compute_ms": round(ms, 3)}) + "\n")
        return TickOut(n, frame, snap, records, commands, stamped)

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
