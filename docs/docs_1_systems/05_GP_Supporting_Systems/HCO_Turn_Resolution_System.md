

**Base Constants**
1. STANDARD_D_FOUL = 95 (defensive foul threshold)
2. STANDARD_O_FOUL = 5 (offensive foul threshold)
3. HARD_STEAL = -200 (hard steal threshold)
4. SOFT_STEAL = -100 (soft steal threshold)
5. HARD_FOUL = 200 (hard foul threshold on steal attempts)
6. SOFT_FOUL = 100 (soft foul threshold on steal attempts)
7. STEAL_ATTEMPT = 20 (base steal attempt rate %)
8. DEAD_BALL_TURNOVER = 7 (dead ball turnover threshold)

**HCO Turn Resolution Flow (5 Steps)**
1. Get Base Constants

2. Get Team Attributes / Strategy Calls
-Offense: offensive_efficiency, discipline, fight
-Defense: defenseive_efficiency, fight, aggression_call

3. Calibrate Constants
-calibrated_d_foul = STANDARD_D_FOUL + int(fight_def * 0.4) (max 98)
-calibrated_o_foul = STANDARD_O_FOUL - fight_off (min 2)
-calibrated_hard_steal = HARD_STEAL - discipline
-calibrated_soft_steal = SOFT_STEAL - discipline
-calibrated_dead_ball_to = DEAD_BALL_TURNOVER - int(0.5 * discipline) (min 2)
-steal_attempt_rate = STEAL_ATTEMPT ± 10 based on aggression (clamped 10-30%)

4. Randomize Event Checks
(order of checks fo Standard Fouls, Steal Attempt, & Dead Ball Turnover are randomized)
-Standard Fouls
    1. Roll 1-100
    2. if roll <= calibrated_o_foul -> O_FOUL
    3. if roll >= calibrated_d_foul -> D_FOUL
    4. Otherwise, no foul
-Steal Attempt
    1. Roll 1-100
    2. if roll < steal_attempt_rate -> steal attempt occurs
        a. Calculate delta = ball_handling_score - defender_pressure_score
        b. if delta <= calibrated_hard_steal -> STEAL
        c. elif delta <= calibrated_soft_steal -> 16% chance steal, or no event
            -roll 1-100, if roll <= 16, STEAL
        d. elif detla >= calibrated_hard_foul -> D_FOUL
        e. elif delta >= calibrated_soft_foul -> 16% chance D_FOUL, or no event
            -roll 1-100, if roll <= 16, D_FOUL
        f. else, no event
-Dead Ball Turnover
    1. Roll 1-100
    2. if roll < calibrated DEAD_BALL_TURNOVER -> Dead Ball Turnover Check
        a. bh_score = calculate_ball_handlling_score(ball_handler)
        b. defender_score = calculate_defender_pressure_score(defender, defense_call)
            -any zone defense reduces defender_score by 10 percent
        c. if defender_score > bh_score -> dead ball turnover occurs
        d. else, no turnover
    3. else, no turnover

5. Shot Attempt (if not Stopping Event)
-result = (offensive_efficiency + random 1-100) - (defensive_efficiency + random 1-100)
    a. if result > 50 = successful (-50 to shot_threshold)
    b. elif result > 0 = mid play change (no change to shot_threshold)
    c. elif result > -50 = contested (+25 to shot_threshold)
    d. else = broken (+100 to shot_threshold)


**Long Form Documentation**

## HCO (Half Court Offense) Resolution System

### Base Values

HCO resolution starts with the following base values (derived from D1 Men's College Basketball statistics):

- **Shot Attempt**: 70
- **Offensive Foul**: 7
- **Defensive Foul (non-shooting)**: 10
- **Dead Ball Turnover**: 7
- **Steal**: 6

### HCO Resolution Flow

The HCO resolution system processes outcomes in the following order:

#### Step 1: Get Team Attributes and Settings

**Offense Team:**
- `offensive_efficiency`
- `discipline`
- `fight`

**Defense Team:**
- `defensive_efficiency`
- `fight`
- `aggression` setting (from `strategy_calls["aggression_call"]` - strings: "passive", "normal", "aggressive")

#### Step 2: Calibrate Universal Constants

**Universal Base Constants:**
- `STANDARD_D_FOUL = 95`
- `STANDARD_O_FOUL = 5`
- `HARD_STEAL = -200`
- `SOFT_STEAL = -100`
- `HARD_FOUL = 200`
- `SOFT_FOUL = 100`
- `SOFT_PROB = 0.16`
- `STEAL_ATTEMPT = 20`
- `DEAD_BALL_TURNOVER = 7`

**Calibration Formulas:**
```python
# Standard D Foul calibration
calibrated_d_foul = STANDARD_D_FOUL + int(fight_def * 0.4)
calibrated_d_foul = min(98, calibrated_d_foul)  # Max 98

# Standard O Foul calibration
calibrated_o_foul = STANDARD_O_FOUL - fight_off
calibrated_o_foul = max(2, calibrated_o_foul)  # Min 2

# Steal thresholds calibration
calibrated_hard_steal = HARD_STEAL - discipline
calibrated_soft_steal = SOFT_STEAL - discipline

# Foul thresholds calibration (on steal attempts)
calibrated_hard_foul = HARD_FOUL - int(fight_def * 0.6)
calibrated_soft_foul = SOFT_FOUL - int(fight_def * 0.6)

# Dead Ball Turnover calibration
calibrated_dead_ball_to = DEAD_BALL_TURNOVER - int(0.5 * discipline)
calibrated_dead_ball_to = max(2, calibrated_dead_ball_to)  # Min 2
```

#### Steps 3-5: Event Checks (Randomized Order)

The system randomizes the execution order of these three event checks to reflect the reality that these events can occur in any order during a possession:

1. **Standard Fouls Check** (`_check_standard_fouls()`)
2. **Steal Attempt Check** (`_check_steal_attempt()`)
3. **Dead Ball Turnover Check** (`_check_dead_ball_turnover()`)

Each check returns immediately if its event occurs. If no event occurs after checking all three, the resolution proceeds to Step 6 (Shot Attempt).

**Modular Functions:**

- **`_check_standard_fouls(calibrated_o_foul, calibrated_d_foul)`**
  - Checks for offensive or defensive fouls
  - Returns `("O_FOUL", None)`, `("D_FOUL", None)`, or `None`
  - **Process:**
    1. Roll: `result = random.randint(1, 100)`
    2. If `result <= STANDARD_O_FOUL`: **O_FOUL result** (end resolution)
    3. Elif `result >= STANDARD_D_FOUL`: **D_FOUL result** (end resolution)
    4. Else: Return `None` (continue to next check)
  - **Range Overlap:** `STANDARD_O_FOUL` and `STANDARD_D_FOUL` will never overlap, as the maximum adjustment for either is ±10, ensuring they remain in separate ranges (O_FOUL: 2-15, D_FOUL: 95-98).

- **`_check_steal_attempt(game, skeleton, calibrated_hard_steal, calibrated_soft_steal, calibrated_hard_foul, calibrated_soft_foul, steal_attempt_rate)`**
  - Checks for steal attempt and resolves it using `resolve_steal_attempt()`
  - Returns `("STEAL", None)`, `("D_FOUL", None)`, or `None`

**Process:**
1. **Apply Aggression Modifier to Steal Attempt Rate:**
   - Base: `STEAL_ATTEMPT = 20`
   - **Aggression from `strategy_calls["aggression_call"]`** (strings: "passive", "normal", "aggressive")
   - `"aggressive"`: `STEAL_ATTEMPT += 10` (30% total)
   - `"passive"`: `STEAL_ATTEMPT -= 10` (10% total)
   - `"normal"` or any other value: No change (20% total)

2. **Roll for Steal Attempt:**
   - `result = random.randint(1, 100)`
   - If `result < STEAL_ATTEMPT`: Proceed with steal attempt
   - Else: Continue to Step 5

3. **If Steal Attempt Occurs:**
   - Select a random step from the skeleton
   - Determine ball handler at that step using `get_ball_handler_from_skeleton()`
   - Determine defender using man-to-man or zone defense logic:
     - **Man Defense**: Defender matches ball handler's position
     - **Zone Defense**: Uses `assign_all_zone_defenders()` with all 6 required arguments:
       - Zone boundaries (calculated from ball handler's spot)
       - Offensive players list (built from skeleton step)
       - Ball handler coordinates
       - Ball handler spot
       - Aggression level (converted from `strategy_settings` integer to string via `aggression_map` for zone defense logic)
       - `is_away_offense` flag
   - Calculate offense value (ball handler protection):
     ```python
     bh_score = (
         attrs["BH"] * 0.5 +
         attrs["AG"] * 0.2 +
         attrs["IQ"] * 0.2 +
         attrs["CH"] * 0.1
     ) * random.randint(1, 6)
     ```
   - Calculate defense value (defender steal attempt):
     ```python
     pressure = (
         def_attrs["OD"] * 0.3 +
         def_attrs["AG"] * 0.3 +
         def_attrs["IQ"] * 0.2 +
         def_attrs["CH"] * 0.2
     ) * random.randint(1, 6)
     if is_zone_defense(defense_call):
         pressure *= 0.9
     ```
   - Run `resolve_steal_attempt(offense_value, defense_value, SOFT_STEAL, HARD_STEAL, SOFT_FOUL, HARD_FOUL)`
   - If result = `"STEAL"`: **STEAL result** (end resolution)
   - If result = `"D_FOUL"`: **D_FOUL result** (end resolution - functionally the same as standard D_FOUL)
   - If result = `"NO_EVENT"`: Continue to Step 5

**Note:** If Step 4 triggers (steal attempt occurs), Step 5 is **not** executed. The resolution ends with either STEAL or D_FOUL, or continues to Step 6 if NO_EVENT.

  - **Process:**
    1. **Roll for Dead Ball Turnover:**
       - `result = random.randint(1, 100)`
       - If `result < DEAD_BALL_TURNOVER`: Proceed with turnover check
       - Else: Return `None` (continue to next check)
    2. **If Turnover Check Occurs:**
       - Select a random step from the skeleton (may be different from other checks' selected steps)
       - Determine ball handler at that step using `get_ball_handler_from_skeleton()`
       - Determine defender using man-to-man or zone defense logic:
         - **Man Defense**: Defender matches ball handler's position
         - **Zone Defense**: Uses `assign_all_zone_defenders()` with all 6 required arguments:
           - Zone boundaries (calculated from ball handler's spot)
           - Offensive players list (built from skeleton step)
           - Ball handler coordinates
           - Ball handler spot
           - Aggression level (from strategy_settings)
           - `is_away_offense` flag
       - Calculate ball handling score (offensive player):
         ```python
         from BackEnd.utils.shared import calculate_ball_handling_score
         bh_score = calculate_ball_handling_score(ball_handler)
         ```
       - Calculate defender score:
         ```python
         from BackEnd.utils.shared import calculate_defender_pressure_score
         defender_score = calculate_defender_pressure_score(defender, defense_call)
         ```
       - If `defender_score > bh_score`: **DEAD_BALL_TURNOVER result** (end resolution)
       - Else: Return `None` (continue to next check)

**Important:** When the resolution system determines a `DEAD_BALL_TURNOVER`, it is converted to `"DEAD BALL"` (with a space) before calling `resolve_turnover_logic()`. The `resolve_turnover_logic()` function respects the resolution system's determination when `from_resolution_system=True`, preventing random conversion of dead ball turnovers to steals.

**Utility Functions:**
- `calculate_ball_handling_score(player)` - Located in `BackEnd/utils/shared.py`
  - Formula: `(BH * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random.randint(1, 6)`
- `calculate_defender_pressure_score(defender, defense_call)` - Located in `BackEnd/utils/shared.py`
  - Formula: `(OD * 0.3 + AG * 0.3 + IQ * 0.2 + CH * 0.2) * random.randint(1, 6)`
  - Zone defense modifier: `pressure *= 0.9`

**Note:** Both functions use `random.randint(1, 6)` multiplier, ensuring consistent randomization across both scores.

#### Step 6: Shot Attempt and Execution Score Calculation

**EV Calculation (Before Execution):**
- **EV Calculation**: Calculated in `turn_manager.py` via `calculate_ev()` before play execution
  - **For Motion Plays**: Uses `game_state["offense_play_focus"]` (chosen focus from strategy settings: inside/attack/outside)
  - **For Set Plays**: Uses `play_doc.get("play_focus")` (intended focus from database)
  - Motion plays have `play_focus = null` in database, so chosen focus from strategy settings is used
  - EV represents expected value based on the **chosen/intended focus** before execution
  - Stored via `_store_ev_score()` after EV calculation

**Execution Score Calculation:**
- **Step 6a: Calculate Effectiveness Scores**
  - `o_random = random.randint(1, 100)`
  - `d_random = random.randint(1, 100)`
  - `o_score = offensive_efficiency + o_random`
  - `d_score = defensive_efficiency + d_random`
  - `result = o_score - d_score`
  
- **Step 6b: Cap Result for Execution Score**
  - If `result > 100`: `result = 100`
  - If `result < -100`: `result = -100`
  - This caps the execution score calculation range to -100 to +100
  
- **Step 6c: Scale to Execution Score (0-100)**
  - Formula: `execution_score = (capped_result + 100) / 2`
  - Maps: -100 → 0%, 0 → 50%, +100 → 100%
  - Execution score represents play execution quality (0% = worst, 100% = best)
  
- **Step 6d: Store Execution Score**
  - Execution score is stored in `game_state["execution_score"]` for later stat tracking
  - Converted to `lean_score` format (-1.0 to +1.0) for storage in scouting data
  - Conversion: `lean_score = (execution_score - 50) / 50`
  - Stored via `_store_execution_score()` after shot resolution
  - **Focus for Storage**:
    - **Motion Plays**: Uses actual shot type (`motion_shot_type`) determined during execution
    - **Set Plays**: Uses intended focus from strategy settings
    - This means Motion Plays can have EV stored under one focus (chosen) and execution score stored under a different focus (actual)

**Skeleton Variant Selection:**
- Uses original uncapped `result` value (not execution_score)
- Variant thresholds:
  - `result > 50` → "successful"
  - `0 < result <= 50` → "mid_play_change"
  - `-50 < result <= 0` → "contested"
  - `result <= -50` → "broken"

#### Step 6: Shot Attempt (if no event occurred in Steps 3-5)

**Process:**
1. **Calculate Play Effectiveness Scores:**
   - `o_score = offense_play_effectiveness_score + offensive_efficiency`
   - `d_score = defense_play_effectiveness_score + defensive_efficiency`
   
   **Database Structure:**
   - **Defensive Zone Plays**: Already have `effectiveness_score` in database
   - **Defensive Man Defense Play**: Needs to be added to database with `effectiveness_score`
   - **Offensive Plays**: Need `effectiveness_score` added to all offensive play documents
   
   **Initial Implementation:**
   - For plays without effectiveness scores, use random numbers:
     - `o_score += random.randint(1, 100)`
     - `d_score += random.randint(1, 100)`

2. **Calculate Result:**
   - `result = o_score - d_score`

3. **Select Skeleton Variant Based on Result:**
   - If `result > 50`: Use **successful** skeleton variant
   - Elif `result > 0`: Use **mid_play_change** skeleton variant
   - Elif `result > -50`: Use **contested** skeleton variant
   - Else: Use **broken** skeleton variant
   
   **Note:** This replaces the previous `lean_score` system. The new result-based selection is used instead of lean_score calculations.

4. **Apply Shot Result Modifiers:**
   - Use existing shot resolution modifiers from `ShotManager.resolve_shot()`
   - Calculate shot outcome (MAKE/MISS) based on shooter attributes, defender attributes, and playcall matchups

### Legacy Calculation Process (To Be Replaced)

#### Step 1: Apply Team Attribute Modifiers

At the start of the game, team attribute modifiers are applied to the base values. These modifiers persist throughout the game (team attributes don't change during turns).

**Example Calculation:**

**Offense Team Attributes:**
- `offensive_efficiency` = 8
- `foul_modifier` = -6
- `turnover_modifier` = 10

**Defense Team Attributes:**
- `defensive_efficiency` = 1
- `foul_modifier` = -7

**Modified Values:**
- **Shot Attempt**: `70 + 8 (offense_efficiency) - 1 (defense_efficiency) = 78`
- **Offensive Foul**: `7 - (-6) (offense team foul_modifier) = 13`
- **Defensive Foul (non-shooting)**: `10 - (-7) (defense team foul_modifier) = 17`
- **Dead Ball Turnover**: `7 - 5 (0.5 * offense team turnover_modifier) = 2`
- **Steal**: `6 - 5 (0.5 * offense team turnover_modifier) = 1`

**Turnover Modifier Split:**
- The `turnover_modifier` is split 50/50 between Dead Ball Turnover and Steal
- If `turnover_modifier` is odd, the extra point (positive or negative) is added to Dead Ball Turnover

**Attribute Application Rules:**
- **Shot Attempt**: `base + offensive_efficiency - defensive_efficiency`
- **Offensive Foul**: `base - offense_team.foul_modifier` (subtracting negative = adding)
- **Defensive Foul (non-shooting)**: `base - defense_team.foul_modifier` (subtracting negative = adding)
- **Dead Ball Turnover**: `base - (0.5 * offense_team.turnover_modifier)` (if odd, add remainder)
- **Steal**: `base - (0.5 * offense_team.turnover_modifier)`

#### Step 2: Apply Aggression Setting Modifiers

At the turn level, the defense team's aggression setting is applied. Aggression settings can change turn by turn.

**Normal Aggression** (default):
- No changes to resolution values

**Aggressive Aggression**:
- **Defensive Foul (non-shooting)**: `+4`
- **Steal**: `+2`
- **Dead Ball Turnover**: `+2`

**Passive Aggression**:
- **Defensive Foul (non-shooting)**: `-4`
- **Steal**: `-2`
- **Dead Ball Turnover**: `-2`

#### Step 3: Enforce Minimum Values

After all modifications, ensure no value goes below **2**:
- If any resolution value is below 2, set it to 2

#### Step 4: Steal Attempt Resolution (HCO-Specific)

**Steal Attempt Rate:**
- Base steal attempt rate: **20%** of half court possessions
- **Aggression from `strategy_calls["aggression_call"]`** (strings: "passive", "normal", "aggressive")
- Aggression setting modifiers:
  - **"aggressive"**: `+10 percentage points` (30% total)
  - **"passive"**: `-10 percentage points` (10% total)
  - **"normal"** or any other value: No change (20% total)

**Steal Attempt Process:**
1. **Step Selection**: If a steal attempt occurs, select a random step from the skeleton
2. **Ball Handler Determination**: Use `get_ball_handler_from_skeleton()` to identify the ball handler at the selected step
3. **Defender Determination**: Use man-to-man or zone defense logic to identify the defender guarding the ball handler at that step
   - **Man Defense**: Defender matches ball handler's position
   - **Zone Defense**: Use zone assignment logic to find which defender(s) are guarding the ball handler's location

**Offense Value Calculation (Ball Handler's Protection):**
```python
bh_score = (
    attrs["BH"] * 0.5 +
    attrs["AG"] * 0.2 +
    attrs["IQ"] * 0.2 +
    attrs["CH"] * 0.1
) * random.randint(1, 6)
```

**Defense Value Calculation (Defender's Steal Attempt):**
```python
pressure = (
    def_attrs["OD"] * 0.3 +
    def_attrs["AG"] * 0.3 +
    def_attrs["IQ"] * 0.2 +
    def_attrs["CH"] * 0.2
) * random.randint(1, 6)
if is_zone_defense(defense_call):
    pressure *= 0.9  # Zone defense reduces steal pressure
```

**Universal Threshold Constants:**
These thresholds are base universal values, calibrated per-turn based on team attributes:

- `HARD_STEAL = -200` (defense wins decisively) - Calibrated using offense team's `discipline`
- `SOFT_STEAL = -100` (defense wins marginally) - Calibrated using offense team's `discipline`
- `HARD_FOUL = 200` (offense wins decisively, defender reaches) - Calibrated using defense team's `fight`
- `SOFT_FOUL = 100` (offense wins marginally, defender reaches) - Calibrated using defense team's `fight`
- `SOFT_PROB = 0.16` (probability for soft bands, calibrated so equal-strength d6 vs d6 yields 30% in soft+hard bands)

**Steal Resolution Function:**
```python
def resolve_steal_attempt(offense_value: int, defense_value: int,
                          soft_steal: int, hard_steal: int,
                          soft_foul: int, hard_foul: int) -> str:
    """
    Resolve outcome of a steal attempt.
    
    Args:
        offense_value: Ball handler's protection value (bh_score)
        defense_value: Defender's steal attempt value (pressure)
        soft_steal: Soft steal threshold (default: -100)
        hard_steal: Hard steal threshold (default: -200)
        soft_foul: Soft foul threshold (default: 100)
        hard_foul: Hard foul threshold (default: 200)
    
    Returns:
        One of:
        - "STEAL" - Steal successful, possession changes
        - "D_FOUL" - Defensive foul on steal attempt, offense retains possession
        - "NO_EVENT" - No event, play continues normally
    """
    delta = offense_value - defense_value  # negative => defense won the contest
    
    # 1) Steal outcomes (defense wins)
    if delta <= hard_steal:
        return "STEAL"
    if delta <= soft_steal:
        # Soft steal band: partial probability to calibrate to baseline rates
        if random.random() < SOFT_PROB:
            return "STEAL"
    
    # 2) Defensive foul outcomes (offense wins / defender reaches)
    if delta >= hard_foul:
        return "D_FOUL"
    if delta >= soft_foul:
        if random.random() < SOFT_PROB:
            return "D_FOUL"
    
    # 3) Otherwise nothing happens; possession continues
    return "NO_EVENT"
```

**Return Value Nomenclature:**
- `"STEAL"` - Steal successful, results in possession change and fast break opportunity
- `"D_FOUL"` - Defensive foul on steal attempt, offense retains possession (may result in free throws if in bonus)
- `"NO_EVENT"` - No event occurs, play continues normally to shot attempt or other outcome

**Threshold Calibration:**
Universal thresholds are calibrated per-turn based on team attributes:
- **Steal thresholds**: Adjusted using offense team's `discipline` attribute
  - Higher `discipline` (lower turnover risk) → thresholds adjusted to favor offense (less likely to steal)
  - Lower `discipline` (higher turnover risk) → thresholds adjusted to favor defense (more likely to steal)
- **Foul thresholds (on steal attempts)**: Adjusted using defense team's `fight` attribute
  - Higher `fight` → thresholds adjusted to reduce foul likelihood
  - Lower `fight` → thresholds adjusted to increase foul likelihood
- Calibration formulas are applied in Step 2 of the resolution flow (see Calibration Formulas above)

### Example: Complete HCO Resolution Calculation

**Initial State:**
- Base values: Shot=70, O_Foul=7, D_Foul=10, TO=7, Steal=6
- Offense: `offensive_efficiency=8`, `foul_modifier=-6`, `turnover_modifier=10`
- Defense: `defensive_efficiency=1`, `foul_modifier=-7`
- Defense Aggression: `aggressive`

**After Step 1 (Team Attributes):**
- Shot Attempt: `70 + 8 - 1 = 77`
- Offensive Foul: `7 - (-6) = 13`
- Defensive Foul: `10 - (-7) = 17`
- Dead Ball Turnover: `7 - 5 = 2` (10 * 0.5 = 5)
- Steal: `6 - 5 = 1`

**After Step 2 (Aggression Setting):**
- Shot Attempt: `77` (unchanged)
- Offensive Foul: `13` (unchanged)
- Defensive Foul: `17 + 4 = 21`
- Dead Ball Turnover: `2 + 2 = 4`
- Steal: `1 + 2 = 3`

**After Step 3 (Minimum Values):**
- All values are ≥ 2, no changes needed

**Final Resolution Values:**
- Shot Attempt: 77
- Offensive Foul: 13
- Defensive Foul: 21
- Dead Ball Turnover: 4
- Steal: 3

### Key Implementation Notes

1. **Team Attribute Persistence**: Team attributes are set at game start and don't change during turns (future: may change during timeouts)
2. **Attribute Inversion**: When possession changes, offense/defense roles swap, so attribute applications are inverted
3. **Turnover Modifier Split**: Always 50/50 between Dead Ball Turnover and Steal, with odd remainder going to Dead Ball Turnover
4. **Minimum Value Enforcement**: Applied after all modifications to ensure no value goes below 2
5. **Future Score Generation**: Player attributes and actions will generate a score that maps to these resolution values

### Status

✅ **HCO Resolution**: Implementation complete (January 2025)
- Modular functions for fouls, steals, and turnovers
- Randomized execution order for event checks
- Respects resolution system determination (prevents random conversion of dead ball turnovers)
- Fast Break, HCT, and FCP resolution logic will be designed after HCO is tested

### Key Files

- `BackEnd/engine/phase_resolution.py` - Current HCO resolution logic (to be replaced)
- `BackEnd/models/turn_manager.py` - Current event type determination (to be replaced)
- `BackEnd/models/team_manager.py` - Team attribute initialization

# Long Form Documentation #2
## HCO (Half Court Offense) Resolution System

### Base Values

HCO resolution starts with the following base values (derived from D1 Men's College Basketball statistics):

- **Shot Attempt**: 70
- **Offensive Foul**: 7
- **Defensive Foul (non-shooting)**: 10
- **Dead Ball Turnover**: 7
- **Steal**: 6

### HCO Resolution Flow

The HCO resolution system processes outcomes in the following order:

#### Step 1: Get Team Attributes and Settings

**Offense Team:**
- `offensive_efficiency`
- `discipline`
- `fight`

**Defense Team:**
- `defensive_efficiency`
- `fight`
- `aggression` setting (from `strategy_calls["aggression_call"]` - strings: "passive", "normal", "aggressive")

#### Step 2: Calibrate Universal Constants

**Universal Base Constants:**
- `STANDARD_D_FOUL = 95`
- `STANDARD_O_FOUL = 5`
- `HARD_STEAL = -200`
- `SOFT_STEAL = -100`
- `HARD_FOUL = 200`
- `SOFT_FOUL = 100`
- `SOFT_PROB = 0.16`
- `STEAL_ATTEMPT = 20`
- `DEAD_BALL_TURNOVER = 7`

**Calibration Formulas:**
```python
# Standard D Foul calibration
calibrated_d_foul = STANDARD_D_FOUL + int(fight_def * 0.4)
calibrated_d_foul = min(98, calibrated_d_foul)  # Max 98

# Standard O Foul calibration
calibrated_o_foul = STANDARD_O_FOUL - fight_off
calibrated_o_foul = max(2, calibrated_o_foul)  # Min 2

# Steal thresholds calibration
calibrated_hard_steal = HARD_STEAL - discipline
calibrated_soft_steal = SOFT_STEAL - discipline

# Foul thresholds calibration (on steal attempts)
calibrated_hard_foul = HARD_FOUL - int(fight_def * 0.6)
calibrated_soft_foul = SOFT_FOUL - int(fight_def * 0.6)

# Dead Ball Turnover calibration
calibrated_dead_ball_to = DEAD_BALL_TURNOVER - int(0.5 * discipline)
calibrated_dead_ball_to = max(2, calibrated_dead_ball_to)  # Min 2
```

#### Steps 3-5: Event Checks (Randomized Order)

The system randomizes the execution order of these three event checks to reflect the reality that these events can occur in any order during a possession:

1. **Standard Fouls Check** (`_check_standard_fouls()`)
2. **Steal Attempt Check** (`_check_steal_attempt()`)
3. **Dead Ball Turnover Check** (`_check_dead_ball_turnover()`)

Each check returns immediately if its event occurs. If no event occurs after checking all three, the resolution proceeds to Step 6 (Shot Attempt).

**Modular Functions:**

- **`_check_standard_fouls(calibrated_o_foul, calibrated_d_foul)`**
  - Checks for offensive or defensive fouls
  - Returns `("O_FOUL", None)`, `("D_FOUL", None)`, or `None`
  - **Process:**
    1. Roll: `result = random.randint(1, 100)`
    2. If `result <= STANDARD_O_FOUL`: **O_FOUL result** (end resolution)
    3. Elif `result >= STANDARD_D_FOUL`: **D_FOUL result** (end resolution)
    4. Else: Return `None` (continue to next check)
  - **Range Overlap:** `STANDARD_O_FOUL` and `STANDARD_D_FOUL` will never overlap, as the maximum adjustment for either is ±10, ensuring they remain in separate ranges (O_FOUL: 2-15, D_FOUL: 95-98).

- **`_check_steal_attempt(game, skeleton, calibrated_hard_steal, calibrated_soft_steal, calibrated_hard_foul, calibrated_soft_foul, steal_attempt_rate)`**
  - Checks for steal attempt and resolves it using `resolve_steal_attempt()`
  - Returns `("STEAL", None)`, `("D_FOUL", None)`, or `None`

**Process:**
1. **Apply Aggression Modifier to Steal Attempt Rate:**
   - Base: `STEAL_ATTEMPT = 20`
   - **Aggression from `strategy_calls["aggression_call"]`** (strings: "passive", "normal", "aggressive")
   - `"aggressive"`: `STEAL_ATTEMPT += 10` (30% total)
   - `"passive"`: `STEAL_ATTEMPT -= 10` (10% total)
   - `"normal"` or any other value: No change (20% total)

2. **Roll for Steal Attempt:**
   - `result = random.randint(1, 100)`
   - If `result < STEAL_ATTEMPT`: Proceed with steal attempt
   - Else: Continue to Step 5

3. **If Steal Attempt Occurs:**
   - Select a random step from the skeleton
   - Determine ball handler at that step using `get_ball_handler_from_skeleton()`
   - Determine defender using man-to-man or zone defense logic:
     - **Man Defense**: Defender matches ball handler's position
     - **Zone Defense**: Uses `assign_all_zone_defenders()` with all 6 required arguments:
       - Zone boundaries (calculated from ball handler's spot)
       - Offensive players list (built from skeleton step)
       - Ball handler coordinates
       - Ball handler spot
       - Aggression level (converted from `strategy_settings` integer to string via `aggression_map` for zone defense logic)
       - `is_away_offense` flag
   - Calculate offense value (ball handler protection):
     ```python
     bh_score = (
         attrs["BH"] * 0.5 +
         attrs["AG"] * 0.2 +
         attrs["IQ"] * 0.2 +
         attrs["CH"] * 0.1
     ) * random.randint(1, 6)
     ```
   - Calculate defense value (defender steal attempt):
     ```python
     pressure = (
         def_attrs["OD"] * 0.3 +
         def_attrs["AG"] * 0.3 +
         def_attrs["IQ"] * 0.2 +
         def_attrs["CH"] * 0.2
     ) * random.randint(1, 6)
     if is_zone_defense(defense_call):
         pressure *= 0.9
     ```
   - Run `resolve_steal_attempt(offense_value, defense_value, SOFT_STEAL, HARD_STEAL, SOFT_FOUL, HARD_FOUL)`
   - If result = `"STEAL"`: **STEAL result** (end resolution)
   - If result = `"D_FOUL"`: **D_FOUL result** (end resolution - functionally the same as standard D_FOUL)
   - If result = `"NO_EVENT"`: Continue to Step 5

**Note:** If Step 4 triggers (steal attempt occurs), Step 5 is **not** executed. The resolution ends with either STEAL or D_FOUL, or continues to Step 6 if NO_EVENT.

  - **Process:**
    1. **Roll for Dead Ball Turnover:**
       - `result = random.randint(1, 100)`
       - If `result < DEAD_BALL_TURNOVER`: Proceed with turnover check
       - Else: Return `None` (continue to next check)
    2. **If Turnover Check Occurs:**
       - Select a random step from the skeleton (may be different from other checks' selected steps)
       - Determine ball handler at that step using `get_ball_handler_from_skeleton()`
       - Determine defender using man-to-man or zone defense logic:
         - **Man Defense**: Defender matches ball handler's position
         - **Zone Defense**: Uses `assign_all_zone_defenders()` with all 6 required arguments:
           - Zone boundaries (calculated from ball handler's spot)
           - Offensive players list (built from skeleton step)
           - Ball handler coordinates
           - Ball handler spot
           - Aggression level (from strategy_settings)
           - `is_away_offense` flag
       - Calculate ball handling score (offensive player):
         ```python
         from BackEnd.utils.shared import calculate_ball_handling_score
         bh_score = calculate_ball_handling_score(ball_handler)
         ```
       - Calculate defender score:
         ```python
         from BackEnd.utils.shared import calculate_defender_pressure_score
         defender_score = calculate_defender_pressure_score(defender, defense_call)
         ```
       - If `defender_score > bh_score`: **DEAD_BALL_TURNOVER result** (end resolution)
       - Else: Return `None` (continue to next check)

**Important:** When the resolution system determines a `DEAD_BALL_TURNOVER`, it is converted to `"DEAD BALL"` (with a space) before calling `resolve_turnover_logic()`. The `resolve_turnover_logic()` function respects the resolution system's determination when `from_resolution_system=True`, preventing random conversion of dead ball turnovers to steals.

**Utility Functions:**
- `calculate_ball_handling_score(player)` - Located in `BackEnd/utils/shared.py`
  - Formula: `(BH * 0.5 + AG * 0.2 + IQ * 0.2 + CH * 0.1) * random.randint(1, 6)`
- `calculate_defender_pressure_score(defender, defense_call)` - Located in `BackEnd/utils/shared.py`
  - Formula: `(OD * 0.3 + AG * 0.3 + IQ * 0.2 + CH * 0.2) * random.randint(1, 6)`
  - Zone defense modifier: `pressure *= 0.9`

**Note:** Both functions use `random.randint(1, 6)` multiplier, ensuring consistent randomization across both scores.

#### Step 6: Shot Attempt and Execution Score Calculation

**EV Calculation (Before Execution):**
- **EV Calculation**: Calculated in `turn_manager.py` via `calculate_ev()` before play execution
  - **For Motion Plays**: Uses `game_state["offense_play_focus"]` (chosen focus from strategy settings: inside/attack/outside)
  - **For Set Plays**: Uses `play_doc.get("play_focus")` (intended focus from database)
  - Motion plays have `play_focus = null` in database, so chosen focus from strategy settings is used
  - EV represents expected value based on the **chosen/intended focus** before execution
  - Stored via `_store_ev_score()` after EV calculation

**Execution Score Calculation:**
- **Step 6a: Calculate Effectiveness Scores**
  - `o_random = random.randint(1, 100)`
  - `d_random = random.randint(1, 100)`
  - `o_score = offensive_efficiency + o_random`
  - `d_score = defensive_efficiency + d_random`
  - `result = o_score - d_score`
  
- **Step 6b: Cap Result for Execution Score**
  - If `result > 100`: `result = 100`
  - If `result < -100`: `result = -100`
  - This caps the execution score calculation range to -100 to +100
  
- **Step 6c: Scale to Execution Score (0-100)**
  - Formula: `execution_score = (capped_result + 100) / 2`
  - Maps: -100 → 0%, 0 → 50%, +100 → 100%
  - Execution score represents play execution quality (0% = worst, 100% = best)
  
- **Step 6d: Store Execution Score**
  - Execution score is stored in `game_state["execution_score"]` for later stat tracking
  - Converted to `lean_score` format (-1.0 to +1.0) for storage in scouting data
  - Conversion: `lean_score = (execution_score - 50) / 50`
  - Stored via `_store_execution_score()` after shot resolution
  - **Focus for Storage**:
    - **Motion Plays**: Uses actual shot type (`motion_shot_type`) determined during execution
    - **Set Plays**: Uses intended focus from strategy settings
    - This means Motion Plays can have EV stored under one focus (chosen) and execution score stored under a different focus (actual)

**Skeleton Variant Selection:**
- Uses original uncapped `result` value (not execution_score)
- Variant thresholds:
  - `result > 50` → "successful"
  - `0 < result <= 50` → "mid_play_change"
  - `-50 < result <= 0` → "contested"
  - `result <= -50` → "broken"

#### Step 6: Shot Attempt (if no event occurred in Steps 3-5)

**Process:**
1. **Calculate Play Effectiveness Scores:**
   - `o_score = offense_play_effectiveness_score + offensive_efficiency`
   - `d_score = defense_play_effectiveness_score + defensive_efficiency`
   
   **Database Structure:**
   - **Defensive Zone Plays**: Already have `effectiveness_score` in database
   - **Defensive Man Defense Play**: Needs to be added to database with `effectiveness_score`
   - **Offensive Plays**: Need `effectiveness_score` added to all offensive play documents
   
   **Initial Implementation:**
   - For plays without effectiveness scores, use random numbers:
     - `o_score += random.randint(1, 100)`
     - `d_score += random.randint(1, 100)`

2. **Calculate Result:**
   - `result = o_score - d_score`

3. **Select Skeleton Variant Based on Result:**
   - If `result > 50`: Use **successful** skeleton variant
   - Elif `result > 0`: Use **mid_play_change** skeleton variant
   - Elif `result > -50`: Use **contested** skeleton variant
   - Else: Use **broken** skeleton variant
   
   **Note:** This replaces the previous `lean_score` system. The new result-based selection is used instead of lean_score calculations.

4. **Apply Shot Result Modifiers:**
   - Use existing shot resolution modifiers from `ShotManager.resolve_shot()`
   - Calculate shot outcome (MAKE/MISS) based on shooter attributes, defender attributes, and playcall matchups

### Legacy Calculation Process (To Be Replaced)

#### Step 1: Apply Team Attribute Modifiers

At the start of the game, team attribute modifiers are applied to the base values. These modifiers persist throughout the game (team attributes don't change during turns).

**Example Calculation:**

**Offense Team Attributes:**
- `offensive_efficiency` = 8
- `foul_modifier` = -6
- `turnover_modifier` = 10

**Defense Team Attributes:**
- `defensive_efficiency` = 1
- `foul_modifier` = -7

**Modified Values:**
- **Shot Attempt**: `70 + 8 (offense_efficiency) - 1 (defense_efficiency) = 78`
- **Offensive Foul**: `7 - (-6) (offense team foul_modifier) = 13`
- **Defensive Foul (non-shooting)**: `10 - (-7) (defense team foul_modifier) = 17`
- **Dead Ball Turnover**: `7 - 5 (0.5 * offense team turnover_modifier) = 2`
- **Steal**: `6 - 5 (0.5 * offense team turnover_modifier) = 1`

**Turnover Modifier Split:**
- The `turnover_modifier` is split 50/50 between Dead Ball Turnover and Steal
- If `turnover_modifier` is odd, the extra point (positive or negative) is added to Dead Ball Turnover

**Attribute Application Rules:**
- **Shot Attempt**: `base + offensive_efficiency - defensive_efficiency`
- **Offensive Foul**: `base - offense_team.foul_modifier` (subtracting negative = adding)
- **Defensive Foul (non-shooting)**: `base - defense_team.foul_modifier` (subtracting negative = adding)
- **Dead Ball Turnover**: `base - (0.5 * offense_team.turnover_modifier)` (if odd, add remainder)
- **Steal**: `base - (0.5 * offense_team.turnover_modifier)`

#### Step 2: Apply Aggression Setting Modifiers

At the turn level, the defense team's aggression setting is applied. Aggression settings can change turn by turn.

**Normal Aggression** (default):
- No changes to resolution values

**Aggressive Aggression**:
- **Defensive Foul (non-shooting)**: `+4`
- **Steal**: `+2`
- **Dead Ball Turnover**: `+2`

**Passive Aggression**:
- **Defensive Foul (non-shooting)**: `-4`
- **Steal**: `-2`
- **Dead Ball Turnover**: `-2`

#### Step 3: Enforce Minimum Values

After all modifications, ensure no value goes below **2**:
- If any resolution value is below 2, set it to 2

#### Step 4: Steal Attempt Resolution (HCO-Specific)

**Steal Attempt Rate:**
- Base steal attempt rate: **20%** of half court possessions
- **Aggression from `strategy_calls["aggression_call"]`** (strings: "passive", "normal", "aggressive")
- Aggression setting modifiers:
  - **"aggressive"**: `+10 percentage points` (30% total)
  - **"passive"**: `-10 percentage points` (10% total)
  - **"normal"** or any other value: No change (20% total)

**Steal Attempt Process:**
1. **Step Selection**: If a steal attempt occurs, select a random step from the skeleton
2. **Ball Handler Determination**: Use `get_ball_handler_from_skeleton()` to identify the ball handler at the selected step
3. **Defender Determination**: Use man-to-man or zone defense logic to identify the defender guarding the ball handler at that step
   - **Man Defense**: Defender matches ball handler's position
   - **Zone Defense**: Use zone assignment logic to find which defender(s) are guarding the ball handler's location

**Offense Value Calculation (Ball Handler's Protection):**
```python
bh_score = (
    attrs["BH"] * 0.5 +
    attrs["AG"] * 0.2 +
    attrs["IQ"] * 0.2 +
    attrs["CH"] * 0.1
) * random.randint(1, 6)
```

**Defense Value Calculation (Defender's Steal Attempt):**
```python
pressure = (
    def_attrs["OD"] * 0.3 +
    def_attrs["AG"] * 0.3 +
    def_attrs["IQ"] * 0.2 +
    def_attrs["CH"] * 0.2
) * random.randint(1, 6)
if is_zone_defense(defense_call):
    pressure *= 0.9  # Zone defense reduces steal pressure
```

**Universal Threshold Constants:**
These thresholds are base universal values, calibrated per-turn based on team attributes:

- `HARD_STEAL = -200` (defense wins decisively) - Calibrated using offense team's `discipline`
- `SOFT_STEAL = -100` (defense wins marginally) - Calibrated using offense team's `discipline`
- `HARD_FOUL = 200` (offense wins decisively, defender reaches) - Calibrated using defense team's `fight`
- `SOFT_FOUL = 100` (offense wins marginally, defender reaches) - Calibrated using defense team's `fight`
- `SOFT_PROB = 0.16` (probability for soft bands, calibrated so equal-strength d6 vs d6 yields 30% in soft+hard bands)

**Steal Resolution Function:**
```python
def resolve_steal_attempt(offense_value: int, defense_value: int,
                          soft_steal: int, hard_steal: int,
                          soft_foul: int, hard_foul: int) -> str:
    """
    Resolve outcome of a steal attempt.
    
    Args:
        offense_value: Ball handler's protection value (bh_score)
        defense_value: Defender's steal attempt value (pressure)
        soft_steal: Soft steal threshold (default: -100)
        hard_steal: Hard steal threshold (default: -200)
        soft_foul: Soft foul threshold (default: 100)
        hard_foul: Hard foul threshold (default: 200)
    
    Returns:
        One of:
        - "STEAL" - Steal successful, possession changes
        - "D_FOUL" - Defensive foul on steal attempt, offense retains possession
        - "NO_EVENT" - No event, play continues normally
    """
    delta = offense_value - defense_value  # negative => defense won the contest
    
    # 1) Steal outcomes (defense wins)
    if delta <= hard_steal:
        return "STEAL"
    if delta <= soft_steal:
        # Soft steal band: partial probability to calibrate to baseline rates
        if random.random() < SOFT_PROB:
            return "STEAL"
    
    # 2) Defensive foul outcomes (offense wins / defender reaches)
    if delta >= hard_foul:
        return "D_FOUL"
    if delta >= soft_foul:
        if random.random() < SOFT_PROB:
            return "D_FOUL"
    
    # 3) Otherwise nothing happens; possession continues
    return "NO_EVENT"
```

**Return Value Nomenclature:**
- `"STEAL"` - Steal successful, results in possession change and fast break opportunity
- `"D_FOUL"` - Defensive foul on steal attempt, offense retains possession (may result in free throws if in bonus)
- `"NO_EVENT"` - No event occurs, play continues normally to shot attempt or other outcome

**Threshold Calibration:**
Universal thresholds are calibrated per-turn based on team attributes:
- **Steal thresholds**: Adjusted using offense team's `discipline` attribute
  - Higher `discipline` (lower turnover risk) → thresholds adjusted to favor offense (less likely to steal)
  - Lower `discipline` (higher turnover risk) → thresholds adjusted to favor defense (more likely to steal)
- **Foul thresholds (on steal attempts)**: Adjusted using defense team's `fight` attribute
  - Higher `fight` → thresholds adjusted to reduce foul likelihood
  - Lower `fight` → thresholds adjusted to increase foul likelihood
- Calibration formulas are applied in Step 2 of the resolution flow (see Calibration Formulas above)

### Example: Complete HCO Resolution Calculation

**Initial State:**
- Base values: Shot=70, O_Foul=7, D_Foul=10, TO=7, Steal=6
- Offense: `offensive_efficiency=8`, `foul_modifier=-6`, `turnover_modifier=10`
- Defense: `defensive_efficiency=1`, `foul_modifier=-7`
- Defense Aggression: `aggressive`

**After Step 1 (Team Attributes):**
- Shot Attempt: `70 + 8 - 1 = 77`
- Offensive Foul: `7 - (-6) = 13`
- Defensive Foul: `10 - (-7) = 17`
- Dead Ball Turnover: `7 - 5 = 2` (10 * 0.5 = 5)
- Steal: `6 - 5 = 1`

**After Step 2 (Aggression Setting):**
- Shot Attempt: `77` (unchanged)
- Offensive Foul: `13` (unchanged)
- Defensive Foul: `17 + 4 = 21`
- Dead Ball Turnover: `2 + 2 = 4`
- Steal: `1 + 2 = 3`

**After Step 3 (Minimum Values):**
- All values are ≥ 2, no changes needed

**Final Resolution Values:**
- Shot Attempt: 77
- Offensive Foul: 13
- Defensive Foul: 21
- Dead Ball Turnover: 4
- Steal: 3

### Key Implementation Notes

1. **Team Attribute Persistence**: Team attributes are set at game start and don't change during turns (future: may change during timeouts)
2. **Attribute Inversion**: When possession changes, offense/defense roles swap, so attribute applications are inverted
3. **Turnover Modifier Split**: Always 50/50 between Dead Ball Turnover and Steal, with odd remainder going to Dead Ball Turnover
4. **Minimum Value Enforcement**: Applied after all modifications to ensure no value goes below 2
5. **Future Score Generation**: Player attributes and actions will generate a score that maps to these resolution values

### Status

✅ **HCO Resolution**: Implementation complete (January 2025)
- Modular functions for fouls, steals, and turnovers
- Randomized execution order for event checks
- Respects resolution system determination (prevents random conversion of dead ball turnovers)
- Fast Break, HCT, and FCP resolution logic will be designed after HCO is tested

### Key Files

- `BackEnd/engine/phase_resolution.py` - Current HCO resolution logic (to be replaced)
- `BackEnd/models/turn_manager.py` - Current event type determination (to be replaced)
- `BackEnd/models/team_manager.py` - Team attribute initialization

