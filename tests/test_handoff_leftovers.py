"""Cross-cluster leftovers after the four handoff fix branches (Sun 01:45): hostile profiles and numbers at sea are
refused in plain words and never crash the loop, the operations screen says what the core refused, the CLI never
echoes a huge edit back, the safety row type is upper case, and D4 acts on an over-limit whose only stand-in is a kW
beside a fresh mode (a guest whose mode is a stand-in leaves its line unconfirmed, as before) and dates a delayed first
action from the steps that landed, not from a feed coming back."""
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


def mission_problems(m: dict) -> list[str]:
    return Ld.check_mission(m, CARDS, Ld.load_vocabulary(assumptions=A), Ld._schema(Ld.ROOT, "config/missions/schema.json"))


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


DOOR = [
    ({"cmd": "input", "input": {"type": "priority_swap", "payload": {"mission": {"id": "sar"}}}}, "no such priority file is loaded"),
    ({"cmd": "input", "input": {"type": "priority_swap", "payload": {"mission": "x: y; z"}}}, "no such priority file is loaded"),
    ({"cmd": "input", "input": {"type": "priority_swap", "payload": {"mission": 10 ** 400}}}, "no such priority file is loaded"),
    ({"cmd": "input", "input": {"type": "priority_swap", "payload": {"mission": "x" * 300}}}, "no such priority file is loaded"),
    ({"cmd": "mission", "value": {"id": "sar"}}, "no such priority file is loaded"),
    ({"cmd": "mission", "value": "x: y; z"}, "no such priority file is loaded"),
    ({"cmd": "mission", "value": 10 ** 400}, "no such priority file is loaded"),
    ({"cmd": "input", "input": {"type": {"a": 1}, "payload": {}}}, "input refused: the type given is not a laptop input"),
    ({"cmd": "input", "input": {"type": "x: y; z", "payload": {}}}, "input refused: the type given is not a laptop input"),
    ({"cmd": "input", "input": {"type": 10 ** 5000, "payload": {}}}, "input refused: the type given is not a laptop input"),
    ({"cmd": "input", "input": "deck_report"}, "input refused: the type given is not a laptop input"),
]


@pytest.mark.parametrize("msg,said", DOOR, ids=[f"{m['cmd']}-{i}" for i, (m, _) in enumerate(DOOR)])
def test_the_screen_door_never_quotes_an_object_or_hostile_value_back(msg, said):
    """Repair round. Two door checks in LiveReplay.command run before the input check and quoted the raw value: a dict
    repr, a semicolon and colons, or 401 digits on the SIM bar. They say what is wrong in plain words instead."""
    lr = live.LiveReplay("survey", 100, running=False)
    assert lr.command(msg) == said and plain(said) and lr.run.laptop == {}


def test_the_screen_door_still_names_a_plain_type_or_file():
    lr = live.LiveReplay("survey", 100, running=False)
    assert lr.command({"cmd": "mission", "value": "fishing"}) == "no priority file fishing"
    assert lr.command({"cmd": "input", "input": {"type": "guest_report", "payload": {}}}) == "input 'guest_report' is not a laptop input"
    assert lr.command({"cmd": "input", "input": {"type": "deck_report", "payload": [1]}}) == \
        "input 'deck_report' refused: payload is not an object"


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


def test_a_shed_order_rank_of_0_is_refused_in_plain_words():
    """Repair round. jsonschema's "0 should not be valid under {'const': 0}" reached the row with braces."""
    bad = profile(shed_order={"sar_air": 0})
    assert mission_problems(bad) == ["shed_order.sar_air: a rank cannot be 0"]
    r = live.Run("survey", {300: [inp(300, "profile_applied", profile=bad)]})
    r.advance_to(301)
    [row] = rows(r, "PROFILE")
    assert row["msg"] == "Profile survey_jury refused: shed_order.sar_air (a rank cannot be 0). survey kept." and plain(row["msg"])


@pytest.mark.parametrize("field", ["weights", "shed_order", "confirm"])
def test_a_long_field_name_is_cut_in_the_profile_row(field):
    """Repair round. A weights key of 5000 letters made a row of 5192 characters: the field path was quoted whole, and
    a confirm rule's name is said again in its problem. Each long word is cut to 40 characters."""
    key = "a" * 5000
    value = {"weights": 0.5, "shed_order": 1, "confirm": {"14": "confirm"}}[field]
    bad = profile(**{field: dict(MISSIONS["survey"].get(field) or {}, **{key: value})})
    r = live.Run("survey", {300: [inp(300, "profile_applied", profile=bad)]})
    r.advance_to(301)
    [row] = rows(r, "PROFILE")
    assert row["refused"] and len(row["msg"]) < 300 and "a" * 41 not in row["msg"] and plain(row["msg"])
    assert row["msg"].startswith(f"Profile survey_jury refused: {(field + '.' + key)[:37]}... (")


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


def test_a_swap_in_force_to_a_long_profile_id_never_reads_none():
    """Repair round. A schema-valid profile id of 44 characters is no PLAIN_ID: its swap read "Priority file None.yaml
    in force." and the next row in the tick said "None kept." The core's file is named only when plain."""
    long_id = "survey_profile_for_the_jury_trial_number_one"
    r = live.Run("survey", {300: [inp(300, "profile_applied", profile=profile() | {"id": long_id})],
                            320: [inp(320, "priority_swap", mission="survey"), inp(320, "priority_swap", mission=long_id),
                                  inp(320, "priority_swap", mission="fishing")]})
    r.advance_to(321)
    assert r.loop.core.mission["id"] == long_id
    msgs = [e["msg"] for e in rows(r, "PROFILE") + rows(r, "PRIORITY")]
    assert sorted(msgs) == ["Priority file survey.yaml in force.", "Priority swap in force.", "Profile applied at sea and in force.",
                            "Swap to fishing.yaml refused: no such priority file is loaded. The file in force is kept."]
    assert all("None" not in m and plain(m) for m in msgs)


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


@pytest.mark.parametrize("raw,value", [("0" * 5000, 0), ("0" * 4400 + "1", 1), ("-" + "0" * 4400 + "1_0", -10),
                                       ("+" + "0" * 4999 + "7", 7)], ids=["zeros", "padded one", "padded minus ten", "plus"])
def test_a_zero_padded_edit_past_the_digit_limit_is_its_value(raw, value):
    """Repair round. Every digit-only edit past 4300 characters read as the largest float, so 0000...1 was refused as
    "above 1000000". Its sign, underscores and leading zeros do not count."""
    assert cli._number("drone.mass_t", raw) == value and type(cli._number("drone.mass_t", raw)) is int
    assert view.admit(I, "A1-survey", {"G4.drone.mass_t": raw})["sentence"] == \
        view.admit(I, "A1-survey", {"G4.drone.mass_t": str(value)})["sentence"]


def test_a_huge_negative_edit_reads_below_the_smallest_number(capsys):
    """Repair round. A negative 5000-digit edit, and any number below -1000000 in a file, read "above 1000000"."""
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.drone.mass_t=-" + "9" * 5000]) == 2
    out = capsys.readouterr().out
    assert "the number given is below -1000000, the smallest number a file may carry" in out and "above" not in out
    assert view.admit(I, "A1-survey", {"G4.drone.mass_t": "-2000000"})["sentence"] == \
        "Card rejected: G4.drone.mass_t (-2000000 is below -1000000, the smallest number a file may carry)."
    prof = profile("sar", shed_order={"sar_air": -(10 ** 400)})
    assert mission_problems(prof) == ["shed_order.sar_air: the number given is below -1000000, the smallest number a file may carry"]


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
    """G4 already at charge, G3's mode missing: on G3's highest-draw stand-in the loop reads 80 against 75. A mode
    stand-in leaves the line unconfirmed, so D4 arms the ladder and takes no step."""
    s = copy.deepcopy(M19)
    s["guests"]["G4"]["mode"]["value"], s["guests"]["G4"]["kw_actual"]["value"] = "charge", 10.0
    s["guests"]["G3"]["mode"] = {"value": None, "source": "plant", "age_s": None, "confidence": "assumed", "stale": False}
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["load_kw"] == 80 and d["limit_kw"] == 75
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["armed"] and d["unconfirmed_because"] == "reading missing"


MODE_STAND_INS = [
    ("sar", "G5", {"confidence": "substituted"}, "feed stale"),
    ("survey", "G5", {"confidence": "substituted", "stale": True}, "feed stale"),
    ("survey", "G4", {"confidence": "substituted"}, "feed stale"),
    ("survey", "G4", {"stale": True}, "feed stale"),
    ("survey", "G4", {"value": None, "confidence": "assumed"}, "reading missing"),
    ("survey", "G3", {"value": None, "confidence": "assumed"}, "reading missing"),
    ("survey", "G4", {"value": "warp"}, "reading missing"),
]


@pytest.mark.parametrize("mission,guest,mode,because", MODE_STAND_INS,
                         ids=[f"{m}-{g}-{'-'.join(f'{k}={v}' for k, v in x.items())}" for m, g, x, _ in MODE_STAND_INS])
def test_a_guest_whose_mode_is_a_stand_in_leaves_its_line_unconfirmed_as_before(mission, guest, mode, because):
    """Repair round. The certain path also took a line whose guest had a stand-in mode, and walked the ladder without
    that guest: on sar with G5's mode substituted it switched G3 off (1 kW) and queued the mission-critical G4, while
    the cheapest 5 S guest G5 kept its full draw. A mode stand-in leaves the line unconfirmed, as 3a79d98 does: the
    ladder armed, no step, nothing queued, the reason in the record."""
    s = copy.deepcopy(M19)
    s["guests"][guest]["mode"].update(mode)
    d = D4.shed(CARDS, MISSIONS[mission], s)
    assert d["verdict"] == "unconfirmed" and d["steps"] == [] and d["queued"] == [] and d["armed"]
    assert d["unconfirmed_because"] == because and d["load_kw"] > d["limit_kw"]


def test_a_mode_stand_in_off_the_binding_line_does_not_hold_back_a_certain_shed():
    """G1 is air cooled, on the bus and never on the loop: its substituted mode leaves only the power line unconfirmed.
    The loop, every mode on it fresh and G5's kW stale, is over for certain and is shed as on fresh readings."""
    s = copy.deepcopy(M19)
    s["guests"]["G1"]["mode"].update(confidence="substituted")
    s["guests"]["G5"]["kw_actual"].update(stale=True)
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["binding"]["class"] == "heat" and steps(d) == steps(D4.shed(CARDS, MISSIONS["survey"], M19))
    assert "unconfirmed_because" not in d


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
