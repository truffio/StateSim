"""Server over real HTTP and WebSocket connections."""

import asyncio
import json
import socket
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
        app, server, port = await started()
        t0, k0 = time.monotonic(), app.session.engine.tick
        await asyncio.sleep(1.0)
        rate = (app.session.engine.tick - k0) / (time.monotonic() - t0)
        server.close()
        return rate, float(app.session.tick_hz)
    rate, tick_hz = run(go())
    assert tick_hz == 10 and 0.85 * tick_hz <= rate <= 1.15 * tick_hz


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
            await drain(ws, 0.3)                          # state carries t, so it never goes quiet
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


async def drain(ws, seconds):
    """All messages arriving in the next `seconds`."""
    out = []
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        try:
            out.append(json.loads(await asyncio.wait_for(ws.recv(), left)))
        except asyncio.TimeoutError:
            break
    return out


@R("REQ-172", "REQ-173")
def test_connect_sends_model_timeline_state_then_tl_deltas_without_duplicates():
    async def go():
        app, server, port = await started()
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            kinds = [json.loads(await ws.recv())["type"] for _ in range(3)]
            assert kinds == ["model", "timeline", "state"]
            await ws.send(json.dumps({"type": "press", "name": "toga"}))
            msgs = await drain(ws, 1.0)
        server.close()
        return msgs
    msgs = run(go())
    states = [m for m in msgs if m["type"] == "state"]
    assert all("tl" in m and "t" in m and m["gen"] == 1 for m in states)
    ids = [i["id"] for m in states for i in m["tl"]]
    assert ids and ids == sorted(set(ids))


@R("REQ-174")
def test_reset_sends_timeline_with_new_gen():
    async def go():
        app, server, port = await started()
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.send(json.dumps({"type": "press", "name": "toga"}))
            await drain(ws, 0.3)
            await ws.send(json.dumps({"type": "reset"}))
            msgs = await drain(ws, 0.5)
        server.close()
        return msgs
    msgs = run(go())
    tl = [m for m in msgs if m["type"] == "timeline"]
    assert tl and tl[0]["gen"] == 2
    later = [m for m in msgs if m["type"] == "state" and m["gen"] == 2]
    assert later
    seen = {i["id"] for i in tl[0]["items"]}
    assert not any(i["id"] in seen for m in later for i in m["tl"])


@R("REQ-172", "REQ-173")
def test_second_client_mid_run_sees_no_gaps_or_duplicates():
    async def go():
        app, server, port = await started()
        async with connect(f"ws://127.0.0.1:{port}/ws") as a:
            await a.send(json.dumps({"type": "press", "name": "toga"}))
            await drain(a, 0.3)
            async with connect(f"ws://127.0.0.1:{port}/ws") as b:
                await b.send(json.dumps({"type": "set", "name": "capa", "value": "bogus"}))
                msgs = await drain(b, 0.8)
        server.close()
        return msgs
    msgs = run(go())
    assert [m["type"] for m in msgs[:3]] == ["model", "timeline", "state"]
    ids = [i["id"] for i in msgs[1]["items"]]
    ids += [i["id"] for m in msgs[3:] if m["type"] == "state" for i in m["tl"]]
    assert ids == list(range(ids[0], ids[0] + len(ids)))   # contiguous, no repeats


@R("REQ-190")
def test_timeline_text_download(server_url):
    url = server_url(EXAMPLES / "actions" / "master.csv")
    resp = urllib.request.urlopen(url + "timeline.txt")
    assert resp.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert "attachment" in resp.headers["Content-Disposition"]
    text = resp.read().decode("utf-8")
    assert text.startswith("StateSim timeline: ") and "(run 1)" in text.splitlines()[0]


def _write_model(d, rows, inputs="variable_name,type,default_value\ngo,bool,false\n", actions=None):
    master = "file_name,type,order,band\nm.csv,state_machine,1,10\ninputs.csv,inputs,,\n"
    if actions:
        master += "actions.csv,actions,,\n"
        (d / "actions.csv").write_text(actions, encoding="utf-8")
    (d / "master.csv").write_text(master, encoding="utf-8")
    (d / "inputs.csv").write_text(inputs, encoding="utf-8")
    head = "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order"
    if actions:
        head += ",action_type,action"
        rows = "".join(r if r.count(",") > 8 else r.rstrip("\n") + ",,\n" for r in rows.splitlines(True))
    (d / "m.csv").write_text(head + "\n" + rows, encoding="utf-8")
    return load_model(d / "master.csv")


@R("REQ-117")
def test_runtime_error_pauses_reports_and_reset_recovers(tmp_path):
    """#25: a failing step pauses the run and tells the client; Reset + Resume work again."""
    model = _write_model(tmp_path, "1,A,B,A,go and undefined_name > 1,r1,,,1\n")

    async def go():
        app, server = await start(model, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.send(json.dumps({"type": "set", "name": "go", "value": True}))
            err = await recv_type(ws, "error")
            assert err["message"].startswith("Paused:") and "m.csv:2" in err["message"]
            st = await recv_type(ws, "state")
            while not st["paused"]:
                st = await recv_type(ws, "state")
            await ws.send(json.dumps({"type": "reset"}))
            await ws.send(json.dumps({"type": "resume"}))
            t0 = app.session.engine.tick
            await asyncio.sleep(0.4)
            assert app.session.engine.tick > t0 and not app.session.paused
        server.close()
        await server.wait_closed()
    run(go())


@R("REQ-117")
def test_action_writing_t_and_dt_keeps_the_server_running(tmp_path):
    """#26: t and dt are Fractions; an action storing them must not break the state messages."""
    model = _write_model(
        tmp_path,
        "1,A,B,A,go,r1,,,1,entry,STAMP\n2,B,A,,not go,r2,,,2,during,COUNT\n",
        inputs="variable_name,type,default_value\ngo,bool,false\nstarted,float,0\nelapsed,int,0\n",
        actions="action,statement\nSTAMP,started = t\nCOUNT,elapsed += dt\n")

    async def go():
        app, server = await start(model, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.send(json.dumps({"type": "set", "name": "go", "value": True}))
            await asyncio.sleep(0.4)
            st = await recv_type(ws, "state")
            while st["inputs"]["elapsed"] == 0:
                st = await recv_type(ws, "state")
            assert isinstance(st["inputs"]["started"], float) and isinstance(st["inputs"]["elapsed"], float)
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws2:          # new clients still connect
            assert json.loads(await ws2.recv())["type"] == "model"
        assert not app.session.paused
        server.close()
        await server.wait_closed()
    run(go())


@R("REQ-125")
def test_malformed_messages_get_an_error_and_keep_the_connection(tmp_path):
    """#27: wrong field types reply with an error; the socket stays open."""
    model = _write_model(tmp_path, "1,A,B,A,go and undefined_name > 1,r1,,,1\n",
                         inputs="variable_name,type,default_value\ngo,bool,false\nn,int,0\n")

    async def go():
        app, server = await start(model, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            for bad in ({"type": "set", "name": "n", "value": 1e999},
                        {"type": "set", "name": [], "value": 1},
                        {"type": "press", "name": {}},
                        {"type": "toggle", "name": 3}):
                await ws.send(json.dumps(bad))
                err = await recv_type(ws, "error")
                assert err["message"]
            await ws.send(json.dumps({"type": "pause"}))
            await ws.send(json.dumps({"type": "set", "name": "go", "value": True}))
            await ws.send(json.dumps({"type": "step"}))           # the step fails: error, still paused
            err = await recv_type(ws, "error")
            while not err["message"].startswith("Paused:"):
                err = await recv_type(ws, "error")
            assert "m.csv:2" in err["message"] and app.session.paused
            await ws.send(json.dumps({"type": "reset"}))
            st = await recv_type(ws, "state")
            while st["gen"] == 1:                              # skip messages sent before the reset
                st = await recv_type(ws, "state")
            assert st["inputs"]["go"] is False
        server.close()
        await server.wait_closed()
    run(go())


@R("REQ-128")
def test_realtime_never_blocks_the_event_loop_for_long(tmp_path):
    """#31: with a huge tick rate, each real-time batch is bounded in wall time."""
    (tmp_path / "master.csv").write_text("file_name,type,order,band\na.csv,state_machine,1,1000\n"
                                         "b.csv,state_machine,2,999.999\n", encoding="utf-8")
    head = "transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order\n"
    for n in "ab":
        (tmp_path / f"{n}.csv").write_text(head + f"1,A,B,A,False,{n}1,,,1\n", encoding="utf-8")
    model = load_model(tmp_path / "master.csv")

    async def go():
        app, server = await start(model, "127.0.0.1", 0)
        loop = asyncio.get_running_loop()
        worst, last, stop = 0.0, loop.time(), loop.time() + 1.5
        while loop.time() < stop:
            await asyncio.sleep(0.01)
            now = loop.time()
            worst, last = max(worst, now - last), now
        assert app.session.engine.tick > 0
        assert worst < 0.3, f"event loop stalled {worst:.2f} s"
        server.close()
        await server.wait_closed()
    run(go())


@R("REQ-117")
def test_a_client_that_stops_reading_does_not_stop_the_others(monkeypatch):
    """#32: a client whose sends never complete (a frozen tab) is dropped after
    the send timeout; the run and the other clients go on."""
    import statesim_server.server as srv
    monkeypatch.setattr(srv, "SEND_TIMEOUT_S", 0.3, raising=False)

    class Frozen:                                   # send() never completes
        transport = None
        aborted = False

        async def send(self, text):
            await asyncio.Event().wait()

    async def go():
        app, server, port = await started("autopilot3")
        async with connect(f"ws://127.0.0.1:{port}/ws") as ws:
            await ws.send(json.dumps({"type": "mode", "mode": "fast"}))
            frozen = Frozen()
            app.clients.add(frozen)
            t0, frames = app.session.engine.tick, 0
            loop = asyncio.get_running_loop()
            end = loop.time() + 2
            while loop.time() < end:
                try:
                    await asyncio.wait_for(ws.recv(), 0.5)
                    frames += 1
                except asyncio.TimeoutError:
                    pass
            assert frozen not in app.clients
            assert app.session.engine.tick > t0 and frames >= 20
        server.close()
        await server.wait_closed()
    run(go())
