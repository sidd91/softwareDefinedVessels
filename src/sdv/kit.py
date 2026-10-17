"""The Deployment Reference Kit (DEC-57) and the governor's computers (DEC-56).

    sdv kit plan                      the boards, edge nodes and kit copies for this hull, and what each device holds
    sdv kit build [--out dist/kit]    the kit: vessel, governor runbook, one datasheet per guest, manifest with checksums
    sdv kit verify DIR                every file against the manifest (each device runs this after a port upload)
    sdv kit install KIT --root DIR    staged install: copy to the idle slot, verify, switch, keep the old slot for rollback

Everything in the kit is generated from the repository (cards, ship profile, signals, docs), so it cannot drift from
what the governor runs. Vendor manuals are listed per guest as required documents; the kit does not invent them.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from sdv import ledger as Lg
from sdv import loader as Ld

ROOT = Ld.ROOT
ZONE_SITE = {"bay": "mission_bays", "mast": "bridge", "flight_deck": "hangar_flight_deck", "hangar_roof": "hangar_flight_deck",
             "ramp": "stern_ramp"}
VESSEL_DOCS = ["README.md", "docs/ARCHITECTURE.md", "docs/STATE_ESTIMATION.md", "docs/PHYSICAL_ACCOUNT.md",
               "docs/PHYSICAL_ACCOUNT_DETAIL.md", "docs/SCENARIO_C_MEMO.md", "docs/DEPLOYMENT.md", "manifests/README.md"]
CONFIG = ["config/assumptions.yaml", "config/signals.yaml", "config/missions/*.yaml", "manifests/G*.yaml", "manifests/schema.json",
          "config/missions/schema.json"]
VENDOR_DOCS = ["operator manual", "maintenance manual", "safety data and emergency procedure", "electrical and data interface specification"]


# ---------------------------------------------------------------------------------------------- the computers
def governor_boards(A: dict) -> int:
    """Two boards on any hull, one more per started 25 m beyond the first 25 m (DEC-56): 60 m gives 4."""
    b = A["governor"]["boards"]
    extra = max(0.0, A["hull"]["loa_m"] - b["base_loa_m"])
    return b["base"] + math.ceil(extra / b["per_extra_m"])


def devices(A: dict) -> list[dict]:
    g = A["governor"]
    out = []
    roles = list(g["roles"])
    for i in range(governor_boards(A)):
        role = roles[i] if i < len(roles) else f"zone_{i - len(roles) + 3}"
        out.append({"id": f"board-{i + 1}", "kind": "board", "role": role, "site": g["placement"].get(role, "hull"),
                    "storage_gb": g["board"]["storage_gb"], "share_gb": g["kit"]["share_gb"]["board"]})
    for site in g["edge_nodes"]["sites"]:
        out.append({"id": f"edge-{site}", "kind": "edge", "role": "local monitoring and shed table", "site": site,
                    "storage_gb": g["edge_nodes"]["storage_gb"], "share_gb": g["kit"]["share_gb"]["edge"]})
    for i, place in enumerate(g["kit"]["ssd_places"][: g["kit"]["copies"]["ssd"]]):
        out.append({"id": f"ssd-{i + 1}", "kind": "ssd", "role": "offline backup copy", "site": place,
                    "storage_gb": g["kit"]["ssd_gb"], "share_gb": g["kit"]["ssd_gb"]})
    out.append({"id": "print-1", "kind": "print", "role": "printed binder", "site": "bridge", "storage_gb": None, "share_gb": None})
    return out


def guest_sites(card: dict, A: dict) -> list[str]:
    sites = set()
    for part in card["placement"]["parts"]:
        for pos in part["allowed"]:
            spec = A["positions"].get(pos.split("_half")[0])
            spec = spec if isinstance(spec, dict) else {}
            zone = spec.get("zone") or spec.get("kind")
            sites.add(ZONE_SITE.get(zone, "mission_bays"))
    if card["placement"].get("uses_ramp"):
        sites.add("stern_ramp")
    return sorted(sites)


# ---------------------------------------------------------------------------------------------- generated pages
def _modes_table(card: dict) -> str:
    rows = ["| Mode | kW | Capability kept | Interruptible | Lasts |", "|---|---|---|---|---|"]
    for m in sorted(card["modes"], key=lambda m: -m["power_kw"]):
        lasts = f"{m['duration_s'] // 60} min" if m.get("duration_s") else ""
        rows.append(f"| {m['name']} | {m['power_kw']} | {round(100 * m['capability_retained'])} % | "
                    f"{'no' if m.get('interruptible', True) is False else 'yes'} | {lasts} |")
    return "\n".join(rows)


def _pred(v) -> str:
    if isinstance(v, dict):
        lo, hi = v.get("min"), v.get("max")
        return f"{lo} to {hi}" if lo is not None and hi is not None else (f"at least {lo}" if lo is not None else f"at most {hi}")
    if isinstance(v, list):
        return " or ".join(map(str, v))
    return str(v).lower() if isinstance(v, bool) else str(v)


def guest_page(card: dict, A: dict, signals: dict, missions: dict, cards: dict) -> str:
    gid = card["id"]
    cap = card["capability"]
    sig = [s for s in signals["signals"] if s["name"].startswith(gid + ".")]
    lines = [f"# {gid}: {card['name']}", "",
             f"Card version {card['version']}, source: {card.get('source', 'card')}. Capability: {cap['name']}, {cap['description']}",
             "", "## Technical data", "", _modes_table(card), "", "| Draws | Value |", "|---|---|"]
    for k, v in card["consumes"].items():
        lines.append(f"| {k} | {', '.join(f'{a} {b}' for a, b in v.items() if a not in ('note', 'assumed'))} |")
    lines += ["", "| Part | Mass | Preferred | Allowed |", "|---|---|---|---|"]
    for p in card["placement"]["parts"]:
        lines.append(f"| {p['name']} | {p['mass_t']} t | {', '.join(p['preferred'])} | {', '.join(p['allowed'])} |")
    lines += ["", f"Cooling: {card.get('cooling', 'n/a')}. Kit copies at: {', '.join(guest_sites(card, A))}.", "", "## Operating conditions", ""]
    for c in card.get("conditions", []):
        lines.append(f"- **{c['activity']}** needs " + ", ".join(f"{k} {_pred(v)}" for k, v in c["requires"].items()) + ".")
    for h in card.get("hard_limits", []):
        w, t = h["when"], h["then"]
        within = f" within {t['within_min']} min" if t.get("within_min") else (f" to {t['mode']}" if t.get("mode") else "")
        lines.append(f"- **Hard limit:** when {w['signal']} {w['op']} {w['value']}, {t['action'].replace('_', ' ')}{within}.")
    for x in (card.get("relations") or {}).get("excludes", []):
        lines.append(f"- **Excludes:** its {x['activity']} cannot run with {x['excludes']}.")
    lines += ["", "## Priority by mission profile", "", "| Profile | Weight | Tier |", "|---|---|---|"]
    for m in missions.values():
        lines.append(f"| {m['name']} | {m['weights'].get(cap['name'], 0)} | {Lg.tier_of(cards, gid, m).replace('_', ' ')} |")
    lines += ["", "## Troubleshooting", "", "| ArgOS shows | What it means | What to check |", "|---|---|---|"]
    for s in sig:
        if s["producer"] == "estimator":
            continue
        feed = signals["feeds"].get(s.get("feed"), {})
        after = feed.get("stale_after_s") or feed.get("stale_after_link_up_s")
        rule = s["fallback"].get("rule") or f"taken as {s['fallback'].get('value')}"
        lines.append(f"| {s['name']} STALE | no reading for more than {after} s on the {s.get('feed')} feed | "
                     f"{feed.get('what', s.get('feed'))}. Meanwhile: {rule} |")
    over = next((x for x in signals["signals"] if x["name"] == f"{gid}.overdraw_pct"), None)
    if over:
        d = signals["derivations"]["overdraw"]
        lines.append(f"| {gid} OVER-DRAW | metered kW above the mode's declared kW by more than {d['threshold_pct']} % for {d['hold_s']} s | "
                     "the guest's own load; the ledger counts the metered kW until it falls back |")
    shed = sorted(card["modes"], key=lambda m: -m["power_kw"])
    lines += ["", "## FAQ", "",
              f"**Why did ArgOS move {gid} to a lower mode?** The ship was over its power or cooling limit. ArgOS steps "
              f"guests down in the order the active profile sets: throttles before sheds, discretionary guests first, "
              f"mission-critical last. {gid}'s steps: " + " to ".join(m["name"] for m in shed) + ".",
              "",
              f"**Can {gid} be restored by hand?** Yes, from its own controls. ArgOS will step it down again while the limit binds; "
              "a recovered genset or pump must read healthy for 60 s before ArgOS restores any guest.",
              "", f"**What if {gid}'s feed is lost?** ArgOS keeps a conservative value, marks it STALE and never sheds on it.", "",
              "## Vendor documents (required at admission)", ""]
    vend = ROOT / "docs/kit/vendor" / gid
    for title in VENDOR_DOCS:
        have = vend.exists() and any(title.split()[0] in f.name.lower() for f in vend.iterdir())
        lines.append(f"- {title}: {'supplied' if have else 'not supplied: the operator brings it with the card'}")
    return "\n".join(lines) + "\n"


def runbook(A: dict, signals: dict) -> str:
    g = A["governor"]
    rt = A["response_time_s"]
    lines = ["# ArgOS runbook", "",
             f"{governor_boards(A)} governor boards ({', '.join(g['roles'])}); edge nodes at {', '.join(g['edge_nodes']['sites']).replace('_', ' ')}.",
             "", "| Event | ArgOS does | Crew does |", "|---|---|---|",
             f"| Genset trip | confirms on 2 of 3 votes in 1 s, first step within {rt['shed_first_action']} s, full plan within {rt['shed_full_sequence']} s | check the PMS; restart takes 5 to 15 min |",
             "| Chilled-water pump fault | confirms on alarm or stop plus low flow or high delta-T; steps guests to the cooling limit | restore the pump; ArgOS restores guests 60 s after it reads healthy |",
             "| A feed goes STALE | holds a conservative value, tightens admission, arms the ladder, never sheds on it | check the named feed; the value returns on its first fresh reading |",
             "| Bridge request unanswered | counts as no after its wait (60 s at 14 aboard) | answer on the bridge panel |",
             f"| Primary board lost | the standby, already in step, takes over after {g['takeover_after_s']} s without heartbeat | replace the board at port; any board can be primary |",
             "| Standby out of step | alarm: the two boards decided differently on the same inputs | keep the primary; the logs show the first field that differs |",
             "| Every board lost | each edge node keeps its last shed table; guests hold their modes | restart a board from the SSD copy |",
             "| Profile refused | keeps the previous profile and names the field | fix the field in the builder and apply again |", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------- build, verify, install
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def build(out: Path) -> dict:
    A = Ld.load_assumptions()
    vocab = Ld.load_vocabulary(assumptions=A)
    cards = Ld.load_cards(vocab=vocab)
    missions = Ld.load_missions(cards, vocab)
    signals = yaml.safe_load((ROOT / "config/signals.yaml").read_text())
    if out.exists():
        shutil.rmtree(out)
    files: dict[str, list[str]] = {}
    every = ["all"]

    def put(rel: str, text: str | None = None, src: Path | None = None, sites=every):
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src is not None:
            shutil.copyfile(src, dst)
        else:
            dst.write_text(text)
        files[rel] = list(sites)

    for rel in VESSEL_DOCS:
        if (ROOT / rel).exists():
            put(f"vessel/{rel}", src=ROOT / rel)
    for pattern in CONFIG:
        for p in sorted(ROOT.glob(pattern)):
            put(f"vessel/{p.relative_to(ROOT)}", src=p)
    put("governor/RUNBOOK.md", runbook(A, signals))
    for gid, card in cards.items():
        put(f"guests/{gid}.md", guest_page(card, A, signals, missions, cards), sites=guest_sites(card, A))
    index = ["# Deployment Reference Kit", "", f"Built from commit {_commit()}. Hull {A['hull']['loa_m']} m.", "",
             "- governor/RUNBOOK.md: what ArgOS and the crew do for each event", "- guests/: one datasheet, troubleshooting and FAQ per guest",
             "- vessel/: the ship profile, signals, mission profiles, cards and design documents", ""]
    put("INDEX.md", "\n".join(index))
    manifest = {"kit": "argos-kit/1", "commit": _commit(), "hull_loa_m": A["hull"]["loa_m"],
                "files": [{"path": rel, "bytes": (out / rel).stat().st_size, "sha256": _sha(out / rel), "sites": sites}
                          for rel, sites in sorted(files.items())]}
    manifest["bytes"] = sum(f["bytes"] for f in manifest["files"])
    manifest["placement"] = place(A, manifest)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


def place(A: dict, manifest: dict) -> list[dict]:
    """What each device holds: the full kit if it fits the device's share, else its site's part plus the shared files."""
    full = manifest["bytes"]
    out = []
    for d in devices(A):
        if d["kind"] == "print":
            out.append({**d, "holds": "full kit, printed"})
            continue
        if full <= d["share_gb"] * 1e9:
            out.append({**d, "holds": "full kit", "bytes": full})
        else:
            part = sum(f["bytes"] for f in manifest["files"] if "all" in f["sites"] or d["site"] in f["sites"])
            out.append({**d, "holds": f"{d['site']} part", "bytes": part})
    return out


def verify(kit: Path) -> list[str]:
    """Every problem: a missing file, a changed file, or a file the manifest does not list."""
    m = json.loads((kit / "manifest.json").read_text())
    problems = []
    listed = set()
    for f in m["files"]:
        p = kit / f["path"]
        listed.add(f["path"])
        if not p.exists():
            problems.append(f"missing {f['path']}")
        elif _sha(p) != f["sha256"]:
            problems.append(f"changed {f['path']}")
    for p in kit.rglob("*"):
        rel = str(p.relative_to(kit))
        if p.is_file() and rel != "manifest.json" and rel not in listed:
            problems.append(f"not in manifest {rel}")
    return problems


def install(kit: Path, root: Path) -> dict:
    """Port upload on one device: copy to the idle slot, verify there, then switch `current`; the old slot stays for rollback."""
    root.mkdir(parents=True, exist_ok=True)
    cur = root / "current"
    active = cur.resolve().name if cur.is_symlink() else None
    idle = "slot_b" if active == "slot_a" else "slot_a"
    target = root / idle
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(kit, target)
    problems = verify(target)
    if problems:
        shutil.rmtree(target)
        return {"installed": False, "kept": active, "problems": problems}
    tmp = root / "current.new"
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(idle, tmp)
    os.replace(tmp, cur)
    return {"installed": True, "slot": idle, "rollback": active, "commit": json.loads((target / "manifest.json").read_text())["commit"]}


def rollback(root: Path) -> str | None:
    cur = root / "current"
    active = cur.resolve().name if cur.is_symlink() else None
    other = "slot_b" if active == "slot_a" else "slot_a"
    if not (root / other).exists():
        return None
    tmp = root / "current.new"
    os.symlink(other, tmp)
    os.replace(tmp, cur)
    return other
