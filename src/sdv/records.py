"""Decision records (config/decision_record.schema.json) from the engine's outputs, each with its sentence.

inputs_hash covers what the decision read (cards, priority file, snapshot or installed set) so a replay can show
that the same inputs gave the same record. Wall-clock latency never enters a record.
"""
from __future__ import annotations

import hashlib
import json

from sdv import explain
from sdv.ledger import Line


def _norm(x):
    """The log serializer's numbers (sdv.loop.canonical): 0.1, whole numbers as integers, so a replayed log hashes the same."""
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, (int, float)):
        v = round(float(x), 1)
        return int(v) if v.is_integer() else v
    if isinstance(x, dict):
        return {str(k): _norm(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    return str(x)


def inputs_hash(*objs) -> str:
    blob = json.dumps(_norm(objs), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _line(l: Line) -> dict:
    return {"class": l.cls, "label": explain.LABELS.get(l.cls, l.cls), "capacity": l.capacity, "demand": l.demand,
            "free": l.capacity - l.demand, "unit": l.unit, "degraded_by": list(l.degraded_by)}


def _step(s) -> dict:
    if isinstance(s, dict):
        return {k: s[k] for k in ("guest", "from_mode", "to_mode", "frees_kw", "cost_per_kw", "capability_lost_pct", "mission_critical", "shed", "response", "due_t_s", "from_kw", "to_kw") if k in s}
    return {"guest": s.guest, "from_mode": s.from_mode, "to_mode": s.to_mode, "frees_kw": s.frees_kw, "cost_per_kw": round(s.price, 4),
            "capability_lost_pct": round(100 * s.capability_lost, 1), "mission_critical": s.mission_critical, "shed": s.shed, "response": s.response}


def _finish(r: dict) -> dict:
    r["sentence"] = explain.sentence(r)
    return r


def from_admission(adm, *, seq: int, tick: int, card_id: str, installed: list[str], mission: dict, cards: dict) -> dict:
    g = adm.genset
    r = {
        "seq": seq, "tick": tick, "t_s": tick, "applies_at_tick": tick + 1, "kind": "D1",
        "subject": f"{card_id} onto {', '.join(installed) or 'an empty ship'}", "mission": mission["id"], "verdict": adm.verdict,
        "binding": _line(adm.binding), "also_failing": [_line(l) for l in adm.over[1:]],
        "options": [{"remove": o.remove, "value_lost": o.value_lost, "mission_critical": o.mission_critical, "mass_after_t": o.mass_after_t,
                     "moves": o.moves} for o in adm.options],
        "placement": adm.placement,
        "genset": {"load_kw": g.load_kw, "reserve_kw": g.reserve_kw, "gate_kw": g.gate_kw, "state": g.state,
                   "steps": [_step(s) for s in g.fix[: g.steps_needed]]},
        "seawater_tip_c": adm.seawater_tip_c,
        "order_source": "declared" if mission.get("shed_order") else "computed",
        "inputs_hash": inputs_hash({g2: cards[g2] for g2 in installed + [card_id]}, mission),
    }
    return _finish(r)


def card_rejected(*, seq: int, tick: int, card_id: str, field: str, mission: dict) -> dict:
    return _finish({"seq": seq, "tick": tick, "t_s": tick, "kind": "D1", "subject": card_id, "mission": mission["id"],
                    "verdict": "card-rejected", "field": field, "inputs_hash": inputs_hash(card_id, field)})


def from_d3(d: dict, *, seq: int, snapshot: dict) -> dict:
    loser = d["loser"]
    r = {
        "seq": seq, "tick": d["tick"], "t_s": d["t_s"], "applies_at_tick": d["applies_at_tick"], "kind": "D3",
        "subject": d["subject"], "mission": d["mission"], "verdict": "proceeds", "proceeds": d["proceeds"], "yields": d["yields"],
        "hard_limit": d["hard_limit"], "deadline_t_s": d["deadline_t_s"], "conflicts": d["conflicts"],
        "reserved": {d["proceeds"]: d["reserved_kw"]} if d["charge_reserved"] else {},
        "cost_to_loser": {"guest": loser["guest"], "minutes_lost": loser["survey_minutes_lost"], "open_ended": loser["open_ended"],
                          "leg": loser["leg"], "holds": loser["holds"]},
        "inputs_hash": inputs_hash(snapshot, d["mission"]),
    }
    return _finish(r)


def from_d4(d: dict, *, seq: int, snapshot: dict) -> dict:
    b = d["binding"]
    r = {
        "seq": seq, "tick": d["tick"], "t_s": d["t_s"], "applies_at_tick": d["applies_at_tick"], "kind": "D4",
        "subject": "load against the shed limit", "mission": d["mission"], "verdict": d["verdict"],
        "binding": {"class": b["class"], "label": explain.LABELS.get(b["class"], b["class"]), "capacity": b["capacity"],
                    "demand": b["demand"], "free": b["free"], "unit": b["unit"], "degraded_by": list(b["degraded_by"])},
        "load_kw": d["load_kw"], "limit_kw": d["limit_kw"], "load_after_kw": d["load_after_kw"], "free_after_kw": d["free_after_kw"],
        "total_kw": d["total_kw"], "loop_kw": d["loop_kw"], "total_after_kw": d["total_after_kw"], "loop_after_kw": d["loop_after_kw"],
        "power_limit_kw": d["power_limit_kw"], "heat_limit_kw": d["heat_limit_kw"],
        "steps": [_step(s) for s in d["steps"]], "armed": [_step(s) for s in d["armed"]], "losses": d["losses"],
        "queued": [_step(s) for s in d.get("queued", [])], "responses": d.get("responses", {}), "envelope": d.get("envelope", {}),
        "order_source": "computed",
        "raw_event_t_s": d.get("raw_event_t_s"), "confirmed_t_s": d.get("confirmed_t_s"), "first_shed_due_t_s": d.get("first_shed_due_t_s"),
        "full_sequence_due_t_s": d.get("full_sequence_due_t_s"),
        "inputs_hash": inputs_hash(snapshot, d["mission"]),
    }
    if "trigger" in d:
        r["trigger"] = d["trigger"]
        r["injected"] = d["trigger_injected"]
    if d["verdict"] == "unconfirmed" and d.get("unconfirmed_because"):   # why nothing was shed, for the sentence
        r["unconfirmed_because"] = d["unconfirmed_because"]
    return _finish(r)


def from_d5(*, seq: int, snapshot: dict, verdict: str, crew: int, deck_evidence: str, deadline_t_s: float | None, mission: dict,
            binding: dict | None = None, next_window: dict | None = None) -> dict:
    """Rule R3 at the crew level aboard (docs/SCENARIO_C_MEMO.md): who clears G4's recovery, and on what evidence. A
    not-now also carries the line that bound (the deck clearing lead) and the window that lifts it."""
    run = snapshot["run"]
    r = {"seq": seq, "tick": run["tick"], "t_s": run["t_ship_s"], "applies_at_tick": run["tick"] + 1, "kind": "D5",
         "subject": "G4 recovery under rule R3", "mission": mission["id"], "verdict": verdict, "rule": "R3",
         "crew_aboard": crew, "deck_evidence": deck_evidence, "deadline_t_s": deadline_t_s,
         "inputs_hash": inputs_hash(snapshot, mission["id"])}
    if binding is not None:
        r["binding"] = binding
    if next_window is not None:
        r["next_window"] = next_window
    return _finish(r)


def from_restore(*, seq: int, snapshot: dict, mission: dict, guest: str, from_mode: str, to_mode: str, binding: dict,
                 load_kw: float, load_after_kw: float, limit_kw: float, healthy_since_t_s: float | None, responses: dict,
                 total_kw: float, loop_kw: float, total_after_kw: float, loop_after_kw: float,
                 power_limit_kw: float, heat_limit_kw: float, from_kw: float, to_kw: float) -> dict:
    """A shed guest stepped back up once every fault has read healthy for the restore hold (A.8 30 s budget, DEC-60).
    load_kw, load_after_kw and limit_kw are the binding line's (the one with the least spare after the step); the
    electrical total and the chilled-water loop are carried beside them, as in every D4 record."""
    run = snapshot["run"]
    r = {"seq": seq, "tick": run["tick"], "t_s": run["t_ship_s"], "applies_at_tick": run["tick"] + 1, "kind": "D4",
         "subject": f"restore {guest}", "mission": mission["id"], "verdict": "restore", "binding": binding,
         "load_kw": load_kw, "limit_kw": limit_kw, "load_after_kw": load_after_kw, "free_after_kw": limit_kw - load_after_kw,
         "total_kw": total_kw, "loop_kw": loop_kw, "total_after_kw": total_after_kw, "loop_after_kw": loop_after_kw,
         "power_limit_kw": power_limit_kw, "heat_limit_kw": heat_limit_kw,
         "steps": [{"guest": guest, "from_mode": from_mode, "to_mode": to_mode, "frees_kw": from_kw - to_kw,
                    "from_kw": from_kw, "to_kw": to_kw, "response": "restore"}],
         "armed": [], "losses": {}, "queued": [], "responses": responses, "order_source": "computed",
         "healthy_since_t_s": healthy_since_t_s, "ceiling_ms": 30000, "inputs_hash": inputs_hash(snapshot, mission["id"])}
    return _finish(r)


def from_safety(row: dict, *, seq: int, tick: int, mission: dict) -> dict:
    """A safety command (A.8: stop, hold, secure in 200 ms) answered from the table built at the last completed tick."""
    r = {"seq": seq, "tick": tick, "t_s": tick, "applies_at_tick": tick + 1, "kind": "safety",
         "subject": f"{row['action']} {row['guest']}", "mission": mission["id"], "verdict": row["state"],
         "safety_request": row["request"], "safety_action": row["action"], "guest": row["guest"], "reason": row["reason"],
         "ceiling_ms": 200, "inputs_hash": inputs_hash(row)}
    return _finish(r)
