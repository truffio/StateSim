"""Command line: python -m statesim_server MASTER_CSV [--port N] [--no-browser]."""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser

from statesim import FileTraceWriter, ModelError, load_model

from .server import start


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m statesim_server",
                                description="Run a StateSim model with its web front end.")
    p.add_argument("master_csv", help="the model's master CSV file")
    p.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=8765, help="port (default 8765; 0 = any free port)")
    p.add_argument("--no-browser", action="store_true", help="do not open a browser")
    p.add_argument("--trace", metavar="FILE", help="write the engine trace to FILE")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        model = load_model(args.master_csv)
    except ModelError as e:
        print(f"model error: {e}", file=sys.stderr)
        return 2
    trace = FileTraceWriter(args.trace) if args.trace else None
    try:
        asyncio.run(_serve(model, args, trace))
    except KeyboardInterrupt:
        pass
    finally:
        if trace is not None:
            trace.close()
    return 0


async def _serve(model, args, trace) -> None:
    _app, server = await start(model, args.host, args.port, trace)
    port = server.sockets[0].getsockname()[1]
    url = f"http://{args.host}:{port}/"
    print(f"StateSim running {args.master_csv} at {url} (Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    await server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
