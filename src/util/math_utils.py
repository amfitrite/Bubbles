import numpy as np

def clamp(val, min_val, max_val):
    """Clamps a numeric value between min_val and max_val."""
    return max(min_val, min(max_val, val))

def lerp(a, b, t):
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t

def smoothstep(x, edge0=0.0, edge1=1.0):
    """
    Standard smoothstep function.
    Clamps x to [0, 1] and applies Hermite interpolation 3x^2 - 2x^3.
    """
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def robust_p95(volumes, min_sample=3):
    """
    Computes robust 95th percentile of volume array.
    If sample size is below min_sample, returns fallback.
    """
    if len(volumes) < min_sample:
        return 1.0 if len(volumes) == 0 else max(1.0, float(np.max(volumes)))
    val = float(np.percentile(volumes, 95))
    return max(0.001, val)
