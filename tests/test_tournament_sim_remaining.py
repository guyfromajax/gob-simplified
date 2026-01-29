from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import (
    save_result,
    TournamentResultRequest,
    sim_remaining,
    SimulateRequest,
    _team_oid_to_name,
)
from BackEnd.db import tournaments_collection, games_collection, teams_collection
from fastapi.testclient import TestClient
from BackEnd.api.api import app
from tests.tournament_test_helpers import seed_teams_ah


def test_sim_remaining_completes_bracket(monkeypatch):
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

    round1 = tournament["bracket"]["round1"]
    user_oid = tournament.get("user_team_object_id")
    for match in round1:
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            opponent = away_name if home_name == "A" else home_name
            break
    else:
        raise AssertionError("User matchup not found")

    user_summary = {"score": {home_name: 90, away_name: 100}}
    game_id = games_collection.insert_one(user_summary).inserted_id

    def fake_run_simulation(h, a):
        return {"home": h, "away": a}

    def fake_summarize(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 80, a: 70}}

    monkeypatch.setattr("BackEnd.api.tournament_routes.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.api.tournament_routes.summarize_game_state", fake_summarize)

    req = TournamentResultRequest(
        tournament_id=str(tid),
        game_id=str(game_id),
        winner=opponent,
    )
    save_result(req)

    sim_remaining(SimulateRequest(tournament_id=str(tid)))
    updated = tournaments_collection.find_one({"_id": tid})
    assert updated["completed"] is True
    assert len(updated.get("results", [])) == 7
    assert updated.get("champion")

    # idempotency
    sim_remaining(SimulateRequest(tournament_id=str(tid)))
    again = tournaments_collection.find_one({"_id": tid})
    assert len(again.get("results", [])) == 7
    assert again["completed"] is True


def test_sim_remaining_endpoint(monkeypatch):
    tournaments_collection.delete_many({})
    games_collection.delete_many({})
    teams_collection.delete_many({})

    for name in ["A", "B", "C", "D", "E", "F", "G", "H"]:
        teams_collection.insert_one({"name": name})

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tournament = manager.create_tournament()
    tid = ObjectId(tournament["_id"])

    round1 = tournament["bracket"]["round1"]
    user_oid = tournament.get("user_team_object_id")
    for match in round1:
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            opponent = away_name if home_name == "A" else home_name
            break
    else:
        raise AssertionError("User matchup not found")

    game_id = games_collection.insert_one({"score": {home_name: 90, away_name: 100}}).inserted_id

    def fake_run_simulation(h, a):
        return {"home": h, "away": a}

    def fake_summarize(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 80, a: 70}}

    monkeypatch.setattr("BackEnd.api.tournament_routes.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.api.tournament_routes.summarize_game_state", fake_summarize)
    monkeypatch.setattr(
        "BackEnd.api.tournament_routes.stat_updater.finalize_game",
        lambda *args, **kwargs: None,
    )

    save_result(
        TournamentResultRequest(
            tournament_id=str(tid),
            game_id=str(game_id),
            winner=opponent,
        )
    )

    client = TestClient(app)
    resp = client.post("/tournament/sim-remaining", json={"tournament_id": str(tid)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["completed"] is True
    assert len(data.get("results", [])) == 7
    assert data.get("champion")
