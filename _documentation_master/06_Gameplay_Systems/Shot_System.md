
**Base Constants**
1. HARD_SHOOTING_FOUL_THRESHOLD (varies by shot_type):
   - Inside: 35 (hard shooting foul threshold)
   - Attack: 80 (hard shooting foul threshold)
   - Outside: 20 (hard shooting foul threshold)
2. SOFT_SHOOTING_FOUL_THRESHOLD (varies by shot_type):
   - Inside: 105 (soft shooting foul threshold)
   - Attack: 140 (soft shooting foul threshold)
   - Outside: 80 (soft shooting foul threshold)
3. SOFT_PROB = 0.16 (probability for soft foul bands)
4. THREE_POINTER_FOUL_MISS_CHANCE = 0.4 (40% chance foul forces miss on 3-pointers)
5. TWO_POINTER_FOUL_MISS_CHANCE = 0.2 (20% chance foul forces miss on 2-pointers)
6. **Zone shot-type threshold deltas (HCO / Final Turn only, `resolve_shot`):** Added to `shot_threshold` when `offensive_state == "HCO"` and not fast break; **`defense_playcall`** exact strings **`2-3 Zone`** / **`3-2 Zone`**:
   - **2-3 Zone:** inside **+25**, attack **+10**, outside **−25**
   - **3-2 Zone:** outside **+50**, inside **−30**, attack **−30**

**Location: contest range, rim box, `has_contest` (implemented in `shot_manager.py`)**
1. **Shooter coordinates:** `roles["shot_spot"]` `{x,y}` when present; otherwise `shooter.coords` (defaults x=50, y=25 if missing).
2. **Attacking basket:** Home offense attacks the away rim `AWAY_RIM_COORDS` (x≈9, y≈25); away offense attacks `HOME_RIM_COORDS` (x≈91, y≈25). Same convention as the rest of the court engine.
3. **Contest (`has_contest`):** Two paths:
   - **HCO / Final Turn** (`offensive_state == "HCO"`): `has_contest = bool(defender or second_defender)` — i.e. **role-based** (whether a contesting defender role is assigned), not a geometry box.
   - **Non-HCO** (FCP, HCT, fast break): geometry box — **every** player in the defensive lineup is checked, and `has_contest` is true if any lies within **|Δx| ≤ `CONTEST_DEFENDER_DX_MAX` (8)** and **|Δy| ≤ `CONTEST_DEFENDER_DY_MAX` (8)** of the shooter.
4. **Rim box:** Axis-aligned box around the attacking basket: **|shooter_x − basket_x| ≤ 6** and **|shooter_y − basket_y| ≤ 6** (same margin on both axes).
5. **Unguarded rim shortcut (99% make):** If `shot_type` is **inside** or **attack**, the attempt is **not** a three-pointer, the shooter is **in the rim box**, and **`has_contest` is false** → resolve make/miss as **make** unless `random.randint(1, 100) == 100` (1% miss). This path **does not** run `calculate_shot_score` defense, **does not** run block reconciliation, charge/blocking foul, or defensive shooting fouls.
6. **No contest, not using the rim shortcut:** Call `calculate_shot_score(..., apply_defense=False)` — offense-only scoring (base shot score, passer/dribble, screener, gravity, zone-vs-3 multiplier still apply); **no** defense subtraction, **no** `DEF_A`, **no** `d_foul` from `check_defensive_foul_on_shot`.
7. **Contest:** Full defensive shot score, shooting-foul check, and (when applicable) block reconciliation and `calculate_charge` **only** when `has_contest` is true (charge remains **attack** shots only, plus existing fast-break defender gating).

**Three-point classification**

- Geometry primitive: `BackEnd.utils.shot_geometry.is_three_point_shot_from_coords()`.
- Canonical classification wrapper: `BackEnd.utils.shot_geometry.classify_shot_value()`.
- Backend classification is the source of truth. The frontend/UESS renderer does not infer whether a shot is worth 1, 2, or 3.
- `classify_shot_value()` returns a self-describing payload including `points`, `shot_value`, `is_three_point_shot`, `classification_coord`, `normalized_coord`, `boundary_x`, `classification_source`, and `allow_three`.
- `ShotManager.resolve_shot()` builds this payload before shot math and stamps shot results with `is_three_point_shot`, `shot_value`, `shot_spot`, `shot_classification_coord`, `shot_classification`, and `shot_classification_source`.
- Coordinate priority for field goals:
  1. Explicit backend `roles["shot_spot"]` coords.
  2. Shooter model `coords`.
  3. Legacy skeleton shoot-location name and `THREE_POINT_SPOTS` fallback only if usable coords are missing.
- The coordinate arc uses the home-offense HCO spot model (`key`, wings, midCorners, corners) and linearly interpolates the boundary x-value by shooter y. Away-offense shots mirror x with `100 - x` before testing. The helper expects display-oriented coords.
- Fast Break shots remain 2-point by default. Only explicit outside Fast Break branches with `shot_type == "outside"` and a backend `shot_spot` can classify as 3s. This covers Triangle corner/wing/kick branches without changing Steal FB, RR rim attacks, or CR rim attacks.
- Dynamic HCT procedural attack-basket shots bypass `ShotManager.resolve_shot()`, so they call the same classification wrapper before `calculate_shot_score()` and carry `is_three_point_shot` through scoring, `3PTA`/`3PTM`, points, and shooting-foul free-throw count.
- OREB putbacks are forced 2-point field goals and stamp a forced-two classification payload.
- Free throws are forced 1-point attempts. They do not use field-goal 2/3 geometry.
- Made-three SFX is stamped by the backend schema emitter only when `turn_result["is_three_point_shot"] is True`, not by raw `points == 3` and not by frontend inference.

**Shot Resolution Flow (13 Steps)**
1. Extract Roles
   - shooter, passer, screener, defender, second_defender from roles dict
   - Get playcall from `roles.get("motion_playcall")` or `game_state["current_playcall"]`
     - motion_playcall: Used for Motion offense (determined during Motion shot resolution)
     - current_playcall: Used for Set plays (from game state)
   - Get defense_call from `game_state["defense_playcall"]`

2. Determine Shot Type
   - `shot_classification = classify_shot_value(...)` via `ShotManager._build_shot_classification()`
   - `is_three = shot_classification["is_three_point_shot"]`
   - is_paint = `is_paint_shot(shooter, roles)` (checks shooter spot against PAINT_SPOTS)
   - shot_type = `roles.get("shot_type")` or `roles.get("motion_shot_type")` (Motion uses motion_shot_type) OR skeleton analysis (Set plays)
     - Motion offense: use randomly chosen type from resolve_motion_offense_shot (motion_shot_type)
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

6. Zone defense shot-type threshold (HCO / Final Turn only)
   - Applies when **not** fast break and `game_state["offensive_state"] == "HCO"` (normal HCO and Final Turn shot resolution both use HCO state; **excludes** FCP, HCT, fast break).
   - **Does not apply** to OREB putbacks (they use `shared.resolve_offensive_rebound` / `calculate_shot_score`, not `resolve_shot`).
   - If `defense_playcall` is **`2-3 Zone`**, add to `shot_threshold` by `shot_type`: **inside +25**, **attack +10**, **outside −25** (higher threshold = harder make).
   - If `defense_playcall` is **`3-2 Zone`**: **outside +50**, **inside −30**, **attack −30**.
   - **`1-3-1 Zone`** and **Man**: no adjustment from this rule.
   - Implemented in `shot_manager.py` as `_hco_zone_shot_threshold_delta()` after crowd / three-point / variant / shot-at-1 threshold lines.

7. Location layer → then Calculate Shot Score (`calculate_shot_score()`)
   - After shot threshold modifiers: compute shooter `(x,y)`, attacking basket, `has_contest`, and whether the **unguarded rim shortcut** applies (see **Location** above). Shortcut: 99% make, skip defense/foul/block/charge pipeline for that outcome.
   - Otherwise `calculate_shot_score(..., apply_defense=has_contest)`.
   a. Base Score: `sum(shooter_attrs[attr] * (weight / 10) for attr, weight in shot_type_weights.items()) * random.randint(1, 6)`
      - Uses shot_type (inside/attack/outside) instead of playcall for attribute weights
      - Shot type weights from PLAYCALL_ATTRIBUTE_WEIGHTS:
        - Inside: SC=6, ST=2, IQ=1, CH=1
        - Attack: SC=5, AG=2, ST=1, IQ=1, CH=1
        - Outside: SH=8, IQ=1, CH=1
   
   b. Passing/Dribbling Bonus
      - if passer: `(passer.PS * 0.8 + passer.IQ * 0.2) * random(1-6) * 0.2`
      - else: `(shooter.AG * 0.8 + shooter.IQ * 0.2) * random(1-6) * 0.2`
   
   c. Defense Score (varies by shot type) — **skipped when `apply_defense` is False** (no defender in contest range, and not taking the unguarded rim shortcut)
      - Paint shots: `(ID * 0.6 + ST * 0.2 + IQ * 0.1 + CH * 0.1) * random(1-6)`
      - Three-point: `(OD * 0.8 + IQ * 0.1 + CH * 0.1) * random(1-6)`
      - Mid-range: `(OD * 0.3 + ID * 0.3 + AG * 0.1 + ST * 0.1 + IQ * 0.1 + CH * 0.1) * random(1-6)`
   
   d. Check Defensive Foul (thresholds vary by shot_type) — **not run when `apply_defense` is False**
      - Inside shots: hard_threshold = 35 - defense_team.discipline, soft_threshold = 105 - defense_team.discipline
      - Attack shots: hard_threshold = 80 - defense_team.discipline, soft_threshold = 140 - defense_team.discipline
      - Outside shots: hard_threshold = 20 - defense_team.discipline, soft_threshold = 80 - defense_team.discipline
      - if defense_score < hard_threshold: d_foul = random() < HARD_PROB (0.70)
      - elif defense_score < soft_threshold: d_foul = random() < SOFT_PROB (0.16)
      - else: d_foul = False
   
   e. Apply Defense Penalty
      - Single defender: shot_score -= defense_score * 0.6
      - Double team: shot_score -= (defense_score * 0.35) + (second_defense_score * 0.35)
   
   f. Defense Scheme Multiplier
      - if Zone defense AND three-point: shot_score *= 1.1 (makes shot more likely to be successful)
      - Otherwise: no multiplier
   
   g. Help Defense Check
      - REMOVED; **location-based contest** (`has_contest` bounding box) determines whether defense/foul/block/charge logic runs (see **Location** at top of this doc)
   
   h. Screener Bonus
      - if screener: shot_score += `calculate_screen_score(screener_attrs) * 0.15`
      - Screen score: `(ST * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1-6)`
   
   i. Gravity Boost
      - Calculate gravity from off-ball players (excluding shooter, passer, screener)
      - Gravity score per player: `(SH * 0.3 + SC * 0.3 + IQ * 0.4)`
      - gravity_boost = total_gravity * 0.02
      - shot_score += gravity_boost

8. Apply Motion Attack Penalty
   - if `roles.get("motion_attack_penalty")` or `game_state.get("motion_attack_penalty")` > 0:
     - Applied when Motion offense chooses "attack" shot type and player is stopped short of basket
     - Penalty = distance from final shot location to basket (calculated in `_apply_attack_penalty()`)
     - shot_score -= penalty
     - Clear penalty after use

9. Determine Make/Miss
   - made = shot_score >= shot_threshold

10. Shooting Foul Calibration (if d_foul)
   - if is_three: 40% chance foul forces miss (THREE_POINTER_FOUL_MISS_CHANCE = 0.4)
   - else: 20% chance foul forces miss (TWO_POINTER_FOUL_MISS_CHANCE = 0.2)
   - if calibration roll triggers: made = False

11. Record Shot Attempt Stats
    - shooter.record_stat("FGA")
    - if is_three: shooter.record_stat("3PTA")

12. Final Result
    - result["result_type"] = "MAKE" if made else "MISS"
    - If made: Calculate points (3 if is_three, else 2), record FGM, 3PTM, PIP if applicable
    - If miss: Determine rebound (geography-based system)
    - Stamp classification metadata: `is_three_point_shot`, `shot_value`, `shot_spot`, `shot_classification_coord`, `shot_classification`, `shot_classification_source`

13. Player Positioning (for all shots)
    - Determine offense get-back players (based on rebounding strategy setting; HCO only — HCT / FCP / Fast Break skip get-back). The shooter is never eligible to be a get-back player; backend selection excludes them by both shooter position and shooter `player_id`.
    - Determine defense release players (based on fast_breaks strategy setting + Covert Release eligibility)
    - Calculate post-shot coordinates for **every** player and populate the four overlay maps on the turn result:
      `offense_rebounder_coords`, `defense_rebounder_coords`, `offense_getback_coords`, `defense_release_coords`.
    - `shot_manager` is the **sole authority** for post-shot placement. The MISS turn emitter absorbs these maps into its final step's `end.coords` via `_apply_post_shot_overlay`. Downstream turns (DREB / OREB / Fast Break / HCO / etc.) read those positions as their starting coords and do **not** re-decide post-shot placement. See [`Rebound_System.md`](Rebound_System.md) "Post-shot placement authority" and [`UESS_System.md`](../00_General_Systems/UESS_System.md).

**Charge and Blocking Foul (attack shots only; requires contest)**
- Before make/miss: if shot_type is **attack** and a defender is in **contest range** (`has_contest`), run charge/block check (`calculate_charge()`). If **CHARGE**: return early with result_type "CHARGE", possession_flips True, next_play_type SIP; no shot attempted. If **BLOCKING_FOUL**: return early with result_type "FOUL", text "Blocking foul on X!", next_play_type SIP or FREE_THROW (if bonus); no shot attempted. With **no** contest, `calculate_charge` is not called (no charge/blocking foul from this path).
- Backend: game_manager treats CHARGE like FOUL for transition—flips possession and appends SIDE_INBOUND when result_type is CHARGE or FOUL (non–free-throw).
- Frontend: CHARGE and FOUL (blocking) both route to handleDefault → playTurnAnimation (skeleton/drive animates; no ball to basket). Announcements: "Charge!" for CHARGE, "BLOCKING FOUL!" for blocking foul.

**Long Form Documentation**

## Shot Resolution System

### Base Values

Shot resolution uses the following base constants:

- **Foul Thresholds (vary by shot_type)**:
  - Inside: HARD=35, SOFT=105
  - Attack: HARD=80, SOFT=140
  - Outside: HARD=20, SOFT=80
- **SOFT_PROB**: 0.16
- **THREE_POINTER_FOUL_MISS_CHANCE**: 0.4
- **TWO_POINTER_FOUL_MISS_CHANCE**: 0.2

### Shot Resolution Flow

#### Step 1: Extract Roles
- shooter, passer, screener, defender, second_defender
- playcall: `roles.get("motion_playcall")` (Motion) or `game_state["current_playcall"]` (Set)
- defense_call: `game_state["defense_playcall"]` ("Man" or "Zone")

#### Step 2: Determine Shot Type
- **shot_classification**: `classify_shot_value()` payload built from backend shot coords. `roles["shot_spot"]` is preferred; shooter coords are fallback; skeleton spot names are compatibility fallback only when usable coords are missing.
- **is_three**: `shot_classification["is_three_point_shot"]`
- **is_paint**: Check shooter spot against PAINT_SPOTS
- **shot_type**: 
  - Motion: `roles.get("shot_type")` or `roles.get("motion_shot_type")` (from resolve_motion_offense_shot)
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
- If `is_three`: `shot_threshold += (THREE_POINT_SHOT_THRESHOLD_INCREASE - (random.randint(1, 5) * momentum))`, where `THREE_POINT_SHOT_THRESHOLD_INCREASE = 55`
- Higher momentum = easier three-pointers

#### Step 5: Apply Variant Modifier
- From `skeleton.get("_variant")`: successful=-50, mid_play_change=0, contested=+25, broken=+100

#### Step 6: Zone defense shot-type threshold (HCO / Final Turn only)
- **Scope:** `resolve_shot()` only; `offensive_state == "HCO"`, not fast break. Covers standard half-court possessions and **Final Turn** shots (still resolved under HCO). **Excludes** FCP/HCT, fast break, and **OREB putbacks** (different code path).
- **`defense_playcall`** from `game_state["defense_playcall"]` (exact strings):
  - **`2-3 Zone`:** `shot_threshold` += **inside +25**, **attack +10**, **outside −25**
  - **`3-2 Zone`:** **outside +50**, **inside −30**, **attack −30**
- **Man** / **`1-3-1 Zone`:** no delta from this step.
- Applied after crowd delta, three-point threshold modifier, skeleton variant modifier, and shot-at-1 penalty (see `shot_manager.py`).

#### Step 7: Calculate Shot Score

**7a. Base Score:**
```python
sum(shooter_attrs[attr] * (weight / 10) for attr, weight in shot_type_weights.items()) * random.randint(1, 6)
```
- Inside: SC=6, ST=2, IQ=1, CH=1
- Attack: SC=5, AG=2, ST=1, IQ=1, CH=1
- Outside: SH=8, IQ=1, CH=1

**7b. Passing/Dribbling Bonus:**
- Passer: `(PS * 0.8 + IQ * 0.2) * random(1-6) * 0.2`
- Dribble: `(AG * 0.8 + IQ * 0.2) * random(1-6) * 0.2`

**7c. Defense Score:**
- Paint: `(ID * 0.6 + ST * 0.2 + IQ * 0.1 + CH * 0.1) * random(1-6)`
- Three-point: `(OD * 0.8 + IQ * 0.1 + CH * 0.1) * random(1-6)`
- Mid-range: `(OD * 0.3 + ID * 0.3 + AG * 0.1 + ST * 0.1 + IQ * 0.1 + CH * 0.1) * random(1-6)`

**7d. Defensive Foul Check:**
- Thresholds: Inside(50/110), Attack(70/130), Outside(30/90) + fight
- If `defense_score < hard_threshold`: d_foul = True
- Elif `defense_score < soft_threshold`: d_foul = random() < 0.16
- Else: d_foul = False

**7e. Defense Penalty** (main `calculate_shot_score`, HCO/set/motion):
- Single defender: `shot_score -= defense_score * 0.6`
- Double team: `shot_score -= (defense_score * 0.35) + (second_defense_score * 0.35)`
- (Fast-break shots use a **separate** simpler penalty in `resolve_fast_break_shot`: single defender `shot_score -= defense_score * 0.2`, with an ID-only defense score `ID*0.8 + IQ*0.1 + CH*0.1`.)

**7f. Defense Scheme Multiplier:**
- Zone vs 3pt: `shot_score *= 1.1`

**7g. Screener Bonus:**
- If screener: `shot_score += (ST * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random(1-6) * 0.15`

**7h. Gravity Boost:**
- Per player: `(SH * 0.3 + SC * 0.3 + IQ * 0.4)`
- Total: `shot_score += total_gravity * 0.02`

#### Step 8: Apply Motion Attack Penalty
- If `motion_attack_penalty > 0`: `shot_score -= penalty`
- Penalty = distance from shot location to basket (when stopped short)

#### Step 9: Determine Make/Miss
- `made = shot_score >= shot_threshold`

#### Step 10: Shooting Foul Calibration
- If d_foul: 3pt=40% miss chance, 2pt=20% miss chance

#### Step 11: Record Stats
- `shooter.record_stat("FGA")`, `shooter.record_stat("3PTA")` if is_three

#### Step 12: Final Result
- If made: Record FGM, 3PTM, PIP, AST, SCR_S, set up AND-1 if d_foul
- If miss: Record DEF_S, determine rebound (geography-based), check block
- All normal `ShotManager.resolve_shot()` field-goal results carry `is_three_point_shot`, `shot_value`, `shot_spot`, `shot_classification_coord`, `shot_classification`, and `shot_classification_source`.
- Dynamic HCT shot results carry the same classification payload from their procedural `shot_spot`.
- OREB putback attempts carry a forced-two classification payload.

#### Step 13: Player Positioning
- Get-back players (offense): Based on rebounding strategy (0-4 scale)
- Release players (defense): Based on fast_breaks strategy (0-4 scale)
- Coordinates calculated in backend for animation

### Key Implementation Notes

1. **Shot Type vs Playcall**: Shot score calculation uses `shot_type` (inside/attack/outside) instead of `playcall` for attribute weights
2. **Motion vs Set Plays**: Both Motion and Set plays use location-based logic to determine `shot_type`:
   - **Motion offense**: Determines `shot_type` during shot resolution (checks possibilities, builds weighted list, selects)
   - **Set plays**: Determines `shot_type` from skeleton analysis (shooter location + attack detection)
   - Attack detection (Set): shoot step = last step; shoot location in PAINT_SPOTS; step before has shooter with action `"handle_ball"` and different location → has_drive = True. Paint + has_drive = attack; paint + no has_drive = inside; else = outside.
3. **Three-Point Momentum**: Three-point threshold modifier uses momentum: `55 - (random(1-5) * momentum)` (`THREE_POINT_SHOT_THRESHOLD_INCREASE = 55`; higher momentum = easier threes)
4. **Shot Value Classification**: `classify_shot_value()` is the canonical backend classifier. `roles["shot_spot"]` is authoritative when present; shooter coords are fallback; skeleton spot names are compatibility fallback only. Fast Breaks are 2-point unless the branch is explicitly `shot_type == "outside"` with a `shot_spot`. OREB putbacks force 2; free throws force 1.
5. **Foul Thresholds by Shot Type**: Different hard/soft thresholds for inside (50/110), attack (70/130), and outside (30/90) shots
6. **Defense Scheme Multiplier**: Only Zone vs 3pt gets 1.1x multiplier (makes shot more likely to be successful)
7. **Location-based contest**: HCO/Final Turn → `has_contest` is role-based (`bool(defender or second_defender)`); non-HCO → geometry box around shooter (|Δx|≤8, |Δy|≤8, `CONTEST_DEFENDER_DX_MAX`/`DY_MAX`) vs all defenders. Rim box around attacking basket (±6, `RIM_BOX_HALF_SPAN`); unguarded rim shortcut (99% make); `apply_defense` only when `has_contest` (unless shortcut applies)
8. **Motion Attack Penalty**: Applied when Motion offense attack shot is stopped short of basket (penalty = distance to basket)
9. **Foul Calibration**: Shooting fouls don't guarantee made shots (40% miss chance on 3pt, 20% on 2pt)
10. **Player Positioning**: Happens at shot attempt, not outcome (players don't know if shot will be made)
11. **Balancing Override**: Triggered when score difference exceeds quarter-based thresholds adjusted by team attributes
12. **Zone shot-type threshold**: 2-3 and 3-2 zone defenses adjust `shot_threshold` by `shot_type` on HCO and Final Turn shots only (`_hco_zone_shot_threshold_delta` in `shot_manager.py`).

### Status

✅ **Shot Resolution**: Implementation active
- Unified shot resolution for HCO and Fast Break field-goal paths through `ShotManager.resolve_shot()`
- Shared backend classification wrapper for field-goal 2/3 decisions and forced-value paths
- Shot type-based attribute weights (inside/attack/outside)
- Shot type-specific foul thresholds
- Momentum-based three-point modifier
- Geography-based rebound system for missed shots
- Shooting foul calibration for realistic outcomes
- Player positioning system for fast break opportunities

## Related

- **Team attribute scale (50–250, center 150):** [Shot_Threshold_Scale_Tuning.md](./Shot_Threshold_Scale_Tuning.md)

### Key Files

- `BackEnd/models/shot_manager.py`: `resolve_shot()`, `_build_shot_classification()`, `_stamp_shot_classification()`, `_hco_zone_shot_threshold_delta()`, `calculate_shot_score()`, `check_defensive_foul_on_shot()`, `resolve_fast_break_shot()`
- `BackEnd/utils/shot_geometry.py`: `is_three_point_shot_from_coords()`, `classify_shot_value()`
- `BackEnd/constants/__init__.py`: PLAYCALL_ATTRIBUTE_WEIGHTS, THREE_POINT_SPOTS, PAINT_SPOTS
- `BackEnd/utils/shared.py`: `calculate_gravity_score()`, `calculate_screen_score()`, `calculate_bounce_spot()`, `determine_rebounder()`, OREB putback forced-two classification
- `BackEnd/engine/dynamic_hct_shot.py`: Dynamic HCT procedural shot classification payloads
- `BackEnd/engine/skeleton_step_emitter.py`: made-three SFX gate from `is_three_point_shot`
- `BackEnd/engine/phase_resolution.py`: `_apply_attack_penalty()`, `resolve_motion_offense_shot()`, `apply_balancing_system()`
