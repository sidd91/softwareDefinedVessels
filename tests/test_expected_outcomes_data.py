"""Checks that the expected-outcomes oracle file agrees with the cards and assumptions.

No governor engine here. tests/oracles/expected_outcomes.yaml copies the hand-computed numbers from
docs/EXPECTED_OUTCOMES.md; each test below recomputes one kind of number from manifests/G*.yaml,
config/missions/*.yaml and config/assumptions.yaml and checks the oracle file says the same thing.
"""
import copy
import glob
import itertools
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
CARDS = {}
for _f in sorted(glob.glob(str(ROOT / "manifests/G*.yaml"))):
    _card = yaml.safe_load(open(_f))
    CARDS[_card["id"]] = _card
FILES = {}
for _f in sorted(glob.glob(str(ROOT / "config/missions/*.yaml"))):
    _m = yaml.safe_load(open(_f))
    FILES[_m["id"]] = _m
O = yaml.safe_load((ROOT / "tests/oracles/expected_outcomes.yaml").read_text())
CASES = O["scenario_a"]
B = O["scenario_b"]
CASE_IDS = [f"{c['case']}-{c['file']}" for c in CASES]

MARGIN_T = A["mass"]["margin_t"]
RESERVE_ONE_SET = A["power"]["guest_reserve_kw"]["one_genset_down"]
HEADROOM = A["power"]["shed_headroom_kw"]
EPS = 1e-6

# Which stability multiplier each slot uses (assumptions mass.multiplier).
SLOT_MULTIPLIER_KEY = {
    "bay1": "bay",
    "bay1_half": "bay",
    "bay2": "bay",
    "flight_deck": "flight_deck",
    "hangar_roof": "hangar_roof",
    "mast_free": "mast",
}


# ---------------------------------------------------------------- helpers


def cards_with(edits):
    """The cards with a case's live edits applied, e.g. {"G4.hangar.mass_t": 0.8}."""
    cards = copy.deepcopy(CARDS)
    for key, value in (edits or {}).items():
        gid, part_name, field = key.split(".")
        part = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)
        part[field] = value
    return cards


def envelope_kw(card):
    """Sustained worst-case draw: a peak counts if it lasts longer than the 60 s peak window."""
    p = card["consumes"]["power_kw"]
    peak_sustained = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
    return max(p["nominal"], peak_sustained)


def mass_t(cards, guests):
    return sum(part["mass_t"] for g in guests for part in cards[g]["placement"]["parts"])


def slot_of(cards, gid, part, placement):
    """The slot a part sits in; an unplaced part (missing or null) counts at its preferred position."""
    slot = (placement or {}).get(f"{gid}.{part['name']}")
    return slot if slot else part["preferred"][0]


def stability_t_eq(cards, guests, placement=None):
    mult = A["mass"]["multiplier"]
    return sum(
        part["mass_t"] * mult[SLOT_MULTIPLIER_KEY[slot_of(cards, g, part, placement)]]
        for g in guests
        for part in cards[g]["placement"]["parts"]
    )


def chilled_kw(cards, guests):
    return sum(envelope_kw(cards[g]) for g in guests if cards[g]["cooling"] == "chilled_water")


def heat_capacity_kw(seawater_c):
    pts = A["heat"]["capacity_kw_at"]
    (t0, c0), (t1, c1) = sorted(pts.items())
    return c0 + (c1 - c0) * (seawater_c - t0) / (t1 - t0)


def tipping_point_c(chilled):
    """Seawater temperature at which the loop capacity falls to the chilled load."""
    pts = A["heat"]["capacity_kw_at"]
    (t0, c0), (t1, c1) = sorted(pts.items())
    return t0 + (c0 - chilled) * (t1 - t0) / (c0 - c1)


def line_kw(cards, guests, placement, line):
    """Power on one mission line; a guest draws on the line of its first part's position."""
    total = 0
    for g in guests:
        slot = slot_of(cards, g, cards[g]["placement"]["parts"][0], placement)
        position = "bay1" if slot == "bay1_half" else slot
        if A["positions"][position]["power_line"] == line:
            total += envelope_kw(cards[g])
    return total


def mode(gid, name):
    return next(m for m in CARDS[gid]["modes"] if m["name"] == name)


def weight(file_id, gid):
    return FILES[file_id]["weights"][CARDS[gid]["capability"]["name"]]


def is_critical(file_id, gid):
    return gid in FILES[file_id]["mission_critical"]


def envelope_mode(cards, gid):
    """The card mode whose draw is the guest's envelope draw."""
    return next(m["name"] for m in cards[gid]["modes"] if m["power_kw"] == envelope_kw(cards[gid]))


def first_step_down(gid, from_mode):
    """The next lower card mode, as a ladder step; None if the mode cannot be interrupted or is off."""
    modes = sorted(CARDS[gid]["modes"], key=lambda m: -m["power_kw"])
    names = [m["name"] for m in modes]
    i = names.index(from_mode)
    if i + 1 == len(modes) or not modes[i].get("interruptible", True):
        return None
    return {"guest": gid, "from_mode": from_mode, "to_mode": names[i + 1]}


def step_frees_kw(step):
    return mode(step["guest"], step["from_mode"])["power_kw"] - mode(step["guest"], step["to_mode"])["power_kw"]


def step_value_lost(file_id, step):
    retained = mode(step["guest"], step["from_mode"])["capability_retained"] - mode(step["guest"], step["to_mode"])["capability_retained"]
    return weight(file_id, step["guest"]) * retained


def step_order_key(file_id, step):
    """Assumption 7: throttles before sheds; within each, non-critical first, then cost per kW, then id."""
    return (
        step["to_mode"] == "off",
        is_critical(file_id, step["guest"]),
        step_value_lost(file_id, step) / step_frees_kw(step),
        step["guest"],
    )


def guests_of(case):
    return case["installed"] + [case["card"]]


def yes_if_options():
    for case, cid in zip(CASES, CASE_IDS):
        for i, option in enumerate(case["yes_if"]):
            yield pytest.param(case, option, id=f"{cid}-option{i + 1}")


def recompute_line(cards, guests, placement, line):
    """Recompute one ledger line of a case from the cards; returns (demand, capacity)."""
    cls = line["class"]
    if cls == "mass":
        return mass_t(cards, guests), MARGIN_T
    if cls == "stability":
        return stability_t_eq(cards, guests, placement), A["mass"]["stability_budget_t_eq"]
    if cls == "power":
        return sum(envelope_kw(cards[g]) for g in guests), A["power"]["envelope_reserve_kw"]
    if cls == "heat":
        return chilled_kw(cards, guests), heat_capacity_kw(A["envelope"]["judge_cooling_at_c"])
    if cls in ("line_port", "line_stbd"):
        side = cls.split("_")[1]
        return line_kw(cards, guests, placement, side), A["power"]["mission_line_kw"][side]
    if cls == "mast_mass":
        return mass_t(cards, ["G1"]) * 1000, A["positions"]["mast_free"]["max_kg"]
    if cls == "mast_area":
        return CARDS["G1"]["placement"]["parts"][0]["area_m2"], A["positions"]["mast_free"]["area_m2"]
    if cls == "mast_air_cooling":
        return envelope_kw(cards["G1"]), A["heat"]["air_cooled_max_kw"]
    if cls == "flight_deck_drone":
        drone = next(p for p in cards["G4"]["placement"]["parts"] if p["name"] == "drone")
        return drone["mass_t"] * 1000, A["positions"]["flight_deck"]["hangar_max_kg"]
    raise AssertionError(f"no recompute rule for line class {cls}")


# ---------------------------------------------------------------- Scenario A: shape


def test_scenario_a_cases_six_brief_drills_under_both_files_plus_our_g6_drill():
    brief_drills = [cid for cid in CASE_IDS if not cid.startswith("A7-")]
    assert sorted(brief_drills) == sorted(f"A{n}-{f}" for n in range(1, 7) for f in ("survey", "sar"))
    # A7 runs our own card, G6, under disaster relief (the file it was written for) and sar.
    assert sorted(cid for cid in CASE_IDS if cid.startswith("A7-")) == ["A7-disaster_relief", "A7-sar"]
    for case in CASES:
        assert case["file"] in FILES
        assert set(guests_of(case)) <= set(CARDS)
        assert case["card"] not in case["installed"]
        assert case["verdict"] in ("yes", "yes-if")


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_both_files_agree_on_everything_but_the_ranking(case):
    # Doc: the sar row of each drill says "Same" for the binding line and placement.
    twin = next(c for c in CASES if c["case"] == case["case"] and c is not case)
    for key in ("installed", "card", "card_edits", "verdict", "binding", "placement", "seawater_tip_c"):
        assert case[key] == twin[key], key
    for key in ("other_lines", "also_binding", "not_enough", "seawater_scan"):
        assert case.get(key) == twin.get(key), key
    assert sorted(map(tuple, (o["remove"] for o in case["yes_if"]))) == sorted(
        map(tuple, (o["remove"] for o in twin["yes_if"]))
    )


# ---------------------------------------------------------------- Scenario A: binding and lines


MASS_BOUND = [c for c in CASES if c["binding"]["class"] == "mass"]
YES_CASES = [c for c in CASES if c["verdict"] == "yes"]


def test_a5_and_a7_are_the_only_drills_not_bound_by_mass():
    assert sorted({c["case"] for c in CASES if c not in MASS_BOUND}) == ["A5", "A7"]


@pytest.mark.parametrize("case", MASS_BOUND, ids=lambda c: f"{c['case']}-{c['file']}")
def test_mass_binding_demand_equals_the_sum_of_card_part_masses(case):
    b = case["binding"]
    cards = cards_with(case["card_edits"])
    assert b["unit"] == "t"
    assert b["demand"] == pytest.approx(mass_t(cards, guests_of(case)), abs=EPS)
    assert b["capacity"] == MARGIN_T
    # A load equal to its limit holds (assumption 4): over the margin is yes-if, within it is yes.
    assert (b["demand"] > b["capacity"]) == (case["verdict"] == "yes-if")


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_binding_and_other_lines_recompute_from_the_cards(case):
    cards = cards_with(case["card_edits"])
    lines = [case["binding"]] + [ln for ln in case.get("other_lines", []) if ln["class"] != "placement"]
    for line in lines:
        demand, capacity = recompute_line(cards, guests_of(case), case["placement"], line)
        assert line["demand"] == pytest.approx(demand, abs=EPS), line["class"]
        assert line["capacity"] == pytest.approx(capacity, abs=EPS), line["class"]
        if line is not case["binding"]:
            # A line other than the binding one is marked fails exactly when it is over.
            assert line.get("fails", False) == (demand > capacity + EPS), line["class"]


@pytest.mark.parametrize("case", YES_CASES, ids=lambda c: f"{c['case']}-{c['file']}")
def test_a_yes_verdict_names_the_tightest_line_as_binding(case):
    cards = cards_with(case["card_edits"])
    # Ship-wide ledger classes only; slot limits (mast, flight-deck drone) are placement detail.
    ledger = {"mass", "stability", "power", "heat", "line_port", "line_stbd"}
    lines = [ln for ln in [case["binding"]] + case.get("other_lines", []) if ln["class"] in ledger]
    free = {}
    for line in lines:
        demand, capacity = recompute_line(cards, guests_of(case), case["placement"], line)
        assert demand <= capacity + EPS, line["class"]
        free[line["class"]] = (capacity - demand) / capacity
    assert min(free, key=free.get) == case["binding"]["class"]


def test_a4_placement_line_g3_needs_both_halves_and_the_node_holds_one():
    for case in (c for c in CASES if c["case"] == "A4"):
        (line,) = case["also_binding"]
        bay1_halves = A["positions"]["bay1"]["halves"]
        held = sum(1 for slot in case["placement"].values() if slot == "bay1_half")
        assert line["capacity"] == bay1_halves - held == 1
        assert line["demand"] == bay1_halves
        # Every G3 part needs the whole bay: the vehicle rides on the cradle.
        assert all(p["allowed"] == [line["slot"]] == ["bay1"] for p in CARDS["G3"]["placement"]["parts"])


# ---------------------------------------------------------------- Scenario A: placement


def check_placement(cards, guests, placement, allow_unplaced):
    expected_keys = {f"{g}.{p['name']}" for g in guests for p in cards[g]["placement"]["parts"]}
    assert set(placement) == expected_keys
    occupants = {}
    for key, slot in placement.items():
        gid, part_name = key.split(".")
        part = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)
        if slot is None:
            assert allow_unplaced, key
            continue
        assert slot in part["allowed"], key
        occupants.setdefault(slot, set()).add(gid)
    for slot, gids in occupants.items():
        limit = A["positions"]["bay1"]["halves"] if slot == "bay1_half" else 1
        assert len(gids) <= limit, slot
    # A whole-bay guest and a half-bay guest cannot share Bay 1.
    assert not (occupants.get("bay1") and occupants.get("bay1_half"))
    # Each position's own limits from assumptions.yaml: tonnes, kilograms and mast area.
    for position, parts in parts_by_position(cards, placement).items():
        pos = A["positions"][position]
        load_t = sum(part["mass_t"] for part in parts)
        if "max_t" in pos:
            assert load_t <= pos["max_t"] + EPS, position
        if "max_kg" in pos:
            assert load_t * 1000 <= pos["max_kg"] + EPS, position
        if "area_m2" in pos:
            assert sum(part.get("area_m2", 0) for part in parts) <= pos["area_m2"] + EPS, position
        if "hangar_max_kg" in pos:
            for part in parts:
                if part["name"] == "drone":
                    assert part["mass_t"] * 1000 <= pos["hangar_max_kg"] + EPS, position


def parts_by_position(cards, placement):
    """Placed parts grouped by position; both halves of Bay 1 count against Bay 1."""
    out = {}
    for key, slot in placement.items():
        if slot is None:
            continue
        gid, part_name = key.split(".")
        part = next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part_name)
        out.setdefault("bay1" if slot == "bay1_half" else slot, []).append(part)
    return out


def slot_is_free(slot, placement, own_key):
    """Whether a slot can take one more part, given everything else that is placed."""
    others = {k: v for k, v in placement.items() if k != own_key and v is not None}
    taken = list(others.values())
    if slot == "bay1":
        return "bay1" not in taken and "bay1_half" not in taken
    if slot == "bay1_half":
        return "bay1" not in taken and taken.count("bay1_half") < A["positions"]["bay1"]["halves"]
    return slot not in taken


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_an_unplaced_part_really_has_no_free_allowed_slot(case):
    # A null slot means the part cannot go anywhere as given: every allowed slot is taken.
    unplaced = [k for k, v in case["placement"].items() if v is None]
    placement_lines = [ln for ln in case.get("other_lines", []) + case.get("also_binding", []) if ln["class"] == "placement"]
    assert bool(unplaced) == bool(placement_lines)
    for line in case.get("other_lines", []):
        if line["class"] == "placement":
            assert line["fails"] is True
    for key in unplaced:
        gid, part_name = key.split(".")
        part = next(p for p in CARDS[gid]["placement"]["parts"] if p["name"] == part_name)
        assert not any(slot_is_free(slot, case["placement"], key) for slot in part["allowed"]), key


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_placement_puts_every_part_in_an_allowed_free_slot(case):
    cards = cards_with(case["card_edits"])
    check_placement(cards, guests_of(case), case["placement"], allow_unplaced=case["verdict"] == "yes-if")
    for option in case["yes_if"]:
        if "placement" in option:
            kept = [g for g in guests_of(case) if g not in option["remove"]]
            check_placement(cards, kept, option["placement"], allow_unplaced=False)


# ---------------------------------------------------------------- Scenario A: yes-if


@pytest.mark.parametrize(("case", "option"), list(yes_if_options()))
def test_every_yes_if_removal_brings_mass_within_the_margin(case, option):
    cards = cards_with(case["card_edits"])
    kept = [g for g in guests_of(case) if g not in option["remove"]]
    assert case["card"] not in option["remove"]
    assert set(option["remove"]) <= set(case["installed"])
    assert mass_t(cards, kept) <= MARGIN_T + EPS
    if "mass_after_t" in option:
        assert option["mass_after_t"] == pytest.approx(mass_t(cards, kept), abs=EPS)
    if "stability_after_t_eq" in option:
        stab = stability_t_eq(cards, kept, option.get("placement"))
        assert option["stability_after_t_eq"] == pytest.approx(stab, abs=EPS)
        assert stab <= A["mass"]["stability_budget_t_eq"]


@pytest.mark.parametrize(("case", "option"), list(yes_if_options()))
def test_yes_if_value_lost_is_the_priority_weight_of_what_leaves(case, option):
    # Removal loses the whole capability (retained 1.0 to 0), so value lost = weight x 1.0.
    assert option["value_lost"] == pytest.approx(sum(weight(case["file"], g) for g in option["remove"]), abs=EPS)
    critical = any(is_critical(case["file"], g) for g in option["remove"])
    assert option.get("mission_critical", False) == critical


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_yes_if_list_is_ranked_by_value_then_size_then_id_with_critical_last(case):
    def key(option):
        return (
            any(is_critical(case["file"], g) for g in option["remove"]),
            option["value_lost"],
            len(option["remove"]),
            option["remove"],
        )

    assert case["yes_if"] == sorted(case["yes_if"], key=key)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_yes_if_list_holds_exactly_the_minimal_mass_fixes(case):
    cards = cards_with(case["card_edits"])
    fits = []
    for n in range(len(case["installed"]) + 1):
        for subset in itertools.combinations(case["installed"], n):
            kept = [g for g in guests_of(case) if g not in subset]
            if mass_t(cards, kept) <= MARGIN_T + EPS and not any(set(f) <= set(subset) for f in fits):
                fits.append(subset)
    if case["verdict"] == "yes":
        assert fits == [()]
        assert case["yes_if"] == []
    else:
        assert sorted(fits) == sorted(tuple(o["remove"]) for o in case["yes_if"])


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_removals_the_doc_calls_not_enough_leave_mass_over(case):
    cards = cards_with(case["card_edits"])
    for item in case.get("not_enough", []):
        kept = [g for g in guests_of(case) if g not in item["remove"]]
        assert item["mass_after_t"] == pytest.approx(mass_t(cards, kept), abs=EPS)
        assert mass_t(cards, kept) > MARGIN_T


def test_a7_g6_is_kept_under_disaster_relief_and_throttled_first_under_sar():
    # Our card's drill: the slide-10 desalination unit is the first to give way under sar,
    # but disaster relief marks it mission-critical, so the drone's charge yields first.
    a7 = {c["file"]: c for c in CASES if c["case"] == "A7"}
    assert all(c["card"] == "G6" for c in a7.values())
    assert "team invention" in CARDS["G6"]["source"]
    sar_fix = a7["sar"]["one_genset_down"]["fix"]
    assert sar_fix[0]["guest"] == "G6" and not is_critical("sar", "G6")
    relief_fix = a7["disaster_relief"]["one_genset_down"]["fix"]
    assert relief_fix[0]["guest"] != "G6"
    assert relief_fix[-1]["guest"] == "G6" and is_critical("disaster_relief", "G6")
    # G5 holds its preferred Bay 2, so G6 sits in a tolerated position.
    unit = CARDS["G6"]["placement"]["parts"][0]
    slot = a7["sar"]["placement"]["G6.unit"]
    assert slot in unit["allowed"] and slot not in unit["preferred"]


def test_a4_node_move_is_one_crane_move_in_the_port_bay_window():
    for case in (c for c in CASES if c["case"] == "A4"):
        option = next(o for o in case["yes_if"] if o["remove"] == ["G2"])
        also = option["also"]
        assert also["hours"] == A["installation"]["in_port"]["hours_per_bay_guest"]
        assert also["crane_moves"] == 1
        assert also["move"] == {"G5.node": "bay2"}
        assert option["placement"]["G5.node"] == "bay2"
        node = next(p for p in CARDS["G5"]["placement"]["parts"] if p["name"] == "node")
        assert node["mass_t"] <= A["installation"]["in_port"]["crane_t"]


# ---------------------------------------------------------------- Scenario A: one genset down


def one_genset_down_blocks():
    for case, cid in zip(CASES, CASE_IDS):
        if case["one_genset_down"]:
            yield pytest.param(case, case["one_genset_down"], guests_of(case), id=cid)
        for i, option in enumerate(case["yes_if"]):
            if "one_genset_down" in option:
                kept = [g for g in guests_of(case) if g not in option["remove"]]
                yield pytest.param(case, option["one_genset_down"], kept, id=f"{cid}-option{i + 1}")


def test_every_case_has_a_one_genset_down_result():
    for case, cid in zip(CASES, CASE_IDS):
        has_own = case["one_genset_down"] is not None
        every_option = case["yes_if"] and all("one_genset_down" in o for o in case["yes_if"])
        assert has_own or every_option, cid


@pytest.mark.parametrize(("case", "ogd", "guests"), list(one_genset_down_blocks()))
def test_one_genset_down_load_is_the_sum_of_envelope_draws(case, ogd, guests):
    cards = cards_with(case["card_edits"])
    load = sum(envelope_kw(cards[g]) for g in guests)
    assert ogd["load_kw"] == pytest.approx(load, abs=EPS)
    assert ogd["reserve_kw"] == RESERVE_ONE_SET
    assert ogd["holds"] == (load <= RESERVE_ONE_SET)
    if "short_kw" in ogd:
        assert ogd["short_kw"] == pytest.approx(load - RESERVE_ONE_SET, abs=EPS)
    if "spare_kw" in ogd:
        assert ogd["spare_kw"] == pytest.approx(RESERVE_ONE_SET - load, abs=EPS)
    if "against_ceiling_kw" in ogd:
        assert ogd["against_ceiling_kw"] == RESERVE_ONE_SET - HEADROOM


@pytest.mark.parametrize(("case", "ogd", "guests"), list(one_genset_down_blocks()))
def test_one_genset_down_fix_steps_match_the_cards_and_close_the_gap(case, ogd, guests):
    cards = cards_with(case["card_edits"])
    fix = ogd.get("fix", [])
    if ogd["holds"] and "against_ceiling_kw" not in ogd:
        assert fix == []
        return
    target = ogd.get("against_ceiling_kw", ogd["reserve_kw"])
    gap = ogd["load_kw"] - target
    needed = ogd.get("steps_needed", len(fix))
    cumulative = 0
    for i, step in enumerate(fix):
        assert step["guest"] in guests
        assert mode(step["guest"], step["from_mode"]).get("interruptible", True)
        frees = step_frees_kw(step)
        if "frees_kw" in step:
            assert step["frees_kw"] == pytest.approx(frees, abs=EPS)
        if "value_lost" in step:
            assert step["value_lost"] == pytest.approx(step_value_lost(case["file"], step), abs=EPS)
        if "capability_lost_pct" in step:
            lost = mode(step["guest"], step["from_mode"])["capability_retained"] - mode(step["guest"], step["to_mode"])["capability_retained"]
            assert step["capability_lost_pct"] == pytest.approx(100 * lost, abs=EPS)
        assert step.get("mission_critical", False) == is_critical(case["file"], step["guest"])
        cumulative += frees
        if "load_after_kw" in step:
            assert step["load_after_kw"] == pytest.approx(ogd["load_kw"] - cumulative, abs=EPS)
        if i + 1 == needed:
            assert cumulative >= gap - EPS
            assert cumulative - frees < gap
    keys = [step_order_key(case["file"], s) for s in fix]
    assert keys == sorted(keys)
    # The listed steps are each guest's first step down from its envelope mode, in ladder order,
    # recomputed from the cards; a wrong guest or mode in the oracle fails here.
    candidates = [s for s in (first_step_down(g, envelope_mode(cards, g)) for g in guests) if s]
    candidates.sort(key=lambda s: step_order_key(case["file"], s))
    as_tuples = [(s["guest"], s["from_mode"], s["to_mode"]) for s in candidates]
    assert [(s["guest"], s["from_mode"], s["to_mode"]) for s in fix] == as_tuples[: len(fix)]


# ---------------------------------------------------------------- Scenario A: seawater


def seawater_blocks():
    for case, cid in zip(CASES, CASE_IDS):
        if case["seawater_tip_c"] is not None:
            yield pytest.param(case, case["seawater_tip_c"], guests_of(case), id=cid)
        for i, option in enumerate(case["yes_if"]):
            if "seawater_tip_c" in option:
                kept = [g for g in guests_of(case) if g not in option["remove"]]
                yield pytest.param(case, option["seawater_tip_c"], kept, id=f"{cid}-option{i + 1}")


@pytest.mark.parametrize(("case", "tip", "guests"), list(seawater_blocks()))
def test_seawater_tipping_point_follows_the_cooling_line(case, tip, guests):
    cards = cards_with(case["card_edits"])
    assert tip == pytest.approx(tipping_point_c(chilled_kw(cards, guests)), abs=EPS)


def test_only_a3_as_given_flips_inside_the_seawater_scan():
    scan_max = A["admission"]["seawater_scan_max_c"]
    step = A["admission"]["seawater_scan_step_c"]
    for case in CASES:
        if case["seawater_tip_c"] is None:
            assert all(o["seawater_tip_c"] > scan_max for o in case["yes_if"])
            continue
        inside = case["seawater_tip_c"] <= scan_max
        assert inside == (case["case"] == "A3"), case["case"]
        if inside:
            chilled = chilled_kw(CARDS, guests_of(case))
            scan = case["seawater_scan"]
            assert heat_capacity_kw(scan["holds_at_c"]) >= chilled
            assert heat_capacity_kw(scan["fails_at_c"]) < chilled
            assert scan["fails_at_c"] - scan["holds_at_c"] == pytest.approx(step)


def test_satcom_is_judged_at_the_guests_minimums():
    s = O["satcom"]
    total = sum(CARDS[g]["consumes"]["data_satcom_mbps"]["min"] for g in s["guests"])
    assert s["demand_mbps_at_min"] == pytest.approx(total)
    assert s["capacity_mbps"] == A["data"]["satcom_envelope_mbps"]
    assert total <= s["capacity_mbps"]
    assert s["g5_nominal_mbps"] == CARDS["G5"]["consumes"]["data_satcom_mbps"]["nominal"] > s["capacity_mbps"]


# ---------------------------------------------------------------- Scenario B: load-outs and ceiling


def test_ceiling_is_the_lower_of_reserve_and_cooling_less_the_headroom():
    c = B["ceiling"]
    cooling = heat_capacity_kw(B["seawater_c"])
    assert c["reserve_kw"] == RESERVE_ONE_SET
    assert c["cooling_kw"] == pytest.approx(cooling, abs=0.05)
    assert c["headroom_kw"] == HEADROOM
    assert c["kw"] == pytest.approx(min(RESERVE_ONE_SET, cooling) - HEADROOM)


def test_heat_passes_at_minute_12():
    h = B["heat_check"]
    assert h["capacity_kw"] == pytest.approx(heat_capacity_kw(B["seawater_c"]) - HEADROOM, abs=0.05)
    loads = [
        sum(d for g, d in row["draws"].items() if CARDS[g]["cooling"] == "chilled_water")
        for lo in B["loadouts"]
        for row in lo["minute_12"].values()
    ]
    assert h["max_chilled_kw"] == max(loads)
    assert h["max_chilled_kw"] <= h["capacity_kw"]


def test_three_loadouts_as_in_the_doc():
    assert [lo["id"] for lo in B["loadouts"]] == ["i", "ii", "iii"]
    assert [lo["guests"] for lo in B["loadouts"]] == [["G2", "G3", "G4", "G5"], ["G3", "G4", "G5"], ["G2", "G3", "G4"]]


@pytest.mark.parametrize("lo", B["loadouts"], ids=lambda lo: lo["id"])
def test_loadout_mass_and_stability_recompute(lo):
    m = mass_t(CARDS, lo["guests"])
    s = stability_t_eq(CARDS, lo["guests"])
    assert lo["mass_t"] == pytest.approx(m, abs=EPS)
    assert lo["stability_t_eq"] == pytest.approx(s, abs=EPS)
    if "mass_over_t" in lo:
        assert lo["mass_over_t"] == pytest.approx(m - MARGIN_T, abs=EPS)
    if "mass_spare_t" in lo:
        assert lo["mass_spare_t"] == pytest.approx(MARGIN_T - m, abs=EPS)
    if "stability_over_t_eq" in lo:
        assert lo["stability_over_t_eq"] == pytest.approx(s - A["mass"]["stability_budget_t_eq"], abs=EPS)
    if "chilled_kw_at_30c" in lo:
        assert lo["chilled_kw_at_30c"] == chilled_kw(CARDS, lo["guests"])
        assert lo["chilled_kw_at_30c"] > heat_capacity_kw(30)
    if "one_genset_down_envelope" in lo:
        ogd = lo["one_genset_down_envelope"]
        assert ogd["load_kw"] == sum(envelope_kw(CARDS[g]) for g in lo["guests"])
        assert ogd["reserve_kw"] == RESERVE_ONE_SET < ogd["load_kw"]


# ---------------------------------------------------------------- Scenario B: minute 12


def minute_12_rows():
    for lo in B["loadouts"]:
        for set_name, row in lo["minute_12"].items():
            yield pytest.param(lo, set_name, row, id=f"{lo['id']}-{set_name}")


@pytest.mark.parametrize(("lo", "set_name", "row"), list(minute_12_rows()))
def test_minute_12_draws_are_the_card_modes_of_the_draw_set(lo, set_name, row):
    modes = B["draw_set_modes"][set_name]
    assert sorted(row["draws"]) == sorted(lo["guests"])
    for g, kw in row["draws"].items():
        assert kw == mode(g, modes[g])["power_kw"], g


@pytest.mark.parametrize(("lo", "set_name", "row"), list(minute_12_rows()))
def test_minute_12_load_is_the_sum_of_draws_and_short_is_against_the_ceiling(lo, set_name, row):
    load = sum(row["draws"].values())
    assert row["load_kw"] == load
    assert row["short_kw"] == max(0, load - B["ceiling"]["kw"])
    if "spare_kw" in row:
        assert row["spare_kw"] == B["ceiling"]["kw"] - load


@pytest.mark.parametrize(("lo", "set_name", "row"), list(minute_12_rows()))
def test_minute_12_ladder_steps_match_card_modes_and_close_the_shortfall(lo, set_name, row):
    modes = B["draw_set_modes"][set_name]
    for file_id in ("survey", "sar"):
        steps = row["ladder"][file_id]
        if row["short_kw"] == 0:
            assert steps == []
            continue
        cumulative = 0
        current = dict(modes)
        for step in steps:
            assert current[step["guest"]] == step["from_mode"]
            assert mode(step["guest"], step["from_mode"]).get("interruptible", True)
            assert step["frees_kw"] == step_frees_kw(step)
            cumulative += step["frees_kw"]
            assert step["cumulative_kw"] == cumulative
            assert step["load_after_kw"] == row["load_kw"] - cumulative
            if "capability_lost_pct" in step:
                lost = mode(step["guest"], step["from_mode"])["capability_retained"] - mode(step["guest"], step["to_mode"])["capability_retained"]
                assert step["capability_lost_pct"] == pytest.approx(100 * lost)
            current[step["guest"]] = step["to_mode"]
        assert cumulative >= row["short_kw"]
        assert cumulative - steps[-1]["frees_kw"] < row["short_kw"]
        # The winner of minute 8 keeps running: G4 is never shed and, under sar, never throttled.
        assert all(s["to_mode"] != "off" for s in steps)
        if file_id == "sar":
            assert all(s["guest"] != "G4" for s in steps)


@pytest.mark.parametrize(("lo", "set_name", "row"), list(minute_12_rows()))
def test_minute_12_ladder_is_the_price_list_walked_in_order(lo, set_name, row):
    for file_id in ("survey", "sar"):
        price = B["price_lists"][file_id]
        current = dict((g, B["draw_set_modes"][set_name][g]) for g in lo["guests"])
        taken, freed = [], 0
        for step in price["throttles"] + price["sheds"]:
            if freed >= row["short_kw"]:
                break
            if current.get(step["guest"]) == step["from_mode"]:
                taken.append((step["guest"], step["from_mode"], step["to_mode"]))
                freed += step_frees_kw(step)
                current[step["guest"]] = step["to_mode"]
        assert taken == [(s["guest"], s["from_mode"], s["to_mode"]) for s in row["ladder"][file_id]]


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_price_lists_recompute_from_weights_and_modes_and_are_in_ladder_order(file_id):
    price = B["price_lists"][file_id]
    for group, steps in (("throttles", price["throttles"]), ("sheds", price["sheds"])):
        for step in steps:
            assert (step["to_mode"] == "off") == (group == "sheds")
            assert mode(step["guest"], step["from_mode"]).get("interruptible", True)
            frees = step_frees_kw(step)
            if "frees_kw" in step:
                assert step["frees_kw"] == frees
            # The doc rounds cost per kW to two significant figures.
            assert step["cost_per_kw"] == pytest.approx(step_value_lost(file_id, step) / frees, rel=0.02, abs=1e-9)
            assert step.get("mission_critical", False) == is_critical(file_id, step["guest"])
    keys = [step_order_key(file_id, s) for s in price["throttles"] + price["sheds"]]
    assert keys == sorted(keys)


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_price_lists_hold_every_step_down_from_the_minute_12_modes(file_id):
    # Every interruptible one-mode step below each guest's minute-12 mode, in either draw set.
    expected = set()
    for set_modes in B["draw_set_modes"].values():
        for gid, start in set_modes.items():
            names = [m["name"] for m in sorted(CARDS[gid]["modes"], key=lambda m: -m["power_kw"])]
            for current in names[names.index(start):]:
                step = first_step_down(gid, current)
                if step:
                    expected.add((step["guest"], step["from_mode"], step["to_mode"]))
    price = B["price_lists"][file_id]
    listed = [(s["guest"], s["from_mode"], s["to_mode"]) for s in price["throttles"] + price["sheds"]]
    assert len(listed) == len(set(listed))
    assert set(listed) == expected


def test_g3_charging_is_never_on_a_ladder():
    assert mode("G3", "charging")["interruptible"] is False
    steps = [s for pl in B["price_lists"].values() for grp in pl.values() for s in grp]
    steps += [s for lo in B["loadouts"] for row in lo["minute_12"].values() for lad in row["ladder"].values() for s in lad]
    assert not any(s["guest"] == "G3" and s["from_mode"] == "charging" for s in steps)


def test_minute_12_robustness_notes():
    r = B["robustness"]
    p = r["probe_paused"]
    assert p["load_drop_kw"] == mode(p["guest"], p["from_mode"])["power_kw"] - mode(p["guest"], p["to_mode"])["power_kw"]
    n = r["g4_not_landed_survey"]
    assert n["draws"]["G4"] == mode("G4", n["g4_mode"])["power_kw"]
    assert n["load_kw"] == sum(n["draws"].values())
    assert n["sheds"] == (n["load_kw"] > B["ceiling"]["kw"])


# ---------------------------------------------------------------- Scenario B: minute 12 as decided (DEC-40)


AS_DECIDED = B["minute_12_as_decided"]


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_minute_12_as_decided_holds_with_no_step(file_id):
    row = AS_DECIDED["by_file"][file_id]
    lo = next(lo for lo in B["loadouts"] if lo["id"] == AS_DECIDED["loadout"])
    assert sorted(row["modes"]) == sorted(lo["guests"])
    load = sum(mode(g, m)["power_kw"] for g, m in row["modes"].items())
    assert row["load_kw"] == load
    assert row["spare_kw"] == B["ceiling"]["kw"] - load > 0
    assert row["steps_taken"] == 0
    # G4's 35 kW fast charge is reserved under sar only (minute 8); under survey it is airborne at 2 kW.
    by_8 = B["minute_8"]["by_file"][file_id]
    assert (row["reserved"] == ["G4"]) == by_8["charge_reserved"]
    assert row["modes"]["G4"] == ("fast_charge" if by_8["charge_reserved"] else "standby")
    assert row["modes"]["G3"] == by_8["g3"]["mode"]


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_minute_12_armed_first_step_is_the_price_list_walked_from_the_modes(file_id):
    row = AS_DECIDED["by_file"][file_id]
    price = B["price_lists"][file_id]
    first = next(s for s in price["throttles"] + price["sheds"] if row["modes"].get(s["guest"]) == s["from_mode"])
    armed = row["armed_first"]
    assert (armed["guest"], armed["from_mode"], armed["to_mode"]) == (first["guest"], first["from_mode"], first["to_mode"])
    assert armed["cost_per_kw"] == first["cost_per_kw"]
    assert armed["cost_per_kw"] == pytest.approx(step_value_lost(file_id, armed) / step_frees_kw(armed), rel=0.02)
    assert armed["frees_kw"] == step_frees_kw(armed)
    lost = mode(armed["guest"], armed["from_mode"])["capability_retained"] - mode(armed["guest"], armed["to_mode"])["capability_retained"]
    assert armed["capability_lost_pct"] == pytest.approx(100 * lost)


def test_minute_12_armed_first_step_is_g5_under_both_files_at_different_prices():
    survey, sar = (AS_DECIDED["by_file"][f]["armed_first"] for f in ("survey", "sar"))
    assert survey["guest"] == sar["guest"] == "G5"
    assert (survey["cost_per_kw"], sar["cost_per_kw"]) == (0.0038, 0.0189)
    # Under survey G4 is in standby, the lowest mode that keeps capability, so it has nothing to throttle.
    assert first_step_down("G4", "standby")["to_mode"] == "off"


# ---------------------------------------------------------------- Scenario B: minute 8


def test_minute_8_hard_limit_timing():
    # Doc: "same outcome for all three load-outs", so minute 8 has no per-load-out rows.
    assert B["minute_8"]["same_for_all_loadouts"] is True
    assert not any("minute_8" in lo for lo in B["loadouts"])
    t = B["minute_8"]["timing"]
    r3 = A["rules"]["r3"]
    assert t["drain_pct_per_min"] == r3["drain_pct_min"]
    assert t["approach_min"] == r3["approach_min"]
    assert t["confirm_min"] == A["crew"]["confirm_s"][14][1] / 60
    assert t["clear_deck_min"] == A["ship_state"]["deck"]["clear_min"][14][1]
    crossed = t["decision_at_min"] - (t["threshold_pct"] - t["battery_pct_at_report"]) / t["drain_pct_per_min"]
    assert t["crossed_threshold_at_min"] == pytest.approx(crossed, abs=0.05)
    assert t["deadline_min"] == pytest.approx(t["crossed_threshold_at_min"] + t["land_within_min"])
    assert t["remaining_min"] == pytest.approx(t["deadline_min"] - t["decision_at_min"])
    assert t["after_approach_min"] == pytest.approx(t["remaining_min"] - t["approach_min"])
    margin_min = t["after_approach_min"] - t["confirm_min"] - t["clear_deck_min"]
    assert t["margin_s"] == pytest.approx(margin_min * 60)
    alt = t["if_counted_from_report"]
    assert alt["deadline_min"] == t["decision_at_min"] + t["land_within_min"]
    alt_margin = alt["deadline_min"] - t["decision_at_min"] - t["approach_min"] - t["confirm_min"] - t["clear_deck_min"]
    assert alt["margin_min"] == pytest.approx(alt_margin)
    # Waiting for the end of the leg overshoots the deadline.
    assert t["leg_ends_at_min"] > t["deadline_min"]
    assert t["wait_for_leg_end"] == "infeasible"
    assert t["ditching_offered"] is False


@pytest.mark.parametrize("file_id", ["survey", "sar"])
def test_minute_8_g4_proceeds_under_its_card_hard_limit(file_id):
    f = B["minute_8"]["by_file"][file_id]
    assert f["proceeds"] == "G4"
    card_limit = CARDS["G4"]["hard_limits"][0]
    assert f["hard_limit"] == {"guest": "G4", "when": card_limit["when"], "then": card_limit["then"]}
    lo, hi = f["survey_minutes_lost"]
    assert lo <= hi
    # sar reserves the drone's 35 kW charge ahead of everything; survey does not.
    assert f["charge_reserved"] == (file_id == "sar")
    if f["charge_reserved"]:
        assert f["reserved_kw"] == mode("G4", "fast_charge")["power_kw"]
    assert f["open_ended"] == (file_id == "sar")


def test_minute_8_survey_minutes_lost_add_up():
    s = B["minute_8"]["by_file"]["survey"]
    c = s["components"]
    assert c["settle_min"] == A["ship_state"]["noise"]["to_quiet_min"]
    assert s["survey_minutes_lost"] == [c["flown_min"] + c["paused_min"] + x for x in c["settle_min"]]
    assert c["flown_min"] == B["minute_8"]["timing"]["decision_at_min"]
    leg = B["minute_8"]["timing"]["leg_ends_at_min"]
    assert s["leg_ends_at_min"] == [leg + x for x in s["survey_minutes_lost"]]
    assert s["g3_holds_kw"] == mode("G3", "standby")["power_kw"]
    # sar's lower bound is the same 25 to 27 minutes.
    assert B["minute_8"]["by_file"]["sar"]["survey_minutes_lost"] == s["survey_minutes_lost"]


def test_minute_8_g3_states_and_the_ramp_after_g4():
    survey = B["minute_8"]["by_file"]["survey"]["g3"]
    sar = B["minute_8"]["by_file"]["sar"]["g3"]
    assert (survey["leg"], survey["holds"]) == ("paused", "depth")
    assert (sar["leg"], sar["holds"]) == ("aborted", "at_sea")
    assert survey["mode"] == sar["mode"] == "standby"
    assert mode("G3", "standby")["power_kw"] == B["minute_8"]["by_file"]["survey"]["g3_holds_kw"]
    # Flight deck and ramp are mutually exclusive (A.3): G4 recovers only with the ramp not in use, and G3
    # comes back over the ramp, so G3's recovery waits for G4's landing.
    g4_recovery = next(c for c in CARDS["G4"]["conditions"] if c["activity"] == "launch_recovery")
    assert g4_recovery["requires"]["ramp"] == "not_in_use"
    assert "stern_ramp" in CARDS["G3"]["relations"]["requires"]
    assert sar["recovery"] == {"via": "stern_ramp", "after": "G4 landed"}
