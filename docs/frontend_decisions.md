# Front end: decisions and open points

Working notes for writing the front end requirements. Sources:
`docs/StateSim_FrontEnd_Spec.md` (the front end of a **previous** tool: a
JavaScript, event-driven engine in one HTML page, used only as a source of UI
ideas), `requirements_simulation_framework_spec.yaml`, and design discussions.
The screen is specified in `docs/frontend_ui_spec.md`; requirements REQ-114
to REQ-134 are in `docs/requirements.csv`. D22 to D29 are the defaults
proposed and accepted on 2026-11-11 before the first front end was built.

## Decided

| # | Topic | Decision |
|---|---|---|
| D1 | Architecture | A local Python server runs the `statesim` engine and serves a web front end (HTML/CSS/JavaScript) over WebSockets. The engine exists only in Python; there is no JavaScript engine and no in-browser Python. |
| D2 | Model files | CSV only. No system JSON file. |
| D3 | UI details of inputs | Widget type, min, max, step, choices, grouping and similar live in the inputs CSV file. |
| D4 | Enum type | Add an `enum` input type (a string restricted to a list of choices). |
| D5 | Execution | Time-based: state machines and equations run periodically at their band rates, so values settle over time. There is no "run until settled" step. |
| D6 | Run modes | **As fast as possible** (back end only, no front end, for testing), and **real time**: each band runs at its frequency in real time, as close as a non-real-time OS allows. The engine itself stays free of wall-clock time; the server paces the ticks. |
| D7 | Momentary buttons | A press must be detectable by slow-band logic: see D23. |
| D8 | StateButtons | Some buttons light up according to a logic variable. |
| D9 | Priority | Every state machine and equation has an order number. Global transitions get lower numbers when they must win. No implicit precedence. |
| D10 | Rationale and titles | Kept in the state machine files. Their use in the front end is still to be defined; they are not shown on the states themselves. |
| D11 | Equations on screen | Not shown in the first version. They work in the background: some drive state machines, others drive aircraft panel outputs. |
| D12 | Rates on screen | Items run in their bands and use the variable values present when they run. No staleness indicator. |
| D13 | Ordering | The state machine evaluation order and the transition evaluation order within a machine are in the definition files. |
| D14 | Aircraft panels | In scope. Aircraft panels will be defined (replacing the previous tool's FMA strip). |
| D15 | Testing | The front end and the back end are both tested. |
| D16 | System log panel | Dropped from the screen (from the previous spec). The engine trace still exists. |
| D17 | `var` type | Dropped. Logic never writes inputs; equation and transition results take that role. |
| D18 | Condition display | No equations or conditions on screen, so no green/red colouring of rows or terms. |
| D19 | Machine layout order | State machines appear on screen in the order of their rows in the master CSV. |
| D20 | State order in a machine | Inside a machine's area, states appear in the order they appear in that machine's CSV file. |
| D21 | Transitions on screen | Nothing about transitions is shown. The current state is strongly highlighted. Hovering the mouse over the active state highlights its possible next states. |
| D22 | Inputs CSV columns | Optional columns `group, widget, label, min, max, step, choices, lit_by, wide`; files without them still load (details in the UI spec, section 4). |
| D23 | Push-button pulse | A press holds the input true for one period of the slowest band, then false. |
| D24 | Run controls | Real time or as fast as possible, Pause/Resume, Step (only while paused), Reset (keeps the model, run mode and pause state). In real time, a backlog longer than 0.5 s is dropped rather than caught up. |
| D25 | Global targets on hover | Highlighted, with a dashed orange border. |
| D26 | Screen updates | Sent after ticks, at most 30 per second. |
| D27 | Loading | Model path on the command line: `python -m statesim_server MASTER_CSV`. Reset restores start values without reloading files. |
| D28 | Clients | Designed for one browser tab. Several tabs share the same session and all see the same values. |
| D30 | Machine display names | The master CSV has an optional `name` column; a state machine card is titled with it, or with the file name when empty. The state variable in equations is still the file name (e.g. `state_ac`). |
| D31 | Rationale and titles | Not used by the front end for now (see D10). |
| D32 | Load errors | Unchanged for now: the first load error stops loading. |
| D33 | Divider position | The page remembers the divider position (in the browser's local storage) and restores it when opened again. |
| D29 | Front end tests | Unit tests of the session, server tests over real HTTP and WebSocket connections, and browser tests with Playwright (skipped when Playwright or Chromium is missing). |

## Open

| # | Topic | Question |
|---|---|---|
| O5 | Aircraft panel definition | **Next feature.** File format, widgets (annunciators, lit buttons, text displays), layout, which variables drive them. |
| O8b | Reloading | Reload edited CSV files without restarting the server. Postponed. |

