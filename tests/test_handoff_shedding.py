"""Handoff fixes in D4 (Sun 00:50): no shed on stand-in values, only the line that binds can hold D4 back, and a
delayed first action keeps its 5 s due tick (docs/HANDOFF_SIDDHARTH.md #1, #2, #9)."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import loader as Ld  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.loop import Loop, load_simulator, replay, scripted_inputs  # noqa: E402

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": True, "payload": payload}


def run(drops, mission="survey", until=1200, log_dir=None):
    inputs = scripted_inputs()
    for t, feed, until_t_s in drops:
        inputs.setdefault(t, []).append(inp(t, "feed_drop", feed=feed, until_t_s=until_t_s))
    loop = Loop(load_simulator(mission=mission), mission, inputs=inputs, log_dir=log_dir, standby=log_dir is not None)
    outs = list(loop.ticks(until=until))
    loop.close()
    return outs


def d4(outs):
    return [r for o in outs for r in o.records if r["kind"] == "D4"]


def in_step_and_replayed(outs, log_dir, mission="survey"):
    snaps, decisions = replay(log_dir, mission)
    return (all(o.standby == "in step" for o in outs)
            and snaps == (log_dir / "snapshots.jsonl").read_text().splitlines()
            and decisions == (log_dir / "decisions.jsonl").read_text().splitlines())


def later(snap, t, since=None):
    """The fixture moved to a later tick of the same over-limit stretch, every guest's mode unchanged (or changed at since)."""
    s = copy.deepcopy(snap)
    s["run"]["tick"] = s["run"]["t_ship_s"] = t
    for b in s["guests"].values():
        if since is not None:
            b["mode"]["since_t_s"] = since
    return s


# ------------------------------------------------------------------------------------------------ #1 stand-in draws

def test_a_guest_meter_drop_sheds_nothing_on_stand_in_draws(tmp_path):
    """#1: from 1133 every mode reads its highest draw (106.5 against 95 kW, then 105 against 75 on the loop). D4 sheds
    nothing on those, and once the feed is back at 1150 it sheds G4 on fresh readings, G5 kept at full."""
    outs = run([(1130, "guest_meter", 1150)], log_dir=tmp_path)
    recs = [r for r in d4(outs) if 1130 <= r["tick"] < 1150]
    assert recs and all(r["verdict"] == "unconfirmed" and r["steps"] == [] for r in recs)
    at_1141 = next(r for r in recs if r["tick"] == 1141)
    assert at_1141["binding"]["class"] == "heat" and at_1141["load_kw"] == 105
    shed = [r for r in d4(outs) if r["verdict"] == "shed"]
    assert [(r["tick"], [(s["guest"], s["to_mode"], s["due_t_s"]) for s in r["steps"]]) for r in shed] == \
        [(1150, [("G4", "charge", 1145)])]   # #9: the first action of the stretch, late, keeps the fault's 5 s tick
    modes = {g: b["mode"]["value"] for g, b in outs[1160].snapshot["guests"].items()}
    assert modes["G5"] == "full" and modes["G4"] == "charge"
    assert in_step_and_replayed(outs, tmp_path)


def test_a_guest_meter_never_heard_is_never_shed_on_its_fallbacks(tmp_path):
    """The estimator's never-heard fallback (highest-draw mode, declared peak) is a stand-in too: the minute-12 trip
    and the minute-19 pump read over on it, and D4 arms the ladder instead of shedding G4 every tick."""
    outs = run([(0, "guest_meter", None)], log_dir=tmp_path)
    recs = d4(outs)
    assert [(r["tick"], r["verdict"]) for r in recs] == [(721, "unconfirmed"), (1141, "unconfirmed")]
    assert all(r["armed"] and r["load_kw"] > r["limit_kw"] for r in recs)
    assert in_step_and_replayed(outs, tmp_path)


def test_a_missing_mode_reading_counts_at_its_highest_draw_and_sheds_nothing():
    """A guest whose mode was never reported (null, not marked stale) is unknown, not standby: it counts at its highest
    draw on the armed ladder and D4 does not act on it."""
    s = copy.deepcopy(SNAP["scenario_b_survey_m19"])
    s["guests"]["G3"]["mode"] = {"value": None, "source": "plant", "age_s": None, "confidence": "assumed", "stale": False}
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["draws"]["G3"] == 25 and d["load_kw"] == 105
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["armed"]
    assert d["unconfirmed_because"] == "reading missing"


# ------------------------------------------------------------------------------------------------ #2 the binding line

def test_a_pms_drop_does_not_hold_up_a_cooling_shed_on_fresh_data():
    """#2: the bus capacity is a stand-in from 1138, but cooling binds at 1141 on fresh chilled-water data with the
    pump fault confirmed: D4 sheds G4 at once, due 1145, as in the nominal run."""
    outs = run([(1135, "pms", 1175)])
    shed = next(r for r in d4(outs) if r["verdict"] == "shed")
    assert (shed["tick"], shed["binding"]["class"], shed["trigger"]) == (1141, "heat", "cooling_degraded")
    assert [(s["guest"], s["to_mode"], s["due_t_s"]) for s in shed["steps"]] == [("G4", "charge", 1145)]
    assert shed["applies_at_tick"] <= shed["first_shed_due_t_s"] == 1145


def test_a_stale_bus_with_the_bus_binding_still_sheds_nothing():
    """The other half of #2: the bus over on a stand-in capacity, cooling within its limit, is not acted on."""
    s = copy.deepcopy(SNAP["scenario_b_survey_m19"])
    for f in ("genset_1_kw", "genset_2_kw", "bus_frequency_hz"):
        s["plant"][f]["stale"], s["plant"][f]["confidence"] = True, "substituted"
    s["capacity"]["power"]["confidence"], s["capacity"]["power"]["stale"] = "substituted", True
    s["capacity"]["power"]["value"]["capacity"] = 60
    s["capacity"]["heat"]["value"]["capacity"] = 133.3
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["binding"]["class"] == "power" and d["load_kw"] > d["limit_kw"]
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["unconfirmed_because"] == "feed stale"


def test_a_fresh_cooling_overload_is_shed_for_cooling_alone_while_the_bus_is_a_stand_in():
    """Both lines over, the bus by more but on a stand-in capacity: D4 sheds what cooling needs (G4) and nothing for
    the bus, so G5 keeps full power."""
    s = copy.deepcopy(SNAP["scenario_b_survey_m19"])
    for f in ("genset_1_kw", "genset_2_kw", "bus_frequency_hz"):
        s["plant"][f]["stale"], s["plant"][f]["confidence"] = True, "substituted"
    s["capacity"]["power"]["confidence"], s["capacity"]["power"]["stale"] = "substituted", True
    s["capacity"]["power"]["value"]["capacity"] = 60
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "shed" and d["binding"]["class"] == "heat"
    assert [(st["guest"], st["to_mode"]) for st in d["steps"]] == [("G4", "charge")]
    assert d["loop_after_kw"] <= d["heat_limit_kw"] and d["total_after_kw"] > d["power_limit_kw"]


# ------------------------------------------------------------------------------------------------ #9 the first due tick

def test_a_delayed_first_action_keeps_the_5_s_due_tick():
    """#9: over since 1141 on the pump fault, first acted on at 1175 (D4 was held back): the step is the first action,
    due 1145, not part of the 60 s sequence."""
    d = D4.shed(CARDS, MISSIONS["survey"], later(SNAP["scenario_b_survey_m19"], 1175), onset_t_s=1141)
    assert [(s["guest"], s["response"], s["due_t_s"]) for s in d["steps"]] == [("G4", "shed_first_action", 1145)]


def test_a_delayed_lone_60_s_first_action_is_due_by_5_s_until_a_step_lands():
    """Every relieving step 60 S: the one that goes first is the first action (due 1145) until a step of the stretch
    has landed (a guest's mode changed since the onset), then the next is due with the full sequence (1200)."""
    m = copy.deepcopy(MISSIONS["survey"])
    m["mission_critical"] = ["G3", "G4", "G5"]
    first = D4.shed(CARDS, m, later(SNAP["scenario_b_survey_m19"], 1175), onset_t_s=1141)
    assert [(s["response"], s["due_t_s"]) for s in first["steps"]] == [("shed_full_sequence", 1145)]
    landed = D4.shed(CARDS, m, later(SNAP["scenario_b_survey_m19"], 1175, since=1170), onset_t_s=1141)
    assert [(s["response"], s["due_t_s"]) for s in landed["steps"]] == [("shed_full_sequence", 1200)]
