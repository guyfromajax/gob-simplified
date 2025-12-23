"""
API routes for managing plays (offensive play skeletons).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from BackEnd.db import plays_collection
from bson import ObjectId
from pathlib import Path

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


@router.get("/play-builder-v2.html")
def serve_play_builder_v2():
    """Serve the Play Builder V2 HTML page."""
    return FileResponse(STATIC_DIR / "play-builder-v2.html")


@router.get("/play-builder.html")
def serve_play_builder():
    """Serve the Play Builder V1 HTML page."""
    return FileResponse(STATIC_DIR / "play-builder.html")


class PlayCreate(BaseModel):
    name: str
    play_type: str
    play_focus: Optional[str] = None  # Optional: None for Motion plays, string for Set Plays
    skeletons: Dict[str, Any]
    effectiveness: Optional[int] = 0  # Play effectiveness (0-100)
    cloaking: Optional[int] = 0  # Play cloaking (0-10)
    momentum: Optional[int] = 0  # Play momentum (0-10)
    copy: Optional[Dict[str, str]] = None  # Optional: copy_1, copy_2, copy_3 for play details page
    game_stats: Optional[Dict[str, int]] = None
    season_stats: Optional[Dict[str, int]] = None


@router.post("/api/plays")
async def create_play(play_data: PlayCreate):
    """
    Create or update a play in MongoDB.
    
    DEVELOPMENT MODE: If a play with the same name exists, it will be overwritten.
    This allows iterating on universal plays during development.
    
    Args:
        play_data: Play data from Play Builder
        
    Returns:
        dict: Created/updated play document with _id
    """
    # Convert to dict
    play_dict = play_data.dict()
    
    # Initialize play metrics if not provided (default to 0 for new plays)
    if play_dict.get("effectiveness") is None:
        play_dict["effectiveness"] = 0
    if play_dict.get("cloaking") is None:
        play_dict["cloaking"] = 0
    if play_dict.get("momentum") is None:
        play_dict["momentum"] = 0
    if not play_dict.get("copy"):
        play_dict["copy"] = {}
    
    # Initialize stats if not provided
    if not play_dict.get("game_stats"):
        play_dict["game_stats"] = {
            "times_run": 0,
            "shot_attempts": 0,
            "made_shots": 0,
            "turnovers": 0,
            "offensive_fouls": 0,
            "defensive_fouls": 0
        }
    
    if not play_dict.get("season_stats"):
        play_dict["season_stats"] = {
            "times_run": 0,
            "shot_attempts": 0,
            "made_shots": 0,
            "turnovers": 0,
            "offensive_fouls": 0,
            "defensive_fouls": 0
        }
    
    # UPSERT: Update if exists (by name), insert if new
    # This allows overwriting plays during development
    result = plays_collection.update_one(
        {"name": play_dict["name"]},  # Find by name
        {"$set": play_dict},           # Update all fields
        upsert=True                    # Insert if doesn't exist
    )
    
    # Get the document (either newly inserted or existing one)
    saved_play = plays_collection.find_one({"name": play_dict["name"]})
    saved_play["_id"] = str(saved_play["_id"])
    
    action = "updated" if result.matched_count > 0 else "created"
    
    return {
        "message": f"Play {action} successfully",
        "play": saved_play,
        "was_update": result.matched_count > 0
    }


@router.get("/api/plays")
async def get_all_plays():
    """
    Get all plays from the database.
    
    Returns:
        list: All play documents
    """
    plays = list(plays_collection.find({}))
    
    # Convert ObjectId to string
    for play in plays:
        play["_id"] = str(play["_id"])
    
    return {"plays": plays}


@router.get("/api/play/{play_name}")
async def get_play_by_name(play_name: str):
    """
    Get a specific play by name (URL decoded).
    
    Args:
        play_name: Play name (URL encoded, will be decoded)
        
    Returns:
        dict: Play document
    """
    try:
        from urllib.parse import unquote
        decoded_name = unquote(play_name)
        play = plays_collection.find_one({"name": decoded_name})
        if not play:
            raise HTTPException(status_code=404, detail=f"Play '{decoded_name}' not found")
        
        play["_id"] = str(play["_id"])
        return play
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/plays/{play_id}")
async def get_play(play_id: str):
    """
    Get a specific play by ID.
    
    Args:
        play_id: MongoDB ObjectId as string
        
    Returns:
        dict: Play document
    """
    try:
        play = plays_collection.find_one({"_id": ObjectId(play_id)})
        if not play:
            raise HTTPException(status_code=404, detail="Play not found")
        
        play["_id"] = str(play["_id"])
        return play
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/plays/{play_id}")
async def delete_play(play_id: str):
    """
    Delete a play by ID.
    
    Args:
        play_id: MongoDB ObjectId as string
        
    Returns:
        dict: Confirmation message
    """
    try:
        result = plays_collection.delete_one({"_id": ObjectId(play_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Play not found")
        
        return {"message": "Play deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

