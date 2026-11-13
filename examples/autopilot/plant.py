"""Very simple aircraft vertical model closing the loop around the AP example.

Not part of the engine: external software reads the engine outputs, computes
the aircraft response and writes it back with set_input, once per tick.
"""

CLIMB_FPM = 1500.0      # vertical speed commanded in VS and ALT_ARMED
GAIN = 10.0             # fpm per ft of altitude error in ALT_CAP / ALT_HOLD


def plant_step(eng, dt_s):
    """Advance the aircraft by dt_s seconds according to the AP mode."""
    s = eng.snapshot()
    mode, i = s["states"]["AP"], s["inputs"]
    if mode in ("VS", "ALT_ARMED"):
        vs = CLIMB_FPM
    elif mode in ("ALT_CAP", "ALT_HOLD"):
        vs = max(-CLIMB_FPM, min(CLIMB_FPM, GAIN * (i["sel_alt"] - i["alt"])))
    else:                                   # OFF / DISC_WARN: level flight
        vs = 0.0
    eng.set_input("vs", vs)
    eng.set_input("alt", i["alt"] + vs / 60.0 * dt_s)
