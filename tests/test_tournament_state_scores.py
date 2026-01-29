import pytest
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import save_result, tournament_state, TournamentResultRequest
from BackEnd.db import tournaments_collection, games_collection
from tests.tournament_test_helpers import seed_teams_ah


def test_tournament_state_includes_scores(monkeypatch):
    seed_teams_ah()
    tournaments_collection.delete_many({})
    games_collection.delete_many({})

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tournament = manager.create_tournament()
    tid = ObjectId(tournament["_id"])
    user_oid = tournament.get("user_team_object_id")

    round1 = tournament["bracket"]["round1"]
    for idx, match in enumerate(round1):
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            user_index = idx
            home = h
            away = a
            break
    else:
        pytest.fail("User matchup not found")

    score_payload = {home: 75, away: 70}
    game_id = games_collection.insert_one({}).inserted_id

    req = TournamentResultRequest(
        tournament_id=str(tid),
        game_id=str(game_id),
        winner="A",
        score=score_payload,
    )
    save_result(req)

    state = tournament_state(str(tid))
    results = state.get("results") or []
    result_doc = next((r for r in results if r["match_index"] == user_index), None)
    assert result_doc is not None
    assert result_doc["score"] == score_payload
    bracket_r1 = state.get("bracket", {}).get("round1") or []
    match_doc = bracket_r1[user_index] if user_index < len(bracket_r1) else None
    assert match_doc is not None
    assert match_doc["score"] == score_payload
