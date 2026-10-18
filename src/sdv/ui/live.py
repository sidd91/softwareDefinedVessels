"""The live source: the tick loop (sdv.loop: simulator, estimator, core) stepped one ship second per screen tick.

A jump back re-runs the loop from tick 0 with the scripted inputs and the laptop inputs given before that tick,
which is what a replay of the logs does, so the screen never shows a state the loop could not reproduce.
Mission compare reads two reference runs, one per built-in priority file, played to the end once.
With RunLogs, every run and re-run writes the loop's five logs to its own directory, <root>/live-<start file>-<n>,
so what the screen showed can be replayed (`uv run sdv replay <dir> --mission <start file>`) and handed over.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from sdv import loop as L
from sdv.ui.data import END_T_S, SCENARIO, Moment
from sdv.ui.view import clock

# Laptop inputs the screen may send (config/signals.yaml events with from: laptop), and the ones the core consumes.
LAPTOP_INPUTS = ("priority_swap", "profile_applied", "crew_change", "deck_report", "standing_plan", "deck_sweep", "bridge_answer")
CORE_INPUTS = ("priority_swap", "profile_applied")


def _log_key(s: dict) -> tuple:
    """The fields whose change the event log reports; a snapshot is kept for the log when one of them moves."""
    crew = s["crew"]
    return (tuple((g, b["activity"]["value"]) for g, b in sorted(s["guests"].items())),
            tuple((f["fault"], f["subject"], f["state"]) for f in s.get("faults", [])),
            json.dumps(crew["bridge_requests"]["value"], sort_keys=True), crew["crew_aboard"]["value"],
            crew["hlo_deck_report"]["value"], crew["standing_plan"]["value"])


class Run:
    """One run of the loop from tick 0. Keeps the latest snapshot, every record, the snapshots the event log
    needs, the decision times, and (keep=True) the snapshots at each decision and the tick it applies. With log_dir
    the loop writes its five logs there (frames, inputs, snapshots, decisions, timing), a line per tick as it goes."""

    def __init__(self, mission: str = "survey", inputs: dict | None = None, standby: bool = False, keep: bool = False,
                 log_dir: Path | None = None):
        self.start = mission
        self.laptop = {int(t): [dict(i) for i in v] for t, v in (inputs or {}).items()}
        merged = L.scripted_inputs(SCENARIO)
        for t, v in self.laptop.items():
            merged.setdefault(t, []).extend(copy.deepcopy(v))
        self.loop = L.Loop(L.load_simulator(SCENARIO, mission, 0, "default"), mission=mission, inputs=merged, standby=standby,
                           log_dir=log_dir)
        self.records: list[dict] = []
        self.key: list[dict] = []
        self.timing: dict[int, float] = {}
        self.inputs_log: list[dict] = []
        self.snapshot: dict | None = None
        self.standby: str | None = None
        self.keep = keep
        self.stored: dict[int, dict] = {}
        self._want: set[int] = set()
        self._last_key = None
        self.step()

    @property
    def t(self) -> int:
        return self.loop.tick

    @property
    def sim_label(self) -> str:
        return getattr(self.loop.sim, "argos_label", "simulator")

    def add_input(self, inp: dict) -> int:
        t = self.loop.add_input(inp)
        self.laptop.setdefault(t, []).append({**inp, "t_s": t})
        return t

    def swaps(self) -> list[tuple[int, str]]:
        """The priority swaps asked for on the laptop, (tick they are stamped, priority file), in order."""
        return [(t, i["payload"]["mission"]) for t in sorted(self.laptop) for i in self.laptop[t] if i["type"] == "priority_swap"]

    def close(self) -> None:
        """Closes the logs; the run itself can still be read."""
        self.loop.close()

    def step(self) -> None:
        core = self.loop.core
        was = core.mission
        k = len(core.timing)
        out = self.loop.step()
        n, snap = out.tick, out.snapshot
        self.snapshot, self.standby = snap, out.standby
        self.records += out.records
        for t in core.timing[k:]:
            self.timing[t["seq"]] = t["latency_ms"]
        key = _log_key(snap)
        if snap.get("events") or key != self._last_key:
            self.key.append(snap)
            self._last_key = key
        if self.keep and (n == 0 or out.records or n in self._want):
            self.stored[n] = snap
            if out.records:
                self._want.add(n + 1)
        mine = [i for i in self.laptop.get(n, []) if i["type"] in CORE_INPUTS]
        for i in mine:
            if i["type"] == "priority_swap":
                self.inputs_log.append({"t_s": n, "type": "STATE", "tag": "PRIORITY",
                                        "msg": f"Priority file {i['payload']['mission']}.yaml in force.", "injected": False})
            else:
                prof = i["payload"]["profile"]
                refused = next((r for r in core.rejected if r["tick"] == n and r["profile"] == prof.get("id")), None)
                if refused:
                    msg = f"Profile {prof.get('id', '?')} refused: {refused['problems'][0]}. {was['id']} kept."
                else:
                    msg = f"Profile {prof['id']} applied at sea and in force."
                self.inputs_log.append({"t_s": n, "type": "STATE", "tag": "PROFILE", "msg": msg, "injected": False,
                                        "refused": bool(refused)})

    def advance_to(self, t_s: int) -> None:
        t_s = min(int(t_s), END_T_S)
        while self.t < t_s:
            self.step()

    def moment(self, t_s: int | None = None) -> Moment:
        """The run now, or (a kept reference run) at an earlier tick it stored."""
        core = self.loop.core
        if t_s is None or t_s >= self.t:
            return Moment(core.mission["id"], self.t, self.snapshot, list(self.records), list(self.key), profile=core.mission,
                          timing=dict(self.timing), standby=self.standby, inputs=list(self.inputs_log), source="live")
        at = max((t for t in self.stored if t <= t_s), default=0)
        snap = self.stored[at]
        return Moment(core.mission["id"], int(t_s), snap, [r for r in self.records if r["tick"] <= t_s],
                      [s for s in self.key if s["run"]["tick"] <= at], profile=core.mission,
                      timing={k: v for k, v in self.timing.items()}, inputs=[], source="live")


class Reference:
    """One full run per built-in priority file, for Mission compare and the jump marks."""

    def __init__(self, missions=("survey", "sar")):
        self.missions = tuple(missions)
        self._runs: dict[str, Run] | None = None

    @property
    def runs(self) -> dict[str, Run]:
        if self._runs is None:
            runs = {}
            for m in self.missions:
                r = Run(m, keep=True)
                r.advance_to(END_T_S)
                runs[m] = r
            self._runs = runs
        return self._runs

    def moment(self, mission: str, t_s: int) -> Moment:
        return self.runs[mission].moment(t_s)

    def records(self, mission: str) -> list[dict]:
        return self.runs[mission].records


def replay_line(log_dir: Path, start: str) -> str:
    """The one command that replays a logged run and compares it byte for byte."""
    return f"uv run sdv replay {log_dir} --mission {start}"


class RunLogs:
    """Where the live runs are logged: one directory per run or re-run, <root>/live-<start file>-<n>. n is a counter,
    never the clock, and counts on from the directories already there, so a server started again never overwrites
    the run the jury saw. `say` (print on the server) is told of each run and how to replay it."""

    def __init__(self, root: Path, say=None):
        self.root = Path(root)
        self.say = say
        taken = [p.name.rsplit("-", 1)[1] for p in self.root.glob("live-*-*")]
        self.n = max((int(s) for s in taken if s.isdigit()), default=0)
        self.last: tuple[Path, str] | None = None       # the directory and start file of the run begun last

    def path(self, start: str, n: int | None = None) -> Path:
        return self.root / f"live-{start}-{self.n + 1 if n is None else n}"

    def new(self, start: str) -> Path:
        self.n += 1
        d = self.path(start, self.n)
        self.last = (d, start)
        if self.say:
            self.say(f"RUN {self.n} under {start}.yaml logs to {d}; replay: {replay_line(d, start)}")
        return d


class LiveReplay:
    """One browser's live run: ship time, pace, run or hold, and the laptop inputs it sends."""

    def __init__(self, mission: str = "survey", t_s: int = 0, speed: float = 12, running: bool = True, standby: bool = True,
                 speeds=(1, 12, 60), logs: RunLogs | None = None):
        self.speeds = tuple(speeds)
        self.standby = standby
        self.logs = logs
        self.speed = speed if speed in self.speeds else 12
        self.run = Run(mission, standby=standby, log_dir=self._log_dir(mission))
        self.run.advance_to(t_s)
        self.running = running and self.t_s < END_T_S

    @property
    def t_s(self) -> int:
        return self.run.t

    @property
    def mission(self) -> str:
        return self.run.loop.core.mission["id"]

    def advance(self) -> None:
        if self.running and self.t_s < END_T_S:
            self.run.step()
        if self.t_s >= END_T_S:
            self.running = False

    def _log_dir(self, start: str) -> Path | None:
        return self.logs.new(start) if self.logs else None

    def _rerun(self, t_s: int, start: str | None = None, keep_inputs: bool = True) -> None:
        laptop = {t: v for t, v in self.run.laptop.items() if t <= t_s} if keep_inputs else {}
        start = start or self.run.start
        self.run.close()
        self.run = Run(start, laptop, standby=self.standby, log_dir=self._log_dir(start))
        self.run.advance_to(t_s)

    def close(self) -> None:
        """The browser is gone or the server stops: the run's logs are closed."""
        self.run.close()

    def command(self, msg: dict, missions=("survey", "sar")) -> str | None:
        """Apply one SIM bar or builder command; returns a refusal reason, or None."""
        cmd = msg.get("cmd")
        if cmd == "run":
            self.running = self.t_s < END_T_S
        elif cmd == "hold":
            self.running = False
        elif cmd == "toggle":
            self.running = not self.running and self.t_s < END_T_S
        elif cmd == "speed" and msg.get("value") in self.speeds:
            self.speed = msg["value"]
        elif cmd == "jump":
            target = max(0, min(int(msg.get("t", 0)), END_T_S))
            if target < self.t_s:
                dropped = [(t, m) for t, m in self.run.swaps() if t > target]    # asked after the target: not replayed
                self._rerun(target)
                for t, m in dropped:
                    self.run.inputs_log.append({"t_s": target, "type": "STATE", "tag": "PRIORITY", "injected": False, "refused": True,
                                                "msg": f"jump back: swap to {m}.yaml at {clock(t)} dropped"})
            else:
                self.run.advance_to(target)
        elif cmd == "restart":
            # a swap chosen while held is stamped for the next tick and not in force yet: it is the file the new run starts under
            pending = [m for t, m in self.run.swaps() if t > self.t_s]
            chosen = pending[-1] if pending else self.mission
            self._rerun(0, chosen if chosen in missions else self.run.start, keep_inputs=False)
            self.running = True
        elif cmd == "mission":
            if msg.get("value") not in missions:
                return f"no priority file {msg.get('value')}"
            if self.t_s == 0:
                self._rerun(0, msg["value"], keep_inputs=False)
            else:
                self.run.add_input({"type": "priority_swap", "injected": False, "payload": {"mission": msg["value"]}})
        elif cmd == "input":
            inp = msg.get("input") or {}
            if inp.get("type") not in LAPTOP_INPUTS or not isinstance(inp.get("payload"), dict):
                return f"input {inp.get('type')!r} is not a laptop input"
            if inp["type"] == "priority_swap" and inp["payload"].get("mission") not in missions:
                return f"no priority file {inp['payload'].get('mission')}"      # the core has no such file: refused, not stamped
            self.run.add_input({"type": inp["type"], "injected": bool(inp.get("injected", False)), "payload": inp["payload"]})
        return None
