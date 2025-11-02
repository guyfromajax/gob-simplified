from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bson import ObjectId
from pathlib import Path
import logging
from typing import Optional

from BackEnd.db import db

router = APIRouter()
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"

@router.get("/game-plan.html")
def serve_game_plan_html():
    """Return the game plan page so query params work in production."""
    return FileResponse(STATIC_DIR / "game-plan.html")

class GamePlanSettings(BaseModel):
    playcall_settings: dict[str, int]
    strategy_settings: dict[str, int]

class GamePlanRequest(BaseModel):
    mode: str  # "franchise", "tournament", "single"
    team_id: str
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None

class GamePlanUpdateRequest(BaseModel):
    mode: str
    team_id: str
    playcall_settings: dict[str, int]
    strategy_settings: dict[str, int]
    franchise_id: Optional[str] = None
    tournament_id: Optional[str] = None
    game_id: Optional[str] = None


def validate_settings(playcall_settings: dict, strategy_settings: dict):
    """Validate that settings are integers 0-4 and offense not all zero."""
    # Validate playcall_settings (offense)
    for key, value in playcall_settings.items():
        if not isinstance(value, int) or value < 0 or value > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Playcall setting '{key}' must be an integer between 0 and 4"
            )
    
    # Validate strategy_settings (defense/general)
    for key, value in strategy_settings.items():
        if not isinstance(value, int) or value < 0 or value > 4:
            raise HTTPException(
                status_code=400,
                detail=f"Strategy setting '{key}' must be an integer between 0 and 4"
            )
    
    # Ensure at least one offense setting is above 0
    if all(v == 0 for v in playcall_settings.values()):
        raise HTTPException(
            status_code=400,
            detail="At least one Offense setting must be above 'Never'. Please increase any Offense slider."
        )


def get_default_settings():
    """Return default settings (all set to 2 = Normal)."""
    return {
        "playcall_settings": {
            "Base": 2,
            "Freelance": 2,
            "Inside": 2,
            "Attack": 2,
            "Outside": 2,
            "Set": 2
        },
        "strategy_settings": {
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "half_court_trap": 2,
            "full_court_press": 2
        }
    }


def populate_team_plays(mode="single"):
    """
    Populate team plays from universal plays collection with tracking stats.
    
    Args:
        mode: "single", "tournament", or "franchise"
        
    Returns:
        dict: {play_name: play_data} with embedded game_stats and optionally season_stats
    """
    try:
        from BackEnd.db import plays_collection
        
        # Get all plays from universal collection
        all_plays = list(plays_collection.find({}))
        
        # Convert to dictionary format for team storage
        plays_dict = {}
        for play in all_plays:
            play_name = play["name"]
            play_data = {
                "play_id": str(play["_id"]),
                "name": play["name"],
                "play_type": play["play_type"], 
                "play_focus": play["play_focus"],
                "skeletons": play["skeletons"],
                "game_stats": {
                    "times_run": 0,
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
                    "effectiveness": 0.0
                }
            }
            
            # Add season_stats for tournament and franchise modes
            if mode in ["tournament", "franchise"]:
                play_data["season_stats"] = {
                    "times_run": 0,
                    "shot_attempts": 0,
                    "made_shots": 0,
                    "turnovers": 0,
                    "offensive_fouls": 0,
                    "defensive_fouls": 0,
                    "effectiveness": 0.0
                }
            
            plays_dict[play_name] = play_data
        
        return plays_dict
    except Exception as e:
        print(f"🚨 Error in populate_team_plays: {e}")
        return {}


def ensure_team_objects_exist(mode: str, doc_id: str, team_id: str):
    """Ensure team objects exist in the mode document. Create with defaults if missing."""
    collection = None
    
    if mode == "franchise":
        collection = db.franchises
    elif mode == "tournament":
        collection = db.tournaments
    elif mode == "single":
        collection = db.games
    else:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    
    # Handle different ID formats for different modes
    if mode == "single":
        # For single game mode, game_id is a UUID string, not ObjectId
        doc = collection.find_one({"_id": doc_id})
    else:
        # For franchise/tournament modes, use ObjectId
        doc = collection.find_one({"_id": ObjectId(doc_id)})
    
    if not doc:
        raise HTTPException(status_code=404, detail=f"{mode.capitalize()} not found")
    
    # For franchise mode, ensure all 8 teams have objects
    if mode == "franchise":
        franchise_teams = doc.get("franchise_teams", {})
        teams = list(db.teams.find())
        defaults = get_default_settings()
        updated = False
        
        # Get populated plays for all teams
        populated_plays = populate_team_plays()
        
        for team in teams:
            tid = str(team["_id"])
            if tid not in franchise_teams:
                franchise_teams[tid] = {
                    "team_chemistry": team.get("team_chemistry", 0),
                    "offensive_efficiency": team.get("offensive_efficiency", 0),
                    "offensive_adjust": team.get("offensive_adjust", 0),
                    "defense_threshold": team.get("defense_threshold", 0),
                    "shot_threshold": team.get("shot_threshold", 0),
                    "turnover_threshold": team.get("turnover_threshold", 0),
                    "foul_threshold": team.get("foul_threshold", 0),
                    "rebound_modifier": team.get("rebound_modifier", 0),
                    "o_tendency_reads": team.get("o_tendency_reads", 0),
                    "d_tendency_reads": team.get("d_tendency_reads", 0),
                    "playcall_settings": defaults["playcall_settings"].copy(),
                    "strategy_settings": defaults["strategy_settings"].copy(),
                    "plays": populated_plays.copy()
                }
                updated = True
            elif "playcall_settings" not in franchise_teams[tid] or "strategy_settings" not in franchise_teams[tid] or not franchise_teams[tid].get("plays"):
                # Add missing settings to existing team object
                if "playcall_settings" not in franchise_teams[tid]:
                    franchise_teams[tid]["playcall_settings"] = defaults["playcall_settings"].copy()
                if "strategy_settings" not in franchise_teams[tid]:
                    franchise_teams[tid]["strategy_settings"] = defaults["strategy_settings"].copy()
                if not franchise_teams[tid].get("plays"):
                    franchise_teams[tid]["plays"] = populated_plays.copy()
                updated = True
        
        if updated:
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"franchise_teams": franchise_teams}}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {"franchise_teams": franchise_teams}}
                )
        
        return franchise_teams
    
    # For tournament and single game modes
    else:
        # Normalize team_id to ObjectId - try name first, then ObjectId
        team = db.teams.find_one({"name": team_id})
        if not team:
            try:
                team = db.teams.find_one({"_id": ObjectId(team_id)})
            except:
                pass
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        
        actual_team_id = str(team["_id"])
        
        # Check if team object exists
        team_key = f"teams.{actual_team_id}"
        team_obj = doc.get("teams", {}).get(actual_team_id)
        
        if not team_obj:
            # Create team object with defaults
            
            defaults = get_default_settings()
            populated_plays = populate_team_plays()
            team_obj = {
                "playcall_settings": defaults["playcall_settings"].copy(),
                "strategy_settings": defaults["strategy_settings"].copy(),
                "plays": populated_plays.copy()
            }
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": {f"{team_key}": team_obj}}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": {f"{team_key}": team_obj}}
                )
        elif "playcall_settings" not in team_obj or "strategy_settings" not in team_obj or not team_obj.get("plays"):
            # Add missing settings
            defaults = get_default_settings()
            populated_plays = populate_team_plays()
            updates = {}
            if "playcall_settings" not in team_obj:
                updates[f"{team_key}.playcall_settings"] = defaults["playcall_settings"].copy()
            if "strategy_settings" not in team_obj:
                updates[f"{team_key}.strategy_settings"] = defaults["strategy_settings"].copy()
            if not team_obj.get("plays"):
                updates[f"{team_key}.plays"] = populated_plays.copy()
            
            if mode == "single":
                collection.update_one(
                    {"_id": doc_id},
                    {"$set": updates}
                )
            else:
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$set": updates}
                )
        
        return doc.get("teams", {})


@router.get("/api/gameplan")
def get_gameplan(mode: str, team_id: str, franchise_id: str = None, tournament_id: str = None, game_id: str = None):
    """Get game plan settings for a team in the specified mode."""
    try:
        print(f"🔍 Gameplan API called with: mode={mode}, team_id={team_id}, franchise_id={franchise_id}, tournament_id={tournament_id}, game_id={game_id}")
        # Determine which collection to use
        if mode == "franchise":
            if not franchise_id:
                raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
            doc_id = franchise_id
            collection = db.franchises
        elif mode == "tournament":
            if not tournament_id:
                raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
            doc_id = tournament_id
            collection = db.tournaments
        elif mode == "single":
            if not game_id:
                raise HTTPException(status_code=400, detail="game_id required for single game mode")
            doc_id = game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
        
        # Ensure team objects exist (creates if missing)
        if mode == "franchise":
            franchise_teams = ensure_team_objects_exist(mode, doc_id, team_id)
            team_obj = franchise_teams.get(team_id, {})
        else:
            teams = ensure_team_objects_exist(mode, doc_id, team_id)
            # For tournament/single mode, get the actual team ID from the teams dict
            actual_team_id = None
            for tid in teams.keys():
                # Find the team that matches our input team_id (could be name or ObjectId)
                try:
                    team_doc = db.teams.find_one({"_id": ObjectId(tid)})
                except:
                    # If tid is not a valid ObjectId, skip this iteration
                    continue
                if team_doc and (team_doc["name"] == team_id or str(team_doc["_id"]) == team_id):
                    actual_team_id = tid
                    break
            team_obj = teams.get(actual_team_id, {}) if actual_team_id else {}
        
        # Get settings or return defaults
        defaults = get_default_settings()
        playcall_settings = team_obj.get("playcall_settings", defaults["playcall_settings"])
        strategy_settings = team_obj.get("strategy_settings", defaults["strategy_settings"])
        
        return {
            "playcall_settings": playcall_settings,
            "strategy_settings": strategy_settings
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"🚨 Error in get_gameplan: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error getting game plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/gameplan")
def update_gameplan(request: GamePlanUpdateRequest):
    """Update game plan settings for a team in the specified mode."""
    try:
        # Validate settings
        validate_settings(request.playcall_settings, request.strategy_settings)
        
        # Determine which collection to use
        if request.mode == "franchise":
            if not request.franchise_id:
                raise HTTPException(status_code=400, detail="franchise_id required for franchise mode")
            doc_id = request.franchise_id
            collection = db.franchises
        elif request.mode == "tournament":
            if not request.tournament_id:
                raise HTTPException(status_code=400, detail="tournament_id required for tournament mode")
            doc_id = request.tournament_id
            collection = db.tournaments
        elif request.mode == "single":
            if not request.game_id:
                raise HTTPException(status_code=400, detail="game_id required for single game mode")
            doc_id = request.game_id
            collection = db.games
        else:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
        # Ensure team objects exist first
        ensure_team_objects_exist(request.mode, doc_id, request.team_id)
        
        # Update settings in the appropriate document
        if request.mode == "franchise":
            update_fields = {
                f"franchise_teams.{request.team_id}.playcall_settings": request.playcall_settings,
                f"franchise_teams.{request.team_id}.strategy_settings": request.strategy_settings
            }
        else:
            update_fields = {
                f"teams.{request.team_id}.playcall_settings": request.playcall_settings,
                f"teams.{request.team_id}.strategy_settings": request.strategy_settings
            }
        
        # Handle different ID formats for different modes
        if request.mode == "single":
            result = collection.update_one(
                {"_id": doc_id},
                {"$set": update_fields}
            )
        else:
            result = collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_fields}
            )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"{request.mode.capitalize()} not found")
        
        logger.info(f"✅ Updated game plan for team {request.team_id} in {request.mode} mode")
        return {"success": True, "message": "Game plan saved successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating game plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

