"""The plant: ship state machine, guest runtimes and the seeded 1 Hz loop.

Numbers are the brief's and the oracles in docs/EXPECTED_OUTCOMES.md; nothing here needs a governor.
"""
import random

import pytest

from sdv.data import load_inputs
from sdv.ledger import cooling_capacity_kw, power_reserve_kw
from sdv.plant.fsm import ShipFSM
from sdv.plant.sim import Simulator


@pytest.fixture(scope="module")
def inputs():
    return load_inputs("scenario-b")


def run(inputs, until_min, seed=1, mission="survey"):
    sim = Simulator(inputs, seed=seed, mission=mission)
    sim.run(until_min)
    return sim


def at(sim, t_min):
    return sim.snapshots[int(round(t_min * 60))]


# -- determinism --------------------------------------------------------------------------------------

def test_same_seed_same_run_hash(inputs):
    assert run(inputs, 20).run_hash() == run(inputs, 20).run_hash()


def test_inputs_are_hashed_into_the_header(inputs):
    h = run(inputs, 1).header()
    assert set(h["inputs"]) == {"assumptions", "cards", "missions", "scenario"}
    assert all(len(v) == 16 for v in h["inputs"].values())


# -- capacities from Annex A ---------------------------------------------------------------------------

def test_cooling_curve_matches_annex_a2(inputs):
    a = inputs.assumptions
    assert cooling_capacity_kw(a, 12, False) == pytest.approx(160)
    assert cooling_capacity_kw(a, 30, False) == pytest.approx(120)
    assert cooling_capacity_kw(a, 24, False) == pytest.approx(133.333, abs=1e-3)
    assert cooling_capacity_kw(a, 30, True) == pytest.approx(72)
    assert cooling_capacity_kw(a, 35, False) == pytest.approx(120), "clamped to the brief's domain"


def test_power_reserve_halves_with_one_genset_down(inputs):
    a = inputs.assumptions
    assert power_reserve_kw(a, "cruise", 2) == 200
    assert power_reserve_kw(a, "slow", 1) == 100


# -- Scenario B as the plant plays it (open loop, DEC-40 timeline) -------------------------------------

def test_scenario_b_minute_0_baseline(inputs):
    s = at(run(inputs, 1), 0)
    ship = s["ship"]
    assert (ship["speed_band"], ship["course"], ship["noise"], ship["deck"]) == ("slow", "steady", "quiet", "clear")
    assert s["gauges"]["power"]["committed"] == pytest.approx(48)  # G3 1 + G4 2 + G5 45
    assert s["gauges"]["heat"]["capacity"] == pytest.approx(133.333, abs=1e-3)
    assert s["gauges"]["mass"]["committed"] == pytest.approx(9.515)  # oracle load-out (ii)


def test_scenario_b_minute_8_drone_reports_18_percent(inputs):
    s = at(run(inputs, 9), 8)
    assert s["guests"]["G4"]["battery_pct"] == pytest.approx(18, abs=0.02)
    assert s["env"]["wind_kn"] == 22
    assert any(e["type"] == "guest_report" for e in s["events"])


def test_scenario_b_minute_12_trip_reserve_100_cooling_nominal(inputs):
    s = at(run(inputs, 13), 12)
    assert s["ship"]["genset"] == 1 and s["ship"]["cooling"] == "nominal"
    assert s["gauges"]["power"]["capacity"] == 100
    assert s["gauges"]["power"]["committed"] == pytest.approx(48)  # holds: G4 still airborne (oracle, survey)


def test_scenario_b_minute_17_landed_fast_charging_is_81_kw(inputs):
    s = at(run(inputs, 18), 17)
    assert s["guests"]["G4"]["mode"] == "fast_charge" and s["ship"]["deck"] == "occupied"
    assert s["gauges"]["power"]["committed"] == pytest.approx(81)
    assert s["gauges"]["heat"]["committed"] == pytest.approx(81)  # all three on chilled water


def test_scenario_b_minute_19_pump_fault_cooling_binds_not_power(inputs):
    s = at(run(inputs, 20), 19)
    heat, power = s["gauges"]["heat"], s["gauges"]["power"]
    assert s["ship"]["cooling"] == "degraded"
    assert heat["capacity"] == pytest.approx(80)
    assert heat["free"] < 0 < power["free"], "the loop is over, the reserve is not"


def test_drone_battery_drains_at_r3_rate_until_landing(inputs):
    sim = run(inputs, 18)
    rate = inputs.assumptions["rules"]["r3"]["drain_pct_min"]
    b8, b12 = at(sim, 8)["guests"]["G4"]["battery_pct"], at(sim, 12)["guests"]["G4"]["battery_pct"]
    assert b8 - b12 == pytest.approx(4 * rate, abs=0.05)
    assert at(sim, 17.5)["guests"]["G4"]["battery_pct"] > at(sim, 17)["guests"]["G4"]["battery_pct"]


# -- ship state machine (A.6) --------------------------------------------------------------------------

def fsm(inputs, crew=14, seed=3, **state):
    return ShipFSM(inputs.assumptions["ship_state"], crew, random.Random(seed), state=state)


def test_going_quiet_takes_2_to_4_minutes_leaving_is_instant(inputs):
    f = fsm(inputs, noise="normal")
    rec = f.request("noise", "quiet", now_s=0)
    assert rec["result"] == "scheduled" and 120 <= rec["ready_at_s"] <= 240
    f.tick(rec["ready_at_s"])
    assert f.state["noise"] == "quiet"
    assert f.request("noise", "manoeuvring", now_s=rec["ready_at_s"])["result"] == "immediate"


def test_speed_band_change_costs_2_to_5_minutes_per_band(inputs):
    f = fsm(inputs, speed_band="slow")
    rec = f.request("speed_band", "fast", now_s=0)  # slow -> cruise -> fast: two bands
    assert 2 * 120 <= rec["ready_at_s"] <= 2 * 300


def test_deck_clear_time_depends_on_crew_and_is_impossible_uncrewed(inputs):
    r14 = fsm(inputs, crew=14, deck="occupied").request("deck", "clear", 0)
    r6 = fsm(inputs, crew=6, deck="occupied").request("deck", "clear", 0)
    r0 = fsm(inputs, crew=0, deck="occupied").request("deck", "clear", 0)
    assert 180 <= r14["ready_at_s"] <= 300
    assert 480 <= r6["ready_at_s"] <= 720
    assert r0["result"] == "refused"
    assert fsm(inputs, crew=0, deck="clear").request("deck", "clear", 0)["result"] == "immediate"


def test_silence_is_instant_and_cooling_is_not_repaired_at_sea(inputs):
    f = fsm(inputs, cooling="degraded")
    assert f.request("emission", "silent", 0)["result"] == "immediate"
    assert f.request("cooling", "nominal", 0)["result"] == "refused"


def test_genset_trip_is_a_plant_event_restart_takes_5_to_15_minutes(inputs):
    f = fsm(inputs)
    assert f.request("genset", 1, 0)["result"] == "refused"  # a trip is confirmed by the plant, never asked for
    f.force("genset", 1, 0, "genset trip")
    assert f.state["genset"] == 1
    rec = f.request("genset", 2, 0)
    assert 300 <= rec["ready_at_s"] <= 900


def test_unknown_state_values_are_rejected(inputs):
    with pytest.raises(ValueError):
        fsm(inputs).request("noise", "loud", 0)
