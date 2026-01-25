"""
Man Defense Matchups Utility

Handles custom defensive matchup assignments for man-to-man defense.
Matchups reset to defaults (position-on-position) at the start of each break
(timeout, quarter break, foul out).
"""

from typing import Dict, Tuple, Optional

# Default matchups: position-on-position
DEFAULT_MATCHUPS = {
    "PG": "PG",
    "SG": "SG",
    "SF": "SF",
    "PF": "PF",
    "C": "C"
}

POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def get_default_matchups() -> Dict[str, str]:
    """
    Returns default position-on-position matchups.
    
    Returns:
        Dict mapping defensive position → offensive position (all same position)
    """
    return DEFAULT_MATCHUPS.copy()


def reset_matchups_to_defaults(game_state: Dict) -> None:
    """
    Resets man defense matchups to defaults in game_state.
    Called at the start of each break (timeout, quarter break, foul out).
    
    Args:
        game_state: Game state dictionary to update
    """
    game_state["man_defense_matchups"] = get_default_matchups()


def validate_man_defense_matchups(matchups: Dict[str, str]) -> Tuple[bool, Optional[str]]:
    """
    Validates that matchups form a valid 1-to-1 mapping.
    
    Requirements:
    - All 5 defensive positions (PG, SG, SF, PF, C) must be present as keys
    - All 5 offensive positions (PG, SG, SF, PF, C) must be present as values
    - No duplicate defensive positions (keys)
    - No duplicate offensive positions (values)
    - Each defensive position guards exactly one offensive position
    - Each offensive position is guarded by exactly one defensive position
    
    Args:
        matchups: Dict mapping defensive position → offensive position
                 Example: {"PG": "SG", "SG": "PG", "SF": "SF", "PF": "PF", "C": "C"}
    
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if matchups are valid, False otherwise
        - error_message: None if valid, error description if invalid
    """
    if not isinstance(matchups, dict):
        return False, "Matchups must be a dictionary"
    
    # Check all 5 defensive positions are present
    missing_defensive = [pos for pos in POSITIONS if pos not in matchups]
    if missing_defensive:
        return False, f"Missing defensive positions: {', '.join(missing_defensive)}"
    
    # Check all values are valid offensive positions
    invalid_offensive = [val for val in matchups.values() if val not in POSITIONS]
    if invalid_offensive:
        return False, f"Invalid offensive positions: {', '.join(invalid_offensive)}"
    
    # Check no duplicate defensive positions (shouldn't happen with dict, but defensive check)
    defensive_positions = list(matchups.keys())
    if len(defensive_positions) != len(set(defensive_positions)):
        return False, "Duplicate defensive positions found"
    
    # Check no duplicate offensive positions (1-to-1 mapping requirement)
    offensive_positions = list(matchups.values())
    if len(offensive_positions) != len(set(offensive_positions)):
        return False, "Duplicate offensive positions found - each offensive player must be guarded by exactly one defender"
    
    # Check all 5 offensive positions are covered
    covered_offensive = set(offensive_positions)
    missing_offensive = set(POSITIONS) - covered_offensive
    if missing_offensive:
        return False, f"Missing offensive positions (not guarded): {', '.join(missing_offensive)}"
    
    return True, None


def get_defender_position_for_man_defense(
    offensive_pos: str,
    game_state: Dict,
    fallback_to_default: bool = True
) -> str:
    """
    Returns the defensive position that should guard the given offensive position
    in man-to-man defense, checking custom matchups first.
    
    Args:
        offensive_pos: Offensive player's position (PG, SG, SF, PF, C)
        game_state: Game state dictionary containing man_defense_matchups
        fallback_to_default: If True, falls back to position-on-position if no custom matchup
    
    Returns:
        Defensive position (PG, SG, SF, PF, C) that should guard the offensive position
    
    Example:
        If matchups = {"PG": "SG", "SG": "PG", ...}:
        - get_defender_position_for_man_defense("SG", game_state) returns "PG"
        - get_defender_position_for_man_defense("PG", game_state) returns "SG"
    """
    if not offensive_pos or offensive_pos not in POSITIONS:
        # Invalid position, fallback to same position
        return offensive_pos if offensive_pos in POSITIONS else "PG"
    
    # Get custom matchups from game state
    matchups = game_state.get("man_defense_matchups", {})
    
    # Find which defensive position guards this offensive position
    # We need to reverse lookup: find defensive_pos where matchups[defensive_pos] == offensive_pos
    for defensive_pos, guarded_offensive_pos in matchups.items():
        if guarded_offensive_pos == offensive_pos:
            return defensive_pos
    
    # No custom matchup found - fallback to default (position-on-position)
    if fallback_to_default:
        return offensive_pos
    
    # Shouldn't happen if matchups are validated, but defensive fallback
    return offensive_pos

