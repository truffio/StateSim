# StateSim

A lightweight, deterministic Python engine that makes aircraft Autoflight /
Autopilot guidance requirements executable. Logic is expressed as state
machines and Boolean equations defined in CSV files and evaluated on a
time-based, synchronous simulation loop. There is no front end in the current
phase; the engine is an importable package (`statesim`).

See `requirements_simulation_framework_spec.yaml` for the full specification.

## Development plan

### Scope
Evaluation and execution of equations and state machines only. No front end,
WebSocket server or orchestration server (deferred). Python only; fully
synchronous and deterministic (no async, threads, wall-clock time or
randomness).

### Architecture (layered engine, compile at load)
| Module | Role |
|---|---|
| `model.py` | Frozen dataclasses: the shared contract |
| `loader.py` | CSV files -> immutable `Model`, with load-time checks |
| `scheduler.py` | Builds the execution plan ordered by band and manual order |
| `evaluator.py` | `compile()` expressions once, `eval()` them at run time |
| `trace.py` | Plain-text trace/log hook |
| `engine.py` | Runtime state (context, state machine states, tick) and API |

Public API: `load_model(master_csv)`, `Engine(model, trace=None)`, `.step()`,
`.run(ticks)`, `.snapshot()`, `.set_input(name, value)`.

Time is an integer tick count. Bands are explicit frequencies in Hz with no
required relationship between them; the tick rate is the least common
multiple of all band frequencies, so all arithmetic is exact. Execution order
is manual (band, then order); state machine order comes from the master file.

### Work breakdown, waves and model tiers
| Wave | Task | Model |
|---|---|---|
| Start | T0 Contracts: package skeleton, `model.py`, `docs/decisions.md` | opus |
| Start | T1 Requirement ID list (`docs/requirements.csv`) | sonnet |
| 1 (parallel) | T2 Loader and load checks, with unit tests | sonnet |
| 1 | T3 Scheduler, with unit tests | haiku |
| 1 | T4 Evaluator, with unit tests | haiku |
| 1 | T5 Trace and logging, with unit tests | haiku |
| 1 | T6 Requirement-based tests, written test-first from the spec | sonnet |
| 1 | T7 Fixture CSV sets with hand-computed expected results | sonnet |
| 1 | T8 Report generator, with unit test | haiku |
| 2 | T9 Engine / runtime, with unit tests | sonnet |
| 3 | T10 Full run, defect fixes, determinism tests | sonnet |
| 3 | T11 Independent semantics and traceability review | opus |
| 4 | T12 Final test report and README usage example | haiku |

Each task owns specific files so parallel agents do not collide. Requirement
tests (T6) and fixtures (T7) depend only on the spec and contracts, so they
are written before the engine is complete.

### Testing
- **Unit tests**: one file per module; coverage target of 90% or more.
- **Requirement-based tests**: each test is tagged `@pytest.mark.req("REQ-xxx")`
  and traces to `docs/requirements.csv`.
- **Determinism tests**: identical runs give identical logs; different
  `PYTHONHASHSEED` values give identical logs; shuffling CSV row order does not
  change results; static check for forbidden imports (random, time, threading,
  asyncio).
- **Final report**: `pytest --junitxml=reports/junit.xml`, then
  `python tools/make_report.py` produces `reports/test_report.md` covering both
  unit and requirement tests, with a requirement -> test -> result
  traceability matrix that flags untested requirements and orphan tests.

### Approved behavior defaults
Recorded in `docs/decisions.md`. Highlights: at most one transition fires per
state machine per pass; a state machine's state is a context variable named
after it (e.g. `AP == "ENGAGED"`); results are visible immediately to later
items in the same pass; result variables start `False`; reserved names `tick`,
`t` (absolute simulation time, ms), `dt` (ms since the item last ran); limits `MAX_EQUATIONS` and `MAX_STATE_MACHINES` are 10,000 each.

## Usage

Install in editable mode (Python 3.11+, no runtime dependencies):

```
pip install -e ".[dev]"
```

```python
from statesim import load_model, Engine, FileTraceWriter

model = load_model("tests/fixtures/minimal/master.csv")   # master CSV
with FileTraceWriter("run.log") as log:                   # plain-text trace
    eng = Engine(model, trace=log)
    eng.step()                       # first step is tick 1, t = 0 ms
    eng.set_input("go", True)        # external input
    eng.run(3)                       # run 3 more ticks
    print(eng.snapshot())
```

`snapshot()` returns `{"tick", "t" (ms), "states", "outputs", "inputs"}`:
state machine states are strings (use `AP == "ENGAGED"` in equations), outputs
are every equation / transition result variable. Inputs are Python values; the
inputs CSV `default_value` is parsed according to its `type` (`bool`, `int`,
`float`, `str`). Time is absolute simulation time in milliseconds (`t`), and
`dt` is the milliseconds since the item last ran.

### Actions (writing variables)

Equations and transitions only compute Booleans and states. To change a
variable, such as setting the speed slider to 0 when the aircraft starts to
climb, use actions. They are listed in an `actions` CSV (one Python assignment
per row, rows with the same name run in order). State machine rows name them
in two optional columns, `action_type` (`entry`, `exit` or `during`) and
`action`. Actions write inputs only. An internal counter is an input with
widget `none`. See `docs/decisions.md` Part C and `docs/cheatsheet.md`.

Known limitations (a load-time checker is a possible future feature): a default
state with no outgoing transition, a global transition to the current state and
undefined variable names are not detected at load. An undefined name raises
`EvaluationError` at run time with the file, line, tick and item.

Cheat sheet: `docs/cheatsheet.md`. Jupyter demos: `notebooks/` (quickstart,
closed-loop 6-state autopilot, bands/computation rate/timers/errors), with example CSV sets in `examples/`.

## Front end

A local web front end (`src/statesim_server/`, a separate package so the
engine stays synchronous) runs a model in real time or as fast as possible:

```
pip install -e ".[server]"
python -m statesim_server examples/autopilot2/master.csv
```

It opens `http://127.0.0.1:8765/`: input cards on the left (built from the
inputs CSV display columns), run controls at the bottom left, and the state
machines on the right, with the active state highlighted. Hover the active
state to see its next states. See `docs/frontend_ui_spec.md`.

## Tests and report

```
python -m pytest --junitxml=reports/junit.xml -q
python tools/make_report.py          # writes reports/test_report.md
```

The report covers unit tests and requirement-based use-case tests, with a
requirement -> test -> result traceability matrix.

## Status
Engine, front end (branch `frontend`), tests and the test report are in
place. The test report (`reports/test_report.md`) lists every requirement with
its tests and results.
