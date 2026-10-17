"""The live source: the tick loop (sdv.loop: simulator, estimator, core) stepped one ship second per screen tick.

A jump back re-runs the loop from tick 0 with the scripted inputs and the laptop inputs given before that tick,
which is what a replay of the logs does, so the screen never shows a state the loop could not reproduce.
Mission compare reads two reference runs, one per built-in priority file, played to the end once.
"""
from __future__ import annotations

import copy
import json

from sdv import loop as L
from sdv.ui.data import END_T_S, SCENARIO, Moment

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
    needs, the decision times, and (keep=True) the snapshots at each decision and the tick it applies."""

    def __init__(self, mission: str = "survey", inputs: dict | None = None, standby: bool = False, keep: bool = False):
        self.start = mission
        self.laptop = {int(t): [dict(i) for i in v] for t, v in (inputs or {}).items()}
        merged = L.scripted_inputs(SCENARIO)
        for t, v in self.laptop.items():
            merged.setdefault(t, []).extend(copy.deepcopy(v))
        self.loop = L.Loop(L.load_simulator(SCENARIO, mission, 0, "default"), mission=mission, inputs=merged, standby=standby)
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


class LiveReplay:
    """One browser's live run: ship time, pace, run or hold, and the laptop inputs it sends."""

    def __init__(self, mission: str = "survey", t_s: int = 0, speed: float = 12, running: bool = True, standby: bool = True,
                 speeds=(1, 12, 60)):
        self.speeds = tuple(speeds)
        self.standby = standby
        self.speed = speed if speed in self.speeds else 12
        self.run = Run(mission, standby=standby)
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

    def _rerun(self, t_s: int, start: str | None = None, keep_inputs: bool = True) -> None:
        laptop = {t: v for t, v in self.run.laptop.items() if t <= t_s} if keep_inputs else {}
        self.run = Run(start or self.run.start, laptop, standby=self.standby)
        self.run.advance_to(t_s)

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
                self._rerun(target)
            else:
                self.run.advance_to(target)
        elif cmd == "restart":
            start = self.mission if self.mission in missions else self.run.start
            self._rerun(0, start, keep_inputs=False)
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
            self.run.add_input({"type": inp["type"], "injected": bool(inp.get("injected", False)), "payload": inp["payload"]})
        return None
