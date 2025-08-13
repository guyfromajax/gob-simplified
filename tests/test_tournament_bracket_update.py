import pytest
from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest
from BackEnd.db import tournaments_collection, games_collection
from BackEnd.tournament.bracket_logic import update_bracket_from_results


def test_update_bracket_uses_saved_results(monkeypatch):
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
    assert updated["current_round"] == 2
    assert len(updated["bracket"]["round2"]) == 2

    winners = [m["winner"] for m in updated["bracket"]["round1"]]
    assert updated["bracket"]["round2"][0]["home_team"] == winners[0]
    assert updated["bracket"]["round2"][0]["away_team"] == winners[1]
    assert updated["bracket"]["round2"][1]["home_team"] == winners[2]
    assert updated["bracket"]["round2"][1]["away_team"] == winners[3]

    # Ensure running the bracket update again does not duplicate or advance
    update_bracket_from_results(str(tid))
    again = tournaments_collection.find_one({"_id": tid})
    assert again["current_round"] == 2
    assert again["bracket"]["round2"] == updated["bracket"]["round2"]


def test_update_bracket_uses_matchups_when_results_empty():
    tournaments_collection.delete_many({})
    games_collection.delete_many({})

    manager = TournamentManager(
        user_team_id="A",
        tournaments_collection=tournaments_collection,
        team_ids=["A", "B", "C", "D", "E", "F", "G", "H"],
    )
    tournament = manager.create_tournament()
    tid = ObjectId(tournament["_id"])

    # Populate winners directly in the bracket without any saved results
    for idx, match in enumerate(tournament["bracket"]["round1"]):
        manager.save_game_result("round1", idx, ObjectId(), match["home_team"])

    tournaments_collection.update_one({"_id": tid}, {"$set": {"results": []}})

    updated = update_bracket_from_results(str(tid))
    assert updated is not None
    assert updated["current_round"] == 2
    assert len(updated["bracket"]["round2"]) == 2

    winners = [m["winner"] for m in updated["bracket"]["round1"]]
    assert updated["bracket"]["round2"][0]["home_team"] == winners[0]
    assert updated["bracket"]["round2"][0]["away_team"] == winners[1]
    assert updated["bracket"]["round2"][1]["home_team"] == winners[2]
    assert updated["bracket"]["round2"][1]["away_team"] == winners[3]
