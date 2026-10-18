"""D1 judges the data links (SATCOM, line-of-sight radio, backbone) at the guests' minimum rates (DEC-38) and the
mission rack's guest cores at nominal, so an oversubscribed link or rack has a line to name; no oracle verdict moves."""
import copy
import json

import jsonschema
import pytest
import yaml

from sdv import admission as Ad
from sdv import ledger as Lg
from sdv import loader as Ld
from sdv import records as Rec
from sdv.ui import data, view

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
CARD_SCHEMA = Ld._schema(Ld.ROOT, "manifests/schema.json")
VALIDATOR = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))
ORACLE = yaml.safe_load((Ld.ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
CASES = ORACLE["scenario_a"]
IDS = [f"{c['case']}-{c['file']}" for c in CASES]
LINKS = ("satcom", "los_radio", "backbone")
NEW = LINKS + ("compute",)
RACK = A["compute"]["nodes"] * A["compute"]["cores_per_node"] * A["compute"]["guest_share"]


def cards_with(part_edits=None, consumes=None):
    """The cards with part fields (G4.hangar.mass_t) and consumed quantities (G1.data_satcom_mbps.min) edited in memory."""
    cards = copy.deepcopy(CARDS)
    for key, value in (part_edits or {}).items():
        gid, part_name, fld = key.split(".")
        next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)[fld] = value
    for key, value in (consumes or {}).items():
        gid, quantity, fld = key.split(".")
        cards[gid]["consumes"][quantity][fld] = value
    return cards


def case_of(cid):
    return CASES[IDS.index(cid)]


def run(case, consumes=None):
    cards = cards_with(case["card_edits"], consumes)
    for gid in case["installed"] + [case["card"]]:
        assert Ld.check_card(cards[gid], VOCAB, CARD_SCHEMA) == [], gid  # still a card the jury could bring
    layout = {k: v for k, v in case["placement"].items() if k.split(".")[0] in case["installed"]}
    return cards, Ad.admit(A, cards, case["installed"], case["card"], MISSIONS[case["file"]], layout)


# ------------------------------------------------------------------------------------------------ the lines

@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_every_oracle_case_carries_the_four_lines_and_keeps_its_verdict(case):
    _, r = run(case)
    assert (r.verdict, r.binding.cls) == (case["verdict"], case["binding"]["class"])
    assert set(NEW) <= set(r.lines) and not any(r.lines[c].over for c in NEW)
    assert {r.lines[c].unit for c in LINKS} == {"Mbit/s"} and r.lines["compute"].unit == "cores"
    assert (r.lines["satcom"].capacity, r.lines["los_radio"].capacity, r.lines["backbone"].capacity) == \
        (A["data"]["satcom_envelope_mbps"], A["data"]["los_radio_operating_mbps"], A["data"]["backbone_mbps"])
    assert r.lines["compute"].capacity == pytest.approx(RACK)


def test_the_four_lines_are_ship_wide_so_a_yes_can_name_the_tightest_of_them():
    assert set(NEW) <= set(Ad.SHIP_WIDE)


def test_satcom_is_judged_at_the_guests_minimum_rates():
    """The oracle's SATCOM row (assumption 8): G1 0.2 + G2 0 (it buffers) + G5 1 at minimum, not G5's 6 nominal."""
    s = ORACLE["satcom"]
    line = Lg.admission_lines(A, CARDS, s["guests"])["satcom"]
    assert line.demand == pytest.approx(s["demand_mbps_at_min"])
    assert line.contributors == {g: CARDS[g]["consumes"]["data_satcom_mbps"]["min"] for g in s["guests"]}
    assert line.capacity == s["capacity_mbps"] < s["g5_nominal_mbps"] == CARDS["G5"]["consumes"]["data_satcom_mbps"]["nominal"]


def test_a_rate_without_a_minimum_counts_at_nominal_and_an_undeclared_link_counts_nothing():
    lines = Lg.admission_lines(A, CARDS, ["G3", "G4", "G6"])
    assert lines["backbone"].contributors == {g: CARDS[g]["consumes"]["data_backbone_mbps"]["nominal"] for g in ("G3", "G6")}
    assert lines["los_radio"].contributors == {"G4": CARDS["G4"]["consumes"]["data_los_radio_mbps"]["min"]}
    assert lines["satcom"].contributors == {} and lines["satcom"].demand == 0
    assert lines["compute"].contributors == {g: CARDS[g]["consumes"]["compute_cores"]["nominal"] for g in ("G3", "G4", "G6")}
    assert lines["compute"].demand == pytest.approx(sum(lines["compute"].contributors.values()))


# ------------------------------------------------------------------------------------------------ binding cases

def test_satcom_binds_when_the_card_itself_oversubscribes_the_link():
    """A2's set (G2, G3, G4 aboard, G1 the card) with G1 asking 3 Mbit/s of SATCOM at minimum: 3 against the 2 Mbit/s
    envelope floor is more over than the 35 kg of mass, and no removal helps because the card is the one asking."""
    cards, r = run(case_of("A2-survey"), {"G1.data_satcom_mbps.min": 3, "G1.data_satcom_mbps.nominal": 3})
    assert r.verdict == "no"
    assert (r.binding.cls, r.binding.demand, r.binding.capacity, r.binding.unit) == ("satcom", 3, A["data"]["satcom_envelope_mbps"], "Mbit/s")
    assert [l.cls for l in r.over] == ["satcom", "mass"] and r.options == []
    assert r.binding.contributors == {"G2": 0, "G1": 3}


def test_satcom_binds_and_the_installed_guest_of_least_value_gives_way():
    """A5's set (G1, G2, G5 aboard, G4 the card) with G5 needing the whole 2 Mbit/s floor at minimum: 2.2 against 2;
    G4 brings no SATCOM, so an installed guest gives way, under rescue G1 (0.5 lost) before G5 (1.0 lost)."""
    cards, r = run(case_of("A5-sar"), {"G5.data_satcom_mbps.min": A["data"]["satcom_envelope_mbps"]})
    assert r.verdict == "yes-if" and r.binding.cls == "satcom"
    assert r.binding.demand == pytest.approx(sum(Lg.judged_rate(cards[g]["consumes"]["data_satcom_mbps"]) for g in ("G1", "G2", "G5")))
    assert r.binding.capacity == A["data"]["satcom_envelope_mbps"] and [l.cls for l in r.over] == ["satcom"]
    assert [o.remove for o in r.options] == [["G1"], ["G5"]]
    assert r.options[0].value_lost == MISSIONS["sar"]["weights"]["passive_rf_detection"]


def test_compute_binds_and_the_guest_that_fills_the_rack_is_the_one_that_leaves():
    """A1's set (G1, G2, G3 aboard, G4 the card) with G3 asking 500 cores: 508 against the rack's guest share is far
    more over than the 35 kg of mass; the only fix is G3 off the ship, mission-critical under survey."""
    cards, r = run(case_of("A1-survey"), {"G3.compute_cores.nominal": 500})
    assert r.verdict == "yes-if" and (r.binding.cls, r.binding.unit) == ("compute", "cores")
    assert r.binding.demand == pytest.approx(sum(cards[g]["consumes"]["compute_cores"]["nominal"] for g in ("G1", "G2", "G3", "G4")))
    assert r.binding.capacity == pytest.approx(RACK) and [l.cls for l in r.over] == ["compute", "mass"]
    assert r.options[0].remove == ["G3"] and r.options[0].mission_critical and all("G3" in o.remove for o in r.options)


# ------------------------------------------------------------------------------------------------ record, sentence, screen

def test_the_record_validates_and_the_sentence_names_the_link_in_its_own_unit():
    case = case_of("A2-survey")
    cards, r = run(case, {"G1.data_satcom_mbps.min": 3, "G1.data_satcom_mbps.nominal": 3})
    rec = Rec.from_admission(r, seq=0, tick=0, card_id=case["card"], installed=case["installed"], mission=MISSIONS["survey"], cards=cards)
    assert not list(VALIDATOR.iter_errors(rec))
    assert (rec["binding"]["label"], rec["binding"]["unit"], rec["binding"]["free"]) == ("SATCOM", "Mbit/s", A["data"]["satcom_envelope_mbps"] - 3)
    assert rec["sentence"] == "SATCOM binds: 3 Mbit/s against 2 Mbit/s, 1 Mbit/s over. No removal set fits."
    assert [l["class"] for l in rec["also_failing"]] == ["mass"]


def test_the_admit_screen_lists_the_four_lines_and_can_show_one_binding():
    I = data.Inputs()
    a = view.admit(I, "A5-survey")
    names = [l["k"] for l in a["lines"]]
    assert names[: 10] == ["MASS", "STABILITY", "POWER", "CHW AT 30 °C", "LINE PORT", "LINE STBD", "SATCOM", "LOS RADIO", "BACKBONE", "COMPUTE"]
    satcom = next(l for l in a["lines"] if l["k"] == "SATCOM")
    assert satcom["v"] == f"{ORACLE['satcom']['demand_mbps_at_min']:.1f} / {A['data']['satcom_envelope_mbps']:.1f} Mbit/s" and satcom["s"] == "OK"
    b = view.admit(I, "A2-survey", {"G1.consumes.data_satcom_mbps.min": "3", "G1.consumes.data_satcom_mbps.nominal": "3"})
    assert b["verdict"] == "NO" and b["binding"] == "SATCOM 3.0 / 2.0 Mbit/s"
    assert next(l for l in b["lines"] if l["k"] == "SATCOM")["s"] == "OVER" and not list(VALIDATOR.iter_errors(b["record"]))
