"""The governor's computers (DEC-56), the Deployment Reference Kit and its port upload (DEC-57), and the standby
board in lockstep."""
import copy
import json

import pytest

from sdv import kit as K
from sdv import loader as Ld
from sdv.loop import Loop, load_simulator, scripted_inputs

A = Ld.load_assumptions()


@pytest.mark.parametrize("loa,boards", [(20, 2), (25, 2), (26, 3), (50, 3), (60, 4), (70, 4), (76, 5)])
def test_two_boards_plus_one_per_started_25_m(loa, boards):
    a = copy.deepcopy(A)
    a["hull"]["loa_m"] = loa
    assert K.governor_boards(a) == boards


def test_the_60_m_hull_carries_four_boards_six_edge_nodes_two_ssds_and_a_binder():
    kinds = [d["kind"] for d in K.devices(A)]
    assert kinds.count("board") == 4 and kinds.count("edge") == 6 and kinds.count("ssd") == 2 and kinds.count("print") == 1
    roles = [d["role"] for d in K.devices(A) if d["kind"] == "board"]
    assert roles == ["primary", "standby", "zone_forward", "zone_aft"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("kit") / "kit"
    return out, K.build(out)


def test_the_kit_has_a_page_per_guest_and_a_verified_manifest(built):
    out, m = built
    paths = {f["path"] for f in m["files"]}
    assert {f"guests/G{i}.md" for i in range(1, 7)} <= paths
    assert {"INDEX.md", "governor/RUNBOOK.md", "vessel/config/assumptions.yaml", "vessel/docs/DEPLOYMENT.md"} <= paths
    assert K.verify(out) == []
    g4 = (out / "guests/G4.md").read_text()
    assert "land or ditch within 12 min" in g4 and "Troubleshooting" in g4 and "not supplied" in g4


def test_a_device_takes_its_site_part_when_the_kit_outgrows_its_share(built):
    _, m = built
    a = copy.deepcopy(A)
    a["governor"]["kit"]["share_gb"]["edge"] = m["bytes"] / 2e9          # half the kit
    plan = {d["id"]: d for d in K.place(a, m)}
    assert plan["board-1"]["holds"] == "full kit" and plan["ssd-1"]["holds"] == "full kit"
    ramp = plan["edge-stern_ramp"]
    assert ramp["holds"] == "stern_ramp part" and ramp["bytes"] < m["bytes"]
    g3 = next(f for f in m["files"] if f["path"] == "guests/G3.md")
    assert "stern_ramp" in g3["sites"]


def test_port_upload_installs_verifies_switches_and_rolls_back(built, tmp_path):
    out, _ = built
    root = tmp_path / "device"
    first = K.install(out, root)
    assert first["installed"] and first["slot"] == "slot_a" and first["rollback"] is None
    second = K.install(out, root)
    assert second["slot"] == "slot_b" and second["rollback"] == "slot_a"
    assert (root / "current").resolve().name == "slot_b"
    assert K.rollback(root) == "slot_a" and (root / "current").resolve().name == "slot_a"


def test_a_damaged_kit_is_refused_and_the_previous_kept(built, tmp_path):
    out, _ = built
    root = tmp_path / "device"
    K.install(out, root)
    bad = tmp_path / "bad"
    import shutil
    shutil.copytree(out, bad)
    (bad / "guests/G5.md").write_text("changed in transit")
    r = K.install(bad, root)
    assert not r["installed"] and r["kept"] == "slot_a" and "changed guests/G5.md" in r["problems"]
    assert (root / "current").resolve().name == "slot_a"


def test_the_standby_stays_in_step_through_scenario_b():
    loop = Loop(load_simulator(mission="sar"), "sar", inputs=scripted_inputs(), standby=True)
    outs = list(loop.ticks(until=1200))
    assert all(o.standby == "in step" for o in outs)


def test_a_standby_that_decides_differently_raises_out_of_step():
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=scripted_inputs(), standby=True)
    loop.standby[1].mission = loop.standby[1].missions["sar"]          # a standby on the wrong profile
    outs = list(loop.ticks(until=500))
    first = next(o for o in outs if o.standby != "in step")
    assert first.tick == 480 and "out of step at tick 480" in first.standby
