"""tools/physical_account.py's "Where used" tracer sees the engine's reads of config/assumptions.yaml.

The engine never names the file: it receives the assumptions as a parameter or attribute called A
(admission_lines(A, ...), self.A, I.A), so the tracer seeds those names in every module under src/. These tests
pin that, the guard against a seeded name rebound to something else, and the directory walk the tool falls back
to outside a git checkout (a worktree export). Importing the tool computes the trace but writes no page.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"tools/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PA = _tool("physical_account")


@pytest.mark.parametrize("key", ["power.shed_headroom_kw", "heat.degraded_factor", "mass.multiplier", "response_time_s",
                                 "envelope.judge_cooling_at_c", "rules.r3.secure_s", "governor.boards",
                                 "data.acoustic_link.judged_latency_s", "positions.bay1.power_line"])
def test_engine_reads_resolve_to_a_src_file(key):
    files = {f for f, _ in PA.where(key)}
    assert any(f.startswith("src/") for f in files), (key, sorted(files))


def test_prefixed_reads_and_aliases_count_and_rebound_seeds_do_not(monkeypatch):
    src = ["def f(A, modes):",
           "    a = modes[0]",
           "    return a['power'], A['power']['shed_headroom_kw'], A['power']['no_such_key']",
           "def g(I, self):",
           "    r3 = self.A['rules']['r3']",
           "    return r3['secure_s'], I.A['heat']['degraded_factor']"]
    monkeypatch.setattr(PA, "TEXTS", {"src/sdv/synthetic.py": src})
    reads = {(i, tuple(c)) for _, i, pre, c in PA.python_reads() if pre == ""}
    assert (3, ("power", "shed_headroom_kw")) in reads
    assert (3, ("power",)) not in reads  # `a` is a mode here, not the assumptions
    assert (3, ("power", "no_such_key")) not in reads  # not a path in the file
    assert (5, ("rules", "r3")) in reads and (6, ("rules", "r3", "secure_s")) in reads
    assert (6, ("heat", "degraded_factor")) in reads


def test_a_seed_reassigned_the_assumptions_keeps_reading(monkeypatch):
    src = ["def f(root):",
           "    A = Ld.load_assumptions(root)",
           "    a = assumptions if assumptions is not None else load_assumptions(root)",
           "    return A['mass']['multiplier'], a['mass']['margin_t']"]
    monkeypatch.setattr(PA, "TEXTS", {"src/sdv/synthetic.py": src})
    reads = {(i, tuple(c)) for _, i, pre, c in PA.python_reads() if pre == ""}
    assert (4, ("mass", "multiplier")) in reads and (4, ("mass", "margin_t")) in reads


def test_names_are_seeded_under_src_only(monkeypatch):
    monkeypatch.setattr(PA, "TEXTS", {"tests/test_synthetic.py": ["def f(A):", "    return A['power']['shed_headroom_kw']"]})
    assert PA.python_reads() == []


def test_directory_walk_stands_in_when_git_lists_nothing(monkeypatch):
    listed = set(PA.TEXTS)
    monkeypatch.setattr(PA.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 128, "", "not a git repository"))
    walked = set(PA.scanned())
    assert listed <= walked
    assert not any("__pycache__" in f or f.endswith(".pyc") for f in walked)
