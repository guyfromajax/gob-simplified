# Transition Standardization Proposal

## Current State

**Current Approach**: Decentralized - Each handler directly sets `game_state["offensive_state"]`:
- `shot_manager.py`: Sets state for shot outcomes
- `phase_resolution.py`: Sets state for free throws, turnovers, fast breaks, FCP/HCT
- `turn_manager.py`: Sets state for OREB outcomes
- `game_manager.py`: Sets state for inbound passes

**Total locations**: 26+ places where `offensive_state` is set directly

## Standardization Analysis

### Option 1: Full Standardization (Single Transition Handler)
**Pros**:
- Single source of truth for all transitions
- Easy to validate all transitions in one place
- Consistent logging/error handling

**Cons**:
- **Over-engineering**: Different handlers need different data (rebound data, foul data, pressure type, etc.)
- **Complexity**: Would need to pass all possible data to a single function
- **Tight coupling**: All handlers would depend on transition handler
- **Less flexible**: Hard to handle edge cases that need custom logic

### Option 2: Lightweight Validation Layer (Recommended)
**Pros**:
- **SS&S aligned**: Keeps current working system, adds validation
- **Non-intrusive**: Doesn't require refactoring existing code
- **Flexible**: Handlers keep their specific logic
- **Validates**: Catches invalid transitions without blocking functionality
- **Easy to implement**: Just add validation calls

**Cons**:
- Transitions still set in multiple places (but that's actually fine - each handler knows its context)

### Option 3: No Standardization
**Pros**:
- Current system works
- No changes needed

**Cons**:
- No validation of transitions
- Hard to catch bugs
- No centralized logging

## Recommendation: Option 2 - Lightweight Validation Layer

### Implementation

Add validation **after** handlers set `offensive_state`, without changing how they set it:

```python
# In game_manager.py, after simulate_macro_turn completes:
from BackEnd.utils.transition_validator import validate_transition

# After result is created, validate the transition
is_valid, error = validate_transition(
    from_result=previous_result,  # Track previous turn's result
    to_offensive_state=game_state["offensive_state"],
    possession_changed=result.get("possession_flips", False),
    game_state=game_state
)

if not is_valid:
    logging.warning(f"⚠️ Invalid transition detected: {error}")
    # Don't block - just log for debugging
```

### Why This Works

1. **Different handlers need different data**:
   - Shot handler needs: shooter, defender, make/miss, foul info
   - Free throw handler needs: makes_shot, free_throws_remaining, bonus status
   - Turnover handler needs: turnover_type, stealer, fast_break_chance
   - OREB handler needs: rebounder, putback result, kickout option

2. **Each handler is the expert** for its domain - they know best what the next state should be

3. **Validation layer** ensures correctness without dictating implementation

## Data Structure Standardization

**Current result structure** is already fairly standardized:
```python
result = {
    "result_type": "MAKE" | "MISS" | "FOUL" | "STEAL" | etc.,
    "possession_flips": bool,
    "next_play_type": "BASELINE_INBOUND" | "HCO" | etc.,  # Informational
    "next_defensive_setup": "FCP" | "HCT" | None,  # For pressure
    # ... handler-specific fields
}
```

**Recommendation**: Keep this structure. It's already standardized enough. Different handlers add their own fields as needed (e.g., `shooter`, `rebounder`, `stealer`), which is fine.

## Next Steps

1. **Add validation logging** (non-blocking) to `game_manager.simulate_macro_turn()`
2. **Track previous turn result** for validation
3. **Create integration tests** for all 51 transitions
4. **Add code comments** referencing transition registry

This gives us:
- ✅ Validation without over-engineering
- ✅ Flexibility for handler-specific logic
- ✅ SS&S: Simple, Stable, Scalable
- ✅ Easy to debug transition issues

