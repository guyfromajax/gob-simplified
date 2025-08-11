from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import save_result, TournamentResultRequest, sim_remaining, SimulateRequest
from BackEnd.db import tournaments_collection, games_collection


def test_sim_remaining_completes_bracket(monkeypatch):
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
            opponent = away if home == "A" else home
            break

    user_summary = {"score": {home: 90, away: 100}}
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
