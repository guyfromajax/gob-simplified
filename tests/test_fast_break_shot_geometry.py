from BackEnd.utils.fast_break_shot_geometry import (
    FB_CONTEST_MAX_X_TRAIL,
    FB_SHOOTER_X_OFFSET_MAX,
    FB_SHOOTER_X_OFFSET_MIN,
    _compute_shooter_target,
    _defender_contests_fb_shot,
    _pick_fb_shot_defender,
)


def test_shooter_target_x_offset_range(monkeypatch):
    seen = []

    def fake_randint(lo, hi):
        seen.append((lo, hi))
        return 3

    monkeypatch.setattr(
        "BackEnd.utils.fast_break_shot_geometry.random.randint", fake_randint
    )
    target = _compute_shooter_target(is_away_offense=False)
    assert seen == [(FB_SHOOTER_X_OFFSET_MIN, FB_SHOOTER_X_OFFSET_MAX), (19, 31)]
    assert target == {"x": 88.0, "y": 3.0}


def test_home_defender_contests_when_within_radius_and_x_trail():
    shooter = {"x": 88.0, "y": 25.0}
    assert _defender_contests_fb_shot({"x": 87.0, "y": 25.0}, shooter, False)
    assert _defender_contests_fb_shot({"x": 85.0, "y": 25.0}, shooter, False)
    assert not _defender_contests_fb_shot({"x": 84.0, "y": 25.0}, shooter, False)
    assert _defender_contests_fb_shot({"x": 90.0, "y": 25.0}, shooter, False)


def test_away_defender_contests_when_within_radius_and_x_trail():
    shooter = {"x": 12.0, "y": 25.0}
    assert _defender_contests_fb_shot({"x": 13.0, "y": 25.0}, shooter, True)
    assert _defender_contests_fb_shot({"x": 15.0, "y": 25.0}, shooter, True)
    assert not _defender_contests_fb_shot({"x": 16.0, "y": 25.0}, shooter, True)
    assert _defender_contests_fb_shot({"x": 10.0, "y": 25.0}, shooter, True)


def test_euclidean_gate_blocks_contest_even_with_valid_x_trail():
    shooter = {"x": 88.0, "y": 25.0}
    assert not _defender_contests_fb_shot({"x": 85.0, "y": 36.0}, shooter, False)


def test_pick_nearest_qualifying_defender():
    shooter = {"x": 88.0, "y": 25.0}
    traversals = [
        {"id": "d1", "start": {"x": 50.0, "y": 25.0}},
        {"id": "d2", "start": {"x": 50.0, "y": 25.0}},
    ]
    end_coords = {
        "d1": {"x": 87.0, "y": 25.0},
        "d2": {"x": 86.0, "y": 25.0},
    }
    contested, shot_defender_id = _pick_fb_shot_defender(
        traversals, end_coords, shooter, is_away_offense=False
    )
    assert contested is True
    assert shot_defender_id == "d1"


def test_x_trail_constant_matches_spec():
    assert FB_CONTEST_MAX_X_TRAIL == 3
