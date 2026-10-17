"""Priority files (src/sdv/priority.py): the four shipped files validate; a hostile file is refused with
the failing field and the old file keeps running (freeze F3, BUILD_PLAN T7)."""
import pytest

from sdv.data import load_cards, load_missions
from sdv.priority import PriorityError, PriorityStore, validate

CARDS = load_cards()
MISSIONS = load_missions()


def test_the_shipped_files_validate_and_the_store_starts_on_the_requested_one():
    store = PriorityStore(MISSIONS, CARDS, "survey")
    assert set(store.missions) == {"survey", "sar", "patrol", "disaster_relief"} and store.active["id"] == "survey"


HOSTILE = [
    ({"id": "x"}, "(root)", "required"),
    ({"id": "Bad Id", "name": "n", "weights": {"sar_air": 1}, "mission_critical": []}, "id", "does not match"),
    ({"id": "w", "name": "n", "weights": {"sar_air": 1.5, "seabed_inspection": 1}, "mission_critical": []}, "weights.sar_air", "maximum"),
    ({"id": "w", "name": "n", "weights": {"sar_air": 1}, "mission_critical": []}, "weights", "no weight for capability"),
    ({"id": "w", "name": "n", "weights": dict(MISSIONS["sar"]["weights"], laser_cannon=1), "mission_critical": []}, "weights.laser_cannon", "no card"),
    ({"id": "w", "name": "n", "weights": MISSIONS["sar"]["weights"], "mission_critical": ["G9"]}, "mission_critical", "unknown guest"),
    ({"id": "w", "name": "n", "weights": MISSIONS["sar"]["weights"], "mission_critical": [], "shed_order": ["G7"]}, "shed_order", "unknown guest"),
    ({"id": "w", "name": "n", "weights": MISSIONS["sar"]["weights"], "mission_critical": [], "extra": 1}, "(root)", "Additional properties"),
]


@pytest.mark.parametrize("mission,field,why", HOSTILE)
def test_hostile_files_are_refused_with_the_failing_field(mission, field, why):
    with pytest.raises(PriorityError) as e:
        validate(mission, CARDS)
    assert e.value.field == field and why.lower() in e.value.why.lower()


def test_a_refused_swap_keeps_the_old_file_and_a_good_swap_switches():
    store = PriorityStore(MISSIONS, CARDS, "survey")
    rec = store.swap({"id": "w", "name": "n", "weights": {"sar_air": 1}, "mission_critical": []}, t_s=5)
    assert rec["result"] == "refused" and rec["kept"] == "survey" and store.active["id"] == "survey"
    rec = store.swap("sar", t_s=6)
    assert rec == {"t_s": 6, "result": "swapped", "from": "survey", "to": "sar"} and store.active["id"] == "sar"
    rec = store.swap(dict(MISSIONS["patrol"], id="jury", shed_order=["G5", "G4"]), t_s=7)
    assert rec["result"] == "swapped" and store.active["id"] == "jury" and store.active["shed_order"] == ["G5", "G4"]
    assert store.swap("nope", t_s=8)["result"] == "refused"


def test_swap_from_a_yaml_path(tmp_path):
    p = tmp_path / "jury.yaml"
    p.write_text("id: jury\nname: Jury\nweights: {sar_air: 1, coastal_connectivity: 1, ocean_data: 0.5, passive_rf_detection: 0.5, seabed_inspection: 0.2, fresh_water: 0.2}\nmission_critical: [G4]\n")
    store = PriorityStore(MISSIONS, CARDS, "survey")
    assert store.swap(p)["result"] == "swapped" and store.active["id"] == "jury"
    p.write_text("id: jury2\nweights: {}\n")
    rec = store.swap(p)
    assert rec["result"] == "refused" and store.active["id"] == "jury"
