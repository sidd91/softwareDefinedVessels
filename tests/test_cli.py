"""The `sdv` command end to end: admit (with a live edit and a jury card file), demo without the prompt,
sim with the governor and replay-check."""
import json

import pytest

from sdv import cli


def run(capsys, *argv):
    code = cli.main(["--no-color", *argv])
    return code, capsys.readouterr().out


def test_admit_prints_the_verdict_sentence_ledger_and_options(capsys):
    code, out = run(capsys, "admit", "G4", "--installed", "G1,G2,G3", "--mission", "sar")
    assert code == 0 and out.startswith("D1 YES-IF for G4 under sar")
    assert "Yes-if. Binding: mass, 10.04 of 10 t; 0.04 t over." in out
    assert "mass          10.04 / 10       t FAILS" in out and "option 1: remove G3  value lost 0.2" in out
    assert "one genset down: 81.5 of 100 kW, gate 95 kW: holds" in out


def test_admit_live_edit_flips_a1_to_yes_and_json_carries_the_record(capsys):
    code, out = run(capsys, "admit", "G4", "--installed", "G1,G2,G3", "--edit", "G4.hangar.mass_t=0.8", "--json")
    assert code == 0 and "D1 YES for G4 under survey" in out and "Yes. Binding: mass, 9.99 of 10 t" in out
    rec = json.loads(out[out.index("{"):])
    assert rec["kind"] == "D1" and rec["verdict"] == "yes" and rec["within_ceiling"] and rec["card_edits"] == {"G4.hangar.mass_t": 0.8}


def test_admit_takes_a_jury_card_file_and_refuses_one_that_breaks_the_schema(capsys, tmp_path):
    card = tmp_path / "G9.yaml"
    card.write_text(
        "id: G9\nname: Jury container\nversion: 1\nsource: jury\n"
        "capability: {name: ocean_data, description: x}\ncooling: chilled_water\n"
        "placement: {parts: [{name: box, mass_t: 2.0, preferred: [bay2], allowed: [bay2, bay1_half]}]}\n"
        "consumes: {power_kw: {nominal: 30}}\n"
        "modes: [{name: full, power_kw: 30, capability_retained: 1.0}, {name: 'off', power_kw: 0, capability_retained: 0.0}]\n"
        "installation: {port: {people: 2, hours: 4}}\ncriticality: {safety_critical: false, mission_critical: per priority file}\n")
    code, out = run(capsys, "admit", "--card-file", str(card), "--installed", "G4,G5", "--mission", "sar")
    assert code == 0 and "D1 YES for G9 under sar" in out and "G9.box=bay1_half" in out  # Bay 2 is G5's
    code, out = run(capsys, "admit", "--card-file", str(card), "--installed", "G3,G4,G5", "--mission", "sar")
    assert code == 0 and "D1 YES-IF for G9 under sar" in out and "G9.box=NONE" in out and "Binding: mass, 11.52 of 10 t" in out
    card.write_text("id: G9\nname: broken\n")
    with pytest.raises(Exception):
        cli.main(["admit", "--card-file", str(card), "--installed", "G3"])


def test_demo_without_prompt_runs_both_files_and_drill_a1(capsys):
    code, out = run(capsys, "demo", "--speed", "0", "--no-prompt")
    assert code == 0
    assert "8.00 min  D3 G4 proceeds  [survey]" in out and "12.00 min  D4 holds  [survey]" in out and "19.00 min  D4 throttled  [survey]" in out
    assert "Same events under the sar file" in out and "sar: Chilled-water loop binds: 81 of 75 kW, 6 kW short. G5 to low_power" in out
    assert "every decision inside its ceiling: True" in out and "D1 YES-IF for G4 under survey" in out


def test_sim_with_governor_writes_a_run_and_replay_check_is_identical(capsys, tmp_path):
    out_file = tmp_path / "run.jsonl"
    code, out = run(capsys, "sim", "scenario-b", "--mission", "sar", "--until-min", "20", "--quiet", "--out", str(out_file))
    assert code == 0 and "decisions" in out
    lines = out_file.read_text().splitlines()
    trailer = json.loads(lines[-1])
    assert trailer["decisions"] and trailer["decisions"][0]["kind"] in ("D3", "D4")
    code, out = run(capsys, "replay-check", "scenario-b", "--mission", "sar", "--until-min", "20")
    assert code == 0 and out.strip().endswith("IDENTICAL")
