from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from pathlib import Path

from BackEnd.db import db, franchise_state_collection
from BackEnd.models.franchise_manager import FranchiseManager

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

@router.get("/franchise/start")
def franchise_start():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    if not state.get("team"):
        return RedirectResponse(url="/franchise/select-team")
    return RedirectResponse(url="/franchise/command-center")

@router.get("/franchise/select-team")
def get_select_team_page():
    return FileResponse(STATIC_DIR / "franchise-select-team.html")

class TeamSelection(BaseModel):
    team_name: str

@router.post("/franchise/select-team")
def select_team(selection: TeamSelection):
    franchise_state_collection.delete_many({})
    franchise_state_collection.insert_one({"_id": "state", "team": selection.team_name})
    manager = FranchiseManager(db)
    manager.initialize_season()
    return {"status": "ok"}

@router.get("/franchise/command-center")
def command_center():
    return FileResponse(STATIC_DIR / "franchise-command-center.html")


@router.get("/animation")
def get_animation_page():
    return FileResponse(STATIC_DIR / "court.html")


@router.post("/franchise/play-next-game")
def play_next_game():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    manager = FranchiseManager(db)
    manager.schedule = state.get("schedule", [])
    manager.week = state.get("week", 1)
    manager.run_week()
    return {"status": "ok"}


@router.get("/franchise/command-center/data")
def command_center_data():
    state = franchise_state_collection.find_one({"_id": "state"}) or {}
    team_name = state.get("team", "")
    team_doc = db.teams.find_one({"name": team_name}) or {}
    return {
        "team": team_name,
        "username": state.get("username", "Coach"),
        "seed": state.get("seed", 1),
        "team_chemistry": team_doc.get("team_chemistry", 0),
        "offense": team_doc.get("offense", "-"),
        "defense": team_doc.get("defense", "-"),
        "athleticism": team_doc.get("athleticism", "-"),
        "intangibles": team_doc.get("intangibles", "-"),
        "prestige": team_doc.get("prestige", "-"),
        "rank": team_doc.get("rank", "-")
    }


@router.get("/franchise/standings")
def standings():
    teams = list(db.teams.find({}, {"name": 1, "record": 1}))
    for t in teams:
        t["record"] = t.get("record", {"W": 0, "L": 0})
    teams.sort(key=lambda x: x["record"].get("W", 0), reverse=True)
    return {"standings": teams}


@router.get("/franchise/leaders")
def leaders():
    players = list(db.players.find())
    categories = ["PTS", "AST", "TPM", "REB", "BLK", "STL"]
    result = {}
    for cat in categories:
        sorted_players = sorted(
            players,
            key=lambda p: p.get("season_stats", {}).get(cat, 0),
            reverse=True
        )[:10]
        result[cat] = [
            {
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "team": p.get("team"),
                "value": p.get("season_stats", {}).get(cat, 0)
            }
            for p in sorted_players
        ]
    return result


@router.get("/franchise/team-stats")
def team_stats():
    teams = list(db.teams.find({}, {"name": 1}))
    output = []
    for t in teams:
        players = list(db.players.find({"team": t["name"]}))
        totals = {}
        for p in players:
            for stat, val in p.get("season_stats", {}).items():
                totals[stat] = totals.get(stat, 0) + val
        output.append({"team": t["name"], "stats": totals})
    return {"teams": output}


@router.get("/franchise/recruits")
def recruits():
    recs = list(db.recruits.find({}, {"_id": 0}).limit(40))
    return {"recruits": recs}
