# Fixture scenarios

Hand-computed expectations (tick starts at 1 on the first step; step N has tick N). Run scenarios: `expected.json` has steps of `set_inputs` + one `engine.step()` + `expect` (subset of snapshot). Error scenarios: `error_contains`, `source_contains` (offending file name) match the load error.

## minimal
One SM `M` (A->B on input `go`) and one equation ordered after it, all at 10 Hz. Checks that the default state is used, an input change fires the transition in the next step, results are visible to a later equation in the same pass, and result variables are exposed. REQ-001, 002, 003, 010, 011, 012, 013, 014, 018, 029, 035, 036, 038, 083, 085, 089, 090, 091.

## ap_engage
Autopilot SM `AP` (OFF/ARMED/ENGAGED) with a two-row guard transition (ARMED->ENGAGED needs `ap_sw` and `alt_cap`), a global disconnect to OFF, and a monitoring equation ordered after the SM that sees the new state in the same pass. Also exercises a conflict at tick 7 (OFF->ARMED, order 1, beats the enabled global disconnect, order 4), after which the global fires at tick 8. REQ-020, 021, 023, 024, 026, 027, 028, 034, 049, 050, 056, 109, 110.

## multirate
Equations only: 30 Hz and 20 Hz bands (tick_hz 60; 30 Hz runs on ticks 1,3,5,7,9; 20 Hz on 1,4,7,10; period_ticks 2 and 3). Thresholds on `tick` show each band recomputes only on its own ticks; `s_copy` copies a 30 Hz result and at the coincident tick 7 proves the higher frequency band runs first. `dt` equals 1000/band_hz ms per item (`dt * 30 == 1000`, `dt * 20 == 1000`). REQ-040, 041, 042, 043, 044, 045, 046, 055, 057, 058, 061, 062.

## conflict
Two transitions from S0 enabled by the same input in one pass. The id 2 transition has order 1 and the id 1 transition has order 2; the manual order wins (state X, not Y), and all row results are still written. REQ-028, 049, 056, 018, 019.

## global_transition
`G` with a global fault transition (empty current_state) firing from IDLE and RUN. A global transition to the current state is a no-op that still wins over the later FAULT->IDLE reset (decisions.md Part B), so the SM stays FAULT until fault drops. REQ-025, 026, 027, 028, 056.

## and_rows
One transition made of three rows (a, b, c) that are ANDed, plus a second one-row transition (differing row counts). Verifies it fires only when all rows are true, that all row results update every pass, and that a middle row false blocks it. REQ-019, 020, 021, 022, 032.

## reuse_equation
A standalone equation `armed_cond` (order 1) is used by name by an SM transition (master order 2), and another standalone equation `lamp` (order 3) uses both `armed_cond` and the SM state. Verifies cross-file reuse and shared ordering space between equations and SMs in a band. REQ-004, 005, 015, 016, 034, 050.

## order_visibility
Equations only with CSV rows deliberately not in order. `y` (order 3) sees `x` (order 2) of the same pass; `p` (order 1) sees `late` (order 4) from the previous pass. REQ-049, 050, 051, 052, 054, 101.

## bad_syntax
Equation with a Python syntax error in equations.csv is rejected at load. REQ-065.

## bad_no_default
SM file with no default_state row. REQ-068.

## bad_dup_default
SM file with two default_state rows. REQ-069.

## bad_band_in_sm_file
SM file that still has a band column (the band belongs in the master CSV). REQ-070.

## bad_no_sm_band
Master CSV state_machine row with an empty band. REQ-138.

## bad_unknown_state
Transition from state C, which is neither the default nor any next_state. REQ-067.

## bad_dup_result_var
Two equations share result_variable e1 (second one, line 3, is the offender). Duplicate result variables are a load error (decisions.md item 13). No dedicated REQ; closest REQ-014.

## bad_nonpositive_band
Equation with band 0. REQ-077.

## bad_inconsistent_transition_id
Rows of transition 1 disagree on next_state (B vs C). REQ-071 (and REQ-066 related).
