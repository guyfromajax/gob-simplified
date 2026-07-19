"""Shot-clock policy when game clock is at or below 30 seconds."""

from BackEnd.utils.shot_clock_policy import (
    can_commit_shot_clock_violation,
    is_shot_clock_enforced,
    sync_late_game_shot_clock,
)


def test_shot_clock_enforced_above_late_threshold():
    gs = {"time_remaining": 31, "shot_clock_remaining": 5}
    assert is_shot_clock_enforced(gs) is True
    assert can_commit_shot_clock_violation(gs) is True
    sync_late_game_shot_clock(gs)
    assert gs["shot_clock_remaining"] == 5


def test_reset_shot_clock_is_disabled_at_or_below_late_threshold():
    gs = {"time_remaining": 30, "shot_clock_remaining": 30}
    assert is_shot_clock_enforced(gs) is False
    assert can_commit_shot_clock_violation(gs) is False
    sync_late_game_shot_clock(gs)
    assert gs["shot_clock_remaining"] == 30


def test_late_game_sync_preserves_shorter_carried_shot_clock():
    gs = {"time_remaining": 18, "shot_clock_remaining": 2}
    sync_late_game_shot_clock(gs)
    assert gs["shot_clock_remaining"] == 2
    assert is_shot_clock_enforced(gs) is True
    assert can_commit_shot_clock_violation(gs) is True


def test_late_game_sync_caps_reset_clock_to_game_clock():
    gs = {"time_remaining": 18, "shot_clock_remaining": 30}
    sync_late_game_shot_clock(gs)
    assert gs["shot_clock_remaining"] == 18
    assert is_shot_clock_enforced(gs) is False
    assert can_commit_shot_clock_violation(gs) is False
