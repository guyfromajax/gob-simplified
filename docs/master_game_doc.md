# Master Game Documentation

> **Last Updated:** January 2025
> **Previously:** `animation_system.md`

This document provides comprehensive documentation of the **GOB** game system, including animation, transitions, game flows, and system architecture.

---

## Turn Data Structure: Three Data Buckets

Every turn result from the backend contains data organized into **three distinct buckets**:

### Bucket 1: Standard/Universal Fields ✅ **Always Present**

**Set by:** `turn_manager.py` (lines 423-650) - Added to ALL results after phase resolution

**Core Identification:**
- `result_type` - "MAKE", "MISS", "FOUL", "FREE_THROW", "HCO", "FAST_BREAK", etc.
- `offense_team_id` - Team on offense DURING this turn (SS&S single source of truth)
- `current_turn` - "HCO", "FCP", "HCT", "FAST_BREAK", "FREE_THROW", "OREB"
- `next_turn` - Next turn type (copied from `next_play_type`)
- `turn_count` - Micro turn counter

**Game State:**
- `score` - {home_team: X, away_team: Y} (authoritative)
- `time_elapsed` - Seconds elapsed in this turn
- `text` - Human-readable description for play-by-play
- `quarter` - Current quarter number

**Lineups & Stats:**
- `home_lineup` / `away_lineup` - Serialized lineup data
- `team_stats` - Scouting data (offense/defense ratings)
- `team_totals` - Cumulative team stats
- `deltas` - Player stat changes from this turn
- `player_energy` - Current NG (Nerve/Game) levels
- `team_plays` - Play effectiveness data

**Strategy:**
- `offensive_playcall` / `defensive_playcall` - Play names
- `offensive_play_type` / `defensive_play_type` - Play types
- `offense_tempo_call` / `defense_tempo_call` - Tempo settings
- `offense_aggression_call` / `defense_aggression_call` - Aggression settings
- `ev` - Expected value score

**Debug:**
- `debug_turn_start` - Debug string for turn start
- `debug_turn_result` - Debug string for turn result

**Purpose:** Provides core game state, routing information, and universal context needed by the frontend for every turn.

---

### Bucket 2: Bespoke/Turn-Specific Fields ⚠️ **Conditional**

**Set by:** Handlers (`shot_manager.py`, `phase_resolution.py`, `turn_manager.py`) - Added only when relevant

**Shot Results (MAKE/MISS):**
- `shooter`, `shooter_id`, `shooter_pos` - Shooter information
- `ball_handler`, `passer`, `screener`, `defender` - Participant names
- `points`, `scoring_team` - Scoring data (if made)
- `next_play_type` - "BASELINE_INBOUND", "HCO", "FAST_BREAK", "FREE_THROW", etc.
- `next_defensive_setup` - "FCP", "HCT", "HCO", None
- `free_throws_remaining`, `has_and_one` - Free throw data (if foul)
- `intended_shooter_pos`, `intended_shooter_id` - For audible/hot read popup
- `foul_player_id`, `foul_team` - Foul information (if shooting foul)
- `is_three_pointer`, `is_and_one` - Shot context flags

**Free Throw Results:**
- `shooter`, `shooter_id`, `shooter_pos` - Shooter information
- `points`, `scoring_team` - Scoring data (if made)
- `free_throws_remaining` - Remaining attempts
- `one_and_one`, `no_lane` - Free throw context
- `attempts` - ["MAKE", "MISS"] array
- `rebounder_id`, `rebound_type` - Rebound data (if missed)

**Foul Results:**
- `ball_handler`, `defender` - Participant names
- `foul_player_id`, `foul_team`, `foul_count` - Foul information
- `fouled_out`, `foul_out_player` - Foul out data (if applicable)
- `fcp_foul`, `hct_foul` - Pressure foul flags

**Turnover Results:**
- `ball_handler`, `victim_id`, `victim_name` - Turnover victim
- `stealer_id`, `stealer_name`, `defender_id` - Steal information (if STEAL)

**Fast Break Results:**
- `fast_break` - true flag
- `roles` - {outlet_passer, outlet_receiver} - Fast break roles

**FCP/HCT Results:**
- `fcp_foul` / `hct_foul` - Pressure foul flags
- `fcp_shot` / `hct_shot` - Pressure shot flags
- `skeleton` - Skeleton data for press break sequences
- `roles` - Player roles for pressure sequences

**Inbound Pass Results:**
- `oDestinations` / `dDestinations` - Offensive/defensive player positions
- `ball_spot` - Inbound spot coordinates
- `offense_setup_positions` - FCP/HCT skeleton step 0 positions

**OREB Results:**
- `rebounder_id` - Player who secured rebound
- `rebound_type` - "OREB"
- Putback/kickout data (varies by outcome)

**Purpose:** Provides turn-specific data needed for animations, announcements, and UI updates. Only present when relevant to the turn type.

---

### Bucket 3: Animation Data ✅ **Always Present (but may be empty)**

**Set by:** `Animator` class (`animator.py`) - Created in `turn_manager.py` (lines 512-522)

**Always Included:**
- `animations[]` - Array of per-player movement tracks
  - Each animation contains:
    - `playerId` - Player identifier
    - `movement[]` - Array of movement steps
      - Each step: `coords` (x, y), `action`, `timestamp`, `has_ball`
  - May be empty array `[]` if no animation (e.g., some free throws, turnovers)

**Conditional:**
- `events[]` - High-level events array
  - Event types: `PUTBACK_ATTEMPT`, `KICKOUT_RESET`, `STEAL`, `FAST_BREAK_START`, etc.
  - Only present when relevant events occur
- `roles{}` - Player roles dictionary
  - Keys: `ball_handler`, `rebounder`, `outlet_receiver`, `outlet_passer`, `shooter`, etc.
  - Only present when roles are assigned

**Purpose:** Provides all data needed to animate the turn visually. The `animations[]` array is always present (even if empty), while `events[]` and `roles{}` are conditional.

---

### Data Flow Pattern

```
1. Handler (shot_manager.py, phase_resolution.py, etc.)
   ↓ Creates result dict with Bucket 2 (bespoke fields)
   
2. turn_manager.py::run_micro_turn()
   ↓ Adds Bucket 1 (standard fields) to result
   ↓ Calls Animator to create Bucket 3 (animation data)
   
3. Result serialized to JSON
   ↓ Sent to frontend
   
4. Frontend receives complete turn data
   ↓ Uses all three buckets for routing, animation, and UI updates
```

---

### Key Design Principles

1. **Bucket 1 (Standard):** Single source of truth for game state, routing, and universal context
2. **Bucket 2 (Bespoke):** Handler-specific data - only present when relevant
3. **Bucket 3 (Animation):** Always present structure, but contents vary by turn type

**Benefits:**
- ✅ Clear separation of concerns (universal vs. turn-specific vs. animation)
- ✅ Frontend can always rely on Bucket 1 being present
- ✅ Handlers only add what they need (no bloated data)
- ✅ Animation data structure is consistent (even if empty)

**See:**
- `BackEnd/models/turn_manager.py` - Standard fields (Bucket 1)
- `BackEnd/models/shot_manager.py` - Shot-specific fields (Bucket 2)
- `BackEnd/engine/phase_resolution.py` - FCP/HCT/Free Throw fields (Bucket 2)
- `BackEnd/models/animator.py` - Animation data creation (Bucket 3)
- `docs/turn_data_structure.md` - Detailed field reference
- `docs/UNIFIED_DATA_STRUCTURE_ANALYSIS.md` - Analysis of data structure patterns

---

## SS&S Core Systems (December 2024)

### Possession Management System ✅ **SS&S**

**Single Source of Truth:** Each turn's `offense_team_id` field

**Backend Responsibility:**
- Sets `result["offense_team_id"] = game.offense_team.team_id` (team on offense DURING this turn)
- Uses `possession_flips` as INTERNAL flag (tells backend when to call `switch_possession()`)
- After turn completes, calls `game.switch_possession()` if `possession_flips=True`
- Next turn automatically has correct `game.offense_team` (updated state)

**Frontend Responsibility:**
- Reads `turnData.offense_team_id` from each turn
- Sets `scene.offenseTeamId = turnData.offense_team_id` (simple assignment, no flip logic)
- Emits `possessionChange` event if value changes

**Benefits:**
- ✅ No double flips (backend flips once, frontend just displays)
- ✅ No confusion (one value, one source)
- ✅ Works for ALL turn types (HCO, FCP, HCT, FREE_THROW, etc.)

**See:** `turnPreparation.js` - `handleTurnTransition()` function

---

### Announcement System ✅ **SS&S**

**Timing-Based Separation:**

**timing='start'** - Context announcements (situation being entered):
- "Press!" - FCP pressure applied (BASELINE_INBOUND with `next_defensive_setup='FCP'`)
- "Trap!" - HCT pressure applied (BASELINE_INBOUND with `next_defensive_setup='HCT'`)
- "Fast Break!" - Fast break initiated

**timing='end'** - Result announcements (outcome of turn):
- "It's Good!" - Made shot (ballManager.js, when ball reaches rim)
- "STEAL!" - Steal occurred
- "TRAVEL!" / "OUT OF BOUNDS!" / etc. - Turnover types
- "OFFENSIVE FOUL!" / "DEFENSIVE FOUL!" - Foul types
- "Rebound!" - Defensive rebound (ballManager.js, when ball reaches rebounder)

**Idempotent Design:**
- `prepareTurnForAnimation()` may be called multiple times (animateGameTurns + AnimationRouter)
- Uses `turn._startAnnouncementsShown` and `turn._endAnnouncementsShown` flags
- First call: Shows announcements, sets flag
- Subsequent calls: Skips announcements (already shown)

**Benefits:**
- ✅ No duplicate announcements (flags prevent)
- ✅ Clear separation (context at start, result at end)
- ✅ Works across all turn types

**See:** `turnPreparation.js` - `prepareTurnForAnimation()` and `finalizeTurnAfterAnimation()`  
**See:** `announcements.js` - `announceFromTurnData()` function

---

## FCP/HCT System ✅ **COMPLETE** (January 2025)

### Overview

The **Full Court Press (FCP)** and **Half Court Trap (HCT)** system handles defensive pressure situations that occur after made shots. Both systems use skeleton-based animations to simulate press break sequences and can result in various outcomes: turnovers, fouls, press breaks, or shot attempts.

**Key Functions:**
- `resolve_full_court_press_logic()` - Handles FCP outcomes in `BackEnd/engine/phase_resolution.py`
- `resolve_half_court_trap_logic()` - Handles HCT outcomes in `BackEnd/engine/phase_resolution.py`
- `get_ball_handler_from_skeleton()` - Determines ball handler dynamically from skeleton steps

### When FCP/HCT Activates

**Trigger Conditions:**
- After made shots when defense applies full court press or half court trap
- Set via `offensive_state = "FCP"` or `offensive_state = "HCT"` in `game_state`
- Determined by `turn_manager.determine_defensive_pressure_type()` in `shot_manager.py`

**State Flow:**
1. Made shot → Sets `offensive_state` based on defensive pressure type
2. BASELINE_INBOUND turn generated (if applicable)
3. Next API call routes to FCP/HCT handler based on `offensive_state`
4. Handler generates outcome turn (FOUL/TURNOVER/HCO/SHOT)

### Possible Outcomes

Both FCP and HCT can result in:

1. **Offensive Foul (O_FOUL)**
   - Possession change
   - Routes to: Side Inbound Pass → HCO
   - Foul player: Determined dynamically from ball handler (60% ball handler, 10% each other player)

2. **Defensive Foul (D_FOUL)**
   - **In Bonus (5-9 fouls)**: Routes to FREE_THROW (1 & 1)
   - **In Double Bonus (10+ fouls)**: Routes to FREE_THROW (2 shots)
   - **Not in Bonus (<5 fouls)**: Routes to Side Inbound Pass → HCO
   - Foul player: Determined dynamically from defender guarding ball handler

3. **Steal (STEAL)**
   - Possession change
   - Routes to: HCO or FAST_BREAK (based on fast break chance)
   - Stealer: Defender guarding ball handler (position-matched)
   - Victim: Ball handler (determined from skeleton)

4. **Dead Ball Turnover (DEAD_BALL_TURNOVER)**
   - Possession change
   - Routes to: Side Inbound Pass → HCO
   - Turnover player: Ball handler (determined from skeleton)

5. **Press/Trap Break (HCO)**
   - Successful press break
   - Routes to: HCO (half court offense)
   - No possession change

6. **Press/Trap Break Shot (SHOT)**
   - Shot attempt during press break
   - Routes to: Standard shot resolution flow
   - Uses FCP/HCT-specific skeleton for animation

### Dynamic Player Assignment System ✅ **NEW** (January 2025)

**Previous Behavior:**
- Ball handler was hardcoded to PG (or first player in lineup)
- Defender was hardcoded to defensive PG
- All events (fouls, steals, turnovers) assigned to these hardcoded players

**Current Behavior:**
- **Ball Handler**: Determined dynamically from skeleton steps
  - Checks skeleton steps for actions: `"handle_ball"`, `"receive"`, `"shoot"`
  - Defaults to last step (where event occurs)
  - Falls back to PG if no ball handler found in skeleton
- **Defender**: Position-matched to ball handler
  - Uses same position as ball handler (e.g., if ball handler is SG, defender is defensive SG)
  - Falls back to defensive PG if position not found
- **All Events**: Use dynamic players
  - Offensive foul: Uses dynamic ball handler
  - Defensive foul: Uses dynamic ball handler and defender
  - Steal: Uses dynamic ball handler (victim) and defender (stealer)
  - Dead ball turnover: Uses dynamic ball handler

**Implementation:**

```python
def get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=None):
    """
    Determine the ball handler from skeleton steps.
    
    Args:
        skeleton: Skeleton dict with "steps" key
        off_lineup: Dictionary of offensive players by position
        step_index: Optional step index to check (defaults to last step if None)
    
    Returns:
        Player object who has the ball, or PG (or first player) as fallback
    """
    # Check skeleton steps for ball possession actions
    # Actions that indicate ball possession: "handle_ball", "receive", "shoot"
    # Defaults to last step (where event likely occurs)
    # Falls back to PG if no ball handler found
```

**Benefits:**
- ✅ More accurate player assignments based on actual game flow
- ✅ Removes hardcoded PG assumption
- ✅ Better stat tracking (correct players get credited)
- ✅ More realistic game simulation

### Skeleton System

**Skeleton Sources:**
- FCP skeletons: `BackEnd/playcall_skeletons/fcp_skeletons.py`
- HCT skeletons: `BackEnd/playcall_skeletons/hct_skeletons.py`
- Skeleton variants: Different skeletons for different outcomes (FOUL, STEAL, HCO, SHOT)

**Skeleton Structure:**
- Each skeleton contains `steps` array
- Each step has `pos_actions` dict mapping positions to actions
- Actions include: `"handle_ball"`, `"receive"`, `"pass"`, `"shoot"`, `"screen"`, etc.
- Ball handler determined by checking for ball possession actions in steps

**Animation Generation:**
- Skeletons converted to animations via `animator.skeleton_to_animations()`
- Animations include player movements, ball movements, and defender positioning
- Frontend uses skeleton data to animate press break sequences

### Key Files

- `BackEnd/engine/phase_resolution.py`
  - `resolve_full_court_press_logic()` - FCP outcome resolution
  - `resolve_half_court_trap_logic()` - HCT outcome resolution
  - `get_ball_handler_from_skeleton()` - Dynamic ball handler determination
  - `select_foul_player()` - Probabilistic foul player selection
- `BackEnd/playcall_skeletons/fcp_skeletons.py` - FCP skeleton definitions
- `BackEnd/playcall_skeletons/hct_skeletons.py` - HCT skeleton definitions
- `BackEnd/models/animator.py` - Skeleton to animation conversion
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - FCP/HCT detection and state tracking

### Future Enhancements

- **More Nuanced Defender Assignment**: Currently uses position matching. Future: Determine defender based on actual defensive assignments (zone/man coverage)
- **Enhanced Ball Handler Detection**: Improve detection logic for edge cases where ball handler isn't clear from skeleton
- **Skeleton Variants**: Add more skeleton variants for different press break scenarios

---

## Fast Break System ✅ **COMPLETE** (January 2025)

### Overview

The **Fast Break** system handles transition offense situations that occur after defensive rebounds or steals. The system determines whether a fast break results in a defensive stop or a shot attempt based on defender positioning relative to the ball handler after the outlet pass.

**Key Functions:**
- `FastBreakTrigger.can_trigger_from_dreb()` - Determines if fast break should trigger from DREB in `BackEnd/engine/fast_break_trigger.py`
- `resolve_fast_break_logic()` - Handles fast break outcome determination in `BackEnd/engine/phase_resolution.py`
- `capture_fast_break_animation()` - Builds animation packet in `BackEnd/models/animator.py`
- `runFastBreakSequence()` - Orchestrates fast break animation in `FrontEnd/static/js/phaser/animation/fastBreak.js`

### When Fast Break Activates

**Trigger Conditions:**
- After defensive rebounds when `defense_releases = True` (defensive players release for fast break)
- After steals with fast break chance
- Set via `next_play_type = "FAST_BREAK"` in turn result
- Determined by `FastBreakTrigger.can_trigger_from_dreb()` for DREB or `FastBreakTrigger.can_trigger_from_steal()` for steals (in `BackEnd/engine/fast_break_trigger.py`)

**State Flow:**
1. DREB or STEAL → Fast break chance determined
2. FAST_BREAK turn generated with `fast_break = true` flag
3. Backend determines outcome (DEFENSIVE_STOP or SHOT) based on defender positioning
4. Frontend animates outlet pass, then defensive stop or shot attempt

### Possible Outcomes

Fast breaks can result in:

1. **Defensive Stop (DEFENSIVE_STOP)**
   - Defender is ahead of ball handler after outlet pass
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Closest defender ahead becomes "stopper" and is placed 1-3 spots in front of ball handler
   - Routes to: HCO (half court offense)

2. **Shot Attempt (SHOT)**
   - No defender ahead of ball handler after outlet pass
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Defender follows and is positioned 1-6 spots behind ball handler
   - Routes to: Standard shot resolution flow (MAKE/MISS)

### Coordinate System and Player Positioning

**Coordinate Orientation:**
- All coordinates stored in **HOME orientation** (basket at x=90 for home, x=10 for away)
- Frontend flips coordinates for away team display
- Backend calculations always use HOME orientation for consistency

**Outlet Receiver (Ball Handler) Starting Coordinates:**
- **Priority 1**: `defense_release_coords` from most recent MISS/MAKE turn (outlet receiver is typically a release player)
- **Priority 2**: `offense_getback_coords` from most recent MISS/MAKE turn (if ball handler was a get-back player)
- **Fallback**: `player.coords` (current position on court)

**Get-Back Defender Coordinates:**
- **Priority**: `offense_getback_coords` from **most recent** MISS/MAKE turn only
- Only defenders who were actually get-back players in the turn that triggered the fast break
- **Fallback**: `defender.coords` (current position on court)

**Example from Logs:**
```
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=34 (from offense_getback_coords)
Y Difference: |34 - 23| = 11 (exceeds ±6 range)
Result: SHOT (defender is ahead in x but NOT within y-range)
Note: Even though defender at x=57 is ahead of ball handler at x=55, they are 11 y-coords 
away, which exceeds the ±6 requirement, so it becomes a shot attempt instead of defensive stop.

Another Example:
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=25 (from offense_getback_coords)
Y Difference: |25 - 23| = 2 (within ±6 range)
Result: DEFENSIVE_STOP (defender at x=57 is ahead AND within y-range, distance: 2)
```

### Defensive Stop vs. Shot Attempt Determination

**Logic (HOME Orientation):**

**Home Offense:**
- Basket at x=90 (larger x is closer to basket)
- Defender ahead if: `defender_x >= ball_handler_x`
- **Defender must also be within ±6 y-coords of outlet receiver**
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Away Offense:**
- Basket at x=10 (smaller x is closer to basket)
- Defender ahead if: `defender_x <= ball_handler_x`
- **Defender must also be within ±6 y-coords of outlet receiver**
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Multiple Get-Back Players:**
- If multiple get-back players meet both conditions (ahead AND within y-range), the closest one (by x-distance) forces the defensive stop
- If neither get-back player meets both conditions, the closest defender overall (by Euclidean distance) becomes the shot defender

**Shot Defender Selection:**
- If no defender meets both conditions (ahead AND within y-range), it's a shot attempt
- The closest defender overall (by Euclidean distance from outlet receiver) becomes the shot defender
- This ensures there's always a defender to animate during shot attempts

**Critical Implementation Detail - Defender Assignment Consistency:**
- **Backend Calculation**: In `phase_resolution.py`, `fb_roles["defender"]` is set to `closest_defender_overall` for shot attempts (line 730)
- **Shot Resolution**: `resolve_fast_break_shot()` in `shot_manager.py` now **respects** the already-set `fb_roles["defender"]` instead of randomly reassigning it
- **Why This Matters**: The defender used in shot resolution must match the defender used in animation to prevent animation freezes or mismatches
- **Implementation**: `resolve_fast_break_shot()` checks if `fb_roles["defender"]` is already set; if so, uses it. Only falls back to random assignment if not set (for edge cases)

**Critical Implementation Detail:**
- **All defenders checked**: The system checks **all defenders in `def_lineup`**, not just those initially in `fb_roles["defense"]`
- **Why**: `get_in_play_defenders()` (called earlier) uses stale `ball_handler.coords` to filter defenders, which might exclude get-back players who are actually ahead of the outlet receiver position
- **Fix**: Loop through all defenders when comparing against outlet receiver position (`ball_handler_outlet_x/y`)
- **Result**: Get-back players who are ahead are correctly detected, even if they weren't initially included in `fb_roles["defense"]`
- **Animation**: If an ahead defender wasn't in the initial list, they're added to `fb_roles["defense"]` for animation purposes

**Implementation:**
```python
# ✅ Check ALL defenders in def_lineup, not just fb_roles["defense"]
# This ensures get-back players are checked even if they weren't initially included
closest_stopping_defender = None  # Defender who is ahead AND within ±6 y-coords
closest_defender_overall = None   # Closest defender overall (for shot attempts)

for defender in def_lineup.values():
    # Get defender coordinates (get-back coords if available, else defender.coords)
    defender_outlet_x = get_defender_coords_x(defender, most_recent_shot_turn)
    defender_outlet_y = get_defender_coords_y(defender, most_recent_shot_turn)
    
    # Calculate Euclidean distance for closest defender overall
    x_distance = abs(defender_outlet_x - ball_handler_outlet_x)
    y_distance = abs(defender_outlet_y - ball_handler_outlet_y)
    total_distance = (x_distance ** 2 + y_distance ** 2) ** 0.5
    
    # Track closest defender overall (for shot attempts)
    if total_distance < closest_distance_overall:
        closest_distance_overall = total_distance
        closest_defender_overall = defender
    
    # Check if defender is ahead (x-coordinate check)
    if is_away_offense:
        is_ahead = defender_outlet_x <= ball_handler_outlet_x
    else:
        is_ahead = defender_outlet_x >= ball_handler_outlet_x
    
    # ✅ NEW: Check if defender is within ±6 y-coords of outlet receiver
    y_diff = abs(defender_outlet_y - ball_handler_outlet_y)
    is_within_y_range = y_diff <= 6
    
    # Defender can force defensive stop if: ahead AND within y-range
    if is_ahead and is_within_y_range:
        defender_ahead = True
        # Track closest stopping defender (x-distance only)
        x_distance_only = abs(defender_outlet_x - ball_handler_outlet_x)
        if x_distance_only < closest_stopping_distance:
            closest_stopping_distance = x_distance_only
            closest_stopping_defender = defender

# If closest stopping defender wasn't in fb_roles["defense"], add them for animation
if closest_stopping_defender and closest_stopping_defender not in fb_roles["defense"]:
    fb_roles["defense"].append(closest_stopping_defender)

if defender_ahead and closest_stopping_defender:
    event_type = "DEFENSIVE_STOP"
    stopper_id = closest_stopping_defender.player_id
else:
    event_type = "SHOT"
    # Use closest defender overall as shot defender
    if closest_defender_overall:
        fb_roles["defender"] = closest_defender_overall
```

### Animation Sequence

**Phase 1: Outlet Pass**
- Outlet passer (rebounder) stays at rebound spot
- Outlet receiver (ball handler) receives pass at current position (no movement)
- Defenders stay at current position (no movement)
- Rebounders (non-get-back, non-release) stay at current position (no movement)

**Phase 2: Defensive Stop or Shot Attempt**

**Defensive Stop:**
- Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
- Stopper (closest defender ahead) moves to position 1-3 spots in front of ball handler
- Get-back defenders chase toward basket
- Rebounders move to random x=40-60, y=starting_y ± 6 (clamped)
- **Early Termination**: Rebounder animations stop when ball handler and stopper both reach their spots

**Shot Attempt:**
- Ball handler (shooter) moves to spot near rim (basket ± 2-6, ±6 Y)
- Defender follows to position 1-6 spots behind shooter
- Get-back defenders chase toward basket
- Rebounders move to random x=5-20 spots from basket, y=rim_y ± 10 (clamped)
- **Early Termination**: 
  - Made shot: Rebounder animations stop when ball hits rim
  - Missed shot: Rebounder animations stop when rebounder grabs ball

### Fast Break MISS → DREB Transition

**Flow:**
1. Fast Break shot attempt results in MISS
2. Defensive rebound occurs (DREB)
3. Transition to HCO (half court offense) via `runDefensiveReboundSetup()`

**Critical Implementation Detail - turnData Handling:**
- **Current Fast Break MISS turn** must be passed as `turnData` to `runDefensiveReboundSetup()`
- **Why**: `runDefensiveReboundSetup()` uses `turnData.animations` to detect pass actions for the outlet pass animation
- **offense_getback lookup**: If current turn doesn't have `offense_getback`, `runDefensiveReboundSetup()` automatically looks up the previous HCO MISS turn (the one that triggered the Fast Break)
- **Why this matters**: The previous HCO MISS turn has the `offense_getback` list needed for get-back player positioning, but the current Fast Break MISS turn has the correct animation data

**Implementation:**
```javascript
// In fastBreak.js - animateFastBreakShot()
// Pass current Fast Break MISS turnData (has animations)
await runDefensiveReboundSetup({
  scene,
  ballSprite,
  playerSprites,
  rebounderId,
  nextPlayType: turnData.next_play_type || "HCO",
  turnData: turnData // ✅ Current Fast Break MISS turn (for animations)
  // runDefensiveReboundSetup will find offense_getback from previous turn if needed
});
```

```javascript
// In turnAnimation.js - runDefensiveReboundSetup()
// Lookup offense_getback from previous turn if current turn doesn't have it
let missTurnForGetback = turnData;
if (!missTurnForGetback || !missTurnForGetback.offense_getback) {
  // Try previous turn if current turn doesn't have offense_getback (Fast Break case)
  const previousTurn = scene.simData?.turns?.[currentIndex - 1];
  if (previousTurn?.result_type === "MISS" && previousTurn.offense_getback) {
    missTurnForGetback = previousTurn;
  }
}
const getBackList = missTurnForGetback?.offense_getback || [];
```

**Why This Fix Was Critical:**
- **Previous Bug**: Passing the previous HCO MISS turn caused `runDefensiveReboundSetup()` to look for pass animations in the wrong turn data
- **Result**: Animation freeze when trying to execute outlet pass after Fast Break MISS → DREB
- **Fix**: Pass current Fast Break MISS turn (correct animations) while still allowing lookup of `offense_getback` from previous turn

### Key Files

- `BackEnd/engine/fast_break_trigger.py`
  - `FastBreakTrigger` - Class for determining fast break triggers
  - `can_trigger_from_dreb()` - Determines if fast break should trigger from defensive rebound
  - `can_trigger_from_steal()` - Determines if fast break should trigger from steal (for future use)
- `BackEnd/engine/phase_resolution.py`
  - `resolve_fast_break_logic()` - Determines defensive stop vs. shot attempt
  - Uses coordinate comparison in HOME orientation
  - Stores `ball_handler_outlet_x/y`, `is_away_offense`, `getback_player_ids` in `fb_roles`
- `BackEnd/models/shot_manager.py`
  - `_calculate_getback_coordinates()` - Calculates get-back player coordinates
  - `_calculate_release_coordinates()` - Calculates release player coordinates
  - Stores `offense_getback_coords` and `defense_release_coords` in turn results
- `BackEnd/models/animator.py`
  - `capture_fast_break_animation()` - Builds animation packet
  - Uses `fb_roles` for ball handler outlet position and `is_away_offense`
  - Handles coordinate flipping for away team display
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - `runFastBreakSequence()` - Orchestrates fast break animation
  - `animateOutletPhase()` - Handles outlet pass (no player movement)
  - `animateDefensiveStop()` - Handles defensive stop animation
  - `animateFastBreakShot()` - Handles shot attempt animation and MISS → DREB transition
  - `moveOtherPlayersToStandardPositions()` - Positions outlet passer and get-back defenders
  - `animateRebounders()` - Handles rebounder animation (extracted for maintainability)
    - Defensive Stop: x=40-60, y=starting_y ± 6 (clamped 1-49)
    - Shot Attempt: x=random 5-20 spots out from basket, y=rim_y ± 10 (clamped 1-49)
    - Returns tween references for early termination
  - Early termination logic for rebounder animations
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
  - `runDefensiveReboundSetup()` - Handles DREB → HCO transition, including Fast Break MISS → DREB cases
  - Automatically looks up `offense_getback` from previous turn if current turn doesn't have it (Fast Break case)

### Future Enhancements

- **Steal → Fast Break**: Currently focuses on DREB → Fast Break. Enhance steal → fast break flow
- **More Nuanced Get-Back Logic**: Consider player attributes (speed, IQ) for get-back player selection
- **Fast Break Fouls**: Add foul handling during fast break sequences
- **Fast Break Turnovers**: Add turnover handling during fast break sequences

---

## Production Animation System

### Ball Animation System ✅ **COMPLETE**

**Status:** Fully refactored and operational (December 2024)

The ball animation system uses a unified architecture with **BallController** as the single source of truth for ball ownership and state. This system integrates with the WIP_GOB approach for player movement synchronization.

**Architecture:**
- **BallController** (`BallController.js`) - Single source of truth for ball state
  - Manages ball ownership, attachment/detachment, and flight state
  - Lifecycle methods: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`
  - Internal state: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
  
- **BallControllerAdapter** (`BallControllerAdapter.js`) - Backward compatibility layer
  - Provides `attachBallToPlayer()` function with old signature
  - Handles state synchronization with WIP_GOB system
  
- **WIP_GOB Integration** (`ballAnimationSimple.js`)
  - **Ball Holder State:** `scene.gameState.ballHolder` (string ID) - synchronized with BallController
- **Conditional Targets:** `getPlayerTweenTargets()` - includes ball in player tween when player has ball
- **Simple Movement:** `animateBallToPosition()`, `animateShotToRim()` - distance-based duration, arc support

**Key Files:**
- `BallController.js` - Core state management
- `BallControllerAdapter.js` - Compatibility layer
- `ballAnimationSimple.js` - WIP_GOB integration
- `ballTween.js` - Pass animations (uses BallControllerAdapter)
- `ballManager.js` - Shot animations (uses BallControllerAdapter)
- `freeThrow.js`, `fastBreak.js` - Special animations (use BallControllerAdapter)

**Benefits:**
- ✅ Single source of truth (BallController)
- ✅ No ownership conflicts
- ✅ No ball teleports (Phaser handles sync automatically)
- ✅ Lifecycle methods for clean state management
- ✅ Better performance (no update callbacks)
- ✅ Easier debugging (one place to check state)
- ✅ Full WIP_GOB integration for player movement

**See:** 
- `Historical/BALL_ANIMATION_SYSTEM_REFACTORING_PLAN.md` - Complete refactoring details (December 2024)
- `Historical/BALL_ANIMATION_MIGRATION_PLAN.md` - WIP_GOB migration details (earlier work)
- `BALL_OWNERSHIP_CONSOLIDATION_PLAN.md` - Ball ownership system consolidation (December 2024)

---

### Ball Ownership Consolidation ✅ **COMPLETE** (December 2024)

**Summary**: Successfully consolidated three competing ball ownership systems into a single, unified architecture.

**What Was Consolidated**:
1. **Old `ballController.js`** (WeakMap-based system) - ❌ **Removed**
2. **BallController** (Class-based system) - ✅ **Now single source of truth**
3. **ballAnimationSimple.js** (WIP_GOB system) - ✅ **Delegates to BallController**

**What Was Accomplished**:
- ✅ Extended BallController API with all compatibility methods
- ✅ Created unified adapter layer (`BallControllerAdapter`) for backward compatibility
- ✅ Migrated all 8 animation files to use adapter
- ✅ Consolidated 3 different `updateBallOwnership` implementations into one unified function
- ✅ Removed old `ball/ballController.js` file (no longer needed)
- ✅ Reduced code duplication by ~200+ lines
- ✅ Eliminated state synchronization issues

**Result**: 
- **Single source of truth**: `BallController` only
- **Simpler**: One system instead of three
- **More stable**: No state conflicts
- **More scalable**: Easier to extend and maintain
- **Better performance**: Reduced logging overhead

**For Details**: See `BALL_OWNERSHIP_CONSOLIDATION_PLAN.md` for complete migration plan and implementation details.

---

### Defender Coordinate System ✅ **COMPLETE** (December 2024)

**Status:** Fully refactored and operational

The defender coordinate system uses a unified architecture with **`get_defender_coords()`** as the single entry point for all defender positioning (ball handler defenders, non-ball handler defenders, and zone defenders).

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

**See:** 
- `DEFENDER_COORDINATE_SYSTEM_REFACTORING_PLAN.md` - Complete refactoring details (December 2024)

---

### Zone Defender Placement System ✅ **COMPLETE** (January 2025)

**Status:** Fully implemented with overlap resolution and multi-defender offset logic

The zone defender placement system assigns defensive coordinates for all zone defenders, handling zone overlaps, multi-defender situations, and prioritizing zone coverage when the ball handler is double-teamed.

**Architecture:**

#### Core Function: `assign_all_zone_defenders()`

**Location:** `BackEnd/utils/shared_defense.py` (lines 794-1086)

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

**Location:** `BackEnd/utils/shared_defense.py` (lines 1089-1165)

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
4. **Animation:** `animator.py` (line 1442) flips defender coordinates to away orientation to match offensive coordinates

**Critical Fix - Fallback Path Coordinate Conversion:**

**Bug:** The fallback path (lines 1046-1076) that assigns the closest defender to guard the ball handler was missing the HOME orientation conversion, causing a double-flip:
- `get_defender_coords()` returned coords in away orientation
- Fallback path assigned directly (still in away orientation)
- `animator.py` flipped again → defender appeared on wrong end of court

**Fix:** Added HOME orientation conversion in fallback path (lines 1072-1075):
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
- Both normal path (lines 881-882) and fallback path (lines 1072-1075) now follow this pattern

**Key Files:**
- `BackEnd/utils/shared_defense.py` - Core zone defense logic
- `BackEnd/constants.py` - Zone definitions (`ZONE_23_NORMAL`, `ZONE_32_NORMAL`, etc.)
- `BackEnd/models/animator.py` - Coordinate flipping for animation (line 1442)
- `tests/test_zone_defense_lower_corner_away_offense.py` - Validation test

---

### Unified Pass System ✅ **COMPLETE** (January 2025)

**Status:** Fully unified and operational

All pass animations now use a single, centralized system (`passDetection.js`) that provides consistent behavior across all pass types and turn scenarios.

**Architecture:**
- **`passDetection.js`** - Centralized pass detection and handling utility
  - `detectPassAtStep()` - Detects passes from animation data by looking for `action: "pass"` and `action: "receive"` at the same step
  - `handlePassAnimation()` - Executes pass animation using `runPass()` with distance-based duration calculation
  - Sets `scene.passInFlight = true` to prevent `updateBallOwnership` from interfering
  
**Pass Types Unified:**
1. **HCO Passes** - Passes within half-court offense turn animations
   - Used by: `playTurnAnimation()`, `ShotAnimationSystem.animatePlayerMovement()`
   - Detects passes from turn animation data automatically
   
2. **Fast Break Outlet Passes** - Outlet passes during fast break sequences
   - Used by: `fastBreak.js` (via `passDetection.js`)
   - Distance-based duration for smooth animation
   
3. **Side Inbound Passes** (SIDE_INBOUND)
   - Used by: `runSideInboundSetup()`
   - Checks `turnData.animations` for pass actions, falls back to hardcoded SF→PG if not found
   
4. **Baseline Inbound Passes** (BASELINE_INBOUND)
   - Used by: `runInboundSetup()`
   - Checks `turnData.animations` for pass actions, falls back to hardcoded SF→PG if not found
   
5. **Opening Tip → PG Pass**
   - Used by: `openingTip.js`
   - Automatically finds PG for tip winner's team and executes pass
   - Uses synthetic `passInfo` since opening tip doesn't have animation data with pass actions
   
6. **DREB Outlet Passes** (Defensive Rebound → HCO)
   - Used by: `runDefensiveReboundSetup()`
   - Checks `turnData.animations` for pass actions, creates synthetic `passInfo` if not found
   - Maintains backward compatibility with existing outlet pass logic

**Key Features:**
- ✅ Single source of truth for all pass animations
- ✅ Consistent behavior across all pass types
- ✅ Automatic pass detection from animation data
- ✅ Fallback to hardcoded passes when animation data doesn't have pass actions
- ✅ Distance-based duration calculation (300-800ms based on distance)
- ✅ Prevents `updateBallOwnership` from teleporting ball during/after passes
- ✅ Future-proof: When backend adds pass actions to animation data, passes work automatically

**Benefits:**
- ✅ **Consistency**: All passes animate the same way
- ✅ **Maintainability**: Fix bugs or improve pass animation in one place
- ✅ **Scalability**: Easy to add new pass types without duplicating code
- ✅ **Future-proof**: Ready for dynamic inbound passes (when backend provides pass actions)
- ✅ **Backward compatible**: Works with current hardcoded passes and future data-driven passes

**Implementation Details:**
- Pass detection looks for `action: "pass"` in one player's movement step
- Finds corresponding `action: "receive"` in another player's movement at the same step
- Calculates pass duration: `Math.max(300, Math.min(800, (distance / 350) * 1000))`
- Uses `runPass()` from `ballTween.js` for actual animation
- Sets `scene.passInFlight = true` to prevent ball ownership updates during pass

**Key Files:**
- `passDetection.js` - Core pass detection and handling
- `turnAnimation.js` - Uses pass detection in step loop and inbound setups
- `ShotAnimationSystem.js` - Uses pass detection in player movement animation
- `openingTip.js` - Uses pass detection for tip winner → PG pass
- `ballTween.js` - `runPass()` function (used by all passes)

**See:**
- `FrontEnd/static/js/phaser/animation/passDetection.js` - Complete implementation

---

### State Tracking System ✅ **CORE COMPONENT** (January 2025)

**Status:** Fundamental architectural pattern - used throughout animation system

State tracking is a **core component** of the animation system, following the SS&S principle of single source of truth. This pattern ensures reliable state management across turns and operations.

**Core Principles:**

1. **Single Source of Truth**: One place tracks state (no scattered flags or duplicate state)
2. **Lifecycle Methods**: Explicit state transitions (start/end methods)
3. **Scene-Level State**: Track cross-turn context on scene object
4. **State Clearing**: Always clear state before transitions

**Architecture:**

#### BallController (Ball State)
- **Purpose**: Single source of truth for ball ownership and flight state
- **State Tracked**: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
- **Lifecycle Methods**: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`
- **Location**: `BallController.js`

**Example:**
```javascript
// BallController tracks ball state
ballController.onShotStart(); // Set isInFlight = true
// ... shot animation ...
ballController.onShotEnd(); // Clear state before next operation
```

#### Scene-Level State (Cross-Turn Context)
- **Purpose**: Track state that persists across multiple turns
- **Pattern**: Store on `scene` object for easy access and debugging

**Examples:**
- `scene.currentPressureType` - Tracks FCP/HCT pressure sequences ("FCP" | "HCT" | null)
- `scene.pressureSequenceActive` - Boolean flag for active pressure sequence
- `scene.currentOffenseTeamId` - Current offensive team
- `scene.gameState.ballHolder` - Ball holder ID (synchronized with BallController)

**Example (FCP/HCT State Tracking):**
```javascript
// Set state when pressure setup detected
if (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT") {
  scene.currentPressureType = turn.next_defensive_setup;
  scene.pressureSequenceActive = true;
}

// Use state for routing (simple check, no complex flag inheritance)
const isFCPHCT = scene.pressureSequenceActive && 
                 (turn.fcp_shot || turn.hct_shot || turn.fcp_foul || turn.hct_foul);

// Clear state when sequence completes
if (turn.result_type === "HCO" && !turn.fcp_shot && !turn.hct_shot) {
  scene.currentPressureType = null;
  scene.pressureSequenceActive = false;
}
```

**Benefits:**
- ✅ **Simple**: One state variable instead of complex flag detection
- ✅ **Reliable**: Doesn't depend on backend flags being present
- ✅ **Maintainable**: Easy to debug (check scene state)
- ✅ **Consistent**: Same pattern everywhere (matches BallController)
- ✅ **SS&S Aligned**: Single source of truth, scalable, sustainable

**State Clearing Pattern:**
Always clear state **before** transitioning to next operation:

```javascript
// ✅ CORRECT
await completeCurrentOperation();
this.ballController.onShotEnd(); // Clear state
await handleNextOperation();

// ❌ WRONG
await completeCurrentOperation();
await handleNextOperation(); // State not cleared!
this.ballController.onShotEnd(); // Too late!
```

**Key Files:**
- `BallController.js` - Ball state management
- `animateGameTurns.js` - Scene-level state tracking (FCP/HCT, offense team)
- `ballAnimationSimple.js` - Ball holder state synchronization

**See:**
- `UNIVERSAL_STATE_CLEARING_PATTERN.md` - Detailed state clearing patterns
- `FCP_HCT_STATE_TRACKING_PROPOSAL.md` - FCP/HCT state tracking implementation
- `Historical/BALL_ANIMATION_SYSTEM_REFACTORING_PLAN.md` - BallController state management

#### Multi-Turn Sequence State Tracking Pattern ✅ **REPLICABLE** (January 2025)

**Purpose**: Track state across multiple turns for sequences that span multiple turns (e.g., FCP/HCT pressure sequences, HCO sequences with fouls/turnovers, Fast Break sequences, OREB putback sequences).

**Current Implementation**: FCP/HCT pressure sequences (January 2025)

**Pattern Overview**:

1. **State Initialization**: Set scene-level state when sequence begins
2. **State Detection**: Use scene state + turn flags to detect sequence turns
3. **State Persistence**: Keep state active across multiple turns in sequence
4. **State Clearing**: Clear state when sequence completes (not on intermediate turns)

**FCP/HCT Implementation Example**:

```javascript
// 1. STATE INITIALIZATION (in animateGameTurns.js)
// Set state when pressure setup detected (BASELINE_INBOUND with next_defensive_setup)
if (turn.next_play_type === "BASELINE_INBOUND" && 
    (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT")) {
  scene.currentPressureType = turn.next_defensive_setup; // "FCP" or "HCT"
  scene.pressureSequenceActive = true;
}

// Also set state when runInboundSetup() is called inline (for made shots)
// This happens in turnAnimation.js when a made shot sets up the next FCP/HCT turn
if (pressureType) {
  scene.currentPressureType = pressureType;
  scene.pressureSequenceActive = true;
}

// 2. STATE DETECTION (in animateGameTurns.js)
// Detect FCP/HCT turns using explicit flags OR scene state
const hasExplicitFCPHCTFlags = turn.fcp_shot === true || turn.hct_shot === true ||
                               turn.fcp_foul === true || turn.hct_foul === true ||
                               (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));

// For press break outcomes, detect using scene state
const isPressBreakOutcome = (turn.result_type === "HCO" || turn.result_type === "TURNOVER") && 
                            scene.pressureSequenceActive;

// For press break shot attempts, detect using scene state
const isPressBreakShotAttempt = scene.pressureSequenceActive && 
                                 (turn.result_type === "MAKE" || turn.result_type === "MISS");

const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;

// 3. STATE PERSISTENCE (in animateGameTurns.js)
// Don't clear state on intermediate turns (e.g., made shot that sets up next FCP/HCT turn)
const isSettingUpNextFCPHCT = (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
                              (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT");
const shouldClearPressureState = 
  ((turn.result_type === "MAKE" || turn.result_type === "MISS") && !nextTurnIsFCPHCT && !isSettingUpNextFCPHCT) ||
  (turn.result_type === "HCO" && !nextTurnIsFCPHCT) ||
  turn.fcp_foul === true || turn.hct_foul === true ||
  turn.result_type === "TURNOVER";

// 4. STATE CLEARING (in animateGameTurns.js)
// Only clear when sequence actually completes
if (shouldClearPressureState && scene.pressureSequenceActive) {
  scene.currentPressureType = null;
  scene.pressureSequenceActive = false;
}
```

**Key Design Decisions**:

1. **Scene-Level State**: Store on `scene` object for easy access and debugging
   - `scene.currentPressureType` - Type of pressure ("FCP" | "HCT" | null)
   - `scene.pressureSequenceActive` - Boolean flag for active sequence

2. **Multi-Source Detection**: Use explicit flags OR scene state
   - Explicit flags: `fcp_shot`, `hct_shot`, `fcp_foul`, `hct_foul`, `next_defensive_setup`
   - Scene state: `scene.pressureSequenceActive` for press break outcomes/shot attempts

3. **State Persistence**: Don't clear state on intermediate turns
   - Made shot that sets up next FCP/HCT turn: Keep state active
   - Press break shot attempt: Keep state active (detected via scene state)
   - Only clear when sequence completes (HCO transition, foul, turnover)

4. **Detection Logic**: Three-part detection
   - Explicit flags (for setup turns and explicit FCP/HCT outcomes)
   - Press break outcomes (HCO/TURNOVER during active sequence)
   - Press break shot attempts (MAKE/MISS during active sequence)

**Replication Guide for Other Use Cases**:

**For HCO Sequences with Fouls/Turnovers**:
```javascript
// 1. Initialize state when HCO sequence begins
scene.hcoSequenceActive = true;
scene.hcoSequenceType = "HCO"; // Could track specific HCO type

// 2. Detect HCO sequence turns
const isHCOSequence = scene.hcoSequenceActive && 
                     (turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                      turn.result_type === "HCO" || turn.o_foul === true ||
                      turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns (e.g., foul during HCO sequence)

// 4. Clear state when sequence completes
if (turn.result_type === "DREB" || turn.result_type === "OREB") {
  scene.hcoSequenceActive = false;
  scene.hcoSequenceType = null;
}
```

**For Fast Break Sequences**:
```javascript
// 1. Initialize state when fast break begins
scene.fastBreakSequenceActive = true;

// 2. Detect fast break sequence turns
const isFastBreakSequence = scene.fastBreakSequenceActive && 
                            (turn.result_type === "FAST_BREAK" ||
                             turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                             turn.fast_break_foul === true || turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns

// 4. Clear state when sequence completes
if (turn.result_type === "HCO" || turn.result_type === "DREB") {
  scene.fastBreakSequenceActive = false;
}
```

**For OREB Putback Sequences**:
```javascript
// 1. Initialize state when OREB occurs
scene.orebSequenceActive = true;

// 2. Detect OREB sequence turns
const isOREBSequence = scene.orebSequenceActive && 
                      (turn.result_type === "OREB" ||
                       turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                       turn.oreb_foul === true || turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns

// 4. Clear state when sequence completes
if (turn.result_type === "DREB" || turn.result_type === "HCO") {
  scene.orebSequenceActive = false;
}
```

**Benefits of This Pattern**:
- ✅ **Simple Detection**: One scene state variable instead of complex flag inheritance
- ✅ **Reliable**: Doesn't depend on backend flags being present on every turn
- ✅ **Maintainable**: Easy to debug (check scene state in console)
- ✅ **Scalable**: Easy to extend to other multi-turn sequences
- ✅ **SS&S Aligned**: Single source of truth, scalable, sustainable

**Key Files**:
- `animateGameTurns.js` - FCP/HCT state tracking implementation
- `turnAnimation.js` - State initialization via `runInboundSetup()`

**Future Work**:
- Replicate pattern for HCO sequences with fouls/turnovers
- Replicate pattern for Fast Break sequences
- Replicate pattern for OREB putback sequences

#### Offensive State Values ✅ **REFERENCE** (January 2025)

**Purpose**: `offensive_state` is the **routing state** that determines which logic function handles each turn in the backend.

**All Possible Values**:

1. **`"HCO"`** - Half Court Offense (default)
   - **When set**: Default state, regular half-court possessions, after side inbounds, after turnovers (dead ball), after defensive stops
   - **Routes to**: `resolve_half_court_offense()` in `turn_manager.py`
   - **Set by**: Default initialization, `game_manager.py` (after side inbound), `phase_resolution.py` (after turnovers, defensive stops), `shot_manager.py` (after missed fast break shots)

2. **`"FREE_THROW"`** - Free Throw Situation
   - **When set**: AND-1 situations, shooting fouls, bonus free throws
   - **Routes to**: `resolve_free_throw()` in `turn_manager.py`
   - **Set by**: `shot_manager.py` (AND-1, shooting fouls), `phase_resolution.py` (bonus free throws)

3. **`"FAST_BREAK"`** - Fast Break Situation
   - **When set**: After defensive rebounds with defense release, after steals with fast break chance
   - **Routes to**: `resolve_fast_break_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (after DREB with defense release), `phase_resolution.py` (after steals with fast break chance)

4. **`"FCP"`** - Full Court Press
   - **When set**: After made shots when defense applies full court press
   - **Routes to**: `resolve_full_court_press_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (made shots), `turn_manager.py` (OREB putbacks), `phase_resolution.py` (after free throws)

5. **`"HCT"`** - Half Court Trap
   - **When set**: After made shots when defense applies half court trap
   - **Routes to**: `resolve_half_court_trap_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (made shots), `turn_manager.py` (OREB putbacks), `phase_resolution.py` (after free throws)

**Important Notes**:
- `offensive_state` is **persistent** across API calls (stored in `game_state`)
- `offensive_state` is **NOT** set on every turn - it's only set when the state needs to change
- If `offensive_state` is not set, it defaults to `"HCO"` (line 261 in `turn_manager.py`)
- `offensive_state` is the **single source of truth** for routing - handlers set it, `turn_manager.py` reads it

**Debugging**:
- Debug logs are added at transition points in `turn_manager.py`:
  - **Before routing** (`🔄 [OFFENSIVE_STATE TRANSITION] Turn #X - BEFORE ROUTING`):
    - `previous_offensive_state`: The state from the previous turn
    - `current_offensive_state`: The state being used to route this turn
    - `transition`: Shows the transition (e.g., `"HCO → FREE_THROW"`)
  - **After handler** (`🔄 [OFFENSIVE_STATE TRANSITION] Turn #X - AFTER HANDLER`):
    - `current_offensive_state`: The state that was used to route this turn
    - `next_offensive_state`: The state that will be used to route the next turn (set by handler)
    - `transition`: Shows the transition (e.g., `"FREE_THROW → HCO"`)
    - `state_changed`: Boolean indicating if the handler changed the state
    - `next_play_type`: Informational only (not used for routing)
- Look for `🔄 [OFFENSIVE_STATE TRANSITION]` in logs to trace state changes across turns
- The logs show the complete flow: `previous → current → next` for each turn

---

#### Backend State Preservation Pattern ✅ **CRITICAL** (January 2025)

**Purpose**: Ensure the backend generates the correct turn sequence by preserving `offensive_state` after generating intermediate turns (e.g., BASELINE_INBOUND).

**Why This Matters**:
After a made shot, the backend generates a separate BASELINE_INBOUND turn. To ensure the next API call generates the correct follow-up turn (FCP/HCT setup turn or regular HCO turn), the backend must preserve `offensive_state` after generating the BASELINE_INBOUND turn.

**The Pattern**:

1. **Made Shot Sets State**: When a shot is made, the backend sets `offensive_state` based on defensive pressure type:
   ```python
   # In shot_manager.py (HCO makes)
   pressure_type = self.game.turn_manager.determine_defensive_pressure_type()  # "FCP", "HCT", or "HCO"
   self.game_state["offensive_state"] = pressure_type
   result["next_defensive_setup"] = pressure_type
   ```

2. **Generate BASELINE_INBOUND Turn**: After the made shot, generate a separate BASELINE_INBOUND turn:
   ```python
   # In game_manager.py
   if (result.get("result_type") == "MAKE" and 
       result.get("next_play_type") == "BASELINE_INBOUND"):
       next_defensive_setup = result.get("next_defensive_setup")
       inbound_payload = self.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
       self.turns.append(inbound_payload)
   ```

3. **Preserve State for Next API Call**: After generating BASELINE_INBOUND, preserve `offensive_state` so the next API call generates the correct turn:
   ```python
   # In game_manager.py (CRITICAL)
   if next_defensive_setup:
       self.game_state["offensive_state"] = next_defensive_setup
   ```

**Complete Flow Example**:

**HCO Make → FCP Setup**:
1. Made shot sets `offensive_state = "FCP"` and `next_defensive_setup = "FCP"`
2. Backend generates BASELINE_INBOUND turn with `next_defensive_setup = "FCP"`
3. Backend preserves `offensive_state = "FCP"` after generating BASELINE_INBOUND
4. Next API call sees `offensive_state == "FCP"` → Generates FCP setup turn (FOUL/HCO/TURNOVER)

**HCO Make → HCO (No Pressure)**:
1. Made shot sets `offensive_state = "HCO"` and `next_defensive_setup = "HCO"`
2. Backend generates BASELINE_INBOUND turn with `next_defensive_setup = "HCO"`
3. Backend preserves `offensive_state = "HCO"` after generating BASELINE_INBOUND
4. Next API call sees `offensive_state == "HCO"` → Generates regular HCO turn

**Consistency Across All Made Shot Types**:

This pattern is used consistently across all made shot types:

- **OREB Putback**: Sets `offensive_state = pressure_type` in `resolve_offensive_rebound_turn()` → Preserved automatically
- **Free Throw**: Sets `offensive_state = pressure_type` in `resolve_free_throw_logic()` → Preserved automatically
- **HCO Make**: Sets `offensive_state = pressure_type` in `shot_manager.py` → **Now explicitly preserved** in `game_manager.py` after BASELINE_INBOUND

**Why HCO Makes Needed Explicit Preservation**:

OREB putback and Free Throw don't generate separate BASELINE_INBOUND turns, so `offensive_state` is preserved automatically. HCO makes generate a separate BASELINE_INBOUND turn, so we must explicitly preserve `offensive_state` after generating it.

**Benefits**:
- ✅ **Consistent Pattern**: Same behavior across all made shot types (HCO, OREB, Free Throw)
- ✅ **Correct Turn Generation**: Next API call generates the correct follow-up turn
- ✅ **SS&S Aligned**: Explicit state preservation, no reliance on defaults
- ✅ **Maintainable**: Clear, uniform logic that's easy to understand and debug

**Key Files**:
- `BackEnd/models/game_manager.py` - State preservation after BASELINE_INBOUND generation
- `BackEnd/models/shot_manager.py` - Initial state setting for HCO makes
- `BackEnd/models/turn_manager.py` - State setting for OREB putbacks
- `BackEnd/engine/phase_resolution.py` - State setting for Free Throws

**See**:
- `docs/FCP_HCT_FLOW_COMPARISON.md` - Comparison of made shot flows

---

### Animation Routing System ✅ **COMPLETE** (Phase 2.6 - January 2025)

**Status:** Fully migrated - All turn-level animations now route through AnimationRouter

The animation routing system provides a **unified, predictable architecture** for all turn animations, replacing scattered animation logic with a clean, centralized pattern. This is a **significant SS&S achievement** that simplifies the codebase, improves stability, and enables scalable extension.

**Architecture Pattern:**

```
animateGameTurns.js (detection)
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Specialized Handlers (execution)
```

**Core Components:**

1. **`AnimationRouter`** (`AnimationRouter.js`) - **Single entry point for all animations**
   - Handles pre/post setup via `prepareTurnForAnimation()` and `finalizeTurnAfterAnimation()`
   - Manages turn queuing to prevent concurrent processing
   - Integrates BallController and AnimationEngine
   - Provides consistent error handling and state management
   
2. **`AnimationEngine`** (`AnimationEngine.js`) - **Routes turns to appropriate handlers**
   - Determines which handler to use based on turn type via `determineHandler()`
   - Maintains a registry of handlers (`animationHandlers` Map)
   - Handlers: `ShotAnimationSystem`, `handleFreeThrow()`, `handleFastBreak()`, `handlePutback()`, `handleOpeningTip()`, `handleDefensiveStop()`, `handleSteal()`, `handleTurnover()`, `handleSideInbound()`, `handleBaselineInbound()`, `handleDefault()` (for HCO setup turns)
   - Fallback to `playTurnAnimation()` for legacy turn types (if needed)
   
3. **Specialized Handlers** - **Execute turn-specific animations**
   - `ShotAnimationSystem` - Handles HCO and FCP/HCT shots (MAKE/MISS)
   - `handleFreeThrow()` - Handles free throw sequences
   - `handleFastBreak()` - Handles fast break sequences
   - `handlePutback()` - Handles putback attempts and OREB kickouts
   - `handleOpeningTip()` - Handles opening tip sequences
   - `handleDefensiveStop()` - Handles defensive stop transitions
   - `handleSteal()` - Handles steal animations
   - `handleTurnover()` - Handles turnover animations
   - `handleSideInbound()` - Handles side inbound passes
   - `handleBaselineInbound()` - Handles baseline inbound passes (with FCP/HCT state tracking)
   - `handleDefault()` - Handles HCO setup turns via `playTurnAnimation()`

**Migration Status:**
- ✅ **Phase 2.4**: FCP/HCT foul turns migrated (December 2024)
- ✅ **Phase 2.5**: Standard HCO turns (MAKE/MISS) migrated (January 2025)
- ✅ **Phase 2.6**: All remaining turn types migrated (January 2025)
  - ✅ SIDE_INBOUND
  - ✅ BASELINE_INBOUND
  - ✅ HCO setup turns
  - ✅ FREE_THROW
  - ✅ FAST_BREAK
  - ✅ PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT
  - ✅ OPENING_TIP
  - ✅ DEFENSIVE_STOP
  - ✅ STEAL (standalone turn type)

**Complete Routing Flow:**

**All Turn Types Now Route Through AnimationRouter:**

1. **HCO shots (MAKE/MISS)** → `AnimationRouter` → `AnimationEngine` → `ShotAnimationSystem`
   - Standard half-court offense shots
   - Handles player movement, ball flight, rebounds, and DREB outlet passes
   
2. **FCP/HCT shots (MAKE/MISS)** → `AnimationRouter` → `AnimationEngine` → `ShotAnimationSystem`
   - FCP/HCT shot attempts (press break + shot)
   - **Same structure as HCO shots**: skeleton animation + shot
   - Both loop through `turnData.animations` steps, handle passes, then shoot
   
3. **FCP/HCT fouls** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`
   - Fouls that occur during FCP/HCT pressure sequences
   
4. **FCP/HCT setup turns** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`
   - Setup turns that establish FCP/HCT pressure (before shot attempts)
   - Animate press/trap setup sequences
   
5. **FREE_THROW** → `AnimationRouter` → `AnimationEngine` → `handleFreeThrow()`
   - Free throw sequences with active player display updates
   
6. **FAST_BREAK** → `AnimationRouter` → `AnimationEngine` → `handleFastBreak()`
   - Fast break sequences with outlet passes and shot attempts
   
7. **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** → `AnimationRouter` → `AnimationEngine` → `handlePutback()`
   - Putback shot attempts and OREB kickout passes
   
8. **OPENING_TIP** → `AnimationRouter` → `AnimationEngine` → `handleOpeningTip()`
   - Opening tip sequences with state transitions
   
9. **DEFENSIVE_STOP** → `AnimationRouter` → `AnimationEngine` → `handleDefensiveStop()`
   - Defensive stop transitions (Fast Break or standard)
   
10. **STEAL** (standalone turn) → `AnimationRouter` → `AnimationEngine` → `handleSteal()`
    - Steal pass animations and possession changes
    
11. **TURNOVER** → `AnimationRouter` → `AnimationEngine` → `handleTurnover()`
    - Turnover animations
    
12. **SIDE_INBOUND** → `AnimationRouter` → `AnimationEngine` → `handleSideInbound()`
    - Side inbound pass sequences
    
13. **BASELINE_INBOUND** → `AnimationRouter` → `AnimationEngine` → `handleBaselineInbound()`
    - Baseline inbound pass sequences with FCP/HCT state tracking
    
14. **HCO setup turns** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`
    - HCO setup turns (not shot attempts)

**Predictable Architecture Benefits:**

**Simple:**
- ✅ **Single Pattern**: All animations follow the same flow: detection → AnimationRouter → AnimationEngine → handler
- ✅ **Clear Separation**: `animateGameTurns.js` only detects and routes, handlers execute
- ✅ **One Mental Model**: "Find the turn type → route through AnimationRouter → handler executes"

**Stable:**
- ✅ **Centralized Routing**: All routing logic in one place (`AnimationEngine.determineHandler()`)
- ✅ **Consistent Error Handling**: AnimationRouter provides uniform error handling
- ✅ **Isolated Handlers**: Bugs in one handler don't affect others
- ✅ **Easier Testing**: Can test routing separately from execution

**Scalable:**
- ✅ **Easy Extension**: Adding new turn types requires only adding a handler to `AnimationEngine`
- ✅ **No Core Changes**: New turn types don't require modifying `animateGameTurns.js`
- ✅ **Clear Extension Points**: Handlers are isolated and can be refactored independently
- ✅ **Future-Proof**: Ready for new animation systems (e.g., `ReboundAnimationSystem`, `PassAnimationSystem`)

**Code Reduction:**
- ✅ **~500 lines removed** from `animateGameTurns.js` (from ~1400 to ~900 lines)
- ✅ **Eliminated duplicate logic** (announcements, score updates, state transitions)
- ✅ **Consistent pre/post setup** across all turn types

**Key Files:**
- `AnimationRouter.js` - Main entry point (single source of truth for routing)
- `AnimationEngine.js` - Turn routing logic and handler registry
- `turnPreparation.js` - Pre/post setup utilities
- `ShotAnimationSystem.js` - Shot handler (HCO and FCP/HCT)
- `animateGameTurns.js` - Turn detection and routing (simplified)
- Handler files - Specialized execution logic

**See:**
- `docs/PHASE_2.6_MIGRATION_PLAN_REVISED.md` - Complete migration plan and status

---

### Animation Detection List (Step 1) ✅ **COMPLETE** (January 2025)

**Status:** Comprehensive catalog of all detection points in `animateGameTurns.js`

This section catalogs every detection point that initiates routing through `AnimationRouter` in the animation system.

**Detection Architecture:**

**Flow:**
```
animateGameTurns.js (detection)  ← STEP 1
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Specialized Handlers (execution)
```

**Detection Pattern:**
All detections follow this pattern:
1. Check turn properties (`result_type`, flags, state)
2. Set `turn.index = i`
3. Call `await animationRouter.processTurn(turn)`
4. `continue` to next turn

**Detection Points (In Order of Execution):**

1. **FREE_THROW** (Line 560)
   - Detection: `turn.result_type === "FREE_THROW"`
   - Routes to: `AnimationRouter` → `handleFreeThrow()`
   - Notes: Active player display, free throw sequence, and text scroll handled by handler

2. **FOUL (FCP/HCT with animations)** (Line 571-573)
   - Detection: `turn.result_type === "FOUL" && (turn.fcp_foul === true || turn.hct_foul === true) && turn.animations && turn.animations.length > 0`
   - Routes to: `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
   - Notes: Only FCP/HCT fouls with animations route through AnimationRouter; non-animated fouls just do announcements

3. **DEAD BALL** (Line 596)
   - Detection: `turn.result_type === "DEAD BALL"`
   - Routes to: Direct announcements (no AnimationRouter)
   - Notes: No animation, just announcements and score updates

4. **SIDE_INBOUND** (Line 611)
   - Detection: `turn.result_type === "SIDE_INBOUND" && !scene.stateMachine?.is(States.FastBreak)`
   - Routes to: `AnimationRouter` → `handleSideInbound()`
   - Notes: Skips animation if in FastBreak state; still does announcements/updates

5. **BASELINE_INBOUND** (Line 633)
   - Detection: `turn.result_type === "BASELINE_INBOUND"`
   - Routes to: `AnimationRouter` → `handleBaselineInbound()`
   - Notes: FCP/HCT state tracking, player animations, and state transitions handled by handler

6. **DEFENSIVE_STOP** (Line 644)
   - Detection: `turn.result_type === "DEFENSIVE_STOP"`
   - Routes to: `AnimationRouter` → `handleDefensiveStop()`
   - Notes: Fast Break defensive stops route to `handleFastBreak()`; non-Fast Break uses `handleDefensiveStop()`

7. **PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT** (Line 655)
   - Detection: `turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT"`
   - Routes to: `AnimationRouter` → `handlePutback()`
   - Notes: All three result types use the same handler; includes debug logging for putback/OREB path tracking

8. **FCP/HCT Detection (Complex)** (Line 707-1055)
   - Detection: Multi-part detection logic
   - Routes to: `playTurnAnimation()` directly (not through AnimationRouter)
   - Detection Logic:
     ```javascript
     // Part 1: Explicit flags
     const hasExplicitFCPHCTFlags = 
       turn.fcp_shot === true || turn.hct_shot === true ||
       turn.fcp_foul === true || turn.hct_foul === true ||
       (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));
     
     // Part 2: Press break outcomes
     const isPressBreakOutcome = 
       (turn.result_type === "HCO" || turn.result_type === "TURNOVER") && 
       scene.pressureSequenceActive;
     
     // Part 3: Press break shot attempts
     const isPressBreakShotAttempt = 
       scene.pressureSequenceActive && 
       (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
       (turn.fcp_shot === true || turn.hct_shot === true);
     
     const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;
     ```
   - Notes: Uses scene-level state; routes directly to `playTurnAnimation()` (not through AnimationRouter); handles both setup turns and shot attempts

9. **TURNOVER** (Line 1057)
   - Detection: `turn.result_type === "TURNOVER"`
   - Routes to: `AnimationRouter` → `handleTurnover()`
   - Notes: Only detected if not already caught by FCP/HCT detection above

10. **OPENING_TIP** (Line 1078)
    - Detection: `turn.result_type === "OPENING_TIP"`
    - Routes to: `AnimationRouter` → `handleOpeningTip()`
    - Notes: Handler validates timing (Q1 start or OT start); state transition to HalfCourt handled by handler

11. **FAST_BREAK (Legacy Detection)** (Line 1104)
    - Detection: `turn.fast_break === true || turn.result_type === "FAST_BREAK"`
    - Routes to: Direct call to `runFastBreakSequence()` (legacy path)
    - Notes: Legacy code that should be removed in favor of detection at line 1141

12. **FAST_BREAK (New Detection)** (Line 1141)
    - Detection: `turn.result_type === "FAST_BREAK" || ((turn.result_type === "MAKE" || turn.result_type === "MISS") && turn.fast_break === true)`
    - Routes to: `AnimationRouter` → `handleFastBreak()`
    - Notes: Handles both explicit FAST_BREAK turns and MAKE/MISS with fast_break flag

13. **HCO Setup Turns** (Line 1156-1166)
    - Detection: `turn.result_type === "HCO" && !(turn.result_type === "MAKE" || turn.result_type === "MISS") && !isFCPHCTTurnForHCO`
    - Routes to: `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
    - Notes: Excludes FCP/HCT turns and shot attempts; only detects pure HCO setup turns

14. **HCO Shots (MAKE/MISS)** (Line 1068-1153)
    - Detection: `const isHCO = !isFastBreak && (turn.result_type === "MAKE" || turn.result_type === "MISS")`
    - Routes to: `AnimationRouter` → `AnimationEngine` → `handleShotAttempt()` → `ShotAnimationSystem`
    - Notes: Uses `result_type` check directly (not `current_turn === "HCO"`). Excludes fast breaks and FCP/HCT turns. Standard half-court offense shots.

15. **STEAL (Standalone Turn)** (Line 1290)
    - Detection: `!scene.stateMachine?.is(States.FastBreak) && turn.result_type === "STEAL"`
    - Routes to: `AnimationRouter` → `handleSteal()`
    - Notes: Only routes standalone STEAL turns; STEAL events within other turns are handled inline

16. **STEAL (Event Within Turn)** (Line 1296)
    - Detection: `!scene.stateMachine?.is(States.FastBreak) && stealEvent` (where `stealEvent = turn.events?.find(e => e.event_type === "STEAL")`)
    - Routes to: Direct call to `runPass()` (inline, not through AnimationRouter)
    - Notes: Not a standalone turn, so doesn't route through AnimationRouter; handled inline with pass animation

**Detection Summary by Result Type:**

| Result Type | Detection Line | Routes Through AnimationRouter? | Handler |
|------------|---------------|--------------------------------|---------|
| `FREE_THROW` | 560 | ✅ Yes | `handleFreeThrow()` |
| `FOUL` (FCP/HCT with animations) | 571 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `FOUL` (non-animated) | 571 | ❌ No | Direct announcements |
| `DEAD BALL` | 596 | ❌ No | Direct announcements |
| `SIDE_INBOUND` | 611 | ✅ Yes | `handleSideInbound()` |
| `BASELINE_INBOUND` | 633 | ✅ Yes | `handleBaselineInbound()` |
| `DEFENSIVE_STOP` | 644 | ✅ Yes | `handleDefensiveStop()` |
| `PUTBACK_MAKE` | 655 | ✅ Yes | `handlePutback()` |
| `PUTBACK_MISS` | 655 | ✅ Yes | `handlePutback()` |
| `OREB_KICKOUT` | 655 | ✅ Yes | `handlePutback()` |
| FCP/HCT (any type) | 707-1055 | ❌ No | Direct to `playTurnAnimation()` |
| `TURNOVER` | 1057 | ✅ Yes | `handleTurnover()` |
| `OPENING_TIP` | 1078 | ✅ Yes | `handleOpeningTip()` |
| `FAST_BREAK` (explicit) | 1141 | ✅ Yes | `handleFastBreak()` |
| `MAKE`/`MISS` (fast_break) | 1141 | ✅ Yes | `handleFastBreak()` |
| `HCO` (setup turn) | 1156 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `MAKE`/`MISS` (HCO shot) | 1069 | ✅ Yes | `handleShotAttempt()` → `ShotAnimationSystem` |
| `STEAL` (standalone) | 1290 | ✅ Yes | `handleSteal()` |
| `STEAL` (event) | 1296 | ❌ No | Direct to `runPass()` |

**Detection by Flag/Property:**

**By `result_type`:**
- `FREE_THROW` → Line 568
- `FOUL` → Line 579
- `DEAD BALL` → Line 614
- `SIDE_INBOUND` → Line 648
- `BASELINE_INBOUND` → Line 670
- `DEFENSIVE_STOP` → Line 681
- `PUTBACK_MAKE` → Line 692
- `PUTBACK_MISS` → Line 692
- `OREB_KICKOUT` → Line 692
- `TURNOVER` → Line 932
- `OPENING_TIP` → Line 953
- `FAST_BREAK` → Line 984
- `HCO` → Line 1006 (result_type check only, not routing)
- `MAKE` → Line 984 (fast break) or 1069 (HCO) or 812 (FCP/HCT)
- `MISS` → Line 984 (fast break) or 1069 (HCO) or 812 (FCP/HCT)
- `STEAL` → Line 1157

**By Flag:**
- `turn.fast_break === true` → Line 1104 (legacy) or 1141 (new)
- `turn.fcp_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.hct_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.fcp_shot === true` → Line 707 (FCP/HCT detection)
- `turn.hct_shot === true` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "FCP"` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "HCT"` → Line 707 (FCP/HCT detection)

**By State:**
- `scene.pressureSequenceActive === true` → Line 707 (FCP/HCT detection)
- `scene.stateMachine?.is(States.FastBreak)` → Line 611 (SIDE_INBOUND skip), 1290 (STEAL skip)

**By Event:**
- `turn.events?.find(e => e.event_type === "STEAL")` → Line 1296 (inline STEAL event)

**Special Cases:**

1. **FCP/HCT Detection (Not Through AnimationRouter)**
   - **Why:** FCP/HCT turns route directly to `playTurnAnimation()` instead of through `AnimationRouter`
   - **Reason:** Historical implementation - could be migrated in future phase

2. **STEAL Events (Not Through AnimationRouter)**
   - **Why:** STEAL events within other turns are not standalone turns, so they don't need routing
   - **Reason:** Events are handled inline as part of the parent turn's animation

3. **Legacy FAST_BREAK Detection**
   - **Why:** Two detection points for fast breaks (line 1104 and 1141)
   - **Reason:** Line 1104 is legacy code that should be removed

**Detection Order Matters:**

The order of detections is **critical** because:
1. **Early exits:** Once a detection matches, the turn is processed and the loop `continue`s
2. **Exclusion logic:** Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT)
3. **State dependencies:** Some detections depend on state set by previous detections (e.g., FCP/HCT uses `scene.pressureSequenceActive`)

**Current Order (as executed):**
1. FREE_THROW (Line 568)
2. FOUL (Line 579)
3. DEAD BALL (Line 614)
4. SIDE_INBOUND (Line 648)
5. BASELINE_INBOUND (Line 670)
6. DEFENSIVE_STOP (Line 681)
7. PUTBACK_MAKE/MISS/OREB_KICKOUT (Line 692)
8. FCP/HCT (complex detection, Line 707-928)
9. TURNOVER (Line 932)
10. OPENING_TIP (Line 953)
11. FAST_BREAK (Line 984)
12. HCO result_type check (Line 1006 - debug only, not routing)
13. HCO shots (MAKE/MISS) (Line 1069 - uses `result_type` check, not `current_turn`)
14. STEAL (standalone) (Line 1157)
15. STEAL (event) (Line 1178)

**Important Notes:**

1. **HCO Routing:** Uses `result_type === "MAKE" || result_type === "MISS"` check (not `current_turn === "HCO"`). This is more permissive and catches all HCO shots, including those where `current_turn` might not be set correctly.

2. **FCP/HCT Routing:** Currently routes directly to `playTurnAnimation()` (not through AnimationRouter). This is historical implementation - could be migrated in future phase.

3. **Detection Order Matters:** Early exits prevent double processing. Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT).

---

### Animation Handler List (Step 3) ✅ **COMPLETE** (January 2025)

**Status:** Comprehensive catalog of all handlers in `AnimationEngine.js`

This section catalogs every handler that executes turn animations after routing through `AnimationRouter` and `AnimationEngine`.

**Handler Architecture:**

**Flow:**
```
animateGameTurns.js (detection)  ← STEP 1
    ↓
AnimationRouter (single entry point)  ← STEP 2
    ↓
AnimationEngine (routing logic)  ← STEP 2
    ↓
Specialized Handlers (execution)  ← STEP 3
```

**Handler Registration:**
All handlers are registered in `AnimationEngine.initializeDefaultHandlers()` and stored in `this.animationHandlers` Map.

**Handler Pattern:**
All handlers follow this pattern:
1. Receive `turnData` and `context` parameters
2. Execute turn-specific animation logic
3. Handle announcements, score updates, and state transitions (or delegate to AnimationRouter)
4. Return Promise (async/await)

---

## Registered Handlers

### 1. `handleFreeThrow()` 
**Registered for:** `FREE_THROW`  
**Location:** `AnimationEngine.js` line 249  
**What it does:**
- Updates active player display (shooter)
- Routes to `FreeThrowAnimationSystem` (if available) or falls back to `runFreeThrowSequence()`
- Appends text scroll with free throw result
- **Note:** `onUpdate` is called inside `runFreeThrowSequence` (no double counting)

**Key Features:**
- Active player display update
- Free throw sequence execution
- Text scroll append
- Handles multiple free throw attempts (via `ftContext`)

---

### 2. `handleSideInbound()`
**Registered for:** `SIDE_INBOUND`  
**Location:** `AnimationEngine.js` line 283  
**What it does:**
- Checks FastBreak state (skips animation if in FastBreak)
- Routes to `PassAnimationSystem` (if available) or falls back to `runSideInboundSetup()`
- Handles side inbound pass animations

**Key Features:**
- FastBreak state check (matches original logic)
- Pass animation system integration
- Fallback to legacy `runSideInboundSetup()`

---

### 3. `handleBaselineInbound()`
**Registered for:** `BASELINE_INBOUND`  
**Location:** `AnimationEngine.js` line 309  
**What it does:**
- **FCP/HCT State Tracking:** Sets `scene.currentPressureType` and `scene.pressureSequenceActive` when pressure setup detected
- Animates all players to their positions using distance-based duration
- Transitions state machine to `HalfCourt`
- Sets `scene._previousTurnWasInbound = true` for HCO pre-step setup

**Key Features:**
- FCP/HCT state initialization (single source of truth)
- Player position animations (distance-based duration)
- State machine transition
- Scene flag for HCO setup

---

## BASELINE_INBOUND (BIP) and Player Setup After Made Shots

After a made shot (HCO MAKE, PUTBACK_MAKE, Fast Break MAKE, Free Throw MAKE), the next turn is always `BASELINE_INBOUND`. This turn handles player positioning and inbound pass animation before transitioning to the next offensive sequence (HCO, HCT, or FCP).

### Process Overview

**Location:** `AnimationEngine.handleBaselineInbound()` → `PassAnimationSystem.executeInboundSequence()` → `runInboundSetup()`

**Flow:**
1. Made shot turn completes (shot animation, celebration, etc.)
2. `BASELINE_INBOUND` turn is created by backend
3. Frontend routes to `AnimationEngine.handleBaselineInbound()`
4. Players are positioned based on next turn type
5. Inbound pass is executed
6. Next turn (HCO/HCT/FCP) begins with players already in position

### Three Next Turn Scenarios

#### 1. BASELINE_INBOUND → HCO (Normal Inbound)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup=None`
- Creates random baseline positions for offensive players (PG, SG, SF, PF, C)
- PG is the inbounder (stays at inbound spot)
- Defensive players retreat to midcourt

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=false`
- **Defensive players:** Animate to midcourt (x: 45 or 55) - retreat animation
- **Offensive players:** Animate to random baseline positions from `oDestinations`
- **Inbound pass:** SF → PG (hardcoded fallback, or dynamic from `turnData.animations`)

**Key Code:**
- `turnAnimation.js` lines 1031-1078: Defensive retreat animation
- `turnAnimation.js` lines 1220-1224: Offensive player positioning (uses `inboundDest`)

---

#### 2. BASELINE_INBOUND → HCT (Half Court Trap)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="HCT"`
- Retrieves HCT skeleton step 0 via `get_skeleton_for_turn("HCO", "HCT", game)`
- Extracts `pos_actions` from step 0 and includes in `offense_setup_positions`
- Applies `apply_opposite_side_logic()` to skeleton (handles `opp` field)
- SF is the inbounder (uses `inbound_left` location from `HCT_SETUP_POSITIONS`)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="HCT"`
- **Defensive players:** Animate directly to HCT trap positions (no retreat)
  - Positions: PG at x=60, SG/SF at x=55, PF/C at x=45 (home orientation)
  - Flipped for away team defense
- **Offensive players:** Animate to skeleton step 0 positions from `offense_setup_positions`
  - **Critical:** Frontend checks `coords` field first (has `opp` logic applied)
  - Falls back to `location` field if `coords` missing
  - Applies `opp` logic when using `location`:
    - `opp=True`: Flip coords for home offense (ball handlers go to away side)
    - `opp=False`: Flip coords for away offense (outlet players go to away side)
- **Inbound pass:** SF → PG (from skeleton step 0 positions)

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: HCT defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling

**Important Notes:**
- `opp` field determines which players go to opposite side (defensive side)
- Ball handlers (usually PG) have `opp=True` and go to opposite side
- Outlet players have `opp=False` and stay on normal offense side
- Coordinate flipping formula: `x = 101 - x` for away team offense

---

#### 3. BASELINE_INBOUND → FCP (Full Court Press)

**Backend Setup:**
- `turn_manager.py` `setup_baseline_inbound()` with `next_defensive_setup="FCP"`
- Retrieves FCP skeleton step 0 via `get_skeleton_for_turn("HCO", "FCP", game)`
- Extracts `pos_actions` from step 0 and includes in `offense_setup_positions`
- Applies `apply_opposite_side_logic()` to skeleton (handles `opp` field)
- SF is the inbounder (uses `inbound_left` location from `FCP_SETUP_POSITIONS`)

**Frontend Execution:**
- `runInboundSetup()` called with `skipRetreat=true`, `pressureType="FCP"`
- **Defensive players:** Animate directly to FCP press positions (no retreat)
  - Positions: PG at x=80, SG/SF at x=73, PF/C at x=37/35 (home orientation)
  - Flipped for away team defense
- **Offensive players:** Animate to skeleton step 0 positions from `offense_setup_positions`
  - **Critical:** Frontend checks `coords` field first (has `opp` logic applied)
  - Falls back to `location` field if `coords` missing
  - Applies `opp` logic when using `location` (same as HCT)
- **Inbound pass:** SF → PG (from skeleton step 0 positions)

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: FCP defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling

**Important Notes:**
- Same `opp` logic as HCT (ball handlers vs outlet players)
- FCP positions are more aggressive (deeper in offensive zone)
- `inbound_left` vs `inbound_right` determined by offense team:
  - Home offense: Uses `inbound_left` (x=3) - correct
  - Away offense: Backend flips to `inbound_right` (x=97) via coordinate flipping

---

### Coordinate System and `opp` Field

**Home Orientation:**
- `HCO_STRING_SPOTS` coordinates are in home team orientation
- Home team attacks right basket (x=91), away team attacks left basket (x=9)
- Midcourt is x=50

**Opposite Side Logic (`opp` field):**
- **Purpose:** Determines which offensive players go to opposite side (defensive side) during press break
- **`opp=True`:** Ball handlers (usually PG) - go to opposite side to break press
- **`opp=False`:** Outlet players (SG, SF, PF, C) - stay on normal offense side
- **Backend:** `apply_opposite_side_logic()` converts locations to coords and stores in `coords` field
- **Frontend:** Prioritizes `coords` field (backend-applied logic), falls back to `location` with manual `opp` application

**Coordinate Flipping:**
- Formula: `x = 101 - x` (flips around midcourt)
- Applied for:
  - Away team offense (normal flip)
  - Home team offense with `opp=True` (ball handlers go to away side)
  - Away team offense with `opp=False` (outlet players go to away side)

### Key Functions

**Backend:**
- `turn_manager.py` `setup_baseline_inbound()`: Creates BASELINE_INBOUND turn data
- `phase_resolution.py` `get_skeleton_for_turn()`: Retrieves FCP/HCT skeleton
- `phase_resolution.py` `apply_opposite_side_logic()`: Applies `opp` field logic

**Frontend:**
- `AnimationEngine.handleBaselineInbound()`: Routes BASELINE_INBOUND turns
- `PassAnimationSystem.executeInboundSequence()`: Handles inbound pass execution
- `turnAnimation.js` `runInboundSetup()`: Positions players and executes inbound pass

---

## SIDE_INBOUND (SIP) and Player Setup After Fouls/Dead Balls

Side inbound passes (`SIDE_INBOUND`) occur after dead ball situations such as fouls (non-shooting), turnovers (dead ball), or other stoppages. Unlike BASELINE_INBOUND, SIP is simpler and doesn't involve defensive pressure setup or retreat animations.

### Process Overview

**Location:** `AnimationEngine.handleSideInbound()` → `PassAnimationSystem.executeInboundSequence()` → `runSideInboundSetup()`

**Flow:**
1. Dead ball situation occurs (foul, turnover, etc.)
2. `SIDE_INBOUND` turn is created by backend
3. Frontend routes to `AnimationEngine.handleSideInbound()`
4. Ball is immediately moved to inbound spot
5. Players are positioned based on `oDestinations` and `dDestinations`
6. Ball attaches to SF when SF reaches the inbound spot
7. Inbound pass is executed (SF → PG)
8. Next turn (typically HCO) begins

### Ball Handling

**Ball Positioning:**
- Ball is immediately moved to `ball_spot` coordinates at the start of the SIP turn
- Ball remains at the inbound spot while players animate to their positions
- This matches BASELINE_INBOUND behavior for consistency

**Ball Attachment:**
- Ball attaches to SF when SF reaches the inbound spot (in SF's tween `onComplete` callback)
- This ensures the ball is attached as soon as the SF arrives, not after all players finish
- Safety fallback attachment exists if SF tween completes without attachment

**Key Code:**
- `turnAnimation.js` lines 294-301: Ball immediately positioned at inbound spot
- `turnAnimation.js` lines 321-327: Ball attaches to SF when SF reaches spot
- `turnAnimation.js` lines 378-384: Safety fallback attachment check

### Player Positioning

**Offensive Players:**
- Positions come from `turnData.oDestinations` (backend-provided)
- All offensive players animate to their destinations using distance-based timing
- SF is the inbounder (receives ball at inbound spot)

**Defensive Players:**
- Positions come from `turnData.dDestinations` (backend-provided)
- All defensive players animate to their destinations using distance-based timing
- No special retreat or pressure positioning (unlike BIP)

### Inbound Pass Execution

**Pass Detection:**
- Frontend checks `turnData.animations` for dynamic pass actions
- If pass detected in animation data, uses `handlePassAnimation()` with pass info
- Falls back to hardcoded SF → PG pass if no pass detected

**Pass Animation:**
- Pass executes after all players reach their positions
- Ball transfers from SF to PG
- PG receives ball and next turn begins

**Key Code:**
- `turnAnimation.js` lines 359-415: Pass detection and execution
- `passDetection.js`: Dynamic pass detection from animation data
- `ballManager.js`: Pass animation execution

### Key Differences from BASELINE_INBOUND

| Aspect | SIDE_INBOUND (SIP) | BASELINE_INBOUND (BIP) |
|--------|-------------------|------------------------|
| **Use Case** | After fouls, dead ball turnovers | After made shots, quarter starts |
| **Defensive Setup** | Simple positioning from `dDestinations` | Complex: retreat animation or FCP/HCT press positions |
| **Pressure Logic** | None | Handles FCP/HCT setup with skeleton positions |
| **Ball Attachment** | Attaches when SF reaches spot | Attaches after all players positioned |
| **Complexity** | Simple, straightforward | Complex with multiple scenarios |
| **Code Function** | `runSideInboundSetup()` | `runInboundSetup()` |

### Key Functions

**Backend:**
- `turn_manager.py`: Creates SIDE_INBOUND turn data with `oDestinations`, `dDestinations`, `ball_spot`

**Frontend:**
- `AnimationEngine.handleSideInbound()`: Routes SIDE_INBOUND turns
- `PassAnimationSystem.executeInboundSequence()`: Handles inbound pass execution
- `turnAnimation.js` `runSideInboundSetup()`: Positions players, handles ball attachment, executes inbound pass

---

## Quarter Start Possession Logic and BASELINE_INBOUND Turns ✅ **COMPLETE** (January 2025)

**Status:** Fully implemented and tested

### Quarter Start Possession Pattern

**Q1 (First Quarter):**
- **Start Type:** Opening Tip
- **Possession:** Winner of opening tip gets possession
- **Turn Type:** `OPENING_TIP` → Transitions to HCO
- **Location:** `BackEnd/utils/opening_tip.py` `execute_opening_tip()`
- **Frontend:** `AnimationEngine.handleOpeningTip()` → `openingTip.js`

**Q2 (Second Quarter):**
- **Start Type:** BASELINE_INBOUND
- **Possession:** Team that did **NOT** win opening tip gets possession
- **Turn Type:** `BASELINE_INBOUND` → Transitions to HCO/HCT/FCP (based on defensive pressure)
- **Location:** `BackEnd/main.py` lines 328-369
- **Frontend:** `AnimationEngine.handleBaselineInbound()` (same as post-shot BIP)

**Q3 (Third Quarter):**
- **Start Type:** BASELINE_INBOUND
- **Possession:** Team that did **NOT** win opening tip gets possession (same as Q2)
- **Turn Type:** `BASELINE_INBOUND` → Transitions to HCO/HCT/FCP (based on defensive pressure)
- **Location:** `BackEnd/main.py` lines 370-411
- **Frontend:** `AnimationEngine.handleBaselineInbound()` (same as post-shot BIP)

**Q4 (Fourth Quarter):**
- **Start Type:** BASELINE_INBOUND
- **Possession:** Opening tip **winner** gets possession
- **Turn Type:** `BASELINE_INBOUND` → Transitions to HCO/HCT/FCP (based on defensive pressure)
- **Location:** `BackEnd/main.py` lines 412-453
- **Frontend:** `AnimationEngine.handleBaselineInbound()` (same as post-shot BIP)

**Overtime Quarters (OT1, OT2, OT3, etc.):**
- **Start Type:** Opening Tip
- **Possession:** Winner of opening tip gets possession
- **Turn Type:** `OPENING_TIP` → Transitions to HCO
- **Location:** `BackEnd/main.py` lines 318-327
- **Frontend:** `AnimationEngine.handleOpeningTip()` → `openingTip.js`
- **Note:** **Every overtime quarter** (even if there are multiple overtimes) always starts with an opening tip, not a BASELINE_INBOUND.

### Possession Logic Summary

**Pattern:**
- **Q1:** Opening tip winner
- **Q2:** Team that did NOT win opening tip
- **Q3:** Team that did NOT win opening tip (same as Q2)
- **Q4:** Opening tip winner (back to Q1 team)
- **OT1, OT2, OT3, etc.:** Opening tip winner (new tip each OT)

**Storage:**
- Opening tip winner stored in `game_state["opening_tip_winner"]` as `"home"` or `"away"`
- Set by: `BackEnd/utils/opening_tip.py` `execute_opening_tip()` line 78
- Used by: `BackEnd/main.py` `simulate_quarter()` for Q2/Q3/Q4 possession determination

### Quarter Start BASELINE_INBOUND Implementation

**Backend (`BackEnd/main.py`):**

For Q2, Q3, and Q4:
1. **Determine Possession:** Based on `opening_tip_winner` from game state
2. **Set Offense/Defense Teams:** Update `game.offense_team` and `game.defense_team`
3. **Check Defensive Pressure:** Call `turn_manager.determine_defensive_pressure_type()` to check for FCP/HCT
4. **Create BASELINE_INBOUND Turn:** Use `turn_manager.setup_baseline_inbound()` with `next_defensive_setup` parameter
5. **Build Complete Turn:** Add `text`, `time_elapsed`, `possession_flips`, `quarter` fields
6. **Append to Turns:** Add to `game.turns` array
7. **Update Clock:** Subtract `time_elapsed` from `time_remaining`

**Key Code:**
```python
# Q2 example (BackEnd/main.py lines 328-369)
elif q == 2:
    # Determine possession (team that did NOT win opening tip)
    opening_tip_winner = gm.game_state.get("opening_tip_winner", "home")
    if opening_tip_winner == "home":
        gm.offense_team = gm.away_team
        gm.defense_team = gm.home_team
    else:
        gm.offense_team = gm.home_team
        gm.defense_team = gm.away_team
    
    # Check for defensive pressure
    pressure_type = gm.turn_manager.determine_defensive_pressure_type()
    next_defensive_setup = pressure_type if pressure_type in ["FCP", "HCT"] else None
    
    # Create BASELINE_INBOUND turn
    inbound_payload = gm.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
    inbound_turn = {
        **inbound_payload,
        "text": f"Start of Q{q}: {gm.offense_team.name} inbounds the ball.",
        "time_elapsed": 4,
        "possession_flips": False,
        "quarter": q,
    }
    gm.turns.append(inbound_turn)
```

**Frontend:**

Quarter start BASELINE_INBOUND turns are handled identically to post-shot BASELINE_INBOUND turns:
- Same routing: `AnimationEngine.handleBaselineInbound()`
- Same execution: `PassAnimationSystem.executeInboundSequence()` → `runInboundSetup()`
- Same player positioning logic (HCO/HCT/FCP based on `next_defensive_setup`)
- Same inbound pass animation

**No Special Handling Required:**
- Quarter start BIPs use the exact same code path as post-shot BIPs
- Frontend cannot distinguish between quarter start BIPs and post-shot BIPs (and doesn't need to)
- All BIPs are unified through the same `BASELINE_INBOUND` turn type

### Benefits

- ✅ **Unified System:** Quarter starts use the same BASELINE_INBOUND system as post-shot inbounds
- ✅ **Consistent Frontend Handling:** No special-case code needed for quarter starts
- ✅ **SS&S Aligned:** Single source of truth for all BASELINE_INBOUND turns
- ✅ **Defensive Pressure Support:** Q2/Q3/Q4 can start with FCP/HCT pressure (same as post-shot)
- ✅ **Proper Possession Logic:** Follows standard basketball rules (alternating possession pattern)

### Key Files

**Backend:**
- `BackEnd/main.py` lines 318-453: Quarter start logic (Q1 opening tip, Q2/Q3/Q4 BASELINE_INBOUND)
- `BackEnd/utils/opening_tip.py`: Opening tip execution and winner storage
- `BackEnd/models/turn_manager.py` `setup_baseline_inbound()`: BASELINE_INBOUND turn creation

**Frontend:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleBaselineInbound()`: Routes all BASELINE_INBOUND turns
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js` `executeInboundSequence()`: Executes inbound passes
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` `runInboundSetup()`: Positions players and handles inbound pass

**Tests:**
- `tests/test_quarter_starts.py`: Comprehensive tests for Q2/Q3/Q4 quarter starts

---

## Timeout System ✅ **COMPLETE** (January 2025)

The timeout system allows game pauses for strategic adjustments, lineup changes, and game plan modifications. Timeouts are treated as standard game turns and integrate seamlessly with the existing transition system.

### Overview

**Timeout Turn Type:** `TIMEOUT`

**Timeout Reasons:**
- `"USER"` - User-initiated timeout (via timeout button)
- `"COMPUTER"` - AI-initiated timeout (future feature)
- `"FOUL_OUT"` - Player fouls out (automatic timeout)
- `"QUARTER_END"` - Quarter end timeout (currently not used, quarter transitions are seamless)

**Key Features:**
- Timeouts are standard game turns (same data structure and flow)
- Game state persists across timeout (scores, clock, fouls, timeouts, lineups)
- Lineup and game plan screens pre-populated with current settings
- Scoreboard displays immediately on timeout resume
- Uses same transition system as other game flows
- Database is single source of truth for timeout state
- Works consistently across all game modes (single, tournament, franchise)

### Transition Flow and Integration

**Timeout Turn Creation:**

1. **User-Initiated Timeout:**
   - User presses timeout button during SIP/BIP turn (2.5-second pause window)
   - Frontend calls `/api/call-timeout` endpoint
   - Backend creates `TIMEOUT` turn via `turn_manager.setup_timeout_turn()`
   - `TIMEOUT` turn appended to `gm.turns` array

2. **Foul-Out Timeout:**
   - Player fouls out during shot resolution
   - `result["fouled_out"] = True` set in `shot_manager.py`
   - `game_manager.simulate_macro_turn()` detects `fouled_out` flag
   - **Captures `timeout_offense_team_id`** before creating timeout turn (`BackEnd/models/game_manager.py` line 260)
   - Creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`
   - Frontend navigates with `resume_from_timeout=true` flag (`FrontEnd/static/js/phaser/utils/foulOutPopup.js`)

**Timeout Turn Payload:**

```python
{
    "result_type": "TIMEOUT",
    "current_turn": "TIMEOUT",
    "timeout_reason": "USER" | "COMPUTER" | "FOUL_OUT" | "QUARTER_END",
    "next_play_type": "SIDE_INBOUND" | "FREE_THROW" | "BASELINE_INBOUND",
    "next_turn": "SIDE_INBOUND" | "FREE_THROW" | "BASELINE_INBOUND",
    "offense_team_id": game.offense_team.team_id,
    "quarter": game.quarter,
    "text": "Timeout called by [Team Name]",
    "time_elapsed": 0,  # Timeouts don't consume game time
    "possession_flips": False,
    "timeout_calling_team": {
        "name": calling_team.name,
        "team_id": calling_team.team_id
    },
    "home_team_timeouts": gm.home_team.timeouts,
    "away_team_timeouts": gm.away_team.timeouts
}
```

**Next Play Type Determination:**

The `next_play_type` in the timeout turn is **always** `"SIDE_INBOUND"` (except when free throws are pending):

1. **`"SIDE_INBOUND"` (Always for timeouts):**
   - Timeouts always resume with SIP (Side Inbound Pass)
   - Team that had possession when timeout was called gets the ball back
   - Creates SIP turn after timeout resume
   - SIP transitions to HCO (defense calls play in HCO)

2. **`"FREE_THROW"` (Special case):**
   - Used when timeout is called during free throw sequence
   - Free throw sequence continues after timeout resume

**Note:** Quarter breaks (Q2/Q3/Q4) use BIP (Baseline Inbound Pass), but this is handled separately in `simulate_quarter()` and is not part of the timeout system.

**Transition System Integration:**

Timeouts use the same centralized transition system as all other turns:

**Backend (`BackEnd/models/game_manager.py` `determine_next_turn()`):**
```python
# TIMEOUT → SIP/Free Throw/BIP (based on next_play_type in timeout turn)
if current == "TIMEOUT":
    return result.get("next_play_type", "SIDE_INBOUND")
```

**Frontend (`FrontEnd/static/js/phaser/animation/animateGameTurns.js`):**
```javascript
if (turn.result_type === "TIMEOUT") {
    turn.index = i;
    await animationRouter.processTurn(turn);
    console.log('⏸️ TIMEOUT: Stopping animation loop - user will navigate to lineup screen');
    break; // Exit the loop - don't process any more turns
}
```

**Key Point:** Timeouts are routed through `AnimationRouter.processTurn()` just like all other turn types, ensuring consistent handling and data flow.

### Game Start and Resume Transitions

The system handles different transition types based on game state. All navigation uses the unified Timeout Navigation Helper for consistent parameter building.

#### 1. **Game Start (Q1) and Overtime**
- **Initial Turn:** Opening Tip
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 392-401)
- **Logic:** Q1 or any OT period → creates opening tip turn
- **Data:** No special state needed (new game)
- **Navigation:** Helper does NOT pass `game_id` for new Q1 game start
- **Frontend:** `set-lineup.js` "Play Now" button, `game-plan.js` "Play Game" button

#### 2. **Quarter Break Returns (Q2, Q3, Q4)**
- **Initial Turn:** BASELINE_INBOUND (BIP)
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 402-443, 444-468, 469-493)
- **Logic:** Quarter break → creates BIP turn with correct possession team
- **Data:** Uses `opening_tip_winner` from game_state to determine possession
- **Navigation:** Helper passes `game_id` (quarter > 1), does NOT set `resume_from_timeout`
- **Frontend:** `gameScene.js` quarter end navigation, `set-lineup.js` "Play Now" button
- **Note:** Not part of timeout system - handled separately

#### 3. **Timeout Returns (Any Quarter)**
- **Initial Turn:** SIDE_INBOUND (SIP)
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 281-332)
- **Logic:** Timeout resume → creates SIP turn with team that had possession
- **Data:** Restores `timeout_next_play_type` and `timeout_offense_team_id` from database
- **Navigation:** Helper passes `game_id` AND sets `resume_from_timeout=true` (any quarter)
- **Frontend:** `timeoutButtonManager.js` timeout button, `set-lineup.js` "Play Now" button, `game-plan.js` "Play Game" button
- **Note:** Supports Q1-Q4 and OT (removed Q1-only restriction)

#### 4. **Player Foul Out Returns (Any Quarter)**
- **Initial Turn:** SIDE_INBOUND (SIP)
- **Location:** Same as timeout returns (uses timeout system)
- **Logic:** Foul out resume → creates SIP turn (same pattern as timeout)
- **Data:** Uses same timeout resume system, captures `timeout_offense_team_id` in `game_manager.py`
- **Navigation:** Helper passes `game_id` AND sets `resume_from_timeout=true` (any quarter)
- **Frontend:** `foulOutPopup.js` navigation to lineup
- **Note:** Supports Q1-Q4 and OT (uses same system as timeout)

### Data Management: Database, LocalStorage, and URL

#### Database (Single Source of Truth)

**When Timeout is Called (`BackEnd/api/api.py` `call_timeout_endpoint()`):**
```python
# Save timeout state to database
gm.game_state["timeout_next_play_type"] = "SIDE_INBOUND"  # Always SIP (except free throws)
gm.game_state["timeout_offense_team_id"] = gm.offense_team.team_id  # Capture possession team

db_summary = summarize_game_state(gm, exclude_animations=True)
games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
```

**Persisted Timeout Data:**
- `timeout_next_play_type`: Always `"SIDE_INBOUND"` (or `"FREE_THROW"` if free throws pending)
- `timeout_offense_team_id`: Team that had possession when timeout was called
- `clock`: Current game clock
- `time_remaining`: Time remaining in seconds
- All other game state (scores, fouls, timeouts, lineups, player stats)

**When Timeout Resumes (`BackEnd/main.py` `simulate_quarter()`):**
```python
# After creating SIP turn, clear timeout state from database
games_collection.update_one(
    {"_id": game_id},
    {"$unset": {"timeout_next_play_type": "", "timeout_offense_team_id": ""}}
)
```

**Database Access by Mode:**
- **Single Game:** `games_collection` document
- **Tournament Game:** Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
- **Franchise Game:** Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)

#### URL Parameters (Navigation Only)

**Purpose:** URL parameters are used for navigation/routing, not business logic. Database is the source of truth.

**Unified Navigation Helper System (SS&S - December 2025):**

All frontend navigation now uses a unified helper (`FrontEnd/static/js/shared/timeoutNavigationHelper.js`) for consistent parameter building across all entry points.

**Helper Functions:**
- `buildGameNavigationParams()`: Builds URL parameters with consistent SS&S logic
- `getResumeFromTimeout()`: Extracts `resume_from_timeout` from URL params
- `getGameId()`: Gets game ID from URL or localStorage

**Navigation Entry Points Using Helper:**
- `set-lineup.js`: "Play Now" button, "Game Plan" button
- `game-plan.js`: `navigateToCourt()`, `navigateBack()`
- `timeoutButtonManager.js`: `showTimeoutPopup()` (timeout button navigation)
- `foulOutPopup.js`: Foul out navigation to lineup
- `gameScene.js`: Quarter end navigation

**Helper Logic (SS&S Rules):**

1. **Game ID Logic:**
   - Pass `game_id` if: `quarter > 1` OR `resumeFromTimeout === true`
   - NOT for new Q1 game start

2. **Resume From Timeout Logic:**
   - Set `resume_from_timeout=true` if: `resumeFromTimeout === true` AND `gameId` exists
   - NOT for quarter breaks (Q2-Q4 without timeout)
   - NOT for new game start
   - **Supports any quarter** (Q1-Q4, OT) - removed Q1-only restriction

3. **Quarter/Period Logic:**
   - Always sets `quarter` and `period` (Q1-Q4 or OT1+)
   - Automatically calculates period label

4. **Parameter Preservation:**
   - Preserves all team info, mode, tournament/franchise IDs
   - Preserves lineup, clock, special params
   - Preserves debug flags

**URL Parameters Used:**
- `resume_from_timeout=true`: Navigation flag (convenience, not source of truth)
- `game_id`: Game identifier
- `quarter`: Quarter number
- `period`: Period label (Q1-Q4 or OT1+)
- `mode`: Game mode (single/tournament/franchise)
- `tournament_id`: Tournament identifier (if applicable)
- `franchise_id`: Franchise identifier (if applicable)
- `week`: Week number (franchise mode)
- Lineup parameters: `home_pg`, `home_sg`, etc.
- `clock`: Clock time (preserved for foul out/timeout)

**Frontend Resilience:**
- Frontend checks database as fallback if URL parameter is missing (`bootGame.js` lines 825-841)
- This provides resilience if URL parameter is lost during navigation
- Helper ensures consistent parameter building even if some params are missing

**Critical Frontend Pattern:**
- All navigation functions read URL params directly from `window.location.search` when called
- Does NOT rely on module-level variables that might be stale (especially after async delays)
- Helper ensures `game_id` and `resume_from_timeout` are always current when navigating
- Prevents params from being lost during navigation chain: lineup → game-plan → court

**Playcall Center Player Image Assignment (SS&S - January 2025):**

Player images in the Playcall Center are assigned once when returning to `court.html` from lineup/game plan screens (all timeout navigation entry points). This ensures stable, predictable behavior.

**When Images Are Set:**
- On `court.html` page load (all game entry/re-entry instances)
- Works for all timeout navigation entry points:
  - Game start / Opening Tip
  - Quarter breaks (Q2-Q4)
  - Timeout breaks (any quarter)
  - Player foul out breaks (any quarter)
  - Overtime breaks

**How Images Are Assigned:**
1. **Read Lineup from URL Params:** Lineup data is preserved by `TimeoutNavigationHelper` in URL params (`home_pg`, `home_sg`, etc. or `away_pg`, `away_sg`, etc.)
2. **Get User Team Side:** From `my_team` URL param ("home" or "away")
3. **Fetch Play Documents:** For each of the 6 offense plays, fetches play document from `/api/play/{play_name}`
4. **Extract Intended Shooter from Skeleton:**
   - Gets successful skeleton from `play.skeletons.successful`
   - Extracts intended shooter position from final step's `pos_actions` where `action == "shoot"`
   - Uses same logic as backend `phase_resolution.py` (lines 1011-1017)
5. **Map Position to Player ID:** Maps intended shooter position to player ID from user's lineup
6. **Set Image Once:** Image path is `/static/images/players/{playerId}.png`
7. **Images Remain Static:** No mid-game changes during gameplay

**Why This Is SS&S:**
- **Single Point of Assignment:** Images set once at timeout navigation return
- **Stable During Gameplay:** Images don't change mid-game (no confusion)
- **Correct Timing:** Lineups are locked at timeout navigation points
- **Clear Data Flow:** Lineup → play skeleton → intended shooter position → player ID → image
- **Works for All Entry Points:** All use `TimeoutNavigationHelper` which preserves lineup params
- **Matches Backend Logic:** Uses same skeleton extraction logic as backend and playcall popup
- **Single Source of Truth:** Uses actual intended shooter from play skeletons, not hardcoded mapping

**Implementation:**
- Location: `FrontEnd/static/court.html` `populatePlayHeadshots()` function (lines 2484-2570)
- Fetches play documents from `/api/play/{play_name}` for each of the 6 offensive plays
- Extracts intended shooter from successful skeleton's final step (same logic as backend)
- Function is async to handle API calls
- Runs on page load (immediate execution)
- Falls back to default image if player image fails to load
- Matches backend logic in `BackEnd/engine/phase_resolution.py` (lines 1004-1020)

#### LocalStorage (Frontend State Only)

**Purpose:** LocalStorage is used for frontend convenience, not business logic.

**Stored Data:**
- `game_id`: Current game identifier (for navigation)
- `game_home`: Home team name (for matchup validation)
- `game_away`: Away team name (for matchup validation)
- `franchise_id`: Franchise identifier (if applicable)
- `franchise_week`: Current week (if applicable)

**New Game Detection:**
- Frontend clears `game_id` from localStorage when starting a new game (`gameScene.js` lines 213-220)
- Prevents stale `game_id` from being passed to backend for new games

**Note:** LocalStorage is not used for timeout state - database is the source of truth.

### Resume Flow

1. **User navigates to lineup screen** (with `resume_from_timeout=true` URL parameter)
   - Navigation uses unified helper (`timeoutNavigationHelper.js`)
   - Helper ensures `game_id` and `resume_from_timeout` are passed correctly
   - Works from any entry point (timeout button, foul out popup)

2. **User makes lineup/game plan changes** (or keeps current settings)
   - Can navigate between Lineup and Game Plan screens
   - Helper preserves all parameters during back navigation
   - All parameters maintained correctly

3. **User navigates back to court** (with `resume_from_timeout=true` flag in URL)
   - Navigation uses unified helper for consistency
   - Helper ensures all parameters are passed correctly

4. **Backend checks database for timeout state** (single source of truth, regardless of URL parameter)
   - Always checks database if `game_id` exists
   - Validates quarter match to prevent stale data
   - Defensively clears `resume_from_timeout` flag if no valid timeout state found

5. **Backend restores timeout state from database:**
   - `timeout_next_play_type` → Always `"SIDE_INBOUND"` (or `"FREE_THROW"`)
   - `timeout_offense_team_id` → Restores possession team
   - `clock` and `time_remaining` → Restores game clock

6. **Backend applies state to GameManager** (whether in memory or newly loaded)
   - Uses `apply_timeout_resume_state_to_gm()` helper
   - Works for both in-memory and newly-loaded games

7. **Backend creates SIP turn** with correct possession team
   - Uses `timeout_offense_team_id` to ensure correct team has possession
   - SIP transitions to HCO (defense calls play)

8. **Backend clears timeout state from database** (defensive cleanup)
   - Uses `$unset` to remove `timeout_next_play_type` and `timeout_offense_team_id`
   - Prevents stale timeout state from affecting future games

9. **Frontend auto-starts game** (bypasses pre-game buttons)
   - Game continues seamlessly

10. **Game continues** with SIP → HCO transition

### Unified Timeout Resume Architecture (Structural Fix - January 2025)

The timeout resume system uses a unified architecture that works consistently across all game modes and memory states.

**Core Principle:** Always use the database as the single source of truth for timeout state, regardless of whether the game is in memory or not.

**Two Helper Functions:**

1. **`restore_timeout_resume_state()`** (`BackEnd/api/api.py` lines 296-395)
   - Loads timeout state from the correct document location based on game mode
   - **Single Game**: `games_collection` document
   - **Tournament Game**: Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
   - **Franchise Game**: Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)
   - Validates that `timeout_next_play_type` exists in saved document
   - Returns saved document with timeout state, or `None` if not found

2. **`apply_timeout_resume_state_to_gm()`** (`BackEnd/api/api.py` lines 397-430)
   - Applies restored state to GameManager instance
   - Restores `timeout_next_play_type` to `gm.game_state`
   - Restores `timeout_offense_team_id` and flips possession if needed
   - Restores `clock` and `time_remaining`
   - Works for both in-memory and newly-loaded games

**Unified Flow (`BackEnd/api/api.py` `simulate_quarter_endpoint()`):**

```python
# Step 1: Always check database for timeout state if game_id exists
# Don't skip Q1 - we could be resuming from a timeout in Q1!
# The database is the source of truth - if timeout_next_play_type exists, we're resuming
if game_id:
    # Step 2: Load timeout state from database (single source of truth)
    timeout_saved_state = restore_timeout_resume_state(game_id, request, games_collection)
else:
    timeout_saved_state = None  # No game_id = brand new game

# Step 3: Validate and apply timeout state (if found)
if timeout_saved_state:
    # Validate quarter match to prevent stale data from affecting new games
    saved_quarter = timeout_saved_state.get("quarter", 0)
    timeout_next_play_type = timeout_saved_state.get("timeout_next_play_type")
    
    if timeout_next_play_type and saved_quarter == request.quarter:
        # Valid timeout state - apply it
        request.resume_from_timeout = True
        if gm is not None:
            # Step 4a: Apply to in-memory game (if exists)
    apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
        # Step 4b: If game not in memory, will apply after DB load (see Step 6)
    else:
        # Stale timeout data (quarter mismatch) - ignore it
        timeout_saved_state = None

# Step 5: If game not in memory, load from DB
if gm is None:
    # ... load game from DB ...
    # Step 6: Apply timeout state to newly loaded game (if found and valid)
    if timeout_saved_state:
        # Quarter validation already done in Step 3
        apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
        request.resume_from_timeout = True

# Step 7: Continue with simulate_quarter()
simulate_quarter(gm, ..., resume_from_timeout=request.resume_from_timeout)
```

**Key Benefits:**
- **Single code path** for all modes (single, tournament, franchise)
- **Works regardless of memory state** (game in memory or not)
- **Works for all quarters** (including Q1 timeout resumes, even if game was evicted from memory)
- **Mode-specific document access** (checks correct location for each mode)
- **Less fragile** (no assumptions about memory state or quarter)
- **Consistent behavior** across all game modes
- **New game protection** (only checks timeout state if game_id exists)
- **Stale data prevention** (validates quarter match before using timeout state)

**Mode-Specific Document Access:**

The system automatically determines the correct document location:

- **Single Mode**: Checks `games_collection` only
- **Tournament Mode**: Checks nested structure first (`tournaments.games.{round}.{game_id}`), then falls back to `games_collection`
- **Franchise Mode**: Checks nested structure first (`franchises.games.week_{week}.{game_id}`), then falls back to `games_collection`

This ensures timeout state is found regardless of where the game document is stored, while maintaining the database as the single source of truth.

**Timeout State Cleanup:**

After resuming from timeout, the system clears timeout state from both memory and database:

```python
# Clear from memory
gm.game_state.pop("timeout_next_play_type", None)
gm.game_state.pop("timeout_offense_team_id", None)

# Clear from database (defensive cleanup)
games_collection.update_one(
    {"_id": game_id},
    {"$unset": {"timeout_next_play_type": "", "timeout_offense_team_id": ""}}
)
```

This prevents stale timeout state from affecting future games.

### Scoreboard Display Immediacy System

**Problem:** Scoreboard items (scores, fouls, timeouts, clock) need to display immediately when resuming from timeout, not wait for the next turn to complete.

**Solution:** Direct DOM updates with team object priority.

**Initial Value Extraction (`FrontEnd/static/js/phaser/gameScene.js`):**

All scoreboard items check team objects first (authoritative source), then fall back to game object:

```javascript
// Scores: Check team objects first (same pattern as timeouts)
const homeScoreFromData = homeTeamObj?.score ?? simData.score?.[homeTeam];
const awayScoreFromData = awayTeamObj?.score ?? simData.score?.[awayTeam];

// Fouls: Check team objects first (same pattern as timeouts)
const homeFoulsFromData = homeTeamObj?.team_fouls ?? simData.fouls?.home;
const awayFoulsFromData = awayTeamObj?.team_fouls ?? simData.fouls?.away;

// Timeouts: Check team objects first (already working)
const homeTimeoutsFromData = homeTeamObj?.timeouts ?? simData.timeouts?.home ?? simData.home_team_timeouts;
const awayTimeoutsFromData = awayTeamObj?.timeouts ?? simData.timeouts?.away ?? simData.away_team_timeouts;
```

**Immediate DOM Update (`FrontEnd/static/js/phaser/gameScene.js` `updateScoreboard()`):**

All scoreboard items use direct DOM manipulation (consistent pattern):

```javascript
// Direct DOM updates for all scoreboard items (consistent pattern)
if (homeScoreEl) homeScoreEl.textContent = liveScore[homeTeam];
if (awayScoreEl) awayScoreEl.textContent = liveScore[awayTeam];
if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
if (homeTolEl) homeTolEl.textContent = `TOL: ${liveHomeTimeouts}`;
if (awayTolEl) awayTolEl.textContent = `TOL: ${liveAwayTimeouts}`;
if (clockEl) clockEl.textContent = liveClock;
if (quarterEl) quarterEl.textContent = livePeriodLabel;
```

**Initial Call (`FrontEnd/static/js/phaser/gameScene.js`):**

When resuming from timeout, `updateScoreboard()` is called with initial values:

```javascript
updateScoreboard({
    score: liveScore,
    homeFouls: liveHomeFouls,
    awayFouls: liveAwayFouls,
    homeTimeouts: liveHomeTimeouts,
    awayTimeouts: liveAwayTimeouts,
    clock: liveClock,
    quarter: liveQuarter,
    period_label: livePeriodLabel,
});
```

**Why Team Objects First?**

Turn data provides values from team objects:
- `turn.homeFouls` = `self.game.home_team.team_fouls` (from team object)
- `turn.home_team_timeouts` = `getattr(gm.home_team, 'timeouts', 5)` (from team object)
- `turn.score` = `game.score.get(team_name, 0)` (from game object, but team objects also have `score`)

Checking team objects first ensures consistency with how turn data provides these values.

### Lineup and Game Plan Pre-Population

**Lineup Pre-Population:**

When navigating to the lineup screen during a timeout, the current lineup is fetched and pre-populated:

**Backend (`BackEnd/api/api.py` `/api/game/{game_id}/lineup` endpoint):**
```python
@app.get("/api/game/{game_id}/lineup")
def get_game_lineup(game_id: str):
    # Returns current lineups for both teams
    return {
        "home_lineup": gm.home_lineup,
        "away_lineup": gm.away_lineup
    }
```

**Frontend (`FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()`):**
```javascript
// Fetch current lineup for both teams
const lineupResponse = await fetch(`/api/game/${gameId}/lineup`);
const lineupData = await lineupResponse.json();
homeLineup = lineupData.home_lineup || {};
awayLineup = lineupData.away_lineup || {};

// Add lineup params to URL
Object.entries(homeLineup).forEach(([pos, playerId]) => {
    params.set(`home_${pos.toLowerCase()}`, playerId);
});
Object.entries(awayLineup).forEach(([pos, playerId]) => {
    params.set(`away_${pos.toLowerCase()}`, playerId);
});
```

**Frontend (`FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`):**
```javascript
function restoreLineupFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
    
    positions.forEach(pos => {
        const homeId = urlParams.get(`home_${pos.toLowerCase()}`);
        const awayId = urlParams.get(`away_${pos.toLowerCase()}`);
        if (homeId) {
            // Pre-populate home lineup slot
            document.querySelector(`#home-${pos.toLowerCase()}`).value = homeId;
        }
        if (awayId) {
            // Pre-populate away lineup slot
            document.querySelector(`#away_${pos.toLowerCase()}`).value = awayId;
        }
    });
}
```

**Game Plan Pre-Population:**

Current game plan settings are fetched and passed to the game plan screen:

**Frontend (`FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()`):**
```javascript
// Fetch current game plan settings for the user's team
const gpResponse = await fetch(`/api/gameplan?${gpParams.toString()}`);
gamePlanSettings = await gpResponse.json();

// Add game plan settings to URL
if (gamePlanSettings) {
    params.set('game_plan_settings', JSON.stringify(gamePlanSettings));
}
```

**Frontend (`FrontEnd/static/game-plan.js` `loadSettings()`):**
```javascript
function loadSettings() {
    const urlParams = new URLSearchParams(window.location.search);
    const gamePlanSettingsParam = urlParams.get('game_plan_settings');
    
    if (gamePlanSettingsParam) {
        // Parse and apply game plan settings from URL
        const settings = JSON.parse(gamePlanSettingsParam);
        // Apply settings to form
    }
}
```

### Timeout Button Functionality

**Feature Flag:**

The timeout button is controlled by a feature flag for easy enabling/disabling:

**Location:** `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`

```javascript
const ENABLE_TIMEOUT_BUTTON = true; // Feature flag for modularity
```

**Button State:**

- **Live:** Button is enabled and clickable (during 2.5-second pause window)
- **Dead:** Button is disabled with reduced opacity (all other times)

**Button Initialization:**

```javascript
function initTimeoutButton() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        // Hide button if feature is disabled
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) return;
    
    // Set initial state (dead)
    updateTimeoutButtonState(false, 'Initial state');
    
    // Attach click listener
    button.addEventListener('click', handleTimeoutButtonClick);
}
```

**2.5-Second Pause Window:**

The timeout button is live during a mandatory 2.5-second pause at the start of SIP and BIP turns:

**Location:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`

```javascript
// In runSideInboundSetup() and runInboundSetup()
if (ENABLE_TIMEOUT_BUTTON && isTimeoutEligible) {
    // Start 2.5-second pause (button becomes live immediately)
    await startTimeoutPause(scene);
    
    // Position players (happens in parallel with pause)
    await Promise.all(playerPromises);
    
    // Mark players positioned (if pause already complete, button stays live)
    markPlayersPositioned();
    
    // Mark inbound pass started (button becomes dead, hide progress bar)
    markInboundPassStarted();
}
```

**Progress Bar:**

A visual countdown progress bar appears during the 2.5-second pause:

- **Appearance:** Orange fill with green border
- **Animation:** Starts full width, reduces proportionally to time remaining
- **Visibility:** Only visible when button is live

**Timeout Eligibility:**

The button is live for all SIP and BIP turns if:
- The turn is a SIP or BIP turn
- The team has timeouts remaining (checked via `/api/call-timeout` endpoint)

**Timeout Button Click Handler:**

```javascript
async function handleTimeoutButtonClick() {
    // Get game context from scene
    const gameId = scene.gameId || scene.simData?.game_id;
    const myTeamSide = scene.userTeamSide || urlParams.get('my_team');
    
    // Call timeout API
    const response = await fetch('/api/call-timeout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            game_id: gameId,
            calling_team: myTeamSide, // 'home' or 'away'
        }),
    });
    
    // Navigate to lineup screen
    await showTimeoutPopup(result, gameId, scene);
}
```

**Animation Freezing:**

When timeout button is pressed, all animations are immediately paused:

**Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

```javascript
async handleTimeout(turnData, context) {
    // Pause all tweens immediately when timeout is called
    if (this.scene.tweens) {
        this.scene.tweens.pauseAll();
    }
    // Set flag to stop the main animation loop
    this.scene.timeoutCalled = true;
    
    // Show timeout popup and navigate to lineup screen
    await showTimeoutPopup(timeoutResult, gameId, this.scene);
}
```

**Location:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

```javascript
if (turn.result_type === "TIMEOUT") {
    turn.index = i;
    await animationRouter.processTurn(turn);
    console.log('⏸️ TIMEOUT: Stopping animation loop');
    break; // Exit the loop - don't process any more turns
}
```

### Comparison: Timeout vs Quarter Break vs Foul Out

**Similarities:**

All three flows use the same core systems:
- **Data Persistence:** Same `summarize_game_state()` and database save/load pattern
- **Resume Flow:** Same `resume_from_timeout` / `resume_from_foul_out` flag pattern
- **Auto-Start:** Same pre-game button bypass logic
- **State Restoration:** Same game state restoration from database
- **Lineup Pre-Population:** Same lineup fetching and URL parameter passing

**Differences:**

| Feature | Timeout | Quarter Break | Foul Out |
|---------|---------|--------------|----------|
| **Turn Type** | `TIMEOUT` | `BASELINE_INBOUND` | `TIMEOUT` (with `timeout_reason="FOUL_OUT"`) |
| **Next Turn** | SIP (default) | BIP (quarter start) | SIP (default) |
| **Timeout Count** | Reduced by 1 | Not affected | Not affected |
| **User Initiation** | User presses button | Automatic (quarter ends) | Automatic (player fouls out) |
| **Animation Freeze** | Yes (immediate pause) | No (seamless transition) | Yes (immediate pause) |
| **Pre-Game Buttons** | Hidden (auto-start) | Hidden (auto-start) | Hidden (auto-start) |
| **Initial Turn Creation** | In `simulate_quarter()` | In `simulate_quarter()` | In `simulate_quarter()` |
| **Offensive State Reset** | Yes (reset to HCO for SIP) | No (preserved) | Yes (reset to HCO for SIP) |

**Key Implementation Details:**

1. **Timeout Resume:**
   - Clears `gm.turns` before creating SIP turn (prevents old turns from being returned)
   - Resets `offensive_state` to `"HCO"` (prevents FCP/HCT from carrying over)
   - Creates SIP turn directly in `simulate_quarter()` (same pattern as quarter breaks create BIP turns)

2. **Quarter Break:**
   - Creates BIP turn directly in `simulate_quarter()` (quarter start logic)
   - Preserves `offensive_state` (defensive pressure can carry over to quarter start)
   - No timeout count reduction

3. **Foul Out:**
   - Same as timeout (creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`)
   - No timeout count reduction
   - Includes `foul_out_player` data in timeout turn payload

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` `setup_timeout_turn()`: Creates timeout turn payload
- `BackEnd/models/game_manager.py` `determine_next_turn()`: Routes TIMEOUT → next turn
- `BackEnd/api/api.py` `call_timeout_endpoint()`: Handles user-initiated timeouts
- `BackEnd/api/api.py` `simulate_quarter_endpoint()`: Handles timeout resume flow
- `BackEnd/main.py` `simulate_quarter()`: Creates initial turn after timeout resume
- `BackEnd/utils/shared.py` `summarize_game_state()`: Saves game state to database

**Frontend:**
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`: Timeout button logic and state management
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleTimeout()`: Handles timeout turn
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`: Stops animation loop on timeout
- `FrontEnd/static/js/phaser/gameScene.js`: Scoreboard immediate update logic
- `FrontEnd/static/js/phaser/bootGame.js`: Auto-start logic for timeout resume
- `FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`: Pre-populates lineup from URL
- `FrontEnd/static/game-plan.js` `loadSettings()`: Pre-populates game plan from URL
- `FrontEnd/static/court.html`: Timeout button and progress bar HTML/CSS

**Tests:**
- `tests/test_timeout_functionality.py`: Comprehensive tests for timeout system

---

## Playcall Center ✅ **ACTIVE** (January 2025)

### Overview

The Playcall Center is a unified tactical hub displayed at the bottom of the court screen (`court.html`). It provides real-time visualization of offensive and defensive play calls, user override controls, and a dynamic lean meter that visualizes the effectiveness of the offensive play against the defensive setup.

**Location:** Fixed position at bottom of court screen, between left and right side panels  
**Purpose:** Display tactical information, enable user playcall overrides, and provide visual feedback on play effectiveness

### Structure

The Playcall Center consists of three main components:

#### 1. Top Row: Status Displays

**Offense Status:**
- Format: `"Motion → Inside"` or `"Set → Attack"`
- Shows offensive play type (Motion/Set) and focus (Inside/Attack/Outside)
- Updated from `turnData.offensive_play_type` and `turnData.offensive_play_focus`
- Displays the actual playcall being executed in the current turn

**Defense Status:**
- Format: `"Man Normal"` or `"2-3 Zone Normal"`
- Shows defensive playcall (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone) and aggression level
- Updated from `turnData.defensive_playcall` (or `defensive_play_type`) and `turnData.aggression`
- Displays the actual defensive setup being used in the current turn

#### 2. Main Row: Three-Column Layout

**Left Panel: Offense Tactical Panel**
- **Title:** "OFFENSE OVERRIDE"
- **Play Scroller:** Displays 6 offensive play options:
  - 4-1 Motion (Inside focus)
  - 3-2 Motion (Attack focus)
  - 5-0 Motion (Outside focus)
  - Base Post Play (Inside focus)
  - Pick & Roll (Lower Wing) (Attack focus)
  - Double Screen For SG (Outside focus)
- **Player Headshots:** Each play displays a player headshot image assigned based on play focus and user's lineup
- **Navigation Buttons:** Up/down arrows to scroll through plays
- **Clear Override Button:** Removes any selected offense override
- **Selection State:** Selected plays are highlighted with `selected` class

**Center: Lean Meter**
- Visual indicator of play effectiveness
- Yellow center line at 50% (neutral position)
- Green fill (positive) fills upward from center line
- Red fill (negative) fills downward from center line
- Animated during turn execution at the middle step
- See "Lean Meter Animation System" below for detailed mechanics

**Right Panel: Defense Tactical Panel**
- **Title:** "DEFENSE OVERRIDE"
- **Defense Type Buttons:**
  - MAN button (Man-to-Man defense)
  - ZONE button (Zone defense - backend converts to specific zone types)
- **Aggression Buttons:**
  - PASSIVE button
  - NORMAL button
  - AGGRESSIVE button
- **Clear Override Button:** Removes any selected defense override
- **Selection State:** Selected buttons are highlighted with `selected` class

### Lean Meter Animation System

The lean meter provides real-time visual feedback on how well the offensive play is executing against the defensive setup.

#### Lean Score Range

**Range:** -1.0 to +1.0
- **+1.0**: Maximum positive (offense executing perfectly) → Full green fill upward (50% of container)
- **+0.5 to +0.99**: Positive (play working well) → Partial green fill
- **0.0**: Neutral (balanced) → No fill, just yellow center line
- **-0.5 to -0.01**: Negative (defense engaged) → Partial red fill downward
- **-1.0**: Maximum negative (defense disrupting) → Full red fill downward (50% of container)

#### Animation Timing

**Trigger Point:** Middle step of turn animation
- Lean score is parsed from turn `text` field (pattern: `"lean:X.XX"`)
- Middle step is calculated as `Math.ceil(maxSteps / 2)`
- Animation triggers during step loop execution

**Animation Systems:**
- **Shot Turns:** Triggered in `ShotAnimationSystem.js` step loop (line 324-340)
- **Other Turns:** Triggered in `turnAnimation.js` step loop (line 1813-1823)

#### Fill Calculation

The lean meter fills proportionally based on the lean score value:

**Positive Scores (Green Fill Upward):**
```javascript
fillPercentage = Math.abs(leanScore) * 50; // 0-50% of container
// Example: 0.47 → 23.5% fill (47% of the space from center to top)
```

**Negative Scores (Red Fill Downward):**
```javascript
fillPercentage = Math.abs(leanScore) * 50; // 0-50% of container
// Example: -0.88 → 44% fill (88% of the space from center to bottom)
```

**CSS Positioning:**
- Green fill: `bottom: 50%` (anchored at center, grows upward)
- Red fill: `top: 50%` (anchored at center, grows downward)
- Both fills start at the yellow center line (50% vertical position)

#### Data Flow

1. **Backend Calculation:**
   - `generate_logic()` in `BackEnd/engine/phase_resolution.py` calculates lean score
   - Currently returns random value (-1 to 1) as placeholder
   - Lean score is embedded in turn `text` field: `"lean:0.96"`

2. **Frontend Parsing:**
   - `parseLeanScoreFromText()` in `playcallCenter.js` extracts lean score from text
   - Pattern: `/lean:([-+]?\d+\.?\d*)/`
   - Returns `null` if not found

3. **Preparation (Turn Start):**
   - `prepareTurnForAnimation()` in `turnPreparation.js` parses lean score
   - Calculates middle step: `Math.ceil(maxSteps / 2)`
   - Stores in `scene._leanScoreToAnimate` and `scene._leanAnimationStep`
   - Resets lean meter to neutral (yellow line only)

4. **Animation Trigger (Middle Step):**
   - During step loop, checks if `stepIndex === scene._leanAnimationStep`
   - Calls `animateLeanMeter(leanScore)` from `playcallCenter.js`
   - Sets `scene._leanAnimationTriggered = true` to prevent duplicate triggers

5. **Visual Update:**
   - `animateLeanMeter()` calculates fill percentage
   - Updates CSS `height` property of fill elements
   - Smooth transition via CSS: `transition: height 0.8s ease-out`

### User Override System (SS&S - January 2025)

The Playcall Center allows users to override playcalls for their team. Overrides persist until used, then are automatically cleared.

#### Override Types

**Offense Override:**
- User selects one of 6 offensive plays from the play scroller
- Stored in `team.strategy_calls["offense_call"]` as play name string (e.g., "3-2 Motion")
- Applied when user's team is on offense during next HCO turn
- Cleared automatically after use (set to `None`)

**Defense Override:**
- User selects defense type (Man or Zone) and aggression level (Passive/Normal/Aggressive)
- Stored in `team.strategy_calls["defense_call"]` as "Man" or "Zone"
- Backend converts generic "Zone" to specific zone types (2-3 Zone, 3-2 Zone, 1-3-1 Zone) based on team preferences
- Applied when user's team is on defense during next HCO turn
- Cleared automatically after use (set to `None`)

**Aggression Override:**
- User selects aggression level (Passive/Normal/Aggressive)
- Stored in `team.strategy_calls["aggression_override"]`
- Applied to defensive playcalls when user's team is on defense

**Tempo Override:**
- User selects tempo level (Slow/Normal/Fast)
- Stored in `team.strategy_calls["tempo_override"]`
- Applied to offensive playcalls when user's team is on offense

#### Data Structure

**Backend Storage (`team.strategy_calls`):**
```python
{
    "offense_call": None | str,          # Play name or None (persists until used)
    "defense_call": None | str,          # "Man", "Zone", or None (persists until used)
    "aggression_override": None | str,   # "normal", "aggressive", "passive", or None
    "tempo_override": None | str,        # "slow", "normal", "fast", or None
    "press_override": None,               # Future: FCP override
    "trap_override": None                 # Future: HCT override
}
```

**Initialization:**
- `TeamManager.__init__()` initializes `strategy_calls` with all fields set to `None`
- Default state: No overrides active (normal play selection logic used)

#### Override Application Flow

1. **User Selection (Frontend):**
   - User clicks play option or defense button in Playcall Center
   - Frontend calls `setPlaycallOverride()` function in `court.html`
   - Function sends POST request to `/api/set-playcall-override`

2. **API Endpoint (`/api/set-playcall-override`):**
   - Receives `PlaycallOverrideRequest` with `game_id`, `user_team_side`, and override values
   - Identifies user team from `user_team_side` ("home" or "away")
   - Updates `team.strategy_calls` with override values
   - Returns success status and current override state

3. **Backend Playcall Selection (`set_playcalls()` in `turn_manager.py`):**
   - Called during HCO turn setup
   - Checks if user team is on offense/defense using `is_user_team` flag
   - If `team.strategy_calls["offense_call"] != None` and user team is on offense:
     - Uses override playcall instead of normal selection
     - Clears override after use: `team.strategy_calls["offense_call"] = None`
   - If `team.strategy_calls["defense_call"] != None` and user team is on defense:
     - Uses override defense (converts "Zone" to specific zone type if needed)
     - Clears override after use: `team.strategy_calls["defense_call"] = None`

4. **Frontend Highlight Management:**
   - Selected buttons receive `selected` class (visual highlight)
   - `updatePlaycallCenter()` checks if turn's playcall matches selected button
   - If match found, removes `selected` class (unhighlights after use)
   - `clearPlaycallHighlights()` can manually clear all highlights

#### Override Persistence

**Current State:**
- Overrides stored in `team.strategy_calls` (in-memory only)
- Lost on server restart or game reload
- **Note:** Database persistence was attempted but reverted due to breaking changes

**Future Enhancement:**
- Persist `strategy_calls` to database in `summarize_game_state()`
- Restore `strategy_calls` when loading games from database
- Ensure overrides survive server restarts and game reloads

#### Override Timing

**When Overrides Are Applied:**
- Only during HCO (Half Court Offense) turns
- Not applied during: FREE_THROW, BASELINE_INBOUND, FCP, HCT, or SIDE_INBOUND turns
- Override persists until next HCO turn where user team is on offense/defense

**User Team Detection:**
- Backend uses `is_user_team` flag on `TeamManager` objects
- Flag set during `GameManager` initialization from `user_team_side` parameter
- Ensures overrides only apply to user's team, not computer team

### Player Image Assignment System

Player headshots in the Playcall Center are assigned once when returning to `court.html` from lineup/game plan screens. The system uses the same logic as the backend to extract the intended shooter from each play's successful skeleton.

**Process (SS&S - January 2025):**

1. **Page Load:** `populatePlayHeadshots()` runs on `court.html` page load (all timeout navigation entry points)

2. **Fetch Play Documents:** For each of the 6 offensive plays, fetches the play document from `/api/play/{play_name}`

3. **Extract Intended Shooter from Skeleton:**
   - Gets the successful skeleton from `play.skeletons.successful` (same as backend: `get_hco_skeleton(None, game, lean_score=1.0)`)
   - Extracts intended shooter position from the final step's `pos_actions` where `action == "shoot"`
   - Uses the same logic as backend `phase_resolution.py` (lines 1011-1017)

4. **Map Position to Player ID:**
   - Reads user's lineup from URL parameters (preserved by `TimeoutNavigationHelper`)
   - Maps the intended shooter position (C, PG, SG, SF, PF) to the corresponding player ID from the lineup
   - Uses `my_team` parameter to determine which lineup to use (home or away)

5. **Set Image:** Sets the headshot image using the player ID: `/static/images/players/{playerId}.png`

**Key Points:**
- Images assigned on page load for all timeout navigation entry points
- Uses actual intended shooter from play skeletons (not hardcoded focus-to-position mapping)
- Matches backend logic and playcall popup behavior
- Uses lineup data from URL parameters (preserved by `TimeoutNavigationHelper`)
- Images remain static during gameplay (no mid-game changes)
- Function is async to handle API calls to fetch play documents
- Location: `FrontEnd/static/court.html` `populatePlayHeadshots()` function (lines 2484-2570)

**Why This Is SS&S:**
- **Single Source of Truth:** Uses the same skeleton data and extraction logic as the backend
- **Consistency:** Playcall Center images match the playcall popup (both use intended shooter from skeleton)
- **Accuracy:** Shows the actual intended shooter for each play, not a heuristic based on play focus
- **Maintainability:** If skeleton data changes, both backend and frontend automatically reflect the change

### Key Files

**Frontend:**
- `FrontEnd/static/court.html`: 
  - Playcall Center HTML structure and CSS (lines 785-1109, 2241-2342)
  - Override button event handlers (lines 2572-2600)
  - `populatePlayHeadshots()` function (lines 2481-2561)
  - `setPlaycallOverride()` function (lines 2544-2600)
- `FrontEnd/static/js/phaser/ui/playcallCenter.js`: Core Playcall Center logic
  - `updatePlaycallCenter()`: Updates status displays, manages highlights, triggers playcall reveal HUD
  - `clearPlaycallHighlights()`: Removes `selected` class from all override buttons
  - `resetLeanMeter()`: Resets meter to neutral
  - `animateLeanMeter()`: Animates meter based on lean score
  - `parseLeanScoreFromText()`: Extracts lean score from turn text
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`: Prepares lean meter animation (lines 66-87)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`: Triggers animation for non-shot turns (lines 1813-1823)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`: Triggers animation for shot turns (lines 324-340)

**Backend:**
- `BackEnd/api/api.py`:
  - `/api/set-playcall-override` endpoint (lines 1703-1764): Receives and stores user overrides
  - `PlaycallOverrideRequest` model (lines 119-127): Request structure for overrides
- `BackEnd/models/turn_manager.py`:
  - `set_playcalls()` (lines 858-1033): Checks and applies user overrides during playcall selection
  - `set_strategy_calls()` (lines 310-370): Generates strategy calls for turn
- `BackEnd/models/team_manager.py`:
  - `TeamManager.__init__()` (lines 50-58): Initializes `strategy_calls` structure
- `BackEnd/engine/phase_resolution.py`: 
  - `generate_logic()`: Calculates lean score (line 794-870)
  - Embeds lean score in turn text (line 1061): `f"lean:{lean_score:.2f}"`

### Future Enhancements

- **Database Persistence:** Restore `strategy_calls` persistence to database (reverted due to breaking changes)
- **Real Lean Score Logic:** Replace placeholder random calculation with actual tactical evaluation
- **Skeleton Variant Selection:** Use lean score to select appropriate skeleton variant (successful, mid_play_change, contested, broken)
- **Specific Zone Selection:** Allow users to select specific zone types (2-3 Zone, 3-2 Zone, 1-3-1 Zone) instead of generic "Zone"
- **Visual Refinements:** Additional styling, animations, or indicators
- **Historical Tracking:** Display lean score trends over time
- **Press/Trap Overrides:** Implement FCP and HCT override functionality

---

### 4. `handleTurnover()`
**Registered for:** `TURNOVER`  
**Location:** `AnimationEngine.js` line 369  
**What it does:**
- Routes to `turnoverAdapter.js` `handleTurnover()` function
- Handles turnover animations and possession changes

**Key Features:**
- Delegates to specialized turnover handler
- Handles possession flips

---

### 5. `handleFastBreak()`
**Registered for:** `FAST_BREAK`  
**Location:** `AnimationEngine.js` line 381  
**What it does:**
- Updates active player display (ball handler and defender)
- Routes to `runFastBreakSequence()` for fast break animations
- Sets `scene._previousTurnWasShot = true` if turn is a shot (MAKE/MISS)

**Key Features:**
- Active player display update
- Fast break sequence execution
- Shot flag setting for next turn

---

### 6. `handlePutback()`
**Registered for:** `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`  
**Location:** `AnimationEngine.js` line 410  
**What it does:**
- Routes to `handleOrebTurn()` function (from `animateGameTurns.js`)
- Handles putback shot attempts and OREB kickout passes

**Key Features:**
- Delegates to specialized OREB handler
- Handles PUTBACK_MAKE, PUTBACK_MISS, and OREB_KICKOUT
- Includes shot animations, rebounds, and inbound setups

---

### 7. `handleOpeningTip()`
**Registered for:** `OPENING_TIP`  
**Location:** `AnimationEngine.js` line 429  
**What it does:**
- Validates opening tip timing (Q1 start or OT start only)
- Routes to `runOpeningTipSequence()` for opening tip animations
- Transitions state machine to `HalfCourt` after completion

**Key Features:**
- Timing validation (prevents mid-game opening tips)
- Opening tip sequence execution
- State machine transition

---

### 8. `handleDefensiveStop()`
**Registered for:** `DEFENSIVE_STOP`  
**Location:** `AnimationEngine.js` line 474  
**What it does:**
- Checks if Fast Break defensive stop (routes to `runFastBreakSequence()`) or standard defensive stop (routes to `runDefensiveStopTransition()`)
- Appends text scroll with defensive stop message

**Key Features:**
- Fast Break vs standard defensive stop routing
- Defensive stop transition animations
- Text scroll append

---

### 9. `handleSteal()`
**Registered for:** `STEAL`  
**Location:** `AnimationEngine.js` line 509  
**What it does:**
- Checks FastBreak state (skips if in FastBreak)
- Executes pass animation from ball handler to stealer using `runPass()`
- Emits `possessionChange` event after pass completes

**Key Features:**
- FastBreak state check
- Steal pass animation
- Possession change emission

---

### 10. `handleShotAttempt()`
**Registered for:** `SHOT_ATTEMPT` (detected via `isShotAttempt()`)  
**Location:** `AnimationEngine.js` line 565  
**What it does:**
- Routes to `ShotAnimationSystem.processShot()` (if available) or falls back to `playTurnAnimation()`
- Handles HCO and FCP/HCT shot attempts (MAKE/MISS)

**Key Features:**
- Shot animation system integration
- Player movement, ball flight, and rebound handling
- Fallback to legacy `playTurnAnimation()`

**Used by:**
- HCO shots (MAKE/MISS)
- FCP/HCT shots (MAKE/MISS) - when routed through AnimationRouter

---

### 11. `handleRebound()`
**Registered for:** `REBOUND` (detected via `isRebound()`)  
**Location:** `AnimationEngine.js` line 599  
**What it does:**
- Routes to `ReboundAnimationSystem.processRebound()` (if available) or falls back to `playTurnAnimation()`
- Handles rebound animations

**Key Features:**
- Rebound animation system integration
- Fallback to legacy `playTurnAnimation()`

**Status:** Handler exists but `ReboundAnimationSystem` may not be fully implemented yet

---

### 12. `handlePass()`
**Registered for:** `PASS` (detected via `isPass()`)  
**Location:** `AnimationEngine.js` line 629  
**What it does:**
- Routes to `PassAnimationSystem.processPass()` (if available) or falls back to `playTurnAnimation()`
- Handles pass animations

**Key Features:**
- Pass animation system integration
- Fallback to legacy `playTurnAnimation()`

**Status:** Handler exists but `PassAnimationSystem` may not be fully implemented yet

---

### 13. `handleDefault()`
**Registered for:** `HCO`, `DEFAULT`  
**Location:** `AnimationEngine.js` line 653  
**What it does:**
- Routes to `playTurnAnimation()` for HCO setup turns and other default animations
- Used as fallback for turn types without specific handlers

**Key Features:**
- Default handler for unhandled turn types
- HCO setup turn execution
- Delegates to `playTurnAnimation()`

**Used by:**
- HCO setup turns (`result_type === "HCO"` but not MAKE/MISS)
- FCP/HCT fouls (with animations)
- Any turn type without a specific handler

---

## Handler Summary Table

| Handler | Registered For | Primary Function | System Used | Fallback |
|---------|---------------|------------------|-------------|----------|
| `handleFreeThrow()` | `FREE_THROW` | Free throw sequences | `FreeThrowAnimationSystem` | `runFreeThrowSequence()` |
| `handleSideInbound()` | `SIDE_INBOUND` | Side inbound passes | `PassAnimationSystem` | `runSideInboundSetup()` |
| `handleBaselineInbound()` | `BASELINE_INBOUND` | Baseline inbound passes | Direct implementation | None |
| `handleTurnover()` | `TURNOVER` | Turnover animations | `turnoverAdapter.js` | None |
| `handleFastBreak()` | `FAST_BREAK` | Fast break sequences | `runFastBreakSequence()` | None |
| `handlePutback()` | `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT` | Putback shots and OREB kickouts | `handleOrebTurn()` | None |
| `handleOpeningTip()` | `OPENING_TIP` | Opening tip sequences | `runOpeningTipSequence()` | None |
| `handleDefensiveStop()` | `DEFENSIVE_STOP` | Defensive stop transitions | `runFastBreakSequence()` or `runDefensiveStopTransition()` | None |
| `handleSteal()` | `STEAL` | Steal pass animations | `runPass()` | None |
| `handleShotAttempt()` | `SHOT_ATTEMPT` (detected) | Shot attempts (MAKE/MISS) | `ShotAnimationSystem` | `playTurnAnimation()` |
| `handleRebound()` | `REBOUND` (detected) | Rebound animations | `ReboundAnimationSystem` | `playTurnAnimation()` |
| `handlePass()` | `PASS` (detected) | Pass animations | `PassAnimationSystem` | `playTurnAnimation()` |
| `handleDefault()` | `HCO`, `DEFAULT` | Default/fallback handler | `playTurnAnimation()` | None |

---

## Handler Responsibilities

**What Handlers Do:**
- ✅ Execute turn-specific animation logic
- ✅ Handle active player display updates (where applicable)
- ✅ Execute animation sequences (player movement, ball flight, etc.)
- ✅ Handle state transitions (where applicable)
- ✅ Append text scroll (where applicable)
- ✅ Set scene flags (where applicable)

**What Handlers DON'T Do (Handled by AnimationRouter):**
- ❌ Pre-turn setup (`prepareTurnForAnimation()`)
- ❌ Post-turn finalization (`finalizeTurnAfterAnimation()`)
- ❌ Announcements (`announceFromTurnData()`)
- ❌ Score updates (`onUpdate()`)
- ❌ Debug score updates (`updateDebugScore()`)
- ❌ Turn queuing and concurrency management

**Exception:** Some handlers (like `handleFreeThrow()`) append text scroll directly because the logic was moved from `animateGameTurns.js` during migration.

---

## Handler Registration Order

Handlers are registered in this order (in `initializeDefaultHandlers()`):
1. `FREE_THROW`
2. `SIDE_INBOUND`
3. `BASELINE_INBOUND`
4. `TURNOVER`
5. `FAST_BREAK`
6. `SHOT_ATTEMPT`
7. `REBOUND`
8. `PASS`
9. `HCO`
10. `DEFAULT`
11. `PUTBACK_MAKE`
12. `PUTBACK_MISS`
13. `OREB_KICKOUT`
14. `OPENING_TIP`
15. `DEFENSIVE_STOP`
16. `STEAL`

**Note:** Registration order doesn't matter for routing (handlers are stored in a Map), but it's listed here for reference.

---

## Handler Routing Logic

**How `AnimationEngine.determineHandler()` Routes:**

1. **Fast Break Detection (Highest Priority):**
   - If `turnData.fast_break === true` OR `turnData.result_type === "FAST_BREAK"` → `handleFastBreak()`

2. **Specific Result Type:**
   - If `turnData.result_type` exists in `animationHandlers` Map → Use that handler

3. **Shot Attempt Detection:**
   - If `isShotAttempt(turnData)` AND not in non-shot result types → `handleShotAttempt()`

4. **Rebound Detection:**
   - If `isRebound(turnData)` → `handleRebound()`

5. **Pass Detection:**
   - If `isPass(turnData)` → `handlePass()`

6. **Default Handler:**
   - Otherwise → `handleDefault()`

**Non-Shot Result Types (Excluded from Shot Attempt Detection):**
- `FOUL`, `FREE_THROW`, `TURNOVER`, `DEAD_BALL`, `DEAD_BALL_TURNOVER`
- `SIDE_INBOUND`, `BASELINE_INBOUND`, `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`
- `DEFENSIVE_STOP`, `OPENING_TIP`, `HCO`, `STEAL`

---

## Specialized Animation Systems

Some handlers route to specialized animation systems (if available):

1. **`ShotAnimationSystem`** - Used by `handleShotAttempt()`
   - Handles HCO and FCP/HCT shot attempts
   - Player movement, ball flight, rebounds

2. **`FreeThrowAnimationSystem`** - Used by `handleFreeThrow()`
   - Handles free throw sequences
   - Multiple attempts, rim hold, state transitions

3. **`ReboundAnimationSystem`** - Used by `handleRebound()`
   - Handles rebound animations
   - **Status:** May not be fully implemented yet

4. **`PassAnimationSystem`** - Used by `handleSideInbound()` and `handlePass()`
   - Handles pass animations
   - **Status:** May not be fully implemented yet

**Fallback Pattern:**
All specialized systems have fallbacks to legacy functions (`playTurnAnimation()`, `runFreeThrowSequence()`, etc.) if the system is not available.

---

## Future Improvements

1. **Complete Specialized Systems:** Fully implement `ReboundAnimationSystem` and `PassAnimationSystem`
2. **Migrate FCP/HCT to Handlers:** Currently routes directly to `playTurnAnimation()` (not through AnimationRouter)
3. **Consolidate Text Scroll:** Move all text scroll appends to AnimationRouter for consistency
4. **Handler Documentation:** Add JSDoc comments to all handlers

---

## Key Files

- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - All handler implementations
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js` - Handler invocation
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` - Shot handler system
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` (used by `handleDefault()`)

---

### Player Animation System

**Status:** Already using WIP_GOB approach

Player animations already use the simplified approach:
- `animateStep()` uses `getPlayerTweenTargets()` for conditional ball inclusion
- Distance-based duration calculation
- Simple Phaser tweens (no complex following systems)

**Notes:**
- `tweenPlayerTo()` in `ballTween.js` still uses `onUpdate` callback for ball following (only used for fast break outlet passes - low priority cleanup)
- Old system flags (`_shotInProgress`, `ballDetached`, `_putbackInProgress`) are no longer **set** anywhere, but may still be **read** in debug logging or dead code checks
- All ball state is managed by `BallController` - old flags are legacy references only

---

### Distance-Based Animation Speed System ✅ **COMPLETE** (January 2025)

**Status:** Fully implemented and operational

The animation system uses a unified distance-based duration calculation that ensures consistent speeds across all animations and respects game speed settings (Slow/Normal/Fast).

**Architecture:**

#### Core Functions

- **`getPlayerDuration(sprite, targetX, targetY, isTransition = false)`** (`turnAnimation.js`)
  - Calculates player movement duration based on distance from current sprite position to target
  - Uses `getPlayerSpeed()` which checks `window.__GAME_SPEED` for dynamic speed settings
  - Formula: `duration = (distance / speed) * 1000` (converts to milliseconds)
  - **Note**: The `isTransition` parameter is accepted but currently unused (distance fully determines time, no upper cap)
  - Minimum duration: 50ms (to avoid zero-length tweens)
  - Default speed: 350 pixels/second (Normal preset)

- **`getBallDuration(ballSprite, targetX, targetY)`** (`ballTween.js`)
  - Calculates ball movement duration based on distance from current position to target
  - Uses `getBallSpeed()` which checks `window.__GAME_SPEED` for dynamic speed settings
  - Formula: `duration = (distance / speed) * 1000` (converts to milliseconds)
  - Default speed: 350 pixels/second (Normal preset)
  - Clamped between 50ms (minimum) and 1000ms (maximum)

#### Game Speed Integration

**Speed Presets** (`gameSpeedManager.js`):
- **Slow**: 250 pixels/second
- **Normal**: 350 pixels/second (default)
- **Fast**: 450 pixels/second

**How It Works**:
1. User selects speed via UI buttons (Slow/Normal/Fast)
2. `gameSpeedManager.setGameSpeed()` updates `window.__GAME_SPEED`
3. `getPlayerSpeed()` and `getBallSpeed()` check `window.__GAME_SPEED` before falling back to defaults
4. All duration calculations automatically use the current speed setting

#### Where It's Used

**Player Animations**:
- ✅ HCO turn animations (`ShotAnimationSystem.animatePlayerMovement()`)
- ✅ Transition animations (IP→HCO, DREB→HCO)
- ✅ Inbound pass setup animations
- ✅ Opening tip player movements
- ✅ Free throw player movements
- ✅ Fast break player movements
- ✅ **Setup tweens** (`runSetupTween()` in `turnAnimation.js` and `ShotAnimationSystem.js`) - Fixed January 2025
- ✅ **Get-back players** during shot attempts - Fixed January 2025
  - Stop on MISS when rebound is secured
  - Stop on MAKE after rim hold (1s HCO, 2s fast break)
- ✅ **Rebound positioning animations** - Fixed January 2025
  - Rebounder to ball bounce
  - Non-rebounders collapse (stop when rebounder secures ball)
  - Player to rebound spot

**Ball Animations**:
- ✅ Pass animations (`passDetection.js`)
- ✅ Opening tip ball movements
- ✅ All ball tweens via `getBallDuration()`

#### Benefits

- ✅ **Consistent Speeds**: All animations use the same distance-based calculation
- ✅ **Game Speed Support**: Slow/Normal/Fast buttons work across all animations
- ✅ **Smooth Transitions**: Distance-based calculation ensures smooth movement regardless of timestamp gaps
- ✅ **No More "Stuck in Mud"**: Replaced slow timestamp-based calculations with responsive distance-based ones
- ✅ **Unified System**: Single source of truth for duration calculations

#### Migration History

**Before (Bug 3 - Fixed January 2025)**:
- `ShotAnimationSystem` used timestamp-based calculation: `(nextStep.timestamp - step.timestamp) * 3`
- Hardcoded speeds in `passDetection.js` and `openingTip.js`
- Game speed buttons had no effect
- Inconsistent speeds between HCO and transitions

**After (Fixed January 2025)**:
- All animations use `getPlayerDuration()` or `getBallDuration()`
- Game speed settings respected everywhere
- Consistent speeds across all animation types
- **Recent Fixes (January 2025)**:
  - `runSetupTween()` now uses distance-based timing (was hardcoded 1000ms)
  - Get-back players use distance-based timing with early termination
  - Rebound animations use distance-based timing and stop when rebounder secures ball
  - BIP → HCO transitions are smooth and consistent

**See:**
- `docs/PHASE_2.5_BUG_LIST.md` - Bug 3 fix details
- `docs/To Do/distance_based_animation_audit.md` - Comprehensive audit and implementation details
- `docs/To Do/animation_speed_edge_cases.md` - Previous edge cases (now resolved)

---

### Shot Resolution Process ✅ **COMPLETE** (January 2025)

**Status:** Fully unified and operational

All made shots (HCO, Fast Break, Putback, Free Throw) now use a consistent resolution process that ensures the ball lands and holds at the correct rim coordinates.

#### Rim Coordinates

**Constants** (`courtConstants.js`):
- **Home Rim**: `{ x: 91, y: 25 }` (grid coordinates)
- **Away Rim**: `{ x: 9, y: 25 }` (grid coordinates)

**Rule**: Teams shoot at their own basket
- Home team shoots at home rim (x: 91)
- Away team shoots at away rim (x: 9)

#### Resolution Process

**For All Made Shots** (HCO, Fast Break, Putback, Free Throw):

1. **Ball Animation to Rim**
   - Ball animates from shooter to rim coordinates using `animateBallFlight()` or `animateShotToRim()`
   - Animation completes when ball reaches rim position
   - Ball remains visible at rim coordinates

2. **Rim Hold (1 Second)**
   - Ball holds at rim coordinates for **1 second** (1000ms)
   - Allows "It's Good!" announcement to display
   - Ball stays visible during this hold period
   - Implemented via `scene.time.delayedCall(1000, resolve)` or `wait(scene, 1000)`

3. **State Cleanup**
   - `ballController.onShotEnd()` is called to clear in-flight state
   - Ball visibility is managed by the specific animation system
   - HCO makes: Ball is explicitly hidden after 1 second hold
   - Fast Break/Putback/Free Throw: Ball remains visible until next play begins

4. **Transition to Next Play**
   - Regular makes: Transition to inbound pass (BASELINE_INBOUND)
   - AND-1 makes: Transition to free throw (FREE_THROW)
   - Ball state is cleared before transition

#### Implementation by Shot Type

**HCO Made Shots** (`ShotAnimationSystem.js`):
- Uses `animateBallFlight()` to animate ball to rim
- `handleMadeShot()` holds ball at rim for 1 second
- Ball is explicitly hidden after 1 second hold
- Then calls `onShotEnd()` and transitions

**Fast Break Made Shots** (`fastBreak.js`):
- Uses `animateShotToRim()` to animate ball to rim (exact rim coordinates, no adjustment)
- Shows announcement
- Waits 1 second (ball remains visible at rim)
- Calls `onShotEnd()` and transitions to inbound

**Putback Made Shots** (`ballManager.js`):
- Uses `animateShotToRim()` to animate ball to rim
- Shows announcement
- Waits 1 second (ball remains visible at rim)
- Calls `onShotEnd()` and resolves

**Free Throw Made Shots** (`freeThrow.js`):
- Uses `animateShotToRim()` to animate ball to rim
- Shows announcement
- Waits `animationConfig.freeThrow.rimHoldMs` (typically 1000ms)
- Ball remains visible at rim during hold
- Calls `onShotEnd()` and continues to next attempt or ends

#### Key Features

- ✅ **Consistent Rim Hold**: All made shots hold at rim for 1 second
- ✅ **Correct Rim Coordinates**: Home team at home rim, away team at away rim
- ✅ **No Manual Repositioning**: Ball lands at exact final position of flight animation
- ✅ **Smooth Transitions**: State cleanup before transitioning to next play
- ✅ **Unified Behavior**: All shot types use the same resolution pattern

#### Benefits

- ✅ **Visual Consistency**: All made shots look the same (ball holds at rim)
- ✅ **Correct Positioning**: Ball always lands at correct rim coordinates
- ✅ **No Teleporting**: Ball stays at rim position throughout hold period
- ✅ **Maintainable**: Single pattern for all shot types

**Key Files:**
- `ShotAnimationSystem.js` - HCO shot resolution
- `fastBreak.js` - Fast break shot resolution
- `ballManager.js` - Putback shot resolution
- `freeThrow.js` - Free throw resolution
- `courtConstants.js` - Rim coordinate constants

**See:**
- `FrontEnd/static/js/phaser/animation/courtConstants.js` - Rim coordinate definitions

---

## Experimental Animation System - PossessionRunner

> ⚠️ **IMPORTANT**: This section describes an **experimental animation system** (PossessionRunner) 
> that is **currently DEPRECATED and disabled**. The production system uses the approach documented above. 
> 
> **Status:** PossessionRunner has been removed from production. The code still exists but is not used.
> - `FEATURE_POSSESSION_RUNNER` flag always returns `false`
> - All animation now uses the standard animation path
> 
> **For all development work, refer to the production system above.**

This section gives incoming contributors a concise tour of the **experimental** front-end
animation stack for **GOB**. It covers the architectural goals, the current
state of the migration, and the major components for the PossessionRunner system.

## Goals

- **Deterministic timelines** – drive every possession strictly from backend
  timestamps so replays, debugging, and automated tests are repeatable.
- **Single orchestration path** – replace ad-hoc tween chains with a single
  runner that controls the finite-state machine (FSM), ball ownership, and
  sprite motion.
- **Progressive rollout** – keep the legacy animation path available behind
  `window.FEATURE_POSSESSION_RUNNER` so QA/gameplay can fall back while we port
  additional scenarios.

## Migration Plan (snapshot)

1. **Normalize backend data** into deterministic action graphs.
   - `FrontEnd/static/js/phaser/animation/possession/normalizeTurn.js`
   - Already landed; generates frame-by-frame positions, passes, and terminal
     metadata.
2. **PossessionRunner** consumes normalized graphs, schedules tweens on a
   Phaser timeline, and emits canonical events.
   - `FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js`
   - Implementation is present; still tuning timings, FSM transitions, and
     timeline creation so freezes don’t occur.
3. **Centralise FSM control** around the runner for rebounds/fast breaks.
   - Current focus once runner stability improves.
4. **Port remaining flows** (fast breaks, offensive rebounds) to the runner
   path.
5. **Add diagnostics** (DEBUG_ANIM hooks, teleport detection, etc.).
   - Many hooks exist; we continue to expand them as issues surface.

## Key Modules (Experimental)

- **PossessionRunner** – orchestrates half-court possessions, manages ball
  ownership, queues player tweens, and transitions the FSM. Emits
  `possessionRunner:*` events when `DEBUG_ANIM` is true.
- **Timeline factory** – `animationTimeline.js` produces a Phaser timeline when
  available, falling back to `timelinePolyfill.js` for test environments.
- **Ball helpers** – `ballManager.js` handles passes, rebounds, and shot arcs,
  and integrates with the runner via injected helper callbacks.
- **Fast break / inbound adapters** – legacy systems still handle special
  flows; we're gradually routing them through the runner or compatible
  timelines.

**Note:** The production ball animation system (WIP_GOB approach) is separate from PossessionRunner and is fully operational. See the "Production Animation System" section above.

## Current Challenges

- **Timeline fallback** – on some builds Phaser’s tween manager does not expose
  `createTimeline`, so we fall back to the polyfill. This causes choppy motion
  and can deadlock if helper promises never resolve. Short-term plan: detect
  the correct tween plugin (`scene.sys.tweens`) and prefer it before the
  polyfill.
- **FSM noise** – duplicate `ShotAttempt` transitions and “duplicate possession
  change” warnings indicate the runner and legacy helpers are both emitting
  state changes. We’ve added guards to skip redundant transitions, but more
  cleanup is needed as we centralise control.
- **Telemetry** – instrumentation now reports timeline steps, pending helper
  counts, and delay scheduling, which helps diagnose freezes. Continue to use
  `DEBUG_ANIM` when testing.

## Getting Started

1. Enable debug flags:
   ```js
   window.DEBUG_ANIM = true;
   window.FEATURE_POSSESSION_RUNNER = true;
   ```
2. Run a possession and watch the console for `possessionRunner:*` events,
   timeline warnings, and FSM transitions.
3. If animation freezes, capture the current scene’s tween capabilities to
   confirm whether the native timeline is available.
4. Iterate on the PossessionRunner/timeline factory to keep the timeline
   running exclusively through Phaser’s tween manager.

This overview should help new developers orient themselves quickly. Dive into
the files listed above, keep `DEBUG_ANIM` running, and feel free to expand this
document as the migration advances.

---

## Defensive Player + Pass Animation Synchronization Fix ✅ **COMPLETE** (January 2025)

**Status:** Fixed and operational

### Problem
Defensive players were not consistently animating in sync with pass animations during HCO steps. The pass would animate, but defensive players would either:
- Move before the pass started (defense moved first, then pass animated)
- Not move at all during the pass
- Move inconsistently (worked for away team but not home team, or vice versa)

This made the game feel unorganic, as players would move while the ball was already in the air, rather than defensive players reacting to the pass.

### Root Cause
The issue was caused by **inconsistent `offenseTeamId` resolution**, which led to incorrect player classification:

1. **Redundant Variables**: The codebase had both `scene.offenseTeamId` and `scene.currentOffenseTeamId`, which could get out of sync
2. **Undefined offenseTeamId**: When both `scene.offenseTeamId` and `turnData.possession_team_id` were undefined/null, all players (including the passer) were misclassified as defensive
3. **Passer Misclassification**: When the passer was misclassified as defensive:
   - `passerPromise` was never set (passer went into `defensivePromises` instead of `offensivePromises`)
   - Code waited for ALL offensive players to finish before starting pass
   - Defensive players finished their animations before the pass started
   - Result: Pass animation started AFTER defensive players finished, breaking sync

### Solution

#### 1. Consolidated to Single `offenseTeamId` Variable
- **Removed**: `scene.currentOffenseTeamId` (redundant)
- **Kept**: `scene.offenseTeamId` as single source of truth
- **Updated**: All references to use `scene.offenseTeamId` only
- **Files**: `turnAnimation.js`, `ShotAnimationSystem.js`, `fastBreak.js`, `possessionManager.js`, `ballManager.js`, `turnoverAdapter.js`, `animateGameTurns.js`

#### 2. Created Robust `offenseTeamId` Resolver
- **New File**: `FrontEnd/static/js/phaser/utils/offenseTeamIdResolver.js`
- **Comprehensive Fallback Chain**:
  1. `turnData.possession_team_id` (backend guarantee - always set)
  2. `scene.offenseTeamId` (scene state - kept in sync by PossessionManager)
  3. Derive from `passInfo` - find passer's `team_id` from `playerSprites`
  4. Derive from animations - find ball handler's `team_id` from `playerSprites`
  5. Derive from `simData` - use `home_team_id` or `away_team_id`
  6. Last resort: `simData.home_team_id` (with warning)
- **Ensures**: `offenseTeamId` is **always defined** (except pre-opening tip)

#### 3. Consolidated Backend Variables
- **Removed**: `starting_possession_team_id` (redundant)
- **Updated**: `possession_team_id` now set **BEFORE** `update_clock_and_possession` (represents team on offense DURING the turn)
- **Result**: Single source of truth for possession team ID

#### 4. Synchronized Pass and Defense Animation
- **Phase 1**: Offensive players move (wait for passer to reach spot)
- **Phase 2**: Pass animation + defensive players animate **in parallel**
- **Phase 3**: Wait for any remaining offensive players (non-passer)
- **Files**: `turnAnimation.js` (line 1885-1924), `ShotAnimationSystem.js` (line 428-450)

### Implementation Details

**Player Classification Logic**:
```javascript
// ✅ ROBUST: offenseTeamId should always be defined (resolved by resolveOffenseTeamId)
const offenseTeamId = resolveOffenseTeamId({
  scene,
  turnData,
  playerSprites,
  passInfo
});

const isOffensivePlayer = offenseTeamId ? String(sprite.team_id) === String(offenseTeamId) : false;
```

**Animation Sequencing**:
```javascript
// Phase 1: Offensive players move (wait for passer if there's a pass)
if (passInfo && passerPromise) {
  await passerPromise; // Wait for passer to reach spot
} else if (offensivePromises.length > 0) {
  await Promise.all(offensivePromises);
}

// Phase 2: Pass animation + defensive players in parallel
const passAndDefensePromises = [];
if (passInfo) {
  passAndDefensePromises.push(handlePassAnimation({ scene, passInfo, playerSprites }));
}
passAndDefensePromises.push(...defensivePromises);
await Promise.all(passAndDefensePromises); // Animate pass and defense simultaneously

// Phase 3: Wait for remaining offensive players
const remainingOffensivePromises = offensivePromises.filter(p => p !== passerPromise);
if (remainingOffensivePromises.length > 0) {
  await Promise.all(remainingOffensivePromises);
}
```

### Benefits

1. **Consistent Synchronization**: Defensive players now always animate in sync with pass animations
2. **Organic Feel**: Defensive players move while the ball is in the air, creating natural defensive reactions
3. **Reliable Classification**: `offenseTeamId` is always defined, ensuring correct player classification
4. **Simplified Codebase**: Single `offenseTeamId` variable instead of multiple redundant variables
5. **Better Maintainability**: Centralized resolver ensures consistent behavior

### Files Modified

**Frontend**:
- `FrontEnd/static/js/phaser/utils/offenseTeamIdResolver.js` (new)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- `FrontEnd/static/js/phaser/utils/possessionManager.js`
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
- `FrontEnd/static/js/phaser/animation/ballManager.js`
- `FrontEnd/static/js/phaser/animation/turnoverAdapter.js`
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- `FrontEnd/static/js/phaser/utils/announcements.js`
- `FrontEnd/static/js/phaser/ui/playcallCenter.js`
- `FrontEnd/static/js/phaser/utils/strategyBars.js`
- `FrontEnd/static/js/phaser/utils/playcallDisplay.js`
- `FrontEnd/static/js/phaser/animation/possession/normalizeTurn.js`
- `FrontEnd/static/js/types.d.ts`

**Backend**:
- `BackEnd/models/turn_manager.py`

### Testing

- ✅ Defensive players animate in sync with pass animations
- ✅ Works consistently for both home and away team on offense
- ✅ Works for both zone and man defense
- ✅ Pass animation starts after passer reaches spot (maintains existing behavior)
- ✅ All offensive players complete their movements
- ✅ No regression in other animation systems

