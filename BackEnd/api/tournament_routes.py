from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from BackEnd.db import tournaments_collection, teams_collection, games_collection
from BackEnd.tournament.tournament_manager import TournamentManager
from BackEnd.main import run_simulation
from BackEnd.utils.game_summary_builder import build_game_summary
from BackEnd.utils.shared import summarize_game_state

router = APIRouter()

class TournamentRequest(BaseModel):
    user_team_id: str

class SimulateRequest(BaseModel):
    tournament_id: str

@router.post("/start-tournament")
def start_tournament(request: TournamentRequest):
    team_docs = list(teams_collection.find({}, {"name": 1}))
    all_team_ids = [team["name"] for team in team_docs]

    if request.user_team_id not in all_team_ids:
        raise HTTPException(status_code=400, detail="Invalid user_team_id")

    manager = TournamentManager(db={"tournaments": tournaments_collection}, user_team_id=request.user_team_id, all_team_ids=all_team_ids)
    tournament = manager.create_tournament()
    return tournament

@router.post("/simulate-tournament-round")
def simulate_round(request: SimulateRequest):
    tournament_doc = tournaments_collection.find_one({"_id": request.tournament_id})
    if not tournament_doc:
        raise HTTPException(status_code=404, detail="Tournament not found")

    manager = TournamentManager(db={"tournaments": tournaments_collection}, user_team_id=tournament_doc["user_team_id"], all_team_ids=[])
    manager.tournament = tournament_doc
    manager.tournament_id = tournament_doc["_id"]

    round_name = f"round{tournament_doc['current_round']}"
    matchups = tournament_doc["bracket"].get(round_name, [])

    for i, matchup in enumerate(matchups):
        if tournament_doc["user_team_id"] in [matchup["home_team"], matchup["away_team"]]:
            continue  # Skip user match
        game = run_simulation(matchup["home_team"], matchup["away_team"])
        summary = summarize_game_state(game)
        game_id = games_collection.insert_one(summary).inserted_id
        winner = matchup["home_team"] if summary["score"][matchup["home_team"]] > summary["score"][matchup["away_team"]] else matchup["away_team"]
        manager.save_game_result(round_name, i, str(game_id), winner)

    manager.advance_round()
    return tournaments_collection.find_one({"_id": request.tournament_id})
