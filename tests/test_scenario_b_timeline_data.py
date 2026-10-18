"""Checks the DEC-40 Scenario B numbers against the timeline, cards and assumptions (no engine needed),
and the arithmetic behind the Physical Account's closing answer (a standby chilled-water pump)."""
from pathlib import Path

import pytest
import yaml

from test_envelope_gate_data import A, CARDS, MISSIONS, first_throttle

ROOT = Path(__file__).resolve().parents[1]
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())


def cooling_kw(seawater_c, factor=1.0):
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    return (c0 + (c1 - c0) * (seawater_c - t0) / (t1 - t0)) * factor


def ceiling(gensets_online, factor=1.0, seawater_c=None):
    # DEC-35: the 60 s peak allowance is never credited (admission.peak_credit_kw is 0).
    reserve = A["power"]["guest_reserve_kw"]["one_genset_down" if gensets_online == 1 else "cruise"] + A["admission"]["peak_credit_kw"]
    sea = TL["location"]["seawater_c"] if seawater_c is None else seawater_c
    return min(reserve, cooling_kw(sea, factor)) - A["power"]["shed_headroom_kw"]


def mode_kw(guest, name):
    return next(m["power_kw"] for m in CARDS[guest]["modes"] if m["name"] == name)


def fault_event():
    return next(e for e in TL["events"] if e["type"] == "cooling_degraded")


def chilled_envelope_kw(guests):
    """Stacked envelope draws of the chilled-water guests (max of nominal and any peak over 60 s)."""
    total = 0
    for g in guests:
        p = CARDS[g]["consumes"]["power_kw"]
        peak = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
        total += max(p["nominal"], peak) if CARDS[g]["cooling"] == "chilled_water" else 0
    return total


def test_load_out_is_the_dec63_set_and_fits_the_margin():
    """The organisers' load-out (DEC-63): G1 on the mast beside G3, G4 and G5; G1 is air-cooled, so it is on the bus only."""
    assert TL["guests"] == ["G1", "G3", "G4", "G5"]
    mass = sum(p["mass_t"] for g in TL["guests"] for p in CARDS[g]["placement"]["parts"])
    brief = sum(p["mass_t"] for g in ["G2", "G3", "G4", "G5"] for p in CARDS[g]["placement"]["parts"])
    assert mass == pytest.approx(9.56) and mass <= A["mass"]["margin_t"]
    assert brief == pytest.approx(13.015) and brief > A["mass"]["margin_t"]
    assert CARDS["G1"]["cooling"] == "air" and CARDS["G1"]["placement"]["parts"][0]["allowed"] == ["mast_free"]
    assert "DEC-63" in TL["provenance"]["guests"]["why"] and "hangar roof" in TL["provenance"]["guests"]["why"]


def test_landing_beats_the_drone_deadline_with_the_seed_and_the_worst_case():
    report = next(e for e in TL["events"] if e["type"] == "guest_report")
    r3 = A["rules"]["r3"]
    deadline = report["t_min"] - (20 - report["battery_pct"]) / r3["drain_pct_min"] + 12  # brief B, G4: land within 12 min
    worst = A["transition_picks"]["r3_worst_case"]
    worst_landing = report["t_min"] + worst["confirm_min"][14] + worst["clear_deck_min"][14] + r3["approach_min"]
    assert TL["seed_pins"]["g4_lands_at_min"] < worst_landing <= deadline
    assert TL["seed_pins"]["approach_min"] == r3["approach_min"]


def test_timeline_events_in_order_and_landing_pinned():
    times = [e["t_min"] for e in TL["events"]]
    assert times == sorted(times)
    landing = next(e for e in TL["events"] if e.get("state") == "landed_fast_charging")
    pins = TL["seed_pins"]
    assert landing["t_min"] == 8 + pins["confirm_min"] + pins["deck_clear_min"] + pins["approach_min"] == pins["g4_lands_at_min"]


def test_minute_12_trip_holds_under_both_files():
    c = ceiling(1)
    assert c == pytest.approx(95) == A["admission"]["one_genset_down_gate"]["kw"]
    g1 = mode_kw("G1", "full")
    survey = g1 + mode_kw("G3", "standby") + mode_kw("G4", "standby") + mode_kw("G5", "full")
    sar = g1 + mode_kw("G3", "standby") + mode_kw("G4", "fast_charge") + mode_kw("G5", "full")
    assert (survey, sar) == (pytest.approx(49.5), pytest.approx(82.5))
    assert survey <= c and sar <= c
    assert (survey - g1, sar - g1) == (pytest.approx(48), pytest.approx(81)), "the loop carries 1.5 kW less: G1 is air-cooled"


@pytest.mark.parametrize("mission,current,cost", [
    ("survey", {"G1": "full", "G3": "standby", "G4": "standby", "G5": "full"}, 0.0038),
    ("sar", {"G1": "full", "G3": "standby", "G4": "fast_charge", "G5": "full"}, 0.0189),
])
def test_minute_12_armed_first_step_is_g5_to_low_power(mission, current, cost):
    # Nothing runs at minute 12; D4 shows the step it would take first. Under survey G4 is airborne at
    # 2 kW with no charge to throttle; under sar its fast charge is reserved and mission-critical.
    guest, to, freed = cheapest_step(current, mission)
    assert (guest, to, freed) == ("G5", "low_power", 37)
    m = MISSIONS[mission]
    lost = 1.0 - next(x for x in CARDS["G5"]["modes"] if x["name"] == "low_power")["capability_retained"]
    assert m["weights"][CARDS["G5"]["capability"]["name"]] * lost / freed == pytest.approx(cost, rel=0.02)


@pytest.mark.parametrize("mission,guest,after,total_after", [("survey", "G4", 56, 57.5), ("sar", "G5", 44, 45.5)])
def test_minute_19_cooling_fault_forces_the_ladder(mission, guest, after, total_after):
    """Cooling is judged on the loop (the chilled-water guests) and power on the bus (every guest): the loop is 6 kW
    over its 75 kW limit while the bus has 12.5 kW spare under its 95, so the same throttle fixes it under each file."""
    fault = fault_event()
    c = ceiling(1, fault["factor"])
    assert c == pytest.approx(75)
    assert fault["load_modes"] == {"G1": "full", "G3": "standby", "G4": "fast_charge", "G5": "full"}
    loop = sum(mode_kw(g, m) for g, m in fault["load_modes"].items() if CARDS[g]["cooling"] == "chilled_water")
    total = sum(mode_kw(g, m) for g, m in fault["load_modes"].items())
    power_limit = A["power"]["guest_reserve_kw"]["one_genset_down"] - A["power"]["shed_headroom_kw"]
    assert loop == pytest.approx(81) and loop > c
    assert total == pytest.approx(82.5) and total <= power_limit
    first = first_throttle(["G4", "G5"], mission)
    assert first[0] == guest
    assert loop - first[1] == pytest.approx(after) and loop - first[1] <= c
    assert total - first[1] == pytest.approx(total_after) and total - first[1] <= power_limit


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


def test_closing_answer_a_standby_pump_removes_the_cooling_sheds():
    """Physical Account closing answer: with a standby pump, losing one pump no longer costs 40 %."""
    fault = fault_event()
    load = sum(mode_kw(g, m) for g, m in fault["load_modes"].items() if CARDS[g]["cooling"] == "chilled_water")  # the loop's load
    today, with_pump = ceiling(1, fault["factor"]), ceiling(1)
    assert load == pytest.approx(81)
    assert today == pytest.approx(75) and load > today  # today: a throttle at minute 19
    assert with_pump == pytest.approx(95) and load <= with_pump  # the loop stays at 133.3 kW, nothing shed
    t30 = A["envelope"]["judge_cooling_at_c"]
    a5 = A["account"]["closing"]["a5_guests"]
    for guests, kw in ((TL["guests"], 105), (a5, 100)):
        chilled = chilled_envelope_kw(guests)
        assert chilled == pytest.approx(kw)
        today, with_pump = ceiling(2, A["heat"]["degraded_factor"], t30), ceiling(2, 1.0, t30)
        assert today == pytest.approx(67) and chilled > today  # a pump loss today, for up to 14 days
        assert with_pump == pytest.approx(115) and chilled <= with_pump
    assert cooling_kw(t30) - cooling_kw(t30, A["heat"]["degraded_factor"]) == pytest.approx(48)


def test_closing_answer_a_battery_bridge_is_capped_by_cooling_at_30c():
    battery = A["account"]["closing"]["battery_kw"]
    t30 = A["envelope"]["judge_cooling_at_c"]
    one_set = A["power"]["guest_reserve_kw"]["one_genset_down"]
    usable = min(one_set + battery, cooling_kw(t30)) - min(one_set, cooling_kw(t30))
    assert usable == pytest.approx(20) and usable < battery


def test_every_scenario_b_choice_is_a_physical_account_row():
    rows = {k for r in A["account"]["rows"] for k in r.get("keys", [])}
    ours = {f"scenario_b.{k}" for k, p in TL["provenance"].items() if p["source"] == "assumed"}
    assert ours and ours <= rows
    assert all(TL["provenance"][k[len("scenario_b."):]].get("why") for k in ours)


def test_acoustic_link_rule_matches_g3_surveying_and_the_scenario_water():
    link = A["data"]["acoustic_link"]
    surveying = next(c for c in CARDS["G3"]["conditions"] if c["activity"] == "surveying")["requires"]
    assert link["up_when"] == {"course": surveying["course"], "noise": surveying["noise"],
                               "deck_machinery": surveying["deck_machinery"]}
    assert TL["location"]["layered"] is False  # a layered column would break the link from minute 0 (A.5)
    # The hold-depth request reaches G3 at the slow end of A.5 inside the 1 min bridge confirm.
    assert link["judged_latency_s"] == max(A["data"]["acoustic_latency_s"])
    assert link["drop_delay_s"] + link["judged_latency_s"] <= TL["seed_pins"]["confirm_min"] * 60


def test_fault_debounce_fits_inside_the_first_shed_ceiling():
    f = A["fault_entry"]
    assert f["confirm"] == {"genset_trip": "power.trip_confirm", "cooling_degraded": "heat.degraded_confirm"}
    assert A["power"]["trip_confirm"]["needed"] == 2 <= len(A["power"]["trip_confirm"]["signals"])
    # The 5 s clock runs from the raw event (A.6: a trip is instant), debounce included.
    assert A["ship_state"]["genset"]["trip_s"] + f["debounce_s"] < A["response_time_s"]["shed_first_action"]
    assert f["record_times"] == ["raw_event", "confirmed"]
