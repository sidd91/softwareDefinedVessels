"""D4: the shedding ladder, precomputed every tick and walked when supply drops (GAMEPLAN, DEC-16).

Pure functions over the cards, the guests' current modes, the active priority file and the two
ceilings (power reserve and cooling, each less the shed headroom). Each step is one guest moving one
mode down its card. Order: all throttles before any shed; non-critical before mission-critical; then
mission weight x capability lost per kW freed; ties by guest id. A `shed_order` in the priority file
(freeze F3) puts those guests' steps first, in that order. Safety-critical guests are never on the
list; a mode marked `interruptible: false` cannot be left. Power and heat are rechecked after every
step; the walk stops when both hold or nothing is left to do.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .data import mode as mode_of
from .decision import Binding, Decision, fmt
from .priority import is_critical, weight


@dataclass(frozen=True)
class Step:
    guest: str
    from_mode: str
    to_mode: str
    frees_kw: float
    capability_lost: float  # share of capability (0..1)
    value_lost: float  # weight x capability lost
    critical: bool
    capability: str

    @property
    def is_shed(self) -> bool:
        return self.to_mode == "off"

    @property
    def cost_per_kw(self) -> float:
        return self.value_lost / self.frees_kw if self.frees_kw else float("inf")

    def sentence(self) -> str:
        what = "switched off" if self.is_shed else f"to {self.to_mode}"
        return f"{self.guest} {what}: frees {fmt(self.frees_kw)} kW; loses {fmt(self.capability_lost * 100)} % of {self.capability}."

    def as_dict(self) -> dict:
        return {"guest": self.guest, "from_mode": self.from_mode, "to_mode": self.to_mode, "frees_kw": self.frees_kw,
                "capability_lost_pct": round(self.capability_lost * 100, 3), "value_lost": round(self.value_lost, 6),
                "cost_per_kw": round(self.cost_per_kw, 6), "mission_critical": self.critical, "shed": self.is_shed,
                "sentence": self.sentence()}


def _step(card: dict, mission: dict, frm: dict, to: dict) -> Step:
    lost = frm["capability_retained"] - to["capability_retained"]
    return Step(card["id"], frm["name"], to["name"], frm["power_kw"] - to["power_kw"], lost,
                weight(mission, card) * lost, is_critical(mission, card["id"]), card["capability"]["name"])


def chain(card: dict, mission: dict, current: str) -> list[Step]:
    """Every step down the card from `current`; a mode marked `interruptible: false` cannot be left, so
    the step out of it is absent while the steps below it stay on the list."""
    if card["criticality"].get("safety_critical"):
        return []
    modes = sorted(card["modes"], key=lambda m: -m["power_kw"])
    i = [m["name"] for m in modes].index(current)
    return [_step(card, mission, modes[j], modes[j + 1]) for j in range(i, len(modes) - 1)
            if modes[j].get("interruptible", True) is not False]


def next_step(card: dict, mission: dict, current: str, keep_capability: bool = False) -> Step | None:
    """The one step the guest can take now from `current`, or None when it cannot step down."""
    steps = chain(card, mission, current)
    s = steps[0] if steps and steps[0].from_mode == current else None
    if s and keep_capability and float(mode_of(card, s.to_mode)["capability_retained"]) <= 0:
        return None
    return s


def order_key(mission: dict, step: Step) -> tuple:
    declared = mission.get("shed_order", [])
    rank = declared.index(step.guest) if step.guest in declared else len(declared)
    return (step.is_shed, rank, step.critical, step.cost_per_kw, step.guest)


def price_list(cards: dict, modes: dict[str, str], mission: dict) -> list[Step]:
    """Every step down from the current modes, each guest's whole chain, in ladder order."""
    steps = [s for gid, current in modes.items() for s in chain(cards[gid], mission, current)]
    return sorted(steps, key=lambda s: order_key(mission, s))


def armed_list(cards: dict, modes: dict[str, str], mission: dict) -> list[Step]:
    """The ladder as the crew sees it before anything happens: each guest's next step, in order."""
    steps = [s for gid, current in modes.items() if (s := next_step(cards[gid], mission, current))]
    return sorted(steps, key=lambda s: order_key(mission, s))


@dataclass
class Ladder:
    steps: list[Step]
    load_before_kw: float
    load_after_kw: float
    ceiling_kw: float
    binding: str  # "power" or "heat"
    holds: bool
    short_kw: float
    modes_after: dict[str, str]
    armed: list[Step] = field(default_factory=list)  # what would come next if more were needed

    def as_dict(self) -> dict:
        return {"steps": [s.as_dict() for s in self.steps], "load_before_kw": self.load_before_kw,
                "load_after_kw": self.load_after_kw, "ceiling_kw": self.ceiling_kw, "binding": self.binding,
                "holds": self.holds, "short_kw": self.short_kw, "armed": [s.as_dict() for s in self.armed]}


def walk(cards: dict, modes: dict[str, str], mission: dict, power_ceiling_kw: float, heat_ceiling_kw: float,
         draw_kw=None, throttle_only: bool = False, keep_capability: bool = False) -> Ladder:
    """Walk the ladder from `modes` until power and heat both hold. `draw_kw(gid, mode)` gives a guest's
    draw (default: the card's mode power); chilled-water guests count against the heat ceiling.
    `throttle_only` / `keep_capability` give the DEC-35 admission prefix."""
    draw = draw_kw or (lambda gid, m: float(mode_of(cards[gid], m)["power_kw"]))
    current = dict(modes)

    def loads():
        p = sum(draw(g, m) for g, m in current.items())
        h = sum(draw(g, m) for g, m in current.items() if cards[g].get("cooling") == "chilled_water" and m != "off")
        return round(p, 3), round(h, 3)

    def short():
        p, h = loads()
        return round(max(p - power_ceiling_kw, h - heat_ceiling_kw), 3), ("heat" if h - heat_ceiling_kw > p - power_ceiling_kw else "power")

    before, _ = loads()
    short0, binding = short()
    taken: list[Step] = []
    while short()[0] > 1e-9:
        candidates = [s for gid, m in current.items() if (s := next_step(cards[gid], mission, m, keep_capability))
                      and not (throttle_only and s.is_shed)]
        if not candidates:
            break
        s = min(candidates, key=lambda s: order_key(mission, s))
        taken.append(s)
        current[s.guest] = s.to_mode
    after, _ = loads()
    remaining, _ = short()
    done = {(s.guest, s.from_mode) for s in taken}
    armed = [s for s in armed_list(cards, modes, mission) if (s.guest, s.from_mode) not in done]
    return Ladder(taken, before, after, power_ceiling_kw if binding == "power" else heat_ceiling_kw, binding,
                  remaining <= 1e-9, max(short0, 0.0), current, armed)


def ceilings(a: dict, power_reserve_kw: float, cooling_kw: float) -> tuple[float, float]:
    h = a["power"]["shed_headroom_kw"]
    return power_reserve_kw - h, cooling_kw - h


def decide(a: dict, cards: dict, modes: dict[str, str], mission: dict, power_reserve_kw: float, cooling_kw: float,
           draw_kw=None, armed_only: bool = False, t_s: float = 0.0) -> Decision:
    """The D4 record. `armed_only` is the every-tick precompute ("if a genset tripped now")."""
    pc, hc = ceilings(a, power_reserve_kw, cooling_kw)
    lad = walk(cards, modes, mission, pc, hc, draw_kw)
    label = {"power": "guest power reserve", "heat": "chilled-water loop"}[lad.binding]
    load = lad.load_before_kw
    binding = Binding(lad.binding, label, lad.ceiling_kw, load, "kW")
    if not lad.steps:
        verdict = "holds"
        first = lad.armed[0].sentence() if lad.armed else "nothing left to shed."
        sentence = (f"Holds: {fmt(load)} of {fmt(lad.ceiling_kw)} kW on the {label}; nothing shed. "
                    f"Armed, in declared order: {first}")
    else:
        verdict = "shed" if any(s.is_shed for s in lad.steps) else "throttled"
        if not lad.holds:
            verdict = "insufficient"
        steps = " ".join(s.sentence() for s in lad.steps)
        sentence = (f"{label[0].upper() + label[1:]} binds: {fmt(load)} of {fmt(lad.ceiling_kw)} kW, "
                    f"{fmt(lad.short_kw)} kW short. {steps} Now {fmt(lad.load_after_kw)} kW"
                    + ("." if lad.holds else f"; still {fmt(lad.load_after_kw - lad.ceiling_kw)} kW short, nothing left to shed."))
    loser = "; ".join(f"{s.guest} loses {fmt(s.capability_lost * 100)} % of {s.capability}" for s in lad.steps) or "none"
    return Decision("D4", "supply", verdict if not armed_only else f"armed:{verdict}", binding, sentence, t_s=t_s,
                    cost_to_loser=loser, options=[s.as_dict() for s in lad.armed], mission=mission["id"],
                    extras={"ladder": lad.as_dict(), "power_ceiling_kw": pc, "heat_ceiling_kw": hc})
