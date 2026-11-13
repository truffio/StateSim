"""Fixtures: a real server process on a free port."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


@pytest.fixture
def server_url():
    """Start `python -m statesim_server` on a free port; yield its URL."""
    procs = []

    def start(master):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        p = subprocess.Popen([sys.executable, "-m", "statesim_server", str(master),
                              "--port", "0", "--no-browser"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        procs.append(p)
        line = p.stdout.readline()
        assert " at http://" in line, line
        return line.split(" at ", 1)[1].split()[0]

    yield start
    for p in procs:
        p.terminate()
        p.wait(timeout=5)
