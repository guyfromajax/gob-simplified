
**Base Constants**
1. HARD_SHOOTING_FOUL_THRESHOLD (varies by shot_type):
   - Inside: 50 (hard shooting foul threshold)
   - Attack: 70 (hard shooting foul threshold)
   - Outside: 30 (hard shooting foul threshold)
2. SOFT_SHOOTING_FOUL_THRESHOLD (varies by shot_type):
   - Inside: 110 (soft shooting foul threshold)
   - Attack: 130 (soft shooting foul threshold)
   - Outside: 90 (soft shooting foul threshold)
3. SOFT_PROB = 0.16 (probability for soft foul bands)
4. THREE_POINTER_FOUL_MISS_CHANCE = 0.4 (40% chance foul forces miss on 3-pointers)
5. TWO_POINTER_FOUL_MISS_CHANCE = 0.2 (20% chance foul forces miss on 2-pointers)

**Shot Resolution Flow (12 Steps)**
1. Extract Roles
   - shooter, passer, screener, defender, second_defender from roles dict
   - Get playcall from `roles.get("motion_playcall")` or `game_state["current_playcall"]`
     - motion_playcall: Used for Motion offense (determined during Motion shot resolution)
     - current_playcall: Used for Set plays (from game state)
   - Get defense_call from `game_state["defense_playcall"]`

2. Determine Shot Type
   - is_three = `is_three_point_shot(shooter, roles)` (checks shooter spot against THREE_POINT_SPOTS)
   - is_paint = `is_paint_shot(shooter, roles)` (checks shooter spot against PAINT_SPOTS)
   - shot_type = `roles.get("shot_type")` (from Motion offense) OR determined from skeleton analysis (for Set plays)
     - Motion offense: shot_type already determined (inside/attack/outside)
     - Set plays: shot_type determined from location + drive detection (same logic as Motion plays)
       - Find shooter's location in final shoot step
       - Check if there was a "drive" action before the shoot action
       - If location in PAINT_SPOTS and has_drive → "attack"
       - If location in PAINT_SPOTS and no drive → "inside"
       - Otherwise → "outside"

3. Get Shot Threshold
   - Check for `game_state["balancing_shot_threshold_override"]` (one-time override)
     - Triggered when score difference exceeds threshold based on quarter and team attributes (fight/discipline)
     - Trailing team: -10 (easier shots)
     - Leading team: 190 (harder shots)
   - Otherwise use `off_team.team_attributes["shot_threshold"]`

4. Apply Three-Point Modifier
   - if is_three: shot_threshold += (100 - (random.randint(1, 5) * momentum))
     - Higher momentum = easier three-pointers (lower threshold modifier)

5. Apply Variant Modifier
   - Get variant from `skeleton.get("_variant")`
   - successful: -50 to threshold
   - mid_play_change: 0 (no change)
   - contested: +25 to threshold
   - broken: +100 to threshold

6. Calculate Shot Score (`calculate_shot_score()`)
   a. Base Score: `sum(shooter_attrs[attr] * (weight / 10) for attr, weight in shot_type_weights.items()) * random.randint(1, 6)`
      - Uses shot_type (inside/attack/outside) instead of playcall for attribute weights
      - Shot type weights from PLAYCALL_ATTRIBUTE_WEIGHTS:
        - Inside: SC=6, ST=2, IQ=1, CH=1
        - Attack: SC=5, AG=2, ST=1, IQ=1, CH=1
        - Outside: SH=8, IQ=1, CH=1
   
   b. Passing/Dribbling Bonus
      - if passer: `(passer.PS * 0.8 + passer.IQ * 0.2) * random(1-6) * 0.2`
      - else: `(shooter.AG * 0.8 + shooter.IQ * 0.2) * random(1-6) * 0.2`
   
   c. Defense Score (varies by shot type)
      - Paint shots: `(ID * 0.6 + ST * 0.2 + IQ * 0.1 + CH * 0.1) * random(1-6)`
      - Three-point: `(OD * 0.8 + IQ * 0.1 + CH * 0.1) * random(1-6)`
      - Mid-range: `(OD * 0.3 + ID * 0.3 + AG * 0.1 + ST * 0.1 + IQ * 0.1 + CH * 0.1) * random(1-6)`
   
   d. Check Defensive Foul (thresholds vary by shot_type)
      - Inside shots: hard_threshold = 50 + defense_team.fight, soft_threshold = 110 + defense_team.fight
      - Attack shots: hard_threshold = 70 + defense_team.fight, soft_threshold = 130 + defense_team.fight
      - Outside shots: hard_threshold = 30 + defense_team.fight, soft_threshold = 90 + defense_team.fight
      - if defense_score < hard_threshold: d_foul = True
      - elif defense_score < soft_threshold: d_foul = random() < SOFT_PROB (0.16)
      - else: d_foul = False
   
   e. Apply Defense Penalty
      - Single defender: shot_score -= defense_score * 0.2
      - Double team: shot_score -= (defense_score * 0.14) + (second_defense_score * 0.14)
   
   f. Defense Scheme Multiplier
      - if Zone defense AND three-point: shot_score *= 1.1 (makes shot more likely to be successful)
      - Otherwise: no multiplier
   
   g. Help Defense Check
      - REMOVED (will be replaced with location-based check in future)
   
   h. Screener Bonus
      - if screener: shot_score += `calculate_screen_score(screener_attrs) * 0.15`
      - Screen score: `(ST * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1-6)`
   
   i. Gravity Boost
      - Calculate gravity from off-ball players (excluding shooter, passer, screener)
      - Gravity score per player: `(SH * 0.3 + SC * 0.3 + IQ * 0.4)`
      - gravity_boost = total_gravity * 0.02
      - shot_score += gravity_boost

7. Apply Motion Attack Penalty
   - if `roles.get("motion_attack_penalty")` or `game_state.get("motion_attack_penalty")` > 0:
     - Applied when Motion offense chooses "attack" shot type and player is stopped short of basket
     - Penalty = distance from final shot location to basket (calculated in `_apply_attack_penalty()`)
     - shot_score -= penalty
     - Clear penalty after use

8. Determine Make/Miss
   - made = shot_score >= shot_threshold

9. Shooting Foul Calibration (if d_foul)
   - if is_three: 40% chance foul forces miss (THREE_POINTER_FOUL_MISS_CHANCE = 0.4)
   - else: 20% chance foul forces miss (TWO_POINTER_FOUL_MISS_CHANCE = 0.2)
   - if calibration roll triggers: made = False

10. Record Shot Attempt Stats
    - shooter.record_stat("FGA")
    - if is_three: shooter.record_stat("3PTA")

11. Final Result
    - result["result_type"] = "MAKE" if made else "MISS"
    - If made: Calculate points (3 if is_three, else 2), record FGM, 3PTM, PIP if applicable
    - If miss: Determine rebound (geography-based system)

12. Player Positioning (for all shots)
    - Determine offense get-back players (based on rebounding strategy setting)
    - Determine defense release players (based on fast_breaks strategy setting)
    - Calculate coordinates for animation


**Long Form Documentation**

## Shot Resolution System

### Base Values

Shot resolution uses the following base constants:

- **Foul Thresholds (vary by shot_type)**:
  - **Inside shots**: HARD=50, SOFT=110
  - **Attack shots**: HARD=70, SOFT=130
  - **Outside shots**: HARD=30, SOFT=90
- **SOFT_PROB**: 0.16 (probability for soft foul bands)
- **THREE_POINTER_FOUL_MISS_CHANCE**: 0.4 (40% chance foul forces miss on 3-pointers)
- **TWO_POINTER_FOUL_MISS_CHANCE**: 0.2 (20% chance foul forces miss on 2-pointers)

### Shot Resolution Flow

The shot resolution system processes outcomes in the following order:

#### Step 1: Extract Roles

Extract player roles and game state information:
- **shooter**: Player taking the shot
- **passer**: Player who passed the ball (can be None)
- **screener**: Player who set a screen (can be None)
- **defender**: Primary defender guarding the shooter
- **second_defender**: Second defender in double-team situations (can be None)
- **playcall**: Offensive playcall from `roles.get("motion_playcall")` or `game_state["current_playcall"]`
  - **motion_playcall**: Used for Motion offense (determined during Motion shot resolution)
  - **current_playcall**: Used for Set plays (from game state)
- **defense_call**: Defensive playcall from `game_state["defense_playcall"]` ("Man" or "Zone")

#### Step 2: Determine Shot Type

**Three-Point Shot Detection:**
- Uses `is_three_point_shot(shooter, roles)` to check if shooter's spot is in `THREE_POINT_SPOTS`
- THREE_POINT_SPOTS includes: key, deep key, upper wing, lower wing, upper midwing, lower midwing, upper midcorner, lower midcorner, upper corner, lower corner, deep upper baseline, deep lower baseline

**Paint Shot Detection:**
- Uses `is_paint_shot(shooter, roles)` to check if shooter's spot is in `PAINT_SPOTS`
- PAINT_SPOTS includes: lower lowpost, lower midpost, upper lowpost, upper midpost, midlane

**Shot Type Determination (inside/attack/outside):**
- **Motion offense**: `shot_type` already determined in `roles.get("shot_type")` (from Motion shot resolution)
- **Set plays**: `shot_type` determined from skeleton analysis using location-based logic (same as Motion plays):
  1. Find the final step where shooter has "shoot" action
  2. Get shooter's location from that step
  3. Check if there was a "drive" action before the shoot action (in previous steps)
  4. Determine shot_type:
     - If location is in `PAINT_SPOTS` and there was a drive action → `"attack"`
     - If location is in `PAINT_SPOTS` and no drive action → `"inside"`
     - Otherwise → `"outside"`
  - **Fallback**: If location not found, use playcall (Inside→inside, Attack/Set→attack, otherwise→outside)
- **Note**: Shot type is used for attribute weights in shot score calculation, not playcall. This ensures consistent logic between Motion and Set plays.

#### Step 3: Get Shot Threshold

**Threshold Sources:**
1. **Balancing Override**: Check for `game_state["balancing_shot_threshold_override"]` (one-time override for game balancing)
   - **Trigger Conditions**: When score difference exceeds threshold based on quarter and team attributes (fight/discipline)
   - **Trailing team**: Gets `-10` (easier shots)
   - **Leading team**: Gets `190` (harder shots)
   - Thresholds by quarter:
     - Trailing: Q1=6, Q2=9, Q3=12, Q4=15
     - Leading: Q1=9, Q2=12, Q3=15, Q4=18
   - Adjusted by team attributes: trailing team subtracts `fight`, leading team adds `discipline`
2. **Team Attribute**: Otherwise use `off_team.team_attributes["shot_threshold"]` (base team shooting ability)

#### Step 4: Apply Three-Point Modifier

**Three-Point Penalty with Momentum:**
- If `is_three`: `shot_threshold += (100 - (random.randint(1, 5) * momentum))`
- **Higher momentum** = easier three-pointers (lower threshold modifier)
- Example: momentum=5, random(1-5)=3 → modifier = 100 - (3 * 5) = 85 (easier than base 100)

#### Step 5: Apply Variant Modifier

**Skeleton Variant Impact:**
- Get variant from `skeleton.get("_variant")` (determined by HCO resolution system)
- Variant modifiers:
  - **successful**: `-50` to threshold (play worked perfectly, easier shot)
  - **mid_play_change**: `0` (no change, neutral)
  - **contested**: `+25` to threshold (defense engaged, harder shot)
  - **broken**: `+100` to threshold (defense disrupted, very difficult shot)

#### Step 6: Calculate Shot Score

The `calculate_shot_score()` function calculates the final shot score through multiple components:

**6a. Base Score Calculation:**
```python
base_score = sum(
    shooter_attrs[attr] * (weight / 10) 
    for attr, weight in shot_type_weights.items()
) * random.randint(1, 6)
```

**Shot Type Attribute Weights (PLAYCALL_ATTRIBUTE_WEIGHTS):**
- **Inside**: SC=6, ST=2, IQ=1, CH=1
- **Attack**: SC=5, AG=2, ST=1, IQ=1, CH=1
- **Outside**: SH=8, IQ=1, CH=1
- **Note**: Uses `shot_type` (inside/attack/outside) instead of playcall for weights lookup

**6b. Passing/Dribbling Bonus:**
- **If passer exists:**
  ```python
  passer_score = (passer.PS * 0.8 + passer.IQ * 0.2) * random.randint(1, 6)
  shot_score += passer_score * 0.2
  ```
- **If no passer (dribble):**
  ```python
  dribble_score = (shooter.AG * 0.8 + shooter.IQ * 0.2) * random.randint(1, 6)
  shot_score += dribble_score * 0.2
  ```

**6c. Defense Score (varies by shot type):**
- **Paint shots** (ID-focused defense):
  ```python
  defense_score = (
      ID * 0.6 + ST * 0.2 + IQ * 0.1 + CH * 0.1
  ) * random.randint(1, 6)
  ```
- **Three-point shots** (OD-focused defense):
  ```python
  defense_score = (
      OD * 0.8 + IQ * 0.1 + CH * 0.1
  ) * random.randint(1, 6)
  ```
- **Mid-range shots** (balanced defense):
  ```python
  defense_score = (
      OD * 0.3 + ID * 0.3 + AG * 0.1 + ST * 0.1 + IQ * 0.1 + CH * 0.1
  ) * random.randint(1, 6)
  ```

**6d. Check Defensive Foul (thresholds vary by shot_type):**
- **Inside shots:**
  ```python
  hard_threshold = 50 + defense_team.fight
  soft_threshold = 110 + defense_team.fight
  ```
- **Attack shots:**
  ```python
  hard_threshold = 70 + defense_team.fight
  soft_threshold = 130 + defense_team.fight
  ```
- **Outside shots:**
  ```python
  hard_threshold = 30 + defense_team.fight
  soft_threshold = 90 + defense_team.fight
  ```
- **Foul Determination:**
  - If `defense_score < hard_threshold`: `d_foul = True` (hard foul)
  - Elif `defense_score < soft_threshold`: `d_foul = random() < SOFT_PROB (0.16)` (soft foul, 16% chance)
  - Else: `d_foul = False` (no foul)

**6e. Apply Defense Penalty:**
- **Single defender:**
  ```python
  shot_score -= defense_score * 0.2
  ```
- **Double team (two defenders):**
  ```python
  shot_score -= (defense_score * 0.14) + (second_defense_score * 0.14)
  ```
  - Each defender applies 14% penalty (total 28%, but less than single defender's 20% due to coordination)

**6f. Defense Scheme Multiplier:**
- **Zone defense vs three-point:**
  ```python
  shot_score *= 1.1  # Makes shot more likely to be successful
  ```
- **Otherwise**: No multiplier applied

**6g. Help Defense Check:**
- **REMOVED** (will be replaced with location-based check in future)

**6h. Screener Bonus:**
- **If screener exists:**
  ```python
  screen_score = (ST * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random.randint(1, 6)
  shot_score += screen_score * 0.15
  ```

**6i. Gravity Boost:**
- **Calculate gravity from off-ball players:**
  - Exclude shooter, passer, and screener
  - **Gravity score per player:**
    ```python
    gravity_score = SH * 0.3 + SC * 0.3 + IQ * 0.4
    ```
  - **Total gravity boost:**
    ```python
    total_gravity = sum(gravity_score for all off-ball players)
    gravity_boost = total_gravity * 0.02
    shot_score += gravity_boost
    ```

#### Step 7: Apply Motion Attack Penalty

**Motion Offense Attack Penalty:**
- If `roles.get("motion_attack_penalty")` or `game_state.get("motion_attack_penalty")` > 0:
  - **Applied when**: Motion offense chooses "attack" shot type and player is stopped short of basket
  - **Penalty calculation**: Distance from final shot location to basket (calculated in `_apply_attack_penalty()`)
  - **No penalty** for ideal spots: "basketSpot", "upper lowPost", "lower lowPost"
  - **Penalty formula**: `penalty = abs(shot_coords["x"] - basket_coords["x"])`
  ```python
  shot_score -= motion_attack_penalty
  game_state.pop("motion_attack_penalty", None)  # Clear after use
  ```

#### Step 8: Determine Make/Miss

**Final Comparison:**
```python
made = shot_score >= shot_threshold
```

#### Step 9: Shooting Foul Calibration

**Foul Miss Chance:**
- If `d_foul` is True (shooting foul occurred):
  - **Three-pointers:**
    ```python
    if random.random() < THREE_POINTER_FOUL_MISS_CHANCE (0.4):
        made = False  # 40% chance foul forces miss
    ```
  - **Two-pointers:**
    ```python
    if random.random() < TWO_POINTER_FOUL_MISS_CHANCE (0.2):
        made = False  # 20% chance foul forces miss
    ```
- This calibration ensures that shooting fouls don't always result in made shots (realistic basketball behavior)

#### Step 10: Record Shot Attempt Stats

**Stat Tracking:**
- `shooter.record_stat("FGA")` (field goal attempt)
- If `is_three`: `shooter.record_stat("3PTA")` (three-point attempt)

#### Step 11: Final Result

**Result Determination:**
- `result["result_type"] = "MAKE" if made else "MISS"`

**If Made:**
- Calculate points: `3 if is_three else 2`
- Record stats:
  - `shooter.record_stat("FGM")` (field goal made)
  - If `is_three`: `shooter.record_stat("3PTM")` (three-point made)
  - If `is_paint`: `shooter.record_stat("PIP", amount=points)` (points in paint)
- If `passer` exists: `passer.record_stat("AST")` (assist)
- If `screener` exists: `screener.record_stat("SCR_S")` (successful screen)
- If `d_foul`: Set up AND-1 free throw situation

**If Missed:**
- If `defender` exists: `defender.record_stat("DEF_S")` (defensive stop)
- Determine rebound using unified geography-based rebound system
- Check for block (based on BLOCK_PROBABILITY by playcall)

#### Step 12: Player Positioning

**For All Shots (Made or Missed):**
- Players release/get back when shot is TAKEN, not when outcome is determined
- **Offense get-back players:**
  - Based on `off_team.strategy_settings.get("rebounding", 2)` (0-4 scale)
  - Probability distribution determines 0, 1, or 2 players getting back
  - Typically PG and/or SG get back on defense
- **Defense release players:**
  - Based on `def_team.strategy_settings.get("fast_breaks", 2)` (0-4 scale)
  - Determined by `FastBreakTrigger.can_trigger_from_dreb()`
  - Release player becomes outlet receiver for potential fast break
- **Coordinate calculation:**
  - Get-back and release player coordinates calculated in backend
  - Stored in result for frontend animation
  - Coordinates updated in player.coords for subsequent play logic

### Key Implementation Notes

1. **Shot Type vs Playcall**: Shot score calculation uses `shot_type` (inside/attack/outside) instead of `playcall` for attribute weights
2. **Motion vs Set Plays**: Both Motion and Set plays use location-based logic to determine `shot_type`:
   - **Motion offense**: Determines `shot_type` during shot resolution (checks possibilities, builds weighted list, selects)
   - **Set plays**: Determines `shot_type` from skeleton analysis (checks shooter location and drive action history)
   - Both use the same logic: paint spot + drive = attack, paint spot + no drive = inside, otherwise = outside
3. **Three-Point Momentum**: Three-point threshold modifier uses momentum: `100 - (random(1-5) * momentum)` (higher momentum = easier threes)
4. **Foul Thresholds by Shot Type**: Different hard/soft thresholds for inside (50/110), attack (70/130), and outside (30/90) shots
5. **Defense Scheme Multiplier**: Only Zone vs 3pt gets 1.1x multiplier (makes shot more likely to be successful)
6. **Help Defense**: Removed (will be replaced with location-based check in future)
7. **Motion Attack Penalty**: Applied when Motion offense attack shot is stopped short of basket (penalty = distance to basket)
8. **Foul Calibration**: Shooting fouls don't guarantee made shots (40% miss chance on 3pt, 20% on 2pt)
9. **Player Positioning**: Happens at shot attempt, not outcome (players don't know if shot will be made)
10. **Balancing Override**: Triggered when score difference exceeds quarter-based thresholds adjusted by team attributes

### Status

✅ **Shot Resolution**: Implementation complete (January 2025)
- Unified shot resolution for HCO, Fast Break, Putback, and Free Throw
- Shot type-based attribute weights (inside/attack/outside)
- Shot type-specific foul thresholds
- Momentum-based three-point modifier
- Geography-based rebound system for missed shots
- Shooting foul calibration for realistic outcomes
- Player positioning system for fast break opportunities

### Key Files

- `BackEnd/models/shot_manager.py`: `resolve_shot()`, `calculate_shot_score()`, `check_defensive_foul_on_shot()`, `resolve_fast_break_shot()`
- `BackEnd/constants/__init__.py`: PLAYCALL_ATTRIBUTE_WEIGHTS, THREE_POINT_SPOTS, PAINT_SPOTS
- `BackEnd/utils/shared.py`: `calculate_gravity_score()`, `calculate_screen_score()`, `calculate_bounce_spot()`, `determine_rebounder()`
- `BackEnd/engine/phase_resolution.py`: `_apply_attack_penalty()`, `resolve_motion_offense_shot()`, `apply_balancing_system()`
