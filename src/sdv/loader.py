"""Load and check the ArgOS inputs: ship profile, signal vocabulary, guest cards and priority files.

Every name a card or priority file uses is checked against config/signals.yaml (signals and the per-guest
activity registry) and config/assumptions.yaml (positions, rules). A file that fails is refused with the file
and the field named. try_load keeps the previous version when a reload fails, so a bad jury card or priority
file never replaces a good one (brief: Scenario A, D1; DESIGN_FREEZE delta 2 and delta 3).

load_cards never raises: a file in manifests/ that fails is left out and reported through `refused`, so one bad
file never blocks start-up. A card handed over as a file (sdv admit --card) goes through load_card with
allow_unregistered: with no activity registry for its id it is judged with an empty activity set, admitted on its
quantities, positions and relations only, and the caller says so.
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


def check_card(card: dict, vocab: Vocabulary, schema: dict, allow_unregistered: bool = False) -> list[str]:
    """Every problem with one guest card, each naming its field. Empty means the card loads.

    A card whose id has no activity registry in config/signals.yaml is refused, unless allow_unregistered: a jury
    card handed over as a file is then judged with an empty activity set. Its conditions and exclusions are still
    checked for signal names and values, but not for activity names, so admission rests on its quantities,
    positions and relations only (D1 reads no condition; activities matter at sea, to D3 and D5)."""
    problems = _schema_problems(card, schema)
    if problems:
        return problems
    gid = card["id"]
    registered = gid in vocab.activities
    if not registered and not allow_unregistered:
        return [f"id: {gid} has no activity registry in config/signals.yaml"]
    acts = vocab.activities.get(gid, {})
    modes = {m["name"] for m in card["modes"]}
    for i, c in enumerate(card.get("conditions", [])):
        where = f"conditions[{i}]"
        if registered and c["activity"] not in acts:
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
        if registered and ex["activity"] not in acts:
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
    if "tiers" in doc:
        return ["tiers: replaced by response.safety_command (200 MS) and shed_order (DEC-60); mission_critical is 60 S, every other guest 5 S"]
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
    for i, gid in enumerate((doc.get("response") or {}).get("safety_command", [])):
        if gid not in cards:
            problems.append(f"response.safety_command[{i}]: no loaded card {gid}")
        elif gid in doc["mission_critical"]:
            problems.append(f"response.safety_command[{i}]: {gid} is mission_critical (60 S); a guest has one response class")
    for i, gid in enumerate(doc["mission_critical"]):
        if gid in cards and cards[gid].get("criticality", {}).get("safety_critical"):
            problems.append(f"mission_critical[{i}]: {gid} is safety-critical on its card (200 MS); a profile cannot put it on the ladder")
    for name in doc.get("shed_order", {}):
        if name not in capabilities:
            problems.append(f"shed_order.{name}: no loaded card returns this capability")
    for rule in doc.get("confirm", {}):
        if rule not in vocab.rules:
            problems.append(f"confirm.{rule}: no rule {rule!r} in config/assumptions.yaml ({sorted(vocab.rules)})")
    return problems


def _schema(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text())


def load_card(path: Path, vocab: Vocabulary | None = None, root: Path = ROOT, allow_unregistered: bool = False) -> dict:
    """One card file, or a LoadError naming the field. A path that cannot be read (mistyped, a directory, not UTF-8
    text) and a file YAML cannot parse are refused the same way, so neither ends in a traceback on stage or at start-up."""
    vocab = vocab or load_vocabulary(root)
    try:
        card = _read(Path(path))
    except (OSError, UnicodeDecodeError) as err:
        why = (err.strerror or str(err)) if isinstance(err, OSError) else f"not UTF-8 text ({err.reason} at byte {err.start})"
        raise LoadError(path, [f"file: {why}"]) from None
    except yaml.YAMLError as err:
        mark = getattr(err, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise LoadError(path, [f"yaml: {getattr(err, 'problem', None) or ' '.join(str(err).split())}{where}"]) from None
    problems = check_card(card, vocab, _schema(root, "manifests/schema.json"), allow_unregistered)
    if problems:
        raise LoadError(path, problems)
    return card


def manifests_dir(root: Path = ROOT) -> Path:
    return root / "manifests"


def load_cards(directory: Path | None = None, vocab: Vocabulary | None = None, root: Path = ROOT,
               refused: list[LoadError] | None = None) -> dict[str, dict]:
    """Every card in manifests/ (or directory) that loads, by id. A file that fails is left out and its LoadError
    appended to `refused` (a second file with an id already loaded too), so one bad file never blocks start-up;
    sdv admit and sdv demo print the refusals once at start (refusal)."""
    vocab = vocab or load_vocabulary(root)
    cards: dict[str, dict] = {}
    seen: dict[str, Path] = {}
    for path in sorted((directory or manifests_dir(root)).glob("G*.yaml")):
        card, err = try_load(load_card, path, None, vocab, root)
        if err is None and card["id"] in seen:
            err = LoadError(path, [f"id: {card['id']} is already loaded from {seen[card['id']].name}"])
        if err is not None:
            if refused is not None:
                refused.append(err)
            continue
        cards[card["id"]] = card
        seen[card["id"]] = path
    return cards


def refusal(err: LoadError, root: Path = ROOT) -> str:
    """The one line a refused file gets at start-up: the file (relative to the repo when inside it) and its first problem."""
    path = Path(err.path)
    shown = path.relative_to(root) if path.is_absolute() and path.is_relative_to(root) else path
    return f"refused {shown}: {err.problems[0]}"


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
