"""Unit tests for shot micro-movements contest resolver and block gate helpers."""

import pytest

from BackEnd.constants.shot_micro_movements_constants import (
    CONTEST_DEFENSE_WIN_THRESHOLD,
    CONTEST_OFFENSE_WIN_THRESHOLD,
)
from BackEnd.engine.shot_micro_movements import (
    FAMILY_BUCKET,
    build_micro_coords_snapshot,
    resolve_contest,
    select_micro_movement,
)


class TestResolveContest:
    def test_offense_win_above_threshold(self):
        result, margin = resolve_contest(400.0, 200.0)
        assert result == "offense_win"
        assert margin == pytest.approx(200.0)
        assert margin > CONTEST_OFFENSE_WIN_THRESHOLD

    def test_defense_win_below_threshold(self):
        result, margin = resolve_contest(100.0, 300.0)
        assert result == "defense_win"
        assert margin == pytest.approx(-200.0)
        assert margin < CONTEST_DEFENSE_WIN_THRESHOLD

    def test_neutral_band(self):
        result, margin = resolve_contest(200.0, 210.0)
        assert result == "neutral"
        assert CONTEST_DEFENSE_WIN_THRESHOLD <= margin <= CONTEST_OFFENSE_WIN_THRESHOLD


class TestMovementRegistry:
    def test_all_pools_have_buckets(self):
        from BackEnd.constants.shot_micro_movements_constants import MOVEMENT_POOL_BY_SHOT_TYPE

        for families in MOVEMENT_POOL_BY_SHOT_TYPE.values():
            for family_id in families:
                assert family_id in FAMILY_BUCKET, family_id

    def test_select_inside_family(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda pool: pool[0],
        )
        family = select_micro_movement(
            "inside",
            shooter_coord={"x": 80.0, "y": 25.0},
            shooter_id="s1",
            off_lineup={},
            all_coords={"s1": {"x": 80.0, "y": 25.0}},
        )
        assert family == "strong_inside"


class TestCoordsSnapshot:
    def test_shooter_coord_overrides_lineup(self):
        class P:
            player_id = "s1"
            coords = {"x": 10, "y": 10}

        coords = build_micro_coords_snapshot(
            {"PG": P()}, {}, "s1", 91.0, 25.0,
        )
        assert coords["s1"] == {"x": 91.0, "y": 25.0}
