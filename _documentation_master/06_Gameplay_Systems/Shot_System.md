
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
2. **Attacking basket (display orientation):** Home offense attacks `HOME_RIM_COORDS` (x≈91, y≈25); away offense attacks `AWAY_RIM_COORDS` (x≈9, y≈25). Matches animation payloads, `HCO_STRING_SPOTS`, and `_animation_transition_basket_xy` in `shot_manager.py`. Away spots mirror with `x → 100 − x`, y unchanged.
3. **Contest (`has_contest`):** Two paths:
   - **HCO / Final Turn** (`offensive_state == "HCO"`): `has_contest = bool(defender or second_defender)` — i.e. **role-based** (whether a contesting defender role is assigned), not a geometry box.
   - **Non-HCO** (FCP, HCT, fast break): Euclidean geometry — **every** player in the defensive lineup is checked, and `has_contest` is true if any lies within **`CONTEST_EUCLIDEAN_RADIUS` (11)** grid spots of the shooter.
4. **Rim box:** Axis-aligned box around the attacking basket: **|shooter_x − basket_x| ≤ 6** and **|shooter_y − basket_y| ≤ 6** (same margin on both axes).
5. **Uncontested inside/attack make rule (universal helper):** Implemented in `BackEnd/utils/uncontested_shot.py`. Applies when `shot_type` is **inside** or **attack**, the attempt is **not** a three-pointer, and Euclidean distance from the shooter to the attacking basket is **≤ 11** (`UNCONTESTED_INSIDE_ATTACK_MAX_DIST`, same as contest radius). **Outside shots are excluded.**
   - `make_threshold = 99 + offense_team.discipline − defense_team.fight` (clamped to 1–100)
   - At distance **≥ 12**: `make_threshold −= 2 × (distance − 11)` (farther = lower threshold = harder make)
   - `roll = random.randint(1, 100)` → **make** if `roll < make_threshold`, else miss
   - When the helper does **not** apply (outside type, three, or distance > 11): uncontested inside/attack fall back to `shot_score >= shot_threshold`
6. **Rim box shortcut path:** If `shot_type` is **inside** or **attack**, not a three, shooter is **in the rim box** (|shooter_x − basket_x| ≤ 6 and |shooter_y − basket_y| ≤ 6), **`has_contest` is false**, and not motion-geometry contest → resolve make/miss via the **universal uncontested helper** (item 5). This path **does not** run `calculate_shot_score` defense, **does not** run block reconciliation, charge/blocking foul, or defensive shooting fouls.
7. **No contest, not using the rim shortcut:** Call `calculate_shot_score(..., apply_defense=False)` — offense-only scoring (base shot score, passer/dribble, screener, gravity, zone-vs-3 multiplier still apply); **no** defense subtraction, **no** `DEF_A`, **no** `d_foul` from `check_defensive_foul_on_shot`. **Make/miss then differs by shot type:** undefended **outside** uses the bespoke rule `shot_score > (210 − shooter.CH + euclidean(shooter, basket))` (see Step 9); undefended **inside/attack** use the universal uncontested helper when geo-eligible, else `shot_score >= shot_threshold`.
8. **Contest:** Full defensive shot score, shooting-foul check, and (when applicable) block reconciliation and `calculate_charge` **only** when `has_contest` is true (charge remains **attack** shots only, plus existing fast-break defender gating).

**Three-point classification**

- Geometry primitive: `BackEnd.utils.shot_geometry.is_three_point_shot_from_coords()`.
- Canonical classification wrapper: `BackEnd.utils.shot_geometry.classify_shot_value()`.
- Backend classification is the source of truth. The frontend/UESS renderer does not infer whether a shot is worth 1, 2, or 3.
- `classify_shot_value()` returns a self-describing payload including `points`, `shot_value`, `is_three_point_shot`, `classification_coord`, `normalized_coord`, `boundary_x`, `classification_source`, and `allow_three`.
- `ShotManager.resolve_shot()` plans micro footwork (`plan_non_dunk_shot_micro`), classifies from **`micro_release_coord`** (post-footwork release), then runs shot math and stamps `is_three_point_shot`, `shot_value`, `shot_spot`, `shot_classification_coord`, `shot_classification`, and `shot_classification_source`.
- Coordinate priority for field goals:
  1. Explicit backend `roles["shot_spot"]` coords (set to the micro release coord when micro runs).
  2. Shooter model `coords`.
  3. Legacy skeleton shoot-location name and `THREE_POINT_SPOTS` fallback only if usable coords are missing.
- Contest / defender proximity still uses the **pre-micro** shoot spot. Dunk stamps force 2-point value.
- The coordinate arc uses the home-offense HCO spot model (`key`, wings, midCorners, corners) and linearly interpolates the boundary x-value by shooter y. Away-offense shots mirror x with `100 - x` before testing. The helper expects display-oriented coords.
- Fast Break shots remain 2-point by default. Only explicit outside Fast Break branches with `shot_type == "outside"` and a backend `shot_spot` can classify as 3s. This covers Triangle corner/wing/kick branches without changing Steal FB, RR rim attacks, or CR rim attacks.
- Dynamic HCT procedural attack-basket shots bypass `ShotManager.resolve_shot()`, so they call the same classification wrapper before `calculate_shot_score()` and carry `is_three_point_shot` through scoring, `3PTA`/`3PTM`, points, and shooting-foul free-throw count.
- OREB putbacks are forced 2-point field goals and stamp a forced-two classification payload. Their nearest defender uses the shared graded proximity curve: full at ≤3, linear to 0.15 at 9, 0.15 through 11, and no contest beyond 11. This does not add the standard `resolve_shot()` shooter-to-rim threshold penalty to OREB.
- Free throws are forced 1-point attempts. They do not use field-goal 2/3 geometry.
- Made-three SFX is stamped by the backend schema emitter only when `turn_result["is_three_point_shot"] is True`, not by raw `points == 3` and not by frontend inference.

**Shot Resolution Flow (13 Steps)**
1. Extract Roles
   - shooter, passer, screener, defender, second_defender from roles dict
   - Get playcall from `roles.get("motion_playcall")` or `game_state["current_playcall"]`
     - motion_playcall: Used for Motion offense (determined during Motion shot resolution)
     - current_playcall: Used for Set plays (from game state)
   - Get defense_call from `game_state["defense_playcall"]`

2. Determine Shot Type + Classify at Micro Release
   - Resolve `shot_type` (motion / skeleton / playcall)
   - `plan_non_dunk_shot_micro(...)` → `micro_release_coord` (and pinned `micro_move_to_coord` when needed)
   - `roles["shot_spot"]` updated to release coord
   - `shot_classification = classify_shot_value(...)` via `ShotManager._build_shot_classification()`
   - `is_three = shot_classification["is_three_point_shot"]`
   - is_paint = `is_paint_shot(shooter, roles)` (pre-micro skeleton paint check; FB derives from classification)
   - Dunk stamp later forces 2PT if selected
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
     - Trailing team: -20 (easier shots)
     - Leading team: 180 (harder shots)
     - Base margin trigger tiers before attributes: Q1/Q2 = 6, Q3 = 8, Q4/OT = 10 for both trailing and leading teams
     - Trailing trigger subtracts offense fight; leading trigger adds offense discipline; minimum trigger is clamped to 1
   - Otherwise use `off_team.team_attributes["shot_threshold"]`

4. Apply Three-Point Modifier (standard `resolve_shot` only; not FLSS CH-vs-1–100 heaves)
   - Distance penalty: all `resolve_shot` attempts add distance from shooter shot coords to the attacking rim.
     - Twos: `shot_threshold += round(distance)`
     - Threes: `shot_threshold += round(distance × 1.5)`
     - Home offense rim: `HOME_RIM_COORDS` (91, 25); away offense rim: `AWAY_RIM_COORDS` (9, 25) — absolute coords, no home-flip
     - If shooter coords unavailable: `shot_threshold += THREE_POINT_SHOT_THRESHOLD_FALLBACK` (25)

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
   - After shot threshold modifiers: compute shooter `(x,y)`, attacking basket, `has_contest`, and whether the **rim box shortcut** applies (see **Location** above). Rim shortcut: universal uncontested inside/attack roll (item 5), skip defense/foul/block/charge pipeline for that outcome.
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
   - **Undefended OUTSIDE exception:** when `has_contest` is false **and** `shot_type == "outside"`, use the bespoke rule `made = shot_score > (210 − shooter.CH + euclidean(shooter, basket))` (strictly `>`; higher chemistry / closer to the basket = easier). `shot_threshold` is left intact for downstream variant selection. Undefended **inside/attack** shots are unchanged (rim-unguarded shortcut or the standard compare).

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
  - Trailing: -20, Leading: 180
  - Base margin trigger tiers before attributes: Q1/Q2 = 6, Q3 = 8, Q4/OT = 10 for both trailing and leading teams
  - Trailing trigger subtracts offense fight; leading trigger adds offense discipline; minimum trigger is clamped to 1
- **Otherwise**: `off_team.team_attributes["shot_threshold"]`

#### Step 4: Apply Three-Point Modifier
- Scope: standard `resolve_shot()` only. FLSS heaves (CH vs roll 1–100) do not use this path.
- Distance penalty: `shot_threshold += round(hypot(shooter_x − rim_x, shooter_y − rim_y))` for twos, and `shot_threshold += round(hypot(...) × 1.5)` for threes, where rim is the attacking rim (`HOME_RIM_COORDS` / `AWAY_RIM_COORDS` by offense side; absolute coords).
- If shooter shot coords are unavailable: `shot_threshold += THREE_POINT_SHOT_THRESHOLD_FALLBACK` (25).
- Typical perimeter spots (key / midWing / wing / midCorner / corner) land ~19–27 vs rim (~20–23 common).

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
- **Undefended OUTSIDE exception** (`not has_contest and shot_type == "outside"`): `made = shot_score > (210 − shooter.CH + euclidean(shooter, basket))` — strictly `>`; higher chemistry / closer = easier. `shot_threshold` is preserved for downstream variant selection (the effective bar is logged as `shot_threshold` in `[SHOT RECON]`). Undefended inside/attack are unchanged.

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
3. **Distance Modifier**: On standard `resolve_shot` attempts, twos add rounded Euclidean distance from shooter shot coords to the attacking rim (`HOME_RIM_COORDS` / `AWAY_RIM_COORDS`); threes add rounded distance × 1.5. FLSS CH heaves excluded.
4. **Shot Value Classification**: `classify_shot_value()` is the canonical backend classifier. `roles["shot_spot"]` is authoritative when present; shooter coords are fallback; skeleton spot names are compatibility fallback only. Fast Breaks are 2-point unless the branch is explicitly `shot_type == "outside"` with a `shot_spot`. OREB putbacks force 2; free throws force 1.
5. **Foul Thresholds by Shot Type**: Different hard/soft thresholds for inside (50/110), attack (70/130), and outside (30/90) shots
6. **Defense Scheme Multiplier**: Only Zone vs 3pt gets 1.1x multiplier (makes shot more likely to be successful)
7. **Location-based contest**: HCO/Final Turn → `has_contest` is role-based (`bool(defender or second_defender)`); non-HCO → Euclidean radius around shooter (`CONTEST_EUCLIDEAN_RADIUS` = 11) vs all defenders. Motion attack drive uses geometry contest at shot resolve. Rim box around attacking basket (±6, `RIM_BOX_HALF_SPAN`); rim-box shortcut uses universal uncontested inside/attack helper; `apply_defense` only when `has_contest` (unless rim shortcut applies)
8. **Motion Attack Penalty**: Applied when Motion offense attack shot is stopped short of basket (penalty = distance to basket)
9. **Foul Calibration**: Shooting fouls don't guarantee made shots (40% miss chance on 3pt, 20% on 2pt)
10. **Player Positioning**: Happens at shot attempt, not outcome (players don't know if shot will be made)
11. **Balancing Override**: Triggered when score difference exceeds quarter-based thresholds adjusted by team attributes. Base trigger tiers are Q1/Q2 = 6, Q3 = 8, Q4/OT = 10 for both trailing and leading teams; trailing subtracts offense fight, leading adds offense discipline, and the minimum trigger is clamped to 1. The one-turn shot-threshold overrides are trailing = 0 and leading = 200 (`shot_threshold_scale.BALANCING_*`).
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

- **Team attribute scale (10–210, center 110):** [Shot_Threshold_Scale_Tuning.md](../00_Operations/Shot_Threshold_Scale_Tuning.md)

### Key Files

- `BackEnd/models/shot_manager.py`: `resolve_shot()`, `_build_shot_classification()`, `_stamp_shot_classification()`, `_hco_zone_shot_threshold_delta()`, `calculate_shot_score()`, `check_defensive_foul_on_shot()`, `resolve_fast_break_shot()`
- `BackEnd/utils/shot_geometry.py`: `is_three_point_shot_from_coords()`, `classify_shot_value()`
- `BackEnd/constants/__init__.py`: PLAYCALL_ATTRIBUTE_WEIGHTS, THREE_POINT_SPOTS, PAINT_SPOTS
- `BackEnd/utils/uncontested_shot.py`: universal uncontested inside/attack make roll (`resolve_uncontested_inside_attack_make`, `apply_uncontested_inside_attack_make`)
- `BackEnd/utils/shared.py`: `calculate_gravity_score()`, `calculate_screen_score()`, `calculate_bounce_spot()`, `determine_rebounder()`, OREB putback forced-two classification
- `BackEnd/engine/dynamic_hct_shot.py`: Dynamic HCT procedural shot classification payloads
- `BackEnd/engine/skeleton_step_emitter.py`: made-three SFX gate from `is_three_point_shot`
- `BackEnd/engine/phase_resolution.py`: `_apply_attack_penalty()`, `resolve_motion_offense_shot()`, `apply_balancing_system()`

---

## Dunk Selection & Block Interaction

**Status:** Implemented (animation in `shot_micro_movements.py` + `dunkPlayback.js`; selection in `resolve_dunk_micro_stamp()`).  
**Depends on:** Shot Micro-Movements System, Block System, `HCO_STRING_SPOTS.basketSpot`.

### Scope

Same rules for **all field-goal paths**: HCO, Fast Break, FCP, HCT, OREB putback (any caller that stamps `micro_movement_family` via `select_and_stamp_shot_micro()` with dunk kwargs).

Only **inside** and **attack** shots. Outside shots never dunk.

### Eligibility (location + AG)

Distance = euclidean grid distance from shooter coord to **`basketSpot`** (home `(87, 25)`, away mirrored).

| Distance from basketSpot | AG gate |
|--------------------------|---------|
| > 10 | Not eligible |
| ≤ 8 | Fully eligible (any AG) |
| ≤ 9 | `AG > 50` |
| ≤ 10 | `AG > 75` |

### Dunk in play (contact / power)

Uses the same score pair as `resolve_contest()`:

```text
margin = shot_score_pre_defense − shot_defense_score_raw + off_fight − def_fight
dunk_in_play = margin > threshold(offense aggression_call)
```

Threshold by offense **`aggression_call`** (`strategy_calls`, same break roll as tempo/aggression bars):

| Offense aggression | Margin threshold |
|--------------------|------------------|
| passive | 150 |
| normal | 100 |
| aggressive | 50 |

Constants: `DUNK_MARGIN_THRESHOLD_BY_OFFENSE_AGGRESSION` in `shot_micro_movements_constants.py` (fallback `DUNK_MARGIN_THRESHOLD = 100`).

**Uncontested inside/attack** (no shot defender within contest radius, or rim-unguarded / motion-attack uncontested paths): skip the margin gate — location + AG + height roll still apply. Callers pass `uncontested=True` into `resolve_dunk_micro_stamp()` / `prepare_dunk_stamp()`.

### Height feasibility roll

Only when `dunk_in_play`. `roll = random.randint(1, 100)` vs `DUNK_HEIGHT_SCALE[inches]`:

| Height (in) | Scale |
|-------------|-------|
| ≤ 68 | 0 |
| 69–71 | 1 |
| 72 | 2 |
| 73 | 5 |
| 74 | 7 |
| 75 | 10 |
| 76 | 12 |
| 77 | 15 |
| 78–79 | 17 / 18 |
| 80 | 20 |
| 81 | 22 |
| 82 | 25 |
| ≥ 83 | 30 |

| Roll | Outcome |
|------|---------|
| `roll == scale + 1` | **Missed dunk** — `dunk_miss: true`, forces `result_type: MISS`, full dunk animation through slam, then normal miss bounce (no hold) |
| `roll ≤ scale` and **MAKE** | **Made dunk** — family `dunk` or `drive_dunk`, skip `[ball_flight]` → `[hold]` with **Dunk!** announce + random dunk VO (`meta.sfx: "dunk_make"`) + `dunk-sfx.wav` at slam (`sfx_on_ball_arrival`); shooter **+MO_DUNK_DELTA** (Player Momentum System) |
| `roll ≤ scale` and **BLOCK** | **Blocked dunk attempt** — same family, `yield_before_slam: true` (rise only), then existing block `[ball_flight]` |
| `roll ≤ scale` and normal **MISS** | No dunk animation — fall through to normal micro pool |
| else | No dunk — normal micro pool |

### Animation family

| Distance from basketSpot | `micro_movement_family` |
|--------------------------|-------------------------|
| ≤ 8 | `dunk` |
| 9–10 (AG-qualified) | `drive_dunk` |

See [`Shot_Micro_Movements_System.md`](Shot_Micro_Movements_System.md) for beat timing and FE playback (`micro_beat_kind: "dunk"`).

### Block interaction

Blocks **remain in play** on contested dunk lanes (no special disable). When a block fires on a dunk-eligible attempt that passed the height roll (`roll ≤ scale`):

- Backend stamps `yield_before_slam: true` on the dunk beat metadata.
- FE stops at the rise apex (p = 0.5); ball stays attached at the approach spot.
- Post-shot uses the normal **BLOCK** path (`[ball_flight]` → block spot → rebound).

When `contest_result == offense_win` (margin ≥ 150), block attempt is gated off entirely (Block System §1.3) — full dunk lane if height roll passes.

### Telemetry

| Field | When |
|-------|------|
| `micro_movement_family` | `dunk` or `drive_dunk` |
| `dunk_miss` | `true` on missed-dunk roll |
| `uses_shot_arc` | `false` for dunk families |

### Key files

- `BackEnd/engine/shot_micro_movements.py`: `resolve_dunk_micro_stamp()`, `select_and_stamp_shot_micro()` dunk kwargs
- `BackEnd/constants/shot_micro_movements_constants.py`: dunk selection thresholds + height scale
- `BackEnd/engine/skeleton_step_emitter.py`: `_build_post_shot_sub_steps()` MAKE dunk hold skip; MISS dunk bounce wiring
- `FrontEnd/static/js/phaser/animation/dunkPlayback.js`: `yield_before_slam` vs full slam
