"""The environment along a mission plan (src/sdv/environment.py) from the cached Open-Meteo data in
config/environment/, the plan in config/plans/, and its use in admission and the simulator (R-080, R-081)."""
import json
from pathlib import Path

import pytest

from sdv import admission, cli, placement as P
from sdv.data import load_assumptions, load_cards, load_inputs, load_missions
from sdv.environment import RouteEnvironment, sea_state
from sdv.governor import Governor
from sdv.ledger import cooling_capacity_kw
from sdv.plant.sim import Simulator

ROOT = Path(__file__).resolve().parents[1]
A = load_assumptions()
CARDS = load_cards()
MISSIONS = load_missions()
PLAN = "sicily_cable_survey"


@pytest.fixture(scope="module")
def route():
    return RouteEnvironment.load(A, PLAN)


def test_cache_is_attributed_complete_and_matches_the_plan(route):
    c = route.cache
    assert c["plan"] == PLAN and c["licence"] == "CC BY 4.0" and "Open-Meteo" in c["source"] and c["fetched_at_utc"]
    assert [w["id"] for w in c["waypoints"]] == [w["id"] for w in route.plan["waypoints"]]
    for w in c["waypoints"]:
        h = w["hourly"]
        n = len(h["time"])
        assert n >= route.plan["days"] * 24 and all(len(h[k]) == n for k in ("seawater_c", "wave_m", "wind_kn", "gust_kn"))
        assert all(v is not None for v in h["seawater_c"]) and all(v is not None for v in h["gust_kn"])
    assert route.offset_h == 6 and route.hours == len(c["waypoints"][0]["hourly"]["time"]) - 6
    assert route.at(0)["time_utc"] == route.plan["depart_utc"]


def test_plan_provenance_names_every_assumed_choice(route):
    prov = route.plan["provenance"]
    assert all(p.get("why") for p in prov.values() if p["source"] == "assumed")
    assert prov["days"]["source"].startswith("brief")


def test_sea_state_follows_the_douglas_scale():
    assert sea_state(A, 0.05) == 0 and sea_state(A, 0.5) == 1 and sea_state(A, 1.3) == 3 and sea_state(A, 2.5) == 3
    assert sea_state(A, 2.6) == 4 and sea_state(A, 15.0) == 8 and sea_state(A, None) is None


def test_conditions_carry_source_age_and_confidence_and_interpolate_along_the_route(route):
    c0, c1 = route.at(0), route.at(0.5)
    assert c0["source"] == "open-meteo (cached)" and c0["age_s"] == 0 and c0["confidence"] == 1.0 and c0["waypoint"] == "off_mazara"
    assert c1["age_s"] == 1800 and c1["seawater_c"] == pytest.approx(c0["seawater_c"], abs=0.05)  # same data hour, 15 min further along
    mid = route.at(60)  # half way between waypoints 1 and 2: the mean of the two series
    a = route.cache["waypoints"][0]["hourly"]["seawater_c"][60 + route.offset_h]
    b = route.cache["waypoints"][1]["hourly"]["seawater_c"][60 + route.offset_h]
    assert mid["seawater_c"] == pytest.approx((a + b) / 2, abs=0.01)


def test_outside_the_data_the_envelope_worst_case_applies(route):
    c = route.at(route.hours + 5)
    assert c["confidence"] == 0.0 and c["tightened"] and c["seawater_c"] == 30 and c["sea_state"] == 5 and c["gust_kn"] == 30
    before = route.at(-1)
    assert before["confidence"] == 0.0 and before["tightened"]


def test_summary_gives_the_cooling_range_from_the_real_seawater(route):
    s = route.summary()
    lo, hi = s["seawater_c"]
    assert 20 < lo < hi < 30 and s["cooling_kw_min"] == pytest.approx(cooling_capacity_kw(A, hi, False), abs=0.1)
    assert s["cooling_kw_max"] == pytest.approx(cooling_capacity_kw(A, lo, False), abs=0.1)
    assert s["sea_state_max"] <= 5 and s["gust_kn_max"] > 25  # the October data has gusts above G4's landing limit
    assert s["envelope_exceeded"]["wind"] is True and s["envelope_exceeded"]["seawater"] is False


def test_closed_windows_follow_the_card_limits_on_gusts(route):
    windows = route.activity_windows(CARDS["G4"])
    (act,) = windows
    assert act["activity"] == "launch_recovery" and act["wind_kn_max"] == 25 and act["closed_h"] > 0
    for start, end in act["windows"]:
        assert all(route.at(h)["gust_kn"] > 25 or route.at(h)["sea_state"] > 4 for h in range(start, end))
        assert start == 0 or not (route.at(start - 1)["gust_kn"] > 25 or route.at(start - 1)["sea_state"] > 4)
    assert route.closed_hours(wind_kn_max=1000, sea_state_max=9) == []
    assert route.activity_windows(CARDS["G3"])[0]["closed_h"] == 0  # sea state never above 4 in the data


def test_admission_adds_the_route_lines_without_changing_the_verdict(route):
    installed = P.default_installed(A, CARDS, ["G2", "G3", "G4"])
    plain = admission.decide(A, CARDS, MISSIONS["survey"], installed, "G5")
    with_route = admission.decide(A, CARDS, MISSIONS["survey"], installed, "G5", route=route)
    assert with_route.verdict == plain.verdict and with_route.binding.as_dict() == plain.binding.as_dict()
    r = with_route.extras["route"]
    assert r["chilled_kw"] == 125 and r["loop_min_kw"] == route.summary()["cooling_kw_min"]
    assert r["free_kw"] == pytest.approx(r["loop_min_kw"] - 125, abs=1e-6) and r["holds_degraded"] is False
    assert with_route.sentence.startswith(plain.sentence) and "On the Strait of Sicily cable corridor survey" in with_route.sentence
    assert "a pump loss there would leave" in with_route.sentence and r["activities"] == []  # the comms node has no weather gate
    drone = admission.decide(A, CARDS, MISSIONS["survey"], P.default_installed(A, CARDS, ["G1", "G2", "G3"]), "G4", route=route)
    assert "Launch recovery closed" in drone.sentence and drone.extras["route"]["activities"][0]["closed_h"] > 0


def test_simulator_follows_the_plan_when_asked_and_the_storyline_still_holds():
    inputs = load_inputs("scenario-b")
    route = RouteEnvironment.load(A, inputs.scenario["plan"])
    gov = Governor(inputs, "survey")
    sim = Simulator(inputs, seed=1, mission="survey", on_tick=gov.on_tick, route=route)
    sim.run(20)
    env0 = sim.snapshots[0]["env"]
    assert env0["source"] == "open-meteo (cached)" and env0["confidence"] == 1.0 and env0["seawater_c"] != 24
    assert sim.snapshots[0]["gauges"]["heat"]["capacity"] == pytest.approx(cooling_capacity_kw(A, env0["seawater_c"], False), abs=0.01)
    fault = next(d for d in gov.decisions if d.kind == "D4" and d.extras.get("trigger") == "cooling_degraded")
    assert fault.verdict == "throttled" and fault.extras["ladder"]["steps"][0]["guest"] == "G4"
    plain = Simulator(load_inputs("scenario-b"), seed=1, mission="survey")
    plain.run(1)
    assert plain.snapshots[0]["env"]["seawater_c"] == 24 and "source" not in plain.snapshots[0]["env"]


def test_cli_route_and_admit_route(capsys):
    assert cli.main(["--no-color", "route", PLAN, "--card", "G4"]) == 0
    out = capsys.readouterr().out
    assert "Open-Meteo" in out and "G4 launch_recovery: closed" in out and "brief judges at 30 °C: 120 kW" in out
    assert cli.main(["--no-color", "admit", "G4", "--installed", "G1,G2,G3", "--route", PLAN]) == 0
    out = capsys.readouterr().out
    assert "on the route (Strait of Sicily cable corridor survey" in out and "launch_recovery: closed" in out
