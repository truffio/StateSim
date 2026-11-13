# Decisions: authoritative behavior spec

This file is the authoritative behavior specification for the engine. Where
it is more specific than `docs/requirements_simulation_framework_spec.yaml`, this
file wins. Part A is user-approved and recorded verbatim. Part B records
contract details resolved while writing the package skeleton (T0); the
module docstrings in `src/statesim/` repeat them next to each signature.

## Part A: user-approved semantics (verbatim)

1. At most one transition fires per SM per pass; all rows of all transitions
   evaluated every pass (no short-circuit), first enabled transition in order
   wins; transitions ordered by their rows' `order` (min per transition_id)
   then transition_id; the SM is scheduled as one unit at its master-file
   `order` within its band, sharing the ordering space with equations.
2. An SM's state is a context variable named after the SM (file stem)
   holding a string, e.g. AP == "ENGAGED".
3. Results and state changes are visible immediately to later items in the
   same pass.
4. Bands are explicit Hz frequencies with no required relationship;
   tick_hz=LCM of all band frequencies (exact arithmetic, Fractions);
   period_ticks=tick_hz/band_hz; every band runs on the first step: step()
   increments tick then runs items where (tick-1) % period_ticks == 0; when
   several bands are due on one tick the higher frequency runs first, then
   lower; within a band by `order`. (Revised T11b) The first step is t = 0:
   see item 6.
5. Ties on (band,order): by master-file row, then CSV row.
6. Reserved context names (revised T11b): tick; `t` = ABSOLUTE simulation
   time in MILLISECONDS, an exact Fraction computed as
   `Fraction(tick-1)*1000/tick_hz` (never accumulated), so the first step is
   t=0 and t keeps increasing; `dt` = milliseconds since the previous run of
   the item being evaluated; on its first run dt is the ideal delta as if it
   were the second run, i.e. `1000/band_hz` ms, so dt is always the item's
   period in ms. `t` does not depend on which other bands exist (a timer
   `t >= 2000` fires at the same simulation time with or without an extra
   20 Hz band).
7. Result variables start False.
8. Input default_value (revised T11b) is parsed by the loader into a Python
   native value according to the inputs CSV `type` column: `bool` accepts
   (case-insensitive) true/false/1/0 (so Python `True`/`False` work); `int`
   -> int; `float` -> float; `str` -> the raw string. Any other/unknown type,
   or a value that fails to convert (including an empty int/float/bool), is
   a ModelError with file:line. `set_input` takes Python values as given, no
   conversion.
9. Log: result changes, state transitions, set_input; one line per event
   with t in milliseconds (`%.3f`), e.g.
   `tick=000012 t=1100.000 | AP | T3 OFF->ARMED "title" | alt=1000, ap_sw=True`,
   values sorted by name.
10. MAX_EQUATIONS/MAX_STATE_MACHINES = 10,000.
11. Global transition to the current state is a no-op, not logged.
12. Timers = expressions over t; "components" deferred.
13. Master CSV (columns file_name, type in {state_machine,equations,inputs},
    order and band [state_machine rows only, both required], optional name); paths relative to the master file's
    directory; duplicate result_variable across files is a load error;
    set_input on unknown name raises KeyError; snapshot also includes inputs.
14. Load checks: expression syntax, duplicate transition_id, unknown states,
    exactly one default_state per SM, a valid band on every master SM row
    and no band column in SM files, limits.
15. `order` column in SM files orders transitions within the SM. (Revised
    2026-11-11) A state machine's band is set on its master CSV row, not in
    its file.

Equations are Python syntax evaluated with `eval(code, ctx)`: the live
context dict is the eval GLOBALS (revised T11b), with `__builtins__` set once
in it, so comprehensions and lambdas can see context names. `__builtins__` is
excluded from snapshots and trace values. Expressions are compiled once in
`Engine.__init__` (code objects are NOT stored in the frozen Model).

## Part B: resolved contract details (T0)

- **Numbers.** `band_hz`, every `order` and `tick_hz` are `fractions.Fraction`
  (parsed with `Fraction(text)`, so "20", "0.5", "1/3" all work). The LCM of
  rationals is `lcm(numerators) / gcd(denominators)` (`model.compute_tick_hz`).
  `period_ticks` is an `int`. `Engine.t` is an exact Fraction in
  milliseconds; `snapshot()["t"]` is `float(t)` (ms).
- **Schedule key.** `(-band_hz, order, seq)`. `seq` enumerates items in
  master-file row order; the equations row expands to one item per equation in
  CSV row order. This realises item 5 (equations all share one master row).
- **Transition id tie-break.** Natural key: numeric ids compare as integers
  and sort before non-numeric ids, which compare as strings
  (`model.transition_sort_key`).
- **No-op global transition (item 11)** still counts as the winning
  transition for that pass: later transitions in order do not fire.
  A non-global self-transition (current_state == next_state) fires and is logged.
- **Row results in SMs.** Every row's `result_variable` is written each pass
  regardless of the current state; changes are logged under the SM's name.
- **"Duplicate transition_id"** means rows sharing an id disagree on
  `current_state` or `next_state` (sharing an id is how rows are grouped).
- **"Unknown state"** means a non-empty `current_state` that is neither the
  default state nor any transition's `next_state` (it could never be entered).
- **Transition order (T11b).** A transition is evaluated when its smallest
  row `order` comes due: all its rows are evaluated together (no order among
  them), ties between transitions broken by natural transition_id. The row
  result variables of a transition are all written at that point.
- **Shared transition_id.** Rows sharing a transition_id, contiguous or not,
  are ONE transition and their equations are ANDed.
- **Runtime errors (T11b).** An exception raised while evaluating an
  expression is wrapped in `statesim.EvaluationError` carrying the
  row/equation source (`file:line`), the tick and the item name (state
  machine or result variable); the original exception is chained
  (`__cause__`). Undefined names are not detected at load: they crash at run
  time, now with location.
- **API details (T11b).** `run(n)` raises ValueError for n < 0.
  `snapshot()` deep-copies values. `TraceSink` and `format_event` are
  exported from `statesim`.
- **Known limitations (future checker feature, deliberately NOT checked at
  load, T11b).** A default state with no outgoing transition; a global
  transition to the current state (it is a no-op that still wins the pass and
  is not logged); undefined names in equations; walrus/assignment in
  equations (equations cannot be relied upon to assign; result variables
  and inputs are only guaranteed distinct names); equation names that are
  Python keywords.
- **Names.** result_variables, input names and SM names must be Python
  identifiers, must not be reserved (tick, t, dt) and must all be mutually
  unique; any clash is a load error.
- **Master file.** At most one `equations` row and at most one `inputs` row
  (zero allowed, so minimal models need only SM files).
- **MAX_EQUATIONS** counts standalone equations plus every SM row.
- **Trace text.** Component is the SM name, `EQ` for standalone equations,
  `INPUT` for set_input. Actions: transitions `T3 OFF->ARMED "title"` (id
  prefixed with `T` when it starts with a digit; title = first non-empty row
  title); results `var False->True`; inputs `set alt 0->1000`. Values: names
  used by the expression(s) involved that exist in the context, sorted;
  strings shown with `repr()`, Fractions as `%.6f`; event time `t` as ms `%.3f`, others with `str()`.
  `set_input` is logged on every call, at the current tick.
- **Sources.** `"file:line"`, file as written in the master CSV, 1-based
  physical line with the header on line 1.

## Part C: actions (setvar), user-approved 2026-11-12

Actions let the logic write variables, which the previous tool did with a
transition's `set_vars`.

- **Actions CSV.** A master row of type `actions` (at most one) lists a file
  with columns `action, statement` and optional `rationale`. Each row is ONE
  Python assignment: `x = 0`, chained `a = b = 0`, or augmented `x += 1`;
  targets are plain names. Rows sharing an `action` name form that action and
  run in file row order (row order matters in this file only). Anything else
  (two statements, a call, `a.b = 1`, unpacking) is a load error.
- **Targets.** A statement may write inputs only. An internal variable
  (counter, timer, flag) is declared in the inputs CSV with widget `none`: it
  is not shown on the front end. Writing an equation result or a state machine
  state is a load error, so each variable has one kind of writer. Values are
  not type-checked or clamped to min/max (like `set_input`).
- **State machine columns.** Optional `action_type` and `action` on any row;
  both set or both empty. `action_type` is one of:
  - `entry`: runs when the row's transition fires, after the state changes.
  - `exit`: runs when the row's transition fires, before the state changes.
    At most one entry and one exit action per transition (across its rows).
  - `during`: belongs to the row's `current_state` (not allowed on a global
    row). It runs on each pass spent in that state when no transition fires.
    At most one during action per state (repeating the same name is fine).
  An action name with no definition in the actions CSV is a load error.
- **Order in one pass of a machine.** All rows evaluated; winner selected as
  before. If a transition fires: exit action, state change (logged), entry
  action. If none fires, or the winner is a global self-transition (no-op),
  the current state's during action runs. A non-global self-transition fires,
  so it runs exit and entry and not during.
- **Initial action.** Optional master column `init_action` on
  `state_machine` rows (an error on other rows): an action run once on the
  machine's first pass, before its transitions are evaluated. Empty (the
  default) runs nothing. Reset builds a new engine, so it runs again.
- **Visibility and trace.** Writes are visible immediately to later
  statements and items in the same pass. Each changed target is logged with
  component = the state machine name and action
  `<ACTION>: set <var> <old!r>-><new!r>`, values = names used by the
  statement. The values on a transition event are taken before its exit
  action runs. A runtime error raises EvaluationError with the actions CSV
  row as source and the state machine as item.
- **Front end.** Controls redraw from the engine's input values every step,
  so a slider written by an action moves by itself; the user can still move
  it afterwards (last writer wins).

## Part D: front end, user-approved 2026-11-11 and 2026-11-12

The front end decisions behind `docs/frontend_ui_spec.md`. The numbers are
the ones the requirements (`decisions.Dn`) and the UI spec refer to; gaps are
decisions later merged into others.

| # | Topic | Decision |
|---|---|---|
| D1 | Architecture | A local Python server (`statesim_server`) runs the `statesim` engine and serves a web front end (HTML/CSS/JavaScript) over a WebSocket. The engine exists only in Python; the page never evaluates logic. The server listens on 127.0.0.1 by default. |
| D2 | Model files | CSV only (plus HTML files for aircraft panels). No system JSON file. |
| D3 | Input display | Widget type, min, max, step, choices, grouping and similar live in the inputs CSV. |
| D4 | Enum type | An `enum` input type: a string restricted to the `choices` list. |
| D5 | Execution | Time-based: items run periodically at their band rates, so values settle over time. There is no "run until settled" step. |
| D6 | Run modes | **Real time** (the server paces the ticks against the wall clock, as closely as the OS allows) and **as fast as possible**. The engine itself stays free of wall-clock time and async code; the server is a separate package. |
| D7 | Push-button pulse | A press holds the input true for one period of the slowest band, then false, so slow-band logic sees it. |
| D8 | Lit buttons | A button can be lit by a logic variable (`lit_by`, `data-lit-by`). Lights follow the variable, never the click. |
| D9 | Priority | Every state machine and equation has an order number. Global transitions get lower numbers when they must win. No implicit precedence. |
| D10 | Rationale and titles | Kept in the state machine files and used in the trace; not shown on the screen. |
| D11 | Equations on screen | Not shown. They work in the background, driving state machines and panel lights and readouts. |
| D12 | Rates on screen | Not shown; no staleness indicator. |
| D13 | Ordering | Machine order and transition order come from the definition files. |
| D16 | Log | No log panel on the screen; the engine trace still exists (`--trace FILE`). |
| D17 | Writing variables | Equations and transitions never write variables. Actions (Part C) write inputs; internal variables are inputs with widget `none` and get no card. |
| D18 | Condition display | No conditions on screen, so no green/red colouring of rows or terms. |
| D19 | Machine order | State machines appear in the order of their master CSV rows. |
| D20 | State order | A machine's states appear in the order they appear in its CSV file. |
| D21 | Transitions on screen | Not shown. The active state is strongly highlighted; hovering it (or focusing it) highlights the targets of its own transitions. Global transition targets are not highlighted (revised 2026-11-12): their conditions often limit the states they can fire from. |
| D22 | Inputs CSV columns | Optional display columns `group, widget, label, min, max, step, choices, lit_by, wide, panel`; files without them still load. |
| D24 | Run controls | Real time or as fast as possible, Pause/Resume, Step (only while paused), Reset (keeps the model, run mode and pause state). In real time, a backlog longer than 0.5 s is dropped rather than caught up. |
| D26 | Screen updates | Sent after ticks, at most 30 per second. |
| D27 | Loading | Model path on the command line: `python -m statesim_server MASTER_CSV`. Reset restores start values without reloading files. |
| D28 | Clients | Designed for one browser tab. Several tabs share the same session and see the same values. |
| D29 | Front end tests | Session unit tests, server tests over real HTTP and WebSocket connections, and browser tests with Playwright (skipped when Playwright or Chromium is missing). |
| D30 | Machine display names | Optional master CSV `name` column; a machine card is titled with it, or with the file name when empty. Equations still use the file name (e.g. `state_ac`). |
| D32 | Load errors | The first load error stops loading, with its `file:line`. |
| D33 | Divider position | Remembered in the browser's local storage and restored when the page is opened again. |
| D34 | Aircraft panels | A panel is an HTML file listed in the master CSV (type `panel`), wired by `data-input`, `data-show`, `data-format` and `data-lit-by` attributes. Its scripts never run. |
| D35 | Panel placement | A full-width top pane above the left and right panes, always shown. Panels sit side by side on one row in master order (revised 2026-11-12); if the row is too wide, all are scaled down by one common factor. |
| D36 | Panel inputs | Inputs CSV `panel` column: the input is driven by that panel and gets no card. Panel widgets: `momentary`, `toggle` (each press flips the bool) and `knob` (int/float within min/max, no wrap). |
| D39 | Panel size | Master CSV `scale` column on panel rows (default 1); the example FCPs use 0.75. |
| D40 | Knob handling | Dragging a knob sets the angle under the pointer (absolute). |

### Open

| # | Topic | Question |
|---|---|---|
| O5b | Aircraft panels | Light equations for the remaining FCP buttons. |
| O8b | Reloading | Reload edited CSV files without restarting the server. Postponed. |

## Part E: timeline, user-approved 2026-11-12

The live timeline and sequence chart. The design is in
`docs/future_timeline.md`; the screen rules are in `docs/frontend_ui_spec.md`
section 11.

- **Lanes:** state machines only. Equations get no lane and never appear as
  events; they are folded into the cause links between machines.
- **Events:** transitions, labelled with their id (and the title on hover or
  when there is room).
- **Where:** an optional pane in the front end, updated live as the user works
  and states change. It can be shown or hidden.
- **Data source:** the current session's log, the same whether the session is
  driven by hand or by an automated test. There are no scenario files.
- **Pane:** at the bottom of the page, full width, hidden by default.
- **Time axis:** the view shows the last 30 s and follows the run.
- **Limits:** at most 20,000 timeline items (the oldest are dropped). A
  broadcast with more than 2,000 new items sends the whole timeline instead.
- **State entry counts as a cause ("A + B", issue #20):** when a transition
  fires one pass after its machine entered the transition's `current_state`,
  its causes are (A) the transition that entered the state and (B) whatever
  produced the conditions its rows read, which were already waiting. Before,
  such a transition had no cause. Rule in `docs/future_timeline.md` section 1.
