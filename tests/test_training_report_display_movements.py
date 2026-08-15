from BackEnd.models.training_execution_v2 import (
    training_report_display_bucket,
    training_report_display_movement,
)


def test_training_report_display_bucket_matches_frontend_scale():
    assert training_report_display_bucket(89) == 8
    assert training_report_display_bucket(90) == 9
    assert training_report_display_bucket(60) == 6
    assert training_report_display_bucket(59) == 5
    assert training_report_display_bucket(100) == 10


def test_training_report_display_bucket_handles_payload_fallbacks():
    assert training_report_display_bucket("79") == 7
    assert training_report_display_bucket(None) == 0
    assert training_report_display_bucket("not-a-number") == 0


def test_training_report_display_movement_only_marks_crossed_tiers():
    assert training_report_display_movement(89, 90) == 1
    assert training_report_display_movement(60, 59) == -1
    assert training_report_display_movement(88, 89) == 0
    assert training_report_display_movement(61, 60) == 0
