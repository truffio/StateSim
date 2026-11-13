# StateSim user interface spec

Version: 6, 2026-11-12. Status: sections 1-10 implemented (`src/statesim_server/`),
section 11 specified; requirements REQ-114 to REQ-147, REQ-159 and REQ-176 to
REQ-188 in `docs/requirements.csv`.

This spec defines the screen of the StateSim front end: what is on it, what
can be clicked, what each control does, and which colours change and why.
The decisions behind it (D1, D19, ...) are in `docs/decisions.md` Part D.

The front end is a web page served by the local Python server, which runs the
engine (D1). The page shows the engine's current values and sends user
actions to it. It never evaluates logic itself.

## 1. Screen layout

```
+------------------------------------------------------------------------+
|          [ AIRCRAFT PANEL(S), full width, always shown ]               |
+---------------------------+-+------------------------------------------+
|                           |#| +--------+ +--------+ +--------+ +------+ |
|                           |#| | AP     | | FD     | | AT     | | ...  | |
| +-----------+ +---------+ |#| | [ ][#] | | [#][ ] | | [ ][ ] | |      | |
| | INPUT     | | INPUT   | |#| | [ ][ ] | +--------+ | [#][ ] | +------+ |
| | CARD      | | CARD    | |#| +--------+            +--------+          |
| +-----------+ +---------+ |#| +--------+ +--------+ ...                 |
| +-----------------------+ |#| | ...    | | ...    |                     |
| | INPUT CARD (wide)     | |#| +--------+ +--------+                     |
| +-----------------------+ |#|                                          |
|                           |#|                                          |
| [Real time|Fast] [Pause] [Step] [Reset] [Timeline]                     |
+---------------------------+-+------------------------------------------+
   left pane               splitter        right pane
+========================================================================+  <- splitter
| Inputs | . .   .     .                                                 |
| Lock   | [Locked  ][Unlocked    ]|                                     |
| Alarm  | [Off][Armed     ][Off  ]|                                     |
|        +---- time axis (s) ------------------- cursor ----[Live]----+  |
+------------------------------------------------------------------------+
   optional Timeline pane (section 11), hidden by default
```

- A **top pane** spans the full window width and holds the aircraft panels
  (section 3). It is always shown when the model has panels.
- Below it, the screen is split into a **left pane** and a **right pane**,
  separated by a vertical **splitter** (`#` above). Together they fill the
  rest of the browser window.
- **Left pane**, top to bottom: input cards (section 4), run controls
  (section 6).
- **Right pane:** the state machine grid (section 5), and nothing else.
- An optional **Timeline pane** (section 11) spans the full width below the
  left and right panes. It is hidden by default.
- Each pane scrolls vertically on its own when its content is taller than the
  window. The page never scrolls horizontally.

### 1.1 Splitter

| Property | Behaviour |
|---|---|
| Look | 8 px vertical bar in the page background colour, with a thin border on each side and a small grip mark at mid-height. |
| Pointer | The cursor shows a left-right resize arrow over the bar. |
| Drag | Pressing and dragging the bar moves it with the pointer, resizing both panes live. Text is not selected while dragging. |
| Keyboard | The bar can take keyboard focus (Tab). Left and right arrows move it by 20 px. |
| Highlight | The bar takes a light blue tint while hovered, focused or dragged. |
| Limits | Left pane at least 280 px; right pane at least 240 px. When the window is resized, the split is clamped to these limits. |
| Default and memory | The position is remembered in the browser and restored when the page is opened again (clamped to the limits). Without a remembered position, the left pane is 440 px wide. |

Content reflows when the split moves: input cards rearrange their columns,
and the state machine grid gains or loses columns. Nothing is clipped.

## 2. What is not on the screen

Not shown anywhere: a title or the model file name, simulation time or tick,
band rates, equations, conditions, transition rows or cards, rationale,
transition titles, a log panel, headings over the panes or the grid, and
explanatory captions.

## 3. Aircraft panels

An aircraft panel is an HTML file, listed in the master CSV with type
`panel` (e.g. `fcp.html,panel,,,Flight control panel`). Its author controls
the look entirely with HTML and CSS; StateSim provides the behaviour.

### 3.1 Placement

- Panels are shown in the **top pane**, full window width, above the left and
  right panes, side by side on **one row** in master CSV order (the first on
  the left), centred and top-aligned. The top pane is always shown.
- A panel is shown at its natural size times the `scale` of its master CSV
  row (optional, a positive number, default 1; e.g. `0.5` for half size),
  with its proportions kept. If the row is wider than the window, every panel
  is scaled down by the same factor so they stay on one row, without leaving
  gaps.

### 3.2 What StateSim takes from the file

- The `<style>` elements and the `<body>` content. Page-wide rules in the
  file (e.g. on `body`) have no effect: each panel lives in its own isolated
  part of the page (a shadow root), so its CSS cannot change the rest of the
  screen and the screen's CSS cannot change the panel.
- Scripts, external stylesheets, frames and inline event handlers (`onclick`
  and the like) are removed and never run.

### 3.3 Bindings

| Attribute | On | Effect |
|---|---|---|
| `data-input="var"` | a button | Writes the input `var`. A `momentary` input gets a pulse per press (like a momentary push-button); a `toggle` input flips between true and false on each press. The button gets class `pressed` for 0.3 s after each press (the panel's CSS can style it). Keyboard: Enter or Space. |
| `data-input="var"` | any element (e.g. a round `div`) whose input is a `knob` | Becomes a knob: it turns over 270° (min at 7:30, max at 4:30), with a pointer mark. Press on the knob and drag: the mark follows the pointer's angle around the knob (the pointer may leave the knob), so one sweep covers the full range; in the bottom gap between the end stops it stays at the nearer end. Also the mouse wheel (Shift: 10 steps) and the keyboard (arrows: 1 step, Page Up/Down: 10 steps, Home/End: min/max). It stops at min and max (no wrap) and sends whole steps. |
| `data-show="var"` | any element | Its text is the current value of `var` (an input, result variable or state), formatted with `data-format`: printf-like, e.g. `%d`, `%03d` (`090`), `%+05d` (`+0500`, `-0500`), `%.2f`, `%s`. |
| `data-lit-by="var"` | any element | Has class `lit` while `var` is true (the panel's CSS draws the light). Lights follow the logic, never the click. |

### 3.4 Panel inputs in the inputs CSV

- Every input driven by a panel has the panel file name in the `panel`
  column. It gets no input card on the left.
- Its `widget` is `momentary` or `toggle` (bool) or `knob` (int or float,
  with min and max; `step` is the knob step).
- At load, StateSim checks that every bound variable exists, that each
  `data-input` names an input whose `panel` is this file, that every input
  with a `panel` is used by that panel, and that the panel is listed in the
  master CSV. Errors give the `file:line`.

### 3.5 Aircraft types

The panels of an aircraft type (its FCP and FMA) are kept together and chosen
by the master CSV, so models of the same aircraft share them:

- A type is a folder `aircraft/<TYPE>/` with its panel HTML files and an
  `aircraft.csv` listing them, with the columns of a master panel row:
  `file_name,type,name,scale,role` (`type` = `panel`).
- The master CSV picks the type with one row: `A220,aircraft,,,,,`. Its panels
  are loaded as if they were master panel rows, in the order of
  `aircraft.csv`. Explicit `panel` rows can be added for a model's own
  panels; only one panel may have role `fma`.
- The folder is looked up next to the master CSV first, then in the package
  (`src/statesim/aircraft/`). Built in: **A220** (`fcp.html`, `fma.html`).
- An undefined type is a load error that names the defined ones. To add a
  type such as the **A320** (not defined yet): create `aircraft/A320/` with
  its panel files and `aircraft.csv`, bind the panels to the model's inputs
  and FMA equations, and set the master row to `A320,aircraft,,,,,`.
- Panel inputs still name the panel file in the inputs CSV `panel` column
  (`fcp.html`).

## 4. Input cards

Input cards let the user write the engine's external inputs. They are
generated from the inputs CSV; no screen layout is coded per model.

### 4.1 Cards

- One card per input group (D3). The card title is the group name in blue
  bold upper case with wide letter spacing.
- Inputs appear in the card in the order of the inputs CSV.
- A card is white, with a light grey border and rounded corners.
- Cards flow in a grid that fills the left pane width, left to right then
  down, as many columns as fit with each column at least 170 px. A card is
  full pane width when any of its inputs has `wide` true or is a slider;
  otherwise one column wide.
- Cards and titles are not clickable.

### 4.2 Inputs CSV columns

`variable_name, type, default_value` are required. The display columns are
optional; a file without them still loads.

| Column | Meaning | Default |
|---|---|---|
| `type` | `bool`, `int`, `float`, `str` or `enum` | (required) |
| `group` | Card the input appears in | `Inputs` |
| `widget` | Control, see the table below | by type: `switch` for bool, `slider` for int/float with min and max (else `number`), `dropdown` for enum, `text` for str |
| `label` | Text shown on the control | the variable name |
| `min`, `max`, `step` | Range of an int or float (a slider needs min and max) | step 1 for int, 1/100 of the range for float |
| `choices` | Enum values separated by `\|` (e.g. `NONE\|APPR1\|LAND3`); the default must be one of them | (required for enum) |
| `lit_by` | Variable that lights a `lit` push-button (an input or result variable) | (required for `lit`) |
| `wide` | `true` makes the input's card full width | `false` |
| `panel` | Panel file that drives the input (no card; see section 3.4) | (none) |

Widgets allowed per type: bool `switch`, `momentary`, `lit`, `toggle`
(panel only); int and float `slider`, `number`, `knob` (panel only); enum
`dropdown`; str `text`. Any type may use `none`: an internal variable that
actions write, with no control and no card. Anything else, a default
outside min/max, or a column that does not apply to the type is a load error
with its `file:line`.

### 4.3 Controls

Every control shows the **engine's current value** of its input. The value
changes when the user operates the control, when an action writes the input
(`docs/decisions.md` Part C), or when the engine's inputs are reset
(section 6). The last writer wins.

| Control | Input type | Look | Clickable | What it does | What changes colour |
|---|---|---|---|---|---|
| **Momentary push-button** (`momentary`) | bool | Full card width, light grey fill, dark 2 px outline, dark bold upper-case label | Yes | A press sends a pulse: the input is true for one period of the slowest band, then false. | Press feedback only (below). |
| **Lit push-button** (`lit`) | bool | Full card width, bold upper-case label | Yes | A press sends the same pulse as a momentary push-button. | The background follows a **linked logic variable**, not the click: green with white text when the variable is true; white with dark border and dark text when false. A press the logic rejects leaves it unlit. |
| **Slider** (`slider`) | int, float | Input name on the left and its value on the right in blue monospace, slider below across the card | Yes (drag the knob or click the track) | Writes the value while it moves, within the min, max and step of the definition. The value readout follows. | Nothing. |
| **Switch** (`switch`) | bool | Input name on the left, two-state sliding switch on the right | Yes (switch or name) | Each click toggles the input between true and false. | On: blue track, knob on the right. Off: grey track, knob on the left. |
| **Drop-down** (`dropdown`) | enum | Input name on the left, drop-down list on the right | Yes | Writes the chosen value (D4). | Nothing. |
| **Number field** (`number`) | int, float | Input name on the left, number box on the right | Yes | Writes the typed value when it is confirmed (Enter or leaving the field). | Nothing. |
| **Text field** (`text`) | str | Input name on the left, text box on the right | Yes | Writes the text when it is confirmed. | Nothing. |

- **Press feedback** (both push-button kinds): while the pointer holds the
  button down it turns light blue with a blue outline and moves down by 1 px;
  after each click (mouse or keyboard) it stays light blue for 0.3 s, then
  fades back. A lit push-button that is lit stays green.
- All controls can be reached and used with the keyboard: Tab to focus;
  Enter or Space presses a push-button or toggles a switch; arrow keys move a
  slider by one step or change the drop-down choice.
- A focused control shows a visible focus ring.
- Labels show the input name or label as written in the inputs CSV.
- The server checks every value it receives (type, min/max, choices) and
  ignores a value that does not fit; the page then shows the engine's value
  again.

## 5. State machine grid

### 5.1 Machine cards

- One card per state machine, in the order of the master CSV rows (D19),
  placed left to right then top to bottom.
- Cards are 200 px wide; the grid shows as many columns as fit the right pane
  and as many rows as needed.
- A card is white with a light grey border and rounded corners. It shows the
  machine's display name in blue bold, then its state boxes. Nothing else.
  The display name is the master CSV `name` column; when it is empty, the
  file name without `.csv` is shown.
- The card and its name are not clickable.

### 5.2 State boxes

- One box per state, in the order the states appear in the machine's CSV file
  (D20), in two columns.
- Each box is at least 34 px high. The state name is centred horizontally and
  vertically and wraps inside the box when too long; as a last resort the font
  is reduced to fit.
- Every box has a 2 px border at all times, so no colour change ever moves or
  resizes anything on the screen.

| Box | Look | Meaning |
|---|---|---|
| Inactive | Light grey fill, grey border, grey text | A state the machine is not in. |
| **Active** | Solid blue fill and border, white bold text | The machine's current state. Exactly one per machine. |
| Next (hover) | Light blue fill, blue border, dark blue text | A state reachable from the active state by one of its own transitions (current_state = the active state). Targets of global transitions are not shown: their conditions often limit the states they can fire from. Shown only while the active state is hovered or focused. |

### 5.3 Interaction

| Action | Result |
|---|---|
| Hover over an inactive state | Nothing. No outline, colour or cursor change. |
| Hover over the active state, or focus it with Tab | Every next state of that machine takes its "Next" look. The active box keeps its look. A transition to the active state itself highlights nothing. |
| Pointer leaves, or focus leaves, the active state | All "Next" looks are removed. |
| Click on any state | Nothing. States cannot be set from the screen. |
| The active state changes while it is hovered | The highlight is removed; it is shown again for the new active state when the pointer moves onto it. |

The active state box is the only focusable element of a machine card. The
cursor stays the normal arrow over all state boxes.

## 6. Run controls

A row of controls at the bottom of the left pane, left aligned. When the left
pane has spare height, the row sits at its bottom edge; otherwise it follows
the last input card.

| Control | Look | What it does | What changes |
|---|---|---|---|
| **Run mode** | Two joined buttons, "Real time" and "As fast as possible" | Selects how fast the engine runs (D6). Exactly one is selected. | The selected one is solid blue with white text; the other is white with dark text. |
| **Pause** | White button, grey border | Stops the engine; it keeps all values. | The label changes to **Resume** while paused; Resume restarts it. |
| **Step** | White button, grey border | While paused, runs the engine for one tick. | Disabled (greyed) while running. |
| **Reset** | White button, grey border | Returns every input, state and result to its start value, keeping the loaded model and the run mode. | Nothing. |
| **Timeline** | White button, grey border | Shows or hides the Timeline pane (section 11). | Pressed look (light blue fill, as a pressed push-button) while the pane is shown. |

In real time the server runs the ticks at the model's tick rate against the
wall clock. If it falls more than 0.5 s behind, it drops the backlog instead
of catching up.

## 7. Colours

| Token | Value | Used for |
|---|---|---|
| Blue | #005c99 | Card and machine titles, values, active state, selected run mode, switch on |
| Dark blue | #003d66 | Text of a next state and of a pressed push-button |
| Light blue | #dcf0fa | Fill of a next state and of a pressed push-button, splitter highlight |
| Green / dark green | #00a37d / #007a5e | Lit push-button fill / border |
| Grey track | #b9c1cc | Switch off |
| Page background | #eef1f5 | Page and splitter |
| Light grey | #f6f8fa | Inactive state, momentary push-button |
| Card | #ffffff | Input and machine cards, buttons |
| Ink / muted | #1c2430 / #4a5565 | Text / inactive state text |
| Lines | #d9dee5, #c3cad4 | Card and state borders, button borders |

Font: Inter (falls back to the system sans-serif); values in JetBrains Mono.

## 8. General rules

- All names shown come from the CSV files and are shown as text, never
  interpreted as HTML.
- The screen layout is built once when the model is loaded; while running,
  only values, lit states, active states and highlights change.
- The server sends screen updates after ticks, at most 30 per second.
- If the connection to the server is lost, a dark message at the bottom of
  the screen says so and the page reconnects every second; it disappears once
  connected again.

## 9. Starting the front end

```
pip install -e ".[server]"
python -m statesim_server examples/autopilot2/master.csv
```

The server listens on `http://127.0.0.1:8765/` and opens the browser. Options:
`--port N` (0 = any free port), `--host`, `--no-browser`, `--trace FILE`
(writes the engine trace).

## 10. Open points for this spec

| # | Point |
|---|---|
| O5b | Aircraft panels: light equations for the other FCP buttons. |
| O8b | Reloading edited CSV files without restarting the server. |

## 11. Timeline pane

An optional pane showing the current session as lanes over time, with the
causes of each transition and a sequence chart. Requirements REQ-176 to
REQ-188; the design is in `docs/future_timeline.md`.

### 11.1 Pane and splitter

| Property | Behaviour |
|---|---|
| Place | At the bottom of the page, full width, below the left and right panes. |
| Default | Hidden. |
| Show / hide | The **Timeline** button in the run bar (section 6). It looks pressed while the pane is shown. Showing or hiding changes nothing else on the page. |
| Splitter | A horizontal bar on top of the pane, like the vertical one in section 1.1. Drag it, or focus it and press ArrowUp / ArrowDown to move it by 20 px. |
| Height | Default 260 px; at least 120 px; at most 70% of the window. |
| Memory | Visibility and height are remembered in the browser. |

### 11.2 Lanes

- A 140 px label column on the left.
- First row **Inputs**, then one lane per state machine in master order,
  labelled with its display name.
- Each state is a bar from when it was entered to when it was left (or to
  now).
- A state's colour is fixed by its position in the machine's file, from a
  palette of 8 muted colours, so it never changes during the session.
- The state name is drawn in the bar when it fits.

### 11.3 Transitions and inputs

| Item | Drawn as | Label | Hover |
|---|---|---|---|
| Transition | Vertical tick at the boundary between two state bars | Transition id | Title and "from -> to" |
| Input change | Dot in the Inputs row | Input name | name = value |

Inputs set to the value they already have are not shown.

### 11.4 Time axis

- At the bottom, in seconds.
- The view shows the last 30 s and follows the run, with a cursor line at the
  current time.
- Scrolling back (wheel or drag) stops following.
- A **Live** button, shown only while not following, resumes following.

### 11.5 Cause lines

- Hovering or selecting a transition draws dashed lines to each of its
  causes: an input dot or another machine's transition.
- Equations are never shown; their effect is folded into the links.

### 11.6 Sequence chart

- Clicking a transition or an input dot opens a chart below the lanes,
  inside the pane.
- Lifelines: Inputs, plus each state machine involved.
- It shows the clicked item and everything it caused, in time order:
  - an arrow from each cause's lifeline to the machine, labelled with the
    transition id (title on hover);
  - each action write as an arrow back to Inputs, labelled `var = value`.
- A close button and the Escape key close it.

### 11.7 Reset and data source

- Reset clears the lanes and the chart.
- The data is the current session only, the same whether it is driven by
  hand or by a test.

### 11.8 Save as text

- While the pane is shown, a **Save as text** button sits in the run bar
  next to the Timeline button. It downloads `statesim-timeline.txt`: the
  current run as plain text, also served at `/timeline.txt`.
- The file is a reconstruction of the run in time order. Each entry starts
  with its number (`#12`) and time in seconds:
  - an input change: `INPUT  name = value`;
  - a transition: machine (display name and file name), transition id,
    `from -> to` and title, then `caused by:` the numbered input changes and
    transitions that led to it (through any equations), or `no recorded
    cause`, then `writes:` its action writes.
  - a display change: a result variable shown on a panel (lit by
    `data-lit-by` or shown by `data-show`), such as an FMA mode text, as
    `DISPLAY  <panel>: <text lit> (<variable>) on` or `off`, then what caused
    it. Inputs and states shown on panels are already listed as input changes
    and transitions. The pane does not draw display changes.
- It holds the same items as the pane (the most recent 20,000), and says so
  when older ones have been dropped.

```
#1     0.100 s  INPUT  TOGA = True
#2     0.200 s  Aircraft (state_ac)  T1  Waiting TOGA -> Takeoff  "Ac accelerating to VR"
                caused by: #1 input TOGA = True
#3     0.200 s  FD engage (state_fd)  T3  FD-disengaged -> FD-engaged  "Automatic engaging of FD"
                caused by: #1 input TOGA = True
                writes: fd_on = True
#7     0.200 s  DISPLAY  Flight mode annunciator: AT (fma_at_color_white) on
                caused by: #6 Autothrottle T1 -> Hold armed
```

## 12. FMA recording

A report of how the FMA changed during a manoeuvre, and which crew input
caused each change. Recording only marks a window: the trace and the
timeline keep running all the time.

### 12.1 Buttons

- The master CSV marks the FMA panel with `role` = `fma` on its panel row (at
  most one panel). Only then does the run bar show **Start recording**. While
  recording it shows **Stop recording** (red, with a dot) and a clock with
  the recording's simulation time (`REC 4.2 s`).
- **Reset** while recording ends the recording, like Stop.

### 12.2 Rows

- The first row is the FMA at Start, captioned "Start of the manoeuvre". A
  blank FMA is not drawn: the row is then only its caption and time.
- Then one row per input that changed the FMA. All FMA changes between one
  input and the next are merged, and the row shows the settled result.
  Inputs that change nothing on the FMA are not shown.
- The caption is the input that caused the change, found by following the
  recorded causes back to it, in plain English: `<description> pressed` for
  a push-button, `<description> on/off` for a switch, `<description> set to
  <value> <unit>` otherwise. The inputs CSV columns `description` and `unit`
  give the words; without them the input's label or name is used.
- If the FMA did not change, the report says "no FMA change during the
  recording".

### 12.3 Compact layout

- A header: title, then the model, date, recording window, number of FMA
  changes and the layout name.
- A vertical list. Each row has a number badge, its caption and time, then
  the FMA, drawn from the FMA panel's own HTML and CSS with the lights of
  that moment. Each row is indented one step (28 px) more than the one
  before, with a thin connector, so the list reads down and to the right.
- Other layouts may be added later; compact is the first and the default.

### 12.4 Preview and Save PNG

Stop opens the report in a new window as an editable preview:

| Item | What can be done |
|---|---|
| Title | Click to edit. Starts as "FMA recording"; the last title is remembered in the browser. |
| Description | An optional line under the title; left out of the image when empty. |
| Caption | Click to edit. A rewrite replaces the recorded text. |
| Note | **+ Note** adds an editable line under the caption; **− Note** removes it. |
| Times | **Show times** shows or hides every row's time. |
| Order | Drag a row by its handle (⠇). The numbers follow the new order; moved rows are not flagged. |
| Hide | **Hide** leaves a row out of the image (shown faded in the preview); **Show** puts it back. |
| Indent | ◀ ▶ move one row by a step; **Indent step** sets the step for all rows. |
| Undo / Reset | **Undo** reverts the last change; **Reset to recording** restores the original report. |

The FMA snapshots themselves cannot be edited. **Save PNG** saves the preview
as shown, without the controls or hidden rows, at twice the screen
resolution, named `<title> - <date> <time>.png`. If the browser blocks the
window, a message asks to allow pop-ups and press Stop again.
