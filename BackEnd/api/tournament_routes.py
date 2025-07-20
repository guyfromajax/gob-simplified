from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from BackEnd.db import tournaments_collection, teams_collection, games_collection
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.main import run_simulation
from BackEnd.utils.shared import summarize_game_state
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
            winner = (
                matchup["home_team"]
                if summary["score"][matchup["home_team"]] > summary["score"][matchup["away_team"]]
                else matchup["away_team"]
            )
            manager.save_game_result(round_name, i, str(game_id), winner)

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
    from bson import ObjectId

    tournament_id = ObjectId(request.tournament_id)
    tournament = tournaments_collection.find_one({"_id": tournament_id})

    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # find and update the user’s game in the current round
    round_key = f"round{tournament['current_round']}"
    for i, match in enumerate(tournament["bracket"][round_key]):
        if match["game_id"] is None and request.winner in [match["home_team"], match["away_team"]]:
            tournament["bracket"][round_key][i]["game_id"] = request.game_id
            tournament["bracket"][round_key][i]["winner"] = request.winner
            break

    tournaments_collection.update_one(
        {"_id": tournament_id},
        {"$set": {
            f"bracket.{round_key}": tournament["bracket"][round_key]
        }}
    )

    return {"status": "success"}
