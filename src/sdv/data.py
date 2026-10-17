"""Loaders for the three input files and the scenarios. One place, so every module reads the same data.

Nothing here decides anything. Hashes of the loaded inputs travel with every run so a replay can prove it
ran on the same ship, cards, priority file and scenario.
"""
from __future__ import annotations

import glob
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
MANIFESTS = ROOT / "manifests"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


@dataclass
class Inputs:
    """Everything a run reads, with a short hash per input."""

    assumptions: dict
    cards: dict[str, dict]
    missions: dict[str, dict]
    scenario: dict
    hashes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.hashes = {
            "assumptions": _digest(self.assumptions),
            "cards": _digest(self.cards),
            "missions": _digest(self.missions),
            "scenario": _digest(self.scenario),
        }


def load_assumptions(path: Path | None = None) -> dict:
    return _load_yaml(path or CONFIG / "assumptions.yaml")


def load_cards(folder: Path | None = None) -> dict[str, dict]:
    cards = {}
    for f in sorted(glob.glob(str((folder or MANIFESTS) / "G*.yaml"))):
        card = _load_yaml(Path(f))
        cards[card["id"]] = card
    return cards


def load_missions(folder: Path | None = None) -> dict[str, dict]:
    missions = {}
    for f in sorted(glob.glob(str((folder or CONFIG / "missions") / "*.yaml"))):
        m = _load_yaml(Path(f))
        missions[m["id"]] = m
    return missions


def load_scenario(name_or_path: str) -> dict:
    p = Path(name_or_path)
    if not p.exists():
        p = CONFIG / "scenarios" / f"{name_or_path.replace('-', '_')}.yaml"
    return _load_yaml(p)


def load_inputs(scenario: str) -> Inputs:
    return Inputs(load_assumptions(), load_cards(), load_missions(), load_scenario(scenario))


def mode(card: dict, name: str) -> dict:
    """The mode entry of a card by name; raises if the card has no such mode."""
    for m in card["modes"]:
        if m["name"] == name:
            return m
    raise KeyError(f"{card['id']} has no mode {name!r}")
