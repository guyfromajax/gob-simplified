"""Tests for PGPC `{player_name}` resolution by ``player_slot``."""

from BackEnd.pgpc_player_slot import (
    answer_name_for_pgpc_answers,
    resolve_player_display_names_for_slot,
    resolve_player_name_for_slot,
)


def _player(pid, name, pts, *, em=50, **stats_kw):
    stats = {
        "PTS": pts,
        "REB": 0,
        "3PTM": 0,
        "F": 0,
        "FTA": 0,
        "FTM": 0,
        "MIN": 32,
        "DEF_A": 0,
        "DEF_S": 0,
    }
    stats.update(stats_kw)
    return {
        "playerId": pid,
        "name": name,
        "team_id": "T1",
        "stats": stats,
        "attributes": {"EM": em},
    }


def test_high_scorer():
    game = {
        "players": [
            _player("1", "Alpha", 30),
            _player("2", "Beta", 12),
        ]
    }
    assert resolve_player_name_for_slot("high_scorer", game, "T1") == "Alpha"


def test_hot_shooter_prefers_three_point_makes():
    game = {
        "players": [
            _player("1", "Alpha", 20, **{"3PTM": 2}),
            _player("2", "Beta", 15, **{"3PTM": 6}),
        ]
    }
    assert resolve_player_name_for_slot("hot_shooter", game, "T1") == "Beta"


def test_top_rebounder():
    game = {
        "players": [
            _player("1", "Alpha", 10, REB=14),
            _player("2", "Beta", 12, REB=4),
        ]
    }
    assert resolve_player_name_for_slot("top_rebounder", game, "T1") == "Alpha"


def test_frustrated_player_min_em():
    game = {
        "players": [
            _player("1", "Low", 10, em=15),
            _player("2", "High", 8, em=90),
        ]
    }
    assert resolve_player_name_for_slot("frustrated_player", game, "T1") == "Low"


def test_surprise_scorer_low_rt_high_pts():
    ctx = {"player_overall_rt": {"1": 45.0, "2": 82.0}}
    game = {
        "players": [
            _player("1", "Sleeper", 22),
            _player("2", "Star", 30),
        ]
    }
    assert resolve_player_name_for_slot("surprise_scorer", game, "T1", ctx) == "Sleeper"


def test_zero_star_high_rt_no_points():
    ctx = {"player_overall_rt": {"1": 85.0, "2": 40.0}}
    game = {
        "players": [
            _player("1", "Frozen", 0),
            _player("2", "Scorer", 12),
        ]
    }
    assert resolve_player_name_for_slot("zero_star", game, "T1", ctx) == "Frozen"


def test_full_name_prefers_first_last_fields():
    p = {
        "playerId": "9",
        "first_name": "Jamie",
        "last_name": "Nguyen",
        "name": "Wrong Display",
        "team_id": "T1",
        "stats": {"PTS": 40, "REB": 0, "3PTM": 0, "F": 0, "FTA": 0, "FTM": 0, "MIN": 32, "DEF_A": 0, "DEF_S": 0},
        "attributes": {"EM": 50},
    }
    game = {"players": [p, _player("2", "Beta", 12)]}
    full, first = resolve_player_display_names_for_slot("high_scorer", game, "T1")
    assert full == "Jamie Nguyen"
    assert first == "Jamie"


def test_answer_token_first_only_when_question_used_placeholder():
    assert (
        answer_name_for_pgpc_answers(
            question_included_player_placeholder=True,
            full_name="Jamie Nguyen",
            first_name="Jamie",
        )
        == "Jamie"
    )
    assert (
        answer_name_for_pgpc_answers(
            question_included_player_placeholder=False,
            full_name="Jamie Nguyen",
            first_name="Jamie",
        )
        == "Jamie Nguyen"
    )
    assert (
        answer_name_for_pgpc_answers(
            question_included_player_placeholder=True,
            full_name="Cher",
            first_name="Cher",
        )
        == "Cher"
    )
