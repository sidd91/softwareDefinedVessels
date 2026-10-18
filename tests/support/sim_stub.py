"""TEST DOUBLE for Siddharth's simulator: a throwaway Scenario B stub built from the frozen contract only
(signals.yaml step, commands, baselines, timeline_mapping, fault_signatures, transition_drafts;
docs/STATE_ESTIMATION.md). It lets the estimator, the loop and the UI run end to end before the real simulator
lands; it is not the simulator and owns no ship physics. Every guess it makes is tagged GUESS-<n>.

    sim = Simulator(scenario, mission, seed, variant)
    frame = sim.step(tick, commands, inputs)
"""
from __future__ import annotations
import copy, math
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[2]
SIG = yaml.safe_load((REPO / "config/signals.yaml").read_text())
SIGS = {s["name"]: s for s in SIG["signals"]}
A = yaml.safe_load((REPO / "config/assumptions.yaml").read_text())
TD = SIG["transition_drafts"]
TM = SIG["timeline_mapping"]["events"]
CMDS = SIG["commands"]
EVREG = SIG["events"]
GUESSES = {}   # tag -> text, filled as the code path is exercised


def guess(tag, text):
    GUESSES.setdefault(tag, text)


def r1(x):
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, float):
        return round(x, 1) + 0.0
    if isinstance(x, dict):
        return {k: r1(v) for k, v in x.items()}
    if isinstance(x, list):
        return [r1(v) for v in x]
    return x


def interp(series, t):
    pts = series
    if t <= pts[0][0]:
        return float(pts[0][1])
    for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            return round(v0 + (v1 - v0) * (t - t0) / (t1 - t0), 1)
    return float(pts[-1][1])


class Lin:
    def __init__(self, v0, to, t0, exp_s, latest_s):
        self.v0, self.to, self.t0 = v0, to, t0
        self.t_end, self.t_latest = t0 + exp_s, (t0 + latest_s if latest_s is not None else None)

    def at(self, t):
        if t >= self.t_end:
            return self.to, None
        if isinstance(self.to, (int, float)) and not isinstance(self.to, bool):
            v = round(self.v0 + (self.to - self.v0) * (t - self.t0) / (self.t_end - self.t0), 1)
        else:
            v = self.v0
        tr = {"to": self.to, "started_t_s": self.t0, "expected_end_t_s": self.t_end}
        if self.t_latest is not None:
            tr["latest_end_t_s"] = self.t_latest
        return v, tr


def band_of(kn):
    for name, (lo, hi) in SIG["derivations"]["speed_band"]["bands_kn"].items():
        if kn >= lo and (hi is None or kn <= hi):
            return name
    return None


class Simulator:
    def __init__(self, scenario="scenario_b", mission="survey", seed=0, variant="default"):
        self.scen = yaml.safe_load((REPO / f"config/scenarios/{scenario}.yaml").read_text())
        self.cards = {g: yaml.safe_load((REPO / f"manifests/{g}.yaml").read_text()) for g in self.scen["guests"]}
        B = SIG["baselines"][scenario]
        assert B["seed"] == seed
        self.B, self.mission, self.variant = B, mission, variant
        start = copy.deepcopy(B["start"])
        if variant != "default":
            start.update(copy.deepcopy(B["variants"][variant]["start"]))
        self.start = start
        self.v = copy.deepcopy(start)            # flat state: raw signal name -> value
        self.reported = {}                       # laptop signal -> reported_t_s
        self.tr = {}                             # signal -> Lin
        self.drops = {}                          # feed -> until_t_s
        self.done = set()                        # applied timeline indices
        self.applied_types = []                  # (tick, type, payload) for triggers
        self.tripped = None
        self.pump = None
        self.requests = copy.deepcopy(start["bridge_requests"])
        self.g3_last_msg = None
        self.g3_link_since = None
        self.g3_outbox = []                      # (arrive_tick, fields, data_demand)
        self.event_rate_now = set()              # event-rate signals that report this tick
        self.log = []                            # simulator log (skips, mismatches, refused commands, ignored inputs)
        self.refused = []                        # commands the ship could not carry out: {t_s, kind, args, why}

    # ------------------------------------------------------------------ helpers
    def card_kw(self, g, mode):
        return float(next(m["power_kw"] for m in self.cards[g]["modes"] if m["name"] == mode))

    def bus_load(self):
        hotel = A["power"]["hotel_kw"]["committed"] - (A["power"]["hotel_shed_on_trip_kw"] if self.tripped else 0)
        return hotel + A["power"]["ship_aux_kw"] + sum(self.v[f"{g}.kw_actual"] for g in self.scen["guests"])

    def link_up(self):
        up = SIG["derivations"]["acoustic_link_up"]  # the simulator applies the same physics (A.5)
        c = A["data"]["acoustic_link"]["up_when"]
        return (all(self.v[k] == want for k, want in c.items()) and not self.scen["location"]["layered"])

    def request(self, seq):
        return next((r for r in self.requests if r["request_seq"] == seq), None)

    # ------------------------------------------------------------------ commands
    def apply_command(self, c, tick):
        k, a = c["kind"], c["args"]
        if k == "set_mode":
            g = a["guest"]
            self.v[f"{g}.mode"] = a["mode"]
            self.v[f"{g}.kw_actual"] = self.card_kw(g, a["mode"])
            guess("G-datademand", "set_mode: 'data_demand change at once' but no card gives a per-mode data rate; the stub keeps the old data_demand (G4 charge on deck {}, G5 low_power keeps satcom 6)")
        elif k == "ship_state":
            if "course" in a:
                if a["course"] == "free":
                    self.v["course"] = "free"
                    self.tr.pop("course", None)
                    self.v["noise"] = "manoeuvring"           # transition_drafts.noise
                    self.recovery_ordered = True
                    guess("G-course-free", "ship_state course free: no transition draft for leaving steady; the stub sets free at once (A.6 'leaving quiet is instant' covers noise only)")
                else:
                    d = TD["course_settle"]
                    self.tr["course"] = Lin(self.v["course"], "steady", tick, d["expected_s"], d["latest_s"])
                    self.v["noise"] = "normal"                # transition_drafts.noise
            if "speed_kn" in a:
                if band_of(self.v["speed_kn"]) == band_of(a["speed_kn"]):
                    d = TD["speed_in_band"]
                    self.tr["speed_kn"] = Lin(self.v["speed_kn"], a["speed_kn"], tick, d["expected_s"], d["latest_s"])
                else:
                    raise NotImplementedError("band change: A.6 min_per_band, no expected value drafted")
            if "noise" in a:
                guess("G-noise-arg", "ship_state noise arg: no draft says how long a commanded noise change takes; unused in Scenario B")
                self.v["noise"] = a["noise"]
        elif k == "clear_deck":
            z = f"deck_{a['zone']}"
            crew = self.v["crew_aboard"]
            rng = A["ship_state"]["deck"]["clear_min"].get(crew)
            if rng is None:
                # A.6: nobody aboard can clear a deck (ship_state.deck.clear_min is null at 0). The command is refused,
                # not raised: the deck stays as it is, the frame carries no transition, and the refusal is kept with the
                # tick (the frame contract has no slot for it; the core's D5 record states the refusal to the operator).
                why = f"{crew} aboard cannot clear a deck (ship_state.deck.clear_min)"
                self.refused.append({"t_s": tick, "kind": k, "args": a, "why": why})
                self.log.append(f"{tick}: clear_deck {a['zone']} refused, {why}")
            else:
                d = TD["deck_clear"]                   # drafted for 14 aboard: the scenario pin (4 min) and A.6's slow end (5)
                exp, latest = d["expected_s"], d["latest_s"]
                if not (60 * rng[0] <= exp <= 60 * rng[1]):
                    # The draft is outside this crew level's A.6 range (6 aboard: 8-12 min) and no scenario pins it.
                    # Expected is the middle of the range, where the 14-aboard pin sits in its 3-5; latest is the slow
                    # end, as the draft takes it. Both from assumptions ship_state.deck.clear_min.
                    guess("G-deck-clear-crew", f"clear_deck at {crew} aboard: no scenario pin, expected is the middle of A.6's {rng[0]}-{rng[1]} min and latest the slow end")
                    exp, latest = 60 * (rng[0] + rng[1]) / 2, 60 * rng[1]
                self.tr[z] = Lin(self.v[z], "clear", tick, exp, latest)
        elif k == "guest_command":
            g, act = a["guest"], a["action"]
            assert g == "G3"
            decided = tick - 1                                 # commands land one tick after the snapshot they were decided on
            arrive = decided + TD["g3_round_trip"]["expected_s"]
            res = {"hold_depth": ("holding_depth", "paused"), "abort_leg": ("holding_at_sea", "aborted"),
                   "resume_leg": ("surveying", "running")}[act]
            flown = decided - self.v["G3.leg_started_t_s"]
            guess("G-leg-flown", "the reply's leg_flown_s: script outcome says 480; the stub uses the decision tick (480), not the tick the vehicle receives the hold (481 + latency)")
            guess("G-acoustic-1k", "G3.data_demand drops to 1 kbit/s at the reply tick (script outcome), not at the command tick")
            self.g3_outbox.append((arrive, {"G3.activity": res[0], "G3.leg_state": res[1], "G3.leg_flown_s": flown,
                                            "G3.hold_ack": act != "resume_leg"}, {"acoustic_kbps": 1}))
        elif k == "bridge_request":
            self.requests.append({"request_seq": a["request_seq"], "rule": a["rule"], "state": "pending",
                                  "asked_t_s": a["asked_t_s"], "answered_t_s": None})
        elif k == "bridge_close":
            self.requests = [r for r in self.requests if r["request_seq"] != a["request_seq"]]
        else:
            raise ValueError(k)

    # ------------------------------------------------------------------ inputs
    def apply_input(self, inp, tick, events):
        assert inp["t_s"] == tick
        t, p = inp["type"], inp["payload"]
        assert EVREG[t]["to"] == "simulator", t
        if t == "bridge_answer":
            r = self.request(p["request_seq"])
            if r is None:
                # No such request is open (asked at another crew level, never asked, or already closed): the answer is
                # ignored, not raised. It is not applied, so it is not echoed in the frame; the simulator log says why.
                self.log.append(f"{tick}: bridge_answer to request {p['request_seq']} ignored, no such request is open")
                return
            r["state"], r["answered_t_s"] = p["answer"], tick      # the entry carries its own answer time
        elif t == "feed_drop":
            self.drops[p["feed"]] = p.get("until_t_s")
        elif t == "crew_change":
            self.v["crew_aboard"] = p["crew_aboard"]
            self.v["people_available"] = min(p.get("people_available", self.v["people_available"]), p["crew_aboard"])
            self.reported["crew_aboard"] = self.reported["people_available"] = tick
        elif t == "deck_sweep":
            self.v["last_sweep"] = {"t_s": tick, "result": p["result"]}
            self.v["deck_activity_since_sweep"] = False
            self.reported["last_sweep"] = tick
        elif t == "deck_report":
            self.v["hlo_deck_report"] = p["deck"]
            self.v["hlo_wind_kn"] = p.get("wind_kn", self.v["hlo_wind_kn"])
            self.reported["hlo_deck_report"] = self.reported["hlo_wind_kn"] = tick
        elif t == "standing_plan":
            self.v["standing_plan"] = "approved" if p["state"] == "approved" else "none"
            self.reported["standing_plan"] = tick
        elif t == "emission_change":
            self.v["emission"] = p["emission"]
        elif t == "genset_trip":
            self.trip(p["genset"])
        elif t == "cooling_degraded":
            self.pump = p["pump"]
        else:
            raise NotImplementedError(t)
        events.append({"t_s": tick, "type": t, "origin": "laptop", "injected": inp["injected"], "payload": p})

    def trip(self, n):
        self.tripped = n

    # ------------------------------------------------------------------ timeline (timeline_mapping, generic)
    def map_event(self, e, tick):
        m = TM[e["type"]]
        payload, flags = {}, {"injected": False}
        used = {"t_min", "type"}
        for pk, sk in (m.get("copy") or {}).items():
            payload[pk] = e[sk]; used.add(sk)
        if "fields" in m:
            payload["fields"] = {k: e[k] for k in m["fields"]}; used |= set(m["fields"])
        for sk, table in (m.get("split") or {}).items():
            payload.update(table[e[sk]]); used.add(sk)
        payload.update(m.get("add") or {})
        for c in m.get("context") or []:
            payload[c] = {"variant": self.variant, "start": copy.deepcopy(self.start)}[c]
        for pk, s in (m.get("plus_s") or {}).items():
            payload[pk] = tick + s
        for fk, sk in (m.get("flag") or {}).items():
            flags[fk] = bool(e[sk]); used.add(sk)
        used |= set((m.get("drop") or {}).keys())
        unmapped = set(e) - used
        return payload, flags, unmapped

    def due_tick(self, e):
        if "trigger" in e:
            after = e["trigger"]["after"]
            hit = [t for (t, typ, p) in self.applied_types
                   if typ == "guest_state" and p.get("guest") == after["guest"]
                   and TM["guest_state"]["split"]["state"].get(after["state"]) == {"activity": p["activity"], "mode": p["mode"]}]
            if not hit:
                return None
            d = hit[0] + 60 * e["trigger"]["delay_min"]
            if d != math.ceil(60 * e["t_min"]):
                self.log.append(f"trigger tick {d} differs from t_min tick {math.ceil(60 * e['t_min'])}")
            return d
        return math.ceil(60 * e["t_min"])

    def timeline(self, tick, events):
        for i, e in enumerate(self.scen["events"]):
            if i in self.done:
                continue
            due = self.due_tick(e)
            if due is None or tick < due:
                continue
            self.done.add(i)
            if e.get("optional"):
                self.log.append(f"{tick}: optional {e['type']} not enabled, skipped")
                continue
            payload, flags, unmapped = self.map_event(e, tick)
            if unmapped:
                self.log.append(f"{tick}: {e['type']} scenario keys not covered by timeline_mapping: {sorted(unmapped)}")
            typ = e["type"]
            if typ == "baseline":
                pass  # tick-0 readings already equal start
            elif typ == "guest_report":
                g = payload["guest"]
                for k, val in payload["fields"].items():
                    self.v[f"{g}.{k}"] = float(val)
                    self.event_rate_now.add(f"{g}.{k}")
            elif typ == "genset_trip":
                self.trip(payload["genset"])
            elif typ == "guest_state":
                g = payload["guest"]
                if g == "G4" and payload["activity"] == "landed":
                    r = [x for x in self.requests if x["rule"] == "R3"]
                    cleared = any(x["state"] == "confirmed" for x in r) or self.latched()
                    if not cleared or self.v["G4.activity"] != "launch_recovery":
                        self.log.append(f"{tick}: landing pin skipped (recovery not cleared: requests {r}, activity {self.v['G4.activity']})")
                        continue
                    self.v.update({"G4.activity": "landed", "G4.mode": payload["mode"],
                                   "G4.kw_actual": self.card_kw("G4", payload["mode"]), "G4.range_km": 0.0,
                                   "G4.data_demand": {}, "deck_flight_deck": "occupied", "deck_machinery": False})
            elif typ == "cooling_degraded":
                self.pump = payload["pump"]
            else:
                raise NotImplementedError(typ)
            self.applied_types.append((tick, typ, payload))
            events.append({"t_s": tick, "type": typ, "origin": "timeline", "injected": flags["injected"], "payload": payload})

    def latched(self):
        s = self.v["last_sweep"]
        return bool(s) and s["result"] == "clear" and not self.v["deck_activity_since_sweep"]

    # ------------------------------------------------------------------ one tick
    def step(self, tick, commands, inputs):
        events = []
        self.event_rate_now = set()
        for c in commands:
            self.apply_command(c, tick)
        self.timeline(tick, events)
        for inp in inputs:
            self.apply_input(inp, tick, events)
        for f, until in list(self.drops.items()):
            if until is not None and tick >= until:
                del self.drops[f]

        trs = {}
        for name, lin in list(self.tr.items()):
            val, tr = lin.at(tick)
            self.v[name] = val
            if tr is None:
                del self.tr[name]
            else:
                trs[name] = tr

        # series (baselines): held after the last point; G4 range only while not landed
        for name, pts in self.B["series"].items():
            if name == "G4.range_km" and self.v["G4.activity"] == "landed":
                continue
            self.v[name] = interp(pts, tick)

        # G4 recovery: the simulator starts launch_recovery once the flight deck is clear and R3 is cleared
        if self.v["G4.activity"] == "airborne" and self.v["deck_flight_deck"] == "clear" and "deck_flight_deck" not in trs:
            r3 = [x for x in self.requests if x["rule"] == "R3"]
            if any(x["state"] == "confirmed" for x in r3) or (self.latched() and self.v["crew_aboard"] == 0 and tick > 0 and self.recovery_ordered):
                self.v["G4.activity"] = "launch_recovery"
                guess("G-recovery-start", "nothing says when G4 enters launch_recovery; the stub starts it on the tick the flight deck is clear and R3 is cleared (781), and the deck_machinery flag with it (script outcome '781 to 1019')")
        if self.v["G4.activity"] == "launch_recovery":
            self.v["deck_machinery"] = True

        # fault signatures
        if self.tripped:
            n, o = self.tripped, 3 - self.tripped
            self.v[f"genset_{n}_relay_trip"] = True
            self.v[f"genset_{n}_kw"] = 0.0
            self.v["bus_frequency_hz"] = 59.6
            self.v[f"genset_{o}_kw"] = round(min(A["power"]["gensets"]["rating_kw"], self.bus_load()), 1)
        else:
            self.v["genset_1_kw"] = self.v["genset_2_kw"] = round(self.bus_load() / 2, 1)
        if self.pump:
            p = self.pump
            sig = SIG["fault_signatures"]["cooling_degraded"]["signals"]
            self.v[f"chw_pump_{p}_alarm"] = sig["chw_pump_P_alarm"]
            self.v[f"chw_pump_{p}_running"] = sig["chw_pump_P_running"]
            self.v["chw_flow_pct"] = float(sig["chw_flow_pct"])
            self.v["chw_supply_c"] = float(sig["chw_supply_c"])
            self.v["chw_return_c"] = self.v["chw_supply_c"] + 9

        self.v["bridge_requests"] = copy.deepcopy(self.requests)

        # G3 acoustic (feeds.g3_acoustic.cadence)
        up = self.link_up()
        if up and self.g3_link_since is None:
            self.g3_link_since = tick
        if not up:
            self.g3_link_since = None
        g3_msg = False
        if tick == 0:
            g3_msg = True                       # the tick-0 readings equal start (baseline)
        else:
            ready = [m for m in self.g3_outbox if m[0] <= tick]
            for m in ready:
                self.g3_outbox.remove(m)
                if up:
                    self.v.update(m[1]); self.v["G3.data_demand"] = m[2]; g3_msg = True
                else:
                    self.log.append(f"{tick}: G3 reply lost, link down")
            if not g3_msg and up:
                due = max(self.g3_last_msg if self.g3_last_msg is not None else -10**9, self.g3_link_since) + SIG["feeds"]["g3_acoustic"]["cadence_s"]
                if tick >= due:
                    if self.v["G3.leg_state"] == "running":
                        self.v["G3.leg_flown_s"] = tick - self.v["G3.leg_started_t_s"]
                    g3_msg = True
        if g3_msg:
            self.g3_last_msg = tick

        # assemble
        frame = {"contract": "argos-frame/1", "tick": tick, "t_ship_s": tick, "signals": {},
                 "guests": {g: {} for g in self.scen["guests"]}, "events": events}
        sourced = set(self.B["scenario_sourced"])
        for s in SIG["signals"]:
            name = s["name"]
            if s["producer"] == "estimator" or s["feed"] in self.drops:
                continue
            if s["group"] == "guests":
                g = name.split(".")[0]
                if g not in self.scen["guests"]:
                    continue
            if s["rate"] == "event":
                if s["feed"] == "g3_acoustic":
                    if not g3_msg:
                        continue
                elif not (tick == 0 or name in self.event_rate_now):
                    continue
                if tick == 0 and self.v.get(name) is None:
                    continue    # G4.battery_pct: no report before minute 8
            if s["rate"] == "hourly" and tick % 3600 != 0:
                continue
            srcs = s["source"] if isinstance(s["source"], list) else [s["source"]]
            src = "scenario" if name in sourced else srcs[0]
            r = {"value": copy.deepcopy(self.v[name]), "source": src, "t_s": tick}
            if name in trs:
                r["transition"] = trs[name]
            if name in self.reported:
                r["reported_t_s"] = self.reported[name]
            if s["group"] == "guests":
                g, key = name.split(".", 1)
                frame["guests"][g][key] = r
            else:
                frame["signals"][name] = r
        return r1(frame)

    recovery_ordered = False


# ---------------------------------------------------------------------------------------------- scripted core
SCRIPT = SIG["baselines"]["scenario_b"]["script"]


def script_commands(snap, mission):
    """The commands baselines.scenario_b.script decides on snapshot `snap`, for this mission."""
    out = []
    for c in SCRIPT["commands"].get(snap, []):
        if "missions" in c and mission not in c["missions"]:
            continue
        out.append({k: c[k] for k in ("seq", "kind", "args")})
    return out


def script_inputs(tick):
    return [{"t_s": tick, "type": i["type"], "injected": i["injected"], "payload": i["payload"]}
            for i in SCRIPT["inputs"].get(tick, [])]


def crew0_hook(n, fr, cmds):
    """crew0 after 480 is not in the script. GUESS: no bridge request or answer (R3 automatic on the latch), no
    clear_deck, the turn into the wind decided at 480, the rest as scripted."""
    out = [c for c in cmds if c["kind"] not in ("bridge_request", "bridge_close", "clear_deck", "ship_state")]
    if n == 480:
        out.append({"seq": 1, "kind": "ship_state", "args": {"course": "free", "speed_kn": 5.0}})
    if n == 1080:
        out += [c for c in cmds if c["kind"] == "ship_state"]
    return out


def frames(mission="survey", variant="default", horizon=1200, extra_inputs=None, script=True, cmd_hook=None):
    """Step the stub 0..horizon with the scripted core's commands and inputs; yields each frame."""
    sim = Simulator("scenario_b", mission, 0, variant)
    extra_inputs = extra_inputs or {}
    cmds = []
    for n in range(horizon + 1):
        ins = (script_inputs(n) if script else []) + extra_inputs.get(n, [])
        fr = sim.step(n, cmds, ins)
        yield fr
        cmds = script_commands(n, mission) if script else []
        if cmd_hook:
            cmds = cmd_hook(n, fr, cmds)
