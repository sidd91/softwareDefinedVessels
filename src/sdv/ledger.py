"""Capacity and demand per resource class under the current conditions (the eight gauges).

Every number comes from `config/assumptions.yaml` or a card. This module computes *lines*; it decides
nothing. Each line is `{class, label, unit, capacity, committed, free, contributors}` so a decision can
quote it verbatim: "cooling loop at 30 °C has 12 kW free, guest needs 20 kW".

Classes (brief, eight): power, heat, deck positions, mast positions, mass/stability, data links, compute,
response time. Power is also broken into the two mission lines, because a line can saturate while the
total does not (A.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Line:
    cls: str
    label: str
    unit: str
    capacity: float
    committed: float = 0.0
    contributors: dict[str, float] = field(default_factory=dict)

    @property
    def free(self) -> float:
        return round(self.capacity - self.committed, 3)

    def add(self, who: str, amount: float) -> None:
        if amount:
            self.committed = round(self.committed + amount, 3)
            self.contributors[who] = round(self.contributors.get(who, 0.0) + amount, 3)

    def as_dict(self) -> dict:
        return {
            "class": self.cls,
            "label": self.label,
            "unit": self.unit,
            "capacity": round(self.capacity, 3),
            "committed": self.committed,
            "free": self.free,
            "contributors": self.contributors,
        }


def cooling_capacity_kw(a: dict, seawater_c: float, degraded: bool) -> float:
    """A.2: ~160 kW at 12 °C falling linearly to ~120 kW at 30 °C; -40 % when degraded. Clamped to the
    brief's domain so a 35 °C stress case does not extrapolate below the curve's intent."""
    (t0, c0), (t1, c1) = sorted(a["heat"]["capacity_kw_at"].items())
    t = min(max(seawater_c, t0), t1)
    cap = c0 + (c1 - c0) * (t - t0) / (t1 - t0)
    return cap * (a["heat"]["degraded_factor"] if degraded else 1.0)


def power_reserve_kw(a: dict, speed_band: str, gensets_online: int) -> float:
    """A.1 / A.9: guest reserve by speed band with both gensets; ~100 kW with one down."""
    if gensets_online < 2:
        return float(a["power"]["guest_reserve_kw"]["one_genset_down"])
    by_speed = a["power"]["guest_reserve_kw_by_speed"]
    band = speed_band if speed_band in by_speed else "cruise"  # alongside/stopped: judge as cruise
    return float(by_speed[band])


def build_lines(a: dict, ship: dict, env: dict, guests: dict) -> dict[str, Line]:
    """`ship` is the FSM snapshot, `env` has seawater_c, `guests` maps id -> GuestRuntime."""
    pos = a["positions"]
    silent = ship["emission"] == "silent"
    degraded = ship["cooling"] == "degraded"

    lines: dict[str, Line] = {}

    def L(key, cls, label, unit, cap):
        lines[key] = Line(cls, label, unit, float(cap))
        return lines[key]

    # 1. electrical power: total guest reserve and the two mission lines
    L("power", "power", "guest power reserve", "kW", power_reserve_kw(a, ship["speed_band"], ship["genset"]))
    for ln, kw in a["power"]["mission_line_kw"].items():
        L(f"power_line_{ln}", "power", f"{ln} mission line", "kW", kw)

    # 2. heat rejection: chilled-water loop at the current seawater temperature
    L("heat", "heat", f"chilled-water loop at {env['seawater_c']:g} °C" + (" (degraded)" if degraded else ""), "kW",
      cooling_capacity_kw(a, env["seawater_c"], degraded))

    # 3. deck positions (in 10-ft halves) and the flight deck / ramp
    bay_halves = sum(p["halves"] for p in pos.values() if isinstance(p, dict) and p.get("kind") == "bay")
    L("bays", "positions", "bay space", "10-ft halves", bay_halves)
    L("flight_deck", "positions", "flight deck hangar", "slot", 1)
    L("stern_ramp", "positions", "stern ramp", "craft", 1)

    # 4. mast positions: three, two taken by the ship's own radar and SATCOM terminal
    occupied = pos.get("mast_occupied", [])
    m = L("mast", "positions", "mast positions", "slot", 1 + len(occupied))  # one free slot + the natives
    for native in occupied:
        m.add(f"ship:{native}", 1)

    # 5. mass and stability
    L("mass", "mass", "mass margin", "t", a["mass"]["margin_t"])
    L("stability", "mass", "stability budget", "t-eq", a["mass"]["stability_budget_t_eq"])

    # 6. data links
    d = a["data"]
    L("satcom", "data", "SATCOM" + (" (silent)" if silent else ""), "Mbit/s", 0 if silent else d["satcom_envelope_mbps"])
    L("los_radio", "data", "line-of-sight radio" + (" (silent)" if silent else ""), "Mbit/s", 0 if silent else d["los_radio_operating_mbps"])
    L("backbone", "data", "backbone", "Mbit/s", d["backbone_mbps"])
    L("acoustic", "data", "acoustic link", "kbit/s", d["acoustic_kbps"]["max"])

    # 7. compute
    c = a["compute"]
    L("compute", "compute", "guest compute", "cores", c["nodes"] * c["cores_per_node"] * c["guest_share"])

    # 8. response time: budgets per decision class; committed = last measured latency (filled by the governor)
    for k, s in a["response_time_s"].items():
        L(f"rt_{k}", "response_time", f"{k} ceiling", "s", s)

    # ---- demand from the guests ---------------------------------------------------------------------
    mult = a["mass"]["multiplier"]
    for gid, g in guests.items():
        kw = g.actual_kw
        lines["power"].add(gid, kw)
        if g.chilled_water:
            lines["heat"].add(gid, kw)
        for part in g.card["placement"]["parts"]:
            p_id = g.placement.get(part["name"])
            p = pos.get(p_id, {})
            if kw and p.get("power_line") and part is g.card["placement"]["parts"][0]:
                lines[f"power_line_{p['power_line']}"].add(gid, kw)
            lines["mass"].add(gid, part["mass_t"])
            lines["stability"].add(gid, part["mass_t"] * mult.get(p.get("zone", "bay"), 1.0))
            kind = p.get("kind")
            if kind == "bay":
                halves = p["halves"] if not p_id.endswith("_half") else 1
                lines["bays"].add(gid, halves)
            elif p_id == "bay1_half":
                lines["bays"].add(gid, 1)
            elif kind == "flight_deck":
                lines["flight_deck"].add(gid, 1)
            elif kind == "mast":
                lines["mast"].add(gid, 1)
        if g.card.get("placement", {}).get("uses_ramp") and g.flags.get("on_ramp"):
            lines["stern_ramp"].add(gid, 1)
        lines["satcom"].add(gid, g.data_mbps("data_satcom_mbps"))
        lines["los_radio"].add(gid, g.data_mbps("data_los_radio_mbps"))
        lines["backbone"].add(gid, g.data_mbps("data_backbone_mbps"))
        lines["acoustic"].add(gid, g.data_mbps("data_acoustic_kbps"))
        lines["compute"].add(gid, g.compute_cores())
    return lines


def gauges(lines: dict[str, Line]) -> dict:
    """The eight headline gauges the screen shows, one per class."""
    pick = {
        "power": "power", "heat": "heat", "deck": "bays", "mast": "mast", "mass": "mass",
        "data": "satcom", "compute": "compute", "response_time": "rt_arbitration",
    }
    return {k: lines[v].as_dict() for k, v in pick.items()}
