from flask import Flask, request, redirect, send_from_directory
from pathlib import Path

from BackEnd.db import db, franchise_state_collection
from BackEnd.models.franchise_manager import FranchiseManager

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "FrontEnd" / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))

@app.route('/franchise/start')
def franchise_start():
    state = franchise_state_collection.find_one({"_id": "state"})
    if state is None:
        return redirect('/franchise/select-team')
    return redirect('/franchise/command-center')

@app.route('/franchise/select-team', methods=['GET', 'POST'])
def franchise_select_team():
    if request.method == 'GET':
        return send_from_directory(str(STATIC_DIR), 'franchise-select-team.html')

    data = request.get_json(silent=True) or request.form
    team = data.get('team_name') or data.get('team')
    username = data.get('username', 'Coach')
    franchise_state_collection.delete_many({})
    franchise_state_collection.insert_one({
        "_id": "state",
        "team": team,
        "username": username,
    })
    manager = FranchiseManager(db)
    manager.initialize_season()
    return redirect('/franchise/command-center')

@app.route('/franchise/command-center')
def franchise_command_center():
    return send_from_directory(str(STATIC_DIR), 'franchise-command-center.html')

@app.route('/franchise/play-next-game', methods=['POST'])
def franchise_play_next_game():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    manager = FranchiseManager(db)
    manager.schedule = state.get('schedule', [])
    manager.week = state.get('week', 1)
    manager.run_week()
    return redirect('/animation')

@app.route('/animation')
def animation_page():
    return send_from_directory(str(STATIC_DIR), 'court.html')

if __name__ == '__main__':
    app.run(debug=True)
