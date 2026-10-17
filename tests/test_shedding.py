"""D4 (src/sdv/shedding.py) against tests/oracles/expected_outcomes.yaml: Scenario B minute 12 and 19,
the price lists, the one-genset-down fixes of Scenario A, and the rules the ladder must never break."""
import copy
from pathlib import Path

import pytest
import yaml

from sdv import shedding
from sdv.data import load_assumptions, load_cards, load_missions
from sdv.ledger import cooling_capacity_kw, power_reserve_kw

ROOT = Path(__file__).resolve().parents[1]
A = load_assumptions()
CARDS = load_cards()
MISSIONS = load_missions()
O = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
B = O["scenario_b"]
TL = yaml.safe_load((ROOT / "config/scenarios/scenario_b.yaml").read_text())


def ceilings(gensets=1, factor_degraded=False, seawater_c=24):
    return shedding.ceilings(A, power_reserve_kw(A, "slow", gensets), cooling_capacity_kw(A, seawater_c, factor_degraded))


def test_ceiling_at_minute_12_is_95_kw():
    pc, hc = ceilings()
    assert pc == B["ceiling"]["kw"] == 95 and hc == pytest.approx(B["ceiling"]["cooling_kw"] - 5, abs=0.05)


@pytest.mark.parametrize("mission", ["survey", "sar"])
def test_minute_12_holds_with_an_armed_ladder(mission):
    modes = {g: m for g, m in B["draw_set_modes"]["L"].items() if g in TL["guests"]}
    d = shedding.decide(A, CARDS, modes, MISSIONS[mission], power_reserve_kw(A, "slow", 1), cooling_capacity_kw(A, 24, False))
    lad = d.extras["ladder"]
    assert d.verdict == "holds" and lad["steps"] == [] and lad["load_before_kw"] == 81
    first = lad["armed"][0]
    expected = {"survey": ("G4", "charge"), "sar": ("G5", "low_power")}[mission]
    assert (first["guest"], first["to_mode"]) == expected
    assert d.binding.cls == "power" and d.binding.capacity == 95 and d.binding.demand == 81
    assert d.sentence.startswith("Holds: 81 of 95 kW")


@pytest.mark.parametrize("mission,guest,to,after", [("survey", "G4", "charge", 56), ("sar", "G5", "low_power", 44)])
def test_minute_19_pump_fault_cooling_binds_and_one_throttle_closes_it(mission, guest, to, after):
    fault = next(e for e in TL["events"] if e["type"] == "cooling_degraded")
    d = shedding.decide(A, CARDS, fault["load_modes"], MISSIONS[mission], power_reserve_kw(A, "slow", 1), cooling_capacity_kw(A, 24, True))
    lad = d.extras["ladder"]
    assert d.binding.cls == "heat" and d.binding.capacity == 75 and d.binding.demand == 81
    assert [(s["guest"], s["from_mode"], s["to_mode"]) for s in lad["steps"]] == [(guest, fault["load_modes"][guest], to)]
    assert lad["load_after_kw"] == after and lad["holds"] and d.verdict == "throttled"
    assert "Chilled-water loop binds: 81 of 75 kW, 6 kW short." in d.sentence
    assert f"{guest} to {to}" in d.sentence and d.cost_to_loser.startswith(f"{guest} loses")


@pytest.mark.parametrize("loadout", B["loadouts"], ids=lambda l: l["id"])
@pytest.mark.parametrize("mission", ["survey", "sar"])
def test_minute_12_set_b_ladders_match_the_oracle(loadout, mission):
    modes = {g: m for g, m in B["draw_set_modes"]["B"].items() if g in loadout["guests"]}
    exp = loadout["minute_12"]["B"]
    pc, hc = ceilings()
    lad = shedding.walk(CARDS, modes, MISSIONS[mission], pc, hc)
    assert lad.load_before_kw == exp["load_kw"] and lad.short_kw == exp["short_kw"]
    assert [(s.guest, s.from_mode, s.to_mode, s.frees_kw) for s in lad.steps] == [
        (s["guest"], s["from_mode"], s["to_mode"], s["frees_kw"]) for s in exp["ladder"][mission]]
    if exp["ladder"][mission]:
        assert lad.load_after_kw == exp["ladder"][mission][-1]["load_after_kw"]
    assert lad.holds


@pytest.mark.parametrize("mission", ["survey", "sar"])
def test_price_lists_at_minute_12_match_the_oracle(mission):
    exp = B["price_lists"][mission]
    steps = shedding.price_list(CARDS, B["draw_set_modes"]["B"], MISSIONS[mission])
    got = [(s.guest, s.from_mode, s.to_mode) for s in steps]
    want = [(s["guest"], s["from_mode"], s["to_mode"]) for s in exp["throttles"] + exp["sheds"]]
    assert got == want
    for s, e in zip(steps, exp["throttles"] + exp["sheds"]):
        assert s.cost_per_kw == pytest.approx(e["cost_per_kw"], abs=5e-4)
        assert s.critical == e.get("mission_critical", False)
    assert all(not s.is_shed for s in steps[: len(exp["throttles"])]) and all(s.is_shed for s in steps[len(exp["throttles"]):])
    assert not any(s.from_mode == "charging" for s in steps)  # G3 charging is not interruptible


def envelope_modes(guests):
    out = {}
    for g in guests:
        p = CARDS[g]["consumes"]["power_kw"]
        peak = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
        draw = max(p["nominal"], peak)
        out[g] = next(m["name"] for m in CARDS[g]["modes"] if m["power_kw"] == draw)
    return out


def ogd_cases():
    for c in O["scenario_a"]:
        if c.get("one_genset_down") and c["one_genset_down"].get("fix"):
            yield pytest.param(c, c["installed"] + [c["card"]], c["one_genset_down"], id=f"{c['case']}-{c['file']}")
        for i, o in enumerate(c.get("yes_if", [])):
            if o.get("one_genset_down", {}).get("fix"):
                kept = [g for g in c["installed"] + [c["card"]] if g not in o["remove"]]
                yield pytest.param(c, kept, o["one_genset_down"], id=f"{c['case']}-{c['file']}-opt{i + 1}")


@pytest.mark.parametrize("case,guests,ogd", list(ogd_cases()))
def test_one_genset_down_fix_is_the_throttle_only_prefix(case, guests, ogd):
    """DEC-35: at the envelope (30 C, one genset down) the ladder's throttle-only prefix, interruptible
    modes that keep capability above 0, must bring the load to the 95 kW gate."""
    pc, hc = shedding.ceilings(A, A["power"]["guest_reserve_kw"]["one_genset_down"], cooling_capacity_kw(A, 30, False))
    lad = shedding.walk(CARDS, envelope_modes(guests), MISSIONS[case["file"]], pc, hc, throttle_only=True, keep_capability=True)
    assert lad.load_before_kw == ogd["load_kw"]
    first = ogd["fix"][0]
    assert (lad.steps[0].guest, lad.steps[0].from_mode, lad.steps[0].to_mode) == (first["guest"], first["from_mode"], first["to_mode"])
    assert lad.steps[0].frees_kw == first["frees_kw"]
    if "load_after_kw" in first:
        assert lad.load_before_kw - lad.steps[0].frees_kw == first["load_after_kw"]
    assert lad.holds and len(lad.steps) == ogd.get("steps_needed", len(lad.steps))
    # The rest of the oracle's list is the armed order after the first step.
    rest = [(s["guest"], s["to_mode"]) for s in ogd["fix"][1:]]
    assert [(s.guest, s.to_mode) for s in lad.armed[: len(rest)]] == rest


def test_safety_critical_guests_are_never_on_the_ladder_and_shed_order_wins():
    cards = copy.deepcopy(CARDS)
    cards["G5"]["criticality"]["safety_critical"] = True
    modes = {"G3": "standby", "G4": "fast_charge", "G5": "full"}
    lad = shedding.walk(cards, modes, MISSIONS["sar"], 40, 200)
    assert all(s.guest != "G5" for s in lad.steps) and not lad.holds  # 48 kW needed, G5's 45 untouchable
    declared = dict(MISSIONS["survey"], shed_order=["G5"])
    steps = shedding.price_list(CARDS, modes, declared)
    assert steps[0].guest == "G5" and steps[0].to_mode == "low_power"


def test_ladder_rechecks_heat_after_each_step():
    # Power is fine (ceiling 200) but the loop can only take 10 kW: G1 is air cooled and must not be touched.
    lad = shedding.walk(CARDS, {"G1": "full", "G5": "full"}, MISSIONS["survey"], 200, 10)
    assert lad.binding == "heat" and [s.guest for s in lad.steps] == ["G5"] and lad.steps[0].to_mode == "low_power"
    assert lad.holds and lad.load_after_kw == 9.5
