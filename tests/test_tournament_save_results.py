import pytest
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import tournaments_collection, games_collection
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest, _team_oid_to_name
from tests.tournament_test_helpers import seed_teams_ah


def test_save_result_simulates_remaining_games(monkeypatch):
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
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            break
    else:
        pytest.fail("User matchup not found")

    user_summary = {"score": {home_name: 100, away_name: 90}}
    game_id = games_collection.insert_one(user_summary).inserted_id

    def fake_run_simulation(h, a):
        return {"home": h, "away": a}

    def fake_summarize_game_state(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 60, a: 50}}

    monkeypatch.setattr("BackEnd.api.tournament_routes.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.api.tournament_routes.summarize_game_state", fake_summarize_game_state)

    req = TournamentResultRequest(
        tournament_id=str(tid),
        game_id=str(game_id),
        winner="A",
    )
    save_result(req)

    updated = tournaments_collection.find_one({"_id": tid})
    assert updated is not None
    assert "results" in updated
    assert len(updated["results"]) == 4
    assert any(r["match_index"] == user_index and r["winner"] == user_oid for r in updated["results"])


def test_save_result_uses_request_score(monkeypatch):
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
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            break
    else:
        pytest.fail("User matchup not found")

    game_id = games_collection.insert_one({}).inserted_id

    def fake_run_simulation(h, a):
        return {"home": h, "away": a}

    def fake_summarize_game_state(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 1, a: 0}}

    monkeypatch.setattr("BackEnd.api.tournament_routes.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.api.tournament_routes.summarize_game_state", fake_summarize_game_state)

    score_payload = {
        home_name: 70 if home_name == "A" else 65,
        away_name: 70 if away_name == "A" else 65,
    }

    req = TournamentResultRequest(
        tournament_id=str(tid),
        game_id=str(game_id),
        winner="A",
        score=score_payload,
    )
    save_result(req)

    updated = tournaments_collection.find_one({"_id": tid})
    match_doc = updated["bracket"]["round1"][user_index]
    assert match_doc["score"] == score_payload
    result_doc = next(r for r in updated["results"] if r["match_index"] == user_index)
    assert result_doc["score"] == score_payload
