## Fast Break System ✅ **COMPLETE** (January 2025)

> **Canonical reference (Bible):** This document is the **single source of truth** for sustained Fast Break knowledge—selection logic, coordinates, defensive stops, shot attempts, constants, and file touchpoints. Short-term project notes may live in `docs/To Do/FB_Update_Brief.md`; if something conflicts, **treat this file as authoritative** unless the team explicitly updates both.

**Base Constants**

1. **Defensive Stop Y-Range**: `DEFENSIVE_STOP_Y_RANGE = 6` for **steal → fast break** (defender must be within ±6 y of outlet receiver to force stop). **`DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET = 8`** for **DREB → outlet** fast breaks (Covert Release; wider band than steals).
2. **Ball Handler Movement (Defensive Stop/Shot)**: X: 5-10 spots toward basket, Y: ±3 spots
3. **Stopper Positioning**: 1-3 spots in front of ball handler (defensive stop)
4. **Defender Positioning (Shot)**: Defender 1 x-coord toward basket from shooter (home offense: shooter x + 1; away offense: shooter x − 1); Y: ±2 of shooter
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
     - Outlet receiver = release player (from `game_state["last_release_player"]`) or fallback to random PG/SG/SF. **Release selection** (Covert Release): on each shot, defense rolls release using `DEFENSE_RELEASE_CHANCES[fast_breaks]` (`fast_breaks` 0–4); if releasing, the releaser is the defender **farthest from the rim in x** among those **not** guarding the shooter (zone assignment at shot step, else man matchup). **IQ reads**: roll `the_read` 1–100 → **good_release** if `the_read <` release player IQ; roll `d_read` 1–100 once → each get-back player gets **good_d_release** if `d_read <` that player’s IQ. **AG**: outlet and get-back **x-band floors** use each player’s **AG** (see **Covert Release** below). Final coords sampled in `covert_release.py` (HOME orientation; mirror **x** when the future FB offense team is away).
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
     - **Y-Coordinate Check (Within Range)**: `|defender_y - ball_handler_y| <= 6` (steal entry) or `<= 8` (DREB/outlet entry)
   - Track closest stopping defender (x-distance only) and **closest defender overall among get-back players only** (Euclidean distance; only defenders in `offense_getback` from most recent shot are eligible for shot defender)

6. **Determine Event Type**
   - **0 Defenders**: Always `SHOT`
   - **Defender Ahead AND Within Y-Range**: Skill check between ball handler and defender
     - **Geography Check**: Defender must be ahead AND within y-range (**±6** steal, **±8** DREB/outlet) (determines if stop attempt is possible)
     - **Skill Check** (if geography check passes):
       - `break_score = ball_handler.attributes["AG"] + ball_handler.attributes["BH"] * random(1-6)`
       - `stop_score = defender.attributes["AG"] + defender.attributes["OD"] * random(1-6)`
       - If `stop_score >= break_score` → `DEFENSIVE_STOP` (defender wins)
       - If `break_score > stop_score` → `SHOT` (ball handler wins, beats defender)
         - Defender still animates to stopper position (shows the attempt)
         - Ball handler animates past stopper to shot spot (shows offensive success)
         - **Shot defender**: Closest get-back (by distance) **excluding the failed stopper**; if no other get-back, no shot defender (defender_count = 0)
   - **Otherwise**: `SHOT`. **Shot defender only when 1 or 2 get-back players**: closest get-back by Euclidean distance; if 0 or 3+ get-back, no shot defender (defender_count = 0)

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
   - **Shot defender pool**: Only **get-back players** (from `offense_getback` on the most recent shot) are eligible. **Only when there are 1 or 2 get-back players** is a shot defender assigned; 0 or 3+ get-back → no shot defender (defender_count = 0). If a get-back defender attempted a stop and failed (`ball_handler_beats_defender`), that defender is **excluded** from being the shot defender (closest remaining get-back is used, or none if he was the only get-back).
   - **Special Case - Ball Handler Beats Defender**:
     - If `ball_handler_beats_defender = True` (from Step 6 skill check):
       - Defender still animates to stopper position (1-3 spots in front of ball handler's starting position)
       - Ball handler animates past stopper to shot spot (shows offensive success)
       - Use `animateFastBreakShotWithStopper()` animation path
       - Shot defender = closest get-back **excluding the failed stopper** (or none if no other get-back)
   - **Charge/Blocking Foul**: Only checked when there is a shot defender (defender present and defender_count ≥ 1). If 0 defenders back, no charge/block check; shot proceeds normally. When applicable, uses same attack-shot logic as half-court (`calculate_charge()`); CHARGE → possession to defense, BLOCKING_FOUL → foul on defender (SIP or free throws if bonus). Shooter and defender are animated to the shot spot; no shot-to-rim.
   - Call `shot_manager.resolve_shot()` (attack adapter) for shot resolution
   - Build animation packet (outlet pass + shot attempt)
   - Track Fast Break stats and team stats
   - If MISS → DREB: Route to `runDefensiveReboundSetup()` with current Fast Break turn data

**Long Form Documentation**

### Overview

The **Fast Break** system handles transition offense situations that occur after defensive rebounds or steals. The system determines whether a fast break results in a defensive stop or a shot attempt based on defender positioning relative to the ball handler after the outlet pass.

**Key Functions:**
- **DREB outlet**: Release chance + Covert Release selection + coords in `shot_manager` / `BackEnd/engine/covert_release.py` (`FastBreakTrigger.DEFENSE_RELEASE_CHANCES`; `can_trigger_from_dreb()` is a **legacy** PG/SG helper, not the live DREB path)
- `resolve_fast_break_logic()` - Handles fast break outcome determination in `BackEnd/engine/phase_resolution.py`
- `capture_fast_break_animation()` - Builds animation packet in `BackEnd/models/animator.py`
- `runFastBreakSequence()` - Orchestrates fast break animation in `FrontEnd/static/js/phaser/animation/fastBreak.js`

### When Fast Break Activates

**Trigger Conditions:**
- After defensive rebounds when the defense rolls a release per `fast_breaks` and Covert Release assigns a releaser (see `covert_release.py`)
- After steals with fast break chance (`FastBreakTrigger.can_trigger_from_steal()`)
- Set via `next_play_type = "FAST_BREAK"` in turn result

**State Flow:**
1. DREB or STEAL → Fast break chance determined
2. FAST_BREAK turn generated with `fast_break = true` flag
3. Backend determines outcome (DEFENSIVE_STOP or SHOT) based on defender positioning
4. Frontend animates outlet pass, then defensive stop or shot attempt

### Possible Outcomes

Fast breaks can result in:

1. **Defensive Stop (DEFENSIVE_STOP)**
   - Defender is ahead of ball handler after outlet pass AND within y-range (**±6** steal, **±8** DREB/outlet)
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - Closest defender ahead becomes "stopper" and is placed 1-3 spots in front of ball handler
   - Routes to: HCO (half court offense)

2. **Shot Attempt (SHOT)**
   - No defender ahead of ball handler after outlet pass OR defender not within the applicable y-range (±6 vs ±8)
   - Ball handler moves 5-10 spots toward basket, ±3 Y (clamped)
   - **Shot defender (if any)**: Only when there are **1 or 2 get-back players**; pool is **get-back players only**. Closest get-back by Euclidean distance becomes shot defender (or, if ball handler beat a stopper, closest get-back **excluding that stopper**). If 0 or 3+ get-back, or only get-back was the failed stopper, no shot defender. When present, defender is positioned 1 x-coord toward basket from shooter (home: +1, away: −1), ±2 y from shooter.
   - Routes to: Standard shot resolution flow (MAKE, MISS, or **BLOCK** — block reconciliation can run on attack shots; see Block System)

### Charge and Blocking Foul (Fast Break Shot Only)

- **When checked**: Only when there is a shot defender defending the attempt: defender is assigned and `defender_count ≥ 1`. If **0 defenders back**, the charge/block check is **skipped** and the shot is resolved normally (make/miss/block).
- **How**: Same as attack shots in half-court. Before make/miss, `calculate_charge(shooter, defender, off_team, def_team)` runs. It uses shooter/defender attributes and team chemistry/discipline; thresholds determine the call.
- **CHARGE** (foul on offense): Possession flips to defense; next play is side inbound. No shot attempt.
- **BLOCKING_FOUL** (foul on defense): Foul recorded on defender; next play is SIP or FREE_THROW if bonus. No shot attempt.
- **Animation**: For either call, shooter and defender are animated to the shot spot near the basket; no ball-to-rim. Announcement ("Charge!" / "Blocking foul on X!") runs in finalizeTurnAfterAnimation.

### Blocks on Fast Break Shots

When a Fast Break shot is **blocked** (block reconciliation in `shot_manager.resolve_shot()` returns BLOCK), the turn has `result_type === "BLOCK"` and is treated as a **shot attempt** for animation, not a defensive stop.

**Routing (frontend):**
- In `runFastBreakSequence()` (fastBreak.js), Phase 2 branches on `result_type`. BLOCK is grouped with MAKE and MISS: `if (result === "MAKE" || result === "MISS" || result === "BLOCK")` → shot path (`animateFastBreakShot` or `animateFastBreakShotWithStopper`). Previously BLOCK fell through to the `else` and ran `animateDefensiveStop()`, so the fast break shot (run to rim + shot) never played.
- **Fix**: BLOCK now follows the same shot-attempt flow as MAKE/MISS so the run to the basket and shot motion always animate; then outcome handling runs for block (bounce from block spot, block announcement, rebound).

**Animation (shot target and outcome):**
- **Shot target**: When `result_type === "BLOCK"` and the backend provides `ball_bounce_x` / `ball_bounce_y` (block spot in grid), the ball is animated to that block spot instead of the rim. Otherwise the rim is used.
- **After the shot**: Block announcement (`announceGameEvent('BLOCK', ...)`), transition to Rebound, then `bounceFromRim(scene, ballSprite, blockSpotGrid, ...)` using the block spot (or basket if block spot missing). Rebound and DREB setup then match the MISS path (`animateRebound`, `runDefensiveReboundSetup` when `rebound_type === "DREB"`).
- **With-stopper path**: `animateFastBreakShotWithStopper()` uses the same logic: block spot as shot target when present, block announcement and bounce from block spot, then same rebound/DREB handling.

**Backend:**
- Block reconciliation runs for inside/attack shots (see Block System). On BLOCK, the turn result includes `result_type: "BLOCK"`, `ball_bounce_x` / `ball_bounce_y` (from the block spot), `rebounderId`, `rebound_type`, and other rebound fields. The frontend uses `ball_bounce_x`/`ball_bounce_y` for both the shot target and the bounce origin so the ball does not snap to the wrong side.

### Shot Threshold When Defender Attempts Stop and Fails

- For **shot difficulty only**, defender count is reduced by 1 when a defender **attempted a stop and failed** (`ball_handler_beats_defender = True`). Effective count = max(0, defender_count − 1).
- **Example**: 1 defender back, they attempt stop and lose → effective count = 0 → shot threshold = 1 (same as no defenders). Stats and animation still use actual defender_count = 1.

### Coordinate System and Player Positioning

**Coordinate Orientation:**
- All coordinates stored in **HOME orientation** (basket at x=90 for home, x=10 for away)
- Frontend flips coordinates for away team display
- Backend calculations always use HOME orientation for consistency

### Covert Release (DREB → outlet only)

Steal-initiated fast breaks **do not** use Covert Release. Play-type naming (e.g. “Covert Release”) applies only to **DREB → outlet** paths.

**Selection (summary)**  
1. Defender guarding the shooter cannot release.  
2. Among other defenders, choose the one **farthest from the basket being attacked** in x (HOME): home team shooting → lowest x on defense; away team shooting → highest x on defense; ties → random.  
3. **`the_read`**, **`d_read`**, **`good_release`**, **`good_d_release` per get-back** — see Step 3 in **Fast Break Resolution Flow** above.

**AG → x floors (HOME, when the fast-break offense team is home)**  
These set the **lower** end of random x; upper bounds and y come from the IQ bands below.

| Role | AG | Floor label | Value |
|------|-----|-------------|--------|
| **Outlet / release player** | AG ≥ 80 | `x_min` | 50 |
| | 60 ≤ AG < 80 | `x_min` | 47 |
| | AG < 60 | `x_min` | 45 |
| **Each get-back player** | AG ≥ 80 | `def_x_min` | 55 |
| | 60 ≤ AG < 80 | `def_x_min` | 53 |
| | AG < 60 | `def_x_min` | 50 |

**IQ → random bands (after floors)**  
Random integer coords; **x** is mirrored with `100 - x` when the **future** fast-break **offense** team is **away** (same as before); **y** is not mirrored.

| Player | Condition | x range (HOME, home FB offense) | y range |
|--------|-----------|----------------------------------|---------|
| Release (outlet receiver) | `good_release` | `x_min` – 55 | 18 – 32 |
| Release | not `good_release` | `(x_min - 5)` – 50 | 22 – 30 |
| Get-back | `good_d_release` | `def_x_min` – 60 | 22 – 30 |
| Get-back | not `good_d_release` | `(def_x_min - 5)` – 60 | 18 – 32 |

Implementation: `BackEnd/engine/covert_release.py` — `release_x_min_from_ag`, `getback_def_x_min_from_ag`, `sample_release_coords`, `sample_getback_coords`, `player_ag`.

**Outlet Receiver (Ball Handler) Starting Coordinates:**
- **Priority 1**: `defense_release_coords` from most recent MISS/MAKE turn (outlet receiver is typically a release player). Sampled via **`covert_release.sample_release_coords(good_release, will_be_home_fb_offense, ag)`** with **release player’s AG**.
- **Priority 2**: `offense_getback_coords` from most recent MISS/MAKE turn (if ball handler was a get-back player)
- **Fallback**: `player.coords` (current position on court)

**Get-Back Defender Coordinates:**
- **Priority**: `offense_getback_coords` from **most recent** MISS/MAKE turn only — **`covert_release.sample_getback_coords(good_d, will_be_home_fb_offense, ag)`** per get-back player (**that player’s AG**)
- Only defenders who were actually get-back players in the turn that triggered the fast break
- **Fallback**: `defender.coords` (current position on court)

**Example from Logs:**
```
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=34 (from offense_getback_coords)
Y Difference: |34 - 23| = 11 (exceeds ±6 steal band and ±8 DREB/outlet band)
Result: SHOT (defender is ahead in x but NOT within y-range)
Note: Even though defender at x=57 is ahead of ball handler at x=55, they are 11 y-coords 
away, so it becomes a shot attempt instead of defensive stop.

Another Example:
Outlet Receiver: x=55, y=23 (from defense_release_coords)
Get-Back Defender: x=57, y=25 (from offense_getback_coords)
Y Difference: |25 - 23| = 2 (within ±6 and ±8 y-bands)
Result: DEFENSIVE_STOP (defender at x=57 is ahead AND within y-range, distance: 2)
```

### Defensive Stop vs. Shot Attempt Determination

**Logic (HOME Orientation):**

**Home Offense:**
- Basket at x=90 (larger x is closer to basket)
- Defender ahead if: `defender_x >= ball_handler_x`
- **Defender must also be within y-range of outlet receiver** (±6 steal, ±8 DREB/outlet — see `defensive_stop_y_range` in `resolve_fast_break_logic`)
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Away Offense:**
- Basket at x=10 (smaller x is closer to basket)
- Defender ahead if: `defender_x <= ball_handler_x`
- **Same y-range rule** (±6 vs ±8 by entry type)
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Multiple Get-Back Players:**
- If multiple get-back players meet both conditions (ahead AND within y-range), the closest one (by x-distance) forces the defensive stop
- If neither get-back player meets both conditions, and there are **1 or 2 get-back players**, the closest get-back (by Euclidean distance from outlet receiver) becomes the shot defender

**Shot Defender Selection (Get-Back Only, 1 or 2):**
- There is a **potential shot defender only when there are 1 or 2 get-back players** on the defensive team (from `offense_getback` on the most recent shot).
- **Pool**: Only get-back players are eligible. The closest get-back by Euclidean distance from outlet receiver becomes the shot defender.
- **0 or 3+ get-back**: No shot defender is assigned (defender_count = 0); charge/block check is skipped; shot proceeds as uncontested (threshold logic still uses effective count).
- **Ball handler beats defender**: The get-back defender who attempted the stop and lost is **excluded** from being the shot defender. The closest **remaining** get-back (by distance) becomes the shot defender; if there is no other get-back, no shot defender (defender_count = 0).

**Skill Check Implementation:**
- **Two-Step Process**: Geography determines if a stop attempt is possible, then skill check determines the outcome.
  1. **Geography Check**: Defender must be ahead AND within y-range (**±6** steal, **±8** DREB/outlet — determines if stop attempt is possible)
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
  - **Shot defender**: The failed stopper is excluded; the closest **other** get-back (by distance) becomes the shot defender, or none if he was the only get-back

**Critical Implementation Detail - Defender Assignment (Get-Back Only, 1 or 2):**
- **Backend Calculation**: In `phase_resolution.py`, `closest_defender_overall` is tracked **only among defenders in `getback_player_ids`** (get-back players from the most recent shot). A shot defender is assigned only when `len(getback_player_ids) in (1, 2)`; otherwise `fb_roles["defender"] = None` and `fb_roles["defender_count"] = 0`. When `ball_handler_beats_defender` is True, the stopper is excluded and the closest remaining get-back is chosen (or none).
- **Shot Resolution**: `resolve_shot()` in `shot_manager.py` **respects** the already-set `fb_roles["defender"]` from phase resolution.
- **Why This Matters**: Only get-back players can contest the shot; the failed stopper cannot also be the shot defender; 0 or 3+ get-back means no charge/block and no shot defender for animation.

**Critical Implementation Detail:**
- **All defenders checked**: The system checks **all defenders in `def_lineup`**, not just those initially in `fb_roles["defense"]`
- **Why**: `get_in_play_defenders()` (called earlier) uses stale `ball_handler.coords` to filter defenders, which might exclude get-back players who are actually ahead of the outlet receiver position
- **Fix**: Loop through all defenders when comparing against outlet receiver position (`ball_handler_outlet_x/y`)
- **Result**: Get-back players who are ahead are correctly detected, even if they weren't initially included in `fb_roles["defense"]`
- **Animation**: If an ahead defender wasn't in the initial list, they're added to `fb_roles["defense"]` for animation purposes

**Implementation:**
```python
# getback_player_ids = from most_recent_shot_turn.get("offense_getback", [])
# ✅ Check ALL defenders in def_lineup for stop/shot geography; shot defender pool = get-back only
closest_stopping_defender = None  # Defender who is ahead AND within ±6 y-coords
closest_defender_overall = None   # Closest defender among GET-BACK PLAYERS ONLY (for shot attempts)
closest_distance_overall = float('inf')

for defender in def_lineup.values():
    defender_id = defender.player_id
    defender_outlet_x = get_defender_coords_x(defender, most_recent_shot_turn)
    defender_outlet_y = get_defender_coords_y(defender, most_recent_shot_turn)
    
    x_distance = abs(defender_outlet_x - ball_handler_outlet_x)
    y_distance = abs(defender_outlet_y - ball_handler_outlet_y)
    total_distance = (x_distance ** 2 + y_distance ** 2) ** 0.5
    
    # Track closest defender overall ONLY among get-back players
    if defender_id in getback_player_ids and total_distance < closest_distance_overall:
        closest_distance_overall = total_distance
        closest_defender_overall = defender
    
    # Check if defender is ahead (x-coordinate check) and within ±6 y
    is_ahead = (defender_outlet_x <= ball_handler_outlet_x) if is_away_offense else (defender_outlet_x >= ball_handler_outlet_x)
    is_within_y_range = abs(defender_outlet_y - ball_handler_outlet_y) <= 6
    if is_ahead and is_within_y_range:
        defender_ahead = True
        x_distance_only = abs(defender_outlet_x - ball_handler_outlet_x)
        if x_distance_only < closest_stopping_distance:
            closest_stopping_distance = x_distance_only
            closest_stopping_defender = defender

num_getback = len(getback_player_ids)
# Shot defender only when 1 or 2 get-back; when ball handler beats defender, exclude stopper from pool
if defender_ahead and closest_stopping_defender:
    # skill check...
    if ball_handler_wins:
        # Shot defender = closest get-back by distance EXCLUDING stopper_id (loop def_lineup, filter getback_player_ids and id != stopper_id)
        fb_roles["defender"] = shot_def  # or None if no other get-back
        fb_roles["defender_count"] = 1 if fb_roles["defender"] else 0
else:
    event_type = "SHOT"
    if num_getback in (1, 2) and closest_defender_overall:
        fb_roles["defender"] = closest_defender_overall
        fb_roles["defender_count"] = num_getback
    else:
        fb_roles["defender"] = None
        fb_roles["defender_count"] = 0
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
- Ball handler (shooter) moves to **shot spot near rim** (basket ± 2-6, ±6 Y). The backend always sets this spot for shot attempts (see "Shot spot (ball handler end position) – backend" below).
- Defender follows to position 1 x-coord toward basket from shooter (home: +1, away: −1), ±2 y from shooter
- Get-back defenders chase toward basket
- Rebounders move to random x=5-20 spots from basket, y=rim_y ± 10 (clamped)
- **Ball flight**: MAKE/MISS → ball to rim (or adjusted rim for make). **BLOCK** → ball to **block spot** when `ball_bounce_x`/`ball_bounce_y` are present; then bounce from that spot, "Block!" announcement, and rebound/DREB same as miss.
- **Early Termination**: 
  - Made shot: Rebounder animations stop when ball hits rim
  - Missed or blocked shot: Rebounder animations stop when rebounder grabs ball

**Shot spot (ball handler end position) – backend**

In `capture_fast_break_animation()` (BackEnd/models/animator.py), the ball handler's end position determines where the shot is taken and is exposed as `turn_result["shot_spot"]` for the frontend. It is set as follows:

1. **Ball handler beats defender** (`hold_up` and `ball_handler_beats_defender`): Shot spot **near the rim** (same as below). Frontend uses `animateFastBreakShotWithStopper()` and may use local shot spot; backend still provides rim spot for consistency.
2. **Defensive stop** (`hold_up` True, outlet set): Ball handler ends at **confrontation spot** (outlet position + 5–10 x toward basket, ±3 y). No shot; this is the stop position.
3. **Shot attempt with outlet, no defensive stop** (`hold_up` False, outlet set): Shot spot **near the rim** (same logic as case 1). Previously this used "outlet + 5–10", which caused the shot to animate from the top-of-key area; the fix ensures all shot attempts get a rim shot spot so the animation shows the shot from near the basket.
4. **Fallback** (no outlet): Defensive stop → top of key; shot attempt → near rim.

The frontend uses `turnData.shot_spot` when present (FAST_BREAK handler) so the shot animates from the correct position.

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
- **`FB_F` / `FB_N`**: Retired — not tracked; use **S / A / %** from **`FB_S`** / **`FB_A`**.

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
- **`Fast_Break_Entries`** (Offense): Incremented each time a team runs a Fast Break (in parallel with per-play **`A`** below)
- **`Fast_Break_Success`** (Offense): Incremented only when Fast Break result_type is:
  - `MAKE`, or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul on the break)
  - **Note**: `MISS` or `TURNOVER` do NOT count as team success (they count as defensive success)
- **`fast_break_plays`** (Offense): Per-play **`A`** / **`S`** for `covert_release`, `rim_runner`, `thirty_two`, `after_steal` (see `BackEnd/constants/fast_break_play_types.py`). DREB outlet (incl. fallback outlet) → **`covert_release`**; steal entry → **`after_steal`**. Same success rules as **`Fast_Break_Success`**, applied to the active play bucket. **`rim_runner`** / **`thirty_two`** reserved until those plays ship.
- Turn payloads include **`fast_break_play`** for the active bucket.
- **`vs_Fast_Break.used`** (Defense): Incremented each time defending a Fast Break
- **`vs_Fast_Break.success`** (Defense): Incremented when Fast Break result_type is:
  - `DEFENSIVE_STOP`, or
  - `MISS`, or
  - `TURNOVER`, or
  - `FOUL` where `foul_team == "OFFENSE"`
- **Alignment with player stats:** Player **`FB_S`** matches team **`Fast_Break_Success`** (only `MAKE` or defensive foul). A `MISS` without defensive foul is not a success for the team or player **`FB_S`**.

**Special Handling:**
- **`Outlet_Score_List`**: Excluded from stat delta calculations (it's a list, not numeric)
- **Team Stats Aggregation**: `Outlet_Score_List` is concatenated (not summed) when aggregating team stats
- **Stat Deltas**: `Outlet_Score_List` and `REB` are excluded from delta calculations in `turn_manager.py`

**Box Score Display:**
- Fast Break stats are available in the Box Score page
- Clicking a player's name opens a popup showing:
  - Fast Breaks: Offense and Defense as **S / A / %** (with hint row); Outlet Passes: Att / Score
- Scouting-notes per-play FB lines (separate UI work) use **`fast_break_plays`** in scouting data

### Key Files

- `BackEnd/engine/fast_break_trigger.py`
  - `FastBreakTrigger` - `DEFENSE_RELEASE_CHANCES` by `fast_breaks` (0–4); steal trigger helper
  - `can_trigger_from_dreb()` - Legacy PG/SG release tuple (live DREB uses Covert Release in `shot_manager`)
  - `can_trigger_from_steal()` - Steal → fast break chance
- `BackEnd/engine/covert_release.py`
  - Covert Release: defender farthest from rim (excluding shooter’s matchup); **AG**-based x floors + **IQ** (`good_release` / `good_d_release`) y/x bands; HOME orientation + **x** mirror for away FB offense
- `BackEnd/constants/fast_break_play_types.py` — Play keys, `default_fast_break_plays()`, `ensure_fast_break_plays()`, `play_key_for_fast_break_entry()`
- `BackEnd/engine/phase_resolution.py`
  - `resolve_fast_break_logic()` - Determines defensive stop vs. shot attempt; increments **`fast_break_plays`** and sets **`fast_break_play`**
  - Uses coordinate comparison in HOME orientation
  - Stores `ball_handler_outlet_x/y`, `is_away_offense`, `getback_player_ids` in `fb_roles`
- `BackEnd/models/shot_manager.py`
  - `_calculate_getback_coordinates(..., good_d=)` / `_calculate_release_coordinates(..., good_release=)` — pass each player’s **AG** into `covert_release` for DREB/outlet positioning
  - Stores `offense_getback_coords` and `defense_release_coords` in turn results
- `BackEnd/models/animator.py`
  - `capture_fast_break_animation()` - Builds animation packet
  - Uses `fb_roles` for ball handler outlet position and `is_away_offense`
  - **Ball handler end position (shot spot)**: Defensive stop → confrontation spot (outlet + 5–10); shot attempt (with or without outlet) → shot spot near rim (so the shot always animates from near the basket, not from top-of-key). Exposed as `turn_result["shot_spot"]` in phase_resolution for frontend use.
- `FrontEnd/static/js/phaser/animation/fastBreak.js`
  - `runFastBreakSequence()` - Orchestrates fast break animation; routes MAKE, MISS, and **BLOCK** to shot path (not defensive stop)
  - `animateOutletPhase()` - Handles outlet pass (no player movement)
  - `animateDefensiveStop()` - Handles defensive stop animation
  - `animateFastBreakShot()` - Handles shot attempt (MAKE/MISS/BLOCK): shot spot move, ball to rim or block spot, then make/miss/block outcome (BLOCK: block announcement, bounce from block spot, rebound/DREB)
  - `animateFastBreakShotWithStopper()` - Same outcome handling for BLOCK (block spot target, block announcement, bounce from block spot, rebound/DREB)
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

- **Additional play types**: More DREB → outlet play types (beyond Covert Release) may layer on top of this flow; scope and triggers TBD
- **Fast Break Fouls**: Add foul handling during fast break sequences
- **Fast Break Turnovers**: Add turnover handling during fast break sequences

