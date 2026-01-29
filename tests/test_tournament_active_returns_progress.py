import pytest
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.db import tournaments_collection, games_collection
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest, _team_oid_to_name
from BackEnd.api.api import get_active_tournament
from tests.tournament_test_helpers import seed_teams_ah


def test_active_tournament_returns_progress(monkeypatch):
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
    for match in round1:
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            break
    else:
        raise AssertionError("User matchup not found")

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

    active = get_active_tournament()
    assert active["current_round"] == 2
    assert len(active["bracket"]["round2"]) == 2
    assert any(r["round"] == 1 for r in active.get("results", []))
