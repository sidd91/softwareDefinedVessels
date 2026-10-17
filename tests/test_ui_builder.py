"""The profile and rule builder offers only what the loader accepts, names each refused field, and saves new files
without ever overwriting one."""
import copy

import yaml

from sdv import loader as Ld
from sdv.ui import builder, data

I = data.Inputs()


def test_the_catalog_comes_from_the_loaded_inputs():
    c = builder.catalog(I)
    assert {p["id"] for p in c["profiles"]} >= {"survey", "sar"}
    assert {x["name"] for x in c["capabilities"]} == {card["capability"]["name"] for card in I.cards.values()}
    assert c["responses"] == [{"id": "safety_command", "tag": "200 MS"}, {"id": "shed_first_action", "tag": "5 S"},
                              {"id": "shed_full_sequence", "tag": "60 S"}]
    assert c["crew_levels"] == [14, 6, 0] and "confirm" not in c["policies"]["0"]
    assert c["defaults"]["r3"] == {"14": "confirm", "6": "standing_plan", "0": "automatic"}
    names = {s["name"] for s in c["signals"]}
    assert {"G4.battery_pct", "emission", "wind_kn"} <= names and "bridge_requests" not in names
    assert next(s for s in c["signals"] if s["name"] == "emission")["ops"] == ["==", "!="]
    assert c["actions"] == ["land_or_ditch", "land", "return_and_land", "mode", "hold"]


def test_profile_checks_are_the_loaders():
    good = dict(copy.deepcopy(I.missions["sar"]), id="sar_edit", shed_order={"coastal_connectivity": 1}, confirm={"r3": {"6": "forbidden"}})
    assert builder.check(I, "profile", good) == []
    assert builder.check(I, "profile", dict(good, weights={"sar_air": 2})) == ["weights.sar_air: 2 is greater than the maximum of 1"]
    both = dict(good, response={"safety_command": ["G4"]})
    assert builder.check(I, "profile", both) == ["response.safety_command[0]: G4 is mission_critical (60 S); a guest has one response class"]
    assert builder.check(I, "nonsense", good) == ["kind: 'nonsense' is not profile or card"]


def test_card_rules_are_checked_against_the_vocabulary():
    card = copy.deepcopy(I.cards["G4"])
    card["hard_limits"].append({"when": {"signal": "wind_kn", "op": ">", "value": 30}, "then": {"action": "land", "within_min": 10}})
    assert builder.check(I, "card", card) == []
    card["hard_limits"].append({"when": {"signal": "G4.battery_pct", "op": "<", "value": 150}, "then": {"action": "land"}})
    assert builder.check(I, "card", card) == ["hard_limits[4].when.value: 150 is outside 0 to 100 %"]


def test_save_writes_a_new_file_the_loader_reads_and_never_overwrites(tmp_path):
    prof = dict(copy.deepcopy(I.missions["sar"]), id="sar_edit", name="Rescue edited", confirm={"r3": {"6": "forbidden"}})
    out = builder.save(I, "profile", prof, profiles_dir=tmp_path, drafts_dir=tmp_path)
    path = tmp_path / "sar_edit.yaml"
    assert out["path"] == str(path) and path.exists()
    loaded = Ld.load_mission(path, I.cards, I.vocab)
    assert loaded["confirm"] == {"r3": {6: "forbidden"}} and loaded["weights"] == prof["weights"]
    again = builder.save(I, "profile", prof, profiles_dir=tmp_path, drafts_dir=tmp_path)
    assert again["problems"] == ["file: sar_edit.yaml exists; files are never overwritten"]
    taken = builder.save(I, "profile", dict(prof, id="survey"), profiles_dir=tmp_path, drafts_dir=tmp_path)
    assert taken["problems"][0].startswith("id: survey is already a priority file")
    bad = builder.save(I, "profile", dict(prof, id="x", weights={"sar_air": 2}), profiles_dir=tmp_path, drafts_dir=tmp_path)
    assert bad["problems"] and not (tmp_path / "x.yaml").exists()


def test_a_card_is_saved_as_a_draft_the_loader_accepts(tmp_path):
    card = copy.deepcopy(I.cards["G6"])
    out = builder.save(I, "card", card, label="silence", profiles_dir=tmp_path, drafts_dir=tmp_path)
    path = tmp_path / "G6_silence.yaml"
    assert out["path"] == str(path)
    assert Ld.load_card(path, I.vocab) == yaml.safe_load(path.read_text())
    assert builder.save(I, "card", card, label="Bad Label", profiles_dir=tmp_path, drafts_dir=tmp_path)["problems"]
