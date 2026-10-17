"""The state-estimation contract (docs/STATE_ESTIMATION.md): config/signals.yaml, config/snapshot.schema.json
and the Scenario B fixtures in tests/fixtures/snapshots/ agree with each other, with the cards and with the
oracles. No engine needed."""
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SIGNALS_FILE = yaml.safe_load((ROOT / "config/signals.yaml").read_text())
SIGNALS = {s["name"]: s for s in SIGNALS_FILE["signals"]}
ACTIVITIES = SIGNALS_FILE["activities"]
SCHEMA = json.loads((ROOT / "config/snapshot.schema.json").read_text())
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())
ORACLE = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
CARDS = {p.stem: yaml.safe_load(p.read_text()) for p in sorted((ROOT / "manifests").glob("G*.yaml"))}
FIXTURE_DIR = ROOT / "tests/fixtures/snapshots"
FIXTURES = {p.stem: json.loads(p.read_text()) for p in sorted(FIXTURE_DIR.glob("*.json"))}

GROUPS = ["plant", "ship_state", "environment", "links", "crew", "capacity"]
KINDS = {"plant", "ship_state", "guest", "crew", "link", "environment", "derived"}
TYPES = {"enum", "number", "integer", "boolean", "ship_time", "capacity", "rates"}
RATE_KEYS = {"backbone_mbps", "satcom_mbps", "los_radio_mbps", "acoustic_kbps"}
CONFIDENCE = SIGNALS_FILE["field_metadata"]["confidence"]
GUEST_ID = re.compile(r"^G\d$")

# Scenario B placement (DEC-32): which mission line feeds each guest's draw.
PLACEMENT = {"G3": "bay1", "G4": "flight_deck", "G5": "bay2"}

# ---------------------------------------------------------------------------------------------------------
# Today's free-text names on the cards, mapped to the typed vocabulary. Remove this table when F2 types the
# cards (DESIGN_FREEZE delta 2): from then on the cards use the signal and activity names directly.
# (guest or None, activity or None, card key) -> signal. The most specific match wins.
CONDITION_KEYS = {
    (None, None, "speed_kn"): "speed_kn",
    (None, None, "speed_kn_max"): "speed_kn",
    (None, None, "sea_state_max"): "sea_state",
    (None, None, "wind_kn_max"): "wind_kn",
    (None, None, "course"): "course",
    (None, None, "noise"): "noise",
    (None, None, "emission"): "emission",
    (None, None, "ramp"): "ramp",
    (None, None, "deck_around_bay"): "deck_bays",
    ("G4", None, "deck"): "deck_flight_deck",
    ("G4", None, "turn_into_wind"): "heading_free",
    ("G6", "start", "people"): "people_available",
    # One key, two meanings: G2 means "machinery is permitted", G3 means "no machinery is running".
    ("G2", "winch", "deck_machinery_allowed"): "deck_machinery_permitted",
    ("G3", "surveying", "deck_machinery_allowed"): "deck_machinery",
}
# Card values that are spelled differently from the signal's values.
VALUE_ALIASES = {("ramp", "not_in_use"): "free", ("heading_free", "free"): True}
# Relation references that are not Gx.activity names today.
REFERENCE_ALIASES = {
    "G4.recovering": ("activity", "G4.launch_recovery"),          # G2.yaml, G3.yaml; OPEN_QUESTIONS #44
    "stern_ramp_ops": ("activity", "G3.launch_recovery"),         # G4.yaml; A.3 flight deck and ramp exclusive
    "emission_silence": ("signal", "emission", "silent"),         # G5.yaml; a ship-state value, not an activity
    "always": ("literal", None),                                  # G5.yaml exclusion when
    "both need the one free mast slot": ("position", "mast_free"),  # G1.yaml; placement contention
}
# Keys of the A.11 installation window and the acoustic rule in config/assumptions.yaml.
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
        return (set(v) >= {"capacity", "committed", "free", "unit", "degraded_by"} and v["unit"] == sig["unit"]
                and abs(v["capacity"] - v["committed"] - v["free"]) < 0.051)
    if t == "rates":
        return set(v) <= RATE_KEYS and all(isinstance(x, (int, float)) and x >= 0 for x in v.values())
    return False


def sources(sig):
    return sig["source"] if isinstance(sig["source"], list) else [sig["source"]]


def stale_limit(sig, crew=14):
    lim = sig["stale_after_s"]
    return lim["by_crew"][crew] if isinstance(lim, dict) else lim


def mode_kw(gid, mode):
    return next(m["power_kw"] for m in CARDS[gid]["modes"] if m["name"] == mode)


def heat_capacity(seawater_c, factor=1.0):
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    t = max(seawater_c, t0)
    return (c0 + (c1 - c0) * (t - t0) / (t1 - t0)) * factor


def at(minute):
    return next(s for n, s in FIXTURES.items() if n.startswith(f"scenario_b_survey_m{minute:02d}"))


# ------------------------------------------------------------------------------ the vocabulary itself

def test_fixtures_exist():
    assert {n[:21] for n in FIXTURES} >= {f"scenario_b_survey_m{m:02d}" for m in (0, 8, 12, 19)}
    assert any("stale" in n for n in FIXTURES)


@pytest.mark.parametrize("name", sorted(SIGNALS))
def test_every_signal_is_typed_with_a_stale_limit_and_a_fallback(name):
    s = SIGNALS[name]
    assert s["kind"] in KINDS and s["type"] in TYPES
    assert s["group"] in GROUPS + ["guests"]
    assert s["producer"] in {"simulator", "laptop", "estimator"}
    assert set(sources(s)) <= set(SIGNALS_FILE["field_metadata"]["source"])
    assert (s["kind"] == "derived") == (s["producer"] == "estimator") == (sources(s) == ["derived"])
    if s["type"] == "enum" or (s["type"] == "integer" and "range" not in s):
        assert s["values"]
    if s["type"] in ("number",) or (s["type"] == "integer" and "values" not in s):
        assert "unit" in s and len(s["range"]) == 2
    lim = s["stale_after_s"]
    if isinstance(lim, dict):
        assert set(lim["by_crew"]) == set(A["crew"]["levels"])
    else:
        assert isinstance(lim, (int, float)) and lim > 0
    assert set(s["fallback"]) & {"value", "rule", "by_use"}
    if "value" in s["fallback"] and s["type"] in ("enum", "boolean", "integer", "number"):
        assert value_ok(s, s["fallback"]["value"]), "fallback outside the signal's type"
    for use, v in s["fallback"].get("by_use", {}).items():
        assert value_ok(s, v), use
    assert s["read_by"] and s["provenance"]
    if s["group"] == "guests":
        assert GUEST_ID.match(name.split(".")[0])


def test_the_default_stale_limit_is_the_assumptions_one():
    assert SIGNALS_FILE["default_stale_after_s"] == A["stale_feed"]["after_s"]
    assert SIGNALS["G4.battery_pct"]["stale_after_s"] == A["rules"]["r3"]["stale_s"]["g4_telemetry"]
    assert SIGNALS_FILE["confirm_rules"]["genset_trip"]["needed"] == A["power"]["trip_confirm"]["needed"]
    assert SIGNALS_FILE["confirm_rules"]["genset_trip"]["hold_s"] == A["fault_entry"]["debounce_s"]
    assert SIGNALS_FILE["confirm_rules"]["restore"]["healthy_hold_s"] == A["fault_entry"]["restore_hold_s"]


def test_speed_is_numeric_and_the_band_is_derived():
    assert SIGNALS["speed_kn"]["type"] == "number" and SIGNALS["speed_kn"]["unit"] == "kn"
    assert SIGNALS["speed_band"]["kind"] == "derived"
    assert SIGNALS["speed_band"]["values"] == A["ship_state"]["speed_band"]["values"]


def test_ship_state_values_match_the_assumptions():
    for var in ["course", "noise", "emission"]:
        assert SIGNALS[var]["values"] == A["ship_state"][var]["values"]
    for zone in ["deck_flight_deck", "deck_bays"]:
        assert SIGNALS[zone]["values"] == A["ship_state"]["deck"]["values"]
    assert SIGNALS["crew_aboard"]["values"] == A["crew"]["levels"]
    assert SIGNALS["cooling_state"]["values"] == A["ship_state"]["cooling"]["values"]
    assert sorted(SIGNALS["gensets_online"]["values"]) == sorted(A["ship_state"]["genset"]["values"])


def test_the_acoustic_rule_reads_only_signals():
    for key, value in A["data"]["acoustic_link"]["up_when"].items():
        assert value_ok(SIGNALS[key], value), key


def test_schema_lists_exactly_the_signals():
    Draft202012Validator.check_schema(SCHEMA)
    props = SCHEMA["properties"]
    for g in GROUPS:
        want = {s["name"] for s in SIGNALS.values() if s["group"] == g}
        assert set(props[g]["properties"]) == want, g
        assert set(props[g]["required"]) == want, g
    for gid in CARDS:
        want = {n.split(".", 1)[1] for n, s in SIGNALS.items() if s["group"] == "guests" and n.startswith(gid + ".")}
        assert set(props["guests"]["properties"][gid]["properties"]) == want, gid


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
            for sig, val in v["effects"].items():
                assert value_ok(SIGNALS[sig], val), f"{gid}.{act} effect {sig}"


def resolve_condition_key(gid, act, key):
    for k in [(gid, act, key), (gid, None, key), (None, None, key)]:
        if k in CONDITION_KEYS:
            return CONDITION_KEYS[k]
    return key if key in SIGNALS else None


def condition_value_ok(sig_name, key, v):
    sig = SIGNALS[sig_name]
    vals = v if isinstance(v, list) and sig["type"] != "number" else [v]
    if sig["type"] == "number" and isinstance(v, list):
        return len(v) == 2 and all(value_ok(sig, x) for x in v)
    return all(value_ok(sig, VALUE_ALIASES.get((sig_name, x), x)) for x in vals)


CARD_CONDITIONS = [(gid, c["activity"], k, v) for gid, card in CARDS.items()
                   for c in card.get("conditions", []) for k, v in c["requires"].items()]


@pytest.mark.parametrize("gid,act,key,value", CARD_CONDITIONS, ids=[f"{g}.{a}.{k}" for g, a, k, _ in CARD_CONDITIONS])
def test_every_condition_key_maps_to_a_signal(gid, act, key, value):
    sig = resolve_condition_key(gid, act, key)
    assert sig in SIGNALS, f"{gid}.{act} requires {key}: no signal"
    assert condition_value_ok(sig, key, value), f"{gid}.{act} {key}: {value!r} is not a value of {sig}"


def resolve_reference(ref, gid):
    """A relation target or condition: a registered activity, a card part, a position or an aliased name."""
    if ref in REFERENCE_ALIASES:
        kind, target, *rest = REFERENCE_ALIASES[ref]
        if kind == "activity":
            g, a = target.split(".")
            return a in ACTIVITIES[g]
        if kind == "signal":
            return value_ok(SIGNALS[target], rest[0])
        if kind == "position":
            return target in A["positions"]
        return kind == "literal"
    m = re.fullmatch(r"(G\d)\.(\w+)", ref)
    if m:
        g, name = m.groups()
        parts = {p["name"] for p in CARDS[g]["placement"]["parts"]}
        return name in ACTIVITIES[g] or name in parts
    return ref in A["positions"]


REFERENCES = [(gid, ref) for gid, card in CARDS.items() for ex in card.get("relations", {}).get("excludes", [])
              for ref in (ex["what"], ex["when"])]
REFERENCES += [(gid, r) for gid, card in CARDS.items() for r in card.get("relations", {}).get("requires", [])]


@pytest.mark.parametrize("gid,ref", REFERENCES, ids=[f"{g}:{r}" for g, r in REFERENCES])
def test_every_relation_reference_resolves(gid, ref):
    assert resolve_reference(ref, gid), f"{gid} refers to {ref!r}, which is no activity, part, position or alias"


LIMITS = [(gid, lim["when"]) for gid, card in CARDS.items() for lim in card.get("hard_limits", [])]


@pytest.mark.parametrize("gid,when", LIMITS, ids=[f"{g}:{w}" for g, w in LIMITS])
def test_every_hard_limit_names_a_signal_or_an_activity(gid, when):
    for clause in when.split(" and "):
        m = re.fullmatch(r"\s*(\w+)\s*(==|<=|>=|<|>)\s*(\w+)\s*", clause)
        if not m:
            assert clause.strip() in ACTIVITIES[gid], f"{gid}: {clause!r} is not a registered activity"
            continue
        ident, _, raw = m.groups()
        sig = f"{gid}.{ident}" if f"{gid}.{ident}" in SIGNALS else ident
        assert sig in SIGNALS, f"{gid}: {ident!r} is no signal"
        value = int(raw) if raw.isdigit() else raw     # not yaml: YAML 1.1 reads "off" as false
        assert value_ok(SIGNALS[sig], value) or SIGNALS[sig]["type"] == "number", f"{gid}: {raw!r} for {sig}"


def test_installation_window_and_ramp_names_resolve():
    for key, value in A["installation"]["at_sea_crewed"]["window"].items():
        target = WINDOW_KEYS[key]
        if isinstance(target, tuple):
            g, a = target[1].split(".")
            assert a in ACTIVITIES[g]
        else:
            assert condition_value_ok(target, key, value), key


# ------------------------------------------------------------------------------ the fixtures

VALIDATOR = Draft202012Validator(SCHEMA)


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_validates_against_the_schema(name):
    errors = sorted(VALIDATOR.iter_errors(FIXTURES[name]), key=lambda e: list(e.path))
    assert not errors, "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_fixture_field_is_a_typed_signal(name):
    snap = FIXTURES[name]
    crew = snap["crew"]["crew_aboard"]["value"]
    for sig_name, group, f in fields(snap):
        assert sig_name in SIGNALS, f"{sig_name} is not in config/signals.yaml"
        sig = SIGNALS[sig_name]
        assert sig["group"] == group, sig_name
        assert value_ok(sig, f["value"]), f"{sig_name}: {f['value']!r}"
        assert f["source"] in sources(sig), sig_name
        assert ("substituted" in f) == (f["confidence"] == "substituted"), sig_name
        if sig["kind"] == "derived":
            # A derived field is as old as its oldest deciding input, and stale only through a fallback.
            assert f["stale"] == ("substituted" in f), sig_name
        else:
            assert f["stale"] == (f["age_s"] > stale_limit(sig, crew)), sig_name
            if f["stale"]:
                assert "substituted" in f, f"{sig_name} is stale with no fallback recorded"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_run_and_clock(name):
    snap = FIXTURES[name]
    run = snap["run"]
    assert run["tick"] == run["t_ship_s"], "1 Hz in ship time: tick n is at n s"
    assert set(run["installed"]) == set(snap["guests"]) == set(TL["guests"])
    assert (ROOT / f"config/missions/{run['mission']}.yaml").exists()
    assert "wall" not in json.dumps(snap), "wall-clock time belongs in the timing log, not the snapshot"
    for _, _, f in fields(snap):
        if "transition" in f:
            tr = f["transition"]
            assert tr["started_t_s"] <= run["t_ship_s"] < tr["expected_end_t_s"] <= tr.get("latest_end_t_s", tr["expected_end_t_s"])
    for gid, block in snap["guests"].items():
        act = block["activity"]["value"]
        mode = block["mode"]["value"]
        if act != "none":
            assert mode in ACTIVITIES[gid][act]["modes"], f"{gid} {act} runs in {ACTIVITIES[gid][act]['modes']}, not {mode}"


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_fixture_capacity_arithmetic(name):
    snap = FIXTURES[name]
    cap = {k: f["value"] for k, f in snap["capacity"].items()}
    modes = {g: b["mode"]["value"] for g, b in snap["guests"].items()}
    draw = {g: mode_kw(g, m) for g, m in modes.items()}
    reserved = sum(snap["held_by_core"]["reservations_kw"].values())
    assert cap["power"]["committed"] == sum(draw.values()) + reserved
    chilled = sum(kw for g, kw in draw.items() if CARDS[g]["cooling"] == "chilled_water")
    assert cap["heat"]["committed"] == chilled
    for line in ["port", "stbd"]:
        on_line = sum(kw for g, kw in draw.items() if A["positions"][PLACEMENT[g]]["power_line"] == line)
        assert cap[f"{line}_line"]["committed"] == on_line, line
        assert cap[f"{line}_line"]["capacity"] == A["power"]["mission_line_kw"][line]
    online = snap["plant"]["gensets_online"]["value"]
    band = snap["ship_state"]["speed_band"]["value"]
    if online == 1:
        reserve = A["power"]["guest_reserve_kw"]["one_genset_down"]
    else:
        by_speed = A["power"]["guest_reserve_kw_by_speed"]
        reserve = by_speed.get(band, SIGNALS_FILE["derivations"]["stopped_reserve_kw"]["value"])
    assert cap["power"]["capacity"] == reserve
    degraded = snap["plant"]["cooling_state"]["value"] == "degraded"
    sea = snap["environment"]["seawater_c"]["value"]
    heat = heat_capacity(sea, A["heat"]["degraded_factor"] if degraded else 1.0)
    assert cap["heat"]["capacity"] == pytest.approx(heat, abs=0.05)
    assert cap["shed_ceiling_kw"] == pytest.approx(min(reserve, heat) - A["power"]["shed_headroom_kw"], abs=0.05)
    link_up = snap["links"]["acoustic_link_up"]["value"]
    ss = {k: f["value"] for k, f in snap["ship_state"].items()}
    rule = A["data"]["acoustic_link"]["up_when"]
    expect_up = all(ss[k] == v for k, v in rule.items()) and not snap["environment"]["layered_water"]["value"]
    assert link_up == expect_up
    satcom = snap["links"]["satcom_mbps"]["value"] if ss["emission"] == "normal" else 0
    assert cap["satcom"]["capacity"] == satcom


# ------------------------------------------------------------------------------ Scenario B, minute by minute

def test_minute_0_matches_the_timeline():
    s = at(0)
    assert s["environment"]["seawater_c"]["value"] == TL["location"]["seawater_c"]
    assert s["environment"]["layered_water"]["value"] == TL["location"]["layered"]
    assert s["ship_state"]["speed_kn"]["value"] == 3.0
    assert s["guests"]["G3"]["activity"]["value"] == "surveying" and s["links"]["acoustic_link_up"]["value"]
    assert s["guests"]["G4"]["activity"]["value"] == "airborne" and s["guests"]["G5"]["mode"]["value"] == "full"


def test_minute_8_land_by_is_18_2():
    s = at(8)
    report = next(e for e in TL["events"] if e["type"] == "guest_report" and e["guest"] == "G4")
    g4 = s["guests"]["G4"]
    assert s["run"]["t_ship_s"] == report["t_min"] * 60
    assert g4["battery_pct"]["value"] == report["battery_pct"] and g4["battery_pct"]["age_s"] == 0
    assert s["environment"]["wind_kn"]["value"] == report["wind_kn"]
    # The card's own numbers: below 20 %, land within 12 min.
    limit = next(l for l in CARDS["G4"]["hard_limits"] if "battery_pct" in l["when"])
    threshold = float(re.search(r"<\s*(\d+)", limit["when"]).group(1))
    within_min = float(re.search(r"within (\d+) min", limit["then"]).group(1))
    drain = A["rules"]["r3"]["drain_pct_min"]
    crossing_min = report["t_min"] - (threshold - report["battery_pct"]) / drain
    expected = (crossing_min + within_min) * 60
    timing = ORACLE["scenario_b"]["minute_8"]["timing"]
    assert g4["battery_crossing_t_s"]["value"] == pytest.approx(crossing_min * 60, abs=0.1)
    assert g4["land_by_t_s"]["value"] == pytest.approx(expected, abs=0.1)
    assert round(g4["land_by_t_s"]["value"] / 60, 1) == timing["deadline_min"] == 18.2
    assert round(g4["battery_crossing_t_s"]["value"] / 60, 1) == timing["crossed_threshold_at_min"]
    # Earlier than the endurance bound, and the deadline never moves later afterwards.
    endurance = g4["airborne_since_t_s"]["value"] + 90 * 60
    assert g4["land_by_t_s"]["value"] < endurance
    for later in FIXTURES.values():
        lb = later["guests"]["G4"]["land_by_t_s"]["value"]
        if later["run"]["t_ship_s"] > 480 and lb is not None:
            assert lb <= g4["land_by_t_s"]["value"]


def test_minute_12_holds_with_g4_airborne_at_2_kw():
    s = at(12)
    trip = next(e for e in TL["events"] if e["type"] == "genset_trip")
    o = ORACLE["scenario_b"]["minute_12_as_decided"]["by_file"]["survey"]
    assert s["plant"]["gensets_online"]["value"] == trip["gensets_online"]
    assert s["plant"]["cooling_state"]["value"] == trip["cooling"]
    assert {g: b["mode"]["value"] for g, b in s["guests"].items()} == o["modes"]
    assert s["guests"]["G4"]["activity"]["value"] == "airborne" and s["guests"]["G4"]["kw_actual"]["value"] == 2.0
    cap = s["capacity"]
    assert cap["power"]["value"]["committed"] == o["load_kw"]
    assert cap["shed_ceiling_kw"]["value"] - o["load_kw"] == o["spare_kw"]
    assert cap["shed_ceiling_kw"]["value"] == ORACLE["scenario_b"]["ceiling"]["kw"]
    fault = next(f for f in s["faults"] if f["fault"] == "genset_trip")
    assert fault["raw_event_t_s"] == trip["t_min"] * 60
    assert fault["confirmed_t_s"] - fault["raw_event_t_s"] == A["fault_entry"]["debounce_s"]
    assert len(fault["votes"]) >= A["power"]["trip_confirm"]["needed"]
    assert fault["first_shed_budget_s"] == A["response_time_s"]["shed_first_action"] - A["fault_entry"]["debounce_s"]


def test_minute_19_one_chilled_water_pump_left():
    s = at(19)
    ev = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    landed = next(e for e in TL["events"] if e["type"] == "guest_state" and e["guest"] == "G4")
    pl = s["plant"]
    assert pl["cooling_state"]["value"] == "degraded"
    assert [pl["chw_pump_1_running"]["value"], pl["chw_pump_2_running"]["value"]].count(True) == 1
    assert pl["chw_pump_1_alarm"]["value"] and not pl["chw_pump_1_running"]["value"]
    assert {g: b["mode"]["value"] for g, b in s["guests"].items()} == ev["load_modes"]
    assert s["guests"]["G4"]["activity"]["value"] == "landed"
    assert s["guests"]["G4"]["mode_ends_t_s"]["value"] == landed["t_min"] * 60 + 1200
    fault = next(f for f in s["faults"] if f["fault"] == "cooling_degraded")
    assert fault["injected"] == ev["injected"] and fault["raw_event_t_s"] == ev["t_min"] * 60
    assert {"pump_alarm"} < set(fault["votes"])
    cap = s["capacity"]
    assert cap["heat"]["value"]["capacity"] == pytest.approx(heat_capacity(24, ev["factor"]), abs=0.05) == 80.0
    assert cap["shed_ceiling_kw"]["value"] == 75.0
    assert cap["power"]["value"]["committed"] == sum(mode_kw(g, m) for g, m in ev["load_modes"].items()) == 81


def test_stale_feed_tightens_but_does_not_shed():
    stale = [s for n, s in FIXTURES.items() if "stale" in n]
    assert stale
    for s in stale:
        subs = [(n, f) for n, _, f in fields(s) if f["stale"]]
        assert subs, "a stale fixture must hold a stale field"
        g = s["plant"]["gensets_online"]
        assert g["stale"] and g["value"] == 1 and "D4" in g["substituted"]["scope"]
        assert not [f for f in s["faults"] if f["state"] == "confirmed"], "no shed without a confirmed fault"
        assert any("stale" in d for d in s["capacity"]["power"]["value"]["degraded_by"])
