"""The governor: closes the loop on the plant through `Simulator.on_tick` (docs/PLANT_CONTRACT.md).

Every tick it reads the snapshot, re-arms the D4 ladder as "if a genset tripped now" (DEC-16), and
answers the tick's events: a guest whose hard limit has just become active gets a D3 decision against
every guest whose activity its own would break; a confirmed genset trip or cooling fault runs D4 on
the current modes and commands the plant; a `priority_swap` event validates and swaps the priority
file (refused files keep the old one). Each decision is a record in the tick's snapshot, so the run
file and the replay check carry them; wall-time latency is kept out of the replay hash.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import right_of_way as row
from . import shedding
from .data import Inputs
from .decision import Decision, ceiling_ms, timed
from .ledger import cooling_capacity_kw, power_reserve_kw
from .priority import PriorityStore

# Ship-state conditions a drone recovery breaks (it turns into the wind and manoeuvres).
RECOVERY_BREAKS = {"course": "steady", "noise": "quiet", "deck_machinery_allowed": False}


@dataclass
class Governor:
    inputs: Inputs
    mission: str
    priorities: PriorityStore = field(init=False)
    decisions: list[Decision] = field(default_factory=list)
    reserved_kw: dict[str, float] = field(default_factory=dict)
    activities: dict[str, dict] = field(default_factory=dict)
    armed: dict | None = None
    telemetry: dict[str, dict] = field(default_factory=dict)  # what guests have reported, not plant truth
    _decided_limits: set = field(default_factory=set)
    _armed_key: tuple | None = None

    def __post_init__(self) -> None:
        self.priorities = PriorityStore(self.inputs.missions, self.inputs.cards, self.mission)
        self.activities = {g: dict(v) for g, v in self.inputs.scenario.get("initial", {}).get("activities", {}).items()}

    # -- helpers ------------------------------------------------------------------------------------
    @property
    def a(self) -> dict:
        return self.inputs.assumptions

    @property
    def cards(self) -> dict:
        return self.inputs.cards

    def _record(self, d: Decision, snap: dict, latency_ms: float) -> Decision:
        d.seq, d.t_s, d.latency_ms = len(self.decisions) + 1, snap["t_s"], latency_ms
        d.ceiling_ms = ceiling_ms(self.a, d.kind)
        d.inputs_hash = self.inputs.hashes["cards"]
        self.decisions.append(d)
        snap.setdefault("decisions", []).append(d.as_dict())
        return d

    def _draw(self, snap: dict):
        """A guest's draw in a mode: the card's figure scaled by its measured over-consumption, and never
        below what D3 reserved for it while it stays in its current mode."""
        guests = snap["guests"]

        def draw(gid: str, mode: str) -> float:
            g = guests[gid]
            factor = g["actual_kw"] / g["declared_kw"] if g["declared_kw"] else 1.0
            kw = float(next(m["power_kw"] for m in self.cards[gid]["modes"] if m["name"] == mode)) * factor
            return max(kw, self.reserved_kw.get(gid, 0.0)) if mode == g["mode"] else kw

        return draw

    def _modes(self, snap: dict) -> dict[str, str]:
        return {gid: g["mode"] for gid, g in snap["guests"].items()}

    # -- the hook -----------------------------------------------------------------------------------
    def on_tick(self, snap: dict, sim) -> None:
        ship, env = snap["ship"], snap["env"]
        for e in snap["events"]:
            if e["type"] == "priority_swap":
                rec = self.priorities.swap(e.get("mission") or e.get("path"), snap["t_s"])
                snap.setdefault("governor_log", []).append(rec)
                if rec["result"] == "swapped":
                    self.mission = rec["to"]
                    sim.mission = self.mission
            elif e["type"] == "guest_report":
                self.telemetry.setdefault(e["guest"], {}).update({k: v for k, v in e.items() if k not in ("type", "guest", "t_min")})
            elif e["type"] in ("genset_trip", "cooling_degraded"):
                self._run_ladder(snap, sim, trigger=e["type"])
            elif e["type"] == "guest_state" and e.get("state") in ("landed_fast_charging", "on_cradle"):
                self.reserved_kw.pop(e["guest"], None)
                self.activities.pop(e["guest"], None)
        self._check_hard_limits(snap, sim)
        self._check_overload(snap, sim)
        self._arm(snap)
        snap["governor"] = {"mission": self.mission, "reserved_kw": dict(self.reserved_kw), "armed": self.armed,
                            "decisions_so_far": len(self.decisions)}

    # -- D3 -----------------------------------------------------------------------------------------
    def _check_hard_limits(self, snap: dict, sim) -> None:
        """Hard limits are judged on what the guest has reported (its telemetry) and the ship state the
        plant confirms; the plant's own battery model is not an input (unknown never means safe, but a
        reading the governor has not received is not a reading)."""
        now_min = snap["t_s"] / 60.0
        ship = snap["ship"]
        for gid, g in snap["guests"].items():
            state = {**ship, "mode": g["mode"], "airborne": g.get("airborne"), **self.telemetry.get(gid, {})}
            for lim in row.active_limits(self.cards[gid], state):
                if lim.within_min is None or (gid, lim.when) in self._decided_limits:
                    continue
                self._decided_limits.add((gid, lim.when))
                for other, act in list(self.activities.items()):
                    if other == gid or not self._conflicts(other, act["activity"]):
                        continue
                    me = row.Party(gid, "launch_recovery", {"airborne": g.get("airborne"), "mode": g["mode"], **self.telemetry.get(gid, {})})
                    them = row.Party(other, act["activity"], {"mode": snap["guests"][other]["mode"], **act})
                    holder: dict = {}
                    with timed(holder):
                        d = row.decide(self.a, self.cards, self.priorities.active, ship, me, them, now_min)
                    self._record(d, snap, holder["latency_ms"])
                    self._apply(d.extras["actions"], sim, snap)
                    if d.extras["loser_outcome"] == "suspended":
                        self.activities.pop(other, None)
                    else:
                        self.activities[other]["paused_until_min"] = d.extras["cost"]["resumes_at_min"]

    def _conflicts(self, gid: str, activity: str) -> bool:
        cond = next((c for c in self.cards[gid].get("conditions", []) if c["activity"] == activity), None)
        req = (cond or {}).get("requires", {})
        return any(req.get(k) == v for k, v in RECOVERY_BREAKS.items())

    def _apply(self, actions: list[dict], sim, snap: dict) -> None:
        for act in actions:
            if "set_mode" in act:
                gid, mode = act["set_mode"]
                if snap["guests"][gid]["mode"] != mode:
                    sim.set_mode(gid, mode, source="governor:D3")
            elif "request_state" in act:
                var, value = act["request_state"]
                sim.request_state(var, value, source="governor:D3")
            elif "reserve_kw" in act:
                gid, kw = act["reserve_kw"]
                self.reserved_kw[gid] = float(kw)

    # -- D4 -----------------------------------------------------------------------------------------
    def _supply(self, snap: dict, gensets: int | None = None) -> tuple[float, float]:
        ship, env = snap["ship"], snap["env"]
        g = ship["genset"] if gensets is None else gensets
        return (power_reserve_kw(self.a, ship["speed_band"], g),
                cooling_capacity_kw(self.a, env["seawater_c"], ship["cooling"] == "degraded"))

    def _run_ladder(self, snap: dict, sim, trigger: str) -> Decision:
        reserve, cooling = self._supply(snap)
        holder: dict = {}
        with timed(holder):
            d = shedding.decide(self.a, self.cards, self._modes(snap), self.priorities.active, reserve, cooling,
                                draw_kw=self._draw(snap), t_s=snap["t_s"])
        d.extras["trigger"] = trigger
        self._record(d, snap, holder["latency_ms"])
        for s in d.extras["ladder"]["steps"]:
            sim.set_mode(s["guest"], s["to_mode"], source=f"governor:D4:{trigger}")
        return d

    def _check_overload(self, snap: dict, sim) -> None:
        """Supply can also be outgrown without a trip: a guest drawing over its card, warmer seawater,
        a reservation. If the current supply no longer carries the load and a step exists, run D4 now."""
        if any(d["kind"] == "D4" for d in snap.get("decisions", [])):
            return
        reserve, cooling = self._supply(snap)
        pc, hc = shedding.ceilings(self.a, reserve, cooling)
        lad = shedding.walk(self.cards, self._modes(snap), self.priorities.active, pc, hc, self._draw(snap))
        if lad.steps:
            self._run_ladder(snap, sim, trigger="overload")

    def _arm(self, snap: dict) -> None:
        """Every tick: the ladder for 'one genset down now' (or the current supply if already down)."""
        ship = snap["ship"]
        reserve, cooling = self._supply(snap, gensets=min(ship["genset"], 1))
        d = shedding.decide(self.a, self.cards, self._modes(snap), self.priorities.active, reserve, cooling,
                            draw_kw=self._draw(snap), armed_only=True, t_s=snap["t_s"])
        lad = d.extras["ladder"]
        first = (lad["steps"] or lad["armed"] or [None])[0]
        key = (self.mission, d.verdict, lad["load_before_kw"], lad["ceiling_kw"], first and (first["guest"], first["to_mode"]))
        self.armed = {"verdict": d.verdict, "load_kw": lad["load_before_kw"], "ceiling_kw": lad["ceiling_kw"], "binding": lad["binding"],
                      "steps": [s["sentence"] for s in lad["steps"]], "next": [s["sentence"] for s in lad["armed"][:3]], "sentence": d.sentence}
        if key != self._armed_key:  # one record per change of the armed plan, not one per tick
            self._armed_key = key
            if any(x["kind"] == "D4" for x in snap.get("decisions", [])):
                return  # a real D4 record already carries this tick's ladder
            d.verdict = "armed"
            d.extras["trigger"] = "precompute"
            self._record(d, snap, 0.0)
