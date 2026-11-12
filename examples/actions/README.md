# Actions: writing variables from state machines

A small phase-of-flight machine that moves the sliders by itself.

| When | Action | Effect |
|---|---|---|
| First pass (master `init_action`) | `START` | `ground_speed = 0` |
| Ground -> Takeoff (TOGA), entry | `TAKEOFF_ROLL` | `ground_speed = 140` |
| Takeoff -> Climb (radio_altitude > 400), entry | `CLIMB_INIT` | `ground_speed = 0`, `climb_ticks = 0` |
| While in Climb, during | `CLIMB_TIMER` | `climb_ticks += 1` (Cruise after 50 passes = 5 s) |
| Cruise -> Ground (radio_altitude == 0), exit | `LANDING` | `ground_speed = 60` |

`climb_ticks` is an internal variable: an input with widget `none`, so it has
no card. The sliders can still be moved by hand at any time.

Run it: `python -m statesim_server examples/actions/master.csv`
