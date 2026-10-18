"""Fixes from the post-freeze engine review (Sat 22:59), on the estimator, the safety table and the kit."""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import kit as K  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import safety as Sf  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.loop import Loop, load_simulator, replay, scripted_inputs  # noqa: E402

CARDS = Ld.load_cards(vocab=Ld.load_vocabulary(assumptions=Ld.load_assumptions()))
MISSIONS = Ld.load_missions(CARDS, Ld.load_vocabulary(assumptions=Ld.load_assumptions()))
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": True, "payload": payload}


def run(mission="survey", until=600, inputs=None, log_dir=None, standby=False):
    loop = Loop(load_simulator(mission=mission), mission, inputs=inputs if inputs is not None else scripted_inputs(),
                log_dir=log_dir, standby=standby)
    outs = list(loop.ticks(until=until))
    loop.close()
    return loop, outs


def test_a_guest_feed_drop_keeps_the_standby_in_step_and_replay_equal(tmp_path):
    """#4: a fallback value read live as 35.0 and back from the log as 35 must not look like a change on one side."""
    inputs = scripted_inputs()
    inputs.setdefault(1130, []).append(inp(1130, "feed_drop", feed="guest_meter", until_t_s=1150))
    _, outs = run(until=1160, inputs=inputs, log_dir=tmp_path, standby=True)
    assert all(o.standby == "in step" for o in outs)
    snaps, _ = replay(tmp_path, "survey")
    assert snaps == (tmp_path / "snapshots.jsonl").read_text().splitlines()


def test_a_crew_level_outside_its_values_is_refused_and_the_run_goes_on():
    """#10: crew 10 is not 14, 6 or 0: counted as missing, never a crash."""
    loop, outs = run(until=60, inputs={5: [inp(5, "crew_change", crew_aboard=10, people_available=4)]})
    assert any("crew_aboard" in m and "outside" in m for m in loop.est.log)
    assert outs[-1].snapshot["crew"]["crew_aboard"]["value"] in (14, 6, 0)


@pytest.mark.parametrize("feed", ["comms", "public_data"])
def test_a_feed_dropped_from_tick_0_takes_its_fallback(feed):
    """#11: a signal never heard is unknown, and unknown takes the conservative value instead of crashing."""
    _, outs = run(until=10, inputs={0: [inp(0, "feed_drop", feed=feed, until_t_s=None)]})
    s = outs[-1].snapshot
    if feed == "comms":
        assert s["links"]["satcom_mbps"]["stale"] and s["capacity"]["satcom"]["value"]["capacity"] == 0
    else:
        assert s["environment"]["seawater_c"]["value"] == 30 and s["environment"]["seawater_c"]["stale"]


def test_crew_answers_expire_and_a_crew_change_voids_the_standing_plan():
    """#12: a clear deck report lasts 300 s, the landing officer's wind 120 s, a standing plan 5400 s or until the
    crew level changes after it."""
    inputs = {10: [inp(10, "standing_plan", state="approved")],
              20: [inp(20, "crew_change", crew_aboard=6, people_available=4)],
              100: [inp(100, "deck_report", deck="clear", wind_kn=20)]}
    _, outs = run(until=460, inputs=inputs)
    assert outs[15].snapshot["crew"]["standing_plan"]["value"] == "approved"
    assert outs[25].snapshot["crew"]["standing_plan"]["value"] == "none"
    assert "crew level changed" in outs[25].snapshot["crew"]["standing_plan"]["substituted"]["rule"]
    assert outs[350].snapshot["crew"]["hlo_deck_report"]["value"] == "clear"
    assert outs[401].snapshot["crew"]["hlo_deck_report"]["value"] == "not_clear"
    assert outs[221].snapshot["crew"]["hlo_wind_kn"]["value"] is None


def test_a_stale_genset_feed_under_overload_sheds_nothing():
    """The old stale-feed check passed at any load; this one is over the limit, so only the stale feed stops D4."""
    _, outs = run(until=600, inputs={597: [inp(597, "feed_drop", feed="pms", until_t_s=None)]})
    s = copy.deepcopy(outs[600].snapshot)
    for g, mode, kw in (("G3", "charging", 25.0), ("G4", "fast_charge", 35.0), ("G5", "full", 45.0)):
        s["guests"][g]["mode"]["value"], s["guests"][g]["kw_actual"]["value"] = mode, kw
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["load_kw"] > d["limit_kw"] and d["verdict"] == "unconfirmed" and d["steps"] == []


def test_a_winch_stop_with_the_winch_already_off_is_not_needed():
    """#19: an activity of winch with the mode already sampling sends no no-op command."""
    snap = copy.deepcopy(SNAP["scenario_b_survey_m00"])
    snap["run"]["installed"] = ["G2", "G3", "G4", "G5"]
    snap["guests"]["G2"] = {"mode": {"value": "sampling"}, "activity": {"value": "winch"}}
    row = Sf.table(CARDS, snap, [], None, False)["g2_stop_winch"]
    assert row["state"] == "not_needed" and row["commands"] == []
    snap["guests"]["G2"]["mode"]["value"] = "winch"
    assert Sf.table(CARDS, snap, [], None, False)["g2_stop_winch"]["state"] == "ready"


def test_safety_reasons_read_as_one_sentence():
    """#20: no second colon inside a reason, activities in words."""
    snap = copy.deepcopy(SNAP["scenario_b_survey_m00"])
    snap["links"]["acoustic_link_up"]["value"] = False
    rows = Sf.table(CARDS, snap, [], None, False)
    assert all(":" not in r["reason"] and "_" not in r["reason"] for r in rows.values())


@pytest.fixture()
def kit(tmp_path):
    out = tmp_path / "kit"
    K.build(out)
    return out


def test_kit_build_refuses_a_folder_that_is_not_a_kit(tmp_path, kit):
    """#13: building into a folder of someone else's files must not delete them."""
    other = tmp_path / "thesis"
    other.mkdir()
    (other / "my_thesis.txt").write_text("keep me")
    with pytest.raises(ValueError):
        K.build(other)
    assert (other / "my_thesis.txt").read_text() == "keep me"
    K.build(kit)                                      # rebuilding an existing kit is fine


def test_a_refused_install_keeps_both_slots_and_the_rollback(tmp_path, kit):
    """#14: two good installs, then a damaged kit and a kit with no manifest: both refused, nothing lost."""
    root = tmp_path / "device"
    assert K.install(kit, root)["slot"] == "slot_a"
    assert K.install(kit, root)["slot"] == "slot_b"
    bad = tmp_path / "bad"
    shutil.copytree(kit, bad)
    (bad / "guests/G5.md").write_text("changed in transit")
    r = K.install(bad, root)
    assert not r["installed"] and r["kept"] == "slot_b"
    nomani = tmp_path / "nomanifest"
    shutil.copytree(kit, nomani)
    (nomani / "manifest.json").unlink()
    r = K.install(nomani, root)
    assert not r["installed"] and "manifest" in r["problems"][0]
    assert (root / "slot_a").exists() and (root / "slot_b").exists()
    assert K.rollback(root) == "slot_a"
