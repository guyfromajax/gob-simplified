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
- **Possession Flip Locations:**
  - **SIP Transitions:** `game_manager.py` `simulate_macro_turn()` flips BEFORE `setup_side_inbound()` (line ~300)
    - Handles offensive fouls and dead ball turnovers
    - Checks `result.get("possession_flips")` and flips if True
    - Clears flag after flipping to prevent frontend double flip
    - **Important:** The HCO turn result has `offense_team_id` set to the team that was on offense DURING that turn (before flip)
    - The SIP turn result has `offense_team_id` set to the NEW offense team (after flip)
  - **Other Transitions:** Various handlers flip possession as needed (OREB, made shots, etc.)
- After turn completes, calls `game.switch_possession()` if `possession_flips=True` (location depends on transition type)
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

### Per-Step Ball Handler Tracking for Defender Positioning ✅ **NEW (March 2025)**

- **FCP**: Defenders still match their assigned offensive player, but at each step, if their assignment is the current ball handler, they switch to `guard_ball`; ball handler is determined **per timestamp** (not just step 0).
- **HCT**: Per-step ball handler detection drives trap logic:
  - Defensive PG tracks the **current** ball handler each step (not the initial handler).
  - Other defenders track their assignments with tighter offsets and respect half-court boundaries.
- **Why it matters**: Prevents PG/SF “swap” behavior when the ball changes hands mid-sequence; defenders always respond to the live ball handler.

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

### FCP/HCT Stat Tracking ✅ **NEW** (January 2025)

**Player-Level Stats:**

**Offensive Stats (FCP_A, FCP_S, FCP_F / HCT_A, HCT_S, HCT_F):**
- **FCP_A / HCT_A**: Attempts - Incremented for ball handler (and shooter if shot was taken)
- **FCP_S / HCT_S**: Success - Incremented when:
  - `MAKE` (made shot)
  - `HCO` (press/trap break - successfully broke through)
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)
- **FCP_F / HCT_F**: Failure - Incremented when:
  - `MISS` (missed shot)
  - `TURNOVER`, `STEAL`, `DEAD BALL`
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)

**Defensive Stats (FCP_A_D, FCP_S_D, FCP_F_D / HCT_A_D, HCT_S_D, HCT_F_D):**
- **FCP_A_D / HCT_A_D**: Defensive Attempts - Incremented for defender
- **FCP_S_D / HCT_S_D**: Defensive Success - Incremented when:
  - `MISS` (missed shot)
  - `TURNOVER`, `STEAL`, `DEAD BALL`
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)
- **FCP_F_D / HCT_F_D**: Defensive Failure - Incremented when:
  - `MAKE` (made shot)
  - `HCO` (press/trap break - defense failed to stop)
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)

**Stat Initialization:**
- All FCP/HCT stats initialized to `0` at game start
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_full_court_press_logic()` and `resolve_half_court_trap_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)
- Stats are recorded via `_record_fcp_stats()` and `_record_hct_stats()` helper functions

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["FCP"]["used"]`**: Incremented each time defense applies Full Court Press
- **`def_scouting["defense"]["FCP"]["success"]`**: Incremented when FCP result_type is:
  - `MISS` (missed shot during press break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)
- **`def_scouting["defense"]["HCT"]["used"]`**: Incremented each time defense applies Half Court Trap
- **`def_scouting["defense"]["HCT"]["success"]`**: Incremented when HCT result_type is:
  - `MISS` (missed shot during trap break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Note:** Team-level offensive success/failure can be derived from defensive tracking:
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Special Handling:**
- **HCO (Press/Trap Break)**: Counts as offensive success at player level (FCP_S/HCT_S) and defensive failure at player level (FCP_F_D/HCT_F_D), but is NOT tracked as defensive success at team level (correct - defense failed to stop the break)
- **MAKE**: Counts as offensive success at player level but NOT as defensive success at team level (correct - offense scored)
- **D_FOUL**: Counts as defensive failure at player level but NOT as defensive success at team level (correct - defense fouled)

### Skeleton System ✅ **UPDATED** (January 2025)

**Skeleton Sources:**
- FCP skeletons: MongoDB `fcp_skeletons` collection
- HCT skeletons: MongoDB `hct_skeletons` collection
- **Variant Structure**: Two variants per skeleton type:
  - `"base"` - Standard press/trap break skeleton (used for all non-shot results: O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)
  - `"shot"` - Shot attempt skeleton (used for SHOT results)
- **Critical**: FCP/HCT "base" variants have step 0 with press/trap break positions (unlike HCO skeletons which don't have step 0)
- **Skeleton Selection**: `get_fcp_skeleton(result_type, game)` or `get_hct_skeleton(result_type, game)` maps result types to variants
  - All non-shot result types map to `"base"` variant
  - SHOT results map to `"shot"` variant
- **Stopper System Integration**: FCP/HCT non-shot results use "base" variant skeletons with stopper system applied (truncation + stopper step)

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

## Free Throw System ✅ **COMPLETE** (January 2025)

### Overview

The Free Throw System handles free throw shot attempts and outcomes. Free throws are awarded for shooting fouls, bonus situations (5+ team fouls), and double bonus situations (10+ team fouls).

**Location:** `BackEnd/engine/phase_resolution.py` - `resolve_free_throw_logic()`  
**Status:** ✅ Fully implemented

### Free Throw Calculation

**Formula:**
```python
ft_shot_score = (attrs["FT"] * 0.7) + (attrs["CH"] * 0.2) + attrs["MO"]
result = random.randint(1, 100)
makes_shot = result < ft_shot_score
```

**Components:**
1. **Player Attributes:**
   - `FT` (Free Throw) - 70% weight
   - `CH` (Clutch) - 20% weight
   - `MO` (Momentum) - Full value added (not weighted)

2. **Random Roll:** `random.randint(1, 100)` (1-100 range)

3. **Success Comparison:**
   - Compares `result` (random 1-100) to `ft_shot_score` (calculated from attributes)
   - If `result < ft_shot_score` → **MAKE**
   - If `result >= ft_shot_score` → **MISS**

**Example:**
- Player with `FT = 80`, `CH = 70`, `MO = 5`
- `ft_shot_score = (80 * 0.7) + (70 * 0.2) + 5 = 56 + 14 + 5 = 75`
- Random roll: `60` (1-100)
- Result: `60 < 75` → **MAKE**

### When Free Throws Are Awarded

**Shooting Fouls:**
- 2 free throws for 2-point shot attempts
- 3 free throws for 3-point shot attempts
- Always awarded regardless of team foul count

**Bonus Situations (Non-Shooting Fouls):**
- **5-9 team fouls:** 1-and-1 free throws (must make first to unlock second)
- **10+ team fouls:** 2 free throws (double bonus)

**1-and-1 Logic:**
- First free throw must be made to unlock the second
- If first is missed, possession changes (defensive rebound)

### Free Throw Outcomes

**Made Free Throw:**
- Awards 1 point
- Decrements `free_throws_remaining`
- If last free throw, determines next defensive setup (pressure type)
- Next play type: `BASELINE_INBOUND` (after made shot)

**Missed Free Throw:**
- No points awarded
- Rebound logic determines offensive or defensive rebound
- If defensive rebound: Next play type determined by `offensive_state`
- If offensive rebound: OREB turn created

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py` - `resolve_free_throw_logic()` (lines 1352-1520)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/FreeThrowAnimationSystem.js` - Free throw animation
- `FrontEnd/static/js/phaser/animation/freeThrow.js` - Free throw sequence handler

---

## Shooting Foul System ✅ **COMPLETE** (January 2025)

### Overview

The Shooting Foul System determines if a defensive foul occurs during a shot attempt and applies calibration logic to account for the disruptive impact of fouls on shot outcomes.

**Location:** `BackEnd/models/shot_manager.py` - `check_defensive_foul_on_shot()`  
**Status:** ✅ Fully implemented

### Universal Constants

```python
HARD_SHOOTING_FOUL_THRESHOLD = 50
SOFT_SHOOTING_FOUL_THRESHOLD = 110
SOFT_PROB = 0.16
```

### Foul Detection Logic

**Step 1: Calculate Thresholds**

Both thresholds are adjusted by the defense team's `foul_modifier` attribute:

```python
hard_threshold = HARD_SHOOTING_FOUL_THRESHOLD + foul_modifier
soft_threshold = SOFT_SHOOTING_FOUL_THRESHOLD + foul_modifier
```

**Note:** `foul_modifier` ranges from -10 to 10, so:
- **Hard threshold range:** 40 to 60
- **Soft threshold range:** 100 to 120

**Step 2: Determine Foul Occurrence**

The system uses `defense_score` (calculated from defender attributes) to determine if a foul occurs:

```python
if defense_score < hard_threshold:
    d_foul = True  # Hard foul: always occurs
elif defense_score < soft_threshold:
    d_foul = random.random() < SOFT_PROB  # Soft foul: 16% chance
else:
    d_foul = False  # No foul
```

**Logic:**
- **Hard Foul:** If `defense_score` is below the hard threshold, a foul always occurs (poor defensive performance)
- **Soft Foul:** If `defense_score` is between hard and soft thresholds, there's a 16% chance of a foul (marginal defensive performance)
- **No Foul:** If `defense_score` is above the soft threshold, no foul occurs (good defensive performance)

### Defense Score Calculation

`defense_score` is calculated based on shot type and defender attributes:

**Paint Shots (Inside):**
```python
defense_score = (
    defense_attrs["ID"] * 0.6 +
    defense_attrs["ST"] * 0.2 +
    defense_attrs["IQ"] * 0.1 +
    defense_attrs["CH"] * 0.1
) * random.randint(1, 6)
```

**Three-Point Shots:**
```python
defense_score = (
    defense_attrs["OD"] * 0.8 +
    defense_attrs["IQ"] * 0.1 +
    defense_attrs["CH"] * 0.1
) * random.randint(1, 6)
```

**Mid-Range Shots:**
```python
defense_score = (
    defense_attrs["OD"] * 0.3 +
    defense_attrs["ID"] * 0.3 +
    defense_attrs["AG"] * 0.1 +
    defense_attrs["ST"] * 0.1 +
    defense_attrs["IQ"] * 0.1 +
    defense_attrs["CH"] * 0.1
) * random.randint(1, 6)
```

**Range:** `defense_score` can range from ~0 (poor defender) to ~600+ (excellent defender with high attributes × 6).

### Foul Calibration (Shot Outcome Adjustment)

**Purpose:** Fouls are significant outliers that can disrupt shot attempts, forcing missed shots even when the standard shot calculation would indicate a make.

**Process:**

After the standard shot result is calculated (`made = shot_score >= shot_threshold`), if a shooting foul is detected, an additional calibration check is performed:

```python
from BackEnd.constants import THREE_POINTER_FOUL_MISS_CHANCE, TWO_POINTER_FOUL_MISS_CHANCE

if d_foul:
    foul_calibration_roll = random.random()
    if is_three:
        # 3-pointers: 40% chance foul forces a miss
        if foul_calibration_roll < THREE_POINTER_FOUL_MISS_CHANCE:  # 0.4
            made = False
        # else: standard shot result holds (could be make or miss)
    else:
        # 2-pointers: 20% chance foul forces a miss
        if foul_calibration_roll < TWO_POINTER_FOUL_MISS_CHANCE:  # 0.2
            made = False
        # else: standard shot result holds (could be make or miss)
```

**Calibration Rates:**
- **3-Pointers:** 40% chance the foul forces a miss (fouls are more disruptive to long-range shots)
- **2-Pointers:** 20% chance the foul forces a miss (fouls are less disruptive to closer shots)

**Note:** If the calibration roll doesn't force a miss, the standard shot result (make or miss) is preserved. This allows for AND-1 situations where the shot is made despite the foul.

### Integration with Shot Resolution

**Flow:**
1. `defense_score` is calculated during `calculate_shot_score()`
2. `check_defensive_foul_on_shot()` is called to determine if a foul occurred
3. Standard shot result is calculated: `made = shot_score >= shot_threshold`
4. **If foul detected:** Foul calibration check is performed to potentially force a miss
5. Shot outcome is finalized (make or miss)
6. If foul occurred:
   - **Made shot + foul:** AND-1 situation → 1 free throw
   - **Missed shot + foul:** Shooting foul → 2 or 3 free throws (based on shot type)

### Shot Location Detection (Three-Point vs Two-Point)

**Purpose:** Accurately determine if a shot is a three-pointer or two-pointer based on the shooter's location at the moment of the shot attempt.

**Implementation:**

The system uses `_get_shooter_position_and_spot()` to extract the shooter's location from the skeleton steps:

```python
def _get_shooter_position_and_spot(self, shooter, roles):
    # Get shooter's position from lineup
    shooter_pos = get_position_from_lineup(shooter)
    
    # Find shooter's spot from the FINAL step (where they actually shoot)
    steps = roles.get("steps", [])
    if steps:
        final_step = steps[-1]  # ✅ FIX: Only check final step first
        pos_actions = final_step.get("pos_actions", {})
        shooter_action = pos_actions.get(shooter_pos)
        if shooter_action and shooter_action.get("action") == "shoot":
            location_key = shooter_action.get("location") or shooter_action.get("spot", "")
            spot = location_key.lower() if location_key else ""
            return (shooter_pos, spot)
    
    # Fallback: search all steps in reverse (backwards compatibility)
    # ...
```

**Key Design Decision:**

The function **prioritizes the final step** (last step in the skeleton) to ensure it captures the actual shot location, not an earlier step that might have a different location. This is critical for:

1. **Motion Plays:** Where the shooter's location may change throughout the motion sequence
2. **Attack Shots:** Where the shooter drives to a new location before shooting
   - **Motion Offense Attack Shots:** Uses two-step process (drive step + shoot step) to ensure proper animation and accurate shot location detection
   - **Step 1:** `action: "drive"` to destination lane spot
   - **Step 2:** `action: "shoot"` at destination lane spot
   - This two-step approach fixes animation bugs where shots appeared from wrong locations
3. **Pass-and-Shoot Sequences:** Where the shooter receives the ball and then shoots

**Why This Matters:**

- **Free Throw Count:** 2-point shots award 2 free throws, 3-point shots award 3 free throws
- **Foul Calibration:** 3-pointers have a 40% chance the foul forces a miss, 2-pointers have a 20% chance
- **Defense Score Calculation:** Different defense score formulas are used for 3-pointers vs 2-pointers

**Location Matching:**

The detected location string (lowercased) is compared against `THREE_POINT_SPOTS` constant:

```python
THREE_POINT_SPOTS = {
    "key", "deep key",
    "upper wing", "deep upper wing",
    "lower wing", "deep lower wing",
    "upper midwing", "lower midwing",
    "lower midcorner", "upper midcorner",
    "upper corner", "lower corner",
    "deep upper baseline", "deep lower baseline"
}
```

If the location matches any spot in this set, the shot is classified as a three-pointer.

### Key Files

**Backend:**
- `BackEnd/models/shot_manager.py`
  - `check_defensive_foul_on_shot()` (lines 1148-1175) - Foul detection logic
  - `calculate_shot_score()` (lines 994-1109) - Defense score calculation and foul check
  - `resolve_shot()` (lines 243-1003) - Shot resolution with foul calibration
  - `_get_shooter_position_and_spot()` (lines 125-188) - Shot location detection (prioritizes final step)
  - `is_three_point_shot()` (lines 164-180) - Three-point classification

**Constants:**
- `BackEnd/constants/__init__.py` - Universal constants (`HARD_SHOOTING_FOUL_THRESHOLD`, `SOFT_SHOOTING_FOUL_THRESHOLD`, `SOFT_PROB`, `THREE_POINT_SPOTS`)

---

## HCO System ✅ **COMPLETE** (January 2025)

### Overview

The **Half Court Offense (HCO)** system handles standard half-court offensive possessions. HCO turns use skeleton-based animations to simulate offensive plays, including ball movement, player cuts, screens, and shot attempts.

**Key Functions:**
- `resolve_hco_logic()` - Handles HCO outcomes in `BackEnd/engine/phase_resolution.py`
- `skeleton_to_animations()` - Converts skeleton steps to animation data in `BackEnd/models/animator.py`
- `ShotAnimationSystem` - Handles HCO shot attempt animations in frontend

### When HCO Activates

**Trigger Conditions:**
- Default offensive state after opening tip, side inbound passes, and defensive rebounds
- Set via `offensive_state = "HCO"` in `game_state`
- Can transition from: Opening Tip, Side Inbound Pass, Defensive Rebound, Press/Trap Break, Fast Break (defensive stop)

**State Flow:**
1. Turn starts with `offensive_state = "HCO"`
2. Offensive playcall selected based on team strategy
3. Skeleton retrieved from play database
4. Skeleton converted to animation data
5. Outcome determined (MAKE, MISS, FOUL, TURNOVER)

### Possible Outcomes

HCO turns can result in:

1. **Made Shot (MAKE)**
   - Points scored
   - Routes to: BASELINE_INBOUND (with optional FCP/HCT pressure)
   - Shooter: Determined from skeleton (intended shooter or hot read)

2. **Missed Shot (MISS)**
   - Shot attempt failed
   - Routes to: OREB (offensive rebound) or DREB (defensive rebound)
   - Rebounder: Determined by rebound calculation

3. **Shooting Foul (D_FOUL)**
   - Defensive foul during shot attempt
   - Routes to: FREE_THROW
   - Foul player: Defender guarding shooter

4. **Non-Shooting Foul (D_FOUL)**
   - Defensive foul before shot attempt
   - **In Bonus**: Routes to FREE_THROW
   - **Not in Bonus**: Routes to Side Inbound Pass → HCO

5. **Offensive Foul (O_FOUL)**
   - Offensive foul (e.g., charge, illegal screen)
   - Possession change
   - Routes to: Side Inbound Pass → HCO

6. **Turnover (TURNOVER)**
   - Ball lost (travel, out of bounds, etc.)
   - Possession change
   - Routes to: Side Inbound Pass → HCO or FAST_BREAK

### Skeleton Animation System

**Skeleton Sources:**
- HCO skeletons: Stored in MongoDB `plays` collection
- Skeleton variants: Different skeletons for different play types (INSIDE, OUTSIDE, MOTION, etc.)
- Play selection: Based on offensive playcall from team strategy

**Skeleton Structure:**
- Each skeleton contains `steps` array
- Each step has `pos_actions` dict mapping positions (PG, SG, SF, PF, C) to actions
- Actions include: `"handle_ball"`, `"receive"`, `"pass"`, `"shoot"`, `"screen"`, `"cut"`, `"drift"`, etc.
- Each action includes `location` (court position) and optional `opp` field (opposite side of court)

**Animation Generation:**
- Skeletons converted to animations via `animator.skeleton_to_animations()` in `BackEnd/models/animator.py`
- Location strings converted to grid coordinates using `HCO_STRING_SPOTS`
- For screen actions, uses `OFFSET_SPOTS` instead to avoid visual overlap
- Animations include player movements, ball movements, and defender positioning
- Frontend uses animation data to render turn animations

### DREB → HCO Transition and Outlet Pass Execution ✅ **NEW** (January 2025)

**Design Pattern:**
When a defensive rebound (DREB) transitions to an HCO turn, the outlet pass executes in the **DREB turn** (via `runDefensiveReboundSetup`), not in the HCO turn itself. This differs from Fast Break outlet passes, which execute in the Fast Break turn.

**Why This Design:**
- **HCO is skeleton-based**: The HCO turn simply plays the skeleton animation. The outlet pass is a **transition step** that happens before the HCO turn begins, positioning players and transferring the ball from rebounder to outlet receiver.
- **Fast Break is self-contained**: Fast Break is a complete sequence (outlet pass → resolution), so it owns its setup and executes the outlet pass as Phase 1 of the Fast Break turn.
- **Separation of concerns**: HCO outlet pass is a transition animation, while HCO turn is the skeleton execution. Keeping them separate maintains clarity and avoids complicating the skeleton-based turn logic.

**Implementation:**
- **Location:** `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runDefensiveReboundSetup()` function
- **Trigger:** Called from `handleOrebTurn()` when `rebound_type === "DREB"` and `next_play_type !== "FAST_BREAK"`
- **Execution:** Outlet pass happens before HCO turn begins, ensuring players are positioned and ball is transferred to the outlet receiver
- **Note:** These two outlet steps are mutually exclusive - never run together. Fast Break outlet is handled separately in `fastBreak.js` (`animateOutletPhase`).

**Key Files:**
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runDefensiveReboundSetup()` (HCO outlet pass)
- `FrontEnd/static/js/phaser/animation/fastBreak.js` - `animateOutletPhase()` (Fast Break outlet pass)
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - `handleOrebTurn()` (calls outlet setup for HCO)

### Screener Offset Coordinate System ✅ **NEW** (January 2025)

**Purpose:**
Screeners automatically animate to offset positions to prevent visual overlap when multiple players are at the same location.

**Implementation:**
- **Location:** `BackEnd/models/animator.py` - `skeleton_to_animations()` method (lines 1087-1094)
- **Detection:** Checks if `action == "screen"` before converting location to coordinates
- **Coordinate Selection:**
  - If `action == "screen"`: Uses `OFFSET_SPOTS[location]` if available
  - Falls back to `HCO_STRING_SPOTS[location]` if offset not defined for that location
  - Otherwise: Uses `HCO_STRING_SPOTS[location]` for all non-screen actions

**Offset Coordinate Mapping:**
- `OFFSET_SPOTS` defines slightly shifted positions (typically ±3 units in x/y) from standard positions
- Offset patterns vary by location type:
  - Center spots: x + 3, y same
  - Upper wing/apex: x + 3, y - 3
  - Lower wing/apex: x + 3, y + 3
  - Upper corner/baseline: x same, y - 3
  - Lower corner/baseline: x same, y + 3
  - Upper post: x - 3, y + 3
  - Lower post: x + 3, y - 3

**Away Team Handling:**
- Offset coordinates are determined first (using `OFFSET_SPOTS`)
- Then away team mirroring is applied (x: 100 - x)
- This ensures screeners on away team animate to correctly mirrored offset positions

**Benefits:**
- Prevents visual overlap when screeners and other players share locations
- Automatic detection (no manual flags needed in play builder)
- Consistent with play builder offset system
- Works for all screen actions across all HCO skeletons

**Key Files:**
- `BackEnd/models/animator.py` - Offset coordinate logic (lines 1087-1094)
- `BackEnd/constants/__init__.py` - `OFFSET_SPOTS` definition (lines 191-231)
- `FrontEnd/static/play-builder.html` - Play builder offset visualization

### Energy Decay System ✅ **SS&S** (January 2025)

**Energy Decay Application:**
- Energy decay is applied to all players (both offensive and defensive) for **every HCO turn**
- Decay happens **before** event determination, ensuring it runs regardless of turn outcome (SHOT, foul, turnover, steal)
- Uses `apply_energy_decay()` function in `phase_resolution.py` (extracted from `determine_event_type()`)

**Decay Logic:**
- Each player's energy (NG) decays based on their ND (Nerve/Defense) attribute
- Higher ND = less decay (better stamina)
- Decay amount determined by `player.get_fatigue_decay_amount()`:
  - ND ≥ 89: 0-0.01 (minimal decay)
  - ND ≥ 79: 0-0.01 (low decay)
  - ND ≥ 69: 0-0.02 (moderate decay)
  - ND < 69: 0-0.03 (higher decay)
- Energy is clamped to minimum 0.1 (10%) and maximum 1.0 (100%)

**Why Extracted:**
- Previously, energy decay was inside `determine_event_type()` in `turn_manager.py`
- With the stopper system, `determine_event_type()` is bypassed for SHOT results
- Extracting energy decay ensures it always runs, maintaining SS&S consistency

**Bench Player Energy Recharge:**
- Players not in the active lineup recharge energy during each HCO turn
- Per turn recharge probabilities:
  - 20% chance: no recharge (0)
  - 70% chance: recharge +0.01 energy
  - 10% chance: recharge +0.02 energy
- Implemented in `apply_bench_energy_recharge()` function
- Called alongside energy decay for HCO turns
- Ensures bench players gradually regain energy when not playing

**Energy Display:**
- Frontend displays energy via `turn.player_energy` (set in `turn_manager.py` line 708-717)
- Energy levels included in `/api/game/{gameId}` response for lineup screen
- Color-coded display: Green (>89%), Yellow (80-89%), Orange (70-79%), Red (<70%)

**Key Files:**
- `BackEnd/engine/phase_resolution.py` - `apply_energy_decay()` function (lines 59-76) and `apply_bench_energy_recharge()` function (lines 79-100)
- `BackEnd/models/player.py` - `decay_energy()`, `recharge_energy()`, and `get_fatigue_decay_amount()` methods
- `BackEnd/models/turn_manager.py` - `player_energy` population (lines 708-717)

### Stat Tracking

**Player-Level Stats:**
- **FGA, FGM**: Shot attempts and makes
- **3PTM, PTS**: Three-pointers and points scored
- **AST**: Assists (on made shots)
- **TO**: Turnovers
- **F**: Fouls (offensive or defensive)
- **SCR_A, SCR_S**: Screen attempts and successes

**Team-Level Stats:**
- **Offensive efficiency**: Points per possession
- **Turnover rate**: Turnovers per possession
- **Shot selection**: Distribution of shot types

**Stat Tracking Location:**
- `BackEnd/models/shot_manager.py` - Shot resolution and stat recording
- `BackEnd/engine/phase_resolution.py` - Screen stat tracking
- `BackEnd/models/turn_manager.py` - Turnover and foul stat recording

### Key Files

- `BackEnd/engine/phase_resolution.py`
  - `resolve_hco_logic()` - HCO outcome resolution
  - `generate_logic()` - Play selection and skeleton retrieval
- `BackEnd/models/animator.py`
  - `skeleton_to_animations()` - Skeleton to animation conversion
  - Screener offset coordinate logic
- `BackEnd/models/shot_manager.py`
  - `resolve_shot()` - Shot attempt resolution
  - `is_three_point_shot()` - Three-point detection
  - `is_paint_shot()` - Paint shot detection
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
  - `animatePlayerMovement()` - HCO shot attempt animations
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
  - `playTurnAnimation()` - HCO skeleton animation orchestration

---

## Stopper System ✅ **COMPLETE** (January 2025)

### Overview

The **Stopper System** is an SS&S (Single Source & Scalable) system that interrupts HCO skeleton animations at strategic points to execute non-shot outcomes (fouls, turnovers, steals). Instead of using result-specific skeletons (like FCP/HCT), the stopper system uses standard HCO playcall skeletons and truncates them at a determined "stopper step," then appends a final stopper action step.

**Key Design Principles:**
- **SS&S Architecture**: Uses shared helper functions (`get_ball_handler_from_skeleton()`, `select_foul_player()`, `resolve_non_shooting_foul()`, `resolve_turnover_logic()`) for consistency across turn types
- **Skeleton Reuse**: Uses existing HCO skeleton variants (successful, mid_play_change, contested, broken) instead of creating result-specific skeletons
- **Dynamic Interruption**: Determines stop step based on result type (random for fouls, strategic for turnovers/steals)
- **Deep Copy Protection**: Always creates a deep copy of the skeleton before modification to prevent cache mutation

### When Stopper System Activates

The stopper system activates in **HCO turns** when `generate_logic()` determines a non-SHOT result:

**Possible Results:**
- `SHOT` - Normal flow, proceeds to shot resolution (no stopper)
- `O_FOUL` - Offensive foul (stopper activates)
- `D_FOUL` - Defensive foul (stopper activates)
- `DEAD_BALL_TURNOVER` - Dead ball turnover (stopper activates)
- `STEAL` - Steal (stopper activates)

**Result Determination:**
- `generate_logic()` in `phase_resolution.py` (line 1469-1474) uses weighted random choice:
  - `SHOT`: 60% weight (default successful outcome)
  - `O_FOUL`: 10% weight
  - `D_FOUL`: 10% weight
  - `DEAD_BALL_TURNOVER`: 10% weight
  - `STEAL`: 10% weight

### Stopper Step Selection

The system determines which step to stop at based on result type:

**Fouls (O_FOUL, D_FOUL):**
- Random step between step 1 and second-to-last step
- Example: For a 7-step skeleton (steps 0-6), chooses randomly from steps 1-5
- Rationale: Fouls can organically happen at any point during the play

**Turnovers/Steals (DEAD_BALL_TURNOVER, STEAL):**
- Strategic step: Currently uses middle step (`len(steps) // 2`)
- TODO: Enhance with player attribute analysis (ball handler's BH, defender's ST, IQ) and positioning
- Rationale: Turnovers are more likely during high-pressure situations (passes, drives)

### Skeleton Truncation Process

1. **Deep Copy Creation** (line 1704):
   - Immediately creates a deep copy of the skeleton after retrieval
   - Prevents in-place modification from mutating the cached skeleton
   - Critical for preventing truncated skeletons in future turns

2. **Stop Step Determination** (lines 1716-1727):
   - Calculates `stop_step_index` based on result type
   - Truncates skeleton to `steps[:stop_step_index + 1]` (includes the stop step)

3. **Ball Handler Identification** (lines 1732-1755):
   - Finds ball handler at the stop step (checks for "handle_ball", "receive", "pass" actions)
   - Falls back to previous step if not found in stop step
   - Determines ball handler position and location for stopper step

4. **Stopper Step Creation** (lines 1757-1781):
   - Creates final stopper step with timestamp = stop_step.timestamp + 300ms
   - Maps result to stopper action: `O_FOUL` → "o_foul", `D_FOUL` → "d_foul", `DEAD_BALL_TURNOVER` → "dead_ball_turnover", `STEAL` → "steal"
   - Adds ball handler to stopper step's `pos_actions` (ball remains with them until stopper)
   - Adds stopper event to `events` array

5. **Skeleton Assembly** (line 1790):
   - Replaces `skeleton["steps"]` with `truncated_steps + [stopper_step]`
   - Frontend animates this truncated skeleton normally (no special handling needed)

### Frontend Animation Handling ✅ **NEW** (January 2025)

**Step 0 Positioning Requirement:**
- Truncated skeletons still include step 0 (the truncation preserves step 0: `truncated_steps = steps[:stop_step_index + 1]`)
- **Critical**: Frontend must position players at step 0 positions **before** starting the step loop
- Without step 0 positioning, step 1 (first pass) can fire before players reach their step 0 positions, causing slow/fast first pass animations

**Implementation:**
- **Shot Attempts (Full Skeletons)**: Route through `ShotAnimationSystem.executeCompleteShotSequence()` which calls `runSetupTween()` at line 162 before starting the step loop
- **Non-Shooting Results (Truncated Skeletons)**: Route through `playTurnAnimation()` which must also call `runSetupTween()` before the step loop starts
- **Location**: `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `runSetupTween()` function (lines 345-390)
- **Execution**: `runSetupTween()` moves all players to their step 0 positions using distance-based duration, then the step loop begins at step 1

**Exception: BIP → FCP/HCT Transitions** ✅ **NEW** (January 2025)
- **Skip `runSetupTween()`** when coming from BASELINE_INBOUND (`fromInbound === true`) AND the turn is FCP/HCT (`isFCPHCT === true`)
- **Reason**: BIP already positions players at skeleton step 0 positions (from `offense_setup_positions`), so `runSetupTween()` is redundant
- **Prevents Timing Conflicts**: The inbound pass animation may still be completing when HCT/FCP starts, and redundant positioning can cause conflicts
- **Location**: `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` function (lines 2211-2217)
- **Code**: `if (!fromInbound || !isFCPHCT) { await runSetupTween({...}); }`

**Why This Matters:**
- Truncated skeletons (o foul, d foul, dead ball turnover, steal) use `playTurnAnimation()` which was missing the `runSetupTween()` call
- Shot attempts use `ShotAnimationSystem` which correctly calls `runSetupTween()` before animation
- The fix ensures both paths position players at step 0 before step 1 starts, preventing animation hitches
- **Exception handling** prevents redundant positioning when BIP already handled it, ensuring smooth BIP → FCP/HCT transitions

**Key Files:**
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` and `runSetupTween()` functions
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` - `executeCompleteShotSequence()` and `runSetupTween()` functions

### Player Role Population

The stopper system uses SS&S helper functions to populate player roles, ensuring consistency with FCP/HCT:

**Ball Handler Determination** (line 1909):
- Uses `get_ball_handler_from_skeleton(skeleton, off_lineup)` - same as FCP/HCT
- Determines ball handler from skeleton steps (from stopper step or last step)

**Defender Determination** (lines 1970-2095):
- **For Non-Shot Outcomes (Steals, Turnovers, Fouls)**: Overrides defender assignment to be based on ball handler's position, not shooter's position
  - `assign_roles()` assigns defender based on shooter position (for shot attempts)
  - For steals/turnovers/fouls, we need whoever is guarding the ball handler at the time of the steal
  - **✅ FIX (January 2025)**: Uses `get_ball_handler_from_skeleton(skeleton, off_lineup, step_index=stop_step_index)` to get the ball handler at the **stop step** where the steal/foul/turnover occurs
    - Critical for Motion plays where the ball handler changes throughout the motion
    - The stop step index is stored in `game_state["steal_stop_step_index"]` by `apply_stopper_system_to_skeleton()`
    - Falls back to `roles.get("ball_handler")` if stop step index is not available (backwards compatibility)
  - **Man-to-Man Defense**: Defender matches ball handler position (e.g., if ball handler is SF, defender is defensive SF)
  - **Zone Defense**: Uses actual zone assignment logic (`assign_all_zone_defenders()`) to determine which defender(s) are actually guarding the ball handler
    - Checks `defender_to_offensive_player` mapping to find which defender(s) are assigned to guard the ball handler
    - **Overlapping Zones**: If ball handler is in overlapping zones:
      - If only one defender is guarding the ball handler → uses that defender
      - If two or more defenders are guarding the ball handler → randomly picks one
      - This respects the zone overlap resolution logic (if one defender is assigned to guard a different player in their zone, they won't be considered)
    - Falls back to position match if no defender is assigned (shouldn't happen, but safety fallback)
- **Stopper System Protection**: The stopper system preserves the defender if already set by override logic (prevents overwriting the correct defender)
  - Checks if `roles["defender"]` is already set before recalculating
  - Only recalculates if defender wasn't set by override logic
- **Implementation**: Located in `resolve_half_court_offense_logic()` after `assign_roles()` is called

**Foul Player Selection** (lines 1918-1921):
- Uses `select_foul_player(foul_team_type, ball_handler, off_lineup, def_lineup)` - same as FCP/HCT
- Probabilistic selection: 60% chance it's the ball handler, 40% distributed among other players

### Event Routing and Handlers

**Event Type Mapping** (lines 1881-1892):
- Maps `result` from `generate_logic()` to `event_type`:
  - `O_FOUL` → `O_FOUL`
  - `D_FOUL` → `D_FOUL`
  - `DEAD_BALL_TURNOVER` → `TURNOVER`
  - `STEAL` → `TURNOVER`

**Handler Routing** (lines 1930-1950):
- **Turnovers**: Calls `resolve_turnover_logic(roles, game, turnover_type)` - shared function
- **Fouls**: Calls `resolve_non_shooting_foul(roles, game)` - shared function
- Both handlers return result with skeleton and animations included

**Animation Generation** (lines 1924-1930):
- Converts truncated skeleton to animations using `animator.skeleton_to_animations()`
- Adds `skeleton` and `animations` to result before returning
- Frontend animates the truncated skeleton normally

### Possession Flip and Transition Handling

**Possession Flips:**
- Handled by shared functions (`resolve_non_shooting_foul()`, `resolve_turnover_logic()`)
- `resolve_non_shooting_foul()` sets `possession_flips: True` for offensive fouls, `False` for defensive fouls
  - **✅ FIX (January 2025):** Does NOT flip possession itself - sets flag only
  - The actual flip happens in `game_manager.py` `simulate_macro_turn()` before `setup_side_inbound()`
  - This prevents double-flipping and ensures consistent behavior (same pattern as dead ball turnovers)
  - **Why:** If `resolve_non_shooting_foul()` flipped possession AND SIP setup also flipped, we'd flip twice (back to original team)
- `resolve_turnover_logic()` sets `possession_flips: True` for all turnovers
  - Same pattern: sets flag only, actual flip happens in `game_manager.py` SIP setup
  - **✅ FIX (January 2025):** Added `from_resolution_system` parameter to respect resolution system's determination
    - When `from_resolution_system=True`, the function respects the `turnover_type` passed (either "STEAL" or "DEAD BALL") and does not randomly convert "DEAD BALL" to "STEAL"
    - This ensures dead ball turnovers from the HCO Resolution System are correctly tracked and displayed
    - Nomenclature conversion: `DEAD_BALL_TURNOVER` (from resolution system) is converted to `"DEAD BALL"` (with space) before calling `resolve_turnover_logic()`

**Transition Handling:**
- Handled by shared functions (sets `offensive_state`, `next_play_type`)
- For steals with Fast Break: Sets `next_play_type = "FAST_BREAK"` to trigger possession flip in `game_manager.py`
- For steals with HCO: Sets `next_play_type = "HCO"` for direct HCO transition
- For dead ball turnovers: Routes to Side Inbound Pass (SIP) → HCO
- **SIP Setup Possession Flip:** `game_manager.py` checks `result.get("possession_flips")` and flips possession BEFORE creating the SIP turn payload (line ~300)
  - This ensures the correct team is on offense for the inbound pass
  - Clears `possession_flips` flag after flipping to prevent frontend double flip
  - **Flow Example (Offensive Foul):**
    1. HCO turn: Bentley-Truman commits offensive foul
    2. `resolve_non_shooting_foul()` sets `possession_flips: True`, returns result with `offense_team_id: "BENTLEY_TRUMAN"` (team on offense DURING the foul)
    3. `game_manager.py` checks `possession_flips=True`, calls `game.switch_possession()` → Lancaster is now offense team
    4. SIP turn created with `offense_team_id: "LANCASTER"` (new offense team after flip)
    5. Next HCO turn will have `offense_team_id: "LANCASTER"` (correct)

### Stat Tracking

**Player Stats:**
- Handled by shared functions:
  - `resolve_non_shooting_foul()`: Records `F` (fouls) for foul player
  - `resolve_turnover_logic()`: Records `TO` (turnovers) for ball handler, `STL` (steals) for defender

**Team Stats:**
- Handled by shared functions (team fouls, scouting data)

### Announcement System

**Announcement Data:**
- Result structure includes all necessary IDs:
  - `foul_player_id` - For foul announcements
  - `victim_id`, `victim_name` - For turnover announcements
  - `stealer_id`, `stealer_name` - For steal announcements
  - `foul_team` - For foul type determination

**Announcement Timing:**
- Announcements occur after animation completes (frontend handles timing)

### Key Implementation Details

**Deep Copy Protection** (line 1704):
```python
# CRITICAL: Always create a deep copy to avoid mutating cached skeleton
if skeleton:
    skeleton = copy.deepcopy(skeleton)
```
- Prevents truncated skeletons from affecting future turns
- Must be done immediately after skeleton retrieval, before any modifications

**Skeleton Variants:**
- Stopper system works consistently across all skeleton variants (successful, mid_play_change, contested, broken)
- Simply truncates the skeleton at the determined step, regardless of variant

**Ball Handling for Steals:**
- If stopper step has a pass: Ball attaches to receiver, then defender steals it
- If no pass: Ball remains with previous ball handler, then defender steals it
- TODO: Implement pass interception logic for future enhancement

### Future Enhancements

**Strategic Step Selection for Turnovers/Steals:**
- Currently uses middle step as placeholder
- TODO: Implement logic to dynamically determine `stop_step_index` based on:
  - Ball handler's BH (Ball Handling) attribute
  - Defender's ST (Steal) attribute
  - Defender's IQ (Intelligence) attribute
  - Player positions and actions in the skeleton
  - This would make turnovers feel more organic and less random

**Defensive Player Selection for Steals:**
- ✅ **COMPLETE** (January 2025): Defender assignment for steals is now implemented
  - For non-shot outcomes (steals, turnovers, fouls), defender is determined based on ball handler's position, not shooter's position
  - **Man-to-Man**: Defender matches ball handler position
  - **Zone Defense**: Uses actual zone assignment logic to find which defender(s) are guarding the ball handler
  - Handles overlapping zones correctly (uses defender actually assigned to guard ball handler)
  - Stopper system preserves the correctly set defender (prevents overwriting)
  - See "Defender Determination" section above for full implementation details

**Pass Interception Logic:**
- Currently treats all steals as steals from the ball handler
- TODO: For steps with passes, implement pass interception logic:
  - Ball attaches to receiver
  - Defender intercepts the pass (different animation than steal from handler)

### Key Files

- `BackEnd/engine/phase_resolution.py`
  - `generate_logic()` - Result determination (lines 1469-1474)
  - `resolve_half_court_offense_logic()` - Stopper system implementation (lines 1704-1950)
  - `resolve_turnover_logic()` - Shared turnover handler (lines 1383-1474)
  - `resolve_non_shooting_foul()` - Shared foul handler (lines 207-293)
  - `get_ball_handler_from_skeleton()` - SS&S helper (lines 115-161)
  - `select_foul_player()` - SS&S helper (lines 163-204)
- `BackEnd/models/animator.py`
  - `skeleton_to_animations()` - Converts truncated skeleton to animations
- `docs/To Do/stopper_system.md`
  - Future enhancement tracking

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

---

## Steal System ✅ **COMPLETE** (January 2025)

### Overview

The **Steal System** handles steal-initiated transitions for Fast Breaks and HCO turns. The system includes two bespoke steps:
- **Steal Entry**: Moves the stealer toward the basket before Fast Break resolution (defensive stop or shot attempt)
- **Steal HCO Setup**: Moves the stealer away from the basket before HCO skeleton animation begins

**Key Functions:**
- `resolve_fast_break_logic()` - Handles steal entry movement and outcome determination in `BackEnd/engine/phase_resolution.py`
- `resolve_half_court_offense_logic()` - Handles steal HCO setup movement in `BackEnd/engine/phase_resolution.py`
- `animateStealEntry()` - Animates stealer movement for Fast Breaks in `FrontEnd/static/js/phaser/animation/fastBreak.js`
- `animateStealHCOSetup()` - Animates stealer movement for HCO in `FrontEnd/static/js/phaser/animation/turnAnimation.js`

**Current Implementation:**
- ✅ **Fast Break**: Steal → Steal Entry → Fast Break resolution
- ✅ **HCO**: Steal → Steal HCO Setup → HCO skeleton animation
- 🔜 **FCP/HCT**: Steal → Steal Entry/Setup → Fast Break or HCO (future)

### When Steal Steps Activate

**Steal Entry (Fast Break):**
- After a steal occurs in FCP, HCT, or HCO turns
- When the next turn is determined to be a Fast Break (based on team aggression setting)
- Ball is already attached to the stealer from the steal turn
- No outlet pass occurs (steal-initiated Fast Breaks bypass outlet phase)

**Steal HCO Setup (HCO):**
- After a steal occurs in FCP, HCT, or HCO turns
- When the next turn is determined to be HCO (fast break chance fails)
- Ball is already attached to the stealer from the steal turn
- Runs as the first step of the HCO turn, before skeleton animation

**State Flow (Fast Break):**
1. Steal occurs → Ball attached to stealer
2. Fast break chance determined by `get_fast_break_chance()` using team **aggression** setting
3. If Fast Break → Steal Entry step executes
4. Stealer moves 5-10 x spots toward basket, ±4 y spots (clamped to 3-47)
5. After movement, defensive stop vs shot determination occurs
6. Fast Break resolution proceeds (shot attempt or defensive stop)

**State Flow (HCO):**
1. Steal occurs → Ball attached to stealer
2. Fast break chance determined by `get_fast_break_chance()` using team **aggression** setting
3. If HCO (fast break chance fails) → Steal HCO Setup step executes
4. Stealer moves 3-7 x spots away from basket, ±3 y spots (clamped to 3-47)
5. After movement, HCO skeleton animation proceeds normally

### Steal Entry Movement

**Movement Parameters:**
- **X Movement**: Random 5-10 grid spots toward offense basket
  - Home team: +5 to +10 (toward x=90)
  - Away team: -10 to -5 (toward x=10)
- **Y Movement**: Random -4 to +4 grid spots
  - Clamped to y min = 3, y max = 47 (stays in bounds)

**Constants:**
- `STEAL_ENTRY_MOVE_X_MIN = 5`
- `STEAL_ENTRY_MOVE_X_MAX = 10`
- `STEAL_ENTRY_MOVE_Y_RANGE = 4` (±4 y-coords)
- `STEAL_ENTRY_Y_MIN = 3`
- `STEAL_ENTRY_Y_MAX = 47`

**Implementation:**
```python
# Backend: BackEnd/engine/phase_resolution.py
ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)

steal_entry_move_x = random.randint(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX)
steal_entry_move_y = random.randint(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE)

ball_handler_after_entry_x = ball_handler_start_x + (direction * steal_entry_move_x)
ball_handler_after_entry_y = max(STEAL_ENTRY_Y_MIN, min(STEAL_ENTRY_Y_MAX, ball_handler_start_y + steal_entry_move_y))
```

**Frontend Animation:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/fastBreak.js
const moveX = turnData.roles?.ball_handler_move_x || 
              Phaser.Math.Between(STEAL_ENTRY_MOVE_X_MIN, STEAL_ENTRY_MOVE_X_MAX);
const moveY = turnData.roles?.ball_handler_move_y || 
              Phaser.Math.Between(-STEAL_ENTRY_MOVE_Y_RANGE, STEAL_ENTRY_MOVE_Y_RANGE);

const targetGrid = {
  x: currentGrid.x + (direction * moveX),
  y: Phaser.Math.Clamp(
    currentGrid.y + moveY,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX
  )
};
```

### Defensive Stop vs Shot Determination

After the stealer completes the steal entry movement, the system uses the **same logic as DREB Fast Breaks** to determine if it's a defensive stop or shot attempt:

**Logic (HOME Orientation):**

**Home Offense:**
- Basket at x=90 (larger x is closer to basket)
- Defender ahead if: `defender_x >= stealer_x` (after steal entry movement)
- **Defender must also be within ±6 y-coords of stealer**
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Away Offense:**
- Basket at x=10 (smaller x is closer to basket)
- Defender ahead if: `defender_x <= stealer_x` (after steal entry movement)
- **Defender must also be within ±6 y-coords of stealer**
- If defender ahead AND within y-range → DEFENSIVE_STOP
- Otherwise → SHOT

**Y-Coord Range Barrier:**
- Uses `DEFENSIVE_STOP_Y_RANGE = 6` (same as DREB Fast Breaks)
- Defender must be within ±6 y-coords of stealer to force defensive stop
- If defender is ahead but outside y-range, it becomes a shot attempt

**Multiple Defenders:**
- If multiple defenders meet both conditions (ahead AND within y-range), the closest one (by x-distance) forces the defensive stop
- If no defender meets both conditions, the closest defender overall (by Euclidean distance) becomes the shot defender

### Integration with Fast Break System

**Steal-Initiated Fast Break Flow:**

1. **Steal Entry Phase** (Bespoke Step)
   - Stealer moves 5-10 x spots toward basket, ±4 y spots (clamped)
   - Ball remains attached to stealer throughout movement
   - No outlet pass occurs (steal-initiated Fast Breaks bypass outlet phase)

2. **Defensive Stop vs Shot Check**
   - Uses stealer's position **after** steal entry movement
   - Applies same logic as DREB Fast Breaks (defender ahead AND within ±6 y-coords)

3. **Fast Break Resolution**
   - If SHOT → Animate shot attempt (same as DREB Fast Breaks)
   - If DEFENSIVE_STOP → Animate defensive stop (same as DREB Fast Breaks)

**Key Differences from DREB Fast Breaks:**
- **No Outlet Pass**: Steal-initiated Fast Breaks skip the outlet pass phase
- **Steal Entry Step**: Stealer moves before defensive stop/shot determination
- **Ball Attachment**: Ball is already attached to stealer from steal turn, remains attached during steal entry

**Backend Data Flow:**
```python
# Backend stores steal entry movement in fb_roles
fb_roles["ball_handler_move_x"] = steal_entry_move_x
fb_roles["ball_handler_move_y"] = steal_entry_move_y
fb_roles["ball_handler_outlet_x"] = ball_handler_after_entry_x  # Position after steal entry
fb_roles["ball_handler_outlet_y"] = ball_handler_after_entry_y
fb_roles["is_steal_entry"] = True  # Flag to indicate steal entry vs outlet pass
```

**Frontend Animation Flow:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/fastBreak.js
if (turnData.roles?.is_steal_entry || (!turnData.roles?.outlet_passer && !turnData.roles?.outlet_receiver)) {
  // Steal Entry Phase
  await animateStealEntry(scene, turnData, playerSprites, ballSprite, width, height);
}

// Then proceed with Fast Break resolution (shot or defensive stop)
if (result === "MAKE" || result === "MISS") {
  await animateFastBreakShot(scene, turnData, playerSprites, ballSprite, width, height);
} else {
  await animateDefensiveStop(scene, turnData, playerSprites, ballSprite, width, height);
}
```

### Steal HCO Setup Movement

**Movement Parameters:**
- **X Movement**: Random 3-7 grid spots away from offense basket
  - Home team: -7 to -3 (away from x=90, toward x=10)
  - Away team: +3 to +7 (away from x=10, toward x=90)
- **Y Movement**: Random -3 to +3 grid spots
  - Clamped to y min = 3, y max = 47 (stays in bounds)

**Constants:**
- `STEAL_HCO_SETUP_MOVE_X_MIN = 3`
- `STEAL_HCO_SETUP_MOVE_X_MAX = 7`
- `STEAL_HCO_SETUP_MOVE_Y_RANGE = 3` (±3 y-coords)
- `STEAL_HCO_SETUP_Y_MIN = 3`
- `STEAL_HCO_SETUP_Y_MAX = 47`

**Implementation:**
```python
# Backend: BackEnd/engine/phase_resolution.py
ball_handler_start_x = getattr(ball_handler, "coords", {}).get("x", 50)
ball_handler_start_y = getattr(ball_handler, "coords", {}).get("y", 25)

hco_setup_move_x = random.randint(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX)
hco_setup_move_y = random.randint(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE)

# Direction away from basket (opposite of steal entry)
hco_setup_final_x = ball_handler_start_x + (direction * hco_setup_move_x)
hco_setup_final_y = max(STEAL_HCO_SETUP_Y_MIN, min(STEAL_HCO_SETUP_Y_MAX, ball_handler_start_y + hco_setup_move_y))
```

**Frontend Animation:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/turnAnimation.js
const moveX = turnData.roles?.ball_handler_hco_setup_move_x || 
              Phaser.Math.Between(STEAL_HCO_SETUP_MOVE_X_MIN, STEAL_HCO_SETUP_MOVE_X_MAX);
const moveY = turnData.roles?.ball_handler_hco_setup_move_y || 
              Phaser.Math.Between(-STEAL_HCO_SETUP_MOVE_Y_RANGE, STEAL_HCO_SETUP_MOVE_Y_RANGE);

const targetGrid = {
  x: currentGrid.x + (direction * moveX),
  y: Phaser.Math.Clamp(
    currentGrid.y + moveY,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX
  )
};
```

### Integration with HCO System

**Steal-Initiated HCO Flow:**

1. **Steal HCO Setup Phase** (Bespoke Step)
   - Stealer moves 3-7 x spots away from basket, ±3 y spots (clamped)
   - Ball remains attached to stealer throughout movement
   - Runs before HCO skeleton animation begins

2. **HCO Skeleton Animation**
   - Proceeds normally after steal HCO setup completes
   - Stealer's position after setup becomes the starting point for skeleton animation

**Key Characteristics:**
- **Movement Direction**: Away from basket (opposite of Steal Entry for Fast Breaks)
- **Timing**: Runs as first step of HCO turn, before skeleton animation
- **Ball Attachment**: Ball is already attached to stealer from steal turn, remains attached during setup

**Backend Data Flow:**
```python
# Backend stores steal HCO setup movement in roles
roles["is_steal_hco_setup"] = True
roles["ball_handler_hco_setup_x"] = hco_setup_final_x
roles["ball_handler_hco_setup_y"] = hco_setup_final_y
roles["ball_handler_hco_setup_move_x"] = hco_setup_move_x
roles["ball_handler_hco_setup_move_y"] = hco_setup_move_y
roles["ball_handler_id"] = getattr(ball_handler, "player_id", None)

# Clear last_stealer after use to prevent persistence
game_state["last_stealer"] = None
```

**Frontend Animation Flow:**
```javascript
// Frontend: FrontEnd/static/js/phaser/animation/turnAnimation.js
// In playTurnAnimation(), before step loop starts:
if (turnData.roles?.is_steal_hco_setup) {
  await animateStealHCOSetup(scene, turnData, playerSprites, ballSprite);
}

// Then proceed with normal HCO skeleton animation
for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
  // ... skeleton animation steps
}
```

### Fast Break Chance Determination

**Team Aggression Setting:**
- Fast break chance after steals is determined by the **offensive team's aggression setting** (not tempo)
- Function: `get_fast_break_chance()` in `BackEnd/utils/shared.py`
- Aggression levels: 0-4 (0 = 0%, 1 = 25%, 2 = 50%, 3 = 75%, 4 = 100%)

**Implementation:**
```python
def get_fast_break_chance(game):
    """
    Determine fast break probability based on the OFFENSIVE team's aggression setting.
    Called after defensive rebounds or steals when the team is now on offense.
    """
    off_team = game.offense_team
    level = off_team.strategy_settings.get("aggression", 2)
    return [0.0, 0.25, 0.5, 0.75, 1.0][level]
```

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py` - `resolve_fast_break_logic()` (steal entry movement calculation) and `resolve_half_court_offense_logic()` (steal HCO setup movement calculation)
- `BackEnd/constants/fast_break_constants.py` - Steal entry and steal HCO setup constants
- `BackEnd/utils/shared.py` - `get_fast_break_chance()` (aggression-based fast break chance)

**Frontend:**
- `FrontEnd/static/js/phaser/animation/fastBreak.js` - `animateStealEntry()` and `runFastBreakSequence()`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `animateStealHCOSetup()` and `playTurnAnimation()`
- `FrontEnd/static/js/phaser/constants/fastBreakConstants.js` - Steal entry and steal HCO setup constants

### Future Enhancements

**FCP/HCT Steals:**
- Currently, FCP/HCT steals can transition to Fast Break or HCO
- When transitioning to Fast Break, Steal Entry step already applies
- When transitioning to HCO, Steal HCO Setup step already applies
- Both paths are now fully implemented

**Additional Steal Contexts:**
- Consider if steals in other contexts (e.g., during Fast Break) need bespoke setup steps
- May require different movement parameters or logic based on specific context

---

## Statistics System ✅ **COMPLETE** (January 2025)

### Overview

The Statistics System tracks comprehensive player-level and team-level statistics across all game situations. Stats are tracked in real-time during gameplay and aggregated at game, season, and career levels.

**Stat Categories:**
- **Standard Basketball Stats**: FGM, FGA, 3PTM, 3PTA, FTM, FTA, PTS, REB, OREB, DREB, AST, STL, BLK, TO, F, PIP, MIN
- **Special Situational Stats**: Fast Break, FCP/HCT, Outlet Pass, Defensive Attempts/Success, Screen Attempts/Success, Help Defense
- **Team-Level Stats**: Scouting data (offense/defense success rates), team totals, team-level situational stats

**Stat Initialization:**
- All stats initialized to `0` at game start (except `Outlet_Score_List` which is initialized as empty array `[]`)
- Initialized in:
  - `Player._init_stats()` - For all stat levels (game, season, career)
  - `_init_game_stats_dict()` in `BackEnd/main.py` - For single game mode
  - Tournament and Franchise mode initialization functions

**Stat Calculation:**
- **PTS**: Automatically calculated as `(2 * FGM) + 3PTM + FTM` when FGM, 3PTM, or FTM are recorded
- **REB**: Automatically calculated as `OREB + DREB` when OREB or DREB are recorded
- **Outlet_Score**: Automatically calculated as average of `Outlet_Score_List` when new scores are added

---

### HCO (Half Court Offense) Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **FGA** (Field Goal Attempts): Incremented for shooter on all shot attempts
- **3PTA** (Three-Point Attempts): Incremented for shooter if shot is a three-pointer
- **FGM** (Field Goals Made): Incremented for shooter when shot is made (via `apply_scoring()`)
- **3PTM** (Three-Pointers Made): Incremented for shooter when three-pointer is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **AST** (Assists): Incremented for passer when shot is made (if passer exists)
- **PIP** (Points in Paint): Incremented for shooter when shot is made from paint (amount = points scored)
- **TO** (Turnovers): Incremented for ball handler on dead ball turnovers
- **F** (Fouls): Incremented for foul player (offensive or defensive)
- **BLK** (Blocks): Incremented for defender when shot is blocked
- **DEF_A** (Defensive Attempts): Incremented for defender on shot attempts
- **DEF_S** (Defensive Success): Incremented for defender when shot is missed (without defensive foul)
- **SCR_A** (Screen Attempts): Incremented for screener on screen attempts
- **SCR_S** (Screen Success): Incremented for screener when screen leads to made shot (50% chance per attempt)
- **HELP_D** (Help Defense): Tracked for help defenders in zone defense

**Team-Level Stats (Scouting Data):**

**Offensive Attempt and Success Tracking:**
- **`off_scouting["offense"]["Playcalls"][type_label]["overall"]["attempts"]`**: Incremented when a playcall is executed
- **`off_scouting["offense"]["Playcalls"][type_label][focus]["attempts"]`**: Incremented by play focus (inside/attack/outside)
  - **Set Plays**: Attempts tracked using intended play focus from strategy settings (tracked in `turn_manager.py` before shot resolution)
  - **Motion Plays**: Attempts tracked using actual shot attempt type (tracked in `phase_resolution.py` after shot resolution)
    - Uses `motion_shot_type` from `roles["motion_shot_type"]` (the actual shot type that was attempted)
    - Reflects the actual shot location, not the strategy setting focus
- **`off_scouting["offense"]["Playcalls"][type_label]["overall"]["success"]`**: Incremented when:
  - Shot is made (`MAKE`), or
  - Defensive foul occurs (`FOUL` where `foul_team == "DEFENSE"`)
- **`off_scouting["offense"]["Playcalls"][type_label][focus]["success"]`**: Same criteria, tracked by play focus (inside/attack/outside)
  - **Set Plays**: Uses intended play focus from strategy settings (what the play was designed for)
  - **Motion Plays**: Uses actual shot attempt type (inside/attack/outside) based on where the shot was taken
    - Determined dynamically from `motion_shot_type` (stored in `roles["motion_shot_type"]`)
    - Reflects the actual shot location, not the strategy setting focus
- **`off_scouting["offense"]["Playcalls"]["Cumulative"][focus]["attempts"]`**: Cumulative attempts across all play types
- **`off_scouting["offense"]["Playcalls"]["Cumulative"][focus]["success"]`**: Cumulative success across all play types

**Key Difference:**
- **Set Plays**: Both attempts and successes use the intended focus (tracked at playcall selection time)
- **Motion Plays**: Both attempts and successes use the actual shot type (tracked after shot resolution)
  - This ensures attempts and successes are tracked consistently for the same shot type
  - Example: If a Motion play starts with "Outside" focus but player chooses "Attack" shot, both attempt and success are tracked under "Attack"

**Expected Value (EV) and Average Execution Tracking:**
- **EV Scores** (`ev_scores`): Expected Value percentage (-99.0 to +99.0) calculated for each playcall matchup
  - Stored in `off_scouting["offense"]["Playcalls"][type_label]["overall"]["ev_scores"]` and focus-specific buckets
  - Also stored in `def_scouting["defense"][tracking_name]["game_stats"]["ev_scores"]` and vs_* buckets
  - Calculated via `calculate_ev()` in `turn_manager.py` and stored via `_store_ev_score()`
  - **Key Fix (January 2025)**: Uses `calls.get("offense_play_type")` (not `"offense_type"`) to match the key used in `set_playcalls()`
- **Average Execution** (`lean_scores`): Lean score (-1.0 to +1.0) representing execution quality
  - Stored in `off_scouting["offense"]["Playcalls"][type_label]["overall"]["lean_scores"]` and focus-specific buckets
  - Also stored in `def_scouting["defense"][tracking_name]["game_stats"]["lean_scores"]` and vs_* buckets
  - Calculated via `generate_logic()` in `phase_resolution.py` and stored via `_store_lean_score()`
  - Uses `game_state["offense_play_type"]` (set correctly in `turn_manager.py`)

**Defensive Success Tracking:**
- **`def_scouting["defense"][tracking_name]["used"]`**: Incremented each time defense is used (by defensive playcall: Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone)
- **`def_scouting["defense"][tracking_name]["success"]`**: Incremented when:
  - Shot is missed (`MISS` without defensive foul), or
  - Turnover occurs (`TURNOVER`), or
  - Offensive foul occurs (`O_FOUL`)
- **Granular Tracking**: Success tracked by:
  - Play type (vs_motion, vs_set)
  - Focus type (vs_inside, vs_attack, vs_outside)
  - Defense type (vs_man, vs_2-3_zone, vs_3-2_zone, vs_1-3-1_zone, vs_zone aggregate)
  - Combinations (vs_motion_inside, vs_set_attack, etc.)

**Stat Tracking Location:**
- `BackEnd/models/shot_manager.py` - `resolve_shot()` method
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_offense_logic()` method

---

### OREB (Offensive Rebound) Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **OREB** (Offensive Rebounds): Incremented for rebounder when offensive rebound is secured
- **DREB** (Defensive Rebounds): Incremented for rebounder when defensive rebound is secured
- **REB** (Total Rebounds): Automatically calculated as `OREB + DREB`
- **FGA** (Field Goal Attempts): Incremented for rebounder on putback attempts
- **FGM** (Field Goals Made): Incremented for rebounder when putback is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **PIP** (Points in Paint): Incremented for rebounder when putback is made (always 2 points, putbacks are from paint)
- **DEF_A** (Defensive Attempts): Incremented for defender on putback attempts
- **DEF_S** (Defensive Success): Incremented for defender when putback is missed

**Putback vs Kickout:**
- **Putback (90% chance)**: Rebounder attempts shot immediately
  - Tracks FGA, FGM, PTS, PIP for rebounder
  - Tracks DEF_A, DEF_S for defender
- **Kickout (10% chance)**: Rebounder passes out, transitions to HCO
  - Only tracks OREB for rebounder
  - No shot attempt stats tracked

**Stat Tracking Location:**
- `BackEnd/utils/shared.py` - `resolve_offensive_rebound()` function
- `BackEnd/models/rebound_manager.py` - `handle_rebound()` method

---

### Free Throw Stat Tracking

**Player-Level Stats:**

**Standard Stats Tracked:**
- **FTA** (Free Throw Attempts): Incremented for shooter on each free throw attempt
- **FTM** (Free Throws Made): Incremented for shooter when free throw is made (via `apply_scoring()`)
- **PTS** (Points): Automatically calculated from FGM, 3PTM, FTM
- **OREB** (Offensive Rebounds): Incremented for rebounder if free throw is missed and offensive rebound secured
- **DREB** (Defensive Rebounds): Incremented for rebounder if free throw is missed and defensive rebound secured

**Free Throw Scenarios:**
- **Regular Free Throws**: 1-3 attempts based on foul situation
- **1-and-1 Free Throws**: Front end must be made to unlock second attempt
- **Bonus/Double Bonus**: Automatic free throws based on team foul count

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_free_throw_logic()` function

**Team-Level Stats:**
- No specific team-level tracking for free throws (standard scoring stat)

---

### Fast Break Stat Tracking

**Player-Level Stats:**

**Offensive Stats (Release Player / Outlet Receiver):**
- **`FB_A`** (Fast Break Attempts): Always incremented when player is the outlet receiver on a Fast Break
- **`FB_S`** (Fast Break Success): Incremented when Fast Break results in:
  - Shot Make (`MAKE`), or
  - Defensive Foul (non-shooting) (`FOUL` where `foul_team == "DEFENSE"`)
- **`FB_F`** (Fast Break Failure): Incremented when Fast Break results in:
  - Steal (`STEAL`), or
  - Dead Ball Turnover (`DEAD BALL`), or
  - Offensive Foul (`FOUL` where `foul_team == "OFFENSE"`)
- **`FB_N`** (Fast Break Neutral): Calculated as `FB_A - (FB_S + FB_F)`
- **Standard Stats**: FGA, FGM, 3PTM, PTS, FB_PTS (fast break points), AST (if assist on made shot)

**Defensive Stats (Get-Back Players):**
- **`FB_A_D`** (Fast Break Attempts Defense): Always incremented when player is a get-back defender on a Fast Break
- **`FB_S_D`** (Fast Break Success Defense): Incremented when Fast Break results in:
  - `DEFENSIVE_STOP`
- **`FB_F_D`** (Fast Break Failure Defense): Incremented when Fast Break results in:
  - Shot Make (`MAKE`), or
  - Shot Make + Foul, or
  - Shot Miss + Foul, or
  - Defensive Foul (non-shooting)

**Outlet Pass Stats (Outlet Passer):**
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

**Team-Level Stats (Scouting Data):**
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

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_fast_break_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_fast_break_stats()` helper function
- `BackEnd/engine/phase_resolution.py` - `_record_outlet_pass_stats()` helper function

**Special Handling:**
- **`Outlet_Score_List`**: Excluded from stat delta calculations (it's a list, not numeric)
- **Team Stats Aggregation**: `Outlet_Score_List` is concatenated (not summed) when aggregating team stats
- **Stat Deltas**: `Outlet_Score_List` and `REB` are excluded from delta calculations in `turn_manager.py`

---

### FCP (Full Court Press) Stat Tracking

**Player-Level Stats:**

**Offensive Stats (All 5 Players in Active Lineup):**
- **`FCP_A`** (FCP Attempts): Always incremented for all offensive players in active lineup
- **`FCP_S`** (FCP Success): Incremented for all offensive players when FCP result_type is:
  - `MAKE` (made shot), or
  - `HCO` (press break - successfully broke through), or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)

**Defensive Stats (All 5 Players in Active Lineup):**
- **`FCP_A_D`** (FCP Attempts Defense): Always incremented for all defensive players in active lineup
- **`FCP_S_D`** (FCP Success Defense): Incremented for all defensive players when FCP result_type is:
  - `MISS` (missed shot), or
  - `TURNOVER`, `STEAL`, `DEAD BALL`, or
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)

**Standard Stats (When Applicable):**
- **FGA, FGM, 3PTM, PTS**: Tracked for shooter on shot attempts
- **AST**: Tracked for passer on made shots
- **TO**: Tracked for ball handler on turnovers/steals
- **STL**: Tracked for defender on steals
- **F**: Tracked for foul player

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["FCP"]["used"]`**: Incremented each time defense applies Full Court Press
- **`def_scouting["defense"]["FCP"]["success"]`**: Incremented when FCP result_type is:
  - `MISS` (missed shot during press break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Offensive Success (Derived):**
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_full_court_press_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_fcp_stats()` helper function

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_full_court_press_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)

---

### HCT (Half Court Trap) Stat Tracking

**Player-Level Stats:**

**Offensive Stats (All 5 Players in Active Lineup):**
- **`HCT_A`** (HCT Attempts): Always incremented for all offensive players in active lineup
- **`HCT_S`** (HCT Success): Incremented for all offensive players when HCT result_type is:
  - `MAKE` (made shot), or
  - `HCO` (trap break - successfully broke through), or
  - `FOUL` where `foul_team == "DEFENSE"` (defensive foul)

**Defensive Stats (All 5 Players in Active Lineup):**
- **`HCT_A_D`** (HCT Attempts Defense): Always incremented for all defensive players in active lineup
- **`HCT_S_D`** (HCT Success Defense): Incremented for all defensive players when HCT result_type is:
  - `MISS` (missed shot), or
  - `TURNOVER`, `STEAL`, `DEAD BALL`, or
  - `FOUL` where `foul_team == "OFFENSE"` (offensive foul)

**Standard Stats (When Applicable):**
- **FGA, FGM, 3PTM, PTS**: Tracked for shooter on shot attempts
- **AST**: Tracked for passer on made shots
- **TO**: Tracked for ball handler on turnovers/steals
- **STL**: Tracked for defender on steals
- **F**: Tracked for foul player

**Team-Level Stats (Scouting Data):**

**Defensive Success Tracking:**
- **`def_scouting["defense"]["HCT"]["used"]`**: Incremented each time defense applies Half Court Trap
- **`def_scouting["defense"]["HCT"]["success"]`**: Incremented when HCT result_type is:
  - `MISS` (missed shot during trap break)
  - `O_FOUL` (offensive foul)
  - `DEAD_BALL_TURNOVER` (dead ball turnover)
  - `STEAL` (steal)

**Offensive Success (Derived):**
- `offensive_successes = total_attempts - defensive_successes`
- `offensive_failures = defensive_successes`
- `defensive_failures = total_attempts - defensive_successes`

**Stat Tracking Location:**
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_trap_logic()` function
- `BackEnd/engine/phase_resolution.py` - `_record_hct_stats()` helper function

**Stat Tracking Timing:**
- **SHOT Results**: Tracked after shot resolution (MAKE/MISS) in `resolve_half_court_trap_logic()`
- **Non-SHOT Results**: Tracked after result type determination (O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER, HCO)

---

### Other Turn Types with Stat Tracking

**Steals:**
- **STL** (Steals): Incremented for defender who steals the ball
- **TO** (Turnovers): Incremented for ball handler (victim of steal)
- **Fast Break Stats**: May trigger fast break opportunity, tracking `FB_A`, `FB_S`, `FB_F` for release player and `FB_A_D`, `FB_S_D`, `FB_F_D` for get-back players

**Turnovers (Dead Ball):**
- **TO** (Turnovers): Incremented for ball handler
- **Fast Break Stats**: May trigger fast break opportunity (same as steals)

**Fouls:**
- **F** (Fouls): Incremented for foul player (offensive or defensive)
- **Team Fouls**: Incremented for foul team
- **Free Throws**: May trigger free throw sequence (tracks FTA, FTM)

**Rebounds:**
- **OREB** (Offensive Rebounds): Incremented for rebounder on offensive rebounds
- **DREB** (Defensive Rebounds): Incremented for rebounder on defensive rebounds
- **REB** (Total Rebounds): Automatically calculated as `OREB + DREB`
- **Fast Break Stats**: DREB may trigger fast break opportunity

---

### Stat Aggregation and Team Totals

**Player Stat Aggregation:**
- Team totals calculated by summing all player stats from roster (not just active lineup)
- Includes bench players who may have played earlier in the game
- Aggregated in `TeamManager.get_team_game_stats()` method

**Team-Level Stats:**
- **Team Stats**: Aggregated from player stats (PTS, FGM, FGA, etc.)
- **Scouting Data**: Tracked separately at team level (offense/defense success rates)
- **Team Stats Dictionary**: Tracks team-level metrics (release_instances, get_back_instances, actual_releases, fast break defender counts)

**Stat Deltas:**
- Calculated between turns to show stat changes
- Excludes calculated stats (REB, PTS) and list stats (Outlet_Score_List)
- Used for frontend stat updates without full roster refresh

**Stat Persistence:**
- Game stats: Stored in game document
- Season stats: Aggregated across games in tournament/franchise mode
- Career stats: Aggregated across all seasons for franchise mode

---

### Key Files

- `BackEnd/models/player.py` - Player stat initialization and recording
- `BackEnd/models/shot_manager.py` - Shot stat tracking (FGA, FGM, AST, BLK, DEF_A, DEF_S)
- `BackEnd/engine/phase_resolution.py` - Fast Break, FCP, HCT, Free Throw stat tracking
- `BackEnd/utils/shared.py` - OREB stat tracking, outlet pass score calculation
- `BackEnd/models/rebound_manager.py` - Rebound stat tracking
- `BackEnd/models/team_manager.py` - Team stat aggregation
- `BackEnd/constants/__init__.py` - `BOX_SCORE_KEYS` definition (all trackable stats)

---

## Box Score System ✅ **COMPLETE** (January 2025)

### Overview

The Box Score System displays comprehensive game statistics for both teams and individual players. It aggregates data from the Statistics System and presents it in a user-friendly format accessible from the post-game screen.

**Key Features:**
- Team-level statistics (totals, fast break points, points in paint, points off turnovers)
- Player-level statistics (all tracked stats per player)
- Special stats popup (Fast Break, Outlet Passes, Traps, Presses, Points Off TOs)
- Real-time updates during game play

### Data Sources

**Backend Data:**
- **Roster API** (`/roster/{team_name}`): Returns player baseline data including `jersey`, `year`, `height`, `weight`, `attributes`
- **Box Score API** (`get_box_score()`): Returns player stats for all players (lineup + bench) with `name`, `playerId`, `jersey`, and all stat values
- **Game Summary**: Includes team totals, box score, and player energy levels

**Frontend Processing:**
- `combinePlayersAndBoxScore()`: Merges roster data with box score stats
- Handles both lineup players (by position) and bench players
- Preserves jersey numbers from multiple possible sources (`jersey`, `jerseyNumber`, `jersey_number`)

### Player Jersey Number Display ✅ **NEW** (January 2025)

**Issue:**
Jersey numbers were not appearing in the box score display or special stats popup because the backend APIs were not including jersey data.

**Root Cause:**
- Roster API (`/roster/{team_name}`) was missing `jersey` field in response
- Box Score API (`get_box_score()`) was missing `jersey` field for both lineup and bench players

**Fix:**
- **Roster API**: Added `"jersey": p.get("jersey", 0)` to player objects in `/roster/{team_name}` endpoint
- **Box Score API**: Added `"jersey": player.jersey` to both lineup and bench player entries in `get_box_score()` method

**Display:**
- Jersey numbers appear next to player names in the box score table: `Player Name (#44)`
- Jersey numbers appear in special stats popup header: `Player Name | #44`
- Handles jersey number 0 as valid (some players may have jersey 0)

**Key Files:**
- `BackEnd/api/api.py` - Roster API endpoint (line 1896)
- `BackEnd/models/game_manager.py` - `get_box_score()` method (lines 516, 530)
- `FrontEnd/static/box-score.js` - Jersey number display logic (lines 397-428, 1156-1181)

### Team Statistics Display

**Team Totals:**
- Points, Field Goals, 3-Pointers, Free Throws
- Rebounds (Defensive, Offensive, Total)
- Assists, Steals, Blocks, Fouls, Turnovers
- Defensive Attempts and Success Rate

**Special Team Stats:**
- **Fast Break Points**: Aggregated from player `FB_PTS` stats
- **Points In The Paint**: Aggregated from player `PIP` stats
- **Points Off Turnovers**: Aggregated from player `POT` stats

### Player Statistics Display

**Standard Stats Table:**
- All tracked stats per player (FGM/FGA, 3PTM/3PTA, FTM/FTA, etc.)
- Minutes played (formatted as MM:SS)
- Defensive and Screen success rates (percentages)

**Special Stats Popup:**
- **Column 1**: Fast Break stats (Offense/Defense attempts and success rates), Outlet Passes (Attempts/Score)
- **Column 2**: Traps (HCT) stats (Offense/Defense attempts and success rates), Points Off TOs (integer value)
- **Column 3**: Presses (FCP) stats (Offense/Defense attempts and success rates)

### Key Files

- `FrontEnd/static/box-score.html` - Box score page structure
- `FrontEnd/static/box-score.js` - Box score rendering and data processing
- `BackEnd/api/api.py` - Roster API endpoint (`/roster/{team_name}`)
- `BackEnd/models/game_manager.py` - Box score generation (`get_box_score()`)
- `BackEnd/models/team_manager.py` - Team stat aggregation (`get_team_game_stats()`)

### Court Page Team Box Score (S3) — Team Measures
- **Location:** `FrontEnd/static/court.html` (Team tabs S3)
- **Layout:** Horizontal pills (same style as Command Center/Training Report) in this order:
  1. Shooting (`shot_threshold`)
  2. Rebounding (`rebound_modifier`)
  3. Offense Efficiency (`offensive_efficiency`)
  4. Defense Efficiency (`defensive_efficiency`)
  5. Fast Break Efficiency (`fb_efficiency`)
  6. Press/Trap Efficiency (`pt_efficiency`)
  7. Aggression (`aggression`)
  8. Discipline (`foul_modifier`)
  9. Momentum (`momentum_score`)
  10. Team Chemistry (chemistry bar)
- **Behavior:** Uses red/green pill component; Team Chemistry uses a fill bar (0–25). Values display next to labels; chemistry shows “value / 25”.
- **Styles:** Reuses `command-center-team-styles.css` for pills; court-specific layout defined in `court.html`.

---

## Player Attribute Tooltips System ✅ **COMPLETE** (January 2025)

### Overview

The Player Attribute Tooltips System provides hover tooltips that display the full names of abbreviated player attributes and statistics across the application. This system uses JavaScript-based tooltips for reliable cross-browser support.

**Key Features:**
- Hover tooltips on attribute abbreviations (SC, SH, ID, OD, PS, BH, RB, ST, AG, FT, ND, IQ, CH, EM, MO, NG)
- Hover tooltips on other abbreviations (POS, HT, WT, RT)
- Works across multiple pages (Lineup Screen, Tournament Command Center, Franchise Command Center, Team Rosters, Player Detail)
- Custom JavaScript tooltip implementation (more reliable than native `title` attribute)
- Smooth fade-in/fade-out animations

### Implementation

**Location:** `FrontEnd/static/js/shared/attributeTooltips.js`

**Core Components:**

1. **Attribute Name Mapping:**
```javascript
const ATTRIBUTE_NAMES = {
  // Attributes
  SC: 'Scoring',
  SH: 'Shooting',
  ID: 'Inside Defense',
  OD: 'Outside Defense',
  PS: 'Passing',
  BH: 'Ball Handling',
  RB: 'Rebounding',
  ST: 'Strength',
  AG: 'Agility',
  FT: 'Free Throw',
  ND: 'Endurance',
  IQ: 'Basketball IQ',
  CH: 'Clutch',
  EM: 'Emotion',
  MO: 'Momentum',
  NG: 'Energy',
  
  // Other abbreviations
  POS: 'Position',
  HT: 'Height',
  WT: 'Weight',
  RT: 'Rating'
};
```

2. **Global Tooltip Element:**
   - Single tooltip element created once and reused for all tooltips
   - Positioned absolutely with high z-index (99999)
   - Styled with dark background, white text, rounded corners, and shadow
   - Uses opacity/visibility transitions for smooth animations

3. **Event-Based Tooltip System:**
   - `setupTooltipEvents(element, tooltipText)` - Attaches mouseenter, mouseleave, and mousemove listeners
   - Tooltip appears on `mouseenter` with fade-in animation
   - Tooltip follows mouse on `mousemove` (updates position)
   - Tooltip disappears on `mouseleave` with fade-out animation
   - Positioned above the element using `getBoundingClientRect()`

4. **Initialization Function:**
   - `initAttributeTooltips(container, selectors)` - Scans container for elements matching selectors
   - Checks element text content against `ATTRIBUTE_NAMES` mapping
   - Adds `attr-tooltip` class and sets up event listeners
   - Also checks `data-attr` attribute for programmatic tooltip assignment

5. **Helper Function:**
   - `addTooltip(element, abbreviation)` - Manually add tooltip to a specific element
   - Useful for dynamically created elements

### Usage

**Automatic Initialization (Lineup Screen):**
```javascript
// In set-lineup.js DOMContentLoaded
if (typeof initAttributeTooltips !== 'undefined') {
  const thead = document.querySelector('.roster-table thead');
  if (thead) {
    initAttributeTooltips(thead, ['th']);
  }
}
```

**Manual Initialization (Other Pages):**
```javascript
// Initialize tooltips for table headers
initAttributeTooltips(document.querySelector('.roster-table'), ['th']);

// Initialize tooltips for specific elements
initAttributeTooltips(document, ['.attr-label', '[data-attr]']);
```

**Programmatic Tooltip Assignment:**
```javascript
// Add tooltip to a specific element
const element = document.querySelector('.some-element');
addTooltip(element, 'SC'); // Will show "Scoring" on hover
```

### Tooltip Styling

**Visual Design:**
- Background: `rgba(0, 0, 0, 0.95)` (dark, semi-transparent)
- Text: White, 12px, Inter font family
- Padding: 6px 10px
- Border radius: 4px
- Box shadow: `0 2px 8px rgba(0, 0, 0, 0.3)`
- Z-index: 99999 (appears above all other content)

**Positioning:**
- Positioned above the element (8px offset)
- Centered horizontally on the element
- Uses `getBoundingClientRect()` for accurate positioning
- Updates position on mouse move for smooth following

**Animation:**
- Fade-in: 0.2s opacity transition
- Fade-out: 0.2s opacity transition
- Uses `opacity` and `visibility` for smooth transitions

### Integration Points

**Pages Using Tooltips:**
1. **Lineup Screen** (`set-lineup.html`) - Table headers (th elements)
2. **Tournament Command Center** (`tournament.html`) - Team roster table headers
3. **Franchise Command Center** (`franchise-command-center.html`) - Team and recruits table headers
4. **Team Roster Pages** (`team-roster/*.html`) - Table headers and player card labels
5. **Player Detail Page** (`player-detail.html`) - Attribute labels

**Script Loading:**
```html
<script src="/static/js/shared/attributeTooltips.js"></script>
```

**CSS Class:**
- Elements with tooltips get the `attr-tooltip` class
- This class sets `cursor: help` to indicate tooltip availability
- Also sets `position: relative` for proper tooltip positioning

### Key Files

**Frontend:**
- `FrontEnd/static/js/shared/attributeTooltips.js` - Core tooltip system
- `FrontEnd/static/set-lineup.js` - Lineup screen initialization
- `FrontEnd/static/tournament.js` - Tournament command center initialization
  - Reads `tournament_id` and `team_id` from URL parameters on page load
  - Prioritizes URL parameters over localStorage for navigation from training report
  - Uses `/tournament/state?tournament_id=...` endpoint (query parameter format)
- `FrontEnd/static/franchise-command-center.js` - Franchise command center initialization
- `FrontEnd/static/team-roster/*.html` - Team roster pages with tooltip initialization

### Technical Details

**Why JavaScript Tooltips Instead of CSS?**
- Native `title` attribute tooltips have inconsistent browser support and timing
- CSS `::after` pseudo-elements with `attr(data-tooltip)` have limited browser support
- JavaScript tooltips provide:
  - Consistent behavior across all browsers
  - Better positioning control
  - Smooth animations
  - Ability to follow mouse movement

**Performance:**
- Single global tooltip element (created once, reused for all tooltips)
- Event listeners attached only to elements that need tooltips
- Efficient DOM queries using `querySelectorAll`
- Minimal reflows/repaints during tooltip display

**Accessibility:**
- Maintains `title` attribute as fallback for screen readers
- `cursor: help` provides visual indication of tooltip availability
- Tooltip text is readable and descriptive

---

## Lineup Selection Screen ✅ **COMPLETE** (January 2025)

### Overview

The Lineup Selection Screen allows users to set their starting lineup before each game and during timeouts. It displays comprehensive player information including current game stats, attributes, and eligibility status for all roster players.

**Key Features:**
- Drag-and-drop lineup selection (5 positions: PG, SG, SF, PF, C)
- Real-time display of player stats and attributes for lineup players
- Player eligibility filtering (energy, fouls, fouled out)
- Auto-set lineup functionality
- Grid view and player card view modes
- Pre-game and in-game (timeout) lineup management

### Data Sources

**Backend Data:**
- **Roster API**: Mode-specific endpoints return player baseline data
  - **Single Game**: `/roster/{team_name}` - Base attributes from universal collection
  - **Franchise Mode**: `/franchise/roster` - Evolved attributes + game-specific attributes (EM, CH, MO)
  - **Tournament Mode**: `/tournament/roster` - Base attributes + tournament-specific attributes (EM, CH, MO)
- **Game API** (`/api/game/{gameId}`): Returns current game state including:
  - Player stats (`stats.game`)
  - Player attributes (`attributes.EM`, `attributes.MO`, `attributes.CH`, `attributes.NG`)
  - Ineligible players (fouled out)

**Frontend Processing:**
- `loadRoster()`: Loads roster from mode-specific endpoint
- `loadRoster()`: If `gameId` exists, fetches game data and merges stats/attributes
- `updateSlotDisplay()`: Displays stats and attributes for each lineup player

### Player Stats and Attributes Display ✅ **NEW** (January 2025)

**Displayed Information for Lineup Players:**
- **Points** (PTS): Current game points
- **Rebounds** (REB): Sum of OREB + DREB + REB
- **Assists** (AST): Current game assists
- **Def %**: Defensive success rate (DEF_S / DEF_A * 100)
- **Emotion** (EM): Emoji display based on value (😎 80+, 😊 60+, 😐 40+, 😕 20+, 😞 <20)
- **Momentum** (MO): Visual bar display (-10 to +10 range)
- **Fouls** (F): Current game foul count
- **Energy** (NG): Percentage with color coding (Green >89%, Yellow 80-89%, Orange 70-79%, Red <70%)

**Data Flow:**
1. **Pre-Game (Q1, no gameId)**: 
   - Roster loads from mode-specific endpoint
   - Game initialized via `/api/init-game` (randomizes EM, CH, MO)
   - Game data fetched and merged into roster
   - All players (lineup + bench) get EM/MO attributes from initialized game

2. **In-Game (timeout, gameId exists)**:
   - Roster loads from mode-specific endpoint
   - Game data fetched from `/api/game/{gameId}`
   - Stats and attributes merged into roster
   - Lineup players display current game stats and updated attributes

**Mode-Specific Attribute Handling:**

- **Single Game Mode**:
  - Roster provides base attributes (SC, SH, ID, OD, etc.)
  - Game API provides: stats + attributes (EM, MO, CH, NG)
  - Frontend merges: roster base + game stats/attributes

- **Franchise Mode**:
  - Roster (`/franchise/roster`) provides evolved + game-specific attributes
  - Game API provides: stats + NG (current energy)
  - Frontend merges: franchise attributes + game stats/NG

- **Tournament Mode**:
  - Roster (`/tournament/roster`) provides base + tournament-specific attributes
  - Game API provides: stats + NG (current energy)
  - Frontend merges: tournament attributes + game stats/NG

### Pre-Game EM/MO Display Fix ✅ **NEW** (January 2025)

**Issue:**
Emotion and momentum values were not displaying on the pre-game (pre-Q1) lineup screen, even though they were initialized when the game was created via `/api/init-game`.

**Root Cause:**
The `/api/game/{gameId}` endpoint was only returning players from the starting lineup (`team.lineup.items()`), which meant only 5 players were returned. The roster has all players (typically 12), so most roster players couldn't be matched with game data to get EM/MO attributes.

**Fix:**
Changed `/api/game/{gameId}` to return ALL players using `team.get_all_players()` instead of just lineup players. This ensures:
- All roster players can be matched with game data
- All players get EM/MO attributes initialized by `init-game`
- Pre-game lineup screen displays emotion/momentum immediately after game initialization
- Works for both lineup players and bench players

**Implementation:**
```python
# Before: Only lineup players
for pos, player in team.lineup.items():  # Only 5 players

# After: All players
for player in team.get_all_players():  # All players (lineup + bench)
```

### Player Eligibility Filtering

**Energy (NG) Restrictions:**
- Default: Exclude players with NG < 80%
- Late Q4/OT: Exclude players with NG < 69% (less than 4 minutes remaining in Q4 or overtime)

**Foul Restrictions (by quarter):**
- Q1: Exclude if player fouls > 1
- Q2: Exclude if player fouls > 2
- Q3: Exclude if player fouls > 3
- Q4: Exclude if player fouls > 3 AND more than 4 minutes remaining
- Overtime: No foul exclusion for active players (5+ fouls still excluded)

**Fouled Out:**
- Players with 5+ fouls are always excluded (marked as ineligible)
- Visual indicators: Reduced opacity, "FOULED OUT" label, disabled interactions

### Key Files

- `FrontEnd/static/set-lineup.html` - Lineup selection page structure
- `FrontEnd/static/set-lineup.js` - Lineup selection logic and data processing
- `BackEnd/api/api.py` - Game state endpoint (`/api/game/{gameId}`), init game endpoint (`/api/init-game`)
- `BackEnd/api/franchise_routes.py` - Franchise roster endpoint (`/franchise/roster`)
- `BackEnd/api/tournament_routes.py` - Tournament roster endpoint (`/tournament/roster`)
- `BackEnd/utils/db_utils.py` - Player eligibility filtering (`is_player_eligible_for_lineup()`)

---

## Play Builder System ✅ **COMPLETE** (January 2025)

### Overview

The Play Builder (`play-builder-v2.html`) is a web-based tool for creating and editing offensive plays. It supports two distinct play types: **Set Plays** and **Motion Plays**, each with different structures and requirements.

### Play Types

#### Set Plays
- **Structure**: Four skeleton variants (`successful`, `mid_play_change`, `contested`, `broken`)
- **Focus**: Required - must select Inside, Attack, Outside, or Balanced
- **Variants**: 
  - `successful`: Direct `steps` array (no versions)
  - `mid_play_change`, `contested`, `broken`: `versions` dictionary (v1-v6), each with a `steps` array
- **Final Step Requirement**: Must have a `shoot` action in the final step
- **Shooter Validation**: Shots only allowed in final step

#### Motion Plays
- **Structure**: Single skeleton variant (`base_loop`)
- **Focus**: Not required (null in database)
- **Variants**: Only `base_loop` with direct `steps` array
- **Loop Structure**: Circular motion with `is_final_step` flag marking loop end
- **Final Step**: Marked with checkbox when building - sets `is_final_step: true` and `loop_back_to: 0`
- **Shooter Validation**: Shots can occur at any step (no restrictions)

### Building Process

#### Step 1: Play Creation
1. **Enter Play Name**: Text input for play name
2. **Select Play Type**: Dropdown - "Motion" or "Set Play"
3. **Select Play Focus** (Set Play only): Dropdown - "Inside", "Attack", "Outside", or "Balanced"
   - Disabled for Motion plays
   - Required for Set Plays to enable "Create Play" button
4. **Create Play Button**: Enabled when name + type (+ focus for Set Plays) are provided

#### Step 2: Step Building
1. **Starting Formation Selection**: 
   - Preset formations: "3-2", "4-1", "5-0", "Screen Entry"
   - Custom: Manual positioning
   - **Note**: Formation must be manually saved as Step 0 by clicking "Add Step" after selection
2. **Step Building**:
   - Drag-and-drop players to court locations
   - Assign actions (handle_ball, pass, receive, shoot, drive, get_open)
   - Add position offsets for screens
   - **Motion Plays**: Checkbox to "Mark as Final Step (Loop End)" available when building new steps
3. **Add Step Button**: Saves current step and increments to next step
   - Timestamp calculation: `(currentStep - 1) * 300` (Step 0 = 0ms, Step 1 = 300ms, etc.)
4. **Finish Variant & Save**: 
   - Auto-submits current step if incomplete
   - Validates variant structure
   - Saves to database via `/api/plays` endpoint

### Variant Management

#### Set Play Variants
- **Successful**: Base skeleton with direct steps array
- **Mid-Play Change**: 6 versions (v1-v6), each with steps array
- **Contested**: 6 versions (v1-v6), each with steps array
- **Broken**: 6 versions (v1-v6), each with steps array
- **Version Selector**: Shown for non-successful variants
- **Clone Function**: Can clone from Successful variant to other variants

#### Motion Play Variants
- **Base Loop**: Single variant with steps array
- **No Version Selector**: Hidden for Motion plays
- **Loop Validation**: Checks for `is_final_step` flag and validates loop structure

### Database Structure

#### Set Play Structure
```json
{
  "name": "Play Name",
  "play_type": "set_play",
  "play_focus": "inside|attack|outside|balanced",
  "skeletons": {
    "successful": {
      "steps": [...],
      "complete": true
    },
    "mid_play_change": {
      "versions": [
        {"steps": [...], "complete": true},
        ...
      ]
    },
    "contested": {...},
    "broken": {...}
  }
}
```

#### Motion Play Structure
```json
{
  "name": "Play Name",
  "play_type": "motion",
  "play_focus": null,
  "skeletons": {
    "base_loop": {
      "steps": [
        {...},
        {"is_final_step": true, "loop_back_to": 0, ...}
      ],
      "complete": true
    }
  }
}
```

### Play Creation Data Structure ✅ **NEW** (January 2025)

When a new play is created via Play Builder V2, the following fields are automatically populated in the play document:

#### Required Fields (Always Set)
- **`_id`**: MongoDB ObjectId (auto-generated)
- **`name`**: Play name (user-provided)
- **`play_type`**: "motion" or "set_play" (converted from user selection)
- **`play_focus`**: 
  - Set Plays: "inside", "attack", "outside", or "balanced" (user-provided)
  - Motion Plays: `null` (not applicable)
- **`skeletons`**: Complete skeleton structure with all variants and steps

#### Initialized Fields (Default Values)
- **`effectiveness`**: `0` (0-100 scale, starts at 0 for new plays)
- **`cloaking`**: `0` (0-10 scale, starts at 0 for new plays)
- **`momentum`**: `0` (0-10 scale, starts at 0 for new plays)
- **`copy`**: `{}` (empty object, for play details page copy text)

#### Statistics Fields (Initialized to Zero)
- **`game_stats`**: Object with all stats initialized to 0:
  ```json
  {
    "times_run": 0,
    "shot_attempts": 0,
    "made_shots": 0,
    "turnovers": 0,
    "offensive_fouls": 0,
    "defensive_fouls": 0
  }
  ```
- **`season_stats`**: Same structure as `game_stats`, all initialized to 0

#### Complete Play Document Example
```json
{
  "_id": "68f919f9065f78d452557809",
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,
  "skeletons": {
    "base_loop": {
      "steps": [...],
      "complete": true
    }
  },
  "effectiveness": 0,
  "cloaking": 0,
  "momentum": 0,
  "copy": {},
  "game_stats": {
    "times_run": 0,
    "shot_attempts": 0,
    "made_shots": 0,
    "turnovers": 0,
    "offensive_fouls": 0,
    "defensive_fouls": 0
  },
  "season_stats": {
    "times_run": 0,
    "shot_attempts": 0,
    "made_shots": 0,
    "turnovers": 0,
    "offensive_fouls": 0,
    "defensive_fouls": 0
  }
}
```

#### Implementation Details

**Frontend (`FrontEnd/static/play-builder-v2.html:4013-4053`):**
- `savePlayToDatabase()` function builds the play data object
- All fields are explicitly set before sending to backend
- Metrics (`effectiveness`, `cloaking`, `momentum`) initialized to 0
- `copy` object initialized as empty object `{}`

**Backend (`BackEnd/api/play_routes.py:30-96`):**
- `PlayCreate` Pydantic model defines accepted fields
- `create_play()` endpoint validates and saves play data
- Backend ensures all fields are initialized if not provided (defensive programming)
- Uses MongoDB `upsert=True` to update existing plays or create new ones (matched by `name`)

**Key Points:**
- All play metrics start at 0 and are updated through gameplay/training
- Statistics accumulate over time as plays are used
- `copy` object can be populated later for play details page descriptions
- Play documents are stored in `plays_collection` (universal plays library)

### Key Functions

#### `updateAnimationVariantDropdown()`
- **Purpose**: Updates animation preview dropdown with available variants
- **Motion Plays**: Only processes `base_loop` variant
- **Set Plays**: Processes all four variants (`successful`, `mid_play_change`, `contested`, `broken`)
- **Error Prevention**: Checks for variant existence before accessing `steps.length`

#### `savePlayToDatabase()`
- **Purpose**: Saves play to MongoDB via `/api/plays` endpoint
- **Motion Plays**: Saves only `base_loop` skeleton
- **Set Plays**: Saves all four variants with version structures
- **Validation**: Ensures proper structure before saving

#### `validateCurrentStep()`
- **Purpose**: Validates step assignments against skeleton rules
- **Set Plays**: Enforces shooter validation (shoot only in final step)
- **Motion Plays**: No shooter restrictions (shoot can be at any step)

#### `validateLoopStructure()`
- **Purpose**: Validates Motion play loop structure
- **Checks**: 
  - At least 2 steps for cohesive cycle
  - `is_final_step` flag is present
  - First and final step position matching (warnings only)

### UI Components

#### Variant Tabs
- **Set Plays**: Shows 4 tabs (Successful, Mid-Play Change, Contested, Broken)
- **Motion Plays**: Shows 1 tab (Base Loop)
- **Visibility**: Controlled by `updateVariantTabsVisibility()` based on play type

#### Formation Selection
- **Preset Formations**: Pre-populate player positions and actions
- **Custom**: Manual positioning required
- **Step 0**: Formation must be manually saved as first step

#### Final Step Checkbox (Motion Only)
- **Visibility**: Only shown for Motion plays when building new steps

---

## Mode Initialization System ✅ **COMPLETE** (January 2025)

### Overview

The Mode Initialization System diversifies attribute values when users create a new mode instance (Single Game, Tournament, or Franchise). This system ensures that each new game mode instance has unique player and team attributes, adding variety and replayability to the game experience.

**Location:** `BackEnd/models/team_manager.py`, `BackEnd/models/player.py`  
**Status:** ✅ Fully implemented for all three game modes  
**Scope:** Applies only to new mode instance creation; existing instances persist their unique data

### Initialization Scope

**Single Game Mode:**
- Applies to the 2 teams participating in the game instance
- Player attributes randomized for all players on both teams
- Team attributes randomized for both teams

**Tournament Mode:**
- Applies to all 8 teams in the tournament instance
- Player attributes randomized for all players on all 8 teams
- Team attributes randomized for all 8 teams

**Franchise Mode:**
- Applies to all 8 teams in the franchise instance
- Player attributes randomized for all players on all 8 teams
- Team attributes randomized for all 8 teams (with different ranges than Single/Tournament)

### Player Attribute Initialization

When a new mode instance is created, player attributes are initialized as follows:

**Copied from Universal Players Collection:**
- `SC` (Shooting Close) - Exact value from universal collection
- `SH` (Shooting) - Exact value from universal collection
- `ID` (Inside Defense) - Exact value from universal collection
- `OD` (Outside Defense) - Exact value from universal collection
- `PS` (Passing) - Exact value from universal collection
- `BH` (Ball Handling) - Exact value from universal collection
- `RB` (Rebounding) - Exact value from universal collection
- `ST` (Stealing) - Exact value from universal collection
- `AG` (Agility) - Exact value from universal collection
- `ND` (Endurance) - Exact value from universal collection
- `IQ` (Intelligence Quotient) - Exact value from universal collection
- `FT` (Free Throw) - Exact value from universal collection

**Randomized Values:**
- `NG` (Energy) - Always set to `1.0` (full energy at start)
- `CH` (Chemistry) - `random.randint(1, 100)`
- `MO` (Momentum) - Weighted random distribution:
  - `0`: 50% chance
  - `-1` or `1`: 15% chance each (30% total)
  - `-2` or `2`: 7.5% chance each (15% total)
  - `-3` or `3`: 2.5% chance each (5% total)
- `EM` (Emotion) - `random.randint(1, 100)`

**Implementation:**
- `Player.randomize_game_attributes()` method in `BackEnd/models/player.py`
- Called during mode instance creation for all players
- Updates both the attribute and its anchor value (e.g., `EM` and `anchor_EM`)

### Team Attribute Initialization

When a new mode instance is created, team attributes are initialized with mode-specific ranges:

**Common Attributes (All Modes):**
- `shot_threshold` - `random.randint(-100, 100)`
- `rebound_modifier` - `random.choice([0.8, 0.9, 1.0, 1.1, 1.2])`

**Team Chemistry (Mode-Specific):**
- **Single Game & Tournament Mode:** `random.randint(7, 25)`
- **Franchise Mode:** `random.randint(7, 13)` (lower range for more challenging progression)

**All Other Team Attributes (Mode-Specific Ranges):**
- **Single Game & Tournament Mode:** `random.randint(-10, 10)`
  - `turnover_modifier`
  - `foul_modifier`
  - `offensive_efficiency`
  - `defensive_efficiency`
  - `fb_efficiency`
  - `pt_efficiency`
  - `fb_opp_modifier`
  - `pt_opp_modifier`
- **Franchise Mode:** `random.randint(-3, 3)` (tighter range for more controlled progression)
  - Same attributes as above

**Implementation:**
- `TeamManager._init_team_attributes(mode)` method in `BackEnd/models/team_manager.py`
- Accepts `mode` parameter to determine attribute ranges
- Called during team initialization when `team_attributes` is not provided

### Initialization Points

**Single Game Mode:**
- **Location:** `BackEnd/api/api.py` - `init_game()` endpoint
- **Process:**
  1. `GameManager` is created with team names
  2. `TeamManager.__init__()` loads roster and initializes team attributes
  3. `_initialize_game_stats()` randomizes player attributes (EM, CH, MO)
  4. Game document is created with initialized attributes

**Tournament Mode:**
- **Location:** `BackEnd/tournament/tournament_manager.py` - `create_tournament()` method
- **Process:**
  1. Tournament document is created
  2. All players from participating teams are loaded
  3. `Player.randomize_game_attributes()` is called for each player
  4. **ALL player attributes are stored** in `tournament.player_stats.{player_id}.attributes` (not just EM, CH, MO)
  5. Team attributes are initialized when teams are first used in games
- **Attribute Storage:** Tournament mode now uses the same architecture as Franchise mode - all attributes are stored in the tournament document to support training and evolution

**Franchise Mode:**
- **Location:** `BackEnd/models/franchise_manager.py` - `initialize_season()` method
- **Process:**
  1. Season is initialized
  2. All players from all teams are loaded
  3. `Player.randomize_game_attributes()` is called for each player
  4. Team attributes are initialized in `franchise_teams` structure with Franchise-specific ranges

### Data Persistence

**Important:** Once a mode instance is created, its unique attribute values persist:
- **Single Game:** Attributes stored in game document, persist across quarters
- **Tournament:** **ALL attributes** stored in `tournament.player_stats.{player_id}.attributes`, persist across rounds (unified with Franchise architecture)
- **Franchise:** **ALL attributes** stored in `franchise.players.{player_id}.attributes`, persist across weeks and seasons

**Evolution:**
- Attributes can change based on:
  - Training system (Franchise/Tournament modes)
  - In-game performance (momentum, chemistry adjustments)
  - User interactions (coaching decisions, lineup changes)
- Initial randomization provides the starting point; subsequent changes build upon these values

### Key Files

- `BackEnd/models/player.py` - `Player.randomize_game_attributes()` (lines 51-70)
  - Player attribute initialization logic
- `BackEnd/models/team_manager.py` - `TeamManager.__init__()` (lines 9-84)
  - Team initialization with mode parameter stored as `self.mode`
  - Used by `_init_scouting_data()` for tournament mode randomization
- `BackEnd/models/team_manager.py` - `TeamManager._init_team_attributes()` (lines 128-142)
  - Team attribute initialization logic with mode-specific ranges
- `BackEnd/api/api.py` - `init_game()` (lines 2099-2142)
  - Single Game mode initialization
- `BackEnd/tournament/tournament_manager.py` - `create_tournament()` (lines 32-86)
  - Tournament mode initialization
- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-210)
  - Franchise mode initialization

---

## Plays System ✅ **COMPLETE** (January 2025)

### Overview

The Plays System is the core mechanism for selecting and executing offensive and defensive plays during gameplay. It integrates playbook settings, strategy preferences, user overrides, and play effectiveness tracking to determine which plays are used in each turn.

**Location:** `BackEnd/models/turn_manager.py` - `set_playcalls()` method  
**Status:** ✅ Fully implemented with playbook integration, user overrides, and effectiveness tracking

### Play Selection Process

The play selection process occurs at the start of each HCO (Half Court Offense) turn via `set_playcalls()`. The system uses a hierarchical approach:

#### 1. User Override Check

**Offensive Play Override:**
- Checks `offense_team.strategy_calls.get("offense_call")` for user-selected play
- If set, uses the specific play name (e.g., "3-2 Motion", "Base Post Play")
- Override is cleared after use (one-time override)
- Looks up play details from database to determine `play_type` and `play_focus`

**Defensive Play Override:**
- Checks `user_team.strategy_calls.get("defense_call")` (regardless of current offense/defense)
- If set, uses the specific defense (e.g., "Man", "2-3 Zone", "Zone")
- Override is persistent until manually cleared by user
- If "Zone" is selected, converts to specific zone type using playbook weights

#### 2. Normal Play Selection (If No Override)

**Offensive Play Selection - Two-Level System:**

**Level 1: Determine Play Type (Motion vs Set Play)**
- Uses `offense_setting` from strategy settings (0-4 slider)
- Weighted random selection based on setting:
  - Setting 0: 100% Motion, 0% Set Play
  - Setting 1: 75% Motion, 25% Set Play
  - Setting 2: 50% Motion, 50% Set Play
  - Setting 3: 25% Motion, 75% Set Play
  - Setting 4: 0% Motion, 100% Set Play

**Level 2: Determine Play Focus (Inside/Attack/Outside)**
- Only applies to Set Plays (Motion plays don't filter by focus)
- Uses `inside`, `attack`, `outside` values from strategy settings
- Weighted random selection:
  - Roll random number from 1 to total (inside + attack + outside)
  - If roll <= inside_val → "inside"
  - Else if roll <= inside_val + attack_val → "attack"
  - Else → "outside"

**Level 3: Select Specific Play**
- Queries universal `plays` collection:
  - **Motion Plays:** `{"play_type": "motion"}`
  - **Set Plays:** `{"play_type": "set_play", "play_focus": chosen_focus}`
- Uses playbook-weighted selection (see Playbook Integration below)
- Falls back to equal weights if no playbook settings exist

**Defensive Play Selection:**
- Uses `defense_setting` from strategy settings (0-4 slider)
- Maps setting to defense options via `STRATEGY_CALL_DICTS["defense"]`
- If "Zone" is selected, converts to specific zone type:
  - Uses playbook-weighted selection for user teams
  - Falls back to equal weights for CPU teams
- Available defenses: "Man", "2-3 Zone", "3-2 Zone", "1-3-1 Zone"

### Playbook Integration

**Weighted Selection System:**
- Loads playbook settings from team document: `teams.{team_id}.playbook_settings`
- Uses `weighted_random_from_dict()` utility for selection
- Only applies to user teams (CPU teams use equal weights)

**Motion Offense Selection:**
- Uses `playbook_settings.motion` dictionary
- Keys are play names, values are percentages (0-100)
- Example: `{"5-0 Motion": 50, "4-1 Motion": 30, "3-2 Motion": 20}`
- Excludes "To Be Added" plays (0% weight)

**Set Play Selection:**
- Uses `playbook_settings.set_play_{focus}` dictionaries
- Separate dictionaries for each focus: `set_play_inside`, `set_play_attack`, `set_play_outside`
- Keys are play names, values are percentages
- Example: `{"set_play_inside": {"Base Post Play": 60, "Wing Entry": 40}}`

**Zone Defense Selection:**
- Uses `playbook_settings.zone_defense` dictionary
- Keys are zone type names: "2-3 Zone", "3-2 Zone", "1-3-1 Zone"
- Values are percentages
- Example: `{"2-3 Zone": 40, "3-2 Zone": 35, "1-3-1 Zone": 25}`

**Fallback Behavior:**
- If no playbook settings exist → Equal weights for all plays
- If CPU team → Equal weights (playbook settings ignored)
- If "To Be Added" play → Excluded from selection (0% weight)

### Play Execution Flow

**1. Skeleton Retrieval:**
- `get_hco_skeleton()` retrieves play skeleton from universal collection
- Uses reference-based architecture: looks up `play_id` from team plays, then fetches skeleton
- **Motion Plays:** Always uses `base_loop` skeleton (no variant selection)
- **Set Plays:** Selects variant based on resolution outcome:
  - `successful` - Play works perfectly (lean_score >= 0.5)
  - `mid_play_change` - Play adjusts mid-execution (0 <= lean_score < 0.5)
  - `contested` - Defense engaged (-0.5 < lean_score < 0)
  - `broken` - Defense disrupts (lean_score <= -0.5)

**2. Resolution System Integration:**
- `resolve_half_court_offense_logic()` calls `resolve_hco_outcome()`
- Determines turn outcome: SHOT, O_FOUL, D_FOUL, STEAL, DEAD_BALL_TURNOVER
- For Set Plays, outcome determines skeleton variant selection
- For Motion Plays, outcome determines shot type (Inside/Attack/Outside)

**3. Stopper System:**
- If non-shot outcome occurs, `apply_stopper_system_to_skeleton()` truncates skeleton
- Appends "stopper step" at the point of interruption
- Preserves animation continuity while reflecting game event

**4. Animation Generation:**
- `skeleton_to_animations()` converts skeleton steps to frontend animation data
- Processes player movements, ball passes, and actions
- Frontend animates the play execution

### Play Effectiveness and Momentum Tracking

**Dual Storage Architecture:**

Effectiveness, momentum, and cloaking values exist in **two locations**:

1. **Universal Collections** (`plays` and `defenses` collections):
   - Template/library values for all plays and defenses
   - Initialized to `0` for all plays and defenses
   - Serve as default starting values when team objects are created
   - Can be modified globally (affects all teams using that play/defense)

2. **Team Objects** (`teams.{team_id}.plays` and `scouting_data["defense"]`):
   - **Per-team instances** with team-specific values
   - Initialized from universal collection values when team object is created
   - Can be modified independently per team by:
     - **Training system** - Based on playbook settings and game plan mix
     - In-game performance (future implementation)
     - Coaching focus selections (future implementation)
   - Allows different teams to have different effectiveness/momentum/cloaking for the same play/defense

**Effectiveness:**
- **Per-team effectiveness** stored in `teams.{team_id}.plays.{play_name}.effectiveness`
- **Per-team defense effectiveness** stored in `scouting_data["defense"][defense_name].effectiveness`
- Separate from calculated effectiveness in `game_stats`/`season_stats`
- Used in matchup calculations and play/defense selection weighting
- Modified by training system based on:
  - Playbook percentages (plays used more frequently get more training benefit)
  - Game plan mix (motion vs set plays, inside vs attack vs outside focus)
  - Defense preferences (man vs zone percentages)

**Momentum:**
- **Per-team momentum** stored in `teams.{team_id}.plays.{play_name}.momentum`
- **Per-team defense momentum** stored in `scouting_data["defense"][defense_name].momentum`
- Tracks recent performance trends for this team's use of the play/defense
- Can increase or decrease based on:
  - Training system modifications
  - Recent success/failure rates (future implementation)
  - Coaching focus selections (future implementation)
  - Game situation and context (future implementation)
- Used to adjust play/defense selection probabilities dynamically

**Cloaking:**
- **Per-team cloaking** stored in `teams.{team_id}.plays.{play_name}.cloaking`
- **Per-team defense cloaking** stored in `scouting_data["defense"][defense_name].cloaking`
- Makes plays/defenses harder for opponents to recognize and counter
- Higher values reduce opponent's ability to anticipate and adjust
- Can be modified by training system
- Used in matchup calculations and offensive/defensive recognition systems

### Database Structure

#### Offensive Plays (Universal `plays` Collection)

**Location:** MongoDB `plays` collection  
**Purpose:** Store offensive play definitions with full skeleton data

**Document Structure:**
```json
{
  "_id": ObjectId("..."),
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,
  "effectiveness": 0,
  "cloaking": 0,
  "momentum": 0,
  "skeletons": {
    "base_loop": {
      "steps": [...],
      "complete": true
    }
  },
  "copy": {
    "copy_1": "Description text...",
    "copy_2": "More description...",
    "copy_3": "Additional details..."
  }
}
```

**Field Descriptions:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Play name (e.g., "4-1 Motion", "3-2 Motion", "Base Post Play")
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str | null) - "inside", "attack", "outside", "balanced" (Set Plays only), or `null` (Motion Plays)
- `skeletons` (dict) - Full skeleton data with animation steps
  - **Motion Plays:** `{"base_loop": {steps: [...], complete: true}}`
  - **Set Plays:** `{"successful": {...}, "mid_play_change": {...}, "contested": {...}, "broken": {...}}`
- `copy` (dict | null) - Optional descriptive text for play details page
- `effectiveness` (float) - Play effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)

#### Defensive Plays (Universal `defenses` Collection)

**Location:** MongoDB `defenses` collection  
**Purpose:** Store defensive playcall definitions with zone configurations

**Document Structure:**
```json
{
  "_id": ObjectId("..."),
  "defense_id": "2-3-zone",
  "defense_type": "Zone",
  "name": "2-3 Zone",
  "description": "Standard 2-3 zone defense with two guards up top and three players in the paint",
  "effectiveness": 0.0,
  "cloaking": 0,
  "momentum": 0,
  "zone_definitions": {
    "normal": {...},
    "lower_shift": {...},
    "upper_shift": {...}
  },
  "shift_triggers": {
    "lower_shift": ["lower wing", "lower midCorner", "lower corner"],
    "upper_shift": ["upper wing", "upper midCorner", "upper corner"]
  },
  "game_stats": {...},
  "season_stats": {...}
}
```

**Field Descriptions:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `defense_id` (str) - Unique defense identifier (e.g., "man", "2-3-zone", "3-2-zone", "1-3-1-zone", "base-man")
- `defense_type` (str) - "Man" or "Zone"
- `name` (str) - Defense display name (e.g., "Man-to-Man", "2-3 Zone", "Base Man")
- `description` (str) - Defense description text
- `effectiveness` (float) - Defense effectiveness score (default: `0`)
- `cloaking` (float) - Cloaking modifier (default: `0`)
- `momentum` (integer) - Momentum score (default: `0`)
- `zone_definitions` (dict | null) - Zone positioning configurations (Zone defenses only)
  - `normal` - Default zone positions
  - `lower_shift` - Zone positions when ball is in lower areas
  - `upper_shift` - Zone positions when ball is in upper areas
  - Additional shifts for 1-3-1 zone (`lower_corner_shift`, `upper_corner_shift`)
  - `null` for Man defenses
- `shift_triggers` (dict | null) - Ball locations that trigger zone shifts
  - Maps shift names to arrays of location strings
  - `null` for Man defenses
- `game_stats` (dict) - Game-level usage and success tracking
- `season_stats` (dict) - Season-level usage and success tracking

### Integration with Resolution System

**HCO Resolution:**
- Plays are selected before resolution begins
- Selected play determines skeleton retrieval
- Resolution outcome (for Set Plays) determines skeleton variant
- Play effectiveness and momentum can influence resolution calculations (future implementation)

**Motion Offense Resolution:**
- Uses `base_loop` skeleton for all turns
- `resolve_motion_offense_shot()` determines shot type dynamically
- Shot type (Inside/Attack/Outside) is determined by player positioning and opportunities
- Attack penalty applied to shot scores for drive-and-shoot actions

**Set Play Resolution:**
- Resolution outcome determines which variant skeleton to use
- Variant selection based on lean score from matchup evaluation
- Each variant has different shot opportunities and player movements

### Key Files

- `BackEnd/models/turn_manager.py` - `set_playcalls()` method (lines 793-1264)
  - Play selection logic
  - User override handling
  - Playbook-weighted selection
- `BackEnd/engine/phase_resolution.py` - `resolve_half_court_offense_logic()` (lines 3105-3200)
  - Play execution and resolution
  - Skeleton retrieval and variant selection
- `BackEnd/engine/phase_resolution.py` - `get_hco_skeleton()` (lines 4709-4791)
  - Skeleton retrieval from universal collection
  - Reference-based architecture
- `BackEnd/engine/phase_resolution.py` - `_get_skeleton_from_team_plays()` (lines 4794-4891)
  - Team play reference lookup
  - Skeleton caching
- `BackEnd/utils/shared.py` - `weighted_random_from_dict()` (lines 21-37)
  - Weighted random selection utility
- `BackEnd/db.py` - `plays_collection`, `defenses_collection`
  - MongoDB collection access

---

## Universal Plays and Defenses Collections ✅ **DOCUMENTED** (January 2025)

### Overview

The game uses two universal MongoDB collections to store play and defense definitions:
- **`plays` collection**: Stores all offensive plays (Set Plays and Motion Plays)
- **`defenses` collection**: Stores all defensive playcalls (Man and Zone defenses)

These collections serve as the "library" of available plays and defenses. Team documents store only **references** to these universal collections, dramatically reducing document size (see Reference-Based Play Architecture).

### Universal Plays Collection

**Location:** MongoDB `plays` collection  
**Purpose:** Store offensive play definitions with full skeleton data

#### Play Document Structure

All plays in the universal collection include the following fields:

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `name` (str) - Play name (e.g., "4-1 Motion", "3-2 Motion")
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str | null) - "inside", "attack", "outside", "balanced" (Set Plays only), or `null` (Motion Plays)
- `skeletons` (dict) - Full skeleton data with animation steps (see Play Builder System for structure)
- `copy` (dict | null) - Optional descriptive text for play details page (`copy_1`, `copy_2`, `copy_3`)

**Effectiveness, Cloaking, and Momentum Fields:**
- `effectiveness` (float) - Play effectiveness score (default: `0`)
  - Used for calculating play success rates and matchup evaluations
  - Can be modified by training, in-game performance, and coaching focus
- `cloaking` (float) - Cloaking modifier (default: `0`)
  - Used for defensive recognition and counter-play adjustments
  - Higher values make plays harder for defenses to recognize and counter
- `momentum` (integer) - Momentum score (default: `0`)
  - Tracks recent performance trends for the play
  - Can increase or decrease based on success/failure rates
  - Used to adjust play selection probabilities dynamically

**Stats Fields (Optional):**
- `game_stats` (dict) - Game-level usage statistics (if tracked at collection level)
- `season_stats` (dict) - Season-level usage statistics (if tracked at collection level)

#### Example Play Document

```json
{
  "_id": ObjectId("..."),
  "name": "4-1 Motion",
  "play_type": "motion",
  "play_focus": null,
  "effectiveness": 0,
  "cloaking": 0,
  "skeletons": {
    "base_loop": {
      "steps": [...],
      "complete": true
    }
  },
  "copy": {
    "copy_1": "Description text...",
    "copy_2": "More description...",
    "copy_3": "Additional details..."
  }
}
```

### Universal Defenses Collection

**Location:** MongoDB `defenses` collection  
**Purpose:** Store defensive playcall definitions with zone configurations

#### Defense Document Structure

All defenses in the universal collection include the following fields:

**Core Fields:**
- `_id` (ObjectId) - Unique MongoDB document ID
- `defense_id` (str) - Unique defense identifier (e.g., "man", "2-3-zone", "3-2-zone", "1-3-1-zone", "base-man")
- `defense_type` (str) - "Man" or "Zone"
- `name` (str) - Defense display name (e.g., "Man-to-Man", "2-3 Zone", "Base Man")
- `description` (str) - Defense description text

**Effectiveness, Cloaking, and Momentum Fields:**
- `effectiveness` (float) - Defense effectiveness score (default: `0`)
  - Used for calculating defensive success rates and matchup evaluations
  - Can be modified by training, in-game performance, and coaching focus
- `cloaking` (float) - Cloaking modifier (default: `0`)
  - Used for offensive recognition and counter-play adjustments
  - Higher values make defenses harder for offenses to recognize and counter
- `momentum` (integer) - Momentum score (default: `0`)
  - Tracks recent performance trends for the defense
  - Can increase or decrease based on success/failure rates
  - Used to adjust defense selection probabilities dynamically

**Zone-Specific Fields (Zone defenses only):**
- `zone_definitions` (dict | null) - Zone positioning configurations
  - `normal` - Default zone positions
  - `lower_shift` - Zone positions when ball is in lower areas
  - `upper_shift` - Zone positions when ball is in upper areas
  - Additional shifts for 1-3-1 zone (`lower_corner_shift`, `upper_corner_shift`)
  - `null` for Man defenses
- `shift_triggers` (dict | null) - Ball locations that trigger zone shifts
  - Maps shift names to arrays of location strings
  - `null` for Man defenses

**Stats Fields:**
- `game_stats` (dict) - Game-level usage and success tracking
  - `used` (int) - Number of times defense was used
  - `success` (int) - Number of successful defensive stops
  - Granular tracking: `vs_motion`, `vs_set`, `vs_inside`, `vs_attack`, `vs_outside`, etc.
- `season_stats` (dict) - Season-level usage and success tracking (same structure as `game_stats`)

#### Example Defense Document

```json
{
  "_id": ObjectId("..."),
  "defense_id": "2-3-zone",
  "defense_type": "Zone",
  "name": "2-3 Zone",
  "description": "Standard 2-3 zone defense with two guards up top and three players in the paint",
  "effectiveness": 0.0,
  "cloaking": 0,
  "zone_definitions": {
    "normal": {...},
    "lower_shift": {...},
    "upper_shift": {...}
  },
  "shift_triggers": {
    "lower_shift": ["lower wing", "lower midCorner", "lower corner"],
    "upper_shift": ["upper wing", "upper midCorner", "upper corner"]
  },
  "game_stats": {...},
  "season_stats": {...}
}
```

### Field Initialization

**Scripts:**
- `scripts/add_effectiveness_cloaking_fields.py` - Adds `effectiveness` and `cloaking` fields
- `scripts/add_momentum_field_to_plays_defenses.py` - Adds `momentum` field

These scripts ensure all plays and defenses have the required fields:
- `effectiveness: 0` - Play/defense effectiveness score
- `cloaking: 0` - Cloaking modifier
- `momentum: 0` - Momentum score

**Usage:**
```bash
python scripts/add_effectiveness_cloaking_fields.py
python scripts/add_momentum_field_to_plays_defenses.py
```

### Reference-Based Architecture

Team documents store only **references** to universal plays and defenses:
- Team plays: `{play_name: {play_id: "...", game_stats: {...}}}`
- Team defenses: Tracking stats only, no full definitions

Full skeleton data and zone definitions are fetched from universal collections when needed, reducing document size by ~95% (see Reference-Based Play Architecture documentation).
- **Function**: Marks step as loop end with `is_final_step: true` and `loop_back_to: 0`

### Animation Preview System ✅ **NEW** (January 2025)

#### Overview
The Play Builder includes an animation preview system that allows users to visualize their plays before saving. The system behaves differently for Motion plays vs Set Plays.

#### Animation Controls

**Variant Selector:**
- **Motion Plays**: Variant selector is hidden - automatically uses `base_loop` variant
- **Set Plays**: Variant selector is shown - user must select from available variants (`successful`, `mid_play_change`, `contested`, `broken`)
- **Dropdown Population**: `updateAnimationVariantDropdown()` populates options based on play type and available steps

**Animate Button:**
- **Motion Plays**: No variant selection required - button works immediately if `base_loop` has steps
- **Set Plays**: Requires variant selection from dropdown before animating
- **Validation**: Checks that selected variant has at least one step before starting animation

#### Animation Behavior

**Set Plays:**
- Animates through all steps sequentially
- Stops at the end of the animation
- Shows step counter: "Animating Step X of Y"

**Motion Plays - Infinite Loop:**
- Animates through all steps sequentially
- **Loop Detection**: When final step (`is_final_step: true`) is reached, automatically loops back to step 0
- **Fallback Loop**: If no final step is marked, loops back to step 0 at the end of all steps
- **Continuous Animation**: Animation continues indefinitely until manually stopped
- **Status Display**: Shows "Animating Step X of Y (Final Step - will loop)" when final step is reached

#### Animation Functions

**`startAnimation()`:**
- **Motion Plays**: Automatically uses `base_loop` variant (no selection needed)
- **Set Plays**: Uses selected variant from dropdown
- **Validation**: Checks for variant existence and step count before starting
- **UI Updates**: Hides animate button, shows stop button, displays status

**`animateNextStep(selectedVariant)`:**
- **Step Rendering**: Updates player positions and actions for current step
- **Loop Logic** (Motion only):
  - Detects when `is_final_step: true` is reached
  - Resets `animationStepIndex` to 0 to loop back
  - If no final step marked, loops at end of steps array
- **Set Play Logic**: Stops animation when all steps are complete
- **Timing**: 1 second delay between steps
- **Status Updates**: Updates status message with current step and loop indication

**`stopAnimation()`:**
- Stops the animation loop
- Clears animation interval
- Resets UI (shows animate button, hides stop button)
- Works for both Motion and Set Plays

#### Key Implementation Details

1. **Variant Selection**: Motion plays bypass variant selection entirely, using `base_loop` automatically
2. **Loop Detection**: Uses `step.is_final_step === true` to identify the loop end point
3. **Index Management**: `animationStepIndex` is reset to 0 when loop condition is met
4. **Status Messages**: Provides clear feedback about current step and loop behavior
5. **Continuous Play**: Motion plays can run indefinitely until user stops them

### Key Files

**Frontend**:
- `FrontEnd/static/play-builder-v2.html` - Main play builder interface
- `FrontEnd/static/play-builder.html` - Legacy play builder (Set Plays only)

**Backend**:
- `BackEnd/api/play_routes.py` - API endpoints for play CRUD operations
- `BackEnd/db.py` - MongoDB connection and `plays_collection` definition

### Future Enhancements

- [x] Animation preview for Motion plays ✅ **COMPLETE** (January 2025)
- [ ] Loop visualization (show loop path)
- [ ] Version cloning between variants
- [ ] Bulk import/export of plays
- [ ] Play templates library

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
- **HCT Turn Start:** ✅ **NEW** (January 2025) - `playTurnAnimation()` skips `runSetupTween()` when `fromInbound === true` AND `isFCPHCT === true`
  - Players are already positioned at step 0 from BIP, so redundant positioning is skipped
  - Prevents timing conflicts with inbound pass animation completion
- **BIP Pass Completion Wait:** ✅ **NEW** (January 2025) - `handleBaselineInbound()` explicitly waits for inbound pass animation to fully complete before returning
  - **Problem Fixed:** HCT/FCP turn was starting before BIP pass animation finished, causing sequencing bug where HCT setup step ran, then BIP pass executed, then HCT continued
  - **Solution:** After `executeInboundSequence()` completes, checks `scene.passInFlight` flag and waits for it to clear
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with 2-second safety timeout
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` function (lines 354-395)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: HCT defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling
- `turnAnimation.js` lines 2211-2217: Skip `runSetupTween()` for BIP → HCT transitions
- `AnimationEngine.js` lines 354-395: BIP pass completion wait logic

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
- **FCP Turn Start:** ✅ **NEW** (January 2025) - `playTurnAnimation()` skips `runSetupTween()` when `fromInbound === true` AND `isFCPHCT === true`
  - Players are already positioned at step 0 from BIP, so redundant positioning is skipped
  - Prevents timing conflicts with inbound pass animation completion
- **BIP Pass Completion Wait:** ✅ **NEW** (January 2025) - `handleBaselineInbound()` explicitly waits for inbound pass animation to fully complete before returning
  - **Problem Fixed:** HCT/FCP turn was starting before BIP pass animation finished, causing sequencing bug where HCT setup step ran, then BIP pass executed, then HCT continued
  - **Solution:** After `executeInboundSequence()` completes, checks `scene.passInFlight` flag and waits for it to clear
  - **Implementation:** Listens for `passEnd` event and polls `passInFlight` as fallback, with 2-second safety timeout
  - **Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - `handleBaselineInbound()` function (lines 354-395)
  - **Why It Matters:** Ensures BIP animation fully completes before next turn (HCT/FCP) starts, preventing visual glitches and timing conflicts

**Key Code:**
- `turnAnimation.js` lines 1186-1225: Skeleton position conversion with `opp` logic
- `turnAnimation.js` lines 1079-1128: FCP defensive positioning
- `BackEnd/engine/phase_resolution.py` `apply_opposite_side_logic()`: Backend `opp` handling
- `turnAnimation.js` lines 2211-2217: Skip `runSetupTween()` for BIP → FCP transitions
- `AnimationEngine.js` lines 354-395: BIP pass completion wait logic

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
   - **Captures `timeout_offense_team_id`** before creating timeout turn (`BackEnd/models/game_manager.py` line 272)
   - Creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`
   - **✅ CRITICAL FIX (January 2025):** Immediately saves game state to database (same pattern as user-initiated timeout)
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

#### 4. **Player Foul Out Returns (Any Quarter)** ✅ **UPDATED** (January 2025)
- **Initial Turn:** SIDE_INBOUND (SIP) or FREE_THROW (based on foul context)
- **Location:** Same as timeout returns (uses timeout system)
- **Logic:** Foul out resume → creates SIP or FREE_THROW turn based on foul context
- **Data:** Uses same timeout resume system, captures `timeout_offense_team_id` in `game_manager.py`
- **Navigation:** Helper passes `game_id` AND sets `resume_from_timeout=true` (any quarter)
- **Frontend:** `foulOutPopup.js` navigation to lineup
- **Note:** Supports Q1-Q4 and OT (uses same system as timeout)

**Foul Out Context System:**
- **Purpose:** Stores detailed foul information to guide next play type determination
- **Location:** `game_state["foul_out_context"]` dictionary
- **Contents:**
  - `foul_type`: "OFFENSIVE" or "DEFENSIVE"
  - `is_shooting_foul`: Boolean (True for shooting fouls, False for non-shooting)
  - `is_bonus`: Boolean (True if team is in bonus situation)
  - `next_play_type`: "SIDE_INBOUND" or "FREE_THROW" (determined by foul context)
  - `shooter`: Player object (for shooting fouls, stores shooter for free throw resume)
- **Set By:** Foul resolution logic in `phase_resolution.py` (non-shooting fouls) and `shot_manager.py` (shooting fouls)
- **Used By:** `turn_manager.py` `setup_timeout_turn()` to determine `next_play_type` for foul-out timeouts

**Possession Flip Logic:**
- **Offensive Fouls:** Possession flips during SIP setup (not during foul resolution)
  - Location: `phase_resolution.py` `resolve_non_shooting_foul()` sets `possession_flips: True` (line ~384)
  - **✅ FIX (January 2025):** Does NOT call `game.switch_possession()` in `resolve_non_shooting_foul()`
  - Actual flip happens in `game_manager.py` `simulate_macro_turn()` before `setup_side_inbound()` (line ~300)
  - This prevents double-flipping and ensures consistent behavior (same pattern as dead ball turnovers)
  - **Flow:**
    1. HCO turn with offensive foul: `offense_team_id` = team that committed foul (e.g., "BENTLEY_TRUMAN")
    2. `resolve_non_shooting_foul()` sets `possession_flips: True` but does NOT flip `game.offense_team`
    3. `game_manager.py` checks `possession_flips=True` and calls `game.switch_possession()`
    4. SIP turn created: `offense_team_id` = new offense team (e.g., "LANCASTER")
  - Next step: SIDE_INBOUND (with new offense team after flip)
- **Defensive Fouls:** No possession flip
  - If Shooting Foul: Next step: FREE_THROW (the shooting player shoots)
  - If Non-Shooting Foul:
    - If Bonus Situation: Next step: FREE_THROW (the player the fouling player was guarding shoots)
    - If Non-Bonus Situation: Next step: SIDE_INBOUND

**Next Play Type Determination:**
- **Location:** `turn_manager.py` `setup_timeout_turn()` (lines 1611-1676)
- **Logic:**
  1. For foul-out timeouts: Uses `foul_out_context` to determine `next_play_type`
  2. For regular timeouts with free throws: Uses `free_throws_remaining` to set `next_play_type = "FREE_THROW"`
  3. For regular timeouts: Defaults to `next_play_type = "SIDE_INBOUND"`
- **Stored In:** `game_state["timeout_next_play_type"]` for resume

**Lineup Screen Population:**
- **Location:** `FrontEnd/static/js/phaser/utils/foulOutPopup.js` `showFoulOutPopup()` function
- **Logic:**
  1. Fetches current lineup from URL parameters (same as timeout flow)
  2. Removes **only** the fouled-out player from the user's team lineup
  3. Leaves the fouled-out player's position empty (not replaced)
  4. Passes populated lineup (minus foul out player) to `TimeoutNavigationHelper`
- **Key Point:** Only removes the fouled-out player if they're on the user's team; other team's lineup is preserved

**Clock Display:**
- **Location:** `FrontEnd/static/js/phaser/gameScene.js` (lines 392-410)
- **Logic:** Clock is initialized immediately on page load using first turn's clock data from backend
- **Ensures:** Correct time remaining displays immediately when returning from lineup/game plan screens, not a stale value that updates only after the next turn

**Key Files:**
- `BackEnd/engine/phase_resolution.py` - Foul resolution and `foul_out_context` storage (non-shooting fouls)
- `BackEnd/models/shot_manager.py` - Shooting foul resolution and `foul_out_context` storage
- `BackEnd/models/game_manager.py` - Foul-out timeout creation and immediate database save (lines 245-304)
- `BackEnd/models/turn_manager.py` - `setup_timeout_turn()` with `foul_out_context` support
- `FrontEnd/static/js/phaser/utils/foulOutPopup.js` - Lineup population and navigation
- `FrontEnd/static/js/phaser/gameScene.js` - Clock initialization on timeout resume

### Data Management: Database, LocalStorage, and URL

#### Database (Single Source of Truth)

**When Timeout is Called:**

**User-Initiated Timeout (`BackEnd/api/api.py` `call_timeout_endpoint()`):**
```python
# Save timeout state to database
gm.game_state["timeout_next_play_type"] = "SIDE_INBOUND"  # Always SIP (except free throws)
gm.game_state["timeout_offense_team_id"] = gm.offense_team.team_id  # Capture possession team

db_summary = summarize_game_state(gm, exclude_animations=True)
games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
```

**Foul-Out Timeout (`BackEnd/models/game_manager.py` `simulate_macro_turn()`):**
```python
# ✅ CRITICAL FIX (January 2025): Save timeout state immediately when foul-out timeout is created
# This ensures timeout state persists even if user navigates away before simulate-turn saves
if self.game_id:
    db_summary = summarize_game_state(self, exclude_animations=True)
    games_collection.update_one({"_id": self.game_id}, {"$set": db_summary}, upsert=True)
```

**Persisted Timeout Data:**
- `timeout_next_play_type`: Always `"SIDE_INBOUND"` (or `"FREE_THROW"` if free throws pending)
- `timeout_offense_team_id`: Team that had possession when timeout was called
- `clock`: Current game clock
- `time_remaining`: Time remaining in seconds
- All other game state (scores, fouls, timeouts, lineups, player stats)

**Key Fix:** Foul-out timeouts now save immediately to database (same as user-initiated timeouts), preventing timeout state loss when "Sim to 4th Quarter" or other operations overwrite game state before the timeout is processed.

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
  - **Game Document Fields:** `tournament_id` and `mode` are always set in `games_collection` documents (matches Franchise pattern)
  - **Implementation:** `BackEnd/api/api.py:1636-1650` - `simulate_quarter_endpoint()` adds `tournament_id` and `mode` when saving game state
- **Franchise Game:** Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)
  - **Game Document Fields:** `franchise_id` and `week` are always set in `games_collection` documents
  - **Implementation:** `BackEnd/api/franchise_routes.py:365-366` - Adds `franchise_id` and `week` when saving game state

#### URL Parameters (Navigation Only)

**Purpose:** URL parameters are used for navigation/routing, not business logic. Database is the source of truth.

**Unified Navigation Helper System (SS&S - December 2025):**

All frontend navigation now uses a unified helper (`FrontEnd/static/js/shared/timeoutNavigationHelper.js`) for consistent parameter building across all entry points.

**Helper Functions:**
- `buildGameNavigationParams()`: Builds URL parameters with consistent SS&S logic
- `getResumeFromTimeout()`: Extracts `resume_from_timeout` from URL params
- `getGameId()`: Gets game ID from URL or localStorage

**Navigation Entry Points Using Helper:**
- `set-lineup.js`: "Play Now" button, "Game Plan" button, "Box Score" button
- `game-plan.js`: `navigateToCourt()`, `navigateBack()`, `navigateToCommandCenter()`, Playbooks button navigation
  - **Navigation Source Detection:** Detects `from` URL parameter (`lineup` vs `command_center`)
  - **Button Visibility:** Shows "Back To Lineup" or "Back To Locker Room" based on navigation source
  - **Button Text:** "Play Game" (from lineup) or "Save Game Plan" (from command center)
  - **Team ID Resolution:** Uses `user_team_id` when from command center, `home_id`/`away_id` when from lineup
- `playbooks.js`: `navigateToPlayDetails()`, `handleBack()` (navigation to/from play-details and game-plan)
- `play-details.html`: `goBack()` (navigation back to playbooks)
- `box-score.js`: `setupLockerRoomButton()` (back navigation from lineup/game-plan)
- `timeoutButtonManager.js`: `showTimeoutPopup()` (timeout button navigation)
- `foulOutPopup.js`: Foul out navigation to lineup
- `gameScene.js`: Quarter end navigation

**Critical Update (January 2025):**
All navigation functions now use `TimeoutNavigationHelper` to ensure consistent parameter preservation, including `resume_from_timeout` and `clock` parameters. This fixes issues where game state was lost during navigation chains (e.g., Foul Out → Lineup → Game Plan → Playbooks → Play Details → back to court).

**Previously Manual Navigation (Now Using Helper):**
- `playbooks.js` `handleBack()`: Now uses helper for game-plan navigation (preserves timeout state)
- `playbooks.js` `navigateToPlayDetails()`: Now uses helper (preserves timeout state)
- `play-details.html` `goBack()`: Now uses helper (preserves timeout state)
- `game-plan.js` Playbooks button: Now uses helper (preserves timeout state)

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
- Prevents params from being lost during navigation chain: lineup → game-plan → playbooks → play-details → box-score → court
- **All navigation functions MUST use `TimeoutNavigationHelper`** - manual parameter preservation is fragile and can lose critical state (e.g., `clock` parameter)

**Foul Out Navigation Fix (January 2025):**
- Fixed issue where quarter time reset to 8 minutes after navigating through playbooks/play-details pages
- Root cause: Manual parameter preservation only preserved params if they were truthy (`if (value)`)
- Solution: All navigation functions now use `TimeoutNavigationHelper` which explicitly preserves `resume_from_timeout` and `clock` parameters
- Affected functions: `playbooks.js` `handleBack()`, `playbooks.js` `navigateToPlayDetails()`, `play-details.html` `goBack()`, `game-plan.js` Playbooks button

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
4. **Determine Play Type:**
   - Checks `play.play_type` to determine if it's a Motion play or Set Play
   - Uses different logic based on play type
5. **Set Plays - Extract Intended Shooter from Skeleton:**
   - Gets successful skeleton from `play.skeletons.successful`
   - Extracts intended shooter position from final step's `pos_actions` where `action == "shoot"`
   - Uses same logic as backend `phase_resolution.py` (lines 1011-1017)
6. **Motion Plays - Analyze Steps 1-10 for Most Likely Shooter:**
   - Gets `base_loop` skeleton from `play.skeletons.base_loop`
   - Analyzes steps 1-10 (excluding step 0) to count shot opportunities for each player
   - **Inside Shots:** Player with most opportunities (handles ball at inside spot OR receives pass at inside spot)
   - **Outside/Attack Shots:** Player who handles ball at outside shot spot the most
   - If tie, chooses randomly
7. **Map Position to Player ID:** Maps shooter position to player ID from user's lineup
8. **Set Image Once:** Image path is `/static/images/players/{playerId}.png`
9. **Images Remain Static:** No mid-game changes during gameplay

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
   - Can navigate between Lineup, Game Plan, Playbooks, and Play Details screens
   - Helper preserves all parameters during all navigation (including `resume_from_timeout` and `clock`)
   - All navigation functions use `TimeoutNavigationHelper` for consistency
   - Parameters maintained correctly through entire navigation chain

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

### Computer Team Lineup Management (January 2025)

The computer team automatically adjusts its lineup during timeouts and at quarter breaks based on player energy levels and foul counts. This ensures the computer team makes strategic lineup decisions without user intervention.

**When Lineups Are Rebuilt:**

1. **During Timeouts:**
   - When the user calls a timeout, the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/api/api.py` `call_timeout_endpoint()` (lines 195-210)
   - Only the computer team's lineup is adjusted (user team lineup remains unchanged)
   - Uses current game state to apply energy and foul filtering rules

2. **At Quarter Breaks:**
   - At the start of each new quarter (Q2, Q3, Q4, OT), the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/main.py` `simulate_quarter()` (lines 402-443, 444-468, 469-493)
   - Ensures the computer team starts each quarter with an optimal lineup based on current player conditions

**Player Eligibility Filtering:**

The system uses `is_player_eligible_for_lineup()` (`BackEnd/utils/db_utils.py`) to filter players based on:

1. **Energy (NG) Filtering:**
   - **Default:** Exclude players with NG < 80% (0.8)
   - **Q4 < 4min or OT:** Exclude players with NG < 69% (0.69)
   - Allows computer team to rest fatigued players during normal play, but be more aggressive in late-game situations

2. **Foul-Based Filtering (by Quarter):**
   - **Q1:** Exclude if player fouls > 1
   - **Q2:** Exclude if player fouls > 2
   - **Q3:** Exclude if player fouls > 3
   - **Q4:** Exclude if player fouls > 3 AND > 4 minutes remaining (no exclusion if ≤ 4 minutes remaining)
   - **Overtime:** No foul exclusion for active players
   - Prevents computer team from playing players in foul trouble early, but allows them to play through foul trouble in critical moments

3. **Fouled Out Players:**
   - Players with 5 or more fouls are always excluded (not considered active)
   - Applied regardless of quarter or time remaining

**Implementation Details:**

- **Function:** `build_lineup_from_mongo(team, game_state=None)` (`BackEnd/utils/db_utils.py`)
  - Accepts `game_state` parameter to access current quarter, time remaining, and player stats
  - Filters `available_players` using `is_player_eligible_for_lineup(player, game_state)`
  - Only applies filtering to computer teams (user team lineups are not modified)

- **Lineup Completion:** `ensure_complete_lineup(team, game_state)` (`BackEnd/utils/db_utils.py`)
  - Ensures lineup has exactly 5 players
  - Uses same eligibility filtering if additional players are needed
  - Falls back to any available players if filtered list is insufficient

- **Game State Access:**
  - `game_state["quarter"]` - Current quarter number
  - `game_state["time_remaining"]` - Time remaining in seconds
  - `player.fouls` - Player's current foul count
  - `player.NG` - Player's current energy level (Nerve/Game)

**Key Features:**
- Only affects computer team (user team lineups are never auto-adjusted)
- Respects explicit lineup choices (doesn't overwrite if lineup is explicitly provided)
- Uses current game state for accurate filtering (quarter, time remaining, player stats)
- Includes error handling and logging for debugging
- Works consistently across all game modes (single, tournament, franchise)

**Backend Locations:**
- `BackEnd/utils/db_utils.py`: `is_player_eligible_for_lineup()`, `build_lineup_from_mongo()`, `ensure_complete_lineup()`
- `BackEnd/api/api.py`: Timeout lineup rebuild logic (`call_timeout_endpoint()`)
- `BackEnd/main.py`: Quarter break lineup rebuild logic (`simulate_quarter()`)

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

**Playcall Name Display:**
- The Playcall Center displays the full offense playcall name from the database (via `playcallDisplay.js`)
- Format: Full playcall name (e.g., "3-2 Motion", "4-1 Motion", "Pick & Roll (Lower Wing)")
- Updated from `turnData.offensive_playcall` or `turnData.current_playcall`
- For Motion plays, displays the actual play name (e.g., "3-2 Motion") instead of just the play type ("Motion")
- Falls back to play type if playcall name is not available
- Backend ensures `offensive_playcall` is set to the actual play name from `game_state["current_playcall"]` (which may be overridden for Motion plays)

#### 2. Main Row: Three-Column Layout

**Left Panel: Offense Tactical Panel**
- **Title:** "OFFENSE OVERRIDE"
- **Play Scroller:** Displays 6 offensive play options in order determined by Playbooks slot assignments:
  - **Slot 1:** First play (assigned in Playbooks page) - shown by default when page loads
  - **Slot 2:** Second play (assigned in Playbooks page)
  - **Slot 3:** Third play (assigned in Playbooks page)
  - **Slot 4:** Fourth play (assigned in Playbooks page)
  - **Slot 5:** Fifth play (assigned in Playbooks page)
  - **Slot 6:** Sixth play (assigned in Playbooks page)
  - Unassigned plays appear after slots 1-6
- **Player Headshots:** Each play displays a player headshot image assigned based on play focus and user's lineup
- **Navigation Buttons:** Up/down arrows to navigate through plays in slot order:
  - **Up (▲):** Previous slot (1→2→3→4→5→6, wraps to 6)
  - **Down (▼):** Next slot (6→5→4→3→2→1, wraps to 1)
- **Clear Override Button:** Removes any selected offense override
- **Selection State:** Selected plays are highlighted with `selected` class
- **Slot Order Integration:** Play order is automatically synchronized with Playbooks page slot assignments (loaded from database on page load)
  - **Loading Process:** `loadAndApplySlotAssignments()` function runs on page load
  - **Team ID Resolution:** Checks multiple URL parameters in order: `team_id`, `user_team_id`, `home_id`, `away_id`
    - Different pages pass team ID with different parameter names (Game Plan uses `user_team_id`)
  - **Event-Based Synchronization:** Uses `playcall-center-reordered` event to notify navigation code when reordering completes
    - Prevents race conditions where navigation might show wrong play before reordering finishes
    - Navigation code listens for event and updates play options/show first play when event fires
  - **Debug Logging:** Comprehensive logging for troubleshooting:
    - API request URL and response
    - Slot assignments and motion dropdowns received
    - Current play order in DOM before reordering
    - PlayId to play name mapping
    - Slot assignment processing for each slot (1-6)
    - Matching attempts and results
    - Final play order after reordering

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
- **PERSISTENT:** Defense override is NOT cleared after use - remains until user manually clears via red X button

**Aggression Override:**
- User selects aggression level (Passive/Normal/Aggressive)
- Stored in `team.strategy_calls["aggression_override"]`
- Applied to defensive playcalls when user's team is on defense
- **PERSISTENT:** Aggression override is NOT cleared after use - remains until user manually clears via red X button
- Applied in `set_strategy_calls()` (not `set_playcalls()`)
- Sets `defense_team.strategy_calls["aggression_call"] = aggression_override`

**Tempo Override:**
- User selects tempo level (Slow/Normal/Fast)
- Stored in `team.strategy_calls["tempo_override"]`
- Applied to offensive playcalls when user's team is on offense

#### Data Structure

**Backend Storage (`team.strategy_calls`):**
```python
{
    "offense_call": None | str,          # Play name or None (cleared after one use)
    "defense_call": None | str,          # "Man", "Zone", or None (persists until manually cleared)
    "aggression_override": None | str,   # "normal", "aggressive", "passive", or None (persists until manually cleared)
    "tempo_override": None | str,        # "slow", "normal", "fast", or None
    "press_override": None,               # Future: FCP override
    "trap_override": None                 # Future: HCT override
}
```

**Turn Result Flag (`result["offense_override_cleared"]`):**
- Boolean flag sent to frontend in turn result
- Initialized to `False` at start of each turn
- Set to `True` when user team's offense override is used and cleared
- Frontend uses this flag to un-highlight the selected offense playcall button
- Prevents false un-highlighting when computer team uses same play name

**Initialization:**
- `TeamManager.__init__()` initializes `strategy_calls` with all fields set to `None`
- Default state: No overrides active (normal play selection logic used)

#### Override Application Flow

1. **User Selection (Frontend):**
   - User clicks play option or defense button in Playcall Center
   - Frontend calls `setPlaycallOverride()` function in `court.html`
   - Function sends POST request to `/api/set-playcall-override`
   - **Key Behavior:** Only sends the field being changed (not all fields with nulls)
   - Example: Setting offense sends only `{offense_override: "4-1 Motion"}`, not all three override fields

2. **API Endpoint (`/api/set-playcall-override`):**
   - Receives `PlaycallOverrideRequest` with `game_id`, `user_team_side`, and override values
   - **SS&S Design:** Only processes fields that are explicitly provided in the request body
   - This prevents accidentally clearing other overrides when setting one field
   - Identifies user team from `user_team_side` ("home" or "away")
   - Updates `team.strategy_calls` with override values
   - Returns success status and current override state
   - **Implementation:** Uses `provided_fields = set(body.keys())` to track which fields were sent
   - Only processes fields in `provided_fields`, ignoring fields not in the request

3. **Backend Playcall Selection (`set_playcalls()` in `turn_manager.py`):**
   - Called during HCO turn setup
   - **User Team Detection:** Uses `game_state["user_team_side"]` instead of `is_user_team` flag (more reliable, persists to DB)
   - Determines if user team is on offense: `is_offense_user = (user_team_side == "home" and offense_team.is_home_team) or (user_team_side == "away" and not offense_team.is_home_team)`
   - **Offense Override:**
     - If `team.strategy_calls["offense_call"] != None` and user team is on offense:
       - Uses override playcall instead of normal selection
       - Clears override after use: `team.strategy_calls["offense_call"] = None`
       - Sets `offense_override_cleared = True` in return dictionary
   - **Defense Override:**
     - If `team.strategy_calls["defense_call"] != None` and user team is on defense:
       - Uses override defense (converts "Zone" to specific zone type if needed)
       - **PERSISTENT:** Defense override is NOT cleared after use - remains until user manually clears via red X button
   - **Aggression Override:**
     - Checked in `set_strategy_calls()` (not `set_playcalls()`)
     - If `team.strategy_calls["aggression_override"] != None`:
       - Applied to `defense_team.strategy_calls["aggression_call"]`
       - **PERSISTENT:** Aggression override is NOT cleared after use - remains until user manually clears via red X button

4. **Frontend Button Un-Highlighting:**
   - **Offense Playcalls:** Un-highlighted automatically when backend clears the override
   - Backend sends `offense_override_cleared: true` flag in turn result when override is used
   - Frontend checks `turnData.offense_override_cleared === true` in `updatePlaycallCenter()`
   - If flag is `true`, finds selected button and removes `selected` class
   - **SS&S Design:** No need to match playcall names or check team sides - backend flag is single source of truth
   - **Defense/Aggression Buttons:** Remain highlighted until user manually clears via red X buttons (persistent overrides)

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
- Backend uses `game_state["user_team_side"]` stored during `GameManager` initialization
- More reliable than `is_user_team` flag - persists to database and survives game reloads
- Value is "home" or "away" indicating which team is the user's team
- Stored in `game_state` and included in `summarize_game_state()` for database persistence
- Ensures overrides only apply to user's team, not computer team

### Player Image Assignment System

Player headshots in the Playcall Center are assigned once when returning to `court.html` from lineup/game plan screens. The system uses different logic for Set Plays vs Motion Plays.

**Process (SS&S - January 2025):**

1. **Page Load:** `populatePlayHeadshots()` runs on `court.html` page load (all timeout navigation entry points)

2. **Fetch Play Documents:** For each of the 6 offensive plays, fetches the play document from `/api/play/{play_name}`

3. **Determine Play Type:**
   - Checks `play.play_type` to determine if it's a Motion play or Set Play
   - Uses different logic based on play type

4. **Set Plays - Extract Intended Shooter from Skeleton:**
   - Gets the successful skeleton from `play.skeletons.successful` (same as backend: `get_hco_skeleton(None, game, lean_score=1.0)`)
   - Extracts intended shooter position from the final step's `pos_actions` where `action == "shoot"`
   - Uses the same logic as backend `phase_resolution.py` (lines 1011-1017)

5. **Motion Plays - Analyze Steps 1-10 for Most Likely Shooter:**
   - Gets the `base_loop` skeleton from `play.skeletons.base_loop`
   - Analyzes steps 1-10 (excluding step 0) to count shot opportunities for each player
   - **Inside Shots:** Player with most opportunities to take inside shot:
     - Counts when player handles ball at inside spot (lower lowPost, lower midPost, midLane, basketSpot, upper lowPost, upper midPost)
     - Counts when player is at inside spot AND there's a ball handler in the same step (matches backend `_check_inside_shot_possibility` logic)
       - Backend doesn't require specific action - just checks if player is at inside location
       - Frontend checks if ball handler exists in step, then counts any player at inside location regardless of action (stationary, cut, post_up, receive, etc.)
   - **Outside/Attack Shots:** Player who handles ball at outside shot spot the most:
     - Counts when player handles ball at any non-inside location
     - Same player image used for both Outside and Attack (since outside spots are also attack-possible spots)
   - If tie between players, chooses randomly
   - Uses `data-focus` attribute from play option to determine which shot type to analyze

6. **Map Position to Player ID:**
   - Reads user's lineup from URL parameters (preserved by `TimeoutNavigationHelper`)
   - Maps the shooter position (C, PG, SG, SF, PF) to the corresponding player ID from the lineup
   - Uses `my_team` parameter to determine which lineup to use (home or away)

7. **Set Image:** Sets the headshot image using the player ID: `/static/images/players/{playerId}.png`

**Key Points:**
- Images assigned on page load for all timeout navigation entry points
- **Set Plays:** Uses actual intended shooter from successful skeleton (not hardcoded focus-to-position mapping)
- **Motion Plays:** Uses statistical analysis of steps 1-10 to find most likely shooter for each shot type
- **Inside Pass Detection:** Matches backend `_check_inside_shot_possibility` logic - counts any player at inside location if ball handler exists in step (regardless of action)
- Matches backend logic for Set Plays and Motion inside pass opportunities
- Uses lineup data from URL parameters (preserved by `TimeoutNavigationHelper`)
- Images remain static during gameplay (no mid-game changes)
- Function is async to handle API calls to fetch play documents
- Location: `FrontEnd/static/court.html` `populatePlayHeadshots()` function (lines 2546-2750)

**Why This Is SS&S:**
- **Single Source of Truth:** Uses the same skeleton data as the backend
- **Set Plays:** Uses intended shooter from successful skeleton (matches backend and playcall popup)
- **Motion Plays:** Uses actual skeleton analysis to determine most likely shooter (reflects dynamic nature of Motion offense)
- **Consistency:** Images set once at timeout navigation return, remain stable during gameplay
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
    - Checks `turnData.offense_override_cleared === true` to un-highlight offense button
    - Reads `turnData.defense_aggression_call` (not `turnData.aggression`) for defense status display
  - `clearPlaycallHighlights()`: Removes `selected` class from all override buttons
  - `resetLeanMeter()`: Resets meter to neutral
  - `animateLeanMeter()`: Animates meter based on lean score
  - `parseLeanScoreFromText()`: Extracts lean score from turn text
- `FrontEnd/static/js/phaser/utils/playcallDisplay.js`: Playcall Center playcall name display
  - `updatePlaycallDisplay()`: Updates playcall names in Playcall Center (offensive-playcall and defensive-playcall elements)
    - Reads `turnData.offensive_playcall` or `turnData.current_playcall` for full playcall name (e.g., "3-2 Motion")
    - Displays full playcall name from database, not just play type ("Motion" or "Set")
    - Falls back to `offensivePlayType` if playcall name is not available
    - For Motion plays, displays the actual play name (e.g., "3-2 Motion") instead of just "Motion"
- `FrontEnd/static/court.html`:
  - `setPlaycallOverride()` function (lines 2697-2752): Sends override requests to backend
    - Only sends the field being changed (not all fields with nulls)
    - Example: `{offense_override: "4-1 Motion"}` instead of all three override fields
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`: Prepares lean meter animation (lines 66-87)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`: Triggers animation for non-shot turns (lines 1813-1823)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`: Triggers animation for shot turns (lines 324-340)

**Backend:**
- `BackEnd/api/api.py`:
  - `/api/set-playcall-override` endpoint (lines 1736-1840): Receives and stores user overrides
    - Only processes fields explicitly provided in request body (prevents accidental clearing)
    - Uses `provided_fields = set(body.keys())` to track which fields were sent
    - Sets `offense_call`, `defense_call`, or `aggression_override` in `team.strategy_calls`
  - `PlaycallOverrideRequest` model (lines 119-127): Request structure for overrides
- `BackEnd/models/turn_manager.py`:
  - `set_playcalls()` (lines 787-1155): Checks and applies user overrides during playcall selection
    - Uses `game_state["user_team_side"]` to determine user team (not `is_user_team` flag)
    - Returns `offense_override_cleared: True` when override is used and cleared
    - Clears `offense_call` after use, but NOT `defense_call` (persistent)
  - `set_strategy_calls()` (lines 1150-1237): Generates strategy calls for turn
    - Applies `aggression_override` to `defense_team.strategy_calls["aggression_call"]`
    - Does NOT clear `aggression_override` after use (persistent)
  - `run_micro_turn()` (line 288+): Initializes `result["offense_override_cleared"] = False` at turn start
    - Sets flag from `calls.get("offense_override_cleared", False)` for HCO turns
- `BackEnd/models/team_manager.py`:
  - `TeamManager.__init__()` (lines 50-58): Initializes `strategy_calls` structure
- `BackEnd/models/game_manager.py`:
  - `GameManager.__init__()`: Stores `user_team_side` in `game_state["user_team_side"]`
- `BackEnd/utils/shared.py`:
  - `summarize_game_state()`: Includes `user_team_side` in saved game state for database persistence
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

## Playbooks Page ✅ **IMPLEMENTED** (January 2025)

### Overview

The Playbooks page allows users to configure their team's offensive and defensive playcall distributions and priority assignments. Users set percentage distributions for each play type and assign priority slots 1-6 to specific plays.

**Location:** `FrontEnd/static/playbooks.html`  
**Purpose:** Configure playcall percentages and priority assignments for offense and defense  
**Status:** ✅ Backend integration complete - loads plays from database

### Layout Structure

**Desktop Grid Layout:**
- **2-column grid** (4 equal columns total, each section spans 2 columns)
- **Column 1-2:** Offense Play Calls (spans 2 columns, 50% width)
- **Column 3-4:** Defense Play Calls (spans 2 columns, 50% width)

**Header Row:**
- **Left:** Page title "Playbooks"
- **Right:** Submit button with helper text

### Six Percentage Sections

Each section contains multiple rows with numeric percentage inputs (0-100) and must total exactly 100%:

**Offense Sections:**
1. **Motion Offense** - 6 slots (loads from database, fills empty slots with "To Be Added")
2. **Set Play Inside Offense** - 2 slots (loads from database, fills empty slots with "To Be Added")
3. **Set Play Attack Offense** - 2 slots (loads from database, fills empty slots with "To Be Added")
4. **Set Play Outside Offense** - 2 slots (loads from database, fills empty slots with "To Be Added")

**Defense Sections:**
5. **Man Defense** - 3 plays (Man Defense, Man Defense Variant 2, Man Defense Variant 3)
6. **Zone Defense** - 5 plays (2-3 Zone, 3-2 Zone, 1-3-1 Zone, Zone Variant 4, Zone Variant 5)

**Validation Rules:**
- Each section displays live total (e.g., "Total: 100%")
- If user edit would push section over 100%, change is prevented/reverted
- Inline error message: "This section must total 100%. You're over by X%."
- Warning state (subtle color + helper text) when section total ≠ 100%
- Submit button disabled unless ALL six sections total exactly 100%

### Default Values (First-Time User)

**If no saved settings exist:**
- Top row in each section = 100%
- All other rows = 0%
- Motion dropdowns default to "-" (explicit unselected state - user must select Inside/Attack/Outside)

### Submit Button

**Location:** Top-right of page header  
**Styling:** Orange button (`#ff7a00`)  
**Behavior:**
- **Enabled:** Only when ALL six section totals == 100%
- **Disabled:** When any section total != 100%
  - Reduced opacity (0.5)
  - Disabled pointer events
  - Helper text displayed: "All sections must total 100% to submit."
- **On Click (when enabled):**
  - Runs final validation
  - Saves UI state to localStorage (for UI persistence)
  - Saves playbook percentages to database via `POST /api/playbooks`
  - Shows success toast notification ("Playbooks saved successfully")
  - On error, shows error toast with details

**Save Process:**
1. Extracts percentages from state (excludes "To Be Added" plays)
2. Builds request with mode, team_id, and mode-specific ID (game_id/tournament_id/franchise_id)
3. Falls back to localStorage for game_id if not in URL (single mode)
4. Validates required parameters before sending
5. Backend resolves team_id (name to ID) and ensures team objects exist
6. Saves to `teams.{team_id}.playbook_settings` in appropriate mode document

### Back Button

**Location:** Top-right of page header (next to Submit button)  
**Styling:** Blue button (`#4a90e2`)  
**Behavior:**
- **Navigation Logic:**
  - If `from=command_center` parameter exists:
    - Tournament mode → `/static/tournament.html`
    - Franchise mode → `/static/franchise-command-center.html`
  - Otherwise, tries to use `document.referrer` if it's a game-plan URL
  - Falls back to game-plan.html with current mode parameters
- **Purpose:** Returns user to the page they came from (Game Plan, Tournament Command Center, or Franchise Command Center)

### Database Integration

**API Endpoint:** `GET /api/playbooks`

**Query Parameters:**
- `mode` (required): `"single"`, `"tournament"`, or `"franchise"`
- `team_id` (required): Team ID
- `game_id` (conditional): Required if mode is `"single"`
- `tournament_id` (conditional): Required if mode is `"tournament"`
- `franchise_id` (conditional): Required if mode is `"franchise"`

**Response:**
```json
{
  "motion": [
    { "name": "3-2 Motion", "play_id": "...", "play_type": "motion", "play_focus": "attack" },
    ...
  ],
  "set_play_inside": [
    { "name": "Base Post Play", "play_id": "...", "play_type": "set_play", "play_focus": "inside" },
    ...
  ],
  "set_play_attack": [...],
  "set_play_outside": [...]
}
```

**Data Source:**
- Plays are loaded from `teams.{team_id}.plays` in the appropriate mode document:
  - **Single Game:** `games_collection` → `game_doc.teams.{team_id}.plays`
  - **Tournament:** `tournaments_collection` → `tournament_doc.teams.{team_id}.plays`
  - **Franchise:** `franchises_collection` → `franchise_doc.teams.{team_id}.plays`

**Play Loading:**
- Frontend loads plays from API on page initialization
- Plays are filtered by `play_type` (motion vs set_play) and `play_focus` (inside/attack/outside)
- Empty slots are filled with "To Be Added" placeholders (disabled for interaction)

**Team ID Resolution (SS&S - ObjectId Standardization):**
- **✅ Standardized Pattern (January 2025):** All navigation now uses `team_id` (ObjectId string) as the consistent anchor for seamless page-to-page transitions.
  
- **Frontend Resolution:**
  - **Command Center Entry:** Resolves team name to ObjectId once on page load, stores in `userTeamId` variable and localStorage
  - **URL Parameters:** All navigation URLs pass `team_id` (ObjectId) instead of team name
  - **Fallback Chain:** Functions use this consistent pattern:
    1. Primary: `team_id` parameter (ObjectId)
    2. Fallback 1: `user_team_id` parameter (ObjectId, used by Game Plan page)
    3. Fallback 2: `home_id` parameter (ObjectId)
    4. Fallback 3: `away_id` parameter (ObjectId)
  - This ensures consistency across all navigation paths (Command Center → Game Plan → Playbooks → Play Details → Court → Training → Training Report)
  
- **Backend Resolution:**
  - **Prefer ObjectId:** All endpoints (`/api/gameplan`, `/api/playbooks`, `/franchise/team-data`, `/tournament/team-data`) now prefer `team_id` (ObjectId) parameter
  - **Backward Compatibility:** Endpoints still accept `team_name` for backward compatibility, but ObjectId is preferred
  - **Direct Database Access:** When ObjectId is provided, backend uses it directly as database key (no resolution needed)
  
- **Benefits:**
  - **Consistent Navigation:** Same identifier format across all pages
  - **No Resolution Overhead:** Backend uses ObjectId directly as database key
  - **Data Persistence:** Settings save/load using same key format
  - **Experience Continuity:** User's team context preserved across all navigation
  
- **Roster Viewing Pattern:**
  - **User's Team:** `team_id` (ObjectId) represents user's team (for navigation context)
  - **Viewed Team:** `view_team_id` (ObjectId) represents team being viewed (read-only display)
  - **Clear Separation:** User context (`team_id`) vs. display (`view_team_id`) prevents navigation confusion
  - **Future-Proof:** Pattern scales to viewing any team (opponents, league teams, etc.) without breaking navigation
  
- **Backend:** The API endpoint (`GET /api/playbooks`) performs team name resolution for backward compatibility, but prefers ObjectId:
  - **Single Game/Tournament Mode:** Resolves team names to team_id by:
    1. Direct lookup in document's `teams` collection
    2. Iterating through teams to match by name
    3. Looking up in `teams` collection by name and matching back to document
  - **Franchise Mode:** Uses the same team name resolution logic:
    1. Direct lookup in document's `franchise_teams` collection
    2. Iterating through `franchise_teams` to match by name
    3. Looking up in `teams` collection by name and matching back to document
  - This ensures that team names (e.g., "Morristown") passed from the frontend are correctly resolved to the actual `team_id` used in the document structure

**Game Completion Navigation Anchor Preservation (SS&S - January 2025):**
- **✅ Complete Navigation Anchor Set:** When a game completes, the completion popup preserves all three navigation parameters:
  1. **`mode`** (franchise/tournament/single) - Which collection/endpoints to use
  2. **`doc_id`** (franchise_id/tournament_id) - Which document within that collection
  3. **`team_id`** (ObjectId string) - Which team within that document (user's team)
  
- **Implementation Flow:**
  - **`bootGame.js`:** Reads `team_id` from URL params (or `home_id`/`away_id` fallback), passes to game scene via `sceneData`
  - **`gameScene.js`:** Stores `teamId` from scene data, passes it to completion popup when game ends
  - **`gameCompletionPopup.js`:** Constructs command center URLs with complete navigation anchor set:
    ```javascript
    // Tournament mode example
    const params = new URLSearchParams();
    if (tournamentId) params.set('tournament_id', tournamentId);
    if (teamId) params.set('team_id', teamId);  // ✅ Preserve navigation anchor
    lockerRoomUrl = `/static/tournament.html?${params.toString()}`;
    ```
  
- **Benefits:**
  - **No Fallback Needed:** Prevents fallback to `/tournament/active?user_team_id=...` which requires ObjectId serialization
  - **Complete Context:** All three navigation parameters preserved for seamless return to command center
  - **Consistent Pattern:** Matches navigation anchor preservation pattern used throughout the application
  
- **Backend ObjectId Serialization:**
  - **`/tournament/active` endpoint:** Now serializes all ObjectIds in nested structures using `jsonable_encoder(doc, custom_encoder={ObjectId: str})`
  - **Consistent with `/tournament/state`:** Both endpoints use the same serialization pattern
  - **Prevents 500 Errors:** Ensures nested ObjectIds (e.g., in `teams` collection) are properly serialized for JSON response

### Persistence Layer

**Current Implementation:**
- **UI State:** localStorage (`gob_playbooks` key) - for UI state persistence
- **Playbook Settings:** ✅ Database storage via `POST /api/playbooks` - saves percentages to team documents

**Game Initialization and Playbook Settings Persistence:**
- When a game is initialized via `/api/init-game`, the game document is created with `mode`, `tournament_id` (for tournament mode), or `franchise_id` (for franchise mode) fields
- These fields are set on the game document at initialization time (not just at game completion) to ensure playbook settings can be loaded during active gameplay
- **Update (January 2025):** `tournament_id` and `mode` are now also set during `simulate_quarter_endpoint()` saves, ensuring they are always present in game documents regardless of game creation path (matches Franchise mode pattern where `franchise_id` and `week` are always set during saves)
- **Frontend:** `set-lineup.js` passes `mode`, `tournament_id`, and `franchise_id` (when available) to `/api/init-game`
- **Backend:** `/api/init-game` stores these fields on the game document:
  - `mode`: "single", "tournament", or "franchise"
  - `tournament_id`: Set if `mode === "tournament"` (string format)
  - `franchise_id`: Set if `mode === "franchise"` (string format)
- **During Gameplay:** `_load_playbook_settings()` in `turn_manager.py` uses these fields to:
  1. Check the game document for `mode` and `tournament_id`/`franchise_id`
  2. Load the appropriate tournament/franchise document
  3. Retrieve `playbook_settings` from `teams.{team_id}.playbook_settings` (or `franchise_teams.{team_id}.playbook_settings` for franchise mode)
- This ensures that playbook settings submitted from the Command Center (Tournament or Franchise) persist and are used when playing games in those modes

**API Endpoints:**
- `GET /api/playbooks` - Loads plays from database (organized by type and focus)
  - Resolves team names to team_id automatically
  - Returns plays organized by motion, set_play_inside, set_play_attack, set_play_outside
  - **Single Game Mode:** Handles both string and ObjectId formats for game_id
    - First attempts lookup with game_id as string
    - Falls back to ObjectId conversion if string lookup fails
    - This supports both UUID strings and MongoDB ObjectId formats
  - **Tournament/Franchise Mode:** Uses ObjectId for document lookup
  - Ensures team objects exist before loading plays (creates with defaults if missing)
  - Reloads document after ensuring team objects to get updated data
- `POST /api/playbooks` - Saves playbook settings (percentages) to `teams.{team_id}.playbook_settings` (or `franchise_teams.{team_id}.playbook_settings` for franchise mode)
  - Request body: `{ mode, team_id, game_id/tournament_id/franchise_id, playbook_settings }`
  - Resolves team names to team_id automatically for all modes (single, tournament, franchise)
  - **Franchise Mode:** Uses the same team name resolution logic as GET endpoint:
    1. Direct lookup in document's `franchise_teams` collection
    2. Iterating through `franchise_teams` to match by name
    3. Looking up in `teams` collection by name and matching back to document
  - Ensures team objects exist before saving
  - Validates required parameters based on mode
  - **Single Game Mode:** Handles both string and ObjectId formats for game_id
    - First attempts update with game_id as string
    - Falls back to ObjectId conversion if string update fails (matched_count == 0)
    - This supports both UUID strings and MongoDB ObjectId formats
  - **Tournament/Franchise Mode:** Uses ObjectId for document lookup
  - Includes detailed logging for team_id resolution and document operations

**Storage Structure:**
```javascript
teams.{team_id}.playbook_settings = {
  "motion": {
    "3-2 Motion": 20,
    "4-1 Motion": 30,
    "5-0 Motion": 50
  },
  "set_play_inside": {
    "Base Post Play": 100
  },
  "set_play_attack": {...},
  "set_play_outside": {...},
  "zone_defense": {
    "2-3 Zone": 40,
    "3-2 Zone": 35,
    "1-3-1 Zone": 25
  }
}
```

**Persistence Interface (`PlaybooksPersistence` class):**
- `load()` - Loads UI state from localStorage
- `save(data)` - Saves UI state to localStorage
- `savePlaybookSettings()` - Saves playbook percentages to database via API

**Data Serialization:**
```javascript
{
  sections: {
    motion: { [playId]: { percentage: number, slot: number | null } },
    'set-play-inside': { [playId]: { percentage: number, slot: number | null } },
    // ... other sections
  },
  slotAssignments: {
    [slotNumber]: { section: string, playId: string, dropdown?: string }
  },
  motionDropdowns: { [playId]: 'Inside' | 'Attack' | 'Outside' }
}
```

### Motion Offense Dropdowns

**Behavior:**
- Each Motion row includes dropdown with options: **- / Inside / Attack / Outside**
- **Default State:** Dropdown defaults to **"-"** (explicit unselected state)
  - Users must explicitly select "Inside", "Attack", or "Outside"
  - Makes it clear when a selection has been made vs. default state
- **Persistence:** Selection persists when changed (stored in `motionDropdowns` state)
  - Dropdown value is updated immediately in UI when changed
  - State is saved to localStorage and synced to database
- **Default Preservation:** When loading persisted state, defaults are merged with saved values (not overwritten)
  - Ensures new Motion plays always default to "-" even after loading persisted state
  - Saved user selections take precedence, but defaults remain for plays without saved values
  - All motion plays are initialized with "-" if no value exists
- **Display:** Dropdown shows current selection immediately when changed

**Integration with Slot Assignment:**
- Motion slot assignments are keyed by dropdown variant
- Example: "5-0 Motion (Inside)" and "5-0 Motion (Attack)" are separate assignable targets
- Slot assignment key format: `motion:${playId}:${dropdown}`

**Integration with Playcall Center:**
- Slot assignments (1-6) determine the order of plays in the Playcall Center
- Slot 1 = First play displayed in Playcall Center (shown by default on page load)
- Slot 2 = Second play, etc.
- Navigation buttons respect slot order:
  - **Up button (▲)**: Navigates to previous slot (1→2→3→4→5→6, wraps to 6)
  - **Down button (▼)**: Navigates to next slot (6→5→4→3→2→1, wraps to 1)
- Plays are automatically reordered when slot assignments are loaded from playbooks
- Unassigned plays appear at the end (after slots 1-6)
- **Loading Implementation:**
  - `loadAndApplySlotAssignments()` function in `court.html` loads slot assignments on page load
  - Fetches from `GET /api/playbooks` endpoint with mode, team_id, and mode-specific ID
  - **Team ID Resolution:** Checks multiple URL parameters in order:
    1. `team_id` (primary)
    2. `user_team_id` (used by Game Plan page)
    3. `home_id` (fallback)
    4. `away_id` (fallback)
  - Maps frontend playIds (like "motion-1") to play names from API response
  - Matches plays by name and focus (for Motion plays, also matches dropdown variant)
  - Reorders DOM elements based on slot assignments (1-6)
  - Dispatches `playcall-center-reordered` event when complete
  - Navigation code listens for event and updates play options/show first play
  - **Event-Based Synchronization:** Prevents race conditions where navigation might show wrong play before reordering completes

### Priority Slots 1-6 (Offense Only)

**Location:** Right column of every Motion and Set Play row  
**Alignment:** Single vertical column of 6 slot controls (aligned across all rows)

**Rules:**
- Each slot number (1-6) can be assigned only **once** across ALL offense play call rows
- If Slot 1 is assigned to one row and user assigns Slot 1 to another row, it auto-unassigns from first and assigns to second
- **Motion Complication:** Slot assignments must support dropdown variants
  - Users can assign Slot 1 to "Motion (Inside)", Slot 2 to "Motion (Attack)", Slot 3 to "Motion (Outside)"
  - Motion slot assignments tracked as distinct targets: `(motionRowId + selectedDropdownFocus)`

**Slot UI/UX:**
- Each slot rendered as small toggle "pill/chip" control
- **When assigned:**
  - **Set Plays:** Normal selected styling (gold background)
  - **Motion:** Selected styling + small badge indicating I/A/O (derived from assigned dropdown variant)
- **Badge Colors:**
  - **Inside (I):** Blue (`#4a90e2`)
  - **Attack (A):** Orange (`#ff7a00`)
  - **Outside (O):** Green (`#4caf50`)
- All slot controls aligned vertically for consistent column reading

**Slot Persistence:**
- Slots remain assigned when dropdown changes
- Example: If Slot 1 is assigned to "5-0 Motion (Inside)" and user changes dropdown to "Attack", checkbox stays highlighted with "I" badge (showing it's still assigned to Inside variant)
- Badge shows the **assigned** dropdown variant, not the current dropdown selection

### Assigned Plays 1-6 List

**Location:** Bottom of Offense column  
**Structure:** Simple 6-row list (rows labeled 1-6)

**Display Format:**
- Each row shows: `"Slot Number: Play Name (Focus)"`
- **Motion examples:**
  - `"1: 5-0 Motion (Inside)"`
  - `"2: 4-1 Motion (Outside)"`
- **Set Play examples:**
  - `"3: Base Post Play (Inside)"`
  - `"4: Pick & Roll (Lower Wing) (Attack)"`
- **Unassigned:** Shows `"Unassigned"` in muted/italic text

**Behavior:**
- Updates live as slot assignments change
- Reflects current state of all 6 slot assignments
- Format: `"Play Name (Focus)"` where Focus is:
  - For Motion: The dropdown variant (Inside/Attack/Outside)
  - For Set Plays: The section focus (Inside/Attack/Outside)

### State Model

**Clean state shape supporting:**
- Six independent section totals + validation state
- Slot uniqueness across offense (enforced via `slotAssignments` object)
- Motion slot assignment keyed by dropdown focus
- Easy serialization/deserialization to save payload

**State Structure (`PlaybooksState` class):**
```javascript
{
  sections: {
    [sectionKey]: {
      [playId]: {
        percentage: number,
        slot: number | null  // For set plays only
      }
    }
  },
  slotAssignments: {
    [slotNumber]: {
      section: string,
      playId: string,
      dropdown?: string  // For motion plays
    }
  },
  motionDropdowns: {
    [playId]: 'Inside' | 'Attack' | 'Outside'
  }
}
```

### Visual and Interaction Quality

**Typography Hierarchy:**
- Page title: 2.5rem, gold color (`#FFD700`)
- Section titles: 1.125rem, white
- Row labels: 0.9375rem, white
- Helper text: 0.875rem, muted white

**Input Alignment:**
- Labels left-aligned
- Inputs right-aligned
- Totals consistent positioning

**Error Handling:**
- Inline section-level error messages (avoid global error dumps)
- Warning states with subtle color changes
- Fast and predictable editing experience (no jank)

**Accessibility:**
- Keyboard navigation support
- Focus states on all interactive elements
- Readable contrast ratios
- ARIA labels where appropriate

### Key Files

**Frontend:**
- `FrontEnd/static/playbooks.html` - Main page structure
- `FrontEnd/static/playbooks.css` - Styling and layout
- `FrontEnd/static/playbooks.js` - State management, validation, and UI logic

**Key Classes:**
- `PlaybooksState` - State management and validation
- `PlaybooksPersistence` - Load/save interface (localStorage + API ready)
- `PlaybooksUI` - UI controller and rendering logic

### Implementation Details

**Backend Files:**
- `BackEnd/api/gameplan_routes.py` - Contains `/api/playbooks` endpoint
- `BackEnd/api/api.py` - Router registration

**Frontend Files:**
- `FrontEnd/static/playbooks.html` - Page structure
- `FrontEnd/static/playbooks.css` - Styling
- `FrontEnd/static/playbooks.js` - State management and API integration

**Key Features:**
- ✅ Loads plays dynamically from database based on game mode
- ✅ Supports 6 motion offense slots (fills with "To Be Added" if needed)
- ✅ Supports 2 slots per Set Play focus (fills with "To Be Added" if needed)
- ✅ "To Be Added" placeholders are disabled (no percentage input, no slot assignment)
- ✅ Mode-aware: Works with single game, tournament, and franchise modes
- ✅ Back button with smart navigation to return to previous page
- ✅ Save functionality with error handling and validation

**Navigation Entry Points:**
- **Game Plan Screen:** Playbooks button links to playbooks.html with mode, team_id, and mode-specific ID
  - **Team ID Resolution (Multiple Fallbacks):**
    1. Primary: `teamId` (derived from `myTeamSide` - `homeId` or `awayId`)
    2. Fallback 1: `userTeamIdParam` (from URL parameter)
    3. Fallback 2: `homeId` or `awayId` (direct from URL parameters)
  - **Additional Parameters:**
    - Also passes `home_id` and `away_id` as fallbacks in URL for playbooks.js to use
    - Falls back to localStorage for `game_id` if not in URL (single mode)
    - Includes debug logging (`🔍 [GAME-PLAN] Navigating to playbooks with params:`) for troubleshooting
  - **Location:** `FrontEnd/static/game-plan.js` - `btnPlaybooks` click handler
- **Tournament Command Center:** Playbooks button links to playbooks.html with tournament_id and team_id
  - **Location:** `FrontEnd/static/tournament.js` - `playbooks-tournament` button handler
- **Franchise Command Center:** Playbooks button links to playbooks.html with franchise_id and team_id
  - **Location:** `FrontEnd/static/franchise-command-center.js` - `playbooks-franchise` button handler

### Game Engine Integration

**✅ Implemented:**
- Playbook percentages are used for weighted random selection when choosing plays
- Motion plays: Uses percentages from `playbook_settings.motion`
- Set plays: Uses percentages from `playbook_settings.set_play_{focus}` (inside/attack/outside)
- Zone defense: Uses percentages from `playbook_settings.zone_defense`
- "To Be Added" plays are excluded from selection
- CPU teams use equal weights (playbook settings only apply to user teams)
- Falls back to equal weights if no playbook settings exist

**Selection Logic:**
- When `set_playcalls()` is called, it loads playbook settings from the team document
- Uses `weighted_random_from_dict()` to select plays based on percentages
- Man defense: Currently only one option ("Man"), so no weighting needed

### Future Enhancements

**Pending:**
- Link priority slots (1-6) to playcall selection order
- Support custom plays (user-created plays per team)
- Motion dropdown focus integration (currently only used for Playcall Center display)

---

## Plays Page System ✅ **IMPLEMENTED** (February 2025)

### Overview

The Plays Page System provides detailed views for individual plays, allowing users to see play animations and information. Each play has its own dedicated page that displays the play's animation and descriptive content.

**Location:** `FrontEnd/static/play-details.html`  
**Purpose:** Display play details, animations, and information  
**Status:** ✅ Fully implemented with auto-animating play visualization

### Navigation

**Entry Point:**
- Play names in the Playbooks page are clickable links (except "To Be Added" placeholders)
- Clicking a play name navigates to `/static/play-details.html` with:
  - `play_name` parameter (URL encoded)
  - All context parameters (mode, team_id, game_id/tournament_id/franchise_id)
  - Preserves navigation context for back button functionality

**Back Navigation:**
- Back button (top-left) returns to Playbooks page
- Reconstructs Playbooks URL with all original parameters
- Maintains user's context across navigation

### Layout Structure

**Header:**
- **Play Name:** Centered, large gold font (2.5rem), with text shadow
- **Play Type:** Centered, smaller font (1.2rem), muted color (Motion or Set Play)

**2-Column Layout:**
- **Left Column (50% width):**
  - Three horizontal info containers
  - Each container has:
    - Title (gold color, 1.1rem)
    - Content area (placeholder "Copy Goes Here" for future content)
  - Containers are vertically centered as a unit, middle-aligned with animation container
  - Containers: "Play Description", "Key Concepts", "Usage Tips"
  
- **Right Column (50% width):**
  - Court animation container
  - Same dimensions and styling as Play Builder v2 animation container
  - Centered horizontally and vertically within its column
  - Uses same court image: `/static/images/courts/bentley_truman.jpg`

### Animation System

**Auto-Start Behavior:**
- Animation begins automatically on page load
- No user interaction required
- Fetches play data from `/api/play/{play_name}` endpoint
- Loads appropriate skeleton based on play type:
  - **Motion Plays:** Uses `base_loop` skeleton
  - **Set Plays:** Uses `successful` skeleton

**Animation Controls:**
- **Pause/Resume Button:** Located below the animation container, horizontally centered
- Button text changes: "⏸️ Pause" when playing, "▶️ Resume" when paused
- Button styling changes: Blue gradient when playing, green gradient when paused
- Clicking pauses/resumes the animation at the current step
- Animation state persists when paused (can resume from same step)

**Animation Logic:**
- Reuses animation system from Play Builder v2:
  - Same constants (court coordinates, positions, ball-handling actions)
  - Same rendering logic (`renderCourtVisualization()`)
  - Same step-by-step animation (`animateNextStep()`)
  - Player icons positioned using percentage-based coordinates
  - Ball sprite follows ball handler or pass/shoot actions
  - Smooth transitions between steps (1 second delay per step)

**Motion Play Animation:**
- Continuous loop behavior
- When reaching final step (marked with `is_final_step: true`), loops back to step 0
- If no final step marked, loops back to step 0 when reaching end of steps
- Runs indefinitely until page is closed

**Set Play Animation:**
- Runs animation from start to finish
- Pauses for 2 seconds after completion
- Restarts from step 0
- Repeats continuously

**Player Rendering:**
- Player icons positioned at court locations based on skeleton step data
- Icons animate smoothly between positions using CSS transitions
- Ball sprite follows ball handler or shows pass/shoot animations
- Position offsets applied for screen actions (collision handling)

### Data Flow

**Page Load:**
1. Extract `play_name` from URL parameters
2. Fetch play data from `/api/play/{play_name}` endpoint
3. Display play name and type in header
4. Load skeleton data (Motion: `base_loop`, Set Play: `successful`)
5. Initialize animation state
6. Auto-start animation

**Animation Loop:**
1. Process current step's `pos_actions` data
2. Update player positions and actions
3. Render court visualization with player icons and ball
4. Move to next step after 1 second delay
5. Handle looping logic (Motion: loop to 0, Set Play: pause then restart)

### Responsive Design

**Desktop:**
- 2-column grid layout
- All content fits above the fold
- Left column containers vertically centered
- Animation container centered in right column

**Mobile/Tablet:**
- Stacks vertically (right column first, then left column)
- Animation container remains full width
- Info containers stack below animation
- Maintains readability and usability

### Key Files

**Frontend:**
- `FrontEnd/static/play-details.html` - Main page structure and animation logic
- `FrontEnd/static/playbooks.js` - Navigation integration (clickable play names)

**Key Features:**
- ✅ Auto-starting animation on page load
- ✅ Motion play continuous loop
- ✅ Set play pause-and-restart behavior
- ✅ Smooth player and ball animations
- ✅ Pause/Resume button for animation control
- ✅ Team-specific court images and player icon colors
- ✅ Responsive layout (desktop-first, mobile-friendly)
- ✅ Back navigation with context preservation
- ✅ Three info containers ready for content (placeholder text)

### Future Enhancements

**Pending:**
- Populate info containers with actual play descriptions, concepts, and tips
- Add play statistics (usage rate, success rate, etc.)
- Add variant selector for Set Plays (successful, mid_play_change, contested, broken)
- Add animation controls (play/pause, speed adjustment)
- Add step-by-step navigation (previous/next step buttons)

---

## Training System ✅ **COMPLETE** (January 2025)

### Overview

The Training System provides a comprehensive interface for allocating training points across various drills and exercises to improve player and team performance. Users can allocate 24 training points across different categories, select a coaching focus style, and view detailed training reports showing attribute changes.

**Location:** `FrontEnd/static/training.html`, `FrontEnd/static/training-report.html`  
**Status:** ✅ **COMPLETE** - UI/UX and backend integration fully implemented

### Page Layout

**Desktop-only page** using a 4-column grid layout. All content fits above the fold at common desktop resolutions.

**Header Section (Sticky on Scroll):**
- Centered page title: "TEAM TRAINING"
- Points Remaining display: "POINTS REMAINING: 24" (dynamic)
- Back button (blue, upper-left corner)
- Submit Training button (orange, upper-right corner)
- Horizontal line below Points Remaining

**Main Content Layout:**

**Left Half - Player Drills:**
- **Column 1:**
  - Offense Drills (Inside Offense, Outside Offense sliders)
  - Technical Drills (Passing, Ball Handling, Rebounding sliders)
- **Column 2:**
  - Defense Drills (Inside Defense, Outside Defense sliders)
  - Weight Room (Strength, Agility sliders)

**Right Half - Team Drills:**
- **Column 1:**
  - Offense (Offense Install slider)
  - Fast Breaks (FB Offense Install, FB Defense Install sliders, Scrimmages slider)
- **Column 2:**
  - Defense (Defense Install slider)
  - Presses / Traps (P/T Defense Install, P/T Offense Install sliders)
- **Bottom of Team Drills Section:**
  - Playbook Training Mode (radio buttons):
    - Current Playbooks (default)
    - All Plays / Even Distribution
    - Custom

**General Section (Full Width):**
- Four sliders in a 4-column grid:
  - Conditioning
  - Free Throws
  - Film Study
  - Breaks

**Coaching Style / Focus Section (Bottom):**
- Title: "Coaching Style / Focus (choose one)"
- Four archetype blocks displayed horizontally (4 columns):
  - **Authoritarian** (red header fill)
    - Sub-options: Discipline, Rebounding, Execution, Teamwork
  - **Systems Coach** (dark/burnt yellow header fill)
    - Sub-options: Offense, Defense, Fast Breaks, Press / Trap
  - **Player Maximizer** (darker green header fill)
    - Sub-options: Top 3 Attributes, Attributes 4–6, Custom Attributes, Opportunity
  - **Culture Builder** (purple header fill)
    - Sub-options: Inspire, Confidence, Community Engagement, Teamwork

### Slider Behavior

- Each slider has discrete steps from 0 to 5
- Default value for all sliders on page load: 0
- Total available training points = 24
- Moving a slider to value N subtracts N from Points Remaining
- Prevents user from allocating more than 24 total points (clamps or reverts last interaction)
- Points Remaining = 24 - sum(all slider values)

### Coaching Focus Selection

- All radios in the Coaching Focus section are part of ONE global radio group
- Only one selection can be active at a time
- Selecting any archetype header or sub-option clears all others

**Visual Behavior:**
- **Archetype header radio selected:**
  - Entire archetype block gets a highlight outline in the archetype's color
  - Header and all four sub-options appear "active" with neutral grey fill
- **Sub-option radio selected:**
  - Only that radio fills with the archetype's header color
  - Archetype block shows a subtle outline in the same color (more subtle than header selection)

### Submit Button Behavior

- Disabled / visually muted (reduced opacity, non-clickable) until:
  1. All 24 training points are allocated (Points Remaining = 0)
  2. A coaching focus is selected
- Becomes active only when both conditions are met

### Auto-Train Button (New)

- **Button:** “Auto-Train” (header, right side)
- **Behavior when clicked:**
  - Automatically assigns all 24 points across the 20 sliders
    - Sets all 20 sliders to `1`
    - Randomly selects four sliders to set to `2` (total = 24)
  - Randomly selects a Coaching Focus (one of the existing focus radio options)
  - Shows confirmation popup: `Training Points Assigned - {Focus Name} Focus Chosen`
    - Popup has a “Close” button; closing keeps the user on the Training page
  - After auto-assign, Points Remaining = 0 and Submit becomes eligible (provided focus set by auto-train)
- **Files:** `FrontEnd/static/training.html`, `FrontEnd/static/training.js`, `FrontEnd/static/training.css`

### Data Capture

On submit, captures:
- All slider values (organized by category: player_drills, team_drills, general)
- Playbook Training Mode selection (Current Playbooks, All Plays / Even Distribution, or Custom)
- Coaching focus selection (archetype-level or specific sub-option)

### Navigation

**Back Button:**
- Returns to previous page based on mode:
  - Franchise mode → Franchise Command Center
  - Tournament mode → Tournament Command Center
  - Single game mode → Game Plan
- Uses URL parameters to determine navigation path

**Submit Button:**
- Validates all requirements are met
- Sends training data to appropriate endpoint based on mode:
  - Franchise mode → `/franchise/run-training`
  - Tournament mode → `/tournament/run-training` (TODO)
  - Single game mode → `/api/training` (TODO)
- Redirects to training report page after successful submission

---

### Backend Training Execution System

**Location:** `BackEnd/models/training_execution_v2.py`

The training execution system applies pre-training conditions, allocates training points, applies coaching focus amplifiers, and generates training reports.

#### Training Execution Flow

0. **Pre-Training Effectiveness Decay** (`_apply_pre_training_effectiveness_decay`, `_apply_pre_training_defense_decay`)
   - All plays and defenses with effectiveness > 0 are reduced by `random.randint(5, 15)`
   - Minimum effectiveness is clamped to 0 (cannot be negative)
   - This represents natural skill degradation between training sessions
   - Original effectiveness values are tracked for change calculation

1. **Pre-Training Conditions** (`apply_pre_training_conditions`)
   - Applies random decreases to player attributes (excluding EM, MO, NG)
   - Player attributes: `+= random.randint(-2, 0)` per attribute
   - Team attributes: Random decreases based on attribute type
   - Rebound modifier: `+= -0.1 or 0`
   - Shot threshold: `+= random.randint(0, 15)`
   - Other team attributes: `+= random.choice([-2, -1, 0])`

2. **Training Point Application** (`apply_training_points`)
   - Maps drill allocations to player/team attributes
   - Applies random increases based on points allocated
   - Applies coaching focus amplifiers
   - Handles special cases (conditioning, film study, breaks)

3. **Play/Defense Training Application** (placeholder - to be implemented)
   - Updates play effectiveness and momentum based on training allocations
   - Updates defense effectiveness and momentum based on training allocations
   - Uses playbook_training_mode to determine which plays/defenses receive training benefits
   - Considers playcall_settings, strategy_settings, and playbook_settings for weighted distribution

4. **Attribute Clamping**
   - Player attributes: Minimum 1, no maximum
   - Team attributes: Clamped to defined ranges (see brief)

5. **Training Report Generation**
   - Calculates changes from original baselines
   - Returns player_changes and team_changes dictionaries
   - Includes coaching focus information

#### Drill-to-Attribute Mapping

**Player Drills:**
- Inside Offense → SC (Shooting Close)
- Outside Offense → SH (Shooting)
- Inside Defense → ID (Inside Defense)
- Outside Defense → OD (Outside Defense)
- Ball Handling → BH
- Passing → PS
- Rebounding → RB
- Strength Training → ST
- Agility Training → AG
- Free Throws → FT
- Conditioning → ND (Endurance), CH (Chemistry, 0.5x multiplier)
- Film Study → IQ, CH (Chemistry, 0.5x multiplier)

**Team Drills:**
- Offense Install → `offensive_efficiency`
- Defense Install → `defensive_efficiency`
- Fast Break Offense Install → `fb_efficiency`
- Fast Break Defense Install → `fb_opp_modifier`
- P/T Defense Install → `pt_efficiency`
- P/T Offense Install → `pt_opp_modifier`
- Scrimmages → Team Chemistry, Shot Threshold (decreases), Rebound Modifier, NG Reduction (if 3-5 points)

#### Training Point Ranges

**Player Attributes:**
- 1 point: `+= random.randint(1, 3)`
- 2 points: `+= random.randint(2, 5)`
- 3 points: `+= random.randint(3, 7)`
- 4 points: `+= random.randint(3, 8)`
- 5 points: `+= random.randint(3, 9)`

**Team Attributes (standard):**
- 1 point: `+= random.randint(1, 2)`
- 2 points: `+= random.randint(2, 3)`
- 3 points: `+= random.randint(3, 5)`
- 4 points: `+= random.randint(3, 6)`
- 5 points: `+= random.randint(3, 7)`

**Rebound Modifier:**
- 1 point: `+= 0.1 or 0.2`
- 2 points: `+= 0.2 or 0.3`
- 3 points: `+= 0.2, 0.3, or 0.4`
- 4 points: `+= 0.2, 0.3, 0.4, or 0.5`
- 5 points: `+= 0.3, 0.4, or 0.5`

**Shot Threshold:**
- 1 point: `-= random.randint(10, 25)`
- 2 points: `-= random.randint(15, 35)`
- 3 points: `-= random.randint(20, 45)`
- 4 points: `-= random.randint(20, 55)`
- 5 points: `-= random.randint(20, 65)`

#### Coaching Focus Amplifiers

**Authoritarian:**
- Discipline: Amplifies BH, `foul_modifier`, `turnover_modifier`
- Rebounding: Amplifies RB, `rebound_modifier`
- Teamwork: Amplifies PS, Motion Play Effectiveness, Zone Defense Effectiveness
- Execution: Amplifies Set Play Effectiveness, Man Defense Effectiveness

**Systems Coach:**
- Offense: Amplifies `offensive_efficiency` gains, offensive play effectiveness
- Defense: Amplifies `defensive_efficiency` gains, defensive play effectiveness
- Fast Breaks: Amplifies `fb_efficiency` gains, `fb_opp_modifier` gains
- Presses/Traps: Amplifies `pt_efficiency` gains, `pt_opp_modifier` gains

**Player Maximizer:**
- Top 3 Attributes: Amplifies gains to player's top 3 attributes (excluding CH, EM, MO, NG)
- Attributes 4-6: Amplifies gains to player's 4th-6th highest attributes
- Custom: Amplifies gains to user-selected attributes (TODO)
- Be Opportunistic: Improves Set Play and Motion Shot Scores (carried to next game)

**Culture Builder:**
- Inspire: Improves EM, MO by `random.randint(1, 2)`, amplifies Team Chemistry gains
- Community Engagement: Improves EM, affects crowd factors (carried to next game)
- Teamwork: Amplifies Team Chemistry gains, improves Motion Play and Zone Defense Effectiveness
- Build Confidence: Improves Set Play Effectiveness, Man Defense Effectiveness

#### Breaks Effect

The "Breaks" slider applies a multiplier to all positive gains (not losses):
- 0 points: `random.choice([0.85, 0.9, 0.95])`
- 1 point: `random.choice([0.9, 0.95, 1, 1, 1])`
- 2 points: `random.choice([0.95, 1, 1, 1, 1])`
- 3 points: `random.choice([0.9, 0.95, 1])`
- 4 points: `random.choice([0.9, 0.95, 1])` + Team Chemistry `+= random.randint(-1, 1)`
- 5 points: `random.choice([0.9, 0.95, 1])` + Team Chemistry `+= random.randint(-3, 3)`

#### NG Reduction from Scrimmages and Conditioning

When scrimmages or conditioning are allocated 3, 4, or 5 points, players may experience NG (Nerve/Game) reduction, which affects their energy for the next game. These reductions can stack if both scrimmages and conditioning are allocated.

**Scrimmages NG Reduction:**
- **3 points:** `reduce_ng_list = [0, 0.01, 0.01, 0.02]`
- **4 points:** `reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]`
- **5 points:** `reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]`

**Conditioning NG Reduction:**
- **3 points:** `reduce_ng_list = [0, 0.01, 0.01, 0.02]`
- **4 points:** `reduce_ng_list = [0, 0.01, 0.02, 0.02, 0.03]`
- **5 points:** `reduce_ng_list = [0.01, 0.02, 0.03, 0.03, 0.04]`

**Process:**
- For each player, `player.NG -= random.choice(reduce_ng_list)`
- NG is clamped to a minimum of 0.0
- NG is rounded to 2 decimal places

**High Endurance (ND > 79) Special Handling:**
Players with ND (Endurance) greater than 79 receive reduced NG penalties:
- **Scrimmages 3:** Omitted entirely (no NG reduction)
- **Scrimmages 4:** Uses scrimmages 3 reduction list
- **Scrimmages 5:** Uses scrimmages 4 reduction list
- **Conditioning 3:** Omitted entirely (no NG reduction)
- **Conditioning 4:** Uses conditioning 3 reduction list
- **Conditioning 5:** Uses conditioning 4 reduction list

**Training Notes:**
The training report automatically generates notes when players have NG reductions:
- **Multiple players (conditioning):** "Multiple players will start the next game with reduced energy due to the amount of conditioning."
- **Single player (conditioning):** "{player name} will start the next game with reduced energy due to the amount of conditioning."
- **Multiple players (scrimmages):** "Multiple players will start the next game with reduced energy due to the amount of scrimmages."
- **Single player (scrimmages):** "{player name} will start the next game with reduced energy due to the amount of scrimmages."

---

### Training Report Page

**Location:** `FrontEnd/static/training-report.html`

After training is submitted, users are automatically redirected to the training report page which displays detailed information about attribute changes. The report can also be accessed via links on the schedule in the Franchise Command Center.

#### Page Layout

**Header Section:**
- Page title: "TRAINING REPORT"
- Week number
- Upcoming Opponent (from schedule)
- Training Focus (formatted as "Archetype (Sub-Option)", e.g., "Culture Builder (Inspire)")
- Orange "Go To Locker Room" button (top-right) - navigates to Franchise/Tournament Command Center

**Player Report Section:**
- Header: "Player Report"
- Toggle between "Attributes" and "Training Changes" views
- **Attributes View:** Shows current attribute values after training
  - **Attribute Order:** Attributes displayed in exact order: SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO
  - **Attribute Formatting:**
    - **SC through FT (first 12):** Displayed as integer values
    - **NG:** Displayed with 2 decimal places (e.g., 1.00, 0.99, 0.98, 0.90)
    - **EM:** Displayed with emoji based on value:
      - >= 80: 😎 (Sunglasses)
      - >= 60: 😊 (Big smile)
      - >= 40: 😐 (Straight face)
      - >= 20: 😕 (Slight frown)
      - < 20: 😞 (Sad face)
    - **MO:** Displayed with red/green horizontal pill visualization
      - Green fill on right side for positive momentum
      - Red fill on left side for negative momentum
      - Yellow center line at 50%
      - No integer value displayed on top of pill
  - **Tooltip Feature:** Hovering over any attribute value displays the training change for that attribute
    - Green tooltip for positive changes (e.g., "+5")
    - Red tooltip for negative changes (e.g., "-3")
    - Black tooltip for zero changes
    - Tooltip appears above the attribute value
- **Training Changes View:** Shows net changes from training
  - **Attribute Order:** Same exact order as Attributes view (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, NG, EM, MO)
  - Only displays attributes that have changes (maintains order)
  - Positive changes: Green text with `+` prefix
  - Negative changes: Red text with `-` prefix
  - Zero changes: Black text
  - **Aggregated Total Row:** Bottom row displays "Total" in the first column and sums all attribute changes across all players
    - Styled with gold background highlight and bold text
    - Provides quick overview of total training impact
- Displays all players on the team with their attribute values or changes

**Team Report Section:**
- Header: "Team Report"
- Displays all team attributes with visualizations:
  - **Red/Green Pills:** Most attributes (Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum)
    - Yellow center line
    - Green fill to the right for positive values
    - Red fill to the left for negative values
    - Proportional fill based on max value
    - No value displayed on top of pill (value shown in change indicator only)
  - **Progress Bar:** Team Chemistry (0-25 scale, blue fill)
    - Shows value as "X / 25" centered on bar
    - Only attribute that displays its value
  - **+/- Indicators:** Fast Break Defense and Press/Trap Breaks
    - Centered, bold indicators
    - No value displayed next to indicators
    - `+++` (green) for value = 10
    - `++` (green) for values 5-9
    - `+` (green) for values 1-4
    - `-` (yellow) for value = 0
    - `-` (red) for values -1 to -4
    - `--` (red) for values -5 to -9
    - `---` (red) for value = -10

#### Training Focus Display Format

The training focus is formatted as "Archetype (Sub-Option)" with proper capitalization:
- **Authoritarian** archetype options:
  - "Authoritarian (Discipline)"
  - "Authoritarian (Rebounding)"
  - "Authoritarian (Teamwork)"
  - "Authoritarian (Execution)"
- **Systems Coach** archetype options:
  - "Systems Coach (Offense)"
  - "Systems Coach (Defense)"
  - "Systems Coach (Fast Breaks)"
  - "Systems Coach (Presses/Traps)"
- **Player Maximizer** archetype options:
  - "Player Maximizer (Top 3 Attributes)"
  - "Player Maximizer (Attributes 4-6)"
  - "Player Maximizer (Custom)"
  - "Player Maximizer (Be Opportunistic)"
- **Culture Builder** archetype options:
  - "Culture Builder (Inspire)"
  - "Culture Builder (Community Engagement)"
  - "Culture Builder (Teamwork)"
  - "Culture Builder (Build Confidence)"

#### Schedule Integration

Training report links appear next to scheduled games on the Franchise Command Center schedule:
- Link appears only for user's team's games
- Link appears only if training has been completed for that week
- Link styled in blue (#4a90e2) with reduced font size
- Link text: "[Training Report]"
- Navigates to training report page with correct parameters (mode, franchise_id, team_id, week)

**Playbook Summary Section:**
- Header: "Playbook Summary"
- Located between Team Report and Training Notes sections
- Displays all plays and defenses attached to the team object
- **Layout:**
  - **Offense Section:**
    - All Motion Plays (sorted alphabetically)
    - All Set Plays (sorted alphabetically)
    - Empty row separator
  - **Defense Section:**
    - All Man Defense Plays (sorted alphabetically)
    - All Zone Defense Plays (sorted alphabetically)
- **For each play/defense:**
  - Play/defense name (left-aligned, min-width 200px)
  - Horizontal progress bar (max value 500, fills proportionally based on effectiveness score)
  - Change indicator (right-aligned, min-width 60px):
    - **Positive changes:** Green text with "+" prefix (e.g., "+10")
    - **Negative changes:** Red text with "-" prefix (e.g., "-5")
    - **Zero changes:** White text (e.g., "0")
- **Pre-Training Effectiveness Decay:**
  - Before applying training points, all plays and defenses with effectiveness > 0 are reduced by a random value between 5-15
  - Minimum effectiveness value is 0 (cannot be negative)
  - This decay represents natural skill degradation between training sessions
  - The change indicator shows the net change from the original effectiveness (before decay) to the final effectiveness (after decay + training)

**Training Notes Section:**
- Header: "Training Notes"
- Displays automatically generated notes about training effects
- **NG Reduction Notes:** Automatically generated when players experience NG reduction from scrimmages or conditioning
  - Shows message for multiple players or individual player names
  - Notes appear as paragraphs in the container
- **Placeholder:** If no notes are generated, displays "No training notes for this session." in italic gray text
- Same horizontal width as Player Report and Team Report sections
- Dynamic height: Expands automatically with content
- No internal scrolling: All text is always visible

#### API Endpoints

**Training Submission:**
- `POST /franchise/run-training` - Submit training for franchise mode
  - Request: `{franchise_id, team_id?, training_data}`
  - Response: `{status, week, player_changes, team_changes, coaching_focus, redirect}`

**Training Report:**
- `GET /franchise/training-report` - Get training report data
  - **Franchise mode:** Query params: `franchise_id, team_id, week` (week is required)
  - **Tournament mode:** Query params: `tournament_id, team_id, round` (round is optional - backend determines from state if not provided)
  - **SS&S Approach:** Backend determines round from `training_status.round` or `latest_training.round` if not provided in URL
  - Response: `{week, round, upcoming_opponent, coaching_focus, player_changes, team_changes, plays_data, scouting_data, plays_effectiveness_changes, defenses_effectiveness_changes, players, team_attributes, training_notes}`

#### Data Storage

**Franchise Document:**
- `franchise_teams.{team_id}.training_reports.{week}` - Training report for specific week
- `latest_training` - Most recent training report (quick access)
- `training_status.training_completed` - Boolean flag
- `training_status.week` - Week number for last training

**Player Updates:**
- `players.{player_id}.attributes.anchor_{attr}` - Updated attribute values
- `players.{player_id}.position_ratings` - Recalculated position ratings

**Team Updates:**
- `franchise_teams.{team_id}.{attribute_name}` - Updated team attribute values

---

### Key Files

**Frontend:**
- `FrontEnd/static/training.html` - Training allocation page
- `FrontEnd/static/training.css` - Training page styling
- `FrontEnd/static/training.js` - Training logic and submission
- `FrontEnd/static/training-report.html` - Training report display page
- `FrontEnd/static/training-report.css` - Report page styling
- `FrontEnd/static/training-report.js` - Report data loading and rendering
- `FrontEnd/static/franchise-command-center.js` - Schedule rendering with training report links

**Backend:**
- `BackEnd/models/training_execution_v2.py` - Core training execution logic
- `BackEnd/api/franchise_routes.py` - Training API endpoints
  - `POST /franchise/run-training` - Submit training
  - `GET /franchise/training-report` - Get training report data
  - `GET /franchise/schedule` - Get schedule with training report flags

#### Data Flow

1. **Training Submission:**
   - User allocates 24 training points and selects coaching focus on `training.html`
   - Frontend sends POST request to `/franchise/run-training` with training data
   - **Data Initialization (Auto-Population):**
     - If `plays_data` is empty or missing, backend automatically populates it from the universal `plays` collection using `populate_team_plays()`
     - If `scouting_data` is empty or missing the `defense` structure, backend automatically initializes it using `TeamManager._init_scouting_data()`
     - Initialized data is saved to the database before training execution
     - This ensures training works even if game plan or playbooks haven't been submitted yet
   - Backend executes training (pre-conditions, point allocation, clamping)
   - Backend stores training report in `franchise_teams.{team_id}.training_reports.{week}`
   - Backend updates player attributes and team attributes in franchise document
   - Backend returns redirect URL to training report page

2. **Training Report Display:**
   - Frontend loads training report data from `/franchise/training-report` endpoint
   - Backend resolves team_id (handles both name and ID formats)
   - Backend retrieves players from `franchise.players` collection (filtered by `meta.team_id`)
   - Backend retrieves training report from `franchise_teams.{team_id}.training_reports.{week}`
   - Frontend renders players table and team attributes with visualizations

3. **Schedule Integration:**
   - Schedule endpoint (`/franchise/schedule`) checks for training reports
   - Adds `has_training_report` and `is_user_team` flags to each game
   - Frontend renders training report links for eligible games

#### Team ID Resolution

The training report system handles team_id in multiple formats:
- **Team Name:** Resolved to team `_id` via database lookup
- **Team ID (string):** Used directly
- **Team ID (ObjectId):** Converted to string

For player loading, the system:
- Checks `meta.team_id` first
- Falls back to `meta.team` name lookup if `team_id` is missing
- Compares resolved team IDs to filter players

---

### Future Enhancements

- Tournament mode training execution
- Single game mode training
- Training history tracking and archiving
- Custom attribute selection for Player Maximizer focus
- Play effectiveness score updates from training
- Training simulation for computer teams

---

## Motion Offense Shot Resolution System ✅ **COMPLETE** (January 2025)

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
   - **Two-step process** (critical for proper animation):
     - **Step 1:** `action: "drive"` to destination lane spot
     - **Step 2:** `action: "shoot"` at destination lane spot
   - Uses `playcall = "Attack"` for shot calculation
   - **Note:** Two-step approach ensures proper drive animation and accurate shot location detection

### Attack Drive Implementation

**Function:** `_create_attack_drive_shoot_steps()` (renamed from `_create_attack_drive_shoot_step()`)

**Returns:** List of two steps `[drive_step, shoot_step]`

**Drive Step:**
```python
{
    "timestamp": timestamp,
    "pos_actions": {
        ball_handler_pos: {
            "location": destination_location,  # e.g., "basketSpot"
            "action": "drive"
        }
    },
    "events": []
}
```

**Shoot Step:**
```python
{
    "timestamp": timestamp + 300,
    "pos_actions": {
        ball_handler_pos: {
            "location": destination_location,  # Same as drive step
            "action": "shoot"
        }
    },
    "events": [{"type": "shot"}],
    "_attack_drive": {
        "start_location": start_location,
        "intended_destination": destination_location,
        "final_location": destination_location,
        "stopped_short": False
    }
}
```

**Why Two Steps?**

1. **Proper Animation:** Frontend animator needs separate `drive` action to create movement animation from start → destination
2. **Accurate Shot Location:** Frontend shot detection finds `shoot` action at final location (not start location)
3. **3-Point Detection:** Shot location detection uses final step's location, ensuring correct 3-point classification
4. **Visual Clarity:** Users see the drive animation before the shot, making the play more realistic

**Drive Destinations:**

Based on starting location:
- **Upper locations** → `["upper lowPost", "upper midPost", "upper bird", "midLane", "basketSpot"]`
- **Lower locations** → `["lower lowPost", "lower midPost", "lower bird", "midLane", "basketSpot"]`
- **Central locations** → All destinations (both upper and lower)

### Execution Flow

1. **Select Random Step:** Choose step 1-N (excluding step 0) for shot attempt
2. **Identify Ball Handler:** Find ball handler position and location at selected step
3. **Check Possibilities:** Determine which shot types are possible (inside/attack/outside)
4. **Build Weighted List:** Create weighted list based on strategy settings and possibilities
5. **Select Shot Type:** Randomly select from weighted list
6. **Execute Shot:**
   - **Inside:** Pass to receiver OR shoot from current location
   - **Outside:** Pass to receiver OR shoot from current location
   - **Attack:** Create two steps (drive + shoot) and append to skeleton
7. **Return Results:** Modified skeleton with shot steps, shooter info, shot type, playcall

### Key Files

**Backend:**
- `BackEnd/engine/phase_resolution.py`
  - `resolve_motion_offense_shot()` (lines 2908-3100) - Main shot resolution function
  - `_create_attack_drive_shoot_steps()` (lines 2812-2847) - Creates drive + shoot steps
  - `_determine_attack_drive_destination()` (lines 2749-2767) - Determines valid drive destinations
  - `_check_inside_shot_possibility()` - Checks if inside shot is possible
  - `_check_attack_shot_possibility()` - Checks if attack shot is possible
  - `_check_outside_shot_possibility()` - Checks if outside shot is possible
  - `_build_shot_type_weighted_list()` - Builds weighted list for shot type selection

**Frontend:**
- `BackEnd/models/animator.py` - Converts skeleton steps to animation data
  - Processes `drive` action to create movement animation
  - Processes `shoot` action to trigger shot animation

### Integration with Shot Detection

**3-Point Detection:**
- Uses `shooter_location` from final step (shoot step for attack shots)
- Compares location against `THREE_POINT_SPOTS` constant
- Two-step approach ensures correct location is detected (not start location)

**Shot Calculation:**
- Uses `playcall` parameter ("Inside", "Outside", "Attack")
- Applies attack penalty if player was stopped short
- Uses base shot calculation (no variant modifier for Motion plays)

---

## In-Game Play Calling System ✅ **IMPLEMENTED** (January 2025)

### Overview

The In-Game Play Calling System determines which offensive and defensive plays are selected during gameplay. It uses weighted random selection based on playbook settings configured by the user, with fallbacks for CPU teams and when no settings exist.

**Location:** `BackEnd/models/turn_manager.py` - `set_playcalls()` method  
**Purpose:** Select offensive and defensive playcalls for each turn  
**Status:** ✅ Playbook integration complete

### Play Selection Flow

**1. Determine Play Type (Motion vs Set Play)**
- Uses `offense_setting` from strategy settings (0-4 slider)
- Weighted random between "motion" and "set_play" based on setting
- Setting 0 = 100% motion, Setting 4 = 100% set play

**2. Determine Play Focus (Inside/Attack/Outside)**
- Uses `inside`, `attack`, `outside` values from strategy settings
- Weighted random selection based on these values
- Only applies to Set Plays (Motion plays don't filter by focus)

**3. Select Specific Play**
- **Motion Plays:** Queries all motion plays, then uses weighted selection based on playbook percentages
- **Set Plays:** Queries plays matching play_type + play_focus, then uses weighted selection based on playbook percentages
- **Zone Defense:** When "Zone" is selected, uses weighted selection from playbook percentages for specific zone types (2-3, 3-2, 1-3-1)

### Playbook Integration

**Weighted Selection:**
- Loads playbook settings from `teams.{team_id}.playbook_settings` in the appropriate mode document
- Uses `weighted_random_from_dict()` to select plays based on percentages
- Only applies to user teams (CPU teams use equal weights)

**Fallback Behavior:**
- If no playbook settings exist → Equal weights for all plays
- If CPU team → Equal weights (playbook settings ignored)
- If "To Be Added" play → Excluded from selection (0% weight)

**Example:**
```python
# User sets playbook:
# - 5-0 Motion: 50%
# - 4-1 Motion: 30%
# - 3-2 Motion: 20%

# When motion offense is selected:
# - 50% chance: 5-0 Motion
# - 30% chance: 4-1 Motion
# - 20% chance: 3-2 Motion
```

### Defense Selection

**Man Defense:**
- Currently only one option ("Man")
- No weighting needed (always selects "Man")
- Future: Will support multiple man defense variants with playbook percentages

**Zone Defense:**
- When "Zone" is selected (from strategy settings or user override), converts to specific zone type
- Uses playbook percentages from `playbook_settings.zone_defense`
- Example: If user sets 2-3 Zone: 40%, 3-2 Zone: 35%, 1-3-1 Zone: 25%, selection follows these weights

### Storage and Mode Support

**Storage Location:**
- **Single Game:** `games_collection` → `game_doc.teams.{team_id}.playbook_settings`
- **Tournament:** `tournaments_collection` → `tournament_doc.teams.{team_id}.playbook_settings`
- **Franchise:** `franchises_collection` → `franchise_doc.teams.{team_id}.playbook_settings`

**Mode Isolation:**
- Each game mode maintains its own playbook settings
- Settings from one mode don't affect another
- Settings persist across games within the same mode

### Key Methods

**`set_playcalls()`** - Main entry point for play selection
- Determines play type (motion/set_play)
- Determines focus (inside/attack/outside) for set plays
- Calls `_select_play_with_playbook_weights()` for offense
- Calls `_select_zone_defense_with_playbook_weights()` for zone defense

**`_load_playbook_settings(team_id)`** - Loads playbook settings from database
- Checks if team is user team (CPU teams return None)
- Loads from appropriate mode document
- Returns playbook_settings dict or None

**`_select_play_with_playbook_weights(matching_plays, play_type, play_focus)`** - Weighted play selection
- Filters out "To Be Added" plays
- Loads playbook settings
- Builds weights dict from percentages
- Uses `weighted_random_from_dict()` for selection

**`_select_zone_defense_with_playbook_weights()`** - Weighted zone defense selection
- Loads playbook settings for defense team
- Uses zone_defense percentages
- Falls back to equal weights if no settings

### Integration Points

**Turn Manager:**
- `set_playcalls()` method calls playbook selection logic
- Results stored in `game_state["current_playcall"]` and `game_state["defense_playcall"]`

**Game Engine:**
- Selected playcall used by `resolve_half_court_offense_logic()`
- Skeleton retrieved based on selected playcall
- Shot resolution uses playcall for scoring calculations

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

## Game Mode Systems ✅ **NEW** (January 2025)

### Overview

The game supports three distinct modes, each with its own data persistence strategy:

1. **Single Game Mode**: One-off games with no persistent state between games
2. **Tournament Mode**: Multi-game tournament brackets with persistent team data
3. **Franchise Mode**: Multi-season franchise with persistent team and player evolution

Each mode stores team objects (attributes, plays, settings) in different MongoDB collections and documents, ensuring data isolation and proper persistence.

---

## Single Game Mode

### Overview

Single Game Mode is designed for one-off games with no persistent state between games. Each game is independent and does not affect future games.

### Team Object Lifecycle

#### 1. **Team Object Creation**

When a user accesses the Game Plan or Playbooks page for the first time in a new game:

- **Trigger**: `ensure_team_objects_exist()` is called with `mode="single"` and `doc_id=game_id`
- **Location**: `BackEnd/api/gameplan_routes.py` (lines 152-299)
- **Process**:
  1. Checks if team object exists in `games` collection under `teams.{team_id}`
  2. If missing, creates team object with:
     - `playcall_settings`: Default settings (all set to 2 = Normal)
     - `strategy_settings`: Default settings (all set to 2 = Normal)
     - `plays`: Populated plays from universal collection
     - **Team attributes**: Copied from the **universal `teams` collection** in MongoDB (the core/master team data):
       - `shot_threshold`, `turnover_modifier`, `foul_modifier`
       - `rebound_modifier`, `momentum_score`
       - `offensive_efficiency`, `team_chemistry`
       - `defensive_efficiency`, `fb_efficiency`, `pt_efficiency`
       - `fb_opp_modifier`, `pt_opp_modifier`

#### 2. **Team Object Storage**

- **Collection**: `games`
- **Document**: Game document (UUID string or ObjectId)
- **Path**: `games.{game_id}.teams.{team_id}`
- **Structure**:
  ```json
  {
    "playcall_settings": {...},
    "strategy_settings": {...},
    "plays": {...},
    "shot_threshold": 0,
    "turnover_modifier": 0,
    "foul_modifier": 0,
    "rebound_modifier": 0,
    "momentum_score": 0,
    "offensive_efficiency": 0,
    "team_chemistry": 0,
    "defensive_efficiency": 0,
    "fb_efficiency": 0,
    "pt_efficiency": 0,
    "fb_opp_modifier": 0,
    "pt_opp_modifier": 0
  }
  ```

#### 3. **Team Object Loading**

When creating a new game instance:

- **Location**: `BackEnd/api/api.py` (lines 1246-1253, 1337-1344)
- **Process**:
  1. `load_team_attributes_from_doc()` is called with `mode="single"` and `doc_id=game_id`
  2. Loads team attributes from `games.{game_id}.teams.{team_id}`
  3. If not found, falls back to the **universal `teams` collection** in MongoDB
  4. Attributes are passed to `GameManager()` constructor
  5. If no attributes are loaded, `TeamManager._init_team_attributes()` generates random values

#### 4. **Team Object Updates**

- **Playbook Settings**: Saved to `games.{game_id}.teams.{team_id}.playbook_settings`
- **Strategy Settings**: Saved to `games.{game_id}.teams.{team_id}.strategy_settings`
- **Team Attributes**: Currently not updated during gameplay (training not implemented for single game mode)

#### 5. **Team Object Persistence**

- Team objects persist for the duration of the game
- When a new game is started, new team objects are created (no carryover from previous games)
- Team attributes are reset to the **universal `teams` collection** values for each new game

### Key Files

- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/models/team_manager.py` - `TeamManager.__init__()` (lines 9-84)
  - Stores `mode` parameter as `self.mode` for use in `_init_scouting_data()` and other methods
- `BackEnd/models/team_manager.py` - `_init_team_attributes()` (lines 128-141)

---

## Tournament Mode ✅ **UPDATED** (January 2025)

### Overview

Tournament Mode supports multi-game tournament brackets where team data persists across games within the tournament. Team attributes can be modified through training and persist throughout the tournament. The Tournament Command Center provides a comprehensive interface for managing tournament progression, viewing schedules, and running training sessions.

**Location:** `FrontEnd/static/tournament.html`, `FrontEnd/static/tournament.js`  
**Status:** ✅ Fully implemented with Schedule tab, training integration, and bracket management

### Tournament Command Center

**Initialization:**
- **URL Parameter Support:** Reads `tournament_id` and `team_id` from URL parameters on page load
  - Priority 1: URL parameters (when navigating from training report, etc.)
  - Priority 2: localStorage (for returning to page)
  - Priority 3: Active tournament lookup by `user_team_id`
- **Data Loading:** `loadTournament()` function prioritizes URL parameters over localStorage
  - Uses `/tournament/state?tournament_id=...` endpoint (query parameter format)
  - Updates `userTeamId` from tournament document if not already set
  - Shows error message if tournament fails to load
- **Error Handling:** Page displays error message if tournament fails to load, preventing empty data display

**Tabs (in order):**
1. **Bracket** - Visual bracket display showing tournament progression
2. **Roster** - Team roster (player attributes) and player statistics for the current tournament
3. **Team** - Team Report section (team attributes) and Playbook Summary section (play effectiveness)
4. **Stats** - Tournament leaderboards for key statistics
5. **Schedule** - Detailed schedule view with First Round, Semifinals, and Championship matchups

**Tab Content Details:**

**Roster Tab:**
- Displays player roster table with attributes (SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, RT)
- Displays player statistics table (PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, MIN, TO)
- Player names are clickable links to player detail pages
- Same content as the previous "Team" tab (renamed for clarity)

**Team Tab:**
- **Team Report Section**: Displays team attributes in a grid layout (same as Training Report)
  - Shows team attributes: Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum, Team Chemistry, Fast Break Defense, Press/Trap Breaks
  - Uses visual indicators (pills, progress bars, +/- indicators) matching Training Report styling
  - Styled with scoped CSS (`command-center-team-styles.css`) to maintain light theme consistency
- **Playbook Summary Section**: Displays play and defense effectiveness
  - Shows offensive plays (motion and set plays) with effectiveness progress bars
  - Shows defensive schemes (man and zone defenses) with effectiveness progress bars
  - Organized by Offense and Defense categories
  - Data loaded from tournament document: `tournaments.{tournament_id}.teams.{team_id}.plays` and `tournaments.{tournament_id}.teams.{team_id}.scouting_data`
  - **Data Loading**: Uses `/tournament/team-data` endpoint (matches pattern used by `/tournament/roster`)
    - Endpoint resolves `team_name` to `team_id` server-side using multiple fallback strategies
    - Handles both formatted ("ocean-city") and unformatted ("Ocean City") team names
    - Falls back to `tournament.user_team_id` if provided team_name doesn't match
    - Initializes `scouting_data.defense` structure if missing
    - Defaults team attributes to 0 if not present

**Header Controls:**
- **Set Game Plan** - Navigate to Game Plan screen
- **Playbooks** - Navigate to Playbooks page
- **Run Training / Play Next Game** - Dynamic button that changes based on training status
  - Shows "Run Training" if training has not been completed for the current round
  - Shows "Play Next Game" if training has been completed for the current round
  - Removes opponent name from button text (simplified display)

### Schedule Tab

**Location:** `FrontEnd/static/tournament.js` - `renderSchedule()` function

**Display Structure:**
- **First Round** - Shows all 4 matchups with seed numbers:
  - Team 8 @ Team 1
  - Team 5 @ Team 4
  - Team 6 @ Team 3
  - Team 7 @ Team 2
- **Semifinals** - Shows 2 matchups:
  - Initially displays "TBD @ TBD" for both matchups
  - Dynamically filled based on First Round winners
  - Shows scores when games are completed
- **Championship** - Shows 1 matchup:
  - Initially displays "TBD @ TBD"
  - Dynamically filled based on Semifinals winners
  - Shows scores when game is completed

**Training Report Links:**
- Training report link appears to the right of the user's matchup after training is run
- Link format: `[Training Report]`
- Styled in blue, smaller font size
- Links to `/static/training-report.html` with tournament context

### Training Flow

**Mandatory Training:**
- User must run training before each game in the tournament
- Training is required for each round (First Round, Semifinals, Championship)
- Training status is tracked per round in `tournament.training_status`

**Training Status Tracking:**
- `training_status.training_completed` - Boolean flag
- `training_status.round` - Current round number (1, 2, or 3)
- `training_status.last_training_date` - Date of last training session

**Button Behavior:**
- If `training_status.training_completed === false` or `training_status.round !== current_round`:
  - Button shows "Run Training"
  - Clicking navigates to `/static/training.html` with tournament context
- If `training_status.training_completed === true` and `training_status.round === current_round`:
  - Button shows "Play Next Game"
  - Clicking proceeds to game simulation and lineup selection

**Training Endpoint:**
- **Location:** `BackEnd/api/tournament_routes.py` - `run_tournament_training()`
- **Endpoint:** `POST /tournament/run-training`
- **Process:**
  1. Loads tournament document
  2. Checks for duplicate training submission (same round)
  3. Loads tournament-specific player attributes from `player_stats`
  4. **Backward Compatibility:** If tournament only has EM, CH, MO (old format), merges with core collection attributes
  5. **Data Initialization (Auto-Population):**
     - If `plays_data` is empty or missing, backend automatically populates it from the universal `plays` collection using `populate_team_plays()`
     - If `scouting_data` is empty or missing the `defense` structure, backend automatically initializes it using `TeamManager._init_scouting_data()`
     - Initialized data is saved to the database before training execution
     - This ensures training works even if game plan or playbooks haven't been submitted yet
  6. Executes training using `execute_training()` from `training_execution_v2.py`
  7. **Saves ALL player attributes** to tournament document (not just modified ones) - unified with Franchise architecture
  8. Marks training as completed for current round
  9. **Training Report Storage (matches Franchise pattern):**
     - Stores training report in `teams.{team_id}.training_reports.{round}` (per-round storage)
     - Also stores in `latest_training` field (quick access)
  10. **Redirects to Training Report page (SS&S approach):**
     - URL: `/static/training-report.html?mode=tournament&tournament_id=...&team_id=...`
     - **Note:** `round` parameter is NOT included in redirect URL
     - Backend determines round from `training_status.round` or `latest_training.round` when loading report
     - This follows SS&S pattern: use URL params for navigation, backend state for data resolution

**Training Report:**
- **Location:** `BackEnd/api/franchise_routes.py` - `get_training_report()` (supports tournament mode)
- **Endpoint:** `GET /franchise/training-report?mode=tournament&tournament_id=...&team_id=...&round=...` (round is optional)
- **SS&S Approach:**
  - **Navigation params (required):** `tournament_id`, `team_id`, `mode`
  - **Round determination:**
    - If `round` parameter provided: use it (for historical reports from schedule links)
    - If not provided: backend determines from `training_status.round` or `latest_training.round`
    - This allows direct navigation after training without needing round in URL
- **Data Source:** 
  - Primary: `tournaments.{tournament_id}.teams.{team_id}.training_reports.{round}` (per-round storage)
  - Fallback: `tournament.latest_training` field (if per-round not found and round matches)
- **Attribute Extraction:**
  - **Unified Architecture:** Tournament mode now uses the same attribute extraction pattern as Franchise mode
  - All attributes are stored in `tournament.player_stats.{player_id}.attributes` (not just EM, CH, MO)
  - Extraction reads directly from tournament document (no merging with core collection needed for new tournaments)
  - **Backward Compatibility:** For old tournaments that only have EM, CH, MO, extraction merges with core collection automatically
- **Displays:** Player attribute changes, team attribute changes, coaching focus, upcoming opponent, play effectiveness changes, defense effectiveness changes
- **Pattern:** Matches Franchise mode pattern - per-round storage with `latest_training` fallback, unified attribute storage
- **SS&S Benefits:** 
  - Reduces URL parameter complexity
  - Backend state is source of truth
  - Historical reports can still use `round` parameter for specific round lookup
  - Unified architecture simplifies code maintenance and reduces bugs

---

## Franchise Mode ✅ **UPDATED** (January 2025)

### Overview

Franchise Mode supports multi-season career mode where team and player data persists across games and seasons. Team attributes and player attributes can be modified through training and persist throughout the franchise. The Franchise Command Center provides a comprehensive interface for managing franchise progression, viewing schedules, standings, and running training sessions.

**Location:** `FrontEnd/static/franchise-command-center.html`, `FrontEnd/static/franchise-command-center.js`  
**Status:** ✅ Fully implemented with Schedule tab, training integration, and franchise management

### Franchise Command Center

**Tabs (in order):**
1. **Standings** - Conference standings table showing wins, losses, win percentage, points for/against, and next opponent
2. **Roster** - Team roster (player attributes) and player statistics for the current season
3. **Team** - Team Report section (team attributes) and Playbook Summary section (play effectiveness)
4. **Stats** - Franchise leaderboards for key statistics across all teams, plus team-level statistics
5. **Schedule** - Season schedule view with weekly matchups and training report links
6. **Recruits** - Recruiting pool with player attributes and position ratings

**Tab Content Details:**

**Roster Tab:**
- Displays player roster table with attributes (SC, SH, ID, OD, PS, BH, RB, AG, ST, ND, IQ, FT, RT)
- Displays player statistics table for the current season (PTS, FGM/FGA, 3PTM/3PTA, FTM/FTA, REB, AST, STL, BLK, F, MIN, TO)
- Player names are clickable links to player detail pages
- Same content as the previous "Team" tab (renamed for clarity)
- **Data Loading**: Roster loaded from `/franchise/roster` endpoint, stats merged from franchise document's `players` collection

**Team Tab:**
- **Team Report Section**: Displays team attributes in a grid layout (same as Training Report)
  - Shows team attributes: Shooting, Rebounding, Offense, Defense, Fast Breaks, Press/Trap, Aggression, Discipline, Momentum, Team Chemistry, Fast Break Defense, Press/Trap Breaks
  - Uses visual indicators (pills, progress bars, +/- indicators) matching Training Report styling
  - Styled with scoped CSS (`command-center-team-styles.css`) to maintain light theme consistency
- **Playbook Summary Section**: Displays play and defense effectiveness
  - Shows offensive plays (motion and set plays) with effectiveness progress bars
  - Shows defensive schemes (man and zone defenses) with effectiveness progress bars
  - Organized by Offense and Defense categories
  - Data loaded from franchise document: `franchises.{franchise_id}.franchise_teams.{team_id}.plays` and `franchises.{franchise_id}.franchise_teams.{team_id}.scouting_data`
  - Loaded when Team tab is opened via `loadTeamData()` function

**Styling Implementation:**
- Team Report and Playbook Summary sections use scoped CSS (`command-center-team-styles.css`)
- Sections wrapped in `.training-report-styled` container to prevent style conflicts
- Maintains command center's light theme while providing Training Report-style visuals
- CSS variables adjusted for light background (white) instead of dark gradient

**Stats Tab:**
- **Leaders Section**: Franchise leaderboards for key statistics across all teams (same as previous "Leaders" tab)
- **Team Stats Section**: Team-level statistics table (points, rebounds, assists, steals, blocks) - moved from previous "Team Stats" tab
- Combined into single tab for better organization

**Header Controls:**
- **Set Game Plan** - Navigate to Game Plan screen with franchise context
- **Playbooks** - Navigate to Playbooks page with franchise context
- **Run Training / Play Now** - Dynamic button that changes based on training status

**Schedule Tab:**
- Displays full season schedule organized by week
- Shows completed games with scores (winner highlighted in bold)
- Shows upcoming games without scores
- Training report links appear next to user's team's games when training has been completed for that week
- Also displays latest training session results below the schedule

**Standings Tab:**
- Displays conference standings table only (schedule moved to Schedule tab)
- Shows team name, wins, losses, win percentage, points for, points against, and next opponent

### Team Object Lifecycle

#### 1. **Team Object Creation**

When a tournament is first created or when a team is first accessed:

- **Trigger**: `ensure_team_objects_exist()` is called with `mode="tournament"` and `doc_id=tournament_id`
- **Location**: `BackEnd/api/gameplan_routes.py` (lines 152-299)
- **Process**:
  1. Checks if team object exists in `tournaments` collection under `teams.{team_id}`
  2. If missing, creates team object with:
     - `playcall_settings`: Default settings (all set to 2 = Normal)
     - `strategy_settings`: Default settings (all set to 2 = Normal)
     - `plays`: Populated via `populate_team_plays(mode="tournament")`
       - **Tournament Mode Randomization**: Each play gets randomized values:
         - `effectiveness`: random.randint(0, 80)
         - `momentum`: random.randint(0, 10)
         - `cloaking`: random.randint(0, 10)
       - Each play and each value gets its own random roll
     - `scouting_data`: Initialized via `populate_scouting_data(mode="tournament")`
       - **Tournament Mode Randomization**: Each defense (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone) gets randomized values:
         - `effectiveness`: random.randint(0, 80)
         - `momentum`: random.randint(0, 10)
         - `cloaking`: random.randint(0, 10)
       - Each defense and each value gets its own random roll
       - **Location**: `BackEnd/api/gameplan_routes.py` - `populate_scouting_data()` function (lines 173-273)
     - **Team attributes**: Copied from the **universal `teams` collection** in MongoDB (same attributes as Single Game Mode)

#### 2. **Team Object Storage**

- **Collection**: `tournaments`
- **Document**: Tournament document (ObjectId)
- **Path**: `tournaments.{tournament_id}.teams.{team_id}`
- **Structure**: Same as Single Game Mode

#### 3. **Team Object Loading**

When creating a new game instance within a tournament:

- **Location**: `BackEnd/api/api.py` (lines 1246-1253, 1337-1344)
- **Process**:
  1. `load_team_attributes_from_doc()` is called with `mode="tournament"` and `doc_id=tournament_id`
  2. Loads team attributes from `tournaments.{tournament_id}.teams.{team_id}`
  3. If not found, falls back to the **universal `teams` collection** in MongoDB
  4. Attributes are passed to `GameManager()` constructor
  5. If no attributes are loaded, `TeamManager._init_team_attributes()` generates random values

**Team Data API Endpoint:**
- **Location**: `BackEnd/api/tournament_routes.py` - `get_tournament_team_data()`
- **Endpoint**: `GET /tournament/team-data?tournament_id=...&team_name=...`
- **Process**:
  1. Resolves `team_name` to `team_id` server-side using multiple fallback strategies:
     - Strategy 1: Exact name match
     - Strategy 2: Case-insensitive match
     - Strategy 3: Normalized name (replace dashes with spaces, title case)
     - Strategy 4: Fallback to `tournament.user_team_id`
  2. Returns team object from `tournaments.{tournament_id}.teams.{team_id}`
  3. Initializes `scouting_data.defense` structure if missing
  4. Defaults team attributes to 0 if not present
- **Pattern**: Matches the successful pattern used by `/tournament/roster` - server-side team name resolution with robust fallback strategies

#### 4. **Team Object Updates**

- **Playbook Settings**: Saved to `tournaments.{tournament_id}.teams.{team_id}.playbook_settings`
- **Strategy Settings**: Saved to `tournaments.{tournament_id}.teams.{team_id}.strategy_settings`
- **Team Attributes**: Updated through training system
  - Training changes are stored in tournament document
  - **ALL player attributes** updated in `tournament.player_stats.{player_id}.attributes` (unified with Franchise architecture)
  - Team attributes can be updated (future: stored in tournament document)
  - Training reports stored in `tournament.latest_training`

#### 5. **Team Object Persistence**

- Team objects persist for the duration of the tournament
- Changes to team attributes persist across all games in the tournament
- When a new tournament is started, new team objects are created (no carryover from previous tournaments)

### Key Files

- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/tournament/tournament_manager.py` - Tournament creation and management

---

## Franchise Mode

### Overview

Franchise Mode supports multi-season franchise play where team and player data evolves over time. Team attributes can be modified through training and persist across seasons.

### Team Object Lifecycle

#### 1. **Team Object Creation**

When a franchise season is initialized:

- **Trigger**: `FranchiseManager.initialize_season()` is called
- **Location**: `BackEnd/models/franchise_manager.py` (lines 109-235)
- **Process**:
  1. Creates `franchise_teams` objects for all 8 teams in the franchise
  2. Each team object includes:
     - `playcall_settings`: Default settings (all set to 2 = Normal)
     - `strategy_settings`: Default settings (all set to 2 = Normal)
     - `plays`: Populated plays from universal collection
     - **Team attributes**: Copied from the **universal `teams` collection** in MongoDB (same attributes as Single Game Mode)

- **Also Triggered By**: `ensure_team_objects_exist()` when accessing Game Plan or Playbooks
- **Location**: `BackEnd/api/gameplan_routes.py` (lines 182-235)
- **Process**: Same as above, but only creates missing team objects (doesn't recreate existing ones)

#### 2. **Team Object Storage**

- **Collection**: `franchises`
- **Document**: Franchise document (ObjectId)
- **Path**: `franchises.{franchise_id}.franchise_teams.{team_id}`
- **Structure**: Same as Single Game Mode

#### 3. **Team Object Loading**

When creating a new game instance within a franchise:

- **Location**: `BackEnd/api/api.py` (lines 1246-1253, 1337-1344)
- **Process**:
  1. `load_team_attributes_from_doc()` is called with `mode="franchise"` and `doc_id=franchise_id`
  2. Loads team attributes from `franchises.{franchise_id}.franchise_teams.{team_id}`
  3. If not found, falls back to the **universal `teams` collection** in MongoDB
  4. Attributes are passed to `GameManager()` constructor
  5. If no attributes are loaded, `TeamManager._init_team_attributes()` generates random values

**Team Data API Endpoint:**
- **Location**: `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()`
- **Endpoint**: `GET /franchise/team-data?franchise_id=...&team_name=...`
- **Process**:
  1. Resolves `team_name` to `team_id` server-side using `db.teams.find_one({"name": team_name})`
  2. Returns team object from `franchises.{franchise_id}.franchise_teams.{team_id}`
  3. Initializes `scouting_data.defense` structure if missing
  4. Defaults team attributes to 0 if not present
- **Pattern**: Matches the successful pattern used by `/franchise/roster` - server-side team name resolution

#### 4. **Team Object Updates**

- **Playbook Settings**: Saved to `franchises.{franchise_id}.franchise_teams.{team_id}.playbook_settings`
- **Strategy Settings**: Saved to `franchises.{franchise_id}.franchise_teams.{team_id}.strategy_settings`
- **Team Attributes**: Updated through training
  - **Location**: `BackEnd/api/franchise_routes.py` (lines 1045-1061)
  - **Process**: Training changes are saved to `franchises.{franchise_id}.franchise_teams.{team_id}.{attribute_name}`
  - **Example**: `franchises.{franchise_id}.franchise_teams.{team_id}.defensive_efficiency = new_value`

#### 5. **Team Object Persistence**

- Team objects persist across all games and seasons in the franchise
- Changes to team attributes persist permanently (until modified again)
- When a new season is started, team objects are preserved (carryover from previous seasons)

### Key Files

- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-235)
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 182-235)
- `BackEnd/api/api.py` - `load_team_attributes_from_doc()` (lines 196-244)
- `BackEnd/api/api.py` - Game creation logic (lines 1246-1253, 1337-1344)
- `BackEnd/api/franchise_routes.py` - Training save logic (lines 1045-1061)

---

## Data Persistence ✅ **NEW** (January 2025)

### Overview

This section documents what data is persisted in each game mode when the user is in non-gameplay situations (Command Center, Game Plan, Playbooks, Training, Training Report). This is critical for understanding what state needs to be maintained across navigation transitions.

**Reference:** For detailed architecture documentation, see:
- `docs/franchise_mode_architecture.md` - Complete franchise mode data structure
- `docs/COMMON_DATA_SET.md` - Common data structure across all modes

---

### Franchise Mode (Non-Gameplay)

**When:** User is in Franchise Mode but not actively playing a game (Command Center, Game Plan, Playbooks, Training, Training Report)

**What Gets Persisted:**

#### **A. Franchise Document (`franchises` collection)**

**Document ID:** `_id: ObjectId("franchise_id")`

**Season Progress:**
- `week`: Current week number (1-14)
- `current_week`: Alias for week
- `schedule`: Pre-generated schedule array `[[team_A_id, team_B_id], ...]` (14 weeks)

**Game Results (Summaries Only):**
- `results`: Object with weekly summaries
  ```javascript
  {
    "1": [{away_id, home_id, away_score, home_score}, ...],
    "2": [{away_id, home_id, away_score, home_score}, ...],
    // ... up to week 14
  }
  ```

**Training State:**
- `training_status`: 
  ```javascript
  {
    "current_week": number,
    "training_completed": boolean,
    "session_type": "preseason" | "in-season"
  }
  ```
- `latest_training`:
  ```javascript
  {
    "player_logs": {...},  // What improved
    "team_log": {...},
    "session_type": "preseason" | "in-season",
    "week": number
  }
  ```

**Stat Tracking:**
- `applied_games`: Array of game IDs `["game_id_1", "game_id_2"]` (prevents double-counting stats)

**Recruiting:**
- `recruits`: Array of recruit objects (franchise-specific pool)

#### **B. Team Objects (`franchise_teams.{team_id}`)**

**For each of the 8 teams in the franchise:**

- **Team Attributes** (mode-specific, randomized on init, updated by training)
  - `team_chemistry`: 7-13 (franchise mode range)
  - `offensive_efficiency`: -3 to +3
  - `shot_threshold`: -100 to +100
  - `turnover_modifier`: -3 to +3
  - `foul_modifier`: -3 to +3
  - `rebound_modifier`: 0.8, 0.9, 1.0, 1.1, or 1.2
  - `defensive_efficiency`: -3 to +3
  - `fb_efficiency`: -3 to +3
  - `pt_efficiency`: -3 to +3
  - `fb_opp_modifier`: -3 to +3
  - `pt_opp_modifier`: -3 to +3

- **Strategy Settings** (user-configurable, persist across all instances)
  - `strategy_settings`: `{offense, inside, attack, outside, tempo, defense, aggression, hc_trap, fc_press, rebounding}` (all 0-4)

- **Plays Data** (updated by training)
  - `plays`: Object with play data including `effectiveness`, `momentum`, `cloaking` (0-100, 0-10, 0-10), `game_stats`, `season_stats`

- **Scouting Data** (updated by training)
  - `scouting_data`: Defense structures (Man, 2-3 Zone, 3-2 Zone, 1-3-1 Zone, vs_Fast_Break, FCP, HCT) with `effectiveness`, `momentum`, `cloaking`, `game_stats`, `season_stats`

- **Playbook Settings** (user-configurable, persist across all instances)
  - `playbook_settings`: `{motion, set_play_inside, set_play_attack, set_play_outside, zone_defense, man_defense, slot_assignments, motion_dropdowns}`

- **Legacy playcall_settings** (still present for backward compatibility)

**Initialization:** Team objects are created for all 8 teams when franchise is initialized via `FranchiseManager.initialize_season()` or lazily via `ensure_team_objects_exist()` when accessing Game Plan/Playbooks.

#### **C. Player Objects (`players.{player_id}`)**

**For each player in the franchise:**

- **Player Metadata** (`meta`: first_name, last_name, team, team_id)
- **Evolved Attributes** (`attributes`: all 30+ attributes with `anchor_` prefixed versions, updated by training)
- **Evolved Position Ratings** (`position_ratings`: PG, SG, SF, PF, C ratings, updated by training)
- **Statistics** (`season`: season stats, `career`: career stats)

#### **D. Additional Collections (Not in Franchise Document)**

**Training Logs (`training_logs` collection):**
- Historical training sessions (separate collection)
- Each session includes allocations, logs, and changes

**Games Collection (`games` collection):**
- Active game documents (during gameplay)
- Not part of franchise document during non-gameplay

**Summary:**
- All team and player data is franchise-specific and isolated from other franchises
- Changes to strategy settings, playbook settings, and training improvements persist across the franchise season
- Team objects include all common data fields (attributes, strategy_settings, plays, scouting_data, playbook_settings)

**For complete structure details, see:** `docs/franchise_mode_architecture.md` Section 7: NON-GAMEPLAY DATA PERSISTENCE

---

### Tournament Mode (Non-Gameplay)

**When:** User is in Tournament Mode but not actively playing a game (Command Center, Game Plan, Playbooks, Training, Training Report)

**What Gets Persisted:**

*(To be documented - similar structure to Franchise Mode but with tournament-specific fields)*

---

### Single Game Mode (Non-Gameplay)

**When:** User is in Single Game Mode but not actively playing (Lineup, Game Plan, Playbooks)

**What Gets Persisted:**

*(To be documented - game document structure)*

---

### Key Files

- `BackEnd/models/franchise_manager.py` - `initialize_season()` (lines 109-235)
- `BackEnd/api/gameplan_routes.py` - `ensure_team_objects_exist()` (lines 152-299)
- `BackEnd/api/franchise_routes.py` - `get_franchise_team_data()` (lines 832-881)
- `docs/franchise_mode_architecture.md` - Complete franchise mode architecture
- `docs/COMMON_DATA_SET.md` - Common data structure across all modes

---

## Team Objects ✅ **COMPLETE** (January 2025)

### Overview

Team objects are the core data structure representing a team in the game engine. They are initialized when a `TeamManager` instance is created and contain all team-level data including players, lineups, attributes, strategy settings, plays, and scouting data.

**Location:** `BackEnd/models/team_manager.py` - `TeamManager.__init__()`  
**Status:** ✅ Fully implemented

### Team Object Structure

#### Base Fields (From Universal Teams Collection)

These fields are loaded from the universal `teams` collection in MongoDB:

- `name` (str) - Team name (e.g., "Morristown", "Bentley Truman")
- `team_id` (str) - Unique team identifier (e.g., "MORRISTOWN", "BENTLEY_TRUMAN")
- `primary_color` (str) - Primary team color (hex format, e.g., "#000000")
- `secondary_color` (str) - Secondary team color (hex format, e.g., "#ffffff")
- `mascot` (str) - Team mascot name
- `coaching` (dict) - Coaching attributes object (see Coaching Attributes System section)

#### Instance Fields (Initialized Per Game)

- `is_home_team` (bool) - Whether this team is the home team
- `is_user_team` (bool) - Whether this is the user's team (for override logic)

#### Player and Lineup Data

- `players` (dict) - Full roster dictionary: `{player_id: Player object}`
  - Loaded via `_load_roster()` from roster files
  - Contains all players on the team (not just active lineup)
  
- `lineup` (dict) - Active lineup dictionary: `{position: Player object}`
  - Initialized as empty dict `{}` - populated later when lineup is set
  - Positions: `"PG"`, `"SG"`, `"SF"`, `"PF"`, `"C"`

#### Game State Fields

- `points` (int) - Current game score (default: 0)
- `points_by_quarter` (list) - Points scored per quarter: `[Q1, Q2, Q3, Q4]` (default: `[0, 0, 0, 0]`)
- `team_fouls` (int) - Current team foul count (default: 0)
- `timeouts` (int) - Remaining timeouts (default: 5)
- `stats` (dict) - Team-level statistics dictionary (default: `{}`)
- `team_stats` (dict) - Team-level tracking stats (default: `{}`)
  - Includes: `release_instances`, `get_back_instances`, `actual_releases`
  - Fast break defender counts: `zero_defenders_back`, `one_defender_back`, `two_defenders_back`

#### Team Attributes

Initialized via `_init_team_attributes()` with the following value ranges:

- `shot_threshold` - `random.randint(-50, 50)`
- `turnover_modifier` - `random.randint(-10, 10)`
- `foul_modifier` - `random.randint(-10, 10)`
- `rebound_modifier` - `random.choice([0.8, 0.9, 1.0, 1.1, 1.2])`
- `momentum_score` - `random.randint(-10, 10)`
- `offensive_efficiency` - `random.randint(-10, 10)`
- `team_chemistry` - `random.randint(7, 25)`
- `defensive_efficiency` - `random.randint(-10, 10)`
- `fb_efficiency` - `random.randint(-10, 10)`
- `pt_efficiency` - `random.randint(-10, 10)`
- `fb_opp_modifier` - `random.randint(-10, 10)`
- `pt_opp_modifier` - `random.randint(-10, 10)`

**Note:** Team attributes can be provided during initialization (from saved games) or generated randomly if not provided.

#### Strategy Settings

Initialized via `_init_strategy_settings()` with randomization (0-4 scale):

- `offense` - `random.randint(0, 4)`
- `inside` - `random.randint(1, 4)` (never zero)
- `attack` - `random.randint(1, 4)` (never zero)
- `outside` - `random.randint(1, 4)` (never zero)
- `tempo` - `random.randint(0, 4)`
- `play_calling` - `random.randint(0, 4)`
- `defense` - `2` (hardcoded for testing - 50/50 man/zone mix)
- `aggression` - `random.randint(0, 4)`
- `hc_trap` - `4` (temporary: hardcoded for testing)
- `fc_press` - `4` (temporary: hardcoded for testing)
- `rebounding` - `random.randint(0, 4)`

**Note:** Strategy settings can be provided during initialization (from saved games) or generated randomly if not provided.

#### Strategy Calls (User Overrides)

Initialized as dictionary with override fields (None = use normal selection):

- `offense_call` (str or None) - Play name string or None (user override persists until used)
- `defense_call` (str or None) - "Man", "Zone", or None (user override persists until used)
- `aggression_override` (str or None) - "normal", "aggressive", "passive", or None (temporary override)
- `tempo_override` (str or None) - "slow", "normal", "fast", or None (temporary override)
- `press_override` (str or None) - Future: FCP override
- `trap_override` (str or None) - Future: HCT override

#### Playcall Trackers

- `playcall_tracker` (dict) - Offensive playcall usage tracker: `{playcall_name: count}`
  - Initialized with all playcalls from `PLAYCALLS` constant set to 0
  
- `defense_playcall_tracker` (dict) - Defensive playcall usage tracker: `{"Man": 0, "Zone": 0}`

#### Scouting Data

Initialized via `_init_scouting_data()` with comprehensive tracking structure:

**Offense Scouting:**
- `Fast_Break_Entries` - Fast break attempt count
- `Fast_Break_Success` - Fast break success count
- `Playcalls` - Nested structure for Motion and Set plays:
  - `Motion` / `Set` buckets:
    - `overall` - Overall attempts, success, ev_scores, lean_scores
    - `inside` / `attack` / `outside` - Focus-specific tracking
    - `vs_man` / `vs_zone` / `vs_2-3_zone` / `vs_3-2_zone` / `vs_1-3-1_zone` - Defense-specific tracking
  - `Cumulative` - Cross-play type focus tracking
- `last_play_by_category` - Tracks last play run for each category (for tooltips)

**Defense Scouting:**
- `Man` / `2-3 Zone` / `3-2 Zone` / `1-3-1 Zone` - Defense type tracking:
  - `used` - Usage count
  - `success` - Success count
  - `effectiveness` (float) - **Per-team effectiveness score** (training-impacted)
    - Initialized to `0.0` (can be modified by training system)
    - Used in matchup calculations and defense selection weighting
  - `momentum` (int) - **Per-team momentum score** (training-impacted)
    - Initialized to `0` (can be modified by training system)
    - Tracks recent performance trends for this team's use of the defense
    - Used to adjust defense selection probabilities dynamically
  - `cloaking` (int) - **Per-team cloaking modifier** (training-impacted)
    - Initialized to `0` (can be modified by training system)
    - Makes the defense harder for opponents to recognize and counter
    - Higher values reduce opponent's ability to anticipate and adjust
  - `game_stats` - Game-level stats (attempts, success, ev_scores, lean_scores, vs_motion/set/inside/attack/outside)
  - `season_stats` - Season-level stats (for tournament/franchise modes)
- `vs_Fast_Break` - Fast break defense tracking
- `FCP` / `HCT` - Pressure defense tracking

**Per-Team Defense Values:**
- Each team has its own instance of every defense with per-team `effectiveness`, `momentum`, and `cloaking` values
- Initial values are set to `0` when the team object is created
- Per-team values can be modified by training system based on playbook settings and game plan mix
- This allows different teams to have different effectiveness/momentum/cloaking for the same defense

#### Plays Data

Initialized via `_init_plays_from_universal()` with reference-based structure:

**Structure:** `{play_name: play_data}`

Each play entry contains:
- `play_id` (str) - Reference to universal play document `_id` (the "library card")
- `name` (str) - Play name
- `play_type` (str) - "motion" or "set_play"
- `play_focus` (str) - "inside", "attack", or "outside" (for set plays)
- `effectiveness` (float) - **Per-team effectiveness score** (training-impacted, separate from calculated effectiveness in stats)
  - Initialized from universal play's `effectiveness` field (defaults to `0` if not present)
  - Can be modified by training system based on playbook settings and game plan mix
  - Used in matchup calculations and play selection weighting
- `momentum` (int) - **Per-team momentum score** (training-impacted)
  - Initialized from universal play's `momentum` field (defaults to `0` if not present)
  - Tracks recent performance trends for this team's use of the play
  - Can be modified by training system
  - Used to adjust play selection probabilities dynamically
- `cloaking` (int) - **Per-team cloaking modifier** (training-impacted)
  - Initialized from universal play's `cloaking` field (defaults to `0` if not present)
  - Makes the play harder for opponents to recognize and counter
  - Higher values reduce opponent's ability to anticipate and adjust
  - Can be modified by training system
- `game_stats` (dict) - Game-level tracking:
  - `times_run` (int) - Number of times play was executed
  - `shot_attempts` (int) - Shot attempts from this play
  - `made_shots` (int) - Made shots from this play
  - `turnovers` (int) - Turnovers from this play
  - `offensive_fouls` (int) - Offensive fouls from this play
  - `defensive_fouls` (int) - Defensive fouls from this play
  - `effectiveness` (float) - **Calculated effectiveness from stats** (separate from per-team effectiveness field above)
- `season_stats` (dict) - Season-level tracking (tournament/franchise modes only):
  - Same structure as `game_stats`

**Note:** Plays data does NOT include full skeletons - skeletons are fetched from the universal `plays` collection when needed (reference-based architecture).

**Per-Team vs Universal Values:**
- Each team has its own instance of every play with per-team `effectiveness`, `momentum`, and `cloaking` values
- Initial values are copied from the universal `plays` collection when the team object is created
- Per-team values can be modified by training, in-game performance, and coaching focus selections
- This allows different teams to have different effectiveness/momentum/cloaking for the same play

### Initialization Methods

#### `_load_roster()`
- Loads roster from roster files via `load_roster()` utility
- Creates `Player` objects for each player
- Returns dictionary: `{player_id: Player object}`

#### `_load_lineup()`
- Returns empty dictionary `{}`
- Lineup is populated later when lineup is set

#### `_init_team_attributes()`
- Generates random team attributes with specified value ranges
- Returns dictionary of all team attributes

#### `_init_strategy_settings()`
- Generates random strategy settings (0-4 scale)
- Returns dictionary of all strategy settings

#### `_init_scouting_data()`
- Creates comprehensive scouting data structure
- Initializes all tracking counters to 0
- Returns nested dictionary structure for offense and defense tracking

#### `_init_plays_from_universal(mode)`
- Fetches all plays from universal `plays` collection
- Creates reference-based play entries (no full skeletons)
- Initializes game_stats and season_stats (if applicable)
- Returns dictionary: `{play_name: play_data}`

#### `_create_defense_structure_template()`
- Creates standard defense structure template
- Used for Man, 2-3 Zone, 3-2 Zone, and 1-3-1 Zone defenses
- Eliminates code duplication (~280 lines saved)
- Returns template dictionary with `used`, `success`, `effectiveness`, `game_stats`, `season_stats`

### Key Files

- `BackEnd/models/team_manager.py` - `TeamManager` class (lines 8-468)
  - `__init__()` - Main initialization (lines 9-84)
  - `_init_team_attributes()` - Team attribute initialization (lines 128-142)
  - `_init_strategy_settings()` - Strategy settings initialization (lines 103-126)
  - `_init_scouting_data()` - Scouting data initialization (lines 188-329)
  - `_init_plays_from_universal()` - Plays initialization (lines 331-383)
  - `_create_defense_structure_template()` - Defense template creation (lines 144-186)

---

## Team Attribute Management

### Attribute List

All team attributes are stored in team objects across all game modes:

**Core Attributes:**
- `shot_threshold` - Shot attempt threshold
- `turnover_modifier` - Turnover modifier
- `foul_modifier` - Foul modifier
- `rebound_modifier` - Rebound effectiveness modifier
- `momentum_score` - Team momentum score
- `offensive_efficiency` - Offensive efficiency rating
- `team_chemistry` - Team chemistry rating

**New Attributes (January 2025):**
- `defensive_efficiency` - Defensive efficiency rating
- `fb_efficiency` - Fast break efficiency rating
- `pt_efficiency` - Press/Trap efficiency rating
- `fb_opp_modifier` - Fast break opponent modifier
- `pt_opp_modifier` - Press/Trap opponent modifier

### Default Values

- **New Attributes**: All default to `0`
- **Core Attributes**: Loaded from the **universal `teams` collection** in MongoDB or generated randomly via `TeamManager._init_team_attributes()`

### Attribute Initialization

1. **First Access**: Team attributes are copied from the **universal `teams` collection** in MongoDB (the core/master team data)
2. **Missing Attributes**: If attributes don't exist in team object, they're initialized from the **universal `teams` collection**
3. **Fallback**: If the **universal `teams` collection** doesn't have attributes, `TeamManager._init_team_attributes()` generates random values

### Universal Teams Collection

The **universal `teams` collection** in MongoDB (`db.teams`) is the source of truth for initial team attribute values. This collection contains the master/base team data that is copied when team objects are first created in any game mode. It stores:

- Team metadata (name, colors, mascot, team_id)
- Base team attributes (shot_threshold, turnover_modifier, etc.)
- Coaching attributes object (effectiveness, training focus list, archetype scores and momentum)
- Initial playbook and strategy settings (if any)

When team objects are created in Single Game, Tournament, or Franchise modes, they copy attribute values from this universal collection. If attributes don't exist in the universal collection, they default to `0` (for new attributes) or are generated randomly (for core attributes via `_init_team_attributes()`).

### Attribute Updates

- **Training**: Updates team attributes in franchise mode (and future tournament mode)
- **Gameplay**: Team attributes are read-only during gameplay (not modified by game events)
- **Persistence**: Changes persist to the appropriate document based on game mode

---

## Attributes System ✅ **COMPLETE** (January 2025)

### Overview

The Attributes System defines the standard display order and formatting rules for player attributes across all game interfaces. This ensures consistency in how attributes are presented to users throughout the application.

**Status:** ✅ Fully implemented - Standard attribute order enforced in Training Report and other displays

### Standard Attribute Display Order

**CRITICAL:** When displaying all player attributes in a horizontal row, they must appear in this exact order:

1. **SC** - Shooting Close
2. **SH** - Shooting
3. **ID** - Inside Defense
4. **OD** - Outside Defense
5. **PS** - Passing
6. **BH** - Ball Handling
7. **RB** - Rebounding
8. **ST** - Strength
9. **AG** - Agility
10. **ND** - Endurance
11. **IQ** - Intelligence Quotient
12. **FT** - Free Throws
13. **NG** - Nerve/Game (Energy)
14. **EM** - Emotion
15. **MO** - Momentum

**Note:** This order applies to any horizontal display of all attributes, including:
- Training Report Player Report section
- Lineup screens
- Player detail pages
- Any other attribute grid or table displays

### Attribute Display Formatting

#### Standard Integer Attributes (SC through FT)

The first 12 attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT) are displayed as **integer values**:
- No decimal places
- Direct numeric display (e.g., `85`, `72`, `50`)

#### NG (Nerve/Game / Energy)

- **Format:** Decimal value with 2 decimal places
- **Range:** 0.00 to 1.00 (typically displayed as 0.90, 0.99, 1.00, etc.)
- **Display Examples:** `1.00`, `0.99`, `0.98`, `0.90`, `0.75`
- **Purpose:** Represents player energy level (100% = 1.00)

#### EM (Emotion)

- **Format:** Emoji display based on value
- **Range:** 0-100
- **Emoji Mapping:**
  - **>= 80:** 😎 (Sunglasses) - Very positive
  - **>= 60:** 😊 (Big smile) - Positive
  - **>= 40:** 😐 (Straight face) - Neutral
  - **>= 20:** 😕 (Slight frown) - Negative
  - **< 20:** 😞 (Sad face) - Very negative
- **Purpose:** Visual representation of player emotional state

#### MO (Momentum)

- **Format:** Red/Green horizontal pill visualization
- **Range:** -10 to +10
- **Visual Design:**
  - **Container:** Horizontal pill with dark background
  - **Center Line:** Yellow vertical line at 50% (center point)
  - **Positive Momentum (0 to +10):** Green fill extending right from center
    - Fill width proportional to value (e.g., +5 = 25% fill, +10 = 50% fill)
  - **Negative Momentum (-10 to 0):** Red fill extending left from center
    - Fill width proportional to absolute value (e.g., -5 = 25% fill, -10 = 50% fill)
  - **No Integer Display:** The numeric value is NOT displayed on top of the pill
- **Purpose:** Visual representation of player momentum trend

### Implementation Examples

**Training Report Player Report:**
- Attributes view: Displays all 15 attributes in standard order with appropriate formatting
- Training Changes view: Displays only changed attributes, maintaining standard order

**Other Displays:**
- Lineup screens, player cards, and detail pages should follow the same order and formatting rules
- When displaying a subset of attributes, maintain relative order (e.g., if showing SC, SH, MO, they appear in that order)

### Key Files

- `FrontEnd/static/training-report.js` - Training Report attribute display implementation
- `FrontEnd/static/training-report.css` - Momentum pill styling
- `FrontEnd/static/set-lineup.js` - Lineup screen attribute display (reference for EM/MO formatting)

---

## Coaching Attributes System ✅ **COMPLETE** (January 2025)

### Overview

The Coaching Attributes System tracks coaching effectiveness and archetype performance for each team. This system stores data about how effective a team's coaching is and tracks performance across different coaching archetypes (Authoritarian, Systems Coach, Player Maximizer, Culture Builder).

**Location:** Universal `teams` collection - `coaching` field  
**Status:** ✅ Fully implemented - All teams in universal collection have coaching structure

### Coaching Object Structure

Each team in the universal `teams` collection contains a `coaching` object with the following structure:

```json
{
  "coaching": {
    "effectiveness": 0,
    "training_focus_list": [],
    "authoritarian": {
      "score": 0,
      "momentum": 0
    },
    "systems coach": {
      "score": 0,
      "momentum": 0
    },
    "player maximizer": {
      "score": 0,
      "momentum": 0
    },
    "culture builder": {
      "score": 0,
      "momentum": 0
    }
  }
}
```

### Field Descriptions

#### Top-Level Fields

- **`effectiveness`** (integer) - Overall coaching effectiveness score
  - Initialized to `0`
  - Represents the team's overall coaching quality
  - Can be modified based on training results, game performance, and coaching focus selections

- **`training_focus_list`** (array of strings) - Historical list of training focus selections
  - Initialized as empty array `[]`
  - Tracks which coaching focuses have been selected over time
  - Used for pattern analysis and coaching development

#### Archetype Objects

Each of the four coaching archetypes has its own object with two fields:

- **`score`** (integer) - Performance score for this archetype
  - Initialized to `0`
  - Tracks how well the team performs when using this coaching style
  - Can increase or decrease based on training focus selections and results

- **`momentum`** (integer) - Momentum score for this archetype
  - Initialized to `0`
  - Tracks recent performance trends for this coaching style
  - Used to determine if a team is trending up or down with a particular approach

**Archetypes:**
1. **`authoritarian`** - Discipline, Rebounding, Execution, Teamwork focus
2. **`systems coach`** - Offense, Defense, Fast Breaks, Presses/Traps focus
3. **`player maximizer`** - Top 3 Attributes, Attributes 4-6, Custom, Be Opportunistic focus
4. **`culture builder`** - Inspire, Community Engagement, Teamwork, Build Confidence focus

### Initialization

**Script:** `scripts/add_coaching_field_to_teams.py`

This script ensures all teams in the universal `teams` collection have the complete coaching structure:
- Adds `coaching` field to all teams that don't have it
- Initializes all fields with default values (0 for integers, [] for arrays)
- Validates and updates teams with incomplete coaching structures
- Provides verification and sample output

**Usage:**
```bash
python scripts/add_coaching_field_to_teams.py
```

### Future Use Cases

The coaching attributes system is designed to support:
- **Training Focus Tracking**: Record which coaching focuses are selected and their effectiveness
- **Archetype Performance Analysis**: Track which coaching styles work best for each team
- **Momentum Tracking**: Identify trends in coaching effectiveness over time
- **Dynamic Coaching Adjustments**: Modify coaching effectiveness based on training and game results
- **Coaching Development**: Allow teams to improve their coaching effectiveness through consistent focus selection

### Integration with Training System

The coaching attributes system integrates with the Training System:
- Training focus selections can update archetype scores and momentum
- Training effectiveness can influence overall coaching effectiveness
- Historical training focus list tracks coaching style evolution

---

## Coaching Grid ✅ **COMPLETE** (January 2025)

### Overview

The Coaching Grid is a desktop-only visualization page that displays a team's coaching status across four coaching archetypes. It provides a 2D grid view showing each archetype's position based on effectiveness and momentum scores.

**Location:** `FrontEnd/static/coaching-grid.html`  
**Status:** ✅ Fully implemented with placeholder data positioning  
**Scope:** User team only (computer teams not viewable)

### Layout Structure

**Page Title:**
- Centered "Coaching Grid" heading at top of page

**Main Content:**
- Large 2D grid container centered on page
- Crosshair design with vertical and horizontal axes intersecting at center
- Axis endpoint labels:
  - **Top center:** "Embedded" (high effectiveness)
  - **Bottom center:** "Fragile" (low effectiveness)
  - **Left center:** "Stagnant" (low momentum)
  - **Right center:** "Compounding" (high momentum)

**Archetype Dots:**
- Four circular dots positioned on the grid
- Each dot has a text label placed near it
- Labels: "Authoritarian", "Systems", "Player Maximizer", "Culture"

### Data Mapping

**Y-Axis (Effectiveness):**
- Range: 0-100
- Midpoint: 50 (center of grid)
- **Top (Embedded):** 100 (maximum effectiveness)
- **Bottom (Fragile):** 0 (minimum effectiveness)
- Conversion: `yPercent = 100 - effectiveness`

**X-Axis (Momentum):**
- Range: 0-10
- Midpoint: 5 (center of grid)
- **Right (Compounding):** 10 (maximum momentum)
- **Left (Stagnant):** 0 (minimum momentum)
- Conversion: `xPercent = (momentum / 10) * 100`

### Archetype Colors

Each dot uses the same color as the corresponding coaching archetype header colors on the Training page:

- **Authoritarian:** `#ff4444` (red) - `var(--color-authoritarian)`
- **Systems:** `#d4a017` (yellow/burnt yellow) - `var(--color-systems-coach)`
- **Player Maximizer:** `#2d8f2d` (green) - `var(--color-player-maximizer)`
- **Culture:** `#9b59b6` (purple) - `var(--color-culture-builder)`

Colors are defined as CSS variables in `coaching-grid.css`, matching `training.css` for consistency.

### Visual Styling

**Dots:**
- Medium-sized (20-24px diameter)
- Subtle border/outline (white border, shadow) for visibility on light background
- Hover effect: Slight scale increase and enhanced shadow
- Positioned using absolute positioning with percentage-based coordinates

**Axis Lines:**
- Thin, neutral gray (`#999`)
- Vertical line: 1px width, full height, centered horizontally
- Horizontal line: 1px height, full width, centered vertically

**Labels:**
- **Axis labels:** Bold-ish, larger font (1.2-1.3rem), positioned at axis endpoints
- **Dot labels:** Smaller font (0.9-1rem), neutral gray, positioned to the right of each dot
- Consistent spacing and alignment

**Grid Container:**
- White background with subtle border and shadow
- Square aspect ratio (1:1)
- Responsive sizing for desktop (max-width: 800-900px)

### Data Source

**Coaching Object Structure:**
The grid reads data from the team's `coaching` object in the universal `teams` collection:

```json
{
  "coaching": {
    "authoritarian": {
      "score": 24,      // effectiveness value (0-100)
      "momentum": 0     // momentum value (0-10)
    },
    "systems coach": {
      "score": 92,
      "momentum": 5
    },
    "player maximizer": {
      "score": 35,
      "momentum": 9
    },
    "culture builder": {
      "score": 50,
      "momentum": 3
    }
  }
}
```

**Field Mapping:**
- `score` → Y-axis position (effectiveness)
- `momentum` → X-axis position (momentum)

### Implementation

**Positioning Logic:**
- `effectivenessToY(effectiveness)` - Converts effectiveness (0-100) to Y coordinate percentage
- `momentumToX(momentum)` - Converts momentum (0-10) to X coordinate percentage
- Dots positioned using `left` and `top` CSS properties with percentage values
- Transform used to center dots on their coordinates (`translate(-50%, -50%)`)

**Data Attributes:**
- Each dot has `data-archetype`, `data-effectiveness`, and `data-momentum` attributes
- Makes it easy to wire up with real data from API endpoints
- JavaScript reads these attributes and calculates positions on page load

**Placeholder Data:**
- Authoritarian: effectiveness=24, momentum=0 (lower-left quadrant)
- Systems: effectiveness=92, momentum=5 (upper-center)
- Player Maximizer: effectiveness=35, momentum=9 (lower-right quadrant)
- Culture: effectiveness=50, momentum=3 (center-left)

### Key Files

- `FrontEnd/static/coaching-grid.html` - Page structure and grid container
- `FrontEnd/static/coaching-grid.css` - Styling for grid, axes, dots, and labels
- `FrontEnd/static/coaching-grid.js` - Positioning logic and data mapping functions

### Future Enhancements

**Data Wiring:**
- Connect to API endpoint to fetch user team's coaching data
- Load coaching object from appropriate mode document (Single Game, Tournament, Franchise)
- Update dot positions dynamically based on real data

**Interactive Features:**
- Tooltips showing exact effectiveness and momentum values on hover
- Click dots to view detailed archetype information
- Animation when positions change (smooth transitions)

**Visual Enhancements:**
- Grid lines or tick marks for better readability
- Quadrant labels or shading to show different coaching zones
- Legend explaining axis meanings

---

## Resolution System 🚧 **IN PROGRESS** (January 2025)

### Overview

The Resolution System is a centralized, unified approach to determining turn outcomes across all major turn types: **HCO (Half Court Offense)**, **Fast Break**, **HCT (Half Court Trap)**, and **FCP (Full Court Press)**.

The system uses **base statistical values** derived from D1 Men's College Basketball statistics, which are then modified by team attributes and in-game settings to produce final resolution values. These values are treated as **absolute base values** (not percentages), so while they may start aggregating to 100, they don't need to stay at 100 as modifications are applied.

### Design Principles

- **Strategic**: Outcomes reflect matchup quality, team attributes, and tactical decisions
- **Simple**: Single calculation, linear modifications, one decision point
- **Transparent**: Clear logic flow, easy to understand and tune
- **SS&S**: One system for all turn types, easy to extend and maintain

### Team Attributes Used

The following team attributes are used in resolution calculations, with a range of **-10 to 10**:

- `offensive_efficiency` - Offensive team's efficiency rating
- `defensive_efficiency` - Defensive team's efficiency rating
- `foul_modifier` - Team's foul tendency modifier
- `turnover_modifier` - Team's turnover tendency modifier
- `fb_efficiency` - Fast break efficiency (for Fast Break turns)
- `pt_efficiency` - Press/Trap efficiency (for HCT/FCP turns)

**Note**: Positive values are always positive for the team, negative values are always negative. The system must be mindful of when to add or subtract attribute modifications from base result values.

### Attribute Inversion

When possession changes and the other team has the ball, team attributes are **inverted** (offense & defense roles swap). The team that was on offense becomes the defense team, and vice versa.

### Minimum Values

All resolution result values have a **minimum value of 2**. There are no maximum values.

---

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
- `turnover_modifier`
- `foul_modifier`

**Defense Team:**
- `defensive_efficiency`
- `foul_modifier`
- `aggression` setting (from `strategy_calls["aggression_call"]` - strings: "passive", "normal", "aggressive")

#### Step 2: Calibrate Universal Constants

**Universal Base Constants:**
- `STANDARD_D_FOUL = 96`
- `STANDARD_O_FOUL = 7`
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
STANDARD_D_FOUL = 96 + int(defense_team.foul_modifier * 0.4)
STANDARD_D_FOUL = min(98, STANDARD_D_FOUL)  # Max 98

# Standard O Foul calibration
STANDARD_O_FOUL = 7 - offense_team.foul_modifier
STANDARD_O_FOUL = max(2, STANDARD_O_FOUL)  # Min 2

# Steal thresholds calibration
HARD_STEAL = -200 - offense_team.turnover_modifier
SOFT_STEAL = -100 - offense_team.turnover_modifier

# Foul thresholds calibration (on steal attempts)
HARD_FOUL = 200 - int(defense_team.foul_modifier * 0.6)
SOFT_FOUL = 100 - int(defense_team.foul_modifier * 0.6)

# Dead Ball Turnover calibration
DEAD_BALL_TURNOVER = 7 - int(0.5 * offense_team.turnover_modifier)
# Note: Minimum value enforcement is handled by the calibration formulas above
# (STANDARD_O_FOUL has min 2, STANDARD_D_FOUL has max 98)
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
  - **Range Overlap:** `STANDARD_O_FOUL` and `STANDARD_D_FOUL` will never overlap, as the maximum adjustment for either is ±10, ensuring they remain in separate ranges (O_FOUL: 2-17, D_FOUL: 92-98).

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
These thresholds are base universal values, adjusted at the start of each game based on the offensive team's `turnover_modifier`:

- `HARD_STEAL = -200` (defense wins decisively)
- `SOFT_STEAL = -100` (defense wins marginally)
- `HARD_FOUL = 200` (offense wins decisively, defender reaches)
- `SOFT_FOUL = 100` (offense wins marginally, defender reaches)
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

**Threshold Adjustment:**
At the start of each game, universal thresholds are adjusted based on the offensive team's `turnover_modifier`:
- Positive `turnover_modifier` (lower turnover risk) → thresholds adjusted to favor offense
- Negative `turnover_modifier` (higher turnover risk) → thresholds adjusted to favor defense
- Adjustment formula: `adjusted_threshold = base_threshold + (turnover_modifier * adjustment_factor)`

**Note:** The exact adjustment factor will be determined during implementation to balance game outcomes with statistical baselines.

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

