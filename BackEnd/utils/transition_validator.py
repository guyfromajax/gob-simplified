"""
Transition Validator

Validates actual game transitions against the transition registry.
This bridges the gap between the documented transitions and the actual code.

SS&S Principle: Centralized validation ensures transitions are correct and
makes debugging transition issues much easier.
"""

from typing import Dict, Optional, Tuple, List
from BackEnd.utils.transition_registry import (
    TurnType,
    Transition,
    get_transition,
    is_valid_transition,
    TRANSITION_REGISTRY
)


# Map backend result types to TurnType enum
RESULT_TYPE_TO_TURN_TYPE: Dict[str, TurnType] = {
    "MAKE": None,  # MAKE doesn't map to a turn type - it's a result
    "MISS": None,  # MISS doesn't map to a turn type - it's a result
    "BLOCK": None,  # BLOCK treated like MISS (result, not a turn type)
    "PUTBACK_MAKE": None,  # PUTBACK_MAKE doesn't map to a turn type
    "PUTBACK_MISS": None,  # PUTBACK_MISS doesn't map to a turn type
    "FREE_THROW": TurnType.FREE_THROW,
    "OREB": TurnType.OREB,
    "DREB": None,  # DREB is embedded in the turn, not a separate turn
    "FAST_BREAK": TurnType.FAST_BREAK,
    "DEFENSIVE_STOP": None,  # DEFENSIVE_STOP is a result, not a turn type
    "FOUL": None,  # FOUL is a result, not a turn type
    "DEAD BALL": None,  # DEAD BALL is a result, not a turn type
    "STEAL": None,  # STEAL is a result, not a turn type
    "BASELINE_INBOUND": TurnType.INBOUND_PASS,
    "SIDE_INBOUND": TurnType.SIDE_INBOUND_PASS,
    "HCO": TurnType.HCO,
    "FCP": TurnType.FCP,
    "HCT": TurnType.HCT,
}


# Map offensive_state values to TurnType enum
OFFENSIVE_STATE_TO_TURN_TYPE: Dict[str, TurnType] = {
    "HCO": TurnType.HCO,
    "FREE_THROW": TurnType.FREE_THROW,
    "FAST_BREAK": TurnType.FAST_BREAK,
    "FCP": TurnType.FCP,
    "HCT": TurnType.HCT,
}


def get_turn_type_from_result(result: Dict) -> Optional[TurnType]:
    """
    Determine the TurnType from a turn result.
    
    This is complex because:
    - Some results (MAKE, MISS) don't represent turn types
    - Some results create separate turns (BASELINE_INBOUND, SIDE_INBOUND)
    - Some results set offensive_state for the next turn
    """
    result_type = result.get("result_type")
    
    # Direct mappings
    if result_type in RESULT_TYPE_TO_TURN_TYPE:
        turn_type = RESULT_TYPE_TO_TURN_TYPE[result_type]
        if turn_type:
            return turn_type
    
    # Check for inbound passes (created as separate turns)
    if result_type == "MAKE" and result.get("next_play_type") == "BASELINE_INBOUND":
        return TurnType.INBOUND_PASS
    
    # For results that set offensive_state, we need to check the next turn
    # This function is called after the turn completes, so we check game_state
    return None


def get_turn_type_from_offensive_state(offensive_state: str) -> Optional[TurnType]:
    """Map offensive_state to TurnType."""
    return OFFENSIVE_STATE_TO_TURN_TYPE.get(offensive_state)


def validate_transition(
    from_result: Dict,
    to_offensive_state: str,
    possession_changed: bool,
    game_state: Dict
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a transition from one turn to another is correct.
    
    Args:
        from_result: The result dict from the previous turn
        to_offensive_state: The offensive_state for the next turn
        possession_changed: Whether possession flipped
        game_state: Current game state
    
    Returns:
        (is_valid, error_message)
    """
    # Determine from_turn type
    from_turn_type = None
    
    # Check if this was an inbound pass turn
    if from_result.get("result_type") in ["BASELINE_INBOUND", "SIDE_INBOUND"]:
        if from_result.get("result_type") == "BASELINE_INBOUND":
            from_turn_type = TurnType.INBOUND_PASS
        else:
            from_turn_type = TurnType.SIDE_INBOUND_PASS
    # Check if this was an OREB turn
    elif from_result.get("result_type") in ["PUTBACK_MAKE", "PUTBACK_MISS", "KICKOUT"]:
        from_turn_type = TurnType.OREB
    # Check offensive_state that was used for this turn
    else:
        previous_state = game_state.get("_previous_offensive_state")
        if previous_state:
            from_turn_type = get_turn_type_from_offensive_state(previous_state)
    
    # Special case: Opening tip
    if game_state.get("_is_opening_tip"):
        from_turn_type = TurnType.OPENING_TIP
    
    # Determine to_turn type
    to_turn_type = get_turn_type_from_offensive_state(to_offensive_state)
    
    if not from_turn_type or not to_turn_type:
        # Can't validate if we can't determine turn types
        return True, None  # Don't fail validation if we can't determine types
    
    # Check if transition is valid
    is_valid = is_valid_transition(from_turn_type, to_turn_type, possession_changed)
    
    if not is_valid:
        transition = get_transition(from_turn_type, to_turn_type, possession_changed)
        error_msg = (
            f"Invalid transition: {from_turn_type.value} -> {to_turn_type.value} "
            f"(PC={possession_changed}). "
            f"From result: {from_result.get('result_type')}, "
            f"Instigating events: {transition.instigating_events if transition else 'Unknown'}"
        )
        return False, error_msg
    
    return True, None


def get_expected_transitions_for_result(result: Dict, game_state: Dict) -> List[Transition]:
    """
    Get all valid transitions that could occur from a given result.
    
    This helps identify what transitions are possible from a turn result.
    """
    from_turn_type = None
    
    # Determine from_turn type
    if result.get("result_type") in ["BASELINE_INBOUND", "SIDE_INBOUND"]:
        if result.get("result_type") == "BASELINE_INBOUND":
            from_turn_type = TurnType.INBOUND_PASS
        else:
            from_turn_type = TurnType.SIDE_INBOUND_PASS
    elif result.get("result_type") in ["PUTBACK_MAKE", "PUTBACK_MISS", "KICKOUT"]:
        from_turn_type = TurnType.OREB
    else:
        previous_state = game_state.get("_previous_offensive_state")
        if previous_state:
            from_turn_type = get_turn_type_from_offensive_state(previous_state)
    
    if not from_turn_type:
        return []
    
    return get_transitions_from(from_turn_type)

