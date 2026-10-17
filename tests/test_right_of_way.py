"""D3 (src/sdv/right_of_way.py) against the oracle's minute-8 block: the drone's hard limit first,
the two priority files giving two outcomes for the loser, and the cost stated in minutes."""
from pathlib import Path

import pytest
import yaml

from sdv import right_of_way as row
from sdv.data import load_assumptions, load_cards, load_missions

ROOT = Path(__file__).resolve().parents[1]
A = load_assumptions()
CARDS = load_cards()
MISSIONS = load_missions()
O = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())["scenario_b"]["minute_8"]
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())
SHIP = dict(TL["initial"]["ship_state"], crew=14)


def parties(battery=18.0):
    g3 = TL["initial"]["activities"]["G3"]
    p_g4 = row.Party("G4", "launch_recovery", {"battery_pct": battery, "airborne": True, "mode": "standby"})
    p_g3 = row.Party("G3", "surveying", {"mode": "standby", "started_min": g3["started_min"], "ends_min": g3["ends_min"]})
    return p_g4, p_g3


def test_card_hard_limits_parse_and_fire_on_the_guest_state():
    limits = row.hard_limits(CARDS["G4"])
    battery = next(h for h in limits if h.signal == "battery_pct")
    assert (battery.op, battery.threshold, battery.within_min) == ("<", 20.0, 12.0)
    assert battery.holds({"battery_pct": 18}) and not battery.holds({"battery_pct": 20}) and not battery.holds({})
    silent = next(h for h in limits if h.signal == "emission")
    assert silent.op == "==" and silent.holds({"emission": "silent"}) and silent.within_min is None
    airborne = next(h for h in limits if h.signal == "airborne")
    assert airborne.op is None and airborne.holds({"airborne": True}) and not airborne.holds({"airborne": False})


@pytest.mark.parametrize("mission", ["survey", "sar"])
def test_minute_8_the_hard_limit_decides_for_g4_under_both_files(mission):
    exp = O["by_file"][mission]
    t = O["timing"]
    p_g4, p_g3 = parties(t["battery_pct_at_report"])
    d = row.decide(A, CARDS, MISSIONS[mission], SHIP, p_g3, p_g4, now_min=t["decision_at_min"])
    assert d.kind == "D3" and d.verdict == f"{exp['proceeds']} proceeds" and d.extras["how"] == "hard_limit"
    assert d.extras["hard_limit"] == exp["hard_limit"]
    timing = d.extras["timing"]
    assert timing["crossed_at_min"] == pytest.approx(t["crossed_threshold_at_min"], abs=0.01)
    assert timing["deadline_min"] == pytest.approx(t["deadline_min"], abs=0.01)
    assert timing["remaining_min"] == pytest.approx(t["remaining_min"], abs=0.01)
    assert timing["if_counted_from_report_min"] == t["if_counted_from_report"]["deadline_min"]
    assert (timing["confirm_min"], timing["clear_deck_min"], timing["approach_min"]) == (t["confirm_min"], t["clear_deck_min"], t["approach_min"])
    # Binding line: landing needs 10 of the 10.2 minutes left; the margin is 12 s.
    assert d.binding.cls == "time" and d.binding.capacity == pytest.approx(t["remaining_min"], abs=0.01)
    assert d.binding.demand == t["confirm_min"] + t["clear_deck_min"] + t["approach_min"]
    assert d.binding.free * 60 == pytest.approx(t["margin_s"], abs=1)
    assert d.extras["alternative"]["feasible"] is False and "minute 40 is infeasible" in d.sentence
    assert d.extras["reserved_kw"] == (exp["reserved_kw"] if exp["charge_reserved"] else 0)
    lo, hi = exp["survey_minutes_lost"]
    assert f"{lo} to {hi} seabed inspection minutes" in d.cost_to_loser
    assert d.sentence.startswith("G4 proceeds: battery pct 18 < 20, must land within 12 min (by minute 18.2, 10.2 min left")


def test_survey_pauses_g3_and_sar_suspends_it():
    p_g4, p_g3 = parties()
    survey = row.decide(A, CARDS, MISSIONS["survey"], SHIP, p_g4, p_g3, now_min=8)
    sar = row.decide(A, CARDS, MISSIONS["sar"], SHIP, p_g4, p_g3, now_min=8)
    assert survey.extras["loser_outcome"] == "paused" and sar.extras["loser_outcome"] == "suspended"
    assert "paused, resumes after the 15-min window at minute 23" in survey.sentence
    assert "leg ends about minute 65 to 67" in survey.sentence
    assert "open-ended" in sar.sentence and "35 kW reserved" in sar.sentence
    assert {"set_mode": ["G3", "standby"], "why": "G3 holds on 1 kW"} in survey.extras["actions"]
    assert {"reserve_kw": ["G4", 35]} in sar.extras["actions"]
    assert all({"request_state": ["course", "free"], "why": "G4 launch_recovery"} in d.extras["actions"] for d in (survey, sar))
    assert survey.sentence != sar.sentence and survey.verdict == sar.verdict


def test_order_of_the_parties_does_not_matter():
    p_g4, p_g3 = parties()
    a = row.decide(A, CARDS, MISSIONS["survey"], SHIP, p_g4, p_g3, now_min=8)
    b = row.decide(A, CARDS, MISSIONS["survey"], SHIP, p_g3, p_g4, now_min=8)
    assert a.sentence == b.sentence and a.binding.as_dict() == b.binding.as_dict()


def test_without_a_hard_limit_the_priority_file_decides():
    p_g4, p_g3 = parties(battery=60.0)  # above 20 %: no hard limit
    survey = row.decide(A, CARDS, MISSIONS["survey"], SHIP, p_g4, p_g3, now_min=8)
    sar = row.decide(A, CARDS, MISSIONS["sar"], SHIP, p_g4, p_g3, now_min=8)
    assert survey.extras["how"] == "mission_value" and survey.verdict == "G3 proceeds"
    assert sar.verdict == "G4 proceeds" and sar.binding.cls == "mission_value"
    assert "mission value" in survey.sentence and survey.extras["weights"] == {"G3": 1.0, "G4": 0.2}


def test_at_zero_crew_the_deck_cannot_be_cleared_and_the_sentence_says_so():
    p_g4, p_g3 = parties()
    d = row.decide(A, CARDS, MISSIONS["sar"], dict(SHIP, crew=0), p_g4, p_g3, now_min=8)
    assert d.extras["timing"]["total_min"] is None and "nobody aboard to clear the deck" in d.sentence


def test_a_clear_deck_is_not_requested_and_an_occupied_one_is():
    p_g4, p_g3 = parties()
    clear = row.decide(A, CARDS, MISSIONS["sar"], SHIP, p_g4, p_g3, now_min=8)
    occupied = row.decide(A, CARDS, MISSIONS["sar"], dict(SHIP, deck="occupied"), p_g4, p_g3, now_min=8)
    assert not any(x.get("request_state") == ["deck", "clear"] for x in clear.extras["actions"])
    assert any(x.get("request_state") == ["deck", "clear"] for x in occupied.extras["actions"])
