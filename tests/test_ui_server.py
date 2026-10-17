"""The screen server: routes, the replay, and a live /ws stream of a Scenario B replay (uvicorn in a thread, the
websockets client; no HTTP test client is installed)."""
import json
import socket
import threading
import time
import urllib.request

import pytest
import uvicorn
from websockets.sync.client import connect

from sdv.ui import data, server

I = data.Inputs()


def test_create_app_exposes_the_page_the_api_and_the_stream():
    app = server.create_app(I)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/", "/api/meta", "/api/state", "/api/compare", "/api/admit", "/api/reference", "/ws", "/static"} <= paths


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


@pytest.fixture(scope="module")
def live():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(server.create_app(I), host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.monotonic() + 10
    while not srv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert srv.started
    yield f"127.0.0.1:{port}"
    srv.should_exit = True
    th.join(timeout=5)


def get(base, path):
    with urllib.request.urlopen(f"http://{base}{path}", timeout=5) as r:
        return r.status, r.read().decode()


def test_the_page_and_its_assets_are_served(live):
    status, html = get(live, "/")
    assert status == 200 and "ArgOS" in html and "/static/js/app.js" in html
    for asset in ("/static/argos.css", "/static/js/app.js", "/static/js/ops.js", "/static/js/compare.js",
                  "/static/js/admit.js", "/static/js/reference.js", "/static/js/util.js"):
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
