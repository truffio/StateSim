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
`t`, `dt`; limits `MAX_EQUATIONS` and `MAX_STATE_MACHINES` are 10,000 each.

## Status
Implementation in progress on branch `feature/engine`.
