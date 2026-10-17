"""Render docs/REQUIREMENTS.md from docs/requirements.yaml (the source of truth).

Edit rows in docs/requirements.yaml, then run:
    uv run python tools/render_requirements.py
New requirements take the next free ID; IDs are never reused or renumbered.
"""
from collections import Counter
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = yaml.safe_load((ROOT / "docs/requirements.yaml").read_text())
TITLES = {
    "deliverable": "Deliverables", "framing": "Problem framing and resource classes", "must-have": "Must-have success criteria",
    "should-have": "Should-have success criteria", "decision-class": "Decision classes (D1 to D6)",
    "judging": "What we are judged on", "scenario": "Reference scenarios", "demo": "Live demo",
    "platform-model": "Platform model and ship state (Annex A)",
    "guest-manifest": "Guest manifest and cards (Annex B)", "physical-account": "Physical Account (Annex C)",
    "constraint": "Constraints", "stack-data": "Stack, data and tools", "out-of-scope": "Out of scope",
    "data-use-ai": "Data use and AI rules",
}
STATUS_ORDER = ["done", "drafted", "planned", "gap", "not-applicable"]


def esc(t):
    return " ".join(str(t or "").split()).replace("|", "\\|")


def link(path):
    return path[5:] if path.startswith("docs/") else "../" + path


def slug(title):
    keep = "".join(c for c in title.lower() if c.isalnum() or c in " -")
    return keep.replace(" ", "-")


reqs = DATA["requirements"]
cats = DATA["meta"]["categories"]
status = Counter(r["status"] for r in reqs)
called = [r for r in reqs if r["called_out"]]
lines = [
    "# Requirements traceability",
    "",
    "Generated from `docs/requirements.yaml` by `tools/render_requirements.py`; edit the YAML, not this file.",
    f"Built {DATA['meta']['built']}, from every page of the slides and the brief, including the organizers'",
    "corrections: " + "; ".join(DATA["meta"]["corrections"]) + ".",
    "",
    "**How to use it.** Each row says how we address a requirement, links the files and WORKLOG decisions",
    "that do it, gives an honest status, and asks one brainstorming question for direction and scope.",
    "Rows marked **Called out** are named explicitly by the slides or brief and must be answered at a",
    "granular level (WORKLOG DEC-24). When work changes how a requirement is addressed, edit its row in",
    "the YAML, re-render, and cite the ID in WORKLOG rows and entries (WORKLOG rules 8 and 9).",
    "Status: done = finished and evidenced; drafted = a draft exists for review; planned = in the plan,",
    "not built; gap = nothing addresses it yet; not-applicable = out of scope by the brief.",
    "",
    "## Summary",
    "",
    "| Section | Rows | Called out | " + " | ".join(STATUS_ORDER) + " |",
    "|---|---|---|" + "---|" * len(STATUS_ORDER),
]
for c in cats:
    rs = [r for r in reqs if r["category"] == c]
    if not rs:
        continue
    sc = Counter(r["status"] for r in rs)
    lines.append(f"| [{TITLES[c]}](#{slug(TITLES[c])}) | {len(rs)} | {sum(r['called_out'] for r in rs)} | "
                 + " | ".join(str(sc.get(s, 0)) for s in STATUS_ORDER) + " |")
lines.append(f"| **All** | **{len(reqs)}** | **{len(called)}** | "
             + " | ".join(f"**{status.get(s, 0)}**" for s in STATUS_ORDER) + " |")
lines += ["", "## Gaps", "", "Rows with status gap. Called-out rows still only planned are counted in the summary above.", ""]
gaps = [r for r in reqs if r["status"] == "gap"]
lines += [f"- **{r['id']}**{' (called out)' if r['called_out'] else ''}: {esc(r['requirement'])}" for r in gaps] or ["- none"]
for c in cats:
    rs = [r for r in reqs if r["category"] == c]
    if not rs:
        continue
    lines += ["", f"## {TITLES[c]}", "",
              "| ID | Requirement and source | How we address it | Links and decisions | Status | Brainstorm question |",
              "|---|---|---|---|---|---|"]
    for r in rs:
        links = [f"[{esc(l['label'])}]({link(l['path'])})" for l in r.get("links", [])]
        links += [f"[{d}](../WORKLOG.md)" for d in r.get("decisions", [])]
        src = "; ".join(r["sources"])
        lines.append(
            f"| {r['id']} | {'**Called out.** ' if r['called_out'] else ''}{esc(r['requirement'])} "
            f"*({esc(src)}: \"{esc(r['quote'])}\")* | {esc(r['how'])} | {', '.join(links) or '-'} | "
            f"{r['status']} | {esc(r['question'])} |")
(ROOT / "docs/REQUIREMENTS.md").write_text("\n".join(lines) + "\n")
print(f"rendered {len(reqs)} requirements; status {dict(status)}")
