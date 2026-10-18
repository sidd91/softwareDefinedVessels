"""Any numeric edit the jury can make to any card gives a verdict or a refusal naming the field, never a traceback
(brief: a jury-chosen card with one number changed; R-152, R-153, R-208): the +20 % sweep over every number under
consumes.* and every part mass, the envelope-mode and ladder rules behind a power edit, the placement and
one-genset-gate lines that replace a crash, and the CLI and API refusal paths."""
import copy
import json
import urllib.error

import jsonschema
import pytest

from sdv import admission as Ad
from sdv import cli
from sdv import ledger as Lg
from sdv import loader as Ld
from sdv import records as Rec
from sdv.cli import EditError, apply_edit
from sdv.ui import data, server, view
from test_ui_server import get, serve

A = Ld.load_assumptions()
VOCAB = Ld.load_vocabulary(assumptions=A)
CARDS = Ld.load_cards(vocab=VOCAB)
MISSIONS = Ld.load_missions(CARDS, VOCAB)
SCHEMA = Ld._schema(Ld.ROOT, "manifests/schema.json")
RECORD = jsonschema.Draft202012Validator(json.loads((Ld.ROOT / "config/decision_record.schema.json").read_text()))
SHIP = ["G1", "G2", "G3"]


def numeric_leaves(card: dict) -> list[str]:
    """Every number the jury can change on a card: consumes.*.{min, nominal, peak, peak_duration_s} and each part's mass."""
    out = []
    for cls, q in card["consumes"].items():
        out += [f"consumes.{cls}.{k}" for k, v in q.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return out + [f"placement.parts.{p['name']}.mass_t" for p in card["placement"]["parts"]]


def value_at(card: dict, field: str):
    node = card
    for k in field.split("."):
        node = next(x for x in node if x["name"] == k) if isinstance(node, list) else node[k]
    return node


def record(r, gid, installed, mission, cards):
    return Rec.from_admission(r, seq=0, tick=0, card_id=gid, installed=installed, mission=MISSIONS[mission], cards=cards)


SWEEP = [(gid, f, m) for gid, c in sorted(CARDS.items()) for f in numeric_leaves(c) for m in ("survey", "sar")]


# ------------------------------------------------------------------------------------------------ the sweep

@pytest.mark.parametrize("gid,field,mission", SWEEP, ids=[f"{g}-{f}-{m}" for g, f, m in SWEEP])
def test_plus_20_percent_on_any_number_gives_a_verdict(gid, field, mission):
    old = value_at(CARDS[gid], field)
    cards = dict(CARDS, **{gid: apply_edit(CARDS[gid], field, repr(round(old * 1.2, 6)))})
    assert value_at(cards[gid], field) == pytest.approx(old * 1.2) and not Ld.check_card(cards[gid], VOCAB, SCHEMA)
    installed = [g for g in SHIP if g != gid]
    r = Ad.admit(A, cards, installed, gid, MISSIONS[mission])
    assert r.verdict in ("yes", "yes-if", "no")
    rec = record(r, gid, installed, mission, cards)
    assert rec["sentence"] and not list(RECORD.iter_errors(rec))


def test_the_sweep_covers_every_card_and_both_power_figures():
    assert {g for g, _, _ in SWEEP} == {"G1", "G2", "G3", "G4", "G5", "G6"}
    assert {"consumes.power_kw.nominal", "consumes.power_kw.peak", "placement.parts.hangar.mass_t"} <= {f for g, f, _ in SWEEP if g == "G4"}


# ------------------------------------------------------------------------------------------------ the two edits that crashed D1

def test_the_power_edits_that_raised_stop_iteration_now_decide_with_a_consistent_step():
    cards = dict(CARDS, G4=apply_edit(CARDS["G4"], "consumes.power_kw.peak", "50"))
    r = Ad.admit(A, cards, SHIP, "G4", MISSIONS["survey"])
    assert (r.verdict, r.binding.cls) == ("yes-if", "mass")
    g = r.genset
    assert (g.load_kw, g.state, g.steps_needed) == (96.5, "holds_by_throttling", 1)
    assert (g.fix[0].guest, g.fix[0].from_mode, g.fix[0].to_mode, g.fix[0].frees_kw) == ("G4", "fast_charge", "charge", 40)
    cards = dict(CARDS, G5=apply_edit(CARDS["G5"], "consumes.power_kw.nominal", "60"))
    r = Ad.admit(A, cards, ["G3", "G4"], "G5", MISSIONS["sar"])
    assert (r.verdict, r.genset.load_kw, r.genset.state) == ("yes", 120, "holds_by_throttling")
    assert Lg.mode_of(cards["G5"], "full")["power_kw"] == 60


def test_envelope_mode_off_the_ladder_takes_the_lowest_covering_mode_else_the_top():
    g4 = copy.deepcopy(CARDS["G4"])
    g4["consumes"]["power_kw"]["peak"] = 12     # between charge (10) and fast charge (35)
    assert Lg.envelope_mode(A, g4) == "fast_charge"
    g4["consumes"]["power_kw"]["peak"] = 50     # above every rung
    assert Lg.envelope_mode(A, g4) == "fast_charge"
    g4["consumes"]["power_kw"]["peak"] = 1      # below nominal: the draw is the 10 kW nominal, an exact rung
    assert Lg.envelope_mode(A, g4) == "charge"
    assert [Lg.envelope_mode(A, CARDS[g]) for g in sorted(CARDS)] == ["full", "winch", "charging", "fast_charge", "full", "production"]


def test_a_step_is_priced_from_the_actual_draw():
    g4 = apply_edit(CARDS["G4"], "modes.0.power_kw", "35")  # the ladder as declared; the draw is passed in
    off_ladder = Lg.next_step({"G4": g4}, "G4", "fast_charge", MISSIONS["survey"], draw_kw=50)
    on_ladder = Lg.next_step({"G4": g4}, "G4", "fast_charge", MISSIONS["survey"])
    assert (off_ladder.to_mode, off_ladder.frees_kw, off_ladder.price) == ("charge", 40, pytest.approx(on_ladder.price * 25 / 40))
    assert on_ladder.frees_kw == 25


# ------------------------------------------------------------------------------------------------ apply_edit

@pytest.mark.parametrize("field,path", [
    ("hangar.mass_t", ("placement", "parts", 1, "mass_t")),
    ("placement.parts.hangar.mass_t", ("placement", "parts", 1, "mass_t")),
    ("placement.parts.1.mass_t", ("placement", "parts", 1, "mass_t")),
    ("modes.0.power_kw", ("modes", 0, "power_kw")),
    ("modes.standby.power_kw", ("modes", 2, "power_kw")),
    ("modes.standby.capability_retained", ("modes", 2, "capability_retained")),
    ("consumes.power_kw.peak_duration_s", ("consumes", "power_kw", "peak_duration_s")),
    ("consumes.data_los_radio_mbps.min", ("consumes", "data_los_radio_mbps", "min")),
    ("installation.port.hours", ("installation", "port", "hours")),
])
def test_apply_edit_addresses_parts_list_indices_and_mode_names(field, path):
    edited = apply_edit(CARDS["G4"], field, "0.5")
    node, base = edited, CARDS["G4"]
    for k in path:
        node, base = node[k], base[k]
    assert node == 0.5 and base != 0.5  # set on a copy, the loaded card untouched


def test_a_declared_power_figure_moves_the_rung_that_drew_it():
    peak = apply_edit(CARDS["G4"], "consumes.power_kw.peak", "40")
    assert (Lg.mode_of(peak, "fast_charge")["power_kw"], Lg.mode_of(peak, "charge")["power_kw"]) == (40, 10)
    assert (Lg.envelope_kw(A, peak), Lg.envelope_mode(A, peak)) == (40, "fast_charge")
    nominal = apply_edit(CARDS["G4"], "consumes.power_kw.nominal", "12")
    assert (Lg.mode_of(nominal, "charge")["power_kw"], Lg.mode_of(nominal, "fast_charge")["power_kw"]) == (12, 35)
    low = apply_edit(CARDS["G5"], "consumes.power_kw.min", "9")
    assert Lg.mode_of(low, "low_power")["power_kw"] == 9
    direct = apply_edit(CARDS["G4"], "modes.0.power_kw", "40")  # a mode edit leaves the declared figures alone
    assert direct["consumes"]["power_kw"]["peak"] == 35 and Lg.mode_of(direct, "fast_charge")["power_kw"] == 40
    assert CARDS["G4"]["consumes"]["power_kw"]["peak"] == 35 and Lg.mode_of(CARDS["G4"], "fast_charge")["power_kw"] == 35


@pytest.mark.parametrize("field,raw,reason", [
    ("nothing", "9", "no field nothing on the card"),
    ("consumes.power_kw.pek", "9", "no field consumes.power_kw.pek on the card"),
    ("modes.9.power_kw", "9", "no field modes.9.power_kw on the card"),
    ("modes.sleep.power_kw", "9", "no field modes.sleep.power_kw on the card"),
    ("hangar.weight", "9", "no field hangar.weight on the card"),
    ("consumes.power_kw.peak", "abc", "'abc' is not a number"),
    ("hangar.mass_t", "blank", "'blank' is not a number"),
    ("hangar.mass_t", "1e999", "'1e999' is not a finite number"),
    ("name", "5", "name is not a number on the card"),
    ("modes", "5", "modes is not a number on the card"),
    ("criticality.safety_critical", "1", "criticality.safety_critical is not a number on the card"),
])
def test_an_edit_that_cannot_apply_is_refused_with_the_field_and_the_reason(field, raw, reason):
    with pytest.raises(EditError) as e:
        apply_edit(CARDS["G4"], field, raw)
    assert (e.value.field, e.value.reason) == (field, reason)


# ------------------------------------------------------------------------------------------------ the lines that replace a crash

def test_a_part_no_position_takes_binds_as_a_placement_line():
    cards = dict(CARDS, G5=apply_edit(CARDS["G5"], "node.mass_t", "0.5"))
    r = Ad.admit(A, cards, ["G2", "G3"], "G5", MISSIONS["survey"])
    assert (r.verdict, r.unplaced, [l.cls for l in r.over]) == ("yes-if", ["G5.node"], ["placement"])
    b = r.binding
    assert (b.cls, b.unit, b.demand, b.capacity, b.over) == ("placement", "positions", 1, 0, True)
    assert (b.contributors, b.degraded_by) == ({"G5.node": ["bay2", "bay1_half"]}, ("G5.node: bay2, bay1_half tried",))
    rec = record(r, "G5", ["G2", "G3"], "survey", cards)
    assert not list(RECORD.iter_errors(rec))
    assert rec["sentence"] == "G5 node has no position: 1 position needed and 0 positions are free. Yes if G2 disembarks, mission value lost 1."
    assert rec["binding"] == {"class": "placement", "label": "Placement", "capacity": 0, "demand": 1, "free": -1, "unit": "positions",
                              "degraded_by": ["G5.node: bay2, bay1_half tried"]}


def test_a4_keeps_mass_binding_with_the_placement_line_behind_it():
    r = Ad.admit(A, CARDS, ["G1", "G2", "G5"], "G3", MISSIONS["survey"])
    assert r.binding.cls == "mass" and r.over[-1].cls == "placement"
    assert (r.over[-1].demand, sorted(r.over[-1].contributors)) == (1, ["G3.cradle", "G3.vehicle"])  # the vehicle rides on the cradle


def test_a_draw_no_throttle_brings_under_the_gate_binds_on_the_gate_line():
    cards = dict(CARDS, G3=apply_edit(CARDS["G3"], "consumes.power_kw.peak", "100"))
    r = Ad.admit(A, cards, ["G1"], "G3", MISSIONS["survey"])
    assert (r.verdict, r.over, r.genset.state) == ("no", [], "does_not_hold")
    assert (r.binding.cls, r.binding.demand, r.binding.capacity, r.binding.unit) == ("genset_gate", 101.5, 95, "kW")
    rec = record(r, "G3", ["G1"], "survey", cards)
    assert not list(RECORD.iter_errors(rec))
    assert rec["sentence"] == "One-genset-down gate binds: 101.5 kW against 95 kW, 6.5 kW over. No removal set fits."


# ------------------------------------------------------------------------------------------------ the CLI

def test_cli_power_edits_decide_and_bad_edits_are_refused_with_exit_2(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.consumes.power_kw.peak=50"]) == 0
    out = capsys.readouterr().out
    assert "VERDICT YES-IF" in out and "gate 95 kW: holds by throttling" in out and "throttle G4 fast_charge to charge, frees 40 kW" in out
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.modes.0.power_kw=40"]) == 0
    assert "VERDICT YES-IF" in capsys.readouterr().out
    assert cli.main(["admit", "G5", "--installed", "G2,G3", "--set", "G5.node.mass_t=0.5"]) == 0
    assert "BINDING placement 1 / 0 positions" in capsys.readouterr().out
    for bad, text in (("G4.consumes.power_kw.peak=abc", "'abc' is not a number"), ("G4.nothing=9", "no field nothing on the card"),
                      ("G9.x=1", "no card G9"), ("G4.hangar.mass_t=-1", "placement.parts[1].mass_t")):
        assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", bad]) == 2
        out = capsys.readouterr().out
        assert out.startswith("refused") and text in out and "Previous card kept" in out and "VERDICT" not in out


# ------------------------------------------------------------------------------------------------ the screen and its API

I = data.Inputs()


def test_view_offers_the_power_edits_and_moves_the_checks_with_them():
    base = view.admit(I, "A1-survey")
    assert [(p["name"], p["label"], p["kw"], p["mode"], p["field"]) for p in base["power"]] == \
        [("nominal", "NOMINAL", 10, "CHARGE", "G4.consumes.power_kw.nominal"), ("peak", "PEAK 20 MIN", 35, "FAST CHARGE", "G4.consumes.power_kw.peak")]
    a = view.admit(I, "A1-survey", {"G4.consumes.power_kw.peak": "50"})
    assert (a["verdict"], a["rejected"], a["power"][1]["kw"], a["power"][1]["mode"]) == ("YES-IF", None, 50, "FAST CHARGE")
    checks = {c["k"]: (c["v"], c["s"]) for c in a["checks"]}
    assert checks["1 GENSET"] == ("96.5 / 100 kW · GATE 95", "HOLDS BY THROTTLING")
    assert checks["THROTTLE"] == ("G4 FAST CHARGE → CHARGE · -40 kW", "STEP")
    assert a["sentence"] == a["record"]["sentence"] and not list(RECORD.iter_errors(a["record"]))
    assert [p["name"] for p in view.admit(I, "A3-survey")["power"]] == ["nominal"]  # G5 declares no peak


def test_view_refuses_an_edit_it_cannot_apply_without_deciding():
    kept = {"G4.consumes.power_kw.peak": "50"}
    for edit, reason in (({"G4.consumes.power_kw.pek": "50"}, "no field consumes.power_kw.pek on the card"),
                         ({"G4.consumes.power_kw.peak": "abc"}, "'abc' is not a number"), ({"G9.x": "1"}, "no card G9")):
        assert view.admit(I, "A1-survey", edit, kept) == {"refused": {"field": next(iter(edit)), "reason": reason}}
    b = view.admit(I, "A1-survey", {"G4.hangar.mass_t": "-1"}, kept)  # a schema problem is still a card-rejected decision
    assert b["verdict"] == "CARD REJECTED" and b["power"][1]["kw"] == 50


@pytest.fixture(scope="module")
def api():
    srv, th, base = serve(server.create_app(I, source="fixtures"))
    yield base
    srv.should_exit = True
    th.join(timeout=5)


def test_api_power_edit_answers_200_with_a_moved_verdict(api):
    status, body = get(api, "/api/admit?case=A1-survey&edit=G4.consumes.power_kw.peak=150")
    d = json.loads(body)
    assert (status, d["verdict"], d["binding"]) == (200, "NO", "CHW AT 30 °C 195.0 / 120.0 kW")
    assert d["sentence"].startswith("Cooling binds: 195 kW against 120 kW, 75 kW over.")
    status, body = get(api, "/api/admit?case=A6-survey&edit=G4.consumes.power_kw.peak=50")
    d = json.loads(body)
    assert (status, d["verdict"]) == (200, "YES") and "holds once G4 goes from fast charge to charge, 40 kW freed" in d["sentence"]
    assert d["edits"] == {"G4.consumes.power_kw.peak": "50"} and d["power"][1]["kw"] == 50


def test_api_bad_field_is_a_422_json_refusal_not_a_500(api):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(api, "/api/admit?case=A1-survey&edit=G4.consumes.power_kw.pek=40")
    assert e.value.code == 422
    assert json.loads(e.value.read()) == {"refused": {"field": "G4.consumes.power_kw.pek", "reason": "no field consumes.power_kw.pek on the card"}}
    with pytest.raises(urllib.error.HTTPError) as e:
        get(api, "/api/admit?case=A1-survey&edit=G4.consumes.power_kw.peak=abc&keep=G4.hangar.mass_t=0.8")
    assert e.value.code == 422 and json.loads(e.value.read())["refused"]["reason"] == "'abc' is not a number"
    status, body = get(api, "/api/admit?case=A1-survey&keep=G4.hangar.mass_t=0.8")  # the kept edit still decides
    assert status == 200 and json.loads(body)["verdict"] == "YES"
