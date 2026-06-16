"""Tests for motion attack drive shot cumulative tracker."""

from BackEnd.utils.shared import (
    empty_motion_attack_shot_tracker,
    format_motion_attack_shot_tracker,
    increment_motion_attack_shot_tracker,
)


def test_increment_driver_shoot_with_defender():
    gs = {"motion_attack_shot_tracker": empty_motion_attack_shot_tracker()}
    increment_motion_attack_shot_tracker(
        gs, driver_shoots=True, has_shot_defender=True,
    )
    tracker = gs["motion_attack_shot_tracker"]
    assert tracker["total"] == 1
    assert tracker["driver_shoot"] == 1
    assert tracker["driver_dish"] == 0
    assert tracker["driver_shoot_with_defender"] == 1
    assert tracker["driver_shoot_without_defender"] == 0


def test_increment_dish_without_defender():
    gs = {}
    increment_motion_attack_shot_tracker(
        gs, driver_shoots=False, has_shot_defender=False,
    )
    tracker = gs["motion_attack_shot_tracker"]
    assert tracker["total"] == 1
    assert tracker["driver_dish"] == 1
    assert tracker["dish_shot_without_defender"] == 1
    assert tracker["dish_shot_with_defender"] == 0


def test_format_includes_all_lines():
    text = format_motion_attack_shot_tracker(empty_motion_attack_shot_tracker())
    assert "MOTION ATTACK SHOT TRACKER" in text
    assert "Driver shoots:" in text
    assert "Dish shot — without shot defender:" in text
