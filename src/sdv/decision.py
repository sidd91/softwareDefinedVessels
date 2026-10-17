"""The decision record (docs/ARCHITECTURE.md contract 6): the one output every engine writes.

The screen, the replay check, the run file and the demo all read this record. The sentence is built
from the binding line's numbers by the engine that made the decision, never from a canned string.
Latency is measured in wall time against the brief's ceiling (A.8, `response_time_s`).
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Iterator

KINDS = {"D1": "admission", "D2": "placement", "D3": "arbitration", "D4": "shed_first_action", "D5": "crew_policy"}


@dataclass
class Binding:
    cls: str
    label: str
    capacity: float
    demand: float
    unit: str

    @property
    def free(self) -> float:
        return round(self.capacity - self.demand, 3)

    def as_dict(self) -> dict:
        return {"class": self.cls, "label": self.label, "capacity": round(self.capacity, 3),
                "demand": round(self.demand, 3), "free": self.free, "unit": self.unit}


@dataclass
class Decision:
    kind: str  # D1..D5
    subject: str
    verdict: str
    binding: Binding | None
    sentence: str
    t_s: float = 0.0
    seq: int = 0
    cost_to_loser: str | None = None
    options: list[dict] = field(default_factory=list)
    placement: dict | None = None
    inputs_hash: str = ""
    latency_ms: float = 0.0
    ceiling_ms: float = 0.0
    mission: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def within_ceiling(self) -> bool:
        return self.latency_ms <= self.ceiling_ms

    def as_dict(self) -> dict:
        d = {
            "seq": self.seq, "t_s": self.t_s, "kind": self.kind, "subject": self.subject, "verdict": self.verdict,
            "binding": self.binding.as_dict() if self.binding else None, "sentence": self.sentence,
            "cost_to_loser": self.cost_to_loser, "options": self.options, "placement": self.placement,
            "inputs_hash": self.inputs_hash, "latency_ms": round(self.latency_ms, 3), "ceiling_ms": self.ceiling_ms,
            "within_ceiling": self.within_ceiling, "mission": self.mission,
        }
        d.update(self.extras)
        return d


def ceiling_ms(assumptions: dict, kind: str) -> float:
    return float(assumptions["response_time_s"][KINDS[kind]]) * 1000.0


@contextmanager
def timed(decision_holder: dict) -> Iterator[None]:
    """Measure wall time around an engine call; the caller copies `latency_ms` into the record."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        decision_holder["latency_ms"] = (time.perf_counter() - t0) * 1000.0


def fmt(x: float) -> str:
    """Numbers in sentences: no trailing zeros, at most two decimals, halves rounded up (7.515 -> 7.52)."""
    if not isinstance(x, float):
        return str(x)
    nudged = x + (1e-9 if x >= 0 else -1e-9)
    return f"{nudged:.2f}".rstrip("0").rstrip(".") or "0"
