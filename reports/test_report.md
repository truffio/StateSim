# Test report

## 1. Summary

| Category | Total | Pass | Fail | Error | Skip |
|---|---:|---:|---:|---:|---:|
| Unit | 229 | 229 | 0 | 0 | 0 |
| Requirement | 105 | 105 | 0 | 0 | 0 |
| Total | 334 | 334 | 0 | 0 | 0 |

Requirements (135): PASS 129, FAIL 0, UNTESTED 0, NOT-AUTOMATED 6, SKIP 0

## 2. Failures

No failures or errors.

## 3. Requirement traceability matrix

| Req ID | Area | Requirement | Verification | Tests | Status |
|---|---|---|---|---|---|
| REQ-001 | master | The engine shall load a master CSV whose rows list definition files with columns file_name, type and order | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-002 | master | The engine shall accept master CSV type values state_machine, equations and inputs | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-003 | master | The engine shall load one state machine per state_machine file in the master CSV | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-004 | master | The engine shall use the master CSV order column to order state machines within their band | use_case_test | tests.requirements.test_behavior::test_master_order_orders_state_machines (pass) | PASS |
| REQ-005 | master | The engine shall share one ordering space within a band between state machines and equations | use_case_test | tests.requirements.test_behavior::test_state_machines_and_equations_share_ordering_space (pass) | PASS |
| REQ-006 | master | The engine shall ignore the master CSV order column for equations and inputs rows | unit_test | tests.requirements.test_loader_api::test_order_ignored_for_equations_and_inputs_rows (pass) | PASS |
| REQ-007 | master | The engine shall take execution rate from the band column of the definition files and not from the master CSV | unit_test | tests.requirements.test_loader_api::test_band_comes_from_definition_files (pass) | PASS |
| REQ-008 | loader | The engine shall read all definition files including the master file as CSV with no YAML or JSON inputs | review | - | NOT-AUTOMATED |
| REQ-009 | loader | The engine shall build an immutable Model from the master CSV and the files it references | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-010 | loader | The engine shall read state machine CSV columns transition_id, current_state, next_state, default_state, equation, result_variable, rationale, title, band and order | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-011 | loader | The engine shall read equations CSV columns equation, explanation, rationale, result_variable, band and order | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-012 | loader | The engine shall read inputs CSV columns variable_name, type and default_value | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-013 | equations | The engine shall evaluate equations as Python-syntax Boolean expressions over context variable names | use_case_test | tests.requirements.test_behavior::test_boolean_expression_over_inputs (pass); tests.requirements.test_behavior::test_comprehension_sees_context_names (pass); tests.requirements.test_behavior::test_runtime_error_is_wrapped_with_location (pass) | PASS |
| REQ-014 | equations | The engine shall assign the result of each standalone equation to its result_variable on every evaluation | use_case_test | tests.requirements.test_behavior::test_standalone_equation_recomputed_every_pass (pass); tests.requirements.test_scenarios::test_run_scenario[reuse_equation] (pass) | PASS |
| REQ-015 | equations | The engine shall make a standalone equation result variable usable by name in state machine equations | use_case_test | tests.requirements.test_behavior::test_equation_results_reused_by_name (pass); tests.requirements.test_examples::test_autopilot_climb_capture_hold (pass); tests.requirements.test_examples::test_autopilot2_a220_autoland_sequence (pass); tests.requirements.test_scenarios::test_run_scenario[reuse_equation] (pass) | PASS |
| REQ-016 | equations | The engine shall make a standalone equation result variable usable by name in other standalone equations | use_case_test | tests.requirements.test_behavior::test_equation_results_reused_by_name (pass); tests.requirements.test_examples::test_autopilot_climb_capture_hold (pass); tests.requirements.test_scenarios::test_run_scenario[reuse_equation] (pass) | PASS |
| REQ-017 | equations | The engine shall not perform sandboxing or AST sanitization of expressions | review | - | NOT-AUTOMATED |
| REQ-018 | state_machine | The engine shall assign the result of each state machine row equation to its result_variable on every evaluation | use_case_test | tests.requirements.test_behavior::test_row_results_updated_every_evaluation (pass) | PASS |
| REQ-019 | state_machine | The engine shall evaluate every row of every transition on every evaluation of its state machine so that result variables are always updated | unit_test | tests.requirements.test_behavior::test_all_rows_evaluated_without_short_circuit (pass); tests.requirements.test_rate::test_rows_track_inputs_continuously_while_state_is_unchanged (pass) | PASS |
| REQ-020 | state_machine | The engine shall treat all rows sharing a transition_id as one transition | unit_test | tests.requirements.test_behavior::test_transitions_with_different_row_counts (pass) | PASS |
| REQ-021 | state_machine | The engine shall AND the equations of a transition so that it is enabled only when all of them are true | use_case_test | tests.requirements.test_behavior::test_transition_rows_are_anded (pass); tests.requirements.test_examples::test_autopilot_climb_capture_hold (pass); tests.requirements.test_examples::test_autopilot_monitor_disconnect_and_interlock (pass); tests.requirements.test_examples::test_autopilot2_a220_autoland_sequence (pass); tests.requirements.test_scenarios::test_run_scenario[and_rows] (pass) | PASS |
| REQ-022 | state_machine | The engine shall support transitions with differing numbers of equations within one state machine | unit_test | tests.requirements.test_behavior::test_transitions_with_different_row_counts (pass); tests.requirements.test_scenarios::test_run_scenario[and_rows] (pass) | PASS |
| REQ-023 | state_machine | The engine shall fire a non-global transition only when the state machine is in the transition current_state | use_case_test | tests.requirements.test_behavior::test_non_global_transition_needs_current_state (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-024 | state_machine | The engine shall not fire a non-global transition whose equations are true when the state machine is not in its current_state | use_case_test | tests.requirements.test_behavior::test_non_global_transition_needs_current_state (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-025 | state_machine | The engine shall treat a transition with empty current_state as global | unit_test | tests.requirements.test_loader_api::test_global_default_and_self_transition (pass) | PASS |
| REQ-026 | state_machine | The engine shall fire an enabled global transition from any state | use_case_test | tests.requirements.test_behavior::test_global_transition_fires_from_any_state (pass); tests.requirements.test_examples::test_autopilot_monitor_disconnect_and_interlock (pass); tests.requirements.test_examples::test_autopilot2_a220_autoland_sequence (pass); tests.requirements.test_scenarios::test_run_scenario[global_transition] (pass) | PASS |
| REQ-027 | state_machine | The engine shall give global and non-global transitions no special precedence | use_case_test | tests.requirements.test_behavior::test_no_precedence_first_enabled_in_order_wins (pass); tests.requirements.test_scenarios::test_run_scenario[global_transition] (pass) | PASS |
| REQ-028 | state_machine | The engine shall apply the first enabled transition in manual (band and order) sequence when several transitions are enabled in the same pass | use_case_test | tests.requirements.test_behavior::test_no_precedence_first_enabled_in_order_wins (pass); tests.requirements.test_examples::test_autopilot2_a220_autoland_sequence (pass); tests.requirements.test_scenarios::test_run_scenario[conflict] (pass) | PASS |
| REQ-029 | state_machine | The engine shall start each state machine in its default_state | use_case_test | tests.requirements.test_behavior::test_state_machine_starts_in_default_state (pass); tests.requirements.test_scenarios::test_run_scenario[minimal] (pass) | PASS |
| REQ-030 | state_machine | The engine shall take the default state from the single row of the file that has default_state filled | unit_test | tests.requirements.test_loader_api::test_global_default_and_self_transition (pass) | PASS |
| REQ-031 | state_machine | The engine shall accept a transition whose next_state equals its current_state; a global transition to the current state is a no-op that still wins the pass and is not logged | unit_test | tests.requirements.test_behavior::test_global_self_transition_is_noop_that_wins_and_is_not_logged (pass); tests.requirements.test_behavior::test_non_global_self_transition_fires_and_is_logged (pass) | PASS |
| REQ-032 | state_machine | The engine shall use each transition expression as written with no implicit negation or inhibit | unit_test | tests.requirements.test_examples::test_autopilot_monitor_disconnect_and_interlock (pass); tests.requirements.test_loader_api::test_expression_used_as_written (pass) | PASS |
| REQ-033 | state_machine | The engine shall support multiple state machines up to MAX_STATE_MACHINES | unit_test | tests.requirements.test_loader_api::test_multiple_state_machines (pass) | PASS |
| REQ-034 | state_machine | The engine shall allow transition equations to reference result variables of other state machines through the shared context | use_case_test | tests.requirements.test_behavior::test_state_machines_share_context (pass) | PASS |
| REQ-035 | inputs | The engine shall initialize every external input to its default_value from the inputs file at start | use_case_test | tests.requirements.test_behavior::test_inputs_start_at_defaults (pass) | PASS |
| REQ-036 | inputs | The engine shall make an input value set with set_input visible to equations at the next evaluation | use_case_test | tests.requirements.test_behavior::test_standalone_equation_recomputed_every_pass (pass); tests.requirements.test_behavior::test_set_input_visible_next_evaluation (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-037 | inputs | The engine shall reject a result_variable (equation or transition row) named like an input so that only set_input writes inputs (assignment inside expressions is not checked: known limitation) | unit_test | tests.requirements.test_loader_api::test_result_variables_cannot_shadow_inputs (pass) | PASS |
| REQ-038 | inputs | The engine shall make input variables usable by name in equations | use_case_test | tests.requirements.test_behavior::test_boolean_expression_over_inputs (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-039 | inputs | The engine shall convert input default_value at load according to the type column (bool accepts true/false/1/0 case-insensitively; int; float; str) and reject an unknown type or a value that fails to convert | unit_test | tests.requirements.test_loader_api::test_input_defaults_converted (pass); tests.requirements.test_loader_api::test_input_default_conversion_failure_rejected[bool-maybe] (pass); tests.requirements.test_loader_api::test_input_default_conversion_failure_rejected[int-1.5] (pass); tests.requirements.test_loader_api::test_input_default_conversion_failure_rejected[float-x] (pass); tests.requirements.test_loader_api::test_input_default_conversion_failure_rejected[list-[1]] (pass); tests.requirements.test_loader_api::test_input_default_conversion_failure_rejected[-1] (pass) | PASS |
| REQ-040 | bands | The engine shall treat each band as an explicit frequency in Hz | unit_test | tests.requirements.test_loader_api::test_band_comes_from_definition_files (pass) | PASS |
| REQ-041 | bands | The engine shall not require any integer multiple or factor relationship between bands | use_case_test | tests.requirements.test_behavior::test_20hz_and_30hz_coexist (pass); tests.requirements.test_behavior::test_non_multiple_and_fractional_bands (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-042 | bands | The engine shall support bands such as 20 Hz and 30 Hz coexisting | use_case_test | tests.requirements.test_behavior::test_20hz_and_30hz_coexist (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-043 | bands | The engine shall evaluate each item at the rate of its band | use_case_test | tests.requirements.test_behavior::test_20hz_and_30hz_coexist (pass); tests.requirements.test_rate::test_every_item_runs_exactly_at_its_band_rate_over_long_run (pass); tests.requirements.test_rate::test_state_machine_reacts_only_on_its_band_passes (pass); tests.requirements.test_rate::test_input_pulse_between_passes_is_not_seen_by_slow_band (pass); tests.requirements.test_rate::test_item_evaluation_times_independent_of_other_bands (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-044 | bands | The engine shall evaluate all items sharing a band at the same rate | use_case_test | tests.requirements.test_behavior::test_20hz_and_30hz_coexist (pass); tests.requirements.test_rate::test_every_item_runs_exactly_at_its_band_rate_over_long_run (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-045 | bands | The engine shall use a tick rate equal to the least common multiple of all band frequencies | unit_test | tests.requirements.test_loader_api::test_tick_rate_is_lcm_and_periods_are_whole (pass) | PASS |
| REQ-046 | bands | The engine shall make every band period a whole number of ticks | unit_test | tests.requirements.test_loader_api::test_tick_rate_is_lcm_and_periods_are_whole (pass) | PASS |
| REQ-047 | bands | The engine shall use exact integer arithmetic for scheduling with no floating-point accumulation | static_check | tests.requirements.test_static::test_scheduling_uses_exact_arithmetic (pass) | PASS |
| REQ-048 | bands | The engine shall support band and order columns in every state machine file and the equations file | unit_test | tests.requirements.test_loader_api::test_load_builds_model_from_master (pass) | PASS |
| REQ-049 | execution | The engine shall run items within a band in their manual order each time the band is scheduled | use_case_test | tests.requirements.test_behavior::test_later_item_sees_earlier_result_same_pass (pass); tests.requirements.test_scenarios::test_run_scenario[order_visibility] (pass) | PASS |
| REQ-050 | execution | The engine shall let a later item see the result of an earlier item in the same pass | use_case_test | tests.requirements.test_behavior::test_later_item_sees_earlier_result_same_pass (pass); tests.requirements.test_scenarios::test_run_scenario[order_visibility] (pass) | PASS |
| REQ-051 | execution | The engine shall let an earlier item see the previous pass value of a later item result | use_case_test | tests.requirements.test_behavior::test_earlier_item_sees_previous_pass_value (pass); tests.requirements.test_scenarios::test_run_scenario[order_visibility] (pass) | PASS |
| REQ-052 | execution | The engine shall not derive or infer execution order from dependencies | use_case_test | tests.requirements.test_behavior::test_later_item_sees_earlier_result_same_pass (pass); tests.requirements.test_behavior::test_earlier_item_sees_previous_pass_value (pass); tests.requirements.test_scenarios::test_run_scenario[order_visibility] (pass) | PASS |
| REQ-053 | execution | The engine shall build the execution plan ordered by (band, order) once at load | unit_test | tests.requirements.test_loader_api::test_schedule_sorted_by_band_then_order (pass) | PASS |
| REQ-054 | execution | The engine shall never depend on dict or set iteration order for execution order | static_check | tests.requirements.test_static::test_no_set_or_dict_order_dependence (pass); tests.unit.test_determinism::test_hash_seed_independent[ap_engage] (pass); tests.unit.test_determinism::test_hash_seed_independent[multirate] (pass); tests.unit.test_determinism::test_hash_seed_independent[reuse_equation] (pass) | PASS |
| REQ-055 | execution | The engine shall recompute item values on every scheduled pass of their band | use_case_test | tests.requirements.test_behavior::test_standalone_equation_recomputed_every_pass (pass); tests.requirements.test_rate::test_continuous_square_wave_over_long_run (pass); tests.requirements.test_rate::test_rows_track_inputs_continuously_while_state_is_unchanged (pass) | PASS |
| REQ-056 | execution | The engine shall apply at most one state change per state machine per pass | use_case_test | tests.requirements.test_behavior::test_at_most_one_state_change_per_pass (pass); tests.requirements.test_scenarios::test_run_scenario[conflict] (pass) | PASS |
| REQ-057 | execution | The engine shall evaluate an item only on ticks that are multiples of its band period | use_case_test | tests.requirements.test_behavior::test_20hz_and_30hz_coexist (pass); tests.requirements.test_rate::test_every_item_runs_exactly_at_its_band_rate_over_long_run (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-058 | execution | The engine shall evaluate all bands on the first step (tick 1, t = 0 ms) | use_case_test | tests.requirements.test_behavior::test_all_bands_run_on_first_step (pass); tests.requirements.test_scenarios::test_run_scenario[multirate] (pass) | PASS |
| REQ-059 | time | The engine shall represent simulation time as an integer tick count | unit_test | tests.requirements.test_loader_api::test_tick_is_integer_and_increments_at_step_start (pass) | PASS |
| REQ-060 | time | The engine shall increment simulation time at the start of each step | unit_test | tests.requirements.test_loader_api::test_tick_is_integer_and_increments_at_step_start (pass) | PASS |
| REQ-061 | time | The engine shall derive t (absolute simulation time in milliseconds, (tick-1)*1000/tick_hz as an exact fraction) and dt (the item period in milliseconds) from the tick | unit_test | tests.requirements.test_behavior::test_t_is_absolute_ms_and_dt_is_period_ms (pass); tests.requirements.test_behavior::test_timer_time_independent_of_other_bands (pass); tests.requirements.test_loader_api::test_tick_is_integer_and_increments_at_step_start (pass) | PASS |
| REQ-062 | time | The engine shall make t and dt (both in milliseconds) available to equations as context names | use_case_test | tests.requirements.test_behavior::test_t_and_dt_available_in_equations (pass); tests.requirements.test_behavior::test_t_is_absolute_ms_and_dt_is_period_ms (pass) | PASS |
| REQ-063 | time | The engine shall run as fast as possible and not be synchronized to wall-clock time | static_check | tests.requirements.test_static::test_no_wall_clock (pass) | PASS |
| REQ-064 | time | The engine shall allow timer behavior to be expressed using t (absolute milliseconds) in equations independent of other bands | use_case_test | tests.requirements.test_behavior::test_timer_expressed_with_t (pass); tests.requirements.test_behavior::test_timer_time_independent_of_other_bands (pass); tests.requirements.test_rate::test_continuous_square_wave_over_long_run (pass) | PASS |
| REQ-065 | loadcheck | The engine shall reject an equation with a syntax error at load | unit_test | tests.requirements.test_loader_api::test_syntax_error_rejected (pass); tests.requirements.test_scenarios::test_error_scenario[bad_syntax] (pass) | PASS |
| REQ-066 | loadcheck | The engine shall treat rows sharing a transition_id as one transition whether or not they are contiguous and AND their equations | unit_test | tests.requirements.test_loader_api::test_non_contiguous_rows_with_same_id_are_one_anded_transition (pass); tests.requirements.test_scenarios::test_error_scenario[bad_inconsistent_transition_id] (pass) | PASS |
| REQ-067 | loadcheck | The engine shall reject a transition referencing an unknown state at load | unit_test | tests.requirements.test_loader_api::test_unknown_state_rejected (pass); tests.requirements.test_scenarios::test_error_scenario[bad_unknown_state] (pass) | PASS |
| REQ-068 | loadcheck | The engine shall reject a state machine file with zero default_state rows at load | unit_test | tests.requirements.test_loader_api::test_default_state_and_band_rules (pass); tests.requirements.test_scenarios::test_error_scenario[bad_no_default] (pass) | PASS |
| REQ-069 | loadcheck | The engine shall reject a state machine file with more than one default_state row at load | unit_test | tests.requirements.test_loader_api::test_default_state_and_band_rules (pass); tests.requirements.test_scenarios::test_error_scenario[bad_dup_default] (pass) | PASS |
| REQ-070 | loadcheck | The engine shall reject a state machine file whose rows use more than one band at load | unit_test | tests.requirements.test_loader_api::test_default_state_and_band_rules (pass); tests.requirements.test_scenarios::test_error_scenario[bad_mixed_band] (pass) | PASS |
| REQ-071 | loadcheck | The engine shall reject at load rows sharing a transition_id that disagree on current_state or next_state | unit_test | tests.requirements.test_loader_api::test_rows_of_one_transition_must_agree[second0] (pass); tests.requirements.test_loader_api::test_rows_of_one_transition_must_agree[second1] (pass); tests.requirements.test_scenarios::test_error_scenario[bad_inconsistent_transition_id] (pass) | PASS |
| REQ-072 | loadcheck | The engine shall reject at load a non-empty current_state that can never be entered (neither the default_state nor any transition next_state) | unit_test | tests.requirements.test_loader_api::test_current_state_that_can_never_be_entered_rejected (pass) | PASS |
| REQ-073 | loadcheck | The engine shall reject a total equation count above MAX_EQUATIONS at load | unit_test | tests.requirements.test_loader_api::test_max_equations_counts_transition_rows (pass) | PASS |
| REQ-074 | loadcheck | The engine shall reject a state machine count above MAX_STATE_MACHINES at load | unit_test | tests.requirements.test_loader_api::test_max_state_machines (pass) | PASS |
| REQ-075 | loadcheck | The engine shall count transition equations toward MAX_EQUATIONS | unit_test | tests.requirements.test_loader_api::test_max_equations_counts_transition_rows (pass) | PASS |
| REQ-076 | loadcheck | The engine shall define MAX_EQUATIONS and MAX_STATE_MACHINES as named constants and not per-component settings | static_check | tests.requirements.test_static::test_limits_are_named_constants (pass) | PASS |
| REQ-077 | loadcheck | The engine shall reject a non-positive or non-numeric band at load | unit_test | tests.requirements.test_loader_api::test_bad_band_rejected[0] (pass); tests.requirements.test_loader_api::test_bad_band_rejected[-5] (pass); tests.requirements.test_loader_api::test_bad_band_rejected[abc] (pass); tests.requirements.test_loader_api::test_bad_band_rejected[] (pass); tests.requirements.test_scenarios::test_error_scenario[bad_nonpositive_band] (pass) | PASS |
| REQ-078 | loadcheck | The engine shall treat load-time checks as startup checks only and not as sandboxing | review | - | NOT-AUTOMATED |
| REQ-079 | compile | The engine shall compile each expression once at load using Python compile() | unit_test | tests.requirements.test_loader_api::test_expressions_compiled_once (pass) | PASS |
| REQ-080 | compile | The engine shall evaluate pre-compiled code objects against the context at runtime without recompiling | unit_test | tests.requirements.test_loader_api::test_expressions_compiled_once (pass) | PASS |
| REQ-081 | api | The engine shall be an importable Python package | static_check | tests.requirements.test_static::test_importable_package (pass) | PASS |
| REQ-082 | api | The engine shall provide Engine(model) as its constructor | unit_test | tests.requirements.test_loader_api::test_public_api (pass) | PASS |
| REQ-083 | api | The engine shall provide Engine.step() advancing simulation by one tick | unit_test | tests.requirements.test_loader_api::test_public_api (pass); tests.requirements.test_scenarios::test_run_scenario[minimal] (pass) | PASS |
| REQ-084 | api | The engine shall provide Engine.run(ticks) executing the given number of steps | unit_test | tests.requirements.test_loader_api::test_public_api (pass) | PASS |
| REQ-085 | api | The engine shall provide Engine.snapshot() returning tick, t (float milliseconds), states, outputs and inputs as an independent deep copy | unit_test | tests.requirements.test_behavior::test_snapshot_contents (pass); tests.requirements.test_scenarios::test_run_scenario[minimal] (pass) | PASS |
| REQ-086 | api | The engine shall provide Engine.set_input(name, value) writing an external input | unit_test | tests.requirements.test_loader_api::test_public_api (pass) | PASS |
| REQ-087 | api | The engine shall implement the layered Loader, Scheduler, Evaluator, runtime state and trace hook design | review | - | NOT-AUTOMATED |
| REQ-088 | api | The engine shall keep runtime state consisting of the context, the current state of each state machine and the tick | review | - | NOT-AUTOMATED |
| REQ-089 | outputs | The engine shall expose the current state of every state machine in the snapshot | use_case_test | tests.requirements.test_behavior::test_state_machine_starts_in_default_state (pass); tests.requirements.test_behavior::test_snapshot_contents (pass); tests.requirements.test_scenarios::test_run_scenario[minimal] (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-090 | outputs | The engine shall expose every result_variable value in the snapshot | use_case_test | tests.requirements.test_behavior::test_row_results_updated_every_evaluation (pass); tests.requirements.test_behavior::test_snapshot_contents (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-091 | outputs | The engine shall expose both state machine row and standalone equation result variables in the snapshot | use_case_test | tests.requirements.test_behavior::test_row_results_updated_every_evaluation (pass); tests.requirements.test_behavior::test_snapshot_contents (pass); tests.requirements.test_scenarios::test_run_scenario[reuse_equation] (pass) | PASS |
| REQ-092 | outputs | The engine shall return a snapshot that is a copy so that mutating it does not alter engine state | unit_test | tests.requirements.test_behavior::test_snapshot_is_a_copy (pass) | PASS |
| REQ-093 | outputs | The engine shall reject set_input for a name not defined in the inputs file | unit_test | tests.requirements.test_behavior::test_set_input_unknown_name_raises_keyerror (pass) | PASS |
| REQ-094 | logging | The engine shall provide a trace hook callback recording each state change or result | unit_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass); tests.requirements.test_logging_determinism::test_result_changes_and_set_input_logged (pass) | PASS |
| REQ-095 | logging | The engine shall record a timestamp in each log entry | unit_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass) | PASS |
| REQ-096 | logging | The engine shall record the component name in each log entry | unit_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass) | PASS |
| REQ-097 | logging | The engine shall record an action or state change description in each log entry | unit_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass); tests.requirements.test_logging_determinism::test_result_changes_and_set_input_logged (pass) | PASS |
| REQ-098 | logging | The engine shall record the variable values involved in triggering the state change or action in each log entry | use_case_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass) | PASS |
| REQ-099 | logging | The engine shall support plain text log file output | unit_test | tests.requirements.test_logging_determinism::test_plain_text_log_file (pass) | PASS |
| REQ-100 | logging | The engine shall record a log entry for every state machine state change | use_case_test | tests.requirements.test_logging_determinism::test_state_change_logged_with_context (pass) | PASS |
| REQ-101 | determinism | The engine shall produce identical snapshots for identical runs with identical inputs | use_case_test | tests.requirements.test_logging_determinism::test_identical_runs_identical_snapshots (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[and_rows] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[ap_engage] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[conflict] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[global_transition] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[minimal] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[multirate] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[order_visibility] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[reuse_equation] (pass); tests.unit.test_determinism::test_hash_seed_independent[ap_engage] (pass); tests.unit.test_determinism::test_hash_seed_independent[multirate] (pass); tests.unit.test_determinism::test_hash_seed_independent[reuse_equation] (pass) | PASS |
| REQ-102 | determinism | The engine shall produce identical logs for identical runs with identical inputs | use_case_test | tests.requirements.test_logging_determinism::test_identical_runs_identical_logs (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[and_rows] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[ap_engage] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[conflict] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[global_transition] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[minimal] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[multirate] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[order_visibility] (pass); tests.unit.test_determinism::test_same_scenario_twice_identical[reuse_equation] (pass); tests.unit.test_determinism::test_hash_seed_independent[ap_engage] (pass); tests.unit.test_determinism::test_hash_seed_independent[multirate] (pass); tests.unit.test_determinism::test_hash_seed_independent[reuse_equation] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[and_rows] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[ap_engage] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[conflict] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[global_transition] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[minimal] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[multirate] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[order_visibility] (pass); tests.unit.test_determinism::test_csv_row_order_irrelevant[reuse_equation] (pass) | PASS |
| REQ-103 | determinism | The engine shall not use async or threads | static_check | tests.requirements.test_static::test_no_async_or_threads (pass) | PASS |
| REQ-104 | determinism | The engine shall not use wall-clock time | static_check | tests.requirements.test_static::test_no_wall_clock (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[and_rows] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[ap_engage] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[conflict] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[global_transition] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[minimal] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[multirate] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[order_visibility] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[reuse_equation] (pass) | PASS |
| REQ-105 | determinism | The engine shall not use randomness | static_check | tests.requirements.test_static::test_no_randomness (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[and_rows] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[ap_engage] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[conflict] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[global_transition] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[minimal] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[multirate] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[order_visibility] (pass); tests.unit.test_determinism::test_no_wall_clock_or_random[reuse_equation] (pass) | PASS |
| REQ-106 | determinism | The engine shall be implemented in Python only | static_check | tests.requirements.test_static::test_python_only (pass) | PASS |
| REQ-107 | scope | The engine shall exclude the front end, WebSocket server and orchestration server from the current phase | review | - | NOT-AUTOMATED |
| REQ-108 | scope | The engine shall not provide an event bus or event mechanism | static_check | tests.requirements.test_static::test_no_event_bus (pass) | PASS |
| REQ-109 | scope | The engine shall support command layer and monitoring layer logic using the same equation and state machine mechanisms | use_case_test | tests.requirements.test_behavior::test_command_and_monitoring_layers_same_pass (pass); tests.requirements.test_examples::test_autopilot_climb_capture_hold (pass); tests.requirements.test_examples::test_autopilot_monitor_disconnect_and_interlock (pass); tests.requirements.test_scenarios::test_run_scenario[ap_engage] (pass) | PASS |
| REQ-110 | scope | The engine shall allow a monitoring equation ordered after a command layer item to see its result in the same pass | use_case_test | tests.requirements.test_behavior::test_command_and_monitoring_layers_same_pass (pass); tests.requirements.test_examples::test_autopilot_climb_capture_hold (pass); tests.requirements.test_examples::test_autopilot_monitor_disconnect_and_interlock (pass) | PASS |
| REQ-111 | bands | The engine shall evaluate each state machine at the rate of its band, so a state change can occur only on a pass of that band | use_case_test | tests.requirements.test_rate::test_every_item_runs_exactly_at_its_band_rate_over_long_run (pass); tests.requirements.test_rate::test_state_machine_reacts_only_on_its_band_passes (pass) | PASS |
| REQ-112 | bands | An item shall see an input only when its band runs; an input change that is reverted between two passes of the band is not seen by that item | use_case_test | tests.requirements.test_rate::test_input_pulse_between_passes_is_not_seen_by_slow_band (pass) | PASS |
| REQ-113 | execution | The engine shall keep evaluating every item at its band rate for the whole run, with no drift in evaluation times over long runs | use_case_test | tests.requirements.test_rate::test_every_item_runs_exactly_at_its_band_rate_over_long_run (pass); tests.requirements.test_rate::test_continuous_square_wave_over_long_run (pass); tests.requirements.test_rate::test_rows_track_inputs_continuously_while_state_is_unchanged (pass); tests.requirements.test_rate::test_item_evaluation_times_independent_of_other_bands (pass) | PASS |
| REQ-114 | frontend | The inputs CSV shall accept the optional display columns group, widget, label, min, max, step, choices, lit_by and wide; files without them shall still load | unit_test | tests.unit.test_inputs_display::test_display_columns_are_read (pass); tests.unit.test_inputs_display::test_files_without_display_columns_still_load_with_defaults (pass); tests.unit.test_inputs_display::test_default_widgets (pass) | PASS |
| REQ-115 | frontend | The engine shall support an enum input type whose value is one of the choices column values ('\|'-separated), with the default one of them | unit_test | tests.unit.test_inputs_display::test_enum_choices_and_default (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[e,enum,X,,,,,,,A\|B,,\n-not one of the choices] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[e,enum,A,,,,,,,,,\n-needs choices] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,slider,,,,,,,\n-not allowed for type bool] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,slider,,,,,,,\n-needs min and max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,,,5,5,,,,\n-must be below max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,20,,,,0,10,,,,\n-outside min/max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,float,1,,,,0,10,0,,,\n-step must be > 0] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,,,0,1,,,,\n-int and float inputs only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[s,str,x,,,,,,,A\|B,,\n-enum inputs only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,lit,,,,,,,\n-needs lit_by] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,switch,,,,,,x,\n-lit widget only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,lit,,,,,,nowhere,\n-not a known variable] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,,,,,,,,maybe\n-invalid wide] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,,,x,,,,,\n-invalid min] (pass) | PASS |
| REQ-116 | frontend | The loader shall reject invalid display definitions: a widget not allowed for the type, a slider without min and max, min not below max, a default outside min/max, choices on a non-enum, a lit push-button without lit_by, an unknown lit_by | unit_test | tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[e,enum,X,,,,,,,A\|B,,\n-not one of the choices] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[e,enum,A,,,,,,,,,\n-needs choices] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,slider,,,,,,,\n-not allowed for type bool] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,slider,,,,,,,\n-needs min and max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,,,5,5,,,,\n-must be below max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,20,,,,0,10,,,,\n-outside min/max] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,float,1,,,,0,10,0,,,\n-step must be > 0] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,,,0,1,,,,\n-int and float inputs only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[s,str,x,,,,,,,A\|B,,\n-enum inputs only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,lit,,,,,,,\n-needs lit_by] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,switch,,,,,,x,\n-lit widget only] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,lit,,,,,,nowhere,\n-not a known variable] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[b,bool,false,,,,,,,,,maybe\n-invalid wide] (pass); tests.unit.test_inputs_display::test_invalid_display_definitions_are_rejected[n,int,1,,,,x,,,,,\n-invalid min] (pass); tests.unit.test_inputs_display::test_lit_by_may_name_an_equation_result (pass) | PASS |
| REQ-117 | frontend | A local Python server shall run a model given its master CSV on the command line, serve the page over HTTP and exchange values with it over a WebSocket; the engine runs only in Python | use_case_test | tests.frontend.test_server::test_command_line_server_serves_page_and_files (pass); tests.frontend.test_server::test_websocket_sends_model_then_state_and_applies_messages (pass) | PASS |
| REQ-118 | frontend | The server shall be a separate package so the engine package stays free of async code and wall-clock time | static_check | tests.requirements.test_static::test_engine_does_not_depend_on_the_server (pass) | PASS |
| REQ-119 | frontend | The page shall build its input cards and state machine cards from the loaded model, with no per-model code | use_case_test | tests.frontend.test_browser::test_layout_built_from_model (pass); tests.frontend.test_server::test_websocket_sends_model_then_state_and_applies_messages (pass); tests.unit.test_session::test_describe_model_layout (pass) | PASS |
| REQ-120 | frontend | The page shall show the state machines in master CSV row order, and each machine's states in the order of its CSV file | use_case_test | tests.frontend.test_browser::test_layout_built_from_model (pass); tests.unit.test_session::test_describe_model_layout (pass); tests.unit.test_session::test_self_transitions_are_not_next_states (pass) | PASS |
| REQ-121 | frontend | The page shall highlight the active state of every state machine, exactly one per machine, and follow state changes while running | use_case_test | tests.frontend.test_browser::test_layout_built_from_model (pass); tests.frontend.test_browser::test_push_button_pulse_moves_the_state_machine (pass) | PASS |
| REQ-122 | frontend | Hovering over or focusing the active state shall highlight its next states (global transition targets dashed); hovering over an inactive state shall do nothing; highlighting shall not move or resize anything | use_case_test | tests.frontend.test_browser::test_hover_active_highlights_next_states_without_moving_anything (pass) | PASS |
| REQ-123 | frontend | The page shall not show equations, conditions, transitions, band rates, simulation time or tick | use_case_test | tests.frontend.test_browser::test_no_equations_rates_or_time_on_screen (pass) | PASS |
| REQ-124 | frontend | The page shall show one input card per input group, titled with the group name, with the group's inputs in CSV order | use_case_test | tests.frontend.test_browser::test_layout_built_from_model (pass); tests.unit.test_session::test_describe_model_layout (pass) | PASS |
| REQ-125 | frontend | Switches, sliders, number fields, drop-downs and text fields shall write their input; the server shall check type, min/max and choices and reject other values | use_case_test | tests.frontend.test_browser::test_widgets_write_inputs (pass); tests.unit.test_session::test_set_writes_valid_values (pass); tests.unit.test_session::test_set_rejects_invalid_values[radio_altitude-3000] (pass); tests.unit.test_session::test_set_rejects_invalid_values[radio_altitude--5] (pass); tests.unit.test_session::test_set_rejects_invalid_values[radio_altitude-2.5] (pass); tests.unit.test_session::test_set_rejects_invalid_values[radio_altitude-high] (pass); tests.unit.test_session::test_set_rejects_invalid_values[radio_altitude-True] (pass); tests.unit.test_session::test_set_rejects_invalid_values[capa-LAND9] (pass); tests.unit.test_session::test_set_rejects_invalid_values[fd_on-1] (pass); tests.unit.test_session::test_set_rejects_invalid_values[nope-True] (pass); tests.unit.test_session::test_set_rejects_invalid_values[toga-True] (pass) | PASS |
| REQ-126 | frontend | A push-button press shall hold its input true for one period of the slowest band and then set it false | use_case_test | tests.frontend.test_browser::test_push_button_pulse_moves_the_state_machine (pass); tests.unit.test_session::test_press_holds_input_for_one_slowest_band_period (pass) | PASS |
| REQ-127 | frontend | A lit push-button shall be lit while its lit_by variable is true and unlit otherwise; the click alone shall not light it | use_case_test | tests.frontend.test_browser::test_lit_push_button_follows_the_logic (pass); tests.unit.test_session::test_lit_follows_its_variable_not_the_click (pass) | PASS |
| REQ-128 | frontend | The run controls shall offer real time and as fast as possible; in real time the server shall run ticks at the model tick rate against the wall clock | use_case_test | tests.frontend.test_browser::test_run_controls (pass); tests.frontend.test_server::test_real_time_paces_ticks_to_the_tick_rate (pass); tests.frontend.test_server::test_fast_mode_runs_faster_and_updates_at_most_30_per_second (pass); tests.unit.test_session::test_mode_pause_resume_step (pass) | PASS |
| REQ-129 | frontend | Pause shall stop the engine and become Resume; Step shall run one tick and be available only while paused | use_case_test | tests.frontend.test_browser::test_run_controls (pass); tests.unit.test_session::test_mode_pause_resume_step (pass) | PASS |
| REQ-130 | frontend | Reset shall return every input, state and result to its start value, keeping the loaded model, the run mode and the pause state | use_case_test | tests.frontend.test_browser::test_run_controls (pass); tests.unit.test_session::test_reset_keeps_model_mode_and_pause (pass) | PASS |
| REQ-131 | frontend | The server shall send screen updates at most 30 times per second while running | use_case_test | tests.frontend.test_server::test_fast_mode_runs_faster_and_updates_at_most_30_per_second (pass) | PASS |
| REQ-132 | frontend | The splitter shall resize the two panes by dragging or with the arrow keys (20 px), keeping the left pane at least 280 px and the right pane at least 240 px | use_case_test | tests.frontend.test_browser::test_splitter_resizes_panes (pass) | PASS |
| REQ-133 | frontend | Names from the CSV files shall be shown as text, never interpreted as HTML | use_case_test | tests.frontend.test_browser::test_names_are_shown_as_text (pass) | PASS |
| REQ-134 | frontend | The server shall listen on 127.0.0.1 by default | unit_test | tests.unit.test_session::test_server_listens_on_localhost_by_default (pass) | PASS |
| REQ-135 | frontend | Momentary push-buttons shall have a light grey fill and a dark outline; every push-button shall show visible feedback while held and for 0.3 s after each press | use_case_test | tests.frontend.test_browser::test_push_button_look_and_press_feedback (pass) | PASS |

## 4. Orphan tests (no requirement property)

- `tests.requirements.test_scenarios::test_error_scenario[bad_dup_result_var]` (requirement, pass)
- `tests.unit.test_determinism::test_run_scenarios_found` (unit, pass)
- `tests.unit.test_determinism::test_shuffle_candidates_checked` (unit, pass)
- `tests.unit.test_engine::test_tick_t_dt_math` (unit, pass)
- `tests.unit.test_engine::test_reserved_names_in_context` (unit, pass)
- `tests.unit.test_engine::test_initial_state_and_inputs` (unit, pass)
- `tests.unit.test_engine::test_set_input_and_unknown` (unit, pass)
- `tests.unit.test_engine::test_snapshot_is_fresh` (unit, pass)
- `tests.unit.test_engine::test_trace_emission` (unit, pass)
- `tests.unit.test_engine::test_one_transition_per_pass_and_no_short_circuit` (unit, pass)
- `tests.unit.test_engine::test_global_self_transition_is_noop_and_wins` (unit, pass)
- `tests.unit.test_evaluator::test_truthiness_of_plain_values` (unit, pass)
- `tests.unit.test_evaluator::test_result_is_always_bool` (unit, pass)
- `tests.unit.test_evaluator::test_and_or_not` (unit, pass)
- `tests.unit.test_evaluator::test_comparisons_numeric` (unit, pass)
- `tests.unit.test_evaluator::test_string_equality_for_state` (unit, pass)
- `tests.unit.test_evaluator::test_string_inequality_and_single_quotes` (unit, pass)
- `tests.unit.test_evaluator::test_surrounding_whitespace_is_stripped` (unit, pass)
- `tests.unit.test_evaluator::test_builtins_are_available` (unit, pass)
- `tests.unit.test_evaluator::test_context_is_used_not_copied` (unit, pass)
- `tests.unit.test_evaluator::test_syntax_error_raises_model_error_with_source` (unit, pass)
- `tests.unit.test_evaluator::test_empty_expression_raises_model_error` (unit, pass)
- `tests.unit.test_evaluator::test_undefined_name_raises_name_error` (unit, pass)
- `tests.unit.test_evaluator::test_names_used_sorted_and_unique` (unit, pass)
- `tests.unit.test_evaluator::test_names_used_includes_comprehension_names` (unit, pass)
- `tests.unit.test_evaluator::test_names_used_empty_for_constant` (unit, pass)
- `tests.unit.test_loader::test_full_model` (unit, pass)
- `tests.unit.test_loader::test_no_equations_or_inputs_rows` (unit, pass)
- `tests.unit.test_loader::test_empty_master_gives_tick_1` (unit, pass)
- `tests.unit.test_loader::test_bom_whitespace_and_extra_columns_crlf` (unit, pass)
- `tests.unit.test_loader::test_master_order_and_fraction_orders` (unit, pass)
- `tests.unit.test_loader::test_paths_relative_to_master_dir` (unit, pass)
- `tests.unit.test_loader::test_input_default_parsing` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,bool,maybe]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,bool,]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,int,1.5]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,int,x]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,float,abc]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,float,]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,list,[1]]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,,1]` (unit, pass)
- `tests.unit.test_loader::test_input_default_bad_value_or_type[a,Int,1]` (unit, pass)
- `tests.unit.test_loader::test_master_missing_column` (unit, pass)
- `tests.unit.test_loader::test_empty_master_file` (unit, pass)
- `tests.unit.test_loader::test_unknown_type` (unit, pass)
- `tests.unit.test_loader::test_sm_row_requires_order` (unit, pass)
- `tests.unit.test_loader::test_missing_listed_file` (unit, pass)
- `tests.unit.test_loader::test_two_equations_rows` (unit, pass)
- `tests.unit.test_loader::test_two_inputs_rows` (unit, pass)
- `tests.unit.test_loader::test_duplicate_sm_name` (unit, pass)
- `tests.unit.test_loader::test_missing_sm_column` (unit, pass)
- `tests.unit.test_loader::test_missing_equations_and_inputs_column` (unit, pass)
- `tests.unit.test_loader::test_syntax_error_in_sm_equation` (unit, pass)
- `tests.unit.test_loader::test_syntax_error_in_standalone_equation` (unit, pass)
- `tests.unit.test_loader::test_statement_not_expression_is_error` (unit, pass)
- `tests.unit.test_loader::test_empty_equation_and_result_variable` (unit, pass)
- `tests.unit.test_loader::test_transition_id_disagreement` (unit, pass)
- `tests.unit.test_loader::test_empty_transition_id_and_next_state` (unit, pass)
- `tests.unit.test_loader::test_unknown_state` (unit, pass)
- `tests.unit.test_loader::test_global_transition_does_not_need_current_state` (unit, pass)
- `tests.unit.test_loader::test_no_default_state` (unit, pass)
- `tests.unit.test_loader::test_empty_sm_file_fails` (unit, pass)
- `tests.unit.test_loader::test_two_default_states` (unit, pass)
- `tests.unit.test_loader::test_mixed_bands_in_sm` (unit, pass)
- `tests.unit.test_loader::test_bad_band[0]` (unit, pass)
- `tests.unit.test_loader::test_bad_band[-5]` (unit, pass)
- `tests.unit.test_loader::test_bad_band[abc]` (unit, pass)
- `tests.unit.test_loader::test_bad_band[]` (unit, pass)
- `tests.unit.test_loader::test_bad_band[1/0]` (unit, pass)
- `tests.unit.test_loader::test_bad_band_standalone_and_bad_order` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[tick]` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[t]` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[dt]` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[1abc]` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[a b]` (unit, pass)
- `tests.unit.test_loader::test_bad_result_variable_names[a-b]` (unit, pass)
- `tests.unit.test_loader::test_bad_input_names[tick]` (unit, pass)
- `tests.unit.test_loader::test_bad_input_names[t]` (unit, pass)
- `tests.unit.test_loader::test_bad_input_names[dt]` (unit, pass)
- `tests.unit.test_loader::test_bad_input_names[9x]` (unit, pass)
- `tests.unit.test_loader::test_bad_input_names[a b]` (unit, pass)
- `tests.unit.test_loader::test_duplicate_result_variable_across_files` (unit, pass)
- `tests.unit.test_loader::test_duplicate_result_variable_within_equations` (unit, pass)
- `tests.unit.test_loader::test_duplicate_result_variable_within_sm` (unit, pass)
- `tests.unit.test_loader::test_duplicate_input_names` (unit, pass)
- `tests.unit.test_loader::test_input_clashes_with_result_variable` (unit, pass)
- `tests.unit.test_loader::test_sm_name_clashes_with_input_and_result` (unit, pass)
- `tests.unit.test_loader::test_sm_name_must_be_identifier_and_not_reserved` (unit, pass)
- `tests.unit.test_loader::test_max_state_machines` (unit, pass)
- `tests.unit.test_loader::test_max_equations_counts_sm_rows_and_standalone` (unit, pass)
- `tests.unit.test_loader::test_error_str_format` (unit, pass)
- `tests.unit.test_report::test_parse_junit_outcomes_and_messages` (unit, pass)
- `tests.unit.test_report::test_parse_junit_reads_req_properties_in_order` (unit, pass)
- `tests.unit.test_report::test_parse_junit_accepts_bytes_and_single_testsuite_root` (unit, pass)
- `tests.unit.test_report::test_load_junit_from_file` (unit, pass)
- `tests.unit.test_report::test_node_id` (unit, pass)
- `tests.unit.test_report::test_classify[tests.requirements.test_req--requirement]` (unit, pass)
- `tests.unit.test_report::test_classify[tests.unit.test_a-tests/requirements/test_a.py-requirement]` (unit, pass)
- `tests.unit.test_report::test_classify[tests.unit.test_a-tests\\requirements\\test_a.py-requirement]` (unit, pass)
- `tests.unit.test_report::test_classify[tests.unit.test_a--unit]` (unit, pass)
- `tests.unit.test_report::test_classify[tests.unit.test_trace-tests/unit/test_trace.py-unit]` (unit, pass)
- `tests.unit.test_report::test_parse_requirements_handles_quoted_commas_and_strips_fields` (unit, pass)
- `tests.unit.test_report::test_parse_requirements_skips_blank_ids_and_strips_whitespace` (unit, pass)
- `tests.unit.test_report::test_parse_requirements_missing_column_raises` (unit, pass)
- `tests.unit.test_report::test_load_requirements_with_bom` (unit, pass)
- `tests.unit.test_report::test_summary_counts_split_unit_and_requirement` (unit, pass)
- `tests.unit.test_report::test_requirement_statuses` (unit, pass)
- `tests.unit.test_report::test_skip_only_requirement_is_skip` (unit, pass)
- `tests.unit.test_report::test_failures_and_orphans` (unit, pass)
- `tests.unit.test_report::test_unknown_req_ids_reported` (unit, pass)
- `tests.unit.test_report::test_render_markdown_sections_and_content` (unit, pass)
- `tests.unit.test_report::test_render_markdown_escapes_pipes_in_table` (unit, pass)
- `tests.unit.test_report::test_render_markdown_no_failures_and_no_orphans` (unit, pass)
- `tests.unit.test_report::test_render_html_is_escaped_and_complete` (unit, pass)
- `tests.unit.test_report::test_main_writes_markdown_and_html` (unit, pass)
- `tests.unit.test_report::test_main_without_html_writes_only_markdown` (unit, pass)
- `tests.unit.test_report::test_main_missing_junit_returns_error` (unit, pass)
- `tests.unit.test_scheduler::test_tick_hz_and_periods_for_20_and_30_hz` (unit, pass)
- `tests.unit.test_scheduler::test_higher_frequency_band_sorts_first_regardless_of_order` (unit, pass)
- `tests.unit.test_scheduler::test_order_within_band_ascending_not_declaration_order` (unit, pass)
- `tests.unit.test_scheduler::test_ties_broken_by_master_row_then_csv_row` (unit, pass)
- `tests.unit.test_scheduler::test_equations_and_state_machines_share_order_space` (unit, pass)
- `tests.unit.test_scheduler::test_equation_expanded_to_one_item_per_equation_with_kind` (unit, pass)
- `tests.unit.test_scheduler::test_build_schedule_is_deterministic` (unit, pass)
- `tests.unit.test_scheduler::test_due_items_20_and_30_hz_over_first_six_ticks` (unit, pass)
- `tests.unit.test_scheduler::test_due_items_preserves_schedule_order` (unit, pass)
- `tests.unit.test_scheduler::test_due_items_empty_schedule` (unit, pass)
- `tests.unit.test_scheduler::test_due_items_rejects_tick_below_one` (unit, pass)
- `tests.unit.test_scheduler::test_non_integer_period_raises` (unit, pass)
- `tests.unit.test_scheduler::test_fractional_band_frequency_period` (unit, pass)
- `tests.unit.test_trace::test_format_value_str_uses_repr` (unit, pass)
- `tests.unit.test_trace::test_format_value_fraction_is_six_decimals` (unit, pass)
- `tests.unit.test_trace::test_format_value_other_types_use_str` (unit, pass)
- `tests.unit.test_trace::test_format_value_int_is_not_fraction_formatted` (unit, pass)
- `tests.unit.test_trace::test_format_event_matches_decisions_example` (unit, pass)
- `tests.unit.test_trace::test_format_event_without_values_has_no_trailing_separator` (unit, pass)
- `tests.unit.test_trace::test_format_event_has_no_newline` (unit, pass)
- `tests.unit.test_trace::test_format_event_tick_is_zero_padded_to_six` (unit, pass)
- `tests.unit.test_trace::test_format_event_time_uses_three_decimals_exact_fraction` (unit, pass)
- `tests.unit.test_trace::test_format_event_values_rendered_in_given_order_with_types` (unit, pass)
- `tests.unit.test_trace::test_format_event_input_action_line` (unit, pass)
- `tests.unit.test_trace::test_list_sink_starts_empty` (unit, pass)
- `tests.unit.test_trace::test_list_sink_keeps_events_in_emission_order` (unit, pass)
- `tests.unit.test_trace::test_list_sink_lines_match_format_event` (unit, pass)
- `tests.unit.test_trace::test_list_sink_satisfies_protocol_by_duck_typing` (unit, pass)
- `tests.unit.test_trace::test_file_writer_writes_one_line_per_event` (unit, pass)
- `tests.unit.test_trace::test_file_writer_uses_lf_newlines` (unit, pass)
- `tests.unit.test_trace::test_file_writer_flushes_on_each_emit` (unit, pass)
- `tests.unit.test_trace::test_file_writer_truncates_existing_file` (unit, pass)
- `tests.unit.test_trace::test_file_writer_context_manager_closes_file` (unit, pass)
- `tests.unit.test_trace::test_file_writer_close_is_idempotent` (unit, pass)
- `tests.unit.test_trace::test_file_writer_is_utf8` (unit, pass)
- `tests.unit.test_trace::test_file_writer_is_deterministic` (unit, pass)
