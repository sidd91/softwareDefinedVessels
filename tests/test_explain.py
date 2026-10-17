"""The one sentence per decision (src/sdv/explain.py): built from the record's fields only, operator style, carrying
the numbers that bound. Expected sentences live in tests/fixtures/records/expected_sentences.yaml."""
import copy
import re

import pytest
import yaml

from sdv import explain as E
from sdv import records as R
from test_decision_record import ENGINE, FIXTURES, ROOT, SNAP, MISSIONS, errors

EXPECTED = yaml.safe_load((ROOT / "tests/fixtures/records/expected_sentences.yaml").read_text())
ALL = {**{f"fixture:{k}": v for k, v in FIXTURES.items()}, **{f"engine:{k}": v for k, v in ENGINE.items()}}
DEMO_WORDS = re.compile(r"\b(demo|jury|judge|scenario|fixture|test|injected|replay)\b", re.I)


def sentences(s: str) -> int:
    """Sentence ends: a stop followed by a space or the end, so 18.2 and parts[1].mass_t do not count."""
    return len(re.findall(r"[.!?](?:\s|$)", s))


def unit(x: float, u: str) -> str:
    return E.qty(x, u)


def must_contain(r: dict) -> list[str]:
    """The numbers (and names) each sentence must carry, read from the record independently of the explainer."""
    k, v = r["kind"], r["verdict"]
    if k == "D1" and v == "card-rejected":
        return [r["subject"], r["field"]]
    out = []
    b = r.get("binding")
    if k in ("D1", "D2") or (k == "D5" and b):
        out += [E.n(b["demand"]), E.n(b["capacity"])]
    if k == "D1" and v == "yes-if":
        o = r["options"][0]
        out += o["remove"] + [E.n(o["value_lost"])]
    if k == "D1" and v == "no" and "card_alone" in r:
        out.append(unit(r["card_alone"]["demand"], r["card_alone"]["unit"]))
    if k == "D1" and v == "not-now" and "within_days" in r["next_window"]:
        out.append(f"{E.n(r['next_window']['within_days'])} days")
    if k == "D1" and v == "yes" and r["genset"]["state"] == "holds_by_throttling":
        g = r["genset"]
        out += [f"{E.n(g['load_kw'])} kW", f"{E.n(g['gate_kw'])} kW", f"{E.n(sum(s['frees_kw'] for s in g['steps']))} kW"]
    if k == "D2":
        out += [E.POSITIONS.get(x["position"], x["position"]) for x in r["placement_rejected"][:1]]
    if k == "D3":
        lim = r["hard_limit"]
        lo, hi = r["cost_to_loser"]["minutes_lost"]
        out += [f"{E.n(lim['when']['value'])} %", f"{E.n(lim['then']['within_min'])} min", f"minute {E.minute(r['deadline_t_s'])}",
                f"{E.n(lo)} to {E.n(hi)}", r["proceeds"], r["cost_to_loser"]["guest"]]
        out += [f"{E.n(kw)} kW" for kw in r.get("reserved", {}).values() if kw]
    if k == "D4":
        out += [E.n(r["load_kw"]), f"{E.n(r['limit_kw'])} kW"]
        if v == "hold":
            out += [f"{len(r['steps'])} steps", f"{E.n(r['armed'][0]['frees_kw'])} kW", r["armed"][0]["guest"]]
        if v == "shed":
            out += [f"{E.n(r['load_after_kw'])} kW", f"{E.n(sum(s['frees_kw'] for s in r['steps']))} kW"]
            out += [f"{g} loses {E.n(100 * (l['capability_before'] - l['capability_after']), 0)} %"
                    for g, l in r["losses"].items() if l["capability_after"] < l["capability_before"]]
            out += [g for g, l in r["losses"].items() if l["capability_after"] == l["capability_before"]]
    if k == "D5":
        out.append(f"{r['crew_aboard']} aboard")
        if r.get("deadline_t_s") is not None and v != "not-now":
            out.append(E.minute(r["deadline_t_s"]))
        if r.get("deck_evidence") and v != "not-now":
            out.append(r["deck_evidence"])
    return out


# ------------------------------------------------------------------------------------------------ the fixtures

def test_every_fixture_has_an_expected_sentence_with_its_source():
    assert sorted(EXPECTED) == sorted(FIXTURES)
    assert all(e["source"] and e["sentence"] for e in EXPECTED.values())


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_the_sentence_is_built_from_the_record(name):
    r = FIXTURES[name]
    assert E.sentence(r) == EXPECTED[name]["sentence"] == r["sentence"]


def test_every_verdict_and_crew_level_has_a_fixture():
    have = {(r["kind"], r["verdict"]) for r in FIXTURES.values()}
    want = {("D1", v) for v in ("yes", "yes-if", "no", "not-now", "card-rejected")} | {("D2", "placed"), ("D2", "unplaced"),
            ("D3", "proceeds"), ("D4", "hold"), ("D4", "shed")} | {("D5", v) for v in ("confirm", "cleared", "held", "not-now", "automatic", "forbidden")}
    assert want <= have
    assert {r["crew_aboard"] for r in FIXTURES.values() if r["kind"] == "D5"} == {14, 6, 0}


# ------------------------------------------------------------------------------------------------ every record, fixture or engine

@pytest.mark.parametrize("name", sorted(ALL))
def test_operator_style(name):
    r = ALL[name]
    s = r["sentence"]
    assert s == E.sentence(r)
    assert 1 <= sentences(s) <= 2, s
    assert ";" not in s and "—" not in s and len(s) <= 240, s
    assert not DEMO_WORDS.search(s), s
    assert not re.search(r"\?|None|null|True|False", s), s
    if r["verdict"] != "card-rejected":
        assert "_" not in s, s            # no snake_case names leak through
    assert s[0].isupper() and s.endswith("."), s


@pytest.mark.parametrize("name", sorted(ALL))
def test_the_sentence_carries_its_binding_numbers(name):
    r = ALL[name]
    missing = [x for x in must_contain(r) if x not in r["sentence"]]
    assert not missing, (missing, r["sentence"])


MUTATIONS = {
    "D1": lambda r: r["binding"].update(demand=r["binding"]["demand"] + 0.5, free=r["binding"]["free"] - 0.5),
    "D2": lambda r: r["binding"].update(capacity=r["binding"]["capacity"] + 3, free=r["binding"]["free"] + 3),
    "D3": lambda r: (r.update(deadline_t_s=r["deadline_t_s"] + 123), r["cost_to_loser"].update(minutes_lost=[31, 34])),
    "D4": lambda r: r.update(load_kw=r["load_kw"] + 3, limit_kw=r["limit_kw"] - 2),
    "D5": lambda r: r.update(crew_aboard={14: 6, 6: 14, 0: 6}[r["crew_aboard"]]),
}


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_no_canned_sentence_the_words_follow_the_numbers(name):
    """Change the deciding numbers and the sentence changes with them: nothing is a fixed string."""
    r = copy.deepcopy(FIXTURES[name])
    before = E.sentence(r)
    if r["verdict"] == "card-rejected":
        r["field"] = "modes[2].power_kw: 'ten' is not of type 'number'"
    else:
        MUTATIONS[r["kind"]](r)
    after = E.sentence(r)
    assert after != before
    missing = [x for x in must_contain(r) if x not in after]
    assert not missing, (missing, after)


# ------------------------------------------------------------------------------------------------ what the brief asks of each class

def test_d1_yes_if_names_the_top_ranked_condition_and_its_cost():
    s = FIXTURES["d1_A1_survey"]["sentence"]
    assert s.startswith("Mass binds: 10.035 t against 10 t, 35 kg over.") and "Yes if G1 disembarks, mission value lost 0.2" in s
    assert "G5 node moves to Bay 2 (4 to 8 h by crane)" in FIXTURES["d1_A4_sar"]["sentence"]


def test_d1_not_now_gives_the_next_window():
    assert FIXTURES["d1_not_now_A6_under_way_survey"]["sentence"].endswith("It can come aboard at the next port call, within 14 days.")
    r = copy.deepcopy(FIXTURES["d1_not_now_A6_under_way_survey"])
    r["next_window"] = {"kind": "at_sea_window", "t_s": 2700}
    assert E.sentence(r).endswith("It can come aboard in the next at-sea window, minute 45.")
    r["next_window"] = {"kind": "resource_frees", "t_s": 2220, "event": "G4's fast charge ends"}
    assert E.sentence(r).endswith("It fits from minute 37, when G4's fast charge ends.")


def test_d3_puts_the_hard_limit_before_the_cost_to_the_loser():
    for f in ("survey", "sar"):
        s = FIXTURES[f"d3_m08_{f}"]["sentence"]
        assert s.index("below 20 %") < s.index("by minute 18.2") < s.index("25 to 27")


def test_d4_minute_12_holds_with_0_steps_and_the_armed_step():
    for f, load in (("survey", 48), ("sar", 81)):
        s = FIXTURES[f"d4_m12_{f}"]["sentence"]
        assert s.startswith(f"Holds: {load} of 95 kW with one genset down") and "0 steps" in s
        assert s.endswith("First armed step: G5 full to low power, 45 to 8 kW, frees 37 kW.")


def test_d4_minute_19_names_kw_freed_capability_lost_and_every_guest():
    s = FIXTURES["d4_m19_survey"]["sentence"]
    assert "81 kW against the 75 kW limit" in s and "G4 fast charge to charge, 35 to 10 kW, frees 25 kW" in s
    assert "the load is 56 kW: G4 loses 30 %, G3 and G5 nothing." in s
    s = FIXTURES["d4_m19_sar"]["sentence"]
    assert "G5 full to low power, 45 to 8 kW, frees 37 kW and the load is 44 kW: G5 loses 70 %, G3 and G4 nothing." in s


def test_d4_unconfirmed_sheds_nothing_and_says_why():
    r = copy.deepcopy(FIXTURES["d4_m19_survey"])
    r.update(verdict="unconfirmed", steps=[], load_after_kw=81, free_after_kw=-6, unconfirmed_because="feed stale")
    assert not errors(r)
    assert E.sentence(r) == ("Not shed: 81 kW against the 75 kW limit is not confirmed (feed stale). "
                             "First armed step: G5 full to low power, 45 to 8 kW, frees 37 kW.")


def test_r3_at_14_6_and_0_aboard():
    assert FIXTURES["d5_r3_14_held"]["sentence"] == ("Recovery held at 14 aboard: the landing officer reports the zone not clear. "
                                                     "G4 at 18 % must start its 4 min approach by minute 14.2 to land by 18.2.")
    assert FIXTURES["d5_r3_6_not_now"]["sentence"] == ("Not now at 6 aboard: deck work (3 min) waits until G4 is secured. "
                                                       "Deck clearing lead 15 min against 8 min, 7 min over.")
    assert FIXTURES["d5_r3_0_forbidden"]["sentence"] == ("Recovery forbidden at 0 aboard: deck activity since the last crew sweep "
                                                         "voided the latch. G4 at 18 % ditches by minute 18.2 and its air rescue capability is lost.")
    assert "latched at the last crew sweep (78 min ago)" in FIXTURES["d5_r3_0_automatic"]["sentence"]


def test_a_d5_record_from_the_core_names_its_evidence():
    """The core's records carry the evidence in words (records.from_d5); the sentence keeps them whole."""
    r = R.from_d5(seq=3, snapshot=SNAP["scenario_b_survey_m08"], verdict="held", crew=14, deck_evidence="no answer from the bridge",
                  deadline_t_s=1091.9, mission=MISSIONS["survey"])
    assert not errors(r)
    assert r["sentence"] == "Recovery held at 14 aboard: no answer from the bridge. G4 must land by minute 18.2."


def test_a_card_rejected_by_the_engine_names_the_field():
    r = R.card_rejected(seq=0, tick=0, card_id="G4", field="placement.parts[1].mass_t: -1 is less than the minimum of 0", mission=MISSIONS["survey"])
    assert not errors(r)
    assert r["sentence"] == "Card rejected: placement.parts[1].mass_t: -1 is less than the minimum of 0."
