"""Checks the mission priority file schema and the loader rule it states, before any engine exists.

A priority file is the jury's swappable input (brief D3), so a bad one must be refused with the field that
is wrong. The schema holds the structure, including the two optional fields of the design freeze (WORKLOG
DEC-44, F3): `shed_order`, keyed by capability name like `weights`, and a per-rule crew policy `confirm`.
`refusals` below adds the checks a schema cannot make alone: names the ship profile and the loaded cards
do not define. The governor's loader must refuse at least what `refusals` refuses.
"""
import copy
import glob
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
CARDS = {c["id"]: c for c in (yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "manifests/G*.yaml"))))}
SCHEMA = json.loads((ROOT / "config/missions/schema.json").read_text())
V = Draft202012Validator(SCHEMA)
FILES = {Path(f).stem: yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "config/missions/*.yaml")))}
CAPABILITIES = {c["capability"]["name"] for c in CARDS.values()}


def refusals(m):
    """Every reason to refuse priority file m, each starting with the field that is wrong.

    The schema runs on the file's JSON form, so crew levels YAML reads as integers (0, 6, 14) become the
    strings the schema names."""
    doc = json.loads(json.dumps(m))
    out = [f"{'/'.join(map(str, e.absolute_path)) or '(file)'}: {e.message}" for e in V.iter_errors(doc)]
    if isinstance(doc, dict):
        out += [f"shed_order/{k}: no loaded guest card returns this capability"
                for k in doc.get("shed_order") or {} if k not in CAPABILITIES]
        out += [f"confirm/{k}: the ship profile defines no such rule" for k in doc.get("confirm") or {} if k not in A["rules"]]
        out += [f"mission_critical: {g} is not a loaded guest" for g in doc.get("mission_critical") or [] if g not in CARDS]
    return out


def with_fields(file_id, **fields):
    m = copy.deepcopy(FILES[file_id])
    m.update(fields)
    return m


def test_the_four_priority_files_are_accepted():
    assert sorted(FILES) == ["disaster_relief", "patrol", "sar", "survey"]
    for file_id, m in FILES.items():
        assert refusals(m) == [], file_id


def test_survey_and_sar_declare_no_shed_order():
    # A declared order in either file would replace the computed ladders that give Scenario B its two
    # outcomes at minute 19 (DEC-40). Disaster relief keeps G5 last through mission_critical instead.
    assert "shed_order" not in FILES["survey"] and "shed_order" not in FILES["sar"]
    assert "G5" in FILES["disaster_relief"]["mission_critical"]


def test_confirm_at_zero_aboard_is_refused():
    m = with_fields("survey", confirm={"r3": {14: "confirm", 6: "standing_plan", 0: "confirm"}})
    found = refusals(m)
    assert len(found) == 1 and found[0].startswith("confirm/r3/0: 'confirm' is not one of"), found


def test_unknown_capability_in_shed_order_is_refused():
    m = with_fields("sar", shed_order={"coastal_connectivity": 1, "sonar_imaging": -1})
    assert refusals(m) == ["shed_order/sonar_imaging: no loaded guest card returns this capability"]


def test_a_declared_order_and_crew_policy_are_accepted():
    m = with_fields("disaster_relief", shed_order={"coastal_connectivity": -1, "seabed_inspection": 1},
                    confirm={"r3": {14: "confirm", 6: "standing_plan", 0: "automatic"}})
    assert refusals(m) == []


@pytest.mark.parametrize("fields,field", [
    ({"priority": "high"}, "(file)"),
    ({"weights": {"sar_air": 1.5}}, "weights/sar_air"),
    ({"shed_order": {"sar_air": 0}}, "shed_order/sar_air"),
    ({"shed_order": {"sar_air": "last"}}, "shed_order/sar_air"),
    ({"shed_order": {"sar_air": 1.5}}, "shed_order/sar_air"),
    ({"confirm": {"r9": {14: "confirm"}}}, "confirm/r9"),
    ({"confirm": {"r3": {3: "automatic"}}}, "confirm/r3"),
    ({"confirm": {"r3": {14: "ask"}}}, "confirm/r3/14"),
    ({"confirm": {"r3": {}}}, "confirm/r3"),
    ({"mission_critical": ["G9"]}, "mission_critical"),
], ids=["unknown field", "weight over 1", "rank 0", "rank text", "rank fraction", "unknown rule",
        "unknown crew level", "unknown policy", "empty policy", "unknown guest"])
def test_a_hostile_file_is_refused_with_the_field_named(fields, field):
    found = refusals(with_fields("sar", **fields))
    assert found and all(f.split(": ")[0] == field for f in found), found


def test_a_file_without_weights_is_refused():
    m = copy.deepcopy(FILES["survey"])
    del m["weights"]
    assert refusals(m) == ["(file): 'weights' is a required property"]


def test_r3_default_crew_policy_fits_the_schema():
    # The default a priority file may override (rules.r3.confirm): confirm at 14, standing plan at 6,
    # automatic at 0, where it means a recovery only on a deck latched clear at the last crew sweep.
    default = A["rules"]["r3"]["confirm"]
    assert default == {14: "confirm", 6: "standing_plan", 0: "automatic"}
    assert set(default) == set(A["crew"]["levels"])
    assert refusals(with_fields("survey", confirm={"r3": default})) == []
