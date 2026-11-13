# StateSim

A lightweight, deterministic Python engine that makes aircraft Autoflight /
Autopilot guidance requirements executable. The logic is written as state
machines and Boolean equations in CSV files and evaluated on a time-based,
synchronous loop. A local web front end lets you drive a model by hand, with
aircraft panels such as a flight control panel; tests drive the same model
from Python.

## Documentation

| Document | What it is |
|---|---|
| [Cheat sheet](docs/cheatsheet.md) | One-page reference: API, CSV columns, execution rules, trace format |
| [Decisions](docs/decisions.md) | The authoritative behaviour spec: engine (Parts A, B), actions (Part C), front end (Part D) |
| [User interface spec](docs/frontend_ui_spec.md) | The front end screen: panels, input cards, state machine grid, run controls, colours |
| [Requirements](docs/requirements.csv) | Numbered requirements (REQ-xxx), each traced to its source and to its tests |
| [Framework spec](docs/requirements_simulation_framework_spec.yaml) | The original specification; `decisions.md` wins where it is more specific |
| [Timeline design](docs/future_timeline.md) | Live timeline and sequence chart: design and decisions |

## Install and run

Python 3.11 or later. The engine has no runtime dependencies.

```
pip install -e ".[dev]"        # engine and tests
pip install -e ".[server]"     # front end server
```

Run a model in the browser:

```
python -m statesim_server examples/autopilot3/master.csv
```

It opens `http://127.0.0.1:8765/`. Aircraft panels sit on top, input cards on
the left, run controls at the bottom left, and the state machines on the
right with the active state highlighted. Hover over the active state to see
where it can go next. Options: `--port N`, `--no-browser`, `--trace FILE`.

The **Timeline** button in the run bar shows a pane with one lane per state
machine, and the input changes, over time. Click a transition to see what it
caused (a sequence chart).

Or run it from Python:

```python
from statesim import load_model, Engine, FileTraceWriter

model = load_model("examples/quickstart/master.csv")
with FileTraceWriter("run.log") as log:       # plain-text trace
    eng = Engine(model, trace=log)
    eng.step()                                # first step: tick 1, t = 0 ms
    eng.set_input("sw", True)                 # external input
    eng.run(3)                                # 3 more ticks
    print(eng.snapshot())                     # tick, t, states, outputs, inputs
```

## Defining a model

A model is a folder of CSV files (plus optional HTML panels), tied together by
one **master** CSV. Paths are relative to the master file. Every file has a
header row, and the column order is free. Expressions are plain Python
(`a and not b`, `alt > 1000`, `state_ac == 'Climb'`).

| File | Holds | How many |
|---|---|---|
| Master | The list of files, machine order and rates | 1 |
| Inputs | External inputs and internal variables | 0 or 1 |
| State machine | One state machine | any number |
| Equations | Standalone Boolean equations | 0 or 1 |
| Actions | Assignments that write variables | 0 or 1 |
| Panel (HTML) | An aircraft panel for the front end | any number |

### 1. Master

One row per file.

```
file_name,type,order,band,name,scale,init_action
state_ac.csv,state_machine,10,10,Aircraft,,
state_ap.csv,state_machine,20,10,AP engage,,
equations.csv,equations,,,,,
inputs.csv,inputs,,,,,
actions.csv,actions,,,,,
fcp.html,panel,,,Flight control panel,0.75,
```

- `type`: `state_machine`, `inputs`, `equations`, `actions` or `panel`.
- `order` and `band` are required on `state_machine` rows. `band` is the rate
  in Hz. `order` sets when the machine runs within its band.
- `name` (optional) is the title shown on the front end. If it's empty, the
  file name is used. Equations always use the file name: `state_ac.csv` is
  read as `state_ac`.
- `scale` (optional, panel rows) shows the panel at that size, for example
  `0.75`.
- `init_action` (optional, `state_machine` rows) names an action that runs
  once on the machine's first pass.

### 2. Inputs

```
variable_name,type,default_value,group,widget,label,min,max,step,choices,lit_by,wide,panel
radio_altitude,int,0,Aircraft,slider,Radio altitude (ft),0,2500,5,,,,
capa,enum,LAND3,Aircraft,dropdown,,,,,NONE|APPR1|LAND3,,,
TOGA,bool,false,Stick,momentary,TOGA,,,,,,,
AP_btn,bool,false,,momentary,,,,,,,,fcp.html
climb_ticks,int,0,,none,,,,,,,,
```

- `variable_name`, `type` and `default_value` are required. `type` is `bool`,
  `int`, `float`, `str` or `enum`.
- The other columns only change how the input looks on the front end, and a
  file without them still loads.
  - `group` is the card the input appears in.
  - `widget`: `switch`, `momentary` or `lit` for a bool; `slider` or `number`
    for an int or float; `dropdown` for an enum; `text` for a str.
  - A `momentary` push-button holds the input true for one period of the
    slowest band. A `lit` push-button is lit by the variable named in `lit_by`.
  - `none` makes an internal variable, such as a counter or a flag that only
    actions write. It gets no control.
  - `panel` names the HTML panel that drives the input. The input then gets no
    card. Its widget is `momentary`, `toggle` or `knob`.
- Full column rules: [UI spec section 4.2](docs/frontend_ui_spec.md).

### 3. State machines

One file per machine. The file name is the machine's name, and its current
state is a string variable with that name (`state_ap == 'Engaged'`).

```
transition_id,current_state,next_state,default_state,equation,result_variable,rationale,title,order,action_type,action
T1,Off,Engaged,Off,AP_btn,ap_t1_btn,Pilot engages AP,Engage,2,entry,AP_ON
T1,Off,Engaged,,law_AP,ap_t1_law,AP law available,Engage,2,,
T2,Engaged,Off,,AP_btn or APdisc,ap_t2,Pilot disengages AP,Disengage,3,entry,AP_OFF
G1,,Off,,not law_AP,ap_g1,AP law lost,Law lost,1,entry,AP_OFF
```

- **A transition is one or more rows that share a `transition_id`.** Its
  rows are ANDed, so extra rows act as guards. In the example, T1 needs both
  `AP_btn` and `law_AP`.
- `current_state` is the state the transition leaves. **Leave it empty for a
  global transition**, which can fire from any state (G1).
- `default_state` is filled on exactly one row: the starting state.
- `equation` is the row's Boolean condition. Its result is stored in
  `result_variable`, a unique name that other logic can read.
- `order` sets the order of the transitions. On each pass all rows are
  evaluated, and the **first** enabled transition fires. At most one fires per
  pass. Give global transitions the lowest numbers when they must win.
- `rationale` and `title` document the transition. The title also appears in
  the trace.
- `action_type` and `action` (optional) run an action:
  - `entry` runs after the transition fires.
  - `exit` runs just before the state changes.
  - `during` runs on every pass spent in `current_state` when no transition
    fires.

### 4. Equations

```
equation,explanation,rationale,result_variable,band,order
state_ap == 'Engaged' and state_at == 'Active',AP and AT both on,,ap_at_on,10,100
t >= 2000,2 s timer,,timer_2s,10,101
```

- Each row is a standalone Boolean, assigned to `result_variable` every time
  it runs, at `band` Hz and in `order` within its band.
- State machines and other equations can use the result.
- An equation can read its own result, which gives its value from the previous
  pass. That makes a latch, for example
  `(state_ac == 'Descent' and appr) or (appr_light and state_ac != 'Landed')`.
- Timers are expressions on `t`, the simulation time in ms. Also available are
  `tick`, and `dt`, the ms since this item last ran.

### 5. Actions

Equations and transitions only compute values. To **write** a variable (set
the speed to 0 at climb, engage AP, count passes), use an action:

```
action,statement,rationale
AP_ON,ap_on = True,
AP_ON,fd_on = True,FD comes on with AP
AP_OFF,ap_on = False,
CLIMB_TIMER,climb_ticks += 1,
```

- Each row is one Python assignment (`=`, `a = b = 0` or `+=`). Rows with
  the same `action` name run in file order.
- Actions write inputs only. Declare internal variables in the inputs CSV
  with widget `none`.
- Writes are visible at once to later items in the same pass, and they appear
  in the trace.

### 6. Aircraft panels (optional)

A panel is an HTML file with its own CSS. StateSim wires it through
attributes, and its scripts never run.

```html
<button data-input="AP_btn" data-lit-by="ap_on">AP</button>   <!-- press + light -->
<div data-input="hdg_sel"></div>                              <!-- knob -->
<span data-show="hdg_sel" data-format="%03d"></span>          <!-- readout -->
```

`data-lit-by` adds the class `lit` while the variable is true, and the
panel's CSS draws the light. See [UI spec section 3](docs/frontend_ui_spec.md).

### How a model runs

- **Ticks and bands:** time advances in integer ticks. The tick rate is the
  least common multiple of all the bands. On each tick, the due bands run
  from the highest frequency to the lowest, and within a band by `order`.
- **Same-pass visibility:** a later item sees an earlier item's results in
  the same pass. Order is never implicit, so give `order` numbers with care.
- **Holding values:** between two passes an item holds its value. A slow band
  never sees an input change that is reverted before its next pass.
- **Load checks:** loading checks syntax, names, states, orders and bindings,
  and stops on the first error with its `file:line`.
- **Not checked at load:** undefined names, which raise `EvaluationError` at
  run time with the file, line and tick. Also a default state with no way out,
  and a global transition to the current state, which does nothing but still
  wins the pass.

### Examples

| Folder | Shows |
|---|---|
| `examples/quickstart` | The smallest model: one lamp, one switch |
| `examples/timers` | Bands, `t` and `dt` |
| `examples/autopilot` | A 6-state autopilot closed-loop with a Python aircraft model (`plant.py`) |
| `examples/actions` | Entry, exit, during and init actions |
| `examples/autopilot2` | Autoland logic with a flight control panel |
| `examples/autopilot3` | Autoland with actions, FCP and FMA panels |

Jupyter demos are in `notebooks/`.

## Architecture

| Module | Role |
|---|---|
| `statesim/model.py` | Frozen dataclasses: the shared contract |
| `statesim/loader.py` | CSV files -> immutable `Model`, with load-time checks |
| `statesim/scheduler.py` | Execution plan ordered by band and `order` |
| `statesim/evaluator.py` | Compiles expressions once, evaluates them at run time |
| `statesim/engine.py` | Runtime state and API (`step`, `run`, `set_input`, `snapshot`) |
| `statesim/trace.py` | Plain-text trace |
| `statesim/timeline.py` | Records transitions and input changes with their causes for the timeline pane |
| `statesim_server/` | Local web server and front end (a separate package, so the engine stays synchronous) |

The engine is deterministic: there are no threads, async code, wall-clock time
or randomness.

## Tests and report

```
python -m pytest --junitxml=reports/junit.xml -q
python tools/make_report.py          # writes reports/test_report.md
```

Unit tests, requirement tests (each tagged `@pytest.mark.req("REQ-xxx")`),
determinism tests and front end tests (browser tests need Playwright). The
report traces every requirement to its tests and results.
