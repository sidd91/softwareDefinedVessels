"""The estimator against the contract: stepping the simulator test double (tests/support/sim_stub.py) through
Scenario B with the scripted core reproduces every snapshot fixture, every snapshot validates, a replay of the
frames gives the same bytes, and the decisions read the estimator's snapshots exactly as they read the fixtures."""
import copy
import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent / "support"))
import sim_stub  # noqa: E402

from sdv import arbitration as D3  # noqa: E402
from sdv import explain as E  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import records as R  # noqa: E402
from sdv import shedding as D4  # noqa: E402
from sdv.estimator import Estimator, r1  # noqa: E402

ROOT = Ld.ROOT
SNAP = {p.stem: json.loads(p.read_text()) for p in (ROOT / "tests/fixtures/snapshots").glob("*.json")}
SCHEMA = jsonschema.Draft202012Validator(json.loads((ROOT / "config/snapshot.schema.json").read_text()))
sys.path.insert(0, str(ROOT / "tools"))
from build_snapshot_fixtures import canonical  # noqa: E402


def drop(tick, feed, until=None):
    return {tick: [{"t_s": tick, "type": "feed_drop", "injected": True, "payload": {"feed": feed, "until_t_s": until}}]}


RUNS = {
    "survey": dict(mission="survey"),
    "sar": dict(mission="sar"),
    "g4drop": dict(mission="survey", extra_inputs=drop(546, "g4_telemetry"), horizon=600),
    "pmsdrop": dict(mission="survey", extra_inputs=drop(597, "pms"), horizon=600),
    "crew0": dict(mission="survey", variant="crew0", horizon=480),
}
PAIRS = [("scenario_b_survey_m00", "survey", 0), ("scenario_b_survey_m08", "survey", 480),
         ("scenario_b_survey_m08_crew0", "crew0", 480), ("scenario_b_survey_m09_stale_g4_telemetry", "g4drop", 560),
         ("scenario_b_survey_m10_stale_genset_feed", "pmsdrop", 600), ("scenario_b_survey_m12", "survey", 721),
         ("scenario_b_survey_m19", "survey", 1141), ("scenario_b_sar_m12", "sar", 721), ("scenario_b_sar_m19", "sar", 1141)]


def run(mission="survey", variant="default", **kw):
    est = Estimator("scenario_b", mission, variant)
    frames, snaps = [], []
    for fr in sim_stub.frames(mission=mission, variant=variant, **kw):
        frames.append(fr)
        snaps.append(est.step(fr))
    return frames, snaps, est


OUT = {name: run(**kw) for name, kw in RUNS.items()}


def flat(s):
    out = {}
    for g in ("plant", "ship_state", "environment", "links", "crew", "capacity"):
        out.update(s[g])
    for g, d in s["guests"].items():
        out.update({f"{g}.{k}": v for k, v in d.items()})
    return out


def comparable(f):
    f = {k: v for k, v in f.items() if k != "since_t_s"}
    if "substituted" in f:
        f["substituted"] = {k: v for k, v in f["substituted"].items() if k != "rule"}
    return f


@pytest.mark.parametrize("fixture,run_name,tick", PAIRS)
def test_the_estimator_reproduces_the_fixture(fixture, run_name, tick):
    """Every field's value, source, age, confidence, staleness, transition, by and substitution (the rule wording
    is signals.yaml's, the fixtures paraphrase it), and the feeds, faults, events and run block."""
    want, got = SNAP[fixture], OUT[run_name][1][tick]
    fw, fg = flat(want), flat(got)
    assert sorted(fw) == sorted(fg)
    diffs = [k for k in fw if comparable(fw[k]) != comparable(fg[k])]
    assert not diffs, {k: (comparable(fw[k]), comparable(fg[k])) for k in diffs}
    for part in ("run", "feeds", "faults", "events"):
        assert want[part] == got[part], part


# The fixtures annotate since_t_s by hand at the ticks they show; the estimator records every change it sees.
# Where they differ the estimator is right about the frames: the fixtures mark G3's start-of-run state since 0,
# skip the series (wind, G4's range), skip the recovery window 781-1019 (G4 pins the heading and runs the hangar
# doors), and skip the fallback changes of the two drops.
SINCE_GAPS = {
    "G3.activity": {0: None, 480: None}, "G3.leg_state": {0: None, 480: None}, "acoustic_link_up": {0: None, 480: None},
    "G3.leg_flown_s": 480, "G3.data_demand": 510, "wind_kn": 475, "bridge_requests": 540,
    "los_radio": 556, "gensets_online": 600, "power": 600, "shed_ceiling_kw": 600,
    "G4.data_demand": 1020, "deck_machinery": 1020, "deck_machinery_permitted": 1020, "heading_free": 1020,
}


@pytest.mark.parametrize("fixture,run_name,tick", PAIRS)
def test_since_is_the_tick_of_the_last_change(fixture, run_name, tick):
    fw, fg = flat(SNAP[fixture]), flat(OUT[run_name][1][tick])
    for k in fw:
        a, b = fw[k].get("since_t_s"), fg[k].get("since_t_s")
        if b is not None:
            assert b <= tick
        if a == b:
            continue
        gap = SINCE_GAPS.get(k)
        if isinstance(gap, dict):
            assert tick in gap and b == gap[tick], (k, a, b)
        elif k == "G4.range_km":
            assert b in (tick - 1, tick - 2, tick - 3, tick, 1018) or a is None, (k, a, b)
        else:
            assert gap is not None and b == gap, (k, a, b)


def test_every_snapshot_validates():
    for name, (_, snaps, _) in OUT.items():
        for s in snaps[::7] + snaps[-3:]:
            errors = list(SCHEMA.iter_errors(s))
            assert not errors, (name, s["run"]["tick"], [f"{list(e.absolute_path)}: {e.message[:120]}" for e in errors[:3]])


def test_replay_of_the_frames_gives_the_same_bytes():
    frames, snaps, _ = OUT["survey"]
    est = Estimator("scenario_b", "survey")
    again = [est.step(json.loads(canonical(fr))) for fr in frames]
    assert [canonical(s) for s in again] == [canonical(s) for s in snaps]


def test_the_estimator_never_skips_a_tick():
    est = Estimator()
    frames = OUT["survey"][0]
    est.step(frames[0])
    with pytest.raises(AssertionError):
        est.step(frames[2])


A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SIGNALS = yaml.safe_load((ROOT / "config/signals.yaml").read_text())


def test_d3_reads_the_estimator_as_it_reads_the_fixture():
    for f in ("survey", "sar"):
        on_fixture = D3.right_of_way(A, SIGNALS, CARDS, MISSIONS[f], SNAP["scenario_b_survey_m08"])
        on_estimate = D3.right_of_way(A, SIGNALS, CARDS, MISSIONS[f], OUT["survey"][1][480])
        assert on_estimate == on_fixture


@pytest.mark.parametrize("mission,tick,reservations", [("survey", 721, None), ("sar", 721, {"G4": 35}),
                                                        ("survey", 1141, None), ("sar", 1141, None)])
def test_d4_reads_the_estimator_as_it_reads_the_fixture(mission, tick, reservations):
    fixture = SNAP[f"scenario_b_{mission}_m{tick // 60:02d}"]
    snap = OUT[mission][1][tick]
    a = R.from_d4(D4.shed(CARDS, MISSIONS[mission], fixture, reservations), seq=2, snapshot=fixture)
    b = R.from_d4(D4.shed(CARDS, MISSIONS[mission], snap, reservations), seq=2, snapshot=snap)
    assert {k: v for k, v in a.items() if k != "inputs_hash"} == {k: v for k, v in b.items() if k != "inputs_hash"}
    assert b["sentence"] == E.sentence(b)


def test_the_trip_confirms_one_tick_after_the_relay_and_the_kw_drop():
    snaps = OUT["survey"][1]
    assert snaps[719]["faults"] == []
    pending = snaps[720]["faults"][0]
    assert pending["state"] == "pending" and pending["raw_event_t_s"] == 720 and pending["confirmed_t_s"] is None
    assert snaps[720]["plant"]["gensets_online"]["value"] == 2
    assert snaps[721]["faults"][0]["state"] == "confirmed"
    assert snaps[721]["plant"]["gensets_online"] == {**snaps[721]["plant"]["gensets_online"], "value": 1, "confidence": "confirmed"}


def test_the_healthy_pump_holds_no_fault():
    """The shared votes (flow, delta-T) count for a pump only while it has a vote of its own."""
    s = OUT["survey"][1][1200]
    assert [f["subject"] for f in s["faults"]] == ["genset_2", "chw_pump_1"]


def test_a_stale_genset_feed_sheds_nothing():
    s = OUT["pmsdrop"][1][600]
    assert s["faults"] == [] and s["plant"]["gensets_online"]["stale"]
    d = D4.shed(CARDS, MISSIONS["survey"], s)
    assert d["verdict"] == "hold" and d["steps"] == []


def test_a_fallback_lifts_on_the_first_fresh_frame():
    frames, snaps, _ = run(mission="survey", extra_inputs=drop(546, "g4_telemetry", until=600), horizon=605)
    assert snaps[599]["feeds"]["g4_telemetry"]["stale"] and snaps[599]["guests"]["G4"]["activity"]["stale"]
    first_fresh = next(t for t in range(560, 606) if "activity" in frames[t]["guests"]["G4"])
    s = snaps[first_fresh]
    assert not s["feeds"]["g4_telemetry"]["stale"] and not s["guests"]["G4"]["activity"]["stale"]
    assert "substituted" not in s["guests"]["G4"]["activity"]
    assert s["capacity"]["los_radio"]["value"]["capacity"] == 20.0


def test_land_by_never_moves_later_and_clears_on_landing():
    snaps = OUT["survey"][1]
    land = [s["guests"]["G4"]["land_by_t_s"]["value"] for s in snaps]
    assert land[0] == -3952 + 90 * 60 and land[480] == 1091.9
    flying = [x for x in land[:1020] if x is not None]
    assert all(b <= a for a, b in zip(flying, flying[1:]))
    assert land[1020] is None


def test_unknown_and_out_of_range_readings_are_refused():
    frames = copy.deepcopy(OUT["survey"][0][:2])
    frames[1]["signals"]["not_a_signal"] = {"value": 1, "source": "plant", "t_s": 1}
    frames[1]["signals"]["genset_1_kw"] = {"value": 9999, "source": "plant", "t_s": 1}
    est = Estimator()
    est.step(frames[0])
    s = est.step(frames[1])
    assert any("not_a_signal" in m for m in est.log) and any("genset_1_kw" in m for m in est.log)
    assert s["plant"]["genset_1_kw"]["value"] == 251.5 and s["plant"]["genset_1_kw"]["age_s"] == 1


def test_recovery_window_effects_carry_their_holders():
    s = OUT["survey"][1][900]
    assert s["guests"]["G4"]["activity"]["value"] == "launch_recovery"
    assert s["ship_state"]["flight_deck_ops"]["value"] == "in_use" and s["ship_state"]["flight_deck_ops"]["by"] == ["G4"]
    assert s["ship_state"]["heading_free"]["value"] is False and s["ship_state"]["heading_free"]["by"] == ["G4"]
    assert s["ship_state"]["deck_machinery"]["value"] is True and s["ship_state"]["deck_machinery"]["by"] == ["G4"]
    assert s["links"]["acoustic_link_up"]["value"] is False


def test_crew0_full_run_and_sar_run_to_the_end():
    for mission in ("survey", "sar"):
        orig = sim_stub.SCRIPT["inputs"]
        sim_stub.SCRIPT["inputs"] = {}
        try:
            _, snaps, est = run(mission=mission, variant="crew0", cmd_hook=sim_stub.crew0_hook)
        finally:
            sim_stub.SCRIPT["inputs"] = orig
        assert snaps[480]["crew"]["deck_latched_clear"]["value"] is True
        assert not list(SCHEMA.iter_errors(snaps[-1]))
