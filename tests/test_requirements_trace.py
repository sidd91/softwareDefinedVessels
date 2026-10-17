"""Keeps docs/requirements.yaml honest: every link resolves, every heading anchor exists,
every decision ID is in WORKLOG.md, and IDs are unique. Rename a heading, and this test
points at the rows to fix."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQS = yaml.safe_load((ROOT / "docs/requirements.yaml").read_text())["requirements"]
WORKLOG_IDS = set(re.findall(r"^\| ((?:DEC|CON|DEF)-\d\d) ", (ROOT / "WORKLOG.md").read_text(), re.M))


def slug(title):
    return "".join(c for c in title.lower() if c.isalnum() or c in " -").replace(" ", "-")


def headings(path, _cache={}):
    if path not in _cache:
        text = (ROOT / path).read_text(errors="ignore")
        _cache[path] = {slug(h.strip()) for h in re.findall(r"^#{1,6} (.+)$", text, re.M)}
    return _cache[path]


def test_requirement_ids_are_unique_and_well_formed():
    ids = [r["id"] for r in REQS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"R-\d{3}", i) for i in ids)


def test_every_link_and_anchor_resolves():
    broken = []
    for r in REQS:
        for link in r.get("links", []):
            path, _, anchor = link["path"].partition("#")
            if not (ROOT / path).exists() or (anchor and anchor not in headings(path)):
                broken.append(f"{r['id']}: {link['path']}")
    assert not broken, broken[:20]


def test_every_decision_id_exists_in_the_worklog():
    unknown = [f"{r['id']}: {d}" for r in REQS for d in r.get("decisions", []) if d not in WORKLOG_IDS]
    assert not unknown, unknown[:20]


def test_status_values_are_known():
    assert {r["status"] for r in REQS} <= {"done", "drafted", "planned", "gap", "not-applicable"}
