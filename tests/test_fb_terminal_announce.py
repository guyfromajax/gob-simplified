"""Regression tests for the backend-owned Fast Break foul/turnover freeze
announcement (`fb_terminal_announce`)."""

import random

from BackEnd.engine.fb_terminal_announce import (
    FB_TERMINAL_ANNOUNCE_HOLD_MS,
    build_fb_terminal_announcement,
    stamp_fb_terminal_freeze,
)


def _terminal_step():
    return {"start": {}, "end": {"coords": {}, "next": {"kind": "end_of_turn"}}}


def test_charge_builds_blocking_primary_announcement():
    ann = build_fb_terminal_announcement(
        {"result_type": "CHARGE", "foul_player_id": "OFF-PG", "shooter_id": "OFF-PG"},
        is_away_offense=False,
    )
    assert ann is not None
    assert ann["text"] == "CHARGE!"
    assert ann["style"] == "primary"
    assert ann["hold_ms"] == FB_TERMINAL_ANNOUNCE_HOLD_MS
    assert "non_blocking" not in ann  # must freeze
    # Offensive foul colors to the defending side (home offense -> away defense).
    assert ann["team"] == "away"
    assert ann["player_data"] == {"playerId": "OFF-PG"}
    assert "duke-charging.wav" in ann["meta"]["sfx"]


def test_defensive_foul_uses_offense_team_and_weighted_text():
    ann = build_fb_terminal_announcement(
        {"result_type": "FOUL", "foul_team": "DEFENSE", "foul_player_id": "DEF-SF"},
        is_away_offense=False,
        rng=random.Random(1),
    )
    assert ann is not None
    assert ann["team"] == "home"  # offense side
    assert ann["hold_ms"] == FB_TERMINAL_ANNOUNCE_HOLD_MS
    assert ann["text"]  # some defensive foul language
    assert ann["meta"]["sfx"] == "whistle-1-lowervol.wav"


def test_offensive_foul_colors_to_defense():
    ann = build_fb_terminal_announcement(
        {"result_type": "FOUL", "foul_team": "OFFENSE", "foul_player_id": "OFF-C"},
        is_away_offense=True,
        rng=random.Random(1),
    )
    assert ann is not None
    # Away offense -> defense side is home.
    assert ann["team"] == "home"


def test_dead_ball_turnover_text_and_team():
    ann = build_fb_terminal_announcement(
        {"result_type": "DEAD BALL", "shooter_id": "OFF-PG", "text": "turnover!"},
        is_away_offense=False,
        rng=random.Random(0),
    )
    assert ann is not None
    assert ann["text"] in ("Travel!", "Double Dribble!")
    assert ann["team"] == "home"  # offense side turned it over
    assert ann["hold_ms"] == FB_TERMINAL_ANNOUNCE_HOLD_MS


def test_steal_turnover_is_excluded():
    ann = build_fb_terminal_announcement(
        {"result_type": "TURNOVER", "stealer_id": "DEF-PG", "text": "steal!"},
        is_away_offense=False,
    )
    assert ann is None


def test_batted_oob_is_excluded():
    assert (
        build_fb_terminal_announcement(
            {"result_type": "DEAD BALL", "rim_runner_bat_oob": True},
            is_away_offense=False,
        )
        is None
    )


def test_shooting_result_types_are_out_of_scope():
    for rt in ("MAKE", "MISS", "BLOCK", "DEFENSIVE_STOP"):
        assert (
            build_fb_terminal_announcement({"result_type": rt}, is_away_offense=False)
            is None
        )


def test_stamp_sets_terminal_announcement_and_turnover_suppression():
    steps = [_terminal_step()]
    turn_result = {"result_type": "DEAD BALL", "shooter_id": "OFF-PG"}
    stamped = stamp_fb_terminal_freeze(
        turn_result, steps, is_away_offense=False, rng=random.Random(0)
    )
    assert stamped is True
    assert steps[-1]["end"]["announcement"]["hold_ms"] == FB_TERMINAL_ANNOUNCE_HOLD_MS
    assert turn_result["suppress_turn_prep_turnover_announce"] is True
    assert "suppress_turn_prep_foul_announce" not in turn_result


def test_stamp_sets_foul_suppression_flag():
    steps = [_terminal_step()]
    turn_result = {"result_type": "CHARGE", "foul_player_id": "OFF-PG"}
    assert stamp_fb_terminal_freeze(turn_result, steps, is_away_offense=False) is True
    assert turn_result["suppress_turn_prep_foul_announce"] is True


def test_stamp_does_not_clobber_existing_announcement():
    steps = [_terminal_step()]
    steps[-1]["end"]["announcement"] = {"text": "Great Stop!", "style": "secondary"}
    turn_result = {"result_type": "FOUL", "foul_team": "DEFENSE", "foul_player_id": "x"}
    assert stamp_fb_terminal_freeze(turn_result, steps, is_away_offense=False) is False
    assert steps[-1]["end"]["announcement"]["text"] == "Great Stop!"


def test_stamp_noop_on_empty_steps():
    turn_result = {"result_type": "CHARGE", "foul_player_id": "x"}
    assert stamp_fb_terminal_freeze(turn_result, None, is_away_offense=False) is False
    assert stamp_fb_terminal_freeze(turn_result, [], is_away_offense=False) is False
