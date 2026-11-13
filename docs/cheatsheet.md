# StateSim cheat sheet

Demos (Jupyter): `notebooks/01_quickstart.ipynb`, `02_autopilot_state_machine.ipynb`,
`03_bands_timers_errors.ipynb`. Example CSV sets: `examples/`.

## Install and run
```
pip install -e ".[dev]"          # Python 3.11+, no runtime deps
jupyter notebook notebooks/      # demos (notebooks fall back to ../src if not installed)
python -m pytest -q              # tests
```

## Minimal code
```python
from statesim import load_model, Engine, ListTraceSink, FileTraceWriter

model = load_model("examples/quickstart/master.csv")
trace = ListTraceSink()                       # or FileTraceWriter("run.log")
eng = Engine(model, trace=trace)

eng.set_input("sw", True)                     # external input (Python value)
eng.step()                                    # one tick (first step = tick 1, t = 0 ms)
eng.run(10)                                   # 10 more ticks (n < 0 -> ValueError)
snap = eng.snapshot()                         # copy: tick, t, states, outputs, inputs
eng.tick, eng.t                               # current tick / time (ms)
trace.lines()                                 # list of log lines
```

| API | Notes |
|---|---|
| `load_model(master_csv)` | returns an immutable `Model`; raises `ModelError` (`file:line`) |
| `Engine(model, trace=None)` | compiles all expressions once |
| `.step()` / `.run(n)` | advance 1 / n ticks |
| `.set_input(name, value)` | `KeyError` if unknown; visible at next evaluation; logged |
| `.snapshot()` | `{"tick","t" (ms),"states","outputs","inputs"}` |
| `ListTraceSink`, `FileTraceWriter(path)` | trace sinks; `FileTraceWriter` is a context manager |
| `ModelError`, `EvaluationError` | load error / run-time error (has `.source .tick .item`) |

## The CSV files
**Master** (`file_name,type,order,band`, optional `name`): one row per file.
For `state_machine` rows, `order` and `band` (Hz) are required; `name` is the
display name on the front end. `type` = `state_machine`,
`equations` or `inputs`. `order` is used for `state_machine` rows only. Paths
are relative to the master file. Max one equations row and one inputs row.

**Inputs** (`variable_name,type,default_value`): `type` = `bool` (true/false/1/0,
any case), `int`, `float`, `str`, `enum`. The value is parsed to a Python value.
Optional display columns for the front end: `group, widget, label, min, max,
step, choices, lit_by, wide` (enum choices separated by `|`; widgets: bool
`switch`/`momentary`/`lit`, int/float `slider`/`number`, enum `dropdown`, str
`text`). See `docs/frontend_ui_spec.md` section 4.

**Equations** (`equation,explanation,rationale,result_variable,band,order`):
one standalone Boolean equation per row. The result is assigned to
`result_variable` every time the row runs.

**State machine** (one file per machine; the machine name = file name without `.csv`):
`transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order`
(no band column: the machine's band is on its master row)

| Column | Meaning |
|---|---|
| `transition_id` | rows sharing an id are ONE transition; all rows are ANDed (guards) |
| `current_state` | state it leaves; **empty = global transition** (from any state) |
| `next_state` | state it enters |
| `default_state` | filled on exactly one row: the starting state |
| `equation` | Python-syntax Boolean expression |
| `result_variable` | Boolean variable receiving this row's result |
| `order` | evaluation order within the band (manual) |
| `action_type`, `action` | optional: `entry` / `exit` (when this row's transition fires) or `during` (each pass in `current_state` with no transition firing), and the action name |

**Actions** (`action,statement`, optional `rationale`; master type `actions`):
one Python assignment per row (`speed = 0`, `n += 1`, `a = b = 0`); rows with
the same `action` run in file order. Statements write inputs only; declare an
internal variable as an input with widget `none` (not shown). Order when a
transition fires: exit action, state change, entry action. A master
`init_action` column on a `state_machine` row runs an action once on the
machine's first pass (empty = none). See `docs/decisions.md` Part C.

```
# actions.csv                      # state_ac.csv (extra columns)
action,statement                   ...,order,action_type,action
CLIMB_INIT,ground_speed = 0        ...,8,entry,CLIMB_INIT
CLIMB_INIT,ap_on = True            ...,30,during,CLIMB_TIMER
CLIMB_TIMER,climb_ticks += 1
```

## Writing equations
* An equation can read its own result: it gets the previous pass value
  (False at start), which makes a latch, e.g.
  `(state_ac == 'Descent' and appr_selected) or (appr_light and state_ac != 'Landed')`.
* Plain Python: `a and not b`, `(x or y) and z`, `alt > 1000`, `AP == "ENGAGED"`.
* Names available: inputs, any result variable, state machine names (their
  current state as a string), and the reserved `tick`, `t` (ms), `dt` (ms).
* Timer: `t >= 2000`. Equations only read; they do not assign variables.
* A standalone equation can be used in a state machine through its `result_variable`.

## Execution rules
* Time is an integer tick count; **tick rate = LCM of all band frequencies**.
  Bands are explicit Hz values with no required relationship (20 Hz and 30 Hz is fine).
* A band runs on ticks where `(tick - 1) % period == 0`, so every band runs on the first step.
* Order per pass: higher frequency band first; within a band by `order`
  (state machines use the master `order`, equations their own); ties by master-file row then CSV row.
* A later item sees an earlier item's results **in the same pass**.
* A state machine evaluates all rows of all its transitions each pass, then fires
  the **first** enabled transition (at most one per pass). A transition is evaluated
  when its smallest row `order` is due; its rows have no order among themselves.
* Every item is evaluated continuously at its band rate for the whole run, and
  only then: between two passes it holds its value. An input change reverted
  between two passes of a slow band is never seen by that band.
* `t` = absolute ms (exact; first run is 0). `dt` = ms since the item last ran
  (first run: its period). Result variables start `False`.

## Closed loop with external software
```python
for _ in range(n):                             # one iteration = one tick
    s = eng.snapshot()                         # read modes / outputs
    eng.set_input("alt", model_of_aircraft(s)) # write the response back
    eng.step()
```
See `examples/autopilot/plant.py` and notebook 2 (6-state autopilot, equations
used as guards, global disconnect, 10 Hz monitor).

## Trace line
```
tick=000007 t=300.000 | EQ | mon_no_cap False->True | AP='ENGAGED', alt_cap=False
tick=000002 t=100.000 | Lamp | T1 OFF->ON "Turn on" | sw=True
tick=000001 t=0.000   | INPUT | set sw False->True | sw=True
```
Components: the state machine name, `EQ` (standalone equations), `INPUT`.

## Gotchas and known limitations
* Not checked at load (a future checker may): a default state with no outgoing
  transition (machine stays put), a global transition to the current state (wins
  the pass, does nothing), undefined names. An undefined name raises `EvaluationError`
  at run time with `file:line`, tick and item.
* Equations are evaluated with Python `eval` (trusted authors, no sandbox).
* `snapshot()` returns copies; modify inputs only with `set_input`.
* Deterministic by design: no threads, async, wall-clock time or randomness.

## Aircraft panels
HTML files listed in the master CSV (`fcp.html,panel,,,Flight control panel,0.75`;
the last column is the optional display `scale`), shown in a full-width top pane. Bind elements with attributes:
`data-input="var"` (button: `momentary`/`toggle`; element: `knob`),
`data-show="var" data-format="%03d"`, `data-lit-by="var"` (adds class `lit`).
Panel inputs set the inputs CSV `panel` column to the file name (no card).
Scripts in panel files never run. See `docs/frontend_ui_spec.md` section 3.

## Front end
```
pip install -e ".[server]"
python -m statesim_server examples/autopilot2/master.csv   # --port N, --no-browser, --trace FILE
```

## Tests and report
```
python -m pytest --junitxml=reports/junit.xml -q
python tools/make_report.py       # reports/test_report.md (unit + requirement tests)
```
