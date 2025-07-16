# 1. Imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from BackEnd.constants import POSITION_LIST
import uuid
from BackEnd.main import run_simulation
from BackEnd.db import (
    players_collection,
    teams_collection,
    games_collection,
    tournaments_collection,
)
from BackEnd.utils.roster_loader import load_roster
from BackEnd.utils.game_summary_builder import build_game_summary
from BackEnd.utils.shared import clean_mongo_ids, summarize_game_state
from pydantic import BaseModel
from fastapi import HTTPException
import pprint
from bson.json_util import dumps
from bson import ObjectId
from fastapi.staticfiles import StaticFiles
from BackEnd.models.animator import Animator   
from .tournament_routes import router as tournament_router
import traceback
from unidecode import unidecode
from typing import Optional

app = FastAPI()
app.include_router(tournament_router)

# app.mount("/", StaticFiles(directory="FrontEnd", html=True), name="static")
# app.mount("/static", StaticFiles(directory="FrontEnd", html=True), name="static")
app.mount("/static", StaticFiles(directory="FrontEnd/static"), name="static")



print("🚀 Loaded FastAPI app from api.py")


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # allows all origins including null
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]  # ← add this line
)

class SimulationRequest(BaseModel):
    home_team: str
    away_team: str

# 4. Routes
@app.get("/")
def root():
    return {"message": "GOB Simulation API is live"}

@app.get("/teams")
def get_team_names():
    teams = teams_collection.find({}, {"name": 1, "_id": 0})
    return sorted([team["name"] for team in teams])


@app.post("/simulate")
def simulate_game(request: SimulationRequest):
    home_team = request.home_team
    away_team = request.away_team

    known_teams = [team["name"] for team in teams_collection.find({}, {"name": 1})]

    if home_team not in known_teams:
        raise HTTPException(status_code=400, detail=f"Unknown home_team: '{home_team}'")
    if away_team not in known_teams:
        raise HTTPException(status_code=400, detail=f"Unknown away_team: '{away_team}'")
    
    print("🔥 Simulate endpoint hit")
    print(f"Home: {request.home_team}, Away: {request.away_team}")

    # ✅ Add this line to print the full request body
    # print("🔍 Full request body:", request)


    game = run_simulation(home_team, away_team)
    # print("Right before summarize_game_state")
    # print("🧪 Turns sample:", game.turns[:3])  
    summary = summarize_game_state(game)

    # ✅ Minimal debug visibility
    # print(f"✅ Game finished: {home_team} vs. {away_team}")
    # print(f"🏀 Final Score: {game.score}")
    # print(f"📊 Team Totals: {game.team_totals}")# show first few entries

    print("\n🔎 DEBUGGING SUMMARY BEFORE INSERT")
    pprint.pprint(summary)

    try:
        print("🔍 About to insert summary into Mongo...")
        inserted_id = games_collection.insert_one(summary).inserted_id
        summary["_id"] = str(inserted_id)
        # games_collection.insert_one(summary)
        # summary.pop("_id", None)
    except Exception as e:
        print("🚨 Mongo insert failed:", e)
        traceback.print_exc()
    
    print("Inside simulate_game()\nReturning summary keys:", summary.keys())
    
    return summary


@app.get("/roster/{team_name}")
def get_team_roster(team_name: str, tournament_id: str | None = None):
    print(f"🔍 Endpoint hit: GET /roster/{team_name}")
    if tournament_id:
        print(f"🔍 Tournament ID provided but ignored: {tournament_id}")

    # Normalize team name to match DB
    normalized_name = unidecode(team_name.strip().replace("-", " ")).lower()

    all_teams = [t["name"] for t in teams_collection.find({}, {"name": 1})]
    match = next((t for t in all_teams if unidecode(t.lower().replace("-", " ")) == normalized_name), None)

    if not match:
        print(f"❌ No team found matching: {normalized_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    team_doc, player_objects = load_roster(match)
    ...


    if not player_objects:
        print(f"❌ No players found for {team_name}")
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    team = team_doc or {"name": team_name}


    display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]

    players = []
    for p in player_objects:
        attributes = p.get("attributes", {})  # safely get nested attributes dict
        players.append({
            "_id": str(p["_id"]),  # ✅ Add this line
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "attributes": {attr: attributes.get(attr, "--") for attr in display_attributes}
        })

    return {
        "team": team.get("name", team_name),
        "team_name": team.get("name", team_name),
        "players": players
    }


@app.get("/games")
def get_games():
    # Fetch the 10 most recent games (you can adjust this)
    games = list(games_collection.find().sort("_id", -1).limit(10))

    # Convert ObjectId to string for JSON serialization
    for game in games:
        game["_id"] = str(game["_id"])

    return JSONResponse(content=games)

@app.get("/player/{player_id}")
def get_player(player_id: str):
    try:
        player = players_collection.find_one({"_id": player_id})
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        player["_id"] = str(player["_id"])  # ensure JSON serializable
        return player
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# for route in app.routes:
#     print(f"🚀 Registered route: {route.path}")


@app.get("/teams/{team_id}/players")
def get_team_players(team_id: str):
    """Return roster data for a given team."""
    team_doc, players = load_roster(team_id)
    if not players:
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_id}'")

    display_attributes = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT", "NG"]
    players_data = []
    for p in players:
        attributes = p.get("attributes", {})
        players_data.append({
            "_id": str(p.get("_id")),
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "attributes": {attr: attributes.get(attr, "--") for attr in display_attributes},
        })

    return {
        "team": team_doc.get("name", team_id) if team_doc else team_id,
        "players": players_data,
    }


@app.get("/tournament/active")
def get_active_tournament(user_team_id: Optional[str] = "BENTLEY-TRUMAN"):
    """Fetch the most recently created active tournament or create one."""
    doc = tournaments_collection.find_one({"completed": False}, sort=[("created_at", -1)])
    if not doc:
        manager = TournamentManager(user_team_id=user_team_id, tournaments_collection=tournaments_collection)
        doc = manager.create_tournament()
    else:
        doc["_id"] = str(doc["_id"])
    return doc
