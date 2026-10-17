"""Render docs/PHYSICAL_ACCOUNT.md from config/assumptions.yaml.

Each assumed number lists where it is used, found by searching the repo for its key. Run:
    uv run python tools/physical_account.py
"""
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
A = yaml.safe_load((ROOT / "config/assumptions.yaml").read_text())


def lookup(dotted):
    node = A
    for k in dotted.split("."):
        node = node[k] if isinstance(node, dict) and k in node else None
        if node is None:
            return None
    return node


def used_in(dotted):
    leaf = dotted.split(".")[-1]
    out = subprocess.run(
        ["git", "grep", "-n", "-w", leaf, "--", "src", "tests", "tools", "manifests"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()
    hits = [line.split(":")[0] + ":" + line.split(":")[1] for line in out if "physical_account.py" not in line]
    return ", ".join(sorted(set(hits))[:4]) or "not yet used in code"


rows = []
for key, prov in A["provenance"].items():
    if prov["source"] != "assumed":
        continue
    val = lookup(key)
    shown = yaml.safe_dump(val, default_flow_style=True, width=200).strip() if isinstance(val, (dict, list)) else str(val)
    rows.append(f"| `{key}` | {shown} | {prov['why']} | {used_in(key)} |")

brief = sorted(k for k, p in A["provenance"].items() if p["source"] != "assumed")
md = ["# Physical Account (draft)", "",
      "Generated from `config/assumptions.yaml` by `tools/physical_account.py`. Every number the",
      "software relies on that is not in Annex A or B, or that narrows a range given there.", "",
      "| Key | Value | Why | Where used |", "|---|---|---|---|", *rows, "",
      "Taken from the brief without change: " + ", ".join(f"`{k}`" for k in brief) + ".", "",
      "Guest-card assumptions are marked `assumed: true` in `manifests/G*.yaml`; G6 is wholly ours.", "",
      "Closing question (draft): more generation. Real 88-95 m patrol ships carry 1.8-2.7 MW;",
      "the reference platform's 900 kW is what makes one genset trip a crisis. To be finalized."]
(ROOT / "docs/PHYSICAL_ACCOUNT.md").write_text("\n".join(md) + "\n")
print(f"wrote docs/PHYSICAL_ACCOUNT.md with {len(rows)} assumed numbers")
