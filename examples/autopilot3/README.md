# Autopilot 3: autoland with actions

Converted from `ap.json`, the latest system file of the previous tool. That
file is not part of the repository. Unlike `autopilot2`, this conversion keeps
the previous tool's `set_vars`: each one became an **action** (see
`docs/decisions.md` Part C). So the logic writes variables itself, for example:
- the speed goes back to 0 at climb;
- FD, AP and AT engage and disengage;
- the CLAWS tracking requests are cleared;
- `on_ground` is set at touchdown.

Run it: `python -m statesim_server examples/autopilot3/master.csv`

| JSON machine | State machine file (= state variable) | Master order |
|---|---|---|
| Aircraft | `state_ac.csv` | 10 |
| FD engage | `state_fd.csv` | 20 |
| AP engage | `state_ap.csv` | 30 |
| Vertical Modes | `state_vert.csv` | 40 |
| Lateral Modes | `state_lat.csv` | 50 |
| Guidance Source | `guidance_src.csv` | 60 |
| Autothrottle | `state_at.csv` | 70 |

The display names on the front end are the JSON machine names.

## How the conversion was done

- **Evaluation order:** everything runs in one 10 Hz band, in JSON order. This
  is assumed to be the previous tool's order. It matters because the logic now
  writes variables: for example, Guidance Source's one-pass
  `ifcc_in_control_prev` pulse is seen by Vertical and Lateral Modes, which run
  before it.
- **Transitions and rows:**
  - Each `event` became one transition. Its top-level `and` terms became
    separate rows of that transition, which are ANDed. A condition with a
    top-level `or` stays one row. Row results are named
    `<machine>_<transition>_<row>`.
  - `T1`, `T2`, ... are the state transitions, in JSON order; `G1`, `G2`, ...
    are the global transitions. Globals get the lowest `order` numbers, so they
    win over the state's own transitions.
  - `action` became `title`, and `rationale` became `rationale`.
- **Actions:** each transition's `set_vars` became an `entry` action named
  `<MACHINE>_<transition>` (in `actions.csv`), with the writes in JSON order.
  Transitions of the same machine with the same writes share one action, named
  after the first, for example `STATE_FD_T1` for all three ways FD engages. A
  machine writing its own state variable (`state_ac = 'Climb'`) is dropped,
  because the transition already sets it.
- **Variables:** the separators became input groups (cards).
  - `int` became a slider, `enum` a dropdown and `bool` a switch.
  - `button` became a momentary push-button.
  - `StateButton` became a button on the flight control panel, lit by its
    state variable: `FD_btn` is lit by `fd_on`, and likewise for AP, AT and
    APPR (see below).
  - `var` variables and the state variables of the StateButtons (`on_ground`,
    `rollout_active`, `ifcc_in_control`, `ifcc_in_control_prev`, `fd_on`,
    `ap_on`, `at_on`, `appr_on`) are internal variables, with widget `none`.
  - `state_*` variables are the state machines themselves.
- **FMA (`fma_logic`) became Boolean equations** (`equations.csv`, after all
  the machines), one per line of each field. For example, `fma_tm_engaged_spd`
  is true while the TM engaged field shows "SPD". The first matching line wins,
  as in the previous tool: each line is ANDed with "no earlier line of this
  field". The FMA panel shows them (see below).

## Flight control panel (`fcp.html`)

This is the panel from `autopilot2`, shown in the top pane at 3/4 size
(`scale` 0.75), with its buttons rebound to this model:

| Button | Input (momentary) | Light (`data-lit-by`) |
|---|---|---|
| FD (both) | `FD_btn` | `fd_on` |
| AP | `AP_btn` | `ap_on` |
| AT | `AT_btn` | `at_on` |
| APPR | `APPR_btn` | `appr_on` |

As in the previous tool, a press is a momentary pulse and the logic decides
the light. For example, FD also comes on by itself with AP or TOGA, and its
light follows. These four buttons therefore have no card on the left.

The other buttons (HDG, NAV, XFR, EDM, FLC, ALT, VNAV, VS, FPA) and the four
knobs (SPD, HDG, ALT, VS) are inputs the logic does not use, as in
`autopilot2`.

## Flight mode annunciator (`fma.html`)

The previous tool's FMA strip, on the right of the FCP in the top pane (also
at 3/4 size). It is generated from `fma_logic`. Each mode text is lit by its
FMA equation and is shown only while lit; because each field is first-match,
at most one text shows per slot.

| Thrust | Lateral | Engage | Vertical |
|---|---|---|---|
| `TM_engaged` | `LNAV_engaged_1`, `LNAV_engaged_2` | AP (`ap_visible`) | `VNAV_engaged_1` |
| `TM_armed` | `LNAV_armed_1`, `LNAV_armed_2` | AT (`at_color`) | `VNAV_armed_1`, `_2`, `_3` |

- **Colours:** engaged modes (top row) are green and armed modes (bottom row)
  white. AP is green. AT is green, or white when `at_color` says white
  (autothrottle Hold armed).
- **The arrow:** the white AP <- AT arrow between AP and AT has no rule in
  `fma_logic`. It's the extra equation `fma_ap_at_arrow`, true while both AP
  and AT are shown.

## Behaviour that changed

**Fixed in the JSON while converting:**
- `ifcc_guidance` (Vertical Modes T9, Flare_Armed to GsTrk) was never
  declared. Every row is evaluated on every pass, so the model would stop on
  the first pass. It now reads `ifcc_in_control`.
- Vertical Modes T15 (Flare_Active, TOGA) went to `'Go Around'`, which is not
  a vertical state. It now goes to `Go_Around`.

**Where the new tool works differently:**
- **Guidance Source G1** (`ifcc_in_control_prev = False`) is a global
  transition to DMC that only fires while the machine is already in DMC. In
  the new tool, a global transition to the current state does nothing, so its
  write is now the `during` action of DMC (`GUIDANCE_SRC_G1`). It runs on the
  pass after IFCC hands back to DMC, so the pulse still lasts one pass. G1 is
  kept and still wins its pass, as before.
- **A transition's `set_vars` set a state that differs from its
  `next_state`:**
  - Lateral Modes T10 and T12 (`state_lat = 'Rollout'`, going to
    No_Lateral_State).
  - Autothrottle T8 (`state_at = 'Active'`, going to Idle).

  In the new tool the state variable *is* the machine's state, so the
  `next_state` wins.
- **Lateral Modes T11** wrote `state_vert = 'No_Lateral_State'`. That write is
  dropped: only the vertical machine can change its own state.

## Worth a look (kept as in the JSON)

- **FMA `LNAV_engaged_2` "LOC":** it reads
  `(state_ac == 'Approach', 'Final Approach')`. That's a tuple, which is
  always true; `state_ac in [...]` was probably meant.
- **Duplicate transitions:** AP engage T3 and T4 are the same transition
  (`law_AP == False`).
- **Copied titles:**
  - Lateral Modes LocTrk to Roll mentions GS and Pitch.
  - Autothrottle G1's title talks about `ifcc_in_control_prev`.
- **Operator precedence:** Guidance Source T2 reads
  `(radio_altitude > 200) and (TOGA == True) or (...)`, which means
  `(A and B) or C`.
- **Switches the logic clears:** Guidance Source clears `dmc_tracking_loc` and
  `dmc_tracking_gs` when IFCC takes control, so those switches flip back by
  themselves.
- **AP and FD after landing:** `ap_on` and `fd_on` stay on after landing.
  Nothing in the JSON turns them off, apart from the buttons and `APdisc`.
