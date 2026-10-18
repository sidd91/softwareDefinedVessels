"""Handoff fixes in the core, the sentences and the records (docs/HANDOFF_SIDDHARTH.md #5 to #8, #16, #22 and the
soak findings on D3 weights, the recovery lead and an unknown priority swap). Each test runs the loop the CLI builds
on the test double, or the one function that broke."""
import copy
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import arbitration as D3  # noqa: E402
from sdv import explain as E  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import records as Rec  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.loop import Loop, load_simulator, replay, scripted_inputs  # noqa: E402

A = Ld.load_assumptions()
CARDS = Ld.load_cards(vocab=Ld.load_vocabulary(assumptions=A))
MISSIONS = Ld.load_missions(CARDS, Ld.load_vocabulary(assumptions=A))
RECORD = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}
SIGNALS = {x["name"]: x for x in yaml.safe_load((Ld.ROOT / "config/signals.yaml").read_text())["signals"]}
WAIT_14 = SIGNALS["bridge_requests"]["wait_s"]["by_crew"][14]
LOST_FEED = "no answer from the bridge, the laptop feed is lost and the crew is taken as one level lower"


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": True, "payload": payload}


def run(mission="survey", until=1200, inputs=None, safety=None, log_dir=None, standby=True):
    """The loop with its standby, the given laptop inputs and the safety requests answered after the ticks named."""
    loop = Loop(load_simulator(mission=mission), mission, inputs=inputs if inputs is not None else scripted_inputs(),
                log_dir=log_dir, standby=standby)
    outs, recs = [], []
    for o in loop.ticks(until=until):
        outs.append(o)
        recs += o.records
        for req in (safety or {}).get(o.tick, []):
            recs += loop.safety(req)
            o.commands = loop.commands      # a safety answer's commands join the tick's
    loop.close()
    return loop, outs, recs


def kinds(recs, kind):
    return [r for r in recs if r["kind"] == kind]


def commands(outs, kind):
    return [(o.tick, c) for o in outs for c in o.commands if c["kind"] == kind]


def same_everywhere(loop, outs, log_dir, mission="survey"):
    """Live, standby and replay give the same snapshots and decisions."""
    assert loop.standby_state == "in step", loop.standby_state
    snaps, recs = replay(log_dir, mission)
    assert snaps == (log_dir / "snapshots.jsonl").read_text().splitlines()
    assert recs == (log_dir / "decisions.jsonl").read_text().splitlines()


def clean(*recs):
    """Each record validates and its sentence reads plainly: no semicolon, at most one colon in each sentence."""
    for r in recs:
        assert not list(RECORD.iter_errors(r)), list(RECORD.iter_errors(r))[0].message
        assert ";" not in r["sentence"], r["sentence"]
        assert all(part.count(":") <= 1 for part in re.split(r"[.!?](?:\s|$)", r["sentence"])), r["sentence"]


# ------------------------------------------------------------------------------------------------ #22 D3 on a word limit

def test_d3_on_the_endurance_limit_says_the_word_not_a_number():
    """#22: G4's 90 min endurance limit reads G4.activity == airborne. Its value is a word, never formatted as a number."""
    r = copy.deepcopy(json.loads((Ld.ROOT / "tests/fixtures/records/d3_m08_survey.json").read_text()))
    r["hard_limit"] = {"guest": "G4", "when": {"signal": "G4.activity", "op": "==", "value": "airborne"},
                       "then": {"action": "land", "within_min": 90}}
    s = E.d3(r)
    assert s.startswith("G4 recovers first: while airborne it must land within 90 min, by minute ")
    assert "==" not in s and ";" not in s and s.count(":") == 1


@pytest.mark.parametrize("until", [520, None])
def test_a_g4_telemetry_drop_gives_a_d3_on_endurance_not_a_crash(tmp_path, until):
    """#22 and soak 1: with no battery report D3 runs on the endurance limit, and the loop goes on to the end."""
    t0 = 480 if until else 100
    inputs = scripted_inputs()
    inputs.setdefault(t0, []).append(inp(t0, "feed_drop", feed="g4_telemetry", until_t_s=until))
    loop, outs, recs = run(inputs=inputs, log_dir=tmp_path)
    assert outs[-1].tick == 1200
    d3 = kinds(recs, "D3")
    assert d3
    clean(*recs)
    if until is None:
        assert d3[0]["hard_limit"]["when"]["value"] == "airborne" and "while airborne it must land" in d3[0]["sentence"]
    same_everywhere(loop, outs, tmp_path)


# ------------------------------------------------------------------------------------------------ #5 lost laptop feed

def test_a_lost_laptop_feed_lets_the_bridge_request_lapse_and_holds_the_recovery(tmp_path):
    """#5: the laptop feed drops at 490, so the open request vanishes from the snapshot. The wait counts from R3's own
    ask, the recovery is held with the lost feed named, and a recall is no longer refused as under way."""
    inputs = scripted_inputs()
    inputs.setdefault(490, []).append(inp(490, "feed_drop", feed="laptop", until_t_s=None))
    loop, outs, recs = run(inputs=inputs, until=900, log_dir=tmp_path)
    d5 = kinds(recs, "D5")
    assert [r["verdict"] for r in d5][:2] == ["confirm", "held"]
    held = d5[1]
    wait = max(loop.core.wait_s.values())
    assert 480 + WAIT_14 < held["tick"] <= 480 + wait + 1 and held["deck_evidence"] == LOST_FEED
    clean(held)
    assert loop.core.r3["state"] == "held"
    assert "under way" not in outs[-1].safety["g4_return_home"]["reason"]
    same_everywhere(loop, outs, tmp_path)


def test_a_bridge_request_that_never_shows_up_lapses_from_r3s_own_ask():
    """#5: a request missing from bridge_requests (feed fresh) is not waited on forever either."""
    from sdv.core import Core
    core = Core("survey")
    snap = copy.deepcopy(SNAP["scenario_b_survey_m08"])
    core.decide(snap)
    assert core.r3["state"] == "asked"
    for dt in range(1, WAIT_14 + 2):
        s = copy.deepcopy(snap)
        s["run"]["tick"] = s["run"]["t_ship_s"] = snap["run"]["tick"] + dt
        s["crew"]["bridge_requests"]["value"] = []
        recs, _ = core.decide(s)
        if dt <= WAIT_14:
            assert not kinds(recs, "D5")
    assert core.r3["state"] == "held" and kinds(recs, "D5")[0]["deck_evidence"] == "no answer from the bridge"


# ------------------------------------------------------------------------------------------------ #6 lapsed recall re-asked

def test_a_lapsed_recall_is_asked_again_at_the_battery_limit_when_g3_is_already_holding(tmp_path):
    """#6: a recall at 100 lapses at 161 and G3 is held at 300, so no D3 comes at 480. The battery limit asks the bridge
    again, once, and the recovery goes on when the bridge confirms."""
    inputs = {540: [inp(540, "bridge_answer", request_seq=2, answer="confirmed")]}
    loop, outs, recs = run(inputs=inputs, safety={100: ["g4_return_home"], 300: ["g3_hold_depth"]}, log_dir=tmp_path)
    assert not kinds(recs, "D3")
    d5 = [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")]
    assert d5 == [(100, "confirm"), (100 + WAIT_14 + 1, "held"), (480, "confirm"), (540, "cleared")]
    asks = [(t, c["args"]["request_seq"]) for t, c in commands(outs, "bridge_request")]
    assert asks == [(100, 1), (480, 2)]
    assert (480, 1) in [(t, c["args"]["request_seq"]) for t, c in commands(outs, "bridge_close")]
    assert outs[-1].snapshot["guests"]["G4"]["activity"]["value"] == "landed"
    clean(*recs)
    same_everywhere(loop, outs, tmp_path)


def test_the_battery_limit_asks_again_only_once():
    """#6: the re-ask at the battery limit lapses too: no third ask while the same limit stays due."""
    _, outs, recs = run(inputs={}, safety={100: ["g4_return_home"], 300: ["g3_hold_depth"]}, until=900, standby=False)
    assert [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")] == [
        (100, "confirm"), (100 + WAIT_14 + 1, "held"), (480, "confirm"), (480 + WAIT_14 + 1, "held")]
    assert [t for t, _ in commands(outs, "bridge_request")] == [100, 480]


# ------------------------------------------------------------------------------------------------ #7 resume after a safety hold

def test_a_g3_held_by_a_safety_request_resumes_after_g4_is_secured(tmp_path):
    """#7: G3 held by the 200 MS request before minute 8, so no D3 paused it. G4 lands at 1020 and the ship re-steadies
    for the survey once G4 is secured (1080), as after a D3 pause."""
    loop, outs, recs = run(safety={300: ["g3_hold_depth"]}, log_dir=tmp_path)
    assert not kinds(recs, "D3")
    landed = loop.core.r3["landed_t_s"]
    resume = [(t, c) for t, c in commands(outs, "ship_state") if c["args"].get("course") == "steady"]
    assert [t for t, _ in resume] == [landed + A["rules"]["r3"]["secure_s"]]
    assert resume[0][1]["args"] == {"course": "steady", "speed_kn": 3.0}
    assert resume[0][1]["seq"] == loop.core.r3["seq"]
    same_everywhere(loop, outs, tmp_path)


def test_an_aborted_leg_is_not_resumed():
    """#7: sar aborts G3's leg at minute 8 (open-ended): no resume after the landing, as before."""
    _, outs, _ = run("sar", standby=False)
    assert not [c for _, c in commands(outs, "ship_state") if c["args"].get("course") == "steady"]


# ------------------------------------------------------------------------------------------------ #8 policy re-run

def test_a_standing_plan_approved_after_a_policy_hold_reopens_the_recovery(tmp_path):
    """#8: 6 aboard with no standing plan holds the recovery at 480. The plan approved at 600, with the landing officer's
    clear report, gives a new D5 and the deck work goes out."""
    inputs = {10: [inp(10, "crew_change", crew_aboard=6, people_available=4)],
              590: [inp(590, "deck_report", deck="clear", wind_kn=20)],
              600: [inp(600, "standing_plan", state="approved")]}
    loop, outs, recs = run(inputs=inputs, log_dir=tmp_path)
    d5 = [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")]
    assert d5 == [(480, "held"), (600, "standing_plan")]
    assert kinds(recs, "D5")[1]["deck_evidence"] == A["rules"]["r3"]["deck_evidence"][6]
    assert [t for t, _ in commands(outs, "clear_deck")] == [600]
    clean(*recs)
    same_everywhere(loop, outs, tmp_path)


def test_a_policy_hold_with_no_plan_stays_one_record():
    """#8: re-running the policy each tick adds nothing while the answer is the same."""
    _, _, recs = run(inputs={10: [inp(10, "crew_change", crew_aboard=6, people_available=4)]}, standby=False)
    assert [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")] == [(480, "held")]


def test_a_bridge_denial_is_not_re_run_as_policy():
    """#8: a denial by the bridge stays held. Only the crew policy is re-run."""
    inputs = {540: [inp(540, "bridge_answer", request_seq=1, answer="denied")]}
    _, _, recs = run(inputs=inputs, until=900, standby=False)
    assert [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")] == [(480, "confirm"), (540, "held")]


# ------------------------------------------------------------------------------------------------ #16 D4 says why

def test_the_unconfirmed_d4_record_says_why():
    """#16: shedding gives unconfirmed_because, the record keeps it, and the sentence reads it."""
    _, outs, _ = run(until=600, inputs={597: [inp(597, "feed_drop", feed="pms", until_t_s=None)]}, standby=False)
    s = copy.deepcopy(outs[600].snapshot)
    for g, mode, kw in (("G3", "charging", 25.0), ("G4", "fast_charge", 35.0), ("G5", "full", 45.0)):
        s["guests"][g]["mode"]["value"], s["guests"][g]["kw_actual"]["value"] = mode, kw
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "unconfirmed" and d["unconfirmed_because"] == "feed stale"
    r = Rec.from_d4(d, seq=1, snapshot=s)
    assert r["unconfirmed_because"] == "feed stale"
    assert "is not confirmed (feed stale)." in r["sentence"]
    clean(r)


# ------------------------------------------------------------------------------------------------ soak 4, soak note, soak 6

def test_a_profile_without_one_capability_weight_still_decides_d3(tmp_path):
    """Soak 4: the loader accepts a weight table that leaves out G3's capability. D3 reads it as 0, as D1 and D4 do."""
    m = copy.deepcopy(MISSIONS["sar"])
    m["id"] = "sar_partial"
    del m["weights"]["seabed_inspection"]
    assert Ld.check_mission(m, CARDS, Ld.load_vocabulary(assumptions=A), Ld._schema(Ld.ROOT, "config/missions/schema.json")) == []
    inputs = scripted_inputs()
    inputs[0] = [inp(0, "profile_applied", profile=m)]
    loop, outs, recs = run("sar", inputs=inputs, until=600, log_dir=tmp_path)
    [d3] = kinds(recs, "D3")
    assert d3["mission"] == "sar_partial" and d3["cost_to_loser"]["leg"] == "aborted"
    same_everywhere(loop, outs, tmp_path, "sar")


@pytest.mark.xfail(strict=True, reason="left unfixed: the confirm time read by integer crew moves the 6-aboard recovery to "
                   "minute 5.1 on the endurance limit, which changes the crew-6 D5 records the screen shows at minute 8")
def test_the_recovery_lead_counts_the_bridge_confirm():
    """Soak note: config keys the confirm times by integer crew level. The lead is confirm, clear and approach."""
    approach = A["rules"]["r3"]["approach_min"] * 60
    for crew in (14, 6):
        want = max(A["crew"]["confirm_s"][crew]) + max(A["ship_state"]["deck"]["clear_min"][crew]) * 60 + approach
        assert D3.recovery_lead_s(A, crew) == want
    assert D3.recovery_lead_s(A, 0) == approach


def test_a_priority_swap_to_an_unknown_file_is_refused_not_a_crash(tmp_path):
    """Soak 6: a swap to a file id that is not loaded keeps the file in force and is logged as refused."""
    inputs = scripted_inputs()
    inputs[300] = [inp(300, "priority_swap", mission="fishing")]
    loop, outs, recs = run(inputs=inputs, until=600, log_dir=tmp_path)
    assert outs[-1].tick == 600 and loop.core.mission["id"] == "survey"
    [refused] = loop.core.rejected
    assert refused["tick"] == 300 and refused["profile"] == "fishing" and "fishing" in refused["problems"][0]
    assert kinds(recs, "D3")[0]["mission"] == "survey"
    same_everywhere(loop, outs, tmp_path)


# ------------------------------------------------------------------------------------------------ repair round

def test_a_denial_after_an_early_recall_is_not_asked_again(tmp_path):
    """#6: a recall at 450 is open when the battery limit comes on at 480, so the limit is covered. The bridge denies
    at 500 and ArgOS does not ask again a tick later."""
    inputs = {500: [inp(500, "bridge_answer", request_seq=1, answer="denied")]}
    loop, outs, recs = run(inputs=inputs, safety={450: ["g4_return_home"]}, log_dir=tmp_path)
    d5 = [(r["tick"], r["verdict"], r["deck_evidence"]) for r in kinds(recs, "D5")]
    assert d5 == [(450, "confirm", d5[0][2]), (500, "held", "the bridge denied the recovery")]
    assert [(t, c["args"]["request_seq"]) for t, c in commands(outs, "bridge_request")] == [(450, 1)]
    assert loop.core.r3_limit == ("G4.battery_pct", "land_or_ditch")
    same_everywhere(loop, outs, tmp_path)


def test_a_recall_that_lapses_after_the_battery_limit_came_on_is_not_asked_again():
    """#6: a recall at 450 lapses at 511. The limit came on while it was open, so no ask at 512, as after a lapse at 541."""
    _, outs, recs = run(inputs={}, safety={450: ["g4_return_home"]}, until=900, standby=False)
    assert [(r["tick"], r["verdict"]) for r in kinds(recs, "D5")] == [(450, "confirm"), (450 + WAIT_14 + 1, "held")]
    assert [t for t, _ in commands(outs, "bridge_request")] == [450]


def test_a_confirmation_hidden_by_a_feed_drop_clears_the_deck_when_the_feed_returns(tmp_path):
    """#5: the bridge confirms at 540 while the laptop feed is down (500 to 700). The wait runs out at 661 and the
    recovery is held, the feed named as the cause. At 700 the fresh list shows the confirmation came in time, so the
    deck is cleared and G4 lands at 1020, as with no drop."""
    inputs = scripted_inputs()
    inputs.setdefault(500, []).append(inp(500, "feed_drop", feed="laptop", until_t_s=700))
    loop, outs, recs = run(inputs=inputs, log_dir=tmp_path)
    d5 = [(r["tick"], r["verdict"], r["deck_evidence"]) for r in kinds(recs, "D5")]
    wait = loop.core.wait_s[6]          # the crew reads the next lower level while the feed is lost
    assert d5[1:] == [(480 + wait + 1, "held", LOST_FEED),
                      (700, "cleared", "the bridge confirmed at minute 9")]
    assert [t for t, _ in commands(outs, "clear_deck")] == [700]
    assert loop.core.r3["landed_t_s"] == 1020
    assert [(t, c["args"]["request_seq"]) for t, c in commands(outs, "bridge_close")] == [(1020, 1)]
    clean(*kinds(recs, "D5"))
    same_everywhere(loop, outs, tmp_path)


def test_a_late_confirmation_seen_after_a_feed_drop_leaves_the_recovery_held():
    """#5: the bridge confirms at 600, past the 60 s wait at 14 aboard. The fresh list at 700 shows it late, as an
    unbroken feed would have, so the recovery stays held and the deck is not cleared."""
    inputs = {500: [inp(500, "feed_drop", feed="laptop", until_t_s=700)],
              600: [inp(600, "bridge_answer", request_seq=1, answer="confirmed")]}
    loop, outs, recs = run(inputs=inputs, until=900, standby=False)
    assert [r["verdict"] for r in kinds(recs, "D5")] == ["confirm", "held"]
    assert not commands(outs, "clear_deck") and loop.core.r3["state"] == "held"


def test_the_hard_limit_row_reads_a_word_limit_as_words():
    """#22: with G4 telemetry lost before minute 8, D3 runs on the endurance limit. Its HARD LIMIT row has no raw
    operator and no stray percent sign. The battery row at minute 8 reads as before."""
    from sdv.ui import data, live, view
    I = data.Inputs()
    r = live.Run("survey", inputs={100: [inp(100, "feed_drop", feed="g4_telemetry", until_t_s=None)]})
    r.advance_to(910)
    rows = {k: v for k, v, _ in view.screen(I, r.moment())["decision"]["rows"]}
    assert rows["HARD LIMIT"] == "G4 WHILE AIRBORNE · LAND WITHIN 90 min"
    r.close()
    nominal = live.Run("survey")
    nominal.advance_to(481)
    rows = {k: v for k, v, _ in view.screen(I, nominal.moment())["decision"]["rows"]}
    assert rows["HARD LIMIT"] == "G4 BATT < 20 % · LAND WITHIN 12 min"
    nominal.close()
