# Motion Offense System

**Date:** January 2025 (Design), February 2025 (Implementation Complete)  
**Status:** ✅ **IMPLEMENTED** - Fully functional motion offense system

---

## Overview

Motion offenses differ fundamentally from Set Plays in execution. Rather than having a single ideal outcome with variant skeletons (successful/contested/broken), Motion offenses use **infinite circular loops** where players cycle through positions until a turn-ending event occurs (shot, foul, turnover, steal).

---

## Core Principles

### 1. Circular Loop Structure
- Motion plays are built as **base loops** (no variant system)
- Final step should match first step (or explicitly loop back to step 0/1)
- Engine continues looping until a turn-ending event occurs
- No skeleton variants needed - just one base loop per motion play

### 2. Location-Based Shot Type Determination
Shot type is determined **dynamically** based on player location, not hard-coded in skeleton:

**Inside Shots:**
- Automatic if player is at lane spots: `lower lowPost`, `lower midPost`, `upper lowPost`, `upper midPost`, `midLane`, `basketSpot`
- Receives pass → shoots from that spot → inside shot
- Uses `playcall = "Inside"` for shot score calculation

**Outside Shots:**
- Any other location → shoot from current spot → outside shot
- Uses `playcall = "Outside"` for shot score calculation

**Attack Shots:**
- Player on non-lane spot (e.g., `upper wing`) chooses to drive
- **Two-step process**: 
  1. Step 1: `action: "drive"` to destination lane spot
  2. Step 2: `action: "shoot"` at destination lane spot
- Shoots from that lane spot → attack shot
- Uses `playcall = "Attack"` for shot score calculation
- **Note**: Two-step approach ensures proper drive animation and accurate shot location detection

### 3. Focus as Influence, Not Constraint
- Focus (Inside/Attack/Outside) **influences probability** of actions, doesn't lock players in
- "Inside" focus → more likely to pass to lane spots
- "Attack" focus → more likely to drive from non-lane spots
- "Outside" focus → more likely to shoot from current spot
- **Player attributes matter**: High IQ players can recognize better opportunities even if they don't match focus

### 4. No Variant Modifier System
- Motion plays do **NOT** use variant modifiers (successful/contested/broken)
- Shot calculation uses base attributes + defense + location-based playcall
- No `_variant` field needed in skeleton for Motion plays
- Set Plays continue to use variant system as they do now

---

## Drive Destination Logic

### Starting Position → Valid Destinations

**Upper Half Starting Positions:**
- Examples: `upper wing`, `upper corner`, `upper midWing`, `upper midCorner`
- Can drive to: `upper lowPost`, `upper midPost`, `upper bird`, `midLane`, `basketSpot`
- Cannot drive to: lower-side spots (unrealistic path)

**Lower Half Starting Positions:**
- Examples: `lower wing`, `lower corner`, `lower midWing`, `lower midCorner`
- Can drive to: `lower lowPost`, `lower midPost`, `lower bird`, `midLane`, `basketSpot`
- Cannot drive to: upper-side spots (unrealistic path)

**Central Starting Positions:**
- Examples: `key`, `topLane`, `deep key`
- Can drive to: **All destinations** (both upper and lower)
- Makes sense since they're central and can go either direction

### Defensive Stops
- Players can be stopped short of ideal destination
- Results in intermediate spots (e.g., `upper midPost` instead of `basketSpot`)
- Penalty applies (see below)

---

## Attack Shot Penalty System

### No Penalty (Ideal Spots)
- `basketSpot` (x = 10 or 90 depending on basket)
- `upper lowPost`
- `lower lowPost`

### Penalty Applies (Stopped Short)
- `upper midPost`, `lower midPost`
- `upper bird`, `lower bird`
- `midLane`
- Any other intermediate spot

### Penalty Calculation
```python
penalty = abs(shot_location_x - basket_spot_x)
shot_score -= penalty
```

**Notes:**
- Basket spot X: Home team offense = x=10, Away team offense = x=90
- Penalty is raw X difference (not scaled)
- Applied before final shot threshold check

---

## Execution Flow

### Implementation Process (Actual Code Flow)

**Function:** `resolve_motion_offense_shot()` in `BackEnd/engine/phase_resolution.py`

1. **Select Random Step**
   - Randomly selects a step from the base_loop skeleton (excluding step 0)
   - Truncates skeleton at selected step

2. **Identify Ball Handler**
   - Finds ball handler at selected step (player with `handle_ball`, `receive`, or `pass` action)
   - Gets ball handler's location

3. **Check Shot Possibilities**
   - **Inside Shot**: Checks if ball handler is at inside location OR if teammates are at inside locations
   - **Attack Shot**: Checks if ball handler is at non-lane spot (can drive)
   - **Outside Shot**: Checks if ball handler or teammates are at outside locations

4. **Build Weighted List**
   - Uses `strategy_settings` weights (`inside`, `attack`, `outside`) to build weighted probability list
   - Special case: If ball handler is at inside location, no attack possible (weighted 4 inside, 2 outside)

5. **Select Shot Type**
   - Randomly selects from weighted list
   - Determines shot type: `inside`, `attack`, or `outside`

6. **Execute Shot**
   - **Inside**: Ball handler shoots OR passes to inside receiver then shoots
   - **Outside**: Ball handler shoots OR passes to outside receiver then shoots
   - **Attack**: Creates drive step to destination, then shoot step at destination
   - Appends necessary steps (pass/receive, drive, shoot) to truncated skeleton

7. **Apply Penalties**
   - For attack shots: Calculates penalty if stopped short of ideal destination
   - Penalty = `abs(shot_location_x - basket_spot_x)`

8. **Return Result**
   - Returns modified skeleton with shot steps appended
   - Returns shooter, shot type, playcall, and attack penalty

**Note:** The skeleton structure is a loop, but execution doesn't cycle through it. Instead, a random step is selected from the loop, and a shot is taken from that step. The loop structure ensures variety in shot opportunities across different steps.

---

## Database Structure

### Motion Play Documents

**Structure:**
```json
{
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,  // No default focus - set at runtime
  "skeletons": {
    "base_loop": {  // Single loop, no variants
      "steps": [
        {
          "step": 0,
          "timestamp": 0,
          "pos_actions": {...}
        },
        // ... more steps
        {
          "step": N,
          "loop_back_to": 0,  // Explicit loop marker
          "is_final_step": true
        }
      ]
    }
  },
  "game_stats": {...},
  "season_stats": {...}
}
```

**Key Requirements:**
- Final step must match first step OR have explicit `loop_back_to` marker
- All steps should have consistent player positioning
- Loop should be cohesive (smooth transition from final → first step)

### Plays to Build

1. **4-1 Motion** (currently exists, needs loop structure)
2. **3-2 Motion** (currently exists, needs loop structure)
3. **5-0 Motion** (currently exists, needs loop structure)
4. **4-1 Flex Motion** (currently exists, needs loop structure)

---

## Integration with Existing Systems

### Harmony with Set Plays

**Set Plays (Unchanged):**
- Continue using variant system (successful/contested/broken)
- Variant determines both skeleton AND shot modifier
- Works exactly as it does now

**Motion Plays (New):**
- Use base loop only (no variants)
- Location determines shot type
- Focus influences decisions
- No variant modifier applied

**Shared Systems:**
- Both use `generate_logic()` for result determination (SHOT vs non-SHOT)
- Both use `calculate_shot_score()` with playcall parameter
- Both use same shot threshold system
- Both use same defensive calculation logic

### `generate_logic()` Usage

**For Motion:**
- Determines result type: "SHOT", "O_FOUL", "D_FOUL", "DEAD_BALL_TURNOVER", "STEAL"
- Returns `lean_score` (not used for variant selection, but could be used for future enhancements)
- If result != "SHOT" → apply stopper system (truncate skeleton)

**For Set Plays:**
- Determines result type AND lean_score
- Lean_score selects skeleton variant
- Variant affects shot modifier

---

## Implementation Status

### ✅ Phase 1: Database Setup - COMPLETE
- ✅ Motion plays exist in database with `base_loop` skeleton structure
- ✅ Final step uses `is_final_step: true` and `loop_back_to: 0` marker
- ✅ Loop structure validated in Play Builder V2

### ✅ Phase 2: Engine Logic - COMPLETE
- ✅ Location-based shot type determination implemented (`_is_inside_location()`, `_is_outside_location()`, `_check_inside_shot_possibility()`, `_check_outside_shot_possibility()`)
- ✅ Drive destination logic implemented (`_determine_attack_drive_destination()` - upper/lower/central mapping)
- ✅ Attack shot penalty system implemented (`_apply_attack_penalty()`)
- ✅ Focus-based probability weighting implemented (`_build_shot_type_weighted_list()` using strategy_settings)
- ✅ Player attribute (IQ) override logic - Focus influences probability, player attributes affect shot calculations
- ✅ Loop continuation logic - Motion plays use base_loop skeleton, engine continues until turn-ending event

### ✅ Phase 3: Integration - COMPLETE
- ✅ `resolve_half_court_offense_logic()` detects Motion plays (`offense_play_type == "motion"`)
- ✅ Motion plays routed through `resolve_motion_offense_shot()` function
- ✅ Set Plays continue working unchanged (separate code paths)
- ✅ Motion plays functional in gameplay

### ⚠️ Phase 4: Testing - PARTIALLY COMPLETE
- ✅ Location-based shot type determination working
- ✅ Drive destinations working for all starting positions
- ✅ Attack shot penalties applied correctly
- ✅ Focus influence on decisions working (via strategy_settings weights)
- ⚠️ Loop continuation testing - May need additional validation for multiple cycles
- ⚠️ Player IQ override logic - May need additional testing/validation

---

## Implementation Files

**Backend (Implemented):**
- ✅ `BackEnd/engine/phase_resolution.py` - Motion execution logic
  - `resolve_motion_offense_shot()` (line 3093) - Main motion shot resolution
  - `_is_inside_location()`, `_is_outside_location()` - Location detection
  - `_check_inside_shot_possibility()`, `_check_outside_shot_possibility()`, `_check_attack_shot_possibility()` - Shot possibility checks
  - `_determine_attack_drive_destination()` - Drive destination logic
  - `_apply_attack_penalty()` - Attack penalty calculation
  - `_build_shot_type_weighted_list()` - Focus-based probability weighting
  - `_create_attack_drive_shoot_steps()`, `_create_shoot_step()`, `_create_pass_receive_step()` - Step creation helpers
- ✅ `BackEnd/models/turn_manager.py` - Playcall selection (handles Motion vs Set Play selection)
- ✅ `BackEnd/models/shot_manager.py` - Shot calculation (uses playcall parameter from motion system)

**Database:**
- ✅ `plays` collection - Motion plays stored with `play_type: "motion"` and `base_loop` skeleton structure

**Constants:**
- ✅ `BackEnd/constants/__init__.py` - `HCO_STRING_SPOTS` provides location-to-coordinate mapping
- ✅ Drive destination mapping implemented in `_determine_attack_drive_destination()`

---

## Implementation Details

### ✅ Resolved Questions

1. **Location X Coordinates**: ✅ **RESOLVED** - `HCO_STRING_SPOTS` constant provides location-to-coordinate mapping (used in `_find_closest_receiver()` and `_apply_attack_penalty()`)

2. **Penalty Application**: ✅ **RESOLVED** - Attack penalty is applied in motion-specific logic (`_apply_attack_penalty()`) before calling `calculate_shot_score()`. The penalty is subtracted from `shot_score` before the final threshold check.

3. **Focus Probability Weights**: ✅ **RESOLVED** - Uses `strategy_settings` weights (`inside`, `attack`, `outside`) from team settings. Default weights are 2 for each type. The weighted list is built by `_build_shot_type_weighted_list()` which multiplies each type by its weight value.

4. **IQ Override Logic**: ⚠️ **PARTIALLY IMPLEMENTED** - Player IQ is used in shot calculations (affects shot score), but there's no explicit "override" mechanism that allows high-IQ players to ignore focus preferences. Focus influence is purely probability-based via strategy_settings weights. This may be a future enhancement.

5. **Loop Detection**: ✅ **RESOLVED** - Uses explicit `is_final_step: true` and `loop_back_to: 0` marker in Play Builder V2. Motion plays use `base_loop` skeleton structure with explicit loop markers.

---

## Notes

- Motion plays are fundamentally different from Set Plays - embrace the difference
- Keep it simple: location determines shot type, focus influences decisions
- Player attributes matter - smart players make better reads
- No need for complex flag systems - location is the flag

