## Defense Coordinate System ✅ **COMPLETE** (December 2024 - January 2025; doc synced to code June 2026)

> **Runtime coords convention (2026-06):** `player.coords` on backend player objects stores **display orientation** (the real visual position — the same orientation animations are emitted in). An earlier "always HOME orientation" runtime convention was sunset (`_normalize_animation_coords_to_runtime_home` in `BackEnd/utils/shared.py` is now a pass-through). The HOME-orientation rules below apply **within the defender-coordinate functions** (internal math + `assign_all_zone_defenders` return values), not to persisted runtime coords.

**Base Constants**

1. **Core Functions**:
   - `get_defender_coords()` - Public API wrapper, handles coordinate orientation automatically
   - `calculate_defender_coords()` - Core unified function, works internally in HOME orientation
   - `assign_all_zone_defenders()` - Zone defense assignment with overlap resolution
2. **Coordinate Orientation**: HOME orientation (x=90 for home basket, x=10 for away basket)
3. **Defender Types**: Ball handler (BH) defenders, non-ball handler defenders, zone defenders
4. **Zone Types Supported**:
   - **2-3 Zone:** Normal, Lower Shift, Upper Shift
   - **3-2 Zone:** Normal, Lower Corner Shift, Upper Corner Shift
   - **1-3-1 Zone:** Normal, Lower Shift, Lower Corner Shift, Upper Shift, Upper Corner Shift
5. **Multi-Defender Offset Patterns**:
   - Center/Key/Wing spots: `y += 2` / `y -= 2`
   - Corner/Baseline/Post spots: `x += x_direction * 2` / `x -= x_direction * 2`
6. **Key Files**:
   - `BackEnd/utils/shared_defense.py` - Core defender coordinate logic **and** zone definitions (`ZONE_23_NORMAL`, `ZONE_32_NORMAL`, `ZONE_131_NORMAL` + shift variants, plus HCT trap-zone constants)
   - `BackEnd/constants.py` - Court spot coordinates (`HCO_STRING_SPOTS`), rim coordinates
   - `BackEnd/models/animator.py` - Flips zone-defender coords back to display orientation for animation (`_position_zone_defenders`; HCT variant: `_position_hct_zone_defenders`)

**Defense Coordinate System Flow (Unified Defender Positioning - 4 Steps)**

1. **Input Processing**: `get_defender_coords()` receives offensive player coordinates in any orientation (home or away)
2. **Orientation Conversion**: Converts input coordinates to HOME orientation for internal calculations
3. **Coordinate Calculation**: `calculate_defender_coords()` calculates defender position using geometric calculation (works in HOME orientation)
4. **Output Conversion**: Converts result back to same orientation as input (returns coordinates in original orientation)

**Zone Defender Placement System Flow (6 Steps)**

1. **Overlap Detection**: Scans all offensive players to find which players are in multiple defensive zones
2. **Overlap Resolution**: Determines which defender should guard each overlap player (prioritizes zone coverage when ball handler is double-teamed)
3. **Coordinate Assignment**: Assigns coordinates for overlap-assigned defenders (using `get_defender_coords()`) and non-overlap defenders (using standard priority logic)
4. **Multi-Defender Detection**: Detects when multiple defenders guard the same offensive player
5. **Offset Application**: Applies coordinate offsets to prevent perfect stacking (pattern depends on offensive player's spot location)
6. **Orientation Conversion**: Converts all defender coordinates to HOME orientation before returning (for consistent animation flipping)

**Long Form Documentation**

### Overview

The Defense Coordinate System provides a unified architecture for calculating defensive player positions. It handles all defender types (ball handler defenders, non-ball handler defenders, and zone defenders) through a single entry point, with automatic coordinate orientation handling.

**Status:** Fully refactored and operational (December 2024)

### Unified Defender Coordinate System

**Architecture:**

- **`get_defender_coords()`** (`BackEnd/utils/shared_defense.py`) - Public API wrapper
  - Handles coordinate orientation transformation automatically
  - Accepts coordinates in any orientation (home or away)
  - Returns coordinates in same orientation as input
  - Delegates to `calculate_defender_coords()` for core logic
  
- **`calculate_defender_coords()`** (`BackEnd/utils/shared_defense.py`) - Core unified function
  - Works internally in HOME orientation
  - Handles both BH and non-BH defenders
  - Uses geometric calculation for positioning
  - Implements complex non-BH defender logic (ball_spot/o_spot combinations)

**Key Features:**
- ✅ Single unified function for all defender types
- ✅ Automatic coordinate orientation handling (no manual flipping)
- ✅ Geometric calculation (x_direction from coordinates, not flags)
- ✅ BH defenders always closer to basket
- ✅ Non-BH defenders positioned correctly relative to assignment
- ✅ Full zone defense support (2-3, 3-2, 1-3-1)

**Benefits:**
- ✅ Single source of truth (one function instead of two)
- ✅ No coordinate flipping bugs (handled automatically)
- ✅ Fixed x_direction bug (geometric calculation)
- ✅ Simpler call sites (no manual coordinate transformations)
- ✅ Easier to maintain and extend
- ✅ More testable and debuggable

**Coordinate Contract:**
- **Input:** Coordinates can be in any orientation (home or away)
- **Internal:** All calculations happen in HOME orientation
- **Output:** Coordinates returned in same orientation as input

**Core Rules:**
- **For BH defenders:** Defender is always positioned closer to the basket than the ball handler
- **For non-BH defenders:** Defender is positioned relative to their assignment and ball handler, maintaining proper spacing, but may not always be closer to basket. Non-BH defenders require `ball_spot` parameter for complex positioning logic

### Zone Defender Placement System

**Status:** Fully implemented with overlap resolution and multi-defender offset logic (January 2025)

The zone defender placement system assigns defensive coordinates for all zone defenders, handling zone overlaps, multi-defender situations, and prioritizing zone coverage when the ball handler is double-teamed.

#### Core Function: `assign_all_zone_defenders()`

**Location:** `BackEnd/utils/shared_defense.py`

**Purpose:** Assigns defensive coordinates for all zone defenders, handling overlaps and applying offsets.

**Process:**

1. **Overlap Detection** (`_detect_overlapping_zones()`)
   - Scans all offensive players to find which players are in multiple defensive zones
   - Returns `overlap_map`: `{offensive_player_id: [defender_positions]}`
   - Uses `_point_in_zone()` to check if player coordinates fall within zone boundaries

2. **Overlap Resolution** (`_resolve_overlap_assignments()`)
   - Determines which defender should guard each overlap player
   - **Key Logic:** When ball handler is double-teamed:
     - If one defender has other players in their zone → that defender guards zone player, other stays on BH
     - If both have other players → randomly choose one to guard zone player, other stays on BH
     - If neither has other players → both double-team ball handler (offsets applied later)
   - **Always ensures:** At least one defender stays on ball handler when BH is double-teamed
   - Returns assignments: `{defender_pos: offensive_player_id}` or `None` (guards zone player via priority)

3. **Coordinate Assignment**
   - For overlap-assigned defenders: Guard specific offensive player using `get_defender_coords()`
   - For non-overlap defenders: Use standard priority logic (`assign_zone_defender_coords()`)
   - Filters players to consider based on overlap assignments (excludes already-assigned overlap players)

4. **Multi-Defender Offset Application** (`_apply_multi_defender_offsets()`)
   - Detects when multiple defenders guard the same offensive player
   - Applies coordinate offsets to prevent perfect stacking
   - Offset pattern depends on offensive player's spot location

#### Multi-Defender Offset Logic

**Location:** `BackEnd/utils/shared_defense.py` (`_apply_multi_defender_offsets`)

**Purpose:** Prevents defenders from stacking perfectly when multiple defenders guard the same offensive player.

**Offset Patterns by Spot Category:**

1. **Center/Key Spots** (`key`, `topLane`, `upper highPost`, `lower highPost`, `midLane`):
   - Defender 1: `y += 2`
   - Defender 2: `y -= 2`
   - **Note:** Uses consistent pattern regardless of zone area (prevents convergence when spots change)

2. **Wing Spots** (`upper wing`, `upper midWing`, `lower wing`, `lower midWing`, `upper apex`, `upper bird`, `lower apex`, `lower bird`):
   - Defender 1: `y += 2`
   - Defender 2: `y -= 2`

3. **Corner/Baseline/Post Spots** (`upper midCorner`, `upper corner`, `lower midCorner`, `lower corner`, `upper midBaseline`, `lower midBaseline`, `upper midPost`, `upper lowPost`, `lower midPost`, `lower lowPost`):
   - Defender 1: `x += x_direction * 2`
   - Defender 2: `x -= x_direction * 2`
   - **x_direction:** `1` if home team on offense, `-1` if away team on offense

**Key Design Decision:**
- Offsets are **always applied** for multi-defender situations (not conditional on zone area)
- This ensures defenders remain offset even when offensive player moves between steps
- Prevents convergence/stacking that occurred with zone-area-based offset logic

#### Zone Coverage Prioritization

**When Ball Handler is Double-Teamed:**

The system prioritizes zone coverage while ensuring ball handler is always guarded:

1. **One Defender Has Other Players in Zone:**
   - That defender guards the closest other player in their zone (by distance to basket)
   - Other defender stays on ball handler

2. **Both Defenders Have Other Players in Zone:**
   - Randomly choose one defender to guard their closest zone player
   - Other defender stays on ball handler
   - **Ensures:** At least one defender always guards ball handler

3. **Neither Defender Has Other Players in Zone:**
   - Both defenders guard ball handler (double-team)
   - Offsets applied via `_apply_multi_defender_offsets()`

**Implementation Details:**
- Uses `_manhattan_distance_to_basket()` to find closest zone player
- Random selection via `random.choice()` when both have zone players
- Assignment stored in `overlap_player_to_guard` dict for coordinate calculation

#### Zone Types Supported

- **2-3 Zone:** Normal, Lower Shift, Upper Shift
- **3-2 Zone:** Normal, Lower Corner Shift, Upper Corner Shift
- **1-3-1 Zone:** Normal, Lower Shift, Lower Corner Shift, Upper Shift, Upper Corner Shift

**Zone Boundaries:**
- Defined as lists of spot names from `HCO_STRING_SPOTS`
- Converted to coordinate polygons via `_get_zone_coordinates()`
- Used for overlap detection via `_point_in_zone()` checks

#### Coordinate Orientation Handling ✅ **CRITICAL** (January 2025)

**Purpose:** Ensures consistent coordinate orientation throughout the zone defense assignment process to prevent double-flipping bugs.

**Coordinate Flow:**
1. **Input:** `assign_all_zone_defenders()` receives offensive player coordinates in their current orientation (away orientation if away team on offense)
2. **Processing:** All zone defense calculations work internally, but `get_defender_coords()` returns coordinates in the same orientation as input (away if away offense)
3. **Output:** `assign_all_zone_defenders()` converts all defender coordinates to **HOME orientation** before returning
4. **Animation:** `animator.py` (`_position_zone_defenders`) flips defender coordinates to away orientation to match offensive coordinates

**Critical Fix - Fallback Path Coordinate Conversion:**

**Bug:** The fallback path in `assign_all_zone_defenders()` (the "ball handler still not guarded → assign closest defender" branch) was missing the HOME orientation conversion, causing a double-flip:
- `get_defender_coords()` returned coords in away orientation
- Fallback path assigned directly (still in away orientation)
- `animator.py` flipped again → defender appeared on wrong end of court

**Fix:** Added HOME orientation conversion in the fallback path:
```python
# get_defender_coords returns in same orientation as input (away if away offense)
# Zone defense expects HOME orientation, so convert if away offense
if is_away_offense:
    coords = get_away_player_coords(coords)
assignments[closest_defender] = coords
```

**Edge Case Fixed:**
- **Scenario:** 1-3-1 zone defense, ball handler in lower corner, away team on offense
- **Symptom:** Defender would animate to correct position initially, then flip to wrong end of court
- **Root Cause:** Fallback path (used when ball handler check fails) didn't convert to HOME orientation
- **Validation:** Test `test_zone_defense_lower_corner_away_offense.py` verifies defender x coordinate is closer to 6 (away side) than 88 (home side)

**Key Principle:**
- **All paths** in `assign_all_zone_defenders()` must return coordinates in HOME orientation
- This ensures `animator.py` can consistently flip once to match offensive coordinate orientation
- Both the normal path and the fallback path follow this pattern

### HCT (Half Court Trap) Zone Defense

`shared_defense.py` also hosts the HCT trap-defense placement built on the same zone machinery: `HCT_STANDARD_UPPER_SHIFT` / `HCT_STANDARD_LOWER_SHIFT` zone constants (stored home-defending orientation, flipped via `_get_zone_coords` like the HCO zones), `compute_hct_trap_formation()` (two trap defenders offset around the ball handler inside a clamp box), and `resolve_hct_defender_collisions()` (HCT-only same-coordinate collision resolution). Animator entry point: `_position_hct_zone_defenders`. Gameplay rules live in `05_GP_Supporting_Systems/FCP_HCT_System.md`.

### Per-Step Timing: The Two-Handler Pass Step (2026-07)

The sections above cover **where** defenders go. This covers **when** across skeleton steps. `_position_zone_defenders` / `_position_standard_defenders` compute a defender coord per skeleton step, keyed on the **current ball handler** for that step (`hasBallAtStep[step_index]`). The emitter reads `end = movement index i+1`, so a coord authored at step S surfaces as the **end of emitted step S−1**.

**The bug this caused:** on a pass, `hasBallAtStep` flips to the receiver **instantly** at step S. So the defenders' post-pass (receiver-coverage) layout landed at index S → the **end of emitted step S−1** → defenders rotated to guard the receiver a **full beat before** the ball ever detached. Worst in zone (big shell shifts); present but subtle in man.

**The fix — two-handler model:** a pass step is the one step with two *sequential, non-overlapping* ball handlers — the **passer owns the start**, the **receiver owns the end**. So on a step where the ball handler flips vs. the previous step (a pass), the defender's animation **holds at his previous (passer-owned) coord** (`def_movement[-1]`), which makes his rotation to the receiver render **across the pass step**, starting the instant the ball detaches (in unison). Implemented in `_position_zone_defenders` and `_position_standard_defenders` (animator.py) via a `prev_ball_handler_pos` tracker + a pass-step hold.

**Gameplay-safety (animation-only):** the change touches only animation coords, not outcomes —
- the zone **assignment map** (`zone_defender_assignments_by_step`, read by `_resolve_hco_shot_defenders` for shot contest) is still computed at the **true** step;
- the hold is **guarded off the final step**, so `player.coords` (synced from the last animation coord and read by the attack-drive geometry contest) is **unchanged**;
- no extra `assign_all_zone_defenders` / `get_defender_coords` call, so the global RNG stream is untouched (SS&S-reproducible).

**Not addressed (follow-up knobs):** the lag fixes the *beat-early* rotation but does **not** duration-match — a short defender shift still finishes early *within* the pass flight (the 50ms-vs-255ms mismatch). Optional polish: a per-defender pass-step tween delay ("read then commit", ~40% of ball flight) or stretching the defender move to span the ball flight. Both layer on top of the corrected endpoints; attribute-driven timing is a candidate here.

### Key Files

- `BackEnd/utils/shared_defense.py` - Core defender coordinate logic
  - `get_defender_coords()` - Public API wrapper
  - `calculate_defender_coords()` - Core unified function
  - `assign_all_zone_defenders()` - Zone defense assignment
  - `_apply_multi_defender_offsets()` - Multi-defender offset logic
  - Zone definitions (`ZONE_23_*`, `ZONE_32_*`, `ZONE_131_*`, `HCT_STANDARD_*`)
- `BackEnd/constants.py` - Court spot coordinates (`HCO_STRING_SPOTS`), rim coordinates
- `BackEnd/models/animator.py` - Coordinate flipping for animation (`_position_zone_defenders`, `_position_hct_zone_defenders`)
- `tests/test_zone_defense_lower_corner_away_offense.py` - Validation test

