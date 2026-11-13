# Future feature: live timeline and sequence chart

Status: **designed, not implemented** (recorded 2026-11-12).

Two views of the current session, built live while the tool runs:

1. **Swimlane timeline.** One lane per state machine showing its states over
   time, a row of input events, and a cursor at the current time.
2. **Sequence chart.** Click an event to see its chain of causes and effects,
   for example: key press → Keypad → Lock → Alarm → LED.

## Decisions (user)

- **Lanes:** state machines only. Equations get no lane and never appear as
  events. They are folded into the cause links between machines.
- **Events:** transitions, labelled with their name: id, plus the title on
  hover or when there's room.
- **Where:** an optional pane in the front end, updated live as the user
  works and states change. It can be shown or hidden.
- **Data source:** the current session's log, the same whether the session is
  driven by hand or by an automated test. There are no scenario files.

## Feasibility (checked)

A prototype on the trace of `examples/actions` rebuilt the lanes exactly from
the transition events (`phase: Ground@0 → Takeoff@2 → Climb@3 → Cruise@54 →
Ground@63`).

The cause links were only guessed. A transition's logged values list every
name its rows read, not the ones that changed. Guessing "the last write in the
same or previous pass" breaks with several bands and with long chains. Hence
part 1 below.

## Design

### 1. Engine: structured trace events with triggers

Extend `TraceEvent` (`src/statesim/trace.py`) with optional fields. They all
have defaults, so existing code and the text log format do not change.

| Field | Meaning |
|---|---|
| `kind` | `input`, `result` (equation or row result), `transition`, `action` |
| `name` | variable written, or state machine name for a transition |
| `old`, `new` | value before / after (states for a transition) |
| `trigger` | names read by the item whose value changed since that item last ran |
| `label`, `title` | transition label (`T2`) and title; for an action, `label` is the action name |
| `phase` | for an action: `entry`, `exit`, `during` or `init` |

How `trigger` is computed:
- The engine keeps, for each state machine and each standalone equation, the
  values of the names it reads, as they were at the end of its previous run.
  At start these are the initial values.
- When the item runs, `trigger` = the names it read whose value differs from
  that copy. For a transition, only the names read by its own rows count.
- `t`, `tick` and `dt` are excluded, so a timer transition has no cause link.
- Because it is "since this item last ran", it stays exact when machines run
  at different rates (bands).

### 2. `Timeline` recorder (`statesim/timeline.py`, no dependencies)

A `TraceSink` that turns events into plain, JSON-ready items with sequential
ids:

- `{"k": "tr", id, t, tick, sm, tid, title, from, to, causes: [ids], writes: [[var, value], ...]}`
- `{"k": "in", id, t, tick, name, value}`: input changes only. A `set_input`
  call that leaves the value the same is skipped.

How causes are folded through equations:
- The recorder keeps `origins[var]`: the set of timeline item ids (inputs or
  transitions) that last produced that variable's value.
- An input change sets `origins[name] = {its id}`.
- A transition sets `origins[sm] = {its id}`. Its `causes` are the union of
  `origins[n]` over its `trigger` names.
- A result change (equation or row result) sets `origins[var]` to the union
  of `origins` over its `trigger`. This is how an equation passes its cause
  through without ever appearing.
- Action writes, by phase:
  - `exit`: logged before its transition. Held until that machine's
    transition arrives in the same tick.
  - `entry`: attached to the machine's transition from the same tick.
  - Both end up in that transition's `writes`, with `origins[var] =
    {transition id}`.
  - `during` / `init`: `origins[var]` = the machine's last transition, if
    any. Not shown as events.

### 3. Server and session

- **Session:** `Session` sends events both to the user's `--trace` file (if
  any) and to a `Timeline`. Reset starts a new `Timeline` with a new
  generation number. Keeping the previous run for an A/B comparison is a
  later option (see Open points).
- **Messages:**
  - On connect, a `{"type": "timeline", "gen", "items": [...]}` message with
    everything so far.
  - Each state broadcast carries `"t"` (simulation ms) and the items added
    since the previous broadcast.
  - When `gen` changes, the browser clears the timeline.
- **Size:** cap the item count (for example 20,000, dropping the oldest),
  because "as fast as possible" mode can produce many transitions.

### 4. Front end: optional Timeline pane

- **Pane:** a toggle in the run bar shows or hides it. Its height can be
  changed with a splitter, like the left pane, and both settings are
  remembered in the browser.
- **Swimlanes (SVG):** one row per state machine, labelled with its display
  name. Each state is a bar; each machine's states keep the same colours
  across the session. Each transition is a tick mark labelled with its id,
  and its title shows on hover. An inputs row shows dots for input changes,
  labelled with the input name.
- **Time axis:** follows the run, showing the last N seconds. Scrolling back
  pauses the follow, and a "Live" button resumes it. A cursor marks the
  current time.
- **Cause lines:** dashed lines from each transition to its causes, drawn
  when a transition is hovered or selected.
- **Sequence chart:** clicking a transition or an input dot opens it below
  the lanes.
  - Lifelines: Inputs, plus each state machine in the chain.
  - Contents: the clicked event and everything it caused, following `causes`
    forward, in time order.
  - An arrow from the cause's lifeline to the machine that changed state,
    labelled with the transition name.
  - Action `writes` drawn as arrows back to Inputs (`ground_speed = 0`).

### 5. Tests

- **Engine:** `trigger` is correct for a single band, for several bands, for
  a timer (no trigger), and through an equation.
- **Timeline:** lanes, cause folding through equations, exit/entry write
  attachment, skipping unchanged inputs, reset generation.
- **Server:** the timeline message on connect, items added to state
  broadcasts, clearing on reset.
- **Browser (Playwright):** the pane toggles, lanes grow while running, and
  clicking a transition shows its chain. Test case: `autopilot2`, whose
  chains run through Guidance Source → Lateral/Vertical → Phase of flight.

## Open points

- **A/B comparison:** keep the previous run on Reset and show a "B" row under
  each lane, marking the first difference.
- **Text trace:** whether to append `| because x, y` lines to it (this
  changes the log format and its tests).
- **Mermaid export:** a `sequenceDiagram` export of a selected chain for
  reports.
