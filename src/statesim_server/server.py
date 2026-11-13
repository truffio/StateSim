"""Local web server: serves the page and runs the session over a WebSocket.

The engine stays synchronous and free of wall-clock time; only this module
paces ticks against real time.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import sys
from urllib.parse import urlsplit
from http import HTTPStatus
from pathlib import Path

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from statesim import Model

from .session import Session, describe_model

STATIC = Path(__file__).resolve().parent / "static"
PAGES = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js", "/app.css": "app.css",
         "/panels.js": "panels.js", "/recording.js": "recording.js",
         "/recorder.html": "recorder.html", "/recorder.js": "recorder.js", "/timeline.js": "timeline.js", "/timeline.css": "timeline.css"}
WS_PATH = "/ws"
TIMELINE_TEXT = "/timeline.txt"   # the current run's timeline as text (a download)
SEND_HZ = 30            # at most this many screen updates per second
FAST_SLICE_S = 0.02     # "as fast as possible": run ticks for this long, then yield
REALTIME_SLICE_S = 0.05  # real time: run at most this long before yielding (catch-up batches)
SEND_TIMEOUT_S = 2.0     # a client that does not take a message this long is dropped
MAX_LAG_S = 0.5         # real time: a backlog longer than this is dropped, not caught up


class App:
    """Session plus pacing loop plus connected clients."""

    def __init__(self, model: Model, trace=None, host: str = "127.0.0.1") -> None:
        self.host = host
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
            if not self._own_page(request):
                return connection.respond(HTTPStatus.FORBIDDEN, "Forbidden: other origin\n")
            return None
        if path == TIMELINE_TEXT:
            body = self.session.timeline_text().encode("utf-8")
            headers = Headers([("Content-Type", "text/plain; charset=utf-8"),
                               ("Content-Length", str(len(body))), ("Cache-Control", "no-store"),
                               ("Content-Disposition", 'attachment; filename="statesim-timeline.txt"')])
            return Response(200, "OK", headers, body)
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

    def _own_page(self, request: Request) -> bool:
        """Only StateSim's own page may open the WebSocket: a browser request
        must come from the page this server served (Origin matches Host), and
        Host must name this machine (no DNS rebinding). A request with no
        Origin is not from a web page (a script or a test) and is allowed."""
        host = request.headers.get("Host", "")
        name = urlsplit(f"//{host}").hostname or ""
        if name not in {"127.0.0.1", "localhost", "::1", self.host.strip("[]")}:
            return False
        origin = request.headers.get("Origin")
        return origin is None or urlsplit(origin).netloc == host

    # --------------------------------------------------------- websocket
    async def handler(self, ws: ServerConnection) -> None:
        try:
            async with self._lock:
                # Take the pending items and build the new client's messages
                # before any await (the run loop steps between awaits), so the
                # timeline sent below holds exactly the items handed to the
                # existing clients, and every later item arrives once.
                state = self.session.state()
                items, too_many = self.session.take_new_items()
                timeline_text = json.dumps(self.session.timeline_message())
                first_state = json.dumps({**state, "tl": []})
                await self._send_state(state, items, too_many, timeline_text)
                if not await self._send_one(ws, self.model_msg, timeline_text, first_state):
                    return
                self.clients.add(ws)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    err = self.session.handle(msg) if isinstance(msg, dict) else "not an object"
                except json.JSONDecodeError:
                    err = "invalid JSON"
                except Exception as exc:          # a bad message must not close the connection
                    err = f"could not apply the message: {exc!r}"
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

    async def _send_one(self, ws: ServerConnection, *texts: str) -> bool:
        """Send to one client; a client that does not take its messages within
        SEND_TIMEOUT_S (a frozen tab) is dropped so it cannot hold up the others."""
        try:
            for text in texts:
                await asyncio.wait_for(ws.send(text), SEND_TIMEOUT_S)
            return True
        except Exception:  # timeout, or the connection is closing
            self.clients.discard(ws)
            if ws.transport is not None:
                ws.transport.abort()
            return False

    async def _send_all(self, text: str) -> None:
        clients = list(self.clients)
        if clients:
            await asyncio.gather(*(self._send_one(ws, text) for ws in clients))

    async def broadcast(self, force: bool = False) -> None:
        async with self._lock:
            await self._broadcast(force)

    async def _broadcast(self, force: bool = False) -> None:
        """Send the state with the new timeline items (caller holds the lock)."""
        state = self.session.state()
        items, too_many = self.session.take_new_items()     # always taken, even with no clients
        timeline_text = json.dumps(self.session.timeline_message()) if too_many else ""
        await self._send_state(state, items, too_many, timeline_text, force)

    async def _send_state(self, state: dict, items: list, too_many: bool,
                          timeline_text: str, force: bool = False) -> None:
        """Send a state with its new items to the clients (caller holds the lock).
        When the items are too many, the full timeline message goes first."""
        if not self.clients:
            return
        if too_many:
            await self._send_all(timeline_text)
            items = []
        key = json.dumps(state)                              # duplicate detection ignores tl
        if not items and key == self._last_sent and not force:
            return
        self._last_sent = key
        state["tl"] = items
        await self._send_all(json.dumps(state))

    async def stopped(self, exc: Exception) -> None:
        """A step failed: pause the session (Reset gives a working one again)
        and tell every client where, with the error's file:line, tick and item."""
        self.session.paused = True
        message = f"Paused: {exc}"
        print(f"StateSim: {message}", file=sys.stderr, flush=True)
        async with self._lock:
            await self._send_all(json.dumps({"type": "error", "message": message}))
            await self._broadcast(force=True)

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
            try:
                if s.mode == "fast":
                    end = now + FAST_SLICE_S
                    while loop.time() < end:
                        s.step()
                else:
                    due = int((now - anchor) * tick_hz) + 1 - done
                    if due * 1.0 / tick_hz > MAX_LAG_S:   # overrun: drop the backlog
                        anchor, done, due = now, 0, 1
                    end = now + REALTIME_SLICE_S
                    for _ in range(max(due, 0)):
                        s.step()
                        done += 1
                        if loop.time() >= end:   # slow steps: yield; a lag over MAX_LAG_S is dropped
                            break
            except Exception as exc:        # e.g. EvaluationError: an undefined name
                await self.stopped(exc)
                continue
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
    app = App(model, trace, host)
    server = await serve(app.handler, host, port, process_request=app.process_request)
    asyncio.get_running_loop().create_task(app.run())
    return app, server
