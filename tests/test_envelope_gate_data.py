"""Checks the DEC-35 envelope gate results in docs/EXPECTED_OUTCOMES.md against the cards.

For each set: the as-loaded one-genset-down load (stacked envelope draws), the 95 kW gate from
assumptions, which throttle step the priority file picks first, and the load after it.
No engine needed; this guards the expected results until the ledger exists."""
import glob
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
CARDS = {c["id"]: c for c in (yaml.safe_load(open(f)) for f in glob.glob(str(ROOT / "manifests/G*.yaml")))}
MISSIONS = {m["id"]: m for m in (yaml.safe_load(open(f)) for f in glob.glob(str(ROOT / "config/missions/*.yaml")))}


def envelope_mode(card):
    """The mode whose power equals the card's envelope draw (max of nominal and any peak over 60 s)."""
    p = card["consumes"]["power_kw"]
    peak = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
    draw = max(p["nominal"], peak)
    return next(m for m in card["modes"] if abs(m["power_kw"] - draw) < 1e-9), draw


def gate_kw():
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    cooling_30 = c0 + (c1 - c0) * (A["envelope"]["judge_cooling_at_c"] - t0) / (t1 - t0)
    return min(A["power"]["guest_reserve_kw"]["one_genset_down"], cooling_30) - A["power"]["shed_headroom_kw"]


def first_throttle(guests, mission):
    """Cheapest eligible throttle: interruptible current mode, next lower mode keeps capability above 0;
    non-critical before mission-critical; cost = weight x capability lost / kW freed."""
    m = MISSIONS[mission]
    options = []
    for g in guests:
        card = CARDS[g]
        mode, _ = envelope_mode(card)
        if mode.get("interruptible") is False:
            continue
        lower = [x for x in card["modes"] if x["power_kw"] < mode["power_kw"] and x["capability_retained"] > 0]
        if not lower:
            continue
        to = max(lower, key=lambda x: x["power_kw"])
        freed = mode["power_kw"] - to["power_kw"]
        cost = m["weights"][card["capability"]["name"]] * (mode["capability_retained"] - to["capability_retained"]) / freed
        options.append((g in m["mission_critical"], cost, g, freed))
    return min(options)[2:] if options else None


CASES = [  # set, as-loaded kW, {mission: (first guest, load after)} or None when nothing is needed
    (["G1", "G2", "G3", "G4"], 81.5, None),
    (["G3", "G4", "G5"], 105, {"survey": ("G4", 80), "sar": ("G5", 68)}),
    (["G1", "G3", "G4", "G5"], 106.5, {"survey": ("G4", 81.5), "sar": ("G5", 69.5)}),   # Scenario B (DEC-63)
    (["G2", "G4", "G5"], 100, {"survey": ("G4", 75), "sar": ("G2", 86)}),
    (["G1", "G2", "G3"], 46.5, None),
    (["G1", "G3", "G5"], 71.5, None),
    (["G1", "G2", "G4", "G5"], 101.5, {"survey": ("G4", 76.5), "sar": ("G2", 87.5)}),
]


def test_gate_is_95_kw():
    assert gate_kw() == pytest.approx(95)


@pytest.mark.parametrize("guests,loaded,expected", CASES)
def test_as_loaded_draw_and_gate_outcome(guests, loaded, expected):
    load = sum(envelope_mode(CARDS[g])[1] for g in guests)
    assert load == pytest.approx(loaded)
    if expected is None:
        assert load <= gate_kw()
        return
    assert load > gate_kw()
    for mission, (guest, after) in expected.items():
        first = first_throttle(guests, mission)
        assert first is not None and first[0] == guest, (mission, first)
        assert load - first[1] == pytest.approx(after)
        assert load - first[1] <= gate_kw()
