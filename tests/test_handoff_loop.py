"""Handoff items on the loop, the screen's laptop inputs, the CLI and the stub (docs/HANDOFF_SIDDHARTH.md #3, #15, #17,
#18, #21, the float frames, soak finding 8 and the stub gaps): the primary, the standby and a replay decide on the same
inputs, a safety request can be sent live, and an input off its contract is refused with the field named."""
import copy
import json
import sys
import threading
import time
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))
import sim_stub  # noqa: E402

from sdv import cli  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import loop as L  # noqa: E402
from sdv.loop import Loop, canonical, load_simulator, replay, scripted_inputs  # noqa: E402
from sdv.ui import data, live, server, view  # noqa: E402

I = data.Inputs()
MISSIONS = Ld.load_missions(Ld.load_cards())
SNAPSHOT = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/snapshot.schema.json").read_text()))
REQUESTS = "r3_hold_landing, g3_hold_depth, g2_stop_winch, g4_return_home"


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": True, "payload": payload}


def run(mission="survey", until=600, inputs=None, log_dir=None, standby=False):
    loop = Loop(load_simulator(mission=mission), mission, inputs=scripted_inputs() if inputs is None else inputs,
                log_dir=log_dir, standby=standby)
    outs = list(loop.ticks(until=until))
    loop.close()
    return loop, outs


def logged(d: Path, name: str) -> list[str]:
    return (d / f"{name}.jsonl").read_text().splitlines()


def replays_equal(d: Path, mission: str) -> bool:
    snaps, recs = replay(d, mission)
    return snaps == logged(d, "snapshots") and recs == logged(d, "decisions")


# ---------------------------------------------------------------------------------------------- #3 weights
@pytest.mark.parametrize("at,weights,until", [
    (0, {"sar_air": 0.24, "seabed_inspection": 0.2}, 600),           # soak finding 2: abort against pause at 480
    (1100, {"sar_air": 0.45, "coastal_connectivity": 0.35}, 1160),   # the handoff's repro: G4 against G5 at 1141
])
def test_a_profile_weight_off_the_tenth_decides_the_same_live_on_the_standby_and_in_replay(tmp_path, at, weights, until):
    """#3: the input log and the standby kept the weights to 0.1, so a juror's 0.24 was 0.2 everywhere but the primary."""
    prof = copy.deepcopy(MISSIONS["sar"])
    prof["id"], prof["name"] = "sar_jury", "Rescue jury"
    prof["weights"].update(weights)
    inputs = scripted_inputs()
    inputs.setdefault(at, []).append(inp(at, "profile_applied", profile=prof))
    _, outs = run("sar", until, inputs, tmp_path, standby=True)
    assert all(o.standby == "in step" for o in outs)
    assert replays_equal(tmp_path, "sar")
    applied = next(json.loads(l) for l in logged(tmp_path, "inputs") if '"profile_applied"' in l)
    assert applied["payload"]["profile"]["weights"] == prof["weights"]


def test_the_nominal_input_log_keeps_its_old_form_and_an_old_log_still_replays(tmp_path):
    """Logged unrounded, the scripted run's inputs are the canonical lines they always were, so an older log replays."""
    run("survey", 600, None, tmp_path)
    lines = logged(tmp_path, "inputs")
    assert lines == [canonical(json.loads(l)) for l in lines] and len(lines) == 1
    assert replays_equal(tmp_path, "survey")


# ---------------------------------------------------------------------------------------------- #17 #18 locks and timing
def test_an_input_added_during_a_tick_is_stamped_for_the_next_one(tmp_path):
    """#17: add_input waits for the tick in progress. Before, a swap sent mid-tick was stamped for that tick after its
    inputs were read, so it was never applied and never logged."""
    loop = Loop(load_simulator(), "survey", inputs={}, log_dir=tmp_path)
    for _ in range(10):
        loop.step()
    step, box = loop.sim.step, {}

    def step_with_a_swap(n, commands, inputs):
        if n == 10:
            th = threading.Thread(target=lambda: box.setdefault("t", loop.add_input(
                {"type": "priority_swap", "injected": False, "payload": {"mission": "sar"}})))
            th.start()
            th.join(0.2)
            box["th"] = th
        return step(n, commands, inputs)

    loop.sim.step = step_with_a_swap
    loop.step()
    box["th"].join(5)
    for _ in range(3):
        loop.step()
    loop.close()
    assert box["t"] == 11 and loop.core.mission["id"] == "sar"
    assert [(i["t_s"], i["type"]) for i in map(json.loads, logged(tmp_path, "inputs"))] == [(11, "priority_swap")]


def test_a_safety_request_waiting_for_the_tick_counts_its_wait():
    """#18: the 200 ms counts from the request. A request held 60 ms by the tick in progress logged 0.08 ms."""
    loop = Loop(load_simulator(), "survey", inputs={})
    for _ in range(5):
        loop.step()
    loop.lock.acquire()
    th = threading.Thread(target=loop.safety, args=("g3_hold_depth",))
    th.start()
    time.sleep(0.06)
    loop.lock.release()
    th.join(5)
    row = loop.core.timing[-1]
    assert row["kind"] == "safety" and row["latency_ms"] >= 50


# ---------------------------------------------------------------------------------------------- #21 run.mission
def test_the_snapshot_names_the_priority_file_in_force(tmp_path):
    """#21: after a swap (or a profile applied at sea) the snapshot's run.mission follows the core, from the next tick."""
    prof = dict(copy.deepcopy(MISSIONS["sar"]), id="sar_jury", name="Rescue jury")
    inputs = {10: [inp(10, "priority_swap", mission="sar")], 15: [inp(15, "profile_applied", profile=prof)]}
    _, outs = run("survey", 20, inputs, tmp_path, standby=True)
    assert [o.snapshot["run"]["mission"] for o in outs[9:18]] == ["survey"] * 2 + ["sar"] * 5 + ["sar_jury"] * 2
    assert all(o.standby == "in step" for o in outs)
    assert replays_equal(tmp_path, "survey")


# ---------------------------------------------------------------------------------------------- float frames
def test_the_primary_decides_on_the_frame_the_log_holds(tmp_path):
    """A whole-number float (crew_aboard 6.0, a metered 45.0 kW) reached the primary as a float and the standby and the
    replay as an integer. The primary now reads the logged frame, so all three see one snapshot, not just one log line."""
    loop = Loop(load_simulator(), "survey", inputs={20: [inp(20, "crew_change", crew_aboard=6.0, people_available=4)]},
                log_dir=tmp_path, standby=True)
    seen, est_step = [], loop.est.step
    loop.est.step = lambda f: (seen.append(json.dumps(f, sort_keys=True, separators=(",", ":"))), est_step(f))[1]
    live_snaps = [json.dumps(o.snapshot, sort_keys=True) for o in loop.ticks(until=60)]
    loop.close()
    assert seen == logged(tmp_path, "frames")
    frames = [json.loads(l) for l in logged(tmp_path, "frames")]
    ins = {}
    for i in map(json.loads, logged(tmp_path, "inputs")):
        ins.setdefault(i["t_s"], []).append(i)
    again = Loop(L._Replay(frames), "survey", inputs=ins)
    assert [json.dumps(o.snapshot, sort_keys=True) for o in again.ticks(until=60)] == live_snaps
    assert loop.standby_state == "in step"


# ---------------------------------------------------------------------------------------------- #15 safety requests
def safety(request):
    return {"cmd": "input", "input": {"type": "safety_request", "payload": {"request": request}}}


def test_a_safety_request_from_the_screen_is_answered_at_once_and_replayed(tmp_path):
    """#15: the screen sends a 200 ms request, the core answers from the table of the last tick, the record shows at
    once, a re-run after a jump back answers it again, and sdv replay reports the log equal."""
    logs = live.RunLogs(tmp_path)
    lr = live.LiveReplay("survey", 300, running=False, logs=logs)
    assert lr.command(safety("g3_hold_depth")) is None
    rec = lr.run.records[-1]
    assert (rec["kind"], rec["tick"], rec["safety_request"], rec["verdict"]) == ("safety", 300, "g3_hold_depth", "sent")
    assert rec["seq"] in lr.run.timing
    assert view.screen(I, lr.run.moment())["header"]
    lr.run.advance_to(320)
    first = [canonical(r) for r in lr.run.records if r["tick"] <= 310]
    lr.command({"cmd": "jump", "t": 310})
    assert [canonical(r) for r in lr.run.records] == first
    lr.close()
    assert cli.main(["replay", str(tmp_path / "live-survey-1"), "--mission", "survey"]) == 0


def test_an_unknown_safety_request_is_refused_with_a_message_and_not_stamped():
    lr = live.LiveReplay("survey", 300, running=False)
    n = len(lr.run.records)
    reason = lr.command(safety("abandon_ship"))
    assert reason == f"input 'safety_request' refused: request 'abandon_ship' is not one of {REQUESTS}"
    assert lr.run.laptop == {} and len(lr.run.records) == n
    live_server = server.Live(I, "survey", 300, running=False)
    assert live_server.command(safety("abandon_ship")).startswith("input 'safety_request' refused: request")
    live_server.close()


def test_sdv_run_sends_a_safety_request_and_the_replay_is_equal(tmp_path, capsys):
    d = tmp_path / "run"
    assert cli.main(["run", "--until", "400", "--safety", "300:g3_hold_depth", "--log-dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "05:00  safety SENT" in out
    assert any(json.loads(l)["type"] == "safety_request" for l in logged(d, "inputs"))
    assert cli.main(["replay", str(d)]) == 0
    assert capsys.readouterr().out.startswith("REPLAY EQUAL 401 snapshots")
    assert cli.main(["run", "--until", "10", "--safety", "5:abandon_ship"]) == 2
    assert capsys.readouterr().out == f"refused: no safety request 'abandon_ship' ({REQUESTS})\n"
    assert cli.main(["run", "--until", "10", "--safety", "soon:g3_hold_depth"]) == 2
    assert capsys.readouterr().out == "refused: safety request tick 'soon' is not a tick (0 or more)\n"
    assert cli.main(["run", "--until", "10", "--safety", "20:g3_hold_depth"]) == 2
    assert capsys.readouterr().out == "refused: safety request tick 20 is after the last tick 10\n"


# ---------------------------------------------------------------------------------------------- soak 8: the input contract
@pytest.mark.parametrize("type_,payload,reason", [
    ("feed_drop", {"feed": "nav"}, "until_t_s is missing"),
    ("feed_drop", {"feed": "radar", "until_t_s": None}, "feed 'radar' is not one of pms, chw, nav"),
    ("deck_report", {"deck": "wet"}, "deck 'wet' is not one of clear, not_clear"),
    ("deck_report", {"deck": "clear", "colour": "red"}, "colour is not in the contract"),
    ("emission_change", {"emission": "loud"}, "emission 'loud' is not one of normal, silent"),
    ("genset_trip", {"genset": "2", "confirmed": True}, "genset '2' is not one of 1, 2"),
    ("genset_trip", {"genset": True, "confirmed": True}, "genset is true or false, not one of 1, 2"),
    ("bridge_answer", {"request_seq": 1, "answer": "maybe"}, "answer 'maybe' is not one of confirmed, denied"),
    ("bridge_answer", {"request_seq": "one", "answer": "denied"}, "request_seq 'one' is not a whole number"),
    ("crew_change", {"crew_aboard": 1}, "crew_aboard 1 is not one of 14, 6, 0"),
    ("crew_change", {"crew_aboard": 7}, "crew_aboard 7 is not one of 14, 6, 0"),
    ("crew_change", {"crew_aboard": None}, "crew_aboard is empty, not one of 14, 6, 0"),
    ("deck_report", {"deck": "clear", "wind_kn": "calm"}, "wind_kn 'calm' is not a number"),
    ("deck_report", {"deck": "clear", "wind_kn": float("nan")}, "wind_kn nan is not a number"),
    ("genset_trip", {"genset": 2}, "confirmed is missing"),
    ("guest_overconsumption", {"guest": "G9", "overdraw_pct": 10}, "guest 'G9' is not one of G1"),
    ("guest_report", {"guest": "G4", "fields": {}}, "guest_report is not a laptop input"),
])
def test_a_laptop_input_off_its_contract_is_refused_naming_the_field(type_, payload, reason):
    """Soak finding 8: an off-contract input reached the simulator and the estimator and broke the snapshot or the run."""
    loop = Loop(load_simulator(), "survey", inputs={})
    loop.step()
    with pytest.raises(ValueError) as e:
        loop.add_input({"type": type_, "injected": True, "payload": payload})
    msg = str(e.value)
    assert msg.startswith(f"input {type_!r} refused: ") and reason in msg
    assert ";" not in msg and msg.count(":") == 1
    assert loop.inputs == {}


def test_the_screen_refuses_an_off_contract_input_with_the_field_named():
    lr = live.LiveReplay("survey", 100, running=False)

    def send(type_, **payload):
        return lr.command({"cmd": "input", "input": {"type": type_, "payload": payload}})

    assert send("crew_change", crew_aboard=7) == "input 'crew_change' refused: crew_aboard 7 is not one of 14, 6, 0"
    assert send("deck_report", deck="wet") == "input 'deck_report' refused: deck 'wet' is not one of clear, not_clear"
    assert send("bridge_answer", request_seq=1, answer="maybe").endswith("answer 'maybe' is not one of confirmed, denied")
    assert lr.run.laptop == {}
    assert send("crew_change", crew_aboard=6.0) is None                 # a whole number sent as 6.0 is the level 6
    assert lr.run.laptop[101][0]["payload"] == {"crew_aboard": 6}
    assert type(lr.run.laptop[101][0]["payload"]["crew_aboard"]) is int


def test_a_feed_drop_on_its_contract_keeps_the_snapshot_valid():
    """A feed_drop with until_t_s null (until further notice) is the contract's form: the snapshot echoing it validates."""
    loop = Loop(load_simulator(), "survey", inputs={})
    for _ in range(100):
        loop.step()
    assert loop.add_input({"type": "feed_drop", "injected": True, "payload": {"feed": "nav", "until_t_s": None}}) == 100
    out = loop.step()
    assert out.snapshot["events"] and not list(SNAPSHOT.iter_errors(out.snapshot))


# ---------------------------------------------------------------------------------------------- stub gaps
def test_the_stub_ignores_an_answer_with_no_open_request_and_refuses_a_deck_nobody_can_clear():
    """Already in the stub: a bridge answer to no open request is logged and ignored, and clear_deck at 6 aboard runs
    on A.6's 8 to 12 minutes while at 0 aboard it is refused."""
    _, outs = run("survey", 60, {50: [inp(50, "bridge_answer", request_seq=7, answer="confirmed")]})
    assert outs[-1].snapshot["crew"]["bridge_requests"]["value"] == []
    sims = {}
    for crew in (6, 0):
        sims[crew] = sim = sim_stub.Simulator()
        sim.step(0, [], [])
        sim.v["crew_aboard"] = crew
        sim.apply_command({"kind": "clear_deck", "args": {"zone": "flight_deck"}}, 5)
        sim.step(6, [], [])
    assert sims[6].tr["deck_flight_deck"].t_end == 5 + 600 and not sims[6].refused
    assert "deck_flight_deck" not in sims[0].tr and sims[0].refused[-1]["t_s"] == 5


def test_the_stub_takes_a_genset_restart_and_a_guest_request():
    """Both are laptop inputs in the contract. The stub raised NotImplementedError. A restart brings genset 2 back at
    its expected end (fault_signatures.genset_restart), and a guest request only reaches the core through the frame."""
    inputs = scripted_inputs()
    inputs[100] = [inp(100, "guest_request", guest="G3", mode="charging", kw=25, interruptible=True)]
    inputs[800] = [inp(800, "genset_restart", genset=2, expected_end_t_s=900)]
    loop, outs = run("survey", 960, inputs, standby=True)
    assert any(e["type"] == "guest_request" for e in outs[100].frame["events"])
    sig = {t: outs[t].frame["signals"] for t in (799, 850, 900)}
    assert sig[799]["genset_2_relay_trip"]["value"] is True and sig[799]["genset_2_kw"]["value"] == 0
    assert sig[850]["genset_2_relay_trip"]["value"] is False and sig[850]["bus_frequency_hz"]["value"] == 60
    assert sig[850]["genset_2_kw"]["value"] == 0
    assert sig[900]["genset_2_kw"]["value"] == sig[900]["genset_1_kw"]["value"] > 0
    assert all(o.standby == "in step" for o in outs)
    for o in outs[95:105] + outs[795:905]:
        assert not list(SNAPSHOT.iter_errors(o.snapshot)), o.tick
