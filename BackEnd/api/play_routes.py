"""
API routes for managing plays (offensive play skeletons).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from BackEnd.db import plays_collection
from bson import ObjectId

router = APIRouter()


class PlayCreate(BaseModel):
    name: str
    play_type: str
    play_focus: str
    skeletons: Dict[str, Any]
    game_stats: Optional[Dict[str, int]] = None
    season_stats: Optional[Dict[str, int]] = None


@router.post("/api/plays")
async def create_play(play_data: PlayCreate):
    """
    Create a new play and save to MongoDB.
    
    Args:
        play_data: Play data from Play Builder
        
    Returns:
        dict: Created play document with _id
    """
    # Convert to dict
    play_dict = play_data.dict()
    
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
    
    # Insert into MongoDB
    result = plays_collection.insert_one(play_dict)
    
    # Return created document
    play_dict["_id"] = str(result.inserted_id)
    
    return {
        "message": "Play created successfully",
        "play": play_dict
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

