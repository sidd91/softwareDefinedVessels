"""Load and check the ArgOS inputs: ship profile, signal vocabulary, guest cards and priority files.

Every name a card or priority file uses is checked against config/signals.yaml (signals and the per-guest
activity registry) and config/assumptions.yaml (positions, rules). A file that fails is refused with the file
and the field named. try_load keeps the previous version when a reload fails, so a bad jury card or priority
file never replaces a good one (brief: Scenario A, D1; DESIGN_FREEZE delta 2 and delta 3).
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONDITION_TYPES = {"enum", "boolean", "number", "integer"}


class LoadError(Exception):
    """A refused input: the file and every problem found, each naming its field."""

    def __init__(self, path: str | Path, problems: list[str]):
        self.path = str(path)
        self.problems = list(problems)
        super().__init__(f"{self.path}: " + "; ".join(self.problems))


@dataclass(frozen=True)
class Vocabulary:
    signals: dict[str, dict]
    activities: dict[str, dict[str, dict]]
    positions: frozenset[str]
    rules: frozenset[str]


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def load_assumptions(root: Path = ROOT) -> dict:
    return _read(root / "config/assumptions.yaml")


def load_vocabulary(root: Path = ROOT, assumptions: dict | None = None) -> Vocabulary:
    s = _read(root / "config/signals.yaml")
    a = assumptions if assumptions is not None else load_assumptions(root)
    return Vocabulary(
        signals={x["name"]: x for x in s["signals"]},
        activities=s["activities"],
        positions=frozenset(a["positions"]),
        rules=frozenset(a.get("rules", {})),
    )


def _path(parts) -> str:
    out = ""
    for p in parts:
        out += f"[{p}]" if isinstance(p, int) else (f".{p}" if out else str(p))
    return out or "(root)"


def _schema_problems(doc: Any, schema: dict) -> list[str]:
    v = jsonschema.Draft202012Validator(schema)
    return [f"{_path(e.absolute_path)}: {e.message}" for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path))]


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _value_problem(sig: dict, value) -> str | None:
    t = sig["type"]
    if t == "enum":
        return None if value in sig["values"] else f"{value!r} is not one of {sig['values']}"
    if t == "boolean":
        return None if isinstance(value, bool) else f"{value!r} is not true or false"
    if t in ("number", "integer"):
        if not _number(value) or (t == "integer" and not float(value).is_integer()):
            return f"{value!r} is not a{'n integer' if t == 'integer' else ' number'}"
        lo, hi = sig.get("range", [None, None])
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            return f"{value} is outside {lo} to {hi} {sig.get('unit', '')}".rstrip()
        return None
    return f"signal type {t} cannot be compared"


def _predicate_problem(sig: dict, pred) -> str | None:
    t = sig["type"]
    if t not in CONDITION_TYPES:
        return f"a {t} signal cannot be a condition"
    if isinstance(pred, dict):
        if t not in ("number", "integer"):
            return "a range needs a number signal"
        for k in ("min", "max"):
            if k in pred and (p := _value_problem(sig, pred[k])):
                return f"{k}: {p}"
        if "min" in pred and "max" in pred and pred["min"] > pred["max"]:
            return f"min {pred['min']} is above max {pred['max']}"
        return None
    if isinstance(pred, list):
        if t != "enum":
            return "a list of choices needs an enum signal; use {min, max} for numbers"
        bad = [x for x in pred if x not in sig["values"]]
        return f"{bad} not among {sig['values']}" if bad else None
    return _value_problem(sig, pred)


def _activity_ref_problem(ref: str, vocab: Vocabulary) -> str | None:
    gid, _, act = ref.partition(".")
    if gid not in vocab.activities:
        return f"{ref}: no guest {gid}"
    if act not in vocab.activities[gid]:
        return f"{ref}: {gid} has no activity {act!r} ({sorted(vocab.activities[gid])})"
    return None


def check_card(card: dict, vocab: Vocabulary, schema: dict) -> list[str]:
    """Every problem with one guest card, each naming its field. Empty means the card loads."""
    problems = _schema_problems(card, schema)
    if problems:
        return problems
    gid = card["id"]
    acts = vocab.activities.get(gid)
    if acts is None:
        return [f"id: {gid} has no activity registry in config/signals.yaml"]
    modes = {m["name"] for m in card["modes"]}
    for i, c in enumerate(card.get("conditions", [])):
        where = f"conditions[{i}]"
        if c["activity"] not in acts:
            problems.append(f"{where}.activity: {c['activity']!r} is not a {gid} activity ({sorted(acts)})")
        for name, pred in c["requires"].items():
            sig = vocab.signals.get(name)
            if sig is None:
                problems.append(f"{where}.requires.{name}: unknown signal")
            elif p := _predicate_problem(sig, pred):
                problems.append(f"{where}.requires.{name}: {p}")
    for i, lim in enumerate(card.get("hard_limits", [])):
        where = f"hard_limits[{i}]"
        sig = vocab.signals.get(lim["when"]["signal"])
        if sig is None:
            problems.append(f"{where}.when.signal: unknown signal {lim['when']['signal']!r}")
        elif p := _value_problem(sig, lim["when"]["value"]):
            problems.append(f"{where}.when.value: {p}")
        if lim["then"]["action"] == "mode" and lim["then"].get("mode") not in modes:
            problems.append(f"{where}.then.mode: {lim['then'].get('mode')!r} is not one of {gid}'s modes {sorted(modes)}")
    rel = card.get("relations", {})
    for i, ex in enumerate(rel.get("excludes", [])):
        where = f"relations.excludes[{i}]"
        if ex["activity"] not in acts:
            problems.append(f"{where}.activity: {ex['activity']!r} is not a {gid} activity")
        if p := _activity_ref_problem(ex["excludes"], vocab):
            problems.append(f"{where}.excludes: {p}")
    for i, pos in enumerate(rel.get("requires", [])):
        if pos not in vocab.positions:
            problems.append(f"relations.requires[{i}]: {pos!r} is not a ship position")
    return problems


def check_mission(mission: dict, cards: dict[str, dict], vocab: Vocabulary, schema: dict) -> list[str]:
    """Every problem with one priority file against the loaded cards and the ship profile."""
    doc = json.loads(json.dumps(mission))  # YAML writes crew levels as ints; the schema reads the JSON form
    for rule, levels in (doc.get("confirm") or {}).items():
        doc["confirm"][rule] = {str(k): v for k, v in levels.items()}
    problems = _schema_problems(doc, schema)
    if problems:
        return problems
    capabilities = {c["capability"]["name"] for c in cards.values()}
    for name in doc["weights"]:
        if name not in capabilities:
            problems.append(f"weights.{name}: no loaded card returns this capability ({sorted(capabilities)})")
    for i, gid in enumerate(doc["mission_critical"]):
        if gid not in cards:
            problems.append(f"mission_critical[{i}]: no loaded card {gid}")
    for name in doc.get("shed_order", {}):
        if name not in capabilities:
            problems.append(f"shed_order.{name}: no loaded card returns this capability")
    for rule in doc.get("confirm", {}):
        if rule not in vocab.rules:
            problems.append(f"confirm.{rule}: no rule {rule!r} in config/assumptions.yaml ({sorted(vocab.rules)})")
    return problems


def _schema(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text())


def load_card(path: Path, vocab: Vocabulary | None = None, root: Path = ROOT) -> dict:
    vocab = vocab or load_vocabulary(root)
    card = _read(Path(path))
    problems = check_card(card, vocab, _schema(root, "manifests/schema.json"))
    if problems:
        raise LoadError(path, problems)
    return card


def load_cards(directory: Path | None = None, vocab: Vocabulary | None = None, root: Path = ROOT) -> dict[str, dict]:
    vocab = vocab or load_vocabulary(root)
    cards = {}
    for path in sorted((directory or root / "manifests").glob("G*.yaml")):
        card = load_card(path, vocab, root)
        cards[card["id"]] = card
    return cards


def load_mission(path: Path, cards: dict[str, dict], vocab: Vocabulary | None = None, root: Path = ROOT) -> dict:
    vocab = vocab or load_vocabulary(root)
    mission = _read(Path(path))
    problems = check_mission(mission, cards, vocab, _schema(root, "config/missions/schema.json"))
    if problems:
        raise LoadError(path, problems)
    return mission


def load_missions(cards: dict[str, dict], vocab: Vocabulary | None = None, root: Path = ROOT) -> dict[str, dict]:
    vocab = vocab or load_vocabulary(root)
    return {m["id"]: m for m in (load_mission(p, cards, vocab, root) for p in sorted((root / "config/missions").glob("*.yaml")))}


def try_load(loader: Callable[..., Any], path: Path, previous: Any, *args, **kwargs) -> tuple[Any, LoadError | None]:
    """Load path; on refusal return the previous value unchanged and the error that names the field."""
    try:
        return loader(path, *args, **kwargs), None
    except LoadError as err:
        return copy.deepcopy(previous), err
