"""The profile and rule builder (WORKLOG DEC-58): forms over the priority files and the guest cards' typed rules.

Everything a form offers comes from the loaded inputs: capabilities and guests from the cards, signals, their
types, values and ranges from config/signals.yaml, rule actions from manifests/schema.json, crew policies from
config/missions/schema.json. Every check is the loader's own (check_mission, check_card), so the builder accepts
exactly what the governor loads. A profile is saved as a new file in config/missions (loaded at the next start) or
applied at sea through the live loop's profile_applied input; a card is saved as a new draft in manifests/drafts,
which the loader does not read until it is moved into manifests/.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from sdv import ledger as Lg
from sdv import loader as Ld
from sdv.ui.data import Inputs

PROFILES_DIR = Ld.ROOT / "config/missions"
DRAFTS_DIR = Ld.ROOT / "manifests/drafts"
OPS = {"number": ["<", "<=", "==", "!=", ">=", ">"], "integer": ["<", "<=", "==", "!=", ">=", ">"],
       "enum": ["==", "!="], "boolean": ["==", "!="]}
_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")    # \Z, not $: a label never carries a trailing newline into a file name


def _schemas() -> tuple[dict, dict]:
    return Ld._schema(Ld.ROOT, "config/missions/schema.json"), Ld._schema(Ld.ROOT, "manifests/schema.json")


def catalog(I: Inputs) -> dict:
    mission_schema, card_schema = _schemas()
    caps: dict[str, list[str]] = {}
    for gid, c in sorted(I.cards.items()):
        caps.setdefault(c["capability"]["name"], []).append(gid)
    signals = []
    for name, sig in I.vocab.signals.items():
        if sig["type"] not in OPS:
            continue
        signals.append({"name": name, "type": sig["type"], "values": sig.get("values"), "range": sig.get("range"),
                        "unit": sig.get("unit", ""), "group": sig.get("group", ""), "ops": OPS[sig["type"]]})
    limit = card_schema["$defs"]["limit"]["properties"]
    policy = mission_schema["$defs"]["crew_policy"]["properties"]
    return {
        "profiles": [{"id": k, "name": m["name"], "doc": m} for k, m in sorted(I.missions.items())],
        "guests": [{"id": g, "name": c["name"], "capability": c["capability"]["name"],
                    "safety_critical": bool(c.get("criticality", {}).get("safety_critical")),
                    "modes": [m["name"] for m in c["modes"]], "hard_limits": c.get("hard_limits", []),
                    "conditions": c.get("conditions", [])} for g, c in sorted(I.cards.items())],
        "capabilities": [{"name": k, "guests": v} for k, v in sorted(caps.items())],
        "responses": [{"id": c, "tag": Lg.response_tag(I.A, c)} for c in Lg.RESPONSE],
        "rules": sorted(I.vocab.rules),
        "crew_levels": [int(k) for k in sorted(policy, key=lambda k: -int(k))],
        "policies": {k: v["enum"] for k, v in policy.items()},
        "defaults": {rule: {str(k): v for k, v in I.A["rules"][rule].get("confirm", {}).items()} for rule in sorted(I.vocab.rules)
                     if isinstance(I.A["rules"][rule], dict) and "confirm" in I.A["rules"][rule]},
        "signals": signals,
        "actions": limit["then"]["properties"]["action"]["enum"],
        "ops": limit["when"]["properties"]["op"]["enum"],
        "cards": I.cards,
    }


def check(I: Inputs, kind: str, doc: dict) -> list[str]:
    """The loader's problems with a profile or a card, each naming its field; empty when it loads."""
    mission_schema, card_schema = _schemas()
    if not isinstance(doc, dict):
        return ["(root): not an object"]
    if kind == "profile":
        return Ld.check_mission(doc, I.cards, I.vocab, mission_schema)
    if kind == "card":
        return Ld.check_card(doc, I.vocab, card_schema)
    return [f"kind: {kind!r} is not profile or card"]


def _plain(doc):
    """The form's JSON (crew levels as strings) as the YAML the loader reads (crew levels as integers)."""
    if isinstance(doc, dict):
        return {(int(k) if isinstance(k, str) and k.isdigit() else k): _plain(v) for k, v in doc.items()}
    if isinstance(doc, list):
        return [_plain(v) for v in doc]
    return doc


def save(I: Inputs, kind: str, doc: dict, label: str = "", profiles_dir: Path = PROFILES_DIR,
         drafts_dir: Path = DRAFTS_DIR) -> dict:
    """Write a valid profile or card as a new file; never overwrites. Returns {path} or {problems}."""
    problems = check(I, kind, doc)
    if problems:
        return {"problems": problems}
    if kind == "profile":
        if doc["id"] in I.missions:
            return {"problems": [f"id: {doc['id']} is already a priority file; give the new file its own id"]}
        path = Path(profiles_dir) / f"{doc['id']}.yaml"
    else:
        if label and not _NAME.match(label):
            return {"problems": ["label: lower-case letters, digits and _ only, starting with a letter"]}
        path = Path(drafts_dir) / f"{doc['id']}_{label or 'draft'}.yaml"
    if path.exists():
        return {"problems": [f"file: {path.name} exists; files are never overwritten"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(_plain(doc), sort_keys=False, allow_unicode=True, width=120))
    try:
        shown = str(path.relative_to(Ld.ROOT))
    except ValueError:
        shown = str(path)
    return {"path": shown}
