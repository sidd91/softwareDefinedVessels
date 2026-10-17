"""The ledger reproduces every hand-computed line in the oracle and the Scenario B limits, loads and ladders."""
import copy

import pytest
import yaml

from sdv import ledger as Lg
from sdv import loader as Ld

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
O = yaml.safe_load((Ld.ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
CASES = O["scenario_a"]


def cards_with(edits):
    cards = copy.deepcopy(CARDS)
    for key, value in (edits or {}).items():
        gid, part_name, fld = key.split(".")
        next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)[fld] = value
    return cards


LINE_CASES = [(c, line) for c in CASES for line in [c["binding"]] + c["other_lines"] if line["class"] != "placement"]


@pytest.mark.parametrize("case,line", LINE_CASES, ids=[f"{c['case']}-{c['file']}-{l['class']}" for c, l in LINE_CASES])
def test_admission_lines_match_the_oracle(case, line):
    cards = cards_with(case["card_edits"])
    lines = Lg.admission_lines(A, cards, case["installed"] + [case["card"]], case["placement"])
    got = lines[line["class"]]
    assert got.demand == pytest.approx(line["demand"], abs=1e-6), line["class"]
    assert got.capacity == pytest.approx(line["capacity"], abs=1e-6), line["class"]


def test_brief_checks():
    five = ["G1", "G2", "G3", "G4", "G5"]
    assert Lg.admission_lines(A, CARDS, five)["power"].demand == pytest.approx(126.5)
    assert Lg.heat_capacity_kw(A, 30) == pytest.approx(120)
    assert Lg.heat_capacity_kw(A, 30, degraded=True) == pytest.approx(72)
    assert Lg.heat_capacity_kw(A, 24) == pytest.approx(133.33, abs=0.01)
    sets_of_four = [[g for g in five if g != out] for out in five]
    over = [s for s in sets_of_four if Lg.admission_lines(A, CARDS, s)["mass"].over]
    assert len(over) == 3


def minute(m, file_id):
    """Scenario B guest modes and conditions at minutes 12 and 19 (docs/EXPECTED_OUTCOMES.md, DEC-40)."""
    modes = {"G3": "standby", "G4": "standby" if m == 12 else "fast_charge", "G5": "full"}
    reserved = {"G4": 35} if (file_id == "sar" and m == 12) else {}
    return modes, dict(gensets_online=1, seawater_c=24, cooling_degraded=(m == 19), reservations=reserved)


@pytest.mark.parametrize("m,file_id,limit,load", [(12, "survey", 95, 48), (12, "sar", 95, 81), (19, "survey", 75, 81), (19, "sar", 75, 81)])
def test_scenario_b_limit_and_load(m, file_id, limit, load):
    modes, cond = minute(m, file_id)
    lines = Lg.operating_lines(A, CARDS, modes, **cond)
    assert Lg.limit_kw(A, lines["power"], lines["heat"]) == pytest.approx(limit)
    assert lines["power"].demand == pytest.approx(load)
    assert ("chilled-water pump" in lines["heat"].degraded_by) == (m == 19)


@pytest.mark.parametrize("file_id,guest,to_mode,price,after", [("survey", "G4", "charge", 0.0024, 56), ("sar", "G5", "low_power", 0.0189, 44)])
def test_minute_19_first_step_and_load_after(file_id, guest, to_mode, price, after):
    modes, cond = minute(19, file_id)
    lines = Lg.operating_lines(A, CARDS, modes, **cond)
    steps = Lg.ladder(CARDS, modes, MISSIONS[file_id])
    taken = Lg.steps_to_fit(steps, lines["power"].demand, Lg.limit_kw(A, lines["power"], lines["heat"]))
    assert [(s.guest, s.to_mode) for s in taken] == [(guest, to_mode)]
    assert taken[0].price == pytest.approx(price, abs=1e-4)
    assert lines["power"].demand - taken[0].frees_kw == pytest.approx(after)


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_minute_12_holds_and_arms_g5_first(file_id):
    modes, cond = minute(12, file_id)
    lines = Lg.operating_lines(A, CARDS, modes, **cond)
    steps = Lg.ladder(CARDS, modes, MISSIONS[file_id])
    assert Lg.steps_to_fit(steps, lines["power"].demand, Lg.limit_kw(A, lines["power"], lines["heat"])) == []
    assert (steps[0].guest, steps[0].to_mode) == ("G5", "low_power")


def test_a_non_interruptible_charge_is_skipped():
    steps = Lg.ladder(CARDS, {"G3": "charging", "G5": "full"}, MISSIONS["survey"])
    assert all(s.guest != "G3" or s.from_mode != "charging" for s in steps)


def test_throttles_come_before_sheds_and_mission_critical_goes_last():
    steps = Lg.ladder(CARDS, {"G3": "standby", "G4": "fast_charge", "G5": "full"}, MISSIONS["survey"])
    sheds = [i for i, s in enumerate(steps) if s.shed]
    assert sheds and all(not s.shed for s in steps[: sheds[0]])
    throttles = [s for s in steps if not s.shed]
    critical = [i for i, s in enumerate(throttles) if s.mission_critical]
    assert all(not s.mission_critical for s in throttles[: critical[0]]) if critical else True


def test_declared_shed_order_overrides_the_price():
    m = copy.deepcopy(MISSIONS["survey"])
    m["shed_order"] = {"coastal_connectivity": 1}
    first = Lg.ladder(CARDS, {"G4": "fast_charge", "G5": "full"}, m)[0]
    assert first.guest == "G5"
    m["shed_order"] = {"coastal_connectivity": -1}
    assert Lg.ladder(CARDS, {"G4": "fast_charge", "G5": "full"}, m)[0].guest == "G4"


GATE = [(["G3", "G4", "G5"], {"survey": ("G4", 80), "sar": ("G5", 68)}), (["G2", "G4", "G5"], {"survey": ("G4", 75), "sar": ("G2", 86)}),
        (["G1", "G2", "G4", "G5"], {"survey": ("G4", 76.5), "sar": ("G2", 87.5)})]


@pytest.mark.parametrize("guests,expected", GATE, ids=["-".join(g) for g, _ in GATE])
def test_dec35_gate_first_throttle_from_envelope_modes(guests, expected):
    modes = {g: Lg.envelope_mode(A, CARDS[g]) for g in guests}
    load = sum(Lg.envelope_kw(A, CARDS[g]) for g in guests)
    for file_id, (guest, after) in expected.items():
        first = next(s for s in Lg.ladder(CARDS, modes, MISSIONS[file_id]) if not s.shed)
        assert first.guest == guest and load - first.frees_kw == pytest.approx(after)
