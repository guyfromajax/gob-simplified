# Coordinate System Refactor Plan

## Problem Statement

The current coordinate system uses manual flipping (`get_away_player_coords`) scattered throughout the codebase, leading to:
- Double-flipping bugs
- Missing flips
- Inconsistent contracts between functions
- Difficult debugging

## Goal

Create a centralized, consistent coordinate handling system that:
1. Has a single, clear contract that never changes
2. Makes coordinate orientation explicit
3. Reduces flipping bugs
4. Is easy to understand and maintain

## Proposed Solution: Coordinate Context Manager

### Phase 1: Create Coordinate Helper Functions (Low Risk)

**File**: `BackEnd/utils/coordinate_utils.py` (new file)

```python
"""
Centralized coordinate system utilities.

All defensive positioning functions work in HOME orientation.
This module provides helpers to normalize coordinates and handle display flipping.
"""

from BackEnd.utils.shared import get_away_player_coords

def normalize_to_home(coords: dict, is_away_orientation: bool) -> dict:
    """
    Normalize coordinates to HOME orientation.
    
    Args:
        coords: Coordinates dict with 'x' and 'y'
        is_away_orientation: True if coords are in away orientation
        
    Returns:
        Coordinates in HOME orientation
    """
    if is_away_orientation:
        return get_away_player_coords(coords)
    return coords

def normalize_to_display(coords: dict, is_away_offense: bool) -> dict:
    """
    Normalize coordinates for display (flip if away team on offense).
    
    Args:
        coords: Coordinates in HOME orientation
        is_away_offense: True if away team has the ball
        
    Returns:
        Coordinates in display orientation (away if away offense, home otherwise)
    """
    if is_away_offense:
        return get_away_player_coords(coords)
    return coords

def ensure_home_orientation(coords: dict, current_orientation: str) -> dict:
    """
    Ensure coordinates are in HOME orientation.
    
    Args:
        coords: Coordinates dict
        current_orientation: 'home' or 'away'
        
    Returns:
        Coordinates guaranteed to be in HOME orientation
    """
    if current_orientation == 'away':
        return get_away_player_coords(coords)
    return coords
```

**Benefits**:
- Makes orientation explicit
- Single source of truth for flipping logic
- Easy to add logging/debugging

### Phase 2: Update assign_bh_defender_coords Contract (Medium Risk)

**File**: `BackEnd/utils/shared_defense.py`

**Changes**:
1. Add explicit type hints and validation
2. Use new helper functions
3. Add clear docstring with examples

```python
def assign_bh_defender_coords(
    ball_coords: dict,  # MUST be in HOME orientation
    aggression_level: str,
    is_away_offense: bool,
    bh_spot: str = "key"
) -> dict:  # ALWAYS returns HOME orientation
    """
    Calculate ball handler defender position.
    
    CONTRACT (NEVER CHANGE):
    - Input: HOME orientation coordinates
    - Output: HOME orientation coordinates
    - Callers must handle display flipping
    
    Examples:
        # Home team has ball
        bh_coords = {"x": 50, "y": 25}  # HOME orientation
        def_coords = assign_bh_defender_coords(bh_coords, "normal", False, "key")
        # Returns: {"x": 53, "y": 25}  # HOME orientation (defender to RIGHT)
        
        # Away team has ball (caller must normalize first)
        bh_coords_away = {"x": 50, "y": 25}  # AWAY orientation
        bh_coords_home = normalize_to_home(bh_coords_away, is_away_orientation=True)
        def_coords = assign_bh_defender_coords(bh_coords_home, "normal", True, "key")
        # Returns: {"x": 47, "y": 25}  # HOME orientation (defender to LEFT)
        # Caller flips for display: normalize_to_display(def_coords, is_away_offense=True)
    """
    # Validate input is in home orientation (optional, for debugging)
    # Could add assertion: assert ball_coords["x"] <= 50 or not is_away_offense
    
    # ... existing logic ...
```

### Phase 3: Update All Callers (Medium Risk)

**Files to update**:
1. `BackEnd/models/animator.py` - `_position_standard_defenders`
2. `BackEnd/models/animator.py` - `_position_zone_defenders`
3. `BackEnd/utils/shared_defense.py` - `assign_zone_defender_coords`
4. `BackEnd/utils/shared_defense.py` - `assign_all_zone_defenders`
5. `BackEnd/models/turn_manager.py` - Any direct calls

**Pattern for each caller**:
```python
# BEFORE (inconsistent):
if is_away_offense:
    coords = get_away_player_coords(coords)  # Sometimes here
def_coords = assign_bh_defender_coords(coords, ...)
if is_away_offense:
    def_coords = get_away_player_coords(def_coords)  # Sometimes here

# AFTER (consistent):
from BackEnd.utils.coordinate_utils import normalize_to_home, normalize_to_display

# Normalize input to home
bh_coords_home = normalize_to_home(bh_coords, is_away_orientation=is_away_offense)

# Calculate (always returns home)
def_coords_home = assign_bh_defender_coords(bh_coords_home, aggression, is_away_offense, spot)

# Normalize output for display
def_coords_display = normalize_to_display(def_coords_home, is_away_offense=is_away_offense)
```

### Phase 4: Add Validation & Logging (Low Risk)

**File**: `BackEnd/utils/coordinate_utils.py`

Add optional validation mode:
```python
DEBUG_COORDINATES = False  # Set to True for debugging

def normalize_to_home(coords: dict, is_away_orientation: bool) -> dict:
    if DEBUG_COORDINATES:
        logging.debug(f"🔄 normalize_to_home: input={coords}, is_away={is_away_orientation}")
    result = get_away_player_coords(coords) if is_away_orientation else coords
    if DEBUG_COORDINATES:
        logging.debug(f"   → output={result}")
    return result
```

## Implementation Steps

### Step 1: Create coordinate_utils.py (30 min)
- Create new file with helper functions
- Add unit tests
- No breaking changes yet

### Step 2: Update assign_bh_defender_coords (15 min)
- Add type hints
- Update docstring with contract
- Use helper functions internally
- Test thoroughly

### Step 3: Update one caller at a time (1-2 hours)
- Start with `_position_standard_defenders` (man defense)
- Test thoroughly
- Then `_position_zone_defenders` (zone defense)
- Test thoroughly
- Then other callers

### Step 4: Add validation (30 min)
- Add debug mode
- Add assertions (optional)
- Test with debug mode on

### Step 5: Cleanup (30 min)
- Remove old manual flipping code
- Update comments
- Remove debug logs if desired

## Testing Strategy

1. **Unit Tests**: Test `normalize_to_home` and `normalize_to_display` with known inputs
2. **Integration Tests**: Test `assign_bh_defender_coords` with both home and away offense
3. **Visual Tests**: Run game and verify defender positions are correct in all scenarios:
   - Home offense, man defense
   - Away offense, man defense
   - Home offense, zone defense
   - Away offense, zone defense
   - Various court positions (key, wing, corner)

## Risk Assessment

- **Low Risk**: Phase 1 (new file, no changes to existing code)
- **Medium Risk**: Phase 2-3 (changes to existing functions, but contract is clear)
- **Low Risk**: Phase 4 (optional validation)

## Rollback Plan

If issues arise:
1. Keep old code commented out
2. Add feature flag to switch between old/new system
3. Can revert one caller at a time

## Success Criteria

- ✅ Single, clear contract for `assign_bh_defender_coords`
- ✅ All coordinate flipping happens through helper functions
- ✅ No double-flipping bugs
- ✅ No missing flip bugs
- ✅ Easy to debug (can enable coordinate logging)
- ✅ All tests pass
- ✅ Visual verification: defenders position correctly in all scenarios

## Future Enhancements (Out of Scope)

- Consider a `CourtPosition` class that encapsulates orientation
- Consider making orientation a type (using TypedDict or dataclass)
- Consider compile-time checks (using mypy or similar)

