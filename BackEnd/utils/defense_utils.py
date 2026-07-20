"""
Utility functions for defensive playcall tracking and mapping.
"""

from BackEnd.utils.sim_random import sim_rng as random
from typing import Any, Dict, Optional

_LINEUP_POSITIONS = ("PG", "SG", "SF", "PF", "C")


def random_defender_fallback_position() -> str:
    """Random lineup slot when man/zone cannot assign a defender position (replaces fixed PG)."""
    return random.choice(_LINEUP_POSITIONS)


def defender_player_from_random_slot_fallback(def_lineup: Optional[Dict[str, Any]]) -> Optional[Any]:
    """
    Pick the player at a random PG/SG/SF/PF/C slot; if that slot is empty, first non-None in lineup.
    """
    if not def_lineup:
        return None
    pos = random_defender_fallback_position()
    player = def_lineup.get(pos)
    if player is not None:
        return player
    return next((p for p in def_lineup.values() if p is not None), None)


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

