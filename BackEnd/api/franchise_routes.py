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
    state = franchise_state_collection.find_one({"_id": "state"})
    if state is None:
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
