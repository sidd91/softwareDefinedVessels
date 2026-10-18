"""Every crew level runs Scenario B to the end through the loop the CLI builds (sdv run): the crew chip at 14, 6 or 0
never crashes the loop, the socket or the CLI, and what the ship cannot do at a level is said in a D5 record, never
silently (docs/SCENARIO_C_MEMO.md: 14 confirms, 6 needs a standing plan and 8-12 min to clear, 0 clears nothing)."""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent / "support"))
import sim_stub  # noqa: E402

from sdv import cli  # noqa: E402
from sdv import loader as Ld  # noqa: E402
from sdv import loop as L  # noqa: E402
from sdv.ui import data, live, view  # noqa: E402

A = Ld.load_assumptions()
RECORD = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))
NOT_NOW_6 = json.loads((Ld.ROOT / "tests/fixtures/records/cases/d5_r3_6_not_now.json").read_text())
PICKS = A["transition_picks"]["r3_worst_case"]
I = data.Inputs()


def laptop(t, typ, **payload):
    return {"t_s": t, "type": typ, "injected": False, "payload": payload}


def cli_loop(mission="survey", variant="default", extra=(), until=1200):
    """The loop as cmd_run builds it: the labelled simulator and the scripted inputs, plus the laptop inputs given."""
    inputs = L.scripted_inputs()
    for i in extra:
        inputs.setdefault(i["t_s"], []).append(i)
    run = L.Loop(L.load_simulator(mission=mission, variant=variant), mission, variant, inputs=inputs)
    outs = list(run.ticks(until=until))
    run.close()
    return run, outs


def d5(records):
    return [r for r in records if r["kind"] == "D5"]


def commands(outs, kind):
    return [(o.tick, c) for o in outs for c in o.commands if c["kind"] == kind]


# ------------------------------------------------------------------------------------------------ the loop the CLI runs

@pytest.mark.parametrize("crew", [14, 6, 0])
def test_every_crew_level_runs_to_the_end_and_every_record_validates(crew):
    run, outs = cli_loop(extra=[laptop(60, "crew_change", crew_aboard=crew)])
    assert outs[-1].tick == 1200
    recs = [r for o in outs for r in o.records]
    assert recs and all(not list(RECORD.iter_errors(r)) for r in recs)
    r3 = d5(recs)
    assert r3 and all(r["crew_aboard"] == crew for r in r3)
    assert all(";" not in r["sentence"] for r in recs)
    if crew == 14:
        assert [(r["tick"], r["verdict"]) for r in r3] == [(480, "confirm"), (540, "cleared")]
        assert outs[-1].snapshot["guests"]["G4"]["activity"]["value"] == "landed" and run.sim.log == []
    else:
        # nobody asked the bridge at this level, so the scripted answer at 540 lands on no open request: ignored, logged
        assert not commands(outs, "bridge_request") and not commands(outs, "clear_deck")
        assert any(m.startswith("540: bridge_answer to request 1 ignored") for m in run.sim.log)
        assert run.sim.refused == []


def test_six_aboard_without_a_plan_is_held_and_zero_without_a_sweep_is_forbidden():
    _, six = cli_loop(extra=[laptop(60, "crew_change", crew_aboard=6)])
    [held] = d5([r for o in six for r in o.records])
    assert (held["tick"], held["verdict"]) == (480, "held") and held["sentence"].startswith("Recovery held at 6 aboard: no standing plan approved.")
    _, zero = cli_loop(extra=[laptop(60, "crew_change", crew_aboard=0)])
    [forbidden] = d5([r for o in zero for r in o.records])
    assert (forbidden["tick"], forbidden["verdict"]) == (480, "forbidden")
    assert forbidden["sentence"] == "Recovery forbidden at 0 aboard: no crew sweep is known, the deck is not latched clear. G4 ditches by minute 18.2."


def test_six_aboard_with_a_standing_plan_names_the_lead_it_cannot_meet():
    """A.6: at 6 aboard the confirm and the clear take 15 min, 7 more than the 8 the hard limit leaves after the approach,
    so a recovery that needs the deck cleared first is not now (the fixture's numbers, docs/SCENARIO_C_MEMO.md)."""
    _, outs = cli_loop(extra=[laptop(60, "crew_change", crew_aboard=6), laptop(60, "standing_plan", state="approved")])
    [r] = d5([r for o in outs for r in o.records])
    assert (r["tick"], r["verdict"], r["crew_aboard"]) == (480, "not-now", 6)
    b, fix = r["binding"], NOT_NOW_6["binding"]
    lead = PICKS["confirm_min"][6] + PICKS["clear_deck_min"][6]
    window = next(l["then"]["within_min"] for l in I.cards["G4"]["hard_limits"] if l["then"]["action"] == "land_or_ditch") - A["rules"]["r3"]["approach_min"]
    assert (b["class"], b["label"], b["unit"]) == (fix["class"], fix["label"], fix["unit"])
    assert (b["demand"], b["capacity"], b["free"]) == (lead, window, window - lead) == (fix["demand"], fix["capacity"], fix["free"])
    assert r["sentence"] == ("Not now at 6 aboard: G4 recovery under rule R3 waits until the landing officer reports the zone clear. "
                             + NOT_NOW_6["sentence"].split(". ", 1)[1])
    assert "6 aboard cannot clear it in time" in r["deck_evidence"]
    assert not commands(outs, "clear_deck") and not commands(outs, "ship_state")   # nothing is sent for a refused recovery


def test_at_six_aboard_a_fresh_landing_officer_clear_report_lets_the_deck_work_go_at_the_slower_pace():
    extra = [laptop(60, "crew_change", crew_aboard=6), laptop(60, "standing_plan", state="approved"),
             laptop(400, "deck_report", deck="clear", wind_kn=20)]
    _, outs = cli_loop(extra=extra)
    [r] = d5([r for o in outs for r in o.records])
    assert (r["tick"], r["verdict"]) == (480, "standing_plan")
    assert [t for t, _ in commands(outs, "clear_deck")] == [480]
    tr = outs[481].frame["signals"]["deck_flight_deck"]["transition"]
    lo, hi = A["ship_state"]["deck"]["clear_min"][6]
    assert (tr["to"], tr["expected_end_t_s"], tr["latest_end_t_s"]) == ("clear", 481 + 60 * (lo + hi) / 2, 481 + 60 * hi)


def test_the_crew0_variant_runs_through_the_cli(capsys):
    assert cli.main(["run", "--variant", "crew0"]) == 0
    out = capsys.readouterr().out
    assert "D5 AUTOMATIC " in out and "Recovery automatic at 0 aboard" in out and "Traceback" not in out


# ------------------------------------------------------------------------------------------------ the crew chip on the screen

def test_the_crew_chip_to_six_after_the_bridge_was_asked_is_a_not_now_not_a_crash():
    lr = live.LiveReplay("survey", 500, running=False)
    lr.command({"cmd": "input", "input": {"type": "crew_change", "payload": {"crew_aboard": 6}}})
    lr.run.advance_to(1200)
    recs = d5(lr.run.records)
    assert [(r["tick"], r["verdict"]) for r in recs] == [(480, "confirm"), (540, "not-now")]
    assert recs[1]["binding"]["class"] == "r3_lead" and recs[1]["deck_evidence"].startswith("the bridge confirmed at minute 9, the flight deck is occupied")
    assert not list(RECORD.iter_errors(recs[1]))
    v = view.screen(I, lr.run.moment())
    assert (v["header"]["crew"], v["decision"]["r3"]["verdict"]) == ("CREW 6", "NOT-NOW")
    assert any(e["type"] == "CREW POLICY" and "Deck clearing lead" in e["msg"] for e in v["log"])


def test_the_crew_chip_to_zero_after_the_bridge_was_asked_holds_the_recovery():
    lr = live.LiveReplay("survey", 500, running=False)
    lr.command({"cmd": "input", "input": {"type": "crew_change", "payload": {"crew_aboard": 0}}})
    lr.run.advance_to(1200)
    assert [(r["tick"], r["verdict"]) for r in d5(lr.run.records)] == [(480, "confirm"), (501, "held")]
    assert lr.run.loop.sim.refused == [] and lr.run.snapshot["guests"]["G4"]["activity"]["value"] == "airborne"


def test_zero_aboard_with_a_latched_but_occupied_deck_is_forbidden_and_the_ship_is_never_asked_to_clear():
    lr = live.LiveReplay("survey", 100, running=False)
    lr.command({"cmd": "input", "input": {"type": "crew_change", "payload": {"crew_aboard": 0}}})
    lr.command({"cmd": "input", "input": {"type": "deck_sweep", "payload": {"result": "clear"}}})
    lr.run.advance_to(1200)
    [r] = d5(lr.run.records)
    assert (r["tick"], r["verdict"]) == (480, "forbidden")
    assert r["sentence"] == ("Recovery forbidden at 0 aboard: platform deck state latched at the last crew sweep, the flight deck is "
                             "occupied and nobody aboard can clear it. G4 ditches by minute 18.2.")
    assert lr.run.loop.sim.refused == [] and lr.run.loop.core.safety_table["r3_hold_landing"]["state"] != "ready"


# ------------------------------------------------------------------------------------------------ the test double

def test_the_stub_clears_at_the_a6_pace_for_six_aboard_and_refuses_for_nobody():
    clear = [{"seq": 1, "kind": "clear_deck", "args": {"zone": "flight_deck"}}]
    sim = sim_stub.Simulator("scenario_b", "survey", 0, "default")
    sim.step(0, [], [])
    sim.step(1, [], [laptop(1, "crew_change", crew_aboard=6)])
    tr = sim.step(2, clear, [])["signals"]["deck_flight_deck"]["transition"]
    lo, hi = A["ship_state"]["deck"]["clear_min"][6]
    assert (tr["expected_end_t_s"], tr["latest_end_t_s"]) == (2 + 60 * (lo + hi) / 2, 2 + 60 * hi)
    sim = sim_stub.Simulator("scenario_b", "survey", 0, "default")
    sim.step(0, [], [])
    sim.step(1, [], [laptop(1, "crew_change", crew_aboard=0)])
    fr = sim.step(2, clear, [])
    assert fr["signals"]["deck_flight_deck"] == {"value": "occupied", "source": "plant", "t_s": 2}
    assert sim.refused == [{"t_s": 2, "kind": "clear_deck", "args": {"zone": "flight_deck"}, "why": "0 aboard cannot clear a deck (ship_state.deck.clear_min)"}]
    assert sim.log == ["2: clear_deck flight_deck refused, 0 aboard cannot clear a deck (ship_state.deck.clear_min)"]
    assert sim.step(3, [], [])["signals"]["deck_flight_deck"]["value"] == "occupied"


def test_a_bridge_answer_with_no_open_request_is_ignored_not_raised():
    sim = sim_stub.Simulator("scenario_b", "survey", 0, "default")
    sim.step(0, [], [])
    fr = sim.step(1, [], [laptop(1, "bridge_answer", request_seq=7, answer="confirmed")])
    assert fr["events"] == [] and fr["signals"]["bridge_requests"]["value"] == []
    assert sim.log == ["1: bridge_answer to request 7 ignored, no such request is open"]
