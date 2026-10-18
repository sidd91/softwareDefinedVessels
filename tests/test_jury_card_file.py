"""A card the jury hands over as a file: `sdv admit --card` admits it or refuses it with the field named, and a bad
file in manifests/ is reported once at start-up without stopping `sdv admit` or `sdv demo`."""
import copy
import json
import shutil
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn
import yaml

from sdv import cli
from sdv import loader as Ld
from sdv.ui import data

VOCAB = Ld.load_vocabulary()
G6 = Ld.load_card(Ld.ROOT / "manifests/G6.yaml", VOCAB)
SIX = ["G1", "G2", "G3", "G4", "G5", "G6"]


def g7(mass_t=3.2) -> dict:
    """The jury's file: G6 copied as G7 with the unit at mass_t (no activity registry for G7 in config/signals.yaml)."""
    card = copy.deepcopy(G6)
    card["id"] = "G7"
    card["placement"]["parts"][0]["mass_t"] = mass_t
    return card


def write(path, card) -> str:
    path.write_text(yaml.safe_dump(card, sort_keys=False))
    return str(path)


# ------------------------------------------------------------------------------------------------ sdv admit --card

def test_a_jury_file_is_admitted_through_the_cli(tmp_path, capsys):
    path = write(tmp_path / "G7.yaml", g7())
    assert cli.main(["admit", "G7", "--card", path, "--installed", "G4,G5", "--mission", "disaster_relief"]) == 0
    out = capsys.readouterr().out
    assert f"loaded: G7 from {path}, card validated" in out
    assert "G7 activities not registered: conditions not judged (2 on the card)" in out
    assert "VERDICT YES · G7 onto G4, G5 · mission disaster_relief" in out
    assert "BINDING heat 98 / 120 kW" in out and "G7.unit bay1_half" in out and "SEAWATER TIP 39.9 °C" in out


def test_the_path_alone_names_the_card(tmp_path, capsys):
    path = write(tmp_path / "G7.yaml", g7())
    assert cli.main(["admit", path, "--installed", "G1,G2,G3"]) == 0
    out = capsys.readouterr().out
    assert "VERDICT YES-IF · G7 onto G1, G2, G3 · mission survey" in out
    assert "BINDING mass 12.245 / 10 t" in out and "Mass binds: 12.245 t against 10 t" in out


def test_a_registered_card_as_a_file_says_nothing_about_activities(tmp_path, capsys):
    path = write(tmp_path / "G4.yaml", Ld.load_card(Ld.ROOT / "manifests/G4.yaml", VOCAB))
    assert cli.main(["admit", "--card", path, "--installed", "G1,G2,G3"]) == 0
    out = capsys.readouterr().out
    assert "activities not registered" not in out and "BINDING mass 10.035 / 10 t" in out


def test_a_one_number_edit_applies_to_the_jury_card(tmp_path, capsys):
    path = write(tmp_path / "G7.yaml", g7())
    assert cli.main(["admit", "--card", path, "--installed", "G4,G5", "--mission", "disaster_relief", "--set", "G7.unit.mass_t=2.8"]) == 0
    out = capsys.readouterr().out
    assert "edited: G7.unit.mass_t = 2.8, card re-validated" in out and "mass                   6.815 / 10" in out


def schema_error(card):
    card["placement"]["parts"][0]["mass_t"] = "abc"


def vocabulary_error(card):
    card["conditions"][0]["requires"]["noise"] = ["loud"]


def unknown_signal(card):
    card["hard_limits"][0]["when"]["signal"] = "battery"


BAD_FILES = [
    ("schema", schema_error, "placement.parts[0].mass_t: 'abc' is not of type 'number'"),
    ("vocabulary", vocabulary_error, "conditions[0].requires.noise: ['loud'] not among"),
    ("unknown signal", unknown_signal, "hard_limits[0].when.signal: unknown signal 'battery'"),
]


@pytest.mark.parametrize("label,mutate,expected", BAD_FILES, ids=[b[0] for b in BAD_FILES])
def test_a_bad_jury_file_is_refused_with_the_field_named(tmp_path, capsys, label, mutate, expected):
    card = g7()
    mutate(card)
    path = write(tmp_path / "G7.yaml", card)
    assert cli.main(["admit", "--card", path, "--installed", "G4,G5"]) == 2
    out = capsys.readouterr().out
    assert f"refused {path}: {expected}" in out and "VERDICT" not in out


def test_a_file_yaml_cannot_read_is_refused_at_its_line(tmp_path, capsys):
    path = tmp_path / "G7.yaml"
    path.write_text("id: G7\nname: [unclosed\n")
    assert cli.main(["admit", "--card", str(path)]) == 2
    out = capsys.readouterr().out
    assert f"refused {path}: yaml: " in out and "line 3, column 1" in out


def test_a_path_that_cannot_be_read_is_refused_not_a_traceback(tmp_path, capsys):
    """A mistyped path on stage ends in the one refusal line and exit 2, never a Python traceback."""
    missing = tmp_path / "nope.yaml"
    assert cli.main(["admit", "--card", str(missing), "--installed", "G4,G5"]) == 2
    assert f"refused {missing}: file: No such file or directory" in capsys.readouterr().out
    assert cli.main(["admit", str(missing)]) == 2                                  # the path in place of the id too
    assert f"refused {missing}: file: No such file or directory" in capsys.readouterr().out
    folder = tmp_path / "G7.yaml"
    folder.mkdir()
    assert cli.main(["admit", "--card", str(folder)]) == 2
    assert f"refused {folder}: file: Is a directory" in capsys.readouterr().out
    binary = tmp_path / "G8.yaml"
    binary.write_bytes(b"\xff\xfeid: G8\n")
    assert cli.main(["admit", "--card", str(binary)]) == 2
    assert f"refused {binary}: file: not UTF-8 text (invalid start byte at byte 0)" in capsys.readouterr().out


def test_the_file_must_be_the_card_named(tmp_path, capsys):
    path = write(tmp_path / "G7.yaml", g7())
    assert cli.main(["admit", "G6", "--card", path]) == 2
    assert f"refused: {path} is card G7, not G6" in capsys.readouterr().out
    assert cli.main(["admit"]) == 2
    assert "refused: no card given" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ a bad file in manifests/

@pytest.fixture
def manifests(tmp_path, monkeypatch):
    """The six cards plus a G7 the loader must refuse (no activity registry), in a directory the loader reads instead."""
    d = tmp_path / "manifests"
    d.mkdir()
    for g in SIX:
        shutil.copy(Ld.ROOT / f"manifests/{g}.yaml", d / f"{g}.yaml")
    write(d / "G7.yaml", g7())
    monkeypatch.setattr(Ld, "manifests_dir", lambda root=Ld.ROOT: d)
    return d


def test_load_cards_reports_a_bad_file_and_keeps_going(manifests):
    bad = copy.deepcopy(G6)
    schema_error(bad)
    write(manifests / "G8.yaml", bad)
    write(manifests / "G9.yaml", copy.deepcopy(G6))                 # a copy that kept G6's id
    (manifests / "G10.yaml").write_text("modes: [\n")
    (manifests / "G11.yaml").mkdir()                                  # a directory the glob matches too
    refused: list[Ld.LoadError] = []
    cards = Ld.load_cards(vocab=VOCAB, refused=refused)
    assert sorted(cards) == SIX and cards["G6"] == G6
    assert [Ld.refusal(e) for e in refused] == [
        f"refused {manifests / 'G10.yaml'}: yaml: expected the node content, but found '<stream end>' at line 2, column 1",
        f"refused {manifests / 'G11.yaml'}: file: Is a directory",
        f"refused {manifests / 'G7.yaml'}: id: G7 has no activity registry in config/signals.yaml",
        f"refused {manifests / 'G8.yaml'}: placement.parts[0].mass_t: 'abc' is not of type 'number'",
        f"refused {manifests / 'G9.yaml'}: id: G6 is already loaded from G6.yaml",
    ]
    assert sorted(Ld.load_cards(vocab=VOCAB)) == SIX                 # with nobody collecting, still no raise


def test_refusal_names_a_repo_file_relative_to_the_repo():
    err = Ld.LoadError(Ld.ROOT / "manifests/G7.yaml", ["id: G7 has no activity registry in config/signals.yaml", "later"])
    assert Ld.refusal(err) == "refused manifests/G7.yaml: id: G7 has no activity registry in config/signals.yaml"


def test_admit_prints_the_refusal_once_and_still_runs(manifests, capsys):
    assert cli.main(["admit", "G4", "--installed", "G1,G2,G3"]) == 0
    out = capsys.readouterr().out
    assert out.count("refused") == 1 and f"refused {manifests / 'G7.yaml'}: id: G7 has no activity registry" in out
    assert "VERDICT YES-IF" in out
    assert cli.main(["admit", "G7", "--installed", "G4,G5"]) == 2
    out = capsys.readouterr().out
    assert f"refused {manifests / 'G7.yaml'}: id: G7" in out and "refused: no card G7" in out


def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.monotonic() + 10
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert srv.started
    return srv, th, f"127.0.0.1:{port}"


def test_demo_starts_with_the_bad_file_present_and_serves_the_api(manifests, monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(app=app, **kw))
    assert cli.main(["demo", "--port", "8222"]) == 0
    out = capsys.readouterr().out
    assert "http://127.0.0.1:8222/" in out
    assert out.count("refused") == 1 and f"refused {manifests / 'G7.yaml'}: id: G7 has no activity registry" in out
    I = seen["app"].state.inputs
    assert isinstance(I, data.Inputs) and sorted(I.cards) == SIX and [e.path for e in I.refused] == [str(manifests / "G7.yaml")]
    srv, th, base = serve(seen["app"])
    try:
        with urllib.request.urlopen(f"http://{base}/api/meta", timeout=60) as r:   # the live source builds both reference runs here
            meta = json.loads(r.read())
        assert r.status == 200 and [m["id"] for m in meta["missions"]] == ["survey", "sar"] and meta["source"] == "live"
        with urllib.request.urlopen(f"http://{base}/api/admit?case=A1-survey", timeout=30) as r:
            assert json.loads(r.read())["verdict"] == "YES-IF"
    finally:
        srv.should_exit = True
        th.join(timeout=5)
