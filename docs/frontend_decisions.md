# Front end: decisions and open points

Working notes for writing the front end requirements. Sources:
`docs/StateSim_FrontEnd_Spec.md` (the front end of a **previous** tool: a
JavaScript, event-driven engine in one HTML page, used only as a source of UI
ideas), `requirements_simulation_framework_spec.yaml`, and design discussions.
No front end code is written until the requirements are agreed.

## Decided

| # | Topic | Decision |
|---|---|---|
| D1 | Architecture | A local Python server runs the `statesim` engine and serves a web front end (HTML/CSS/JavaScript) over WebSockets. The engine exists only in Python; there is no JavaScript engine and no in-browser Python. |
| D2 | Model files | CSV only. No system JSON file. |
| D3 | UI details of inputs | Widget type, min, max, step, choices, grouping and similar live in the inputs CSV file. |
| D4 | Enum type | Add an `enum` input type (a string restricted to a list of choices). |
| D5 | Execution | Time-based: state machines and equations run periodically at their band rates, so values settle over time. There is no "run until settled" step. |
| D6 | Run modes | **As fast as possible** (back end only, no front end, for testing), and **real time**: each band runs at its frequency in real time, as close as a non-real-time OS allows. The engine itself stays free of wall-clock time; the server paces the ticks. |
| D7 | Momentary buttons | A press must be detectable by slow-band logic. Leaning towards a pulse with a minimum duration; buffering is the alternative. To be settled. |
| D8 | StateButtons | Some buttons light up according to a logic variable. |
| D9 | Priority | Every state machine and equation has an order number. Global transitions get lower numbers when they must win. No implicit precedence. |
| D10 | Rationale and titles | Kept in the state machine files. Their use in the front end is still to be defined; they are not shown on the states themselves. |
| D11 | Equations on screen | Not shown in the first version. They work in the background: some drive state machines, others drive aircraft panel outputs. |
| D12 | Rates on screen | Items run in their bands and use the variable values present when they run. No staleness indicator. |
| D13 | Ordering | The state machine evaluation order and the transition evaluation order within a machine are in the definition files. |
| D14 | Aircraft panels | In scope. Aircraft panels will be defined (replacing the previous tool's FMA strip). |
| D15 | Testing | The front end and the back end are both tested. |
| D16 | System log panel | Dropped from the screen (from the previous spec). The engine trace still exists. |

## Open

| # | Topic | Question |
|---|---|---|
| O1 | Button pulse | Pulse duration rule (fixed ms, the slowest band period reading the input, or per button), or buffering until read. |
| O2 | `var` type | The previous tool had hidden variables written by the logic. Here logic never writes inputs; equation and transition results take that role. Drop `var`? |
| O3 | Condition colouring | Colour each transition row green or red only, or also each part inside a row expression (needs a new engine feature)? |
| O4 | State display order | Order of the state boxes inside a machine card (a new column, or first appearance in the file). |
| O5 | Aircraft panel definition | File format, widgets (annunciators, lit buttons, text displays), layout, which variables drive them. |
| O6 | Inputs CSV columns | Exact new columns for D3 and D4. |
| O7 | Real-time pacing | Overrun behaviour (a tick takes longer than its period), and pause, step and speed controls. |
| O8 | Loading and reset | Model path on the command line or chosen in the page; reset to defaults without reloading; reload edited files. |
| O9 | Error reporting | Report every load error at once instead of the first. |
| O10 | Clients | One browser client, or several at once. |
| O11 | Front end test approach | Browser tests (e.g. Playwright) and server API tests. |
