"""Tests for frozen PGPC game snapshot pruning."""

from BackEnd.pgpc_snapshot_storage import build_pgpc_snapshot, prune_game_doc_for_pgpc_snapshot


def test_prune_drops_turns_and_keeps_teams_players():
    game = {
        "_id": "g1",
        "quarter": 4,
        "teams": {"a": {"score": 70}},
        "players": [{"playerId": "p1"}],
        "turns": [{"huge": True}] * 5000,
        "text_log": ["x"] * 1000,
    }
    pr = prune_game_doc_for_pgpc_snapshot(game)
    assert "turns" not in pr
    assert "text_log" not in pr
    assert pr["teams"] == {"a": {"score": 70}}
    assert len(pr["players"]) == 1


def test_build_pgpc_snapshot_includes_context_copy():
    game = {"quarter": 4, "teams": {}}
    ctx = {"user_won": True, "week": 2}
    snap = build_pgpc_snapshot(game, ctx)
    assert snap["context"]["user_won"] is True
    snap["context"]["user_won"] = False
    assert ctx["user_won"] is True
