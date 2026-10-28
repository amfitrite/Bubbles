from src.util.math_utils import lerp, smoothstep, clamp
from src.util.time_utils import nice_time_step, nice_tick_step

class LODSelector:
    """
    Computes dynamic level of detail (LOD) based on the camera time span and price range.
    """
    TRANSITION_START_MS = 5 * 60_000.0    # 5 minutes
    TRANSITION_END_MS = 30 * 60_000.0     # 30 minutes

    @classmethod
    def calculate(cls, time_span_ms: float, price_range: float, tick_size: float = 0.01):
        """
        Returns:
            bucket_ms (int): Time grouping bucket in ms.
            price_bin (float): Price grouping step.
            macro_weight (float): 0.0 (Pure Micro) to 1.0 (Pure Macro).
            target_rows (int): Expected price rows in viewport.
        """
        # 1. Bucket step targeting approx ~120 columns across canvas
        target_bucket_ms = max(25.0, time_span_ms / 120.0)
        bucket_ms = nice_time_step(target_bucket_ms)

        # 2. Macro weight transition (0.0 at <=5m, 1.0 at >=30m)
        macro_weight = smoothstep(
            time_span_ms,
            cls.TRANSITION_START_MS,
            cls.TRANSITION_END_MS
        )

        # 3. Target rows shrink from 24 down to 4 as we zoom out
        target_rows = int(round(lerp(24, 4, macro_weight)))
        target_rows = max(2, target_rows)

        # 4. Price bin step
        target_step = price_range / float(target_rows)
        price_bin = nice_tick_step(target_step, tick_size)

        return bucket_ms, price_bin, macro_weight, target_rows
