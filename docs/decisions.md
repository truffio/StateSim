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
   lower; within a band by `order`.
5. Ties on (band,order): by master-file row, then CSV row.
6. Reserved context names: tick, t (seconds = tick/tick_hz computed exactly,
   not accumulated), dt (= 1/band_hz of the item being evaluated).
7. Result variables start False.
8. Input default_value parsed with ast.literal_eval, fallback raw string.
9. Log: result changes, state transitions, set_input; one line per event
   e.g. `tick=000012 t=0.240000 | AP | T3 OFF->ARMED "title" | alt=1000, ap_sw=True`,
   values sorted by name.
10. MAX_EQUATIONS/MAX_STATE_MACHINES = 10,000.
11. Global transition to the current state is a no-op, not logged.
12. Timers = expressions over t; "components" deferred.
13. Master CSV (columns file_name, type in {state_machine,equations,inputs},
    order [state_machine rows only]); paths relative to the master file's
    directory; duplicate result_variable across files is a load error;
    set_input on unknown name raises KeyError; snapshot also includes inputs.
14. Load checks: expression syntax, duplicate transition_id, unknown states,
    exactly one default_state per SM, single band per SM file, limits.
15. `order` column in SM files orders transitions within the SM; band stays
    in each SM file (all rows same band).

Equations are Python syntax evaluated with
`eval(code, {"__builtins__": builtins}, ctx)`; expressions are compiled once
in `Engine.__init__` (code objects are NOT stored in the frozen Model).

## Part B: resolved contract details (T0)

- **Numbers.** `band_hz`, every `order` and `tick_hz` are `fractions.Fraction`
  (parsed with `Fraction(text)`, so "20", "0.5", "1/3" all work). The LCM of
  rationals is `lcm(numerators) / gcd(denominators)` (`model.compute_tick_hz`).
  `period_ticks` is an `int`. `Engine.t` is an exact Fraction; `snapshot()["t"]`
  is `float(t)`.
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
  strings shown with `repr()`, Fractions as `%.6f`, others with `str()`.
  `set_input` is logged on every call, at the current tick.
- **Sources.** `"file:line"`, file as written in the master CSV, 1-based
  physical line with the header on line 1.
