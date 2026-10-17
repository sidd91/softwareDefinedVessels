"""The 200 ms safety table (A.8: "safety commands (stop, hold, secure) 200 ms"; DEC-16, DEC-60).

The core rebuilds the table at the end of every tick, after D3, D5 and D4, from that tick's snapshot and the commands
it just decided. A request arriving between ticks is answered by looking its row up: no ledger, no ladder, no solver.
Its commands are applied with the next tick's frame, like every command, and the answer is a record. The governor only
requests ship and guest states; it does not drive machinery (assumptions provenance safety_commands).

Each row: request, action (stop, hold or secure, the brief's words), guest, state (ready, not_needed or cannot),
reason, commands, and effect (what the core itself changes: hold or open the R3 recovery).
"""
from __future__ import annotations

REQUESTS = ("r3_hold_landing", "g3_hold_depth", "g2_stop_winch", "g4_return_home")
ACTION = {"g2_stop_winch": ("stop", "G2"), "g3_hold_depth": ("hold", "G3"), "r3_hold_landing": ("hold", "G4"),
          "g4_return_home": ("secure", "G4")}
FLYING = ("airborne", "launch_recovery")


def _row(request: str, state: str, reason: str, commands=(), effect: str | None = None) -> dict:
    action, guest = ACTION[request]
    return {"request": request, "action": action, "guest": guest, "state": state, "reason": reason,
            "commands": list(commands), "effect": effect}


def _value(snap: dict, gid: str, key: str):
    g = snap["guests"].get(gid)
    return g[key]["value"] if g and key in g else None


RECALL = {"confirm": "the bridge is asked to confirm the recovery", "standing_plan": "recovery cleared under the standing plan",
          "automatic": "recovery cleared on the deck latched clear"}


def table(cards: dict, snap: dict, decided: list[dict], r3: dict | None, g3_hold_pending: bool,
          landing_hold: dict | None = None, policy: tuple[str, str] | None = None) -> dict[str, dict]:
    aboard = set(snap["run"]["installed"])
    out = {}

    # STOP G2's winch: the next mode down on its card
    if "G2" not in aboard:
        out["g2_stop_winch"] = _row("g2_stop_winch", "not_needed", "G2 is not aboard")
    elif any(c["kind"] == "set_mode" and c["args"]["guest"] == "G2" for c in decided):
        out["g2_stop_winch"] = _row("g2_stop_winch", "not_needed", "G2's mode is already being changed this second")
    elif _value(snap, "G2", "mode") == "winch" or _value(snap, "G2", "activity") == "winch":
        modes = sorted(cards["G2"]["modes"], key=lambda m: -m["power_kw"])
        names = [m["name"] for m in modes]
        down = names[min(names.index("winch") + 1, len(names) - 1)]
        out["g2_stop_winch"] = _row("g2_stop_winch", "ready", f"G2 goes to {down.replace('_', ' ')}",
                                    [{"kind": "set_mode", "args": {"guest": "G2", "mode": down}}])
    else:
        out["g2_stop_winch"] = _row("g2_stop_winch", "not_needed", "the winch is not running")

    # HOLD G3 at depth: only over a working acoustic link
    act = _value(snap, "G3", "activity")
    if "G3" not in aboard:
        out["g3_hold_depth"] = _row("g3_hold_depth", "not_needed", "G3 is not aboard")
    elif act != "surveying":
        out["g3_hold_depth"] = _row("g3_hold_depth", "not_needed", f"G3 is {str(act).replace('_', ' ')}, not surveying")
    elif not snap["links"]["acoustic_link_up"]["value"]:
        out["g3_hold_depth"] = _row("g3_hold_depth", "cannot", "the acoustic link is down: keep the course steady and the ship quiet until it is back")
    elif g3_hold_pending or any(c["kind"] == "guest_command" and c["args"]["guest"] == "G3" for c in decided):
        out["g3_hold_depth"] = _row("g3_hold_depth", "not_needed", "a hold is already on its way to G3")
    else:
        out["g3_hold_depth"] = _row("g3_hold_depth", "ready", "sent over the acoustic link",
                                    [{"kind": "guest_command", "args": {"guest": "G3", "action": "hold_depth"}}])

    # HOLD G4's landing (R3) and SECURE G4 home
    g4 = _value(snap, "G4", "activity")
    if "G4" not in aboard:
        out["r3_hold_landing"] = _row("r3_hold_landing", "not_needed", "G4 is not aboard")
        out["g4_return_home"] = _row("g4_return_home", "not_needed", "G4 is not aboard")
        return out
    state = r3["state"] if r3 else None
    crew = snap["crew"]["crew_aboard"]["value"]
    if g4 not in FLYING:
        out["r3_hold_landing"] = _row("r3_hold_landing", "not_needed", f"G4 is {str(g4).replace('_', ' ')}, not flying")
    elif landing_hold is not None:
        out["r3_hold_landing"] = _row("r3_hold_landing", "not_needed", "the landing is already held")
    elif crew == 0:
        out["r3_hold_landing"] = _row("r3_hold_landing", "cannot", "nobody aboard can lift a hold: recovery runs on the deck latched clear")
    elif g4 == "launch_recovery" or (r3 and r3.get("cleared_cmds")):
        out["r3_hold_landing"] = _row("r3_hold_landing", "cannot", "the deck is already being cleared for G4: the landing officer waves G4 off by radio")
    elif state in ("held", "forbidden"):
        out["r3_hold_landing"] = _row("r3_hold_landing", "not_needed", f"G4's recovery is already {state}")
    else:
        out["r3_hold_landing"] = _row("r3_hold_landing", "ready", "deck work for G4 waits for the landing officer to report the zone clear",
                                      effect="hold")
    verdict, evidence = policy or ("confirm", "")
    if g4 != "airborne":
        out["g4_return_home"] = _row("g4_return_home", "not_needed", f"G4 is {str(g4).replace('_', ' ')}, not airborne")
    elif landing_hold is not None:
        out["g4_return_home"] = _row("g4_return_home", "cannot", "the landing is held: the landing officer must report the zone clear first")
    elif state in ("asked", "cleared"):
        out["g4_return_home"] = _row("g4_return_home", "not_needed", "G4's recovery is already under way")
    elif verdict in RECALL:
        out["g4_return_home"] = _row("g4_return_home", "ready", RECALL[verdict], effect="open_r3")
    else:
        out["g4_return_home"] = _row("g4_return_home", "cannot", f"recovery {verdict}: {evidence}")
    return out
