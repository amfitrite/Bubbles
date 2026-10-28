import bisect

# Standard ladder in milliseconds as per README specification
TIME_LADDER_MS = [
    25, 50, 100, 250, 500,           # Sub-second
    1_000, 2_000, 5_000, 10_000,     # Seconds
    15_000, 30_000,                  # Seconds
    60_000, 120_000, 300_000,        # 1m, 2m, 5m
    600_000, 900_000, 1_800_000,     # 10m, 15m, 30m
    3_600_000, 7_200_000,            # 1h, 2h
    14_400_000, 21_600_000,          # 4h, 6h
    43_200_000, 86_400_000           # 12h, 1d
]

# Multiple multipliers for tick size ladder
TICK_MULTIPLIERS = [
    1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000
]

def nice_time_step(target_ms: float) -> int:
    """
    Selects the closest nice time step from the ladder for target_ms.
    """
    if target_ms <= TIME_LADDER_MS[0]:
        return TIME_LADDER_MS[0]
    if target_ms >= TIME_LADDER_MS[-1]:
        return TIME_LADDER_MS[-1]

    idx = bisect.bisect_left(TIME_LADDER_MS, target_ms)
    if idx == 0:
        return TIME_LADDER_MS[0]
    
    # Compare which one is closer
    prev_val = TIME_LADDER_MS[idx - 1]
    curr_val = TIME_LADDER_MS[idx]
    if (target_ms - prev_val) < (curr_val - target_ms):
        return prev_val
    return curr_val

def nice_tick_step(target_step: float, tick_size: float = 0.01) -> float:
    """
    Selects a clean multiple of tick_size based on target_step.
    """
    if tick_size <= 0:
        tick_size = 0.01
    
    target_multiplier = max(1.0, target_step / tick_size)
    idx = bisect.bisect_left(TICK_MULTIPLIERS, target_multiplier)
    if idx >= len(TICK_MULTIPLIERS):
        multiplier = TICK_MULTIPLIERS[-1]
    elif idx == 0:
        multiplier = TICK_MULTIPLIERS[0]
    else:
        prev_m = TICK_MULTIPLIERS[idx - 1]
        curr_m = TICK_MULTIPLIERS[idx]
        multiplier = prev_m if (target_multiplier - prev_m) < (curr_m - target_multiplier) else curr_m

    return round(multiplier * tick_size, 6)
