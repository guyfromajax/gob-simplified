# Defender Coordinate System Refactoring Plan

## Problem Statement

The current defender coordinate system has persistent bugs and complexity issues:

1. **Persistent Bug**: When away team has the ball, BH defender gets wrong `x_direction` (1 instead of -1), causing defender to animate on wrong side of ball handler
2. **Multiple Functions**: Separate functions for BH defenders, non-BH defenders, zone defenders
3. **Complex Coordinate Flipping**: Functions expect HOME orientation, but callers pass different orientations, requiring manual unflipping at each call site
4. **Inconsistent Logic**: Different `x_direction` calculations scattered across codebase
5. **Multiple Call Sites**: Called from `animator.py` in 5+ places with different coordinate assumptions
6. **Hard to Debug**: Coordinate transformations happen at multiple layers, making bugs hard to trace

## Root Cause Analysis

### Current Architecture Issues

1. **Dual Function System**:
   - `assign_bh_defender_coords()` - Ball handler defenders
   - `assign_non_bh_defender_coords()` - Off-ball defenders
   - `assign_zone_defender_coords()` - Zone defenders (calls BH function internally)
   - `assign_all_zone_defenders()` - Zone coordinator

2. **Coordinate Orientation Confusion**:
   - Functions expect HOME orientation internally
   - Callers must manually unflip coordinates before calling
   - Functions return HOME orientation
   - Callers must manually flip back for display
   - This creates opportunities for bugs at every transformation point

3. **x_direction Calculation Issues**:
   - In `assign_bh_defender_coords()`: `x_direction = -1 if is_away_offense else 1`
   - Logic is correct, but `is_away_offense` may be passed incorrectly, or coordinates are in wrong orientation
   - In `assign_non_bh_defender_coords()`: `x_direction = 1 if bx > ox else -1` (different logic!)
   - No single source of truth for direction calculation

4. **Call Site Complexity**:
   - `animator.py` line 630: Man defense, BH defender setup
   - `animator.py` line 654: Man defense, BH defender movement
   - `animator.py` line 820: Zone defense, BH in zone
   - `animator.py` line 1152: Zone defense, overlap assignment
   - `shared_defense.py` line 845: Zone defense, deep location mapping
   - Each call site has different coordinate states and flipping logic

## Solution: Unified Defender Coordinate System

### Core Principles

**For Ball Handler Defenders**: Defender is always positioned closer to the basket than the ball handler.

**For Non-Ball Handler Defenders**: Defender is positioned relative to their assignment, maintaining proper spacing and positioning, but may not always be closer to the basket than the offensive player they're guarding.

Calculate defender position directly from:
1. Offensive player coordinates
2. Target basket coordinates (for BH defenders)
3. Ball handler coordinates (for non-BH defenders - relative positioning)
4. Aggression level (spacing)
5. Court spot (for specialized positioning)

### Design Goals

1. **Single Entry Point**: One function handles all defender types (BH, non-BH, zone)
2. **Unified Coordinate Handling**: Always work in HOME orientation internally, flip only at boundaries
3. **Direct Calculation**: Calculate `x_direction` from coordinates and basket position, not from `is_away_offense` flag
4. **Clear Contract**: Explicit input/output orientation in function signature
5. **BH Defender Rule**: "Closer to basket" rule enforced mathematically for BH defenders
6. **Non-BH Defender Rule**: Relative positioning based on assignment and ball handler location

## Proposed Architecture

### New Unified Function

```python
def calculate_defender_coords(
    offensive_coords: dict,
    target_basket: dict,
    aggression_level: str,
    spot: str = "key",
    ball_handler_coords: dict = None,
    is_ball_handler: bool = False
) -> dict:
    """
    Calculate defender coordinates for any defensive scenario.
    
    CORE RULES:
    - For BH defenders: Defender is always positioned closer to the basket than the ball handler.
    - For non-BH defenders: Defender is positioned relative to their assignment and ball handler,
      maintaining proper spacing, but may not always be closer to basket.
    
    Args:
        offensive_coords: Offensive player coordinates in HOME orientation
        target_basket: Basket coordinates being defended (HOME_RIM_COORDS or AWAY_RIM_COORDS)
        aggression_level: Defense aggression ("aggressive", "normal", "passive")
        spot: Court spot string ("key", "lower wing", etc.)
        ball_handler_coords: Optional ball handler coordinates (for non-BH defenders)
        is_ball_handler: Whether this is the ball handler's defender
    
    Returns:
        Defender coordinates in HOME orientation
    """
    ox = offensive_coords["x"]
    oy = offensive_coords["y"]
    
    if is_ball_handler:
        # BH DEFENDER: Always closer to basket than ball handler
        basket_x = target_basket["x"]
        basket_y = target_basket["y"]
        
        # Calculate direction vector from offensive player to basket
        dx = basket_x - ox  # Positive = toward basket (right), Negative = away from basket (left)
        dy = basket_y - oy  # Positive = toward basket (down), Negative = away from basket (up)
        
        # Normalize direction (unit vector)
        distance_to_basket = ((dx ** 2) + (dy ** 2)) ** 0.5
        if distance_to_basket == 0:
            # Offensive player is at basket (edge case)
            unit_x = 0
            unit_y = 0
        else:
            unit_x = dx / distance_to_basket
            unit_y = dy / distance_to_basket
        
        # Get spacing based on aggression
        spacing = get_spacing(aggression_level, is_ball_handler=True)
        
        # Calculate defender position: move toward basket by spacing amount
        def_x = ox + (unit_x * spacing)
        def_y = oy + (unit_y * spacing)
        
        # Apply spot-specific adjustments (for specialized positioning)
        def_x, def_y = apply_spot_adjustments(def_x, def_y, spot, unit_x, unit_y, spacing, is_ball_handler=True)
        
        # EDGE CASE: Corner locations for BH defenders
        if spot in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline", 
                    "lower midcorner", "upper midcorner"]:
            # X position: Defender's x should equal ball handler's x
            def_x = ox  # Defender x equals ball handler x
            
            # Y position: Follow corner y-position rules
            # Upper corner: defender's y must be LOWER (defender below ball handler)
            if "upper" in spot:
                def_y = oy - random.randint(2, 4)  # Defender below (lower y value)
            # Lower corner: defender's y must be HIGHER (defender above ball handler)
            elif "lower" in spot:
                def_y = oy + random.randint(2, 4)  # Defender above (higher y value)
        
        # Verify defender is closer to basket (BH defender requirement)
        verify_defender_closer_to_basket(def_x, def_y, ox, oy, basket_x, basket_y)
    else:
        # NON-BH DEFENDER: Position relative to assignment and ball handler
        # Use existing logic from assign_non_bh_defender_coords() but with unified structure
        bx = ball_handler_coords["x"] if ball_handler_coords else ox
        by = ball_handler_coords["y"] if ball_handler_coords else oy
        
        # EDGE CASE 1: Post defenders (low/medium post)
        # Offensive player is very close to basket, defender must stay tight (closer to player)
        # rather than being in standard help defense position
        if spot in ["lower lowPost", "upper lowPost", "lower midPost", "upper midPost"]:
            # Tight defense: defender stays very close to offensive player
            # X position: defender on basket side of offensive player
            # Determine basket direction from target_basket
            basket_x = target_basket["x"]
            # If basket is to the right (x > ox), defender should be to the right (ox + 2)
            # If basket is to the left (x < ox), defender should be to the left (ox - 2)
            def_x = ox + 2 if basket_x > ox else ox - 2
            # Y position: slight adjustment based on ball handler
            def_y = oy + random.choice([0.3, 0.4, 0.5]) * (abs(by - oy) * (-1 if oy > 25 else 1))
        
        # EDGE CASE 2: Corner locations for non-BH defenders
        elif spot in ["lower corner", "upper corner", "lower midBaseline", "upper midBaseline",
                      "lower midcorner", "upper midcorner"]:
            # Upper corner: defender's y must be LOWER (defender below offensive player)
            if "upper" in spot:
                def_y = oy - random.randint(2, 4)  # Defender below (lower y value)
            # Lower corner: defender's y must be HIGHER (defender above offensive player)
            elif "lower" in spot:
                def_y = oy + random.randint(2, 4)  # Defender above (higher y value)
            
            # X position: relative to ball handler and offensive player
            x_direction = 1 if bx > ox else -1
            def_x = ox + 0.1 * (abs(bx - ox) * x_direction)
        
        # Standard non-BH defender positioning
        else:
            # Calculate relative positioning (may not be closer to basket)
            # This maintains proper spacing and positioning relative to assignment
            def_x, def_y = calculate_non_bh_positioning(
                ox, oy, bx, by, aggression_level, spot, target_basket
            )
    
    return {"x": int(def_x), "y": int(def_y)}
```

### Coordinate Orientation Wrapper

```python
def get_defender_coords(
    offensive_coords: dict,
    is_away_offense: bool,
    aggression_level: str,
    spot: str = "key",
    ball_handler_coords: dict = None,
    is_ball_handler: bool = False
) -> dict:
    """
    Public API for getting defender coordinates.
    Handles coordinate orientation transformation automatically.
    
    Args:
        offensive_coords: Offensive player coordinates (in current orientation)
        is_away_offense: Whether away team is on offense
        aggression_level: Defense aggression setting
        spot: Court spot string
        ball_handler_coords: Optional ball handler coordinates
        is_ball_handler: Whether this is ball handler's defender
    
    Returns:
        Defender coordinates (in same orientation as input)
    """
    # Determine target basket
    if is_away_offense:
        # Away team attacking home basket
        target_basket = HOME_RIM_COORDS
    else:
        # Home team attacking away basket
        target_basket = AWAY_RIM_COORDS
    
    # Convert offensive coords to HOME orientation for calculation
    if is_away_offense:
        offensive_coords_home = get_away_player_coords(offensive_coords)
    else:
        offensive_coords_home = offensive_coords
    
    # Convert ball handler coords if provided
    if ball_handler_coords:
        if is_away_offense:
            ball_handler_coords_home = get_away_player_coords(ball_handler_coords)
        else:
            ball_handler_coords_home = ball_handler_coords
    else:
        ball_handler_coords_home = None
    
    # Calculate in HOME orientation
    defender_coords_home = calculate_defender_coords(
        offensive_coords_home,
        target_basket,
        aggression_level,
        spot,
        ball_handler_coords_home,
        is_ball_handler
    )
    
    # Convert back to original orientation
    if is_away_offense:
        return get_away_player_coords(defender_coords_home)
    else:
        return defender_coords_home
```

### Zone Defense Integration

Zone defenders use the same unified function, but with zone-specific logic for determining which offensive player to guard:

```python
def get_zone_defender_coords(
    defender_pos: str,
    zone_boundaries: dict,
    offensive_players: list,
    ball_handler_coords: dict,
    ball_spot: str,
    aggression_level: str,
    is_away_offense: bool
) -> dict:
    """
    Get defender coordinates for zone defense.
    Uses unified calculate_defender_coords internally.
    """
    # Priority 1: Ball handler in zone
    if ball_handler_in_zone(defender_pos, zone_boundaries, ball_handler_coords):
        return get_defender_coords(
            ball_handler_coords,
            is_away_offense,
            aggression_level,
            ball_spot,
            None,
            is_ball_handler=True
        )
    
    # Priority 2: Other offensive players in zone
    # ... zone-specific logic ...
    
    # Fallback: Zone center
    return get_zone_center(defender_pos, zone_boundaries)
```

## Edge Cases and Special Positioning Rules

### Post Defenders (Low/Medium Post)
**Scenario**: Non-BH defender guarding offensive player in low or medium post

**Rule**: Offensive player is very close to basket, so defender must stay **tight** (closer to their player) rather than being in standard help defense position.

**Implementation**:
- X position: Defender positioned on basket side of offensive player
  - Calculated from basket position: `def_x = ox + 2 if basket_x > ox else ox - 2`
  - This automatically handles both home and away offense
- Y position: Slight adjustment based on ball handler location
- **Key**: Defender stays close to assignment, not in help position

### Corner Location Edge Cases

#### Non-BH Defenders in Corners
**Scenario**: Non-BH defender guarding offensive player in corner location

**Rules**:
1. **Upper corner**: Defender's y position must always be **LOWER** (defender below offensive player)
   - `def_y = oy - random.randint(2, 4)` (lower y value = defender below)
2. **Lower corner**: Defender's y position must always be **HIGHER** (defender above offensive player)
   - `def_y = oy + random.randint(2, 4)` (higher y value = defender above)
3. X position: Relative to ball handler and offensive player positioning

#### BH Defenders in Corners
**Scenario**: Ball handler in corner location

**Rules**:
1. **X position**: Defender's x value should **equal** the ball handler's x value (with potential slight variation in future, but equal for now).
   - `def_x = ox` (defender x equals ball handler x)
2. **Y position**: Follow corner y-position rules (same as non-BH defenders)
   - **Upper corner**: Defender's y must be **LOWER** (defender below ball handler)
     - `def_y = oy - random.randint(2, 4)` (lower y value = defender below)
   - **Lower corner**: Defender's y must be **HIGHER** (defender above ball handler)
     - `def_y = oy + random.randint(2, 4)` (higher y value = defender above)

## Implementation Phases

### Phase 1: Create Unified Core Function
**Goal**: Build the new unified `calculate_defender_coords()` function

**Tasks**:
1. Create `calculate_defender_coords()` with direct basket-based calculation
2. Implement `get_spacing()` helper for aggression levels
3. Implement `apply_spot_adjustments()` for specialized positioning
4. Implement `verify_defender_closer_to_basket()` validation
5. Add comprehensive unit tests

**Files to Create/Modify**:
- `BackEnd/utils/shared_defense.py` - Add new functions
- `BackEnd/tests/test_defender_coords.py` - New test file

**Success Criteria**:
- Function correctly calculates defender position for all spots
- BH defenders are always closer to basket than ball handler
- Non-BH defenders position correctly relative to assignment
- Works correctly for both home and away offense (in HOME orientation)

---

### Phase 2: Create Public API Wrapper
**Goal**: Build `get_defender_coords()` wrapper that handles orientation

**Tasks**:
1. Create `get_defender_coords()` wrapper function
2. Implement automatic coordinate flipping/unflipping
3. Add comprehensive tests for orientation handling
4. Document coordinate contract clearly

**Files to Modify**:
- `BackEnd/utils/shared_defense.py` - Add wrapper function

**Success Criteria**:
- Wrapper correctly handles coordinate orientation
- Callers can pass coordinates in any orientation
- Returns coordinates in same orientation as input

---

### Phase 3: Migrate Man Defense (BH Defenders)
**Goal**: Replace `assign_bh_defender_coords()` calls with new system

**Tasks**:
1. Update `animator.py` line 630 (BH defender setup) to use `get_defender_coords()`
2. Update `animator.py` line 654 (BH defender movement) to use `get_defender_coords()`
3. Remove coordinate flipping logic from call sites
4. Test man defense BH defender positioning

**Files to Modify**:
- `BackEnd/models/animator.py` - Replace `assign_bh_defender_coords()` calls

**Success Criteria**:
- BH defenders position correctly for home and away offense
- No manual coordinate flipping at call sites
- x_direction bug fixed (defender on correct side)

---

### Phase 4: Migrate Man Defense (Non-BH Defenders)
**Goal**: Replace `assign_non_bh_defender_coords()` calls with new system

**Tasks**:
1. Update `animator.py` non-BH defender calls to use `get_defender_coords()`
2. Pass `ball_handler_coords` parameter for relative positioning
3. Remove coordinate flipping logic from call sites
4. Test non-BH defender positioning

**Files to Modify**:
- `BackEnd/models/animator.py` - Replace `assign_non_bh_defender_coords()` calls

**Success Criteria**:
- Non-BH defenders position correctly
- Defenders maintain proper spacing relative to ball handler
- No manual coordinate flipping at call sites

---

### Phase 5: Migrate Zone Defense ✅ COMPLETE
**Goal**: Replace zone defense functions with new unified system

**Tasks**:
1. Update `assign_zone_defender_coords()` to use `get_defender_coords()`
2. Update `assign_all_zone_defenders()` to use unified system
3. Update `animator.py` `_position_zone_defenders()` to use new functions
4. Remove coordinate flipping logic from zone call sites
5. Test all zone types (2-3, 3-2, 1-3-1)

**Files to Modify**:
- `BackEnd/utils/shared_defense.py` - Update zone functions
- `BackEnd/models/animator.py` - Update zone positioning

**Success Criteria**:
- ✅ Zone defenders position correctly
- ✅ BH defenders in zone use unified system
- ✅ All zone types work correctly
- ✅ No manual coordinate flipping at call sites
- ✅ **COMPLETED**: All zone defense functions migrated to use `get_defender_coords()`
- ✅ **COMPLETED**: x_direction bug fixed for away offense in zone defense

---

### Phase 6: Remove Old Functions and Cleanup
**Goal**: Remove old functions and consolidate code

**Tasks**:
1. Remove `assign_bh_defender_coords()` (replaced by unified system)
2. Remove `assign_non_bh_defender_coords()` (replaced by unified system)
3. Update `assign_zone_defender_coords()` to be a thin wrapper
4. Remove all coordinate flipping logic from call sites
5. Update documentation
6. Run full test suite

**Files to Modify**:
- `BackEnd/utils/shared_defense.py` - Remove old functions
- `BackEnd/models/animator.py` - Remove coordinate flipping code
- `docs/animation_system.md` - Update documentation

**Success Criteria**:
- No old functions remain
- All call sites use unified system
- No coordinate flipping logic at call sites
- All tests pass

---

### Phase 7: Final Testing and Validation
**Goal**: Comprehensive testing and bug verification

**Tasks**:
1. Test all defensive scenarios:
   - Home offense, man defense
   - Away offense, man defense
   - Home offense, zone defense (2-3, 3-2, 1-3-1)
   - Away offense, zone defense (2-3, 3-2, 1-3-1)
   - Full court press
   - Half court trap
2. Verify x_direction bug is fixed
3. Verify BH defenders are always closer to basket
4. Verify non-BH defenders position correctly (may not be closer to basket)
5. Verify no coordinate flipping bugs
6. Performance testing

**Success Criteria**:
- All scenarios work correctly
- x_direction bug fixed
- No coordinate orientation bugs
- Performance acceptable

## Key Benefits

1. **Single Source of Truth**: One function calculates all defender positions
2. **Automatic Orientation Handling**: Callers don't need to manage coordinate flipping
3. **Direct Calculation**: x_direction calculated from coordinates, not flags
4. **Simpler Call Sites**: No manual coordinate transformations
5. **Easier to Debug**: Clear coordinate flow through system
6. **More Maintainable**: Changes in one place affect all defenders
7. **Testable**: Core function works in single orientation, easier to test

## Migration Strategy

### Backward Compatibility
- Keep old functions during migration (mark as deprecated)
- Migrate one phase at a time
- Test thoroughly after each phase
- Remove old functions only after all phases complete

### Risk Mitigation
- Comprehensive tests before starting
- Migrate in phases (low risk)
- Keep old code until new code proven
- Test each scenario after migration

## Testing Strategy

### Unit Tests
- Test `calculate_defender_coords()` with various inputs
- Test coordinate orientation handling
- Test spot-specific adjustments
- Test edge cases:
  - Player at basket
  - Post defenders (low/medium post) - verify tight positioning
  - Corner locations for non-BH defenders - verify y-position rules
  - Corner locations for BH defenders - verify x equals ball handler x AND y-position rules

### Integration Tests
- Test man defense scenarios
- Test zone defense scenarios
- Test coordinate flipping
- Test x_direction correctness

### Visual Testing
- Verify defenders animate on correct side
- Verify BH defenders are closer to basket
- Verify non-BH defenders maintain proper spacing and positioning
- Verify spacing looks correct

## Expected Outcome

After completion:
- ✅ Single unified function for all defender coordinates
- ✅ Automatic coordinate orientation handling
- ✅ x_direction bug fixed (calculated from coordinates)
- ✅ BH defenders always closer to basket
- ✅ Non-BH defenders positioned correctly (relative to assignment)
- ✅ Simpler call sites (no manual flipping)
- ✅ Easier to maintain and extend
- ✅ More testable and debuggable

## Timeline Estimate

- Phase 1: 2-3 hours (core function + tests)
- Phase 2: 1-2 hours (wrapper + tests)
- Phase 3: 1-2 hours (BH defender migration)
- Phase 4: 1-2 hours (non-BH defender migration)
- Phase 5: 2-3 hours (zone defense migration)
- Phase 6: 1-2 hours (cleanup)
- Phase 7: 2-3 hours (testing)

**Total: 10-17 hours**

## Notes

- This refactoring is similar in scope to the ball animation consolidation
- Focus on incremental changes and thorough testing
- Keep old functions until new system is proven
- Coordinate orientation is the key complexity - handle it automatically

