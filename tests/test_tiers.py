"""Graceful degradation by criticality tier (DEC-59) and profiles changed at sea (DEC-58)."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import ledger as Lg  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.loop import Loop, canonical, load_simulator, replay, scripted_inputs  # noqa: E402

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SCHEMA = Ld._schema(Ld.ROOT, "config/missions/schema.json")
M19 = json.loads((Ld.ROOT / "tests/fixtures/snapshots/scenario_b_survey_m19.json").read_text())


def survey(**tiers):
    m = copy.deepcopy(MISSIONS["survey"])
    m["id"] = "survey_edited"
    if tiers:
        m["tiers"] = tiers
    return m


def test_the_tier_of_every_guest():
    m = survey(vessel_critical=["G6"], discretionary=["G5"])
    assert {g: Lg.tier_of(CARDS, g, m) for g in sorted(CARDS)} == {
        "G1": "mission_support", "G2": "mission_support", "G3": "mission_critical", "G4": "mission_support",
        "G5": "discretionary", "G6": "vessel_critical"}


def test_a_discretionary_guest_degrades_first():
    """Survey at minute 19 normally slows G4's charge (cheapest per kW); with G5 discretionary it goes first."""
    plain = D4.shed(CARDS, MISSIONS["survey"], M19)
    tiered = D4.shed(CARDS, survey(discretionary=["G5"]), M19)
    assert [s["guest"] for s in plain["steps"]] == ["G4"]
    assert [s["guest"] for s in tiered["steps"]] == ["G5"] and tiered["steps"][0]["tier"] == "discretionary"


def test_a_vessel_critical_guest_is_never_on_the_ladder():
    steps = Lg.ladder(CARDS, {"G3": "standby", "G4": "fast_charge", "G5": "full"}, survey(vessel_critical=["G4"]))
    assert steps and "G4" not in {s.guest for s in steps}


def test_throttles_still_come_before_sheds_across_tiers():
    steps = Lg.ladder(CARDS, {"G3": "standby", "G4": "fast_charge", "G5": "full"}, survey(discretionary=["G5"]))
    sheds = [i for i, s in enumerate(steps) if s.shed]
    throttles = [i for i, s in enumerate(steps) if not s.shed]
    assert not sheds or max(throttles) < min(sheds)


@pytest.mark.parametrize("tiers,needle", [({"discretionary": ["G9"]}, "tiers.discretionary[0]: no loaded card G9"),
                                          ({"vessel_critical": ["G3"]}, "G3 is already mission_critical"),
                                          ({"discretionary": ["G5"], "vessel_critical": ["G5"]}, "G5 is already discretionary"),
                                          ({"critical": ["G5"]}, "critical")])
def test_the_loader_refuses_a_bad_tier(tiers, needle):
    m = copy.deepcopy(MISSIONS["survey"])
    m["tiers"] = tiers
    problems = Ld.check_mission(m, CARDS, VOCAB, SCHEMA)
    assert problems and any(needle in p for p in problems), problems


def applied(tick, profile):
    return {"t_s": tick, "type": "profile_applied", "injected": False, "payload": {"profile": profile}}


def test_an_edited_profile_applied_at_sea_changes_the_shed_and_replays(tmp_path):
    inputs = scripted_inputs()
    inputs[1100] = [applied(1100, survey(discretionary=["G5"]))]
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=inputs, log_dir=tmp_path)
    outs = list(loop.ticks(until=1200))
    loop.close()
    shed = next(r for o in outs for r in o.records if r["verdict"] == "shed")
    assert shed["tick"] == 1141 and shed["mission"] == "survey_edited" and shed["steps"][0]["guest"] == "G5"
    snaps, recs = replay(tmp_path, "survey")
    assert snaps == (tmp_path / "snapshots.jsonl").read_text().splitlines()
    assert recs == (tmp_path / "decisions.jsonl").read_text().splitlines()


def test_a_bad_profile_at_sea_is_refused_and_the_previous_kept():
    bad = survey(discretionary=["G3"])
    inputs = scripted_inputs()
    inputs[1100] = [applied(1100, bad)]
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=inputs)
    outs = list(loop.ticks(until=1200))
    assert loop.core.rejected and "G3 is already mission_critical" in loop.core.rejected[0]["problems"][0]
    shed = next(r for o in outs for r in o.records if r["verdict"] == "shed")
    assert shed["mission"] == "survey" and shed["steps"][0]["guest"] == "G4"


def test_a_profile_can_forbid_recovery_at_a_crew_level():
    m = survey()
    m["confirm"] = {"r3": {14: "forbidden"}}
    inputs = {0: [applied(0, m)]}
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=inputs)
    outs = list(loop.ticks(until=500))
    d5 = next(r for o in outs for r in o.records if r["kind"] == "D5")
    assert d5["verdict"] == "forbidden" and "forbids it at 14 aboard" in d5["sentence"]
    assert not any(c["kind"] == "bridge_request" for o in outs for c in o.commands)
