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
    # Backward compatibility: map generic "Zone" to catalog name path for resolver
    if playcall in ("Zone", "zone"):
        return "2-3 Zone"
    # For specific zone names / slugs, return as-is
    return playcall

def is_zone_defense(defense_playcall: str) -> bool:
    """
    Check if a defensive playcall is a zone defense type.
    
    Args:
        defense_playcall: Defense playcall identifier (e.g., "Man", "2-3 Zone", "3-2 Zone")
        
    Returns:
        True if zone defense, False if man defense
    """
    from BackEnd.utils.defense_identity import is_zone_defense_id, resolve_to_defense_id

    if not defense_playcall or not isinstance(defense_playcall, str):
        return False
    did = resolve_to_defense_id(defense_playcall.strip())
    if did and is_zone_defense_id(did):
        return True
    # Legacy display strings / partial reads (empty DB in tests)
    zone_types = ["2-3 Zone", "3-2 Zone", "1-3-1 Zone"]
    return defense_playcall in zone_types or defense_playcall.endswith(" Zone")

