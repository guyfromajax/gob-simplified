"""Tests for PGPC snapshot types and franchise context builder."""

from BackEnd.pgpc_context import build_franchise_context_for_pgpc


def test_build_franchise_context_scores_and_margin():
    game_doc = {
        "quarter": 4,
        "teams": {
            "t_home": {
                "team_id": "t_home",
                "name": "Homers",
                "score": 72,
                "points_by_quarter": [20, 18, 17, 17],
            },
            "t_away": {
                "team_id": "t_away",
                "name": "Visitors",
                "score": 65,
                "points_by_quarter": [15, 16, 18, 16],
            },
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        user_team_id="t_home",
        opponent_team_id="t_away",
        franchise_id="f1",
        user_id="u1",
        week=3,
    )
    assert ctx["user_won"] is True
    assert ctx["margin_user_minus_opp"] == 7
    assert ctx["overtime"] is False
    assert ctx["franchise_id"] == "f1"
    assert ctx["week"] == 3


def test_build_franchise_context_overtime_from_extra_period_scoring():
    """OT leaves 5+ buckets; quarter may still be 5 before final bump in some saves."""
    game_doc = {
        "quarter": 5,
        "teams": {
            "a": {"team_id": "a", "score": 80, "points_by_quarter": [20, 20, 20, 15, 5]},
            "b": {"team_id": "b", "score": 78, "points_by_quarter": [18, 22, 20, 15, 3]},
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        user_team_id="a",
        opponent_team_id="b",
    )
    assert ctx["overtime"] is True
    assert ctx["user_won"] is True


def test_build_franchise_context_regulation_end_quarter_5_not_overtime():
    """After Q4 the engine stores quarter=5 even when no OT was played."""
    game_doc = {
        "quarter": 5,
        "teams": {
            "a": {"team_id": "a", "score": 80, "points_by_quarter": [20, 20, 20, 20]},
            "b": {"team_id": "b", "score": 70, "points_by_quarter": [18, 18, 17, 17]},
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        user_team_id="a",
        opponent_team_id="b",
    )
    assert ctx["overtime"] is False


def test_build_franchise_context_overtime_from_quarter_six_plus():
    game_doc = {
        "quarter": 6,
        "teams": {
            "a": {"team_id": "a", "score": 85, "points_by_quarter": [20, 20, 20, 15, 10]},
            "b": {"team_id": "b", "score": 82, "points_by_quarter": [18, 22, 20, 15, 7]},
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        user_team_id="a",
        opponent_team_id="b",
    )
    assert ctx["overtime"] is True


def test_build_franchise_context_team_lookup_by_nested_team_id():
    game_doc = {
        "quarter": 4,
        "teams": {
            "canonical_x": {"team_id": "real_uuid_1", "score": 50, "points_by_quarter": [10, 10, 15, 15]},
            "canonical_y": {"team_id": "real_uuid_2", "score": 60, "points_by_quarter": [12, 12, 18, 18]},
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        user_team_id="real_uuid_2",
        opponent_team_id="real_uuid_1",
    )
    assert ctx["user_won"] is True
    assert ctx["margin_user_minus_opp"] == 10


def test_build_franchise_context_streaks_from_results():
    game_doc = {
        "quarter": 4,
        "teams": {
            "t_u": {"team_id": "t_u", "score": 80, "points_by_quarter": [20, 20, 20, 20]},
            "t_opp": {"team_id": "t_opp", "score": 70, "points_by_quarter": [18, 18, 17, 17]},
        },
    }
    franchise_doc = {
        "results": {
            "1": [
                {
                    "away_id": "t_u",
                    "home_id": "o1",
                    "away_score": 70,
                    "home_score": 60,
                }
            ],
            "2": [
                {
                    "away_id": "o2",
                    "home_id": "t_u",
                    "away_score": 55,
                    "home_score": 60,
                }
            ],
        },
    }
    ctx = build_franchise_context_for_pgpc(
        game_doc,
        franchise_doc,
        user_team_id="t_u",
        opponent_team_id="t_opp",
        week=3,
        attach_db_fields=False,
    )
    assert ctx["winning_streak_after_game"] == 3
    assert ctx["losing_streak_after_game"] == 0
    assert ctx["season_series_vs_opponent"] == {"w": 1, "l": 0}
