"""Live injection (the jury's failures): events pushed into a running simulator land on the next tick,
are recorded, and the governor answers them like scripted ones. The key map is the keyboard stand-in
for the board's button and knob (DESIGN_FREEZE delta 10)."""
import pytest

from sdv.cli import KeyInjector
from sdv.data import load_inputs
from sdv.governor import Governor
from sdv.plant.sim import Simulator


def loop(mission="survey", schedule=None, until_min=21):
    """Run with a schedule {t_min: key} of jury keypresses, fed through the real key map (no terminal)."""
    inputs = load_inputs("scenario-b")
    gov = Governor(inputs, mission)
    sim = Simulator(inputs, seed=1, mission=mission, on_tick=gov.on_tick)
    keys = KeyInjector(sim, gov, ["survey", "sar"], color=False)
    pressed = dict(schedule or {})

    def sink(s):
        if s is None:
            return
        t_min = s["t_s"] / 60
        if t_min in pressed:
            e = keys.event_for(pressed.pop(t_min))
            keys.injected.append(sim.inject(e))

    sim.run(until_min, sink=sink)
    return gov, sim, keys


def test_injected_event_lands_on_the_next_tick_and_is_recorded_with_its_source():
    gov, sim, keys = loop(schedule={5.0: "c"})
    e = keys.injected[0]
    assert e["type"] == "cooling_degraded" and e["injected"] and e["source"] == "jury" and e["t_s"] == 5 * 60 + 1
    snap = sim.snapshots[5 * 60 + 1]
    assert any(x["type"] == "cooling_degraded" and x.get("injected") for x in snap["events"])
    assert snap["ship"]["cooling"] == "degraded" and snap["gauges"]["heat"]["capacity"] == 80
    assert any(a["type"] == "cooling_degraded" and a.get("injected") for a in sim.applied)


def test_early_pump_fault_then_the_scripted_landing_forces_a_throttle_at_17_not_19():
    gov, sim, _ = loop(schedule={5.0: "c"})
    d4 = [d for d in gov.decisions if d.kind == "D4" and d.verdict != "armed"]
    assert d4[0].t_s == 301 and d4[0].verdict == "holds"  # 48 of 75 kW, nothing shed
    overload = next(d for d in d4 if d.extras["trigger"] == "overload")
    assert overload.t_s == 17 * 60 and overload.binding.cls == "heat" and overload.extras["ladder"]["steps"][0]["guest"] == "G4"
    assert sim.snapshots[17 * 60 + 1]["guests"]["G4"]["mode"] == "charge"


def test_over_consumption_is_seen_by_the_ledger_and_the_ladder():
    gov, sim, _ = loop(schedule={3.0: "o"})
    s = sim.snapshots[3 * 60 + 1]
    assert s["guests"]["G5"]["actual_kw"] == 54 and s["guests"]["G5"]["declared_kw"] == 45 and s["gauges"]["power"]["committed"] == 57
    fault = next(d for d in gov.decisions if d.kind == "D4" and d.extras.get("trigger") == "cooling_degraded")
    assert fault.binding.demand == 90 and fault.extras["ladder"]["steps"][0]["guest"] == "G4"  # 1 + 54 + 35


def test_swap_key_toggles_the_file_and_changes_the_later_decision():
    gov, sim, keys = loop(schedule={10.0: "s"})
    assert keys.injected[0] == {**keys.injected[0], "type": "priority_swap", "mission": "sar"}
    assert gov.mission == "sar" and sim.mission == "sar"
    fault = next(d for d in gov.decisions if d.kind == "D4" and d.extras.get("trigger") == "cooling_degraded")
    assert fault.mission == "sar" and fault.extras["ladder"]["steps"][0]["guest"] == "G5"


def test_crew_key_steps_through_the_levels_and_the_deadline_verdict_follows():
    gov, sim, keys = loop(schedule={2.0: "k"})
    assert keys.injected[0]["crew"] == 6 and sim.fsm.crew == 6
    (d3,) = [d for d in gov.decisions if d.kind == "D3"]
    assert d3.verdict == "G4 proceeds, deadline not met" and d3.extras["deadline_met"] is False
    assert d3.extras["fallback"] == "ditch" and "cannot be met with 6 aboard (8.8 min short): the card's fallback is to ditch" in d3.sentence
    assert d3.binding.demand == 3 + 12 + 4 and d3.binding.capacity == pytest.approx(10.2, abs=0.01)


def test_a_genset_trip_never_repairs_a_failed_pump():
    gov, sim, _ = loop(schedule={5.0: "c"})
    assert all(s["ship"]["cooling"] == "degraded" for s in sim.snapshots[5 * 60 + 1:])
    trip = next(d for d in gov.decisions if d.kind == "D4" and d.extras.get("trigger") == "genset_trip")
    assert trip.binding.cls == "heat" and trip.binding.capacity == 75  # cooling, not power, is the tighter line now


def test_battery_key_reports_the_plant_battery_and_fires_d3_early():
    gov, sim, keys = loop(schedule={7.0: "b"})
    assert keys.injected[0]["type"] == "guest_report" and 18 < keys.injected[0]["battery_pct"] < 20
    (d3,) = [d for d in gov.decisions if d.kind == "D3"]
    assert d3.t_s == 7 * 60 + 1 and "must land within 12 min" in d3.sentence


def test_genset_keys_trip_and_restart_and_seawater_key_warms_the_loop():
    gov, sim, keys = loop(schedule={3.0: "g", 6.0: "r", 9.0: "w"})
    assert sim.snapshots[3 * 60 + 1]["ship"]["genset"] == 1 and sim.snapshots[6 * 60 + 1]["ship"]["genset"] == 2
    assert sim.snapshots[9 * 60 + 1]["env"]["seawater_c"] == 27 and sim.snapshots[9 * 60 + 1]["gauges"]["heat"]["capacity"] == pytest.approx(126.67, abs=0.01)
    trip = next(d for d in gov.decisions if d.kind == "D4" and d.extras.get("trigger") == "genset_trip")
    assert trip.t_s == 3 * 60 + 1 and trip.verdict == "holds"


def test_unknown_key_and_pause_do_not_inject():
    inputs = load_inputs("scenario-b")
    sim = Simulator(inputs, seed=1, mission="survey")
    keys = KeyInjector(sim, Governor(inputs, "survey"), ["survey", "sar"], color=False)
    assert keys.event_for("x") is None and keys.event_for("p") is None and keys.fd is None
    keys.close()
