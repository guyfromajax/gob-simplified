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


class TestContestDefenderNoJet:
    """A far contest defender must not be teleported next to the shooter over a
    short micro beat. Every micro step must keep the defender within his
    standard-rate reach for that step's duration."""

    def _player(self, pid, x, y):
        from types import SimpleNamespace

        return SimpleNamespace(
            player_id=pid,
            coords={"x": x, "y": y},
            attributes={"AG": 50, "IQ": 50, "CH": 50},
        )

    def test_far_defender_contest_is_clamped_per_beat(self):
        from BackEnd.engine.shot_micro_movements import (
            _ag_grid_per_game_sec,
            _euclid,
            build_shot_micro_steps,
        )

        shooter = self._player("shooter", 85.0, 25.0)
        defender = self._player("defender", 40.0, 25.0)  # ~45 grid units away
        off_lineup = {"C": shooter}
        def_lineup = {"C": defender}
        start_coords = {
            "shooter": {"x": 85.0, "y": 25.0},
            "defender": {"x": 40.0, "y": 25.0},
        }

        steps = build_shot_micro_steps(
            family_id="strong_inside",
            contest_result="defense_win",
            start_coords=start_coords,
            shooter_id="shooter",
            defender_id="defender",
            off_lineup=off_lineup,
            def_lineup=def_lineup,
            away_offense=False,
            clock_start={"clock_remaining": 20.0, "shot_clock_remaining": 12.0},
            shot_type="inside",
            next_step={"kind": "next_step", "index": 2},
            apply_contest_layer=True,
        )

        assert steps
        rate = _ag_grid_per_game_sec(defender, "standard")
        for step in steps:
            s = step["start"]["coords"]["defender"]
            e = step["end"]["coords"]["defender"]
            step_t = float(step["end"]["time_elapsed"])
            delta = _euclid(s, e)
            # No superhuman speed: distance covered ≤ rate × step duration.
            assert delta <= rate * step_t + 1e-6, (
                f"defender jet: {delta:.2f} grid in {step_t:.3f}s "
                f"(max {rate * step_t:.2f})"
            )


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


class TestFinalTurnMicroBudget:
    def _shooter(self, ag=50):
        from types import SimpleNamespace

        return SimpleNamespace(player_id="s1", attributes={"AG": ag})

    def test_set_pump_pre_release_exceeds_tight_budget(self):
        from BackEnd.engine.shot_micro_movements import (
            estimate_micro_pre_release_seconds,
            select_micro_movement,
        )

        coord = {"x": 83.0, "y": 18.0}
        pre = estimate_micro_pre_release_seconds(
            "set_pump",
            shooter_player=self._shooter(),
            shooter_coord=coord,
            off_lineup={},
            all_coords={"s1": coord},
            shooter_id="s1",
        )
        assert pre == pytest.approx(1.05)
        family = select_micro_movement(
            "outside",
            shooter_coord=coord,
            shooter_id="s1",
            off_lineup={},
            all_coords={"s1": coord},
            max_pre_release_seconds=0.5,
            shooter_player=self._shooter(),
        )
        assert family == "set"

    def test_flss_inject_is_noop(self):
        from BackEnd.engine.shot_micro_movements import inject_shot_micro_before_post_shot

        steps = [
            {
                "start": {
                    "coords": {"s1": {"x": 80, "y": 25}},
                    "action": {"s1": "shoot"},
                },
                "end": {"coords": {"s1": {"x": 80, "y": 25}}},
            }
        ]
        before = len(steps)
        inject_shot_micro_before_post_shot(
            steps,
            {"flss": True, "result_type": "MISS", "micro_movement_family": "set_pump"},
            {},
            {},
            False,
        )
        assert len(steps) == before

    def test_worst_case_outside_reserve_positive(self):
        from BackEnd.engine.shot_micro_movements import worst_case_final_turn_micro_reserve

        assert worst_case_final_turn_micro_reserve("outside") > 1.0


class TestDunkMicroMovement:
    def test_dunk_families_registered_bucket_a(self):
        assert FAMILY_BUCKET["dunk"] == "A"
        assert FAMILY_BUCKET["drive_dunk"] == "A"

    def test_build_dunk_beats_strong(self):
        from BackEnd.engine.shot_micro_movements import _build_family_beats

        beats = _build_family_beats(
            "dunk",
            {"x": 85.0, "y": 25.0},
            False,
            {},
            {"s1": {"x": 85.0, "y": 25.0}},
            "s1",
        )
        assert [b["kind"] for b in beats] == ["move", "dunk"]
        assert beats[0]["archetype"] == "burst"

    def test_build_drive_dunk_beats(self):
        from BackEnd.engine.shot_micro_movements import _build_family_beats

        beats = _build_family_beats(
            "drive_dunk",
            {"x": 70.0, "y": 25.0},
            False,
            {},
            {"s1": {"x": 70.0, "y": 25.0}},
            "s1",
        )
        assert [b["kind"] for b in beats] == ["move", "dunk"]
        assert beats[0]["archetype"] == "sprint"

    def test_dunk_terminal_step_stamps_micro_beat(self):
        from BackEnd.constants import MADE_SHOT_SWEET_SPOT_HOME_RIM
        from BackEnd.constants.shot_micro_movements_constants import DUNK_APPROACH_HOME

        steps = build_shot_micro_steps(
            family_id="dunk",
            contest_result="neutral",
            start_coords={"s1": {"x": 85.0, "y": 25.0}},
            shooter_id="s1",
            defender_id="d2",
            off_lineup={},
            def_lineup={},
            away_offense=False,
            clock_start={"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            shot_type="inside",
            next_step={"kind": "turn_stop", "event": "SHOT_ATTEMPT", "payload": {}},
            apply_contest_layer=True,
            result_type="MAKE",
        )
        assert len(steps) == 2
        dunk_step = steps[-1]
        meta = dunk_step["start"]["advance_trigger"]["metadata"]
        assert meta["micro_beat_kind"] == "dunk"
        assert meta["approach_coord"] == DUNK_APPROACH_HOME
        assert meta["resolve_coord"] == MADE_SHOT_SWEET_SPOT_HOME_RIM
        assert meta["yield_before_slam"] is False
        assert dunk_step["end"]["ball"] == {"coords": dict(MADE_SHOT_SWEET_SPOT_HOME_RIM)}
        assert dunk_step["start"]["flourish"]["s1"]["kind"] == "rattle"
        assert dunk_step["start"]["flourish"]["d2"]["kind"] == "rattle"
        assert dunk_step["start"]["sfx_on_ball_arrival"] == {
            "file": "dunk-sfx.wav",
            "volume": 0.7,
            "event": "shot_result_make_dunk",
        }

    def test_dunk_block_yields_before_slam(self):
        steps = build_shot_micro_steps(
            family_id="dunk",
            contest_result=None,
            start_coords={"s1": {"x": 85.0, "y": 25.0}},
            shooter_id="s1",
            defender_id=None,
            off_lineup={},
            def_lineup={},
            away_offense=False,
            clock_start={"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            shot_type="inside",
            next_step={"kind": "next_step", "index": 3},
            apply_contest_layer=False,
            result_type="BLOCK",
        )
        meta = steps[-1]["start"]["advance_trigger"]["metadata"]
        assert meta["yield_before_slam"] is True
        assert steps[-1]["end"]["ball"] == {"owner_player_id": "s1"}

    def test_dunk_make_skips_ball_flight_in_post_shot(self):
        from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps

        shoot_step = {
            "start": {
                "coords": {"s1": {"x": 85.0, "y": 25.0}},
                "destination": {"s1": {"x": 88.0, "y": 25.0}},
                "action": {"s1": "shoot"},
                "archetype": {"s1": "shot_motion"},
                "clock": {"clock_remaining": 5.0, "shot_clock_remaining": 4.0},
            },
            "end": {
                "coords": {"s1": {"x": 88.0, "y": 25.0}},
                "ball": {"coords": {"x": 90.0, "y": 25.0}},
                "clock": {"clock_remaining": 4.0, "shot_clock_remaining": 3.0},
                "time_elapsed": 1.0,
                "next": {"kind": "turn_stop", "event": "SHOT_ATTEMPT", "payload": {}},
            },
        }
        steps = [shoot_step]
        turn = {
            "result_type": "MAKE",
            "micro_movement_family": "dunk",
            "shooter_id": "s1",
        }
        _build_post_shot_sub_steps(steps, turn, {}, {}, False)
        assert len(steps) == 2
        assert steps[1]["start"]["announcement"]["text"] == "Dunk!"
        assert steps[1]["start"]["announcement"]["meta"] == {"sfx": "dunk_make"}
        assert shoot_step["end"]["next"] == {"kind": "next_step", "index": 1}
        assert all(
            step.get("start", {}).get("ball_motion_style") != "shot"
            for step in steps
        )


class TestDunkSelection:
    def _team(self, fight=50):
        from types import SimpleNamespace

        return SimpleNamespace(team_attributes={"fight": fight})

    def _shooter(self, *, height=80, ag=60, x=85.0, y=25.0):
        from types import SimpleNamespace

        return SimpleNamespace(
            height=height,
            attributes={"AG": ag},
            player_id="s1",
        )

    def test_location_eligibility_by_ag(self):
        from BackEnd.engine.shot_micro_movements import dunk_location_eligible

        assert dunk_location_eligible(7.0, 40) is True
        assert dunk_location_eligible(9.5, 60) is False
        assert dunk_location_eligible(9.0, 55) is True
        assert dunk_location_eligible(9.5, 80) is True
        assert dunk_location_eligible(10.5, 80) is False

    def test_margin_gate(self):
        from BackEnd.engine.shot_micro_movements import dunk_in_play_margin

        assert dunk_in_play_margin(200, 50, off_fight=10, def_fight=5) == 155
        assert dunk_in_play_margin(150, 60, off_fight=0, def_fight=0) == 90

    def test_resolve_returns_none_when_margin_low(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import resolve_dunk_micro_stamp

        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.randint",
            lambda _a, _b: 1,
        )
        stamp = resolve_dunk_micro_stamp(
            shot_type="inside",
            shooter_coord={"x": 85.0, "y": 25.0},
            shooter_player=self._shooter(),
            off_team=self._team(),
            def_team=self._team(),
            shot_score_pre_defense=150.0,
            shot_defense_score_raw=60.0,
            result_type="MAKE",
            away_offense=False,
        )
        assert stamp is None

    def test_resolve_made_dunk_family_by_distance(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import resolve_dunk_micro_stamp

        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.randint",
            lambda _a, _b: 10,
        )
        close = resolve_dunk_micro_stamp(
            shot_type="attack",
            shooter_coord={"x": 85.0, "y": 25.0},
            shooter_player=self._shooter(height=80),
            off_team=self._team(),
            def_team=self._team(),
            shot_score_pre_defense=200.0,
            shot_defense_score_raw=50.0,
            result_type="MAKE",
            away_offense=False,
        )
        assert close == {
            "family_id": "dunk",
            "dunk_miss": False,
            "force_miss": False,
        }

        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.randint",
            lambda _a, _b: 10,
        )
        drive = resolve_dunk_micro_stamp(
            shot_type="attack",
            shooter_coord={"x": 78.0, "y": 25.0},
            shooter_player=self._shooter(height=80, ag=80),
            off_team=self._team(),
            def_team=self._team(),
            shot_score_pre_defense=200.0,
            shot_defense_score_raw=50.0,
            result_type="MAKE",
            away_offense=False,
        )
        assert drive["family_id"] == "drive_dunk"

    def test_resolve_missed_dunk_roll(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import resolve_dunk_micro_stamp

        # height 80 → scale 20; roll == 21 → missed dunk
        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.randint",
            lambda _a, _b: 21,
        )
        stamp = resolve_dunk_micro_stamp(
            shot_type="inside",
            shooter_coord={"x": 85.0, "y": 25.0},
            shooter_player=self._shooter(height=80),
            off_team=self._team(),
            def_team=self._team(),
            shot_score_pre_defense=200.0,
            shot_defense_score_raw=50.0,
            result_type="MAKE",
            away_offense=False,
        )
        assert stamp["dunk_miss"] is True
        assert stamp["force_miss"] is True

    def test_select_and_stamp_overrides_micro_family(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import select_and_stamp_shot_micro

        turn: dict = {}
        dunk_stamp = {
            "family_id": "drive_dunk",
            "dunk_miss": False,
            "force_miss": False,
        }
        select_and_stamp_shot_micro(
            turn,
            shot_type="attack",
            shooter_id="s1",
            shooter_x=80.0,
            shooter_y=25.0,
            off_lineup={},
            def_lineup={},
            has_contest=True,
            contest_result="offense_win",
            contest_margin=120.0,
            shot_defense_score_raw=40.0,
            shooter_player=self._shooter(ag=80),
            shot_score_pre_defense=200.0,
            off_team=self._team(),
            def_team=self._team(),
            result_type="MAKE",
            dunk_stamp=dunk_stamp,
        )
        assert turn["micro_movement_family"] == "drive_dunk"
        assert turn["uses_shot_arc"] is False

    def test_dunk_miss_metadata_and_post_shot_bounce(self):
        from BackEnd.engine.skeleton_step_emitter import _build_post_shot_sub_steps

        steps = build_shot_micro_steps(
            family_id="dunk",
            contest_result=None,
            start_coords={"s1": {"x": 85.0, "y": 25.0}},
            shooter_id="s1",
            defender_id=None,
            off_lineup={},
            def_lineup={},
            away_offense=False,
            clock_start={"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            shot_type="inside",
            next_step={"kind": "next_step", "index": 3},
            apply_contest_layer=False,
            result_type="MISS",
            dunk_miss=True,
        )
        meta = steps[-1]["start"]["advance_trigger"]["metadata"]
        assert meta["dunk_miss"] is True
        assert meta["yield_before_slam"] is False

        shoot_step = steps[-1]
        turn = {
            "result_type": "MISS",
            "micro_movement_family": "dunk",
            "dunk_miss": True,
            "shooter_id": "s1",
            "ball_bounce_x": 90.0,
            "ball_bounce_y": 26.0,
        }
        _build_post_shot_sub_steps(steps, turn, {}, {}, False)
        assert len(steps) == 3
        assert steps[-1]["start"]["advance_trigger"]["metadata"]["kind"] == "bounce"
        assert steps[-2]["end"]["next"] == {"kind": "next_step", "index": 2}

    def test_prepare_dunk_stamp_force_miss(self, monkeypatch):
        from BackEnd.engine.shot_micro_movements import prepare_dunk_stamp

        monkeypatch.setattr(
            "BackEnd.engine.shot_micro_movements.random.randint",
            lambda _a, _b: 21,
        )
        stamp, made = prepare_dunk_stamp(
            shot_type="inside",
            shooter_coord={"x": 85.0, "y": 25.0},
            shooter_player=self._shooter(height=80),
            off_team=self._team(),
            def_team=self._team(),
            shot_score_pre_defense=200.0,
            shot_defense_score_raw=50.0,
            made=True,
            away_offense=False,
        )
        assert stamp is not None
        assert stamp["force_miss"] is True
        assert made is False


class TestShootingFoulMicro:
    def test_is_shooting_foul_turn_signal(self):
        from BackEnd.engine.shot_micro_movements import is_shooting_foul_turn

        assert is_shooting_foul_turn({
            "foul_team": "DEFENSE",
            "foul_player_id": "d1",
            "next_play_type": "FREE_THROW",
            "free_throws_remaining": 2,
            "result_type": "MISS",
        })
        assert not is_shooting_foul_turn({
            "foul_team": "DEFENSE",
            "foul_player_id": "d1",
            "result_type": "BLOCKING_FOUL",
        })
        assert not is_shooting_foul_turn({
            "foul_team": "OFFENSE",
            "foul_player_id": "o1",
            "next_play_type": "FREE_THROW",
        })

    def test_animation_branch_forces_defense_win(self):
        from BackEnd.engine.shot_micro_movements import animation_branch_for_shot

        assert animation_branch_for_shot("offense_win", is_shooting_foul=True) == "defense_win"
        assert animation_branch_for_shot("offense_win", is_shooting_foul=False) == "offense_win"

    def test_shooting_foul_hack_on_shot_beat_not_gather(self):
        from BackEnd.engine.shot_micro_movements import _build_family_beats, build_shot_micro_steps

        beats = _build_family_beats(
            "pump_dribble_shoot",
            {"x": 75.0, "y": 30.0},
            away_offense=False,
            off_lineup={},
            all_coords={"s1": {"x": 75.0, "y": 30.0}, "d2": {"x": 77.0, "y": 28.0}},
            shooter_id="s1",
        )
        assert any(b.get("flourish") == "gather" for b in beats)

        steps = build_shot_micro_steps(
            family_id="pump_dribble_shoot",
            contest_result="offense_win",
            start_coords={"s1": {"x": 75.0, "y": 30.0}, "d2": {"x": 77.0, "y": 28.0}},
            shooter_id="s1",
            defender_id="d2",
            off_lineup={},
            def_lineup={},
            away_offense=False,
            clock_start={"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            shot_type="inside",
            next_step={"kind": "next_step", "index": 9},
            apply_contest_layer=True,
            is_shooting_foul=True,
        )
        shot_step = steps[-1]
        shot_fl = shot_step["start"]["flourish"]
        assert shot_fl["d2"]["kind"] == "hack"
        assert shot_fl["s1"]["kind"] == "rattle"
        assert shot_fl["s1"]["foul_rattle_mult"] == 1.5
        assert shot_step["start"]["advance_trigger"]["metadata"]["shooting_foul"] is True
        assert not any(
            (s.get("start", {}).get("flourish") or {}).get("d2", {}).get("kind") == "hack"
            for s in steps[:-1]
        )

    def test_offense_win_without_foul_keeps_separation(self):
        from BackEnd.engine.shot_micro_movements import build_shot_micro_steps

        steps = build_shot_micro_steps(
            family_id="fade_away",
            contest_result="offense_win",
            start_coords={"s1": {"x": 75.0, "y": 30.0}, "d2": {"x": 77.0, "y": 28.0}},
            shooter_id="s1",
            defender_id="d2",
            off_lineup={},
            def_lineup={},
            away_offense=False,
            clock_start={"clock_remaining": 10.0, "shot_clock_remaining": 8.0},
            shot_type="outside",
            next_step={"kind": "next_step", "index": 3},
            apply_contest_layer=True,
            is_shooting_foul=False,
        )
        shot_fl = steps[-1]["start"]["flourish"]
        assert shot_fl["d2"]["kind"] == "rattle"
        assert "hack" not in {v.get("kind") for v in shot_fl.values()}


def test_stamp_shooting_foul_skips_when_whistle_on_shot_beat():
    from BackEnd.engine.skeleton_step_emitter import _stamp_shooting_foul_on_miss_end

    step = {"end": {}}
    turn = {
        "result_type": "MISS",
        "next_play_type": "FREE_THROW",
        "foul_player_id": "d1",
        "shooting_foul_whistle_on_shot_beat": True,
    }
    _stamp_shooting_foul_on_miss_end(step, turn)
    assert "announcement" not in step["end"]
