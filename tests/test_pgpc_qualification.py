"""Unit tests for PGPC question qualification (no GameManager / bson)."""

from BackEnd.pgpc_qualification import get_qualifying_pgpc_questions


def _row(pid, team_id, pts, **stats):
    base = {
        "PTS": pts,
        "FGM": 0,
        "FGA": 0,
        "3PTM": 0,
        "3PTA": 0,
        "FTM": 0,
        "FTA": 0,
        "REB": 0,
        "F": 0,
        "MIN": 32,
        "DEF_A": 0,
        "DEF_S": 0,
        "PIP": 0,
        "FB_PTS": 0,
    }
    base.update(stats)
    return {
        "playerId": pid,
        "team_id": team_id,
        "stats": base,
        "attributes": {"EM": 50, "CH": 0, "MO": 0, "NG": 1.0},
    }


def _base_teams(*, u_score, o_score, u_pbq, o_pbq):
    return {
        "T_USER": {
            "team_id": "T_USER",
            "score": u_score,
            "points_by_quarter": list(u_pbq),
            "attributes": {"team_chemistry": 25},
        },
        "T_OPP": {
            "team_id": "T_OPP",
            "score": o_score,
            "points_by_quarter": list(o_pbq),
            "attributes": {"team_chemistry": 18},
        },
    }


def _ctx(**kwargs):
    base = {
        "user_team_id": "T_USER",
        "opponent_team_id": "T_OPP",
        "user_won": True,
        "margin_user_minus_opp": 10,
        "overtime": False,
        "winning_streak_after_game": 0,
        "losing_streak_after_game": 0,
    }
    base.update(kwargs)
    return base


def test_win_generic_qualifies():
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=70,
            o_score=60,
            u_pbq=[20, 20, 15, 15],
            o_pbq=[15, 15, 15, 15],
        ),
        "players": [],
    }
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, _ctx())}
    assert "win_generic_01" in ids


def test_come_from_behind_win_uses_points_by_quarter():
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=70,
            o_score=60,
            u_pbq=[15, 15, 15],
            o_pbq=[20, 20, 10],
        ),
        "players": [],
    }
    ctx = _ctx(user_won=True, margin_user_minus_opp=10)
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, ctx)}
    assert "come_from_behind_win_01" in ids


def test_bench_outscores_starter_requires_opening_lineup():
    starters = [f"s{i}" for i in range(5)]
    bench = ["b1"]
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=80,
            o_score=70,
            u_pbq=[20, 20, 20, 20],
            o_pbq=[18, 18, 18, 16],
        ),
        "opening_lineup": {"T_USER": starters},
        "players": [
            *[ _row(s, "T_USER", 8) for s in starters ],
            _row("b1", "T_USER", 22),
        ],
    }
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, _ctx())}
    assert "bench_outperformer_01" in ids


def test_bench_pts_low_qualifies():
    starters = [f"s{i}" for i in range(5)]
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=60,
            o_score=55,
            u_pbq=[15, 15, 15, 15],
            o_pbq=[14, 14, 14, 13],
        ),
        "opening_lineup": {"T_USER": starters},
        "players": [
            *[ _row(s, "T_USER", 12) for s in starters ],
            _row("b1", "T_USER", 2),
            _row("b2", "T_USER", 1),
        ],
    }
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, _ctx())}
    assert "bench_scoring_low_01" in ids


def test_winning_streak_band_filter():
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=65,
            o_score=60,
            u_pbq=[16, 16, 16, 17],
            o_pbq=[15, 15, 15, 15],
        ),
        "players": [],
    }
    ctx = _ctx(winning_streak_after_game=5)
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, ctx)}
    assert "winning_streak_01" in ids


def test_tier_c_lead_changes_requires_blob():
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=65,
            o_score=60,
            u_pbq=[16, 16, 16, 17],
            o_pbq=[15, 15, 15, 15],
        ),
        "players": [],
    }
    without = {q["id"] for q in get_qualifying_pgpc_questions(game, _ctx())}
    assert "lead_changes_high_01" not in without

    game["pgpc_tier_c"] = {"lead_changes": 12}
    with_blob = {q["id"] for q in get_qualifying_pgpc_questions(game, _ctx())}
    assert "lead_changes_high_01" in with_blob


def test_major_upset_rank_gap():
    game = {
        "quarter": 4,
        "teams": _base_teams(
            u_score=72,
            o_score=68,
            u_pbq=[18, 18, 18, 18],
            o_pbq=[17, 17, 17, 17],
        ),
        "players": [],
    }
    ctx = _ctx(
        user_natl_rank=75,
        opponent_natl_rank=10,
    )
    ids = {q["id"] for q in get_qualifying_pgpc_questions(game, ctx)}
    assert "win_major_upset_01" in ids
