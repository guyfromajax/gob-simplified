from bson import ObjectId

from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import simulate_round, SimulateRequest
from BackEnd.db import tournaments_collection, games_collection


def test_simulate_round_records_results(monkeypatch):
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
    monkeypatch.setattr(
        "BackEnd.api.tournament_routes.stat_updater.finalize_game",
        lambda *args, **kwargs: None,
    )

    resp = simulate_round(SimulateRequest(tournament_id=str(tid)))
    assert "home" in resp and "away" in resp

    updated = tournaments_collection.find_one({"_id": tid})
    results = updated.get("results", [])
    assert len(results) == 3

    for idx, match in enumerate(updated["bracket"]["round1"]):
        if "A" in (match["home_team"], match["away_team"]):
            continue
        res = next(
            r for r in results if r["round"] == 1 and r["match_index"] == idx
        )
        assert res["home_team"] == match["home_team"]
        assert res["away_team"] == match["away_team"]
        assert res["score"][match["home_team"]] == 80
        assert res["score"][match["away_team"]] == 70
        assert res["winner"] == match["home_team"]
