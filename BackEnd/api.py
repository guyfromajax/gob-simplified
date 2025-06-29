# 1. Imports
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from BackEnd.constants import POSITION_LIST
import uuid
from BackEnd.main import run_simulation
from BackEnd.db import players_collection, teams_collection, games_collection
from BackEnd.utils.game_summary_builder import build_game_summary
from BackEnd.utils.shared import clean_mongo_ids, summarize_game_state
from pydantic import BaseModel
from fastapi import HTTPException
import pprint
from bson.json_util import dumps
from bson import ObjectId
from fastapi.staticfiles import StaticFiles
from BackEnd.models.animator import Animator    


app = FastAPI()
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
    print("🔍 Full request body:", request)


    game = run_simulation(home_team, away_team)
    print("Right before summarize_game_state")
    print("🧪 Turns sample:", game.turns[:3])  
    summary = summarize_game_state(game)

    # ✅ Minimal debug visibility
    print(f"✅ Game finished: {home_team} vs. {away_team}")
    print(f"🏀 Final Score: {game.score}")
    print(f"📊 Team Totals: {game.team_totals}")# show first few entries

    games_collection.insert_one(summary)
    summary.pop("_id", None)  # ✅ remove Mongo's ObjectId

    # ✅ Attach turn log and other details to return payload
    
    summary["turns"] = game.turns
    summary["home_team_name"] = game.home_team.name
    summary["away_team_name"] = game.away_team.name
    summary["score"] = game.score
    summary["home_team_id"] = game.home_team.team_id
    summary["players"] = []
    
    for pos, player in game.home_team.lineup.items():
        coords = player.coords if hasattr(player, "coords") and player.coords else {"x": 0, "y": 0}
        summary["players"].append({
            "playerId": player.player_id,
            "team": "home",  # for animation styling
            "team_id": game.home_team.team_id,  # for logos/colors later
            "pos": pos,
            "jersey": player.attributes.get("jersey", 1),
            "x": coords.get("x", 0),
            "y": coords.get("y", 0)
        })
    for pos, player in game.away_team.lineup.items():
        coords = player.coords if hasattr(player, "coords") and player.coords else {"x": 0, "y": 0}
        summary["players"].append({
            "playerId": player.player_id,
            "team": "away",
            "team_id": game.away_team.team_id,
            "pos": pos,
            "jersey": player.attributes.get("jersey", 6),  # adjust if needed
            "x": coords.get("x", 0),
            "y": coords.get("y", 0)
        })

    
    return summary


@app.get("/roster/{team_name}")
def get_team_roster(team_name: str):
    print(f"🔍 Endpoint hit: GET /roster/{team_name}")

    team = teams_collection.find_one({"name": team_name})
    if not team:
        print(f"❌ No team found with name: '{team_name}'")
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")

    player_ids = team.get("player_ids", [])
    if not player_ids:
        raise HTTPException(status_code=404, detail=f"No players found for team '{team_name}'")

    player_objects = list(players_collection.find({
        "_id": {"$in": player_ids}
    }))

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
        "team": team_name,
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
