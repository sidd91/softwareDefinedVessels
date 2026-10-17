"""Screen view models built from one replay moment (snapshot plus records) and the engine's inputs.

Every number on the screen is computed here from the snapshot, the records, the cards and config/assumptions.yaml,
so tests can hold the screen to docs/EXPECTED_OUTCOMES.md. The browser only renders these dicts.

A record's commands take effect at its applies_at_tick. The fixtures hold the snapshot a decision read, not the
next one, so the guest modes a record changed are shown from that tick on (a live run's next snapshot carries them).
"""
from __future__ import annotations

import copy
import time

from sdv import admission as Ad
from sdv import ledger as Lg
from sdv import loader as Ld
from sdv import placement as Pl
from sdv import records as Rec
from sdv.ui.data import END_T_S, Inputs, Moment

MISSION_NAMES = {"survey": "SURVEY", "sar": "RESCUE", "patrol": "PATROL", "disaster_relief": "DISASTER RELIEF"}
SHORT = {"G1": "RF SENSOR", "G2": "OCEAN MODULE", "G3": "SEABED VEH", "G4": "UAV", "G5": "COMMS NODE", "G6": "DESAL UNIT"}
SLOTS = {"bay1": "BAY 1", "bay1_half": "BAY 1 HALF", "bay2": "BAY 2", "flight_deck": "FD", "mast_free": "MAST",
         "hangar_roof": "HANGAR ROOF", "stern_ramp": "RAMP", None: "--"}
SUBJECTS = {"genset_1": "GEN 1", "genset_2": "GEN 2", "chw_pump_1": "CHW P1", "chw_pump_2": "CHW P2"}
ACTIVITY_POS = {"surveying": "DEPTH", "holding_depth": "DEPTH", "holding_at_sea": "AT SEA", "airborne": "AIR", "recovering": "AIR"}
HOLDS = {"depth": "holding_depth", "at_sea": "holding_at_sea"}
CLASS_NAMES = {"heat": "COOLING CHW", "power": "POWER"}
SIGNAL_NAMES = {"speed_kn": "SPEED", "deck_machinery": "DECK MACHINERY", "heading_free": "HEADING", "noise": "NOISE",
                "course": "COURSE", "deck_flight_deck": "FLIGHT DECK", "ramp": "RAMP", "emission": "EMISSION"}
CEILING_S = {"D1": 30.0, "D2": 30.0, "D3": 2.0, "D4": 5.0, "D5": 2.0}
TIER_NAMES = {"vessel_critical": "VESSEL CRITICAL", "mission_critical": "MISSION CRITICAL", "mission_support": "MISSION SUPPORT",
              "discretionary": "DISCRETIONARY"}


# ------------------------------------------------------------------------------------------- formatting

def f1(x: float) -> str:
    return f"{x:.1f}"


def f3(x: float) -> str:
    return f"{x:.3f}"


def kw(x: float) -> str:
    """Whole kilowatts as an operator writes them on a mode line: 35, 1.5."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def clock(t: float) -> str:
    t = int(round(t))
    sign = "-" if t < 0 else ""
    t = abs(t)
    return f"{sign}{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def words(s: str) -> str:
    return str(s).replace("_", " ").upper()


def mission_name(mission: str, profile: dict | None = None) -> str:
    if mission in MISSION_NAMES:
        return MISSION_NAMES[mission]
    return (profile or {}).get("name", "").upper() or words(mission)


def _file(I: Inputs, m: Moment) -> dict:
    """The priority file in force: the live run's (a profile applied at sea included), else the loaded one."""
    return m.profile or I.missions.get(m.mission) or {"id": m.mission, "name": m.mission, "weights": {}, "mission_critical": []}


# ------------------------------------------------------------------------------------------- ship state

def guest_states(I: Inputs, m: Moment) -> tuple[dict, dict]:
    """Per guest: mode, activity, committed kW and capability, with every applied record's commands taken in."""
    snap = m.snapshot
    tick = snap["run"]["tick"]
    gs = {}
    for g, b in snap["guests"].items():
        fresh = not b["kw_actual"].get("stale") and b["kw_actual"].get("confidence") != "substituted"
        gs[g] = {"mode": b["mode"]["value"], "activity": b["activity"]["value"],
                 "kw_actual": b["kw_actual"]["value"] if fresh else None, "applied": None}
    reserved: dict[str, float] = {}
    for r in m.records:
        if r.get("applies_at_tick", r["tick"] + 1) > m.t_s:
            continue
        reserved.update(r.get("reserved") or {})
        if r["tick"] < tick:
            continue  # the snapshot already carries it
        if r["kind"] == "D4":
            for step in r.get("steps") or []:
                if step["guest"] in gs:
                    gs[step["guest"]].update(mode=step["to_mode"], kw_actual=None, applied=r["seq"])
        elif r["kind"] == "D3":
            loser = r["cost_to_loser"]
            if loser["guest"] in gs:
                gs[loser["guest"]]["activity"] = HOLDS.get(loser.get("holds"), gs[loser["guest"]]["activity"])
    for g, s in gs.items():
        s["kw"] = Lg.committed_kw(I.cards, g, s["mode"], reserved.get(g, 0.0), s["kw_actual"])
        s["reserved_kw"] = reserved.get(g)
        s["capability"] = Lg.mode_of(I.cards[g], s["mode"])["capability_retained"]
    return gs, reserved


def plant_lines(I: Inputs, m: Moment, gs: dict) -> dict:
    cap = {k: v["value"] for k, v in m.snapshot["capacity"].items()}
    headroom = I.A["power"]["shed_headroom_kw"]
    power, heat = cap["power"], cap["heat"]
    load = sum(s["kw"] for s in gs.values())
    chilled = sum(s["kw"] for g, s in gs.items() if I.cards[g]["cooling"] == "chilled_water")
    sw = m.snapshot["environment"]["seawater_c"]["value"]
    nominal_heat = Lg.heat_capacity_kw(I.A, sw)
    return {
        "power_cap": power["capacity"], "heat_cap": heat["capacity"], "heat_nominal": nominal_heat,
        "power_degraded": bool(power["degraded_by"]), "heat_degraded": bool(heat["degraded_by"]),
        "power_limit": power["capacity"] - headroom, "heat_limit": heat["capacity"] - headroom, "headroom": headroom,
        "ceiling": cap["shed_ceiling_kw"], "binds": "heat" if heat["capacity"] <= power["capacity"] else "power",
        "load": load, "chilled": chilled, "seawater_c": sw, "cap": cap,
    }


def _faults(snap: dict) -> list[dict]:
    return [f for f in snap.get("faults", []) if f["state"] == "confirmed"]


def _injected_subjects(snap: dict) -> set:
    return {f["subject"] for f in _faults(snap) if f.get("injected")}


def _value(snap: dict, group: str, name: str):
    return snap[group][name]["value"]


def _latest(records: list, kinds=("D3", "D4", "D5")) -> dict | None:
    rs = [r for r in records if r["kind"] in kinds]
    return max(rs, key=lambda r: (r["tick"], r["seq"])) if rs else None


def _acting(records: list, kinds=("D3", "D4")) -> dict | None:
    """The decision the panel shows: the latest D3 or D4, except that a D4 recheck after a shed on the same fault
    (the 19:02 hold after the 19:01 shed) leaves the shed on show, since that is the decision the fault caused."""
    r = _latest(records, kinds)
    if r and r["kind"] == "D4" and r["verdict"] != "shed" and r.get("raw_event_t_s") is not None:
        shed = [x for x in records if x["kind"] == "D4" and x["verdict"] == "shed" and x.get("raw_event_t_s") == r["raw_event_t_s"]]
        if shed:
            return max(shed, key=lambda x: (x["tick"], x["seq"]))
    return r


# ------------------------------------------------------------------------------------------- header and chips

def header(I: Inputs, m: Moment, pl: dict) -> dict:
    snap = m.snapshot
    ss = snap["ship_state"]
    crew = _value(snap, "crew", "crew_aboard")
    policy = I.A["rules"]["r3"]["confirm"].get(crew, "")
    speed = ss["speed_kn"]
    sp = f"{f1(speed['value'])} kn"
    if "transition" in speed:
        sp += f" → {f1(speed['transition']['to'])}"
    alarms = _faults(snap)
    builtin = m.mission in I.missions and I.missions[m.mission] == _file(I, m)
    return {
        "mission": mission_name(m.mission, _file(I, m)), "mission_id": m.mission,
        "priority_file": f"{m.mission}.yaml" if builtin else f"{m.mission} · AT SEA",
        "standby": None if m.standby is None else ("IN STEP" if m.standby == "in step" else "OUT OF STEP"),
        "source": m.source,
        "crew": f"CREW {crew}", "crew_policy": words(policy), "sea": f"SW {f1(pl['seawater_c'])} °C",
        "sea_state": f"SEA STATE {_value(snap, 'environment', 'sea_state')}", "speed": f"SPEED {sp}",
        "alarms": len(alarms), "clock": "T+" + clock(m.t_s), "t_s": m.t_s, "end_t_s": END_T_S,
    }


def _transition(field: dict, fmt=words) -> str:
    v = fmt(field["value"])
    if "transition" in field:
        v += " → " + fmt(field["transition"]["to"])
    return v


def ship_state(m: Moment) -> list[dict]:
    ss = m.snapshot["ship_state"]
    env = m.snapshot["environment"]
    chips = [
        ("COURSE", _transition(ss["course"])),
        ("SPEED", _transition(ss["speed_kn"], lambda v: f"{f1(v)} kn") + " · " + words(ss["speed_band"]["value"])),
        ("NOISE", _transition(ss["noise"])),
        ("DECK", "FD " + _transition(ss["deck_flight_deck"])),
        ("RAMP", _transition(ss["ramp"])),
        ("EMISSION", _transition(ss["emission"])),
        ("WIND", f"{f1(env['wind_kn']['value'])} kn"),
    ]
    return [{"k": k, "v": v, "moving": "→" in v} for k, v in chips]


# ------------------------------------------------------------------------------------------- mimic, plant, guests

def _placement(I: Inputs, guests: list[str]) -> dict:
    """D2's placement of the guests aboard; the cards do not change during a replay, so it is computed once per set."""
    cache = I.__dict__.setdefault("_placement_cache", {})
    key = tuple(guests)
    if key not in cache:
        cache[key] = Pl.place(I.A, I.cards, guests)
    return cache[key]


def _pos(I: Inputs, g: str, s: dict, placement: dict) -> str:
    if s["activity"] in ACTIVITY_POS:
        return ACTIVITY_POS[s["activity"]]
    first = I.cards[g]["placement"]["parts"][0]["name"]
    return SLOTS.get(placement.get(f"{g}.{first}"), "--")


def _drawing_kw(s: dict) -> float:
    """What the guest draws now; a reservation counts in the ledger but is shown beside the draw."""
    return s["kw"] if not _reserved_only(s) else (s["kw_actual"] if s["kw_actual"] is not None else s["kw"])


def _reserved_only(s: dict) -> bool:
    return bool(s.get("reserved_kw")) and s["reserved_kw"] > (s["kw_actual"] or 0)


def _mode_line(g: str, s: dict) -> str:
    line = f"{words(s['mode'])} {kw(_drawing_kw(s))} kW"
    if _reserved_only(s):
        line += f" · RSV {kw(s['reserved_kw'])}"
    return line


def mimic(I: Inputs, m: Moment, gs: dict, hot: set) -> dict:
    snap = m.snapshot
    guests = list(gs)
    placement = _placement(I, guests)
    by_slot: dict[str, list] = {}
    for key, slot in placement.items():
        by_slot.setdefault(slot, []).append(key)
    zones = []
    for slot, label in (("flight_deck", "FD · HANGAR"), ("bay1", "BAY 1"), ("bay2", "BAY 2")):
        keys = by_slot.get(slot, []) + (by_slot.get("bay1_half", []) if slot == "bay1" else [])
        owners = sorted({k.split(".")[0] for k in keys})
        if not owners:
            zones.append({"zone": label, "guest": "FREE", "mode": "", "extra": "", "hot": False})
            continue
        g = owners[0]
        s = gs[g]
        extra = ""
        if g == "G4":
            b = snap["guests"]["G4"]
            batt = b.get("battery_pct", {}).get("value")
            land_by = b.get("land_by_t_s", {}).get("value")
            parts = [words(s["activity"])]
            if batt is not None and s["activity"] in ("airborne", "recovering"):
                parts.append(f"BATT {batt:.0f} %")
            if land_by is not None and s["activity"] in ("airborne", "recovering"):
                parts.append(f"LAND BY {clock(land_by)} · T-{clock(max(0, land_by - m.t_s))[3:]}")
            extra = " · ".join(parts)
        elif g == "G3":
            extra = {"holding_depth": "VEHICLE AT DEPTH · HOLD", "surveying": "VEHICLE AT DEPTH · SURVEY",
                     "holding_at_sea": "VEHICLE AT SEA · HOLD"}.get(s["activity"], words(s["activity"]))
        else:
            extra = words(s["activity"])
        zones.append({"zone": label, "guest": f"{g} {SHORT.get(g, '')}".strip(), "mode": _mode_line(g, s), "extra": extra,
                      "hot": g in hot})
    mast_used = len(I.A["positions"]["mast_occupied"]) + len(by_slot.get("mast_free", []))
    mast_guests = " ".join(sorted({k.split(".")[0] + " ANT" for k in by_slot.get("mast_free", [])}))
    zones.append({"zone": "MAST", "guest": mast_guests or "FREE", "mode": f"{len(I.A['positions']['mast_occupied'])} HOST + "
                  f"{len(by_slot.get('mast_free', []))}", "extra": f"{mast_used} / 3", "hot": False})
    ramp = snap["ship_state"]["ramp"]["value"]
    return {"ramp": words(ramp), "zones": zones}


def plant(I: Inputs, m: Moment, pl: dict) -> list[dict]:
    p = m.snapshot["plant"]
    inj = _injected_subjects(m.snapshot)

    def pump(n):
        if p[f"chw_pump_{n}_running"]["value"]:
            return "RUN"
        return "TRIP" if p[f"chw_pump_{n}_alarm"]["value"] else "OFF"

    cells = [
        {"tag": "GEN 1", "state": "TRIP" if p["genset_1_relay_trip"]["value"] else "RUN", "subject": "genset_1"},
        {"tag": "GEN 2", "state": "TRIP" if p["genset_2_relay_trip"]["value"] else "RUN", "subject": "genset_2"},
        {"tag": "CHW P1", "state": pump(1), "subject": "chw_pump_1"},
        {"tag": "CHW P2", "state": pump(2), "subject": "chw_pump_2"},
        {"tag": "CHW CAP", "state": f"{f1(pl['heat_cap'])} kW", "subject": None},
        {"tag": "SHORE", "state": "ON" if _value(m.snapshot, "ship_state", "situation") == "alongside" else "OFF", "subject": None},
    ]
    for c in cells:
        c["trip"] = c["state"] == "TRIP"
        c["injected"] = c.pop("subject") in inj
    return cells


def guest_rows(I: Inputs, m: Moment, gs: dict) -> list[dict]:
    placement = _placement(I, list(gs))
    file = _file(I, m)
    out = []
    for g, s in gs.items():
        out.append({"id": g, "pos": _pos(I, g, s, placement), "mode": words(s["mode"]) + (f" · RSV {kw(s['reserved_kw'])}" if _reserved_only(s) else ""),
                    "kw": kw(_drawing_kw(s)),
                    "cap": f"{s['capability'] * 100:.0f} %", "rsv": f"{kw(s['reserved_kw'])} kW" if s.get("reserved_kw") else "",
                    "activity": words(s["activity"]), "tier": TIER_NAMES[Lg.tier_of(I.cards, g, file)]})
    return out


# ------------------------------------------------------------------------------------------- tiles and ledger

def _status(cls: str, pl: dict) -> str:
    degraded = pl[f"{cls}_degraded"]
    limit = pl[f"{cls}_limit"]
    used = pl["load"] if cls == "power" else pl["chilled"]
    if degraded and pl["binds"] == cls:
        return "LIMITING"
    if used > limit:
        return "OVER"
    if degraded:
        return "DEGRADED"
    if limit - used < 0.1 * limit:
        return "NEAR LIMIT"
    return "NORMAL"


def _data_lines(I: Inputs, m: Moment) -> dict:
    snap = m.snapshot
    cap = {k: v["value"] for k, v in snap["capacity"].items()}
    demand: dict[str, float] = {}
    for b in snap["guests"].values():
        for k, v in (b.get("data_demand", {}).get("value") or {}).items():
            demand[k] = demand.get(k, 0) + v
    out = {}
    for link, key, unit in (("satcom", "satcom_mbps", "Mbit/s"), ("los_radio", "los_radio_mbps", "Mbit/s"), ("acoustic", "acoustic_kbps", "kbit/s")):
        c = cap[link]
        d = demand.get(key, 0)
        state = "NORMAL" if d <= c["capacity"] else "OVER"
        if c["zero_by_rule"]:
            state = "DOWN"
        out[link] = {"capacity": c["capacity"], "demand": d, "unit": unit, "state": state, "degraded_by": c["degraded_by"]}
    return out


def _mass(I: Inputs, guests: list[str]) -> dict:
    return Lg.admission_lines(I.A, I.cards, guests, _placement(I, guests))


def _compute(I: Inputs, guests: list[str]) -> tuple[int, int, dict]:
    c = I.A["compute"]
    total = int(c["nodes"] * c["cores_per_node"] * c["guest_share"])
    per = {g: I.cards[g]["consumes"].get("compute_cores", {}).get("nominal", 0) for g in guests}
    return sum(per.values()), total, per


def _deck(I: Inputs, m: Moment, guests: list[str]) -> tuple[int, int, list[str]]:
    placement = _placement(I, guests)
    used = {"bay1" if s == "bay1_half" else s for s in placement.values()} & {"bay1", "bay2", "flight_deck"}
    names = [SLOTS[s] for s in ("bay1", "bay2", "flight_deck") if s in used]
    if _value(m.snapshot, "ship_state", "ramp") != "free":
        names.append("RAMP")
    return len(names), 4, names


def _response(r: dict | None, timing: dict | None = None) -> tuple[float | None, float, str]:
    """Seconds against the decision's ceiling: the decision time from the timing log when the run has one,
    otherwise ship time from the raw event to the tick the first command applies."""
    if not r:
        return None, CEILING_S["D4"], "D4 FIRST ACTION"
    ceil = r["ceiling_ms"] / 1000 if r.get("ceiling_ms") else CEILING_S.get(r["kind"], 5.0)
    name = {"D3": "D3 RIGHT OF WAY", "D4": "D4 FIRST ACTION", "D5": "D5 CREW POLICY"}.get(r["kind"], r["kind"])
    if timing and r["seq"] in timing:
        return timing[r["seq"]] / 1000, ceil, name + " · COMPUTE"
    start = r.get("raw_event_t_s") if r.get("raw_event_t_s") is not None else r["t_s"]
    return r.get("applies_at_tick", r["tick"] + 1) - start, ceil, name + " · SHIP TIME"


def resp_text(resp: float | None, ceil: float) -> str:
    if resp is None:
        return f"-- / {f1(ceil)} s"
    return f"{resp * 1000:.2f} ms / {f1(ceil)} s" if resp < 0.1 else f"{f1(resp)} / {f1(ceil)} s"


def tiles(I: Inputs, m: Moment, gs: dict, pl: dict) -> list[dict]:
    guests = list(gs)
    snap = m.snapshot
    inj = _injected_subjects(snap)
    lines = _mass(I, guests)
    mass, stab = lines["mass"], lines["stability"]
    data = _data_lines(I, m)
    used_cores, total_cores, per_cores = _compute(I, guests)
    deck_used, deck_total, deck_names = _deck(I, m, guests)
    mast_free = sum(1 for s in _placement(I, guests).values() if s == "mast_free")
    mast_host = len(I.A["positions"]["mast_occupied"])
    p = snap["plant"]
    pumps = sum(1 for n in (1, 2) if p[f"chw_pump_{n}_running"]["value"])
    tripped = [SUBJECTS[f"genset_{n}"] for n in (1, 2) if p[f"genset_{n}_relay_trip"]["value"]]
    resp, ceil, resp_label = _response(_acting(m.records), m.timing)

    chw_sub = f"{2 - pumps} OF 2 PUMPS DOWN" if pumps < 2 else f"2 PUMPS · SW {pl['seawater_c']:.0f} °C"
    if pumps < 2:
        chw_sub = "P1 TRIP · 1 OF 2 PUMPS" if not p["chw_pump_1_running"]["value"] else "P2 TRIP · 1 OF 2 PUMPS"
    if pl["binds"] == "heat" and pl["power_cap"] > pl["heat_cap"] and pl["heat_degraded"]:
        usable = pl["ceiling"] - pl["load"]
        power_sub = f"USABLE {f1(usable)} kW · CHW BINDS" if usable >= 0 else f"CHW {f1(-usable)} kW OVER LIMIT"
    elif tripped:
        power_sub = f"{' '.join(tripped)} TRIP · {pl['power_cap']:.0f} kW"
    else:
        power_sub = f"2 GEN · {pl['power_cap']:.0f} kW"

    sat, los = data["satcom"], data["los_radio"]
    data_state = "NORMAL" if sat["state"] == "NORMAL" and los["state"] == "NORMAL" else "REDUCED"
    data_sub = f"LOS {los['demand']:.0f} / {los['capacity']:.0f}"
    if data["acoustic"]["state"] == "DOWN":
        data_sub += " · ACOUSTIC DOWN"

    def bar(used, top, limit=None):
        return {"pct": _pct(used, top), "mark": None if limit is None else _pct(limit, top)}

    return [
        {"name": "COOLING CHW", "value": f"{f1(pl['chilled'])} / {f1(pl['heat_limit'])} kW", "sub": chw_sub,
         "state": _status("heat", pl), "injected": "chw_pump_1" in inj or "chw_pump_2" in inj,
         **bar(pl["chilled"], pl["heat_cap"], pl["heat_limit"])},
        {"name": "POWER", "value": f"{f1(pl['load'])} / {f1(pl['power_limit'])} kW", "sub": power_sub,
         "state": _status("power", pl), **bar(pl["load"], pl["power_cap"], pl["power_limit"])},
        {"name": "DECK", "value": f"{deck_used} / {deck_total}", "sub": " · ".join(deck_names) or "ALL FREE",
         "state": "FULL" if deck_used >= deck_total else "NORMAL", **bar(deck_used, deck_total)},
        {"name": "MAST", "value": f"{mast_host + mast_free} / 3", "sub": f"{mast_host} HOST" + (" · G5 ANT" if mast_free else ""),
         "state": "FULL" if mast_host + mast_free >= 3 else "NORMAL", **bar(mast_host + mast_free, 3)},
        {"name": "MASS / STAB", "value": f"{f3(mass.demand)} / {f3(mass.capacity)} t", "sub": f"STAB {f3(stab.demand)} / {f3(stab.capacity)}",
         "state": "OVER" if mass.over or stab.over else ("NEAR LIMIT" if mass.free < 0.1 * mass.capacity else "NORMAL"),
         **bar(mass.demand, mass.capacity, mass.capacity)},
        {"name": "DATA LINKS", "value": f"{f1(sat['demand'])} / {f1(sat['capacity'])} Mbit/s", "sub": "SATCOM · " + data_sub,
         "state": data_state, **bar(sat["demand"], sat["capacity"])},
        {"name": "COMPUTE", "value": f"{used_cores} / {total_cores} cores",
         "sub": " · ".join(f"{g} {n}" for g, n in per_cores.items() if n) or "NONE", "state": "NORMAL", **bar(used_cores, total_cores)},
        {"name": "RESPONSE", "value": resp_text(resp, ceil), "sub": resp_label,
         "state": "NORMAL" if resp is None or resp <= ceil else "LATE", **bar(resp or 0, ceil)},
    ]


def _pct(v: float, top: float) -> int:
    return max(0, min(100, round(v / top * 100))) if top else 0


def ledger_rows(I: Inputs, m: Moment, gs: dict, pl: dict) -> list[dict]:
    guests = list(gs)
    lines = _mass(I, guests)
    data = _data_lines(I, m)
    used_cores, total_cores, _ = _compute(I, guests)
    deck_used, deck_total, deck_names = _deck(I, m, guests)
    placement = _placement(I, guests)
    mast_free = sum(1 for s in placement.values() if s == "mast_free")
    resp, ceil, _ = _response(_acting(m.records, ("D4",)), m.timing)
    side = {}
    for g, s in gs.items():
        slot = placement.get(f"{g}.{I.cards[g]['placement']['parts'][0]['name']}")
        position = "bay1" if slot == "bay1_half" else slot
        line = I.A["positions"].get(position, {}).get("power_line")
        side[line] = side.get(line, 0) + s["kw"]
    rows = [
        ("COOLING CHW", f"{f1(pl['heat_cap'])} kW", f"{f1(pl['heat_limit'])} kW", f"{f1(pl['chilled'])} kW",
         f"{f1(pl['heat_limit'] - pl['chilled'])} kW", _status("heat", pl)),
        ("POWER", f"{f1(pl['power_cap'])} kW", f"{f1(pl['power_limit'])} kW", f"{f1(pl['load'])} kW",
         f"{f1(pl['power_limit'] - pl['load'])} kW", _status("power", pl)),
    ]
    for key, name in (("port", "PORT LINE"), ("stbd", "STBD LINE")):
        c = I.A["power"]["mission_line_kw"][key]
        rows.append((name, f"{f1(c)} kW", f"{f1(c)} kW", f"{f1(side.get(key, 0))} kW", f"{f1(c - side.get(key, 0))} kW", "NORMAL"))
    mass, stab = lines["mass"], lines["stability"]
    rows += [
        ("DECK", f"{deck_total} POS", f"{deck_total} POS", " · ".join(deck_names), f"{deck_total - deck_used}",
         "FULL" if deck_used >= deck_total else "NORMAL"),
        ("MAST", "3 POS", "3 POS", f"{len(I.A['positions']['mast_occupied'])} HOST" + (" · G5 ANT" if mast_free else ""),
         f"{3 - len(I.A['positions']['mast_occupied']) - mast_free}", "FULL" if len(I.A["positions"]["mast_occupied"]) + mast_free >= 3 else "NORMAL"),
        ("MASS", f"{f3(mass.capacity)} t", f"{f3(mass.capacity)} t", f"{f3(mass.demand)} t", f"{f3(mass.free)} t",
         "OVER" if mass.over else ("NEAR LIMIT" if mass.free < 0.1 * mass.capacity else "NORMAL")),
        ("STABILITY", f"{f3(stab.capacity)} t-eq", f"{f3(stab.capacity)} t-eq", f"{f3(stab.demand)} t-eq", f"{f3(stab.free)} t-eq",
         "OVER" if stab.over else "NORMAL"),
    ]
    for link, name in (("satcom", "DATA SATCOM"), ("los_radio", "DATA LOS"), ("acoustic", "DATA ACOUSTIC")):
        d = data[link]
        free = "--" if d["state"] == "DOWN" else f"{f1(d['capacity'] - d['demand'])} {d['unit']}"
        rows.append((name, f"{f1(d['capacity'])} {d['unit']}", f"{f1(d['capacity'])} {d['unit']}", f"{f1(d['demand'])} {d['unit']}",
                     free, d["state"]))
    rows += [
        ("COMPUTE", f"{total_cores} cores", f"{total_cores} cores", f"{used_cores} cores", f"{total_cores - used_cores} cores", "NORMAL"),
        ("RESPONSE D4", f"{f1(ceil)} s", f"{f1(ceil)} s", "--" if resp is None else resp_text(resp, ceil).split(" / ")[0],
         "--" if resp is None else f"{f1(ceil - resp)} s", "--" if resp is None else ("NORMAL" if resp <= ceil else "LATE")),
    ]
    return [dict(zip(("name", "cap", "lim", "used", "free", "state"), r)) for r in rows]


# ------------------------------------------------------------------------------------------- decisions

def _step_text(s: dict) -> str:
    return f"{s['guest']} {words(s['from_mode'])} → {words(s['to_mode'])}"


def _trigger(r: dict, snap: dict) -> tuple[str, bool]:
    f = next((f for f in snap.get("faults", []) if f["fault"] == r.get("trigger")), None)
    subject = SUBJECTS.get(f["subject"], words(f["subject"])) if f else words(r.get("trigger", ""))
    word = "TRIP" if r.get("trigger") in ("genset_trip", "cooling_degraded") else ""
    when = clock(r["raw_event_t_s"]) if r.get("raw_event_t_s") is not None else clock(r["t_s"])
    return f"{subject} {word} · {when}".replace("  ", " "), bool(r.get("injected"))


def _losses(r: dict) -> str:
    out = []
    for g, l in sorted((r.get("losses") or {}).items()):
        if l["mode_before"] == l["mode_after"]:
            out.append(f"{g} NONE")
        else:
            out.append(f"{g} {words(l['mode_before'])} → {words(l['mode_after'])} · CAP {l['capability_before'] * 100:.0f} → {l['capability_after'] * 100:.0f} %")
    return " · ".join(out) or "NONE"


def _cond_value(signal: str, v) -> str:
    if isinstance(v, dict):
        lo, hi = v.get("min"), v.get("max")
        unit = " kn" if signal.endswith("_kn") else ""
        return f"{lo} TO {hi}{unit}" if lo is not None and hi is not None else (f"≥ {lo}{unit}" if lo is not None else f"≤ {hi}{unit}")
    if signal == "heading_free":
        return "FREE" if v else "STEADY"
    if isinstance(v, bool):
        return "ON" if v else "OFF"
    if signal.endswith("_kn"):
        return f"{f1(v)} kn"
    return words(v)


def decision(I: Inputs, m: Moment, gs: dict, pl: dict) -> dict | None:
    """The decision panel: the latest record, its one sentence first."""
    r = _acting(m.records)
    if r is None:
        return None
    snap = m.snapshot
    applied = m.t_s >= r.get("applies_at_tick", r["tick"] + 1)
    resp, ceil, _ = _response(r, m.timing)
    out = {"kind": r["kind"], "seq": r["seq"], "sentence": r["sentence"], "t": clock(r["t_s"]), "rows": [], "conflicts": [],
           "applied": applied}
    if r["kind"] == "D3":
        lim = r["hard_limit"]
        out["title"] = f"RIGHT OF WAY · {r['proceeds']} / {r['yields']}"
        out["tag"] = f"{r['proceeds']} PROCEEDS"
        out["tone"] = "action"
        loser = r["cost_to_loser"]
        lo, hi = loser["minutes_lost"]
        cost = f"{loser['guest']} SURVEY LOSS {lo:.0f} TO {hi:.0f} min" + (" · OPEN-ENDED" if loser["open_ended"] else "")
        when = lim["when"]
        sig = when["signal"].split(".")[-1]
        sig_word = {"battery_pct": "BATT"}.get(sig, words(sig))
        out["rows"] = [
            ("HARD LIMIT", f"{lim['guest']} {sig_word} {when['op']} {when['value']} % · LAND WITHIN {lim['then'].get('within_min')} min", False),
            ("LAND BY", f"{clock(r['deadline_t_s'])} · T-{clock(max(0, r['deadline_t_s'] - m.t_s))[3:]}", False),
            ("DECISION", f"{r['proceeds']} RECOVERS · {loser['guest']} {words(HOLDS.get(loser.get('holds'), loser.get('holds') or ''))}", False),
            ("LEG", f"{loser['guest']} {words(loser.get('leg', ''))}", False),
            ("COST", cost, False),
        ]
        if r.get("reserved"):
            out["rows"].append(("RESERVED", " · ".join(f"{g} {kw(v)} kW" for g, v in r["reserved"].items()), False))
        out["rows"].append(("RESPONSE", resp_text(resp, ceil), False))
        out["r3"] = _r3(m)
        now = m.snapshots_so_far[-1]["ship_state"]
        for c in r.get("conflicts", []):
            if "signal" in c:
                sig = c["signal"]
                current = now.get(sig, {}).get("value")
                out["conflicts"].append({"k": SIGNAL_NAMES.get(sig, words(sig)), "now": _cond_value(sig, current) if current is not None else "--",
                                         "a": _cond_value(sig, c.get(r["yields"])), "b": _cond_value(sig, c.get(r["proceeds"]))})
            elif "exclusion" in c:
                out["conflicts"].append({"k": "EXCLUSION", "now": "--", "a": words(c["exclusion"].replace(".", " ")), "b": ""})
        out["conflict_heads"] = [r["yields"] + " NEEDS", r["proceeds"] + " NEEDS"]
        return out
    if r["kind"] == "D4":
        b = r["binding"]
        cls = "CHW" if b["class"] == "heat" else words(b["class"])
        trig, injected = _trigger(r, snap)
        cap = b["capacity"]
        out["title"] = f"LOAD MANAGEMENT · {cls} LIMIT"
        out["rows"] = [("TRIGGER", trig, injected),
                       ("LIMIT", f"{f1(cap)} - {f1(cap - r['limit_kw'])} = {f1(r['limit_kw'])} kW", False),
                       ("DEMAND", f"{f1(r['load_kw'])} kW", False)]
        if r["verdict"] == "shed":
            out["tag"] = "EXECUTED" if applied else "COMMANDED"
            out["tone"] = "shed"
            out["rows"] += [("ACTION", " · ".join(_step_text(s) for s in r["steps"]), False),
                            ("FREED", f"{f1(sum(s['frees_kw'] for s in r['steps']))} kW", False),
                            ("RESULT", f"{f1(r['load_after_kw'])} / {f1(r['limit_kw'])} kW", False)]
        else:
            out["tag"] = "HOLDS" if r["verdict"] == "hold" else words(r["verdict"])
            out["tone"] = "hold"
            out["rows"] += [("ACTION", f"0 STEPS · {f1(r['limit_kw'] - r['load_kw'])} kW SPARE", False),
                            ("RESULT", f"{f1(r['load_kw'])} / {f1(r['limit_kw'])} kW", False)]
            if r.get("armed"):
                a = r["armed"][0]
                out["rows"].append(("NEXT", f"{_step_text(a)} · {kw(a['frees_kw'])} kW", False))
        out["rows"] += [("LOSS", _losses(r), False), ("RESPONSE", resp_text(resp, ceil), False)]
        later = _latest(m.records, ("D4",))
        if later is not r and later["verdict"] == "hold":
            out["recheck"] = f"RECHECK {clock(later['t_s'])} · HOLDS {f1(later['load_kw'])} / {f1(later['limit_kw'])} kW"
        out["r3"] = _r3(m)
        return out
    out.update(title=r["kind"], tag=words(r["verdict"]), tone="hold")
    return out


def _r3(m: Moment) -> dict | None:
    """The latest crew-policy record for rule R3, shown under the decision it follows."""
    r = _latest(m.records, ("D5",))
    if r is None:
        return None
    return {"t": clock(r["t_s"]), "crew": r.get("crew_aboard"), "verdict": words(r["verdict"]), "sentence": r["sentence"],
            "evidence": r.get("deck_evidence", "")}


def shed_order(I: Inputs, m: Moment) -> dict:
    """Executed and armed steps of the latest D4 record, then the mission-critical guests that go last."""
    r = _acting(m.records, ("D4",))
    latest = _latest(m.records, ("D4",))
    file = _file(I, m)
    rows = []
    if r:
        applied = m.t_s >= r.get("applies_at_tick", r["tick"] + 1)
        for s in r["steps"]:
            rows.append((s, "EXECUTED" if applied else "COMMANDED"))
        for s in (latest or r)["armed"]:
            rows.append((s, "ARMED"))
    out = []
    for i, (s, state) in enumerate(rows, 1):
        tier = s.get("tier") or Lg.tier_of(I.cards, s["guest"], file)
        out.append({"n": str(i), "g": s["guest"], "step": f"{words(s['from_mode'])} → {words(s['to_mode'])}",
                    "kw": f"-{kw(s['frees_kw'])}", "loss": f"{s.get('capability_lost_pct', 0):.0f} %", "tier": TIER_NAMES[tier],
                    "mc": tier == "mission_critical", "shed": bool(s.get("shed")), "state": state})
    listed = {s["g"] for s in out}
    for g in m.snapshot["guests"]:
        tier = Lg.tier_of(I.cards, g, file)
        if g not in listed and tier in ("mission_critical", "vessel_critical"):
            out.append({"n": "--" if tier == "vessel_critical" else str(len(out) + 1), "g": g,
                        "step": "VESSEL CRITICAL" if tier == "vessel_critical" else "MISSION CRITICAL", "kw": "--", "loss": "--",
                        "tier": TIER_NAMES[tier], "mc": tier == "mission_critical", "shed": False,
                        "state": "NEVER" if tier == "vessel_critical" else "LAST"})
    src = r["order_source"] if r else ("declared" if file.get("shed_order") else "computed")
    return {"rows": out, "source": f"ORDER {words(src)} · TIER, THEN LOSS PER kW", "mission": mission_name(m.mission, file)}


# ------------------------------------------------------------------------------------------- event log

LAPTOP_EVENTS = {
    "crew_change": lambda p: ("CREW", f"{p['crew_aboard']} aboard."),
    "deck_report": lambda p: ("HLO", f"Deck report: {words(p['deck']).lower()}." + (f" Wind {f1(p['wind_kn'])} kn." if p.get("wind_kn") is not None else "")),
    "standing_plan": lambda p: ("BRIDGE", f"Standing plan {p['state']}."),
    "deck_sweep": lambda p: ("CREW", f"Deck sweep: {words(p['result']).lower()}."),
}

ACTIVITY_MSG = {"holding_depth": "Holding depth. Survey leg paused.", "holding_at_sea": "Holding at sea. Survey leg aborted.",
                "surveying": "Surveying on the acoustic link.", "launch_recovery": "Recovery approach.",
                "on_cradle": "On the cradle."}


def _guest_report(snap: dict, e: dict) -> str:
    g = e["payload"]["guest"]
    b = snap["guests"][g]
    parts = []
    if "battery_pct" in e["payload"]["fields"]:
        parts.append(f"Battery {e['payload']['fields']['battery_pct']:.0f} %.")
    parts.append(f"Wind {f1(snap['environment']['wind_kn']['value'])} kn.")
    land_by = b.get("land_by_t_s", {}).get("value")
    if land_by is not None:
        parts.append(f"Land by {clock(land_by)}.")
    return " ".join(parts)


def log_rows(I: Inputs, m: Moment) -> list[dict]:
    rows = []
    prev = None
    faults_seen, requests_seen = set(), set()
    trip = I.A["power"]["trip_confirm"]
    for snap in m.snapshots_so_far:
        t = snap["run"]["t_ship_s"]
        for e in snap.get("events", []):
            if e["type"] == "baseline":
                p = e["payload"]["start"]
                load = sum(b["kw_actual"]["value"] for b in snap["guests"].values())
                rows.append({"t_s": e["t_s"], "order": 0, "type": "START", "tag": "--",
                             "msg": f"Cable route survey. {f1(p['speed_kn'])} kn. CHW {f1(snap['capacity']['heat']['value']['capacity'])} kW "
                                    f"at {p['seawater_c']:.0f} °C. Demand {f1(load)} kW.", "injected": bool(e.get("injected"))})
            elif e["type"] == "guest_report":
                rows.append({"t_s": e["t_s"], "order": 1, "type": "STATE", "tag": e["payload"]["guest"], "msg": _guest_report(snap, e),
                             "injected": bool(e.get("injected"))})
            elif e["type"] in LAPTOP_EVENTS:
                tag, msg = LAPTOP_EVENTS[e["type"]](e["payload"])
                rows.append({"t_s": e["t_s"], "order": 1, "type": "STATE", "tag": tag, "msg": msg, "injected": bool(e.get("injected"))})
        for f in _faults(snap):
            key = (f["fault"], f["subject"], f["raw_event_t_s"])
            if key in faults_seen:
                continue
            faults_seen.add(key)
            tag = SUBJECTS.get(f["subject"], words(f["subject"]))
            if f["fault"] == "genset_trip":
                msg = (f"Trip confirmed {len(f['votes'])} of {len(trip['signals'])} at {clock(f['confirmed_t_s'])}. "
                       f"Guest reserve {snap['capacity']['power']['value']['capacity']:.0f} kW.")
            elif f["fault"] == "cooling_degraded":
                nominal = Lg.heat_capacity_kw(I.A, snap["environment"]["seawater_c"]["value"])
                msg = f"Pump trip confirmed at {clock(f['confirmed_t_s'])}. CHW capacity {f1(nominal)} → {f1(snap['capacity']['heat']['value']['capacity'])} kW."
            else:
                msg = f"{words(f['fault']).capitalize()} confirmed at {clock(f['confirmed_t_s'])}."
            rows.append({"t_s": f["raw_event_t_s"], "order": 2, "type": "ALARM", "tag": tag, "msg": msg, "injected": bool(f.get("injected"))})
        for req in snap["crew"]["bridge_requests"]["value"] or []:
            if any(r["kind"] == "D5" for r in m.records):
                break  # the crew-policy records carry the bridge's answer
            if req.get("state") == "confirmed" and req["request_seq"] not in requests_seen:
                requests_seen.add(req["request_seq"])
                rows.append({"t_s": req["answered_t_s"], "order": 1, "type": "STATE", "tag": req["rule"],
                             "msg": f"Clear deck for G4 recovery. Bridge confirmed, asked {clock(req['asked_t_s'])}.", "injected": False})
        if prev is not None:
            for g, b in snap["guests"].items():
                was = prev["guests"].get(g, {}).get("activity", {}).get("value")
                now = b["activity"]["value"]
                if was == now:
                    continue
                at = b["activity"].get("since_t_s", t)
                if now == "landed":
                    msg = f"Landed. {words(b['mode']['value']).capitalize()} {kw(b['kw_actual']['value'])} kW."
                else:
                    msg = ACTIVITY_MSG.get(now, f"{words(now).capitalize()}.")
                rows.append({"t_s": at, "order": 1, "type": "STATE", "tag": g, "msg": msg, "injected": False})
        prev = snap
    for r in m.records:
        if r["kind"] == "D3":
            typ, tag = "ARBITRATION", f"{r['proceeds']} / {r['yields']}"
        elif r["kind"] == "D4" and r["verdict"] == "shed":
            typ, tag = "SHED", " ".join(sorted({s["guest"] for s in r["steps"]}))
        elif r["kind"] == "D4":
            typ, tag = "HOLD", "D4"
        elif r["kind"] == "D5":
            typ, tag = "CREW POLICY", f"{r.get('rule', 'R3')} · {r.get('crew_aboard', '')}".rstrip(" ·")
        else:
            typ, tag = r["kind"], words(r.get("rule", r["subject"]))
        rows.append({"t_s": r["t_s"], "order": 3, "type": typ, "tag": tag, "msg": r["sentence"], "injected": False, "seq": r["seq"]})
    for e in m.inputs:
        rows.append({**e, "order": 1})
    rows.sort(key=lambda e: (e["t_s"], e["order"], e.get("seq", 0)), reverse=True)
    for e in rows:
        e["t"] = clock(e["t_s"])
    return rows


# ------------------------------------------------------------------------------------------- active constraint

def _draws_before(I: Inputs, r: dict, m: Moment) -> dict:
    """Per guest kW the shed decision read: each guest's mode before the step, or its reservation."""
    reserved: dict = {}
    for x in m.records:
        if x["tick"] <= r["tick"]:
            reserved.update(x.get("reserved") or {})
    return {g: Lg.committed_kw(I.cards, g, l["mode_before"], reserved.get(g, 0.0)) for g, l in (r.get("losses") or {}).items()}


def constraint(I: Inputs, m: Moment, gs: dict, pl: dict) -> dict:
    """The constraint-ledger drill-down: the limit arithmetic of the binding class, step by step. A shed shows the
    load it read, the shortfall, each step and the load after; otherwise the load now against the limit."""
    r = _acting(m.records, ("D4",))
    shed = r if r and r["verdict"] == "shed" else None
    snap = m.snapshot
    inj = _injected_subjects(snap)
    cls = pl["binds"]
    rows = []
    if cls == "heat":
        rows.append((f"CHW CAPACITY AT {pl['seawater_c']:.0f} °C", f"{f1(pl['heat_nominal'])} kW", 0, False))
        if pl["heat_degraded"]:
            down = [n for n in (1, 2) if not snap["plant"][f"chw_pump_{n}_running"]["value"]]
            rows.append((f"P{down[0] if down else 1} TRIP · 1 OF 2 PUMPS", f"× {I.A['heat']['degraded_factor']:.2f}", 0,
                         bool({"chw_pump_1", "chw_pump_2"} & inj)))
            rows.append(("AVAILABLE", f"{f1(pl['heat_cap'])} kW", 0, False))
        title = "CHILLED WATER"
    else:
        reserve = "GEN 1 ONLY" if pl["power_degraded"] else f"2 GEN · {words(_value(snap, 'ship_state', 'speed_band'))}"
        rows.append((f"GUEST RESERVE · {reserve}", f"{f1(pl['power_cap'])} kW", 0, False))
        title = "POWER"
    rows.append(("HEADROOM", f"-{f1(pl['headroom'])} kW", 0, False))
    rows.append(("LIMIT", f"{f1(pl['ceiling'])} kW", 1, False))
    if shed:
        before, after = shed["load_kw"], shed["load_after_kw"]
        draws = _draws_before(I, shed, m)
        rows.append(("DEMAND " + " + ".join(f"{g} {kw(v)}" for g, v in draws.items()), f"{f1(before)} kW", 0, False))
        rows.append(("SHORTFALL", f"{f1(before - shed['limit_kw'])} kW", 2, False))
        for st in shed["steps"]:
            rows.append((f"{st['guest']} {words(st['from_mode'])} → {words(st['to_mode'])}", f"-{f1(st['frees_kw'])} kW", 0, False))
        rows.append(("DEMAND AFTER", f"{f1(after)} kW", 1, False))
        if abs(pl["load"] - after) > 0.05 and m.t_s >= shed.get("applies_at_tick", shed["tick"] + 1):
            rows.append(("DEMAND NOW", f"{f1(pl['load'])} kW", 1, False))
    else:
        before = pl["load"]
        rows.append(("DEMAND " + " + ".join(f"{g} {kw(x['kw'])}" for g, x in gs.items()), f"{f1(before)} kW", 0, False))
        rows.append(("SPARE", f"{f1(pl['ceiling'] - before)} kW", 1, False))
    action = None
    if shed:
        st = shed["steps"][0]
        loss = shed["losses"][st["guest"]]
        resp, ceil, _ = _response(shed, m.timing)
        action = {"t": clock(shed.get("applies_at_tick", shed["tick"] + 1)), "what": " · ".join(_step_text(x) for x in shed["steps"]),
                  "kw": f"-{f1(sum(x['frees_kw'] for x in shed['steps']))} kW · {'CHW' if cls == 'heat' else 'POWER'} {f1(after)} / {f1(shed['limit_kw'])} kW",
                  "impact": f"{st['guest']} CAPABILITY {loss['capability_before'] * 100:.0f} → {loss['capability_after'] * 100:.0f} % · RESPONSE {resp_text(resp, ceil)}"}
    elif r:
        resp, ceil, _ = _response(r, m.timing)
        action = {"t": clock(r["t_s"]), "what": "NO ACTION · HOLDS", "kw": f"{f1(r['load_kw'])} / {f1(r['limit_kw'])} kW",
                  "impact": f"LOSS NONE · RESPONSE {resp_text(resp, ceil)}"}
    tone = "limit" if (pl["heat_degraded"] if cls == "heat" else pl["power_degraded"]) else "normal"
    return {"title": f"ACTIVE CONSTRAINT · {title}", "headline": f"{f1(before)} / {f1(pl['ceiling'])} kW", "tone": tone,
            "rows": [{"k": k, "v": v, "style": st_, "injected": i} for k, v, st_, i in rows], "action": action}


def alarms(m: Moment) -> list[dict]:
    out = []
    for f in sorted(_faults(m.snapshot), key=lambda f: -f["raw_event_t_s"]):
        tag = SUBJECTS.get(f["subject"], words(f["subject"]))
        msg = "TRIP · 2 OF 3 CONFIRMED" if f["fault"] == "genset_trip" else "PUMP TRIP"
        out.append({"t": clock(f["raw_event_t_s"]), "tag": tag, "msg": msg, "injected": bool(f.get("injected"))})
    return out


# ------------------------------------------------------------------------------------------- the whole screen

def screen(I: Inputs, m: Moment) -> dict:
    """Operations and its ledger drill-down for one moment, live or replayed."""
    gs, _ = guest_states(I, m)
    pl = plant_lines(I, m, gs)
    d = decision(I, m, gs, pl)
    acting = _acting(m.records)
    hot = set()
    if acting and acting["kind"] == "D4":
        hot = {s["guest"] for s in acting["steps"]}
    elif acting and acting["kind"] == "D3":
        hot = {acting["proceeds"]}
    return {
        "mission": m.mission, "t_s": m.t_s, "header": header(I, m, pl), "ship_state": ship_state(m),
        "mimic": mimic(I, m, gs, hot), "plant": plant(I, m, pl), "tiles": tiles(I, m, gs, pl), "decision": d,
        "shed_order": shed_order(I, m), "guests": guest_rows(I, m, gs), "log": log_rows(I, m),
        "ledger": {"constraint": constraint(I, m, gs, pl), "rows": ledger_rows(I, m, gs, pl), "alarms": alarms(m)},
        "snapshot_tick": m.snapshot["run"]["tick"], "records_seen": len(m.records),
    }


def operations(I: Inputs, mission: str, t_s: int) -> dict:
    """The fixture replay's screen at one ship second."""
    return screen(I, I.moment(mission, t_s))


def marks(records: list[dict]) -> list[dict]:
    """One mark per decision moment (D3, and each fault's acting D4), for the timeline and the jump keys."""
    out = [{"t_s": 0, "at": 0, "t": "00:00", "label": "START"}]
    seen = set()
    for r in records:
        if r["kind"] == "D3":
            label = f"{r['proceeds']} LOW BATT"
        elif r["kind"] == "D4" and r.get("raw_event_t_s") is not None:
            if r["raw_event_t_s"] in seen:
                continue
            seen.add(r["raw_event_t_s"])
            r = _acting([x for x in records if x["kind"] == "D4" and x.get("raw_event_t_s") == r["raw_event_t_s"]], ("D4",))
            label = {"genset_trip": "GEN 2 TRIP", "cooling_degraded": "CHW P1 TRIP"}.get(r.get("trigger"), words(r.get("trigger", "D4")))
        else:
            continue
        start = r.get("raw_event_t_s") if r.get("raw_event_t_s") is not None else r["t_s"]
        out.append({"t_s": int(r.get("applies_at_tick", r["tick"] + 1)), "at": int(start), "t": clock(start)[:5],
                    "label": label, "injected": bool(r.get("injected"))})
    return out


def compare(I: Inputs, t_s: int, files=("survey", "sar"), moments: dict | None = None, mark_records: list | None = None) -> dict:
    """Both priority files at one moment: from the given moments (the live reference runs) or the fixture replay.
    The timeline marks come from mark_records (the whole run), else from the first file's records."""
    ships = {}
    for f in files:
        v = screen(I, moments[f]) if moments else operations(I, f, t_s)
        ships[f] = {"name": f"MISSION {mission_name(f)}", "weights": _weights(I, f), "decision": v["decision"],
                    "bars": [t for t in v["tiles"] if t["name"] in ("POWER", "COOLING CHW")], "guests": v["guests"],
                    "mimic": v["mimic"]}
    a, b = (ships[f]["decision"] or {} for f in files)
    ra, rb = dict((k, v) for k, v, _ in a.get("rows", [])), dict((k, v) for k, v, _ in b.get("rows", []))
    diff = []
    for k in list(dict.fromkeys(list(ra) + list(rb))):
        if k in ("RESPONSE", "LAND BY", "HARD LIMIT", "TRIGGER", "LIMIT"):
            continue
        if ra.get(k) != rb.get(k) or k == "ACTION":
            diff.append({"k": k, "a": ra.get(k, "--"), "b": rb.get(k, "--")})
    for f in files:
        gs = {g["id"]: g for g in ships[f]["guests"]}
        ships[f]["cap"] = " · ".join(f"{g} {x['cap']}" for g, x in gs.items())
    if ships[files[0]]["cap"] != ships[files[1]]["cap"]:
        diff.append({"k": "CAPABILITY", "a": ships[files[0]]["cap"], "b": ships[files[1]]["cap"]})
    recs = mark_records if mark_records is not None else (moments[files[0]].records if moments else I.records.get(files[0], []))
    return {"t_s": t_s, "clock": "T+" + clock(t_s), "files": list(files), "ships": ships, "diff": diff, "marks": marks(recs)}


def _weights(I: Inputs, mission: str) -> str:
    names = {"seabed_inspection": "SEABED", "sar_air": "UAV", "coastal_connectivity": "COMMS", "ocean_data": "OCEAN",
             "passive_rf_detection": "RF", "fresh_water": "WATER"}
    w = I.missions[mission]["weights"]
    shown = [(names.get(k, words(k)), v) for k, v in w.items() if k in ("seabed_inspection", "sar_air", "coastal_connectivity")]
    shown.sort(key=lambda x: -x[1])
    return " · ".join(f"{k} {v:.1f}" for k, v in shown)


# ------------------------------------------------------------------------------------------- admission (D1)

def cases(I: Inputs) -> list[dict]:
    return [{"id": f"{c['case']}-{c['file']}", "case": c["case"], "file": c["file"], "installed": c["installed"], "card": c["card"],
             "label": f"{c['case']} · {c['card']} ONTO {' '.join(c['installed'])} · {mission_name(c['file'])}"} for c in I.cases]


def _card_facts(I: Inputs, card: dict) -> list[tuple[str, str]]:
    c = card["consumes"]
    p = c["power_kw"]
    power = f"{kw(p['nominal'])} kW NOM"
    if p.get("peak"):
        power += f" · {kw(p['peak'])} kW {p.get('peak_duration_s', 0) // 60:.0f} min"
    data = [f"{words(k[5:].rsplit('_', 1)[0])} {kw(v.get('min', v.get('nominal')))} TO {kw(v['nominal'])} {k.rsplit('_', 1)[1].replace('mbps', 'Mbit/s').replace('kbps', 'kbit/s')}"
            if v.get("min") is not None else f"{words(k[5:].rsplit('_', 1)[0])} {kw(v['nominal'])} {k.rsplit('_', 1)[1].replace('mbps', 'Mbit/s').replace('kbps', 'kbit/s')}"
            for k, v in c.items() if k.startswith("data_")]
    hard = []
    for h in card.get("hard_limits", []):
        w = h["when"]
        if w["signal"].endswith("battery_pct"):
            hard.append(f"BATT {w['op']} {w['value']} % · LAND ≤ {h['then'].get('within_min')} min")
    return [("POWER", power), ("COOLING", "CHW" if card["cooling"] == "chilled_water" else "AIR"),
            ("DATA", " · ".join(data) or "--"), ("HARD LIMIT", " · ".join(hard) or "NONE")]


def _apply(cards: dict, I: Inputs, schema: dict, target: str, raw) -> tuple[dict | None, str | None]:
    """One jury edit on a copy of the cards, re-validated; (cards, None) or (None, problem)."""
    from sdv.cli import apply_edit
    gid, _, fld = target.partition(".")
    if gid not in cards:
        return None, f"no card {gid}"
    try:
        edited = apply_edit(cards[gid], fld, str(raw))
    except (KeyError, IndexError, TypeError):
        return None, f"no field {fld}"
    problems = Ld.check_card(edited, I.vocab, schema)
    if problems:
        return None, problems[0]
    return {**cards, gid: edited}, None


def admit(I: Inputs, case_id: str = "A1-survey", edits: dict[str, str] | None = None, kept: dict[str, str] | None = None) -> dict:
    """Run D1 on a Scenario A case with the jury's edits; every verdict word, line and sentence is the engine's.
    `kept` holds the edits of the last accepted card: a rejected edit leaves that card in force."""
    edits, kept = edits or {}, kept or {}
    case = next((c for c in I.cases if f"{c['case']}-{c['file']}" == case_id), None)
    if case is None:
        return {"error": f"no case {case_id}", "cases": cases(I)}
    cards = copy.deepcopy(I.cards)
    for key, value in case["card_edits"].items():
        gid, part, fld = key.split(".")
        next(p for p in cards[gid]["placement"]["parts"] if p["name"] == part)[fld] = value
    schema = Ld._schema(Ld.ROOT, "manifests/schema.json")
    for target, raw in kept.items():
        if target not in edits:
            cards = _apply(cards, I, schema, target, raw)[0] or cards
    previous = cards
    for target, raw in kept.items():
        previous = _apply(previous, I, schema, target, raw)[0] or previous
    rejected = None
    applied = {}
    for target, raw in edits.items():
        nxt, problem = _apply(cards, I, schema, target, raw)
        if problem:
            rejected = {"field": target, "problem": problem}
            break
        cards = nxt
        applied[target] = raw
    mission = I.missions[case["file"]]
    installed, card_id = case["installed"], case["card"]
    layout = {k: v for k, v in case["placement"].items() if k.split(".")[0] in installed}
    if rejected:
        cards = previous  # the previous card is kept: decide on the last accepted inputs
        applied = dict(kept)
    t0 = time.perf_counter()
    adm = Ad.admit(I.A, cards, installed, card_id, mission, layout)
    rec = Rec.from_admission(adm, seq=0, tick=0, card_id=card_id, installed=installed, mission=mission, cards=cards)
    ms = (time.perf_counter() - t0) * 1000
    if rejected:
        rec_rej = Rec.card_rejected(seq=1, tick=0, card_id=card_id, field=f"{rejected['field']} ({rejected['problem']})", mission=mission)
    card = cards[card_id]
    parts = [{"name": p["name"], "mass_t": p["mass_t"], "pos": SLOTS.get(adm.placement.get(f"{card_id}.{p['name']}"), "--"),
              "field": f"{card_id}.{p['name']}.mass_t", "base": next(q for q in I.cards[card_id]["placement"]["parts"] if q["name"] == p["name"])["mass_t"]}
             for p in card["placement"]["parts"]]
    over = {l.cls for l in adm.over}
    order = ["mass", "stability", "power", "heat", "line_port", "line_stbd", "mast_mass", "mast_area", "mast_air_cooling", "flight_deck_drone"]
    unit = {"t": "t", "t_eq": "t-eq", "kW": "kW", "kg": "kg", "m2": "m²"}
    label = {"heat": "CHW AT 30 °C", "line_port": "LINE PORT", "line_stbd": "LINE STBD", "mast_mass": "MAST SLOT MASS",
             "mast_area": "MAST SLOT AREA", "mast_air_cooling": "MAST AIR COOLING", "flight_deck_drone": "HANGAR DRONE"}
    lines = []
    for cls in order:
        if cls not in adm.lines:
            continue
        l = adm.lines[cls]
        digits = 3 if l.unit in ("t", "t_eq") else 1
        lines.append({"k": label.get(cls, words(cls)), "v": f"{l.demand:.{digits}f} / {l.capacity:.{digits}f} {unit.get(l.unit, l.unit)}",
                      "free": f"{l.free:.{digits}f}", "s": "OVER" if cls in over else "OK",
                      "binding": adm.binding is not None and cls == adm.binding.cls})
    g = adm.genset
    gstate = {"fits": "HOLDS", "holds_by_throttling": "HOLDS BY THROTTLING", "does_not_hold": "DOES NOT HOLD"}[g.state]
    checks = [{"k": "1 GENSET", "v": f"{kw(g.load_kw)} / {kw(g.reserve_kw)} kW · GATE {kw(g.gate_kw)}", "s": gstate}]
    for s in g.fix[: g.steps_needed]:
        checks.append({"k": "THROTTLE", "v": f"{s.guest} {words(s.from_mode)} → {words(s.to_mode)} · -{kw(s.frees_kw)} kW", "s": "STEP"})
    placed = [f"{SLOTS.get(v, v)}" for k, v in adm.placement.items() if k.startswith(card_id + ".")]
    checks.append({"k": "PLACEMENT", "v": f"{card_id} → {' · '.join(dict.fromkeys(placed)) or 'NONE'}",
                   "s": "PLACED" if all(adm.placement.get(f"{card_id}.{p['name']}") for p in card["placement"]["parts"]) else "NO POSITION"})
    tip = adm.seawater_tip_c
    env_max = I.A["envelope"]["seawater_c"][1]
    checks.append({"k": "SEAWATER TIP", "v": "NONE IN SCAN" if tip is None else f"{tip:.1f} °C",
                   "s": "--" if tip is None else ("HOLDS" if tip > env_max else "FAILS IN ENV")})
    heat = adm.lines["heat"]
    factor, headroom = I.A["heat"]["degraded_factor"], I.A["power"]["shed_headroom_kw"]
    checks.append({"k": f"CHW -{(1 - factor) * 100:.0f} % AT {env_max} °C",
                   "v": f"{f1(heat.demand)} / {f1(heat.capacity * factor)} kW · GATE {kw(heat.capacity * factor - headroom)}", "s": "INFO"})
    options = [{"n": i, "remove": " ".join(o.remove), "value_lost": f"{o.value_lost:.1f}", "mc": o.mission_critical,
                "mass_after": f"{o.mass_after_t:.3f} t", "moves": " · ".join(f"{k} → {SLOTS.get(v, v)}" for k, v in o.moves.items())}
               for i, o in enumerate(adm.options, 1)]
    verdict = "CARD REJECTED" if rejected else words(adm.verdict).replace("YES IF", "YES-IF").replace("NOT NOW", "NOT NOW")
    b = adm.binding
    binding = f"{label.get(b.cls, words(b.cls))} {b.demand:.3f} / {b.capacity:.3f} {unit.get(b.unit, b.unit)}" if b and b.unit in ("t", "t_eq") \
        else (f"{label.get(b.cls, words(b.cls))} {f1(b.demand)} / {f1(b.capacity)} {unit.get(b.unit, b.unit)}" if b else "--")
    return {
        "case": {"id": case_id, "label": next(c["label"] for c in cases(I) if c["id"] == case_id), "installed": installed, "card": card_id,
                 "mission": mission_name(case["file"]), "file": case["file"], "card_name": card["name"].upper()},
        "cases": cases(I),
        "parts": parts, "facts": [{"k": k, "v": v} for k, v in _card_facts(I, card)],
        "edits": applied, "rejected": rejected,
        "verdict": verdict, "verdict_raw": "card-rejected" if rejected else adm.verdict,
        "binding": "SCHEMA" if rejected else binding,
        "sentence": rec_rej["sentence"] if rejected else rec["sentence"],
        "lines": lines, "options": options, "checks": checks,
        "latency_ms": ms, "ceiling_s": 30.0, "record": rec_rej if rejected else rec,
        "envelope": f"ENVELOPE {I.A['envelope']['seawater_c'][1]} °C · 2 GEN",
    }


# ------------------------------------------------------------------------------------------- reference

def reference(I: Inputs) -> dict:
    guests = []
    for g, c in sorted(I.cards.items()):
        pos = []
        for p in c["placement"]["parts"]:
            pos += [SLOTS.get(s, words(s)) for s in p["allowed"]]
        modes = " · ".join(f"{words(m['name']).lower()} {kw(m['power_kw'])}" if m["power_kw"] else words(m["name"]).lower() for m in c["modes"])
        guests.append({"id": g, "name": c["name"], "pos": " · ".join(dict.fromkeys(pos)), "modes": modes,
                       "cooling": "CHW" if c["cooling"] == "chilled_water" else "AIR"})
    missions = [{"id": k, "name": mission_name(k, m), "weights": " · ".join(f"{words(w)} {v:.1f}" for w, v in m["weights"].items()),
                 "mc": " ".join(m["mission_critical"]) or "--",
                 "tiers": " · ".join(f"{g} {TIER_NAMES[Lg.tier_of(I.cards, g, m)]}" for g in sorted(I.cards))} for k, m in I.missions.items()]
    try:
        from sdv import kit
        devices = [{k: d.get(k) for k in ("id", "kind", "role", "site", "storage_gb")} for d in kit.devices(I.A)]
    except Exception:  # the kit is optional for the screen
        devices = []
    return {"guests": guests, "missions": missions, "devices": devices}
