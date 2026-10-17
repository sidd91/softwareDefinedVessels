"""The ship-state machine (src/sdv/plant/fsm.py) against Annex A.6 as encoded in
config/assumptions.yaml and the Scenario B pins in config/scenarios/scenario_b.yaml (DEC-52)."""
import random
from pathlib import Path

import pytest
import yaml

from sdv.plant.fsm import VARS, ShipFSM, pins_from_scenario

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())
SS = A["ship_state"]
MIN = 60


def fsm(crew=14, seed=0, pins=None, **overrides):
    return ShipFSM(SS, crew, random.Random(seed), state=dict(TL["initial"]["ship_state"], **overrides), pins=pins or {})


def scenario_fsm(seed=0):
    return ShipFSM(SS, TL["initial"]["crew"], random.Random(seed), state=dict(TL["initial"]["ship_state"]),
                   pins=pins_from_scenario(TL))


def minutes(rec):
    return (rec["ready_at_s"] - rec["t_s"]) / MIN


def in_range(x, rng):
    return rng[0] <= x <= rng[1]


# -- vocabulary (freeze F2: unknown names are refused) ---------------------------------------
def test_initial_state_is_scenario_b_minute_0_and_covers_every_a6_variable():
    m = scenario_fsm()
    assert set(m.state) == set(VARS) == set(SS)
    assert m.state == TL["initial"]["ship_state"]
    assert m.crew == 14 and not m.pending


@pytest.mark.parametrize("var,value,err", [("course", "wobbly", ValueError), ("speed_band", "warp", ValueError),
                                           ("genset", 3, ValueError), ("mood", "happy", KeyError)])
def test_unknown_names_are_refused_by_request_force_and_initial_state(var, value, err):
    m = fsm()
    with pytest.raises(err):
        m.request(var, value, 0)
    with pytest.raises(err):
        m.force(var, value, 0, "test")
    with pytest.raises(err):
        fsm(**{var: value})


# -- Scenario B: the pinned deck clear makes the landing land at minute 17 ------------------
def test_scenario_b_pins_give_the_dec40_landing_time():
    pins = TL["seed_pins"]
    m = scenario_fsm()
    t = (8 + pins["confirm_min"]) * MIN  # minute 8 report, crew confirms, then the deck is cleared
    m.force("deck", "occupied", t, "people on deck during the leg")
    rec = m.request("deck", "clear", t)
    assert rec["result"] == "scheduled" and rec["pick"] == "pinned" and minutes(rec) == pins["deck_clear_min"]
    assert m.state["deck"] == "occupied" and m.snapshot()["pending"][0]["value"] == "clear"
    assert m.tick(rec["ready_at_s"] - 1) == [] and m.state["deck"] == "occupied"
    assert [p.var for p in m.tick(rec["ready_at_s"])] == ["deck"] and m.state["deck"] == "clear"
    assert rec["ready_at_s"] / MIN + pins["approach_min"] == pins["g4_lands_at_min"] == 17


def test_pins_from_scenario_maps_only_the_plant_pins():
    assert pins_from_scenario(TL) == {"deck.clear_min": 4.0}
    assert pins_from_scenario({}) == {}


@pytest.mark.parametrize("seed", range(5))
def test_the_pinned_deck_clear_does_not_depend_on_the_seed(seed):
    m = scenario_fsm(seed)
    m.force("deck", "occupied", 0, "test")
    assert minutes(m.request("deck", "clear", 0)) == TL["seed_pins"]["deck_clear_min"]


# -- A.6 ranges: seeded draws stay inside, same seed replays the same numbers ---------------
@pytest.mark.parametrize("seed", range(25))
def test_seeded_durations_stay_inside_the_a6_ranges(seed):
    m = fsm(seed=seed, course="free", noise="normal", speed_band="stopped")
    m.force("deck", "occupied", 0, "test")
    assert in_range(minutes(m.request("course", "steady", 0)), SS["course"]["settle_min"])
    assert in_range(minutes(m.request("noise", "quiet", 0)), SS["noise"]["to_quiet_min"])
    assert in_range(minutes(m.request("deck", "clear", 0)), SS["deck"]["clear_min"][14])
    assert in_range(minutes(m.request("speed_band", "slow", 0)), SS["speed_band"]["min_per_band"])
    m.force("genset", 1, 0, "genset trip")
    assert in_range(minutes(m.request("genset", 2, 0)), SS["genset"]["restart_min"])
    assert all(p.pick == "seeded" for p in m.pending)


def test_same_seed_replays_the_same_durations_and_pins_win_over_the_seed():
    def durations(seed, pins=None):
        m = fsm(seed=seed, pins=pins, course="free", noise="normal")
        m.force("deck", "occupied", 0, "test")
        return [m.request(v, t, 0)["ready_at_s"] for v, t in (("course", "steady"), ("noise", "quiet"), ("deck", "clear"))]

    assert durations(7) == durations(7)
    assert any(a != b for a, b in zip(durations(7), durations(8)))
    pinned = durations(7, pins={"deck.clear_min": 4})
    assert pinned[2] == 4 * MIN and pinned[:2] == durations(7)[:2]
    assert len({fsm(seed=s, course="free").request("course", "steady", 0)["ready_at_s"] for s in range(10)}) > 1


# -- each variable's rule --------------------------------------------------------------------
def test_course_settles_to_steady_but_goes_free_at_once():
    m = fsm(course="free")
    rec = m.request("course", "steady", 0)
    assert rec["result"] == "scheduled" and m.state["course"] == "free"
    m.tick(rec["ready_at_s"])
    assert m.state["course"] == "steady"
    assert m.request("course", "free", rec["ready_at_s"])["result"] == "immediate" and m.state["course"] == "free"


def test_speed_band_takes_one_pick_per_band_crossed():
    m = fsm(speed_band="stopped", pins={"speed_band.min_per_band": 3})
    one = m.request("speed_band", "slow", 0)
    assert minutes(one) == 3
    m.tick(one.get("ready_at_s"))
    three = m.request("speed_band", "fast", one["ready_at_s"])  # slow -> cruise -> fast
    assert minutes(three) == 2 * 3
    m.tick(three["ready_at_s"] - 1)
    assert m.state["speed_band"] == "slow"
    m.tick(three["ready_at_s"])
    assert m.state["speed_band"] == "fast"


def test_noise_takes_time_to_go_quiet_and_none_to_leave_it():
    m = fsm(noise="quiet")
    assert m.request("noise", "manoeuvring", 0)["result"] == "immediate" and SS["noise"]["leave_quiet_min"] == 0
    assert in_range(minutes(m.request("noise", "quiet", 0)), SS["noise"]["to_quiet_min"])


@pytest.mark.parametrize("crew", [14, 6])
def test_deck_clear_time_depends_on_crew_level(crew):
    m = fsm(crew=crew)
    m.force("deck", "occupied", 0, "test")
    assert in_range(minutes(m.request("deck", "clear", 0)), SS["deck"]["clear_min"][crew])


def test_deck_cannot_be_cleared_at_zero_crew_but_a_clear_deck_stays_clear():
    m = fsm(crew=0)
    assert m.request("deck", "clear", 0)["result"] == "immediate"  # already clear: nothing to do (A.6)
    m.force("deck", "occupied", 0, "test")
    rec = m.request("deck", "clear", 0)
    assert rec["result"] == "refused" and "0 aboard" in rec["why"] and m.state["deck"] == "occupied"


def test_emission_is_instant_and_silent_forbids_the_a6_actions():
    m = fsm()
    assert m.forbidden_actions() == [] and m.snapshot()["forbidden_actions"] == []
    assert m.request("emission", "silent", 0)["result"] == "immediate" and m.state["emission"] == "silent"
    assert m.forbidden_actions() == SS["emission"]["silent_forbids"]
    assert {"radio_transmit", "satcom_transmit"} <= set(m.snapshot()["forbidden_actions"])
    m.request("emission", "normal", 0)
    assert m.forbidden_actions() == []


def test_genset_trip_is_an_event_and_restart_takes_5_to_15_minutes():
    m = fsm()
    rec = m.request("genset", 1, 0)
    assert rec["result"] == "refused" and "plant event" in rec["why"] and m.state["genset"] == 2
    m.force("genset", 1, 0, "genset trip")
    assert m.state["genset"] == 1
    restart = m.request("genset", 2, 0)
    assert in_range(minutes(restart), SS["genset"]["restart_min"]) and m.state["genset"] == 1
    m.tick(restart["ready_at_s"])
    assert m.state["genset"] == 2


def test_a_forced_restart_overrides_a_pending_one():
    m = fsm()
    m.force("genset", 1, 0, "genset trip")
    m.request("genset", 2, 0)
    assert [p.var for p in m.pending] == ["genset"]
    m.force("genset", 2, 10, "genset restart")
    assert m.state["genset"] == 2 and m.pending == []


def test_cooling_degrades_only_by_plant_event_and_never_repairs_at_sea():
    m = fsm()
    rec = m.request("cooling", "degraded", 0)
    assert rec["result"] == "refused" and "plant event" in rec["why"] and m.state["cooling"] == "nominal"
    m.force("cooling", "degraded", 0, "plant alarm plus flow")
    assert m.state["cooling"] == "degraded"
    rec = m.request("cooling", "nominal", 0)
    assert rec["result"] == "refused" and "at sea" in rec["why"]
    assert not SS["cooling"]["repair_at_sea"]


def test_scenario_b_plant_events_in_order():
    m = scenario_fsm()
    seen = {}
    for e in TL["events"]:
        t = e["t_min"] * MIN
        m.tick(t)
        if e["type"] in ("genset_trip", "genset_restart"):
            m.force("genset", e["gensets_online"], t, e["type"])
        elif e["type"] == "cooling_degraded":
            m.force("cooling", "degraded", t, "plant alarm")
        else:
            continue
        seen[e["t_min"]] = (m.state["genset"], m.state["cooling"])
    assert seen == {12: (1, "nominal"), 19: (1, "degraded"), 24: (2, "degraded")}


# -- pending moves and the clock ------------------------------------------------------------
def test_a_new_request_replaces_the_pending_move_for_that_variable():
    m = fsm(course="free")
    first = m.request("course", "steady", 0)
    assert m.request("course", "free", 5)["result"] == "immediate"  # free is instant and drops the settle
    assert m.pending == [] and m.state["course"] == "free"
    again = m.request("course", "steady", 5)
    assert again["result"] == "scheduled" and again["t_s"] == 5 and first["result"] == "scheduled"
    assert [(p.var, p.value) for p in m.pending] == [("course", "steady")]
    m.tick(first["ready_at_s"] + 5 * MIN)
    assert m.state["course"] == "steady" and m.pending == []


def test_tick_completes_moves_in_ready_order_and_logs_them():
    m = fsm(course="free", noise="normal", pins={"course.settle_min": 2, "noise.to_quiet_min": 3})
    a, b = m.request("course", "steady", 0), m.request("noise", "quiet", 0)
    assert [p.var for p in m.tick(a["ready_at_s"])] == ["course"]
    assert m.state["course"] == "steady" and m.state["noise"] == "normal"
    assert [p.var for p in m.tick(b["ready_at_s"])] == ["noise"] and m.state["noise"] == "quiet"
    assert m.tick(b["ready_at_s"]) == []
    assert [r["result"] for r in m.log] == ["scheduled", "scheduled", "settled", "settled"]


# -- snapshot (ARCHITECTURE contract 4, ship-state block) ------------------------------------
def test_snapshot_carries_value_age_eta_and_pick_per_variable():
    m = fsm(course="free", pins={"course.settle_min": 2})
    m.tick(10)
    m.request("course", "steady", 10)
    m.tick(40)
    s = m.snapshot()
    assert s["crew"] == 14 and set(VARS) <= set(s) and set(s["age_s"]) == set(VARS)
    assert s["course"] == "free" and s["age_s"]["course"] == 40
    assert s["pending"] == [{"var": "course", "value": "steady", "ready_at_s": 10 + 2 * MIN, "eta_s": 2 * MIN - 30, "pick": "pinned"}]
    m.tick(10 + 2 * MIN)
    s = m.snapshot()
    assert s["course"] == "steady" and s["age_s"]["course"] == 0 and s["pending"] == []
    m.tick(10 + 2 * MIN + 7)
    assert m.snapshot()["age_s"]["course"] == 7 and m.snapshot()["age_s"]["genset"] == 10 + 2 * MIN + 7
