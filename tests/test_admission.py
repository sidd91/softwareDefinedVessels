"""D1 + D2 (src/sdv/admission.py, placement.py) against every Scenario A drill in the oracle file:
verdict, binding line, placement, ranked yes-if options with their placements and moves, the
one-genset-down line and fix, and the seawater tipping point. Plus the rules the engine must keep."""
from pathlib import Path

import pytest
import yaml

from sdv import admission, placement as P
from sdv.data import load_assumptions, load_cards, load_missions

ROOT = Path(__file__).resolve().parents[1]
A = load_assumptions()
CARDS = load_cards()
MISSIONS = load_missions()
CASES = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())["scenario_a"]
IDS = [f"{c['case']}-{c['file']}" for c in CASES]
EPS = 1e-6


def installed_of(case):
    return {k: v for k, v in case["placement"].items() if k.split(".")[0] in case["installed"]}


def run(case):
    return admission.decide(A, CARDS, MISSIONS[case["file"]], installed_of(case), case["card"], case["card_edits"])


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_verdict_binding_and_as_given_placement(case):
    d = run(case)
    assert d.kind == "D1" and d.verdict == case["verdict"]
    assert d.binding.cls == case["binding"]["class"]
    assert d.binding.demand == pytest.approx(case["binding"]["demand"], abs=EPS)
    assert d.binding.capacity == pytest.approx(case["binding"]["capacity"], abs=EPS)
    assert d.placement == case["placement"]
    for ln in case.get("other_lines", []):
        if ln["class"] == "placement":
            assert any(k for k, v in d.placement.items() if v is None)
            continue
        if ln["class"] in admission.LEDGER:
            got = next(x for x in d.extras["lines"] if x["class"] == ln["class"])
            assert got["demand"] == pytest.approx(ln["demand"], abs=EPS) and got["capacity"] == pytest.approx(ln["capacity"], abs=EPS)
            assert got["fails"] == ln.get("fails", False)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_yes_if_options_match_in_order_value_and_placement(case):
    d = run(case)
    got = d.extras["yes_if"]
    assert [o["remove"] for o in got] == [o["remove"] for o in case["yes_if"]]
    for g, e in zip(got, case["yes_if"]):
        assert g["value_lost"] == pytest.approx(e["value_lost"], abs=EPS)
        assert g["mission_critical"] == e.get("mission_critical", False)
        if "mass_after_t" in e:
            assert g["mass_after_t"] == pytest.approx(e["mass_after_t"], abs=EPS)
        if "stability_after_t_eq" in e:
            assert g["stability_after_t_eq"] == pytest.approx(e["stability_after_t_eq"], abs=EPS)
        if "placement" in e:
            assert g["placement"] == e["placement"]
        if "also" in e:
            assert [(m["part"], m["to"]) for m in g["moves"]] == list(e["also"]["move"].items())
            assert g["crane"]["moves"] == e["also"]["crane_moves"] and g["crane"]["hours"] == e["also"]["hours"]
        else:
            assert g["moves"] == []
        if "one_genset_down" in e:
            check_ogd(g["one_genset_down"], e["one_genset_down"])
        if "seawater_tip_c" in e:
            assert g["seawater"]["tip_c"] == pytest.approx(e["seawater_tip_c"], abs=0.01)
    for ne in case.get("not_enough", []):
        got_ne = next(x for x in d.extras["not_enough"] if x["remove"] == ne["remove"])
        assert got_ne["mass_after_t"] == pytest.approx(ne["mass_after_t"], abs=EPS)


def check_ogd(got, exp):
    assert got["load_kw"] == pytest.approx(exp["load_kw"], abs=EPS) and got["reserve_kw"] == exp["reserve_kw"]
    assert got["holds"] == exp["holds"]
    if "short_kw" in exp:
        assert got["short_kw"] == pytest.approx(exp["short_kw"], abs=EPS)
    if exp.get("fix"):
        f, e = got["fix"][0], exp["fix"][0]
        assert (f["guest"], f["from_mode"], f["to_mode"], f["frees_kw"]) == (e["guest"], e["from_mode"], e["to_mode"], e["frees_kw"])
        assert got["status"] == "holds by throttling"
        if "load_after_kw" in e:
            assert got["load_kw"] - f["frees_kw"] == pytest.approx(e["load_after_kw"], abs=EPS)
    else:
        assert got["status"] == "holds" and not got["fix"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_one_genset_down_and_seawater_tip_for_the_set_as_given(case):
    d = run(case)
    if case.get("one_genset_down"):
        check_ogd(d.extras["one_genset_down"], case["one_genset_down"])
    else:
        assert d.extras["one_genset_down"] is None  # the card could not be placed as given
    if case["seawater_tip_c"] is None:
        assert d.extras["seawater"] is None
    else:
        tip = d.extras["seawater"]
        assert tip["tip_c"] == pytest.approx(case["seawater_tip_c"], abs=0.01)
        if "seawater_scan" in case:
            assert (tip["holds_at_c"], tip["fails_at_c"]) == (case["seawater_scan"]["holds_at_c"], case["seawater_scan"]["fails_at_c"])
        else:
            assert tip["inside_scan"] == (case["seawater_tip_c"] <= A["admission"]["seawater_scan_max_c"])


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_default_installed_layout_reproduces_the_oracle_layout(case):
    assert P.default_installed(A, CARDS, case["installed"]) == installed_of(case)


def test_sentences_are_built_from_the_binding_numbers():
    a1 = run(next(c for c in CASES if c["case"] == "A1" and c["file"] == "survey"))
    assert a1.sentence.startswith("Yes-if. Binding: mass, 10.04 of 10 t; 0.04 t over. In order of mission value lost under survey: remove G1 (0.2 value lost")
    assert "remove G3 (1 value lost, mission-critical" in a1.sentence
    a5 = run(next(c for c in CASES if c["case"] == "A5" and c["file"] == "survey"))
    assert a5.sentence.startswith("Yes. Binding: heat, 100 of 120 kW at 30 °C; 20 kW free. One genset down: 101.5 of 100 kW, 1.5 kW short as loaded; holds by throttling G4 to charge (25 kW freed, 30 % of G4's capability lost), automatic within 5 s, no guest switched off.")
    assert "Cooling flips at 39 °C seawater, outside the 12-30 °C envelope." in a5.sentence
    assert "Placement: drone to flight_deck, hangar to flight_deck." in a5.sentence
    a3 = run(next(c for c in CASES if c["case"] == "A3" and c["file"] == "sar"))
    assert "also failing: stability, heat, placement" in a3.sentence
    assert "remove G3 (0.2 value lost; 7.52 t; one genset down holds by throttling at 100 kW)" in a3.sentence
    a4 = run(next(c for c in CASES if c["case"] == "A4" and c["file"] == "sar"))
    assert "G5.node bay1_half to bay2, 1 crane move 4-8 h" in a4.sentence


def test_a_card_nothing_can_fix_is_refused():
    cards = admission.apply_edits(CARDS, {"G6.unit.mass_t": 20.0})
    d = admission.decide(A, cards, MISSIONS["sar"], P.default_installed(A, CARDS, ["G4"]), "G6")
    assert d.verdict == "no" and d.binding.cls in ("mass", "placement") and d.sentence.startswith("No.")
    assert d.extras["yes_if"] == []


def test_live_edits_reach_the_consumption_and_placement_fields():
    cards = admission.apply_edits(CARDS, {"G4.hangar.mass_t": 0.8, "G4.power_kw.nominal": 12})
    assert next(p for p in cards["G4"]["placement"]["parts"] if p["name"] == "hangar")["mass_t"] == 0.8
    assert cards["G4"]["consumes"]["power_kw"]["nominal"] == 12 and CARDS["G4"]["consumes"]["power_kw"]["nominal"] == 10


def test_slot_rules_from_the_positions_table():
    bad = {"G1.sensor": "mast_free", "G5.node": "bay2", "G5.antenna": "mast_free"}
    why = [r.why for r in P.slot_rejections(A, CARDS, bad)]
    assert any("mast_free holds 1 guest" in w for w in why) and any("60 kg" in w for w in why) and any("0.6 m2" in w for w in why)
    assert P.valid(A, CARDS, {"G5.node": "bay1_half", "G6.unit": "bay1_half"})
    assert not P.valid(A, CARDS, {"G2.module": "bay1_half", "G6.unit": "bay1_half"})  # G2 needs the bay clear
    assert not P.valid(A, CARDS, {"G3.cradle": "bay1", "G3.vehicle": "bay1", "G6.unit": "bay1_half"})
    assert P.valid(A, CARDS, {"G4.drone": "flight_deck", "G4.hangar": "flight_deck"})
    heavy = admission.apply_edits(CARDS, {"G4.drone.mass_t": 0.2})
    assert any("150 kg" in r.why for r in P.slot_rejections(A, heavy, {"G4.drone": "flight_deck", "G4.hangar": "flight_deck"}))


def test_admission_is_well_inside_its_ceiling():
    import time
    t0 = time.perf_counter()
    for case in CASES:
        run(case)
    assert (time.perf_counter() - t0) / len(CASES) < 1.0  # seconds per drill, against a 30 s ceiling
