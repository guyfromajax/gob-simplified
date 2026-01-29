import pytest
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import (
    simulate_round,
    save_result,
    SimulateRequest,
    TournamentResultRequest,
    _team_oid_to_name,
)
from BackEnd.db import tournaments_collection, games_collection
from tests.tournament_test_helpers import seed_teams_ah


def test_simulate_round_records_results(monkeypatch):
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

    def fake_run_simulation(home, away):
        return {"home": home, "away": away}

    def fake_summarize(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 80, a: 70}}

    monkeypatch.setattr("BackEnd.api.tournament_routes.run_simulation", fake_run_simulation)
    monkeypatch.setattr("BackEnd.api.tournament_routes.summarize_game_state", fake_summarize)

    resp = simulate_round(SimulateRequest(tournament_id=str(tid)))
    assert "home" in resp and "away" in resp

    round1 = tournament["bracket"]["round1"]
    user_oid = tournament.get("user_team_object_id")
    for idx, match in enumerate(round1):
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            home_name = _team_oid_to_name(h) or h
            away_name = _team_oid_to_name(a) or a
            break
    else:
        pytest.fail("User matchup not found")

    game_id = games_collection.insert_one({"score": {home_name: 90, away_name: 80}}).inserted_id
    save_result(
        TournamentResultRequest(
            tournament_id=str(tid),
            game_id=str(game_id),
            winner="A",
        )
    )

    updated = tournaments_collection.find_one({"_id": tid})
    results = updated.get("results", [])
    assert len(results) == 4

    for idx, match in enumerate(updated["bracket"]["round1"]):
        h, a = str(match["home_team"]), str(match["away_team"])
        if user_oid and user_oid in (h, a):
            continue
        res = next(
            (r for r in results if r["round"] == 1 and r["match_index"] == idx),
            None,
        )
        assert res is not None
        assert res["home_team"] == h
        assert res["away_team"] == a
        home_name = _team_oid_to_name(h) or h
        away_name = _team_oid_to_name(a) or a
        assert res["score"].get(home_name) == 80
        assert res["score"].get(away_name) == 70
        assert res["winner"] == h
