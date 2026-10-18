"""The standalone deployment map: seeded sampling inside the operations area, weather read as Siddharth's
RouteEnvironment reads it, his Douglas scale, the weather windows, and D1 run by the real engine at the route's
seawater temperature; the page loads nothing from the network."""
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "deploy_map"))
import deploy as M  # noqa: E402

from sdv import admission as Ad  # noqa: E402
from sdv import loader as Ld  # noqa: E402

PLAN, CACHE, COAST = M.load("sicily_cable_survey")
ROUTE = M.Route(PLAN, CACHE)
D = M.build("sicily_cable_survey", 0, 200)


def test_the_same_seed_draws_the_same_map_and_another_seed_does_not():
    assert M.build("sicily_cable_survey", 0, 200)["samples"] == D["samples"]
    assert M.build("sicily_cable_survey", 1, 200)["samples"] != D["samples"]


@pytest.mark.parametrize("wave,state", [(0.05, 0), (0.1, 0), (0.3, 1), (1.0, 2), (2.0, 3), (2.5, 3), (2.54, 4), (5.0, 5), (20.0, 8)])
def test_the_douglas_scale_is_siddharths(wave, state):
    assert M.sea_state(wave) == state


def test_points_stay_on_the_route_or_inside_the_area():
    width = D["sampling"]["corridor_km"]
    for s in D["samples"]:
        d = ROUTE.distance_km(s["lat"], s["lon"])
        assert d <= width + 0.05 if s["kind"] == "area" else d < 0.05, s
    assert {s["kind"] for s in D["samples"]} == {"route", "area"}


def test_weather_at_a_waypoint_is_that_waypoints_own_series():
    for w in PLAN["waypoints"][:-1]:
        lat, lon, i, j, f = ROUTE.at_hour(w["eta_h"])
        got = ROUTE.weather(w["eta_h"], i, j, f)
        k = int(w["eta_h"]) + ROUTE.offset_h
        own = next(x for x in CACHE["waypoints"] if x["id"] == w["id"])["hourly"]
        assert (lat, lon) == (w["lat"], w["lon"])
        assert all(math.isclose(got[key], own[key][k], abs_tol=0.01) for key in M.VARS)


def test_a_window_is_the_share_of_sampled_hours_inside_its_limits():
    g4 = next(w for w in D["windows"] if w["guest"] == "G4")
    assert (g4["wind_kn_max"], g4["sea_state_max"]) == (25, 4)
    by_hand = sum(1 for s in D["samples"] if s["gust_kn"] <= 25 and s["sea_state"] <= 4) / len(D["samples"])
    assert g4["open_pct"] == round(100 * by_hand, 1)
    assert {w["guest"] for w in D["windows"]} == {"G2", "G3", "G4"}


def test_d1_at_30_c_is_the_engines_own_verdict_and_cooler_water_leaves_more_cooling():
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    cards = Ld.load_cards(vocab=vocab)
    missions = Ld.load_missions(cards, vocab)
    for p in D["profiles"]:
        r = Ad.admit(A, cards, ["G3", "G4"], "G5", missions[p["id"]])
        assert (p["envelope"]["verdict"], p["envelope"]["cooling_kw"]) == (r.verdict, round(r.lines["heat"].capacity, 1))
        assert p["route_max"]["cooling_kw"] >= p["envelope"]["cooling_kw"]


def test_the_route_warns_that_one_pump_down_cannot_carry_the_load_out():
    c = D["cooling"]
    assert c["load_out_heat_kw"] == 105 and c["degraded_kw_at_max"] < c["load_out_heat_kw"] < c["normal_kw_at_max"]


def test_the_page_is_self_contained_and_credits_its_data():
    page = M.page(D)
    assert not re.search(r"""(src|href)=["']https?:|@import|url\(https?:""", page)
    assert "Open-Meteo" in page and "Natural Earth" in page and "<svg" in page
