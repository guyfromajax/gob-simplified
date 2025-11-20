# Zone Defense Integration Plan

## Overview
This plan outlines the steps to integrate the 2-3 zone defense system into the current codebase. Zone defense logic has been preserved in separate files and needs to be integrated alongside the existing man-to-man defense.

## Current State

### ✅ Already Present:
- `BackEnd/constants.py`: Zone defense strategy dictionary (`STRATEGY_CALL_DICTS["defense"]`) already includes zone weights
- `BackEnd/models/turn_manager.py`: Basic zone defense checks exist but use simplified logic (random defender selection)

### ❌ Missing:
- Zone defense functions in `BackEnd/utils/shared_defense.py`
- `_position_zone_defenders()` method in `BackEnd/models/animator.py`
- Zone defense routing in `skeleton_to_animations()` method
- Proper zone defense logic in `turn_manager.py` methods (`assign_roles()`, `calculate_foul_turnover()`)

## Integration Steps

### Step 1: Add Zone Defense Functions to `shared_defense.py`
**File:** `BackEnd/utils/shared_defense.py`

**Action:** Add all zone defense functions from `shared_defense_ZONE_DEFENSE_ONLY.py`

**Functions to add:**
- Zone definitions: `ZONE_23_NORMAL`, `ZONE_23_LOWER_SHIFT`, `ZONE_23_UPPER_SHIFT`
- Helper functions: `_get_zone_coords()`, `_point_in_polygon()`, `_get_23_zone_boundaries()`, `_point_in_zone()`
- Distance functions: `_manhattan_distance_to_basket()`, `_distance_toward_basket()`, `_find_closest_spot_in_zone_to_point()`
- Core functions: `assign_zone_defender_coords()`, `_detect_overlapping_zones()`, `_resolve_overlap_assignments()`, `assign_all_zone_defenders()`

**Note:** The reference file includes both MAN and ZONE defense functions. We already have MAN defense functions, so we only need to add the ZONE-specific functions (starting from line 255 in the reference file).

---

### Step 2: Add `_position_zone_defenders()` Method to `animator.py`
**File:** `BackEnd/models/animator.py`

**Action:** Add the `_position_zone_defenders()` method from `animator_ZONE_DEFENSE_ONLY.py`

**Location:** After `_position_hct_defenders()` method (around line 1143)

**Key Points:**
- Method signature: `def _position_zone_defenders(self, offensive_animations, def_lineup, skeleton_steps)`
- Handles zone boundary shifts based on ball location
- Calls `assign_all_zone_defenders()` for each step
- Flips defensive coordinates when away team is on offense
- Returns list of defensive animations

---

### Step 3: Integrate Zone Defense Routing in `skeleton_to_animations()`
**File:** `BackEnd/models/animator.py`

**Location:** Around line 846-870 (where defensive positioning is decided)

**Current Structure:**
```python
if add_defenders and def_lineup:
    if is_fcp:
        # FCP positioning
    elif is_hct:
        # HCT positioning
    else:
        # Standard (man-to-man) positioning
```

**Action:** Add zone defense check before standard positioning:
```python
if add_defenders and def_lineup:
    defense_playcall = self.game.game_state.get("defense_playcall", "Man")
    
    if is_fcp:
        # FCP positioning
    elif is_hct:
        # HCT positioning
    elif defense_playcall == "Zone":
        # Zone defense positioning
        defensive_anims = self._position_zone_defenders(
            offensive_animations,
            def_lineup,
            steps
        )
        animations.extend(defensive_anims)
    else:
        # Standard (man-to-man) positioning
```

---

### Step 4: Update `assign_roles()` in `turn_manager.py`
**File:** `BackEnd/models/turn_manager.py`

**Location:** Around line 1335 (in `assign_roles()` method)

**Current Code:**
```python
if game_state["defense_playcall"] == "Zone":
    defender_pos = random.choice(list(def_lineup))
else:
    defender_pos = shooter_pos
```

**Action:** Replace with proper zone defense logic from `turn_manager_ZONE_DEFENSE_ONLY.py` (lines 46-113)

**Key Logic:**
- Get shooter's spot from final step
- Get ball handler's spot for zone shift logic
- Get zone boundaries using `_get_23_zone_boundaries()`
- Find which defender's zone contains the shooter
- Handle overlaps (prefer C, then PF/SF, then PG/SG)
- Fallback to random if shooter not in any zone

---

### Step 5: Update `calculate_foul_turnover()` in `turn_manager.py`
**File:** `BackEnd/models/turn_manager.py`

**Location:** Around lines 1401, 1409, 1424

**Current Code:**
- Line 1401: `defender = def_lineup.get(def_pos) if defense_call != "Zone" else random.choice(list(def_lineup.values()))`
- Line 1409: `if defense_call == "Zone": pressure *= 0.9`
- Line 1424: `defender = def_lineup[pos] if defense_call != "Zone" else random.choice(list(def_lineup.values()))`

**Action:** Keep the pressure reduction for zone defense (line 1409). The random defender selection is acceptable for foul/turnover calculation (simplified logic is fine here).

**Note:** The current random selection for zone defense in foul calculations is acceptable and matches the reference implementation.

---

## Testing Checklist

After integration, test:

- [ ] **Zone Defense Call Selection**: Verify that defense playcall is set to "Zone" when strategy setting is 4 (zone only) or randomly when strategy setting allows zone
- [ ] **Zone Positioning**: Verify defensive players position in zone areas, not on specific offensive players
- [ ] **Zone Shifts**: Verify zones shift when ball moves to lower/upper wings/corners
- [ ] **Ball Handler Priority**: Verify defenders guard ball handler when ball handler enters their zone
- [ ] **Overlap Handling**: Verify proper defender assignment when offensive player is in multiple zones
- [ ] **Away Team Offense**: Verify zone defense works correctly when away team has the ball (coordinate flipping)
- [ ] **Shot Defender Assignment**: Verify correct defender is assigned to shooter based on zone logic
- [ ] **Foul/Turnover Calculations**: Verify zone defense reduces pressure (0.9 multiplier) in calculations

---

## Files Modified

1. `BackEnd/utils/shared_defense.py` - Add zone defense functions
2. `BackEnd/models/animator.py` - Add `_position_zone_defenders()` method and routing logic
3. `BackEnd/models/turn_manager.py` - Update `assign_roles()` method with proper zone logic

---

## Files Unchanged

- `BackEnd/constants.py` - Already has zone defense strategy dictionary ✅
- `BackEnd/models/turn_manager.py` - `calculate_foul_turnover()` zone logic is acceptable as-is
- `BackEnd/models/turn_manager.py` - `set_playcalls()` already sets `defense_playcall` correctly ✅

---

## Implementation Order

1. **Step 1** - Add zone functions to `shared_defense.py` (foundation)
2. **Step 2** - Add `_position_zone_defenders()` method (core logic)
3. **Step 3** - Add routing in `skeleton_to_animations()` (integration)
4. **Step 4** - Update `assign_roles()` (shot defender logic)
5. **Step 5** - Verify `calculate_foul_turnover()` (should be fine as-is)

---

## Notes

- Zone defense functions in `shared_defense_ZONE_DEFENSE_ONLY.py` depend on existing MAN defense functions (`assign_bh_defender_coords`, `assign_non_bh_defender_coords`), which are already present ✅
- Coordinate flipping logic is critical - ensure zone boundaries match offensive coordinate orientation
- Zone shifts (normal/lower/upper) are determined by ball handler location, not shooter location
- Overlap resolution prioritizes defenders without other players in their zones

---

## Rollback Plan

If issues arise:
1. Comment out zone defense routing in `skeleton_to_animations()` (force man-to-man)
2. Comment out zone logic in `assign_roles()` (use position matching)
3. Zone functions in `shared_defense.py` can remain (not called if routing is disabled)

