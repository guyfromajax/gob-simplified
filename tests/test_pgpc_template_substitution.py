"""PGPC template placeholder resolution."""

from __future__ import annotations

from BackEnd.pgpc_template_substitution import (
    apply_pgpc_substitutions,
    build_pgpc_substitutions,
)


def _ctx(**kwargs):
    base = {
        "user_team_id": "u1",
        "opponent_team_id": "o1",
        "winning_streak_after_game": 4,
        "losing_streak_after_game": 0,
        "prestige_drop_streak": 5,
    }
    base.update(kwargs)
    return base


def _game():
    return {
        "teams": {
            "u1": {"name": "User U", "team_id": "u1", "score": 80},
            "o1": {"name": "Opp College", "team_id": "o1", "score": 70},
        },
        "players": [
            {
                "playerId": "p1",
                "team_id": "u1",
                "first_name": "Sam",
                "last_name": "Jones",
                "stats": {
                    "PTS": 28,
                    "REB": 11,
                    "3PTM": 5,
                    "F": 4,
                    "FTM": 3,
                    "FTA": 10,
                    "MIN": 35,
                    "FGM": 10,
                    "FGA": 20,
                    "FB_PTS": 8,
                    "PIP": 14,
                },
            },
            {
                "playerId": "os",
                "team_id": "o1",
                "stats": {
                    "PTS": 5,
                    "FGM": 2,
                    "FGA": 10,
                    "FB_PTS": 18,
                    "PIP": 4,
                },
            },
        ],
        "opening_lineup": {"u1": ["p1", "x2", "x3", "x4", "x5"]},
        "pgpc_tier_c": {
            "lead_changes": 7,
            "first_blood": {
                "user_run_before_opp_score": 9,
                "opponent_run_before_user_score": 6,
            },
            "unanswered_run": {"user_longest": 12, "opponent_longest": 15},
            "early_foul_trouble": {"by_player": {"p1": 3}},
        },
    }


def test_build_substitutions_core_stats():
    g = _game()
    ctx = _ctx()
    ctx["player_overall_rt"] = {"os": 90.0}
    row = g["players"][0]
    subs = build_pgpc_substitutions(
        g, ctx, slot_player=row, player_slot="foul_trouble"
    )
    assert subs["{win_streak}"] == "4"
    assert subs["{opponent_name}"] == "Opp College"
    assert subs["{user_fg_pct}"] == "50"
    assert subs["{opp_fg_pct}"] == "20"
    assert subs["{fg_pct_gap}"] == "30"
    assert subs["{fb_pts_gap}"] == "10"
    assert subs["{pip_gap}"] == "10"
    assert subs["{bench_pts}"] == "0"
    assert subs["{lead_changes}"] == "7"
    assert subs["{opening_run}"] == "9"
    assert subs["{opp_opening_run}"] == "6"
    assert subs["{user_run}"] == "12"
    assert subs["{opp_run}"] == "15"
    assert subs["{opp_star_pts}"] == "5"
    assert subs["{player_pts}"] == "28"
    assert subs["{player_fouls}"] == "3"  # halftime for foul_trouble
    q = "Run {user_run}, {opponent_name}, {player_name}"
    out = apply_pgpc_substitutions(q, subs)
    assert "{player_name}" in out
    assert "12" in out and "Opp College" in out


def test_foul_out_uses_game_fouls_not_halftime():
    g = _game()
    ctx = _ctx()
    row = g["players"][0]
    subs = build_pgpc_substitutions(g, ctx, slot_player=row, player_slot="foul_out")
    assert subs["{player_fouls}"] == "4"


def test_apply_pgpc_substitutions_leaves_player_name():
    subs = {"{x}": "y", "{player_name}": "should_not_apply"}
    assert apply_pgpc_substitutions("Hi {player_name} {x}", subs) == "Hi {player_name} y"
