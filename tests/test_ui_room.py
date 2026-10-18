"""The room map (/room): its route and page, and /api/room's per-cell free numbers, derived from the snapshot plus
config/assumptions.yaml and the cards, for the Scenario B snapshots and for a Scenario A admission case."""
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest
import uvicorn

from sdv.ui import data, room, server

I = data.Inputs()


def by_id(r):
    return {c["id"]: c for c in r["cells"]}


# ------------------------------------------------------------------------------------------- Scenario B, at sea

@pytest.mark.parametrize("mission", ["survey", "sar"])
@pytest.mark.parametrize("t", [0, 481, 722, 1142])
def test_scenario_b_cells_hold_the_slot_limits_and_what_is_free(mission, t):
    r = room.room(I, I.moment(mission, t))
    assert [c["id"] for c in r["cells"]] == list(room.ORDER)
    # the organisers' load-out (DEC-63): G1 on the free mast slot, G3 in Bay 1, G4 on the flight deck, G5 in Bay 2 with its antenna on the roof
    assert r["situation"] == "at_sea" and r["installed"] == ["G1", "G3", "G4", "G5"] and r["t_s"] == t and r["mission"] == mission
    c = by_id(r)
    mast = c["mast_free"]
    assert mast["who"] == "G1 radio sensor" and mast["natives"] == ["radar", "SATCOM"] and mast["primary"] == ["G1"]
    assert mast["limits"] == {"slots_total": 3, "slots_used": 3, "slots_free": 0, "max_kg": 60, "area_m2": 0.6, "mass_kg": 45.0,
                              "part_area_m2": 0.5, "air_cooled_max_kw": 2}
    assert mast["what"] == "45 of 60 kg · 0.5 of 0.6 m² · air cooled" and (mast["free_k"], mast["free_v"], mast["free_n"]) == ("free slots", "0", 0)
    bay2 = c["bay2"]
    assert bay2["who"] == "G5 comms node" and bay2["what"] == "3.0 of 4 t" and bay2["tag"] == "stbd line"
    assert bay2["limits"] == {"max_t": 4, "mass_t": 3.0, "free_t": 1.0, "halves": 1, "halves_used": 1, "halves_free": 0}
    assert bay2["free_v"] == "1.0 t under limit" and bay2["free_n"] == 1.0
    bay1 = c["bay1"]
    assert bay1["who"] == "G3 survey vehicle" and bay1["what"] == "5.5 of 8 t · cradle 3.5 + vehicle 2.0" and bay1["tag"] == "port line"
    assert bay1["limits"] == {"max_t": 8, "mass_t": 5.5, "free_t": 2.5, "halves": 2, "halves_used": 2, "halves_free": 0}
    fd = c["flight_deck"]
    assert fd["who"] == "G4 rescue drone" and fd["what"] == "hangar 0.85 t · drone 140 of 150 kg"
    assert fd["limits"] == {"hangar_max_kg": 150, "drone_kg": 140.0, "free_kg": 10.0, "hangar_t": 0.85, "area_m": [12, 8]}
    assert fd["free_v"] == "10 kg under hangar limit"
    roof = c["hangar_roof"]
    assert roof["who"] == "G5 antenna" and roof["guests"] == ["G5"] and roof["primary"] == []   # a secondary part: no draw of its own
    assert roof["limits"] == {"max_kg": 60, "mass_kg": 25.0, "free_kg": 35.0, "multiplier": 1.2} and roof["free_v"] == "35 kg"
    assert roof["what"] == "25 of 60 kg · stability ×1.2"
    ramp = c["stern_ramp"]
    assert ramp["who"] == "free" and ramp["users"] == ["G3"] and ramp["limits"] == {"max_t": 5, "craft_len_m": [7, 9]}
    assert (ramp["free_k"], ramp["free_v"]) == ("excludes", "flight deck ops") and ramp["what"] == "one craft ≤ 5 t · 7–9 m"
    assert r["mast"] == {"slots_free": 0, "slots_total": 3, "natives": ["radar", "SATCOM"], "guest": "G1 radio sensor"}
    assert r["deck"] == {"halves_total": 3, "halves_free": 0, "bays_free": []}
    assert not any(cell["held"] for cell in r["cells"])


def test_mutability_follows_a11_and_at_sea_marks_the_crane_positions_port_only():
    r = room.room(I, I.moment("survey", 722))
    c = by_id(r)
    assert {k: v["mutability"] for k, v in c.items()} == {"mast_free": "port", "bay2": "port", "bay1": "port", "flight_deck": "sea",
                                                          "hangar_roof": "port", "stern_ramp": "sea"}
    assert {k for k, v in c.items() if v["port_only"]} == {"mast_free", "bay2", "bay1", "hangar_roof"}
    assert c["bay1"]["rule"] == "changes in port · crane 8 t alongside · 4–8 h" and c["bay1"]["rule_detail"] == ""
    assert c["mast_free"]["rule"] == "changes in port · crane alongside · 2–4 h"
    assert c["flight_deck"]["rule"] == "changes at sea in a window · drone swap 30 min, 3 people"
    assert c["stern_ramp"]["rule"] == "changes at sea in a window · vehicle swap 45 min, 4 people"
    assert c["flight_deck"]["rule_detail"] == c["stern_ramp"]["rule_detail"] == (
        "at-sea window: sea state ≤ 3, wind ≤ 20 kn, 4–8 kn, course steady, deck clear, survey vehicle not listening · "
        "≤ 250 kg via flight deck or stern ramp")
    assert c["bay2"]["primary"] == ["G5"] and c["mast_free"]["primary"] == ["G1"] and c["bay1"]["primary"] == ["G3"]
    assert r["as_built"]["gensets"] == "2 × 450 kW" and r["as_built"]["loop"] == "160 → 120 kW · 12 → 30 °C"
    assert r["as_built"]["lines"] == "150 + 150 kW" and (r["as_built"]["mass_t"], r["as_built"]["stability_t_eq"], r["as_built"]["headroom_kw"]) == (10, 12, 5)
    assert r["as_built"]["mast_natives"] == ["navigation radar", "satellite terminal"] and r["as_built"]["trip_signals"] == 3
    assert r["sources"]["heat"] == "brief A.2" and r["sources"]["mass"] == "brief A.4" and r["sources"]["positions"] == "brief A.3"
    assert r["sources"]["headroom"] == "assumed" and r["sources"]["response"] == "brief A.8"
    assert r["profile"]["id"] == "survey" and r["profile"]["mission_critical"] == ["G3"] and r["route_seawater_c"] == 24
    json.dumps(r)


def test_the_profile_in_force_is_the_live_runs_file():
    m = I.moment("sar", 481)
    m.mission, m.profile = "sar_edit", {**I.missions["sar"], "id": "sar_edit", "name": "Rescue edit"}   # as live.Run.moment gives it
    r = room.room(I, m)
    assert r["profile"]["id"] == "sar_edit" and r["profile"]["name"] == "RESCUE EDIT" and r["profile"]["mission_critical"] == ["G4"]


# ------------------------------------------------------------------------------------------- Scenario A, the pier

def test_admission_case_a5_holds_the_card_over_the_flight_deck():
    r = room.admission_room(I, "A5-survey")
    assert r["situation"] == "alongside" and r["installed"] == ["G1", "G2", "G5"] and r["card"] == "G4" and r["verdict"] == "YES"
    assert r["edits"] == {} and r["unplaced"] == []
    c = by_id(r)
    assert not any(cell["port_only"] for cell in r["cells"])
    assert c["mast_free"]["who"] == "G1 radio sensor" and c["mast_free"]["limits"]["mass_kg"] == 45.0 and c["mast_free"]["limits"]["slots_free"] == 0
    assert c["mast_free"]["what"] == "45 of 60 kg · 0.5 of 0.6 m² · air cooled"
    assert c["bay2"]["who"] == "G2 ocean module" and c["bay2"]["limits"]["free_t"] == 0.5 and c["bay2"]["free_v"] == "0.5 t under limit"
    assert c["bay1"]["who"] == "G5 comms node" and c["bay1"]["what"] == "3.0 of 8 t · one half"
    assert c["bay1"]["limits"] == {"max_t": 8, "mass_t": 3.0, "free_t": 5.0, "halves": 2, "halves_used": 1, "halves_free": 1}
    assert c["bay1"]["free_v"] == "1 half · 5.0 t under limit"
    assert c["flight_deck"]["held"] and c["flight_deck"]["who"] == "G4 rescue drone" and c["flight_deck"]["limits"]["free_kg"] == 10.0
    assert c["hangar_roof"]["who"] == "G5 antenna" and c["hangar_roof"]["limits"] == {"max_kg": 60, "mass_kg": 25.0, "free_kg": 35.0, "multiplier": 1.2}
    assert c["hangar_roof"]["free_v"] == "35 kg"
    assert c["stern_ramp"]["who"] == "free" and c["stern_ramp"]["users"] == []
    assert r["mast"]["guest"] == "G1 radio sensor" and r["deck"] == {"halves_total": 3, "halves_free": 1, "bays_free": []}


def test_the_jurys_edits_reach_the_pier_cells_and_a_refusal_passes_through():
    r = room.admission_room(I, "A5-survey", {"G4.consumes.power_kw.peak": "50"}, {"G4.hangar.mass_t": "0.8"})
    fd = by_id(r)["flight_deck"]
    assert fd["limits"]["hangar_t"] == 0.8 and fd["what"] == "hangar 0.80 t · drone 140 of 150 kg"
    assert r["edits"] == {"G4.hangar.mass_t": "0.8", "G4.consumes.power_kw.peak": "50"} and r["verdict"] == "YES"
    assert room.admission_room(I, "A5-survey", {"G4.consumes.power_kw.peak": "abc"}) == {
        "refused": {"field": "G4.consumes.power_kw.peak", "reason": "'abc' is not a number"}}
    assert "error" in room.admission_room(I, "A9-survey")


def test_a3_names_the_part_no_position_takes():
    r = room.admission_room(I, "A3-survey")
    assert r["unplaced"] == [{"guest": "G5", "part": "node", "mass_t": 3.0}]
    assert by_id(r)["mast_free"]["who"] == "G5 antenna"


# ------------------------------------------------------------------------------------------- the server

def test_create_app_registers_the_room_page_and_its_route():
    app = server.create_app(I)
    paths = {getattr(r, "path", None) for r in app.routes}
    assert {"/room", "/api/room"} <= paths


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
def replay():
    srv, th, base = serve(server.create_app(I, source="fixtures"))
    yield base
    srv.should_exit = True
    th.join(timeout=5)


def get(base, path):
    try:
        with urllib.request.urlopen(f"http://{base}{path}", timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_the_room_page_and_its_assets_are_served(replay):
    status, html = get(replay, "/room")
    assert status == 200 and "Room aboard" in html and "/static/room/room.js" in html and "/static/room/room.css" in html
    assert "Role views" in html and "not access control" in html
    for asset in ("/static/room/room.js", "/static/room/room.css"):
        assert get(replay, asset)[0] == 200
    status, html = get(replay, "/")      # the console is untouched: it loads none of the room page's assets
    assert status == 200 and "/static/js/app.js" in html and "/static/room/" not in html


def test_api_room_answers_for_a_moment_and_for_the_pier(replay):
    status, body = get(replay, "/api/room?mission=sar&t=1142")
    r = json.loads(body)
    assert status == 200 and r["mission"] == "sar" and r["t_s"] == 1142 and by_id(r)["bay2"]["limits"]["free_t"] == 1.0
    status, body = get(replay, "/api/room?case=A5-survey&edit=G4.hangar.mass_t=0.8")
    r = json.loads(body)
    assert status == 200 and by_id(r)["flight_deck"]["limits"]["hangar_t"] == 0.8 and r["verdict"] == "YES"
    status, body = get(replay, "/api/room?case=A5-survey&edit=G4.consumes.power_kw.peak=abc&keep=G4.hangar.mass_t=0.8")
    assert status == 422 and json.loads(body) == {"refused": {"field": "G4.consumes.power_kw.peak", "reason": "'abc' is not a number"}}
    assert get(replay, "/api/room?mission=patrol&t=0")[0] == 404
    assert get(replay, "/api/room?case=A9-survey")[0] == 404


# ------------------------------------------------------------------------------------------- the page's own discipline

ROOM_JS = (data.ROOT / "src/sdv/ui/static/room/room.js").read_text()
ROOM_PAGE = (data.ROOT / "src/sdv/ui/static/room/index.html").read_text()


def test_room_js_paints_only_when_the_markup_changes_and_keeps_its_controls_static():
    """main's SIM-bar lesson (tests/test_ui_static.py): a button rebuilt between mousedown and mouseup never fires, so
    the operator's row is static markup changed in place, and every other region goes through paint()."""
    import re
    assigns = [m.start() for m in re.finditer(r"\.innerHTML\s*=", ROOM_JS)]
    paint = re.search(r"function paint\(el, html\) \{(.*?)\}", ROOM_JS, re.S)
    assert paint and len(assigns) == 1 and paint.start() < assigns[0] < paint.end()
    assert "el.__last !== html" in paint.group(1)
    for control in ('id="ops-run"', 'id="ops-restart"', 'id="ops-speed"', 'id="ops-jump"', 'id="ops-fill"', 'id="profile"', 'id="presets"', 'id="tabs"'):
        assert control in ROOM_PAGE, control
    assert "run.textContent = t.running ? 'Hold' : 'Run'" in ROOM_JS and "$('ops-fill').style.width" in ROOM_JS
    assert "paint($('ops-speed')" in ROOM_JS and "paint($('ops-jump')" in ROOM_JS and "paint($('profile')" in ROOM_JS


def test_the_room_page_loads_nothing_but_google_fonts_from_outside():
    import re
    urls = set(re.findall(r"https?://[^\s\"')]+", ROOM_PAGE + ROOM_JS + (data.ROOT / "src/sdv/ui/static/room/room.css").read_text()))
    assert urls == {"https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"}
    assert "Role views" in ROOM_PAGE and "not access control" in ROOM_PAGE
