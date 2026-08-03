"""Tank-mask validation for portrait kit bakes.

A usable jersey mask must contain a real tank region. Blank / near-blank masks
fail open at paint time (`ValueError: no tank found`) and leave generic
silhouettes — so the bake must refuse to write them.

Call ``_tank`` on RGB only (not RGBA). Channel min/max over four channels lets
alpha=255 break the neutrality gate and yield an empty mask.
"""
from __future__ import annotations

from typing import Any

# Absolute tank pixels after threshold (>128). Healthy Broad/Lean kits sit
# ~110k–180k on a 1024² canvas; anything under a few thousand is unusable.
MIN_TANK_PIXELS = 5_000
TANK_THRESHOLD = 128


def tank_pixel_count(mask_arr: Any, *, threshold: int = TANK_THRESHOLD) -> int:
    """Count tank pixels in an L-mode / bool / 0-255 mask array."""
    import numpy as np

    arr = np.asarray(mask_arr)
    if arr.dtype == bool:
        return int(arr.sum())
    return int((arr > threshold).sum())


def assert_tank_mask_usable(
    tank_or_mask: Any,
    *,
    source: str,
    min_pixels: int = MIN_TANK_PIXELS,
) -> int:
    """
    Raise RuntimeError if the mask has too few tank pixels.

    Returns the tank pixel count on success.
    """
    count = tank_pixel_count(tank_or_mask)
    if count < min_pixels:
        raise RuntimeError(
            f"unusable tank mask for {source}: {count} tank pixels "
            f"(minimum {min_pixels}). Refusing to write a blank/near-blank mask."
        )
    return count
