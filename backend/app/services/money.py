"""The API, experiment and browser share a half-up cent convention."""
import math


def round_cost(value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError("cost must be finite and nonnegative")
    # Match the browser's documented tolerance for floating-point summation.
    scaled = value * 100
    if not math.isfinite(scaled):
        # Huge finite floats have no fractional-cent precision. Scaling must
        # not turn an otherwise representable total into an overflow error.
        return value
    return math.floor(scaled + 0.5 + 1e-7) / 100
