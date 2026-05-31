"""UESS: shooting-foul-on-miss announcements for PUTBACK_MISS (OREB putback)."""

from BackEnd.engine.skeleton_step_emitter import (
    _shooting_foul_on_miss_announcement,
    _stamp_shooting_foul_on_miss_end,
)


def test_putback_miss_shooting_foul_announcement():
    turn = {
        "result_type": "PUTBACK_MISS",
        "next_play_type": "FREE_THROW",
        "free_throws_remaining": 2,
        "foul_player_id": "defender-42",
    }
    ann = _shooting_foul_on_miss_announcement(turn)
    assert ann is not None
    assert ann["text"] == "Shooting Foul!"
    assert ann["style"] == "shooting_foul"
    assert ann.get("meta", {}).get("sfx") == "foul"


def test_hco_miss_shooting_foul_announcement_regression():
    turn = {
        "result_type": "MISS",
        "next_play_type": "FREE_THROW",
        "foul_player_id": "def-1",
    }
    assert _shooting_foul_on_miss_announcement(turn) is not None


def test_putback_miss_without_free_throws_no_announcement():
    turn = {
        "result_type": "PUTBACK_MISS",
        "next_play_type": "HCO",
        "free_throws_remaining": 0,
        "foul_player_id": "def-1",
    }
    assert _shooting_foul_on_miss_announcement(turn) is None


def test_stamp_shooting_foul_on_putback_miss_step_end():
    turn = {
        "result_type": "PUTBACK_MISS",
        "next_play_type": "FREE_THROW",
        "foul_player_id": "def-9",
    }
    step = {"start": {}, "end": {"next": {"kind": "turn_stop", "event": "SHOT_ATTEMPT"}}}
    _stamp_shooting_foul_on_miss_end(step, turn)
    assert step["end"]["announcement"]["text"] == "Shooting Foul!"
