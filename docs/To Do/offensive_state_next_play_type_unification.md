# System Upgrade: Unify `offensive_state` and `next_play_type` Setting

**Status:** 📋 To Do  
**Priority:** Medium  
**Created:** January 2025  
**Related Bug:** Fast Break Miss → DREB → HCO possession flip bug (commit `6a2ea9b5`)

---

## Problem Statement

Currently, `offensive_state` and `next_play_type` are set independently throughout the codebase, leading to:

1. **Inconsistency Bugs:** The fast break DREB bug occurred because `offensive_state` was set to `"HCO"` but `next_play_type` was not set, causing the possession flip check in `game_manager.py` to fail silently.

2. **Implicit Dependencies:** Code relies on both values being set together, but there's no enforcement mechanism.

3. **Silent Failures:** When `possession_flips=True` but `next_play_type` is missing, the possession flip logic in `game_manager.py` (lines 207, 218) fails silently without logging or validation.

4. **Maintenance Burden:** Developers must remember to set both values in every location, with no compile-time or runtime checks.

---

## Current State Analysis

### Where `offensive_state` and `next_play_type` Are Set

**Files with Multiple Locations:**
- `BackEnd/models/shot_manager.py`: ~10 locations
- `BackEnd/engine/phase_resolution.py`: ~15 locations
- `BackEnd/models/turn_manager.py`: ~5 locations
- `BackEnd/models/game_manager.py`: ~3 locations
- `BackEnd/main.py`: ~4 locations

**Common Patterns:**
1. **Made Shots:** Set `offensive_state` to pressure type, set `next_play_type` to `"BASELINE_INBOUND"`
2. **Missed Shots with DREB:** Set `offensive_state` to `"HCO"` or `"FAST_BREAK"`, set `next_play_type` to match
3. **Free Throws:** Set `offensive_state` to `"FREE_THROW"` or pressure type, set `next_play_type` accordingly
4. **Steals:** Set `offensive_state` to `"FAST_BREAK"` or `"HCO"`, set `next_play_type` to match

**Critical Dependency:**
- `game_manager.py` lines 207-224 check `result.get("next_play_type")` to determine when to flip possession
- If `next_play_type` is missing, possession flips silently fail

---

## System Upgrade Solution

### 1. Create Unified State Setter Function

**Location:** `BackEnd/models/game_manager.py` (or new utility file)

**Function Signature:**
```python
def set_next_turn_state(
    self,
    game_state: dict,
    result: dict,
    next_state: str,
    next_play_type: str = None,
    next_defensive_setup: str = None,
    validate: bool = True
) -> None:
    """
    Unified function to set offensive_state and next_play_type together.
    Ensures consistency and prevents bugs from missing next_play_type.
    
    Args:
        game_state: The game's state dictionary
        result: The turn result dictionary
        next_state: The next offensive_state ("HCO", "FAST_BREAK", "FCP", "HCT", "FREE_THROW", etc.)
        next_play_type: The next_play_type (defaults to next_state if not provided)
        next_defensive_setup: Optional defensive setup for BASELINE_INBOUND turns
        validate: If True, validates that next_state and next_play_type are compatible
    
    Raises:
        ValueError: If validation fails and validate=True
    """
    # Set offensive_state
    game_state["offensive_state"] = next_state
    
    # Set next_play_type (default to next_state if not provided)
    if next_play_type is None:
        next_play_type = next_state
    result["next_play_type"] = next_play_type
    
    # Set next_defensive_setup if provided
    if next_defensive_setup:
        result["next_defensive_setup"] = next_defensive_setup
    
    # Validation (if enabled)
    if validate:
        # Validate that next_state and next_play_type are compatible
        valid_combinations = {
            "HCO": ["HCO", "BASELINE_INBOUND", "SIDE_INBOUND"],
            "FAST_BREAK": ["FAST_BREAK", "HCO", "BASELINE_INBOUND"],
            "FCP": ["FCP", "BASELINE_INBOUND"],
            "HCT": ["HCT", "BASELINE_INBOUND"],
            "FREE_THROW": ["FREE_THROW", "BASELINE_INBOUND"],
        }
        
        if next_state in valid_combinations:
            if next_play_type not in valid_combinations[next_state]:
                raise ValueError(
                    f"Invalid combination: offensive_state='{next_state}' but next_play_type='{next_play_type}'. "
                    f"Valid next_play_type values for '{next_state}': {valid_combinations[next_state]}"
                )
    
    # Log for debugging (optional, can be controlled by DEBUG flag)
    import logging
    logging.debug(
        f"🔄 [STATE SETTER] Set offensive_state='{next_state}', next_play_type='{next_play_type}'"
        + (f", next_defensive_setup='{next_defensive_setup}'" if next_defensive_setup else "")
    )
```

### 2. Add Validation in `game_manager.py`

**Location:** `BackEnd/models/game_manager.py` `simulate_macro_turn()`

**Add Before Possession Flip Checks:**
```python
# ✅ VALIDATION: Ensure next_play_type is set when possession_flips=True
if result.get("possession_flips") and not result.get("next_play_type"):
    import logging
    logging.error(
        f"🚨 [POSSESSION FLIP BUG] possession_flips=True but next_play_type is missing! "
        f"result_type={result.get('result_type')}, current_turn={result.get('current_turn')}, "
        f"offensive_state={self.game_state.get('offensive_state')}"
    )
    # Attempt to infer next_play_type from offensive_state as fallback
    inferred_next = self.game_state.get("offensive_state", "HCO")
    result["next_play_type"] = inferred_next
    logging.warning(f"⚠️ [FALLBACK] Inferred next_play_type='{inferred_next}' from offensive_state")
```

---

## Migration Plan

### Phase 1: Create Function and Add Validation (Low Risk)
1. Add `set_next_turn_state()` to `GameManager` class
2. Add validation logging in `game_manager.py` (non-breaking, just logs warnings)
3. Test that existing code still works
4. **Git commit:** "Add unified state setter function and validation"

### Phase 2: Migrate High-Impact Locations (Medium Risk)
Migrate locations that are most likely to cause bugs:

1. **`shot_manager.py` `resolve_fast_break_shot()`** (lines 1005, 1023)
   - Replace: `self.game_state["offensive_state"] = "HCO"` + `result["next_play_type"] = "HCO"`
   - With: `self.game.set_next_turn_state(self.game_state, result, "HCO", "HCO")`

2. **`shot_manager.py` `resolve_shot()` - Made Shots** (lines 374, 379)
   - Replace: Setting `offensive_state` and `next_play_type` separately
   - With: `self.game.set_next_turn_state(self.game_state, result, pressure_type, "BASELINE_INBOUND", next_defensive_setup=pressure_type)`

3. **`phase_resolution.py` `resolve_free_throw_logic()`** (lines 616, 619, 700)
   - Replace: Setting `offensive_state` and `next_play_type` separately
   - With: `game.set_next_turn_state(game_state, result, ...)`

4. **`phase_resolution.py` `resolve_fast_break_logic()`** (lines 397, 743, 746)
   - Replace: Setting `offensive_state` separately
   - With: `game.set_next_turn_state(game_state, result, ...)`

5. **Test each migration individually**
6. **Git commit:** "Migrate high-impact locations to unified state setter"

### Phase 3: Migrate Remaining Locations (Low Risk)
1. Migrate all remaining locations in:
   - `BackEnd/models/turn_manager.py`
   - `BackEnd/main.py`
   - `BackEnd/utils/opening_tip.py`
   - Any other files found in audit

2. **Test thoroughly**
3. **Git commit:** "Complete migration to unified state setter"

### Phase 4: Remove Validation Fallback (Optional)
Once all locations are migrated and validated:
1. Remove the fallback logic from `game_manager.py` validation
2. Make validation raise errors instead of warnings (optional, for stricter enforcement)
3. **Git commit:** "Remove fallback logic, enforce unified state setter"

---

## Benefits

1. **Prevents Bugs:** Single function ensures both values are always set together
2. **Explicit Dependencies:** Makes the relationship between `offensive_state` and `next_play_type` explicit
3. **Validation:** Catches inconsistencies at runtime
4. **Maintainability:** One place to update logic if patterns change
5. **SS&S Compliance:** Single source of truth for state transitions
6. **Documentation:** Function signature and docstring document the pattern

---

## Testing Strategy

### Unit Tests
1. Test `set_next_turn_state()` with various combinations
2. Test validation logic (should raise errors for invalid combinations)
3. Test that `game_state` and `result` are updated correctly

### Integration Tests
1. Test Fast Break → DREB → HCO transition (the original bug)
2. Test Made Shot → BASELINE_INBOUND transition
3. Test Free Throw → BASELINE_INBOUND transition
4. Test Steal → FAST_BREAK transition
5. Verify possession flips work correctly in all scenarios

### Regression Tests
1. Run existing test suite to ensure no regressions
2. Test all 51 turn-to-turn transitions from `TRANSITION_SYSTEM.md`

---

## Rollback Plan

If issues arise:
1. The validation in Phase 1 is non-breaking (just logs warnings)
2. Each phase can be rolled back independently
3. Keep the original code commented out during migration for easy rollback

---

## Future Enhancements (Optional)

1. **Type Hints:** Add type hints to make the function signature clearer
2. **Enum for States:** Create an enum for valid `offensive_state` and `next_play_type` values
3. **Static Analysis:** Add a linter rule to detect direct assignments to `offensive_state` or `next_play_type`
4. **Documentation:** Add examples to docstring showing common usage patterns

---

## Related Files

- `BackEnd/models/shot_manager.py` - Primary location for shot-related state setting
- `BackEnd/engine/phase_resolution.py` - Free throw, fast break, steal logic
- `BackEnd/models/turn_manager.py` - Putback and OREB logic
- `BackEnd/models/game_manager.py` - Possession flip validation and BASELINE_INBOUND creation
- `docs/TRANSITION_SYSTEM.md` - Reference for all 51 turn-to-turn transitions

---

## Notes

- This upgrade maintains backward compatibility during migration
- The validation in Phase 1 will help identify any remaining inconsistencies
- Consider this a "foundation" upgrade that makes future features easier to implement correctly

