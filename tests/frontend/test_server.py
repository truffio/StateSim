"""Server over real HTTP and WebSocket connections."""

import asyncio
import json
import time
import urllib.request
from urllib.error import HTTPError

import pytest
from websockets.asyncio.client import connect

from statesim import load_model
from statesim_server.server import start

from .conftest import EXAMPLES

R = pytest.mark.req


def run(coro):
    return asyncio.run(asyncio.wait_for(coro, 20))


async def started(example="autopilot2"):
    app, server = await start(load_model(EXAMPLES / example / "master.csv"), "127.0.0.1", 0)
    return app, server, server.sockets[0].getsockname()[1]


async def recv_type(ws, kind):
    while True:
        msg = json.loads(await ws.recv())
        if msg["type"] == kind:
            return msg


@R("REQ-117")
def test_command_line_server_serves_page_and_files(server_url):
    url = server_url(EXAMPLES / "autopilot2" / "master.csv")
    page = urllib.request.urlopen(url).read().decode()
    assert '<script src="app.js">' in page
    for f in ("app.js", "app.css"):
        assert urllib.request.urlopen(url + f).status == 200
    with pytest.raises(HTTPError):
        urllib.request.urlopen(url + "../pyproject.toml")


@R("REQ-117", "REQ-119")
def test_websocket_sends_model_then_state_and_applies_messages():
    async def go():
        app, server, port = await started()
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            model = json.loads(await ws.recv())
            assert model["type"] == "model" and len(model["machines"]) == 5
            await ws.send(json.dumps({"type": "pause"}))
            st = await recv_type(ws, "state")
            while not st["paused"]:                  # skip updates sent before the pause
                st = await recv_type(ws, "state")
            await ws.send(json.dumps({"type": "press", "name": "toga"}))
            await ws.send(json.dumps({"type": "step"}))
            while st["states"]["state_ac"] != "Takeoff":
                st = await recv_type(ws, "state")
            await ws.send(json.dumps({"type": "set", "name": "capa", "value": "LAND9"}))
            err = await recv_type(ws, "error")
            assert "LAND9" in err["message"]
            await ws.send("not json")
            assert (await recv_type(ws, "error"))["message"] == "invalid JSON"
        server.close()
    run(go())


@R("REQ-128")
def test_real_time_paces_ticks_to_the_tick_rate():
    async def go():
        app, server, port = await started()              # 20 Hz
        t0, k0 = time.monotonic(), app.session.engine.tick
        await asyncio.sleep(1.0)
        rate = (app.session.engine.tick - k0) / (time.monotonic() - t0)
        server.close()
        return rate
    assert 17 <= run(go()) <= 23


@R("REQ-128", "REQ-131")
def test_fast_mode_runs_faster_and_updates_at_most_30_per_second():
    async def go():
        app, server, port = await started()
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "mode", "mode": "fast"}))
            await ws.send(json.dumps({"type": "set", "name": "fd_on", "value": True}))
            await ws.send(json.dumps({"type": "set", "name": "fd_on", "value": False}))
            await asyncio.sleep(0.3)                      # replies to the messages above
            while True:                                   # drain
                try:
                    await asyncio.wait_for(ws.recv(), 0.05)
                except asyncio.TimeoutError:
                    break
            # make every update different so none is skipped as unchanged
            t0, k0, count = time.monotonic(), app.session.engine.tick, 0
            end = t0 + 1.0
            while time.monotonic() < end:
                app.session.engine.set_input("radio_altitude", count % 2500)
                try:
                    await asyncio.wait_for(ws.recv(), end - time.monotonic())
                    count += 1
                except asyncio.TimeoutError:
                    break
            ticks = app.session.engine.tick - k0
        server.close()
        return count, ticks
    count, ticks = run(go())
    assert count <= 32
    assert ticks > 1000                                   # far above 20 ticks/s
