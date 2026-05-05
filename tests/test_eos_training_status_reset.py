"""EOS weeks 27-34: franchise week advance must not churn training_status."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from BackEnd.api import franchise_routes as fr


def test_training_reset_skipped_for_eos_calendar_weeks():
    for w in range(27, 35):
        assert fr._training_status_reset_after_advance_to_week(w) is None


def test_training_reset_applied_after_eos_and_regular_season():
    out = fr._training_status_reset_after_advance_to_week(35)
    assert out is not None
    assert out["training_status.training_completed"] is False
    assert out["training_status.session_type"] == "in-season"

    out2 = fr._training_status_reset_after_advance_to_week(5)
    assert out2 is not None
    assert out2["training_status.training_completed"] is False
