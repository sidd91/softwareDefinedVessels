"""D3 at minute 8 and D4 at minutes 12 and 19 of Scenario B, decided on the contract's snapshots."""
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


@pytest.mark.parametrize("snap,file_id,reserved,load", [("scenario_b_survey_m12", "survey", {}, 48), ("scenario_b_sar_m12", "sar", {"G4": 35}, 81)])
def test_minute_12_holds_with_the_armed_step(snap, file_id, reserved, load):
    r = D4.shed(CARDS, MISSIONS[file_id], SNAP[snap], reserved)
    want = O["minute_12_as_decided"]["by_file"][file_id]
    assert r["verdict"] == "hold" and r["steps"] == []
    assert r["load_kw"] == pytest.approx(want["load_kw"]) == load
    assert r["limit_kw"] == 95 and r["binding"]["class"] == "power"
    first = r["armed"][0]
    arm = want["armed_first"]
    assert (first["guest"], first["from_mode"], first["to_mode"]) == (arm["guest"], arm["from_mode"], arm["to_mode"])
    assert first["cost_per_kw"] == pytest.approx(arm["cost_per_kw"], abs=1e-4)
    assert first["capability_lost_pct"] == arm["capability_lost_pct"]
    assert r["raw_event_t_s"] == 720 and r["confirmed_t_s"] == 721


@pytest.mark.parametrize("snap,file_id,guest,to_mode,after,kept", [
    ("scenario_b_survey_m19", "survey", "G4", "charge", 56, 0.7), ("scenario_b_sar_m19", "sar", "G5", "low_power", 44, 0.3)])
def test_minute_19_sheds_one_step_against_the_cooling_limit(snap, file_id, guest, to_mode, after, kept):
    r = D4.shed(CARDS, MISSIONS[file_id], SNAP[snap])
    assert r["verdict"] == "shed" and r["load_kw"] == 81 and r["limit_kw"] == 75
    assert r["binding"]["class"] == "heat" and r["binding"]["capacity"] == 80
    assert [(s["guest"], s["to_mode"]) for s in r["steps"]] == [(guest, to_mode)]
    assert r["load_after_kw"] == pytest.approx(after)
    assert r["losses"][guest]["capability_after"] == pytest.approx(kept)
    assert r["trigger"] == "cooling_degraded" and r["trigger_injected"] is True
    assert r["confirmed_t_s"] == 1141 and r["applies_at_tick"] <= r["first_shed_due_t_s"]


def test_d4_never_acts_on_a_stale_feed():
    r = D4.shed(CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m10_stale_genset_feed"])
    assert r["steps"] == []
