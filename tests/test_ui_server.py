"""The screen server: routes, the fixture replay, the live loop, and /ws streams of Scenario B (uvicorn in a thread,
the websockets client; no HTTP test client is installed)."""
import json
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn
from websockets.sync.client import connect

from sdv.ui import data, server
from sdv.ui.live import RunLogs

I = data.Inputs()


def test_create_app_exposes_the_page_the_api_and_the_stream():
    app = server.create_app(I)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/", "/api/meta", "/api/state", "/api/compare", "/api/admit", "/api/reference", "/api/builder",
            "/api/builder/check", "/api/builder/save", "/ws", "/static"} <= paths
    assert app.state.source == "live"
    with pytest.raises(ValueError):
        server.create_app(I, source="nonsense")


def test_state_carries_the_snapshot_and_the_records_decided_by_then():
    p = server.state(I, "survey", 722)
    assert p["tick"] == p["t_s"] == 722 and p["mission"] == "survey"
    assert p["snapshot"]["run"]["t_ship_s"] == 721
    assert [(r["kind"], r["tick"]) for r in p["records"]] == [("D3", 480), ("D4", 721)]
    assert p["view"]["header"]["clock"] == "T+00:12:02"
    json.dumps(p)  # the /ws message is plain JSON


def test_state_refuses_an_unknown_priority_file():
    with pytest.raises(KeyError):
        server.state(I, "patrol", 0)


def test_replay_commands():
    rp = server.Replay(I, "survey", 0, 12)
    rp.advance()
    assert rp.t_s == 1 and rp.running
    rp.command({"cmd": "hold"})
    rp.advance()
    assert rp.t_s == 1 and not rp.running
    rp.command({"cmd": "jump", "t": 99999})
    assert rp.t_s == data.END_T_S
    rp.command({"cmd": "run"})
    assert not rp.running  # nothing left to play
    rp.command({"cmd": "restart"})
    assert rp.t_s == 0 and rp.running
    rp.command({"cmd": "mission", "value": "sar"})
    rp.command({"cmd": "mission", "value": "nonsense"})
    rp.command({"cmd": "speed", "value": 60})
    rp.command({"cmd": "speed", "value": 7})
    assert rp.mission == "sar" and rp.speed == 60


def test_parse_edits():
    assert server.parse_edits(["G4.hangar.mass_t=0.9", "bad", "=1"]) == {"G4.hangar.mass_t": "0.9"}


def test_run_says_where_the_live_runs_go_and_how_to_replay_the_last(monkeypatch, tmp_path, capsys):
    def serve_one_run(app, host, port, log_level):
        app.state.run_logs.new("sar")                       # a browser connected under sar.yaml, then the server stopped
    monkeypatch.setattr(uvicorn, "run", serve_one_run)
    server.run("127.0.0.1", 8999, "live", tmp_path)
    d = tmp_path / "live-sar-1"
    assert capsys.readouterr().out.splitlines() == [
        f"LOGS {tmp_path}: one directory per run, live-<file>-<n>; the first under survey.yaml replays with: "
        f"uv run sdv replay {tmp_path / 'live-survey-1'} --mission survey",
        f"RUN 1 under sar.yaml logs to {d}; replay: uv run sdv replay {d} --mission sar",
        f"LAST RUN {d} under sar.yaml; replay: uv run sdv replay {d} --mission sar"]
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    server.run("127.0.0.1", 8999, "fixtures", tmp_path)       # the fixture replay logs nothing
    assert capsys.readouterr().out == ""


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


@pytest.fixture(scope="module")
def live():
    """The fixture replay (the name is the server's, not the source's)."""
    srv, th, base = serve(server.create_app(I, source="fixtures"))
    yield base
    srv.should_exit = True
    th.join(timeout=5)


@pytest.fixture(scope="module")
def loop_server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("builder")
    srv, th, base = serve(server.create_app(I, source="live", profiles_dir=tmp, drafts_dir=tmp, run_logs=RunLogs(tmp / "runs")))
    yield base, tmp
    srv.should_exit = True
    th.join(timeout=5)


def get(base, path):
    with urllib.request.urlopen(f"http://{base}{path}", timeout=30) as r:
        return r.status, r.read().decode()


def post(base, path, body):
    req = urllib.request.Request(f"http://{base}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_the_page_and_its_assets_are_served(live):
    status, html = get(live, "/")
    assert status == 200 and "ArgOS" in html and "/static/js/app.js" in html
    for asset in ("/static/argos.css", "/static/js/app.js", "/static/js/ops.js", "/static/js/compare.js",
                  "/static/js/admit.js", "/static/js/reference.js", "/static/js/util.js", "/static/js/builder.js"):
        assert get(live, asset)[0] == 200


def test_the_api_answers(live):
    meta = json.loads(get(live, "/api/meta")[1])
    assert [m["id"] for m in meta["missions"]] == ["survey", "sar"]
    admit = json.loads(get(live, "/api/admit?case=A1-survey&edit=G4.hangar.mass_t=0.80")[1])
    assert admit["verdict"] == "YES"
    compare = json.loads(get(live, "/api/compare?t=722")[1])
    assert compare["ships"]["sar"]["decision"]["tag"] == "HOLDS"


def test_ws_streams_a_scenario_b_replay(live):
    with connect(f"ws://{live}/ws?mission=survey&t=1138&speed=60") as ws:
        first = json.loads(ws.recv(timeout=5))
        assert first["t_s"] == 1138 and first["source"] == "replay" and set(first) >= {"snapshot", "records", "view"}
        seen = [first]
        while seen[-1]["t_s"] < 1142:
            seen.append(json.loads(ws.recv(timeout=5)))
        ticks = [m["t_s"] for m in seen]
        assert ticks == list(range(1138, 1143))
        last = seen[-1]
        assert last["snapshot"]["run"]["t_ship_s"] == 1141
        assert last["records"][-1]["verdict"] == "shed"
        assert last["view"]["decision"]["tag"] == "EXECUTED"
        ws.send(json.dumps({"cmd": "hold"}))
        held = json.loads(ws.recv(timeout=5))
        while held["running"]:
            held = json.loads(ws.recv(timeout=5))
        ws.send(json.dumps({"cmd": "mission", "value": "sar"}))
        swapped = json.loads(ws.recv(timeout=5))
        assert swapped["mission"] == "sar" and swapped["t_s"] == held["t_s"]
        assert swapped["view"]["decision"]["rows"][3] == ["ACTION", "G5 FULL → LOW POWER", False]


def test_an_engine_error_is_an_error_frame_and_the_socket_and_the_run_survive(live, monkeypatch):
    """A tick that raises is reported on the stream and holds the run where it failed; the socket stays up and takes
    the next command, so the screen never reconnects into a silent restart."""
    def boom(self):
        raise ValueError("clear_deck at 0 aboard")
    monkeypatch.setattr(server.Replay, "advance", boom)
    with connect(f"ws://{live}/ws?mission=survey&t=100&speed=60") as ws:
        first = json.loads(ws.recv(timeout=5))
        assert first["type"] == "tick" and first["running"]
        err = json.loads(ws.recv(timeout=5))
        assert err == {"type": "error", "tick": 100, "t_s": 100, "message": "ValueError: clear_deck at 0 aboard"}
        held = json.loads(ws.recv(timeout=5))
        assert (held["type"], held["t_s"], held["running"]) == ("tick", 100, False)
        ws.send(json.dumps({"cmd": "jump", "t": 300}))
        jumped = json.loads(ws.recv(timeout=5))
        assert (jumped["type"], jumped["t_s"], jumped["running"]) == ("tick", 300, False)


def test_ws_streams_the_live_loop_and_takes_laptop_inputs(loop_server):
    base, _ = loop_server
    with connect(f"ws://{base}/ws?mission=sar&t=1138&speed=60") as ws:
        first = json.loads(ws.recv(timeout=30))
        assert first["source"] == "live" and first["sim"] and first["standby"] == "in step"
        assert first["t_s"] == first["snapshot"]["run"]["tick"] == 1138
        msg = first
        while msg["t_s"] < 1143:
            msg = json.loads(ws.recv(timeout=5))
            assert msg["snapshot"]["run"]["tick"] == msg["t_s"]
        assert [r["verdict"] for r in msg["records"] if r["kind"] == "D4"][-2:] == ["shed", "hold"]
        assert msg["view"]["decision"]["tag"] == "EXECUTED"
        ws.send(json.dumps({"cmd": "hold"}))
        while msg["running"]:
            msg = json.loads(ws.recv(timeout=5))
        ws.send(json.dumps({"cmd": "input", "input": {"type": "genset_trip", "payload": {}}}))
        refused = json.loads(ws.recv(timeout=5))
        assert refused["refused"].startswith("input 'genset_trip'")
        prof = dict(I.missions["sar"], id="sar_ws", name="Rescue ws")
        ws.send(json.dumps({"cmd": "input", "input": {"type": "profile_applied", "payload": {"profile": prof}}}))
        ws.recv(timeout=5)
        ws.send(json.dumps({"cmd": "run"}))
        while msg["view"]["header"]["priority_file"] != "sar_ws · AT SEA":
            msg = json.loads(ws.recv(timeout=5))
    d = loop_server[1] / "runs" / "live-sar-1"                   # the run the browser watched is on disk, tick by tick
    assert sorted(p.name for p in d.iterdir()) == ["decisions.jsonl", "frames.jsonl", "inputs.jsonl", "snapshots.jsonl", "timing.jsonl"]
    assert len((d / "frames.jsonl").read_text().splitlines()) > msg["t_s"]
    assert any(json.loads(l)["type"] == "profile_applied" for l in (d / "inputs.jsonl").read_text().splitlines())


def test_live_api_meta_compare_and_builder(loop_server):
    base, tmp = loop_server
    meta = json.loads(get(base, "/api/meta")[1])
    assert meta["source"] == "live" and [m["label"] for m in meta["marks"]["survey"]] == ["START", "G4 LOW BATT", "GEN 2 TRIP", "CHW P1 TRIP"]
    c = json.loads(get(base, "/api/compare?t=1142")[1])
    assert c["ships"]["survey"]["decision"]["tag"] == "EXECUTED"
    s = json.loads(get(base, "/api/state?mission=sar&t=722")[1])
    assert s["snapshot"]["run"]["tick"] == 722 and s["view"]["decision"]["tag"] == "HOLDS"
    cat = json.loads(get(base, "/api/builder")[1])
    assert "G4" in cat["cards"]
    prof = dict(I.missions["survey"], id="survey_net", name="Survey net")
    assert post(base, "/api/builder/check", {"kind": "profile", "doc": prof}) == (200, {"problems": []})
    status, out = post(base, "/api/builder/save", {"kind": "profile", "doc": prof})
    assert status == 200 and (tmp / "survey_net.yaml").exists()
    status, out = post(base, "/api/builder/save", {"kind": "profile", "doc": dict(prof, weights={"sar_air": 9})})
    assert status == 422 and out["problems"]
