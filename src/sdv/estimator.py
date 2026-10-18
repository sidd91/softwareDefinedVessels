"""State estimation: one argos-frame/1 in, one argos-snapshot/2 out, per tick (docs/STATE_ESTIMATION.md).

    est = Estimator("scenario_b", mission="survey", variant="default")
    snapshot = est.step(frame)

The estimator reads only the frames and its own previous estimate, so a replay of the frame log reproduces every
snapshot. config/signals.yaml is the only authority for names, feeds, fallbacks, confirm rules and derivations;
the nine steps below follow "Each tick, in order". Wall time never enters a snapshot.
"""
from __future__ import annotations

import copy
import json
import math

import yaml

from sdv import ledger as Lg
from sdv.loader import ROOT

SOURCE_CONF = {"plant": "measured", "guest_report": "reported", "crew_report": "reported", "laptop": "reported",
               "public_data": "reported", "scenario": "assumed"}
GROUPS = ("plant", "ship_state", "environment", "links", "crew")
EFFECT_IDLE_SIM = ("ramp", "deck_machinery")          # the simulator reports these; the estimator takes the worse
FAULT_ACTIVE = ("confirmed", "restoring")
SUBJECTS = {"genset_1": ("genset_trip", "pms"), "genset_2": ("genset_trip", "pms"),
            "chw_pump_1": ("cooling_degraded", "chw"), "chw_pump_2": ("cooling_degraded", "chw")}
NO_RULE = "computed from the inputs' fallbacks"


def r1(x):
    """signals.yaml rounding: 0.1 for every number, a whole number kept whole."""
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, float):
        return round(x, 1) + 0.0
    if isinstance(x, dict):
        return {k: r1(v) for k, v in x.items()}
    if isinstance(x, list):
        return [r1(v) for v in x]
    return x


def _canon(x):
    """The log serializer's form (sdv.loop.canonical): numbers to 0.1, whole numbers as integers, so a value read
    live (35.0) and the same value read back from a log (35) compare equal and since_t_s never diverges."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        v = round(float(x), 1)
        return int(v) if v.is_integer() else v
    if isinstance(x, dict):
        return {k: _canon(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_canon(v) for v in x]
    return x


def _key(v) -> str:
    return json.dumps(_canon(v), sort_keys=True)


CREW_ANSWERS = ("hlo_deck_report", "hlo_wind_kn", "standing_plan")


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}"


def cap(capacity, unit, degraded=(), zero=False) -> dict:
    return {"capacity": capacity, "unit": unit, "degraded_by": list(degraded), "zero_by_rule": zero}


class Estimator:
    def __init__(self, scenario: str = "scenario_b", mission: str = "survey", variant: str = "default", seed: int = 0,
                 installed: list[str] | None = None, root=ROOT):
        self.S = yaml.safe_load((root / "config/signals.yaml").read_text())
        self.A = yaml.safe_load((root / "config/assumptions.yaml").read_text())
        self.scen = yaml.safe_load((root / f"config/scenarios/{scenario}.yaml").read_text())
        self.SIG = {s["name"]: s for s in self.S["signals"]}
        self.scenario, self.mission, self.variant, self.seed = scenario, mission, variant, seed
        self.installed = list(installed or self.scen["guests"])
        self.cards = {g: yaml.safe_load((root / f"manifests/{g}.yaml").read_text()) for g in self.installed}
        self.constants = {"layered_water": bool(self.scen["location"]["layered"])}
        self.names = [s["name"] for s in self.S["signals"]
                      if s["group"] != "guests" or s["name"].split(".")[0] in self.installed]
        self.last: dict[str, dict] = {}       # raw signal -> its last reading {value, source, t_s, transition, reported_t_s}
        self.seen: dict[str, tuple] = {}      # field -> (value key, since_t_s)
        self.good: dict[str, object] = {}     # derived field -> its last value computed from fresh inputs
        self.faults: dict[str, dict] = {}     # subject -> fault record (snapshot shape) plus private _ok
        self.drops: dict[str, dict] = {}      # feed -> {event_t_s, until_t_s, injected}
        self.unheard: set[str] = set()        # feeds dropped before their first reading, until one arrives
        self.crew_changed_t_s: int | None = None   # the tick an accepted crew_aboard reading last changed
        self.answered: dict[str, float] = {}  # crew answer -> when it was given (reported_t_s, else first seen)
        self.link_since: int | None = None
        self.land_by: float | None = None
        self.log: list[str] = []              # refusals, mismatches and cancelled faults, by tick
        self.tick = -1

    # ---------------------------------------------------------------------------------------------- 1. read
    def _valid(self, sig: dict, v) -> bool:
        if v is None:
            return bool(sig.get("nullable")) or sig.get("type") in ("sweep",) or sig["name"].startswith("hlo_")
        t = sig.get("type")
        if "values" in sig and v not in sig["values"]:
            return False                      # a crew level of 10, a mode the card does not have
        if t == "integer" and (isinstance(v, bool) or not isinstance(v, (int, float)) or not float(v).is_integer()):
            return False
        if t in ("number", "integer", "ship_time"):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return False
            lo, hi = sig.get("range", [None, None])
            return (lo is None or v >= lo) and (hi is None or v <= hi)
        if t == "boolean":
            return isinstance(v, bool)
        if t == "sweep":
            return isinstance(v, dict) and v.get("result") in ("clear", "not_clear") and _number(v.get("t_s"))
        if t == "requests":
            return isinstance(v, list) and all(isinstance(q, dict) and "request_seq" in q and "state" in q for q in v)
        if t == "rates":
            return isinstance(v, dict) and all(_number(x) for x in v.values())
        if t == "enum" or "values" in sig:
            return v in sig["values"]
        return True

    def _read(self, frame: dict) -> None:
        readings = dict(frame.get("signals", {}))
        for g, d in frame.get("guests", {}).items():
            for k, r in d.items():
                readings[f"{g}.{k}"] = r
        for name, r in readings.items():
            sig = self.SIG.get(name)
            if sig is None or sig["producer"] == "estimator":
                self.log.append(f"{self.tick}: refused reading {name}: not a simulator signal in signals.yaml")
                continue
            if not self._valid(sig, r["value"]):
                self.log.append(f"{self.tick}: {name} = {r['value']!r} outside its type or range, counted as missing")
                continue
            if sig.get("type") == "integer" and r["value"] is not None:
                r = {**r, "value": int(r["value"])}   # 6.0 and 6 are one crew level, live and on replay
            if name == "crew_aboard" or name in CREW_ANSWERS:
                prev = self.last.get(name)
                same = prev is not None and _canon(prev["value"]) == _canon(r["value"])
                if name == "crew_aboard" and prev is not None and not same:
                    self.crew_changed_t_s = self.tick
                if name in CREW_ANSWERS:
                    self.answered[name] = r.get("reported_t_s", self.answered.get(name) if same else r["t_s"])
            self.last[name] = r

    # ---------------------------------------------------------------------------------------------- 3. feeds
    def _feeds(self, link_up: bool) -> dict:
        out = {}
        for f, cfg in self.S["feeds"].items():
            if "heartbeat" in cfg:
                r = self.last.get(cfg["heartbeat"])
                last = r["t_s"] if r else None
            else:
                ts = [self.last[n]["t_s"] for n in self.names if self.SIG[n].get("feed") == f and n in self.last]
                last = max(ts) if ts else None
            if f == "g3_acoustic":
                since = self.link_since if self.link_since is not None else 0
                stale = link_up and last is not None and self.tick - max(last, since) > cfg["stale_after_link_up_s"]
            else:
                stale = (last is None and f in self.unheard) or (last is not None and self.tick - last > cfg["stale_after_s"])
            drop = self.drops.get(f)
            out[f] = {"stale": bool(stale), "last_heard_t_s": last, "drop": copy.deepcopy(drop)}
        return out

    # ---------------------------------------------------------------------------------------------- 4. fall back
    def _fallback_value(self, sig: dict, last, age: float | None):
        fb = sig["fallback"]
        name = sig["name"]
        if "by_use" in fb:
            return last, "bound"
        if sig.get("grace_s") is not None and age is not None and age <= self.S["feeds"][sig["feed"]]["stale_after_s"] + sig["grace_s"]:
            return last, "hold"
        if "value" in fb:
            v = fb["value"]
            if "worse" in fb.get("rule", "") and isinstance(last, (int, float)) and v is not None:
                return max(last, v), "bound"
            return copy.deepcopy(v), "bound"
        rule = fb.get("rule", "")
        g = name.split(".")[0]
        card = self.cards.get(g)
        if "highest-draw mode" in rule and card:
            return max(card["modes"], key=lambda m: m["power_kw"])["name"], "bound"
        if "declared peak" in rule and card:
            p = card["consumes"]["power_kw"]
            return float(p.get("peak", p["nominal"])), "bound"
        if "nominal rates" in rule and card:
            return {k[5:]: v["nominal"] for k, v in card["consumes"].items() if k.startswith("data_") and "nominal" in v}, "bound"
        if "next lower level" in rule:
            levels = sig["values"]
            i = levels.index(last) if last in levels else len(levels) - 1
            return levels[min(i + 1, len(levels) - 1)], "bound"
        return copy.deepcopy(last), "bound"

    def _raw(self, name: str, feeds: dict) -> dict:
        sig = self.SIG[name]
        srcs = sig["source"] if isinstance(sig["source"], list) else [sig["source"]]
        r = self.last.get(name)
        if r is None:
            unknown = {"value": None, "source": srcs[0], "age_s": None, "confidence": "assumed", "stale": False}
            if sig["rate"] == "event" or sig["feed"] not in self.unheard:
                return unknown
            # never heard because its feed was dropped before its first reading (an hourly reading can be an hour
            # away after the drop ends): unknown never means safe, take the fallback while there is one
            value, stage = self._fallback_value(sig, None, None)
            if value is None:
                return unknown
            return {"value": value, "source": srcs[0], "age_s": None, "confidence": "substituted", "stale": True,
                    "substituted": {"last_value": None, "last_good_t_s": None,
                                    "rule": sig["fallback"].get("rule", "the fallback value"), "stage": stage}}
        age = self.tick - r["t_s"]
        feed = self.S["feeds"][sig["feed"]]
        if sig["rate"] == "event":
            stale = feeds[sig["feed"]]["stale"]
        else:
            stale = age > feed.get("stale_after_s", self.S["default_stale_after_s"])
        f = {"value": copy.deepcopy(r["value"]), "source": r["source"], "age_s": age,
             "confidence": "substituted" if stale else SOURCE_CONF[r["source"]], "stale": bool(stale)}
        if "reported_t_s" in r:
            f["reported_t_s"] = r["reported_t_s"]
        if stale:
            value, stage = self._fallback_value(sig, r["value"], age)
            f["value"] = value
            f["substituted"] = {"last_value": copy.deepcopy(r["value"]), "last_good_t_s": r["t_s"],
                                "rule": sig["fallback"].get("rule", "the fallback value"), "stage": stage}
        elif "transition" in r and r["t_s"] == self.tick:
            f["transition"] = copy.deepcopy(r["transition"])
        return f

    # ---------------------------------------------------------------------------------------------- 5. faults
    def _votes(self, subject: str, F: dict) -> tuple[list, list] | None:
        """Own votes and shared votes for one subject, or None when its feed is stale (no vote is cast)."""
        v = lambda n: F[n]["value"]
        n = subject.rsplit("_", 1)[1]
        if subject.startswith("genset"):
            names = [f"genset_{n}_relay_trip", f"genset_{n}_kw", "bus_frequency_hz"]
            if any(F[x]["stale"] for x in names):
                return None
            own = (["relay_trip"] if v(f"genset_{n}_relay_trip") is True else []) + \
                  (["kw_near_zero"] if v(f"genset_{n}_kw") is not None and v(f"genset_{n}_kw") < 22.5 else [])
            shared = ["frequency_dip"] if v("bus_frequency_hz") is not None and v("bus_frequency_hz") < 58.8 else []
            return own, shared
        names = [f"chw_pump_{n}_alarm", f"chw_pump_{n}_running", "chw_flow_pct", "chw_supply_c", "chw_return_c"]
        if any(F[x]["stale"] for x in names):
            return None
        own = (["pump_alarm"] if v(f"chw_pump_{n}_alarm") is True else []) + \
              (["pump_stopped"] if v(f"chw_pump_{n}_running") is False else [])
        shared = (["flow_low"] if v("chw_flow_pct") is not None and v("chw_flow_pct") < 70 else []) + \
                 (["delta_t_high"] if v("chw_return_c") is not None and v("chw_supply_c") is not None
                  and v("chw_return_c") - v("chw_supply_c") > 8 else [])
        return own, shared

    def _confirm(self, F: dict, events: list) -> None:
        R = self.S["confirm_rules"]
        rt = self.A["response_time_s"]
        t = self.tick
        for subject, (rule, _feed) in SUBJECTS.items():
            votes = self._votes(subject, F)
            f = self.faults.get(subject)
            if votes is None:
                if f and f["state"] == "pending":
                    f["state"] = "held_stale"
                continue
            own, shared = votes
            counted = own + (shared if own else [])
            ok = len(counted) >= R["genset_trip"]["needed"] if rule == "genset_trip" else bool(own) and bool(shared)
            if f is None or f["state"] == "cleared":
                if not own:
                    continue
                n = subject.rsplit("_", 1)[1]
                key = "genset" if rule == "genset_trip" else "pump"
                injected = any(e["type"] == rule and str(e["payload"].get(key)) == n and e["injected"] for e in events)
                f = self.faults[subject] = {
                    "fault": rule, "subject": subject, "state": "pending", "raw_event_t_s": t, "confirmed_t_s": None,
                    "votes": counted, "first_shed_due_t_s": t + rt["shed_first_action"],
                    "full_sequence_due_t_s": t + rt["shed_full_sequence"], "healthy_since_t_s": None,
                    "injected": injected, "_ok": None}
            if f["state"] in ("pending", "held_stale"):
                if not own:
                    self.log.append(f"{t}: {rule} on {subject} cancelled, its votes dropped before {R[rule]['hold_s']} s")
                    del self.faults[subject]
                    continue
                f["votes"] = counted
                held = f["state"] == "held_stale"
                if ok and (f["_ok"] == t - R[rule]["hold_s"] or (held and f["_ok"] is not None)):
                    f["state"], f["confirmed_t_s"] = "confirmed", t
                elif held:
                    f["state"] = "pending"
                f["_ok"] = t if ok else None
            elif f["state"] in FAULT_ACTIVE:
                if own:
                    f["state"], f["healthy_since_t_s"] = "confirmed", None
                elif f["state"] == "confirmed":
                    f["state"], f["healthy_since_t_s"] = "restoring", t
                elif t - f["healthy_since_t_s"] >= R["restore"]["healthy_hold_s"]:
                    f["state"] = "cleared"

    # ---------------------------------------------------------------------------------------------- 6-8. derive
    def _inputs(self, name: str) -> list[str]:
        out = []
        for i in self.SIG[name].get("inputs", []):
            out += [f"{g}.{i[2:]}" for g in self.installed] if i.startswith("*.") else [i]
        return out

    def _derived(self, name: str, value, F: dict, active_rules: set, extra: dict | None = None) -> dict:
        sig = self.SIG[name]
        conf, goods, scopes = [], [], []
        for i in self._inputs(name):
            if i.startswith("run."):
                conf.append("assumed")
                continue
            if i not in F:
                continue
            c = F[i]["confidence"]
            conf.append(c)
            s = F[i].get("substituted")
            if c == "substituted" and s:
                if s.get("last_good_t_s") is not None:
                    goods.append(s["last_good_t_s"])
                if s.get("scope"):
                    scopes.append(s["scope"])
        order = self.S["field_metadata"]["confidence"]
        if "substituted" in conf:
            c = "substituted"
        elif sig.get("confirm") in active_rules:
            c = "confirmed"
        elif conf:
            c = min(conf, key=order.index)
        else:
            c = "assumed"
        f = {"value": value, "source": "derived", "age_s": 0, "confidence": c, "stale": c == "substituted"}
        if c == "substituted":
            fb = sig["fallback"]
            s = {"last_value": copy.deepcopy(self.good.get(name)), "last_good_t_s": min(goods) if goods else None,
                 "rule": fb.get("rule", NO_RULE), "stage": "derived"}
            scope = fb.get("scope") or (scopes[0] if scopes else None)
            if scope:
                s["scope"] = scope
            f["substituted"] = s
        else:
            self.good[name] = copy.deepcopy(value)
        if extra:
            f.update(extra)
        return f

    def _effects(self, F: dict) -> dict[str, list[str]]:
        acts = self.S["activities"]
        holders = {}
        for k in self.S["derivations"]["effects"]["idle"]:
            holders[k] = sorted(g for g in self.installed
                                if (a := F[f"{g}.activity"]["value"]) not in (None, "none") and k in acts[g].get(a, {}).get("effects", {}))
        return holders

    def _excluders(self, F: dict, what: str) -> list[str]:
        acts = self.S["activities"]
        return sorted(g for g in self.installed
                      if (a := F[f"{g}.activity"]["value"]) not in (None, "none") and what in acts[g].get(a, {}).get("excludes", []))

    def _reserve_kw(self, gensets: int, kn) -> float:
        if gensets < 2:
            return self.A["power"]["guest_reserve_kw"]["one_genset_down"]
        by = self.A["power"]["guest_reserve_kw_by_speed"]
        bands = self.S["derivations"]["speed_band"]["bands_kn"]
        if kn is None:
            return by["fast"]
        reserve = {"stopped": self.S["derivations"]["guest_reserve_kw"]["stopped_kw"], **by}
        named = sorted(bands.items(), key=lambda kv: kv[1][0])
        for b, (lo, hi) in named:
            if kn >= lo and (hi is None or kn <= hi):
                return reserve[b]
        for (b0, (_, hi0)), (b1, (lo1, _)) in zip(named, named[1:]):
            if hi0 < kn < lo1:
                return min(reserve[b0], reserve[b1])
        return by["fast"]

    def _band(self, kn) -> str | None:
        if kn is None:
            return None
        bands = sorted(self.S["derivations"]["speed_band"]["bands_kn"].items(), key=lambda kv: kv[1][0])
        for b, (lo, hi) in bands:
            if kn >= lo and (hi is None or kn <= hi):
                return b
        for (b0, (_, hi0)), (b1, (lo1, _)) in zip(bands, bands[1:]):
            if hi0 < kn < lo1:
                return b1
        return bands[-1][0]

    def _g4_limits(self) -> dict:
        lim = {}
        for h in self.cards.get("G4", {}).get("hard_limits", []):
            w, th = h["when"], h["then"]
            if w["signal"] == "G4.battery_pct":
                lim["battery_pct"], lim["battery_within_s"] = w["value"], 60 * th["within_min"]
            elif w["signal"] == "G4.activity" and w["value"] == "airborne":
                lim["endurance_s"] = 60 * th["within_min"]
        return lim

    def _derive(self, F: dict, feeds: dict, events: list) -> None:
        t = self.tick
        d = self.S["derivations"]
        active = {f["fault"] for f in self.faults.values() if f["state"] in FAULT_ACTIVE}
        confirmed = {s: f for s, f in self.faults.items() if f["state"] in FAULT_ACTIVE}
        v = lambda n: F[n]["value"]

        # faults to plant state
        trips = sorted(s for s, f in confirmed.items() if f["fault"] == "genset_trip")
        pumps = sorted(s for s, f in confirmed.items() if f["fault"] == "cooling_degraded")
        F["gensets_online"] = self._derived("gensets_online", max(1, 2 - len(trips)), F, active)
        F["tripped_genset"] = self._derived("tripped_genset", trips[0] if trips else "none", F, active)
        F["cooling_state"] = self._derived("cooling_state", "degraded" if pumps else "nominal", F, active)
        for n in ("gensets_online", "cooling_state"):
            if F[n]["stale"]:
                F[n]["value"] = self.SIG[n]["fallback"]["value"]

        holders = self._effects(F)
        F["heading_free"] = self._derived("heading_free", not holders["heading_free"], F, active, {"by": holders["heading_free"]})
        F["flight_deck_ops"] = self._derived("flight_deck_ops", "in_use" if holders["flight_deck_ops"] else "free", F, active,
                                             {"by": holders["flight_deck_ops"]})
        F["deck_machinery_permitted"] = self._derived(
            "deck_machinery_permitted", v("emission") == "normal" and not self._excluders(F, "deck_machinery"), F, active)
        band = self._band(v("speed_kn"))
        F["speed_band"] = self._derived("speed_band", band if band else self.SIG["speed_band"]["fallback"]["value"], F, active)

        up, failing = self._up, self._failing
        F["acoustic_link_up"] = self._derived("acoustic_link_up", up, F, active)
        F["acoustic_kbps"] = self._derived("acoustic_kbps", float(d["acoustic_kbps"]["value_up"]) if up else 0.0, F, active)

        # the deck latch (R3)
        sweep = v("last_sweep")
        F["deck_latched_clear"] = self._derived(
            "deck_latched_clear", bool(sweep) and sweep.get("result") == "clear" and v("deck_activity_since_sweep") is False, F, active)

        # guests: over-draw and mode end times
        for g in self.installed:
            card = self.cards[g]
            mode, kw = F[f"{g}.mode"], F[f"{g}.kw_actual"]
            declared = next((m["power_kw"] for m in card["modes"] if m["name"] == mode["value"]), 0)
            fresh = not kw["stale"] and kw["value"] is not None
            od = round((kw["value"] / declared - 1) * 100, 1) if fresh and declared else None
            F[f"{g}.overdraw_pct"] = self._derived(f"{g}.overdraw_pct", od, F, active)
            if f"{g}.mode_ends_t_s" in self.SIG:
                dur = next((m.get("duration_s") for m in card["modes"] if m["name"] == mode["value"]), None)
                start = self.seen.get(f"{g}.mode", (None, None))[1]
                start = 0 if start is None else start
                if self._changed(f"{g}.mode", mode["value"]):
                    start = t
                F[f"{g}.mode_ends_t_s"] = self._derived(f"{g}.mode_ends_t_s", start + dur if dur else None, F, active)

        # G4's land-by (derivations.g4_land_by)
        if "G4" in self.installed:
            lim = self._g4_limits()
            act = v("G4.activity")
            flying = act in ("airborne", "launch_recovery")
            launched = v("G4.launched_t_s")
            F["G4.airborne_since_t_s"] = self._derived("G4.airborne_since_t_s", launched if flying else None, F, active)
            bat, rep = F["G4.battery_pct"], self.last.get("G4.battery_pct")
            cross = None
            if flying and rep is not None and rep["value"] is not None:
                pct, t_rep = rep["value"], rep["t_s"]
                th = lim["battery_pct"]
                if pct < th:
                    cross = round(t_rep - (th - pct) / self.A["rules"]["r3"]["drain_pct_min"] * 60, 1)
                elif bat["stale"]:
                    cross = round(t_rep + (pct - th) / d["g4_land_by"]["drain_pct_max"] * 60, 1)
            F["G4.battery_crossing_t_s"] = self._derived("G4.battery_crossing_t_s", cross, F, active)
            if flying:
                bounds = [b for b in (launched + lim["endurance_s"] if launched is not None else None,
                                      cross + lim["battery_within_s"] if cross is not None else None) if b is not None]
                new = min(bounds) if bounds else None
                if self.land_by is not None and (new is None or new > self.land_by):
                    new = self.land_by
                self.land_by = new
            else:
                self.land_by = None
            F["G4.land_by_t_s"] = self._derived("G4.land_by_t_s", None if self.land_by is None else round(self.land_by, 1), F, active)

        # capacity of the live classes
        reasons = []
        if trips:
            f = confirmed[trips[0]]
            reasons.append(f"one genset down: {trips[0]} tripped, confirmed at {_num(f['confirmed_t_s'])} s")
        elif F["gensets_online"]["stale"]:
            reasons.append("genset feed stale: taken as one genset down for admission and the armed ladder; D4 does not act on it")
        if v("speed_kn") is None:
            reasons.append("speed unknown: reserve at the fast band's figure")
        F["power"] = self._derived("power", cap(self._reserve_kw(v("gensets_online"), v("speed_kn")), "kW", reasons), F, active)
        line = self.A["power"]["mission_line_kw"]
        F["port_line"] = self._derived("port_line", cap(line["port"], "kW"), F, active)
        F["stbd_line"] = self._derived("stbd_line", cap(line["stbd"], "kW"), F, active)
        degraded = v("cooling_state") == "degraded"
        why = []
        if pumps:
            why.append(f"cooling degraded: chilled-water pump {pumps[0].rsplit('_', 1)[1]} failed, one of two running "
                       f"(x{_num(self.A['heat']['degraded_factor'])})")
        elif degraded:
            why.append("chilled-water feed stale: taken as degraded for admission and the armed ladder; D4 does not act on it")
        heat = round(Lg.heat_capacity_kw(self.A, v("seawater_c"), degraded), 1)
        F["heat"] = self._derived("heat", cap(heat, "kW", why), F, active)
        silent = v("emission") == "silent"
        F["satcom"] = self._derived("satcom", cap(0.0 if silent else float(v("satcom_mbps")), "Mbit/s",
                                                  ["emission silent: SATCOM 0 by rule"] if silent else [], silent), F, active)
        rng = F["G4.range_km"] if "G4" in self.installed else None
        if silent:
            radio = cap(0.0, "Mbit/s", ["emission silent: radio 0 by rule"], True)
        elif rng is not None and v("G4.activity") in ("airborne", "launch_recovery") and (
                rng["value"] is None or rng["value"] > self.A["data"]["los_radio_drone_range_km_max"]):
            floor = float(self.A["data"]["los_radio_mbps"]["min"])
            cause = "G4 range unknown (telemetry stale)" if rng["value"] is None else \
                f"G4 beyond {_num(self.A['data']['los_radio_drone_range_km_max'])} km"
            radio = cap(floor, "Mbit/s", [f"{cause}: radio at its {_num(floor)} Mbit/s floor"])
        else:
            radio = cap(float(v("los_radio_mbps")), "Mbit/s")
        F["los_radio"] = self._derived("los_radio", radio, F, active)
        if up:
            ac = cap(float(v("acoustic_kbps")), "kbit/s")
        else:
            words = []
            for k in failing:
                w = f"{k.replace('_', ' ')} {str(v(k)).lower()}" if k != "deck_machinery" else "deck machinery running"
                tr = F[k].get("transition")
                if tr:
                    w += f" (settling to {tr['to']})" if k == "course" else f" (going to {tr['to']})"
                words.append(w)
            if self.constants["layered_water"]:
                words.append("layered water")
            ac = cap(0.0, "kbit/s", ["acoustic link down: " + ", ".join(words)], True)
        F["acoustic"] = self._derived("acoustic", ac, F, active)
        ceiling = round(min(F["power"]["value"]["capacity"], heat) - self.A["power"]["shed_headroom_kw"], 1)
        F["shed_ceiling_kw"] = self._derived("shed_ceiling_kw", ceiling, F, active)

    def _merge_effects(self, F: dict) -> None:
        """ramp and deck_machinery: the worse of the simulator's value and the running activities' effects."""
        holders = self._effects(F)
        for k in EFFECT_IDLE_SIM:
            idle = self.S["derivations"]["effects"]["idle"][k]
            if holders[k] and F[k]["value"] == idle:
                self.log.append(f"{self.tick}: {k} reads {idle!r} while {', '.join(holders[k])} runs: taken as in use")
                F[k]["value"] = True if k == "deck_machinery" else "in_use"
            F[k]["by"] = holders[k]

    def _link(self, F: dict) -> None:
        """The acoustic link (A.5): every up_when condition holds and the water column is not layered."""
        want = self.A["data"]["acoustic_link"]["up_when"]
        self._failing = [k for k, w in want.items() if F[k]["value"] != w]
        self._up = not self._failing and not self.constants["layered_water"]
        if self._up and self.link_since is None:
            self.link_since = self.tick
        if not self._up:
            self.link_since = None

    # ---------------------------------------------------------------------------------------------- since
    def _changed(self, name: str, value) -> bool:
        prev = self.seen.get(name)
        return prev is not None and json.loads(prev[0])[0] != _canon(value)

    def _expire(self, F: dict) -> None:
        """Crew answers do not last (signals.yaml expires_after_s, counted from reported_t_s): a clear deck report,
        the landing officer's wind and a standing plan lapse to their fallbacks; a standing plan is also void once
        a crew change after it was approved, except the hand-over to 0 aboard."""
        crew = (self.last.get("crew_aboard") or {}).get("value")
        for name in CREW_ANSWERS:
            sig, f = self.SIG[name], F.get(name)
            rep, life = (f or {}).get("reported_t_s", self.answered.get(name)), sig.get("expires_after_s")
            if not f or f["stale"] or rep is None or f["value"] in (None, "none", "not_clear"):
                continue
            why = None
            if life is not None and self.tick - rep > life:
                why = f"expired: the report is older than {life} s"
            # a crew level reading that changes voids the plan; a stale reading's fallback does not, and at the
            # hand-over to 0 aboard the departing crew's plan stands (docs/SCENARIO_C_MEMO.md)
            if name == "standing_plan" and self.crew_changed_t_s is not None and self.crew_changed_t_s > rep and crew != 0:
                why = "void: the crew level changed after the plan was approved"
            if why:
                f["substituted"] = {"last_value": copy.deepcopy(f["value"]), "last_good_t_s": rep, "rule": why, "stage": "bound"}
                f["value"] = copy.deepcopy(sig["fallback"]["value"])
                f["confidence"] = "substituted"

    def _since(self, F: dict) -> None:
        """since_t_s is the tick the value last changed. A number moving through a transition changes every tick,
        and its change ends on the transition's end tick; a capacity changes with its figure, not its wording."""
        for name, f in F.items():
            val = f["value"]
            if isinstance(val, dict) and "capacity" in val:
                val = (val["capacity"], val["zero_by_rule"])
            moving = "transition" in f and isinstance(val, (int, float)) and not isinstance(val, bool)
            k = _key([val, moving])
            prev = self.seen.get(name)
            since = prev[1] if prev else None
            if prev is not None and (prev[0] != k or moving):
                since = self.tick
            self.seen[name] = (k, since)
            if since is not None:
                f["since_t_s"] = since

    # ---------------------------------------------------------------------------------------------- one tick
    def step(self, frame: dict) -> dict:
        assert frame["contract"] == "argos-frame/1"
        assert frame["tick"] == self.tick + 1, f"frame {frame['tick']} after {self.tick}: ticks are never skipped"
        self.tick = t = frame["tick"]
        events = frame.get("events", [])
        for e in events:
            if e["type"] == "baseline":
                self.variant = e["payload"].get("variant", self.variant)
            if e["type"] == "feed_drop":
                p = e["payload"]
                self.drops[p["feed"]] = {"event_t_s": e["t_s"], "until_t_s": p.get("until_t_s"), "injected": e["injected"]}
                self.unheard.add(p["feed"])
        for f, drop in list(self.drops.items()):
            if drop["until_t_s"] is not None and t >= drop["until_t_s"]:
                del self.drops[f]

        self._read(frame)                                            # 1
        self.unheard -= {self.SIG[n].get("feed") for n in self.last}
        feeds = self._feeds(False)                                   # 2-3, G3's feed once the link is known
        raw = [n for n in self.names if self.SIG[n]["producer"] != "estimator"]
        F = {n: self._raw(n, feeds) for n in raw}                    # 4
        self._expire(F)
        self._merge_effects(F)
        self._link(F)
        feeds["g3_acoustic"] = self._feeds(self._up)["g3_acoustic"]
        for n in raw:
            if self.SIG[n].get("feed") == "g3_acoustic":
                F[n] = self._raw(n, feeds)
        self._confirm(F, events)                                     # 5
        self._derive(F, feeds, events)                               # 6-8
        self._since(F)

        snap = {"run": {"contract": "argos-snapshot/2", "scenario": self.scenario, "variant": self.variant,      # 9
                        "mission": self.mission, "seed": self.seed, "tick": t, "t_ship_s": frame["t_ship_s"],
                        "installed": self.installed,
                        "constants": {k: {"value": v, "source": "scenario", "confidence": "assumed"} for k, v in self.constants.items()}}}
        for g in GROUPS:
            snap[g] = {s["name"]: F[s["name"]] for s in self.S["signals"] if s["group"] == g}
        snap["guests"] = {g: {s["name"].split(".", 1)[1]: F[s["name"]] for s in self.S["signals"]
                              if s["group"] == "guests" and s["name"].startswith(g + ".")} for g in self.installed}
        snap["capacity"] = {s["name"]: F[s["name"]] for s in self.S["signals"] if s["group"] == "capacity"}
        snap["feeds"] = feeds
        snap["faults"] = [{k: v for k, v in f.items() if not k.startswith("_")}
                          for f in sorted(self.faults.values(), key=lambda f: (f["raw_event_t_s"], f["subject"]))]
        snap["events"] = copy.deepcopy(events)
        return r1(snap)
