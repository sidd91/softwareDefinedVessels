"""The standalone deployment map: seeded sampling inside the operations area, weather read as Siddharth's
RouteEnvironment reads it, the Douglas scale, ranges taken from the data (every planned hour along the route, every
hour at each distinct grid point), the weather windows, and D1 run by the real engine at the route's seawater
temperature; the page loads nothing from the network and credits its data."""
import html
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "deploy_map"))
import deploy as M  # noqa: E402

from sdv import admission as Ad  # noqa: E402
from sdv import ledger as Lg  # noqa: E402
from sdv import loader as Ld  # noqa: E402

PLAN, CACHE, COAST = M.load("sicily_cable_survey")
ROUTE = M.Route(PLAN, CACHE)
D = M.build("sicily_cable_survey", 0, 200)
PAGE = M.page(D)


def _engine():
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    cards = Ld.load_cards(vocab=vocab)
    return A, cards, Ld.load_missions(cards, vocab)


def _screen_text(page: str) -> str:
    body = re.sub(r"<style>.*?</style>", "", page, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", body))


# ---------------------------------------------------------------------------------------------- the seed
def test_the_same_seed_draws_the_same_map_and_another_seed_does_not():
    again = M.build("sicily_cable_survey", 0, 200)
    assert again == D and M.page(again) == PAGE
    other = M.build("sicily_cable_survey", 1, 200)
    assert other["samples"] != D["samples"]
    assert len(D["samples"]) == 200 and sum(s["kind"] == "area" for s in D["samples"]) == 100


def test_the_ranges_and_the_judgements_come_from_the_data_not_the_seed():
    for seed, points in ((1, 200), (7, 40)):
        other = M.build("sicily_cable_survey", seed, points)
        assert (other["ranges"], other["cooling"], other["profiles"][0]["route_max"]) == \
               (D["ranges"], D["cooling"], D["profiles"][0]["route_max"])


# ---------------------------------------------------------------------------------------------- the Douglas scale
@pytest.mark.parametrize("wave,state", [(0.0, 0), (0.05, 1), (0.1, 1), (0.3, 2), (1.0, 3), (2.0, 4), (2.5, 4),
                                        (2.54, 5), (5.0, 6), (20.0, 9)])
def test_the_douglas_scale_reads_each_wave_in_its_own_state(wave, state):
    assert M.sea_state(wave) == state


def test_the_douglas_tops_are_the_wmo_scale_and_unknown_stays_unknown():
    assert M.CFG["sea_state_wave_m"] == [0.0, 0.1, 0.5, 1.25, 2.5, 4.0, 6.0, 9.0, 14.0]
    assert M.sea_state(None) is None
    assert "fbe59a5" in (ROOT / "tools" / "deploy_map" / "config.yaml").read_text()   # the note for Siddharth's port


# ---------------------------------------------------------------------------------------------- the samples
def test_points_stay_on_the_route_or_inside_the_area_within_the_voyage():
    width = D["sampling"]["corridor_km"]
    for s in D["samples"]:
        d = ROUTE.distance_km(s["lat"], s["lon"])
        assert d <= width + 0.05 if s["kind"] == "area" else d < 0.05, s
        assert 0 <= s["t_h"] <= ROUTE.end_h, s
    assert {s["kind"] for s in D["samples"]} == {"route", "area"}


def test_the_area_is_drawn_over_each_stretch_of_sea_once():
    assert ROUTE.unique_legs == [(0, 1), (1, 2)]             # the return leg runs back over leg 2
    assert D["sampling"]["area_legs"] == [["off_mazara", "corridor_mid"], ["corridor_mid", "off_kelibia"]]
    assert D["sampling"]["hours"] == [0, 336]
    first = ROUTE.leg_km[0]
    assert ROUTE.at_km(first + 1.0, ROUTE.unique_legs)[2:4] == (1, 2)
    lat, lon, i, j, f = ROUTE.at_km(first + ROUTE.leg_km[1], ROUTE.unique_legs)
    assert (lat, lon, f) == (PLAN["waypoints"][2]["lat"], PLAN["waypoints"][2]["lon"], 1.0)


def test_weather_at_a_waypoint_is_that_waypoints_own_series():
    for w in PLAN["waypoints"][:-1]:
        lat, lon, i, j, f = ROUTE.at_hour(w["eta_h"])
        got = ROUTE.weather(w["eta_h"], i, j, f)
        k = int(w["eta_h"]) + ROUTE.offset_h
        own = next(x for x in CACHE["waypoints"] if x["id"] == w["id"])["hourly"]
        assert (lat, lon) == (w["lat"], w["lon"])
        assert all(math.isclose(got[key], own[key][k], abs_tol=0.01) for key in M.VARS)


def test_the_sea_state_is_read_from_the_blended_wave_before_it_is_rounded():
    # Hour 293, between off_kelibia (1.02 m) and corridor_mid_return (1.44 m): the blend is 1.2519 m, over the 1.25 top.
    lat, lon, i, j, f = ROUTE.at_hour(293)
    k = 293 + ROUTE.offset_h
    a, b = (ROUTE.series[ROUTE.wps[n]["id"]]["wave_m"][k] for n in (i, j))
    assert round((1 - f) * a + f * b, 4) == 1.2519
    got = ROUTE.weather(293, i, j, f)
    assert (got["wave_m"], got["sea_state"]) == (1.25, 4)          # shown at 2 decimals, read as SS 4 not SS 3
    hist = {}
    for h in M.route_hours(ROUTE):
        hist[h["sea_state"]] = hist.get(h["sea_state"], 0) + 1
    assert hist == {2: 108, 3: 181, 4: 48}


# ---------------------------------------------------------------------------------------------- the ranges
def _route_seawater_by_hand() -> list[float]:
    """Every planned hour, departure to the last waypoint: position by hour, seawater blended between the two waypoints."""
    wps = PLAN["waypoints"]
    series = {w["id"]: w["hourly"]["seawater_c"] for w in CACHE["waypoints"]}
    off = int((datetime.fromisoformat(PLAN["depart_utc"]) - datetime.fromisoformat(CACHE["waypoints"][0]["hourly"]["time"][0])).total_seconds() // 3600)
    out = []
    for t in range(wps[-1]["eta_h"] + 1):
        a, b = next((a, b) for a, b in zip(wps, wps[1:]) if a["eta_h"] <= t <= b["eta_h"])
        f = (t - a["eta_h"]) / (b["eta_h"] - a["eta_h"])
        out.append(round((1 - f) * series[a["id"]][t + off] + f * series[b["id"]][t + off], 2))
    return out


def test_route_ranges_cover_every_planned_hour_along_the_route():
    by_hand = _route_seawater_by_hand()
    route = D["ranges"]["route"]
    assert route["hours"] == len(by_hand) == 337
    assert route["seawater_c"]["max"] == max(by_hand) == 25.98
    assert route["seawater_c"]["p90"] == M.pct(by_hand, 90)


def test_area_ranges_cover_every_hour_at_the_three_distinct_grid_points():
    r = D["ranges"]
    assert (r["grid_points"], r["waypoints"]) == (3, 4)          # corridor_mid and corridor_mid_return share one cell
    assert r["area"]["hours"] == 3 * len(CACHE["waypoints"][0]["hourly"]["time"])
    every = [x for w in CACHE["waypoints"] for x in w["hourly"]["seawater_c"]]
    assert r["area"]["seawater_c"]["max"] == max(every) == 27.2


def test_the_route_and_every_sample_lie_inside_the_areas_extremes():
    route, area = D["ranges"]["route"], D["ranges"]["area"]
    for key in M.VARS + ("sea_state",):
        assert area[key]["min"] <= route[key]["min"] <= route[key]["max"] <= area[key]["max"], key
        for s in D["samples"]:
            assert area[key]["min"] - 0.01 <= s[key] <= area[key]["max"] + 0.01, (key, s)


@pytest.mark.parametrize("first,last,label", [("2026-10-01T00:00", "2026-10-15T23:00", "1-15 OCT 2026"),
                                              ("2026-09-28T00:00", "2026-10-12T23:00", "28 SEP-12 OCT 2026"),
                                              ("2026-12-28T00:00", "2027-01-03T23:00", "28 DEC 2026-3 JAN 2027")])
def test_the_period_label_is_the_datas_own(first, last, label):
    cache = {"waypoints": [{"hourly": {"time": [first, last]}}, {"hourly": {"time": [first, last]}}]}
    assert M.data_period(cache) == label


def test_the_period_label_refuses_series_on_different_hours():
    with pytest.raises(ValueError):
        M.data_period({"waypoints": [{"hourly": {"time": ["2026-10-01T00:00"]}}, {"hourly": {"time": ["2026-10-02T00:00"]}}]})


# ---------------------------------------------------------------------------------------------- windows and D1
def test_a_window_is_the_share_of_sampled_hours_inside_its_limits():
    g4 = next(w for w in D["windows"] if w["guest"] == "G4")
    assert (g4["wind_kn_max"], g4["sea_state_max"]) == (25, 4)
    by_hand = sum(1 for s in D["samples"] if s["gust_kn"] <= 25 and s["sea_state"] <= 4) / len(D["samples"])
    assert g4["open_pct"] == round(100 * by_hand, 1)
    assert {w["guest"] for w in D["windows"]} == {"G2", "G3", "G4"}


def test_d1_at_30_c_is_the_engines_own_verdict_and_cooler_water_leaves_more_cooling():
    A, cards, missions = _engine()
    for p in D["profiles"]:
        r = Ad.admit(A, cards, ["G3", "G4"], "G5", missions[p["id"]])
        assert (p["envelope"]["verdict"], p["envelope"]["cooling_kw"]) == (r.verdict, round(r.lines["heat"].capacity, 1))
        assert p["route_max"]["cooling_kw"] >= p["envelope"]["cooling_kw"]


def test_d1_and_the_cooling_rows_are_judged_at_the_routes_p90_and_max_seawater():
    A, _, _ = _engine()
    route, c = D["ranges"]["route"]["seawater_c"], D["cooling"]
    for p in D["profiles"]:
        assert (p["route_p90"]["seawater_c"], p["route_max"]["seawater_c"]) == (route["p90"], route["max"])
    assert (c["route_p90_c"], c["route_max_c"]) == (route["p90"], route["max"])
    assert c["normal_kw_at_p90"] == round(Lg.heat_capacity_kw(A, route["p90"]), 1)
    assert c["normal_kw_at_max"] == round(Lg.heat_capacity_kw(A, route["max"]), 1)
    assert c["degraded_kw_at_max"] == round(Lg.heat_capacity_kw(A, route["max"], True), 1)


def test_the_route_warns_that_one_pump_down_cannot_carry_the_load_out():
    c = D["cooling"]
    assert c["load_out_heat_kw"] == 105 and c["degraded_kw_at_max"] < c["load_out_heat_kw"] < c["normal_kw_at_max"]


def test_a_mission_critical_guest_outside_the_load_out_says_so():
    by_id = {p["id"]: {x["guest"]: x for x in p["mission_critical"]} for p in D["profiles"]}
    assert not by_id["patrol"]["G1"]["in_load_out"] and not by_id["disaster_relief"]["G6"]["in_load_out"]
    assert by_id["disaster_relief"]["G5"]["in_load_out"] and by_id["disaster_relief"]["G5"]["activities"] == []
    cards = {re.search(r"<h3>(.*?)</h3>", c).group(1): c for c in PAGE.split("<div class='card'>")[1:]}
    relief, patrol, sar = cards["DISASTER RELIEF"], cards["PATROL"], cards["SEARCH AND RESCUE"]
    assert re.search(r"<b>G6</b> <span class='muted'>NOT IN LOAD-OUT</span>", relief)
    assert re.search(r"<b>G5</b> <span class='muted'>NOT WEATHER-GATED</span>", relief)
    assert re.search(r"<b>G1</b> <span class='muted'>NOT IN LOAD-OUT</span>", patrol)
    assert "NOT IN LOAD-OUT" not in sar and "% OPEN" in sar


# ---------------------------------------------------------------------------------------------- the page
def test_the_page_is_self_contained_and_credits_its_data():
    # <a href> links are fine, fetches are not: no remote src, <link href>, @import or url(), protocol-relative included
    assert re.search(r"""src=["']?(https?:)?//|<link[^>]+href=["']?(https?:)?//|@import|url\(["']?(https?:)?//""", PAGE) is None
    assert re.search(r"""<a href=["']https?://""", PAGE)
    assert ('<a href="https://open-meteo.com/">Weather data by Open-Meteo.com</a> · '
            '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>') in PAGE
    assert "Made with Natural Earth" in PAGE and "<svg" in PAGE


def test_the_page_names_its_ranges_and_their_source():
    assert "<h2>WEATHER RANGES · 1-15 OCT 2026 · OPEN-METEO MARINE AND ARCHIVE</h2>" in PAGE
    assert "<th>ROUTE P90</th><th>ROUTE MAX</th><th>AREA MAX</th>" in PAGE
    assert "<tr><th>SEAWATER</th><td>25.8</td><td>26.0</td><td>27.2</td>" in PAGE
    assert "COOLING AT ROUTE P90 SEAWATER" in PAGE and "COOLING AT ROUTE MAX SEAWATER" in PAGE and "ONE PUMP DOWN AT ROUTE MAX" in PAGE
    assert "WEATHER BETWEEN 3 GRID POINTS (4 WAYPOINTS), INTERPOLATED ALONG THE ROUTE" in PAGE
    assert "AREA ±10 KM · ROUTE WEATHER" in PAGE
    assert "FORECAST" not in PAGE and "4 GRID POINTS" not in PAGE


def test_the_jury_sees_no_seed_branch_or_commit():
    header = re.search(r"<header>.*?</header>", PAGE, re.S).group(0)
    assert "SEED" not in header and "POINTS" not in header
    text = _screen_text(PAGE)
    assert "PLAN S. CHAWLA" in text
    assert not re.search(r"seed|fbe59a5|feat/|Siddharth", text, re.I)
    assert ";" not in text
    assert (D["sampling"]["seed"], D["sampling"]["points"]) == (0, 200)      # kept in deployment.json
