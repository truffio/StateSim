# StateSim — Front End Spec

Version: 2026-11-11 · Author: Martin

## How to use this document

This is a description of the front end of an **existing** tool, StateSim. It is written as input for designing a **new**, different tool. Read it as a source of proven UI ideas, not as requirements to copy one to one.

- Sections "Overview" to "Visual design" describe how the existing front end looks and behaves.
- The section "Carry forward to the new tool" lists the ideas to keep, the decisions already made for the new tool, open questions and known issues not to repeat.
- How states are computed (the engine) is out of scope. The existing engine is event-driven; the new tool will be time-based. Where this document mentions engine behaviour, it only explains what the screen shows.

Glossary:

- **Machine:** one finite state machine. A system file holds several machines that run side by side over shared variables.
- **Transition card:** the on-screen card showing one outgoing transition of a machine and its condition.
- **Global transition:** a transition a machine can take from any state; it overrides the current state's transitions.
- **FMA:** Flight Mode Annunciator, the cockpit display showing active autopilot and autothrottle modes.
- **CLAWS:** the flight control law software that provides guidance laws; its availability flags appear as inputs.
- **StateButton:** a push-button whose lit look shows a linked state variable.

## Overview

StateSim is a single self-contained HTML file. It loads a system JSON file, lets the user drive the system's input variables, and shows each machine's current state, the live truth of every outgoing transition, and (in the older build) a transition log.

- **Delivery:** `StateSim.html`, opened directly from disk. No build step, server, framework or external dependency; vanilla JavaScript and inline CSS.
- **Audience:** engineers reviewing or demonstrating mode logic (e.g. Airbus A220 autoland, autopilot and autothrottle modes), who need to see *why* a transition is or is not armed.
- **Engine contract (existing tool):** every input change runs the engine once, then the screen re-renders from its state.
- **Screen:** a wide desktop browser window. With 7 machines the screen is very wide and the equations area grows down the page.

Two builds exist. The older one is in the repo (`StateSim.html`). A newer "IFCS baseline" build, running `A220_IFCSbaseline.json`, adds an FMA strip, cockpit-style panel cards and lit StateButtons. Where the two builds differ, this spec describes the baseline build.

## Loading a system file

The app opens on a full-screen upload card and switches to the simulator as soon as a valid file is read.

1. **Upload screen:** centred white card with a dashed blue border, heading "Multi-System Simulator", the line "Load your System JSON file", and a "Select JSON File" button (a hidden `<input type=file accept=.json>`).
2. **Read:** the file is read client-side with `FileReader`; nothing leaves the browser.
3. **Parse:** JSON parse. A file with top-level `states` and no `machines` is wrapped as a one-machine system.
4. **On error:** stay on the upload screen and show `Error: <message>` in red under the button. (Recommended: list every validation problem with its machine, state and transition, not just the first.)
5. **On success:** hide the upload screen, show the simulator, set the title to `system_name`, build the controls and machine views, and run the first evaluation.

**Reload:** "Reset System / Load File" under the control cards reloads the page, discarding all state and returning to the upload screen. There is no way to reset to defaults while keeping the loaded file.

## Input file shape (as far as the front end uses it)

```json
{
  "system_name": "Autoland Guidance",
  "variables": [
    {"type": "separator", "title": "Aircraft Controls"},
    {"name": "radio_altitude", "type": "int", "min": 0, "max": 2500, "step": 5, "default": 0},
    {"name": "capa", "type": "enum", "choices": ["NONE", "APPR1", "APPR2", "LAND2", "LAND3"], "default": "LAND3"},
    {"name": "on_ground", "type": "var", "default": true},
    {"type": "separator", "title": "Flight Control Panel"},
    {"name": "AP_btn", "type": "StateButton", "StateVar": "ap_on"},
    {"type": "separator", "title": "Stick Controls"},
    {"name": "TOGA", "type": "button"},
    {"type": "separator", "title": "CLAWS availability"},
    {"name": "law_AP", "type": "bool", "default": true}
  ],
  "machines": [
    {
      "name": "AP engage",
      "initial_state": "AP-disengaged",
      "global_transitions": [],
      "states": {
        "AP-disengaged": {
          "transitions": [
            {
              "event": "(AP_btn == True) and (law_AP == True)",
              "next_state": "AP-engaged"
            }
          ]
        },
        "AP-engaged": {
          "transitions": [
            {
              "event": "(APdisc == True)",
              "next_state": "AP-disengaged",
              "rationale": "Manual disengagement"
            },
            {
              "event": "(law_AP == False)",
              "next_state": "AP-disengaged",
              "rationale": ["Automatic disengagement caused by", "CLAWS not available"]
            }
          ]
        }
      }
    }
  ]
}
```

Conditions (`event`) use a Python-like syntax: `==`, `!=`, `<`, `<=`, `>`, `>=`, `and`, `or`, `True`, `False`, `x in [...]`, `x not in [...]`, parentheses and quoted strings.

## Layout

The left side holds an FMA strip above a two-column grid of control cards. The right side shows every machine side by side, with its transition cards directly underneath.

```
+-------------------------------------+  +------------+ +------------+ +------------+       
| SPD  | FMS1 |  AP  <-  AT  | ALTS   |  | Aircraft   | | FD engage  | | AP engage  |  ...  
+-------------------------------------+  | [ ][ ]     | | [ ][#]     | | [ ][#]     |  (7 machine
+-----------------+ +-----------------+  | [ ][#Cruise] +------------+ +------------+   cards in
| AIRCRAFT        | | FLIGHT CONTROL  |  | [ ][ ] ... |                                the row)
| CONTROLS        | | PANEL           |  +------------+                                        
| ground_speed ---| | [  FD_BTN  ] lit|                                                        
| radio_alt ------| | [  AP_BTN  ] lit|  STATE TRANSITION EQUATIONS                            
| capa   [LAND3 v]| | [  AT_BTN  ] lit|  +------------+ +------------+ +------------+          
+-----------------+ | [ APPR_BTN ]    |  |[GLOBAL]    | |To: FD-     | |To: AP-     |          
+-----------------+ +-----------------+  |To:Touchdown| | disengaged | | disengaged |          
| STICK CONTROLS  | | CLAWS REQUESTS  |  |cond (red/  | |cond ...    | |Rationale:  |          
| [   TOGA    ]   | | dmc_tracking_loc|  | green terms| +------------+ | Manual     |          
| [  APDISC   ]   | | dmc_tracking_gs |  +------------+                +------------+          
| [  ATDISC   ]   | | claws_req_flare |  +------------+                +------------+          
+-----------------+ +-----------------+  |[GLOBAL]    |                |To: AP-     |          
+-----------------+                      |To: APPR    |                | disengaged |          
| CLAWS           |                      |   armed    |                |Rationale:  |          
| AVAILABILITY    |                      +------------+                | CLAWS ...  |          
| law_AP      [x] |                      +------------+                +------------+          
| law_loc     [x] |                      |To: Descent |                                        
| ... 11 laws     |                      +------------+                                        
+-----------------+                                                                            
[        Reset System / Load File        ]                                                     
```

`[#]` marks the highlighted active state. Each equations column sits directly under its machine card.

| Region | Placement | Contents |
| --- | --- | --- |
| FMA strip | Top of the left side, full width of the control grid | Black bar in four columns: thrust mode (SPD), lateral mode (FMS1), AP and AT engage status with an arrow between them, vertical mode (ALTS); green text |
| Control cards | Two equal columns under the FMA, filled left to right then down | One card per separator, its title in blue upper case. Baseline order: Aircraft Controls, Flight Control Panel, Stick Controls, CLAWS requests, CLAWS availability |
| Reset button | Full width under the cards | "Reset System / Load File", dark fill |
| State row | Top of the right side | One card per machine: name in blue, states in a two-column grid. 7 machines in the baseline file: Aircraft, FD engage, AP engage, Vertical Modes, Lateral Modes, Guidance Source, Autothrottle |
| State transition equations | Under the state row, one column per machine, aligned with its card | Header "STATE TRANSITION EQUATIONS", then the machine name and its transition cards |

The older repo build has a different layout: a single 320 px controls column, a "Real-time Logic Analysis" header over the equations, and a 100 px dark system log at the bottom.

**Alignment rule:** each machine card and its equations column share one width, so column *n* of states always sits above column *n* of equations. With 7 machines the columns are narrow, so conditions wrap onto several lines and the equations area grows down the page. Both rows should scroll sideways together when the machines don't fit (today they don't; see Known issues).

## Interactions

In the existing tool, every control writes its variable and immediately triggers one evaluation. There is no Run, Pause or Step button.

### Control cards

Each `separator` entry in `variables` opens a new card titled with its `title`; the variables after it, up to the next separator, go in that card. Cards flow into the two-column grid in file order. (The older build groups by a per-variable `group` field instead, default "General Inputs".)

| Type | Control | Fires on | Value written |
| --- | --- | --- | --- |
| `int` / `float` | Range slider, with name and live value | `input` (while dragging) | Slider value, parsed as int or float |
| `bool` | Checkbox, label clickable | `change` | `checked` |
| `enum` | Select of `choices` | `change` | Selected string |
| `button` | Full-width red button, name in upper case | `mousedown` | `true`, then `false` 200 ms later (two evaluations) |
| `StateButton` | Full-width button, lit or unlit (below) | `mousedown` | Same pulse as `button` |
| `var` | None: internal variable, hidden, takes no space | — | Only written by the logic |

**StateButton:** pulses like `button` when pressed. It is filled green while its `StateVar` is `true` (FD_BTN, AP_BTN, AT_BTN engaged) and outlined with dark text while `false` (APPR_BTN). The lit look follows the logic's result, not the click, so a press the logic rejects leaves the button unlit. The machine decides what a press means, e.g. FD engage leaves `FD-engaged` on `(FD_btn == True) and (ap_on == False)`.

**Grouping by convention in the baseline file:** flight control panel inputs are StateButtons, stick and throttle switches (TOGA, APDISC, ATDISC) are red momentary buttons, CLAWS requests and availability flags are checkboxes.

**Write-back (existing tool only):** when the logic changes a variable that has a control, the control updates to match (slider position and value, checkbox, select). `var` values are not visible anywhere.

### State display

- Each machine's active state box is highlighted (blue outline and tint), and its header shows `[StateName]`.
- Exactly one box per machine is active at any time.
- State boxes appear in the order the states are listed in the file.

### Transition cards

For each machine, the column lists the transitions that can fire from the current state: globals first, tagged **[GLOBAL]** in orange, then the current state's transitions in file order. Each card shows:

1. `To: <next_state>` in bold blue.
2. The condition in monospace. Each term (e.g. `radio_altitude < 2500`) is coloured green if true and red if false, and `and`/`or` are greyed. In the baseline build this includes terms inside `in [...]` lists and terms that wrap across lines.
3. **Rationale:** an underlined label and one line per entry, when the transition has a `rationale` (a string or a list of strings).
4. (Older build) `Sets: <variable names>` when the transition writes variables.

A card whose whole condition is true gets a green left border and tint. A machine with no candidate transitions shows "No active transitions." in grey italics. Several cards may lead to the same target, each with its own rationale (e.g. AP-disengaged by manual disconnect or by CLAWS unavailability).

### FMA strip

After each evaluation the strip shows display outputs computed from the current states and variables (`fma_logic` in the baseline file: per output, an ordered list of `{text, equation}` rules and a default).

| Column | Example | Driven by |
| --- | --- | --- |
| Thrust mode | SPD | `TM_engaged` (HOLD, THRUST, SPD, RETARD); `TM_armed` |
| Lateral mode | FMS1 | `LNAV_engaged_1`; `LNAV_armed_1` (APPR) |
| Engage status | AP <- AT | `ap_visible` shows or hides AP; `at_color` sets AT green, white or hidden (`off`) |
| Vertical mode | ALTS | Vertical-mode outputs |

An empty-string output leaves its slot blank, and `off` or `false` hides the label. Engaged modes are green.

**New tool:** the FMA strip and `fma_logic` are replaced by an aircraft output panel that displays results of boolean equations. That panel, including the AP <- AT arrow, will be defined later.

### System log (older build only)

One line per fired transition: local time, a machine tag and `<from> -> <to>`. It auto-scrolls to the newest line and is never cleared. **New tool:** dropped.

## Visual design

A compact light theme in Segoe UI, dense enough to show several machines with about ten states each on one screen.

| Token | Value | Used for |
| --- | --- | --- |
| `--primary-blue` | #005c99 | Titles, active state, target state, slider values |
| `--active-bg` | #dcf0fa | Active state fill |
| `--bg-color` | #f0f2f5 | Page background |
| `--success-color` | #00b894 | True terms, firing card border, lit StateButton |
| `--fail-color` | #ff4757 | False terms, errors, momentary button fill |
| `--machine-border` | #e1e4e8 | Machine card border |
| (inline) | #e67e22 | [GLOBAL] tag |

| Element | Look |
| --- | --- |
| FMA strip | Black background, rounded corners, thin dividers between columns, bold green labels |
| StateButton lit | Solid green fill, white bold label |
| StateButton unlit | White fill, dark 2 px border, dark bold label |
| Momentary button | Solid red fill, white bold upper-case label |
| Control card | White card, light shadow, blue upper-case title with letter spacing |
| Machine card | Light grey card, blue name, states in a two-column grid; active state blue-outlined and tinted |
| Transition card | 11 px text, 3 px left border (green when its condition is true), monospace condition |

Rendering rules:

- Any text from the JSON (names, states, conditions, rationale) must be HTML-escaped.
- State names may contain spaces ("Waiting TOGA", "Final Approach") and must render and highlight correctly.
- Build controls and state grids once at load; on each evaluation re-render only transition cards, highlights and outputs.

## Carry forward to the new tool

The existing front end has several ideas worth keeping. The new tool's engine is time-based and its machines only set their own state, which removes a few features.

### Ideas worth reusing

- **Fully data-driven UI:** controls, state grids and transition cards are all generated from one JSON file, with no per-system code.
- **Type-to-widget mapping:** slider for `int`/`float`, checkbox for `bool`, select for `enum`, momentary button, and StateButton, with internal variables hidden.
- **StateButton:** its lit look follows the logic's result, not the click, like a real cockpit push-button.
- **Cockpit-style grouping:** controls sit in panels named after the real hardware (Flight Control Panel, Stick Controls, CLAWS requests and availability).
- **Column alignment:** each machine's states sit directly above its transitions, so the eye goes from "where am I" to "where can I go".
- **Live condition highlighting:** every term is green or red, and a card turns green when its whole condition is true. This shows *why* a transition is or isn't armed.
- **Inline rationale** on each transition, and a **[GLOBAL]** tag marking override transitions.
- **Output strip** showing derived state the way a cockpit display does (the FMA), as the model for the aircraft output panel.
- **Zero install:** one HTML file, a file picker, runs offline.

### Decided for the new tool

| Topic | Existing tool | New tool |
| --- | --- | --- |
| Execution | Event-driven: one evaluation per input change, at most one transition per machine | Time-based; runs until things settle; details belong to the engine spec |
| Machine order | File order, sequential | Defined by the new tool |
| Variable writes | Transitions write variables via `set_vars`; controls sync back | No `set_vars`. Machines set only their state; boolean equations outside the machines drive variables |
| FMA strip, `fma_logic` | Hard-coded FMA columns driven by `fma_logic` rules | Replaced by an aircraft output panel driven by boolean equations; defined later |
| System log | Dark log panel under the equations | Dropped |
| `action` field | Written on transitions, never displayed | Not a concern for now |
| Grouping | `separator` entries in the flat `variables` list | Keep grouping; how it is declared is still open |
| Fast discrete events (e.g. `ground_time_gt_2s`) | Manual checkbox | Probably stays a manual input or button; to be confirmed |

### Still open

- **How groups are declared:** separators in a flat list, or one list per group?
- **Fast discrete events:** manual inputs, or driven by time?
- **Aircraft output panel:** how it is defined in the file and laid out on screen.
- **Time on screen:** with time-based execution, does the user need play, pause, step and a speed control? Should the screen show the current time or tick?
- **Equation-driven variables:** with no `set_vars`, should variables computed by boolean equations get a read-only display?

### Known issues not to carry over

- Text from the JSON (state names, conditions) is put into the page as raw HTML; only rationale is escaped.
- Buttons fire on `mousedown` only, so keyboard and touch users can't press them.
- The state row and the equations scroll sideways independently, breaking column alignment.
- Reset needs a full page reload and a new file pick.
- A bad file fails silently: unknown variables or states just make conditions false, with no report.
