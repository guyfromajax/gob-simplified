"""Unit tests for shot micro-movements contest resolver and block gate helpers."""

import pytest

from BackEnd.constants.shot_micro_movements_constants import (
    CONTEST_DEFENSE_WIN_THRESHOLD,
    CONTEST_OFFENSE_WIN_THRESHOLD,
)
from BackEnd.engine.shot_micro_movements import (
    FAMILY_BUCKET,
    _pick_outside_dribble_target,
    apply_shot_micro_steps_to_chain,
    build_micro_coords_snapshot,
    build_shot_micro_steps,
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


class TestTravelShootInsertion:
    def test_inserts_micro_after_fb_drive(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda pool: "straight_inside",
        )
        travel: dict = {
            "start": {
                "coords": {
                    "s1": {"x": 50.0, "y": 25.0},
                    "d1": {"x": 48.0, "y": 25.0},
                },
                "destination": {"s1": {"x": 88.0, "y": 25.0}, "d1": None},
                "action": {"s1": "shoot", "d1": "stationary"},
                "archetype": {"s1": "sprint", "d1": "standard"},
                "ball": {"owner_player_id": "s1"},
                "clock": {"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            },
            "end": {
                "coords": {
                    "s1": {"x": 88.0, "y": 25.0},
                    "d1": {"x": 86.0, "y": 25.0},
                },
                "ball": {"owner_player_id": "s1"},
                "time_elapsed": 2.0,
                "clock": {"clock_remaining": 8.0, "shot_clock_remaining": 6.0},
                "next": {"kind": "next_step", "index": 1},
            },
        }
        steps = [travel]
        turn_result = {
            "result_type": "MAKE",
            "micro_movement_family": "straight_inside",
            "shooter_id": "s1",
            "shot_type": "inside",
            "has_contest": False,
        }
        apply_shot_micro_steps_to_chain(steps, turn_result, {}, {}, False)

        assert len(steps) == 2
        assert steps[0]["start"]["action"]["s1"] == "sprint"
        assert steps[0]["end"]["next"]["index"] == 1
        assert steps[1]["start"]["coords"]["s1"] == {"x": 88.0, "y": 25.0}
        assert steps[1]["start"]["action"]["s1"] == "shoot"

    def test_in_place_shoot_still_replaces(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda pool: "straight_inside",
        )
        shoot: dict = {
            "start": {
                "coords": {"s1": {"x": 88.0, "y": 25.0}},
                "destination": {"s1": None},
                "action": {"s1": "shoot"},
                "archetype": {"s1": "shot_motion"},
                "ball": {"owner_player_id": "s1"},
                "clock": {"clock_remaining": 8.0, "shot_clock_remaining": 6.0},
            },
            "end": {
                "coords": {"s1": {"x": 88.0, "y": 25.0}},
                "ball": {"owner_player_id": "s1"},
                "time_elapsed": 0.4,
                "clock": {"clock_remaining": 7.6, "shot_clock_remaining": 5.6},
                "next": {"kind": "next_step", "index": 1},
            },
        }
        steps = [shoot]
        turn_result = {
            "result_type": "MISS",
            "micro_movement_family": "straight_inside",
            "shooter_id": "s1",
            "shot_type": "inside",
            "has_contest": False,
        }
        apply_shot_micro_steps_to_chain(steps, turn_result, {}, {}, False)

        assert len(steps) == 1
        assert steps[0]["start"]["action"]["s1"] == "shoot"


class TestAwayOutsideDribbleMirror:
    """Away offense must pick arc targets on the left half (display x < 50)."""

    AWAY_UPPER_WING = {"x": 27.0, "y": 40.0}  # mirror of home upper wing (73, 40)

    def test_nearest_spot_uses_mirrored_coords(self):
        from BackEnd.engine.shot_micro_movements import _nearest_arc_spot_name

        assert _nearest_arc_spot_name(self.AWAY_UPPER_WING, away_offense=True) == "upper wing"
        assert _nearest_arc_spot_name({"x": 73.0, "y": 40.0}, away_offense=False) == "upper wing"

    def test_dribble_target_stays_on_away_half(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda candidates: candidates[0],
        )
        target = _pick_outside_dribble_target(
            self.AWAY_UPPER_WING, teammates=[], away_offense=True,
        )
        assert target is not None
        assert target["x"] < 50.0

    def test_build_micro_move_to_stays_on_away_half(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda candidates: candidates[0],
        )
        start = {"s1": dict(self.AWAY_UPPER_WING)}
        steps = build_shot_micro_steps(
            family_id="dribble_shoot",
            contest_result=None,
            start_coords=start,
            shooter_id="s1",
            defender_id=None,
            off_lineup={},
            def_lineup={},
            away_offense=True,
            clock_start={"clock_remaining": 8.0, "shot_clock_remaining": 6.0},
            shot_type="outside",
            next_step={"kind": "next_step", "index": 2},
            apply_contest_layer=False,
        )
        assert len(steps) == 3
        move_dest = steps[0]["end"]["coords"]["s1"]
        assert move_dest["x"] < 50.0
        assert steps[1]["start"]["flourish"]["s1"]["kind"] == "gather"
        assert steps[2]["start"]["action"]["s1"] == "shoot"
        assert steps[2]["start"]["coords"]["s1"]["x"] < 50.0


class TestShotBallArc:
    def test_apex_sanity_checks(self):
        from BackEnd.utils.shot_ball_arc import compute_shot_ball_arc

        # strong ~7.6 grid → ~46px (style mult 0.85)
        strong = compute_shot_ball_arc(
            {"x": 92.4, "y": 25.0},
            away_offense=False,
            family_id="strong_inside",
        )
        assert strong is None  # no arc style for strong_inside

        fade = compute_shot_ball_arc(
            {"x": 81.2, "y": 25.0},
            away_offense=False,
            family_id="fade_away",
        )
        assert fade is not None
        assert fade["apex_px"] == pytest.approx(96.1, abs=1.0)

        outside = compute_shot_ball_arc(
            {"x": 68.0, "y": 25.0},
            away_offense=False,
            family_id="dribble_shoot",
        )
        assert outside is not None
        assert outside["apex_px"] == pytest.approx(123.5, abs=2.0)

    def test_apex_pos_past_midpoint(self):
        from BackEnd.utils.shot_ball_arc import compute_shot_ball_arc

        flat = compute_shot_ball_arc(
            {"x": 83.4, "y": 25.0},
            away_offense=False,
            family_id="fade_away",
        )
        tall = compute_shot_ball_arc(
            {"x": 68.0, "y": 25.0},
            away_offense=False,
            family_id="dribble_shoot",
        )
        assert flat["apex_pos"] >= 0.54
        assert flat["apex_pos"] <= 0.60
        assert tall["apex_pos"] <= flat["apex_pos"]

    def test_arc_flight_rate_slower_than_straight(self):
        from BackEnd.constants import (
            ARC_SHOT_BALL_GRID_PER_GAME_SECOND,
            SHOT_BALL_GRID_PER_GAME_SECOND,
        )
        from BackEnd.utils.shot_ball_arc import shot_ball_flight_grid_rate

        assert ARC_SHOT_BALL_GRID_PER_GAME_SECOND == 20
        assert shot_ball_flight_grid_rate(uses_arc=True) == 20.0
        assert shot_ball_flight_grid_rate(uses_arc=False) == float(
            SHOT_BALL_GRID_PER_GAME_SECOND,
        )

    def test_stamp_metadata_includes_arc_flight_rate(self):
        from BackEnd.utils.shot_ball_arc import stamp_shot_ball_arc_metadata

        metadata: dict = {}
        stamp_shot_ball_arc_metadata(
            metadata,
            {
                "result_type": "MAKE",
                "uses_shot_arc": True,
                "micro_movement_family": "fade_away",
            },
            {"x": 81.2, "y": 25.0},
            away_offense=False,
        )
        assert "shot_ball_arc" in metadata
        assert metadata["ball_grid_per_game_second"] == 20.0

    def test_roll_shot_arc_probabilities(self, monkeypatch):
        from BackEnd.utils import shot_ball_arc as arc_mod

        monkeypatch.setattr(arc_mod.random, "random", lambda: 0.3)
        assert arc_mod.roll_shot_arc("fade_away") is True
        assert arc_mod.roll_shot_arc("set") is True
        monkeypatch.setattr(arc_mod.random, "random", lambda: 0.6)
        assert arc_mod.roll_shot_arc("jab_step") is False
        assert arc_mod.roll_shot_arc("strong_inside") is False


class TestShotManagerMicroTelemetryMerge:
    """ShotManager.resolve_shot uses a scratch dict; arc requires uses_shot_arc on turn."""

    def test_scratch_merge_includes_uses_shot_arc(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro

        turn: dict = {}
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda pool: "fade_away",
        )
        select_and_stamp_shot_micro(
            turn,
            shot_type="inside",
            shooter_id="s1",
            shooter_x=81.2,
            shooter_y=25.0,
            off_lineup={},
            def_lineup={},
            has_contest=False,
            contest_result=None,
            contest_margin=None,
            shot_defense_score_raw=0.0,
        )
        # Mirror shot_manager.resolve_shot scratch → result merge.
        result = {
            "micro_movement_family": turn.get("micro_movement_family"),
            "uses_shot_arc": bool(turn.get("uses_shot_arc")),
        }
        assert result["micro_movement_family"] == "fade_away"
        assert result["uses_shot_arc"] is True


class TestGatherBeats:
    def test_pump_dribble_shoot_includes_gather(self, monkeypatch):
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.choice",
            lambda candidates: candidates[0],
        )
        from BackEnd.engine.shot_micro_movements import _build_family_beats

        beats = _build_family_beats(
            "pump_dribble_shoot",
            {"x": 75.0, "y": 30.0},
            away_offense=False,
            off_lineup={},
            all_coords={"s1": {"x": 75.0, "y": 30.0}},
            shooter_id="s1",
        )
        kinds = [b["kind"] for b in beats]
        assert kinds == ["flourish", "move_to", "flourish", "shot"]
        assert beats[2]["flourish"] == "gather"

    def test_dribble_pump_shoot_no_gather(self):
        from BackEnd.engine.shot_micro_movements import _build_family_beats

        beats = _build_family_beats(
            "dribble_pump_shoot",
            {"x": 75.0, "y": 30.0},
            away_offense=False,
            off_lineup={},
            all_coords={"s1": {"x": 75.0, "y": 30.0}},
            shooter_id="s1",
        )
        assert not any(b.get("flourish") == "gather" for b in beats)
