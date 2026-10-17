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
from sdv import records as Rec
from sdv import shedding as D4

CEILING_MS = {"D1": "admission", "D2": "placement", "D3": "arbitration", "D4": "shed_first_action", "D5": "arbitration"}


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
        sig = {x["name"]: x for x in self.signals["signals"]}
        self.wait_s = {int(k): v for k, v in sig["bridge_requests"]["wait_s"]["by_crew"].items()}

    # ---------------------------------------------------------------------------------------------- helpers
    def _record(self, r: dict, started: float, cmds: list, out_cmds: list) -> dict:
        ms = (time.perf_counter() - started) * 1000
        self.records.append(r)
        ceiling = self.A["response_time_s"][CEILING_MS[r["kind"]]] * 1000
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
    def _r3_open(self, snap: dict, d3: dict, out: list, cmds: list) -> None:
        crew = snap["crew"]["crew_aboard"]["value"]
        r3 = self.A["rules"]["r3"]
        how = (self.mission.get("confirm") or {}).get("r3", {}).get(crew) or \
            (self.mission.get("confirm") or {}).get("r3", {}).get(str(crew)) or r3["confirm"][crew]
        evidence = r3["deck_evidence"][crew]
        started = time.perf_counter()
        seq = self._take_seq()
        c = []
        if how == "confirm":
            verdict = "confirm"
            req = self.next_request
            self.next_request += 1
            c.append({"kind": "bridge_request", "args": {"request_seq": req, "rule": "R3", "asked_t_s": snap["run"]["t_ship_s"]}})
            self.r3 = {"seq": seq, "request_seq": req, "state": "asked", "landed_t_s": None}
        elif how == "standing_plan" and snap["crew"]["standing_plan"]["value"] == "approved":
            verdict = "standing_plan"
            self.r3 = {"seq": seq, "request_seq": None, "state": "cleared", "landed_t_s": None}
            c += self._clear_cmds(snap)
        elif how == "automatic" and snap["crew"]["deck_latched_clear"]["value"] is True:
            verdict = "automatic"
            self.r3 = {"seq": seq, "request_seq": None, "state": "cleared", "landed_t_s": None}
            c += self._clear_cmds(snap)
        elif how == "forbidden":
            verdict, evidence = "forbidden", f"the {self.mission['name'].lower()} file forbids it at {crew} aboard"
        else:
            verdict = "forbidden" if crew == 0 else "held"
            evidence = ("deck activity since the last crew sweep voided the latch" if crew == 0 else "no standing plan approved")
        if verdict in ("forbidden", "held"):
            self.r3 = {"seq": seq, "request_seq": None, "state": verdict, "landed_t_s": None}
        r = Rec.from_d5(seq=seq, snapshot=snap, verdict=verdict, crew=crew, deck_evidence=evidence,
                        deadline_t_s=d3["deadline_t_s"], mission=self.mission)
        out.append(self._record(r, started, c, cmds))

    def _clear_cmds(self, snap: dict) -> list:
        c = [{"kind": "ship_state", "args": self._ship_for("G4", "launch_recovery", snap,
                                                          course="free" if self._requires("G4", "launch_recovery").get("heading_free") else None)}]
        if snap["ship_state"]["deck_flight_deck"]["value"] != "clear":
            c.append({"kind": "clear_deck", "args": {"zone": "flight_deck"}})
        return c

    def _r3_follow(self, snap: dict, out: list, cmds: list) -> None:
        r3, t = self.r3, snap["run"]["t_ship_s"]
        g4 = snap["guests"].get("G4", {})
        if r3["state"] == "asked":
            req = next((q for q in snap["crew"]["bridge_requests"]["value"] if q["request_seq"] == r3["request_seq"]), None)
            crew = snap["crew"]["crew_aboard"]["value"]
            if req and (req["state"] in ("confirmed", "denied") or t - req["asked_t_s"] > self.wait_s[crew]):
                started = time.perf_counter()
                seq = self._take_seq()
                if req["state"] == "confirmed":
                    r3["state"] = "cleared"
                    c = self._clear_cmds(snap)
                    verdict, evidence = "cleared", f"the bridge confirmed at minute {req['answered_t_s'] / 60:g}"
                else:
                    r3["state"] = "held"
                    c = []
                    verdict = "held"
                    evidence = "the bridge denied the recovery" if req["state"] == "denied" else "no answer from the bridge"
                r = Rec.from_d5(seq=seq, snapshot=snap, verdict=verdict, crew=crew, deck_evidence=evidence,
                                deadline_t_s=self.d3["deadline_t_s"], mission=self.mission)
                out.append(self._record(r, started, c, cmds))
        if r3["landed_t_s"] is None and g4.get("activity", {}).get("value") == "landed":
            r3["landed_t_s"] = t
            self.reservations.pop("G4", None)
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
                out.append(self._record(r, started, [{"kind": "guest_command", "args": {"guest": d["yields"], "action": action}}], cmds))
                self._r3_open(snap, d, out, cmds)
        elif self.r3 is not None:
            self._r3_follow(snap, out, cmds)

        started = time.perf_counter()
        d = D4.shed(self.cards, self.mission, snap, self.reservations)
        key = None
        if d["verdict"] == "shed":
            key = ("shed", d["tick"])
        elif "trigger" in d:
            key = (d["trigger_subject"], d["confirmed_t_s"], d["verdict"])
        if key and key not in self.d4_keys:
            self.d4_keys.add(key)
            r = Rec.from_d4(d, seq=self._take_seq(), snapshot=snap)
            c = [{"kind": "set_mode", "args": {"guest": s["guest"], "mode": s["to_mode"]}} for s in d["steps"]]
            out.append(self._record(r, started, c, cmds))
        return out, cmds
