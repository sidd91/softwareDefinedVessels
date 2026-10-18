"""D3 at minute 8 and D4 at minutes 12 and 19 of Scenario B, decided on the contract's snapshots."""
import copy
import json

import pytest
import yaml

from sdv import arbitration as D3
from sdv import loader as Ld
from sdv import shedding as D4

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SIGNALS = yaml.safe_load((Ld.ROOT / "config/signals.yaml").read_text())
O = yaml.safe_load((Ld.ROOT / "tests/oracles/expected_outcomes.yaml").read_text())["scenario_b"]
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_minute_8_matches_the_oracle(file_id):
    r = D3.right_of_way(A, SIGNALS, CARDS, MISSIONS[file_id], SNAP["scenario_b_survey_m08"])
    want = O["minute_8"]["by_file"][file_id]
    assert r["proceeds"] == want["proceeds"]
    assert r["hard_limit"] == want["hard_limit"]
    assert r["deadline_min"] == O["minute_8"]["timing"]["deadline_min"] == 18.2
    assert r["wait_for_leg_end"] == O["minute_8"]["timing"]["wait_for_leg_end"]
    assert r["charge_reserved"] == want["charge_reserved"]
    assert r["reserved_kw"] == want.get("reserved_kw", 0)
    assert r["loser"]["survey_minutes_lost"] == want["survey_minutes_lost"]
    assert r["loser"]["open_ended"] == want["open_ended"]
    for k, v in want["g3"].items():
        assert r["loser"][k] == v, k
    if "leg_ends_at_min" in want:
        assert r["loser"]["leg_ends_at_min"] == want["leg_ends_at_min"]


def test_minute_8_conflict_is_two_sets_of_ship_state_conditions():
    r = D3.right_of_way(A, SIGNALS, CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m08"])
    signals = {c["signal"] for c in r["conflicts"] if "signal" in c}
    assert {"speed_kn", "deck_machinery"} <= signals
    assert any("exclusion" in c for c in r["conflicts"])


@pytest.mark.parametrize("file_id,reserve,leg", [("patrol", True, "aborted"), ("disaster_relief", True, "aborted")])
def test_minute_8_is_computable_for_every_priority_file(file_id, reserve, leg):
    r = D3.right_of_way(A, SIGNALS, CARDS, MISSIONS[file_id], SNAP["scenario_b_survey_m08"])
    assert r["proceeds"] == "G4" and r["charge_reserved"] == reserve and r["loser"]["leg"] == leg


def test_no_conflict_before_the_battery_report():
    assert D3.right_of_way(A, SIGNALS, CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m00"]) is None


@pytest.mark.parametrize("snap,file_id,reserved,load", [("scenario_b_survey_m12", "survey", {}, 49.5), ("scenario_b_sar_m12", "sar", {"G4": 35}, 82.5)])
def test_minute_12_holds_with_the_armed_step(snap, file_id, reserved, load):
    r = D4.shed(CARDS, MISSIONS[file_id], SNAP[snap], reserved)
    want = O["minute_12_as_decided"]["by_file"][file_id]
    assert r["verdict"] == "hold" and r["steps"] == []
    assert r["load_kw"] == pytest.approx(want["load_kw"]) == load
    assert r["limit_kw"] == 95 and r["binding"]["class"] == "power"
    # power binds on every guest's draw; the loop carries 1.5 kW less (G1 is air-cooled) against 128.3
    assert (r["total_kw"], r["loop_kw"]) == (load, want["loop_kw"]) and r["power_limit_kw"] == 95 and r["heat_limit_kw"] == pytest.approx(128.3)
    assert (r["total_after_kw"], r["loop_after_kw"], r["free_after_kw"]) == (load, want["loop_kw"], want["spare_kw"])
    first = r["armed"][0]
    arm = want["armed_first"]
    assert (first["guest"], first["from_mode"], first["to_mode"]) == (arm["guest"], arm["from_mode"], arm["to_mode"])
    assert first["cost_per_kw"] == pytest.approx(arm["cost_per_kw"], abs=1e-4)
    assert first["capability_lost_pct"] == arm["capability_lost_pct"]
    # G1 has no throttle: its one step is a shed, the last 5 S step of the ladder, before the 60 S mission-critical guest (DEC-60)
    first_action = [s for s in r["armed"] if s["response"] == "shed_first_action"]
    assert (first_action[-1]["guest"], first_action[-1]["to_mode"], first_action[-1]["frees_kw"], first_action[-1]["capability_lost_pct"]) == ("G1", "off", 1.5, 100.0)
    assert r["armed"][-1]["response"] == "shed_full_sequence" and r["armed"][-1]["guest"] == MISSIONS[file_id]["mission_critical"][0]
    assert r["losses"]["G1"] == {"mode_before": "full", "mode_after": "full", "capability_before": 1.0, "capability_after": 1.0}
    assert r["raw_event_t_s"] == 720 and r["confirmed_t_s"] == 721
    # Every guest now against its envelope draw (R-067): the envelope set is the oracle's draw set B on load-out ii, 106.5 kW.
    env, ii = r["envelope"], next(l for l in O["loadouts"] if l["id"] == "ii")
    assert env["G1"]["cooling"] == "air" and all(e["cooling"] == "chilled_water" for g, e in env.items() if g != "G1")
    assert {g: e["envelope_mode"] for g, e in env.items()} == {g: m for g, m in O["draw_set_modes"]["B"].items() if g in env}
    assert {g: e["envelope_kw"] for g, e in env.items()} == ii["minute_12"]["B"]["draws"]
    assert sum(e["envelope_kw"] for e in env.values()) == ii["one_genset_down_envelope"]["load_kw"] > r["limit_kw"] > r["load_kw"]
    assert {g: (e["mode"], e["kw"]) for g, e in env.items()} == {g: (SNAP[snap]["guests"][g]["mode"]["value"], r["draws"][g]) for g in env}
    assert {g: e["activity"] for g, e in env.items()} == {g: SNAP[snap]["guests"][g]["activity"]["value"] for g in env}


@pytest.mark.parametrize("snap,file_id,guest,to_mode,after,kept", [
    ("scenario_b_survey_m19", "survey", "G4", "charge", 56, 0.7), ("scenario_b_sar_m19", "sar", "G5", "low_power", 44, 0.3)])
def test_minute_19_sheds_one_step_against_the_cooling_limit(snap, file_id, guest, to_mode, after, kept):
    r = D4.shed(CARDS, MISSIONS[file_id], SNAP[snap])
    want = O["minute_19_as_decided"]
    assert r["verdict"] == "shed" and r["load_kw"] == 81 and r["limit_kw"] == 75
    assert r["binding"]["class"] == "heat" and r["binding"]["capacity"] == 80 and r["binding"]["demand"] == 81
    # cooling binds on the loop (G3 1 + G4 35 + G5 45) while the bus, G1's 1.5 kW included, is under its own 95 kW limit
    assert (r["loop_kw"], r["total_kw"], r["heat_limit_kw"], r["power_limit_kw"]) == (81, 82.5, want["heat_limit_kw"], want["power_limit_kw"])
    assert [(s["guest"], s["to_mode"]) for s in r["steps"]] == [(guest, to_mode)]
    assert r["load_after_kw"] == pytest.approx(after) == r["loop_after_kw"] == want["by_file"][file_id]["loop_after_kw"]
    assert r["total_after_kw"] == pytest.approx(want["by_file"][file_id]["total_after_kw"])
    assert r["losses"][guest]["capability_after"] == pytest.approx(kept) and r["losses"]["G1"]["capability_after"] == 1.0
    assert r["trigger"] == "cooling_degraded" and r["trigger_injected"] is True
    assert r["confirmed_t_s"] == 1141 and r["applies_at_tick"] <= r["first_shed_due_t_s"]


def without_g1(snap):
    s = copy.deepcopy(snap)
    del s["guests"]["G1"]
    s["run"]["installed"] = [g for g in s["run"]["installed"] if g != "G1"]
    return s


@pytest.mark.parametrize("snap,file_id,guest,after", [("scenario_b_survey_m19", "survey", "G4", 56), ("scenario_b_sar_m19", "sar", "G5", 44)])
def test_without_g1_the_two_lines_coincide_and_the_decision_is_the_old_sets(snap, file_id, guest, after):
    """Every guest on the loop: the bus and the loop carry the same load, and the DEC-32 set decides as it did."""
    r = D4.shed(CARDS, MISSIONS[file_id], without_g1(SNAP[snap]))
    assert (r["total_kw"], r["loop_kw"], r["load_kw"], r["limit_kw"]) == (81, 81, 81, 75)
    assert [s["guest"] for s in r["steps"]] == [guest] and (r["load_after_kw"], r["total_after_kw"]) == (after, after)
    assert "G1" not in r["losses"] and not any(s["guest"] == "G1" for s in r["armed"])


def test_an_air_cooled_step_is_passed_over_while_only_the_loop_is_over():
    """With G4 and G5 on safety commands only, the ladder is G1 off (5 S) then G3 off (60 S). G1's 1.5 kW is on the bus, not on
    the loop, so switching it off would relieve nothing that is over: the walk passes it over and takes G3's step alone, which
    still leaves the loop 5 kW over, and the record shows that."""
    s = copy.deepcopy(SNAP["scenario_b_survey_m19"])
    m = copy.deepcopy(MISSIONS["survey"])
    m["response"] = {"safety_command": ["G4", "G5"]}     # 200 MS: never on the ladder (DEC-60)
    m["mission_critical"] = ["G3"]
    r = D4.shed(CARDS, m, s)
    assert r["binding"]["class"] == "heat" and [(x["guest"], x["to_mode"]) for x in r["steps"]] == [("G3", "off")]
    assert (r["total_after_kw"], r["loop_after_kw"]) == (81.5, 80) and r["load_after_kw"] == 80 > r["limit_kw"]
    assert r["queued"] == [] and [a["guest"] for a in r["armed"]] == ["G1"], "G1 stays armed for the bus, untouched for the loop"
    assert r["losses"]["G1"]["capability_after"] == 1.0


def test_d4_never_acts_on_a_stale_feed():
    r = D4.shed(CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m10_stale_genset_feed"])
    assert r["steps"] == []
