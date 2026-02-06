## Fast Break System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Defensive Stop Y-Range**: `DEFENSIVE_STOP_Y_RANGE = 6` (defender must be within ±6 y-coords of outlet receiver to force stop)
2. **Ball Handler Movement (Defensive Stop/Shot)**: X: 5-10 spots toward basket, Y: ±3 spots
3. **Stopper Positioning**: 1-3 spots in front of ball handler (defensive stop)
4. **Defender Positioning (Shot)**: Defender between basket and shooter; X: 1–3 coords toward basket from shooter; Y: ±2 of shooter
5. **Steal Entry Movement**: X: 5-10 spots toward basket, Y: ±4 spots (clamped 3-47)
6. **Outlet Pass Score Formula**: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)`, scaled to 1-100 range
7. **Defense Release Chances**: Based on `fast_breaks` setting (0-4): `{0: 0.0, 1: 0.25, 2: 0.5, 3: 0.75, 4: 1.0}`

**Fast Break Resolution Flow (8 Steps)**

1. **Apply Energy Decay**
   - Apply energy decay to all active players (offense and defense) via `apply_energy_decay()`
   - **Note**: Bench recharge does NOT happen during Fast Break turns (only during HCO turns)

2. **Track Defensive Attempt**
   - Increment `off_scouting["offense"]["Fast_Break_Entries"]`
   - Increment `def_scouting["defense"]["vs_Fast_Break"]["used"]`

3. **Determine Entry Type and Set Roles**
   - **DREB Entry**: 
     - Outlet passer = rebounder (from `game_state["last_rebounder"]`)
     - Outlet receiver = release player (from `game_state["last_release_player"]`) or fallback to random PG/SG/SF
     - Calculate outlet pass score: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random(1-6)`, scaled to 1-100
   - **Steal Entry**:
     - Ball handler = stealer (from `game_state["last_stealer"]`)
     - No outlet pass (no outlet passer/receiver)

4. **Calculate Ball Handler Position After Entry**
   - **DREB Entry**: Ball handler receives outlet pass at starting position (no movement during outlet pass)
     - Priority 1: `defense_release_coords` from most recent MISS/MAKE turn
     - Priority 2: `offense_getback_coords` from most recent MISS/MAKE turn
     - Fallback: `player.coords`
   - **Steal Entry**: Ball handler moves 5-10 x spots toward basket, ±4 y spots (clamped 3-47)
     - Uses `last_stealer_coords` from game_state if available

5. **Check All Defenders for Defensive Stop**
   - Loop through **all defenders in `def_lineup`** (not just `fb_roles["defense"]`)
   - Get defender coordinates:
     - Priority: `offense_getback_coords` from most recent MISS/MAKE turn (if defender was a get-back player)
     - Fallback: `defender.coords`
   - For each defender, check:
     - **X-Coordinate Check (Ahead)**: 
       - Home offense: `defender_x >= ball_handler_x` (basket at x=90)
       - Away offense: `defender_x <= ball_handler_x` (basket at x=10)
     - **Y-Coordinate Check (Within Range)**: `|defender_y - ball_handler_y| <= 6`
   - Track closest stopping defender (x-distance only) and closest defender overall (Euclidean distance)

6. **Determine Event Type**
   - **0 Defenders**: Always `SHOT`
   - **Defender Ahead AND Within Y-Range**: Skill check between ball handler and defender
     - **Geography Check**: Defender must be ahead AND within ±6 y-coords (determines if stop attempt is possible)
     - **Skill Check** (if geography check passes):
       - `break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * random(1-6)`
       - `stop_score = defender.attributes["AG"] + defender.attributes["OD"] * random(1-6)`
       - If `stop_score >= break_score` → `DEFENSIVE_STOP` (defender wins)
       - If `break_score > stop_score` → `SHOT` (ball handler wins, beats defender)
         - Defender still animates to stopper position (shows the attempt)
         - Ball handler animates past stopper to shot spot (shows offensive success)
   - **Otherwise**: `SHOT` (closest defender overall becomes shot defender)

7. **Handle DEFENSIVE_STOP Result**
   - Set `offensive_state = "HCO"`
   - Build animation packet (outlet pass + defensive stop)
   - Track Fast Break stats (release player: `FB_A`, get-back players: `FB_A_D`, `FB_S_D`)
   - Track team stats (`def_scouting["defense"]["vs_Fast_Break"]["success"] += 1`)
   - Return result with `next_play_type = "HCO"`

8. **Handle SHOT Result**
   - Assign shooter (random from `[ball_handler] + offense`)
   - Assign passer:
     - If shooter is outlet receiver: passer = outlet passer (rebounder)
     - Else if shooter != ball_handler: passer = ball_handler
     - Else: passer = None
   - **Shot threshold**: Uses effective defender count. If a defender attempted a stop and failed (`ball_handler_beats_defender`), effective count = defender_count − 1 (min 0). Threshold: 0 def → 1; 1 def → base; 2+ def → base + 100 + def_chem − off_fight. Stats and animation still use actual defender_count.
   - **Special Case - Ball Handler Beats Defender**:
     - If `ball_handler_beats_defender = True` (from Step 6 skill check):
       - Defender still animates to stopper position (1-3 spots in front of ball handler's starting position)
       - Ball handler animates past stopper to shot spot (shows offensive success)
       - Use `animateFastBreakShotWithStopper()` animation path
   - **Charge/Blocking Foul**: Only checked when there is a shot defender (defender present and defender_count ≥ 1). If 0 defenders back, no charge/block check; shot proceeds normally. When applicable, uses same attack-shot logic as half-court (`calculate_charge()`); CHARGE → possession to defense, BLOCKING_FOUL → foul on defender (SIP or free throws if bonus). Shooter and defender are animated to the shot spot; no shot-to-rim.
   - Call `shot_manager.resolve_shot()` (attack adapter) for shot resolution
   - Build animation packet (outlet pass + shot attempt)
   - Track Fast Break stats and team stats
   - If MISS → DREB: Route to `runDefensiveReboundSetup()` with current Fast Break turn data

**Long Form Documentation**

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
   - Defender is ahead of ball handler after outlet pass AND within ±6 y-coords
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Closest defender ahead becomes "stopper" and is placed 1-3 spots in front of ball handler
   - Routes to: HCO (half court offense)

2. **Shot Attempt (SHOT)**
   - No defender ahead of ball handler after outlet pass OR defender not within ±6 y-coords
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Closest defender overall (by Euclidean distance) follows and is positioned between basket and shooter (1–3 x-coords toward basket from shooter, ±2 y from shooter)
   - Routes to: Standard shot resolution flow (MAKE/MISS)

### Charge and Blocking Foul (Fast Break Shot Only)

- **When checked**: Only when there is a shot defender defending the attempt: defender is assigned and `defender_count ≥ 1`. If **0 defenders back**, the charge/block check is **skipped** and the shot is resolved normally (make/miss).
- **How**: Same as attack shots in half-court. Before make/miss, `calculate_charge(shooter, defender, off_team, def_team)` runs. It uses shooter/defender attributes and team chemistry/discipline; thresholds determine the call.
- **CHARGE** (foul on offense): Possession flips to defense; next play is side inbound. No shot attempt.
- **BLOCKING_FOUL** (foul on defense): Foul recorded on defender; next play is SIP or FREE_THROW if bonus. No shot attempt.
- **Animation**: For either call, shooter and defender are animated to the shot spot near the basket; no ball-to-rim. Announcement ("Charge!" / "Blocking foul on X!") runs in finalizeTurnAfterAnimation.

### Shot Threshold When Defender Attempts Stop and Fails

- For **shot difficulty only**, defender count is reduced by 1 when a defender **attempted a stop and failed** (`ball_handler_beats_defender = True`). Effective count = max(0, defender_count − 1).
- **Example**: 1 defender back, they attempt stop and lose → effective count = 0 → shot threshold = 1 (same as no defenders). Stats and animation still use actual defender_count = 1.

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

**Skill Check Implementation:**
- **Two-Step Process**: Geography determines if a stop attempt is possible, then skill check determines the outcome.
  1. **Geography Check**: Defender must be ahead AND within ±6 y-coords (determines if stop attempt is possible)
  2. **Skill Check** (if geography check passes):
     - `break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * random(1-6)`
     - `stop_score = defender.attributes["AG"] + defender.attributes["OD"] * random(1-6)`
     - If `stop_score >= break_score` → `DEFENSIVE_STOP` (defender successfully stops the break)
     - If `break_score > stop_score` → `SHOT` (ball handler beats the defender)
- **Animation Behavior When Ball Handler Wins**:
  - Defender still animates to stopper position (1-3 spots in front of ball handler's starting position)
  - Ball handler animates past the stopper to shot spot near rim
  - This visually shows the offensive player's success in beating the defender
  - Flag `ball_handler_beats_defender = True` is set in `fb_roles` to trigger special animation path

**Critical Implementation Detail - Defender Assignment Consistency:**
- **Backend Calculation**: In `phase_resolution.py`, `fb_roles["defender"]` is set to `closest_defender_overall` for shot attempts (line 1183)
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

**Phase 1: Outlet Pass (DREB Entry Only)**
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
- Defender follows to position between basket and shooter (1–3 x toward basket from shooter, ±2 y from shooter)
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

### Fast Break Stat Tracking

The Fast Break system tracks comprehensive statistics for both offensive and defensive players involved in fast break situations.

**Stat Tracking Function:**
- `_record_fast_break_stats()` in `BackEnd/engine/phase_resolution.py` - Records stats after Fast Break turn completes

**Offensive Stats (Release Player / Outlet Receiver):**

The release player (outlet receiver) tracks:
- **`FB_A`** (Fast Break Attempts): Always incremented when player is the outlet receiver on a Fast Break
- **`FB_S`** (Fast Break Success): Incremented when Fast Break results in:
  - Shot Make
  - Defensive Foul (non-shooting)
  - **Note**: Shot Miss (without defensive foul) does NOT count as success (matches team-level criteria)
- **`FB_F`** (Fast Break Failure): Incremented when Fast Break results in:
  - Steal
  - Dead Ball Turnover
  - Offensive Foul
- **`FB_N`** (Fast Break Neutral): Calculated as `FB_A - (FB_S + FB_F)`

**Defensive Stats (Get-Back Players):**

All get-back players (defenders who got back on defense) track:
- **`FB_A_D`** (Fast Break Attempts Defense): Always incremented when player is a get-back defender on a Fast Break
- **`FB_S_D`** (Fast Break Success Defense): Incremented when Fast Break results in:
  - DEFENSIVE_STOP
- **`FB_F_D`** (Fast Break Failure Defense): Incremented when Fast Break results in:
  - Shot Make
  - Shot Make + Foul
  - Shot Miss + Foul
  - Defensive Foul (non-shooting)

**Outlet Pass Stats (Outlet Passer):**

The outlet passer tracks:
- **`Outlet_A`** (Outlet Pass Attempts): Always incremented when player makes an outlet pass
- **`Outlet_S`** (Outlet Pass Successes): Incremented when outlet pass leads to a shot attempt (not a defensive stop)
- **`Outlet_Score`** (Average Outlet Pass Score): Average of all outlet pass scores (1-100 scale)
- **`Outlet_Score_List`** (Outlet Pass Score List): Array of individual outlet pass scores
- **`Outlet_Score_Cum`** (Cumulative Outlet Pass Score): Sum of all outlet pass scores

**Outlet Pass Score Calculation:**
- **Formula**: `(PS * 0.6 + ST * 0.2 + IQ * 0.2) * random.randint(1, 6)`
- **Scaling**: Raw score (1-600 range, midpoint 175) is scaled to 1-100 range (midpoint 50)
- **Function**: `calculate_outlet_pass_score()` in `BackEnd/utils/shared.py`
- **Scaling Function**: `scale_score_to_100()` in `BackEnd/utils/shared.py` (universal helper for all attribute-based scores)

**Stat Initialization:**
- All Fast Break stats initialized to `0` (except `Outlet_Score_List` which is initialized as empty array `[]`)
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Tracking Timing:**
- **Outlet Pass Stats**: Tracked immediately after outlet pass score is calculated (in `resolve_fast_break_logic()`)
- **Fast Break Stats**: Tracked after Fast Break turn result is finalized (both DEFENSIVE_STOP and SHOT paths)
- Stats are recorded in both `run_micro_turn()` and `resolve_offensive_rebound_turn()` paths

**Team Stats (Scouting Data):**
- **`Fast_Break_Entries`** (Offense): Incremented each time a team runs a Fast Break
- **`Fast_Break_Success`** (Offense): Incremented only when Fast Break result_type is:
  - `MAKE`, or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul on the break)
  - **Note**: `MISS` or `TURNOVER` do NOT count as team success (they count as defensive success)
- **`vs_Fast_Break.used`** (Defense): Incremented each time defending a Fast Break
- **`vs_Fast_Break.success`** (Defense): Incremented when Fast Break result_type is:
  - `DEFENSIVE_STOP`, or
  - `MISS`, or
  - `TURNOVER`, or
  - `FOUL` where `foul_team == "OFFENSE"`
- **Alignment with player stats:** Player `FB_S` now matches team `Fast_Break_Success` (only `MAKE` or defensive foul). A `MISS` without defensive foul is neutral (`FB_N`) for players and not a success for the team.

**Special Handling:**
- **`Outlet_Score_List`**: Excluded from stat delta calculations (it's a list, not numeric)
- **Team Stats Aggregation**: `Outlet_Score_List` is concatenated (not summed) when aggregating team stats
- **Stat Deltas**: `Outlet_Score_List` and `REB` are excluded from delta calculations in `turn_manager.py`

**Box Score Display:**
- Fast Break stats are available in the Box Score page
- Clicking a player's name opens a popup showing:
  - Fast Breaks: Offense (Attempts / Success Rate), Defense (Attempts / Success Rate)
  - Outlet Passes: Att / Score (average of `Outlet_Score_List`)

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

- **More Nuanced Get-Back Logic**: Consider player attributes (speed, IQ) for get-back player selection
- **Fast Break Fouls**: Add foul handling during fast break sequences
- **Fast Break Turnovers**: Add turnover handling during fast break sequences

