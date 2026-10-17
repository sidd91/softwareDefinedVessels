"""The screen on the live tick loop: the same numbers as the oracles, the shed kept on show through its recheck,
laptop inputs (priority swap, a profile applied at sea, crew level) and jumps that re-run the loop."""
import pytest

from sdv.ui import data, live, view

I = data.Inputs()


@pytest.fixture(scope="module")
def ref():
    return live.Reference()


def tile(v, name):
    return next(t for t in v["tiles"] if t["name"] == name)


def rows(d):
    return {k: val for k, val, _ in d["rows"]}


@pytest.mark.parametrize("mission,m12,m19,step", [
    ("survey", "48.0", "56.0", "G4 FAST CHARGE → CHARGE"),
    ("sar", "81.0", "44.0", "G5 FULL → LOW POWER"),
])
def test_live_run_matches_the_oracles(ref, mission, m12, m19, step):
    v8 = view.screen(I, ref.moment(mission, 481))
    assert v8["decision"]["kind"] == "D3" and v8["decision"]["r3"]["verdict"] == "CONFIRM"
    v12 = view.screen(I, ref.moment(mission, 722))
    assert tile(v12, "POWER")["value"] == f"{m12} / 95.0 kW" and v12["decision"]["tag"] == "HOLDS"
    v19 = view.screen(I, ref.moment(mission, 1142))
    assert tile(v19, "COOLING CHW")["value"] == f"{m19} / 75.0 kW"
    assert rows(v19["decision"])["ACTION"] == step and v19["decision"]["tag"] == "EXECUTED"


def test_the_recheck_after_the_shed_keeps_the_shed_on_show():
    r = live.Run("survey")
    r.advance_to(1150)
    kinds = [(x["kind"], x["verdict"], x["tick"]) for x in r.records]
    assert ("D4", "hold", 1142) in kinds
    v = view.screen(I, r.moment())
    assert v["decision"]["tag"] == "EXECUTED" and v["decision"]["recheck"].startswith("RECHECK 00:19:02 · HOLDS 56.0")
    assert v["shed_order"]["rows"][0]["state"] == "EXECUTED"
    calc = [(x["k"], x["v"]) for x in v["ledger"]["constraint"]["rows"]]
    assert ("DEMAND G3 1 + G4 35 + G5 45", "81.0 kW") in calc and calc[-1] == ("DEMAND AFTER", "56.0 kW")
    assert tile(v, "RESPONSE")["sub"] == "D4 FIRST ACTION · COMPUTE"
    log = [(e["type"], e["tag"]) for e in v["log"]]
    assert ("CREW POLICY", "R3 · 14") in log and ("STATE", "R3") not in log


def test_a_jump_back_re_runs_the_loop_to_the_same_records():
    lr = live.LiveReplay("sar", 0, running=False)
    lr.command({"cmd": "jump", "t": 1150})
    first = [(r["seq"], r["kind"], r["verdict"], r["sentence"]) for r in lr.run.records]
    lr.command({"cmd": "jump", "t": 700})
    assert lr.t_s == 700 and all(r["tick"] <= 700 for r in lr.run.records)
    lr.command({"cmd": "jump", "t": 1150})
    assert [(r["seq"], r["kind"], r["verdict"], r["sentence"]) for r in lr.run.records] == first


def test_a_priority_swap_mid_run_decides_under_the_new_file():
    lr = live.LiveReplay("survey", 600, running=False)
    lr.command({"cmd": "mission", "value": "sar"})
    lr.run.advance_to(730)
    d4 = [r for r in lr.run.records if r["kind"] == "D4"]
    assert d4 and d4[-1]["mission"] == "sar"
    v = view.screen(I, lr.run.moment())
    assert v["header"]["mission"] == "RESCUE" and v["header"]["priority_file"] == "sar.yaml"
    assert any(e["tag"] == "PRIORITY" and "sar.yaml" in e["msg"] for e in v["log"])
    assert lr.command({"cmd": "mission", "value": "nonsense"}) == "no priority file nonsense"


def test_a_profile_applied_at_sea_takes_effect_and_a_bad_one_is_refused():
    prof = dict(I.missions["sar"], id="sar_tiers", name="Rescue with tiers", shed_order={"coastal_connectivity": 1})
    lr = live.LiveReplay("sar", 600, running=False)
    assert lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": prof}}}) is None
    lr.run.advance_to(1150)
    shed = next(r for r in lr.run.records if r["kind"] == "D4" and r["verdict"] == "shed")
    assert shed["mission"] == "sar_tiers" and shed["steps"][0]["guest"] == "G5" and shed["steps"][0]["response"] == "shed_first_action"
    v = view.screen(I, lr.run.moment())
    assert v["header"]["priority_file"] == "sar_tiers · AT SEA" and v["header"]["mission"] == "RESCUE WITH TIERS"
    bad = dict(prof, id="bad_one", weights={"sar_air": 2})
    lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": bad}}})
    lr.run.advance_to(1152)
    row = next(e for e in view.screen(I, lr.run.moment())["log"] if e["tag"] == "PROFILE" and "bad_one" in e["msg"])
    assert row["msg"].startswith("Profile bad_one refused: weights.sar_air") and row["msg"].endswith("sar_tiers kept.")
    assert lr.mission == "sar_tiers"


def test_crew_level_before_minute_8_changes_the_r3_record():
    lr = live.LiveReplay("survey", 100, running=False)
    lr.command({"cmd": "input", "input": {"type": "crew_change", "payload": {"crew_aboard": 6}}})
    lr.run.advance_to(481)
    d5 = next(r for r in lr.run.records if r["kind"] == "D5")
    assert d5["crew_aboard"] == 6 and d5["verdict"] != "confirm"
    v = view.screen(I, lr.run.moment())
    assert v["header"]["crew"] == "CREW 6"
    assert any(e["tag"] == "CREW" and e["msg"] == "6 aboard." for e in v["log"])


def test_only_laptop_inputs_are_accepted():
    lr = live.LiveReplay("survey", 0, running=False)
    assert lr.command({"cmd": "input", "input": {"type": "genset_trip", "payload": {"genset": 2}}}).startswith("input 'genset_trip'")
    assert lr.command({"cmd": "input", "input": {"type": "crew_change"}}).startswith("input 'crew_change'")


def test_the_live_marks_and_compare(ref):
    marks = view.marks(ref.records("survey"))
    assert [(m["label"], m["t_s"]) for m in marks] == [("START", 0), ("G4 LOW BATT", 481), ("GEN 2 TRIP", 722), ("CHW P1 TRIP", 1142)]
    c = view.compare(I, 481, ("survey", "sar"), {f: ref.moment(f, 481) for f in ("survey", "sar")}, ref.records("survey"))
    diff = {d["k"]: (d["a"], d["b"]) for d in c["diff"]}
    assert diff["LEG"] == ("G3 PAUSED", "G3 ABORTED") and diff["RESERVED"] == ("--", "G4 35 kW")
