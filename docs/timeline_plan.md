# Implementation plan: live timeline and sequence chart

Branch `charts`. Implements the design in `docs/future_timeline.md`. Out of
scope (still open points there): A/B comparison, causes in the text trace,
Mermaid export.

## Model tiers

| Tier | Used for | Why |
|---|---|---|
| **Fable** | The two hard tasks: cause folding (T3) and the timeline pane with the sequence chart (T4) | Subtle semantics, or a large UI with layout logic. A mistake there is costly to find later |
| **Opus** | Engine triggers (T2), contracts (T0), integration and review (T7, T8) | Moderate, but exact: touches the engine's core loop and the cross-task contracts |
| **Sonnet** | Server wiring (T5), browser and integration tests (T6), requirements and UI spec (T1) | Well specified, follows existing patterns |
| **Haiku** | README, cheat sheet, decisions entry, test report (T9) | Mechanical text edits |

Fable is used for 2 of the 10 tasks. Everything that only follows a fixed
contract goes to Sonnet or Haiku.

## Contracts (T0, #12, done first, by the lead)

GitHub: epics #9 (timeline data), #10 (front end), #11 (specs, integration,
docs); one issue per task, linked as sub-issues and labelled with its model.

Fixed before any parallel work, so tasks never wait on each other's code.
Done: the fields are on `TraceEvent` (`src/statesim/trace.py`), the
`Timeline` API is a stub in `src/statesim/timeline.py`, and the fixture is
built by `tests/fixtures/timeline/make_fixture.py`. The fixture holds
`{"machines", "gen", "items"}`, where `machines` is `describe_model()`'s
list.

1. **`TraceEvent` new fields**, all with defaults, so the text log does not
   change: `kind: str = ""`, `name: str = ""`, `old: object = None`,
   `new: object = None`, `trigger: tuple[str, ...] = ()`, `label: str = ""`,
   `title: str = ""`, `phase: str = ""`.
   - `kind` is one of `input`, `result`, `transition` or `action`.
   - `trigger` is sorted, so the output stays deterministic.
2. **Timeline items**, JSON-ready dicts with sequential `id`s and `t` in float
   ms:
   - `{"k":"tr", id, t, tick, sm, tid, title, from, to, causes:[ids], writes:[[var, value], ...]}`
   - `{"k":"in", id, t, tick, name, value}`
3. **`Timeline` API:**
   - A `TraceSink`: `emit(event)`.
   - `items_since(id) -> list` and `all() -> list`.
   - `gen: int`; `cap` defaults to 20,000 and drops the oldest items.
4. **Messages:**
   - `{"type":"timeline","gen","items":[...]}`: sent on connect, and again
     when a delta would exceed 2,000 items.
   - Every `state` message also carries `"t"` (ms), `"gen"` and `"tl"`: the
     items added since the last broadcast.
5. **Fixture:** `tests/fixtures/timeline/autopilot3_items.json`, a real item
   list for the front end to work against before the server is wired. T0
   produces it with a throwaway recorder that has naive causes. T3 replaces it
   with real output.

## Tasks and waves

```
Wave 0  T0 contracts (lead, Opus)
Wave 1  T1 docs/reqs (Sonnet) | T2 engine (Opus) | T3 recorder (Fable) | T4 front end (Fable)
Wave 2  T5 session+server (Sonnet)  -> T6 browser + example tests (Sonnet)
Wave 3  T7 integration (lead, Opus) | T8 cause-chain review (Opus) | T9 docs (Haiku)
```

Each Wave 1 task runs in its own git worktree, owns its files, and is tested
on its own. The lead merges the worktrees in order T1, T2, T3, T4 and runs the
full test suite after each one.

### T1 (#13): Requirements and UI spec (Sonnet)
- **Files:** `docs/requirements.csv` (new REQ-160 onward) and
  `docs/frontend_ui_spec.md` (new section 11, Timeline pane, and the colour
  tokens).
- **Contents:** one REQ per behaviour in design sections 1 to 4, each with
  its verification kind. The pane's look and interactions are written as
  tables, in the style of the existing spec.
- **Done when:** every row has a spec reference, and `make_report.py`
  accepts the file.

### T2 (#14): Engine triggers (Opus)
- **Files:** `src/statesim/trace.py` and `src/statesim/engine.py`; new test
  file `tests/unit/test_triggers.py`.
- **Work:**
  - Fill in the new fields on every event.
  - Keep a last-seen copy of the names each item reads (each state machine,
    each equation). Update it at the end of the item's run.
  - Exclude `t`, `tick` and `dt`.
  - A transition's `trigger` uses only its own rows' names. It is captured
    with its values, before the exit action runs.
  - Mark action events with `phase`: `init`, `exit`, `entry` or `during`.
  - Bookkeeping runs only when a trace sink is attached, so headless runs
    keep their speed.
- **Tests:** single band, two bands (a slow machine sees a change made
  between its passes), timer (no trigger), through an equation, set before
  the first step, an action writing a name its own rows read, determinism
  (the same trace under different `PYTHONHASHSEED` values).
- **Done when:** all existing tests pass unchanged (the text log is
  byte-identical) and the new tests pass.

### T3 (#15): Timeline recorder (Fable)
- **Files:** `src/statesim/timeline.py` (standard library only) and its test
  file `tests/unit/test_timeline.py`.
- **Work:** origin folding as in design section 2.
  - Exit writes are held until their machine's transition in the same tick.
  - Entry writes are attached to it.
  - `during` and `init` writes take the machine's last transition as their
    origin.
  - Unchanged inputs are skipped.
  - The cap drops the oldest items; causes that point to dropped ids are
    allowed.
- **Tests:** built from hand-made `TraceEvent`s only, so T3 doesn't depend
  on T2. Once T2 is merged, add one end-to-end test with `examples/actions`.
- **Also:** regenerate the fixture from `examples/autopilot3` (one scripted
  autoland) after merging with T2.

### T4 (#16): Timeline pane and sequence chart (Fable)
- **Files:** new `src/statesim_server/static/timeline.js` and
  `timeline.css`, plus small hooks in `index.html`, `app.js` and `server.py`
  `PAGES` (one line).
- **Work:** everything in design section 4.
  - A pane across the full width at the bottom, with a run-bar toggle and a
    horizontal splitter. Its height and visibility are remembered in the
    browser, wrapped in try/catch.
  - SVG swimlanes with stable colours per state, transition ticks with
    titles on hover, and an inputs row.
  - A follow mode with a Live button; the default window is 30 s.
  - Dashed cause lines on hover or selection.
  - The sequence chart (forward closure over `causes`) below the lanes.
  - The API is `StateSimTimeline.build(el, machines)`, `.reset(gen, items)`,
    `.add(items, t)`.
  - It's developed against the T0 fixture, using a test page that loads it.
- **Done when:** the fixture renders, a click shows its chain, and 20,000
  items stay responsive (redraws are batched with `requestAnimationFrame`
  and only the visible window is drawn).

### T5 (#17): Session and server wiring (Sonnet, after T2 and T3)
- **Files:** `session.py` and `server.py`, and the tests `test_session.py`
  and `test_server.py`.
- **Work:**
  - The session sends events to both the user's trace and a `Timeline`.
  - Reset starts a new `Timeline` with `gen + 1`.
  - Connect sends the `timeline` message.
  - Broadcasts carry `t`, `gen` and `tl`, and fall back to a full message
    when a delta is too large.
  - A broadcast that includes items is never skipped as a duplicate.

### T6 (#18): Browser and example tests (Sonnet, after T4 and T5)
- **Files:** `tests/frontend/test_browser.py` and
  `tests/requirements/test_examples.py`.
- **Tests:**
  - The pane toggles and remembers its setting.
  - Lanes grow while running.
  - Reset clears the lanes.
  - Clicking a transition shows its chain on `autopilot2`: Guidance Source,
    then Lateral/Vertical, then Phase of flight.
  - On `autopilot3`, the AP press leads to the AP engage transition, then
    the FD transition (through `ap_on`).

### T7 (#19): Integration (lead, Opus)
- Merge the worktrees.
- Run the full suite and the report.
- Check by hand in the browser on autopilot3 in both run modes.

### T8 (#20): Cause-chain review (Opus)
- Read only. Compare the chains on `autopilot2` and `autopilot3` with the
  logic, and list any wrong or missing link with its reason.
- Escalate to Fable only if it finds a semantic flaw in the trigger rule
  itself.

### T9 (#21): Docs (Haiku)
- README (a front end paragraph and a link), the cheat sheet (timeline
  messages, `TraceEvent` fields), a new Part E in `decisions.md` holding the
  user decisions from the design, the status line of `future_timeline.md`
  (now "implemented"), and the test report.

## Risks and how the plan handles them

| Risk | Handling |
|---|---|
| The text trace changes by accident | T2 must keep every existing trace test byte-identical |
| Trigger bookkeeping slows "as fast as possible" | Done only when a sink is attached; T7 times autopilot3 for 10,000 ticks before and after (budget: below 25% slower) |
| Cause links are wrong but look plausible | T3 tests are hand-computed; T8 reviews the real chains on two examples |
| Too many items in fast mode | The 20,000-item cap, a full resend when a delta exceeds 2,000, and drawing only the visible window |
| Parallel agents collide | Worktrees, owned files, and contracts frozen in T0 |
