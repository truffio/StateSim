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
         "/panels.js": "panels.js", "/timeline.js": "timeline.js", "/timeline.css": "timeline.css"}
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
        self._sent_gen = self.session.timeline.gen
        self._lock = asyncio.Lock()   # one sender at a time keeps message order per client

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
        try:
            async with self._lock:
                # Hand pending items to the existing clients first, so the
                # timeline sent below holds exactly the items already taken
                # and every later item arrives once, in a broadcast.
                await self._broadcast()
                await ws.send(self.model_msg)
                await ws.send(json.dumps(self.session.timeline_message()))
                await ws.send(json.dumps({**self.session.state(), "tl": []}))
                self.clients.add(ws)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    err = self.session.handle(msg) if isinstance(msg, dict) else "not an object"
                except json.JSONDecodeError:
                    err = "invalid JSON"
                if err:
                    await ws.send(json.dumps({"type": "error", "message": err}))
                self.wake.set()
                async with self._lock:
                    if self.session.timeline.gen != self._sent_gen:     # Reset
                        self.session.take_new_items()                  # the message holds them
                        await self._send_all(json.dumps(self.session.timeline_message()))
                        self._sent_gen = self.session.timeline.gen
                    await self._broadcast(force=True)
        finally:
            self.clients.discard(ws)

    async def _send_all(self, text: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send(text)
            except Exception:  # connection closing; its handler cleans up
                self.clients.discard(ws)

    async def broadcast(self, force: bool = False) -> None:
        async with self._lock:
            await self._broadcast(force)

    async def _broadcast(self, force: bool = False) -> None:
        """Send the state with the new timeline items (caller holds the lock)."""
        state = self.session.state()
        items, too_many = self.session.take_new_items()     # always taken, even with no clients
        if not self.clients:
            return
        if too_many:
            await self._send_all(json.dumps(self.session.timeline_message()))
            items = []
        key = json.dumps(state)                              # duplicate detection ignores tl
        if not items and key == self._last_sent and not force:
            return
        self._last_sent = key
        state["tl"] = items
        await self._send_all(json.dumps(state))

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
