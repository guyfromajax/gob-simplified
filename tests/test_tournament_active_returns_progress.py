import pytest
from bson import ObjectId
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import tournaments_collection, games_collection
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest
from BackEnd.api.api import get_active_tournament


def test_active_tournament_returns_progress(monkeypatch):
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
    for match in round1:
        if "A" in (match["home_team"], match["away_team"]):
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

    active = get_active_tournament()
    assert active["current_round"] == 2
    assert len(active["bracket"]["round2"]) == 2
    assert any(r["round"] == 1 for r in active.get("results", []))
