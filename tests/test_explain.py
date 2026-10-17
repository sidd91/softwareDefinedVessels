"""Every engine decision becomes a schema-valid record whose one sentence carries its binding numbers."""
import json

import jsonschema
import pytest
import yaml

from sdv import admission as Ad
from sdv import arbitration as D3
from sdv import explain as E
from sdv import loader as Ld
from sdv import records as R
from sdv import shedding as D4

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SIGNALS = yaml.safe_load((Ld.ROOT / "config/signals.yaml").read_text())
SCHEMA = json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text())
CASES = yaml.safe_load((Ld.ROOT / "tests/oracles/expected_outcomes.yaml").read_text())["scenario_a"]
SNAP = {p.stem: json.loads(p.read_text()) for p in (Ld.ROOT / "tests/fixtures/snapshots").glob("*.json")}
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def d1_record(case):
    import copy
    cards = copy.deepcopy(CARDS)
    for key, value in case["card_edits"].items():
        gid, part, fld = key.split(".")
        next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part)[fld] = value
    layout = {k: v for k, v in case["placement"].items() if k.split(".")[0] in case["installed"]}
    adm = Ad.admit(A, cards, case["installed"], case["card"], MISSIONS[case["file"]], layout)
    return R.from_admission(adm, seq=0, tick=0, card_id=case["card"], installed=case["installed"], mission=MISSIONS[case["file"]], cards=cards)


def scenario_b_records():
    out = {}
    for f in ("survey", "sar"):
        out[f"m08-{f}"] = R.from_d3(D3.right_of_way(A, SIGNALS, CARDS, MISSIONS[f], SNAP["scenario_b_survey_m08"]), seq=1, snapshot=SNAP["scenario_b_survey_m08"])
    out["m12-survey"] = R.from_d4(D4.shed(CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m12"]), seq=2, snapshot=SNAP["scenario_b_survey_m12"])
    out["m12-sar"] = R.from_d4(D4.shed(CARDS, MISSIONS["sar"], SNAP["scenario_b_sar_m12"], {"G4": 35}), seq=2, snapshot=SNAP["scenario_b_sar_m12"])
    out["m19-survey"] = R.from_d4(D4.shed(CARDS, MISSIONS["survey"], SNAP["scenario_b_survey_m19"]), seq=3, snapshot=SNAP["scenario_b_survey_m19"])
    out["m19-sar"] = R.from_d4(D4.shed(CARDS, MISSIONS["sar"], SNAP["scenario_b_sar_m19"]), seq=3, snapshot=SNAP["scenario_b_sar_m19"])
    return out


D1 = {f"{c['case']}-{c['file']}": d1_record(c) for c in CASES}
B = scenario_b_records()
ALL = {**D1, **B}


@pytest.mark.parametrize("name", sorted(ALL))
def test_every_record_validates_and_its_sentence_is_operator_style(name):
    r = ALL[name]
    errors = sorted(VALIDATOR.iter_errors(r), key=lambda e: list(e.absolute_path))
    assert not errors, [f"{list(e.absolute_path)}: {e.message}" for e in errors]
    s = r["sentence"]
    assert ";" not in s and "—" not in s and len(s) < 320
    assert "demo" not in s.lower()


@pytest.mark.parametrize("name", sorted(D1))
def test_the_d1_sentence_carries_the_binding_numbers(name):
    r = D1[name]
    b = r["binding"]
    assert E.n(b["demand"]) in r["sentence"] and E.n(b["capacity"]) in r["sentence"]


EXPECTED = {
    "A1-survey": "Refused on mass: 10.035 t against 10 t, 35 kg over. Admit if G1 disembarks, mission value lost 0.2.",
    "A6-survey": "Admitted. Mass is the tightest line: 9.985 t against 10 t, 15 kg spare.",
    "A5-survey": "Admitted. Cooling is the tightest line: 100 kW against 120 kW, 20 kW spare. With one genset down it holds by moving G4 from fast charge to charge, 25 kW freed.",
    "m08-survey": "G4 recovers first: below 20 % it must land within 12 min, by minute 18.2, so waiting for the leg end is not possible. G3 holds depth and the survey pauses: 25 to 27 survey minutes lost.",
    "m08-sar": "G4 recovers first: below 20 % it must land within 12 min, by minute 18.2, so waiting for the leg end is not possible. The survey is suspended and G4's 35 kW charge is reserved. G3's leg is aborted with no resume time.",
    "m12-survey": "Holds: 48 of 95 kW, power limits (one genset down). Next step if needed: G5 full to low power, 37 kW.",
    "m12-sar": "Holds: 81 of 95 kW, power limits (one genset down). Next step if needed: G5 full to low power, 37 kW.",
    "m19-survey": "Cooling binds (cooling degraded): 81 kW against a 75 kW limit. G4 fast charge to charge frees 25 kW. Load 56 of 75 kW. G4 keeps 70 %.",
    "m19-sar": "Cooling binds (cooling degraded): 81 kW against a 75 kW limit. G5 full to low power frees 37 kW. Load 44 of 75 kW. G5 keeps 30 %.",
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_key_sentences(name):
    assert ALL[name]["sentence"] == EXPECTED[name]


def test_a_rejected_card_names_the_field():
    r = R.card_rejected(seq=0, tick=0, card_id="G4", field="placement.parts[1].mass_t: -1 is less than the minimum of 0", mission=MISSIONS["survey"])
    assert not list(VALIDATOR.iter_errors(r))
    assert r["sentence"].startswith("Card rejected: placement.parts[1].mass_t") and r["sentence"].endswith("Previous card kept.")


@pytest.mark.parametrize("verdict,expect", [("held", "Recovery held: the landing officer reports the zone not clear. G4 must land by minute 18.2."),
                                            ("forbidden", "Recovery forbidden at 0 aboard: deck activity since the last crew sweep voided the latch. G4 ditches by minute 18.2 and its rescue capability is lost.")])
def test_r3_sentences(verdict, expect):
    evidence = "the landing officer reports the zone not clear" if verdict == "held" else "deck activity since the last crew sweep voided the latch"
    r = {"kind": "D5", "verdict": verdict, "crew_aboard": 14 if verdict == "held" else 0, "deck_evidence": evidence, "deadline_t_s": 1091.9}
    assert E.sentence(r) == expect


def test_same_inputs_give_the_same_record():
    again = scenario_b_records()
    assert json.dumps(again, sort_keys=True) == json.dumps(B, sort_keys=True)
