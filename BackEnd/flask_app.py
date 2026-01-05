from flask import Flask, request, redirect, send_from_directory, jsonify
from pathlib import Path

from BackEnd.db import db, franchise_state_collection
from BackEnd.models.franchise_manager import FranchiseManager, RecruitManager

BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "FrontEnd" / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR))

@app.route('/franchise/start')
def franchise_start():
    # Note: franchise_state_collection is deprecated - using franchise document instead
    # This is legacy Flask app - consider migrating to FastAPI routes
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        if not state.get("team"):
            return redirect('/franchise/select-team')
        return redirect('/franchise/command-center')
    except Exception:
        # If collection doesn't exist (expected for new deployments), redirect to select-team
        return redirect('/franchise/select-team')

@app.route('/franchise/select-team', methods=['GET', 'POST'])
def franchise_select_team():
    if request.method == 'GET':
        return send_from_directory(str(STATIC_DIR), 'franchise-select-team.html')

    data = request.get_json(silent=True) or request.form
    team = data.get('team_name') or data.get('team')
    username = data.get('username', 'Coach')
    # Note: franchise_state_collection removed - using franchise document instead
    # This is legacy Flask app - consider migrating to FastAPI routes
    manager = FranchiseManager(db)
    manager.initialize_season()
    return redirect('/franchise/command-center')

@app.route('/franchise/command-center')
def franchise_command_center():
    return send_from_directory(str(STATIC_DIR), 'franchise-command-center.html')

@app.route('/franchise/play-next-game', methods=['POST'])
def franchise_play_next_game():
    # Note: franchise_state_collection is deprecated - should use franchise document
    # This is legacy Flask app - consider migrating to FastAPI routes
    try:
        state = franchise_state_collection.find_one({"_id": "state"}) or {}
        manager = FranchiseManager(db)
        manager.schedule = state.get('schedule', [])
        manager.week = state.get('week', 1)
        manager.run_week()
        return redirect('/animation')
    except Exception:
        # If collection doesn't exist, use defaults
        manager = FranchiseManager(db)
        manager.schedule = []
        manager.week = 1
        manager.run_week()
        return redirect('/animation')


@app.route('/franchise/debug/names')
def franchise_debug_names():
    manager = RecruitManager(db)
    data = manager.diagnostics or {"detail": "NAMES_DIAG not enabled"}
    return jsonify(data)

@app.route('/animation')
def animation_page():
    return send_from_directory(str(STATIC_DIR), 'court.html')

if __name__ == '__main__':
    app.run(debug=True)
