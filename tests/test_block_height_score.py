import pytest

from BackEnd.constants import BLOCK_RECONCILIATION_BLOCK_THRESHOLD
from BackEnd.utils.shared import height_to_block_score


@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (None, 0),
        ("invalid", 0),
        (70, 0),
        (72, 0),
        (73, 1),
        (74, 2),
        (75, 3),
        (76, 4),
        (77, 5),
        (78, 6),
        (79, 7),
        (80, 8),
        (81, 9),
        (82, 10),
        (86, 10),
    ],
)
def test_height_to_block_score_ascends_and_clamps(height, expected):
    assert height_to_block_score(height) == expected


def test_block_reconciliation_threshold_is_recalibrated():
    assert BLOCK_RECONCILIATION_BLOCK_THRESHOLD == -50
