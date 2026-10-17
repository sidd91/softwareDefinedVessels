"""Build the Scenario B snapshot and frame fixtures in tests/fixtures/ from compact specs.

Each fixture is written twice: the snapshot the estimator emits (tests/fixtures/snapshots/) and the frame the
simulator would hand it on that tick (tests/fixtures/frames/). The specs below hold the readings (value and
reading time) and the derived values; this script fills in what the contract makes mechanical: age_s, stale,
confidence, feed health, the effect fields' `by`, and the frame (every reading whose t_s is this tick).
tests/test_snapshot_contract.py fails if the committed fixtures differ from this script's output, and checks the
derived values independently against config and the oracles.

    uv run python tools/build_snapshot_fixtures.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
NOW = "now"
CONF = None  # set in load()


def load(root: Path = ROOT):
    S = yaml.safe_load((root / "config/signals.yaml").read_text())
    return S, {s["name"]: s for s in S["signals"]}


def r1(x):
    """Canonical rounding: every float to 0.1."""
    if isinstance(x, float):
        return round(x, 1) + 0.0
    if isinstance(x, dict):
        return {k: r1(v) for k, v in x.items()}
    if isinstance(x, list):
        return [r1(v) for v in x]
    return x


# ------------------------------------------------------------------------------------------------ helpers

def R(value, t=NOW, src=None, since=None, tr=None, rep=None, sub=None):
    """A raw reading: value, reading time t (NOW = this tick; None = never read)."""
    return {"v": value, "t": t, "src": src, "since": since, "tr": tr, "rep": rep, "sub": sub}


def D(value, since=None, sub=None):
    """A derived value."""
    return {"v": value, "since": since, "sub": sub}


def cap(capacity, unit, degraded=(), zero=False):
    return {"capacity": capacity, "unit": unit, "degraded_by": list(degraded), "zero_by_rule": zero}


def sub(last, t, rule, stage="bound", scope=None):
    s = {"last_value": last, "last_good_t_s": t, "rule": rule, "stage": stage}
    if scope:
        s["scope"] = scope
    return s


SOURCE_CONF = {"plant": "measured", "guest_report": "reported", "crew_report": "reported", "laptop": "reported",
               "public_data": "reported", "scenario": "assumed"}
FAULT_RULE_STATES = {"confirmed", "restoring"}


class Spec:
    def __init__(self, name, tick, mission="survey"):
        self.name, self.tick, self.mission = name, tick, mission
        self.raw, self.derived = {}, {}
        self.faults, self.events, self.notes = [], [], []
        self.drops = {}
        self.installed = ["G3", "G4", "G5"]
        self.constants = {"layered_water": False}

    def copy(self, name, tick=None, mission=None):
        c = copy.deepcopy(self)
        c.name = name
        c.tick = self.tick if tick is None else tick
        c.mission = mission or self.mission
        c.events, c.notes = [], []
        return c


def assemble(spec: Spec, S: dict, SIG: dict) -> tuple[dict, dict]:
    tick = spec.tick
    order = S["field_metadata"]["confidence"]
    feeds = S["feeds"]
    raw = {}
    for name, r in spec.raw.items():
        t = tick if r["t"] == NOW else r["t"]
        raw[name] = dict(r, t=t)

    # ---- feed health
    link = spec.derived["acoustic_link_up"]
    feed_state = {}
    for f, cfg in feeds.items():
        members = [n for n in raw if SIG[n].get("feed") == f]
        times = [raw[n]["t"] for n in members if raw[n]["t"] is not None]
        if "heartbeat" in cfg:
            last = raw[cfg["heartbeat"]]["t"] if cfg["heartbeat"] in raw else None
        else:
            last = max(times) if times else None
        if f == "g3_acoustic":
            up_since = link["since"] if link["since"] is not None else 0
            stale = bool(link["v"]) and last is not None and tick - max(last, up_since) > cfg["stale_after_link_up_s"]
        else:
            stale = last is not None and tick - last > cfg["stale_after_s"]
        feed_state[f] = {"stale": stale, "last_heard_t_s": last, "fallback_active": stale, "drop": spec.drops.get(f)}

    fields = {}
    for name, r in raw.items():
        sig = SIG[name]
        srcs = sig["source"] if isinstance(sig["source"], list) else [sig["source"]]
        src = r["src"] or srcs[0]
        age = None if r["t"] is None else tick - r["t"]
        fs = feed_state[sig["feed"]]
        if sig["rate"] == "1 Hz":
            stale = age is not None and age > feeds[sig["feed"]]["stale_after_s"]
        elif sig["rate"] == "hourly":
            stale = age is not None and age > feeds[sig["feed"]]["stale_after_s"]
        else:
            stale = fs["stale"]
        assert stale == (r["sub"] is not None), f"{spec.name} {name}: stale {stale} but substituted {r['sub'] is not None}"
        conf = "substituted" if stale else ("assumed" if r["t"] is None else SOURCE_CONF[src])
        f = {"value": r["v"], "source": src, "age_s": age, "confidence": conf, "stale": stale}
        if r["since"] is not None:
            f["since_t_s"] = r["since"]
        if r["rep"] is not None:
            f["reported_t_s"] = r["rep"]
        if r["tr"]:
            f["transition"] = r["tr"]
        if r["sub"]:
            f["substituted"] = r["sub"]
        fields[name] = f

    # ---- effect fields: who holds them
    acts = {g: fields[f"{g}.activity"]["value"] for g in spec.installed}
    holders = {k: sorted(g for g, a in acts.items() if a != "none" and k in S["activities"][g][a]["effects"])
               for k in S["derivations"]["effects"]["idle"]}

    active_rules = {f["fault"] for f in spec.faults if f["state"] in FAULT_RULE_STATES}

    def conf_of(ref):
        if ref == "run.layered_water":
            return "assumed", None
        f = get(ref)
        return f["confidence"], f.get("substituted", {}).get("last_good_t_s")

    def inputs_of(sig):
        out = []
        for i in sig["inputs"]:
            if i.startswith("*."):
                out += [f"{g}.{i[2:]}" for g in spec.installed]
            else:
                out.append(i)
        return out

    def get(name):
        if name in fields:
            return fields[name]
        sig = SIG[name]
        d = spec.derived[name]
        ins = [conf_of(i) for i in inputs_of(sig)]
        if any(c == "substituted" for c, _ in ins):
            conf = "substituted"
        elif sig.get("confirm") in active_rules:
            conf = "confirmed"
        elif ins:
            conf = min((c for c, _ in ins), key=order.index)
        else:
            conf = "assumed"
        s = d["sub"]
        if conf == "substituted" and s is None:
            goods = [t for c, t in ins if c == "substituted" and t is not None]
            rule = sig["fallback"].get("rule", "computed from the inputs' fallbacks")
            s = sub(d["v"], min(goods) if goods else None, rule, stage="derived")
        assert (conf == "substituted") == (s is not None), f"{spec.name} {name}: confidence {conf}, substituted given"
        f = {"value": d["v"], "source": "derived", "age_s": 0, "confidence": conf, "stale": conf == "substituted"}
        if d["since"] is not None:
            f["since_t_s"] = d["since"]
        if s:
            f["substituted"] = s
        fields[name] = f
        return f

    for name in spec.derived:
        get(name)
    for k, gs in holders.items():
        fields[k]["by"] = gs

    # ---- the snapshot
    snap = {"run": {"contract": "argos-snapshot/2", "scenario": "scenario_b", "mission": spec.mission, "seed": 0,
                    "tick": tick, "t_ship_s": tick, "installed": spec.installed,
                    "constants": {k: {"value": v, "source": "scenario", "confidence": "assumed"} for k, v in spec.constants.items()}}}
    for g in ["plant", "ship_state", "environment", "links", "crew"]:
        snap[g] = {s["name"]: fields[s["name"]] for s in S["signals"] if s["group"] == g}
    snap["guests"] = {gid: {s["name"].split(".", 1)[1]: fields[s["name"]] for s in S["signals"]
                            if s["group"] == "guests" and s["name"].startswith(gid + ".")} for gid in spec.installed}
    snap["capacity"] = {s["name"]: fields[s["name"]] for s in S["signals"] if s["group"] == "capacity"}
    snap["feeds"] = feed_state
    snap["faults"] = spec.faults
    snap["events"] = spec.events
    snap["notes"] = spec.notes

    # ---- the frame: every reading that arrived on this tick
    frame = {"contract": "argos-frame/1", "tick": tick, "t_ship_s": tick, "signals": {}, "guests": {g: {} for g in spec.installed},
             "events": spec.events}
    for s in S["signals"]:
        name = s["name"]
        if name not in raw or raw[name]["t"] != tick:
            continue
        r = raw[name]
        reading = {"value": r["v"], "source": fields[name]["source"], "t_s": tick}
        if r["tr"]:
            reading["transition"] = r["tr"]
        if r["rep"] is not None:
            reading["reported_t_s"] = r["rep"]
        if s["group"] == "guests":
            gid, key = name.split(".", 1)
            frame["guests"][gid][key] = reading
        else:
            frame["signals"][name] = reading
    return r1(snap), r1(frame)


# ------------------------------------------------------------------------------------------------ Scenario B

def speed_line(t, t0, v0, v1, t_end, t_latest):
    """Linear A.6 change from v0 at t0 to v1 at t_end; a reading at t, with its transition while under way."""
    if t >= t_end:
        return R(v1, since=t_end)
    return R(round(v0 + (v1 - v0) * (t - t0) / (t_end - t0), 1), since=t,
             tr={"to": v1, "started_t_s": t0, "expected_end_t_s": t_end, "latest_end_t_s": t_latest})


def base(A) -> Spec:
    s = Spec("scenario_b_survey_m00", 0)
    heat = round(160 - (40 / 18) * (24 - 12), 1)
    s.raw = {
        "genset_1_relay_trip": R(False), "genset_2_relay_trip": R(False), "genset_1_kw": R(330.0), "genset_2_kw": R(325.0),
        "bus_frequency_hz": R(60.0),
        "chw_pump_1_running": R(True), "chw_pump_2_running": R(True), "chw_pump_1_alarm": R(False), "chw_pump_2_alarm": R(False),
        "chw_flow_pct": R(100.0), "chw_supply_c": R(7.0), "chw_return_c": R(12.0),
        "course": R("steady"), "speed_kn": R(3.0), "noise": R("quiet"), "situation": R("at_sea", src="scenario"),
        "deck_flight_deck": R("occupied"), "deck_bays": R("clear"), "ramp": R("free"), "deck_machinery": R(False),
        "deck_activity_since_sweep": R(True), "emission": R("normal"), "radar_transmitting": R(True),
        "seawater_c": R(24.0, t=0, src="scenario"), "sea_state": R(4, t=0, src="scenario"),
        "wind_kn": R(18.0), "wind_from_deg": R(300.0),
        "satcom_mbps": R(6.0), "los_radio_mbps": R(20.0),
        "crew_aboard": R(14), "people_available": R(4), "bridge_requests": R([]), "hlo_deck_report": R("none"),
        "hlo_wind_kn": R(None), "standing_plan": R("none"), "last_sweep": R(None),
        "G3.mode": R("standby"), "G3.activity": R("surveying", t=0, since=0), "G3.kw_actual": R(1.0),
        "G3.data_demand": R({"acoustic_kbps": 3}), "G3.leg_state": R("running", t=0, since=0), "G3.leg_started_t_s": R(0, t=0),
        "G3.leg_flown_s": R(0, t=0), "G3.hold_ack": R(False, t=0),
        "G4.mode": R("standby"), "G4.activity": R("airborne"), "G4.kw_actual": R(2.0), "G4.data_demand": R({"los_radio_mbps": 20}),
        "G4.battery_pct": R(None, t=None), "G4.range_km": R(12.0), "G4.launched_t_s": R(-3952, t=0),
        "G5.mode": R("full"), "G5.activity": R("transmitting"), "G5.kw_actual": R(45.0),
        "G5.data_demand": R({"satcom_mbps": 6, "backbone_mbps": 1000}),
    }
    s.derived = {
        "gensets_online": D(2), "tripped_genset": D("none"), "cooling_state": D("nominal"),
        "speed_band": D("slow"), "heading_free": D(False), "deck_machinery_permitted": D(False), "flight_deck_ops": D("free"),
        "acoustic_link_up": D(True, since=0), "acoustic_kbps": D(3.0), "deck_latched_clear": D(False),
        "G3.overdraw_pct": D(0.0), "G3.mode_ends_t_s": D(None),
        "G4.overdraw_pct": D(0.0), "G4.mode_ends_t_s": D(None), "G4.airborne_since_t_s": D(-3952),
        "G4.battery_crossing_t_s": D(None), "G4.land_by_t_s": D(-3952 + 90 * 60),
        "G5.overdraw_pct": D(0.0),
        "power": D(cap(250, "kW")), "port_line": D(cap(150, "kW")), "stbd_line": D(cap(150, "kW")),
        "heat": D(cap(heat, "kW")), "satcom": D(cap(6.0, "Mbit/s")), "los_radio": D(cap(20.0, "Mbit/s")),
        "acoustic": D(cap(3.0, "kbit/s")), "shed_ceiling_kw": D(round(min(250, heat) - 5, 1)),
    }
    return s


ACOUSTIC_DOWN = "acoustic link down: course free, noise manoeuvring"
TRIP = {"fault": "genset_trip", "subject": "genset_2", "state": "confirmed", "raw_event_t_s": 720, "confirmed_t_s": 721,
        "votes": ["relay_trip", "kw_near_zero"], "first_shed_due_t_s": 725, "full_sequence_due_t_s": 780,
        "healthy_since_t_s": None, "injected": False}
COOLING = {"fault": "cooling_degraded", "subject": "chw_pump_1", "state": "confirmed", "raw_event_t_s": 1140, "confirmed_t_s": 1141,
           "votes": ["pump_alarm", "pump_stopped", "flow_low", "delta_t_high"], "first_shed_due_t_s": 1145,
           "full_sequence_due_t_s": 1200, "healthy_since_t_s": None, "injected": True}


def after_minute_8(m8: Spec, name: str, tick: int, mission: str) -> Spec:
    """After D3's minute-8 decision (record seq 1): G3 told to hold (acked at 510), the bridge confirms at 540, the
    manoeuvre commands issued on snapshot 540 are applied at tick 541 (course free, noise manoeuvring, 3 to 5 kn,
    the deck cleared over the seed's 4 min)."""
    s = m8.copy(name, tick, mission)
    holds = "holding_depth" if mission == "survey" else "holding_at_sea"
    leg = "paused" if mission == "survey" else "aborted"
    s.raw.update({
        "G3.activity": R(holds, t=510, since=510), "G3.leg_state": R(leg, t=510, since=510), "G3.leg_started_t_s": R(0, t=510),
        "G3.leg_flown_s": R(480, t=510), "G3.hold_ack": R(True, t=510, since=510), "G3.data_demand": R({"acoustic_kbps": 1}),
        "course": R("free", since=541), "noise": R("manoeuvring", since=541),
        "speed_kn": speed_line(tick, 541, 3.0, 5.0, 661, 721),
        "bridge_requests": R([{"request_seq": 1, "rule": "R3", "state": "confirmed" if tick >= 540 else "pending",
                               "asked_t_s": 480, "answered_t_s": 540 if tick >= 540 else None}]),
    })
    if tick < 781:
        s.raw["deck_flight_deck"] = R("occupied", tr={"to": "clear", "started_t_s": 541, "expected_end_t_s": 781, "latest_end_t_s": 841})
    s.derived.update({
        "heading_free": D(True, since=510), "deck_machinery_permitted": D(True, since=510),
        "acoustic_link_up": D(False, since=541), "acoustic_kbps": D(0.0, since=541),
        "acoustic": D(cap(0.0, "kbit/s", [ACOUSTIC_DOWN], zero=True), since=541),
    })
    return s


def landed(s: Spec):
    """G4 landed at 1020 (seed g4_lands_at_min 17) and fast-charges until 2220; the R3 request closed at landing."""
    s.raw.update({
        "G4.mode": R("fast_charge", since=1020), "G4.activity": R("landed", since=1020), "G4.kw_actual": R(35.0, since=1020),
        "G4.data_demand": R({}), "G4.range_km": R(0.0, since=1020),
        "deck_flight_deck": R("occupied", since=1020), "bridge_requests": R([]),
        "genset_1_kw": R(420.0, since=1020),
    })
    s.derived.update({
        "G4.mode_ends_t_s": D(2220, since=1020), "G4.airborne_since_t_s": D(None, since=1020),
        "G4.battery_crossing_t_s": D(None, since=1020), "G4.land_by_t_s": D(None, since=1020),
        "flight_deck_ops": D("free", since=1020),
    })


def tripped(s: Spec):
    s.raw.update({"genset_2_relay_trip": R(True, since=720), "genset_2_kw": R(0.0, since=720),
                  "genset_1_kw": R(385.0, since=720), "bus_frequency_hz": R(59.6, since=720)})
    s.derived.update({"gensets_online": D(1, since=721), "tripped_genset": D("genset_2", since=721),
                      "power": D(cap(100, "kW", ["one genset down: genset_2 tripped, confirmed at 721 s"]), since=721),
                      "shed_ceiling_kw": D(95.0, since=721)})
    s.faults = [copy.deepcopy(TRIP)]


def cooling(s: Spec):
    s.raw.update({"chw_pump_1_running": R(False, since=1140), "chw_pump_1_alarm": R(True, since=1140),
                  "chw_flow_pct": R(50.0, since=1140), "chw_supply_c": R(8.5, since=1140), "chw_return_c": R(17.5, since=1140)})
    s.derived.update({"cooling_state": D("degraded", since=1141),
                      "heat": D(cap(80.0, "kW", ["cooling degraded: chilled-water pump 1 failed, one of two running (x0.6)"]), since=1141),
                      "shed_ceiling_kw": D(75.0, since=1141)})
    s.faults = [copy.deepcopy(TRIP), copy.deepcopy(COOLING)]


def specs(root: Path = ROOT) -> list[Spec]:
    A = yaml.safe_load((root / "config/assumptions.yaml").read_text())
    drain = A["rules"]["r3"]["drain_pct_min"]
    out = []

    m0 = base(A)
    m0.events = [{"t_s": 0, "type": "baseline", "origin": "timeline", "injected": False, "payload": {
        "note": "3 kn over the cable route, G3 on its 40-min leg on the acoustic link, G4 airborne, G5 full",
        "assumed": {"seed": 0, "sea_state": 4, "wind_kn": 18, "satcom_mbps": 6, "G4": {"launched_t_s": -3952}}}}]
    m0.notes = [
        "Scenario B, survey file, minute 0: 3 kn over the cable route, G3 on its 40-min leg on the acoustic link, G4 airborne at 2 kW, G5 full.",
        "G4 has sent no battery report yet (one report, at minute 8, as in the brief), so battery_pct is null and its land-by is the endurance bound: launched -3952 s + 90 min = 1448 s, confidence assumed.",
        "Assumed for this fixture (the baseline payload lists them): seed 0; sea state 4; wind 18 kn rising to 22 kn by minute 8 (the ship's anemometer); SATCOM 6 Mbit/s of 2-8; G4 launched at -3952 s, dated back from 18 % at minute 8 at rules.r3.drain_pct_min; genset kW and chilled-water temperatures are plausible, not from the brief.",
        "The flight deck starts occupied; the seed clears it in 4 min after the minute-8 confirmation (seed_pins.deck_clear_min).",
    ]
    out.append(m0)

    m8 = m0.copy("scenario_b_survey_m08", 480)
    cross = round(480 - (20 - 18) / drain * 60, 1)
    m8.raw.update({
        "G4.battery_pct": R(18.0, t=480, since=480), "G4.range_km": R(11.0), "wind_kn": R(22.0),
        "G3.activity": R("surveying", t=480, since=0), "G3.leg_state": R("running", t=480, since=0),
        "G3.leg_started_t_s": R(0, t=480), "G3.leg_flown_s": R(480, t=480), "G3.hold_ack": R(False, t=480),
    })
    m8.derived.update({"G4.battery_crossing_t_s": D(cross, since=480), "G4.land_by_t_s": D(round(cross + 720, 1), since=480)})
    m8.events = [{"t_s": 480, "type": "guest_report", "origin": "timeline", "injected": False,
                  "payload": {"guest": "G4", "fields": {"battery_pct": 18}}}]
    m8.notes = [
        "Scenario B, survey file, minute 8: G4 reports 18 % battery. This is D3's input, before the decision: the ship is still at 3 kn, steady and quiet.",
        f"G4's land-by: the 20 % crossing is dated back at {drain} %/min to {cross} s (minute 6.2), plus 12 min = {round(cross + 720, 1)} s (minute 18.2), earlier than the endurance bound 1448 s (docs/EXPECTED_OUTCOMES.md minute 8).",
        "scenario_b.yaml puts wind_kn 22 on G4's report; here it is the ship's anemometer reading, and the report carries the battery only.",
    ]
    out.append(m8)

    c0 = m8.copy("scenario_b_survey_m08_crew0")
    c0.raw.update({"crew_aboard": R(0), "people_available": R(0), "last_sweep": R({"t_s": -4200, "result": "clear"}),
                   "deck_activity_since_sweep": R(False), "deck_flight_deck": R("clear")})
    c0.derived.update({"deck_latched_clear": D(True)})
    c0.events = copy.deepcopy(m8.events)
    c0.notes = [
        "Scenario B at minute 8 with 0 aboard (DEMO_SCRIPT Scenario C segment, +11): rule R3 reads the deck latched at the last crew sweep.",
        "The crew swept the deck clear at -4200 s and left; G4's launch at -3952 s is its own and does not count (rules.r3.latched_deck), so deck_activity_since_sweep is false and deck_latched_clear is true: recovery is automatic, with no confirm button.",
    ]
    out.append(c0)

    m9 = after_minute_8(m8, "scenario_b_survey_m09_stale_g4_telemetry", 560, "survey")
    m9_rule = "the earliest 20 % crossing the last report allows (derivations.g4_land_by.stale_rule): 18 % is below 20 %, so the crossing stays dated back to 371.9 s and land-by stays 1091.9 s"
    m9.raw.update({
        "G4.activity": R("airborne", t=545, sub=sub("airborne", 545, "the last value; airborne because the last value was airborne")),
        "G4.range_km": R(None, t=545, sub=sub(10.0, 545, "unknown: taken beyond 20 km, so the radio is at its 1 Mbit/s floor")),
        "G4.battery_pct": R(18.0, t=480, since=480, sub=sub(18.0, 480, m9_rule)),
        "G4.launched_t_s": R(-3952, t=0, sub=sub(-3952, 0, "keeps the last value")),
    })
    m9.derived.update({"los_radio": D(cap(1.0, "Mbit/s", ["G4 range unknown (telemetry stale): radio at its 1 Mbit/s floor"]),
                                      sub=sub(cap(20.0, "Mbit/s"), 545, "computed from the inputs' fallbacks", "derived"))})
    m9.drops = {"g4_telemetry": {"event_t_s": 546, "until_t_s": None, "injected": True}}
    m9.notes = [
        "Scenario B, survey file, 560 s, INJECTED feed drop (DEMO_SCRIPT 'Data feed drops'): G4's telemetry last arrived at 545 s; at 560 s its heartbeat is 15 s old, over R3's 10 s.",
        "G4's battery report (480 s, 80 s old) is stale with its feed, not by its own age. Its fallback is " + m9_rule + ". The decision sentence names the stale feed.",
        "G4's activity keeps its last value, airborne, substituted; its range is unknown, so the radio counts at its 1 Mbit/s floor. Every field derived from G4's activity is substituted with it.",
        "The bridge confirmed the recovery at 540 s (request seq 1, the minute-8 D3 record); the manoeuvre commands from snapshot 540 were applied at 541 s.",
    ]
    out.append(m9)

    m10 = after_minute_8(m8, "scenario_b_survey_m10_stale_genset_feed", 600, "survey")
    pms_rule = "casts no vote; a pending trip is held; gensets_online falls back instead"
    for k, v in [("genset_1_relay_trip", False), ("genset_2_relay_trip", False), ("genset_1_kw", 330.0), ("genset_2_kw", 325.0), ("bus_frequency_hz", 60.0)]:
        m10.raw[k] = R(v, t=596, sub=sub(v, 596, pms_rule))
    scope = "admission and arming the D4 ladder only; D4 never acts on a substituted value"
    m10.raw["G4.range_km"] = R(9.0)
    m10.derived.update({
        "gensets_online": D(1, sub=sub(2, 596, "one genset down", "derived", scope)),
        "tripped_genset": D("none", sub=sub("none", 596, "keeps the last confirmed value", "derived")),
        "power": D(cap(100, "kW", ["genset feed stale: taken as one genset down for admission and the armed ladder; D4 does not act on it"]),
                   sub=sub(cap(250, "kW"), 596, "computed from the inputs' fallbacks", "derived", scope)),
        "shed_ceiling_kw": D(95.0, sub=sub(128.3, 596, "computed from the inputs' fallbacks", "derived", scope)),
    })
    m10.drops = {"pms": {"event_t_s": 597, "until_t_s": None, "injected": True}}
    m10.notes = [
        "Scenario B, survey file, minute 10, INJECTED feed drop: the power management feed (relay flags, genset kW, bus frequency) last arrived at 596 s; at 600 s it is 4 s old, over the 3 s limit.",
        "gensets_online falls to 1 for admission and the armed ladder only. No fault is confirmed and no input is fresh, so D4 does not shed. The decision sentence names the stale feed. The fallback lifts after 3 fresh frames.",
        "G4's battery report is 120 s old on a healthy telemetry feed: not stale, confidence reported, and the minute-18.2 deadline stands.",
        "G3 last spoke at 510 s (hold acknowledged); the acoustic link has been down by design since 541 s, so G3's reports are old but not stale.",
    ]
    out.append(m10)

    m12 = after_minute_8(m8, "scenario_b_survey_m12", 721, "survey")
    tripped(m12)
    m12.raw.update({"G4.range_km": R(6.0), "wind_kn": R(23.0)})
    m12.notes = [
        "Scenario B, survey file, minute 12: genset 2 trips at 720 s (relay flag, kW to zero, the bus held at 59.6 Hz: fault_signatures.genset_trip). Relay and kW hold for 1 s, so the trip is confirmed at 721 s, this tick; D4's first shed would be applied at 722 s, inside the 725 s due time.",
        "G4 is airborne at 2 kW with no reservation (DEC-40): the ledger's load is 48 kW against a 95 kW ceiling, so the trip holds with 0 steps (tests/oracles minute_12_as_decided).",
        "The ship reached 5 kn at 661 s (one setting inside the slow band, no band change) and the deck is being cleared (541 s to 781 s, seed 4 min); G3 has held depth since its ack at 510 s and is out of acoustic contact.",
    ]
    out.append(m12)

    m19 = after_minute_8(m8, "scenario_b_survey_m19", 1141, "survey")
    tripped(m19)
    landed(m19)
    cooling(m19)
    m19.raw.update({
        "course": R("free", since=541, tr={"to": "steady", "started_t_s": 1081, "expected_end_t_s": 1201, "latest_end_t_s": 1261}),
        "speed_kn": speed_line(1141, 1081, 5.0, 3.0, 1201, 1261),
        "noise": R("normal", since=1081), "wind_kn": R(22.0),
    })
    m19.derived["acoustic"] = D(cap(0.0, "kbit/s", ["acoustic link down: course free (settling to steady), noise normal"], zero=True), since=541)
    m19.notes = [
        "Scenario B, survey file, minute 19: INJECTED fault. Chilled-water pump 1 fails at 1140 s, 2 min after G4 landed (scenario_b cooling_degraded trigger); alarm, pump stopped, low flow and high delta-T hold 1 s, confirmed at 1141 s. One pump running: cooling x0.6.",
        "Heat 133.3 x 0.6 = 80 kW, ceiling min(100, 80) - 5 = 75 kW against the ledger's 81 kW (G3 1 + G4 35 fast charge + G5 45): cooling binds, 6 kW over (docs/EXPECTED_OUTCOMES.md, Scenario B as decided).",
        "G4 landed at 1020 s and fast-charges until 2220 s; its last battery report is still the 18 % of minute 8. The commands after securing G4 (snapshot 1080) took effect at 1081 s: the ship slows back to 3 kn and settles its course to resume the survey. The genset is still down (restart at minute 24 is optional).",
    ]
    out.append(m19)

    sar12 = after_minute_8(m8, "scenario_b_sar_m12", 721, "sar")
    tripped(sar12)
    sar12.raw.update({"G4.range_km": R(6.0), "wind_kn": R(23.0)})
    sar12.notes = [
        "Scenario B, sar file, minute 12: the ship state is the survey run's; G3's leg was aborted at minute 8 and it holds at sea (acked at 510 s).",
        "G4 is airborne at 2 kW. Its 35 kW fast charge is reserved from minute 8 (DEC-40); the reservation is in the decision log, not the snapshot, and the ledger counts max(2, 35) = 35: 1 + 35 + 45 = 81 kW against 95, 14 spare, 0 steps (tests/oracles minute_12_as_decided.sar).",
    ]
    out.append(sar12)

    sar19 = after_minute_8(m8, "scenario_b_sar_m19", 1141, "sar")
    tripped(sar19)
    landed(sar19)
    cooling(sar19)
    sar19.raw.update({"wind_kn": R(22.0)})
    sar19.notes = [
        "Scenario B, sar file, minute 19: the injected pump fault as in the survey run. G3 still holds at sea, to be recovered over the ramp once the flight deck is done; the ship stays at 5 kn with its course free.",
        "Ledger 81 kW against a 75 kW ceiling; D4's commands from this snapshot are applied at 1142 s: sar takes G5 to 8 kW (44 kW), per scenario_b provenance.",
    ]
    out.append(sar19)
    return out


def build(root: Path = ROOT) -> dict:
    S, SIG = load(root)
    files = {}
    for spec in specs(root):
        snap, frame = assemble(spec, S, SIG)
        files[f"tests/fixtures/snapshots/{spec.name}.json"] = snap
        files[f"tests/fixtures/frames/{spec.name}.json"] = frame
    return files


def render(obj) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    for rel, obj in build().items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(obj))
    return 0


if __name__ == "__main__":
    sys.exit(main())
