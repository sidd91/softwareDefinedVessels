"""Guest runtimes: each admitted guest sits in one mode of its card and draws what that mode says.

The plant reports *actual* consumption; the governor compares it with the declaration. An
`over_consumption` factor models the brief's guest that exceeds its card by 10-20 %.

The rescue drone carries a battery: it drains while airborne at the rate in `assumptions.rules.r3`
and charges on the hangar at the rates in `assumptions.sim`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data import mode


@dataclass
class GuestRuntime:
    card: dict
    mode: str
    placement: dict[str, str]  # part name -> position id
    over_consumption: float = 1.0
    airborne: bool = False
    battery_pct: float | None = None
    flags: dict = field(default_factory=dict)

    @property
    def gid(self) -> str:
        return self.card["id"]

    @property
    def declared_kw(self) -> float:
        return float(mode(self.card, self.mode)["power_kw"])

    @property
    def actual_kw(self) -> float:
        return round(self.declared_kw * self.over_consumption, 3)

    @property
    def capability_retained(self) -> float:
        return float(mode(self.card, self.mode)["capability_retained"])

    @property
    def chilled_water(self) -> bool:
        return self.card.get("cooling") == "chilled_water" and self.mode != "off"

    def data_mbps(self, key: str) -> float:
        """Declared nominal data use for a link class while not off (e.g. `data_satcom_mbps`)."""
        if self.mode == "off":
            return 0.0
        q = self.card["consumes"].get(key)
        return float(q.get("nominal", q.get("min", 0))) if q else 0.0

    def compute_cores(self) -> float:
        if self.mode == "off":
            return 0.0
        q = self.card["consumes"].get("compute_cores")
        return float(q["nominal"]) if q else 0.0

    def set_mode(self, name: str) -> None:
        mode(self.card, name)  # validates
        self.mode = name

    def tick_battery(self, dt_s: float, drain_pct_min: float, charge_pct_min: dict[str, float]) -> None:
        if self.battery_pct is None:
            return
        if self.airborne:
            self.battery_pct -= drain_pct_min * dt_s / 60
        else:
            self.battery_pct += charge_pct_min.get(self.mode, 0.0) * dt_s / 60
        self.battery_pct = max(0.0, min(100.0, self.battery_pct))

    def snapshot(self) -> dict:
        d = {
            "mode": self.mode,
            "declared_kw": self.declared_kw,
            "actual_kw": self.actual_kw,
            "capability_retained": self.capability_retained,
            "placement": self.placement,
        }
        if self.battery_pct is not None:
            d["battery_pct"] = round(self.battery_pct, 2)
            d["airborne"] = self.airborne
        if self.over_consumption != 1.0:
            d["over_consumption"] = self.over_consumption
        d.update(self.flags)
        return d


def default_placement(card: dict) -> dict[str, str]:
    """Each part at its first preferred position. D2 will replace this; the plant only needs *a* placement."""
    return {p["name"]: p["preferred"][0] for p in card["placement"]["parts"]}
