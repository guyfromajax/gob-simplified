from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from BackEnd.db import tournaments_collection, teams_collection, games_collection
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.tournament.bracket_logic import update_bracket_from_results
from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
from BackEnd.utils.stat_updater import apply_stats_from_summary
from bson import ObjectId

router = APIRouter()


class StartTournamentRequest(BaseModel):
    """Payload for creating a new tournament."""
    user_team_id: str

class TournamentResultRequest(BaseModel):
    tournament_id: str
    game_id: str
    winner: str

class SimulateRequest(BaseModel):
    tournament_id: str

@router.post("/start-tournament")
def start_tournament(request: StartTournamentRequest):
    team_docs = list(teams_collection.find({}, {"name": 1}))
    all_team_ids = [team["name"] for team in team_docs]

    if request.user_team_id not in all_team_ids:
        raise HTTPException(status_code=400, detail="Invalid user_team_id")

    manager = TournamentManager(
        user_team_id=request.user_team_id,
        tournaments_collection=tournaments_collection,
    )
    tournament = manager.create_tournament()
    tournament["_id"] = str(tournament["_id"])
    return tournament

@router.post("/simulate-tournament-round")
def simulate_round(request: SimulateRequest):
    """Simulate all non-user games for the current round and return the user's
    matchup. If the user game has already been played, a flag is returned."""

    try:
        try:
            tournament_id = ObjectId(request.tournament_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid tournament_id")

        tournament_doc = tournaments_collection.find_one({"_id": tournament_id})
        if not tournament_doc:
            raise HTTPException(status_code=404, detail="Tournament not found")

        manager = TournamentManager(tournaments_collection=tournaments_collection)
        manager.tournament = tournament_doc
        manager.tournament_id = tournament_id

        round_name = f"round{tournament_doc['current_round']}"
        matchups = tournament_doc["bracket"].get(round_name, [])

        user_team_id = tournament_doc.get("user_team_id")
        user_matchup = None
        already_played = False

        for i, matchup in enumerate(matchups):
            if user_team_id in [matchup["home_team"], matchup["away_team"]]:
                user_matchup = {"home": matchup["home_team"], "away": matchup["away_team"]}
                if matchup.get("game_id"):
                    already_played = True
                continue  # skip sim for user game

            # Skip games already simulated
            if matchup.get("game_id"):
                continue

            game = run_simulation(matchup["home_team"], matchup["away_team"])
            summary = summarize_game_state(game)
            game_id = games_collection.insert_one(summary).inserted_id
            #add a print statement here to show team name and score for each team after the game is simulated
            print(f"Home team: {matchup['home_team']} - Score: {summary['score'][matchup['home_team']]}")
            print(f"Away team: {matchup['away_team']} - Score: {summary['score'][matchup['away_team']]}")
            winner = (
                matchup["home_team"]
                if summary["score"][matchup["home_team"]] > summary["score"][matchup["away_team"]]
                else matchup["away_team"]
            )
            manager.save_game_result(round_name, i, str(game_id), winner)
            apply_stats_from_summary(summary, str(game_id), request.tournament_id)

        # Reload tournament to check if round is complete
        updated_doc = tournaments_collection.find_one({"_id": tournament_id})
        if updated_doc:
            all_done = all(m.get("winner") for m in updated_doc["bracket"].get(round_name, []))
            if all_done:
                manager.tournament = updated_doc
                manager.advance_round()

        if already_played:
            return {"already_played": True}
        if user_matchup:
            return user_matchup

        return {"error": "User matchup not found"}

    except Exception as e:
        print("🚨 Error in simulate_round:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tournament/save-result")
def save_result(request: TournamentResultRequest):
    """Save the user's game result, simulate remaining games in the round and
    persist all results to the tournament document.

    Each result entry includes home/away team, score, winner, round number and
    match index. A log message is printed for each database write indicating
    success or failure.
    """

    from bson import ObjectId

    tournament_id = ObjectId(request.tournament_id)
    tournament = tournaments_collection.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    round_num = tournament["current_round"]
    round_key = f"round{round_num}"

    manager = TournamentManager(tournaments_collection=tournaments_collection)
    manager.tournament = tournament
    manager.tournament_id = tournament_id

    def _log_result(result_doc):
        exists = tournaments_collection.find_one(
            {
                "_id": tournament_id,
                "results": {
                    "$elemMatch": {
                        "round": result_doc["round"],
                        "match_index": result_doc["match_index"],
                    }
                },
            }
        )
        if exists:
            return
        try:
            update_result = tournaments_collection.update_one(
                {"_id": tournament_id}, {"$push": {"results": result_doc}}
            )
            if update_result.modified_count == 1:
                print(
                    f"✅ Saved result for round {result_doc['round']} match {result_doc['match_index']}"
                )
            else:
                print(
                    f"⚠️ No document updated for round {result_doc['round']} match {result_doc['match_index']}"
                )
        except Exception as e:
            print(
                f"❌ Failed to save result for round {result_doc['round']} match {result_doc['match_index']}: {e}"
            )

    # Save user's game result
    user_match_index = None
    home_team = away_team = None
    for i, match in enumerate(tournament["bracket"][round_key]):
        if request.winner in [match["home_team"], match["away_team"]]:
            user_match_index = i
            home_team = match["home_team"]
            away_team = match["away_team"]
            summary = games_collection.find_one({"_id": ObjectId(request.game_id)}) or {}
            manager.save_game_result(round_key, i, request.game_id, request.winner, summary.get("score"))
            apply_stats_from_summary(summary, request.game_id, request.tournament_id)
            user_result = {
                "home_team": home_team,
                "away_team": away_team,
                "score": summary.get("score", {}),
                "winner": request.winner,
                "round": round_num,
                "match_index": i,
            }
            _log_result(user_result)
            break

    if user_match_index is None:
        raise HTTPException(status_code=400, detail="User matchup not found")

    # Ensure all match results are recorded
    for i, match in enumerate(manager.tournament["bracket"][round_key]):
        if i == user_match_index:
            continue
        if match.get("game_id"):
            summary = games_collection.find_one({"_id": ObjectId(match["game_id"])} ) or {}
            manager.save_game_result(round_key, i, match["game_id"], match["winner"], summary.get("score"))
            apply_stats_from_summary(summary, match["game_id"], request.tournament_id)
            result_doc = {
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                "score": summary.get("score", {}),
                "winner": match["winner"],
                "round": round_num,
                "match_index": i,
            }
            _log_result(result_doc)
            continue

        try:
            game = run_simulation(match["home_team"], match["away_team"])
            summary = summarize_game_state(game)
            insert_result = games_collection.insert_one(summary)
            game_id = insert_result.inserted_id
            apply_stats_from_summary(summary, str(game_id), request.tournament_id)
            print(f"✅ Game document inserted for round {round_num} match {i}")
        except Exception as e:
            print(
                f"❌ Failed to simulate or insert game for round {round_num} match {i}: {e}"
            )
            continue

        home = match["home_team"]
        away = match["away_team"]
        winner = home if summary["score"][home] > summary["score"][away] else away
        manager.save_game_result(round_key, i, str(game_id), winner, summary.get("score"))

        result_doc = {
            "home_team": home,
            "away_team": away,
            "score": summary.get("score", {}),
            "winner": winner,
            "round": round_num,
            "match_index": i,
        }
        _log_result(result_doc)

    # Use saved results to advance the bracket to the next round.  This relies
    # solely on the stored results and is safe to re-run (idempotent).
    update_bracket_from_results(tournament_id, tournaments_collection=tournaments_collection)

    return {"status": "success"}


@router.get("/tournament/state/{tournament_id}")
def tournament_state(tournament_id: str):
    """Return the current bracket state for a tournament."""
    try:
        tid = ObjectId(tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")
    doc = tournaments_collection.find_one({"_id": tid})
    if not doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    doc["_id"] = str(doc["_id"])
    return doc


@router.post("/tournament/sim-remaining")
def sim_remaining(request: SimulateRequest):
    """Simulate all remaining games until the bracket is complete.

    The endpoint is idempotent; already simulated games are skipped and existing
    results are preserved.  The updated tournament document is returned."""

    try:
        tid = ObjectId(request.tournament_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid tournament_id")

    tournament = tournaments_collection.find_one({"_id": tid})
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    manager = TournamentManager(tournaments_collection=tournaments_collection)
    manager.tournament_id = tid

    def _log_result(result_doc):
        exists = tournaments_collection.find_one(
            {
                "_id": tid,
                "results": {
                    "$elemMatch": {
                        "round": result_doc["round"],
                        "match_index": result_doc["match_index"],
                    }
                },
            }
        )
        if not exists:
            tournaments_collection.update_one(
                {"_id": tid}, {"$push": {"results": result_doc}}
            )

    while True:
        tournament = tournaments_collection.find_one({"_id": tid})
        if not tournament or tournament.get("completed"):
            break

        round_num = tournament.get("current_round", 1)
        round_key = "final" if round_num == 3 else f"round{round_num}"
        matchups = tournament.get("bracket", {}).get(round_key, [])
        manager.tournament = tournament

        for i, match in enumerate(matchups):
            if match.get("game_id"):
                exists = tournaments_collection.find_one(
                    {
                        "_id": tid,
                        "results": {
                            "$elemMatch": {"round": round_num, "match_index": i}
                        },
                    }
                )
                if not exists:
                    summary = games_collection.find_one({"_id": ObjectId(match["game_id"])}) or {}
                    apply_stats_from_summary(summary, match["game_id"], request.tournament_id)
                    result_doc = {
                        "home_team": match["home_team"],
                        "away_team": match["away_team"],
                        "score": summary.get("score", {}),
                        "winner": match.get("winner"),
                        "round": round_num,
                        "match_index": i,
                    }
                    _log_result(result_doc)
                continue

            game = run_simulation(match["home_team"], match["away_team"])
            summary = summarize_game_state(game)
            game_id = games_collection.insert_one(summary).inserted_id
            apply_stats_from_summary(summary, str(game_id), request.tournament_id)
            home = match["home_team"]
            away = match["away_team"]
            winner = home if summary["score"][home] > summary["score"][away] else away
            manager.save_game_result(round_key, i, str(game_id), winner, summary.get("score"))
            result_doc = {
                "home_team": home,
                "away_team": away,
                "score": summary.get("score", {}),
                "winner": winner,
                "round": round_num,
                "match_index": i,
            }
            _log_result(result_doc)

        update_bracket_from_results(tid, tournaments_collection=tournaments_collection)

    final_doc = tournaments_collection.find_one({"_id": tid})
    if not final_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")
    final_doc["_id"] = str(final_doc["_id"])
    return final_doc
