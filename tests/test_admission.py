"""D1 admission and D2 placement reproduce every Scenario A case in the oracle, from the cards alone."""
import copy

import pytest
import yaml

from sdv import admission as Ad
from sdv import loader as Ld

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
CASES = yaml.safe_load((Ld.ROOT / "tests/oracles/expected_outcomes.yaml").read_text())["scenario_a"]
IDS = [f"{c['case']}-{c['file']}" for c in CASES]


def cards_with(edits):
    cards = copy.deepcopy(CARDS)
    for key, value in (edits or {}).items():
        gid, part_name, fld = key.split(".")
        next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)[fld] = value
    return cards


def run(case):
    cards = cards_with(case["card_edits"])
    installed_layout = {k: v for k, v in case["placement"].items() if k.split(".")[0] in case["installed"]}
    return Ad.admit(A, cards, case["installed"], case["card"], MISSIONS[case["file"]], installed_layout)


RESULTS = {cid: run(c) for c, cid in zip(CASES, IDS)}


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_verdict_and_binding_line(case):
    r = RESULTS[f"{case['case']}-{case['file']}"]
    assert r.verdict == case["verdict"]
    b = case["binding"]
    assert r.binding.cls == b["class"]
    assert r.binding.demand == pytest.approx(b["demand"], abs=1e-6)
    assert r.binding.capacity == pytest.approx(b["capacity"], abs=1e-6)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_placement(case):
    r = RESULTS[f"{case['case']}-{case['file']}"]
    assert r.placement == case["placement"]


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_yes_if_options_ranked_with_their_numbers(case):
    r = RESULTS[f"{case['case']}-{case['file']}"]
    assert [o.remove for o in r.options] == [o["remove"] for o in case["yes_if"]]
    for got, want in zip(r.options, case["yes_if"]):
        assert got.value_lost == pytest.approx(want["value_lost"], abs=1e-6)
        assert got.mission_critical == want.get("mission_critical", False)
        if "mass_after_t" in want:
            assert got.mass_after_t == pytest.approx(want["mass_after_t"], abs=1e-6)
        if "stability_after_t_eq" in want:
            assert got.stability_after_t_eq == pytest.approx(want["stability_after_t_eq"], abs=1e-6)
        if "placement" in want:
            assert {k: v for k, v in got.placement.items()} == want["placement"]
        if "also" in want:
            assert got.moves == want["also"]["move"]
        if "one_genset_down" in want:
            check_genset(got.genset, want["one_genset_down"])
        if "seawater_tip_c" in want:
            assert got.seawater_tip_c == pytest.approx(want["seawater_tip_c"], abs=1e-6)


def check_genset(got, want):
    assert got.holds == want["holds"]
    assert got.load_kw == pytest.approx(want["load_kw"], abs=1e-6)
    assert got.reserve_kw == want["reserve_kw"]
    fix = want.get("fix", [])
    assert [(s.guest, s.from_mode, s.to_mode) for s in got.fix[: len(fix)]] == [(s["guest"], s["from_mode"], s["to_mode"]) for s in fix]
    for s, w in zip(got.fix, fix):
        if "frees_kw" in w:
            assert s.frees_kw == pytest.approx(w["frees_kw"], abs=1e-6)
        if "value_lost" in w:
            assert s.value_lost == pytest.approx(w["value_lost"], abs=1e-6)
    if "steps_needed" in want:
        assert got.steps_needed == want["steps_needed"]


@pytest.mark.parametrize("case", [c for c in CASES if c["one_genset_down"]], ids=[i for c, i in zip(CASES, IDS) if c["one_genset_down"]])
def test_one_genset_down(case):
    check_genset(RESULTS[f"{case['case']}-{case['file']}"].genset, case["one_genset_down"])


@pytest.mark.parametrize("case", [c for c in CASES if c["seawater_tip_c"] is not None], ids=[i for c, i in zip(CASES, IDS) if c["seawater_tip_c"] is not None])
def test_seawater_tipping_point(case):
    assert RESULTS[f"{case['case']}-{case['file']}"].seawater_tip_c == pytest.approx(case["seawater_tip_c"], abs=1e-6)


def test_a_one_number_edit_flips_the_35_kg_case():
    a1 = RESULTS["A1-survey"]
    a6 = RESULTS["A6-survey"]
    assert (a1.verdict, a6.verdict) == ("yes-if", "yes")
    assert round((a1.binding.demand - a1.binding.capacity) * 1000) == 35
