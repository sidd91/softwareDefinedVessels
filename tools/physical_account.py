"""Render the Physical Account (brief Annex C) from config/assumptions.yaml, the scenario files and the guest cards.

docs/PHYSICAL_ACCOUNT.md is the one-page deliverable. Its rows, short reasons and closing answer live in the
`account` block of config/assumptions.yaml with {{key}} placeholders, so the page follows the data when a
decision changes a number. The script stops if an assumed key is in no row, or if the closing answer's
arithmetic no longer holds. docs/PHYSICAL_ACCOUNT_DETAIL.md keeps one row per assumed key with its full
reason and every file:line that reads it. Run:
    uv run python tools/physical_account.py

"Where used" is an exact trace, not a word match. A key counts as used on a line that names its full
dotted key (for example `power.shed_headroom_kw`, the form the engine's accessor will take) or reads it
through a subscript chain on a variable loaded from the same YAML file, following simple aliases such as
`p = A["power"]` then `p["shed_headroom_kw"]`. Rows may add exact `trace` patterns for uses that are not a
key lookup (card fields, priority files, dynamic subscripts).

The engine never names the file: it receives the assumptions as a parameter or attribute called `A`
(`admission_lines(A, ...)`, `self.A`, `I.A`; `a` and `assumptions` in the loader), so in every module under src/
those names are seeded as reads of config/assumptions.yaml. A seeded name bound to something else (`a` for a mode
or a parser) reads nothing until its block ends, and any read must be a path that exists in the YAML.

A key nothing reads shows its `status` instead of "not yet": `documented only` for a design statement no code
looks up, or, for a `source: measured` figure (the governor's own footprint on the board), "planned" until it is
measured.
"""
from pathlib import Path
import glob
import html
import os
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())
SCEN = {Path(f).stem: yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "config/scenarios/*.yaml")))}
CARDS = {c["id"]: c for c in (yaml.safe_load(open(f)) for f in sorted(glob.glob(str(ROOT / "manifests/G*.yaml"))))}
ACC = A["account"]

# Provenance of every key: assumptions.yaml as written, scenario keys prefixed with the scenario id.
PROV = dict(A["provenance"])
for sid, s in SCEN.items():
    PROV.update({f"{sid}.{k}": p for k, p in (s.get("provenance") or {}).items()})
SOURCE_FILE = {"": "config/assumptions.yaml", **{sid: f"config/scenarios/{sid}.yaml" for sid in SCEN}}


# ---------------------------------------------------------------- values

def lookup(dotted):
    first, *rest = dotted.split(".")
    node, path = (SCEN[first], rest) if first in SCEN else (A, [first, *rest])
    for k in path:
        if isinstance(node, list):  # a list of events or modes: pick the item by its type or name
            node = next((x for x in node if isinstance(x, dict) and k in (x.get("type"), x.get("name"))), None)
        elif isinstance(node, dict):
            node = node.get(int(k) if k.isdigit() and int(k) in node else k)
        else:
            return None
        if node is None:
            return None
    return node


def num(v):
    """Up to three decimals when the value has them (9.515 t, 1.11 %/min), else one (133.3 kW)."""
    if not isinstance(v, float):
        return str(v)
    places = 3 if abs(v - round(v, 3)) < 1e-9 and abs(v - round(v, 1)) > 1e-9 else 1
    return f"{v:.{places}f}".rstrip("0").rstrip(".")


def fmt(v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, dict):
        return ", ".join(f"{fmt(k)} {fmt(x)}" for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v)
    if isinstance(v, (int, float)):
        return num(v)
    return str(v).replace("_", " ")


def shown(v):
    if isinstance(v, (dict, list)):
        return yaml.safe_dump(v, default_flow_style=True, width=400, sort_keys=False).strip()
    return str(v)


def mode_kw(guest, name):
    return next(m["power_kw"] for m in CARDS[guest]["modes"] if m["name"] == name)


def envelope_kw(card):
    """Admission draw: max of nominal and any peak lasting longer than the brief's 60 s (A.1)."""
    p = card["consumes"]["power_kw"]
    peak = p.get("peak", 0) if p.get("peak_duration_s", 0) > A["power"]["peak_max_s"] else 0
    return max(p["nominal"], peak)


def chilled_kw(guests):
    return sum(envelope_kw(CARDS[g]) for g in guests if CARDS[g]["cooling"] == "chilled_water")


def mass_t(guests):
    return round(sum(p["mass_t"] for g in guests for p in CARDS[g]["placement"]["parts"]), 3)


def derived():
    """Numbers the account quotes that are worked out from the data, never typed in."""
    (t0, c0), (t1, c1) = sorted(A["heat"]["capacity_kw_at"].items())
    cool = lambda t: c0 + (c1 - c0) * (t - t0) / (t1 - t0)
    deg, head = A["heat"]["degraded_factor"], A["power"]["shed_headroom_kw"]
    r_one, r_cruise = A["power"]["guest_reserve_kw"]["one_genset_down"], A["power"]["guest_reserve_kw"]["cruise"]
    b = SCEN["scenario_b"]
    fault = lookup("scenario_b.events.cooling_degraded")
    sw_b, t30 = b["location"]["seawater_c"], A["envelope"]["judge_cooling_at_c"]
    battery = ACC["closing"]["battery_kw"]
    lines = {}
    for pos in ("bay1", "bay2", "flight_deck", "mast_free", "hangar_roof"):
        lines.setdefault(A["positions"][pos]["power_line"], []).append(
            {"bay1": "Bay 1", "bay2": "Bay 2", "flight_deck": "deck", "mast_free": "mast", "hangar_roof": "roof"}[pos])
    c = {
        "cool_30": cool(t30), "cool_30_deg": cool(t30) * deg, "sw_b": sw_b,
        "cool_b": cool(sw_b), "cool_b_deg": cool(sw_b) * deg,
        "gate": min(r_one, cool(t30)) - head,
        "ceiling_b": min(r_one, cool(sw_b)) - head, "ceiling_b_deg": min(r_one, cool(sw_b) * deg) - head,
        "gate_30": min(r_cruise, cool(t30)) - head, "gate_30_deg": min(r_cruise, cool(t30) * deg) - head,
        "load_19": sum(mode_kw(g, m) for g, m in fault["load_modes"].items()),
        "chilled_b": chilled_kw(b["guests"]), "chilled_a5": chilled_kw(ACC["closing"]["a5_guests"]),
        "pump_saves_30": cool(t30) * (1 - deg),
        "battery_usable_30": min(r_one + battery, cool(t30)) - head - (min(r_one, cool(t30)) - head),
        "mass_b": mass_t(b["guests"]), "mass_b_brief": mass_t(["G2", "G3", "G4", "G5"]),
        "trip_signals": len(A["power"]["trip_confirm"]["signals"]),
        "ramp_min": min(A["positions"]["stern_ramp"]["craft_len_m"]),
        "lines": "; ".join(f"{side}: {', '.join(names)}" for side, names in lines.items()),
    }
    # The closing answer is only true while these hold; stop rather than print a stale claim.
    checks = {
        "today the minute-19 fault forces a throttle": c["load_19"] > c["ceiling_b_deg"],
        "with a standby pump the minute-19 load fits": c["load_19"] <= c["ceiling_b"],
        "at 30 C a pump loss leaves too little for Scenario B and A5": min(c["chilled_b"], c["chilled_a5"]) > c["gate_30_deg"],
        "at 30 C both fit a full loop": max(c["chilled_b"], c["chilled_a5"]) <= c["gate_30"],
        "a battery bridge is capped by cooling at 30 C": c["battery_usable_30"] < battery,
        "the 95 kW gate in the data matches the rule": A["admission"]["one_genset_down_gate"]["kw"] == c["gate"],
    }
    if not all(checks.values()):
        sys.exit("Physical Account: closing answer or gate no longer holds: " + "; ".join(k for k, ok in checks.items() if not ok))
    return c


def card_lists():
    briefs = {g: c for g, c in CARDS.items() if "team invention" not in c.get("source", "")}
    cores = [f"{g} {c['consumes']['compute_cores']['nominal']}" for g, c in briefs.items()
             if c["consumes"].get("compute_cores", {}).get("assumed")]
    modes = ["; ".join(f"{g} " + ", ".join(f"{m['name']} {num(m['power_kw'])}/{num(m['capability_retained'])}" for m in ms)
                       for g, c in briefs.items() if (ms := [m for m in c["modes"] if m.get("assumed")]))]
    units = {"data_acoustic_kbps": ("acoustic", "kbit/s"), "data_satcom_mbps": ("SATCOM", "Mbit/s"),
             "data_los_radio_mbps": ("radio", "Mbit/s"), "data_backbone_mbps": ("backbone", "Mbit/s")}
    floors = [f"{g} {units[k][0]} {num(q['min'])} {units[k][1]}" for g, c in briefs.items()
              for k, q in c["consumes"].items() if k in units and q.get("assumed") and "min" in q]
    parts = ["; ".join(f"{g} " + ", ".join(f"{p['name']} {num(p['mass_t'])} t" + (f" {num(p['length_m'])} m" if "length_m" in p else "")
                                     for p in ps)
                       for g, c in briefs.items() if (ps := [p for p in c["placement"]["parts"] if p.get("assumed")]))]
    return {"cores": ", ".join(cores),
            "modes": ", ".join(modes), "floors": ", ".join(floors) or "none",
            "parts": ", ".join(parts) or "no mass split"}


CALC = derived()
CARD = card_lists()


def fill(text):
    def one(m):
        key = m.group(1)
        if key.startswith("calc."):
            return num(CALC[key[5:]]) if isinstance(CALC[key[5:]], float) else fmt(CALC[key[5:]])
        if key.startswith("cards."):
            return CARD[key[6:]]
        if key.startswith("closing."):
            return fmt(ACC["closing"][key[8:]])
        v = lookup(key)
        if v is None:
            sys.exit(f"Physical Account: {{{{{key}}}}} names no value")
        return fmt(v)
    return re.sub(r"\{\{([\w.]+)\}\}", one, text)


# ---------------------------------------------------------------- where used

SCAN = ("src", "tests", "manifests", "config/scenarios", "config/missions")
KIND = {"src": "code", "tests": "test", "manifests": "card", "config/scenarios": "scenario", "config/missions": "missions"}
SUBS = r'(?:\[\s*["\']\w+["\']\s*\])+'
CHAIN = re.compile(rf"\b([A-Za-z_]\w*)({SUBS})")
ASSIGN = re.compile(rf"^\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*(?:#.*)?$")
# How src/ names the assumptions dict it is handed: a parameter A, self.A, I.A; a and assumptions in the loader.
SEEDED = {"A": "", "a": "", "assumptions": ""}
RESEED = re.compile(r"\b(?:A|a|assumptions|load_assumptions)\b")  # an assignment that still holds the assumptions
# Bindings that end an alias; those marked True also end a seeded name's reach in their block. A def does not:
# a parameter named A is how the engine receives the assumptions.
REBIND = {r"\bfor\s+(.+?)\s+in\b": True, r"\bdef\s+\w+\((.*?)\)": False, r"\bas\s+(\w+)": True,
          r"\blambda\s+(.*?):": True, r"^\s*([A-Za-z_][\w\s,]*)=(?!=)": True}


def scanned():
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *SCAN],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    except OSError:  # no git on the box
        out = []
    if not out:  # not a git checkout (an exported copy): walk the same directories
        for d in SCAN:
            for dp, dns, fns in os.walk(ROOT / d):
                dns[:] = [n for n in dns if not n.startswith(".") and n != "__pycache__"]
                out += [str(Path(dp, fn).relative_to(ROOT)) for fn in fns if not fn.startswith(".")]
    texts = {}
    for f in sorted(set(out)):
        try:
            texts[f] = (ROOT / f).read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            pass
    return texts


# This tracer's own test names keys to check that they resolve; naming them there is not a use.
TEXTS = {f: t for f, t in scanned().items() if f != "tests/test_physical_account_tracer.py"}


def segs(subs):
    return re.findall(r'["\'](\w+)["\']', subs)


def is_path(pre, chain):
    """True when the chain is a path in its YAML source; a seeded name holding anything else reads no key."""
    node = SCEN[pre] if pre else A
    for k in chain:
        if not isinstance(node, dict) or k not in node:
            return False
        node = node[k]
    return True


def python_reads():
    """(file, line, source, chain) for every subscript chain on a variable loaded from a YAML source."""
    roots = {}  # file -> {name: source prefix}
    for f, lines in TEXTS.items():
        if f.endswith(".py"):
            roots[f] = {m.group(1): pre for line in lines for pre, src in SOURCE_FILE.items()
                        if (m := re.match(r"^\s*([A-Za-z_]\w*)\s*=.*" + re.escape(Path(src).name), line))}
    by_stem = {Path(f).stem: f for f in roots}
    reads = []
    for f, lines in TEXTS.items():
        if not f.endswith(".py"):
            continue
        seeded = SEEDED if f.startswith("src/") else {}
        names = {**seeded, **roots[f]}
        for line in lines:  # names imported from another scanned module that loaded a source
            if m := re.match(r"^\s*from\s+(\w+)\s+import\s+(.+)$", line):
                for n in re.split(r"[,\s()]+", m.group(2)):
                    if n in roots.get(by_stem.get(m.group(1), ""), {}):
                        names[n] = roots[by_stem[m.group(1)]][n]
        alias = {}  # name -> (source prefix, chain, indent of the assignment)
        shadow = {}  # seeded name -> indent of the block that bound it to something else
        for i, line in enumerate(lines, 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            # An alias lives in the block that assigned it; any other binding of the name ends it. So does a
            # seeded name's reach when the binding cannot be the assumptions.
            rebound, shadowed = set(), set()
            for pat, shadows in REBIND.items():
                for m in re.finditer(pat, line):
                    found = re.findall(r"[A-Za-z_]\w*", m.group(1))
                    rebound.update(found)
                    shadowed.update(found if shadows else ())
            alias = {n: a for n, a in alias.items() if a[2] <= indent and n not in rebound}
            shadow = {n: d for n, d in shadow.items() if d <= indent}
            shadow.update({n: indent for n in shadowed if n in seeded})
            for m in CHAIN.finditer(line):
                name, chain = m.group(1), segs(m.group(2))
                if name in names and name not in shadow:
                    reads.append((f, i, names[name], chain))
                elif name in alias:
                    reads.append((f, i, alias[name][0], alias[name][1] + chain))
            if m := ASSIGN.match(line):
                lhs, rhs = m.group(1), m.group(2)
                r = re.fullmatch(rf"(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*)({SUBS})", rhs)  # r3 = self.A["rules"]["r3"]
                if r and r.group(1) in names and r.group(1) not in shadow:
                    alias[lhs] = (names[r.group(1)], segs(r.group(2)), indent)
                elif r and r.group(1) in alias:
                    alias[lhs] = (alias[r.group(1)][0], alias[r.group(1)][1] + segs(r.group(2)), indent)
                else:
                    alias.pop(lhs, None)
                    if lhs in seeded and RESEED.search(re.sub(r"\"[^\"]*\"|'[^']*'", "", rhs)):
                        shadow.pop(lhs, None)  # A = Ld.load_assumptions(); a = assumptions if ... else load_assumptions(root)
    return [r for r in reads if is_path(r[2], r[3])]


READS = python_reads()


def split_key(key):
    first, *rest = key.split(".")
    return (first, rest) if first in SCEN else ("", key.split("."))


def where(key):
    """Every file:line that reads this exact key."""
    pre, chain = split_key(key)
    hits = {(f, i) for f, i, p, c in READS if p == pre and c[:len(chain)] == chain}
    # The engine's accessor form: the full dotted key as a quoted string in code, e.g. A("power.shed_headroom_kw").
    dotted = re.compile(r"[\"']" + re.escape(key) + r"(\.\w+)*[\"']")
    extra = PROV.get(key, {}).get("trace")  # an exact pattern for a use that is not a key lookup
    pats = [(".py", dotted)] + ([(".py", re.compile(extra))] if extra else [])
    if pre == "" and len(chain) == 2 and chain[0] == "positions":  # cards name positions in preferred/allowed
        pats.append((".yaml", re.compile(r"(preferred|allowed):.*\b" + re.escape(chain[1]) + r"\b")))
    for f, lines in TEXTS.items():
        for i, line in enumerate(lines, 1):
            if any(f.endswith(ext) and p.search(line) for ext, p in pats):
                hits.add((f, i))
    return sorted(hits)


def traced(patterns):
    pats = [re.compile(p) for p in patterns]
    return sorted((f, i) for f, lines in TEXTS.items() for i, line in enumerate(lines, 1) if any(p.search(line) for p in pats))


def kinds(hits):
    return ", ".join(sorted({KIND[next(d for d in SCAN if f.startswith(d + "/"))] for f, _ in hits})) or "not yet"


def used_in(keys, hits):
    """Where a row's numbers are used; a key nothing reads adds its status ("documented only"; a measured key "planned")."""
    unread = [PROV[k] for k in keys if not where(k)]
    status = sorted({p.get("status", "measured" if p["source"] == "measured" else "") for p in unread} - {""})
    return ", ".join(([kinds(hits)] if hits else []) + status) or "not yet"


def refs(hits, limit=4):
    out = [f"{f}:{i}" for f, i in hits[:limit]]
    return ", ".join(out) + (f" (+{len(hits) - limit} more)" if len(hits) > limit else "") if out else "not yet"


# ---------------------------------------------------------------- render

def render():
    """Write both pages; stops if an assumed or measured key is in no row."""
    assumed = [k for k, p in PROV.items() if p["source"] == "assumed"]
    measured = [k for k, p in PROV.items() if p["source"] == "measured"]
    rows = ACC["rows"]
    covered = [k for r in rows for k in r.get("keys", [])]
    missing = [k for k in assumed + measured if k not in covered]
    unknown = [k for k in covered if PROV.get(k, {}).get("source") not in ("assumed", "measured")]
    if missing or unknown:
        sys.exit(f"Physical Account: assumed or measured keys in no row: {missing}; row keys that are neither: {unknown}")

    # The one-page table is HTML inside the Markdown so it can carry Annex C's column widths; a pipe table
    # lets the browser squeeze the reasons column and the page overflows.
    cells = lambda tag, xs: "<tr>" + "".join(f"<{tag}>{html.escape(str(x), quote=False)}</{tag}>" for x in xs) + "</tr>"
    one = ["# Physical Account", "", " ".join(ACC["intro"].split()), "", "<table>",
           "<colgroup>" + "".join(f'<col style="width:{w}%">' for w in ACC["widths"]) + "</colgroup>",
           "<thead>" + cells("th", ["Annex C row", "What we assumed", "Value", "Why", "Used in"]) + "</thead>", "<tbody>"]
    last = None
    for r in rows:
        hits = sorted({h for k in r.get("keys", []) for h in where(k)} | set(traced(r.get("trace", []))))
        one.append(cells("td", [r["row"] if r["row"] != last else "", r["what"], fill(r["value"]), r["why"], used_in(r.get("keys", []), hits)]))
        last = r["row"]
    # A non-breaking space keeps "30 °C" on one line.
    one += ["</tbody>", "</table>", "", re.sub(r"(\d) °C", "\\1\u00a0°C", fill(" ".join(ACC["closing"]["text"].split())))]
    (ROOT / "docs/PHYSICAL_ACCOUNT.md").write_text("\n".join(one) + "\n")

    det = ["# Physical Account, detail", "",
           "Full reasons and every file:line that reads each assumed or measured key. One-page version: [PHYSICAL_ACCOUNT.md](PHYSICAL_ACCOUNT.md).",
           "A key counts as read where a line names its full dotted key, or reads it through a subscript chain on a variable",
           "loaded from its YAML file; a key nothing reads shows its status (documented only, planned) or \"not yet\".", "",
           "| Key | Value | Why | Where used |", "|---|---|---|---|"]
    for r in rows:
        for k in r.get("keys", []):
            hits = where(k)
            status = PROV[k].get("status") if not hits else None  # "documented only", or "planned" for a measured key
            det.append(f"| `{k}` | {shown(lookup(k))} | {PROV[k]['why']} | {status or refs(hits)} |")
    det += ["", "## Guest-card values we assumed", "",
            "Card lines marked `assumed: true`: at least one number on the line is ours, not Annex B's. G6 is wholly our invention.", "",
            "| Card line | Where |", "|---|---|"]
    for f, lines in TEXTS.items():
        if f.startswith("manifests/G") and f.endswith(".yaml"):
            det += [f"| `{line.strip()[:110]}` | {f}:{i} |" for i, line in enumerate(lines, 1) if "assumed: true" in line]
    from_brief = {k: p for k, p in PROV.items() if p["source"].startswith("brief")}
    narrowed = {k: p["narrowed"] for k, p in from_brief.items() if p.get("narrowed")}
    unchanged = sorted(k for k in from_brief if k not in narrowed)
    det += ["", "Taken from the brief, then narrowed by the rows above: " +
            "; ".join(f"`{k}`: {why}" for k, why in narrowed.items()) + ".", "",
            "Taken from the brief without change: " + ", ".join(f"`{k}`" for k in unchanged) + ".", "",
            "The closing answer's numbers are derived from these files by tools/physical_account.py, which stops if any of its",
            "claims no longer holds; tests/test_scenario_b_timeline_data.py checks them again."]
    (ROOT / "docs/PHYSICAL_ACCOUNT_DETAIL.md").write_text("\n".join(det) + "\n")
    print(f"wrote one-page account ({len(rows)} rows, {len(assumed)} assumed and {len(measured)} measured keys, {len(CARDS)} cards) and detail page")


if __name__ == "__main__":
    render()
