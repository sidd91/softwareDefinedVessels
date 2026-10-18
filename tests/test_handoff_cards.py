"""Cards and priority files from the soak (soak 5, 9 and 10): a hostile file is refused with the field named, never a
crash, and the card-rejected sentence names the field and the rule in plain words."""
import copy
import json
import math

import pytest
import yaml

from sdv import cli
from sdv import loader as Ld
from sdv.loop import Loop, load_simulator
from sdv.ui import builder, data, server, view
from test_loader import HOSTILE_CARDS, HOSTILE_MISSIONS, card_problems, mission_problems
from test_ui_server import get, post, serve

I = data.Inputs()
VOCAB = Ld.load_vocabulary()
CARD_SCHEMA = Ld._schema(Ld.ROOT, "manifests/schema.json")
MISSION_SCHEMA = Ld._schema(Ld.ROOT, "config/missions/schema.json")
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
HUGE = 10 ** 400


@pytest.fixture(scope="module")
def api():
    srv, th, base = serve(server.create_app(I, source="fixtures"))
    yield base
    srv.should_exit = True
    th.join(timeout=5)


def profile(**fields) -> dict:
    return dict(copy.deepcopy(MISSIONS["survey"]), id="survey_jury", **fields)


# ------------------------------------------------------------------------------------------------ soak 5

BAD_CONFIRM = [
    ("one word for a rule", {"r3": "automatic"}, "confirm.r3:"),
    ("a list for a rule", {"r3": ["confirm"]}, "confirm.r3:"),
    ("one word for the block", "automatic", "confirm:"),
    ("a list for the block", ["r3"], "confirm:"),
    ("a number for a rule", {"r3": 14}, "confirm.r3:"),
]


@pytest.mark.parametrize("label,confirm,field", BAD_CONFIRM, ids=[b[0] for b in BAD_CONFIRM])
def test_a_profile_whose_confirm_is_not_a_block_is_refused_with_the_field_named(label, confirm, field):
    problems = Ld.check_mission(profile(confirm=confirm), CARDS, VOCAB, MISSION_SCHEMA)
    assert problems and problems[0].startswith(field), problems
    assert not any("{" in p or "[" + "'" in p for p in problems), problems   # no section dumped back
    assert builder.check(I, "profile", profile(confirm=confirm)) == problems


def test_a_priority_file_that_is_not_a_block_is_refused():
    for doc in (None, 5, "survey", ["survey"]):
        problems = Ld.check_mission(doc, CARDS, VOCAB, MISSION_SCHEMA)
        assert problems and problems[0].startswith("(root):"), problems


def test_the_builder_check_answers_a_bad_confirm_with_its_problems(api):
    status, out = post(api, "/api/builder/check", {"kind": "profile", "doc": profile(confirm={"r3": "automatic"})})
    assert status == 200 and out["problems"][0].startswith("confirm.r3:"), out


def test_the_loop_at_sea_refuses_a_bad_confirm_and_keeps_the_previous_profile(tmp_path):
    bad = profile(confirm={"r3": "automatic"})
    inputs = {300: [{"t_s": 300, "type": "profile_applied", "injected": False, "payload": {"profile": bad}}]}
    loop = Loop(load_simulator(mission="survey"), "survey", inputs=inputs, log_dir=tmp_path)
    try:
        ticks = [out.tick for out in loop.ticks(until=302)]
    finally:
        loop.close()
    assert ticks[-1] == 302
    assert loop.core.mission["id"] == "survey"
    (refused,) = loop.core.rejected
    assert refused["tick"] == 300 and refused["profile"] == "survey_jury" and refused["problems"][0].startswith("confirm.r3:")


# ------------------------------------------------------------------------------------------------ soak 9

def plain(sentence: str) -> bool:
    """A jury-facing sentence: no semicolon, one colon at most, nothing dumped from the card."""
    return ";" not in sentence and sentence.count(":") <= 1 and not any(c in sentence for c in "{}'")


def test_the_card_rejected_sentence_names_the_field_and_the_rule_in_plain_words():
    a = view.admit(I, "A4-survey", {"G3.installation.at_sea.people": "4.07"})
    assert a["verdict"] == "CARD REJECTED"
    assert a["sentence"] == "Card rejected: G3.installation.at_sea.people (4.07 is not a whole number)."
    assert a["rejected"] == {"field": "G3.installation.at_sea.people", "problem": "4.07 is not a whole number"}
    assert a["sentence"] == a["record"]["sentence"]


def test_the_refusal_line_names_the_field_inside_the_section_not_the_section():
    card = copy.deepcopy(CARDS["G3"])
    card["installation"]["at_sea"]["people"] = 4.07
    assert Ld.check_card(card, VOCAB, CARD_SCHEMA) == ["installation.at_sea.people: 4.07 is not of type 'integer'"]


REJECTED_EDITS = [
    ("A4-survey", "G3.installation.at_sea.people", "4.07", "4.07 is not a whole number"),
    ("A1-survey", "G4.hangar.mass_t", "-1", "-1 is less than the minimum of 0"),
    ("A1-survey", "G4.modes.0.capability_retained", "1.5", "1.5 is greater than the maximum of 1"),
    ("A1-survey", "G4.drone.mass_t", "9" * 400, "the number given is above 1000000, the largest number a file may carry"),
    ("A1-survey", "G4.consumes.power_kw.peak", "2e6", "2000000 is above 1000000, the largest number a file may carry"),
]


@pytest.mark.parametrize("case,field,raw,words", REJECTED_EDITS, ids=[r[1] + "=" + r[2][:8] for r in REJECTED_EDITS])
def test_every_card_rejected_sentence_is_plain(case, field, raw, words):
    a = view.admit(I, case, {field: raw})
    assert a["verdict_raw"] == "card-rejected" and a["sentence"] == f"Card rejected: {field} ({words}).", a["sentence"]
    assert plain(a["sentence"]), a["sentence"]
    json.dumps(a, allow_nan=False)


def test_in_words_keeps_no_semicolon_or_colon_from_a_hostile_text():
    said = Ld.in_words("hard_limits[0].when.value: 'x; y: z' is not of type 'number'")
    assert ";" not in said and ":" not in said and said.endswith("is not a number")
    assert Ld.in_words("conditions[0].requires.speed_kn: min 12 is above max 5") == "min 12 is above max 5"


# ------------------------------------------------------------------------------------------------ soak 10

def at_mass(value):
    def mutate(card):
        card["placement"]["parts"][0]["mass_t"] = value
    return mutate


NUMBERS = [
    ("inf", math.inf, "placement.parts[0].mass_t: inf is not a finite number"),
    ("minus inf", -math.inf, "placement.parts[0].mass_t: -inf is not a finite number"),
    ("nan", math.nan, "placement.parts[0].mass_t: nan is not a finite number"),
    ("400 digits", HUGE, "placement.parts[0].mass_t: the number given is above 1000000, the largest number a file may carry"),
    ("5000 digits", 10 ** 5000, "placement.parts[0].mass_t: the number given is above 1000000, the largest number a file may carry"),
    ("two million", 2e6, "placement.parts[0].mass_t: 2000000 is above 1000000, the largest number a file may carry"),
]


@pytest.mark.parametrize("label,value,problem", NUMBERS, ids=[n[0] for n in NUMBERS])
def test_a_card_number_that_is_not_finite_or_too_large_is_refused(label, value, problem):
    assert card_problems("G4", at_mass(value)) == [problem]


def test_a_huge_number_where_d1_converts_to_float_is_refused_not_a_crash():
    def limit(card):
        card["hard_limits"][0]["when"]["value"] = HUGE
    assert card_problems("G4", limit) == ["hard_limits[0].when.value: the number given is above 1000000, the largest number a file may carry"]


def test_the_largest_number_still_loads_and_every_shipped_card_and_file_is_valid():
    assert card_problems("G4", at_mass(1_000_000)) == []
    assert sorted(CARDS) == ["G1", "G2", "G3", "G4", "G5", "G6"] and sorted(MISSIONS) == ["disaster_relief", "patrol", "sar", "survey"]
    for gid, card in CARDS.items():
        assert Ld.check_card(card, VOCAB, CARD_SCHEMA) == [], gid
    for mid, m in MISSIONS.items():
        assert Ld.check_mission(m, CARDS, VOCAB, MISSION_SCHEMA) == [], mid


def test_a_priority_file_weight_that_is_not_finite_is_refused():
    assert Ld.check_mission(profile(weights=dict(MISSIONS["survey"]["weights"], sar_air=math.nan)), CARDS, VOCAB, MISSION_SCHEMA) == \
        ["weights.sar_air: nan is not a finite number"]
    assert Ld.check_mission(profile(shed_order={"sar_air": 10 ** 5000}), CARDS, VOCAB, MISSION_SCHEMA) == \
        ["shed_order.sar_air: the number given is above 1000000, the largest number a file may carry"]


def test_sdv_admit_refuses_a_400_digit_edit_with_the_field_named(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.drone.mass_t=" + "9" * 400]) == 2
    out = capsys.readouterr().out
    assert "refused: G4 edit G4.drone.mass_t=" in out and "above 1000000" in out and "VERDICT" not in out


@pytest.mark.parametrize("text,problem", [
    (".inf", "placement.parts[0].mass_t: inf is not a finite number"),
    (".nan", "placement.parts[0].mass_t: nan is not a finite number"),
    ("9" * 5000, "yaml: Exceeds the limit (4300 digits) for integer string conversion"),
], ids=["inf", "nan", "5000 digits"])
def test_a_card_file_with_a_number_out_of_bounds_is_refused_at_load(tmp_path, text, problem):
    raw = yaml.safe_dump(CARDS["G4"], sort_keys=False).replace("mass_t: 0.14", f"mass_t: {text}", 1)
    assert f"mass_t: {text}" in raw
    path = tmp_path / "G4.yaml"
    path.write_text(raw)
    with pytest.raises(Ld.LoadError) as e:
        Ld.load_card(path, VOCAB)
    assert e.value.problems[0].startswith(problem), e.value.problems
    refused = []
    assert sorted(Ld.load_cards(tmp_path, VOCAB, refused=refused)) == [] and len(refused) == 1   # start-up survives it


def test_the_builder_refuses_a_card_with_infinity():
    card = copy.deepcopy(CARDS["G4"])
    card["consumes"]["power_kw"]["peak"] = math.inf
    assert builder.check(I, "card", card) == ["consumes.power_kw.peak: inf is not a finite number"]


def test_api_admit_answers_a_huge_edit_with_a_card_rejected_decision(api):
    status, body = get(api, "/api/admit?case=A1-survey&edit=G4.drone.mass_t=" + "9" * 400)
    d = json.loads(body)
    assert (status, d["verdict"]) == (200, "CARD REJECTED") and "above 1000000" in d["sentence"]


# ------------------------------------------------------------------------------------------------ the facts still hold

def test_the_15_hostile_cards_and_8_hostile_priority_files_are_still_refused():
    assert len(HOSTILE_CARDS) == 15 and len(HOSTILE_MISSIONS) == 8
    for label, gid, mutate, expected in HOSTILE_CARDS:
        assert any(expected in p for p in card_problems(gid, mutate)), label
    for label, mid, mutate, expected in HOSTILE_MISSIONS:
        assert any(expected in p for p in mission_problems(mid, mutate)), label
