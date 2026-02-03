"""
API routes for managing plays (offensive play skeletons).
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from BackEnd.db import plays_collection, client
from BackEnd.utils.auth import require_admin_for_builder
from bson import ObjectId
from pathlib import Path

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


def get_staging_plays_collection():
    """
    Get plays collection from gob-staging database for safe testing.
    All play builders save to staging first, then can be migrated to production.
    
    Returns:
        Plays collection from gob-staging database
    """
    if not client:
        raise HTTPException(status_code=500, detail="MongoDB client not available")
    
    staging_db = client["gob-staging"]
    return staging_db["plays"]


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
async def create_play(play_data: PlayCreate, _user=Depends(require_admin_for_builder)):
    """
    Create or update a play in MongoDB.
    
    ✅ SAFETY: Always saves to gob-staging database for testing before production migration.
    
    DEVELOPMENT MODE: If a play with the same name exists, it will be overwritten.
    This allows iterating on universal plays during development.
    
    Args:
        play_data: Play data from Play Builder
        
    Returns:
        dict: Created/updated play document with _id
    """
    # Always use staging collection for safety
    staging_collection = get_staging_plays_collection()
    
    # Convert to dict
    play_dict = play_data.dict()
    
    # ✅ PRESERVE existing copy from database if not provided in update
    # This prevents Plays Builder from losing copy when Play Builder V2 saves
    existing_copy = None
    if play_dict.get("name"):
        existing_play = staging_collection.find_one({"name": play_dict["name"]})
        if existing_play and existing_play.get("copy"):
            existing_copy = existing_play.get("copy")
    
    # Initialize play metrics if not provided (default to 0 for new plays)
    if play_dict.get("effectiveness") is None:
        play_dict["effectiveness"] = 0
    if play_dict.get("cloaking") is None:
        play_dict["cloaking"] = 0
    if play_dict.get("momentum") is None:
        play_dict["momentum"] = 0
    
    # ✅ Only set copy to {} if it's truly missing AND no existing copy exists
    # If copy is provided in update, use it. Otherwise, preserve existing copy.
    if not play_dict.get("copy"):
        if existing_copy:
            play_dict["copy"] = existing_copy  # Preserve existing copy
        else:
            play_dict["copy"] = {}  # Only set to empty if no existing copy
    
    # ✅ Universal plays collection should NOT have game_stats or season_stats
    # Stats are only stored in team-specific play objects (teams.{team_id}.plays on game/tournament doc, or FTD for franchise)
    # Remove stats if they exist (they shouldn't be in universal collection)
    if "game_stats" in play_dict:
        del play_dict["game_stats"]
    if "season_stats" in play_dict:
        del play_dict["season_stats"]
    
    # UPSERT: Update if exists (by name), insert if new
    # This allows overwriting plays during development
    result = staging_collection.update_one(
        {"name": play_dict["name"]},  # Find by name
        {"$set": play_dict},           # Update all fields
        upsert=True                    # Insert if doesn't exist
    )
    
    # Get the document (either newly inserted or existing one)
    saved_play = staging_collection.find_one({"name": play_dict["name"]})
    saved_play["_id"] = str(saved_play["_id"])
    
    action = "updated" if result.matched_count > 0 else "created"
    
    return {
        "message": f"Play {action} successfully to gob-staging",
        "play": saved_play,
        "was_update": result.matched_count > 0
    }


@router.get("/api/plays")
async def get_all_plays():
    """
    Get all plays from the database.
    
    ✅ Returns plays from gob-staging (where builders save).
    
    Returns:
        list: All play documents
    """
    staging_collection = get_staging_plays_collection()
    plays = list(staging_collection.find({}))
    
    # Convert ObjectId to string
    for play in plays:
        play["_id"] = str(play["_id"])
    
    return {"plays": plays}


@router.get("/api/play/{play_name}")
async def get_play_by_name(play_name: str):
    """
    Get a specific play by name (URL decoded).
    
    ✅ Returns play from gob-staging (where builders save).
    
    Args:
        play_name: Play name (URL encoded, will be decoded)
        
    Returns:
        dict: Play document
    """
    try:
        from urllib.parse import unquote
        staging_collection = get_staging_plays_collection()
        decoded_name = unquote(play_name)
        play = staging_collection.find_one({"name": decoded_name})
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
    
    ✅ Returns play from gob-staging (where builders save).
    
    Args:
        play_id: MongoDB ObjectId as string
        
    Returns:
        dict: Play document
    """
    try:
        staging_collection = get_staging_plays_collection()
        play = staging_collection.find_one({"_id": ObjectId(play_id)})
        if not play:
            raise HTTPException(status_code=404, detail="Play not found")
        
        play["_id"] = str(play["_id"])
        return play
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/plays/{play_id}")
async def delete_play(play_id: str, _user=Depends(require_admin_for_builder)):
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

