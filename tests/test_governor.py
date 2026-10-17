"""The closed loop: governor + plant over Scenario B under both priority files (DEC-40 storyline),
replay identity with decisions included, and the live priority swap."""
import copy

import pytest

from sdv.data import load_inputs
from sdv.governor import Governor
from sdv.plant.sim import Simulator, _strip_timing


def run(mission, until_min=21, scenario=None, seed=1):
    inputs = scenario or load_inputs("scenario-b")
    gov = Governor(inputs, mission)
    sim = Simulator(inputs, seed=seed, mission=mission, on_tick=gov.on_tick)
    h = sim.run(until_min)
    return gov, sim, h


def by_kind(gov, kind, verdict=None):
    return [d for d in gov.decisions if d.kind == kind and (verdict is None or d.verdict == verdict)]


@pytest.mark.parametrize("mission,outcome,m12_load,m19_guest,m19_to,m19_after", [
    ("survey", "paused", 48, "G4", "charge", 56), ("sar", "suspended", 81, "G5", "low_power", 44)])
def test_scenario_b_storyline_under_each_file(mission, outcome, m12_load, m19_guest, m19_to, m19_after):
    gov, sim, _ = run(mission)
    (d3,) = by_kind(gov, "D3")
    assert d3.t_s == 8 * 60 and d3.verdict == "G4 proceeds" and d3.extras["loser_outcome"] == outcome
    assert "battery pct 18 < 20, must land within 12 min (by minute 18.2" in d3.sentence
    trip = next(d for d in by_kind(gov, "D4") if d.extras.get("trigger") == "genset_trip")
    assert trip.t_s == 12 * 60 and trip.verdict == "holds" and trip.binding.demand == m12_load and trip.binding.capacity == 95
    assert trip.extras["ladder"]["steps"] == [] and trip.extras["ladder"]["armed"]
    fault = next(d for d in by_kind(gov, "D4") if d.extras.get("trigger") == "cooling_degraded")
    assert fault.t_s == 19 * 60 and fault.verdict == "throttled" and fault.binding.cls == "heat" and fault.binding.capacity == 75
    (step,) = fault.extras["ladder"]["steps"]
    assert (step["guest"], step["to_mode"]) == (m19_guest, m19_to) and fault.extras["ladder"]["load_after_kw"] == m19_after
    after = sim.snapshots[19 * 60 + 1]
    assert after["gauges"]["power"]["committed"] == m19_after and after["guests"][m19_guest]["mode"] == m19_to
    assert all(d.within_ceiling for d in gov.decisions)
    assert all(d.latency_ms < 100 for d in gov.decisions if d.kind in ("D3", "D4"))


def test_the_two_files_give_two_different_decisions_on_the_same_events():
    s, _, _ = run("survey")
    r, _, _ = run("sar")
    d3s, d3r = by_kind(s, "D3")[0], by_kind(r, "D3")[0]
    assert d3s.verdict == d3r.verdict and d3s.sentence != d3r.sentence
    assert d3s.extras["reserved_kw"] == 0 and d3r.extras["reserved_kw"] == 35
    fs = next(d for d in by_kind(s, "D4") if d.extras.get("trigger") == "cooling_degraded")
    fr = next(d for d in by_kind(r, "D4") if d.extras.get("trigger") == "cooling_degraded")
    assert fs.extras["ladder"]["steps"][0]["guest"] != fr.extras["ladder"]["steps"][0]["guest"]


def test_d3_acts_on_the_report_not_on_the_plant_battery_and_commands_the_plant():
    gov, sim, _ = run("survey", until_min=9)
    (d3,) = by_kind(gov, "D3")
    assert d3.t_s == 480  # the report at minute 8, although the plant's battery crossed 20 % earlier
    assert any(r["source"] == "governor:D3" and r["var"] == "course" and r["value"] == "free" for r in sim.fsm.log)
    assert sim.snapshots[481]["ship"]["course"] == "free"


def test_decisions_are_in_the_snapshots_and_replay_is_identical_without_timing():
    g1, s1, h1 = run("sar")
    g2, s2, h2 = run("sar")
    assert h1 == h2
    recs1 = [d for s in s1.snapshots for d in s.get("decisions", [])]
    recs2 = [d for s in s2.snapshots for d in s.get("decisions", [])]
    assert len(recs1) == len(g1.decisions) >= 5
    assert _strip_timing(recs1) == _strip_timing(recs2)
    assert all("latency_ms" in r for r in recs1)
    assert all("latency_ms" not in str(_strip_timing(r)) for r in recs1)
    armed = s1.snapshots[12 * 60]["governor"]["armed"]
    assert armed["load_kw"] == 81 and armed["ceiling_kw"] == 95 and armed["next"]


def test_armed_ladder_is_recorded_only_when_the_plan_changes():
    gov, sim, _ = run("survey")
    armed = by_kind(gov, "D4", "armed")
    assert 2 <= len(armed) <= 6
    assert all(d.extras["trigger"] == "precompute" for d in armed)
    assert all("armed" in s["governor"] for s in sim.snapshots)


def test_priority_swap_event_changes_the_later_decisions_and_a_bad_file_is_refused():
    inputs = load_inputs("scenario-b")
    sc = copy.deepcopy(inputs.scenario)
    sc["events"].append({"t_min": 10, "type": "priority_swap", "mission": "sar"})
    sc["events"].append({"t_min": 11, "type": "priority_swap", "mission": {"id": "hostile", "name": "x", "weights": {"sar_air": 2}, "mission_critical": ["G9"]}})
    sc["events"].sort(key=lambda e: e["t_min"])
    inputs = type(inputs)(inputs.assumptions, inputs.cards, inputs.missions, sc)
    gov, sim, _ = run("survey", scenario=inputs)
    log = [r for s in sim.snapshots for r in s.get("governor_log", [])]
    assert log[0]["result"] == "swapped" and log[0]["from"] == "survey" and log[0]["to"] == "sar"
    assert log[1]["result"] == "refused" and log[1]["kept"] == "sar" and log[1]["field"].startswith("weights")
    (d3,) = by_kind(gov, "D3")
    assert d3.mission == "survey" and d3.extras["loser_outcome"] == "paused"  # decided before the swap
    fault = next(d for d in by_kind(gov, "D4") if d.extras.get("trigger") == "cooling_degraded")
    assert fault.mission == "sar" and fault.extras["ladder"]["steps"][0]["guest"] == "G5"
    assert sim.snapshots[-1]["governor"]["mission"] == "sar" and sim.mission == "sar"
