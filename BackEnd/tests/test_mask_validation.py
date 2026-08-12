"""Tank-mask validation + RGBA/_tank footgun regression."""
from __future__ import annotations

import os
import sys
import unittest

import numpy as np

# Bake helpers live under scripts/; keep import path aligned with bake scripts.
_SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
_RECRUIT = os.path.join(_SCRIPTS, "recruit_sets")
sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, _RECRUIT)

from mask_validation import (  # noqa: E402
    MIN_TANK_PIXELS,
    assert_tank_mask_usable,
    tank_pixel_count,
)
import apply_team_uniforms as uni  # noqa: E402


class TestMaskValidation(unittest.TestCase):
    def test_assert_rejects_blank(self):
        blank = np.zeros((64, 64), dtype=np.uint8)
        with self.assertRaises(RuntimeError):
            assert_tank_mask_usable(blank, source="blank")

    def test_assert_accepts_healthy(self):
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[10:50, 10:50] = 255
        self.assertGreaterEqual(
            assert_tank_mask_usable(mask, source="ok", min_pixels=100),
            100,
        )

    def test_tank_ignores_alpha_channel(self):
        """RGBA must not empty the mask — alpha=255 used to inflate max−min."""
        from scipy import ndimage

        H = W = 128
        rgb = np.zeros((H, W, 3), dtype=np.float32)
        # White tank band in lower half (neutral, bright).
        rgb[70:110, 40:90] = 240.0
        # Mild shading on fabric (still neutral on RGB).
        rgb[80:100, 50:80] = np.array([235.0, 232.0, 230.0])
        person = np.zeros((H, W), dtype=bool)
        person[20:115, 30:100] = True

        rgba = np.dstack([rgb, np.full((H, W), 255.0, dtype=np.float32)])
        tank_rgb = uni._tank(rgb, person, np, ndimage)
        tank_rgba = uni._tank(rgba, person, np, ndimage)
        self.assertGreaterEqual(int(tank_rgb.sum()), MIN_TANK_PIXELS // 50)
        self.assertEqual(int(tank_rgb.sum()), int(tank_rgba.sum()))
        self.assertEqual(tank_pixel_count(tank_rgb), int(tank_rgb.sum()))


if __name__ == "__main__":
    unittest.main()
