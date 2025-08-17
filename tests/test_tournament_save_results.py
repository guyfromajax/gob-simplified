import pytest
from bson import ObjectId
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import tournaments_collection, games_collection
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest


def test_save_result_simulates_remaining_games(monkeypatch):
    tournaments_collection.delete_many({})
    games_collection.delete_many({})

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tournament = manager.create_tournament()
    tid = ObjectId(tournament["_id"])

    round1 = tournament["bracket"]["round1"]
    for idx, match in enumerate(round1):
        if "A" in (match["home_team"], match["away_team"]):
            user_index = idx
            home = match["home_team"]
            away = match["away_team"]
            break

    user_summary = {"score": {home: 100, away: 90}}
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
    assert any(r["match_index"] == user_index and r["winner"] == "A" for r in updated["results"])


def test_save_result_uses_request_score(monkeypatch):
    tournaments_collection.delete_many({})
    games_collection.delete_many({})

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tournament = manager.create_tournament()
    tid = ObjectId(tournament["_id"])

    round1 = tournament["bracket"]["round1"]
    for idx, match in enumerate(round1):
        if "A" in (match["home_team"], match["away_team"]):
            user_index = idx
            home = match["home_team"]
            away = match["away_team"]
            break

    # insert game summary without score so request.score is used
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
        home: 70 if home == "A" else 65,
        away: 70 if away == "A" else 65,
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
