"""What the screen reads: the engine's inputs, the Scenario B snapshot fixtures as a replay timeline, and the
decision records.

Snapshots come from tests/fixtures/snapshots (docs/STATE_ESTIMATION.md, config/snapshot.schema.json) and decision
records from tests/fixtures/records (config/decision_record.schema.json). The live engine replaces this module
later: the server only needs `moment(mission, t_s)`.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sdv import loader as Ld

ROOT = Ld.ROOT
SNAPSHOTS = ROOT / "tests/fixtures/snapshots"
RECORD_FIXTURES = ROOT / "tests/fixtures/records"
CASES = ROOT / "tests/oracles/expected_outcomes.yaml"

SCENARIO = "scenario_b"
END_T_S = 1200            # the replay stops at minute 20; the minute-24 restart is optional and has no fixture
SHARED_UNTIL_T_S = 480    # both priority files see the same ship until the minute-8 decision
REPLAY_KINDS = ("D3", "D4", "D5")
_MAIN_LINE = re.compile(r"^scenario_b_(?P<mission>[a-z_]+?)_m(?P<minute>\d\d)$")


@dataclass
class Moment:
    """The replay at one ship second: the latest snapshot at or before it and every record decided by then."""
    mission: str
    t_s: int
    snapshot: dict
    records: list
    snapshots_so_far: list = field(default_factory=list)


def load_timeline(directory: Path = SNAPSHOTS) -> dict[str, list[dict]]:
    """Per priority file, the main-line snapshots in time order (variants such as _crew0 or _stale_* are left out).
    A file without its own snapshot before the first decision uses the survey run's, relabelled."""
    found: dict[str, dict[int, dict]] = {}
    for p in sorted(directory.glob(f"{SCENARIO}_*.json")):
        m = _MAIN_LINE.match(p.stem)
        if m:
            found.setdefault(m["mission"], {})[int(m["minute"])] = json.loads(p.read_text())
    minutes = sorted(set().union(*(d.keys() for d in found.values()))) if found else []
    out = {}
    for mission, own in found.items():
        seq = []
        for minute in minutes:
            snap = own.get(minute)
            if snap is None:
                base = found.get("survey", {}).get(minute)
                if base is None or base["run"]["t_ship_s"] > SHARED_UNTIL_T_S:
                    continue
                snap = copy.deepcopy(base)
                snap["run"]["mission"] = mission
            seq.append(snap)
        out[mission] = sorted(seq, key=lambda s: s["run"]["t_ship_s"])
    return out


def _read_records(directory: Path) -> list[dict]:
    out = []
    for p in sorted(directory.glob("*.json*")):
        if p.suffix == ".jsonl":
            out += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
        elif p.suffix == ".json":
            doc = json.loads(p.read_text())
            out += doc if isinstance(doc, list) else [doc]
    return out


def load_records(directory: Path = RECORD_FIXTURES) -> dict[str, list[dict]]:
    """Per priority file, the Scenario B records (D3, D4, D5) in decision order. D1 records belong to Scenario A
    and the Admission review, which runs D1 itself."""
    by: dict[str, list[dict]] = {}
    for r in _read_records(directory) if directory.is_dir() else []:
        if r.get("kind") in REPLAY_KINDS:
            by.setdefault(r.get("mission", ""), []).append(r)
    for recs in by.values():
        recs.sort(key=lambda r: (r["tick"], r["seq"]))
    return by


class Inputs:
    """Everything loaded once at start: config, cards, priority files, the timeline and the records."""

    def __init__(self, snapshots: Path = SNAPSHOTS, records: Path = RECORD_FIXTURES):
        self.A = Ld.load_assumptions()
        self.vocab = Ld.load_vocabulary(assumptions=self.A)
        self.cards = Ld.load_cards(vocab=self.vocab)
        self.missions = Ld.load_missions(self.cards, self.vocab)
        self.signals = yaml.safe_load((ROOT / "config/signals.yaml").read_text())
        self.scenario = yaml.safe_load((ROOT / f"config/scenarios/{SCENARIO}.yaml").read_text())
        self.timeline = load_timeline(snapshots)
        self.records_dir = records
        self.records = load_records(records)
        self.cases = yaml.safe_load(CASES.read_text())["scenario_a"] if CASES.exists() else []

    @property
    def replay_missions(self) -> list[str]:
        return [m for m in ("survey", "sar") if m in self.timeline] + sorted(m for m in self.timeline if m not in ("survey", "sar"))

    def moment(self, mission: str, t_s: int) -> Moment:
        snaps = self.timeline[mission]
        seen = [s for s in snaps if s["run"]["t_ship_s"] <= t_s] or snaps[:1]
        recs = [r for r in self.records.get(mission, []) if r["tick"] <= t_s]
        return Moment(mission, t_s, seen[-1], recs, seen)

    def decision_ticks(self, mission: str) -> list[int]:
        return sorted({r["tick"] for r in self.records.get(mission, [])})
