"""Render the Physical Account (brief Annex C) from config/assumptions.yaml and the guest cards.

docs/PHYSICAL_ACCOUNT.md is the one-page deliverable, grouped by Annex C's rows with short reasons.
docs/PHYSICAL_ACCOUNT_DETAIL.md keeps the full reason and where each number is used. Run:
    uv run python tools/physical_account.py
"""
from pathlib import Path
import glob
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
CLASSES = [
    ("Electrical power", ("power.",)), ("Heat rejection", ("heat.",)), ("Positions", ("positions.", "hull.")),
    ("Mass / stability", ("mass.",)), ("Data links", ("data.",)), ("State transitions", ("ship_state.",)),
    ("Compute / response time", ("compute.", "response_time_s.", "admission.")),
    ("Mission priorities / crew", ("rules.", "crew.")),
]

# Related keys share one line on the one-page account; the detail page keeps one row per key.
GROUPS = [
    ("power balance", ["power.gensets.load_limit", "power.hotel_kw.committed", "power.ship_aux_kw", "power.hotel_shed_on_trip_kw"],
     "2 x 405 kW less 455 kW committed = 355 kW: the 200 kW reserve plus 155 kW spare; one set plus hotel shed = 100 kW",
     lambda L: f"load limit {L('power.gensets.load_limit')}; hotel {L('power.hotel_kw.committed')} kW; aux {L('power.ship_aux_kw')} kW; hotel shed {L('power.hotel_shed_on_trip_kw')} kW"),
    ("reserve by speed", ["power.guest_reserve_kw_by_speed", "power.envelope_reserve_kw"],
     "less propulsion at slow speed; admit at the lower band",
     lambda L: ", ".join(f"{k} {v}" for k, v in L("power.guest_reserve_kw_by_speed").items()) + f" kW; envelope {L('power.envelope_reserve_kw')} kW"),
    ("mission line wiring", ["positions.bay1.power_line", "positions.bay2.power_line", "positions.flight_deck.power_line",
                             "positions.mast_free.power_line", "power.line_lost_on_trip"],
     "split positions across lines; both survive a trip",
     lambda L: f"Bay 1 {L('positions.bay1.power_line')}, Bay 2 {L('positions.bay2.power_line')}, deck {L('positions.flight_deck.power_line')}, mast {L('positions.mast_free.power_line')}; lost on trip: {L('power.line_lost_on_trip')}"),
    ("R3 timing", ["rules.r3.approach_min", "rules.r3.drain_pct_min", "rules.r3.stale_s"],
     "dates the drone's deadline conservatively; drain unverified",
     lambda L: f"approach {L('rules.r3.approach_min')} min; drain {L('rules.r3.drain_pct_min')} %/min; stale {L('rules.r3.stale_s')['camera']} s camera, {L('rules.r3.stale_s')['g4_telemetry']} s drone"),
    ("R3 deck evidence", ["rules.r3.zone", "rules.r3.change_threshold", "rules.r3.unchanged", "rules.r3.camera"],
     "camera proves the zone unchanged since the sweep",
     lambda L: f"landing zone; threshold {L('rules.r3.change_threshold').replace('_', ' ')}; markers and frame match"),
    ("R3 authority", ["rules.r3.override", "rules.r3.uncrewed_launch"],
     "humans override only when aboard",
     lambda L: "landing officer at 14 and 6; at 0 launch only if recovery stays possible"),
    ("tipping-point scan", ["admission.seawater_scan_step_c", "admission.seawater_scan_max_c"],
     "reports where a verdict flips",
     lambda L: f"{L('admission.seawater_scan_step_c')} °C steps to {L('admission.seawater_scan_max_c')} °C"),
]

EXTRA = {
    "Mass / stability": [("G4 hangar mass", "850 kg, not Annex B's 900 kg", "organizer correction (WORKLOG DEC-22)", "card, test"),
                         ("Scenario B load-out", "G2, G3, G4, G5: 13.015 t against 10 t", "the brief's own scenario exceeds its margin (CON-12)", "test")],
    "State transitions": [("R3 lead time", "slow end of A.6: confirm 1 min at 14, 3 at 6; clear 5 min at 14, 12 at 6", "the rule must hold in the worst case", "not yet")],
    "Mission priorities / crew": [("weights per mission", "four files; weights 0.2 to 1.0; one or two mission-critical guests each", "Annex B gives only high, medium, low", "test")],
}


def lookup(dotted):
    node = A
    for k in dotted.split("."):
        if not isinstance(node, dict) or k not in node:
            return None
        node = node[k]
    return node


def shown(v):
    if isinstance(v, (dict, list)):
        return yaml.safe_dump(v, default_flow_style=True, width=400).strip()
    return str(v)


def label(dotted):
    return " ".join(dotted.split(".")[1:]).replace("_", " ")


def short_value(v):
    t = shown(v)
    return t if len(t) <= 40 else "rule text, see detail"


def used_short(dotted):
    leaf = dotted.split(".")[-1]
    out = subprocess.run(["git", "grep", "-l", "-w", leaf, "--", "src", "tests", "manifests"],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    kinds = sorted({"code" if f.startswith("src") else "test" if f.startswith("tests") else "card" for f in out})
    return ", ".join(kinds) or "not yet"


def used_in(dotted):
    leaf = dotted.split(".")[-1]
    out = subprocess.run(["git", "grep", "-l", "-w", leaf, "--", "src", "tests", "manifests"],
                         cwd=ROOT, capture_output=True, text=True).stdout.split()
    return ", ".join(sorted(set(out))[:2]) or "not yet in code"


assumed = {k: p for k, p in A["provenance"].items() if p["source"] == "assumed"}
brief = sorted(k for k, p in A["provenance"].items() if p["source"] != "assumed")
cards = [yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "manifests/G*.yaml")))]


def card_line(c):
    bits = [f"{cls} {q.get('min', '-')}/{q['nominal']}" for cls, q in c["consumes"].items() if q.get("assumed")]
    bits += [f"{m['name']} {m['power_kw']} kW keeps {m['capability_retained']}" for m in c["modes"] if m.get("assumed")]
    return c["id"], ("all numbers ours" if "team invention" in c.get("source", "") else "; ".join(bits))


one = ["# Physical Account", "",
       "Every number our software relies on that is not in Annex A or B, or that narrows a range given there.",
       "Full reasons and code locations: [detail page](PHYSICAL_ACCOUNT_DETAIL.md). Generated by `tools/physical_account.py`.", "",
       "| Annex C row | What we assumed | Value | Why | Used in |", "|---|---|---|---|---|"]
grouped = {k: g for g in GROUPS for k in g[1]}
done = set()
empty = []
for title, prefixes in CLASSES:
    keys = [k for k in assumed if k.startswith(prefixes)]
    rows = []
    for k in keys:
        if k in done:
            continue
        if k in grouped:
            name, members, why, fmt = grouped[k]
            members = [m for m in members if m in assumed]
            done.update(members)
            vals = fmt(lookup)
            used = ", ".join(sorted({u for m in members for u in used_short(m).split(", ") if u != "not yet"})) or "not yet"
            rows.append((name, vals, why, used))
        else:
            done.add(k)
            rows.append((label(k), short_value(lookup(k)), assumed[k].get("short", ""), used_short(k)))
    rows += EXTRA.get(title, [])
    if not rows:
        empty.append(title.lower())
    for i, (name, val, why, used) in enumerate(rows):
        one.append(f"| {title if i == 0 else ''} | {name} | {val} | {why} | {used} |")
cores = ", ".join(f"{c['id']} {c['consumes']['compute_cores']['nominal']}" for c in cards
                  if c["consumes"].get("compute_cores", {}).get("assumed"))
modes = ", ".join(f"{c['id']} {m['name']} {m['capability_retained']}" for c in cards if "team invention" not in c.get("source", "")
                  for m in c["modes"] if m.get("assumed"))
links = ", ".join(f"{c['id']} {cls.split('_')[1]} min {q.get('min')}" for c in cards if "team invention" not in c.get("source", "")
                  for cls, q in c["consumes"].items() if q.get("assumed") and cls.startswith("data"))
one.append(f"| Guest cards | gaps in Annex B | compute cores: {cores}; capability kept in lower modes: {modes}; link floors: {links} | Annex B gives the kW, not cores, capability kept or link floors | card |")
one.append("|  | G6 desalination | all numbers ours | our invented sixth card | card |")
if empty:
    one.append(f"| {', '.join(empty).capitalize()} | nothing beyond Annex A | - | - | - |")
one += ["", "**Closing question (draft, team to confirm).** One change: a 50 kW, 12.5 kWh battery bridge that lifts the",
        "one-genset-down guest reserve from 100 to 150 kW for the 5-15 min restart. Scenario B's four guests at their sustained worst (G2 20 +",
        "G3 charge 25 + G4 35 + G5 45 = 125 kW, plus 5 kW headroom) would then ride through the trip with no shedding, where",
        "today the governor must shed at least 30 kW. Real 88-95 m patrol ships carry 1.8-2.7 MW against this platform's 900 kW."]
(ROOT / "docs/PHYSICAL_ACCOUNT.md").write_text("\n".join(one) + "\n")

det = ["# Physical Account, detail", "", "Full reasons and where each assumed number is used. One-page version:",
       "[PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md).", "", "| Key | Value | Why | Where used |", "|---|---|---|---|"]
for k, p in assumed.items():
    det.append(f"| `{k}` | {shown(lookup(k))} | {p['why']} | {used_in(k)} |")
det += ["", "Taken from the brief without change: " + ", ".join(f"`{k}`" for k in brief) + "."]
(ROOT / "docs/PHYSICAL_ACCOUNT_DETAIL.md").write_text("\n".join(det) + "\n")
print(f"wrote one-page account ({len(assumed)} assumed keys, {len(cards)} cards) and detail page")
