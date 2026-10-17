"""The ArgOS screen server: one page, four views, and /ws pushing {snapshot, records} per tick from a replay.

    uv run python -m sdv.ui.server [--host 127.0.0.1] [--port 8000]

Routes:
    GET /                 the page (static/index.html)
    GET /api/meta         priority files, replay end, decision moments, where the records come from
    GET /api/state        one moment: ?mission=survey&t=1142 -> {tick, t_s, mission, snapshot, records, view}
    GET /api/compare      both priority files at one moment: ?t=1142
    GET /api/admit        D1 on a Scenario A case with the jury's edits: ?case=A1-survey&edit=G4.hangar.mass_t=0.9
                          (&keep=... the last accepted edits, kept in force when an edit is rejected)
    GET /api/reference    guests and priority files for the Reference view
    WS  /ws               ?mission=survey&t=0&speed=12&run=1; accepts {"cmd": run|hold|speed|jump|mission|restart}

The replay advances one ship second per tick, `speed` ticks per wall-clock second (SIM x12 is one ship minute every
5 s). The live engine replaces Replay.payload's source later; the message shape stays {snapshot, records}.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sdv.ui import data, view

STATIC = Path(__file__).parent / "static"
SPEEDS = (1, 12, 60)


def meta(I: data.Inputs) -> dict:
    src = str(I.records_dir.relative_to(data.ROOT)) if I.records_dir.is_relative_to(data.ROOT) else str(I.records_dir)
    return {"missions": [{"id": m, "name": view.mission_name(m)} for m in I.replay_missions], "end_t_s": data.END_T_S,
            "marks": {m: view.marks(I, m) for m in I.replay_missions}, "records_source": src, "speeds": list(SPEEDS),
            "scenario": data.SCENARIO, "location": I.scenario.get("location", {}).get("name", "")}


def state(I: data.Inputs, mission: str, t_s: int) -> dict:
    """The /ws message for one tick: the snapshot and records the screen reads, plus the view built from them."""
    if mission not in I.timeline:
        raise KeyError(mission)
    t_s = max(0, min(int(t_s), data.END_T_S))
    m = I.moment(mission, t_s)
    return {"type": "tick", "tick": t_s, "t_s": t_s, "mission": mission, "snapshot": m.snapshot, "records": m.records,
            "view": view.operations(I, mission, t_s)}


def parse_edits(edit: list[str]) -> dict[str, str]:
    out = {}
    for e in edit:
        field, sep, value = e.partition("=")
        if sep and field.strip():
            out[field.strip()] = value.strip()
    return out


class Replay:
    """One browser's replay: ship time, priority file, pace, run or hold."""

    def __init__(self, I: data.Inputs, mission: str = "survey", t_s: int = 0, speed: float = 12, running: bool = True):
        self.I = I
        self.mission = mission if mission in I.timeline else I.replay_missions[0]
        self.t_s = max(0, min(int(t_s), data.END_T_S))
        self.speed = speed if speed in SPEEDS else 12
        self.running = running and self.t_s < data.END_T_S

    def payload(self) -> dict:
        p = state(self.I, self.mission, self.t_s)
        p.update(running=self.running, speed=self.speed, end_t_s=data.END_T_S, source="replay")
        return p

    def advance(self) -> None:
        if self.running and self.t_s < data.END_T_S:
            self.t_s += 1
        if self.t_s >= data.END_T_S:
            self.running = False

    def command(self, msg: dict) -> None:
        cmd = msg.get("cmd")
        if cmd == "run":
            self.running = self.t_s < data.END_T_S
        elif cmd == "hold":
            self.running = False
        elif cmd == "toggle":
            self.running = not self.running and self.t_s < data.END_T_S
        elif cmd == "speed" and msg.get("value") in SPEEDS:
            self.speed = msg["value"]
        elif cmd == "jump":
            self.t_s = max(0, min(int(msg.get("t", 0)), data.END_T_S))
        elif cmd == "restart":
            self.t_s, self.running = 0, True
        elif cmd == "mission" and msg.get("value") in self.I.timeline:
            self.mission = msg["value"]


def create_app(inputs: data.Inputs | None = None) -> FastAPI:
    I = inputs or data.Inputs()
    app = FastAPI(title="ArgOS", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.inputs = I
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.middleware("http")
    async def revalidate_static(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/meta")
    def api_meta():
        return meta(I)

    @app.get("/api/state")
    def api_state(mission: str = "survey", t: int = 0):
        try:
            return state(I, mission, t)
        except KeyError:
            return JSONResponse({"error": f"no replay for priority file {mission}"}, status_code=404)

    @app.get("/api/compare")
    def api_compare(t: int = 0):
        return view.compare(I, max(0, min(t, data.END_T_S)), tuple(I.replay_missions[:2]))

    @app.get("/api/admit")
    def api_admit(case: str = "A1-survey", edit: list[str] = Query(default=[]), keep: list[str] = Query(default=[])):
        return view.admit(I, case, parse_edits(edit), parse_edits(keep))

    @app.get("/api/reference")
    def api_reference():
        return view.reference(I)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        q = websocket.query_params
        try:
            speed = float(q.get("speed", 12))
            t0 = int(q.get("t", 0))
        except ValueError:
            speed, t0 = 12, 0
        rp = Replay(I, q.get("mission", "survey"), t0, int(speed) if speed.is_integer() else speed, q.get("run", "1") != "0")
        changed = asyncio.Event()

        async def receive():
            try:
                while True:
                    msg = await websocket.receive_json()
                    if isinstance(msg, dict):
                        rp.command(msg)
                        changed.set()
            finally:
                changed.set()

        rx = asyncio.create_task(receive())
        loop = asyncio.get_running_loop()
        try:
            await websocket.send_json(rp.payload())
            due = loop.time() + 1 / rp.speed
            while not rx.done():
                timeout = max(0.0, due - loop.time()) if rp.running else None
                try:
                    await asyncio.wait_for(changed.wait(), timeout)
                except asyncio.TimeoutError:
                    rp.advance()
                    due += 1 / rp.speed
                    if due < loop.time() - 1:
                        due = loop.time() + 1 / rp.speed  # fell behind: do not burst
                else:
                    changed.clear()
                    due = loop.time() + 1 / rp.speed
                if rx.done():
                    break
                await websocket.send_json(rp.payload())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            rx.cancel()

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m sdv.ui.server", description="ArgOS screen")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    print(f"ArgOS screen on http://{a.host}:{a.port}/")
    run(a.host, a.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
