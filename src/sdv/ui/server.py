"""The ArgOS screen server: one page, five views, and /ws pushing {snapshot, records} per tick.

    uv run python -m sdv.ui.server [--host 127.0.0.1] [--port 8000] [--source live|fixtures] [--log-dir runs/live]

The source is the live tick loop (sdv.loop: simulator, estimator, core) by default; `fixtures` replays
tests/fixtures/snapshots and tests/fixtures/records instead. Every live run and re-run (a jump back, RESTART) is
logged to its own directory under --log-dir, live-<start file>-<n>, for `uv run sdv replay <dir> --mission <file>`.

Routes:
    GET  /                  the page (static/index.html)
    GET  /api/meta          priority files, run end, decision marks, source
    GET  /api/state         one moment: ?mission=survey&t=1142 -> {tick, t_s, mission, snapshot, records, view}
    GET  /api/compare       both priority files at one moment: ?t=1142
    GET  /api/admit         D1 on a Scenario A case with the jury's edits: ?case=A1-survey&edit=G4.hangar.mass_t=0.9
                            or &edit=G4.consumes.power_kw.peak=40 (&keep=... the last accepted edits, kept in force
                            when an edit is rejected); 422 {refused: {field, reason}} for an edit that cannot apply
    GET  /api/reference     guests, priority files, tiers and the governor's computers for the Reference view
    GET  /api/builder       what the profile and rule builder offers
    POST /api/builder/check {kind: profile|card, doc} -> {problems}
    POST /api/builder/save  {kind, doc, label} -> {path} or {problems}; a new file, never an overwrite
    WS   /ws                ?mission=survey&t=0&speed=12&run=1; accepts {"cmd": run|hold|toggle|speed|jump|restart|mission}
                            and, live, {"cmd": "input", "input": {type, injected, payload}} for laptop inputs

The run advances one ship second per tick, `speed` ticks per wall-clock second (SIM x12 is one ship minute every
5 s). Every message is {type, tick, t_s, mission, snapshot, records, view, running, speed, end_t_s, source}.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from fastapi import Body, FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sdv.ui import builder, data, live, view

STATIC = Path(__file__).parent / "static"
SPEEDS = (1, 12, 60)
SOURCES = ("live", "fixtures")


def meta(I: data.Inputs, source: str = "fixtures", ref: live.Reference | None = None) -> dict:
    if source == "live":
        missions = list(ref.missions)
        marks = {m: view.marks(ref.records(m)) for m in missions}
        records = "live core"
    else:
        missions = I.replay_missions
        marks = {m: view.marks(I.records.get(m, [])) for m in missions}
        records = str(I.records_dir.relative_to(data.ROOT)) if I.records_dir.is_relative_to(data.ROOT) else str(I.records_dir)
    return {"missions": [{"id": m, "name": view.mission_name(m)} for m in missions], "end_t_s": data.END_T_S,
            "marks": marks, "records_source": records, "speeds": list(SPEEDS), "source": source,
            "scenario": data.SCENARIO, "location": I.scenario.get("location", {}).get("name", "")}


def state(I: data.Inputs, mission: str, t_s: int) -> dict:
    """The fixture replay's message for one tick: the snapshot and records the screen reads, plus the view."""
    if mission not in I.timeline:
        raise KeyError(mission)
    t_s = max(0, min(int(t_s), data.END_T_S))
    return live_state(I, I.moment(mission, t_s))


def live_state(I: data.Inputs, m: data.Moment) -> dict:
    return {"type": "tick", "tick": m.t_s, "t_s": m.t_s, "mission": m.mission, "snapshot": m.snapshot, "records": m.records,
            "view": view.screen(I, m)}


def parse_edits(edit: list[str]) -> dict[str, str]:
    out = {}
    for e in edit:
        field, sep, value = e.partition("=")
        if sep and field.strip():
            out[field.strip()] = value.strip()
    return out


class Replay:
    """One browser's fixture replay: ship time, priority file, pace, run or hold."""

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

    def command(self, msg: dict) -> str | None:
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
        elif cmd == "input":
            return "the fixture replay takes no inputs"
        return None

    def close(self) -> None:
        pass    # nothing is logged: the fixtures are the log


class Live:
    """One browser's live run (sdv.ui.live), with the same interface as Replay."""

    def __init__(self, I: data.Inputs, mission: str = "survey", t_s: int = 0, speed: float = 12, running: bool = True,
                 run_logs: live.RunLogs | None = None):
        self.I = I
        self.lr = live.LiveReplay(mission if mission in I.missions else "survey", t_s, speed, running, speeds=SPEEDS, logs=run_logs)

    @property
    def speed(self):
        return self.lr.speed

    @property
    def running(self):
        return self.lr.running

    @property
    def t_s(self):
        return self.lr.t_s

    def payload(self) -> dict:
        run = self.lr.run
        p = live_state(self.I, run.moment())
        p.update(running=self.lr.running, speed=self.lr.speed, end_t_s=data.END_T_S, source="live", sim=run.sim_label,
                 standby=run.standby, rejected=run.loop.core.rejected[-3:])
        return p

    def advance(self) -> None:
        self.lr.advance()

    def command(self, msg: dict) -> str | None:
        return self.lr.command(msg, missions=tuple(self.I.missions))

    def close(self) -> None:
        self.lr.close()


def create_app(inputs: data.Inputs | None = None, source: str = "live", profiles_dir: Path = builder.PROFILES_DIR,
               drafts_dir: Path = builder.DRAFTS_DIR, run_logs: live.RunLogs | None = None) -> FastAPI:
    if source not in SOURCES:
        raise ValueError(f"source {source!r} is not one of {SOURCES}")
    I = inputs or data.Inputs()
    ref = live.Reference() if source == "live" else None
    app = FastAPI(title="ArgOS", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.inputs, app.state.source, app.state.reference, app.state.run_logs = I, source, ref, run_logs
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
        return meta(I, source, ref)

    @app.get("/api/state")
    def api_state(mission: str = "survey", t: int = 0):
        t = max(0, min(t, data.END_T_S))
        try:
            if ref is not None:
                if mission not in ref.missions:
                    raise KeyError(mission)
                return live_state(I, ref.moment(mission, t))
            return state(I, mission, t)
        except KeyError:
            return JSONResponse({"error": f"no run for priority file {mission}"}, status_code=404)

    @app.get("/api/compare")
    def api_compare(t: int = 0):
        t = max(0, min(t, data.END_T_S))
        if ref is not None:
            files = ref.missions[:2]
            return view.compare(I, t, files, {f: ref.moment(f, t) for f in files}, ref.records(files[0]))
        return view.compare(I, t, tuple(I.replay_missions[:2]))

    @app.get("/api/admit")
    def api_admit(case: str = "A1-survey", edit: list[str] = Query(default=[]), keep: list[str] = Query(default=[])):
        out = view.admit(I, case, parse_edits(edit), parse_edits(keep))
        if "refused" in out:  # an edit that cannot be applied: {refused: {field, reason}}, the last verdict stands
            return JSONResponse(out, status_code=422)
        return out

    @app.get("/api/reference")
    def api_reference():
        return view.reference(I)

    @app.get("/api/builder")
    def api_builder():
        return builder.catalog(I)

    @app.post("/api/builder/check")
    def api_builder_check(body: dict = Body(...)):
        return {"problems": builder.check(I, body.get("kind", ""), body.get("doc"))}

    @app.post("/api/builder/save")
    def api_builder_save(body: dict = Body(...)):
        out = builder.save(I, body.get("kind", ""), body.get("doc"), body.get("label", ""), profiles_dir, drafts_dir)
        return JSONResponse(out, status_code=422 if "problems" in out else 200)

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        q = websocket.query_params
        try:
            speed = float(q.get("speed", 12))
            t0 = int(q.get("t", 0))
        except ValueError:
            speed, t0 = 12.0, 0
        speed = int(speed) if speed.is_integer() else speed
        running = q.get("run", "1") != "0"
        mission = q.get("mission", "survey")
        rp = Live(I, mission, t0, speed, running, run_logs) if source == "live" else Replay(I, mission, t0, speed, running)
        changed = asyncio.Event()
        refusals: list[str] = []
        errors: list[str] = []

        def guarded(fn, *args):
            """One step of the run (a tick, a command, the payload). An exception in the engine is reported to the
            screen as an error frame and the run is held at the tick it failed on; the socket stays up."""
            try:
                return fn(*args)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{type(e).__name__}: {e}")
                rp.command({"cmd": "hold"})
                return None

        async def receive():
            try:
                while True:
                    msg = await websocket.receive_json()
                    if isinstance(msg, dict):
                        refused = guarded(rp.command, msg)
                        if refused:
                            refusals.append(refused)
                        changed.set()
            finally:
                changed.set()

        rx = asyncio.create_task(receive())
        loop = asyncio.get_running_loop()

        async def send():
            p = guarded(rp.payload)
            while errors:
                await websocket.send_json({"type": "error", "tick": rp.t_s, "t_s": rp.t_s, "message": errors.pop(0)})
            if p is None:
                return
            if refusals:
                p["refused"] = refusals.pop()
            await websocket.send_json(p)

        try:
            await send()
            due = loop.time() + 1 / rp.speed
            while not rx.done():
                timeout = max(0.0, due - loop.time()) if rp.running else None
                try:
                    await asyncio.wait_for(changed.wait(), timeout)
                except asyncio.TimeoutError:
                    guarded(rp.advance)
                    due += 1 / rp.speed
                    if due < loop.time() - 1:
                        due = loop.time() + 1 / rp.speed  # fell behind: do not burst
                else:
                    changed.clear()
                    due = loop.time() + 1 / rp.speed
                if rx.done():
                    break
                await send()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            rx.cancel()
            rp.close()

    return app


def run(host: str = "127.0.0.1", port: int = 8000, source: str = "live", log_dir: Path | None = None) -> None:
    """Serves until stopped. With log_dir (live source) it says where the runs are logged and how to replay the
    first, tells of each run as a browser starts or re-runs one, and on shutdown repeats the line for the last run."""
    import uvicorn

    def say(line: str) -> None:
        print(line, flush=True)     # stdout may be a file (nohup, a service): these lines must not wait in a buffer

    logs = live.RunLogs(log_dir, say=say) if source == "live" and log_dir is not None else None
    if logs:
        first = logs.path("survey")
        say(f"LOGS {logs.root}: one directory per run, live-<file>-<n>; the first under survey.yaml replays with: "
            f"{live.replay_line(first, 'survey')}")
    try:
        uvicorn.run(create_app(source=source, run_logs=logs), host=host, port=port, log_level="warning")
    finally:
        if logs and logs.last:
            d, start = logs.last
            say(f"LAST RUN {d} under {start}.yaml; replay: {live.replay_line(d, start)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m sdv.ui.server", description="ArgOS screen")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--source", choices=SOURCES, default="live", help="the live tick loop (default) or the fixture replay")
    p.add_argument("--log-dir", default="runs/live", help="live runs are logged here, one directory per run, for sdv replay")
    a = p.parse_args(argv)
    print(f"ArgOS screen on http://{a.host}:{a.port}/ ({a.source})")
    run(a.host, a.port, a.source, Path(a.log_dir) if a.source == "live" else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
