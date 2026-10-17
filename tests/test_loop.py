"""The loop with the live core: its decisions send exactly the commands the Scenario B script pins, so the frames
equal the scripted run's byte for byte; every record validates; a replay from the logs reproduces every snapshot
and record; ship time never depends on wall time."""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))
import sim_stub  # noqa: E402

from sdv import loader as Ld  # noqa: E402
from sdv.loop import Loop, canonical, first_difference, load_simulator, replay, scripted_inputs  # noqa: E402

RECORD = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))


def live(mission, tmp=None, horizon=1200, variant="default", inputs=None):
    loop = Loop(load_simulator(mission=mission, variant=variant), mission, variant,
                inputs=scripted_inputs() if inputs is None else inputs, log_dir=tmp)
    outs = list(loop.ticks(until=horizon))
    loop.close()
    return loop, outs


@pytest.fixture(scope="module", params=["survey", "sar"])
def run(request, tmp_path_factory):
    tmp = tmp_path_factory.mktemp(request.param)
    loop, outs = live(request.param, tmp)
    return request.param, loop, outs, tmp


def test_the_core_sends_the_scripted_commands(run):
    mission, _, outs, _ = run
    live_cmds = {o.tick: [{k: c[k] for k in ("kind", "args")} for c in o.commands] for o in outs if o.commands}
    script = {t: [{k: c[k] for k in ("kind", "args")} for c in sim_stub.script_commands(t, mission)]
              for t in range(1201) if sim_stub.script_commands(t, mission)}
    assert live_cmds == script


def test_the_frames_equal_the_scripted_run(run):
    mission, _, outs, _ = run
    ref = [canonical(f) for f in sim_stub.frames(mission=mission)]
    assert [canonical(o.frame) for o in outs] == ref


EXPECTED = {
    "survey": [(480, "D3", "proceeds"), (480, "D5", "confirm"), (540, "D5", "cleared"), (721, "D4", "hold"),
               (1141, "D4", "shed"), (1142, "D4", "hold")],
    "sar": [(480, "D3", "proceeds"), (480, "D5", "confirm"), (540, "D5", "cleared"), (721, "D4", "hold"),
            (1141, "D4", "shed"), (1142, "D4", "hold")],
}


def test_the_records_and_their_sentences(run):
    mission, loop, outs, _ = run
    recs = [r for o in outs for r in o.records]
    assert [(r["tick"], r["kind"], r["verdict"]) for r in recs] == EXPECTED[mission]
    assert [r["seq"] for r in recs] == list(range(1, len(recs) + 1))
    for r in recs:
        assert not list(RECORD.iter_errors(r)), r["kind"]
        assert ";" not in r["sentence"]
    shed = next(r for r in recs if r["verdict"] == "shed")
    assert shed["steps"][0]["guest"] == ("G4" if mission == "survey" else "G5")
    assert shed["confirmed_t_s"] == 1141 and shed["first_shed_due_t_s"] == 1145 and shed["applies_at_tick"] == 1142


def test_every_command_carries_the_record_that_sent_it(run):
    _, _, outs, _ = run
    seqs = {r["seq"] for o in outs for r in o.records}
    assert all(c["seq"] in seqs for o in outs for c in o.commands)


def test_the_timing_log_is_inside_every_ceiling(run):
    _, loop, _, _ = run
    assert loop.core.timing and all(t["latency_ms"] < t["ceiling_ms"] for t in loop.core.timing)
    ticks = sorted(w["compute_ms"] for w in loop.wall)
    assert ticks[int(0.99 * len(ticks))] < 1000 / 12                     # one tick at x12 pacing; overruns are logged, not fatal


def test_a_replay_from_the_logs_reproduces_every_snapshot_and_record(run):
    mission, _, _, tmp = run
    snaps = (tmp / "snapshots.jsonl").read_text().splitlines()
    recs = (tmp / "decisions.jsonl").read_text().splitlines()
    again_snaps, again_recs = replay(tmp, mission)
    assert first_difference(snaps, again_snaps) is None
    assert first_difference(recs, again_recs) is None


def test_first_difference_names_the_field():
    a = [canonical({"x": {"y": 1}})]
    b = [canonical({"x": {"y": 2}})]
    assert first_difference(a, b) == "line 0: .x.y: 1 against 2"


def test_a_late_bridge_answer_counts_as_no():
    loop, outs = live("survey", horizon=600, inputs={})
    recs = [r for o in outs for r in o.records]
    held = next(r for r in recs if r["kind"] == "D5" and r["verdict"] == "held")
    assert held["tick"] == 541 and "no answer" in held["sentence"]
    assert not any(c["kind"] == "clear_deck" for o in outs for c in o.commands)


def test_crew0_recovers_automatically_on_the_latch():
    orig = sim_stub.SCRIPT["inputs"]
    loop, outs = live("survey", variant="crew0", horizon=1200, inputs={})
    d5 = next(r for o in outs for r in o.records if r["kind"] == "D5")
    assert d5["verdict"] == "automatic" and d5["tick"] == 480
    cmds = [(o.tick, c["kind"]) for o in outs for c in o.commands]
    assert (480, "ship_state") in cmds and not any(k in ("bridge_request", "clear_deck") for _, k in cmds)
    sim_stub.SCRIPT["inputs"] = {}
    try:
        ref = [canonical(f) for f in sim_stub.frames(mission="survey", variant="crew0", cmd_hook=sim_stub.crew0_hook)]
    finally:
        sim_stub.SCRIPT["inputs"] = orig
    assert [canonical(o.frame) for o in outs][:1080] == ref[:1080]


def test_a_priority_swap_changes_the_file_for_later_decisions():
    inputs = scripted_inputs()
    inputs.setdefault(300, []).append({"t_s": 300, "type": "priority_swap", "injected": False, "payload": {"mission": "sar"}})
    loop, outs = live("survey", horizon=500, inputs=inputs)
    d3 = next(r for o in outs for r in o.records if r["kind"] == "D3")
    assert d3["mission"] == "sar" and d3["cost_to_loser"]["open_ended"]
