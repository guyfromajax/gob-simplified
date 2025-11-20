"""
Utility functions for defensive playcall tracking and mapping.
"""

def map_defense_playcall_to_tracking_name(playcall: str) -> str:
    """
    Map defensive playcall identifier to tracking name for stats.
    
    Since we now store specific play names in game_state (e.g., "2-3 Zone"),
    this function is mainly for backward compatibility and validation.
    
    Args:
        playcall: Defense playcall identifier ("Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone", etc.)
        
    Returns:
        Tracking name for stats (same as input, or mapped for backward compatibility)
    """
    # Backward compatibility: map generic "Zone" to "2-3 Zone" if it still exists
    if playcall == "Zone":
        return "2-3 Zone"
    # For specific zone names, return as-is
    return playcall

def is_zone_defense(defense_playcall: str) -> bool:
    """
    Check if a defensive playcall is a zone defense type.
    
    Args:
        defense_playcall: Defense playcall identifier (e.g., "Man", "2-3 Zone", "3-2 Zone")
        
    Returns:
        True if zone defense, False if man defense
    """
    # List of known zone defense types (will expand as more are added)
    zone_types = ["2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
    return defense_playcall in zone_types or defense_playcall.endswith(" Zone")

