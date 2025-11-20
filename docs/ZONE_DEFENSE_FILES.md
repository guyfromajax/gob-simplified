# Zone Defense Implementation Files

These files contain the zone defense implementation code. The user will download and preserve these files before reverting to the commit before ball animation steps 1 & 2.

## Zone Defense Files

### 1. `BackEnd/utils/shared_defense.py`
**Purpose:** Core zone defense logic
**Contains:**
- Zone definitions: `ZONE_23_NORMAL`, `ZONE_23_LOWER_SHIFT`, `ZONE_23_UPPER_SHIFT`
- Point-in-polygon algorithm: `_point_in_polygon()`, `_point_in_zone()`
- Zone coordinate conversion: `_get_zone_coords()`, `_get_23_zone_boundaries()`
- Distance calculations: `_manhattan_distance_to_basket()`, `_distance_toward_basket()`
- Zone assignment functions: `assign_zone_defender_coords()`, `assign_all_zone_defenders()`
- Overlap detection and resolution: `_detect_overlapping_zones()`, `_resolve_overlap_assignments()`

**Note:** This is a **NEW FILE** created for zone defense. Save the entire file.

---

### 2. `BackEnd/models/animator.py`
**Purpose:** Zone defense positioning in animation system
**Contains:**
- `_position_zone_defenders()` method (lines ~1344-1520)
  - Builds offensive player positions by step
  - Calls zone defense assignment functions
  - Creates defensive animations with zone-based positioning

**Note:** Only the `_position_zone_defenders()` method is zone-specific. The rest of the file is general animation logic.

**To extract zone defense:**
- Copy the entire `_position_zone_defenders()` method
- Copy any imports related to zone defense: `from BackEnd.utils.shared_defense import ...`

---

### 3. `BackEnd/models/turn_manager.py`
**Purpose:** Zone defense logic in turn management
**Contains:**
- Zone defense logic in `set_playcalls()` method (currently commented out with `# ✅ TEMPORARY: Force MAN defense`)
- Zone defense logic in `assign_roles()` method (currently commented out with `# ✅ TEMPORARY: Zone defense disabled`)
- Zone defense logic in `calculate_foul_turnover()` method (currently commented out)

**Note:** These sections are currently disabled/commented out for debugging. Save the commented code for reference.

**To extract zone defense:**
- Look for commented sections with `# ✅ TEMPORARY: Zone defense disabled`
- Save the uncommented version of the zone defense logic (the commented code shows what was disabled)

---

### 4. `BackEnd/constants.py`
**Purpose:** Strategy call dictionaries with zone defense weights
**Contains:**
- `STRATEGY_CALL_DICTS["defense"]` dictionary:
  ```python
  "defense": {
      0: ["Man"],
      1: ["Man", "Man", "Zone"],
      2: ["Man", "Zone"],
      3: ["Man", "Zone", "Zone"],
      4: ["Zone"]
  }
  ```

**Note:** This is a modification to an existing dictionary. Save the entire `STRATEGY_CALL_DICTS` dictionary or at least the `"defense"` key.

---

### 5. Integration in `BackEnd/models/animator.py` (skeleton_to_animations method)
**Purpose:** Route to zone defense positioning based on defense_playcall
**Contains:**
- Check for `defense_playcall == "Zone"` in `skeleton_to_animations()` method
- Calls `_position_zone_defenders()` when zone defense is detected
- Currently commented out with `# ✅ TEMPORARY: Zone defense disabled`

**Location:** In `skeleton_to_animations()` method, around the section that adds defensive animations.

**To extract:**
- Look for the `elif defense_playcall == "Zone":` block (currently commented)
- Save the uncommented version

---

## Summary

**Files to save:**
1. ✅ `BackEnd/utils/shared_defense.py` - **ENTIRE FILE** (new file)
2. ⚠️ `BackEnd/models/animator.py` - `_position_zone_defenders()` method only
3. ⚠️ `BackEnd/models/turn_manager.py` - Zone defense sections in `set_playcalls()`, `assign_roles()`, `calculate_foul_turnover()`
4. ⚠️ `BackEnd/constants.py` - `STRATEGY_CALL_DICTS["defense"]` dictionary
5. ⚠️ `BackEnd/models/animator.py` - Integration logic in `skeleton_to_animations()` method

**Current Status:**
- Zone defense logic is fully implemented
- Currently **disabled/commented out** for debugging (forcing MAN defense)
- All code is preserved in comments - just need to uncomment when re-enabling

---

## Re-enabling Zone Defense After Revert

After reverting and re-uploading these files:

1. Uncomment the zone defense sections in `turn_manager.py`
2. Uncomment the zone defense integration in `animator.py` (`skeleton_to_animations()`)
3. Ensure `shared_defense.py` is present (or re-upload it)
4. Test that `STRATEGY_CALL_DICTS["defense"]` includes zone weights in `constants.py`

---

## Marker Convention

The user will add a marker to filenames when downloading:
- Example: `shared_defense_ZONE_DEFENSE_ONLY.py`
- This indicates these files should only be accessed for zone defense components

