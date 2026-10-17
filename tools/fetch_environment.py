"""Fetch the environment along a mission plan from Open-Meteo (Marine + Archive) and cache it in the repo.

    uv run python tools/fetch_environment.py sicily_cable_survey

One-time, network-only step; everything else reads the cache offline. Open-Meteo is the public source the
brief itself names; data CC BY 4.0 (attribution in the README). No third-party client: stdlib urllib.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MARINE = "https://marine-api.open-meteo.com/v1/marine"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def get(url: str, params: dict) -> dict:
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.load(r)


def main(plan_id: str) -> int:
    plan = yaml.safe_load((ROOT / "config/plans" / f"{plan_id}.yaml").read_text())
    start = datetime.fromisoformat(plan["depart_utc"]).replace(tzinfo=timezone.utc)
    end = start + timedelta(days=plan["days"])
    dates = {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d"), "timezone": "UTC"}
    out = {"plan": plan_id, "fetched_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
           "source": "Open-Meteo Marine API (sea_surface_temperature, wave_height, wave_period) and Archive API (wind_speed_10m, wind_gusts_10m), hourly",
           "licence": "CC BY 4.0", "attribution": "Weather data by Open-Meteo.com", "urls": [], "waypoints": []}
    for wp in plan["waypoints"]:
        loc = {"latitude": wp["lat"], "longitude": wp["lon"]}
        m = get(MARINE, {**loc, **dates, "hourly": "sea_surface_temperature,wave_height,wave_period"})
        a = get(ARCHIVE, {**loc, **dates, "hourly": "wind_speed_10m,wind_gusts_10m", "wind_speed_unit": "kn"})
        out["urls"] += [MARINE, ARCHIVE]
        assert m["hourly"]["time"] == a["hourly"]["time"], "marine and archive hours differ"
        out["waypoints"].append({
            "id": wp["id"], "lat": wp["lat"], "lon": wp["lon"], "grid_lat": m["latitude"], "grid_lon": m["longitude"],
            "hourly": {"time": m["hourly"]["time"], "seawater_c": m["hourly"]["sea_surface_temperature"],
                       "wave_m": m["hourly"]["wave_height"], "wave_s": m["hourly"]["wave_period"],
                       "wind_kn": a["hourly"]["wind_speed_10m"], "gust_kn": a["hourly"]["wind_gusts_10m"]}})
        print(f"{wp['id']}: {len(m['hourly']['time'])} hours")
    out["urls"] = sorted(set(out["urls"]))
    path = ROOT / "config/environment" / f"{plan_id}.json"
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    print(f"wrote {path} ({path.stat().st_size // 1024} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "sicily_cable_survey"))
