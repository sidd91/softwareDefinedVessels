"""The screen's view models hold the numbers of docs/EXPECTED_OUTCOMES.md and the records' own sentences."""
import json

import jsonschema
import pytest

from sdv.ui import data, view

I = data.Inputs()
SCHEMA = json.loads((data.ROOT / "config/decision_record.schema.json").read_text())
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


def tile(v, name):
    return next(t for t in v["tiles"] if t["name"] == name)


def rows(d):
    return {k: val for k, val, _ in d["rows"]}


# ------------------------------------------------------------------------------------------- inputs

def test_the_timeline_holds_the_main_line_snapshots_per_file():
    assert [s["run"]["t_ship_s"] for s in I.timeline["survey"]] == [0, 480, 721, 1141]
    assert [s["run"]["t_ship_s"] for s in I.timeline["sar"]] == [0, 480, 721, 1141]
    assert all(s["run"]["mission"] == "sar" for s in I.timeline["sar"])
    assert all("crew0" not in json.dumps(s["notes"]) for s in I.timeline["survey"] if s["run"]["t_ship_s"] == 480)


def test_the_replay_reads_the_scenario_b_record_fixtures():
    for mission in ("survey", "sar"):
        recs = I.records[mission]
        assert [(r["kind"], r["tick"]) for r in recs] == [("D3", 480), ("D4", 721), ("D4", 1141)]
        for r in recs:
            errors = sorted(VALIDATOR.iter_errors(r), key=lambda e: list(e.absolute_path))
            assert not errors, [e.message for e in errors]


def test_records_are_released_at_their_tick():
    assert [r["kind"] for r in I.moment("survey", 479).records] == []
    assert [r["kind"] for r in I.moment("survey", 480).records] == ["D3"]
    assert [r["kind"] for r in I.moment("survey", 1141).records] == ["D3", "D4", "D4"]


# ------------------------------------------------------------------------------------------- operations

def test_minute_0_baseline():
    v = view.operations(I, "survey", 0)
    assert tile(v, "POWER")["value"] == "48.0 / 245.0 kW"
    assert tile(v, "COOLING CHW")["value"] == "48.0 / 128.3 kW"
    assert tile(v, "MASS / STAB")["value"] == "9.515 / 10.000 t"
    assert tile(v, "MASS / STAB")["sub"] == "STAB 9.763 / 12.000"
    assert tile(v, "COMPUTE")["value"] == "8 / 102 cores"
    assert tile(v, "DECK")["value"] == "3 / 4" and tile(v, "MAST")["value"] == "3 / 3"
    assert v["decision"] is None and v["header"]["alarms"] == 0
    assert v["log"][0]["type"] == "START" and "Demand 48.0 kW" in v["log"][0]["msg"]


@pytest.mark.parametrize("mission,reserved", [("survey", None), ("sar", "G4 35 kW")])
def test_minute_8_right_of_way(mission, reserved):
    v = view.operations(I, mission, 481)
    d = v["decision"]
    assert d["kind"] == "D3" and d["tag"] == "G4 PROCEEDS"
    r = rows(d)
    assert r["LAND BY"].startswith("00:18:12")
    assert "25 TO 27 min" in r["COST"]
    assert r.get("RESERVED") == reserved
    assert {c["k"] for c in d["conflicts"]} >= {"SPEED", "DECK MACHINERY", "EXCLUSION"}
    assert d["sentence"] == I.moment(mission, 481).records[-1]["sentence"]
    g3 = next(g for g in v["guests"] if g["id"] == "G3")
    assert g3["pos"] == ("DEPTH" if mission == "survey" else "AT SEA")


@pytest.mark.parametrize("mission,load", [("survey", "48.0"), ("sar", "81.0")])
def test_minute_12_holds_with_the_armed_step(mission, load):
    v = view.operations(I, mission, 722)
    assert tile(v, "POWER")["value"] == f"{load} / 95.0 kW"
    assert tile(v, "POWER")["state"] == "LIMITING"
    d = v["decision"]
    assert d["tag"] == "HOLDS"
    r = rows(d)
    assert r["RESULT"] == f"{load} / 95.0 kW"
    assert r["NEXT"] == "G5 FULL → LOW POWER · 37 kW"
    assert r["LOSS"] == "G3 NONE · G4 NONE · G5 NONE"
    assert v["shed_order"]["rows"][0]["state"] == "ARMED" and v["shed_order"]["rows"][0]["g"] == "G5"
    types = [(e["type"], e["tag"]) for e in v["log"][:2]]
    assert types == [("HOLD", "D4"), ("ALARM", "GEN 2")]


@pytest.mark.parametrize("mission,after,step,guest,cap", [
    ("survey", "56.0", "G4 FAST CHARGE → CHARGE", "G4", "70 %"),
    ("sar", "44.0", "G5 FULL → LOW POWER", "G5", "30 %"),
])
def test_minute_19_cooling_binds_and_d4_sheds(mission, after, step, guest, cap):
    v = view.operations(I, mission, 1142)
    chw = tile(v, "COOLING CHW")
    assert chw["value"] == f"{after} / 75.0 kW" and chw["state"] == "LIMITING" and chw["injected"]
    assert tile(v, "POWER")["state"] == "DEGRADED"
    d = v["decision"]
    assert d["tag"] == "EXECUTED"
    r = rows(d)
    assert r["LIMIT"] == "80.0 - 5.0 = 75.0 kW" and r["DEMAND"] == "81.0 kW"
    assert r["ACTION"] == step and r["RESULT"] == f"{after} / 75.0 kW"
    assert d["rows"][0][2] is True  # the trigger carries INJECTED
    assert next(g for g in v["guests"] if g["id"] == guest)["cap"] == cap
    calc = [(x["k"], x["v"]) for x in v["ledger"]["constraint"]["rows"]]
    assert calc[:5] == [("CHW CAPACITY AT 24 °C", "133.3 kW"), ("P1 TRIP · 1 OF 2 PUMPS", "× 0.60"), ("AVAILABLE", "80.0 kW"),
                        ("HEADROOM", "-5.0 kW"), ("LIMIT", "75.0 kW")]
    assert ("DEMAND G3 1 + G4 35 + G5 45", "81.0 kW") in calc and ("SHORTFALL", "6.0 kW") in calc
    assert calc[-1] == ("DEMAND AFTER", f"{after} kW")


def test_minute_19_before_the_command_applies_the_step_is_commanded():
    v = view.operations(I, "survey", 1141)
    assert v["decision"]["tag"] == "COMMANDED"
    assert tile(v, "COOLING CHW")["value"] == "81.0 / 75.0 kW"


def test_injected_marks_only_the_injected_fault():
    v = view.operations(I, "survey", 1142)
    marked = [e for e in v["log"] if e["injected"]]
    assert [(e["type"], e["tag"]) for e in marked] == [("ALARM", "CHW P1")]
    assert [p["tag"] for p in v["plant"] if p["injected"]] == ["CHW P1"]
    assert not any(p["injected"] for p in v["plant"] if p["tag"] == "GEN 2")


def test_every_decision_reaches_the_log_with_its_sentence():
    v = view.operations(I, "sar", data.END_T_S)
    logged = [e["msg"] for e in v["log"] if e.get("seq") is not None]
    assert sorted(logged) == sorted(r["sentence"] for r in I.records["sar"])


@pytest.mark.parametrize("mission", ["survey", "sar"])
@pytest.mark.parametrize("t", [0, 481, 722, 1141, 1142, data.END_T_S])
def test_screen_text_is_operator_style(mission, t):
    for s in strings(view.operations(I, mission, t)):
        assert ";" not in s and "demo" not in s.lower(), s


# ------------------------------------------------------------------------------------------- compare and admission

def test_compare_shows_both_files_on_the_same_inputs():
    c = view.compare(I, 1142)
    assert c["files"] == ["survey", "sar"]
    diff = {d["k"]: (d["a"], d["b"]) for d in c["diff"]}
    assert diff["ACTION"] == ("G4 FAST CHARGE → CHARGE", "G5 FULL → LOW POWER")
    assert diff["RESULT"] == ("56.0 / 75.0 kW", "44.0 / 75.0 kW")
    assert [m["label"] for m in c["marks"]] == ["START", "G4 LOW BATT", "GEN 2 TRIP", "CHW P1 TRIP"]


@pytest.mark.parametrize("case,verdict,first", [
    ("A1-survey", "YES-IF", "G1"), ("A1-sar", "YES-IF", "G3"), ("A3-survey", "YES-IF", "G2"),
    ("A5-survey", "YES", None), ("A6-survey", "YES", None), ("A7-disaster_relief", "YES", None),
])
def test_admission_cases(case, verdict, first):
    a = view.admit(I, case)
    assert a["verdict"] == verdict
    assert (a["options"][0]["remove"] if a["options"] else None) == first
    assert a["sentence"] == a["record"]["sentence"]
    assert not list(VALIDATOR.iter_errors(a["record"]))


def test_one_number_edit_and_a_rejected_edit_keeps_the_previous_card():
    a = view.admit(I, "A1-survey", {"G4.hangar.mass_t": "0.80"})
    assert a["verdict"] == "YES" and a["binding"] == "MASS 9.985 / 10.000 t"
    b = view.admit(I, "A1-survey", {"G4.hangar.mass_t": "-1"}, {"G4.hangar.mass_t": "0.80"})
    assert b["verdict"] == "CARD REJECTED" and b["rejected"]["field"] == "G4.hangar.mass_t"
    assert next(p for p in b["parts"] if p["name"] == "hangar")["mass_t"] == 0.80
    assert b["sentence"].startswith("Card rejected: G4.hangar.mass_t")


def test_a1_checks_name_the_one_genset_gate_and_the_tipping_point():
    checks = {c["k"]: (c["v"], c["s"]) for c in view.admit(I, "A1-survey")["checks"]}
    assert checks["1 GENSET"] == ("81.5 / 100 kW · GATE 95", "HOLDS")
    assert checks["SEAWATER TIP"] == ("48.0 °C", "HOLDS")
    assert checks["CHW -40 % AT 30 °C"][0] == "80.0 / 72.0 kW · GATE 67"


def test_reference_guests_come_from_the_cards():
    ref = view.reference(I)
    g4 = next(g for g in ref["guests"] if g["id"] == "G4")
    assert g4["modes"] == "fast charge 35 · charge 10 · standby 2 · off"
    assert {m["id"] for m in ref["missions"]} >= {"survey", "sar"}
