# 1. Imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from BackEnd.main import main
from pymongo import MongoClient
import os



# 2. FastAPI App Setup
app = FastAPI()
#MongoDB Setup
# MONGO_URI = "mongodb://jamiejosephdavies:Vu23fYitD0kR6IoH@mvp-cluster.dsp46ta.mongodb.net:27017/?retryWrites=true&w=majority"
MONGO_URI = os.environ["MONGO_URI"]


client = MongoClient(MONGO_URI)
db = client["gob"]
games_collection = db["games"]

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
