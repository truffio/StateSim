"""Local web server: serves the page and runs the session over a WebSocket.

The engine stays synchronous and free of wall-clock time; only this module
paces ticks against real time.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
from http import HTTPStatus
from pathlib import Path

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from statesim import Model

from .session import Session, describe_model

STATIC = Path(__file__).resolve().parent / "static"
PAGES = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/app.css": "app.css",
         "/panels.js": "panels.js"}
WS_PATH = "/ws"
SEND_HZ = 30            # at most this many screen updates per second
FAST_SLICE_S = 0.02     # "as fast as possible": run ticks for this long, then yield
MAX_LAG_S = 0.5         # real time: a backlog longer than this is dropped, not caught up


class App:
    """Session plus pacing loop plus connected clients."""

    def __init__(self, model: Model, trace=None) -> None:
        self.session = Session(model, trace)
        self.model_msg = json.dumps(describe_model(model))
        self.clients: set[ServerConnection] = set()
        self.wake = asyncio.Event()
        self._last_sent = ""

    # -------------------------------------------------------------- http
    def process_request(self, connection: ServerConnection, request: Request):
        path = request.path.split("?", 1)[0]
        if path == WS_PATH:
            return None
        name = PAGES.get(path)
        if name is None:
            return connection.respond(HTTPStatus.NOT_FOUND, "Not found\n")
        body = (STATIC / name).read_bytes()
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        headers = Headers([("Content-Type", ctype), ("Content-Length", str(len(body))),
                           ("Cache-Control", "no-store")])
        return Response(200, "OK", headers, body)

    # --------------------------------------------------------- websocket
    async def handler(self, ws: ServerConnection) -> None:
        self.clients.add(ws)
        try:
            await ws.send(self.model_msg)
            await ws.send(json.dumps(self.session.state()))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    err = self.session.handle(msg) if isinstance(msg, dict) else "not an object"
                except json.JSONDecodeError:
                    err = "invalid JSON"
                if err:
                    await ws.send(json.dumps({"type": "error", "message": err}))
                self.wake.set()
                await self.broadcast(force=True)
        finally:
            self.clients.discard(ws)

    async def broadcast(self, force: bool = False) -> None:
        text = json.dumps(self.session.state())
        if not self.clients or (text == self._last_sent and not force):
            return
        self._last_sent = text
        for ws in list(self.clients):
            try:
                await ws.send(text)
            except Exception:  # connection closing; its handler cleans up
                self.clients.discard(ws)

    # ------------------------------------------------------------- pacing
    async def run(self) -> None:
        """Advance the session according to its mode while not paused."""
        loop = asyncio.get_running_loop()
        s = self.session
        tick_hz = float(s.tick_hz)
        anchor, done, last_send = loop.time(), 0, 0.0
        state_key = None
        while True:
            key = (s.mode, s.paused, id(s.engine))
            if key != state_key:            # mode, pause or reset changed: re-anchor
                state_key, anchor, done = key, loop.time(), 0
            if s.paused:
                self.wake.clear()
                await self.wake.wait()
                continue
            now = loop.time()
            if s.mode == "fast":
                end = now + FAST_SLICE_S
                while loop.time() < end:
                    s.step()
            else:
                due = int((now - anchor) * tick_hz) + 1 - done
                if due * 1.0 / tick_hz > MAX_LAG_S:   # overrun: drop the backlog
                    anchor, done, due = now, 0, 1
                for _ in range(max(due, 0)):
                    s.step()
                    done += 1
            if loop.time() - last_send >= 1 / SEND_HZ:
                last_send = loop.time()
                await self.broadcast()
            if s.mode == "fast":
                await asyncio.sleep(0)
            else:
                wait = anchor + done / tick_hz - loop.time()
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=max(wait, 0.0))
                except asyncio.TimeoutError:
                    pass


async def start(model: Model, host: str, port: int, trace=None):
    """Start serving; returns (App, server). Port 0 picks a free port."""
    app = App(model, trace)
    server = await serve(app.handler, host, port, process_request=app.process_request)
    asyncio.get_running_loop().create_task(app.run())
    return app, server
