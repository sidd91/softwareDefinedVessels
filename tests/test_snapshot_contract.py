"""The state-estimation contract (docs/STATE_ESTIMATION.md): config/signals.yaml, the two generated schemas, the
Scenario B snapshot and frame fixtures, the cards and the oracles agree. No engine needed: where a value is
derived, this file recomputes it from config and checks the fixture."""
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"tools/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _tool("gen_snapshot_schema")
BUILD = _tool("build_snapshot_fixtures")

SIGNALS_FILE = yaml.safe_load((ROOT / "config/signals.yaml").read_text())
SIGNALS = {s["name"]: s for s in SIGNALS_FILE["signals"]}
ACTIVITIES = SIGNALS_FILE["activities"]
FEEDS = SIGNALS_FILE["feeds"]
DERIV = SIGNALS_FILE["derivations"]
SCHEMA = json.loads((ROOT / "config/snapshot.schema.json").read_text())
FRAME_SCHEMA = json.loads((ROOT / "config/frame.schema.json").read_text())
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())
ORACLE = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
CARDS = {p.stem: yaml.safe_load(p.read_text()) for p in sorted((ROOT / "manifests").glob("G*.yaml"))}
FIXTURES = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "tests/fixtures/snapshots").glob("*.json"))}
FRAMES = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "tests/fixtures/frames").glob("*.json"))}

GROUPS = ["plant", "ship_state", "environment", "links", "crew", "capacity"]
KINDS = {"plant", "ship_state", "guest", "crew", "link", "environment", "derived"}
TYPES = {"enum", "number", "integer", "boolean", "ship_time", "capacity", "rates", "requests", "sweep"}
RATES = {"1 Hz", "event", "hourly", "per tick"}
RATE_KEYS = {"backbone_mbps", "satcom_mbps", "los_radio_mbps", "acoustic_kbps"}
CONFIDENCE = SIGNALS_FILE["field_metadata"]["confidence"]
EFFECT_IDLE = DERIV["effects"]["idle"]
GUEST_ID = re.compile(r"^G\d$")
# ARCHITECTURE data contract 6, the event types the timeline may carry.
CONTRACT_6_EVENTS = {"baseline", "card_presented", "card_edited", "priority_swap", "genset_trip", "genset_restart",
                     "cooling_degraded", "guest_report", "guest_state", "guest_overconsumption", "crew_change",
                     "deck_report", "emission_change", "feed_drop"}
# Scenario B placement (DEC-32): which mission line feeds each guest's draw.
PLACEMENT = {"G3": "bay1", "G4": "flight_deck", "G5": "bay2"}
# The sar reservation (DEC-40), as the decision log would hold it: the oracle's minute-8 reserved_kw.
BASE = SIGNALS_FILE["baselines"]["scenario_b"]
SAR_RESERVATIONS = {"G4": {"mode": "fast_charge", "kw": ORACLE["scenario_b"]["minute_8"]["by_file"]["sar"]["reserved_kw"], "since_t_s": 480}}

# ---------------------------------------------------------------------------------------------------------
# The cards are typed (F2): conditions, exclusions and limits use signal and activity names directly.
# WINDOW_KEYS maps the installation-window keys in config/assumptions.yaml, which are not card fields.
WINDOW_KEYS = {"sea_state_max": "sea_state", "wind_kn_max": "wind_kn", "speed_kn": "speed_kn", "course": "course",
               "deck": "deck_flight_deck", "survey_vehicle_listening": ("activity", "G3.surveying")}
# ---------------------------------------------------------------------------------------------------------


def fields(snap):
    """Yield (signal name, group, field) for every field in a snapshot."""
    for g in GROUPS:
        for key, f in snap[g].items():
            yield key, g, f
    for gid, block in snap["guests"].items():
        for key, f in block.items():
            yield f"{gid}.{key}", "guests", f


def field(snap, name):
    if name in SIGNALS and SIGNALS[name]["group"] == "guests":
        gid, key = name.split(".", 1)
        return snap["guests"][gid][key]
    return snap[SIGNALS[name]["group"]][name]


def value_ok(sig, v):
    t = sig["type"]
    if v is None:
        return sig.get("nullable", False)
    if t == "enum":
        return v in sig["values"]
    if t == "boolean":
        return isinstance(v, bool)
    if t == "integer":
        if not isinstance(v, int) or isinstance(v, bool):
            return False
        return v in sig["values"] if "values" in sig else sig["range"][0] <= v <= sig["range"][1]
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and sig["range"][0] <= v <= sig["range"][1]
    if t == "ship_time":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "capacity":
        return set(v) == {"capacity", "unit", "degraded_by", "zero_by_rule"} and v["unit"] == sig["unit"]
    if t == "rates":
        return isinstance(v, dict) and set(v) <= RATE_KEYS and all(isinstance(x, (int, float)) and x >= 0 for x in v.values())
    if t == "requests":
        return isinstance(v, list)
    if t == "sweep":
        return isinstance(v, dict) and v.get("result") in ("clear", "not_clear")
    return False


def sources(sig):
    return sig["source"] if isinstance(sig["source"], list) else [sig["source"]]


def mode_kw(gid, mode):
    return next(m["power_kw"] for m in CARDS[gid]["modes"] if m["name"] == mode)


def heat_capacity(seawater_c, factor=1.0):
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    t = min(max(seawater_c, t0), t1)
    return (c0 + (c1 - c0) * (t - t0) / (t1 - t0)) * factor


def guest_reserve_kw(speed_kn, gensets_online):
    """derivations.guest_reserve_kw: by band, a gap takes the lower of its neighbours, null takes the lowest."""
    if gensets_online == 1:
        return A["power"]["guest_reserve_kw"]["one_genset_down"]
    by_band = dict(A["power"]["guest_reserve_kw_by_speed"], stopped=DERIV["guest_reserve_kw"]["stopped_kw"])
    if speed_kn is None:
        return min(by_band.values())
    bands = list(DERIV["speed_band"]["bands_kn"].items())
    for name, (lo, hi) in bands:
        if lo <= speed_kn and (hi is None or speed_kn <= hi):
            return by_band[name]
    for (n0, (_, hi0)), (n1, (lo1, _)) in zip(bands, bands[1:]):
        if hi0 < speed_kn < lo1:
            return min(by_band[n0], by_band[n1])
    raise AssertionError(speed_kn)


def speed_band(speed_kn):
    bands = list(DERIV["speed_band"]["bands_kn"].items())
    for i, (name, (lo, hi)) in enumerate(bands):
        if lo <= speed_kn and (hi is None or speed_kn <= hi):
            return name
        if i + 1 < len(bands) and hi < speed_kn < bands[i + 1][1][0]:
            return bands[i + 1][0]
    raise AssertionError(speed_kn)


def ledger(snap, reservations=None):
    """ledger_rules: committed per class, with reservations from the decision log; buffered links."""
    reservations = reservations or {}
    per = {}
    for g, b in snap["guests"].items():
        kw = mode_kw(g, b["mode"]["value"])
        kw = max(kw, reservations.get(g, {}).get("kw", 0))
        if not b["kw_actual"]["stale"]:
            kw = max(kw, b["kw_actual"]["value"])
        per[g] = kw
    cap = {k: f["value"] for k, f in snap["capacity"].items()}
    out = {"power": sum(per.values()),
           "heat": sum(kw for g, kw in per.items() if CARDS[g]["cooling"] == "chilled_water")}
    for line in ["port", "stbd"]:
        out[f"{line}_line"] = sum(kw for g, kw in per.items() if A["positions"][PLACEMENT[g]]["power_line"] == line)
    links = {"satcom": "satcom_mbps", "los_radio": "los_radio_mbps", "acoustic": "acoustic_kbps"}
    lines = {k: {"capacity": cap[k]["capacity"], "committed": v, "free": cap[k]["capacity"] - v} for k, v in out.items()}
    for cls, key in links.items():
        demand = {g: b["data_demand"]["value"].get(key, 0) for g, b in snap["guests"].items()}
        if cap[cls]["zero_by_rule"]:
            lines[cls] = {"capacity": 0, "committed": 0, "free": 0, "buffered": {g: d for g, d in demand.items() if d}}
        else:
            c = sum(demand.values())
            lines[cls] = {"capacity": cap[cls]["capacity"], "committed": c, "free": cap[cls]["capacity"] - c}
    return lines


def floats(obj):
    if isinstance(obj, float):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from floats(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from floats(v)


def survey(minute):
    return FIXTURES[f"scenario_b_survey_m{minute:02d}"]


def running(snap):
    return {g: b["activity"]["value"] for g, b in snap["guests"].items() if b["activity"]["value"] != "none"}


# ------------------------------------------------------------------------------ the vocabulary itself

def test_fixtures_exist():
    want = {f"scenario_b_survey_m{m:02d}" for m in (0, 8, 12, 19)} | {"scenario_b_sar_m12", "scenario_b_sar_m19"}
    assert set(FIXTURES) >= want
    assert set(FIXTURES) == set(FRAMES), "every snapshot fixture has the frame that produces it"
    assert {"scenario_b_survey_m10_stale_genset_feed", "scenario_b_survey_m09_stale_g4_telemetry", "scenario_b_survey_m08_crew0"} <= set(FIXTURES)


@pytest.mark.parametrize("name", sorted(SIGNALS))
def test_every_signal_is_typed_with_a_feed_and_a_fallback(name):
    s = SIGNALS[name]
    assert s["kind"] in KINDS and s["type"] in TYPES and s["rate"] in RATES
    assert s["group"] in GROUPS + ["guests"]
    assert s["producer"] in {"simulator", "laptop", "estimator"}
    assert set(sources(s)) <= set(SIGNALS_FILE["field_metadata"]["source"])
    assert (s["kind"] == "derived") == (s["producer"] == "estimator") == (sources(s) == ["derived"]) == (s["rate"] == "per tick")
    if s["kind"] == "derived":
        assert "feed" not in s and isinstance(s["inputs"], list)
        for i in s["inputs"]:
            assert i in SIGNALS or i.startswith("*.") or i.split(".", 1)[1] in SIGNALS_FILE["run_constants"], f"{name} input {i}"
    else:
        assert s["feed"] in FEEDS and "inputs" not in s
    if s["type"] == "enum" or (s["type"] == "integer" and "range" not in s):
        assert s["values"]
    if s["type"] == "number" or (s["type"] == "integer" and "values" not in s):
        assert "unit" in s and len(s["range"]) == 2
    assert set(s["fallback"]) & {"value", "rule", "by_use"}
    if "value" in s["fallback"] and s["type"] in ("enum", "boolean", "integer", "number", "requests", "sweep"):
        assert value_ok(s, s["fallback"]["value"]), "fallback outside the signal's type (null needs nullable)"
    for use, v in s["fallback"].get("by_use", {}).items():
        assert value_ok(s, v), use
    assert s["read_by"] and s["provenance"]
    if s["group"] == "guests":
        assert GUEST_ID.match(name.split(".")[0])
    if "grace_s" in s:
        assert s["grace_s"] == SIGNALS_FILE["fallback_policy"]["grace_s"] and s["rate"] == "1 Hz"
    if "confirm" in s:
        assert s["confirm"] in SIGNALS_FILE["confirm_rules"]


def test_every_feed_has_a_stale_rule_and_members():
    for f, cfg in FEEDS.items():
        members = [n for n, s in SIGNALS.items() if s.get("feed") == f]
        assert members, f
        assert ("stale_after_s" in cfg) != ("stale_after_link_up_s" in cfg), f
        if any(SIGNALS[n]["rate"] == "event" for n in members) and f != "g3_acoustic":
            hb = cfg["heartbeat"]
            assert hb in members and SIGNALS[hb]["rate"] == "1 Hz", f"{f}: an event member needs a 1 Hz heartbeat"


def test_stale_limits_come_from_the_assumptions():
    assert SIGNALS_FILE["default_stale_after_s"] == A["stale_feed"]["after_s"]
    for f, cfg in FEEDS.items():
        if f not in ("public_data", "g4_telemetry", "g3_acoustic"):
            assert cfg["stale_after_s"] == A["stale_feed"]["after_s"], f
    assert FEEDS["g4_telemetry"]["stale_after_s"] == A["rules"]["r3"]["stale_s"]["g4_telemetry"]
    assert FEEDS["g3_acoustic"]["stale_after_link_up_s"] == 2 * A["data"]["acoustic_link"]["judged_latency_s"]
    # G4's battery is a report: it follows the telemetry heartbeat, not its own age.
    assert SIGNALS["G4.battery_pct"]["rate"] == "event" and SIGNALS["G4.battery_pct"]["feed"] == "g4_telemetry"
    assert SIGNALS["G4.battery_pct"]["nullable"]
    cr = SIGNALS_FILE["confirm_rules"]
    assert cr["genset_trip"]["needed"] == A["power"]["trip_confirm"]["needed"]
    assert len(cr["genset_trip"]["votes"]) == len(A["power"]["trip_confirm"]["signals"])
    assert cr["genset_trip"]["hold_s"] == cr["cooling_degraded"]["hold_s"] == A["fault_entry"]["debounce_s"]
    assert cr["restore"]["healthy_hold_s"] == A["fault_entry"]["restore_hold_s"]


def test_speed_is_numeric_nullable_and_the_reserve_never_loosens_in_a_gap():
    s = SIGNALS["speed_kn"]
    assert s["type"] == "number" and s["unit"] == "kn" and s["nullable"] and s["fallback"]["value"] is None
    assert SIGNALS["wind_from_deg"]["nullable"] and SIGNALS["wind_from_deg"]["fallback"]["value"] is None
    assert SIGNALS["speed_band"]["kind"] == "derived"
    assert SIGNALS["speed_band"]["values"] == A["ship_state"]["speed_band"]["values"]
    kn = A["ship_state"]["speed_band"]["kn"]
    bands = DERIV["speed_band"]["bands_kn"]
    assert bands["slow"] == kn["slow"] and bands["cruise"] == kn["cruise"] and bands["fast"][0] == kn["fast"]
    by = A["power"]["guest_reserve_kw_by_speed"]
    assert guest_reserve_kw(2.0, 2) == 200          # 0.5-3 kn: min(stopped 200, slow 250)
    assert guest_reserve_kw(4.0, 2) == by["slow"] == 250
    assert guest_reserve_kw(5.0, 2) == 250          # the slow band's own top
    assert guest_reserve_kw(7.0, 2) == 200          # 5-10 kn: min(slow, cruise)
    assert guest_reserve_kw(16.0, 2) == 150         # 14-18 kn: min(cruise, fast)
    assert guest_reserve_kw(0.0, 2) == DERIV["guest_reserve_kw"]["stopped_kw"]
    assert guest_reserve_kw(None, 2) == min(by.values())
    assert guest_reserve_kw(4.0, 1) == A["power"]["guest_reserve_kw"]["one_genset_down"]


def test_ship_state_values_match_the_assumptions():
    for var in ["course", "noise", "emission"]:
        assert SIGNALS[var]["values"] == A["ship_state"][var]["values"]
    for zone in ["deck_flight_deck", "deck_bays"]:
        assert SIGNALS[zone]["values"] == A["ship_state"]["deck"]["values"]
    assert SIGNALS["crew_aboard"]["values"] == A["crew"]["levels"]
    assert SIGNALS["cooling_state"]["values"] == A["ship_state"]["cooling"]["values"]
    assert sorted(SIGNALS["gensets_online"]["values"]) == sorted(A["ship_state"]["genset"]["values"])
    assert set(SIGNALS["bridge_requests"]["wait_s"]["by_crew"]) == set(A["crew"]["levels"])
    for level, (lo, hi) in ((k, v) for k, v in A["crew"]["confirm_s"].items() if v):
        assert SIGNALS["bridge_requests"]["wait_s"]["by_crew"][level] == hi
    assert SIGNALS["bridge_requests"]["wait_s"]["by_crew"][0] == 0


def test_the_acoustic_rule_reads_signals_and_the_scenario_water_column():
    for key, value in A["data"]["acoustic_link"]["up_when"].items():
        assert value_ok(SIGNALS[key], value), key
    assert "layered_water" not in SIGNALS, "not a live field (assumptions data.acoustic_link.layered_water)"
    assert "layered_water" in SIGNALS_FILE["run_constants"]
    assert "run.layered_water" in SIGNALS["acoustic_link_up"]["inputs"]


def test_kw_actual_ranges_leave_room_for_an_overdraw():
    for gid, card in CARDS.items():
        top = max(m["power_kw"] for m in card["modes"])
        assert SIGNALS[f"{gid}.kw_actual"]["range"] == [0, 2 * top], gid
        assert f"{gid}.overdraw_pct" in SIGNALS
    assert DERIV["overdraw"]["threshold_pct"] < 10, "the brief's 10-20 % over-draw must be caught"


# ------------------------------------------------------------------------------ generated files

def test_schemas_are_the_generators_output():
    for path, text in GEN.outputs(ROOT).items():
        assert path.read_text() == text, f"{path.name} is out of date: run tools/gen_snapshot_schema.py"


def test_fixtures_are_the_builders_output():
    built = BUILD.build(ROOT)
    on_disk = {f"tests/fixtures/snapshots/{n}.json" for n in FIXTURES} | {f"tests/fixtures/frames/{n}.json" for n in FRAMES}
    assert set(built) == on_disk
    for rel, obj in built.items():
        assert (ROOT / rel).read_text() == BUILD.render(obj), f"{rel} is out of date: run tools/build_snapshot_fixtures.py"


def test_schema_lists_exactly_the_signals():
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator.check_schema(FRAME_SCHEMA)
    props = SCHEMA["properties"]
    for g in GROUPS:
        want = {s["name"] for s in SIGNALS.values() if s["group"] == g}
        assert set(props[g]["properties"]) == want == set(props[g]["required"]), g
    raw = {n for n, s in SIGNALS.items() if s["producer"] != "estimator"}
    assert set(FRAME_SCHEMA["properties"]["signals"]["properties"]) == {n for n in raw if SIGNALS[n]["group"] != "guests"}
    for gid in CARDS:
        want = {n.split(".", 1)[1] for n, s in SIGNALS.items() if s["group"] == "guests" and n.startswith(gid + ".")}
        assert set(props["guests"]["properties"][gid]["properties"]) == want, gid
        frame_want = {n.split(".", 1)[1] for n in raw if n.startswith(gid + ".")}
        assert set(FRAME_SCHEMA["properties"]["guests"]["properties"][gid]["properties"]) == frame_want, gid
    assert set(props["feeds"]["properties"]) == set(FEEDS)
    assert "held_by_core" not in props, "reservations are the ledger's, from the decision log"


def test_event_types_cover_contract_6_and_scenario_b():
    enum = set(SCHEMA["$defs"]["event"]["properties"]["type"]["enum"])
    assert enum == set(SIGNALS_FILE["events"])
    assert CONTRACT_6_EVENTS <= enum
    assert {"guest_request", "deck_sweep", "bridge_answer", "safety_request"} <= enum
    assert {e["type"] for e in TL["events"]} <= enum
    assert TL["g3_charge_requests"] and "guest_request" in enum
    v = Draft202012Validator(SCHEMA["$defs"]["event"])
    good = {"t_s": 600, "type": "guest_request", "origin": "timeline", "injected": False,
            "payload": {"guest": "G3", "mode": "charging", "kw": 25, "interruptible": False}}
    assert v.is_valid(good)
    assert not v.is_valid(dict(good, payload={"guest": "G3"})), "a guest_request payload is typed"
    assert not v.is_valid(dict(good, type="feed_drop", payload={"feed": "nonsense", "until_t_s": None}))
    assert v.is_valid(dict(good, type="feed_drop", payload={"feed": "pms", "until_t_s": None}))


# ------------------------------------------------------------------------------ activities and card names

def test_registry_covers_every_card_activity_and_mode():
    assert set(ACTIVITIES) == set(CARDS)
    for gid, card in CARDS.items():
        card_acts = {c["activity"] for c in card.get("conditions", [])}
        reg = ACTIVITIES[gid]
        assert card_acts == {a for a, v in reg.items() if v["card"]}, gid
        modes = {m["name"] for m in card["modes"]}
        assert set(SIGNALS[f"{gid}.mode"]["values"]) == modes, gid
        assert set(SIGNALS[f"{gid}.activity"]["values"]) == set(reg) | {"none"}, gid
        for act, v in reg.items():
            assert set(v["modes"]) <= modes, f"{gid}.{act}"
            assert set(v["effects"]) <= set(EFFECT_IDLE), f"{gid}.{act}: effects only on the four effect fields"
            for sig, val in v["effects"].items():
                assert value_ok(SIGNALS[sig], val) and val != EFFECT_IDLE[sig], f"{gid}.{act} effect {sig}"
            assert set(v["excludes"]) <= set(EFFECT_IDLE), f"{gid}.{act} excludes"


def resolve_condition_key(gid, act, key):
    return key if key in SIGNALS else None


def condition_value_ok(sig_name, key, v):
    sig = SIGNALS[sig_name]
    if isinstance(v, dict):
        return sig["type"] in ("number", "integer") and all(value_ok(sig, x) for x in v.values())
    vals = v if isinstance(v, list) else [v]
    return all(value_ok(sig, x) for x in vals)


def condition_holds(sig_name, key, want, value):
    if value is None:
        return False
    if isinstance(want, dict):
        return want.get("min", float("-inf")) <= value <= want.get("max", float("inf"))
    if SIGNALS[sig_name]["type"] == "number":
        return abs(value - want) <= DERIV["speed_tolerance_kn"]["value"]
    if isinstance(want, list):
        return value in want
    return value == want


def sample_value(want):
    """One value that satisfies a condition's predicate."""
    if isinstance(want, dict):
        return want.get("min", want.get("max"))
    return want[0] if isinstance(want, list) else want


CARD_CONDITIONS = [(gid, c["activity"], k, v) for gid, card in CARDS.items()
                   for c in card.get("conditions", []) for k, v in c["requires"].items()]


@pytest.mark.parametrize("gid,act,key,value", CARD_CONDITIONS, ids=[f"{g}.{a}.{k}" for g, a, k, _ in CARD_CONDITIONS])
def test_every_condition_key_maps_to_a_signal(gid, act, key, value):
    sig = resolve_condition_key(gid, act, key)
    assert sig in SIGNALS, f"{gid}.{act} requires {key}: no signal"
    assert condition_value_ok(sig, key, value), f"{gid}.{act} {key}: {value!r} is not a value of {sig}"


SELF_EFFECTS = [(g, a) for g, reg in ACTIVITIES.items() for a, v in reg.items() if v["effects"] and v["card"]]


@pytest.mark.parametrize("gid,act", SELF_EFFECTS, ids=[f"{g}.{a}" for g, a in SELF_EFFECTS])
def test_an_activity_never_fails_its_own_conditions(gid, act):
    """derivations.effects.self_exclusion: a guest's conditions see the state less its own effects."""
    conds = next(c["requires"] for c in CARDS[gid]["conditions"] if c["activity"] == act)
    state = {}
    for key, want in conds.items():
        sig = resolve_condition_key(gid, act, key)
        state[sig] = {"value": sample_value(want), "by": []}
    for sig, val in ACTIVITIES[gid][act]["effects"].items():
        state[sig] = {"value": val, "by": [gid]}

    def seen_by(g, sig):
        f = state[sig]
        return EFFECT_IDLE[sig] if f["by"] == [g] else f["value"]

    for key, want in conds.items():
        sig = resolve_condition_key(gid, act, key)
        assert condition_holds(sig, key, want, seen_by(gid, sig)), f"{gid}.{act} {key} fails against its own effect"


def resolve_reference(ref, gid):
    m = re.fullmatch(r"(G\d)\.(\w+)", ref)
    if m:
        g, name = m.groups()
        return g in ACTIVITIES and name in ACTIVITIES[g]
    return ref in A["positions"]


REFERENCES = [(gid, ref) for gid, card in CARDS.items() for ex in card.get("relations", {}).get("excludes", [])
              for ref in (f"{gid}.{ex['activity']}", ex["excludes"])]
REFERENCES += [(gid, r) for gid, card in CARDS.items() for r in card.get("relations", {}).get("requires", [])]


@pytest.mark.parametrize("gid,ref", REFERENCES, ids=[f"{g}:{r}" for g, r in REFERENCES])
def test_every_relation_reference_resolves(gid, ref):
    assert resolve_reference(ref, gid), f"{gid} refers to {ref!r}, which is no activity, part, position or alias"


LIMITS = [(gid, lim["when"]) for gid, card in CARDS.items() for lim in card.get("hard_limits", [])]


@pytest.mark.parametrize("gid,when", LIMITS, ids=[f"{g}:{w['signal']}" for g, w in LIMITS])
def test_every_hard_limit_names_a_signal(gid, when):
    assert when["signal"] in SIGNALS, f"{gid}: {when['signal']!r} is no signal"
    assert value_ok(SIGNALS[when["signal"]], when["value"]), f"{gid}: {when['value']!r} for {when['signal']}"


def test_installation_window_and_ramp_names_resolve():
    for key, value in A["installation"]["at_sea_crewed"]["window"].items():
        target = WINDOW_KEYS[key]
        if isinstance(target, tuple):
            g, a = target[1].split(".")
            assert a in ACTIVITIES[g]
        else:
            assert condition_value_ok(target, key, value), key


# ------------------------------------------------------------------------------ fixtures: shape and clock

SNAP_V = Draft202012Validator(SCHEMA)
FRAME_V = Draft202012Validator(FRAME_SCHEMA)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_validates_against_the_schemas(name):
    for v, obj in ((SNAP_V, FIXTURES[name]), (FRAME_V, FRAMES[name])):
        errors = sorted(v.iter_errors(obj), key=lambda e: list(e.path))
        assert not errors, "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_field_is_typed_aged_and_stale_by_its_feed(name):
    snap = FIXTURES[name]
    tick = snap["run"]["tick"]
    for sig_name, group, f in fields(snap):
        assert sig_name in SIGNALS, f"{sig_name} is not in config/signals.yaml"
        sig = SIGNALS[sig_name]
        assert sig["group"] == group, sig_name
        assert value_ok(sig, f["value"]), f"{sig_name}: {f['value']!r}"
        assert f["source"] in sources(sig), sig_name
        assert ("substituted" in f) == (f["confidence"] == "substituted") == f["stale"], sig_name
        assert ("by" in f) == (sig_name in EFFECT_IDLE), sig_name
        if sig["kind"] == "derived":
            assert f["age_s"] == 0, sig_name
            continue
        feed = snap["feeds"][sig["feed"]]
        if f["age_s"] is None:
            assert f["value"] is None and f["confidence"] == "assumed", f"{sig_name}: no reading yet"
        if sig["rate"] in ("1 Hz", "hourly"):
            limit = FEEDS[sig["feed"]]["stale_after_s"]
            assert f["stale"] == (f["age_s"] is not None and f["age_s"] > limit), sig_name
        else:
            assert f["stale"] == feed["stale"], f"{sig_name}: an event-rate report is stale with its feed"
        if f["stale"]:
            assert feed["stale"], sig_name
            assert f["substituted"]["last_good_t_s"] is not None
        if "reported_t_s" in f:
            assert f["reported_t_s"] <= tick


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_confidence_follows_the_rule(name):
    """field_metadata.confidence_rule, recomputed from the sources and each derived signal's inputs."""
    snap = FIXTURES[name]
    by_source = {"plant": "measured", "guest_report": "reported", "crew_report": "reported", "laptop": "reported",
                 "public_data": "reported", "scenario": "assumed"}
    active = {f["fault"] for f in snap["faults"] if f["state"] in ("confirmed", "restoring")}

    def conf(ref):
        if ref.startswith("run."):
            return snap["run"]["constants"][ref[4:]]["confidence"]
        return field(snap, ref)["confidence"]

    for sig_name, _, f in fields(snap):
        sig = SIGNALS[sig_name]
        if sig["kind"] != "derived":
            want = "substituted" if f["stale"] else ("assumed" if f["age_s"] is None else by_source[f["source"]])
        else:
            ins = []
            for i in sig["inputs"]:
                ins += [f"{g}.{i[2:]}" for g in snap["guests"]] if i.startswith("*.") else [i]
            cs = [conf(i) for i in ins]
            if "substituted" in cs:
                want = "substituted"
            elif sig.get("confirm") in active:
                want = "confirmed"
            else:
                want = min(cs, key=CONFIDENCE.index) if cs else "assumed"
        assert f["confidence"] == want, f"{sig_name}: {f['confidence']} where the rule gives {want}"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_the_frame_produces_the_snapshot(name):
    """Every reading in the frame is the snapshot's field at age 0; a field not in the frame is older, or dropped."""
    snap, frame = FIXTURES[name], FRAMES[name]
    tick = snap["run"]["tick"]
    assert frame["tick"] == frame["t_ship_s"] == tick and frame["events"] == snap["events"]
    readings = dict(frame["signals"])
    for gid, block in frame["guests"].items():
        readings.update({f"{gid}.{k}": r for k, r in block.items()})
    for n, r in readings.items():
        assert SIGNALS[n]["producer"] in ("simulator", "laptop")
        f = field(snap, n)
        assert r["t_s"] == tick and f["age_s"] == 0 and not f["stale"], n
        assert r["value"] == f["value"] and r["source"] == f["source"], n
        assert r.get("transition") == f.get("transition") and r.get("reported_t_s") == f.get("reported_t_s"), n
    for sig_name, _, f in fields(snap):
        sig = SIGNALS[sig_name]
        if sig["kind"] == "derived":
            continue
        if sig_name not in readings:
            assert f["age_s"] is None or f["age_s"] > 0, f"{sig_name}: fresh in the snapshot but not in the frame"
            if sig["rate"] == "1 Hz":
                assert f["stale"] or f["age_s"] is None, f"{sig_name}: a 1 Hz signal is in every frame unless its feed dropped"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_run_clock_and_rounding(name):
    snap = FIXTURES[name]
    run = snap["run"]
    tick = run["tick"]
    assert run["tick"] == run["t_ship_s"], "1 Hz in ship time: tick n is at n s"
    assert set(run["installed"]) == set(snap["guests"]) == set(TL["guests"])
    assert run["variant"] == "default" or run["variant"] in BASE["variants"]
    assert (ROOT / f"config/missions/{run['mission']}.yaml").exists()
    assert run["constants"]["layered_water"]["value"] == TL["location"]["layered"]
    assert "wall" not in json.dumps(snap), "wall-clock time belongs in the timing log, not the snapshot"
    for x in floats(snap):
        assert round(x, 1) == x, f"{x} is not rounded to 0.1"
    for _, _, f in fields(snap):
        if "transition" in f:
            tr = f["transition"]
            assert tr["started_t_s"] <= tick < tr["expected_end_t_s"] <= tr.get("latest_end_t_s", tr["expected_end_t_s"])
            if isinstance(tr["to"], (int, float)) and not isinstance(tr["to"], bool):
                # A number moves on the line from where it started to `to`; the start value is the value at started_t_s.
                assert f["since_t_s"] == tick, "a ramping value changes every tick"
    for gid, act in running(snap).items():
        mode = snap["guests"][gid]["mode"]["value"]
        assert mode in ACTIVITIES[gid][act]["modes"], f"{gid} {act} runs in {ACTIVITIES[gid][act]['modes']}, not {mode}"


SPEED_PATH = [FIXTURES[n] for n in sorted(FIXTURES) if n.startswith("scenario_b_survey") or n.startswith("scenario_b_sar")]


def test_speed_lies_on_its_transition_line_and_stays_in_the_slow_band():
    """Each speed change is linear from its start to `to`; minute 8's 3 to 5 kn stays inside the slow band."""
    starts = {}
    for snap in sorted(SPEED_PATH, key=lambda s: s["run"]["tick"]):
        f = snap["ship_state"]["speed_kn"]
        if "transition" in f:
            tr = f["transition"]
            starts.setdefault(tr["started_t_s"], (tr, []))[1].append((snap["run"]["tick"], f["value"]))
        assert snap["ship_state"]["speed_band"]["value"] == speed_band(f["value"])
        assert snap["ship_state"]["speed_band"]["value"] == "slow", "no A.6 band change in Scenario B (EXPECTED_OUTCOMES minute 8)"
    v_from = {541: 3.0, 1081: 5.0}
    assert set(starts) == set(v_from)
    for t0, (tr, points) in starts.items():
        for t, v in points:
            line = v_from[t0] + (tr["to"] - v_from[t0]) * (t - t0) / (tr["expected_end_t_s"] - t0)
            assert abs(v - line) <= 0.05, (t0, t, v, line)


# ------------------------------------------------------------------------------ fixtures: derived values

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_effect_fields_and_permissions_follow_the_running_activities(name):
    snap = FIXTURES[name]
    acts = running(snap)
    ss = snap["ship_state"]
    for k in EFFECT_IDLE:
        want = sorted(g for g, a in acts.items() if k in ACTIVITIES[g][a]["effects"])
        assert ss[k]["by"] == want, k
    if ss["deck_machinery"]["by"]:
        assert ss["deck_machinery"]["value"] is True, "the worse of the simulator and the activities"
    if ss["ramp"]["by"]:
        assert ss["ramp"]["value"] == "in_use"
    assert ss["heading_free"]["value"] == (not ss["heading_free"]["by"])
    assert ss["flight_deck_ops"]["value"] == ("in_use" if ss["flight_deck_ops"]["by"] else "free")
    excluded = any("deck_machinery" in ACTIVITIES[g][a]["excludes"] for g, a in acts.items())
    assert ss["deck_machinery_permitted"]["value"] == (ss["emission"]["value"] == "normal" and not excluded)
    crew = snap["crew"]
    sweep = crew["last_sweep"]["value"]
    latched = bool(sweep and sweep["result"] == "clear" and not ss["deck_activity_since_sweep"]["value"])
    assert crew["deck_latched_clear"]["value"] == latched


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_capacity_follows_the_derivations(name):
    snap = FIXTURES[name]
    cap = {k: f["value"] for k, f in snap["capacity"].items()}
    ss = {k: f["value"] for k, f in snap["ship_state"].items()}
    online = snap["plant"]["gensets_online"]["value"]
    reserve = guest_reserve_kw(ss["speed_kn"], online)
    assert cap["power"]["capacity"] == reserve
    for line in ["port", "stbd"]:
        assert cap[f"{line}_line"]["capacity"] == A["power"]["mission_line_kw"][line]
    degraded = snap["plant"]["cooling_state"]["value"] == "degraded"
    heat = heat_capacity(snap["environment"]["seawater_c"]["value"], A["heat"]["degraded_factor"] if degraded else 1.0)
    assert cap["heat"]["capacity"] == pytest.approx(heat, abs=0.05)
    assert cap["shed_ceiling_kw"] == pytest.approx(min(reserve, heat) - A["power"]["shed_headroom_kw"], abs=0.05)
    rule = A["data"]["acoustic_link"]["up_when"]
    up = all(ss[k] == v for k, v in rule.items()) and not snap["run"]["constants"]["layered_water"]["value"]
    assert snap["links"]["acoustic_link_up"]["value"] == up
    assert snap["links"]["acoustic_kbps"]["value"] == (DERIV["acoustic_kbps"]["value_up"] if up else 0)
    assert cap["acoustic"]["capacity"] == snap["links"]["acoustic_kbps"]["value"]
    assert cap["acoustic"]["zero_by_rule"] == (not up)
    silent = ss["emission"] == "silent"
    assert cap["satcom"]["capacity"] == (0 if silent else snap["links"]["satcom_mbps"]["value"])
    assert cap["satcom"]["zero_by_rule"] == cap["los_radio"]["zero_by_rule"] == silent
    g4 = snap["guests"].get("G4")
    floor = A["data"]["los_radio_mbps"]["min"]
    far = g4 is not None and (g4["range_km"]["value"] is None or g4["range_km"]["value"] > A["data"]["los_radio_drone_range_km_max"])
    assert cap["los_radio"]["capacity"] == (0 if silent else floor if far else snap["links"]["los_radio_mbps"]["value"])
    for k, f in snap["capacity"].items():
        if isinstance(f["value"], dict) and f["value"]["capacity"] == 0 and k in ("satcom", "los_radio", "acoustic"):
            assert f["value"]["zero_by_rule"] and f["value"]["degraded_by"], f"{k}: a zero capacity says why"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_guest_derivations(name):
    snap = FIXTURES[name]
    tick = snap["run"]["tick"]
    for gid, b in snap["guests"].items():
        mode = b["mode"]["value"]
        declared = mode_kw(gid, mode)
        od = b["overdraw_pct"]["value"]
        if declared and not b["kw_actual"]["stale"]:
            assert od == pytest.approx(round((b["kw_actual"]["value"] / declared - 1) * 100, 1))
        else:
            assert od is None
        if "mode_ends_t_s" in b:
            dur = next(m.get("duration_s") for m in CARDS[gid]["modes"] if m["name"] == mode)
            ends = b["mode_ends_t_s"]["value"]
            assert (ends is None) == (dur is None), gid
            if dur:
                assert ends == b["mode"]["since_t_s"] + dur
    g4 = snap["guests"]["G4"]
    flying = g4["activity"]["value"] in ("airborne", "launch_recovery")
    assert (g4["airborne_since_t_s"]["value"] is not None) == flying
    if not flying:
        assert g4["land_by_t_s"]["value"] is None and g4["battery_crossing_t_s"]["value"] is None
        return
    assert g4["airborne_since_t_s"]["value"] == g4["launched_t_s"]["value"]
    endurance = g4["launched_t_s"]["value"] + 90 * 60
    pct, rep = g4["battery_pct"]["value"], g4["battery_pct"]
    if pct is None or (pct >= 20 and not rep["stale"]):
        assert g4["battery_crossing_t_s"]["value"] is None
        assert g4["land_by_t_s"]["value"] == endurance
    else:
        t_report = tick - rep["age_s"]
        if pct < 20:
            crossing = t_report - (20 - pct) / A["rules"]["r3"]["drain_pct_min"] * 60
        else:
            crossing = t_report + (pct - 20) / DERIV["g4_land_by"]["drain_pct_max"] * 60
        assert g4["battery_crossing_t_s"]["value"] == round(crossing, 1)
        assert g4["land_by_t_s"]["value"] == round(min(endurance, crossing + 12 * 60), 1)


def test_the_stale_battery_rule_projects_forward_at_the_fastest_drain():
    """A report of 25 % at 480 s on a feed that then drops: the earliest crossing it allows is 680 s."""
    crossing = 480 + (25 - 20) / DERIV["g4_land_by"]["drain_pct_max"] * 60
    assert crossing == 680
    assert crossing + 12 * 60 < 480 + (25 - 20) / A["rules"]["r3"]["drain_pct_min"] * 60 + 12 * 60


def test_the_land_by_deadline_never_moves_later():
    for mission in ("survey", "sar"):
        runs = sorted((s for s in FIXTURES.values() if s["run"]["mission"] == mission and s["crew"]["crew_aboard"]["value"] == 14),
                      key=lambda s: s["run"]["tick"])
        last = math.inf
        for s in runs:
            lb = s["guests"]["G4"]["land_by_t_s"]["value"]
            if lb is not None:
                assert lb <= last, (mission, s["run"]["tick"])
                last = lb


# ------------------------------------------------------------------------------ the ledger on top of the snapshot

def test_ledger_survey_minute_12_holds_with_g4_airborne_at_2_kw():
    s = survey(12)
    o = ORACLE["scenario_b"]["minute_12_as_decided"]["by_file"]["survey"]
    assert {g: b["mode"]["value"] for g, b in s["guests"].items()} == o["modes"] and o["reserved"] == []
    L = ledger(s)
    assert L["power"]["committed"] == o["load_kw"] == 48
    assert s["capacity"]["shed_ceiling_kw"]["value"] - L["power"]["committed"] == o["spare_kw"] == 47


def test_ledger_sar_minute_12_counts_the_reservation():
    s = FIXTURES["scenario_b_sar_m12"]
    o = ORACLE["scenario_b"]["minute_12_as_decided"]["by_file"]["sar"]
    assert s["run"]["mission"] == "sar" and o["reserved"] == list(SAR_RESERVATIONS)
    assert s["guests"]["G4"]["mode"]["value"] == "standby" and s["guests"]["G4"]["activity"]["value"] == "airborne"
    assert s["guests"]["G3"]["activity"]["value"] == "holding_at_sea" and s["guests"]["G3"]["leg_state"]["value"] == "aborted"
    assert SAR_RESERVATIONS["G4"]["kw"] == mode_kw("G4", o["modes"]["G4"]) == 35
    L = ledger(s, SAR_RESERVATIONS)
    assert L["power"]["committed"] == o["load_kw"] == 81, "max(declared 2, reserved 35) per guest, not 2 + 35"
    assert s["capacity"]["shed_ceiling_kw"]["value"] == ORACLE["scenario_b"]["ceiling"]["kw"] == 95
    assert s["capacity"]["shed_ceiling_kw"]["value"] - L["power"]["committed"] == o["spare_kw"] == 14
    assert ledger(s)["power"]["committed"] == 48, "without the decision log the snapshot alone gives the survey load"


@pytest.mark.parametrize("name", ["scenario_b_survey_m19", "scenario_b_sar_m19"])
def test_ledger_minute_19_cooling_binds(name):
    s = FIXTURES[name]
    ev = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    res = SAR_RESERVATIONS if s["run"]["mission"] == "sar" else None
    L = ledger(s, res)
    assert {g: b["mode"]["value"] for g, b in s["guests"].items()} == ev["load_modes"]
    assert L["power"]["committed"] == L["heat"]["committed"] == 81
    assert s["capacity"]["heat"]["value"]["capacity"] == pytest.approx(heat_capacity(24, ev["factor"]), abs=0.05) == 80.0
    assert s["capacity"]["shed_ceiling_kw"]["value"] == 75.0
    if s["run"]["mission"] == "sar":
        m = re.search(r"sar takes G5 to (\d+) kW \((\d+) kW\)", TL["provenance"]["events.cooling_degraded"]["why"])
        assert mode_kw("G5", "low_power") == int(m.group(1))
        assert L["power"]["committed"] - mode_kw("G5", "full") + mode_kw("G5", "low_power") == int(m.group(2)) == 44


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_ledger_buffers_demand_on_a_link_that_is_zero_by_rule(name):
    s = FIXTURES[name]
    L = ledger(s)
    for cls in ("satcom", "los_radio", "acoustic"):
        if s["capacity"][cls]["value"]["zero_by_rule"]:
            assert L[cls]["committed"] == 0 and L[cls]["free"] == 0, cls
            demand = {g: b["data_demand"]["value"] for g, b in s["guests"].items()}
            assert sum(L[cls]["buffered"].values()) == sum(d.get({"satcom": "satcom_mbps", "los_radio": "los_radio_mbps", "acoustic": "acoustic_kbps"}[cls], 0) for d in demand.values())
        if L[cls]["capacity"] == 0:
            assert L[cls]["free"] >= 0


def test_the_ledger_counts_a_fresh_overdraw():
    s = json.loads(json.dumps(survey(12)))
    s["guests"]["G5"]["kw_actual"]["value"] = 51.8          # 15 % over its 45 kW (DEMO_SCRIPT)
    assert ledger(s)["power"]["committed"] == pytest.approx(48 - 45 + 51.8)
    s["guests"]["G5"]["kw_actual"]["stale"] = True
    assert ledger(s)["power"]["committed"] == 48, "a stale meter never raises committed: D4 does not act on it"


# ------------------------------------------------------------------------------ Scenario B, minute by minute

def test_minute_0_matches_the_timeline():
    s = survey(0)
    assert s["environment"]["seawater_c"]["value"] == TL["location"]["seawater_c"]
    assert s["ship_state"]["speed_kn"]["value"] == 3.0
    assert s["guests"]["G3"]["activity"]["value"] == "surveying" and s["links"]["acoustic_link_up"]["value"]
    assert s["guests"]["G4"]["activity"]["value"] == "airborne" and s["guests"]["G5"]["mode"]["value"] == "full"
    b = s["guests"]["G4"]["battery_pct"]
    assert b["value"] is None and b["age_s"] is None and not b["stale"], "no battery report before minute 8"
    lb = s["guests"]["G4"]["land_by_t_s"]
    assert lb["value"] == s["guests"]["G4"]["launched_t_s"]["value"] + 90 * 60 == 1448 and lb["confidence"] == "assumed"
    base = next(e for e in s["events"] if e["type"] == "baseline")
    assert base["payload"]["variant"] == s["run"]["variant"] == "default"
    assert base["payload"]["start"]["G4.launched_t_s"] == s["guests"]["G4"]["launched_t_s"]["value"]
    assert s["ship_state"]["heading_free"]["by"] == ["G3"] and not s["ship_state"]["deck_machinery_permitted"]["value"]


def test_minute_8_land_by_is_18_2():
    s = survey(8)
    report = next(e for e in TL["events"] if e["type"] == "guest_report" and e["guest"] == "G4")
    g4 = s["guests"]["G4"]
    assert s["run"]["t_ship_s"] == report["t_min"] * 60
    assert g4["battery_pct"]["value"] == report["battery_pct"] and g4["battery_pct"]["age_s"] == 0
    limit = next(l for l in CARDS["G4"]["hard_limits"] if l["when"]["signal"] == "G4.battery_pct")
    threshold = float(limit["when"]["value"])
    within_min = float(limit["then"]["within_min"])
    drain = A["rules"]["r3"]["drain_pct_min"]
    crossing_min = report["t_min"] - (threshold - report["battery_pct"]) / drain
    timing = ORACLE["scenario_b"]["minute_8"]["timing"]
    assert g4["battery_crossing_t_s"]["value"] == round(crossing_min * 60, 1) == 371.9
    assert g4["land_by_t_s"]["value"] == round((crossing_min + within_min) * 60, 1) == 1091.9
    assert round(g4["land_by_t_s"]["value"] / 60, 1) == timing["deadline_min"] == 18.2
    assert round(g4["battery_crossing_t_s"]["value"] / 60, 1) == timing["crossed_threshold_at_min"]
    assert g4["land_by_t_s"]["value"] < g4["launched_t_s"]["value"] + 90 * 60


def test_minute_8_with_nobody_aboard_reads_the_latched_deck():
    s = FIXTURES["scenario_b_survey_m08_crew0"]
    assert s["crew"]["crew_aboard"]["value"] == 0 and A["rules"]["r3"]["confirm"][0] == "automatic"
    assert s["crew"]["last_sweep"]["value"]["result"] == "clear"
    assert s["crew"]["last_sweep"]["value"]["t_s"] < s["guests"]["G4"]["launched_t_s"]["value"], "G4's own launch is excepted"
    assert not s["ship_state"]["deck_activity_since_sweep"]["value"]
    assert s["crew"]["deck_latched_clear"]["value"] is True
    assert s["crew"]["bridge_requests"]["value"] == [] and SIGNALS["bridge_requests"]["wait_s"]["by_crew"][0] == 0


def test_bridge_answers_hold_for_their_request():
    for name in ("scenario_b_survey_m10_stale_genset_feed", "scenario_b_survey_m12", "scenario_b_sar_m12"):
        reqs = FIXTURES[name]["crew"]["bridge_requests"]["value"]
        assert reqs == [{"request_seq": 1, "rule": "R3", "state": "confirmed", "asked_t_s": 480, "answered_t_s": 540}], name
        wait = SIGNALS["bridge_requests"]["wait_s"]["by_crew"][14]
        assert reqs[0]["answered_t_s"] - reqs[0]["asked_t_s"] <= wait, "answered inside the wait"
    closed = survey(19)["crew"]["bridge_requests"]
    assert closed["value"] == [] and closed["since_t_s"] == 1021, "the core's bridge_close from snapshot 1020 (G4 landed) is applied at 1021"


def test_minute_12_trip_timing():
    s = survey(12)
    trip = next(e for e in TL["events"] if e["type"] == "genset_trip")
    assert s["plant"]["gensets_online"]["value"] == trip["gensets_online"]
    assert s["plant"]["gensets_online"]["confidence"] == "confirmed"
    assert s["plant"]["cooling_state"]["value"] == trip["cooling"]
    assert s["guests"]["G4"]["activity"]["value"] == "airborne" and s["guests"]["G4"]["kw_actual"]["value"] == 2.0
    fault = next(f for f in s["faults"] if f["fault"] == "genset_trip")
    raw = math.ceil(60 * trip["t_min"])
    assert fault["raw_event_t_s"] == raw
    assert fault["confirmed_t_s"] - fault["raw_event_t_s"] == SIGNALS_FILE["confirm_rules"]["genset_trip"]["hold_s"]
    assert len(fault["votes"]) >= A["power"]["trip_confirm"]["needed"]
    assert "frequency_dip" not in fault["votes"] and s["plant"]["bus_frequency_hz"]["value"] == 59.6 > 58.8
    assert fault["first_shed_due_t_s"] == raw + A["response_time_s"]["shed_first_action"]
    assert fault["full_sequence_due_t_s"] == raw + A["response_time_s"]["shed_full_sequence"]
    assert fault["confirmed_t_s"] + 1 <= fault["first_shed_due_t_s"], "the first shed lands at the next tick, in ship time"


def test_minute_19_one_chilled_water_pump_left():
    s = survey(19)
    ev = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    landed = next(e for e in TL["events"] if e["type"] == "guest_state" and e["guest"] == "G4")
    pl = s["plant"]
    assert pl["cooling_state"]["value"] == "degraded" and pl["cooling_state"]["confidence"] == "confirmed"
    assert [pl["chw_pump_1_running"]["value"], pl["chw_pump_2_running"]["value"]].count(True) == 1
    assert pl["chw_pump_1_alarm"]["value"] and not pl["chw_pump_1_running"]["value"]
    assert pl["chw_return_c"]["value"] - pl["chw_supply_c"]["value"] > 8 and pl["chw_flow_pct"]["value"] < 70
    assert s["guests"]["G4"]["activity"]["value"] == "landed"
    assert s["guests"]["G4"]["mode_ends_t_s"]["value"] == landed["t_min"] * 60 + 1200
    fault = next(f for f in s["faults"] if f["fault"] == "cooling_degraded")
    assert fault["injected"] == ev["injected"] and fault["raw_event_t_s"] == (landed["t_min"] + ev["trigger"]["delay_min"]) * 60
    assert {"pump_alarm"} < set(fault["votes"])
    assert "noise manoeuvring" not in " ".join(s["capacity"]["acoustic"]["value"]["degraded_by"])
    assert s["ship_state"]["noise"]["value"] == "normal"


# ------------------------------------------------------------------------------ feeds that drop

def test_a_stale_genset_feed_tightens_but_does_not_shed():
    s = FIXTURES["scenario_b_survey_m10_stale_genset_feed"]
    feed = s["feeds"]["pms"]
    assert feed["stale"] and feed["drop"]["injected"] and feed["drop"]["until_t_s"] is None
    pms = [n for n, sig in SIGNALS.items() if sig.get("feed") == "pms"]
    assert all(field(s, n)["stale"] for n in pms)
    assert not any(n in FRAMES["scenario_b_survey_m10_stale_genset_feed"]["signals"] for n in pms), "a dropped feed is left out of the frame"
    g = s["plant"]["gensets_online"]
    assert g["stale"] and g["value"] == 1 and "D4 never acts on a substituted value" in g["substituted"]["scope"]
    assert not [f for f in s["faults"] if f["state"] == "confirmed"], "no shed without a confirmed fault"
    assert any("stale" in d for d in s["capacity"]["power"]["value"]["degraded_by"])
    assert s["capacity"]["power"]["confidence"] == s["capacity"]["shed_ceiling_kw"]["confidence"] == "substituted"
    b = s["guests"]["G4"]["battery_pct"]
    assert b["age_s"] == 120 and not b["stale"] and b["confidence"] == "reported", "an old report on a healthy feed"
    assert s["guests"]["G4"]["land_by_t_s"]["confidence"] == "reported"


def test_stale_g4_telemetry_takes_the_earliest_crossing():
    s = FIXTURES["scenario_b_survey_m09_stale_g4_telemetry"]
    g4 = s["guests"]["G4"]
    feed = s["feeds"]["g4_telemetry"]
    assert feed["stale"] and feed["drop"]["injected"]
    assert s["run"]["tick"] - feed["last_heard_t_s"] > FEEDS["g4_telemetry"]["stale_after_s"]
    assert g4["battery_pct"]["age_s"] == 80 and g4["battery_pct"]["stale"], "stale with its feed"
    assert g4["activity"]["value"] == "airborne" and g4["activity"]["substituted"]["last_value"] == "airborne"
    assert g4["land_by_t_s"]["value"] == survey(8)["guests"]["G4"]["land_by_t_s"]["value"]
    assert g4["land_by_t_s"]["confidence"] == "substituted", "the decision sentence names the stale feed"
    assert s["capacity"]["los_radio"]["value"]["capacity"] == A["data"]["los_radio_mbps"]["min"]


def test_g3_is_out_of_contact_not_stale_while_the_link_is_down():
    for name in ("scenario_b_survey_m19", "scenario_b_sar_m19"):
        s = FIXTURES[name]
        g3 = s["guests"]["G3"]
        assert not s["links"]["acoustic_link_up"]["value"]
        assert g3["activity"]["age_s"] > FEEDS["g3_acoustic"]["stale_after_link_up_s"] and not g3["activity"]["stale"]
        assert g3["hold_ack"]["value"] is True and g3["activity"]["confidence"] == "reported"
    assert "surveying only if the last report was surveying" in SIGNALS["G3.activity"]["fallback"]["rule"]
    assert "airborne only if the last value was airborne" in SIGNALS["G4.activity"]["fallback"]["rule"]


def test_the_hold_ack_is_a_feasible_round_trip():
    lo, hi = A["data"]["acoustic_latency_s"]
    ack = survey(12)["guests"]["G3"]["hold_ack"]
    assert ack["value"] and 2 * lo <= ack["since_t_s"] - 480 <= 2 * hi
    assert ack["since_t_s"] < survey(12)["links"]["acoustic_link_up"]["since_t_s"], "acked before the manoeuvre breaks the link"


# ------------------------------------------------------------------------------ the bus load behind the genset kW

@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_genset_kw_follows_the_bus_load(name):
    """fault_signatures.bus_load: half each with both online, the other capped at its rating after a trip."""
    snap = FIXTURES[name]
    p = A["power"]
    pl = snap["plant"]
    guests = sum(b["kw_actual"]["value"] for b in snap["guests"].values())
    tripped = pl["genset_2_relay_trip"]["value"] or pl["genset_1_relay_trip"]["value"]
    load = p["hotel_kw"]["committed"] - (p["hotel_shed_on_trip_kw"] if tripped else 0) + p["ship_aux_kw"] + guests
    g1, g2 = pl["genset_1_kw"]["value"], pl["genset_2_kw"]["value"]
    if tripped:
        assert g2 == 0 and g1 == round(min(p["gensets"]["rating_kw"], load), 1)
    else:
        assert g1 == g2 == round(load / 2, 1)
    assert max(g1, g2) <= SIGNALS["genset_1_kw"]["range"][1] == p["gensets"]["rating_kw"]
    assert max(g1, g2) <= p["gensets"]["rating_kw"] * p["gensets"]["load_limit"], "inside the 405 kW load limit in Scenario B"


def test_bus_load_numbers_are_the_fixtures():
    kw = SIGNALS_FILE["fault_signatures"]["bus_load"]["scenario_b_kw"]
    assert survey(0)["plant"]["genset_1_kw"]["value"] == kw["both_online"] == BASE["start"]["genset_1_kw"]
    assert survey(12)["plant"]["genset_1_kw"]["value"] == FIXTURES["scenario_b_sar_m12"]["plant"]["genset_1_kw"]["value"] == kw["tripped_g4_airborne"]
    assert survey(19)["plant"]["genset_1_kw"]["value"] == kw["tripped_g4_fast_charge"]


# ------------------------------------------------------------------------------ the run baseline

STEP_DEFS = FRAME_SCHEMA["$defs"]


def _validator(name):
    return Draft202012Validator({**STEP_DEFS[name], "$defs": STEP_DEFS})


EVENT_V, CMD_V, INPUT_V, START_V = (_validator(n) for n in ("event", "command", "input", "start"))


def run_start(variant="default"):
    return {**BASE["start"], **(BASE["variants"][variant]["start"] if variant != "default" else {})}


def test_the_baseline_start_is_the_tick_0_frame():
    frame, snap = FRAMES["scenario_b_survey_m00"], survey(0)
    readings = dict(frame["signals"])
    for gid, block in frame["guests"].items():
        readings.update({f"{gid}.{k}": r for k, r in block.items()})
    assert set(readings) == set(BASE["start"]), "every tick-0 reading has a start value, and nothing else does"
    raw = {n for n, s in SIGNALS.items()
           if s["producer"] != "estimator" and (s["group"] != "guests" or n.split(".")[0] in TL["guests"])}
    assert raw - set(BASE["start"]) == {"G4.battery_pct"}, "only G4's battery has no reading before minute 8"
    for n, r in readings.items():
        assert r["value"] == BASE["start"][n], n
        assert r["source"] == ("scenario" if n in BASE["scenario_sourced"] else sources(SIGNALS[n])[0]), n
    assert BASE["start"]["seawater_c"] == TL["location"]["seawater_c"] and BASE["seed"] == snap["run"]["seed"]
    base = next(e for e in frame["events"] if e["type"] == "baseline")
    assert base["payload"]["start"] == run_start() and base["payload"]["note"] == TL["events"][0]["note"]
    for variant in ["default", *BASE["variants"]]:
        assert START_V.is_valid(run_start(variant)), variant
    assert not START_V.is_valid(dict(BASE["start"], crew_aboard=3)), "start values are typed"
    for name, points in BASE["series"].items():
        assert points[0] == [0, BASE["start"][name]], name


def test_the_crew0_fixture_starts_from_its_variant():
    s = FIXTURES["scenario_b_survey_m08_crew0"]
    v = BASE["variants"]["crew0"]["start"]
    assert s["run"]["variant"] == "crew0"
    for name, value in v.items():
        assert field(s, name)["value"] == value, name
    assert v["last_sweep"]["t_s"] < 0, "a sweep from before tick 0, which no deck_sweep input could express"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_wind_and_g4_range_follow_the_baseline_series(name):
    snap = FIXTURES[name]
    tick = snap["run"]["tick"]
    series = {n: BUILD.series_at(p, tick) for n, p in BASE["series"].items()}
    assert snap["environment"]["wind_kn"]["value"] == series["wind_kn"]
    g4 = snap["guests"]["G4"]
    if g4["activity"]["value"] == "landed":
        assert g4["range_km"]["value"] == 0
    elif not g4["range_km"]["stale"]:
        assert g4["range_km"]["value"] == series["G4.range_km"]
    else:
        last = g4["range_km"]["substituted"]
        assert last["last_value"] == BUILD.series_at(BASE["series"]["G4.range_km"], last["last_good_t_s"])


# ------------------------------------------------------------------------------ the timeline, mapped to frame events

MAPPING = SIGNALS_FILE["timeline_mapping"]


def applied_tick(e):
    if "trigger" in e:
        after = e["trigger"]["after"]
        landing = next(x for x in TL["events"] if x.get("guest") == after["guest"] and x.get("state") == after["state"])
        return applied_tick(landing) + 60 * e["trigger"]["delay_min"]
    return math.ceil(60 * e["t_min"])


def frame_event(e, variant="default"):
    """timeline_mapping applied to one scenario event: the frame event the simulator echoes."""
    m = MAPPING["events"][e["type"]]
    tick = applied_tick(e)
    payload = {pk: e[sk] for pk, sk in m.get("copy", {}).items()}
    if "fields" in m:
        payload["fields"] = {k: e[k] for k in m["fields"]}
    for sk, table in m.get("split", {}).items():
        payload.update(table[e[sk]])
    payload.update(m.get("add", {}))
    context = {"variant": variant, "start": run_start(variant)}
    payload.update({k: context[k] for k in m.get("context", [])})
    payload.update({k: tick + d for k, d in m.get("plus_s", {}).items()})
    injected = bool(e.get(m.get("flag", {}).get("injected"), False))
    accounted = (set(m.get("copy", {}).values()) | set(m.get("fields", [])) | set(m.get("split", {}))
                 | set(m.get("drop", {})) | set(m.get("flag", {}).values()))
    assert accounted == set(e) - {"t_min", "type"}, f"{e['type']}: every scenario key is mapped or dropped"
    return {"t_s": tick, "type": e["type"], "origin": "timeline", "injected": injected, "payload": payload}


@pytest.mark.parametrize("e", TL["events"], ids=[e["type"] for e in TL["events"]])
def test_every_timeline_event_maps_to_a_valid_frame_event(e):
    assert e["type"] in MAPPING["events"]
    ev = frame_event(e)
    errors = list(EVENT_V.iter_errors(ev))
    assert not errors, "; ".join(x.message for x in errors[:3])
    literal = {"t_s": ev["t_s"], "type": e["type"], "origin": "timeline", "injected": False,
               "payload": {k: v for k, v in e.items() if k not in ("t_min", "type")}}
    if e["type"] != "baseline":
        assert not EVENT_V.is_valid(literal), "copied as-is the scenario keys do not validate; the mapping is needed"


def test_the_mapped_events_are_the_fixtures_events_and_ticks():
    by_type = {e["type"]: frame_event(e) for e in TL["events"]}
    assert FRAMES["scenario_b_survey_m00"]["events"] == [by_type["baseline"]]
    assert FRAMES["scenario_b_survey_m08"]["events"] == [by_type["guest_report"]]
    assert FRAMES["scenario_b_survey_m08"]["guests"]["G4"]["battery_pct"]["value"] == by_type["guest_report"]["payload"]["fields"]["battery_pct"]
    trip, cool = by_type["genset_trip"], by_type["cooling_degraded"]
    for name in ("scenario_b_survey_m19", "scenario_b_sar_m19"):
        faults = {f["fault"]: f for f in FIXTURES[name]["faults"]}
        assert faults["genset_trip"]["raw_event_t_s"] == trip["t_s"] and faults["genset_trip"]["subject"] == f"genset_{trip['payload']['genset']}"
        assert faults["cooling_degraded"]["raw_event_t_s"] == cool["t_s"] == 1140
        assert faults["cooling_degraded"]["subject"] == f"chw_pump_{cool['payload']['pump']}" and faults["cooling_degraded"]["injected"] == cool["injected"]
        g4 = FIXTURES[name]["guests"]["G4"]
        landed = by_type["guest_state"]
        assert (g4["activity"]["value"], g4["mode"]["value"]) == (landed["payload"]["activity"], landed["payload"]["mode"])
        assert g4["mode"]["since_t_s"] == landed["t_s"] == 1020


def test_the_landing_pin_is_honoured_and_the_lag_comes_out_of_the_approach():
    pins, drafts = TL["seed_pins"], SIGNALS_FILE["transition_drafts"]
    landing = applied_tick(next(e for e in TL["events"] if e.get("state") == "landed_fast_charging"))
    assert landing == 60 * pins["g4_lands_at_min"] == 1020
    script = BASE["script"]
    answer = next(t for t, xs in script["inputs"].items() for x in xs if x["type"] == "bridge_answer")
    assert answer == 480 + 60 * pins["confirm_min"]
    decided = next(t for t, xs in script["commands"].items() for c in xs if c["kind"] == "clear_deck")
    assert decided == answer, "the deck clear is decided on the snapshot that shows the answer"
    clear_end = decided + 1 + drafts["deck_clear"]["expected_s"]
    assert drafts["deck_clear"]["expected_s"] == 60 * pins["deck_clear_min"]
    tr = survey(12)["ship_state"]["deck_flight_deck"]["transition"]
    assert (tr["started_t_s"], tr["expected_end_t_s"], tr["latest_end_t_s"]) == (decided + 1, clear_end, decided + 1 + drafts["deck_clear"]["latest_s"])
    approach = landing - clear_end
    assert approach == 60 * pins["approach_min"] - 1, "the one-tick actuation lag is absorbed in the final approach"


# ------------------------------------------------------------------------------ sim.step: commands and inputs

def script_commands(mission):
    for tick, cmds in BASE["script"]["commands"].items():
        for c in cmds:
            if mission in c.get("missions", [mission]):
                yield tick, {k: v for k, v in c.items() if k in ("seq", "kind", "args")}


def test_events_are_routed_to_the_simulator_or_the_core():
    for name, ev in SIGNALS_FILE["events"].items():
        assert set(ev["from"]) <= {"timeline", "laptop"} and ev["from"], name
        assert ev["to"] in ("simulator", "core"), name
    inputs = set(STEP_DEFS["input"]["properties"]["type"]["enum"])
    want = {n for n, ev in SIGNALS_FILE["events"].items() if "laptop" in ev["from"] and ev["to"] == "simulator"}
    assert inputs == want
    assert {"card_presented", "card_edited", "priority_swap", "safety_request"} == {n for n, ev in SIGNALS_FILE["events"].items() if ev["to"] == "core"}
    assert not inputs & {"card_presented", "safety_request"}, "core-only inputs never reach sim.step"
    assert {e["type"] for e in TL["events"]} <= {n for n, ev in SIGNALS_FILE["events"].items() if "timeline" in ev["from"]}


@pytest.mark.parametrize("mission", ["survey", "sar"])
def test_the_scenario_b_script_is_typed(mission):
    assert set(STEP_DEFS["command"]["properties"]["kind"]["enum"]) == set(SIGNALS_FILE["commands"])
    for tick, c in script_commands(mission):
        errors = list(CMD_V.iter_errors(c))
        assert not errors, (tick, c, [e.message for e in errors[:3]])
    for tick, xs in BASE["script"]["inputs"].items():
        for x in xs:
            inp = {"t_s": tick, **{k: v for k, v in x.items() if k != "why"}}
            assert INPUT_V.is_valid(inp), inp
    assert not CMD_V.is_valid({"seq": 1, "kind": "set_mode", "args": {"guest": "G4"}}), "command args are typed"
    assert not INPUT_V.is_valid({"t_s": 0, "type": "safety_request", "injected": False, "payload": {"request": "g3_hold_depth"}})


def test_a_bridge_request_carries_the_decision_tick():
    req = next(c for t, c in script_commands("survey") if c["kind"] == "bridge_request")
    decided = next(t for t, c in script_commands("survey") if c["kind"] == "bridge_request")
    assert req["args"]["asked_t_s"] == decided == 480, "asked at the core's tick, not at 481 when it is applied"
    assert survey(8)["crew"]["bridge_requests"]["value"] == [], "the request is applied in frame 481"
    answer = BASE["script"]["inputs"][540][0]
    for name in ("scenario_b_survey_m12", "scenario_b_sar_m12"):
        (r,) = FIXTURES[name]["crew"]["bridge_requests"]["value"]
        assert (r["request_seq"], r["rule"], r["asked_t_s"]) == (req["args"]["request_seq"], req["args"]["rule"], req["args"]["asked_t_s"])
        assert (r["state"], r["answered_t_s"]) == (answer["payload"]["answer"], 540), "answered at the input's tick"
    close = next(t for t, c in script_commands("survey") if c["kind"] == "bridge_close")
    assert survey(19)["crew"]["bridge_requests"]["since_t_s"] == close + 1


def test_readings_carry_their_arrival_tick():
    """step.readings: t_s is the arrival tick, so a report is age 0 on arrival (test_the_frame_produces_the_snapshot)."""
    assert "arrival" in SIGNALS_FILE["step"]["readings"]
    ack = survey(12)["guests"]["G3"]["hold_ack"]
    assert ack["since_t_s"] == 480 + SIGNALS_FILE["transition_drafts"]["g3_round_trip"]["expected_s"]


# ------------------------------------------------------------------------------ G3's cadence, fault subjects, the lift

def g3_message_ticks():
    """feeds.g3_acoustic.cadence: every cadence_s while the link is up, the ack restarting the count."""
    cad = FEEDS["g3_acoustic"]["cadence_s"]
    link_down = 541
    ticks, t = [], 0
    ack = 480 + SIGNALS_FILE["transition_drafts"]["g3_round_trip"]["expected_s"]
    while t < link_down:
        if t > ack and ack not in ticks:
            ticks.append(ack)
            t = ack + cad
            continue
        ticks.append(t)
        t += cad
    return sorted(ticks)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_g3_reports_follow_its_cadence(name):
    cad = FEEDS["g3_acoustic"]["cadence_s"]
    assert FEEDS["g3_acoustic"]["stale_after_link_up_s"] == 2 * cad
    msgs = g3_message_ticks()
    assert msgs[-3:] == [420, 480, 510] and msgs[-1] + cad > 541, "the next message after the ack is lost: the link drops at 541"
    snap = FIXTURES[name]
    tick = snap["run"]["tick"]
    last = tick - snap["guests"]["G3"]["activity"]["age_s"]
    assert last == max(t for t in msgs if t <= tick)
    if snap["links"]["acoustic_link_up"]["value"]:
        assert tick - last < cad


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_faults_are_held_only_by_subjects_with_their_own_vote(name):
    """confirm_rules shared votes: the loop's flow and delta-T, and the bus frequency, never make a subject alone."""
    snap = FIXTURES[name]
    pl = {k: f["value"] for k, f in snap["plant"].items()}
    cr = SIGNALS_FILE["confirm_rules"]
    assert cr["genset_trip"]["shared"] == ["frequency_dip"] and set(cr["cooling_degraded"]["shared"]) == set(cr["cooling_degraded"]["plus_any"])
    pumps = {f"chw_pump_{p}" for p in (1, 2) if pl[f"chw_pump_{p}_alarm"] or not pl[f"chw_pump_{p}_running"]}
    gens = {f"genset_{g}" for g in (1, 2) if pl[f"genset_{g}_relay_trip"] or pl[f"genset_{g}_kw"] < 22.5}
    held = {f["subject"] for f in snap["faults"]}
    assert held == pumps | gens
    if pumps:
        shared = pl["chw_flow_pct"] < 70 or pl["chw_return_c"] - pl["chw_supply_c"] > 8
        assert shared and "chw_pump_2" not in held, "the healthy pump sees the shared votes but holds no fault"


def test_a_fallback_lifts_on_the_first_fresh_frame():
    fp = SIGNALS_FILE["fallback_policy"]
    assert "lift_after_fresh_frames" not in fp and "first fresh frame" in fp["lift"]
    assert "fallback_active" not in json.dumps(SCHEMA["properties"]["feeds"])
    for name, snap in FIXTURES.items():
        for f, state in snap["feeds"].items():
            members = [n for n, s in SIGNALS.items() if s.get("feed") == f and s["rate"] in ("1 Hz", "hourly")]
            if members and f != "g3_acoustic":
                installed = [n for n in members if "." not in n or n.split(".")[0] in snap["guests"]]
                assert state["stale"] == any(field(snap, n)["stale"] for n in installed), (name, f)


# ------------------------------------------------------------------------------ transitions and serialization

def test_fixture_transitions_use_the_drafted_durations():
    d = SIGNALS_FILE["transition_drafts"]
    seen = set()
    for snap in FIXTURES.values():
        for key, draft in (("speed_kn", "speed_in_band"), ("course", "course_settle"), ("deck_flight_deck", "deck_clear")):
            f = snap["ship_state"][key]
            if "transition" in f:
                tr = f["transition"]
                assert tr["expected_end_t_s"] - tr["started_t_s"] == d[draft]["expected_s"], (key, tr)
                assert tr["latest_end_t_s"] - tr["started_t_s"] == d[draft]["latest_s"], (key, tr)
                seen.add(key)
    assert seen == {"speed_kn", "course", "deck_flight_deck"}


def test_canonical_serialization_is_byte_stable():
    c = BUILD.canonical
    assert c(18) == c(18.0) == "18" and c({"b": 0.26, "a": [True, None]}) == '{"a":[true,null],"b":0.3}'
    for rel, obj in BUILD.build(ROOT).items():
        text = c(obj)
        assert c(json.loads(BUILD.render(obj))) == text == c(json.loads(text)), rel
