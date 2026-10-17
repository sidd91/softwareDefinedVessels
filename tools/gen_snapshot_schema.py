"""Generate config/snapshot.schema.json and config/frame.schema.json from config/signals.yaml.

signals.yaml is the only authority for signal names, types, feeds and events; the two schemas are derived from
it and tests/test_snapshot_contract.py fails if a committed schema differs from this generator's output.

    uv run python tools/gen_snapshot_schema.py          # rewrite both schemas
    uv run python tools/gen_snapshot_schema.py --check  # exit 1 if either is out of date
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUPS = ["plant", "ship_state", "environment", "links", "crew", "capacity"]
GUESTS = ["G1", "G2", "G3", "G4", "G5", "G6"]
SNAPSHOT_PATH = ROOT / "config/snapshot.schema.json"
FRAME_PATH = ROOT / "config/frame.schema.json"
BASE_ID = "https://github.com/GhostWalka/softwareDefinedVessels/config/"


def load_signals(root: Path = ROOT) -> dict:
    return yaml.safe_load((root / "config/signals.yaml").read_text())


def value_schema(sig: dict) -> dict:
    t, nul = sig["type"], sig.get("nullable", False)
    if t == "enum" or (t == "integer" and "values" in sig):
        return {"enum": list(sig["values"]) + ([None] if nul else [])}
    if t in ("number", "integer"):
        lo, hi = sig["range"]
        return {"type": [t, "null"] if nul else t, "minimum": lo, "maximum": hi}
    if t == "boolean":
        return {"type": ["boolean", "null"] if nul else "boolean"}
    if t == "ship_time":
        return {"type": ["number", "null"] if nul else "number"}
    if t in ("capacity", "rates", "requests", "sweep"):
        ref = {"$ref": f"#/$defs/{t}_value"}
        return {"anyOf": [ref, {"type": "null"}]} if nul else ref
    raise ValueError(f"{sig['name']}: unknown type {t}")


def sources(sig: dict) -> list:
    return sig["source"] if isinstance(sig["source"], list) else [sig["source"]]


def describe(sig: dict) -> str:
    parts = [sig.get("unit"), sig["kind"], sig["rate"], f"feed {sig['feed']}" if "feed" in sig else None]
    return "; ".join(p for p in parts if p)


def raw_signals(S: dict) -> list:
    return [s for s in S["signals"] if s["producer"] in ("simulator", "laptop")]


def shared_defs(S: dict) -> dict:
    feeds = list(S["feeds"])
    return {
        "transition": {
            "type": "object", "additionalProperties": False, "required": ["to", "started_t_s", "expected_end_t_s"],
            "description": "a change under way (an A.6 transition, a genset restart); the value moves linearly for numbers, enums keep the old value until the end tick",
            "properties": {"to": True, "started_t_s": {"type": "number"}, "expected_end_t_s": {"type": "number"},
                           "latest_end_t_s": {"type": "number"}},
        },
        "rates_value": {
            "type": "object", "additionalProperties": False,
            "properties": {k: {"type": "number", "minimum": 0} for k in ["backbone_mbps", "satcom_mbps", "los_radio_mbps", "acoustic_kbps"]},
        },
        "requests_value": {
            "type": "array", "description": "open bridge confirmation requests, one per decision that asked",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["request_seq", "rule", "state", "asked_t_s", "answered_t_s"],
                      "properties": {"request_seq": {"type": "integer", "minimum": 0}, "rule": {"type": "string"},
                                     "state": {"enum": ["pending", "confirmed", "denied"]},
                                     "asked_t_s": {"type": "number"}, "answered_t_s": {"type": ["number", "null"]}}},
        },
        "sweep_value": {
            "type": "object", "additionalProperties": False, "required": ["t_s", "result"],
            "properties": {"t_s": {"type": "number"}, "result": {"enum": ["clear", "not_clear"]}},
        },
        "capacity_value": {
            "type": "object", "additionalProperties": False, "required": ["capacity", "unit", "degraded_by", "zero_by_rule"],
            "description": "capacity of a live class; committed and free are ledger lines (ledger_rules)",
            "properties": {"capacity": {"type": "number", "minimum": 0}, "unit": {"enum": ["kW", "Mbit/s", "kbit/s"]},
                           "degraded_by": {"type": "array", "items": {"type": "string"}},
                           "zero_by_rule": {"type": "boolean", "description": "0 by rule (acoustic down, silence): demand is buffered"}},
        },
        "start": {
            "type": "object", "additionalProperties": False,
            "description": "a run's starting state (signals.yaml baselines): raw signal name (Gx.key for guests) to its value at tick 0",
            "properties": {sig["name"]: value_schema(sig) for sig in raw_signals(S)},
        },
        "event": event_schema(S, feeds),
    }


def payload_type(t, feeds: list) -> dict:
    if isinstance(t, list):
        return {"enum": t}
    simple = {"string": {"type": "string"}, "guest": {"enum": GUESTS}, "feed": {"enum": feeds},
              "number": {"type": "number"}, "number?": {"type": ["number", "null"]}, "integer": {"type": "integer"},
              "boolean": {"type": "boolean"}, "object": {"type": "object"}, "any": True, "start": {"$ref": "#/$defs/start"}}
    return simple[t]


def typed_object(spec: dict, optional: list, feeds: list) -> dict:
    return {"type": "object", "additionalProperties": False,
            "required": [k for k in spec if k not in optional],
            "properties": {k: payload_type(t, feeds) for k, t in spec.items()}}


def event_cases(S: dict, feeds: list, names: list) -> list:
    return [{"if": {"properties": {"type": {"const": n}}},
             "then": {"properties": {"payload": typed_object(S["events"][n]["payload"], S["events"][n].get("optional", []), feeds)}}}
            for n in names]


def event_schema(S: dict, feeds: list) -> dict:
    types = list(S["events"])
    cases = event_cases(S, feeds, types)
    return {
        "type": "object", "additionalProperties": False, "required": ["t_s", "type", "origin", "injected", "payload"],
        "description": "an event the simulator applied at this tick (timeline or laptop); signals.yaml events",
        "properties": {"t_s": {"type": "number"}, "type": {"enum": types}, "origin": {"enum": ["timeline", "laptop"]},
                       "injected": {"type": "boolean"}, "payload": {"type": "object"}},
        "allOf": cases,
    }


def snapshot_field(sig: dict) -> dict:
    return {"description": describe(sig), "allOf": [{"$ref": "#/$defs/field"}],
            "properties": {"value": value_schema(sig), "source": {"enum": sources(sig)}}}


def group(props: dict, title: str, required=True) -> dict:
    g = {"type": "object", "description": title, "additionalProperties": False, "properties": props}
    if required:
        g["required"] = list(props)
    return g


def build_snapshot_schema(S: dict) -> dict:
    meta = S["field_metadata"]
    groups = {g: {} for g in GROUPS}
    guests = {g: {} for g in GUESTS}
    for sig in S["signals"]:
        if sig["group"] == "guests":
            gid, key = sig["name"].split(".", 1)
            guests[gid][key] = snapshot_field(sig)
        else:
            groups[sig["group"]][sig["name"]] = snapshot_field(sig)
    feed_state = {"type": "object", "additionalProperties": False, "required": ["stale", "last_heard_t_s", "drop"],
                  "properties": {"stale": {"type": "boolean", "description": "the feed's fallbacks are in force; they lift on the first fresh frame (fallback_policy.lift)"},
                                 "last_heard_t_s": {"type": ["number", "null"]},
                                 "drop": {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
                                                                         "required": ["event_t_s", "until_t_s", "injected"],
                                                                         "properties": {"event_t_s": {"type": "number"},
                                                                                        "until_t_s": {"type": ["number", "null"]},
                                                                                        "injected": {"type": "boolean"}}}]}}}
    constants = {k: {"type": "object", "additionalProperties": False, "required": ["value", "source", "confidence"],
                     "properties": {"value": value_schema({"name": k, **c}), "source": {"const": c["source"]},
                                    "confidence": {"const": "assumed"}}}
                 for k, c in S["run_constants"].items()}
    defs = shared_defs(S)
    defs.update({
        "field": {
            "type": "object", "additionalProperties": False, "required": ["value", "source", "age_s", "confidence", "stale"],
            "properties": {
                "value": True,
                "source": {"enum": meta["source"]},
                "age_s": {"type": ["number", "null"], "minimum": 0, "description": "ship seconds since the reading (t_ship_s - t_s); 0 for a derived field; null before the first reading"},
                "confidence": {"enum": meta["confidence"]},
                "stale": {"type": "boolean", "description": "the signal's feed has gone quiet (feeds); a derived field only through a substituted input"},
                "since_t_s": {"type": "number", "description": "ship time the value last changed"},
                "reported_t_s": {"type": "number", "description": "for a crew answer: when it was given; expiry counts from here"},
                "transition": {"$ref": "#/$defs/transition"},
                "substituted": {"$ref": "#/$defs/substituted"},
                "by": {"type": "array", "items": {"enum": GUESTS}, "uniqueItems": True,
                       "description": "effect fields only: the guests whose running activity sets this value"},
            },
        },
        "substituted": {
            "type": "object", "additionalProperties": False, "required": ["last_value", "last_good_t_s", "rule", "stage"],
            "description": "the conservative fallback in use, for the decision sentence",
            "properties": {"last_value": True, "last_good_t_s": {"type": ["number", "null"]}, "rule": {"type": "string"},
                           "stage": {"enum": ["hold", "bound", "crew_report", "derived"]}, "scope": {"type": "string"}},
        },
        "fault": {
            "type": "object", "additionalProperties": False,
            "required": ["fault", "subject", "state", "raw_event_t_s", "confirmed_t_s", "votes", "first_shed_due_t_s",
                         "full_sequence_due_t_s", "healthy_since_t_s", "injected"],
            "properties": {
                "fault": {"enum": list(S["confirm_rules"])[:2]},
                "subject": {"type": "string"},
                "state": {"enum": ["pending", "held_stale", "confirmed", "restoring", "cleared"]},
                "raw_event_t_s": {"type": "number", "description": "the first tick any vote for this subject was true"},
                "confirmed_t_s": {"type": ["number", "null"]},
                "votes": {"type": "array", "uniqueItems": True,
                          "items": {"enum": list(S["confirm_rules"]["genset_trip"]["votes"]) + list(S["confirm_rules"]["cooling_degraded"]["needs_any"]) + list(S["confirm_rules"]["cooling_degraded"]["plus_any"])}},
                "first_shed_due_t_s": {"type": "number", "description": "raw_event_t_s + 5 s (A.8), ship time"},
                "full_sequence_due_t_s": {"type": "number", "description": "raw_event_t_s + 60 s (A.8), ship time"},
                "healthy_since_t_s": {"type": ["number", "null"]},
                "injected": {"type": "boolean"},
            },
        },
    })
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "snapshot.schema.json",
        "title": "ArgOS conditions snapshot",
        "description": ("GENERATED by tools/gen_snapshot_schema.py from config/signals.yaml; do not edit. One snapshot per "
                        "tick (tick n at t_ship_s n): what the state estimator hands the core. Every field carries value, "
                        "source, age_s, confidence and stale. No wall-clock time, so a replay reproduces it exactly. "
                        "Contract: docs/STATE_ESTIMATION.md."),
        "type": "object",
        "additionalProperties": False,
        "required": ["run"] + GROUPS[:5] + ["guests", "capacity", "feeds", "faults", "events"],
        "properties": {
            "run": {
                "type": "object", "additionalProperties": False,
                "required": ["contract", "scenario", "variant", "mission", "seed", "tick", "t_ship_s", "installed", "constants"],
                "properties": {
                    "contract": {"const": "argos-snapshot/2"},
                    "scenario": {"type": "string"},
                    "variant": {"type": "string", "description": "the starting state (signals.yaml baselines.<scenario>.variants, or default)"},
                    "mission": {"type": "string", "description": "the priority file in force (config/missions/<id>.yaml)"},
                    "seed": {"type": "integer"},
                    "tick": {"type": "integer", "minimum": 0, "description": "snapshot counter; tick n is at t_ship_s = n"},
                    "t_ship_s": {"type": "integer", "minimum": 0, "description": "ship seconds since minute 0 (ARCHITECTURE contract 4 calls it t_s)"},
                    "installed": {"type": "array", "items": {"enum": GUESTS}, "uniqueItems": True},
                    "constants": group(constants, "run constants stated by the scenario (signals.yaml run_constants)"),
                },
            },
            **{g: group(groups[g], g) for g in GROUPS},
            "guests": {"type": "object", "additionalProperties": False, "description": "one entry per installed guest",
                       "properties": {g: group(guests[g], g) for g in GUESTS}},
            "feeds": group({f: feed_state for f in S["feeds"]}, "health of each feed (signals.yaml feeds)"),
            "faults": {"type": "array", "items": {"$ref": "#/$defs/fault"}},
            "events": {"type": "array", "items": {"$ref": "#/$defs/event"}},
            "notes": {"type": "array", "items": {"type": "string"}, "description": "free text for fixtures; never read by the core"},
        },
        "$defs": defs,
    }


def input_schema(S: dict) -> dict:
    """A laptop input as the core passes it to sim.step (signals.yaml step.inputs)."""
    feeds = list(S["feeds"])
    names = [n for n, ev in S["events"].items() if "laptop" in ev["from"] and ev["to"] == "simulator"]
    return {
        "type": "object", "additionalProperties": False, "required": ["t_s", "type", "injected", "payload"],
        "description": "a laptop input stamped with tick t_s, passed to sim.step(t_s, commands, inputs); events with to: core never reach the simulator",
        "properties": {"t_s": {"type": "integer", "minimum": 0}, "type": {"enum": names}, "injected": {"type": "boolean"},
                       "payload": {"type": "object"}},
        "allOf": event_cases(S, feeds, names),
    }


def command_schema(S: dict) -> dict:
    """A core command (signals.yaml commands; Siddharth defines the set, contract 5)."""
    feeds = list(S["feeds"])
    cases = [{"if": {"properties": {"kind": {"const": k}}},
              "then": {"properties": {"args": typed_object(c["args"], c.get("optional", []), feeds)}}}
             for k, c in S["commands"].items()]
    return {
        "type": "object", "additionalProperties": False, "required": ["seq", "kind", "args"],
        "description": "a command decided on snapshot n - 1 and applied by sim.step in frame n; seq is the decision record that sent it",
        "properties": {"seq": {"type": "integer", "minimum": 0}, "kind": {"enum": list(S["commands"])}, "args": {"type": "object"}},
        "allOf": cases,
    }


def frame_reading(sig: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["value", "source", "t_s"],
            "description": describe(sig),
            "properties": {"value": value_schema(sig), "source": {"enum": sources(sig)},
                           "t_s": {"type": "number", "description": "the tick the reading arrived (= the frame tick), ship seconds"},
                           "transition": {"$ref": "#/$defs/transition"},
                           "reported_t_s": {"type": "number", "description": "crew answers: when the answer was given"}}}


def build_frame_schema(S: dict) -> dict:
    raw = raw_signals(S)
    flat = {s["name"]: frame_reading(s) for s in raw if s["group"] != "guests"}
    guests = {g: {} for g in GUESTS}
    for s in raw:
        if s["group"] == "guests":
            gid, key = s["name"].split(".", 1)
            guests[gid][key] = frame_reading(s)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": BASE_ID + "frame.schema.json",
        "title": "ArgOS simulator frame",
        "description": ("GENERATED by tools/gen_snapshot_schema.py from config/signals.yaml; do not edit. What "
                        "Simulator.step(tick, commands, inputs) returns for one tick: the readings that arrived this tick, "
                        "the events it applied. Every reading's t_s is this tick (arrival time). A 1 Hz signal is present "
                        "every tick; an event-rate signal only on the tick its report arrives; a dropped feed's signals are "
                        "left out, never null. $defs.command and $defs.input type the two argument lists. "
                        "Contract: docs/STATE_ESTIMATION.md."),
        "type": "object",
        "additionalProperties": False,
        "required": ["contract", "tick", "t_ship_s", "signals", "guests", "events"],
        "properties": {
            "contract": {"const": "argos-frame/1"},
            "tick": {"type": "integer", "minimum": 0},
            "t_ship_s": {"type": "integer", "minimum": 0},
            "signals": group(flat, "readings that arrived this tick (producer simulator or laptop)", required=False),
            "guests": {"type": "object", "additionalProperties": False,
                       "properties": {g: group(guests[g], g, required=False) for g in GUESTS}},
            "events": {"type": "array", "items": {"$ref": "#/$defs/event"}},
        },
        "$defs": {**shared_defs(S), "command": command_schema(S), "input": input_schema(S)},
    }


def render(schema: dict) -> str:
    return json.dumps(schema, indent=1, ensure_ascii=False) + "\n"


def outputs(root: Path = ROOT) -> dict:
    S = load_signals(root)
    return {SNAPSHOT_PATH: render(build_snapshot_schema(S)), FRAME_PATH: render(build_frame_schema(S))}


def main(argv: list) -> int:
    stale = []
    for path, text in outputs().items():
        if "--check" in argv:
            if not path.exists() or path.read_text() != text:
                stale.append(path.relative_to(ROOT))
        else:
            path.write_text(text)
    if stale:
        print("out of date:", ", ".join(map(str, stale)), "(run tools/gen_snapshot_schema.py)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
