"""The sdv admit command prints the D1 verdict from the real engine and refuses a bad one-number edit."""
from sdv import cli


def test_admit_the_35_kg_case(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3"]) == 0
    out = capsys.readouterr().out
    assert "VERDICT YES-IF" in out and "BINDING mass 10.035 / 10 t" in out
    assert "1. remove G1: value lost 0.2, mass 9.99 t" in out
    assert "/ 30 s" in out


def test_a_one_number_edit_flips_it(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.hangar.mass_t=0.8"]) == 0
    out = capsys.readouterr().out
    assert "card re-validated" in out and "VERDICT YES " in out and "BINDING mass 9.985 / 10 t" in out


def test_a_bad_edit_is_refused_with_the_field(capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3", "--set", "G4.hangar.mass_t=-1"]) == 2
    out = capsys.readouterr().out
    assert "refused" in out and "mass_t" in out and "Previous card kept" in out


def test_unknown_priority_file_is_refused(capsys):
    assert cli.main(["admit", "G4", "--mission", "fishing"]) == 2
    assert "no priority file 'fishing'" in capsys.readouterr().out
