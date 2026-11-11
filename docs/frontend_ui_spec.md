# StateSim user interface spec

Version: draft 1, 2026-11-11. Status: for review; nothing is implemented yet.

This spec defines the screen of the StateSim front end: what is on it, what
can be clicked, what each control does, and which colours change and why.
Decisions and open points behind it are in `docs/frontend_decisions.md`. A
mockup is in `docs/mockups/frontend_mockup.html` (example data only).

The front end is a web page served by the local Python server, which runs the
engine (D1). The page shows the engine's current values and sends user
actions to it. It never evaluates logic itself.

## 1. Screen layout

```
+---------------------------+-+------------------------------------------+
| Aircraft panels           |#| +--------+ +--------+ +--------+ +------+ |
|                           |#| | AP     | | FD     | | AT     | | ...  | |
| +-----------+ +---------+ |#| | [ ][#] | | [#][ ] | | [ ][ ] | |      | |
| | INPUT     | | INPUT   | |#| | [ ][ ] | +--------+ | [#][ ] | +------+ |
| | CARD      | | CARD    | |#| +--------+            +--------+          |
| +-----------+ +---------+ |#| +--------+ +--------+ ...                 |
| +-----------------------+ |#| | ...    | | ...    |                     |
| | INPUT CARD (wide)     | |#| +--------+ +--------+                     |
| +-----------------------+ |#|                                          |
|                           |#|                                          |
| [Real time|Fast] [Pause] [Step] [Reset]                                |
+---------------------------+-+------------------------------------------+
   left pane               splitter        right pane
```

- The screen is split into a **left pane** and a **right pane**, separated by
  a vertical **splitter** (`#` above). Together they fill the browser window.
- **Left pane**, top to bottom: aircraft panels (section 3), input cards
  (section 4), run controls (section 6).
- **Right pane:** the state machine grid (section 5), and nothing else.
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
| Default | Left pane 440 px wide. |

Content reflows when the split moves: input cards rearrange their columns,
and the state machine grid gains or loses columns. Nothing is clipped.

## 2. What is not on the screen

Not shown anywhere: a title or the model file name, simulation time or tick,
band rates, equations, conditions, transition rows or cards, rationale,
transition titles, a log panel, headings over the panes or the grid, and
explanatory captions.

## 3. Aircraft panels

Aircraft panels are shown at the **top of the left pane**, above the input
cards. They display results of the logic in a cockpit-like form. Their
content, look and definition are to be specified separately (O5); each panel
will have a defined width and height.

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
  either one column wide or the full pane width (how this is declared is open,
  O6).
- Cards and titles are not clickable.

### 4.2 Controls

Every control shows the **engine's current value** of its input. The value
changes only when the user operates the control, or when the engine's inputs
are reset (section 6). The logic never writes inputs.

| Control | Input type | Look | Clickable | What it does | What changes colour |
|---|---|---|---|---|---|
| **Momentary push-button** | bool | Full card width, solid red, white bold upper-case label | Yes | A press sends a pulse: the input becomes true, then false after the pulse duration (O1). | Nothing. Its colour is fixed. |
| **Lit push-button** | bool | Full card width, bold upper-case label | Yes | A press sends the same pulse as a momentary push-button. | The background follows a **linked logic variable**, not the click: green with white text when the variable is true; white with dark border and dark text when false. A press the logic rejects leaves it unlit. |
| **Slider** | int, float | Input name on the left and its value on the right in blue monospace, slider below across the card | Yes (drag the knob or click the track) | Writes the value while it moves, within the min, max and step of the definition. The value readout follows. | Nothing. |
| **Switch** | bool | Input name on the left, two-state sliding switch on the right | Yes (switch or name) | Each click toggles the input between true and false. | On: blue track, knob on the right. Off: grey track, knob on the left. |
| **Drop-down** | enum | Input name on the left, drop-down list on the right | Yes | Writes the chosen value (D4). | Nothing. |

- All controls can be reached and used with the keyboard: Tab to focus;
  Enter or Space presses a push-button or toggles a switch; arrow keys move a
  slider by one step or change the drop-down choice.
- A focused control shows a visible focus ring.
- Labels show the input name or label as written in the inputs CSV.

## 5. State machine grid

### 5.1 Machine cards

- One card per state machine, in the order of the master CSV rows (D19),
  placed left to right then top to bottom.
- Cards are 200 px wide; the grid shows as many columns as fit the right pane
  and as many rows as needed.
- A card is white with a light grey border and rounded corners. It shows the
  machine name in blue bold, then its state boxes. Nothing else.
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
| Next (hover) | Light blue fill, blue border, dark blue text | A state reachable from the active state by one of its transitions. Shown only while the active state is hovered or focused. |
| Next, global (hover) | Light orange fill, dashed orange border, dark orange text | A target of a global transition. Shown only while the active state is hovered or focused, if global targets are included (O12). |

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

The labels, the paused state and the exact effect of each control are still
open (O7) and are to be confirmed.

## 7. Colours

| Token | Value | Used for |
|---|---|---|
| Blue | #005c99 | Card and machine titles, values, active state, selected run mode, switch on |
| Dark blue | #003d66 | Text of a next state |
| Light blue | #dcf0fa | Fill of a next state, splitter highlight |
| Green / dark green | #00a37d / #007a5e | Lit push-button fill / border |
| Red | #c62a3a | Momentary push-button |
| Orange / light orange / dark orange | #b35c00 / #fff1de / #6b3600 | Global next state border / fill / text |
| Grey track | #b9c1cc | Switch off |
| Page background | #eef1f5 | Page and splitter |
| Card | #ffffff | Input and machine cards, buttons |
| Ink / muted | #1c2430 / #4a5565 | Text / inactive state text |
| Lines | #d9dee5, #c3cad4 | Card and state borders, button borders |

Font: Inter (falls back to the system sans-serif); values in JetBrains Mono.

## 8. General rules

- All names shown come from the CSV files and are shown as text, never
  interpreted as HTML.
- The screen layout is built once when the model is loaded; while running,
  only values, lit states, active states and highlights change.

## 9. Open points for this spec

| # | Point |
|---|---|
| O1 | Pulse duration of push-buttons. |
| O5 | Aircraft panels: definition, content, size and placement. |
| O6 | Inputs CSV columns: group, widget type, label, min, max, step, choices, linked variable of a lit push-button, card width. |
| O7 | Run controls: whether "As fast as possible" belongs on the screen (it was described as a back-end-only mode), labels, Pause and Step behaviour, Reset scope. |
| O12 | Whether the targets of global transitions are highlighted as next states. |
| O13 | How often the screen updates while running (every tick, or capped at the display refresh rate). |
| O14 | Whether the splitter position is remembered between sessions. |
