"""Universal over-and-back pass geometry and passer awareness."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from BackEnd.engine.over_and_back import (
    CROSS_HALF_URGENCY_X_MAX,
    CROSS_HALF_URGENCY_X_MIN,
    cross_half_urgency_target,
    is_over_and_back_pass,
    passer_commits_over_and_back_pass,
    passer_over_and_back_threshold,
    should_hold_instead_of_backcourt_pass,
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


def test_grace_beat_always_holds_backcourt_pass():
    rng = MagicMock()
    rng.randint.return_value = 100  # would commit if not grace
    assert should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(99, 99),
        grace_bh_pos="PG",
        current_bh_pos="PG",
        rng=rng,
    )


def test_after_grace_uses_passer_awareness():
    rng = MagicMock()
    rng.randint.return_value = 40
    assert should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(40, 40),
        grace_bh_pos=None,
        current_bh_pos="PG",
        rng=rng,
    )
    rng.randint.return_value = 99
    assert not should_hold_instead_of_backcourt_pass(
        True,
        {"x": 45, "y": 25},
        False,
        _player(99, 99),
        grace_bh_pos=None,
        current_bh_pos="PG",
        rng=rng,
    )


def test_cross_half_urgency_target_is_frontcourt_side():
    rng = MagicMock()
    rng.randint.side_effect = [55, 0]
    target = cross_half_urgency_target(
        {"x": 40, "y": 25},
        is_away_offense=False,
        clamp_fn=lambda xy: {"x": int(xy["x"]), "y": int(xy["y"])},
        flip_fn=lambda xy: xy,
        rng=rng,
    )
    assert CROSS_HALF_URGENCY_X_MIN <= target["x"] <= CROSS_HALF_URGENCY_X_MAX
