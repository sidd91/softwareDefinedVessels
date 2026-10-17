"""The ArgOS ledger: capacity, demand and free per resource class, and the shed ladder.

Pure functions over the loaded inputs (src/sdv/loader.py). Two views of the same model:
- admission (D1): every guest at its envelope draw, judged at the mission envelope: both gensets, the
  envelope reserve, cooling at the envelope's judged seawater temperature (brief A.10, WORKLOG DEC-35);
- operations (D4): every guest at its current mode, or a larger reserved or measured draw
  (config/signals.yaml ledger_rules), under the current plant state.
Every number comes from config/assumptions.yaml or a card.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SLOT_MULTIPLIER = {"bay1": "bay", "bay1_half": "bay", "bay2": "bay", "flight_deck": "flight_deck",
                   "hangar_roof": "hangar_roof", "mast_free": "mast"}


@dataclass(frozen=True)
class Line:
    cls: str
    unit: str
    capacity: float
    demand: float
    contributors: dict = field(default_factory=dict)
    degraded_by: tuple = ()

    @property
    def free(self) -> float:
        return self.capacity - self.demand

    @property
    def over(self) -> bool:
        return self.demand > self.capacity + 1e-9

    @property
    def margin(self) -> float:
        """Free capacity as a share of capacity; the smallest margin is the tightest line."""
        return self.free / self.capacity if self.capacity else float("-inf")


# ------------------------------------------------------------------------------------------- per guest

def mode_of(card: dict, name: str) -> dict:
    return next(m for m in card["modes"] if m["name"] == name)


def envelope_kw(A: dict, card: dict) -> float:
    """Sustained worst-case draw: a peak counts when it lasts longer than the peak window (A.1)."""
    p = card["consumes"]["power_kw"]
    peak = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
    return max(p["nominal"], peak)


def envelope_mode(A: dict, card: dict) -> str:
    draw = envelope_kw(A, card)
    return next(m["name"] for m in card["modes"] if abs(m["power_kw"] - draw) < 1e-9)


def slot_of(part: dict, gid: str, placement: dict | None) -> str:
    """Where a part sits; an unplaced part counts at its preferred position."""
    slot = (placement or {}).get(f"{gid}.{part['name']}")
    return slot or part["preferred"][0]


# ------------------------------------------------------------------------------------------- plant

def heat_capacity_kw(A: dict, seawater_c: float, degraded: bool = False) -> float:
    """Chilled-water capacity: linear between the two points of A.2, flat below the cold point."""
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    t = max(seawater_c, t0)
    cap = c0 + (c1 - c0) * (t - t0) / (t1 - t0)
    return cap * (A["heat"]["degraded_factor"] if degraded else 1.0)


def guest_reserve_kw(A: dict, gensets_online: int, speed_band: str | None = None) -> float:
    """Guest power reserve: one genset gives the one-down figure; two give the band's figure (A.1, A.9)."""
    if gensets_online < 2:
        return A["power"]["guest_reserve_kw"]["one_genset_down"]
    if speed_band is None:
        return A["power"]["guest_reserve_kw"]["cruise"]
    return A["power"]["guest_reserve_kw_by_speed"][speed_band]


def limit_kw(A: dict, power: Line, heat: Line) -> float:
    """The shed limit: the lower of power reserve and cooling capacity, less the headroom kept free."""
    return min(power.capacity, heat.capacity) - A["power"]["shed_headroom_kw"]


# ------------------------------------------------------------------------------------------- admission view

def admission_lines(A: dict, cards: dict, guests: list[str], placement: dict | None = None) -> dict[str, Line]:
    """Every ledger line for a set of guests at their envelope draws, judged at the mission envelope."""
    draws = {g: envelope_kw(A, cards[g]) for g in guests}
    parts = [(g, p) for g in guests for p in cards[g]["placement"]["parts"]]
    mult = A["mass"]["multiplier"]
    lines = {
        "mass": Line("mass", "t", A["mass"]["margin_t"], sum(p["mass_t"] for _, p in parts),
                     {g: sum(p["mass_t"] for gg, p in parts if gg == g) for g in guests}),
        "stability": Line("stability", "t_eq", A["mass"]["stability_budget_t_eq"],
                          sum(p["mass_t"] * mult[SLOT_MULTIPLIER[slot_of(p, g, placement)]] for g, p in parts)),
        "power": Line("power", "kW", A["power"]["envelope_reserve_kw"], sum(draws.values()), draws),
        "heat": Line("heat", "kW", heat_capacity_kw(A, A["envelope"]["judge_cooling_at_c"]),
                     sum(draws[g] for g in guests if cards[g]["cooling"] == "chilled_water"),
                     {g: draws[g] for g in guests if cards[g]["cooling"] == "chilled_water"}),
    }
    for side, cap in A["power"]["mission_line_kw"].items():
        on = {}
        for g in guests:
            slot = slot_of(cards[g]["placement"]["parts"][0], g, placement)
            position = "bay1" if slot == "bay1_half" else slot
            if A["positions"].get(position, {}).get("power_line") == side:
                on[g] = draws[g]
        lines[f"line_{side}"] = Line(f"line_{side}", "kW", cap, sum(on.values()), on)
    mast = A["positions"]["mast_free"]
    on_mast = [(g, p) for g, p in parts if slot_of(p, g, placement) == "mast_free"]
    for g, p in on_mast:
        lines["mast_mass"] = Line("mast_mass", "kg", mast["max_kg"], p["mass_t"] * 1000, {g: p["mass_t"] * 1000})
        if "area_m2" in p:
            lines["mast_area"] = Line("mast_area", "m2", mast["area_m2"], p["area_m2"], {g: p["area_m2"]})
        if len(cards[g]["placement"]["parts"]) == 1:  # the whole guest sits on the mast, so its draw is air-cooled there
            lines["mast_air_cooling"] = Line("mast_air_cooling", "kW", A["heat"]["air_cooled_max_kw"], draws[g], {g: draws[g]})
    for g, p in parts:
        if p["name"] == "drone" and slot_of(p, g, placement) == "flight_deck":
            fd = A["positions"]["flight_deck"]
            lines["flight_deck_drone"] = Line("flight_deck_drone", "kg", fd["hangar_max_kg"], p["mass_t"] * 1000, {g: p["mass_t"] * 1000})
    return lines


# ------------------------------------------------------------------------------------------- operations view

def committed_kw(cards: dict, gid: str, mode: str, reserved_kw: float = 0.0, kw_actual: float | None = None) -> float:
    """config/signals.yaml ledger_rules.committed: the largest of the mode's kW, a reservation and a fresh reading."""
    return max(mode_of(cards[gid], mode)["power_kw"], reserved_kw, kw_actual if kw_actual is not None else 0.0)


def operating_lines(A: dict, cards: dict, modes: dict[str, str], *, gensets_online: int, seawater_c: float,
                    cooling_degraded: bool = False, speed_band: str | None = None,
                    reservations: dict[str, float] | None = None, kw_actual: dict[str, float] | None = None) -> dict[str, Line]:
    """Power and heat lines for the guests in their current modes under the current plant state."""
    reservations = reservations or {}
    kw_actual = kw_actual or {}
    draws = {g: committed_kw(cards, g, m, reservations.get(g, 0.0), kw_actual.get(g)) for g, m in modes.items()}
    chilled = {g: d for g, d in draws.items() if cards[g]["cooling"] == "chilled_water"}
    power = Line("power", "kW", guest_reserve_kw(A, gensets_online, speed_band), sum(draws.values()), draws,
                 ("genset trip",) if gensets_online < 2 else ())
    heat = Line("heat", "kW", heat_capacity_kw(A, seawater_c, cooling_degraded), sum(chilled.values()), chilled,
                ("chilled-water pump",) if cooling_degraded else ())
    return {"power": power, "heat": heat}


# ------------------------------------------------------------------------------------------- shed ladder

@dataclass(frozen=True)
class Step:
    guest: str
    from_mode: str
    to_mode: str
    frees_kw: float
    capability_lost: float
    value_lost: float
    price: float
    mission_critical: bool
    shed: bool
    rank: tuple
    tier: str = "mission_support"

    @property
    def order_key(self) -> tuple:
        return (self.shed, TIER_RANK[self.tier], self.rank, self.price, self.guest)


# Graceful degradation by criticality tier (DEC-59): discretionary first, mission support, mission-critical last;
# vessel-critical (a card's safety_critical, or the profile's tiers.vessel_critical) is never shed.
TIERS = ("vessel_critical", "mission_critical", "mission_support", "discretionary")
TIER_RANK = {"discretionary": 0, "mission_support": 1, "mission_critical": 2}


def tier_of(cards: dict, gid: str, mission: dict) -> str:
    t = mission.get("tiers") or {}
    if cards[gid].get("criticality", {}).get("safety_critical") or gid in t.get("vessel_critical", []):
        return "vessel_critical"
    if gid in mission["mission_critical"]:
        return "mission_critical"
    return "discretionary" if gid in t.get("discretionary", []) else "mission_support"


def _shed_rank(mission: dict, capability: str) -> tuple:
    """F3 precedence: a positive rank before every unlisted capability (1 first), a negative one after (-1 last)."""
    r = (mission.get("shed_order") or {}).get(capability)
    if r is None:
        return (1, 0)
    return (0, r) if r > 0 else (2, r)


def next_step(cards: dict, gid: str, mode: str, mission: dict) -> Step | None:
    """One guest's next step down its mode ladder; None if the mode cannot be interrupted, is off, or the guest is vessel-critical."""
    card = cards[gid]
    tier = tier_of(cards, gid, mission)
    if tier == "vessel_critical":
        return None
    ordered = sorted(card["modes"], key=lambda m: -m["power_kw"])
    names = [m["name"] for m in ordered]
    i = names.index(mode)
    if i + 1 == len(ordered) or ordered[i].get("interruptible", True) is False:
        return None
    a, b = ordered[i], ordered[i + 1]
    frees = a["power_kw"] - b["power_kw"]
    if frees <= 0:
        return None
    lost = a["capability_retained"] - b["capability_retained"]
    cap = card["capability"]["name"]
    value = mission["weights"].get(cap, 0.0) * lost
    return Step(gid, a["name"], b["name"], frees, lost, value, value / frees, tier == "mission_critical",
                b["capability_retained"] <= 0, _shed_rank(mission, cap), tier)


def ladder(cards: dict, modes: dict[str, str], mission: dict) -> list[Step]:
    """The full precomputed ladder from the current modes: each round takes the cheapest next step of any guest."""
    current = dict(modes)
    steps = []
    while True:
        options = [s for s in (next_step(cards, g, m, mission) for g, m in current.items()) if s]
        if not options:
            return steps
        best = min(options, key=lambda s: s.order_key)
        steps.append(best)
        current[best.guest] = best.to_mode


def steps_to_fit(steps: list[Step], load_kw: float, limit: float, throttles_only: bool = False) -> list[Step] | None:
    """The shortest ladder prefix that brings load within limit; None if it cannot (DEC-35's throttle-only prefix when asked)."""
    taken, load = [], load_kw
    for s in steps:
        if load <= limit + 1e-9:
            return taken
        if throttles_only and s.shed:
            break
        taken.append(s)
        load -= s.frees_kw
    return taken if load <= limit + 1e-9 else None
