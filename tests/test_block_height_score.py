import pytest

from BackEnd.constants import BLOCK_RECONCILIATION_BLOCK_THRESHOLD_BASE
from BackEnd.models.shot_manager import (
    _block_reconciliation_threshold,
    _calculate_defense_block_score,
)
from BackEnd.utils.shared import height_to_block_score


# Rides LEAGUE_MEDIAN_HEIGHT_IN (offsets from the constant, not literals). After the
# two 2026-08 HS shifts the median is 75: <=75 -> 0, then h-75, >=85 -> 10. Preserves
# the ~1.68 league-mean block score against the shifted distribution.
@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (None, 0),
        ("invalid", 0),
        (74, 0),
        (75, 0),
        (76, 1),
        (77, 2),
        (78, 3),
        (79, 4),
        (80, 5),
        (81, 6),
        (82, 7),
        (83, 8),
        (84, 9),
        (85, 10),
        (89, 10),
    ],
)
def test_height_to_block_score_ascends_and_clamps(height, expected):
    assert height_to_block_score(height) == expected


def test_block_reconciliation_threshold_base_is_recalibrated():
    assert BLOCK_RECONCILIATION_BLOCK_THRESHOLD_BASE == 70


@pytest.mark.parametrize(
    ("stored_defensive_efficiency", "expected"),
    [(20, 80), (0, 70), (-20, 60)],
)
def test_block_reconciliation_threshold_uses_normalized_defensive_efficiency(
    stored_defensive_efficiency,
    expected,
):
    assert _block_reconciliation_threshold(stored_defensive_efficiency) == expected


def test_defense_block_score_uses_requested_additive_composite():
    # Stored core-8 +10 normalizes to gameplay +5 before entering the formula.
    assert _calculate_defense_block_score(50, 8, 6, 10, 4) == pytest.approx(117.6)
