import pytest

from BackEnd.constants import BLOCK_RECONCILIATION_BLOCK_THRESHOLD
from BackEnd.utils.shared import height_to_block_score


# Re-banded +6 in. for the recalibrated height distribution (design §11.2):
# <=78 -> 0, then h-78, >=88 -> 10. Preserves the ~1.68 league-mean block score.
@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (None, 0),
        ("invalid", 0),
        (76, 0),
        (78, 0),
        (79, 1),
        (80, 2),
        (81, 3),
        (82, 4),
        (83, 5),
        (84, 6),
        (85, 7),
        (86, 8),
        (87, 9),
        (88, 10),
        (92, 10),
    ],
)
def test_height_to_block_score_ascends_and_clamps(height, expected):
    assert height_to_block_score(height) == expected


def test_block_reconciliation_threshold_is_recalibrated():
    assert BLOCK_RECONCILIATION_BLOCK_THRESHOLD == -50
