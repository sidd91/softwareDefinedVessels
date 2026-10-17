"""The environment along a mission plan, generated from public data instead of typed into a scenario.

A plan (`config/plans/<id>.yaml`) says where the ship is and when; the cache
(`config/environment/<id>.json`, written once by `tools/fetch_environment.py` from Open-Meteo, CC BY 4.0)
holds hourly seawater temperature, wave height and wind at each waypoint. This module turns the two into:

- `at(t_h)`: the conditions at hour `t_h` of the plan, interpolated along the route, each with `source`,
  `age_s` and `confidence` (ARCHITECTURE contract 4). Outside the data, confidence is 0 and the limits
  tighten ("unknown never means safe").
- `summary(...)`: the worst and best of a window: seawater range, the cooling loop's lowest capacity, the
  highest sea state and gust, and how many hours each weather-gated activity is closed.
- `closed_hours(...)`: the windows in which a card's `wind_kn_max` / `sea_state_max` are exceeded.

Sea state comes from wave height on the Douglas scale and wind limits are judged against gusts
(`assumptions.environment`, with their reasons). Rules read from data; nothing physical is hard-coded.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from .data import CONFIG
from .ledger import cooling_capacity_kw

PLANS = CONFIG / "plans"
CACHE = CONFIG / "environment"


def load_plan(plan_id: str) -> dict:
    return yaml.safe_load((PLANS / f"{plan_id}.yaml").read_text())


def load_cache(plan_id: str) -> dict:
    return json.loads((CACHE / f"{plan_id}.json").read_text())


def sea_state(a: dict, wave_m: float | None) -> int | None:
    if wave_m is None:
        return None
    for state, top in enumerate(a["environment"]["sea_state_wave_m"]):
        if wave_m <= top:
            return state
    return len(a["environment"]["sea_state_wave_m"])


@dataclass
class RouteEnvironment:
    a: dict
    plan: dict
    cache: dict

    @classmethod
    def load(cls, a: dict, plan_id: str) -> "RouteEnvironment":
        return cls(a, load_plan(plan_id), load_cache(plan_id))

    @property
    def id(self) -> str:
        return self.plan["id"]

    @property
    def start(self) -> datetime:
        return datetime.fromisoformat(self.plan["depart_utc"]).replace(tzinfo=timezone.utc)

    @property
    def offset_h(self) -> int:
        """The cache starts at 00:00 of the departure day; plan hour 0 is the departure time."""
        first = datetime.fromisoformat(self.cache["waypoints"][0]["hourly"]["time"][0]).replace(tzinfo=timezone.utc)
        return int((self.start - first).total_seconds() // 3600)

    @property
    def hours(self) -> int:
        return len(self.cache["waypoints"][0]["hourly"]["time"]) - self.offset_h

    def period(self) -> str:
        end = self.start + timedelta(hours=self.hours - 1)
        return f"{self.start:%d %b} to {end:%d %b %Y}"

    # -- position along the route -------------------------------------------------------------------
    def _bracket(self, t_h: float) -> tuple[int, int, float]:
        """Indexes of the waypoints before and after `t_h`, and the fraction between them."""
        wps = self.plan["waypoints"]
        if t_h <= wps[0]["eta_h"]:
            return 0, 0, 0.0
        for i in range(len(wps) - 1):
            a, b = wps[i], wps[i + 1]
            if a["eta_h"] <= t_h <= b["eta_h"]:
                span = b["eta_h"] - a["eta_h"]
                return i, i + 1, (t_h - a["eta_h"]) / span if span else 0.0
        return len(wps) - 1, len(wps) - 1, 0.0

    def _series(self, key: str, i: int, j: int, f: float) -> list[float | None]:
        sa = self.cache["waypoints"][i]["hourly"][key]
        sb = self.cache["waypoints"][j]["hourly"][key]
        return [None if (x is None or y is None) else (1 - f) * x + f * y for x, y in zip(sa, sb)]

    def at(self, t_h: float) -> dict:
        """Conditions at hour `t_h` of the plan (fractional hours read the last full hour)."""
        i, j, f = self._bracket(t_h)
        idx = int(t_h)
        inside = 0 <= idx < self.hours
        k = min(max(idx, 0), self.hours - 1) + self.offset_h
        vals = {key: self._series(key, i, j, f)[k] for key in ("seawater_c", "wave_m", "wind_kn", "gust_kn")}
        age_s = (t_h - idx) * 3600 if inside else float("inf")
        stale = age_s > self.a["environment"]["stale_after_h"] * 3600
        out = {
            "t_h": t_h, "time_utc": self.cache["waypoints"][0]["hourly"]["time"][k],
            "seawater_c": None if vals["seawater_c"] is None else round(vals["seawater_c"], 2),
            "wave_m": None if vals["wave_m"] is None else round(vals["wave_m"], 2),
            "sea_state": sea_state(self.a, vals["wave_m"]),
            "wind_kn": None if vals["wind_kn"] is None else round(vals["wind_kn"], 1),
            "gust_kn": None if vals["gust_kn"] is None else round(vals["gust_kn"], 1),
            "source": "open-meteo (cached)", "age_s": age_s if inside else None,
            "confidence": 0.0 if (stale or not inside) else 1.0,
            "waypoint": self.plan["waypoints"][i]["id"] if f < 0.5 else self.plan["waypoints"][j]["id"],
        }
        if out["confidence"] == 0.0:  # unknown never means safe: the envelope's worst case applies
            env = self.a["envelope"]
            out.update({"seawater_c": float(env["seawater_c"][1]), "sea_state": env["sea_state_max"],
                        "wind_kn": float(env["wind_kn_max"]), "gust_kn": float(env["wind_kn_max"]), "tightened": True})
        return out

    # -- windows and summaries ----------------------------------------------------------------------
    def closed_hours(self, wind_kn_max: float | None = None, sea_state_max: int | None = None,
                     from_h: float = 0, to_h: float | None = None) -> list[tuple[int, int]]:
        """Hour windows [start, end) in which the limits are exceeded (gusts if the assumptions say so)."""
        to_h = self.hours if to_h is None else min(to_h, self.hours)
        wind_key = "gust_kn" if self.a["environment"]["wind_limits_use_gusts"] else "wind_kn"
        closed, start = [], None
        for h in range(int(from_h), int(to_h)):
            c = self.at(h)
            shut = (wind_kn_max is not None and c[wind_key] is not None and c[wind_key] > wind_kn_max) or \
                   (sea_state_max is not None and c["sea_state"] is not None and c["sea_state"] > sea_state_max)
            if shut and start is None:
                start = h
            if not shut and start is not None:
                closed.append((start, h))
                start = None
        if start is not None:
            closed.append((start, int(to_h)))
        return closed

    def summary(self, from_h: float = 0, to_h: float | None = None, degraded: bool = False) -> dict:
        to_h = self.hours if to_h is None else min(to_h, self.hours)
        rows = [self.at(h) for h in range(int(from_h), int(to_h))]
        sst = [r["seawater_c"] for r in rows if r["seawater_c"] is not None]
        gusts = [r["gust_kn"] for r in rows if r["gust_kn"] is not None]
        winds = [r["wind_kn"] for r in rows if r["wind_kn"] is not None]
        states = [r["sea_state"] for r in rows if r["sea_state"] is not None]
        hi, lo = max(sst), min(sst)
        return {
            "plan": self.id, "name": self.plan["name"], "period": self.period(), "hours": len(rows),
            "seawater_c": [round(lo, 2), round(hi, 2)], "seawater_max_at": rows[[r["seawater_c"] for r in rows].index(hi)]["time_utc"],
            "cooling_kw_min": round(cooling_capacity_kw(self.a, hi, degraded), 1),
            "cooling_kw_max": round(cooling_capacity_kw(self.a, lo, degraded), 1),
            "sea_state_max": max(states), "wind_kn_max": round(max(winds), 1), "gust_kn_max": round(max(gusts), 1),
            "envelope_exceeded": {"seawater": hi > self.a["envelope"]["seawater_c"][1], "sea_state": max(states) > self.a["envelope"]["sea_state_max"],
                                  "wind": max(gusts) > self.a["envelope"]["wind_kn_max"]},
            "source": self.cache["source"], "licence": self.cache["licence"], "fetched_at_utc": self.cache["fetched_at_utc"],
        }

    def activity_windows(self, card: dict, from_h: float = 0, to_h: float | None = None) -> list[dict]:
        """For each weather-gated activity on a card: the hours it is closed on this route."""
        out = []
        for cond in card.get("conditions", []):
            req = cond.get("requires", {})
            if "wind_kn_max" not in req and "sea_state_max" not in req:
                continue
            closed = self.closed_hours(req.get("wind_kn_max"), req.get("sea_state_max"), from_h, to_h)
            out.append({"activity": cond["activity"], "wind_kn_max": req.get("wind_kn_max"), "sea_state_max": req.get("sea_state_max"),
                        "closed_h": sum(e - s for s, e in closed), "windows": closed[:6], "n_windows": len(closed)})
        return out
