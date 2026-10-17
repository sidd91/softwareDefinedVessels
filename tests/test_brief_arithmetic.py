"""Checks that our data files encode the challenge brief correctly.

No governor logic here: each test restates a number or sentence from the brief (or the
organizers' correction) and checks the manifests and assumptions agree with it.
"""
import glob
import itertools
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
CARDS = {
    yaml.safe_load(open(f))["id"]: yaml.safe_load(open(f))
    for f in sorted(glob.glob(str(ROOT / "manifests/G*.yaml")))
}
BRIEF_FIVE = ["G1", "G2", "G3", "G4", "G5"]


def envelope_kw(card):
    """Sustained worst-case draw: a peak counts if it lasts longer than the 60 s peak window."""
    p = card["consumes"]["power_kw"]
    peak_sustained = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
    return max(p["nominal"], peak_sustained)


def mass_t(card):
    return sum(part["mass_t"] for part in card["placement"]["parts"])


def heat_capacity_kw(seawater_c, degraded=False):
    pts = A["heat"]["capacity_kw_at"]
    (t0, c0), (t1, c1) = sorted(pts.items())
    cap = c0 + (c1 - c0) * (seawater_c - t0) / (t1 - t0)
    return cap * (A["heat"]["degraded_factor"] if degraded else 1.0)


def test_every_card_validates_against_the_schema():
    v = Draft202012Validator(json.loads((ROOT / "manifests/schema.json").read_text()))
    for gid, card in CARDS.items():
        assert not list(v.iter_errors(card)), gid


def test_six_cards_five_from_the_brief_plus_one_of_ours():
    assert sorted(CARDS) == ["G1", "G2", "G3", "G4", "G5", "G6"]
    assert "team invention" in CARDS["G6"]["source"]


def test_all_five_fit_the_cruise_reserve():
    # Brief: "at cruise all five fit the 200 kW reserve"
    total = sum(envelope_kw(CARDS[g]) for g in BRIEF_FIVE)
    assert total == pytest.approx(126.5)
    assert total <= A["power"]["guest_reserve_kw"]["cruise"]


def test_one_genset_down_g5_g4_g3_charging_exceed_the_reserve():
    # Brief: "with one genset down they do not (G5 + G4 + G3 charging = 105 kW against ~100)"
    total = sum(envelope_kw(CARDS[g]) for g in ["G5", "G4", "G3"])
    assert total == pytest.approx(105)
    assert total > A["power"]["guest_reserve_kw"]["one_genset_down"]


def test_all_five_do_not_fit_a_degraded_loop_in_30c_water():
    # Brief: "nor in 30 °C water with a degraded loop"
    chilled = sum(envelope_kw(CARDS[g]) for g in BRIEF_FIVE if CARDS[g]["cooling"] == "chilled_water")
    assert chilled > heat_capacity_kw(30, degraded=True)


def test_three_of_five_sets_of_four_exceed_the_mass_margin():
    # Organizers' correction: "Three of the five possible sets of four exceed the 10 t margin."
    over = [s for s in itertools.combinations(BRIEF_FIVE, 4) if sum(mass_t(CARDS[g]) for g in s) > A["mass"]["margin_t"]]
    assert len(over) == 3
    without_g5 = sum(mass_t(CARDS[g]) for g in ["G1", "G2", "G3", "G4"])
    assert without_g5 == pytest.approx(10.035)  # 35 kg over: the Scenario A edge case


def test_g4_hangar_is_850_kg_after_the_correction():
    hangar = next(p for p in CARDS["G4"]["placement"]["parts"] if p["name"] == "hangar")
    assert hangar["mass_t"] == pytest.approx(0.85)


def test_cooling_capacity_matches_annex_a():
    assert heat_capacity_kw(12) == pytest.approx(160)
    assert heat_capacity_kw(30) == pytest.approx(120)
    assert heat_capacity_kw(24) == pytest.approx(133.33, abs=0.01)  # Scenario B water
    assert heat_capacity_kw(30, degraded=True) == pytest.approx(72)


def test_power_budget_closes_against_the_brief():
    p = A["power"]
    one_set = p["gensets"]["rating_kw"] * p["gensets"]["load_limit"]
    cruise_guest_room = 2 * one_set - p["hotel_kw"]["committed"] - p["ship_aux_kw"]
    assert cruise_guest_room >= p["guest_reserve_kw"]["cruise"]  # 355 kW available, 200 offered
    degraded_room = one_set - (p["hotel_kw"]["committed"] - p["hotel_shed_on_trip_kw"]) - p["ship_aux_kw"]
    assert degraded_room == pytest.approx(p["guest_reserve_kw"]["one_genset_down"])


def test_every_capability_has_a_weight_in_every_priority_file():
    missions = [yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "config/missions/*.yaml")))]
    assert len(missions) >= 2  # brief: at least two priority sets
    caps = {card["capability"]["name"] for card in CARDS.values()}
    for m in missions:
        assert caps <= set(m["weights"]), m["id"]


def test_every_assumed_number_has_a_reason():
    for key, prov in A["provenance"].items():
        if prov["source"] == "assumed":
            assert prov.get("why"), key


def test_every_priority_file_validates_against_its_schema():
    v = Draft202012Validator(json.loads((ROOT / "config/missions/schema.json").read_text()))
    for f in sorted(glob.glob(str(ROOT / "config/missions/*.yaml"))):
        m = yaml.safe_load(open(f))
        assert not list(v.iter_errors(m)), f
        assert set(m["mission_critical"]) <= set(CARDS), f
