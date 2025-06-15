# 1. Imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from BackEnd.main import main

# 2. FastAPI App Setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return summarize_game_state(game_state)

