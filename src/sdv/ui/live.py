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
import re
from pathlib import Path

from sdv import loader as Ld
from sdv import loop as L
from sdv.core import PLAIN_ID
from sdv.ui.data import END_T_S, SCENARIO, Moment
from sdv.ui.view import clock

# Laptop inputs the screen may send (config/signals.yaml events with from: laptop), and the ones the core consumes.
# A safety_request is answered at once from the last tick's 200 MS table (sdv.loop.Loop.safety).
LAPTOP_INPUTS = ("priority_swap", "profile_applied", "crew_change", "deck_report", "standing_plan", "deck_sweep", "bridge_answer",
                 "safety_request")
CORE_INPUTS = ("priority_swap", "profile_applied")


def _name(x) -> str | None:
    """A file id the event log may quote, or None: never a long or punctuated text from a payload."""
    return x if isinstance(x, str) and PLAIN_ID.match(x) else None


def _no_file(mission) -> str:
    """A swap the screen refuses at the door: the name quoted only when it is a plain file name."""
    return f"no priority file {mission}" if _name(mission) else "no such priority file is loaded"


def _kept(mission_id: str) -> str:
    """The file in force after a refusal, named when its id is a plain name (an id may be any length)."""
    return f"{mission_id} kept." if _name(mission_id) else "The file in force is kept."


SHOWN_MAX = 40      # a field path or a word longer than this is cut in a row, as sdv admit cuts a long edit


def _cut(text: str) -> str:
    return re.sub(r"\S{%d,}" % (SHOWN_MAX + 1), lambda m: m.group()[:SHOWN_MAX - 3] + "...", text)


def _refusal(what: str, problem: str, kept: str) -> str:
    """A refused profile as one plain sentence, the field named as the Admission screen names it:
    "Profile jury_a refused: confirm.r3 (automatic is not a section of named fields). survey kept."
    A long field path or word is cut, and a problem that still carries braces is told as a form the field refuses."""
    field, sep, _ = problem.partition(": ")
    said = re.sub(r"'([^']*)'", r"\1", Ld.in_words(problem))
    if any(c in said for c in "{}"):
        said = "is not in a form this field allows"
    where = f"{field} ({said})" if sep and re.fullmatch(r"[\w.\[\]]+", field) else said
    return f"{what} refused: {_cut(where)}. {_kept(kept)}"


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
        self._rejected_seen = 0                 # the core's refusals already told in the event log
        self.step()

    @property
    def t(self) -> int:
        return self.loop.tick

    @property
    def sim_label(self) -> str:
        return getattr(self.loop.sim, "argos_label", "simulator")

    def add_input(self, inp: dict) -> int:
        inp = self.loop.check_input(inp)
        if inp["type"] == "safety_request":       # answered now: its record shows at once, a re-run answers it again
            k = len(self.loop.core.timing)
            self.records += self.loop.safety(inp["payload"]["request"], inp["injected"])
            for r in self.loop.core.timing[k:]:
                self.timing[r["seq"]] = r["latency_ms"]
            t = self.loop.tick
        else:
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
        # The core logs each input it refuses with its place among the tick's core inputs, read here as the loop
        # stamped them: a swap or a profile is in force unless the core refused it.
        refusals = {r["input"]: r for r in core.rejected[self._rejected_seen:]}
        self._rejected_seen = len(core.rejected)
        kept = was["id"]
        to_core = [i for i in self.loop.inputs.get(n, []) if L.EVENTS[i["type"]]["to"] == "core" and i["type"] != "safety_request"]
        for k, i in enumerate(to_core):
            if i["type"] not in CORE_INPUTS:
                continue
            payload = i.get("payload") if isinstance(i.get("payload"), dict) else {}
            refused = refusals.get(k)
            if i["type"] == "priority_swap":
                name = _name(payload.get("mission"))
                if refused:
                    what = f"Swap to {name}.yaml" if name else "Priority swap"
                    msg = f"{what} refused: no such priority file is loaded. {_kept(kept)}"
                else:   # in force: the name is a loaded file's id, schema-valid but of any length
                    kept = payload["mission"]
                    msg = f"Priority file {name}.yaml in force." if name else "Priority swap in force."
                tag = "PRIORITY"
            else:
                prof = payload.get("profile")
                if refused:
                    name = _name(prof.get("id")) if isinstance(prof, dict) else None
                    msg = _refusal(f"Profile {name}" if name else "Profile", refused["problems"][0], kept)
                else:
                    kept, name = prof["id"], _name(prof["id"])
                    msg = f"Profile {name} applied at sea and in force." if name else "Profile applied at sea and in force."
                tag = "PROFILE"
            self.inputs_log.append({"t_s": n, "type": "STATE", "tag": tag, "msg": msg, "injected": False,
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
                return _no_file(msg.get("value"))
            if self.t_s == 0:
                self._rerun(0, msg["value"], keep_inputs=False)
            else:
                self.run.add_input({"type": "priority_swap", "injected": False, "payload": {"mission": msg["value"]}})
        elif cmd == "input":
            inp = msg.get("input") if isinstance(msg.get("input"), dict) else {}
            t = inp.get("type")
            if t not in LAPTOP_INPUTS:      # quoted back only when it is a plain name, as the input check does
                return f"input {t!r} is not a laptop input" if isinstance(t, str) and L._quoted(t) \
                    else "input refused: the type given is not a laptop input"
            if not isinstance(inp.get("payload"), dict):
                return f"input {t!r} refused: payload is not an object"
            if t == "priority_swap" and inp["payload"].get("mission") not in missions:
                return _no_file(inp["payload"].get("mission"))      # the core has no such file: refused, not stamped
            try:          # off its signals.yaml contract: refused with the field named, never stamped
                checked = self.run.loop.check_input({"type": inp["type"], "injected": bool(inp.get("injected", False)),
                                                     "payload": inp["payload"]})
            except ValueError as e:
                return str(e)
            self.run.add_input(checked)
        return None
