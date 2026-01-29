import random
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
from fastapi import HTTPException
from tests.tournament_test_helpers import seed_teams_ah


def test_full_tournament_advances_bracket(monkeypatch):
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

    def fake_run_simulation(h, a):
        return {"home": h, "away": a}

    def fake_summarize(game):
        h = game["home"]
        a = game["away"]
        return {"score": {h: 80, a: 70}}

    monkeypatch.setattr(
        "BackEnd.api.tournament_routes.run_simulation", fake_run_simulation
    )
    monkeypatch.setattr(
        "BackEnd.api.tournament_routes.summarize_game_state", fake_summarize
    )

    # Round 1
    matchup = simulate_round(SimulateRequest(tournament_id=str(tid)))
    home, away = matchup["home"], matchup["away"]
    winner = "A"
    score = {home: 90, away: 80} if winner == home else {home: 80, away: 90}
    game_id = games_collection.insert_one({"score": score}).inserted_id
    save_result(
        TournamentResultRequest(
            tournament_id=str(tid), game_id=str(game_id), winner=winner
        )
    )

    tour = tournaments_collection.find_one({"_id": tid})
    assert tour["current_round"] == 2
    round2 = tour["bracket"]["round2"]
    assert len(round2) == 2
    r1_winners = [m["winner"] for m in tour["bracket"]["round1"]]
    assert round2[0]["home_team"] == r1_winners[0]
    assert round2[0]["away_team"] == r1_winners[1]
    assert round2[1]["home_team"] == r1_winners[2]
    assert round2[1]["away_team"] == r1_winners[3]

    # Round 2
    matchup2 = simulate_round(SimulateRequest(tournament_id=str(tid)))
    home2, away2 = matchup2["home"], matchup2["away"]
    winner2 = "A"
    score2 = {home2: 90, away2: 80} if winner2 == home2 else {home2: 80, away2: 90}
    game_id2 = games_collection.insert_one({"score": score2}).inserted_id
    save_result(
        TournamentResultRequest(
            tournament_id=str(tid), game_id=str(game_id2), winner=winner2
        )
    )

    tour2 = tournaments_collection.find_one({"_id": tid})
    assert tour2["current_round"] == 3
    final = tour2["bracket"]["final"]
    assert len(final) == 1
    r2_winners = [m["winner"] for m in tour2["bracket"]["round2"]]
    assert final[0]["home_team"] == r2_winners[0]
    assert final[0]["away_team"] == r2_winners[1]

    # Final
    try:
        matchup3 = simulate_round(SimulateRequest(tournament_id=str(tid)))
    except HTTPException as exc:
        assert exc.status_code == 409
        matchup3 = {}

    if "home" in matchup3:
        home3, away3 = matchup3["home"], matchup3["away"]
    else:
        final_match = tournaments_collection.find_one({"_id": tid})["bracket"]["final"][0]
        h3, a3 = final_match["home_team"], final_match["away_team"]
        home3 = _team_oid_to_name(h3) or str(h3)
        away3 = _team_oid_to_name(a3) or str(a3)
    winner3 = "A"
    score3 = {home3: 90, away3: 80} if winner3 == home3 else {home3: 80, away3: 90}
    game_id3 = games_collection.insert_one({"score": score3}).inserted_id
    save_result(
        TournamentResultRequest(
            tournament_id=str(tid), game_id=str(game_id3), winner=winner3
        )
    )

    tour3 = tournaments_collection.find_one({"_id": tid})
    assert tour3["current_round"] == 3
    assert tour3["completed"] is True
    assert str(tour3["champion"]) == str(tour3["user_team_object_id"])
    assert tour3["bracket"]["final"][0]["winner"] is not None
