"""Phase 2 after-steal E2E tests (drive resolution path)."""

from types import SimpleNamespace

import pytest

from BackEnd.engine.after_steal_fast_break import resolve_after_steal_fast_break
from BackEnd.engine.after_steal_fast_break_step_emitter import (
    build_after_steal_fast_break_animation_steps,
)
from tests.test_utils import build_mock_game


@pytest.fixture(autouse=True)
def _enable_drive_resolution(monkeypatch):
    monkeypatch.setattr("BackEnd.constants.USE_FB_DRIVE_RESOLUTION_AFTER_STEAL", True)


def _seed_steal(game):
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    stealer = game.offense_team.lineup["PG"]
    stealer.player_id = "home-PG"
    game.game_state["last_stealer"] = stealer
    game.game_state["last_stealer_coords"] = {"x": 55.0, "y": 25.0}
    game.game_state["offensive_state"] = "FAST_BREAK"
    for team in (game.offense_team, game.defense_team):
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_a, **_k: None
            player.add_momentum = lambda *_a, **_k: None
    return stealer


def test_neutral_hco_returns_defensive_stop(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "NEUTRAL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "away-SF",
            "t_meet_game_seconds": 1.2,
            "t_drive_game_seconds": 1.2,
            "defender_end_coords": {"away-SF": meet},
            "defender_archetypes": {"away-SF": "sprint"},
            "stop_decision": {"action": "HCO"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "DEFENSIVE_STOP"
    assert result["fb_drive_resolution"]["outcome"] == "NEUTRAL"
    assert result["next_play_type"] == "HCO"


def test_pos_o_stamps_path_knots_on_turn(monkeypatch):
    meet = {"x": 70, "y": 25}
    shimmy = {"x": 70, "y": 27}
    shot_spot = {"x": 88, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                shimmy,
                shot_spot,
            ],
            "shot_spot": shot_spot,
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": True,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 200,
            "shot_score_pre_defense": 180,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "home-PG",
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MAKE"
    assert len(result["fb_drive_resolution"]["bh_path_knots"]) == 4


def test_emitter_includes_path_knots_metadata_for_pos_o():
    meet = {"x": 70, "y": 25}
    shot_spot = {"x": 88, "y": 25}
    end_coords = {
        f"home-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["home-PG"] = dict(shot_spot)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"away-{pos}"] = {"x": 50.0, "y": 25.0}

    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [
                {"x": 55, "y": 25},
                meet,
                {"x": 70, "y": 27},
                shot_spot,
            ],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    meta = steps[0]["start"]["advance_trigger"]["metadata"]
    assert "path_knots" in meta
    assert len(meta["path_knots"]) == 4


def test_meet_defensive_foul_non_bonus_routes_to_side_inbound(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "D_FOUL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "d8_credited_player_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "FOUL"
    assert result["next_play_type"] == "SIDE_INBOUND"
    assert game.game_state["free_throws_remaining"] == 0
    assert result["meet_coords"] == meet


def test_meet_defensive_foul_emits_meet_drive_step(monkeypatch):
    meet = {"x": 75, "y": 25}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "D_FOUL",
            "meet_x": meet["x"],
            "meet_y": meet["y"],
            "stopper_id": "Bentley-Truman-SF",
            "d8_credited_player_id": "Bentley-Truman-SF",
            "t_meet_game_seconds": 1.0,
            "t_drive_game_seconds": 1.0,
            "defender_end_coords": {"Bentley-Truman-SF": meet},
            "defender_archetypes": {"Bentley-Truman-SF": "sprint"},
        },
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)
    end_coords = {
        f"home-{pos}": {"x": 60.0, "y": 25.0}
        for pos in ("PG", "SG", "SF", "PF", "C")
    }
    end_coords["home-PG"] = dict(meet)
    for pos in ("PG", "SG", "SF", "PF", "C"):
        end_coords[f"away-{pos}"] = {"x": 50.0, "y": 25.0}
    result["after_steal_end_coords"] = end_coords
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]

    steps = build_after_steal_fast_break_animation_steps(result, game)
    assert steps is not None
    assert len(steps) == 1
    assert steps[0]["end"]["next"] == {"kind": "end_of_turn"}


def test_miss_with_oreb_stamps_ball_bounce_coords(monkeypatch):
    """A drive-resolution MISS that yields an OREB must stamp ball_bounce_x/y so
    the follow-up OREB putback turn's rebound-capture step renders (regression:
    the drive-resolution rewrite dropped ball_bounce, only stamping ballSpot,
    which the OREB emitter doesn't read → OREB fell back to legacy, un-animated
    + un-announced)."""
    shot_spot = {"x": 88, "y": 25}
    bounce = {"x": 86.0, "y": 27.0}
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration.resolve_fb_drive_step",
        lambda **kwargs: {
            "outcome": "POS_O",
            "meet_x": 70,
            "meet_y": 25,
            "shot_spot": shot_spot,
            "t_drive_game_seconds": 2.0,
            "contested": False,
            "defender_end_coords": {},
            "defender_archetypes": {},
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_shot_attempt",
        lambda **kwargs: {
            "made": False,
            "d_foul": False,
            "foul_player": None,
            "has_and_one": False,
            "free_throws_remaining": 0,
            "fouled_out_info": {},
            "shot_score": 40,
            "shot_score_pre_defense": 60,
            "shot_defense_score_for_sfx": 0,
            "shot_defense_score_raw": 0,
            "shot_variant": None,
            "shot_variant_extras": {},
            "contest_result": None,
            "contest_margin": None,
            "shot_type": "attack",
            "contested": False,
            "shot_defender": None,
            "shot_defender_id": None,
            "select_and_stamp_shot_micro_kwargs": {
                "shot_type": "attack",
                "shooter_id": "home-PG",
                "shooter_x": 88.0,
                "shooter_y": 25.0,
                "off_lineup": {},
                "def_lineup": {},
                "has_contest": False,
                "contest_result": None,
                "contest_margin": None,
                "shot_defense_score_raw": 0.0,
            },
        },
    )
    monkeypatch.setattr(
        "BackEnd.engine.after_steal_drive_integration._resolve_rebound_on_miss",
        lambda **kwargs: (
            False,
            "OREB",
            dict(bounce),
            {"offense_rebounders": ["home-C"], "defense_rebounders": ["away-C"]},
            "home-C",
        ),
    )

    game = build_mock_game()
    _seed_steal(game)
    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MISS"
    assert result["next_play_type"] == "OREB"
    assert result["ballSpot"] == bounce
    assert result["ball_bounce_x"] == bounce["x"]
    assert result["ball_bounce_y"] == bounce["y"]


def test_fb_start_announcement_is_secondary_and_non_blocking():
    """The ``Fast Break!`` drive-start callout (shared by after-steal AND CR via
    ``_build_drive_step``) must be a secondary, non-blocking ribbon — otherwise
    the FE routes it to the center overlay and freezes the court ~1s."""
    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _fb_secondary_announcement,
    )

    ann = _fb_secondary_announcement("home")
    assert ann["text"] == "Fast Break!"
    assert ann["style"] == "secondary"
    assert ann["non_blocking"] is True


def test_suppress_fast_break_stinger_flags_only_fast_break_callouts():
    """Steal FBs keep the ``Fast Break!`` ribbon but must not play the court
    stinger — every FB callout gets ``meta.suppressCourtSfx`` while other
    announcements are left untouched."""
    from BackEnd.engine.after_steal_fast_break_step_emitter import (
        _suppress_fast_break_stinger,
    )

    steps = [
        {"start": {"announcement": {"text": "Fast Break!", "style": "secondary"}}},
        {"start": {"announcement": {"text": "Great Stop!", "style": "secondary"}}},
        {"start": {}},
    ]
    _suppress_fast_break_stinger(steps)
    assert steps[0]["start"]["announcement"]["meta"]["suppressCourtSfx"] is True
    assert "meta" not in steps[1]["start"]["announcement"]
    # No crash on steps without an announcement.
    assert "announcement" not in steps[2]["start"]


def test_steal_fb_drive_callout_suppresses_court_stinger():
    """End-to-end: a built steal-FB turn's ``Fast Break!`` schema callout carries
    ``meta.suppressCourtSfx`` so the FE skips ``fast-break-braddock.mp3``."""
    shot_spot = {"x": 88, "y": 25}
    meet = {"x": 70, "y": 25}
    end_coords = {f"home-{p}": {"x": 60.0, "y": 25.0} for p in ("PG", "SG", "SF", "PF", "C")}
    end_coords.update({f"away-{p}": {"x": 62.0, "y": 25.0} for p in ("PG", "SG", "SF", "PF", "C")})
    turn_result = {
        "result_type": "MAKE",
        "shooter_id": "home-PG",
        "ball_handler": SimpleNamespace(player_id="home-PG"),
        "bh_target": shot_spot,
        "t_shooter_game_seconds": 2.0,
        "after_steal_end_coords": end_coords,
        "fb_drive_resolution": {
            "outcome": "POS_O",
            "bh_path_knots": [{"x": 55, "y": 25}, meet, {"x": 70, "y": 27}, shot_spot],
            "t_drive_game_seconds": 2.0,
        },
        "shot_score_pre_defense": 100,
        "shot_defense_score_for_sfx": 0,
        "shot_type": "attack",
        "shot_variant": None,
    }
    game = build_mock_game()
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.turns = [{"final_coords": {pid: {"x": 50.0, "y": 25.0} for pid in end_coords}}]
    for pos, player in game.home_team.lineup.items():
        player.player_id = f"home-{pos}"
    for pos, player in game.away_team.lineup.items():
        player.player_id = f"away-{pos}"

    steps = build_after_steal_fast_break_animation_steps(turn_result, game)
    assert steps is not None
    fb_callouts = [
        s for s in steps
        if (s.get("start") or {}).get("announcement", {}).get("text") == "Fast Break!"
    ]
    assert fb_callouts, "expected a Fast Break! callout on the steal FB drive"
    for step in fb_callouts:
        assert step["start"]["announcement"]["meta"]["suppressCourtSfx"] is True
