"""
Utility functions for generating and managing game IDs across all game modes.
Standardizes game_id format to MongoDB ObjectId (24-character hex string).
"""
from __future__ import annotations

import random
import time
from typing import Any, Optional, Tuple

from bson import ObjectId


def generate_game_id() -> str:
    """
    Generate a game_id in MongoDB ObjectId format (24-character hex string).
    
    ObjectId format: 8-byte timestamp + 6-byte random + 4-byte counter
    This ensures uniqueness and compatibility with MongoDB operations.
    """
    # 8-byte timestamp (seconds since epoch)
    timestamp = int(time.time())
    timestamp_hex = format(timestamp, '08x')
    
    # 6-byte random value
    random_part = format(random.randint(0, 0xffffff), '06x')
    
    # 4-byte counter (additional randomness)
    counter = format(random.randint(0, 0xffff), '04x')
    
    # Additional 6 bytes for full 24-character ObjectId format
    extra_random = format(random.randint(0, 0xffffff), '06x')
    
    game_id = timestamp_hex + random_part + counter + extra_random
    
    # Ensure exactly 24 characters
    if len(game_id) < 24:
        game_id = game_id.ljust(24, '0')
    elif len(game_id) > 24:
        game_id = game_id[:24]
    
    return game_id


def validate_game_id(game_id: Optional[str]) -> bool:
    """
    Validate that a game_id is in the correct MongoDB ObjectId format.
    
    Args:
        game_id: The game_id to validate
        
    Returns:
        True if valid ObjectId format, False otherwise
    """
    if not game_id:
        return False
    
    # Check if it's a 24-character hex string
    if len(game_id) != 24:
        return False
    
    try:
        int(game_id, 16)
        return True
    except ValueError:
        return False


def normalize_game_id(game_id: Optional[str]) -> Optional[str]:
    """
    Normalize a game_id to ensure it's in the correct format.
    
    Args:
        game_id: The game_id to normalize
        
    Returns:
        Normalized game_id or None if invalid
    """
    if not game_id:
        return None
    
    # If it's already valid, return as-is
    if validate_game_id(game_id):
        return game_id
    
    # If it's a UUID format, convert to ObjectId format
    if len(game_id) == 36 and game_id.count('-') == 4:
        # Convert UUID to ObjectId format
        return generate_game_id()
    
    # For any other format, generate a new one
    return generate_game_id()


def find_game_doc(games_collection, game_id: str) -> Tuple[Optional[dict], Any]:
    """
    Find a game document by _id, trying the raw id then ObjectId when applicable.

    Returns (doc, effective_id) for updates. Avoids creating a string-id duplicate
    when the canonical record already uses ObjectId (or vice versa).
    """
    if games_collection is None or not game_id:
        return None, None
    saved = games_collection.find_one({"_id": game_id})
    if saved:
        return saved, game_id
    if isinstance(game_id, str) and len(game_id) == 24:
        try:
            oid = ObjectId(game_id)
            saved = games_collection.find_one({"_id": oid})
            if saved:
                return saved, oid
        except (ValueError, TypeError):
            pass
    return None, None


def resolve_game_write_id(games_collection, game_id: str):
    """Resolve the canonical _id to use for game writes."""
    _saved, effective_id = find_game_doc(games_collection, game_id)
    if effective_id is not None:
        return effective_id
    if isinstance(game_id, str) and len(game_id) == 24:
        try:
            return ObjectId(game_id)
        except (ValueError, TypeError):
            return game_id
    return game_id


def purge_game_id_format_duplicates(games_collection, game_id: str, *, keep_id: Any) -> None:
    """Delete alternate string/ObjectId duplicates for the same hex game id."""
    if games_collection is None or not game_id:
        return
    candidates = []
    if isinstance(game_id, str) and len(game_id) == 24:
        candidates.append(game_id)
        try:
            candidates.append(ObjectId(game_id))
        except (ValueError, TypeError):
            pass
    for alt_id in candidates:
        if alt_id != keep_id and str(alt_id) != str(keep_id):
            games_collection.delete_one({"_id": alt_id})


def franchise_matchup_claim_key(game: dict[str, Any]) -> Optional[str]:
    """
    Stable once-per-franchise-week matchup id for stat rollup idempotency.

    Prevents double-counting when two game documents (e.g. string vs ObjectId _id)
    exist for the same played game.
    """
    week = game.get("week")
    if week is None:
        return None
    home = game.get("home_team_id")
    away = game.get("away_team_id")
    if not home or not away:
        home = game.get("team2_id")
        away = game.get("team1_id")
    if not home or not away:
        return None
    left, right = sorted([str(home), str(away)])
    return f"{int(week)}:{left}:{right}"
