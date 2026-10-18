"""Deployment map: the route and its operations area on a small offline map, weather sampled at random points
along it, and the parameters each mission profile is then judged against. A standalone tool, outside the ArgOS
screen, until the team decides to wire it in.

    uv run python tools/deploy_map/deploy.py [--plan sicily_cable_survey] [--seed 0] [--points 400] [--out DIR]

Writes DIR/index.html (one self-contained page, nothing fetched) and DIR/deployment.json.
Data: Siddharth's plan and Open-Meteo cache (feat/ship-state-fsm fbe59a5; weather CC BY 4.0, Open-Meteo.com),
Natural Earth coastlines (public domain). The verdicts come from the real engine (sdv.admission, sdv.ledger).
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sdv import admission as Ad  # noqa: E402
from sdv import ledger as Lg  # noqa: E402
from sdv import loader as Ld  # noqa: E402

DATA = HERE / "data"
CFG = yaml.safe_load((HERE / "config.yaml").read_text())
KM_PER_DEG = 111.32
VARS = ("seawater_c", "wave_m", "wind_kn", "gust_kn")


# ---------------------------------------------------------------------------------------------- inputs
def load(plan_id: str) -> tuple[dict, dict, dict]:
    plan = yaml.safe_load((DATA / f"{plan_id}.yaml").read_text())
    cache = json.loads((DATA / f"{plan_id}.json").read_text())
    coast = json.loads((DATA / "coast_strait_of_sicily.json").read_text())
    return plan, cache, coast


def sea_state(wave_m: float | None) -> int | None:
    """Douglas scale from wave height (Siddharth's thresholds)."""
    if wave_m is None:
        return None
    for state, top in enumerate(CFG["sea_state_wave_m"]):
        if wave_m <= top:
            return state
    return len(CFG["sea_state_wave_m"])


# ---------------------------------------------------------------------------------------------- the route
class Route:
    """Waypoints with planned hours; position by hour (constant speed per leg), weather blended between the two
    waypoints' hourly series, as Siddharth's RouteEnvironment does."""

    def __init__(self, plan: dict, cache: dict):
        self.plan, self.cache = plan, cache
        self.wps = plan["waypoints"]
        self.series = {w["id"]: w["hourly"] for w in cache["waypoints"]}
        self.lat0 = math.radians(sum(w["lat"] for w in self.wps) / len(self.wps))
        times = cache["waypoints"][0]["hourly"]["time"]
        self.t0 = datetime.fromisoformat(times[0])
        self.start = datetime.fromisoformat(plan["depart_utc"])
        self.offset_h = int((self.start - self.t0).total_seconds() // 3600)
        self.hours = len(times) - self.offset_h
        self.end_h = min(self.wps[-1]["eta_h"], self.hours)
        self.legs = [(i, i + 1) for i in range(len(self.wps) - 1)]
        self.leg_km = [self.km(self.wps[i], self.wps[j]) for i, j in self.legs]

    def xy(self, lat: float, lon: float) -> tuple[float, float]:
        return lon * KM_PER_DEG * math.cos(self.lat0), lat * KM_PER_DEG

    def km(self, a: dict, b: dict) -> float:
        (x1, y1), (x2, y2) = self.xy(a["lat"], a["lon"]), self.xy(b["lat"], b["lon"])
        return math.hypot(x2 - x1, y2 - y1)

    def at_hour(self, t_h: float) -> tuple[float, float, int, int, float]:
        for i, j in self.legs:
            a, b = self.wps[i], self.wps[j]
            if a["eta_h"] <= t_h <= b["eta_h"]:
                span = b["eta_h"] - a["eta_h"]
                f = (t_h - a["eta_h"]) / span if span else 0.0
                return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (b["lon"] - a["lon"]), i, j, f
        last = len(self.wps) - 1
        return self.wps[last]["lat"], self.wps[last]["lon"], last, last, 0.0

    def at_km(self, s: float) -> tuple[float, float, int, int, float]:
        for (i, j), length in zip(self.legs, self.leg_km):
            if s <= length or (i, j) == self.legs[-1]:
                f = min(max(s / length, 0.0), 1.0) if length else 0.0
                a, b = self.wps[i], self.wps[j]
                return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (b["lon"] - a["lon"]), i, j, f
            s -= length
        raise ValueError(s)

    def weather(self, t_h: float, i: int, j: int, f: float) -> dict:
        k = min(max(int(t_h), 0), self.hours - 1) + self.offset_h
        out = {}
        for key in VARS:
            a, b = self.series[self.wps[i]["id"]][key][k], self.series[self.wps[j]["id"]][key][k]
            out[key] = None if a is None or b is None else round((1 - f) * a + f * b, 2)
        out["sea_state"] = sea_state(out["wave_m"])
        out["time_utc"] = (self.t0 + timedelta(hours=k)).strftime("%Y-%m-%d %H:%M")
        return out

    def distance_km(self, lat: float, lon: float) -> float:
        px, py = self.xy(lat, lon)
        best = math.inf
        for i, j in self.legs:
            (ax, ay), (bx, by) = self.xy(self.wps[i]["lat"], self.wps[i]["lon"]), self.xy(self.wps[j]["lat"], self.wps[j]["lon"])
            dx, dy = bx - ax, by - ay
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
        return best


def sample(route: Route, n: int, seed: int, corridor_km: float) -> list[dict]:
    """Half the points along the route at the hour the ship is there, half anywhere in the area at any hour."""
    rng = random.Random(seed)
    total = sum(route.leg_km)
    out = []
    for k in range(n):
        if k % 2 == 0:
            t = rng.uniform(0, route.end_h)
            lat, lon, i, j, f = route.at_hour(t)
            kind = "route"
        else:
            lat, lon, i, j, f = route.at_km(rng.uniform(0, total))
            a, b = route.wps[i], route.wps[j]
            (ax, ay), (bx, by) = route.xy(a["lat"], a["lon"]), route.xy(b["lat"], b["lon"])
            length = math.hypot(bx - ax, by - ay) or 1.0
            nx, ny = -(by - ay) / length, (bx - ax) / length          # unit normal to the leg, in km
            off = rng.uniform(-corridor_km, corridor_km)
            lat += off * ny / KM_PER_DEG
            lon += off * nx / (KM_PER_DEG * math.cos(route.lat0))
            t = rng.uniform(0, route.hours)
            kind = "area"
        w = route.weather(t, i, j, f)
        out.append({"kind": kind, "lat": round(lat, 4), "lon": round(lon, 4), "t_h": round(t, 2), **w})
    return out


# ---------------------------------------------------------------------------------------------- parameters
def pct(vals: list[float], p: float) -> float:
    s = sorted(vals)
    if not s:
        return math.nan
    x = (len(s) - 1) * p / 100
    lo, hi = math.floor(x), math.ceil(x)
    return round(s[lo] + (s[hi] - s[lo]) * (x - lo), 2)


def ranges(samples: list[dict]) -> dict:
    out = {}
    for key in VARS + ("sea_state",):
        vals = [s[key] for s in samples if s[key] is not None]
        out[key] = {"p10": pct(vals, 10), "p50": pct(vals, 50), "p90": pct(vals, 90), "max": max(vals), "min": min(vals)}
    out["sea_state_hist"] = {str(k): sum(1 for s in samples if s["sea_state"] == k) for k in sorted({s["sea_state"] for s in samples})}
    return out


def gated(cards: dict) -> list[dict]:
    """Card activities that a weather limit can close: a typed max on wind_kn or sea_state."""
    out = []
    for gid, card in sorted(cards.items()):
        for c in card.get("conditions", []):
            req = c.get("requires", {})
            wind = req.get("wind_kn", {}).get("max") if isinstance(req.get("wind_kn"), dict) else None
            ss = req.get("sea_state", {}).get("max") if isinstance(req.get("sea_state"), dict) else None
            if wind is not None or ss is not None:
                out.append({"guest": gid, "activity": c["activity"], "wind_kn_max": wind, "sea_state_max": ss})
    return out


def is_open(s: dict, act: dict) -> bool:
    wind = s["gust_kn"] if CFG["wind_limits_use_gusts"] else s["wind_kn"]
    if act["wind_kn_max"] is not None and (wind is None or wind > act["wind_kn_max"]):
        return False
    if act["sea_state_max"] is not None and (s["sea_state"] is None or s["sea_state"] > act["sea_state_max"]):
        return False
    return True


def windows(samples: list[dict], acts: list[dict]) -> list[dict]:
    return [{**a, "open_pct": round(100 * sum(is_open(s, a) for s in samples) / len(samples), 1)} for a in acts]


def judge(A: dict, cards: dict, mission: dict, load_out: list[str], seawater_c: float) -> dict:
    """D1 on the load-out with cooling judged at `seawater_c` instead of the envelope's 30 C."""
    a = copy.deepcopy(A)
    a["envelope"]["judge_cooling_at_c"] = seawater_c
    r = Ad.admit(a, cards, load_out[:-1], load_out[-1], mission)
    heat = r.lines["heat"]
    return {"seawater_c": seawater_c, "verdict": r.verdict, "binding": r.binding.cls,
            "binding_demand": round(r.binding.demand, 3), "binding_capacity": round(r.binding.capacity, 3), "unit": r.binding.unit,
            "heat_kw": round(heat.demand, 1), "cooling_kw": round(heat.capacity, 1), "one_genset_down": r.genset.state}


def profiles(A: dict, cards: dict, missions: dict, rng_: dict, wins: list[dict], load_out: list[str]) -> list[dict]:
    out = []
    for mid, m in sorted(missions.items()):
        mc = []
        for g in m["mission_critical"]:
            acts = [w for w in wins if w["guest"] == g]
            mc.append({"guest": g, "activities": [{"activity": w["activity"], "open_pct": w["open_pct"]} for w in acts]})
        out.append({"id": mid, "name": m["name"],
                    "envelope": judge(A, cards, m, load_out, A["envelope"]["judge_cooling_at_c"]),
                    "route_p90": judge(A, cards, m, load_out, rng_["seawater_c"]["p90"]),
                    "route_max": judge(A, cards, m, load_out, rng_["seawater_c"]["max"]),
                    "mission_critical": mc})
    return out


def build(plan_id: str, seed: int, points: int) -> dict:
    plan, cache, coast = load(plan_id)
    route = Route(plan, cache)
    samples = sample(route, points, seed, CFG["corridor_km"])
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    cards = Ld.load_cards(vocab=vocab)
    missions = Ld.load_missions(cards, vocab)
    rng_ = ranges(samples)
    wins = windows(samples, gated(cards))
    hot = rng_["seawater_c"]["max"]
    return {
        "plan": {"id": plan["id"], "name": plan["name"], "depart_utc": plan["depart_utc"], "days": plan["days"],
                 "waypoints": plan["waypoints"], "km": round(sum(route.leg_km), 1),
                 "period": f"{route.start:%d %b} to {(route.start + timedelta(hours=route.end_h)):%d %b %Y}"},
        "sampling": {"seed": seed, "points": points, "corridor_km": CFG["corridor_km"]},
        "ranges": rng_,
        "cooling": {"load_out_heat_kw": round(Lg.admission_lines(A, cards, CFG["load_out"])["heat"].demand, 1),
                    "normal_kw_at_p90": round(Lg.heat_capacity_kw(A, rng_["seawater_c"]["p90"]), 1),
                    "normal_kw_at_max": round(Lg.heat_capacity_kw(A, hot), 1),
                    "degraded_kw_at_max": round(Lg.heat_capacity_kw(A, hot, True), 1),
                    "envelope_kw": round(Lg.heat_capacity_kw(A, A["envelope"]["judge_cooling_at_c"]), 1)},
        "windows": wins,
        "load_out": CFG["load_out"],
        "profiles": profiles(A, cards, missions, rng_, wins, CFG["load_out"]),
        "samples": samples,
        "coast": coast,
        "sources": {"weather": f"{cache['attribution']} ({cache['licence']}), fetched {cache['fetched_at_utc']}",
                    "coast": coast["attribution"] + " (public domain)", "plan": "Siddharth, feat/ship-state-fsm fbe59a5"},
    }


# ---------------------------------------------------------------------------------------------- the page
SS_COLOR = {"low": "#5FB3A8", "mid": "#F0A63A", "high": "#E5484D"}


def _ss_class(ss: int | None) -> str:
    return "high" if ss is None or ss >= 5 else ("mid" if ss == 4 else "low")


def svg_map(d: dict, width: int = 1000) -> str:
    W, S, E, N = d["coast"]["bbox"]
    k = math.cos(math.radians((S + N) / 2))
    scale = width / ((E - W) * k)
    height = round((N - S) * scale)
    X = lambda lon: round((lon - W) * k * scale, 1)
    Y = lambda lat: round((N - lat) * scale, 1)
    km_px = scale / KM_PER_DEG
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Route and operations area">',
             f'<rect width="{width}" height="{height}" fill="#0B1626"/>']
    for g in [x / 2 for x in range(math.ceil(W * 2), math.floor(E * 2) + 1)]:
        parts.append(f'<line x1="{X(g)}" y1="0" x2="{X(g)}" y2="{height}" stroke="#16263D" stroke-width="1"/>'
                     f'<text x="{X(g) + 4}" y="{height - 8}" class="grat">{g:.1f}°E</text>')
    for g in [x / 2 for x in range(math.ceil(S * 2), math.floor(N * 2) + 1)]:
        parts.append(f'<line x1="0" y1="{Y(g)}" x2="{width}" y2="{Y(g)}" stroke="#16263D" stroke-width="1"/>'
                     f'<text x="6" y="{Y(g) - 6}" class="grat">{g:.1f}°N</text>')
    for ring in d["coast"]["rings"]:
        pts = " ".join(f"{X(lon)},{Y(lat)}" for lon, lat in ring)
        parts.append(f'<polygon points="{pts}" fill="#1E2D42" stroke="#33496A" stroke-width="1.2"/>')
    wps = d["plan"]["waypoints"]
    line = " ".join(f"{X(w['lon'])},{Y(w['lat'])}" for w in wps)
    parts.append(f'<polyline points="{line}" fill="none" stroke="#F0A63A" stroke-opacity="0.16" '
                 f'stroke-width="{round(2 * d["sampling"]["corridor_km"] * km_px, 1)}" stroke-linecap="round" stroke-linejoin="round"/>')
    for s in d["samples"]:
        parts.append(f'<circle cx="{X(s["lon"])}" cy="{Y(s["lat"])}" r="{3.2 if s["kind"] == "route" else 2.6}" '
                     f'fill="{SS_COLOR[_ss_class(s["sea_state"])]}" fill-opacity="0.85"><title>{s["time_utc"]} UTC · SS {s["sea_state"]} · '
                     f'gust {s["gust_kn"]} kn · SW {s["seawater_c"]} °C</title></circle>')
    parts.append(f'<polyline points="{line}" fill="none" stroke="#F0A63A" stroke-width="3" stroke-dasharray="10 6"/>')
    seen = set()
    for w in wps:
        key = (w["lat"], w["lon"])
        if key in seen:
            continue
        seen.add(key)
        label = html.escape(w["id"].replace("_return", "").replace("_", " ").upper())
        parts.append(f'<circle cx="{X(w["lon"])}" cy="{Y(w["lat"])}" r="7" fill="#0B1626" stroke="#F0A63A" stroke-width="3"/>'
                     f'<text x="{X(w["lon"]) + 12}" y="{Y(w["lat"]) - 10}" class="wp">{label}</text>')
    scale_km = 20
    parts.append(f'<line x1="{width - 40 - scale_km * km_px:.1f}" y1="{height - 30}" x2="{width - 40}" y2="{height - 30}" stroke="#C9D4E2" stroke-width="3"/>'
                 f'<text x="{width - 40 - scale_km * km_px:.1f}" y="{height - 40}" class="grat">{scale_km} km</text>')
    parts.append("</svg>")
    return "".join(parts)


def _row(label: str, r: dict, unit: str, fmt: str = "{:.1f}") -> str:
    v = lambda x: fmt.format(x)
    return f"<tr><th>{label}</th><td>{v(r['p50'])}</td><td>{v(r['p90'])}</td><td>{v(r['max'])}</td><td class='u'>{unit}</td></tr>"


def _share(pct_open: float) -> str:
    return "ok" if pct_open >= 90 else ("warn" if pct_open >= 70 else "bad")


def _margin(spare: float) -> str:
    return "ok" if spare >= 10 else ("warn" if spare >= 0 else "bad")


def page(d: dict) -> str:
    r = d["ranges"]
    wins = "".join(
        f"<tr><th>{html.escape(w['guest'])} {html.escape(w['activity'].replace('_', ' ').upper())}</th>"
        f"<td class='mono'>{'GUST ≤ ' + str(w['wind_kn_max']) + ' KN' if w['wind_kn_max'] is not None else ''}"
        f"{' · ' if w['wind_kn_max'] is not None and w['sea_state_max'] is not None else ''}"
        f"{'SS ≤ ' + str(w['sea_state_max']) if w['sea_state_max'] is not None else ''}</td>"
        f"<td class='big {_share(w['open_pct'])}'>{w['open_pct']:.0f} %</td></tr>"
        for w in d["windows"])
    cards = []
    for p in d["profiles"]:
        cols = (p["envelope"], p["route_p90"], p["route_max"])
        verdicts = "".join(f"<td><span class='tag {'ok' if j['verdict'] == 'yes' else 'warn' if j['verdict'] in ('yes-if', 'not-now') else 'bad'}'>"
                           f"{j['verdict'].upper()}</span></td>" for j in cols)
        spares = "".join(f"<td class='{_margin(j['cooling_kw'] - j['heat_kw'])}'>{j['cooling_kw'] - j['heat_kw']:+.0f}</td>" for j in cols)
        mc = "".join(
            f"<div class='mc'><b>{html.escape(x['guest'])}</b> " + (" · ".join(
                f"{html.escape(a['activity'].replace('_', ' ').upper())} <span class='{_share(a['open_pct'])}'>{a['open_pct']:.0f} % OPEN</span>"
                for a in x["activities"]) or "<span class='muted'>NOT WEATHER-GATED</span>") + "</div>"
            for x in p["mission_critical"])
        cards.append(f"<div class='card'><h3>{html.escape(p['name'].upper())}</h3><table class='mini'><thead><tr><th></th>"
                     f"<th>30 °C</th><th>P90 {p['route_p90']['seawater_c']:.1f}</th><th>MAX {p['route_max']['seawater_c']:.1f}</th></tr></thead><tbody>"
                     f"<tr><th>D1</th>{verdicts}</tr><tr><th>COOLING SPARE kW</th>{spares}</tr></tbody></table>"
                     f"<div class='k' style='margin-top:6px'>MISSION CRITICAL</div>{mc}</div>")
    c = d["cooling"]
    hist = " · ".join(f"SS {k}: {v}" for k, v in d["ranges"]["sea_state_hist"].items())
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ArgOS · Deployment map</title>
<style>
:root {{ --navy:#0E1A2B; --panel:#13223A; --line:#24406A; --ink:#C9D4E2; --head:#F3F6FA; --mut:#8FA1B8; --amber:#F0A63A; --ok:#5FB3A8; --bad:#E5484D; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--navy); color:var(--ink); font-family:'Titillium Web','IBM Plex Sans',system-ui,sans-serif; }}
header {{ display:flex; justify-content:space-between; align-items:baseline; padding:14px 24px; background:#0A1422; border-bottom:1px solid var(--line); }}
header h1 {{ margin:0; font-size:22px; letter-spacing:2px; color:var(--head); }} header span {{ color:var(--mut); font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:13px; }}
main {{ display:grid; grid-template-columns:minmax(0,1fr) 520px; gap:16px; padding:16px 24px; }}
@media (max-width: 1100px) {{ main {{ grid-template-columns:1fr; }} }}
.map {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:10px; overflow:auto; }}
.map svg {{ width:100%; height:auto; display:block; }}
.grat {{ fill:#5C6F89; font:12px 'IBM Plex Mono',ui-monospace,monospace; }} .wp {{ fill:var(--amber); font:600 14px 'IBM Plex Mono',ui-monospace,monospace; letter-spacing:1px; }}
.legend {{ display:flex; gap:18px; flex-wrap:wrap; padding:8px 4px 0; font:13px 'IBM Plex Mono',ui-monospace,monospace; color:var(--mut); }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:5px; margin-right:6px; vertical-align:middle; }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px 14px; margin-bottom:12px; }}
h2 {{ margin:0 0 8px; font-size:14px; letter-spacing:2px; color:var(--mut); font-weight:600; }}
h3 {{ margin:0 0 6px; font-size:15px; letter-spacing:1px; color:var(--head); }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }} th {{ text-align:left; font-weight:600; color:var(--ink); padding:4px 6px; }}
td {{ padding:4px 6px; font-family:'IBM Plex Mono',ui-monospace,monospace; text-align:right; color:var(--head); }} td.u {{ color:var(--mut); text-align:left; }}
thead th {{ color:var(--mut); font-size:12px; letter-spacing:1px; text-align:right; }} thead th:first-child {{ text-align:left; }}
tbody tr + tr {{ border-top:1px solid #1B2D47; }}
.big {{ font-size:18px; font-weight:600; }} .mono {{ font-family:'IBM Plex Mono',ui-monospace,monospace; font-size:13px; }}
.ok {{ color:var(--ok); }} .warn {{ color:var(--amber); }} .bad {{ color:var(--bad); }} .muted {{ color:var(--mut); }}
.tag {{ font:600 12px 'IBM Plex Mono',ui-monospace,monospace; padding:1px 6px; border-radius:3px; border:1px solid currentColor; }}
.cards {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }} .card {{ background:#0F1D31; border:1px solid var(--line); border-radius:6px; padding:10px; }}
.kv {{ display:flex; gap:8px; align-items:baseline; margin:3px 0; flex-wrap:wrap; }} .k {{ font:12px 'IBM Plex Mono',ui-monospace,monospace; color:var(--mut); letter-spacing:1px; min-width:78px; }}
.mc {{ font-size:13px; margin-top:3px; }} table.mini td {{ text-align:center; font-size:13px; }} table.mini thead th {{ text-align:center; }} table.mini tbody th {{ font-size:12px; color:var(--mut); }} footer {{ padding:0 24px 18px; color:var(--mut); font:12px 'IBM Plex Mono',ui-monospace,monospace; }} footer a {{ color:var(--mut); }}
</style></head><body>
<header><h1>ARGOS · DEPLOYMENT MAP</h1><span>{html.escape(d['plan']['name'].upper())} · {html.escape(d['plan']['period'].upper())} · {d['plan']['km']:.0f} KM · SEED {d['sampling']['seed']} · {d['sampling']['points']} POINTS</span></header>
<main>
<div class="map">{svg_map(d)}
<div class="legend"><span><i class="dot" style="background:{SS_COLOR['low']}"></i>SEA STATE ≤ 3</span><span><i class="dot" style="background:{SS_COLOR['mid']}"></i>SEA STATE 4</span><span><i class="dot" style="background:{SS_COLOR['high']}"></i>SEA STATE ≥ 5</span><span>— ROUTE</span><span>▒ AREA ±{d['sampling']['corridor_km']} KM</span></div></div>
<div>
<section><h2>FORECAST RANGES</h2><table><thead><tr><th></th><th>P50</th><th>P90</th><th>MAX</th><th></th></tr></thead><tbody>
{_row('SEAWATER', r['seawater_c'], '°C')}{_row('WIND', r['wind_kn'], 'kn')}{_row('GUST', r['gust_kn'], 'kn')}{_row('WAVE', r['wave_m'], 'm', '{:.2f}')}{_row('SEA STATE', r['sea_state'], 'Douglas', '{:.0f}')}
</tbody></table><div class="mono muted" style="margin-top:6px">{hist}</div></section>
<section><h2>DEPLOYMENT PARAMETERS</h2><table><tbody>
<tr><th>LOAD-OUT HEAT ({' · '.join(d['load_out'])})</th><td class="big">{c['load_out_heat_kw']:.1f}</td><td class="u">kW</td></tr>
<tr><th>COOLING AT P90 SEAWATER</th><td class="big {_margin(c['normal_kw_at_p90'] - c['load_out_heat_kw'])}">{c['normal_kw_at_p90']:.1f}</td><td class="u">kW</td></tr>
<tr><th>COOLING AT MAX SEAWATER</th><td class="big {_margin(c['normal_kw_at_max'] - c['load_out_heat_kw'])}">{c['normal_kw_at_max']:.1f}</td><td class="u">kW</td></tr>
<tr><th>ONE PUMP DOWN AT MAX</th><td class="big {_margin(c['degraded_kw_at_max'] - c['load_out_heat_kw'])}">{c['degraded_kw_at_max']:.1f}</td><td class="u">kW</td></tr>
<tr><th>BRIEF ENVELOPE (30 °C)</th><td class="big {_margin(c['envelope_kw'] - c['load_out_heat_kw'])}">{c['envelope_kw']:.1f}</td><td class="u">kW</td></tr>
</tbody></table></section>
<section><h2>WEATHER WINDOWS · SHARE OF SAMPLED HOURS OPEN</h2><table><tbody>{wins}</tbody></table></section>
<section><h2>MISSION PROFILES · LOAD-OUT {' · '.join(d['load_out'])} · D1 AT ROUTE SEAWATER</h2><div class="cards">{''.join(cards)}</div></section>
</div></main>
<footer>{html.escape(d['sources']['weather'])} · {html.escape(d['sources']['coast'])} · PLAN {html.escape(d['sources']['plan'])} · WEATHER BETWEEN 4 GRID POINTS, INTERPOLATED ALONG THE ROUTE</footer>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="deploy_map", description="ArgOS deployment map")
    ap.add_argument("--plan", default=CFG["plan"])
    ap.add_argument("--seed", type=int, default=CFG["seed"])
    ap.add_argument("--points", type=int, default=CFG["points"])
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args(argv)
    d = build(a.plan, a.seed, a.points)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "deployment.json").write_text(json.dumps({k: v for k, v in d.items() if k != "coast"}, indent=1) + "\n")
    (out / "index.html").write_text(page(d))
    r = d["ranges"]
    print(f"DEPLOYMENT {d['plan']['name']} · {d['plan']['period']} · {d['sampling']['points']} points, seed {d['sampling']['seed']}")
    print(f"  seawater P90 {r['seawater_c']['p90']} max {r['seawater_c']['max']} °C · gust P90 {r['gust_kn']['p90']} kn · sea state P90 {r['sea_state']['p90']:.0f}")
    for w in d["windows"]:
        print(f"  {w['guest']} {w['activity']}: {w['open_pct']:.0f} % open")
    for p in d["profiles"]:
        print(f"  {p['id']}: envelope {p['envelope']['verdict']} · route max {p['route_max']['verdict']} ({p['route_max']['binding']})")
    print(f"  wrote {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
