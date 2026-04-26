"""Split-phase franchise training state helpers."""

from BackEnd.utils.franchise_training_state import (
    franchise_training_fully_complete_for_week,
    franchise_user_training_applied_for_week,
)


def test_legacy_single_shot_fully_complete():
    ts = {"training_completed": True, "week": 3}
    assert franchise_training_fully_complete_for_week(ts, 3) is True
    assert franchise_user_training_applied_for_week(ts, 3) is False


def test_split_path_not_complete_until_distant():
    ts = {
        "training_completed": False,
        "week": 2,
        "user_training_applied_week": 2,
    }
    assert franchise_training_fully_complete_for_week(ts, 2) is False
    assert franchise_user_training_applied_for_week(ts, 2) is True

    ts_done = {
        **ts,
        "training_completed": True,
        "cpu_distant_complete_week": 2,
    }
    assert franchise_training_fully_complete_for_week(ts_done, 2) is True


def test_week_mismatch_not_complete():
    ts = {"training_completed": True, "week": 2, "user_training_applied_week": 2, "cpu_distant_complete_week": 2}
    assert franchise_training_fully_complete_for_week(ts, 3) is False
