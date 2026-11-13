# Autopilot 2: A220 autoland demo

Converted from `A220_demo.json`, a system file of the previous tool. The JSON
is kept for reference; the tool runs the CSV files: `master.csv`.

| JSON machine | State machine file (= state variable) | Display name (master `name`) | Master order |
|---|---|---|---|
| AC phase of flight | `state_ac.csv` | Aircraft phase of flight | 20 |
| Vertical Modes | `state_vert.csv` | Vertical guidance | 30 |
| Lateral Modes | `state_lat.csv` | Lateral guidance | 40 |
| Guidance Source | `guidance_src.csv` | Guidance source | 10 |
| Autothrottle | `state_at.csv` | Autothrust | 50 |

The previous tool kept copies of the states in variables (`state_ac`,
`state_vert`, `state_lat`, `state_at`). The machines are named after those
variables, so the conditions that read them are unchanged. The master rows
keep the JSON order (screen order); the `order` column runs Guidance Source
first so `ifcc_in_control` is up to date when the other machines read it.

## How the conversion was done

- Everything runs in one 10 Hz band (state machine bands in `master.csv`).
- Each `event` became one transition. Its top-level `and` terms became
  separate rows of that transition (ANDed); a condition with a top-level `or`
  stays one row. Row results are named `<machine>_<transition>_<row>`.
- Transitions `T1`, `T2`, ... are the state transitions in JSON order; `G1`,
  `G2`, ... the global transitions. Globals get the lowest `order` numbers, so
  they win over the state's own transitions, as in the previous tool.
- `action` became `title`; `rationale` became `rationale`.
- Buttons became `bool` inputs shown as momentary push-buttons; `capa` is an
  `enum` input (default `LAND3`). The JSON's min, max, step and choices are in
  the inputs CSV display columns, and the inputs are grouped into cards like
  the previous tool's panels.

Run it with the front end: `python -m statesim_server examples/autopilot2/master.csv`.

## Flight control panel (`fcp.html`)

Shown in the top pane (based on `testFCP.html`). `fd_on` (both FD buttons),
`ap_on` and `appr_selected` (APPR) are toggle buttons there, and EDM is a
momentary button, so they have no card on the left. The other buttons (HDG,
NAV, AT, XFR, FLC, ALT, VNAV, VS, FPA) and the four knobs (SPD, HDG, ALT, VS)
are new inputs the logic does not use yet. The panel is shown at 3/4 size
(`scale` 0.75 in `master.csv`).

The APPR light (`appr_light` in `equations.csv`, order 15) comes on when APPR
is selected while the phase of flight is Descent, and stays on until the phase
of flight is Landed or Waiting TOGA (or Reset). It reads its own previous value
to stay on, and runs before the phase of flight machine (order 20) so it still
sees Descent on the pass where Descent changes to Approach. The other buttons
have no light yet.

## Behaviour that changed

The new tool never writes variables from transitions (`set_vars` is gone).

**Replaced by equations** (`equations.csv`):

| Variable | Now computed as |
|---|---|
| `ifcc_in_control` | `guidance_src == 'IFCC'` |
| `ifcc_in_control_prev` | `ifcc_in_control` from the previous pass, so "IFCC just released control" is true for one pass |
| `on_ground` | `radio_altitude == 0` |
| `rollout_active` | `state_lat == 'Rollout'` |
| `at_on` | `state_at != 'Idle'` |

**No longer written by the logic; the user sets them as inputs:**

- `fd_on`, `ap_on`: were switched on at takeoff and climb, and off when landed.
- `appr_selected`, `dmc_tracking_loc`, `dmc_tracking_gs`: were cleared on go
  around, on IFCC taking or releasing control, and at the end of rollout. If
  they stay true after IFCC hands back to DMC, the lateral and vertical modes
  re-arm (`preLocTrk`, `preGsTrk`).
- `claws_req_flare`: was cleared on nosedown.
- `ground_time_gt_2s`: was cleared at takeoff and on GS capture.
- `ground_speed`, `radio_altitude`: were set to 140 or 0 at touchdown.

**Fixed in the JSON while converting:**

- `ifcc_guidance` (Flare_Armed to GsTrk) was never declared, so that condition
  would fail; it now reads `ifcc_in_control`.

Kept as in the JSON, worth a look: Autothrottle's global transition title
("resetting ifcc_in_control_prev to False") looks copied from Guidance
Source; `preGsTrk` has a test transition on `state_vert == 'mp'` that can never
be true.
