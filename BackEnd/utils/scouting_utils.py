"""
Shared utilities for scouting report functionality.
Extracts play usage data from game documents for both franchise and tournament modes.
"""
from typing import List, Dict, Any, Optional
from bson import ObjectId
from BackEnd.db import teams_collection


def extract_plays_from_game_document(
    last_game: Dict[str, Any],
    team_name: str,
    team_object_id: str,
    team_id_field: Optional[str]
) -> List[Dict[str, Any]]:
    """
    Extract play usage data from a game document for scouting reports.
    
    This function handles the complex matching logic to find the correct team
    in the game document's teams object, which can be keyed by team_id strings,
    team names, or ObjectId strings.
    
    Args:
        last_game: Game document from games collection
        team_name: Name of the team (e.g., "Little York")
        team_object_id: ObjectId string of the team document
        team_id_field: team_id field value (e.g., "LITTLE_YORK")
    
    Returns:
        List of play dictionaries with name, times_run, successes, and total_playcalls
    """
    plays_data = []
    
    if not last_game:
        return plays_data
    
    # Extract play usage from game document
    teams_obj = last_game.get("teams", {})
    
    if not teams_obj:
        return plays_data
    
    # Game documents use team_id strings (like "LITTLE_YORK") as keys, not ObjectIds
    # We need to find the team key by matching team name or team_id
    team_key = None
    
    # Try multiple matching strategies
    for key in teams_obj.keys():
        # Strategy 1: Match by team_id field (e.g., "LITTLE_YORK")
        if team_id_field and key == team_id_field:
            team_key = key
            break
        # Strategy 2: Match by team name
        if key == team_name:
            team_key = key
            break
        # Strategy 3: Try to match by ObjectId (if key is an ObjectId string)
        try:
            if len(key) == 24:  # ObjectId string length
                key_obj_id = ObjectId(key)
                if key_obj_id == ObjectId(team_object_id):
                    team_key = key
                    break
                # Also check if this ObjectId matches our team
                key_team_doc = teams_collection.find_one({"_id": key_obj_id})
                if key_team_doc and key_team_doc.get("name") == team_name:
                    team_key = key
                    break
        except Exception:
            pass
    
    if not team_key:
        return plays_data
    
    team_plays = teams_obj.get(team_key, {}).get("plays", {})
    
    if not team_plays:
        return plays_data
    
    # Calculate total playcalls for usage %
    total_playcalls = 0
    for play_name, play_data in team_plays.items():
        game_stats = play_data.get("game_stats", {})
        times_run = game_stats.get("times_run", 0)
        total_playcalls += times_run
    
    # Build plays array
    for play_name, play_data in team_plays.items():
        game_stats = play_data.get("game_stats", {})
        times_run = game_stats.get("times_run", 0)
        successes = game_stats.get("successes", 0)
        
        if times_run > 0:  # Only include plays that were actually run
            plays_data.append({
                "name": play_name,
                "times_run": times_run,
                "successes": successes,
                "total_playcalls": total_playcalls
            })
    
    return plays_data

