"""Priority files: validated before use, swapped atomically, the old one kept when the new one is bad.

A swap is the jury's "different ship" test (freeze F3). The file is checked against
`config/missions/schema.json` and then against the cards: every capability a card can return needs a
weight, every mission-critical id must be a known guest, and an optional `shed_order` may only name
known guests. A bad file is refused with the failing field; the governor keeps running on the old one.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from .data import CONFIG

SCHEMA_PATH = CONFIG / "missions" / "schema.json"


class PriorityError(ValueError):
    def __init__(self, field: str, why: str):
        super().__init__(f"{field}: {why}")
        self.field, self.why = field, why


def validate(mission: dict, cards: dict[str, dict], schema: dict | None = None) -> dict:
    schema = schema or json.loads(SCHEMA_PATH.read_text())
    try:
        jsonschema.validate(mission, schema)
    except jsonschema.ValidationError as e:
        path = ".".join(str(p) for p in e.absolute_path) or "(root)"
        raise PriorityError(path, e.message) from None
    capabilities = {c["capability"]["name"] for c in cards.values()}
    missing = sorted(capabilities - set(mission["weights"]))
    if missing:
        raise PriorityError("weights", f"no weight for capability {missing[0]!r}")
    unknown = sorted(set(mission["weights"]) - capabilities)
    if unknown:
        raise PriorityError(f"weights.{unknown[0]}", "no card returns this capability")
    for gid in mission["mission_critical"]:
        if gid not in cards:
            raise PriorityError("mission_critical", f"unknown guest {gid!r}")
    for gid in mission.get("shed_order", []):
        if gid not in cards:
            raise PriorityError("shed_order", f"unknown guest {gid!r}")
    return mission


def weight(mission: dict, card: dict) -> float:
    return float(mission["weights"][card["capability"]["name"]])


def is_critical(mission: dict, gid: str) -> bool:
    return gid in mission["mission_critical"]


class PriorityStore:
    """The active priority file and the swap that validates before it switches."""

    def __init__(self, missions: dict[str, dict], cards: dict[str, dict], active: str):
        self.cards = cards
        self.missions = {k: validate(m, cards) for k, m in missions.items()}
        self.active_id = active
        self.log: list[dict] = []

    @property
    def active(self) -> dict:
        return self.missions[self.active_id]

    def swap(self, mission: dict | str | Path, t_s: float = 0.0) -> dict:
        """Switch to a mission (dict, id, or path to a YAML file). Returns a log record; on refusal the
        record says why and the active file is unchanged."""
        try:
            if isinstance(mission, (str, Path)) and str(mission) in self.missions:
                m = self.missions[str(mission)]
            else:
                if isinstance(mission, (str, Path)):
                    try:
                        mission = yaml.safe_load(Path(mission).read_text())
                    except (OSError, yaml.YAMLError) as e:
                        raise PriorityError("(file)", f"{mission}: {e.__class__.__name__}") from None
                if not isinstance(mission, dict):
                    raise PriorityError("(root)", "the file is not a mapping")
                m = validate(mission, self.cards)
                self.missions[m["id"]] = m
            prev, self.active_id = self.active_id, m["id"]
            rec = {"t_s": t_s, "result": "swapped", "from": prev, "to": m["id"]}
        except PriorityError as e:
            rec = {"t_s": t_s, "result": "refused", "field": e.field, "why": e.why, "kept": self.active_id}
        self.log.append(rec)
        return rec
