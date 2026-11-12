# Decisions: authoritative behavior spec

This file is the authoritative behavior specification for the engine. Where
it is more specific than `requirements_simulation_framework_spec.yaml`, this
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
