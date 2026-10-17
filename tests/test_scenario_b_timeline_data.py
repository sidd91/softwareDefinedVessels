"""Checks the DEC-40 Scenario B numbers against the timeline, cards and assumptions (no engine needed)."""
from pathlib import Path

import pytest
import yaml

from test_envelope_gate_data import A, CARDS, MISSIONS, first_throttle

ROOT = Path(__file__).resolve().parents[1]
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())


def cooling_kw(seawater_c, factor=1.0):
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    return (c0 + (c1 - c0) * (seawater_c - t0) / (t1 - t0)) * factor


def ceiling(gensets_online, factor=1.0):
    reserve = A["power"]["guest_reserve_kw"]["one_genset_down" if gensets_online == 1 else "cruise"]
    return min(reserve, cooling_kw(TL["location"]["seawater_c"], factor)) - A["power"]["shed_headroom_kw"]


def mode_kw(guest, name):
    return next(m["power_kw"] for m in CARDS[guest]["modes"] if m["name"] == name)


def test_timeline_events_in_order_and_landing_pinned():
    times = [e["t_min"] for e in TL["events"]]
    assert times == sorted(times)
    landing = next(e for e in TL["events"] if e.get("state") == "landed_fast_charging")
    pins = TL["seed_pins"]
    assert landing["t_min"] == 8 + pins["confirm_min"] + pins["deck_clear_min"] + pins["approach_min"] == pins["g4_lands_at_min"]


def test_minute_12_trip_holds_under_both_files():
    c = ceiling(1)
    assert c == pytest.approx(95)
    survey = mode_kw("G3", "standby") + mode_kw("G4", "standby") + mode_kw("G5", "full")
    sar = mode_kw("G3", "standby") + mode_kw("G4", "fast_charge") + mode_kw("G5", "full")
    assert (survey, sar) == (pytest.approx(48), pytest.approx(81))
    assert survey <= c and sar <= c


@pytest.mark.parametrize("mission,guest,after", [("survey", "G4", 56), ("sar", "G5", 44)])
def test_minute_19_cooling_fault_forces_the_ladder(mission, guest, after):
    fault = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    c = ceiling(1, fault["factor"])
    assert c == pytest.approx(75)
    load = mode_kw("G3", "standby") + mode_kw("G4", "fast_charge") + mode_kw("G5", "full")
    assert load == pytest.approx(81) and load > c
    first = first_throttle(["G4", "G5"], mission)
    assert first[0] == guest
    after_kw = load - first[1]
    assert after_kw == pytest.approx(after)
    assert after_kw <= c


def test_fault_follows_the_landing_inside_the_fast_charge():
    fault = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    landing = next(e for e in TL["events"] if e.get("state") == fault["trigger"]["after"]["state"])
    assert landing["guest"] == fault["trigger"]["after"]["guest"] == "G4"
    assert fault["t_min"] == landing["t_min"] + fault["trigger"]["delay_min"]
    fast = next(m for m in CARDS["G4"]["modes"] if m["name"] == "fast_charge")
    assert landing["t_min"] < fault["t_min"] < landing["t_min"] + fast["duration_s"] / 60


def cheapest_step(current, mission):
    """Same rule as first_throttle, but from each guest's current mode."""
    m = MISSIONS[mission]
    options = []
    for g, mode_name in current.items():
        card = CARDS[g]
        mode = next(x for x in card["modes"] if x["name"] == mode_name)
        if mode.get("interruptible") is False:
            continue
        lower = [x for x in card["modes"] if x["power_kw"] < mode["power_kw"] and x["capability_retained"] > 0]
        if not lower:
            continue
        to = max(lower, key=lambda x: x["power_kw"])
        freed = mode["power_kw"] - to["power_kw"]
        cost = m["weights"][card["capability"]["name"]] * (mode["capability_retained"] - to["capability_retained"]) / freed
        options.append((g in m["mission_critical"], cost, g, to["name"], freed))
    return min(options)[2:] if options else None


@pytest.mark.parametrize("req", TL["g3_charge_requests"], ids=lambda r: r["mission"])
def test_g3_charge_start_after_the_fault(req):
    c = ceiling(1, next(e for e in TL["events"] if e["type"] == "cooling_degraded")["factor"])
    others = sum(mode_kw(g, mode) for g, mode in req["others"].items())
    load = mode_kw("G3", "charging") + others
    if req["mission"] == "survey":
        assert load == pytest.approx(80) and load > c
        step = cheapest_step(req["others"], "survey")
        assert step[:2] == ("G5", "low_power")
        assert load - step[2] == pytest.approx(43) and load - step[2] <= c
    else:
        assert load == pytest.approx(68) and load <= c
