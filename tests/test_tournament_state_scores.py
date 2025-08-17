from bson import ObjectId
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.api.tournament_routes import save_result, tournament_state, TournamentResultRequest
from BackEnd.db import tournaments_collection, games_collection


def test_tournament_state_includes_scores(monkeypatch):
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

    score_payload = {home: 75, away: 70}
    game_id = games_collection.insert_one({}).inserted_id

    req = TournamentResultRequest(
        tournament_id=str(tid),
        game_id=str(game_id),
        winner=home,
        score=score_payload,
    )
    save_result(req)

    state = tournament_state(str(tid))
    result_doc = next(r for r in state["results"] if r["match_index"] == user_index)
    assert result_doc["score"] == score_payload
    match_doc = state["bracket"]["round1"][user_index]
    assert match_doc["score"] == score_payload
