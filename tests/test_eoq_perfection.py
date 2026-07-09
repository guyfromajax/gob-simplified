"""Tests for EOQ perfection helpers (run-out clock, FLSS zones, inside paint)."""

import random

from BackEnd.constants import is_inside_paint_grid
from BackEnd.constants.shot_variants import (
    SHOT_VARIANT_AIRBALL,
    SHOT_VARIANT_BACK_OF_RIM,
    SHOT_VARIANT_BANK_MISS,
    SHOT_VARIANT_HEAVY_RATTLE,
    SHOT_VARIANT_LITTLE_RATTLE,
    SHOT_VARIANT_NORMAL_RATTLE,
    select_flss_heave_miss_variant,
)
from BackEnd.engine.eoq_perfection import (
    build_flss_skeleton_steps,
    classify_flss_zone,
    compute_flss_drive_plan,
    ensure_flss_miss_bounce_coords,
    flss_heave_sfx_eligible,
    resolve_flss_coach_sfx_stamp,
    roll_flss_airball_animation_coords,
    stamp_flss_airball_animation_coords,
    strip_terminal_rebound_fields,
)
from BackEnd.utils import situational_logic as sl


class _Team:
    def __init__(self, name, score):
        self.name = name
        self.team_id = name
        self.lineup = {}
        self.team_attributes = {"team_chemistry": 15}
        self.is_home_team = name == "Home"


class _Game:
    def __init__(self, quarter, off_score, def_score):
        self.quarter = quarter
        self.offense_team = _Team("Home", off_score)
        self.defense_team = _Team("Away", def_score)
        self.home_team = self.offense_team
        self.away_team = self.defense_team
        self.score = {"Home": off_score, "Away": def_score}
        self.game_state = {}


def test_is_inside_paint_grid_home_basket():
    assert is_inside_paint_grid(87, 25, home_basket=True) is True
    assert is_inside_paint_grid(80, 19, home_basket=True) is True
    assert is_inside_paint_grid(70, 25, home_basket=True) is False


def test_classify_flss_zone_home():
    assert classify_flss_zone(70, is_home_offense=True) == "normal"
    assert classify_flss_zone(60, is_home_offense=True) == "penalty"
    assert classify_flss_zone(40, is_home_offense=True) == "heave"


def test_classify_flss_zone_away():
    assert classify_flss_zone(30, is_home_offense=False) == "normal"
    assert classify_flss_zone(43, is_home_offense=False) == "penalty"
    assert classify_flss_zone(55, is_home_offense=False) == "heave"


def test_flss_heave_sfx_eligible():
    assert flss_heave_sfx_eligible(45, is_home_offense=True) is True
    assert flss_heave_sfx_eligible(55, is_home_offense=False) is True
    assert flss_heave_sfx_eligible(55, is_home_offense=True) is False


def test_resolve_flss_coach_sfx_stamp():
    from BackEnd.constants.flss_sfx import (
        FINAL_SHOT_SFX_FILES,
        FLSS_COACH_VO_HEAVE_FILE,
        FLSS_COACH_VO_LAUNCH_FILE,
        flss_coach_vo_pool,
    )

    assert flss_coach_vo_pool(flss_heave_sfx=False) == (FLSS_COACH_VO_LAUNCH_FILE,)
    assert flss_coach_vo_pool(flss_heave_sfx=True) == (
        FLSS_COACH_VO_LAUNCH_FILE,
        FLSS_COACH_VO_HEAVE_FILE,
    )

    base = resolve_flss_coach_sfx_stamp(flss_heave_sfx=False)
    assert base["event"] == "flss_vo"
    assert base["file"] == FLSS_COACH_VO_LAUNCH_FILE
    assert base["file"] not in FINAL_SHOT_SFX_FILES
    assert base["volume"] == 0.7
    heave = resolve_flss_coach_sfx_stamp(flss_heave_sfx=True)
    assert heave["file"] in (FLSS_COACH_VO_LAUNCH_FILE, FLSS_COACH_VO_HEAVE_FILE)
    assert heave["file"] not in FINAL_SHOT_SFX_FILES


def test_should_run_out_clock_q4():
    g = _Game(4, 80, 70)
    assert sl.should_run_out_clock(g, 25) is True
    g2 = _Game(4, 50, 80)
    assert sl.should_run_out_clock(g2, 25) is True
    g3 = _Game(4, 70, 68)
    assert sl.should_run_out_clock(g3, 25) is False
    g4 = _Game(2, 80, 70)
    assert sl.should_run_out_clock(g4, 25) is False


def test_strip_terminal_rebound_fields():
    payload = {
        "rebounderId": "p1",
        "rebound_type": "DREB",
        "ball_bounce_x": 85,
        "result_type": "MISS",
    }
    strip_terminal_rebound_fields(payload)
    assert "rebounderId" not in payload
    assert "rebound_type" not in payload
    assert payload["ball_bounce_x"] == 85


class _Shooter:
    attributes = {"AG": 50}


def test_flss_drive_plan_sprints_toward_basket_home():
    plan = compute_flss_drive_plan(_Shooter(), 50, 25, 7, is_home_offense=True)
    assert plan.drive_budget == 6.0
    assert plan.end_x > 50
    assert plan.end_x <= 91


def test_flss_drive_plan_pull_up_at_toplane():
    plan = compute_flss_drive_plan(_Shooter(), 60, 25, 10, is_home_offense=True)
    assert plan.pull_up_jumper is True
    assert plan.end_x == 74.0


def test_flss_drive_plan_no_pull_up_when_past_toplane():
    plan = compute_flss_drive_plan(_Shooter(), 78, 25, 10, is_home_offense=True)
    assert plan.pull_up_jumper is False
    assert plan.end_x > 78


def test_flss_drive_plan_away_offense():
    plan = compute_flss_drive_plan(_Shooter(), 50, 25, 7, is_home_offense=False)
    assert plan.drive_budget == 6.0
    assert plan.end_x < 50


def test_build_flss_skeleton_steps_includes_drive_and_shoot():
    plan = compute_flss_drive_plan(_Shooter(), 50, 25, 7, is_home_offense=True)
    steps = build_flss_skeleton_steps(
        "PG",
        spot_start="deep key",
        spot_end="topLane",
        start_coords={"x": 50, "y": 25},
        end_coords={"x": plan.end_x, "y": 25},
        drive_plan=plan,
    )
    assert len(steps) == 2
    assert steps[0]["_flss_sprint_drive"] is True
    assert steps[0]["pos_actions"]["PG"]["archetype"] == "sprint"
    assert steps[1]["pos_actions"]["PG"]["action"] == "shoot"
    assert steps[1]["_step_t_floor_game_seconds"] == 1.0


def test_select_flss_heave_miss_variant_bands():
    rattle = {SHOT_VARIANT_LITTLE_RATTLE, SHOT_VARIANT_NORMAL_RATTLE, SHOT_VARIANT_HEAVY_RATTLE}
    assert select_flss_heave_miss_variant(3, rng=random.Random(0)) in rattle
    assert select_flss_heave_miss_variant(5, rng=random.Random(1)) in rattle
    assert select_flss_heave_miss_variant(6, rng=random.Random(0)) == SHOT_VARIANT_BACK_OF_RIM
    assert select_flss_heave_miss_variant(15, rng=random.Random(0)) == SHOT_VARIANT_BACK_OF_RIM
    assert select_flss_heave_miss_variant(16, rng=random.Random(0)) == SHOT_VARIANT_BANK_MISS
    assert select_flss_heave_miss_variant(30, rng=random.Random(0)) == SHOT_VARIANT_BANK_MISS
    assert select_flss_heave_miss_variant(31, rng=random.Random(0)) == SHOT_VARIANT_AIRBALL


def test_ensure_flss_miss_bounce_coords_stamps_non_airball():
    game = _Game(4, 70, 68)
    result = {
        "flss": True,
        "result_type": "MISS",
        "shot_variant": "BACK_OF_RIM",
    }
    ensure_flss_miss_bounce_coords(
        game, result, shooter_coords={"x": 40, "y": 25}
    )
    assert result.get("ball_bounce_x") is not None
    assert result.get("ball_bounce_y") is not None


def test_ensure_flss_miss_bounce_coords_skips_airball():
    game = _Game(4, 70, 68)
    result = {
        "flss": True,
        "result_type": "MISS",
        "shot_variant": "AIRBALL",
    }
    ensure_flss_miss_bounce_coords(
        game, result, shooter_coords={"x": 40, "y": 25}
    )
    assert "ball_bounce_x" not in result
    assert "ball_bounce_y" not in result


def test_roll_flss_airball_animation_coords_home():
    coords = roll_flss_airball_animation_coords(away_offense=False, rng=random.Random(0))
    assert 86 <= coords["flss_airball_land_x"] <= 89
    assert 20 <= coords["flss_airball_land_y"] <= 30
    assert coords["flss_airball_oob_x"] == 97.0
    assert coords["flss_airball_oob_y"] == coords["flss_airball_land_y"]


def test_roll_flss_airball_animation_coords_away():
    coords = roll_flss_airball_animation_coords(away_offense=True, rng=random.Random(1))
    assert 11 <= coords["flss_airball_land_x"] <= 14
    assert coords["flss_airball_oob_x"] == 3.0
    assert coords["flss_airball_oob_y"] == coords["flss_airball_land_y"]


def test_stamp_flss_airball_animation_coords():
    game = _Game(4, 70, 68)
    result = {"flss": True, "result_type": "MISS", "shot_variant": "AIRBALL"}
    stamp_flss_airball_animation_coords(game, result)
    assert result.get("flss_airball_land_x") is not None
    assert result.get("flss_airball_oob_y") == result.get("flss_airball_land_y")
