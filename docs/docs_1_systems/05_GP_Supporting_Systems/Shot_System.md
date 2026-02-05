
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
     - Set plays: shot_type determined from location + attack detection (see Attack detection below)
       - If location in PAINT_SPOTS and has_drive (attack) → "attack"
       - If location in PAINT_SPOTS and no attack → "inside"
       - Otherwise → "outside"
   - **Attack detection (Set plays, HCO):** has_drive is True only when:
     - Shoot step = last step in skeleton; shooter has action "shoot" there.
     - Shoot location (from that step) is one of: upper lowPost, lower lowPost, upper midPost, lower midPost, midLane (PAINT_SPOTS).
     - Step immediately before: shooter has action "handle_ball" and his location is not equal to his shoot location (i.e. he moved into the shot).

3. Get Shot Threshold
   - Check for `game_state["balancing_shot_threshold_override"]` (one-time override)
     - Triggered when score difference exceeds threshold based on quarter and team attributes (fight/discipline)
     - Trailing team: -10 (easier shots)
     - Leading team: 190 (harder shots)
   - Otherwise use `off_team.team_attributes["shot_threshold"]`

4. Apply Three-Point Modifier
   - if is_three: shot_threshold += (40 - (random.randint(1, 5) * momentum))
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
      - Single defender: shot_score -= defense_score * 0.6
      - Double team: shot_score -= (defense_score * 0.35) + (second_defense_score * 0.35)
   
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
  - Inside: HARD=50, SOFT=110
  - Attack: HARD=70, SOFT=130
  - Outside: HARD=30, SOFT=90
- **SOFT_PROB**: 0.16
- **THREE_POINTER_FOUL_MISS_CHANCE**: 0.4
- **TWO_POINTER_FOUL_MISS_CHANCE**: 0.2

### Shot Resolution Flow

#### Step 1: Extract Roles
- shooter, passer, screener, defender, second_defender
- playcall: `roles.get("motion_playcall")` (Motion) or `game_state["current_playcall"]` (Set)
- defense_call: `game_state["defense_playcall"]` ("Man" or "Zone")

#### Step 2: Determine Shot Type
- **is_three**: Check shooter spot against THREE_POINT_SPOTS
- **is_paint**: Check shooter spot against PAINT_SPOTS
- **shot_type**: 
  - Motion: `roles.get("shot_type")` (already determined)
  - Set: Analyze skeleton (location + attack detection)
    - Paint spot + attack (has_drive) → "attack"
    - Paint spot + no attack → "inside"
    - Otherwise → "outside"
- **Attack detection (Set plays):** has_drive is set to True only when:
  1. Shoot step is the last step; shooter has action `"shoot"` there.
  2. Shoot location (from that step) is in PAINT_SPOTS: upper lowPost, lower lowPost, upper midPost, lower midPost, midLane.
  3. In the step immediately before the shoot step: the shooter has action `"handle_ball"` and his location is not equal to his shoot location (he moved into the shot). Locations compared case-insensitively.

#### Step 3: Get Shot Threshold
- **Balancing Override**: `game_state["balancing_shot_threshold_override"]` (if score diff exceeds quarter-based threshold)
  - Trailing: -10, Leading: 190
- **Otherwise**: `off_team.team_attributes["shot_threshold"]`

#### Step 4: Apply Three-Point Modifier
- If `is_three`: `shot_threshold += (100 - (random.randint(1, 5) * momentum))`
- Higher momentum = easier three-pointers

#### Step 5: Apply Variant Modifier
- From `skeleton.get("_variant")`: successful=-50, mid_play_change=0, contested=+25, broken=+100

#### Step 6: Calculate Shot Score

**6a. Base Score:**
```python
sum(shooter_attrs[attr] * (weight / 10) for attr, weight in shot_type_weights.items()) * random.randint(1, 6)
```
- Inside: SC=6, ST=2, IQ=1, CH=1
- Attack: SC=5, AG=2, ST=1, IQ=1, CH=1
- Outside: SH=8, IQ=1, CH=1

**6b. Passing/Dribbling Bonus:**
- Passer: `(PS * 0.8 + IQ * 0.2) * random(1-6) * 0.2`
- Dribble: `(AG * 0.8 + IQ * 0.2) * random(1-6) * 0.2`

**6c. Defense Score:**
- Paint: `(ID * 0.6 + ST * 0.2 + IQ * 0.1 + CH * 0.1) * random(1-6)`
- Three-point: `(OD * 0.8 + IQ * 0.1 + CH * 0.1) * random(1-6)`
- Mid-range: `(OD * 0.3 + ID * 0.3 + AG * 0.1 + ST * 0.1 + IQ * 0.1 + CH * 0.1) * random(1-6)`

**6d. Defensive Foul Check:**
- Thresholds: Inside(50/110), Attack(70/130), Outside(30/90) + fight
- If `defense_score < hard_threshold`: d_foul = True
- Elif `defense_score < soft_threshold`: d_foul = random() < 0.16
- Else: d_foul = False

**6e. Defense Penalty:**
- Single: `shot_score -= defense_score * 0.2`
- Double team: `shot_score -= (defense_score * 0.14) + (second_defense_score * 0.14)`

**6f. Defense Scheme Multiplier:**
- Zone vs 3pt: `shot_score *= 1.1`

**6g. Screener Bonus:**
- If screener: `shot_score += (ST * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1-6) * 0.15`

**6h. Gravity Boost:**
- Per player: `(SH * 0.3 + SC * 0.3 + IQ * 0.4)`
- Total: `shot_score += total_gravity * 0.02`

#### Step 7: Apply Motion Attack Penalty
- If `motion_attack_penalty > 0`: `shot_score -= penalty`
- Penalty = distance from shot location to basket (when stopped short)

#### Step 8: Determine Make/Miss
- `made = shot_score >= shot_threshold`

#### Step 9: Shooting Foul Calibration
- If d_foul: 3pt=40% miss chance, 2pt=20% miss chance

#### Step 10: Record Stats
- `shooter.record_stat("FGA")`, `shooter.record_stat("3PTA")` if is_three

#### Step 11: Final Result
- If made: Record FGM, 3PTM, PIP, AST, SCR_S, set up AND-1 if d_foul
- If miss: Record DEF_S, determine rebound (geography-based), check block

#### Step 12: Player Positioning
- Get-back players (offense): Based on rebounding strategy (0-4 scale)
- Release players (defense): Based on fast_breaks strategy (0-4 scale)
- Coordinates calculated in backend for animation

### Key Implementation Notes

1. **Shot Type vs Playcall**: Shot score calculation uses `shot_type` (inside/attack/outside) instead of `playcall` for attribute weights
2. **Motion vs Set Plays**: Both Motion and Set plays use location-based logic to determine `shot_type`:
   - **Motion offense**: Determines `shot_type` during shot resolution (checks possibilities, builds weighted list, selects)
   - **Set plays**: Determines `shot_type` from skeleton analysis (shooter location + attack detection)
   - Attack detection (Set): shoot step = last step; shoot location in PAINT_SPOTS; step before has shooter with action `"handle_ball"` and different location → has_drive = True. Paint + has_drive = attack; paint + no has_drive = inside; else = outside.
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
