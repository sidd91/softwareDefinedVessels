"""Cross-cluster leftovers after the four handoff fix branches (Sun 01:45): hostile profiles and numbers at sea are
refused in plain words and never crash the loop, the operations screen says what the core refused, the CLI never
echoes a huge edit back, the safety row type is upper case, and D4 acts on an over-limit that fresh values alone
prove and dates a delayed first action from the steps that landed, not from a feed coming back."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import cli  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.loop import Loop, canonical, check_input, exact, load_simulator, replay, scripted_inputs  # noqa: E402
from sdv.ui import data, live, view  # noqa: E402

I = data.Inputs()
A = Ld.load_assumptions()
CARDS = Ld.load_cards(vocab=Ld.load_vocabulary(assumptions=A))
MISSIONS = Ld.load_missions(CARDS, Ld.load_vocabulary(assumptions=A))
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}
CSS = (Ld.ROOT / "src/sdv/ui/static/argos.css").read_text()


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": False, "payload": payload}


def plain(sentence: str) -> bool:
    """A jury-facing sentence: no semicolon, one colon at most, nothing dumped from a payload or a card."""
    return ";" not in sentence and sentence.count(":") <= 1 and not any(c in sentence for c in "{}'")


def run(mission="survey", until=302, inputs=None, log_dir=None):
    """The loop with its standby and logs, as the CLI and the screen build it."""
    loop = Loop(load_simulator(mission=mission), mission, inputs=scripted_inputs() if inputs is None else inputs,
                log_dir=log_dir, standby=True)
    try:
        outs = list(loop.ticks(until=until))
    finally:
        loop.close()
    return loop, outs


def same_everywhere(outs, log_dir: Path, mission="survey") -> bool:
    """The standby stayed in step and a replay of the logs gives every snapshot and record byte for byte."""
    snaps, recs = replay(log_dir, mission)
    return (all(o.standby == "in step" for o in outs)
            and snaps == (log_dir / "snapshots.jsonl").read_text().splitlines()
            and recs == (log_dir / "decisions.jsonl").read_text().splitlines())


def profile(base="survey", **fields) -> dict:
    return dict(copy.deepcopy(MISSIONS[base]), id=f"{base}_jury", **fields)


def rows(run_: live.Run, tag: str) -> list[dict]:
    return [e for e in view.screen(I, run_.moment())["log"] if e["tag"] == tag]


# ------------------------------------------------------------------------------------------------ 1 profile not an object

NOT_OBJECTS = [("text", "automatic"), ("empty", None), ("a list", ["survey"]), ("a number", 3)]


@pytest.mark.parametrize("kind,prof", NOT_OBJECTS, ids=[k for k, _ in NOT_OBJECTS])
def test_a_profile_that_is_not_an_object_is_refused_at_sea_not_a_crash(tmp_path, kind, prof):
    """The core called prof.get('id') on whatever the input carried: a string, None, a list or a number killed the
    loop at sea. It is refused with a plain problem, the file in force stays, the standby and a replay agree."""
    inputs = scripted_inputs()
    inputs[300] = [inp(300, "profile_applied", profile=prof)]
    loop, outs = run(inputs=inputs, log_dir=tmp_path)
    assert outs[-1].tick == 302 and loop.core.mission["id"] == "survey"
    [refused] = loop.core.rejected
    assert refused["tick"] == 300 and refused["profile"] is None
    assert refused["problems"] == [f"(root): the profile sent is {kind}, not a priority file"]
    assert same_everywhere(outs, tmp_path)


def test_a_profile_input_without_its_profile_is_refused_at_sea(tmp_path):
    inputs = scripted_inputs()
    inputs[300] = [{"t_s": 300, "type": "profile_applied", "injected": False, "payload": {}}]
    loop, outs = run(inputs=inputs, log_dir=tmp_path)
    assert loop.core.mission["id"] == "survey" and loop.core.rejected[0]["problems"][0].endswith("is empty, not a priority file")
    assert same_everywhere(outs, tmp_path)


@pytest.mark.parametrize("kind,prof", NOT_OBJECTS, ids=[k for k, _ in NOT_OBJECTS])
def test_the_operations_screen_logs_a_refused_non_object_profile_in_plain_words(kind, prof):
    """live.Run read prof.get('id') too. The row names no id it does not have and keeps to one plain sentence."""
    r = live.Run("survey", {300: [inp(300, "profile_applied", profile=prof)]})
    r.advance_to(301)
    [row] = rows(r, "PROFILE")
    assert row["msg"] == f"Profile refused: the profile sent is {kind}, not a priority file. survey kept."
    assert row["refused"] and plain(row["msg"])


def test_the_screen_refuses_a_non_object_profile_at_the_door():
    lr = live.LiveReplay("survey", 100, running=False)
    said = lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": "automatic"}}})
    assert said == "input 'profile_applied' refused: profile 'automatic' is not an object" and lr.run.laptop == {}


# ------------------------------------------------------------------------------------------------ 2 numbers past float range

def test_canonical_never_raises_on_an_integer_past_float_range():
    """norm did round(float(x)): OverflowError on 10**400. Such a number is capped at the largest float, sign kept."""
    big = json.loads(canonical({"a": 10 ** 400, "b": -(10 ** 5000), "c": [10 ** 400]}))
    assert big["a"] == int(sys.float_info.max) and big["b"] == -int(sys.float_info.max) and big["c"] == [big["a"]]
    assert canonical({"x": 2.25, "y": 35.0, "z": 10 ** 300}) == '{"x":2.2,"y":35,"z":%d}' % int(float(10 ** 300))


@pytest.mark.parametrize("number", [10 ** 400, 10 ** 5000], ids=["400 digits", "5000 digits"])
def test_a_profile_with_a_huge_shed_order_applied_at_sea_is_refused_cleanly(tmp_path, number):
    """The 400-digit profile already reached the loader's number check. The 5000-digit one could not be written to the
    input log (Python's digit limit), so the loop died before the core saw it. It is logged as the largest float and
    refused by the same check, the same way live, on the standby and in a replay."""
    prof = profile("sar", shed_order={"sar_air": number})
    inputs = scripted_inputs()
    inputs[5] = [inp(5, "profile_applied", profile=prof)]
    loop, outs = run("sar", 8, inputs, tmp_path)
    assert outs[-1].tick == 8 and loop.core.mission["id"] == "sar"
    assert loop.core.rejected[0]["problems"] == \
        ["shed_order.sar_air: the number given is above 1000000, the largest number a file may carry"]
    assert same_everywhere(outs, tmp_path, "sar")
    assert json.loads(exact({"n": 10 ** 5000}))["n"] == sys.float_info.max


def test_the_screen_logs_a_huge_number_profile_as_refused():
    lr = live.LiveReplay("sar", 600, running=False)
    prof = profile("sar", shed_order={"sar_air": 10 ** 400})
    assert lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": prof}}}) is None
    lr.run.advance_to(602)
    [row] = rows(lr.run, "PROFILE")
    assert row["msg"] == ("Profile sar_jury refused: shed_order.sar_air (the number given is above 1000000, the largest "
                          "number a file may carry). sar kept.") and plain(row["msg"])


def test_the_door_refuses_a_profile_the_input_log_cannot_carry():
    with pytest.raises(ValueError) as e:
        check_input({"type": "profile_applied", "payload": {"profile": profile(shed_order={"sar_air": 10 ** 5000})}})
    assert str(e.value) == "input 'profile_applied' refused: profile holds a number too long to log"


# ------------------------------------------------------------------------------------------------ 3 the input contract check

HUGE_FIELDS = [
    ("crew_change", {"crew_aboard": 10 ** 400}, "crew_aboard"),
    ("crew_change", {"crew_aboard": 14, "people_available": 10 ** 400}, "people_available"),
    ("deck_report", {"deck": "clear", "wind_kn": 10 ** 400}, "wind_kn"),
    ("bridge_answer", {"request_seq": 10 ** 400, "answer": "confirmed"}, "request_seq"),
    ("feed_drop", {"feed": "nav", "until_t_s": 10 ** 400}, "until_t_s"),
    ("cooling_degraded", {"pump": 1, "factor": 10 ** 400, "confirmed": True}, "factor"),
    ("genset_trip", {"genset": 10 ** 5000, "confirmed": True}, "genset"),
    ("card_edited", {"guest": "G4", "field": "drone.mass_t", "from": 0.4, "to": 10 ** 400}, "to"),
]


@pytest.mark.parametrize("type_,payload,field", HUGE_FIELDS, ids=[f"{t}.{f}" for t, _, f in HUGE_FIELDS])
def test_a_huge_number_in_any_payload_field_is_refused_in_plain_words(type_, payload, field):
    """_conform built every type test at once, so math.isfinite raised OverflowError on a huge int in any field."""
    with pytest.raises(ValueError) as e:
        check_input({"type": type_, "payload": payload}, tuple(CARDS))
    msg = str(e.value)
    assert msg == f"input {type_!r} refused: {field} is above 1000000, the largest number an input may carry"
    assert ";" not in msg and msg.count(":") == 1


OBJECT_VALUES = [
    ("deck_report", {"deck": {"state": "clear"}}, "deck is an object, not one of clear, not_clear"),
    ("crew_change", {"crew_aboard": [14]}, "crew_aboard is a list, not one of 14, 6, 0"),
    ("priority_swap", {"mission": {"id": "sar"}}, "mission is an object, not text"),
    ("bridge_answer", {"request_seq": {"n": 1}, "answer": "denied"}, "request_seq is an object, not a whole number"),
    ("deck_report", {"deck": "clear", "wind_kn": [3]}, "wind_kn is a list, not a number"),
    ("deck_report", {"deck": "clear; x: y"}, "deck is text, not one of clear, not_clear"),
    ("deck_report", {"deck": "clear", "wind: x; y": 1}, "the payload has a field that is not in the contract"),
]


@pytest.mark.parametrize("type_,payload,reason", OBJECT_VALUES, ids=[r for _, _, r in OBJECT_VALUES])
def test_an_object_or_hostile_value_is_described_not_quoted(type_, payload, reason):
    """The refusal quoted object values as a Python dict repr, a second colon in the sentence."""
    with pytest.raises(ValueError) as e:
        check_input({"type": type_, "payload": payload})
    assert str(e.value) == f"input {type_!r} refused: {reason}" and plain(reason)


def test_an_input_type_that_is_not_text_is_refused_without_quoting_it():
    for t in ({"a": 1}, 10 ** 5000, "x" * 300):
        with pytest.raises(ValueError) as e:
            check_input({"type": t, "payload": {}})
        assert str(e.value) == "input refused: the type given is not a laptop input"


def test_a_huge_negative_number_is_refused_as_below_the_smallest():
    with pytest.raises(ValueError) as e:
        check_input({"type": "feed_drop", "payload": {"feed": "nav", "until_t_s": -(10 ** 400)}})
    assert str(e.value) == "input 'feed_drop' refused: until_t_s is below -1000000, the smallest number an input may carry"


def test_the_screen_refuses_a_huge_number_without_an_error_frame():
    lr = live.LiveReplay("survey", 100, running=False)
    said = lr.command({"cmd": "input", "input": {"type": "bridge_answer", "payload": {"request_seq": 10 ** 400, "answer": "confirmed"}}})
    assert said == "input 'bridge_answer' refused: request_seq is above 1000000, the largest number an input may carry"
    assert lr.run.laptop == {}


# ------------------------------------------------------------------------------------------------ 4 the PROFILE row

def test_a_refused_profile_row_names_the_field_in_one_plain_sentence():
    """The row quoted the raw schema problem: "confirm.r3: 'automatic' is not of type 'object'", a second colon."""
    lr = live.LiveReplay("survey", 300, running=False)
    bad = profile(confirm={"r3": "automatic"})
    assert lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": bad}}}) is None
    lr.run.advance_to(302)
    [row] = rows(lr.run, "PROFILE")
    assert row["msg"] == "Profile survey_jury refused: confirm.r3 (automatic is not a section of named fields). survey kept."
    assert row["refused"] and plain(row["msg"])
    assert lr.mission == "survey"


def test_two_profiles_in_one_tick_each_get_their_own_row():
    good = dict(profile("sar"), id="sar_tiers", shed_order={"coastal_connectivity": 1})
    bad = dict(profile("sar"), id="sar_tiers", weights={"sar_air": 2})
    r = live.Run("sar", {300: [inp(300, "profile_applied", profile=good), inp(300, "profile_applied", profile=bad)]})
    r.advance_to(301)
    msgs = sorted(e["msg"] for e in rows(r, "PROFILE"))
    assert msgs == ["Profile sar_tiers applied at sea and in force.",
                    "Profile sar_tiers refused: weights.sar_air (2 is greater than the maximum of 1). sar_tiers kept."]


# ------------------------------------------------------------------------------------------------ 5 a refused swap

def test_a_swap_the_core_refused_is_logged_as_refused_not_in_force():
    """Every priority_swap read "Priority file X.yaml in force.", even one the core refused and logged in rejected."""
    r = live.Run("survey", {300: [inp(300, "priority_swap", mission="fishing")]})
    r.advance_to(301)
    [row] = rows(r, "PRIORITY")
    assert row["msg"] == "Swap to fishing.yaml refused: no such priority file is loaded. survey kept."
    assert row["refused"] and plain(row["msg"]) and r.loop.core.mission["id"] == "survey"
    ok = live.Run("survey", {300: [inp(300, "priority_swap", mission="sar")]})
    ok.advance_to(301)
    assert [e["msg"] for e in rows(ok, "PRIORITY")] == ["Priority file sar.yaml in force."]


def test_a_swap_put_in_force_and_one_refused_in_the_same_tick_each_read_right():
    r = live.Run("survey", {300: [inp(300, "priority_swap", mission="sar"), inp(300, "priority_swap", mission="fishing")]})
    r.advance_to(301)
    assert sorted(e["msg"] for e in rows(r, "PRIORITY")) == \
        ["Priority file sar.yaml in force.", "Swap to fishing.yaml refused: no such priority file is loaded. sar kept."]
    assert r.loop.core.mission["id"] == "sar"


def test_a_swap_to_a_hostile_name_is_refused_without_quoting_it():
    r = live.Run("survey", {300: [inp(300, "priority_swap", mission="x: y; z" * 10)]})
    r.advance_to(301)
    [row] = rows(r, "PRIORITY")
    assert row["msg"] == "Priority swap refused: no such priority file is loaded. survey kept." and plain(row["msg"])
    assert r.loop.core.rejected[0]["problems"] == ["no priority file of that name is loaded"]


# ------------------------------------------------------------------------------------------------ 6 a huge digit edit

def test_a_digit_edit_past_the_digit_limit_reads_as_above_the_largest_number(capsys):
    """int() refuses more than 4300 digits, so the edit read "is not a number" and echoed all 5000 digits back."""
    raw = "9" * 5000
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", f"G4.drone.mass_t={raw}"]) == 2
    out = capsys.readouterr().out
    assert "the number given is above 1000000, the largest number a file may carry" in out
    assert "9" * 21 not in out and len(out) < 300
    a = view.admit(I, "A1-survey", {"G4.drone.mass_t": raw})
    assert a["sentence"] == "Card rejected: G4.drone.mass_t (the number given is above 1000000, the largest number a file may carry)."
    assert view.admit(I, "A1-survey", {"G4.drone.mass_t": "-" + raw})["verdict_raw"] == "card-rejected"


@pytest.mark.parametrize("raw,reason", [
    ("x" * 50, "the value given is not a number"),
    ("1" * 30 + "e" * 5, "the value given is not a number"),
    ("9" * 400 + "e9", "the value given is not a finite number"),
    ("abc", "'abc' is not a number"),
    ("1e400", "'1e400' is not a finite number"),
])
def test_an_edit_that_is_not_a_number_never_echoes_a_long_value(raw, reason):
    with pytest.raises(cli.EditError) as e:
        cli.apply_edit(CARDS["G4"], "drone.mass_t", raw)
    assert e.value.reason == reason


def test_the_cli_never_echoes_a_long_edit_back(capsys):
    raw = "9" * 400
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", f"G4.drone.mass_t={raw}"]) == 2
    out = capsys.readouterr().out
    assert "9" * 21 not in out and "the number given is above 1000000" in out


# ------------------------------------------------------------------------------------------------ 7 the SAFETY row

def test_a_safety_row_is_upper_case_and_styled_like_the_other_rows():
    lr = live.LiveReplay("survey", 300, running=False)
    assert lr.command({"cmd": "input", "input": {"type": "safety_request", "payload": {"request": "g3_hold_depth"}}}) is None
    log = view.screen(I, lr.run.moment())["log"]
    [row] = [e for e in log if e.get("seq") == lr.run.records[-1]["seq"]]
    assert row["type"] == "SAFETY"
    assert all(e["type"] == e["type"].upper() for e in log)
    assert re.search(r"\.t-SAFETY\b[^{]*\{[^}]*background", CSS)


# ------------------------------------------------------------------------------------------------ 8 over on fresh values alone

M19 = SNAP["scenario_b_survey_m19"]


def steps(d):
    return [(s["guest"], s["to_mode"], s["response"], s["due_t_s"]) for s in d["steps"]]


@pytest.mark.parametrize("kw", [
    {"value": 45.0, "source": "plant", "age_s": 6, "confidence": "measured", "stale": True},
    {"value": 45.0, "source": "plant", "age_s": 0, "confidence": "substituted", "stale": False},
    {"value": None, "source": "plant", "age_s": None, "confidence": "assumed", "stale": False},
], ids=["stale", "substituted", "missing"])
def test_a_kw_stand_in_with_a_fresh_mode_does_not_hold_back_a_certain_shed(kw):
    """G5's mode reads full, fresh. Its kW is a stand-in, so it counts at full's 45 kW, a lower bound. The loop is
    over on that already (81 against 75): the over-limit is certain and D4 sheds G4 as on fresh readings."""
    nominal = D4.shed(CARDS, MISSIONS["survey"], M19)
    s = copy.deepcopy(M19)
    s["guests"]["G5"]["kw_actual"] = kw
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "shed" and steps(d) == steps(nominal) == [("G4", "charge", "shed_first_action", 1145)]
    assert "unconfirmed_because" not in d


def test_a_line_over_only_on_stand_in_values_stays_unconfirmed():
    """G4 already at charge, G3's mode missing: on G3's highest-draw stand-in the loop reads 80 against 75, on fresh
    values alone 56. Only the stand-in makes it over, so D4 arms the ladder and takes no step."""
    s = copy.deepcopy(M19)
    s["guests"]["G4"]["mode"]["value"], s["guests"]["G4"]["kw_actual"]["value"] = "charge", 10.0
    s["guests"]["G3"]["mode"] = {"value": None, "source": "plant", "age_s": None, "confidence": "assumed", "stale": False}
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["load_kw"] == 80 and d["limit_kw"] == 75
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["armed"] and d["unconfirmed_because"] == "reading missing"


def test_a_certain_shed_takes_no_step_for_a_guest_whose_mode_is_a_stand_in():
    """G5's mode is a substituted stand-in while the loop is over on fresh values alone (G3 1, G4 35 and G5's fresh
    45 kW, 81 against 75): D4 sheds, and never from G5's unknown mode."""
    s = copy.deepcopy(M19)
    s["guests"]["G5"]["mode"].update(confidence="substituted", stale=True)
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "shed" and [st["guest"] for st in d["steps"]] == ["G4"]
    assert all(st["guest"] != "G5" for st in d["steps"] + d["queued"])


def test_a_stand_in_capacity_still_holds_back_even_a_line_over_on_fresh_draws():
    s = copy.deepcopy(M19)
    s["capacity"]["heat"].update(confidence="substituted", stale=True)
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["unconfirmed_because"] == "feed stale"


# ------------------------------------------------------------------------------------------------ 9 a feed coming back

def every_step_60_s() -> dict:
    m = profile(mission_critical=["G3", "G4", "G5"])
    m["id"] = "survey_mc"
    return m


def test_a_mode_back_from_its_stand_in_is_not_a_landed_step(tmp_path):
    """guest_meter lost 1130 to 1150, every relieving step 60 S: when the feed returns G3's mode goes from its
    highest-draw stand-in (charging) back to standby. That read as a step of the stretch having landed, so the late
    lone first action at 1150 was tagged due 1200. It is the first action, due by the pump fault's 5 s tick."""
    inputs = scripted_inputs()
    inputs.setdefault(0, []).append(inp(0, "profile_applied", profile=every_step_60_s()))
    inputs.setdefault(1130, []).append(inp(1130, "feed_drop", feed="guest_meter", until_t_s=1150))
    loop, outs = run("survey", 1160, inputs, tmp_path)
    shed = [r for o in outs for r in o.records if r["kind"] == "D4" and r["verdict"] == "shed"]
    assert [(r["tick"], steps(r)) for r in shed] == [(1150, [("G4", "charge", "shed_full_sequence", 1145)])]
    assert outs[1150].snapshot["guests"]["G3"]["mode"]["since_t_s"] == 1150      # the change out of the stand-in
    assert same_everywhere(outs, tmp_path)


def test_a_fresh_mode_change_after_the_onset_still_counts_as_landed():
    """The core passes each guest's last change between fresh readings: one after the onset is a landed step."""
    m = every_step_60_s()
    s = copy.deepcopy(M19)
    s["run"]["tick"] = s["run"]["t_ship_s"] = 1175
    first = D4.shed(CARDS, m, s, onset_t_s=1141, mode_changed_t_s={"G3": None, "G4": 1020, "G5": None, "G1": None})
    landed = D4.shed(CARDS, m, s, onset_t_s=1141, mode_changed_t_s={"G3": 1170, "G4": 1020, "G5": None, "G1": None})
    assert [(st["response"], st["due_t_s"]) for st in first["steps"]] == [("shed_full_sequence", 1145)]
    assert [(st["response"], st["due_t_s"]) for st in landed["steps"]] == [("shed_full_sequence", 1200)]
