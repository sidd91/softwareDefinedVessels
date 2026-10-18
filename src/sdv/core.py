"""The core: on each snapshot, run every decision it triggers, each to a record, and collect their commands.

    core = Core(mission="survey")
    records, commands = core.decide(snapshot, core_inputs)

Per tick: D3 when G4's recovery meets G3's leg; the R3 follow-through by crew level (D5: ask the bridge, turn into
the wind and clear the deck once cleared, close the request when G4 lands, resume a paused survey once G4 is
secured); D4 every tick, recorded when a fault confirms or a step is taken. Commands from snapshot n are applied in
frame n + 1, each carrying the seq of the record that sent it. Wall-clock latency goes to the timing log only.
"""
from __future__ import annotations

import time

import yaml

from sdv import admission as Ad
from sdv import arbitration as D3
from sdv import loader as Ld
from sdv import ledger as Lg
from sdv import records as Rec
from sdv import safety as Sf
from sdv import shedding as D4

CEILING_MS = {"D1": "admission", "D2": "placement", "D3": "arbitration", "D4": "shed_first_action", "D5": "arbitration",
              "safety": "safety_command"}
ACTIVE_FAULT = ("pending", "held_stale", "confirmed", "restoring")


def _pred_value(pred, current):
    """The value a ship-state command should ask for to meet a card predicate, moving as little as possible."""
    if isinstance(pred, dict):
        lo, hi = pred.get("min"), pred.get("max")
        if current is not None and (lo is None or current >= lo) and (hi is None or current <= hi):
            return current
        return float(lo if lo is not None and (current is None or current < lo) else hi)
    return float(pred) if isinstance(pred, (int, float)) and not isinstance(pred, bool) else pred


class Core:
    def __init__(self, mission: str = "survey", root=Ld.ROOT):
        self.A = Ld.load_assumptions()
        self.vocab = vocab = Ld.load_vocabulary(assumptions=self.A)
        self.cards = Ld.load_cards(vocab=vocab)
        self.missions = Ld.load_missions(self.cards, vocab)
        self.mission_schema = Ld._schema(root, "config/missions/schema.json")
        self.rejected: list[dict] = []          # profiles refused at sea, with the fields named; the previous one is kept
        self.signals = yaml.safe_load((root / "config/signals.yaml").read_text())
        self.mission = self.missions[mission]
        self.seq = 0
        self.records: list[dict] = []
        self.timing: list[dict] = []
        self.reservations: dict[str, float] = {}
        self.d3: dict | None = None            # the open D3 decision and its follow-through
        self.r3: dict | None = None            # {"seq", "request_seq", "state", "landed_t_s"}
        self.d4_keys: set = set()
        self.next_request = 1
        self.shed_from: dict[str, str] = {}    # guest -> its mode before the first shed, for the 30 S restore
        self.safety_table: dict[str, dict] = {}
        self.safety_tick: int | None = None
        self.last_snap: dict | None = None
        self.last_cmds: list = []
        self.g3_hold_since: int | None = None   # tick a hold or abort was sent to G3, until G3 reports it or it is lost
        self.landing_hold: dict | None = None   # {"t_s": tick} while a 200 MS landing hold is in force
        self.commanded: dict[str, str] = {}     # the mode ArgOS last set per guest (shed or restore)
        self.over_since: float | None = None    # first tick of the current over-limit stretch, for the A.8 due ticks
        sig = {x["name"]: x for x in self.signals["signals"]}
        self.wait_s = {int(k): v for k, v in sig["bridge_requests"]["wait_s"]["by_crew"].items()}

    # ---------------------------------------------------------------------------------------------- helpers
    def _record(self, r: dict, started: float, cmds: list, out_cmds: list) -> dict:
        ms = (time.perf_counter() - started) * 1000
        self.records.append(r)
        key = "admission" if r.get("verdict") == "restore" else CEILING_MS[r["kind"]]
        ceiling = self.A["response_time_s"][key] * 1000
        self.timing.append({"tick": r["tick"], "seq": r["seq"], "kind": r["kind"], "latency_ms": round(ms, 3), "ceiling_ms": ceiling})
        out_cmds += [{"seq": r["seq"], **c} for c in cmds]
        return r

    def _take_seq(self) -> int:
        self.seq += 1
        return self.seq

    def _requires(self, gid: str, activity: str) -> dict:
        return next(c["requires"] for c in self.cards[gid].get("conditions", []) if c["activity"] == activity)

    def _ship_for(self, gid: str, activity: str, snap: dict, course: str | None = None) -> dict:
        req = self._requires(gid, activity)
        args = {}
        if course:
            args["course"] = course
        elif "course" in req:
            args["course"] = req["course"]
        if "speed_kn" in req:
            args["speed_kn"] = _pred_value(req["speed_kn"], snap["ship_state"]["speed_kn"]["value"])
        return args

    # ---------------------------------------------------------------------------------------------- R3 (D5)
    def _r3_policy(self, snap: dict) -> tuple[str, str]:
        """R3 by crew level, the profile's override first: (verdict, evidence) before anything is sent."""
        crew = snap["crew"]["crew_aboard"]["value"]
        r3 = self.A["rules"]["r3"]
        own = (self.mission.get("confirm") or {}).get("r3", {})
        how = own.get(crew) or own.get(str(crew)) or r3["confirm"][crew]
        evidence = r3["deck_evidence"][crew]
        if how == "confirm":
            return "confirm", evidence
        if how == "standing_plan":
            ok = snap["crew"]["standing_plan"]["value"] == "approved"
            return ("standing_plan", evidence) if ok else ("held", "no standing plan approved")
        if how == "automatic":
            if snap["crew"]["deck_latched_clear"]["value"] is True:
                return "automatic", evidence
            sweep = snap["crew"]["last_sweep"]["value"]
            if not sweep:
                return "forbidden", "no crew sweep is known, the deck is not latched clear"
            if sweep.get("result") != "clear":
                return "forbidden", "the last crew sweep found the deck not clear"
            return "forbidden", "deck activity since the last crew sweep voided the latch"
        return "forbidden", f"the {self.mission['name'].lower()} file forbids it at {crew} aboard"

    def _r3_window_min(self) -> float:
        """Minutes G4's land-or-ditch limit leaves to clear the deck: its within_min less the approach (rules.r3)."""
        lim = next(l for l in self.cards["G4"]["hard_limits"] if l["then"]["action"] == "land_or_ditch")
        return lim["then"]["within_min"] - self.A["rules"]["r3"]["approach_min"]

    def _deck_short(self, snap: dict) -> dict | None:
        """Why the crew aboard cannot clear the flight deck for G4, or None when it reads clear, the landing officer
        reports the zone clear, or they can (A.6 ship_state.deck.clear_min). At 0 aboard nobody can: forbidden. At a
        level whose lead, the confirm and the clear at the transition_picks worst case, exceeds the minutes the hard
        limit leaves after the approach, the zone had to be kept clear from launch (docs/SCENARIO_C_MEMO.md): not now,
        with the lead as the binding line."""
        deck = snap["ship_state"]["deck_flight_deck"]["value"]
        rep = snap["crew"]["hlo_deck_report"]
        if deck == "clear" or (rep["value"] == "clear" and not rep["stale"]):
            return None
        crew = snap["crew"]["crew_aboard"]["value"]
        if self.A["ship_state"]["deck"]["clear_min"].get(crew) is None:
            return {"verdict": "forbidden", "state": "forbidden", "evidence": f"the flight deck is {deck} and nobody aboard can clear it"}
        picks = self.A["transition_picks"]["r3_worst_case"]
        lead, window = picks["confirm_min"][crew] + picks["clear_deck_min"][crew], self._r3_window_min()
        if lead <= window:
            return None
        binding = {"class": "r3_lead", "label": Rec.explain.LABELS["r3_lead"], "capacity": window, "demand": lead,
                   "free": window - lead, "unit": "min"}
        return {"verdict": "not-now", "state": "held", "evidence": f"the flight deck is {deck} and {crew} aboard cannot clear it in time",
                "binding": binding, "next_window": {"kind": "event", "event": "the landing officer reports the zone clear"}}

    @staticmethod
    def _shorted(r3: dict, verdict: str, evidence: str) -> tuple[str, str, dict]:
        """The verdict, evidence and extra record fields after _clear_or_withhold: as given, unless the crew aboard could
        not clear the deck (r3["short"]), when the refusal's verdict, its reason and its line take over."""
        s = r3.get("short")
        if not s:
            return verdict, evidence, {}
        return s["verdict"], f"{evidence}, {s['evidence']}", {k: s[k] for k in ("binding", "next_window") if k in s}

    def _clear_or_withhold(self, snap: dict, r3: dict) -> list:
        """The turn into the wind and the deck clear, or nothing while a 200 MS landing hold is in force, or nothing when
        the crew aboard cannot clear the deck for G4 (r3["short"] then carries the refusal for the record)."""
        if self.landing_hold is not None:
            r3["withheld"] = True
            return []
        short = self._deck_short(snap)
        if short:
            r3["short"], r3["state"], r3["withheld"] = short, short["state"], False
            return []
        r3.pop("short", None)
        r3["cleared_cmds"], r3["withheld"] = True, False
        return self._clear_cmds(snap)

    def _r3_open(self, snap: dict, deadline_t_s: float | None, out: list, cmds: list) -> None:
        crew = snap["crew"]["crew_aboard"]["value"]
        verdict, evidence = self._r3_policy(snap)
        started = time.perf_counter()
        seq = self._take_seq()
        r3 = {"seq": seq, "request_seq": None, "state": verdict, "landed_t_s": None, "deadline_t_s": deadline_t_s,
              "cleared_cmds": False, "evidence": evidence}
        c, extra = [], {}
        if verdict == "confirm":
            req = self.next_request
            self.next_request += 1
            c.append({"kind": "bridge_request", "args": {"request_seq": req, "rule": "R3", "asked_t_s": snap["run"]["t_ship_s"]}})
            r3.update(request_seq=req, state="asked")
        elif verdict in ("standing_plan", "automatic"):
            r3["state"] = "cleared"
            c += self._clear_or_withhold(snap, r3)
            if r3.get("withheld"):
                evidence += ", deck clearing waits for the landing hold to lift"
            verdict, evidence, extra = self._shorted(r3, verdict, evidence)
        self.r3 = r3
        r = Rec.from_d5(seq=seq, snapshot=snap, verdict=verdict, crew=crew, deck_evidence=evidence,
                        deadline_t_s=deadline_t_s, mission=self.mission, **extra)
        out.append(self._record(r, started, c, cmds))

    def _r3_reopen(self, snap: dict, deadline_t_s: float | None, out: list, cmds: list) -> None:
        """Ask again after a recovery the bridge let lapse or denied: close the old request first."""
        old = self.r3
        if old and old.get("request_seq") is not None and old["landed_t_s"] is None:
            cmds.append({"seq": old["seq"], "kind": "bridge_close", "args": {"request_seq": old["request_seq"]}})
        self.r3 = None
        self._r3_open(snap, deadline_t_s, out, cmds)

    def _clear_cmds(self, snap: dict) -> list:
        c = [{"kind": "ship_state", "args": self._ship_for("G4", "launch_recovery", snap,
                                                          course="free" if self._requires("G4", "launch_recovery").get("heading_free") else None)}]
        if snap["ship_state"]["deck_flight_deck"]["value"] != "clear":
            c.append({"kind": "clear_deck", "args": {"zone": "flight_deck"}})
        return c

    def _hold_release(self, snap: dict, out: list, cmds: list) -> None:
        """A 200 MS landing hold lifts only on a fresh landing-officer report of a clear zone, newer than the hold. The
        recovery then goes on where R3 had it: deck work withheld by the hold goes out now; a pending bridge request,
        a denial or a forbidden recovery stay as they were."""
        hold = self.landing_hold
        rep = snap["crew"]["hlo_deck_report"]
        if hold is None or rep["value"] != "clear" or rep["stale"] or (rep.get("reported_t_s") or -1) <= hold["t_s"]:
            return
        self.landing_hold = None
        r3 = self.r3
        if r3 and r3["state"] == "cleared" and r3.get("withheld") and r3["landed_t_s"] is None:
            started = time.perf_counter()
            seq = self._take_seq()
            c = self._clear_or_withhold(snap, r3)
            r = Rec.from_d5(seq=seq, snapshot=snap, verdict="cleared", crew=snap["crew"]["crew_aboard"]["value"],
                            deck_evidence=f"the landing officer reported the zone clear at minute {Rec.explain.minute(rep['reported_t_s'])}, landing hold lifted",
                            deadline_t_s=r3["deadline_t_s"], mission=self.mission)
            out.append(self._record(r, started, c, cmds))

    def _r3_follow(self, snap: dict, out: list, cmds: list) -> None:
        r3, t = self.r3, snap["run"]["t_ship_s"]
        g4 = snap["guests"].get("G4", {})
        if r3["state"] == "asked":
            req = next((q for q in snap["crew"]["bridge_requests"]["value"] if q["request_seq"] == r3["request_seq"]), None)
            crew = snap["crew"]["crew_aboard"]["value"]
            if req and (req["state"] in ("confirmed", "denied") or t - req["asked_t_s"] > self.wait_s[crew]):
                started = time.perf_counter()
                seq = self._take_seq()
                extra = {}
                if req["state"] == "confirmed":
                    r3["state"] = "cleared"
                    c = self._clear_or_withhold(snap, r3)
                    verdict = "cleared"
                    evidence = f"the bridge confirmed at minute {Rec.explain.minute(req['answered_t_s'])}"
                    if r3.get("withheld"):
                        evidence += ", deck clearing waits for the landing hold to lift"
                    verdict, evidence, extra = self._shorted(r3, verdict, evidence)
                else:
                    r3["state"] = "held"
                    c = []
                    verdict = "held"
                    evidence = "the bridge denied the recovery" if req["state"] == "denied" else "no answer from the bridge"
                r3["evidence"] = evidence
                r = Rec.from_d5(seq=seq, snapshot=snap, verdict=verdict, crew=crew, deck_evidence=evidence,
                                deadline_t_s=r3["deadline_t_s"], mission=self.mission, **extra)
                out.append(self._record(r, started, c, cmds))
        if r3["landed_t_s"] is None and g4.get("activity", {}).get("value") == "landed":
            r3["landed_t_s"] = t
            self.reservations.pop("G4", None)
            self.landing_hold = None
            if r3["request_seq"] is not None:
                cmds.append({"seq": r3["seq"], "kind": "bridge_close", "args": {"request_seq": r3["request_seq"]}})
        d3 = self.d3
        if (r3["landed_t_s"] is not None and d3 and d3["loser"]["leg"] == "paused" and not d3.get("resumed")
                and t >= r3["landed_t_s"] + self.A["rules"]["r3"]["secure_s"]):
            d3["resumed"] = t
            cmds.append({"seq": d3["seq"], "kind": "ship_state", "args": self._ship_for("G3", "surveying", snap)})

    # ---------------------------------------------------------------------------------------------- one tick
    def decide(self, snap: dict, core_inputs: list | None = None) -> tuple[list, list]:
        out, cmds = [], []
        for i in core_inputs or []:
            if i["type"] == "priority_swap":
                self.mission = self.missions[i["payload"]["mission"]]
            elif i["type"] == "profile_applied":
                prof = i["payload"]["profile"]
                problems = Ld.check_mission(prof, self.cards, self.vocab, self.mission_schema)
                if problems:
                    self.rejected.append({"tick": snap["run"]["tick"], "profile": prof.get("id"), "problems": problems})
                else:
                    self.missions[prof["id"]] = prof
                    self.mission = prof
            elif i["type"] == "card_presented":
                started = time.perf_counter()
                gid = i["payload"]["guest"]
                installed = [g for g in snap["run"]["installed"] if g != gid]
                adm = Ad.admit(self.A, self.cards, installed, gid, self.mission)
                r = Rec.from_admission(adm, seq=self._take_seq(), tick=snap["run"]["tick"], card_id=gid, installed=installed,
                                       mission=self.mission, cards=self.cards)
                out.append(self._record(r, started, [], cmds))

        self._hold_release(snap, out, cmds)
        r3_before = self.r3
        if self.d3 is None:
            started = time.perf_counter()
            d = D3.right_of_way(self.A, self.signals, self.cards, self.mission, snap)
            if d is not None:
                seq = self._take_seq()
                r = Rec.from_d3(d, seq=seq, snapshot=snap)
                self.d3 = {**d, "seq": seq}
                if d["charge_reserved"]:
                    self.reservations[d["proceeds"]] = d["reserved_kw"]
                action = "hold_depth" if d["loser"]["leg"] == "paused" else "abort_leg"
                self.g3_hold_since = snap["run"]["tick"]
                out.append(self._record(r, started, [{"kind": "guest_command", "args": {"guest": d["yields"], "action": action}}], cmds))
                if self.r3 is None:
                    self._r3_open(snap, d["deadline_t_s"], out, cmds)
                elif self.r3["state"] == "held" and self.r3["landed_t_s"] is None:
                    self._r3_reopen(snap, d["deadline_t_s"], out, cmds)   # an earlier recall lapsed: the hard limit asks again
                else:
                    self.r3["deadline_t_s"] = d["deadline_t_s"]
        if self.r3 is None and "G4" in snap["guests"] and D3.recovery_due(self.A, self.cards, snap) is not None:
            # no conflict to arbitrate (G3 already holding, or not aboard): R3 still opens G4's recovery
            self._r3_open(snap, snap["guests"]["G4"]["land_by_t_s"]["value"], out, cmds)
        if r3_before is not None:
            self._r3_follow(snap, out, cmds)

        started = time.perf_counter()
        d = D4.shed(self.cards, self.mission, snap, self.reservations, onset_t_s=self.over_since)
        over = d["load_kw"] > d["limit_kw"] + 1e-9
        self.over_since = (self.over_since if self.over_since is not None else snap["run"]["t_ship_s"]) if over else None
        key = None
        if d["verdict"] == "shed":
            key = ("shed", d["tick"])
        elif "trigger" in d:
            key = (d["trigger_subject"], d["confirmed_t_s"], d["verdict"])
        if key and key not in self.d4_keys:
            self.d4_keys.add(key)
            r = Rec.from_d4(d, seq=self._take_seq(), snapshot=snap)
            c = [{"kind": "set_mode", "args": {"guest": s["guest"], "mode": s["to_mode"]}} for s in d["steps"]]
            for s in d["steps"]:
                self.shed_from.setdefault(s["guest"], s["from_mode"])
                self.commanded[s["guest"]] = s["to_mode"]
            out.append(self._record(r, started, c, cmds))
        elif d["verdict"] == "hold":
            self._restore(snap, d, out, cmds)

        # the 200 MS table for requests that arrive before the next tick
        self._expire_g3_hold(snap)
        self.safety_tick, self.last_snap, self.last_cmds = snap["run"]["tick"], snap, list(cmds)
        self._rebuild_table()
        return out, cmds

    def _expire_g3_hold(self, snap: dict) -> None:
        """A hold on its way to G3 stops counting once G3 reports it, once the link drops (the reply is lost), or after
        the acoustic link's judged latency with no answer."""
        since = self.g3_hold_since
        if since is None:
            return
        g3 = snap["guests"].get("G3", {}).get("activity", {}).get("value")
        late = snap["run"]["tick"] - since > self.A["data"]["acoustic_link"]["judged_latency_s"]
        if g3 != "surveying" or not snap["links"]["acoustic_link_up"]["value"] or late:
            self.g3_hold_since = None

    def _rebuild_table(self) -> None:
        self.safety_table = Sf.table(self.cards, self.last_snap, self.last_cmds, self.r3, self.g3_hold_since is not None,
                                     self.landing_hold, self._r3_policy(self.last_snap))

    # ---------------------------------------------------------------------------------------------- 30 S restore
    def _restore(self, snap: dict, d: dict, out: list, cmds: list) -> None:
        """Step a shed guest back up once no fault is open (each cleared after its healthy hold) and it fits under the
        limit; one step per tick, the last guest shed first. Decided on the A.8 30 s admission budget (DEC-60)."""
        if not self.shed_from or any(f["state"] in ACTIVE_FAULT for f in snap["faults"]):
            return
        started = time.perf_counter()
        guests = snap["guests"]
        for g in reversed(list(self.shed_from)):
            if g not in guests:
                continue
            card = self.cards[g]
            names = [m["name"] for m in sorted(card["modes"], key=lambda m: -m["power_kw"])]
            cur, orig = guests[g]["mode"]["value"], self.shed_from[g]
            if names.index(cur) <= names.index(orig):
                del self.shed_from[g]
                continue
            if g in self.commanded and names.index(cur) > names.index(self.commanded[g]):
                del self.shed_from[g]          # the crew switched it further down by hand: leave it to them
                continue
            up = names[names.index(cur) - 1]
            before = d["draws"][g]
            after = Lg.committed_kw(self.cards, g, up, self.reservations.get(g, 0.0))
            load_after = d["load_kw"] - before + after
            if load_after > d["limit_kw"] + 1e-9:
                return
            if up == orig:
                del self.shed_from[g]
            healthy = max((f["healthy_since_t_s"] for f in snap["faults"] if f.get("healthy_since_t_s") is not None), default=None)
            b = d["binding"]
            binding = {"class": b["class"], "label": Rec.explain.LABELS.get(b["class"], b["class"]), "capacity": b["capacity"],
                       "demand": load_after, "free": b["capacity"] - load_after, "unit": "kW", "degraded_by": list(b["degraded_by"])}
            r = Rec.from_restore(seq=self._take_seq(), snapshot=snap, mission=self.mission, guest=g, from_mode=cur, to_mode=up,
                                 binding=binding, load_kw=d["load_kw"], load_after_kw=load_after, limit_kw=d["limit_kw"],
                                 healthy_since_t_s=healthy, responses=d.get("responses", {}))
            self.commanded[g] = up
            out.append(self._record(r, started, [{"kind": "set_mode", "args": {"guest": g, "mode": up}}], cmds))
            return

    # ---------------------------------------------------------------------------------------------- 200 MS
    def safety(self, request: str) -> tuple[list, list]:
        """Answer a safety request from the table built at the last completed tick: one lookup, no solver."""
        started = time.perf_counter()
        if request not in Sf.REQUESTS:
            raise ValueError(f"no safety request {request!r} ({', '.join(Sf.REQUESTS)})")
        if self.safety_tick is None:
            raise RuntimeError("no safety table before the first tick")
        tick = self.safety_tick
        row = self.safety_table[request]
        verdict = "sent" if row["state"] == "ready" else row["state"]
        r = Rec.from_safety({**row, "state": verdict}, seq=self._take_seq(), tick=tick, mission=self.mission)
        out, cmds = [], []
        self._record(r, started, row["commands"] if verdict == "sent" else [], cmds)
        out.append(r)
        if verdict == "sent":
            snap = self.last_snap
            if row["effect"] == "hold":
                self.landing_hold = {"t_s": tick}
            elif row["effect"] == "open_r3":
                deadline = snap["guests"]["G4"]["land_by_t_s"]["value"]
                if self.r3 is None:
                    self._r3_open(snap, deadline, out, cmds)
                else:
                    self._r3_reopen(snap, deadline, out, cmds)
            elif request == "g3_hold_depth":
                self.g3_hold_since = tick
        self.last_cmds += cmds
        self._rebuild_table()
        return out, cmds
