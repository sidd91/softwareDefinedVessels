"""Polish round (Sun 04:00): every value a refusal quotes back follows the door's rule, a profile too deep to log is
refused at the door, a schema enum or pattern problem is said in words, a jump to a time that is not a number is
refused in a sentence, and a plain name never carries a trailing newline.

1. cli._number quoted the juror's edit with repr(raw), so 'EDIT REFUSED' and 'sdv admit --set' could show
   semicolons, braces and Python escapes. The CLI also echoed a long field name in full, twice.
2. A profile nested about 500 levels deep passed the door, then copy.deepcopy for the standby raised RecursionError
   after the simulator had stepped, and every later tick failed until RESTART.
3. live._refusal stripped quotes with a regex that mispaired on a double-quoted value with an apostrophe, and an
   enum problem kept Python's list brackets.
4. A jump to a time that is not a number raised from int(). The door quoted None and True as Python writes them.
   PLAIN_ID and _FIELD ended in '$', which matches before a trailing newline."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))

from sdv import cli  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import loop as L  # noqa: E402
from sdv.core import PLAIN_ID  # noqa: E402
from sdv.loop import Loop, check_input, load_simulator, replay, scripted_inputs  # noqa: E402
from sdv.ui import builder, data, live, server, view  # noqa: E402

I = data.Inputs()
A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
MISSION_SCHEMA = Ld._schema(Ld.ROOT, "config/missions/schema.json")
POLICIES = "confirm, standing_plan, automatic, forbidden"


def plain(sentence: str) -> bool:
    """A jury-facing sentence: no semicolon, one colon at most, no brace, quote, bracket or backslash from a payload."""
    return ";" not in sentence and sentence.count(":") <= 1 and not any(c in sentence for c in "{}'\"[]\\")


def inp(t, type_, **payload):
    return {"t_s": t, "type": type_, "injected": False, "payload": payload}


def profile(base="survey", **fields) -> dict:
    return {**copy.deepcopy(MISSIONS[base]), "id": f"{base}_jury", **fields}


def mission_problems(m: dict) -> list[str]:
    return Ld.check_mission(m, CARDS, VOCAB, MISSION_SCHEMA)


def rows(run_: live.Run, tag: str) -> list[dict]:
    return [e for e in view.screen(I, run_.moment())["log"] if e["tag"] == tag]


def nested(levels: int) -> dict:
    """A dict `levels` deep: nested(1) is {}, nested(2) is {"a": {}}."""
    d: dict = {}
    for _ in range(levels - 1):
        d = {"a": d}
    return d


# ------------------------------------------------------------------------------------------------ 1 the edit box

HOSTILE_EDITS = ["a;b", "{x}", "a:b", "\x01", "\x1b[2J", "a\\b", "it's", 'say "9"', "9\nx"]


@pytest.mark.parametrize("raw", HOSTILE_EDITS, ids=[repr(r) for r in HOSTILE_EDITS])
def test_an_edit_with_punctuation_or_a_control_character_is_described_not_quoted(raw):
    with pytest.raises(cli.EditError) as e:
        cli.apply_edit(CARDS["G4"], "drone.mass_t", raw)
    assert e.value.reason == "the value given is not a number"


def test_a_plain_edit_is_still_quoted_back():
    for raw, reason in (("abc", "'abc' is not a number"), ("1e400", "'1e400' is not a finite number"),
                        ("x" * 50, "the value given is not a number")):
        with pytest.raises(cli.EditError) as e:
            cli.apply_edit(CARDS["G4"], "drone.mass_t", raw)
        assert e.value.reason == reason


@pytest.mark.parametrize("raw", ["{x}", "a;b", "\x01"], ids=["braces", "semicolon", "control"])
def test_the_admission_edit_box_refusal_is_plain(raw):
    a = view.admit(I, "A1-survey", {"G4.hangar.mass_t": raw})
    assert a == {"refused": {"field": "G4.hangar.mass_t", "reason": "the value given is not a number"}}
    assert plain(f"EDIT REFUSED · {a['refused']['field']} · {a['refused']['reason']} · PREVIOUS VERDICT KEPT")


def test_sdv_admit_never_echoes_a_hostile_edit(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.drone.mass_t={x;y}"]) == 2
    out = capsys.readouterr().out
    assert out == "refused: G4 edit G4.drone.mass_t: the value given is not a number. Previous card kept.\n"


def test_a_long_field_name_is_cut_in_the_reason():
    field = "x" * 60
    with pytest.raises(cli.EditError) as e:
        cli.apply_edit(CARDS["G4"], field, "1")
    assert e.value.field == field and e.value.reason == f"no field {'x' * 37}... on the card"


def test_sdv_admit_cuts_a_long_field_name_where_it_echoes_it(capsys):
    target = "G4." + "x" * 60
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", f"{target}=1"]) == 2
    out = capsys.readouterr().out
    assert out == f"refused: G4 edit {target[:37]}...=1: no field {'x' * 37}... on the card. Previous card kept.\n"
    assert "x" * 41 not in out


def test_sdv_admit_cuts_a_long_card_id_and_describes_a_hostile_one(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", f"G{'9' * 60}.x=1"]) == 2
    out = capsys.readouterr().out
    assert "9" * 41 not in out and out.endswith(f"no card G{'9' * 36}.... Previous card kept.\n")
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G{1}.x=1"]) == 2
    assert capsys.readouterr().out == "refused: edit: no such card. Previous card kept.\n"


def test_the_admission_edit_box_cuts_a_long_field():
    target = "G4." + "x" * 60
    a = view.admit(I, "A1-survey", {target: "1"})
    assert a == {"refused": {"field": target[:37] + "...", "reason": f"no field {'x' * 37}... on the card"}}


def test_a_field_with_punctuation_is_described_not_echoed():
    with pytest.raises(cli.EditError) as e:
        cli.apply_edit(CARDS["G4"], "drone.mass;t", "1")
    assert e.value.reason == "the card has no such field"
    a = view.admit(I, "A1-survey", {"G4.{x}": "1"})
    assert a == {"refused": {"field": "the field given", "reason": "the card has no such field"}}


# ------------------------------------------------------------------------------------------------ 2 a profile too deep to log

@pytest.mark.parametrize("levels", [65, 500, 5000])
def test_the_door_refuses_a_profile_nested_too_deep(levels):
    with pytest.raises(ValueError) as e:
        check_input({"type": "profile_applied", "payload": {"profile": nested(levels)}})
    assert str(e.value) == "input 'profile_applied' refused: profile is nested too deep to log"


def test_lists_count_as_levels_and_64_levels_pass_the_door():
    deep_list: list = []
    for _ in range(64):
        deep_list = [deep_list]
    with pytest.raises(ValueError) as e:
        check_input({"type": "profile_applied", "payload": {"profile": {"notes": deep_list}}})
    assert str(e.value).endswith("profile is nested too deep to log")
    assert check_input({"type": "profile_applied", "payload": {"profile": nested(64)}})["payload"]["profile"] == nested(64)


def test_the_screen_refuses_a_deep_profile_and_the_run_keeps_ticking():
    """It used to step the simulator, raise in the standby's deepcopy, and fail every tick after ('ticks are never skipped')."""
    lr = live.LiveReplay("survey", 100, running=False)
    said = lr.command({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": nested(600)}}})
    assert said == "input 'profile_applied' refused: profile is nested too deep to log" and lr.run.laptop == {}
    lr.run.advance_to(103)
    assert lr.t_s == 103 and lr.run.standby == "in step"


def test_a_64_level_profile_is_refused_by_the_core_the_same_way_live_on_the_standby_and_in_a_replay(tmp_path):
    inputs = scripted_inputs()
    inputs[5] = [inp(5, "profile_applied", profile=nested(64))]
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=inputs, log_dir=tmp_path, standby=True)
    try:
        outs = list(loop.ticks(until=8))
    finally:
        loop.close()
    assert outs[-1].tick == 8 and loop.core.mission["id"] == "survey" and len(loop.core.rejected) == 1
    snaps, recs = replay(tmp_path, "survey")
    assert all(o.standby == "in step" for o in outs)
    assert snaps == (tmp_path / "snapshots.jsonl").read_text().splitlines()
    assert recs == (tmp_path / "decisions.jsonl").read_text().splitlines()


# ------------------------------------------------------------------------------------------------ 3 schema problems in words

@pytest.mark.parametrize("value,problem", [
    ("auto", f"confirm.r3.14: 'auto' is not one of {POLICIES}"),
    ("it's", f"confirm.r3.14: is not one of {POLICIES}"),
    ('say "yes"', f"confirm.r3.14: is not one of {POLICIES}"),
    (True, f"confirm.r3.14: is not one of {POLICIES}"),
    (3, f"confirm.r3.14: 3 is not one of {POLICIES}"),
])
def test_an_enum_problem_is_said_in_words(value, problem):
    assert mission_problems(profile(confirm={"r3": {"14": value}})) == [problem]


@pytest.mark.parametrize("value,problem", [
    ("Survey Jury", "id: 'Survey Jury' is not a plain lower-case name"),
    ("it's", "id: is not a plain lower-case name"),
])
def test_a_pattern_problem_is_said_in_words(value, problem):
    assert mission_problems(profile(id=value)) == [problem]


def test_a_guest_id_pattern_problem_is_said_in_words():
    assert mission_problems(profile(mission_critical=["g5"])) == ["mission_critical[0]: 'g5' is not a guest id such as G4"]


@pytest.mark.parametrize("prof,msg", [
    (profile(confirm={"r3": {"14": "auto"}}),
     f"Profile survey_jury refused: confirm.r3.14 (auto is not one of {POLICIES}). survey kept."),
    (profile(confirm={"r3": {"14": "it's"}}),
     f"Profile survey_jury refused: confirm.r3.14 (is not one of {POLICIES}). survey kept."),
    (profile(confirm={"r3": {"14": "it's", "6": "o'clock"}}),
     f"Profile survey_jury refused: confirm.r3.14 (is not one of {POLICIES}). survey kept."),
    (profile(weights=dict(MISSIONS["survey"]["weights"], sar_air="it's")),
     "Profile survey_jury refused: weights.sar_air (is text where a number is expected). survey kept."),
    (profile(id="it's"), "Profile refused: id (is not a plain lower-case name). survey kept."),
    (profile(**{"it's": 1}), "Profile survey_jury refused: has a field that is not allowed here. survey kept."),
    (profile(weights=dict(MISSIONS["survey"]["weights"], uav=0.5)),
     "Profile survey_jury refused: weights.uav (no loaded card returns this capability, the loaded cards return "
     "coastal_connectivity, fresh_water, ocean_data, passive_rf_detection, sar_air, seabed_inspection). survey kept."),
])
def test_the_profile_row_is_one_plain_sentence(prof, msg):
    r = live.Run("survey", {300: [inp(300, "profile_applied", profile=prof)]})
    r.advance_to(301)
    [row] = rows(r, "PROFILE")
    assert row["msg"] == msg and plain(row["msg"]), row["msg"]


def test_an_enum_problem_in_a_card_file_names_the_choices_without_brackets():
    card = copy.deepcopy(CARDS["G4"])
    card["cooling"] = "water"
    assert Ld.check_card(card, VOCAB, Ld._schema(Ld.ROOT, "manifests/schema.json")) == \
        ["cooling: 'water' is not one of chilled_water, air"]


# ------------------------------------------------------------------------------------------------ 4 jump, None and True, newline

@pytest.mark.parametrize("t", ["abc", None, float("nan"), float("inf"), [1], {"t": 1}, "9" * 5000],
                         ids=["text", "none", "nan", "inf", "list", "object", "5000 digits"])
def test_a_jump_to_a_time_that_is_not_a_number_is_refused_in_a_sentence(t):
    lr = live.LiveReplay("survey", 100, running=False)
    said = lr.command({"cmd": "jump", "t": t})
    assert said == "jump refused: the time given is not a number" and plain(said)
    assert lr.t_s == 100 and not lr.running


def test_a_jump_to_a_number_still_lands():
    lr = live.LiveReplay("survey", 100, running=False)
    assert lr.command({"cmd": "jump", "t": 140}) is None and lr.t_s == 140
    assert lr.command({"cmd": "jump", "t": "150"}) is None and lr.t_s == 150
    assert lr.command({"cmd": "jump", "t": 160.7}) is None and lr.t_s == 160


def test_the_fixture_replay_refuses_the_same_jump():
    rp = server.Replay(I, "survey", 100, 12, False)
    assert rp.command({"cmd": "jump", "t": "abc"}) == "jump refused: the time given is not a number" and rp.t_s == 100
    assert rp.command({"cmd": "jump", "t": 140}) is None and rp.t_s == 140


@pytest.mark.parametrize("type_,payload,reason", [
    ("genset_trip", {"genset": True, "confirmed": True}, "genset is true or false, not one of 1, 2"),
    ("crew_change", {"crew_aboard": None}, "crew_aboard is empty, not one of 14, 6, 0"),
    ("bridge_answer", {"request_seq": None, "answer": "denied"}, "request_seq is empty, not a whole number"),
    ("deck_report", {"deck": "clear", "wind_kn": True}, "wind_kn is true or false, not a number"),
    ("profile_applied", {"profile": None}, "profile is empty, not an object"),
    ("genset_trip", {"genset": 1, "confirmed": None}, "confirmed is empty, not true or false"),
])
def test_none_and_true_are_described_not_written_as_python_writes_them(type_, payload, reason):
    assert L._quoted(None) is None and L._quoted(True) is None and L._quoted(False) is None
    with pytest.raises(ValueError) as e:
        check_input({"type": type_, "payload": payload})
    assert str(e.value) == f"input {type_!r} refused: {reason}"
    assert "None" not in str(e.value) and "True" not in str(e.value)


@pytest.mark.parametrize("text", ["{x}", "a}", "x{"])
def test_the_door_never_quotes_a_brace(text):
    assert L._quoted(text) is None
    with pytest.raises(ValueError) as e:
        check_input({"type": "deck_report", "payload": {"deck": text}})
    assert str(e.value) == "input 'deck_report' refused: deck is text, not one of clear, not_clear"


def test_a_plain_name_never_carries_a_trailing_newline():
    assert PLAIN_ID.match("sar") and not PLAIN_ID.match("sar\n")
    assert L._FIELD.match("deck") and not L._FIELD.match("deck\n")
    assert live._name("sar\n") is None and live._no_file("sar\n") == "no such priority file is loaded"
    lr = live.LiveReplay("survey", 100, running=False)
    assert lr.command({"cmd": "mission", "value": "sar\n"}) == "no such priority file is loaded"
    with pytest.raises(ValueError) as e:
        check_input({"type": "deck_report", "payload": {"deck": "clear", "deck\n": 1}})
    assert str(e.value) == "input 'deck_report' refused: the payload has a field that is not in the contract"


def test_the_core_does_not_quote_a_swap_name_with_a_trailing_newline():
    r = live.Run("survey", {300: [inp(300, "priority_swap", mission="fishing\n")]})
    r.advance_to(301)
    assert r.loop.core.rejected[0]["problems"] == ["no priority file of that name is loaded"]
    assert r.loop.core.rejected[0]["profile"] is None


def test_a_builder_label_with_a_trailing_newline_is_refused(tmp_path):
    out = builder.save(I, "card", copy.deepcopy(CARDS["G4"]), "jury\n", tmp_path / "profiles", tmp_path / "drafts")
    assert out == {"problems": ["label: lower-case letters, digits and _ only, starting with a letter"]}
    assert not (tmp_path / "drafts").exists()
