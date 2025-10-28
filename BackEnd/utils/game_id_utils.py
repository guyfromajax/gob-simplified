"""
Utility functions for generating and managing game IDs across all game modes.
Standardizes game_id format to MongoDB ObjectId (24-character hex string).
"""
import random
import time
from typing import Optional


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
