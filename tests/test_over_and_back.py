"""Universal over-and-back pass geometry and passer awareness."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from BackEnd.engine.over_and_back import (
    is_over_and_back_pass,
    passer_commits_over_and_back_pass,
    passer_over_and_back_threshold,
)


def _player(ps=50, ch=50):
    return SimpleNamespace(attributes={"PS": ps, "CH": ch})


def test_threshold_formula():
    assert passer_over_and_back_threshold(_player(80, 60)) == 76.0


def test_smart_passer_holds_high_roll():
    rng = MagicMock()
    rng.randint.return_value = 77
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is True
    rng.randint.return_value = 76
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is False
    rng.randint.return_value = 50
    assert passer_commits_over_and_back_pass(_player(80, 60), rng=rng) is False


def test_weak_passer_commits_on_low_roll():
    rng = MagicMock()
    rng.randint.return_value = 50
    assert passer_commits_over_and_back_pass(_player(40, 40), rng=rng) is True


def test_is_over_and_back_requires_frontcourt_established():
    assert not is_over_and_back_pass(False, {"x": 45, "y": 25}, False)
    assert is_over_and_back_pass(True, {"x": 45, "y": 25}, False)
