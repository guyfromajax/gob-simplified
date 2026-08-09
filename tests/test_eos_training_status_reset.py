"""Training exists only in franchise weeks 1–26."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.api import franchise_routes as fr


def test_training_reset_skipped_after_regular_season():
    for w in range(27, 38):
        assert fr._training_status_reset_after_advance_to_week(w) is None


def test_training_reset_applied_during_regular_season():
    for week in (1, 2, 26):
        out = fr._training_status_reset_after_advance_to_week(week)
        assert out is not None
        assert out["training_status.training_completed"] is False
        assert out["training_status.session_type"] == "in-season"
