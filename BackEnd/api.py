# 1. Imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
import os
import uuid
from BackEnd.main import main


# Mongo setup
MONGO_URI = os.environ["MONGO_URI"]
client = MongoClient(MONGO_URI)
db = client["gob"]
games_collection = db["games"]
players_collection = db["players"]
teams_collection = db["teams"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]  # ← add this line
)

# 3. Utility Functions (like summarize_game_state)
def summarize_game_state(game_state):
    return {
        "final_score": game_state["score"],
        "points_by_quarter": game_state["points_by_quarter"],
        "box_score": game_state["box_score"],
        "scouting": game_state["scouting_data"],
    }

# 4. Routes
@app.get("/")
def root():
    return {"message": "GOB Simulation API is live"}

@app.post("/simulate")
def simulate_game():
    game_state = main(return_game_state=True)
    summary = summarize_game_state(game_state)

    games_collection.insert_one(summary)  # ✅ Mongo write
    return summarize_game_state(game_state)

@app.get("/games")
def get_games():
    # Fetch the 10 most recent games (you can adjust this)
    games = list(games_collection.find().sort("_id", -1).limit(10))

    # Convert ObjectId to string for JSON serialization
    for game in games:
        game["_id"] = str(game["_id"])

    return JSONResponse(content=games)


@app.post("/setup_teams")
def setup_teams():
    # 🔄 TEMP FIX: clear the collection to avoid "already exist" block
    teams_collection.delete_many({})
    players_collection.delete_many({})
    print("✅ Cleared teams and players collections.")

    if teams_collection.count_documents({"name": "Lancaster"}) > 0:
        return {"message": "Teams already exist"}
    
    # Define players for Lancaster
    lancaster_players = [
    {
        "first_name": "Ervin", "last_name": "Miller", "SC": 39, "SH": 80, "ID": 43, "OD": 93, "PS": 97, "BH": 113,
        "RB": 47, "AG": 94, "ST": 47, "ND": 85, "IQ": 103, "FT": 100, "CH": 30, "EM": 0, "NG": 1
    },
    {
        "first_name": "Norris", "last_name": "Khan", "SC": 73, "SH": 97, "ID": 35, "OD": 90, "PS": 91, "BH": 63,
        "RB": 29, "AG": 65, "ST": 35, "ND": 112, "IQ": 75, "FT": 108, "CH": 44, "EM": 0, "NG": 1
    },
    {
        "first_name": "Wilbert", "last_name": "Struthers", "SC": 94, "SH": 65, "ID": 99, "OD": 67, "PS": 76, "BH": 79,
        "RB": 66, "AG": 54, "ST": 72, "ND": 27, "IQ": 62, "FT": 84, "CH": 58, "EM": 0, "NG": 1
    },
    {
        "first_name": "Cedric", "last_name": "Buckles", "SC": 87, "SH": 15, "ID": 93, "OD": 18, "PS": 42, "BH": 7,
        "RB": 94, "AG": 34, "ST": 97, "ND": 56, "IQ": 73, "FT": 28, "CH": 91, "EM": 0, "NG": 1
    },
    {
        "first_name": "Roger", "last_name": "Henrich", "SC": 69, "SH": 27, "ID": 93, "OD": 51, "PS": 58, "BH": 63,
        "RB": 42, "AG": 94, "ST": 57, "ND": 38, "IQ": 62, "FT": 24, "CH": 91, "EM": 0, "NG": 1
    },
    {
        "first_name": "Tmmy", "last_name": "Depaz", "SC": 54, "SH": 44, "ID": 67, "OD": 56, "PS": 56, "BH": 54,
        "RB": 55, "AG": 39, "ST": 64, "ND": 60, "IQ": 69, "FT": 79, "CH": 49, "EM": 0, "NG": 1
    },
    {
        "first_name": "Stuart", "last_name": "Marconi", "SC": 13, "SH": 44, "ID": 49, "OD": 90, "PS": 101, "BH": 63,
        "RB": 24, "AG": 77, "ST": 44, "ND": 33, "IQ": 36, "FT": 75, "CH": 64, "EM": 0, "NG": 1
    },
    {
        "first_name": "Benny", "last_name": "Pena", "SC": 27, "SH": 27, "ID": 53, "OD": 21, "PS": 23, "BH": 63,
        "RB": 68, "AG": 72, "ST": 44, "ND": 60, "IQ": 93, "FT": 34, "CH": 48, "EM": 0, "NG": 1
    },
    {
        "first_name": "Damon", "last_name": "Martin", "SC": 8, "SH": 94, "ID": 9, "OD": 30, "PS": 35, "BH": 47,
        "RB": 51, "AG": 63, "ST": 11, "ND": 7, "IQ": 17, "FT": 94, "CH": 19, "EM": 0, "NG": 1
    },
    {
        "first_name": "Joey", "last_name": "Giblin", "SC": 27, "SH": 51, "ID": 17, "OD": 30, "PS": 37, "BH": 9,
        "RB": 29, "AG": 29, "ST": 47, "ND": 63, "IQ": 69, "FT": 18, "CH": 41, "EM": 0, "NG": 1
    },
    {
        "first_name": "Jeremy", "last_name": "Johnson", "SC": 24, "SH": 35, "ID": 14, "OD": 6, "PS": 12, "BH": 27,
        "RB": 43, "AG": 41, "ST": 7, "ND": 34, "IQ": 93, "FT": 47, "CH": 99, "EM": 0, "NG": 1
    },
    {
        "first_name": "Ellis", "last_name": "Clemons", "SC": 21, "SH": 28, "ID": 11, "OD": 30, "PS": 36, "BH": 20,
        "RB": 28, "AG": 31, "ST": 4, "ND": 17, "IQ": 21, "FT": 44, "CH": 13, "EM": 0, "NG": 1
    }]

    bt_players = [
    {       
        "first_name": "Xenon", "last_name": "Fletcher", "SC": 44, "SH": 79, "ID": 44, "OD": 94, "PS": 100, "BH": 110,
        "RB": 105, "AG": 52, "ST": 50, "ND": 92, "IQ": 107, "FT": 104, "CH": 98, "EM": 0, "NG": 1
    },
    {
        "first_name": "Trent", "last_name": "Athens", "SC": 71, "SH": 104, "ID": 39, "OD": 93, "PS": 94, "BH": 59,
        "RB": 28, "AG": 69, "ST": 73, "ND": 114, "IQ": 66, "FT": 109, "CH": 25, "EM": 0, "NG": 1
    },
    {
        "first_name": "Ronnie", "last_name": "Rozier", "SC": 92, "SH": 67, "ID": 97, "OD": 73, "PS": 84, "BH": 64,
        "RB": 63, "AG": 51, "ST": 98, "ND": 73, "IQ": 65, "FT": 81, "CH": 17, "EM": 0, "NG": 1
    },
    {
        "first_name": "CJ", "last_name": "Castleman", "SC": 90, "SH": 17, "ID": 87, "OD": 17, "PS": 47, "BH": 11,
        "RB": 95, "AG": 91, "ST": 105, "ND": 63, "IQ": 83, "FT": 29, "CH": 11, "EM": 0, "NG": 1
    },
    {
        "first_name": "Kermit", "last_name": "Prospect", "SC": 65, "SH": 35, "ID": 84, "OD": 57, "PS": 67, "BH": 44,
        "RB": 49, "AG": 97, "ST": 68, "ND": 47, "IQ": 22, "FT": 95, "CH": 73, "EM": 0, "NG": 1
    },
    {
        "first_name": "Omar", "last_name": "Nola", "SC": 47, "SH": 34, "ID": 64, "OD": 58, "PS": 56, "BH": 54,
        "RB": 55, "AG": 37, "ST": 64, "ND": 68, "IQ": 48, "FT": 81, "CH": 38, "EM": 0, "NG": 1
    },
    {
        "first_name": "Von", "last_name": "Sanborn", "SC": 26, "SH": 46, "ID": 52, "OD": 94, "PS": 96, "BH": 57,
        "RB": 56, "AG": 87, "ST": 43, "ND": 35, "IQ": 32, "FT": 73, "CH": 34, "EM": 0, "NG": 1
    },
    {
        "first_name": "Freddie", "last_name": "Anderson", "SC": 38, "SH": 30, "ID": 53, "OD": 25, "PS": 20, "BH": 25,
        "RB": 62, "AG": 72, "ST": 39, "ND": 67, "IQ": 87, "FT": 34, "CH": 60, "EM": 0, "NG": 1
    },
    {
        "first_name": "Kent", "last_name": "McManus", "SC": 10, "SH": 92, "ID": 15, "OD": 37, "PS": 33, "BH": 57,
        "RB": 15, "AG": 57, "ST": 9, "ND": 14, "IQ": 17, "FT": 30, "CH": 62, "EM": 0, "NG": 1
    },
    {
        "first_name": "Clint", "last_name": "Workman", "SC": 31, "SH": 55, "ID": 19, "OD": 25, "PS": 11, "BH": 15,
        "RB": 28, "AG": 23, "ST": 56, "ND": 65, "IQ": 63, "FT": 76, "CH": 14, "EM": 0, "NG": 1
    },
    {
        "first_name": "Pete", "last_name": "Del Fino", "SC": 34, "SH": 31, "ID": 17, "OD": 12, "PS": 11, "BH": 37,
        "RB": 37, "AG": 35, "ST": 15, "ND": 36, "IQ": 89, "FT": 45, "CH": 24, "EM": 0, "NG": 1
    },
    {
        "first_name": "Delmont", "last_name": "Braggs", "SC": 25, "SH": 34, "ID": 13, "OD": 28, "PS": 36, "BH": 28,
        "RB": 28, "AG": 34, "ST": 26, "ND": 23, "IQ": 22, "FT": 37, "CH": 84, "EM": 0, "NG": 1
    }]



    # Save players and capture their IDs
    def insert_players(team_name, players):
        player_ids = []
        for player in players:
            player["team"] = team_name
            player["_id"] = str(uuid.uuid4())
            players_collection.insert_one(player)
            player_ids.append(player["_id"])
        return player_ids

    lancaster_ids = insert_players("Lancaster", lancaster_players)
    bt_ids = insert_players("Bentley-Truman", bt_players)

    # Save teams
    teams_collection.insert_many([
        {"_id": str(uuid.uuid4()), "name": "Lancaster", "player_ids": lancaster_ids},
        {"_id": str(uuid.uuid4()), "name": "Bentley-Truman", "player_ids": bt_ids},
    ])

    return {"message": "Teams and players created"}
