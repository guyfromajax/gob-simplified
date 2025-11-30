"""
Transition Event Detector

Detects which instigating event occurred based on game result and state.
Maps actual game outcomes to the instigating events defined in transitions.md.

SS&S Principle: Single source of truth for event detection ensures consistency
between production code, tests, and documentation.

This is an optional utility - game works without it, but it provides valuable
observability and validation capabilities.
"""

from typing import Dict, Optional, List, Tuple
from BackEnd.utils.transition_registry import TurnType, get_turn_type_from_offensive_state


def detect_instigating_event(
    result: Dict,
    game_state: Dict,
    previous_offensive_state: Optional[str] = None
) -> Optional[str]:
    """
    Detect which instigating event occurred based on result and game state.
    
    Returns a string matching the instigating events in transitions.md, or None
    if the event cannot be determined.
    
    Args:
        result: The turn result dictionary
        game_state: Current game state
        previous_offensive_state: The offensive_state before this turn (optional)
    
    Returns:
        Instigating event string (e.g., "Made Shot, No Foul", "Press/Trap Break, HCO next step")
        or None if cannot be determined
    """
    result_type = result.get("result_type")
    previous_state = previous_offensive_state or game_state.get("_previous_offensive_state")
    
    # Determine if we're in a pressure situation (FCP/HCT)
    is_pressure = previous_state in ["FCP", "HCT"]
    pressure_type = "Press/Trap Break" if is_pressure else None
    
    # ============================================
    # SHOT-RELATED EVENTS
    # ============================================
    if result_type in ["MAKE", "MISS"]:
        made = result_type == "MAKE"
        has_foul = result.get("free_throws_remaining", 0) > 0 or result.get("has_and_one", False)
        is_pressure_shot = result.get("fcp_shot") or result.get("hct_shot")
        
        if is_pressure_shot:
            # FCP/HCT shot events
            if made and not has_foul:
                return f"{pressure_type}, Made Shot Attempt, No Foul"
            elif made and has_foul:
                return f"{pressure_type}, Made Shot Attempt, Shooting Foul"
            elif not made:
                # Check for rebound
                rebound_type = result.get("rebound_type") or game_state.get("last_rebound")
                if rebound_type == "OREB":
                    return f"{pressure_type}, Missed Shot Attempt, OREB"
                else:
                    # DREB - check next step
                    next_state = game_state.get("offensive_state", "HCO")
                    if next_state == "FAST_BREAK":
                        return f"{pressure_type}, Missed Shot Attempt, DREB, Fast Break next step"
                    else:
                        return f"{pressure_type}, Missed Shot Attempt, DREB, HCO next step"
        else:
            # Regular shot events (HCO, Fast Break, OREB)
            if made and not has_foul:
                return "Made Shot, No Foul"
            elif made and has_foul:
                return "Made Shot, Foul"
            elif not made and has_foul:
                return "Missed Shot, Foul"
            elif not made:
                # Check for rebound
                rebound_type = result.get("rebound_type") or game_state.get("last_rebound")
                if rebound_type == "OREB":
                    return "Missed Shot, OREB"
                else:
                    # DREB - check next step
                    next_state = game_state.get("offensive_state", "HCO")
                    if next_state == "FAST_BREAK":
                        return "Missed Shot, DREB, Fast Break next step"
                    else:
                        return "Missed Shot, DREB, HCO next step"
    
    # ============================================
    # PUTBACK EVENTS (OREB turns)
    # ============================================
    if result_type in ["PUTBACK_MAKE", "PUTBACK_MISS", "KICKOUT"]:
        if result_type == "PUTBACK_MAKE":
            has_foul = result.get("free_throws_remaining", 0) > 0
            return "Made Shot, No Foul" if not has_foul else "Made Shot, Foul"
        elif result_type == "PUTBACK_MISS":
            has_foul = result.get("free_throws_remaining", 0) > 0
            if has_foul:
                return "Missed Shot, Foul"
            else:
                rebound_type = result.get("rebound_type") or game_state.get("last_rebound")
                if rebound_type == "OREB":
                    return "Missed Shot, OREB"
                else:
                    next_state = game_state.get("offensive_state", "HCO")
                    if next_state == "FAST_BREAK":
                        return "Missed Shot, DREB, Fast Break next step"
                    else:
                        return "Missed Shot, DREB, HCO next step"
        elif result_type == "KICKOUT":
            return "Kickout Pass"
    
    # ============================================
    # FREE THROW EVENTS
    # ============================================
    if result_type == "FREE_THROW" or previous_state == "FREE_THROW":
        free_throws_remaining = game_state.get("free_throws_remaining", 0)
        is_final = free_throws_remaining <= 0
        
        if is_final:
            # Final free throw
            made = result.get("points", 0) > 0  # Simplified - may need better detection
            if made:
                return "Final FT Made"
            else:
                # Check for rebound or foul
                rebound_type = game_state.get("last_rebound")
                if rebound_type == "OREB":
                    return "Final FT Missed, OREB"
                else:
                    # Check for foul on rebound
                    has_foul = result.get("free_throws_remaining", 0) > 0  # Foul after miss
                    if has_foul:
                        foul_team = result.get("foul_team")
                        in_bonus = game_state.get("team_fouls", {}).get(foul_team, 0) >= 5
                        if in_bonus:
                            return "Final Free Throw Missed, Defensive Foul, Bonus Situation"
                        else:
                            return "Final Free Throw Missed, Defensive Foul, No Bonus Situation"
                    else:
                        next_state = game_state.get("offensive_state", "HCO")
                        if next_state == "FAST_BREAK":
                            return "Final FT Missed, DREB, Fast Break next step"
                        else:
                            return "Final FT Missed, DREB, HCO next step"
    
    # ============================================
    # TURNOVER EVENTS
    # ============================================
    if result_type == "STEAL":
        next_state = game_state.get("offensive_state", "HCO")
        if is_pressure:
            if next_state == "FAST_BREAK":
                return "Steal, Fast Break as next step"
            else:
                return "Steal, HCO as next step"
        else:
            if next_state == "FAST_BREAK":
                return "Steal, Fast Break next step"
            else:
                return "Steal, HCO next step"
    
    if result_type == "DEAD BALL":
        if is_pressure:
            return "Dead Ball Turnover"
        else:
            return "Dead Ball Turnover"
    
    # ============================================
    # FOUL EVENTS
    # ============================================
    if result_type == "FOUL":
        foul_team = result.get("foul_team")
        is_offensive = foul_team == game_state.get("offense_team_id")  # Simplified
        is_shooting = result.get("free_throws_remaining", 0) > 0
        in_bonus = False  # Would need to check team fouls
        
        if is_pressure:
            if is_offensive:
                return "Offensive Foul"
            elif is_shooting:
                return f"{pressure_type}, Made Shot Attempt, Shooting Foul"
            else:
                if in_bonus:
                    return "Non-shooting Defensive Foul, Bonus Situation"
                else:
                    return "Non-Shooting Defensive Foul"
        else:
            if is_offensive:
                # Check if on a missed shot
                if game_state.get("last_rebound") == "OREB":
                    return "Missed Shot, Offensive Foul"
                else:
                    return "Offensive Foul"
            elif is_shooting:
                return "Made Shot, Foul"  # or "Missed Shot, Foul" - need to check
            else:
                if in_bonus:
                    return "Non-Shooting Defensive Foul, Bonus Situation"
                else:
                    # Check if on a missed shot
                    if game_state.get("last_rebound") == "OREB":
                        return "Missed Shot, Non-Shooting Defensive Foul"
                    else:
                        return "Non-Shooting Defensive Foul, No Bonus"
    
    # ============================================
    # PRESSURE BREAK EVENTS (FCP/HCT)
    # ============================================
    if is_pressure and result_type == "HCO":
        next_state = game_state.get("offensive_state", "HCO")
        if next_state == "HCO":
            return f"{pressure_type}, HCO next step"
        elif next_state == "FAST_BREAK":
            return f"{pressure_type}, Fast Break next step"
    
    # ============================================
    # FAST BREAK EVENTS
    # ============================================
    if result_type == "DEFENSIVE_STOP":
        return "Defensive Stop"
    
    # ============================================
    # INBOUND PASS EVENTS
    # ============================================
    if result_type in ["BASELINE_INBOUND", "SIDE_INBOUND"]:
        return "Inbound Pass Complete" if result_type == "BASELINE_INBOUND" else "Side Inbound Pass Complete"
    
    # ============================================
    # OPENING TIP
    # ============================================
    if game_state.get("_is_opening_tip") or previous_state is None:
        return "Opening Tip"
    
    return None  # Cannot determine event


def get_all_possible_events_for_transition(
    from_turn_type: TurnType,
    to_turn_type: TurnType,
    possession_change: bool
) -> List[str]:
    """
    Get all possible instigating events for a given transition.
    
    Useful for testing - verifies that detected event matches one of the
    expected events for the transition.
    """
    from BackEnd.utils.transition_registry import get_transition
    
    transition = get_transition(from_turn_type, to_turn_type, possession_change)
    if transition:
        return transition.instigating_events
    return []


def validate_event_matches_transition(
    detected_event: Optional[str],
    from_turn_type: TurnType,
    to_turn_type: TurnType,
    possession_change: bool
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a detected event matches one of the expected events for a transition.
    
    Returns:
        (is_valid, error_message)
    """
    if detected_event is None:
        return True, None  # Can't validate if event couldn't be detected
    
    expected_events = get_all_possible_events_for_transition(
        from_turn_type, to_turn_type, possession_change
    )
    
    if not expected_events:
        return True, None  # No expected events to validate against
    
    if detected_event in expected_events:
        return True, None
    
    error_msg = (
        f"Detected event '{detected_event}' does not match expected events "
        f"for transition {from_turn_type.value} -> {to_turn_type.value} (PC={possession_change}). "
        f"Expected: {expected_events}"
    )
    return False, error_msg

