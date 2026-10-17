"""The A.8 response classes as degradation priorities (DEC-60): 200 MS never shed and answered from the safety table,
5 S in the first action, 60 S one step per tick within the full sequence, 30 S restore; plus profiles at sea."""
import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import ledger as Lg  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import safety as Sf  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.core import Core  # noqa: E402
from sdv.loop import Loop, load_simulator, replay, scripted_inputs  # noqa: E402

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SCHEMA = Ld._schema(Ld.ROOT, "config/missions/schema.json")
RECORD = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}


def edited(base="survey", **kw):
    m = copy.deepcopy(MISSIONS[base])
    m["id"] = f"{base}_edited"
    m.update(kw)
    return m


def applied(tick, profile):
    return {"t_s": tick, "type": "profile_applied", "injected": False, "payload": {"profile": profile}}


def run(mission="survey", until=1200, inputs=None, log_dir=None, standby=False, hooks=None):
    loop = Loop(load_simulator(mission=mission), mission, inputs=scripted_inputs() if inputs is None else inputs,
                log_dir=log_dir, standby=standby)
    outs, extra = [], []
    for out in loop.ticks(until=until):
        outs.append(out)
        for req in (hooks or {}).get(out.tick, []):
            extra += loop.safety(req)
    loop.close()
    return loop, outs, extra


# ------------------------------------------------------------------------------------------------ the classes

def test_the_tags_come_from_the_brief_numbers():
    assert [Lg.response_tag(A, c) for c in ("safety_command", "shed_first_action", "shed_full_sequence", "restore", "arbitration")] == \
        ["200 MS", "5 S", "60 S", "30 S", "2 S"]


def test_every_guest_has_one_class_per_profile():
    m = edited(response={"safety_command": ["G6"]})
    assert {g: Lg.response_of(CARDS, g, m) for g in sorted(CARDS)} == {
        "G1": "shed_first_action", "G2": "shed_first_action", "G3": "shed_full_sequence", "G4": "shed_first_action",
        "G5": "shed_first_action", "G6": "safety_command"}
    assert {g: Lg.response_of(CARDS, g, MISSIONS["sar"]) for g in ("G3", "G4", "G5")} == {
        "G3": "shed_first_action", "G4": "shed_full_sequence", "G5": "shed_first_action"}


def test_a_200_ms_guest_is_never_on_either_ladder():
    m = edited(response={"safety_command": ["G4"]})
    modes = {"G3": "standby", "G4": "fast_charge", "G5": "full"}
    assert "G4" not in {s.guest for s in Lg.ladder(CARDS, modes, m)} | {s.guest for s in Lg.ladder(CARDS, modes, m, for_shed=True)}


def test_d4_takes_every_5_s_step_before_any_60_s_step():
    modes = {"G3": "standby", "G4": "fast_charge", "G5": "full"}
    order = [s.response for s in Lg.ladder(CARDS, modes, MISSIONS["sar"], for_shed=True)]
    assert order == sorted(order, key=lambda r: Lg.RESPONSE_RANK[r])
    for cls in ("shed_first_action", "shed_full_sequence"):        # throttles before sheds inside each class
        within = [s.shed for s in Lg.ladder(CARDS, modes, MISSIONS["sar"], for_shed=True) if s.response == cls]
        assert within == sorted(within)


def test_d1_keeps_throttles_first_for_the_one_genset_down_check():
    modes = {"G3": "standby", "G4": "fast_charge", "G5": "full"}
    sheds = [s.shed for s in Lg.ladder(CARDS, modes, MISSIONS["sar"])]
    assert sheds == sorted(sheds)


@pytest.mark.parametrize("mission,needle", [
    ({"response": {"safety_command": ["G9"]}}, "response.safety_command[0]: no loaded card G9"),
    ({"response": {"safety_command": ["G3"]}}, "G3 is mission_critical (60 S); a guest has one response class"),
    ({"tiers": {"discretionary": ["G5"]}}, "tiers: replaced by response.safety_command (200 MS) and shed_order"),
])
def test_the_loader_refuses_a_bad_class_with_the_field_named(mission, needle):
    problems = Ld.check_mission(edited(**mission), CARDS, VOCAB, SCHEMA)
    assert any(needle in p for p in problems), problems


def test_a_safety_critical_card_cannot_be_put_on_the_ladder():
    cards = copy.deepcopy(CARDS)
    cards["G3"]["criticality"]["safety_critical"] = True
    problems = Ld.check_mission(MISSIONS["survey"], cards, VOCAB, SCHEMA)
    assert any("G3 is safety-critical on its card (200 MS)" in p for p in problems)


# ------------------------------------------------------------------------------------------------ 5 S and 60 S

def test_minute_19_steps_carry_their_class_and_due_tick():
    for f, guest in (("survey", "G4"), ("sar", "G5")):
        d = D4.shed(CARDS, MISSIONS[f], SNAP[f"scenario_b_{f}_m19"])
        s = d["steps"][0]
        assert (s["guest"], s["response"], s["due_t_s"]) == (guest, "shed_first_action", 1145)
        assert d["first_shed_due_t_s"] == 1145 and d["full_sequence_due_t_s"] == 1200 and d["queued"] == []
        assert d["applies_at_tick"] <= s["due_t_s"]


def test_60_s_steps_go_one_per_tick_after_a_fresh_reading_within_60_s():
    """sar with G4 and G5 both mission-critical: the first action takes only G3 (5 S); still short, G4 goes alone the
    next tick (60 S); then it holds."""
    inputs = scripted_inputs()
    inputs[1100] = [applied(1100, edited("sar", mission_critical=["G4", "G5"]))]
    _, outs, _ = run("sar", inputs=inputs)
    d4 = [r for o in outs for r in o.records if r["kind"] == "D4" and r["tick"] >= 1141]
    assert [(r["tick"], r["verdict"], [s["guest"] for s in r["steps"]]) for r in d4[:3]] == \
        [(1141, "shed", ["G3"]), (1142, "shed", ["G4"]), (1143, "hold", [])]
    first, second = d4[0], d4[1]
    assert first["steps"][0]["response"] == "shed_first_action" and first["applies_at_tick"] <= first["first_shed_due_t_s"]
    assert [q["guest"] for q in first["queued"]] == ["G4"] and first["queued"][0]["due_t_s"] == 1200
    assert "Next if still short: G4 fast charge to charge" in first["sentence"]
    assert second["steps"][0]["response"] == "shed_full_sequence" and second["applies_at_tick"] <= second["full_sequence_due_t_s"]


# ------------------------------------------------------------------------------------------------ 200 MS

def test_hold_g3_answers_at_once_and_lands_next_tick(tmp_path):
    loop, outs, extra = run("survey", until=1200, log_dir=tmp_path, standby=True, hooks={300: ["g3_hold_depth"]})
    sent = extra[0]
    assert (sent["kind"], sent["verdict"], sent["tick"], sent["applies_at_tick"]) == ("safety", "sent", 300, 301)
    assert not list(RECORD.iter_errors(sent)) and sent["sentence"] == "G3 told to hold depth, sent over the acoustic link."
    assert outs[300].safety["g3_hold_depth"]["state"] == "ready"
    held = next(o.tick for o in outs if o.snapshot["guests"]["G3"]["activity"]["value"] == "holding_depth")
    assert 301 < held <= 301 + 60
    timing = [t for t in loop.core.timing if t["kind"] == "safety"]
    assert timing and all(t["latency_ms"] < t["ceiling_ms"] == 200 for t in timing)
    # no conflict at minute 8 any more, yet R3 still opens G4's recovery and it lands at the pin
    recs = [r for o in outs for r in o.records]
    assert not any(r["kind"] == "D3" for r in recs)
    assert [(r["tick"], r["verdict"]) for r in recs if r["kind"] == "D5"][:2] == [(480, "confirm"), (540, "cleared")]
    assert outs[1020].snapshot["guests"]["G4"]["activity"]["value"] == "landed"
    assert all(o.standby == "in step" for o in outs)
    snaps, decisions = replay(tmp_path, "survey")
    assert snaps == (tmp_path / "snapshots.jsonl").read_text().splitlines()
    assert decisions == (tmp_path / "decisions.jsonl").read_text().splitlines()


def test_requests_with_nothing_to_do_or_no_way_to_do_it():
    _, _, extra = run("survey", until=600, hooks={10: ["g2_stop_winch"], 560: ["g3_hold_depth", "g4_return_home"]})
    assert [(r["safety_request"], r["verdict"]) for r in extra] == \
        [("g2_stop_winch", "not_needed"), ("g3_hold_depth", "not_needed"), ("g4_return_home", "not_needed")]
    assert extra[0]["sentence"] == "No winch stop needed: G2 is not aboard."
    snap = copy.deepcopy(SNAP["scenario_b_survey_m00"])
    snap["links"]["acoustic_link_up"]["value"] = False
    row = Sf.table(CARDS, snap, [], None, False)["g3_hold_depth"]
    assert row["state"] == "cannot" and "acoustic link is down" in row["reason"]


def test_a_landing_hold_after_the_deck_is_cleared_cannot_stop_g4():
    _, outs, extra = run("survey", until=620, hooks={600: ["r3_hold_landing", "g4_return_home"]})
    hold, recall = extra
    assert (hold["verdict"], hold["safety_action"]) == ("cannot", "hold") and "waves G4 off by radio" in hold["sentence"]
    assert recall["verdict"] == "not_needed"


def test_a_landing_hold_before_the_bridge_answers_withholds_the_deck_work_until_the_landing_officer_clears():
    inputs = scripted_inputs()
    inputs[700] = [{"t_s": 700, "type": "deck_report", "injected": False, "payload": {"deck": "clear", "wind_kn": 20}}]
    loop, outs, extra = run("survey", until=1100, inputs=inputs, hooks={500: ["r3_hold_landing"]})
    assert extra[0]["verdict"] == "sent"
    d5 = [r for o in outs for r in o.records if r["kind"] == "D5"]
    assert [(r["tick"], r["verdict"]) for r in d5] == [(480, "confirm"), (540, "cleared"), (700, "cleared")]
    assert "waits for the landing hold to lift" in d5[1]["sentence"] and "landing hold lifted" in d5[2]["sentence"]
    deck = [(o.tick, c["kind"]) for o in outs[:1000] for c in o.commands if c["kind"] in ("clear_deck", "ship_state")]
    assert deck and all(t == 700 for t, _ in deck)
    assert all(o.snapshot["guests"]["G4"]["activity"]["value"] == "airborne" for o in outs[541:701])


def test_lifting_a_hold_keeps_a_denial():
    inputs = {540: [{"t_s": 540, "type": "bridge_answer", "injected": False, "payload": {"request_seq": 1, "answer": "denied"}}],
              600: [{"t_s": 600, "type": "deck_report", "injected": False, "payload": {"deck": "clear", "wind_kn": 20}}]}
    _, outs, extra = run("survey", until=700, inputs=inputs, hooks={500: ["r3_hold_landing"]})
    d5 = [(r["tick"], r["verdict"]) for o in outs for r in o.records if r["kind"] == "D5"]
    assert d5 == [(480, "confirm"), (540, "held")]
    assert not any(c["kind"] in ("clear_deck", "ship_state") for o in outs for c in o.commands)


def test_a_forbidden_recovery_cannot_be_held_or_recalled_into_clearing():
    _, outs, extra = run("survey", until=600, inputs={0: [applied(0, edited(confirm={"r3": {14: "forbidden"}}))]},
                         hooks={500: ["r3_hold_landing", "g4_return_home"]})
    assert [r["verdict"] for r in extra] == ["not_needed", "cannot"] and "forbids it" in extra[1]["sentence"]


def test_an_early_recall_that_lapses_is_asked_again_at_the_hard_limit():
    _, outs, extra = run("survey", until=500, inputs={}, hooks={100: ["g4_return_home"]})
    assert extra[0]["verdict"] == "sent" and extra[0]["reason"] == "the bridge is asked to confirm the recovery"
    recs = sorted(extra + [r for o in outs for r in o.records], key=lambda r: r["seq"])
    d5 = [(r["tick"], r["verdict"]) for r in recs if r["kind"] == "D5"]
    assert d5[:2] == [(100, "confirm"), (161, "held")] and (480, "confirm") in d5
    at480 = [(c["kind"], c["args"].get("request_seq")) for c in outs[480].commands]
    assert ("bridge_close", 1) in at480 and ("bridge_request", 2) in at480


def test_an_unknown_safety_request_is_refused_before_anything_is_logged():
    loop = Loop(load_simulator(mission="survey"), "survey", inputs={})
    list(loop.ticks(until=3))
    seq = loop.core.seq
    with pytest.raises(ValueError):
        loop.safety("open_the_bay_doors")
    assert loop.core.seq == seq and not loop.inputs.get(3)


def test_a_hold_on_its_way_to_g3_expires_when_the_link_drops():
    core = Core("survey")
    snap = copy.deepcopy(SNAP["scenario_b_survey_m00"])
    core.decide(snap)
    assert core.safety("g3_hold_depth")[0][0]["verdict"] == "sent"
    later = copy.deepcopy(snap)
    later["run"]["tick"] = later["run"]["t_ship_s"] = 5
    later["links"]["acoustic_link_up"]["value"] = False
    core.decide(later)
    assert core.g3_hold_since is None and core.safety_table["g3_hold_depth"]["state"] == "cannot"


# ------------------------------------------------------------------------------------------------ 30 S restore

def recovered(snap, tick, mode_g4="charge", fault_state="cleared"):
    s = copy.deepcopy(snap)
    s["run"]["tick"] = s["run"]["t_ship_s"] = tick
    s["guests"]["G4"]["mode"]["value"] = mode_g4
    s["guests"]["G4"]["kw_actual"]["value"] = 10.0
    for f in s["faults"]:
        f["state"], f["healthy_since_t_s"] = fault_state, tick - 61
    s["capacity"]["heat"]["value"] = {"capacity": 133.3, "unit": "kW", "degraded_by": [], "zero_by_rule": False}
    s["capacity"]["power"]["value"] = {"capacity": 250, "unit": "kW", "degraded_by": [], "zero_by_rule": False}
    s["capacity"]["shed_ceiling_kw"]["value"] = 128.3
    return s


def test_a_shed_guest_is_restored_once_every_fault_is_healthy():
    core = Core("survey")
    recs, cmds = core.decide(SNAP["scenario_b_survey_m19"])
    assert recs[-1]["verdict"] == "shed" and core.shed_from == {"G4": "fast_charge"}
    recs, cmds = core.decide(recovered(SNAP["scenario_b_survey_m19"], 1400, fault_state="restoring"))
    assert not [r for r in recs if r["verdict"] == "restore"]
    recs, cmds = core.decide(recovered(SNAP["scenario_b_survey_m19"], 1460))
    r = next(r for r in recs if r["verdict"] == "restore")
    assert not list(RECORD.iter_errors(r))
    assert (r["steps"][0]["from_mode"], r["steps"][0]["to_mode"], r["load_after_kw"]) == ("charge", "fast_charge", 81)
    assert cmds == [{"seq": r["seq"], "kind": "set_mode", "args": {"guest": "G4", "mode": "fast_charge"}}]
    assert r["sentence"] == "Restored G4 from charge to fast charge: every fault healthy since minute 23.3. Load 81 of 128.3 kW."
    assert core.timing[-1]["ceiling_ms"] == 30000 and core.shed_from == {}


def test_no_restore_while_it_would_not_fit():
    core = Core("survey")
    core.decide(SNAP["scenario_b_survey_m19"])
    tight = recovered(SNAP["scenario_b_survey_m19"], 1460)
    tight["capacity"]["shed_ceiling_kw"]["value"] = 75.0
    recs, _ = core.decide(tight)
    assert not [r for r in recs if r["verdict"] == "restore"] and core.shed_from == {"G4": "fast_charge"}


# ------------------------------------------------------------------------------------------------ profiles at sea

def test_an_edited_profile_applied_at_sea_changes_the_shed_and_replays(tmp_path):
    inputs = scripted_inputs()
    inputs[1100] = [applied(1100, edited(shed_order={"coastal_connectivity": 1}))]
    _, outs, _ = run("survey", inputs=inputs, log_dir=tmp_path)
    shed = next(r for o in outs for r in o.records if r["verdict"] == "shed")
    assert shed["tick"] == 1141 and shed["mission"] == "survey_edited" and shed["steps"][0]["guest"] == "G5"
    snaps, recs = replay(tmp_path, "survey")
    assert snaps == (tmp_path / "snapshots.jsonl").read_text().splitlines()
    assert recs == (tmp_path / "decisions.jsonl").read_text().splitlines()


def test_a_bad_profile_at_sea_is_refused_and_the_previous_kept():
    inputs = scripted_inputs()
    inputs[1100] = [applied(1100, edited(response={"safety_command": ["G3"]}))]
    loop, outs, _ = run("survey", inputs=inputs)
    assert loop.core.rejected and "G3 is mission_critical (60 S)" in loop.core.rejected[0]["problems"][0]
    shed = next(r for o in outs for r in o.records if r["verdict"] == "shed")
    assert shed["mission"] == "survey" and shed["steps"][0]["guest"] == "G4"


def test_a_profile_can_forbid_recovery_at_a_crew_level():
    _, outs, _ = run("survey", until=500, inputs={0: [applied(0, edited(confirm={"r3": {14: "forbidden"}}))]})
    d5 = next(r for o in outs for r in o.records if r["kind"] == "D5")
    assert d5["verdict"] == "forbidden" and "forbids it at 14 aboard" in d5["sentence"]
    assert not any(c["kind"] == "bridge_request" for o in outs for c in o.commands)
