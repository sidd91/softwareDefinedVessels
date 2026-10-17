"""The loader accepts the six cards and four priority files and refuses hostile ones, naming the field."""
import copy

import pytest
import yaml

from sdv import loader as L

VOCAB = L.load_vocabulary()
CARD_SCHEMA = L._schema(L.ROOT, "manifests/schema.json")
MISSION_SCHEMA = L._schema(L.ROOT, "config/missions/schema.json")
CARDS = L.load_cards(vocab=VOCAB)
MISSIONS = L.load_missions(CARDS, VOCAB)


def test_all_six_cards_and_four_priority_files_load():
    assert sorted(CARDS) == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert sorted(MISSIONS) == ["disaster_relief", "patrol", "sar", "survey"]


def card_problems(gid, mutate):
    card = copy.deepcopy(CARDS[gid])
    mutate(card)
    return L.check_card(card, VOCAB, CARD_SCHEMA)


def first_condition(card):
    return card["conditions"][0]["requires"]


HOSTILE_CARDS = [
    ("unknown signal", "G4", lambda c: first_condition(c).update(wind_kn_max=25), "requires.wind_kn_max: unknown signal"),
    ("enum value", "G3", lambda c: c["conditions"][0]["requires"].update(noise="silent"), "requires.noise: 'silent' is not one of"),
    ("range on an enum", "G2", lambda c: c["conditions"][0]["requires"].update(course={"max": 1}), "requires.course: a range needs a number signal"),
    ("list on a number", "G4", lambda c: first_condition(c).update(speed_kn=[5, 12]), "requires.speed_kn: a list of choices needs an enum signal"),
    ("min above max", "G4", lambda c: first_condition(c).update(speed_kn={"min": 12, "max": 5}), "min 12 is above max 5"),
    ("out of range", "G4", lambda c: first_condition(c).update(wind_kn={"max": 500}), "outside 0 to 80 kn"),
    ("not a boolean", "G4", lambda c: first_condition(c).update(heading_free="free"), "requires.heading_free: 'free' is not true or false"),
    ("unknown activity", "G3", lambda c: c["conditions"][0].update(activity="diving"), "conditions[0].activity: 'diving' is not a G3 activity"),
    ("exclusion target", "G2", lambda c: c["relations"]["excludes"][1].update(excludes="G4.recovering"), "relations.excludes[1].excludes: G4.recovering: G4 has no activity 'recovering'"),
    ("limit signal", "G4", lambda c: c["hard_limits"][0]["when"].update(signal="battery_pct"), "hard_limits[0].when.signal: unknown signal 'battery_pct'"),
    ("limit value", "G4", lambda c: c["hard_limits"][1]["when"].update(value="quiet"), "hard_limits[1].when.value: 'quiet' is not one of"),
    ("limit mode", "G6", lambda c: c["hard_limits"][0]["then"].update(mode="drain"), "hard_limits[0].then.mode: 'drain' is not one of G6's modes"),
    ("position", "G3", lambda c: c["relations"].update(requires=["slipway"]), "relations.requires[0]: 'slipway' is not a ship position"),
    ("free text limit", "G4", lambda c: c["hard_limits"][0].update(when="battery_pct < 20"), "hard_limits[0].when:"),
    ("free text exclusion", "G6", lambda c: c["relations"].update(excludes=[{"what": "G6.production", "when": "G3.surveying", "kind": "conditional"}]), "relations.excludes[0]:"),
]


@pytest.mark.parametrize("label,gid,mutate,expected", HOSTILE_CARDS, ids=[h[0] for h in HOSTILE_CARDS])
def test_a_hostile_card_is_refused_with_the_field_named(label, gid, mutate, expected):
    problems = card_problems(gid, mutate)
    assert any(expected in p for p in problems), problems


def mission_problems(mid, mutate):
    m = copy.deepcopy(MISSIONS[mid])
    mutate(m)
    return L.check_mission(m, CARDS, VOCAB, MISSION_SCHEMA)


HOSTILE_MISSIONS = [
    ("typo in a weight", "survey", lambda m: m["weights"].update(uav=0.5), "weights.uav: no loaded card returns this capability"),
    ("weight above 1", "sar", lambda m: m["weights"].update(sar_air=1.5), "weights.sar_air:"),
    ("unknown guest", "sar", lambda m: m["mission_critical"].append("G9"), "mission_critical[1]: no loaded card G9"),
    ("shed order name", "disaster_relief", lambda m: m.update(shed_order={"desalination": 1}), "shed_order.desalination: no loaded card"),
    ("shed rank zero", "survey", lambda m: m.update(shed_order={"coastal_connectivity": 0}), "shed_order.coastal_connectivity:"),
    ("unknown rule", "survey", lambda m: m.update(confirm={"r9": {14: "confirm"}}), "confirm.r9: no rule 'r9'"),
    ("confirm at 0 aboard", "survey", lambda m: m.update(confirm={"r3": {0: "confirm"}}), "confirm.r3.0:"),
    ("missing weights", "patrol", lambda m: m.pop("weights"), "'weights' is a required property"),
]


@pytest.mark.parametrize("label,mid,mutate,expected", HOSTILE_MISSIONS, ids=[h[0] for h in HOSTILE_MISSIONS])
def test_a_hostile_priority_file_is_refused_with_the_field_named(label, mid, mutate, expected):
    problems = mission_problems(mid, mutate)
    assert any(expected in p for p in problems), problems


def test_a_valid_confirm_and_shed_order_load():
    assert not mission_problems("disaster_relief", lambda m: m.update(shed_order={"fresh_water": -1}, confirm={"r3": {14: "confirm", 6: "standing_plan", 0: "forbidden"}}))


def test_try_load_keeps_the_previous_card_and_names_the_field(tmp_path):
    bad = copy.deepcopy(CARDS["G4"])
    bad["hard_limits"][0]["when"]["signal"] = "battery"
    path = tmp_path / "G4.yaml"
    path.write_text(yaml.safe_dump(bad))
    kept, err = L.try_load(L.load_card, path, CARDS["G4"], VOCAB)
    assert kept == CARDS["G4"]
    assert err is not None and err.path == str(path)
    assert "hard_limits[0].when.signal: unknown signal 'battery'" in str(err)


def test_try_load_accepts_a_one_number_edit(tmp_path):
    edited = copy.deepcopy(CARDS["G4"])
    hangar = next(p for p in edited["placement"]["parts"] if p["name"] == "hangar")
    hangar["mass_t"] = 0.8
    path = tmp_path / "G4.yaml"
    path.write_text(yaml.safe_dump(edited))
    card, err = L.try_load(L.load_card, path, CARDS["G4"], VOCAB)
    assert err is None and card == edited


def test_every_card_activity_with_conditions_is_registered():
    for gid, card in CARDS.items():
        registered = {a for a, v in VOCAB.activities[gid].items() if v["card"]}
        assert {c["activity"] for c in card.get("conditions", [])} == registered, gid
