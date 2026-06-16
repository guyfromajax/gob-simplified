## Motion Offense Shot Resolution System ✅ **COMPLETE** (January 2025; attack-drive expansion June 2026)

**Base Constants**

1. **Shot Types**: Inside, Outside, Attack
2. **Playcall Mapping**: `{"inside": "Inside", "outside": "Outside", "attack": "Attack"}`
3. **Skeleton Timestamp Offsets**: +300ms between drive and next step; +600ms drive → dish shoot (game-clock hints only — UESS emitter uses distance-based step T)
4. **Attack Drive Geometry** (`BackEnd/engine/attack_drive_clearance.py`):
   - `ATTACK_DRIVE_CONTEST_RADIUS = 10` — guarded / contested (euclidean grid spots)
   - `ATTACK_DRIVE_INSIDE_RADIUS = 15` — dish receiver inside vs outside classification
   - Read bases / floor: `PERIMETER_OFFENSE_READ_BASE = 150`, `PERIMETER_DEFENSE_READ_BASE = 125`, `HELP_READ_BASE = 100`, `READ_THRESHOLD_FLOOR = -3`
   - `DRIVE_CONTEST_DEF_BONUS_MULTIPLIER = 2` — defense chemistry + efficiency bonus on drive contest
5. **Drive Destinations**:
   - **Upper locations** → `["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]`
   - **Lower locations** → `["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]`
   - **Central locations** → All destinations (both upper and lower)
6. **Key Functions**:
   - `resolve_motion_offense_shot()` — Main shot resolution function
   - `build_attack_drive_sequence()` — Full HCO attack drive (clearance, perimeter reads, contest, dish/shoot)
   - `_create_attack_drive_shoot_steps()` — Delegates to `build_attack_drive_sequence()` when `selected_step` + lineups + game are available
   - `_determine_attack_drive_destination()` — Determines valid drive destinations
   - `_check_inside_shot_possibility()` / `_check_attack_shot_possibility()` / `_check_outside_shot_possibility()`
   - `_build_shot_type_weighted_list()` — Builds weighted list for shot type selection
   - `_apply_attack_penalty()` — Calculates penalty if player stopped short
7. **Key Files**:
   - `BackEnd/engine/phase_resolution.py` — Motion shot resolution entry
   - `BackEnd/engine/attack_drive_clearance.py` — Attack drive logic (backend-only, UESS)
   - `BackEnd/engine/skeleton_step_emitter.py` — `attack_drive_driver` gate, pass/shoot gates
   - `BackEnd/models/shot_manager.py` — Motion attack geometry contest + uncontested (OREB rule)
   - `BackEnd/models/animator.py` — Skeleton → animations; `_attack_drive` defender overrides

**Motion Offense Shot Resolution Flow (8 Steps)**

1. **Select Random Step**: Choose step 1-N (excluding step 0) for shot attempt, truncate skeleton at selected step
2. **Identify Ball Handler**: Find ball handler position and location at selected step from `pos_actions`
3. **Check Possibilities**: Determine which shot types are possible (inside/attack/outside) based on ball handler location and available receivers
4. **Build Weighted List**: Create weighted list based on strategy settings (`inside`, `attack`, `outside` weights) and shot type possibilities
5. **Select Shot Type**: Randomly select from weighted list (inside, outside, or attack)
6. **Execute Shot**:
   - **Inside**: Ball handler shoots from current location OR passes to inside receiver who shoots
   - **Outside**: Ball handler shoots from current location OR passes to outside receiver who shoots
   - **Attack**: Drive step (all concurrent movement) → shoot **or** pass/receive → shoot (see Attack Drive section)
7. **Append Steps**: Add new shot steps to truncated skeleton
8. **Return Results**: Modified skeleton with shot steps, shooter info, shot type, playcall, and attack penalty

**Long Form Documentation**

### Overview

The Motion Offense Shot Resolution System handles shot attempts in Motion offense plays. Unlike Set Plays which have predetermined shot locations, Motion plays dynamically determine shot type (inside/outside/attack) based on player positions and strategy settings.

**Key Function:** `resolve_motion_offense_shot()` in `BackEnd/engine/phase_resolution.py`

### Shot Type Determination

Motion offense shots are determined dynamically based on:
1. **Ball handler location** at the selected step
2. **Available receivers** at inside/outside locations
3. **Strategy settings** (inside/attack/outside weights)
4. **Player attributes** (IQ can influence decisions)

**Three Shot Types:**

1. **Inside Shots:**
   - Ball handler at inside location → shoots from current spot
   - OR ball handler passes to receiver at inside location → receiver shoots
   - Uses `playcall = "Inside"` for shot calculation

2. **Outside Shots:**
   - Ball handler at outside location → shoots from current spot
   - OR ball handler passes to receiver at outside location → receiver shoots
   - Uses `playcall = "Outside"` for shot calculation

3. **Attack Shots:**
   - Ball handler at non-lane spot chooses to drive
   - **HCO motion path** (when `selected_step` + lineups available): full drive sequence via `build_attack_drive_sequence()`
   - **Shoot path:** drive step → shoot step (+300ms skeleton offset)
   - **Dish path:** drive step → pass/receive step (+300ms) → shoot step (+600ms)
   - Driver shoot uses `playcall = "Attack"`; dish to interior receiver may resolve as **Inside**; dish to perimeter resolves as **Outside**
   - **Final Turn:** unchanged fallback (simple drive → shoot, no expansion)

### Attack Drive Implementation

**Primary function:** `build_attack_drive_sequence()` in `BackEnd/engine/attack_drive_clearance.py`

**Entry:** `_create_attack_drive_shoot_steps()` in `phase_resolution.py` delegates when HCO motion context is available.

**UESS contract:** All logic backend-only. One drive step holds all concurrent offensive/defensive movement. Step T is distance-based via `skeleton_step_emitter` (`attack_drive_driver` gate on drive; `shooter` gate on shoot; pass step gates on ball arrival). Skeleton `timestamp` offsets are game-clock ordering hints, not animation pause durations.

**Step outcomes:**

| Path | Steps | Notes |
|------|-------|-------|
| Driver shoots | `[drive, shoot]` | All 5 offense on drive step; shoot step everyone stationary except shooter |
| Driver dishes | `[drive, pass/receive, shoot]` | Pass + receive same step; receiver shoots on step 3 |

**Drive step metadata (`_attack_drive` on drive step):**
- `driver_gate: True`, `gate_driver_pos` — emitter gates step T on driver arrival
- `defender_overrides` — man/zone reactions (contest, help, double, perimeter follow, beaten primary)
- `dish_receiver_pos` — clearance midLane spacer (spacing, not driver dish)
- `double_team`, `help_read_success`, `drive_offense_wins`, `defender_count`, `driver_shoots`, `dish_target_pos`

**Drive Destinations** (unchanged):

Based on starting location:
- **Upper locations** → `["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]`
- **Lower locations** → `["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]`
- **Central locations** → All destinations (both upper and lower)

---

### Attack Drive — Lane Clearance (blast radius)

When attack is selected, teammates in the **drive lane** clear on the drive step before the driver arrives.

**Blast radius:** Same-half `lowPost`, `midPost`, `bird` spots; destination spot itself; central destinations (`midLane`, `basketSpot`) only block a teammate **on** the destination.

**Offensive reactions:**
- One in-way teammate (closest x to basket; random tie-break) → `cut` to **midLane** if destination ≠ midLane
- Others in blast radius → **evac** coords (home x 77–87 / away x 13–23; y opposite vertical half; ≥3 euclidean separation)
- Driver → `drive`; everyone else not moving → `stationary`

**Defensive reactions (clearance layer):**
- Man: BH defender sticks to drive destination unless beaten by drive contest (below)
- Double on clearance dish spacer: dish defender **read** (not 50/50): `player_read > 100 - (def_chemistry + defensive_efficiency)` (floor **−3**)
- Help defender: **always evaluated**; same help threshold; rotates to dish spacer or collapse point

---

### Attack Drive — Perimeter Relocation Reads

During the **same drive step**, perimeter players (key, midWing, wing, midCorner, corner, deep spots) who were **not** already assigned clearance movement execute a read.

**Offense read:** `player_read > 150 - (offense_team_chemistry + offensive_efficiency)` (floor **−3**) → `cut` to an **open tangential** spot (single-pass, random player order; vacated spots become open for later players in that pass).

**Tangents:**

| Spot | Open tangents |
|------|----------------|
| key | upper midWing, lower midWing |
| midWing | key or wing (same vertical half) |
| wing | midWing or midCorner (same half) |
| midCorner | wing or corner (same half) |
| corner | midCorner (same half) |
| deep key | key, upper midWing, lower midWing |
| deep wing | key, wing, midWing (same half) |
| deep baseline | corner, midCorner, wing (same half) |

If no open tangent → player stays put.

**Defender follow:** Defender of a relocating player (man matchup or zone shell assignment) reads `player_read > 125 - (defense_team_chemistry + defensive_efficiency)` (floor **−3**) → `cut` to guard new spot. Openness is inferred dynamically at shot time from coords (no explicit flag).

---

### Attack Drive — Drive Contest

**Offense drive score:** `calculate_ball_handling_score(driver) + offensive_efficiency × random(1,3)`

**Defense drive score:** `calculate_defender_pressure_score(primary_defender, defense_call) + defensive_efficiency × random(1,3)`

**Offense wins:** `offense_score > defense_score + 2 × (defense_team_chemistry + defensive_efficiency)`

| Outcome | Primary defender |
|---------|------------------|
| Offense wins | `cut` to halfway grid point between driver start and drive destination |
| Defense wins | `guard_ball` at drive destination |

---

### Attack Drive — Driver Decision (post-drive geometry)

After all drive-step movement is resolved, count defenders whose **end coords** are within **10 euclidean grid spots** of the driver at the destination. Any defender counts.

| Defenders at spot | Shoot / dish odds | Shot resolution |
|-------------------|-------------------|-----------------|
| 0 (unguarded) | Always shoot | OREB uncontested rule (`apply_defense=False`, 99% make) |
| 1 | 75% shoot / 25% dish | Contested `calculate_shot_score` when shooting |
| 2+ (double team) | 25% shoot / 75% dish | If shoot: **+100 defense shot score bonus** (×0.2 impact on final score) |

**Dish target selection** (when dish chosen):
1. 75% branch — interior priority after drive completes: **midLane** → random **lowPost** → random **midPost** (one preferred interior target)
2. 25% branch — random teammate except driver

Clearance midLane spacer can also be the driver dish target.

**Dish shot type:** Inside if receiver end coord ≤ **15 euclidean** from attacking basket; else Outside. Updates `shot_type` / `playcall` returned from `resolve_motion_offense_shot()`.

**Unguarded dish receiver:** OREB uncontested rule (same as unguarded driver shoot).

---

### Attack Drive — Shot Resolution Flags

`resolve_motion_offense_shot()` returns and `resolve_hco_outcome()` stamps on `roles`:

| Flag | Purpose |
|------|---------|
| `motion_attack_geometry_contest` | Use euclidean ≤10 contest (not role-based HCO contest) |
| `motion_attack_uncontested` | OREB 99% make path in `shot_manager.resolve_shot()` |
| `motion_attack_defense_bonus` | +100 defense score when double-teamed driver shoots |

Contest defenders assigned by closest-in-range geometry at shot resolve time (after `apply_coords_from_animations_list`).

### Tuning Reference — Numbers & Read Thresholds

High-level design knobs for attack-drive logic. **Code lives in** `attack_drive_clearance.py` (and `shared.py` for score helpers). Change the doc first, then sync constants in code.

**Read score (all reads):** `player_read = (IQ × 0.8 + CH × 0.2) × random(1, 6)` — pass if **read > threshold**

**Perimeter relocation (offense)**
- Threshold: **150 − (offense team chemistry + offensive efficiency)**; floor **−3**
- Pass → cut to open tangential spot (random player order, single pass)

**Perimeter follow (defense)**
- Threshold: **125 − (defense team chemistry + defensive efficiency)**; floor **−3**
- Pass → defender cuts to guard relocated offensive player

**Help / double-team read (defense)**
- Threshold: **100 − (defense chemistry + defensive efficiency)**; floor **−3**
- Applies to: clearance midLane spacer double, help rotation to collapse point
- No 50/50 — read gate only

**Drive contest (primary defender stick vs beaten)**
- Offense score: `calculate_ball_handling_score(driver)` + **offensive efficiency × random(1, 3)**
  - Ball handling helper: **(BH × 0.5 + AG × 0.2 + IQ × 0.2 + CH × 0.1) × random(1, 6)**
- Defense score: `calculate_defender_pressure_score(primary)` + **defensive efficiency × random(1, 3)**
  - Pressure helper: **(OD × 0.3 + AG × 0.3 + IQ × 0.2 + CH × 0.2) × random(1, 6)**; zone × **0.9**
- Offense wins if: **offense score > defense score + 2 × (defense chemistry + defensive efficiency)**
- **Defense wins** → primary `guard_ball` at drive destination
- **Offense wins** → primary `cut` to **halfway** point (start → destination midpoint)

**Geometry (post-drive)**
- **Contest radius:** 10 euclidean grid spots (defender counts as guarding driver/receiver)
- **Inside vs outside dish shot:** receiver ≤ **15** euclidean from basket → Inside; else Outside

**Driver shoot vs dish (after geometry count)**
- **0 defenders** at spot → 100% shoot
- **1 defender** → **75%** shoot / **25%** dish
- **2+ defenders** (double team) → **25%** shoot / **75%** dish
- When dish chosen → **75%** prefer interior target (midLane → lowPost → midPost) / **25%** random teammate

**Shot resolution bonuses (at `resolve_shot`)**
- Unguarded driver or dish receiver → **99%** make (OREB uncontested path)
- Double-team + driver shoots → **+100** defense shot score bonus (× **0.2** applied to final shot score)
- Charge / blocking foul on attack shots → see [`Shot_System.md`](Shot_System.md) (`CHARGE_THRESHOLD` **−240**, `BLOCKING_FOUL_THRESHOLD` **+220**)

**Lane clearance (evac spacing)**
- Evac x range: home **77–87** / away **13–23**
- Evac y range: upper half **19–25** / lower half **26–32**
- Min separation between evac coords: **3** euclidean

**Skeleton timing hints (not animation duration)**
- Drive → next step: **+300** ms
- Drive → dish shoot: **+600** ms

### Execution Flow Details

**Phase 1: Select Random Step**
- Choose step 1-N (excluding step 0) for shot attempt
- Truncate skeleton at selected step
- Store last timestamp for new step creation

**Phase 2: Identify Ball Handler**
- Find ball handler position and location at selected step from `pos_actions`
- Look for actions: `handle_ball`, `receive`, or `pass`
- Extract ball handler position (e.g., "PG", "SG") and location (e.g., "upper wing", "key")

**Phase 3: Check Shot Possibilities**
- `_check_inside_shot_possibility()`: Checks if ball handler is at inside location OR if there are available inside receivers
- `_check_attack_shot_possibility()`: Checks if ball handler is NOT at inside location (attack shots require non-inside starting position)
- `_check_outside_shot_possibility()`: Checks if ball handler is at outside location OR if there are available outside receivers
- Each function returns boolean possibility and list of viable receivers/players

**Phase 4: Build Weighted List**
- Get strategy settings from `off_team.strategy_settings` (`inside`, `attack`, `outside` weights)
- `_build_shot_type_weighted_list()` creates weighted list based on:
  - Strategy settings (user preferences)
  - Shot type possibilities (what's actually available)
  - Ball handler location (if at inside, inside shots get weight boost)
- Returns list like `["inside", "inside", "attack", "outside"]` for random selection

**Phase 5: Select Shot Type**
- Randomly select from weighted list
- Log selected shot type for debugging

**Phase 6: Execute Shot**

**Inside Shot Execution:**
- If ball handler at inside location:
  - Create single shoot step at current location
- Else (ball handler not at inside):
  - Find closest inside receiver using `_find_closest_receiver()`
  - Create pass/receive step
  - Create shoot step for receiver
  - Update shooter to receiver

**Outside Shot Execution:**
- If ball handler at outside location:
  - Create single shoot step at current location
- Else (ball handler not at outside):
  - Find closest outside receiver using `_find_closest_receiver()`
  - Create pass/receive step
  - Create shoot step for receiver
  - Update shooter to receiver

**Attack Shot Execution:**
- Determine valid drive destinations using `_determine_attack_drive_destination(ball_handler_location)`
- Randomly select destination from valid destinations
- Call `_create_attack_drive_shoot_steps()` → `build_attack_drive_sequence()` when HCO context available
- Possible skeleton append: 2 steps (drive + shoot) or 3 steps (drive + pass/receive + shoot)
- Shooter may change on dish; `shot_type` / `playcall` may become Inside or Outside on dish
- Calculate attack penalty using `_apply_attack_penalty()` on final shooter location
- Return motion attack flags for geometry contest / uncontested / double-team defense bonus

**Phase 7: Append Steps**
- Append all new steps to truncated skeleton
- Skeleton now contains: original steps up to selected step + new shot steps

**Phase 8: Return Results**
- Map shot type to playcall: `{"inside": "Inside", "outside": "Outside", "attack": "Attack"}`
- Return dictionary with:
  - `skeleton`: Modified skeleton with shot steps
  - `shooter`, `shooter_pos`, `shooter_location`
  - `shot_type`, `playcall`, `attack_penalty`
  - **Attack drive only:** `motion_attack_uncontested`, `motion_attack_geometry_contest`, `motion_attack_defense_bonus`

### Attack Penalty System

**Function:** `_apply_attack_penalty(shot_location, is_away_offense)`

**Purpose:** Calculate penalty if player was stopped short of intended destination during attack drive

**Logic:**
- No penalty for ideal spots: `["basketSpot", "upper lowPost", "lower lowPost"]`
- For other locations: Calculate distance from shot location to basket
- Penalty = `abs(shot_coords["x"] - basket_coords["x"])`
- Penalty is subtracted from shot score during shot calculation

**Note:** `stopped_short` is not yet implemented; penalty applies to non-ideal shot locations regardless.

### Integration with Shot Detection

**3-Point Detection:**
- Uses `shooter_location` from final step (shoot step)
- Compares location against `THREE_POINT_SPOTS` constant
- Dish to perimeter receiver correctly classifies as outside / three-point when applicable

**Shot Calculation:**
- Uses `playcall` / `motion_shot_type` for attribute weights (Inside / Attack / Outside)
- Motion attack drives with `motion_attack_geometry_contest`: contest via euclidean ≤10 at resolve time
- Unguarded motion attack (driver or dish receiver): OREB rule — `apply_defense=False`, 99% make
- Double-team driver shoot: +100 defense score bonus
- Applies attack penalty if `attack_penalty > 0`
- No variant modifier for Motion plays (unlike Set Plays)

See also: [`Shot_System.md`](Shot_System.md) for general shot resolution; uncontested paths documented there.

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_motion_offense_shot()` — Main shot resolution function
  - `_create_attack_drive_shoot_steps()` — Delegates to attack drive sequence builder
  - `_determine_attack_drive_destination()`, `_check_*_shot_possibility()`, `_build_shot_type_weighted_list()`, `_apply_attack_penalty()`
  - `_create_pass_receive_step()`, `_create_shoot_step()`
- `BackEnd/engine/attack_drive_clearance.py` ✅ **June 2026**
  - `build_attack_drive_sequence()` — Full drive resolver (clearance, perimeter, contest, dish/shoot)
  - `build_attack_drive_clearance()` — Legacy wrapper returning pos_actions only (tests)
  - Constants: `ATTACK_DRIVE_CONTEST_RADIUS`, `ATTACK_DRIVE_INSIDE_RADIUS`
- `BackEnd/engine/skeleton_step_emitter.py` — UESS step emission; `attack_drive_driver` / shooter gates
- `BackEnd/models/shot_manager.py` — `resolve_shot()` motion attack geometry + uncontested handling
- `BackEnd/utils/shared.py` — `calculate_ball_handling_score()`, `calculate_defender_pressure_score()`, `player_read()`
- Attribute weights: `BackEnd/constants/__init__.py` → `PLAYCALL_ATTRIBUTE_WEIGHTS`

**Animation (backend → frontend data):**
- `BackEnd/models/animator.py` — Skeleton → animations; `_attack_drive_defender_override()` on drive steps

**Tests:**
- `tests/test_attack_drive_clearance.py`

### UESS Coord Notes (attack drive)

| Step | All 10 end coords |
|------|-------------------|
| Drive | 5 offense explicit in `pos_actions`; 5 defense via `defender_overrides` + emitter defaults |
| Pass/receive | Passer + receiver explicit; others stationary at prior step end (emitter chain) |
| Shoot | All 5 offense explicit (stationary + shooter) |

Step N+1 `start.coords` = step N `end.coords` per player (emitter). Pass/receive step T is distance-based (ball + movers), not skeleton timestamp.

**QA focus:** Dish turns — verify no teleport at step boundaries; `final_ball_handler_id` correct after pass step.

### Differences from Set Play Shot Resolution

**Motion Offense:**
- Shot type determined dynamically during resolution
- Attack drives: multi-layer backend logic on single concurrent drive step (HCO only)
- Uses `base_loop` skeleton (no variants)
- No variant modifier applied to shot threshold

**Set Plays:**
- Shot location predetermined in skeleton
- Shot type from skeleton analysis (location + drive detection)
- Uses variant skeletons and variant modifier on shot threshold
