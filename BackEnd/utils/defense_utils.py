"""
Utility functions for defensive playcall tracking and mapping.
"""

def map_defense_playcall_to_tracking_name(playcall: str) -> str:
    """
    Map defensive playcall identifier to tracking name for stats.
    
    Currently:
    - "Man" → "Man"
    - "Zone" → "2-3 Zone" (only one zone type right now)
    
    Future:
    - When multiple zone types are added, playcall will be "2-3 Zone", "3-2 Zone", etc.
    - This function can be updated to handle backward compatibility.
    
    Args:
        playcall: Defense playcall identifier ("Man" or "Zone")
        
    Returns:
        Tracking name for stats ("Man" or "2-3 Zone")
    """
    if playcall == "Zone":
        return "2-3 Zone"
    return playcall

