# Master Game Documentation

> **Last Updated:** January 2025
> **Previously:** `docs/Animation_System/animation_system.md`

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
- `docs/GP_Core_Docs/TURN_SYSTEM.md` - Complete turn data structure and execution patterns reference
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
- `BALL_OWNERSHIP_CONSOLIDATION_PLAN.md` - Ball ownership system consolidation (December 2024)
- `docs/Animation_System/animation_system.md` - Complete ball animation system documentation

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
- `docs/Animation_System/animation_system.md` - BallController state management (see "State Management Patterns" section)

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


---

## Turn-by-Turn Simulation System ✅ **COMPLETE** (February 2025)

The turn-by-turn simulation system processes gameplay one turn at a time, allowing for real-time animation and user interaction. Each turn is fetched from the backend, animated, and then the next turn is requested.

### Quarter Completion Handling

**Critical Pattern:** The final turn of each quarter (the turn that consumes all remaining time) must be animated before quarter completion is handled.

**Backend Behavior:**
- When a turn is simulated that consumes all remaining time (`time_remaining <= 0`), the backend:
  1. Creates the turn normally (with full animation data)
  2. Sets `quarter_complete: True` in the response
  3. Returns the turn with `quarter_complete: True`

**Frontend Behavior:**
- The frontend checks for `quarter_complete` **AFTER** animating the turn, not before
- If `!turnData.turn` (no turn returned), the frontend breaks immediately (quarter already ended)
- If `turnData.turn` exists but `quarter_complete: True`, the frontend:
  1. Animates the turn first (it's the final turn of the quarter)
  2. Checks `quarter_complete` after animation completes
  3. Handles quarter completion (updates scores, breaks loop, etc.)

**Implementation Location:**
- `FrontEnd/static/js/phaser/gameScene.js` `simulateTurnByTurn()` method
- Lines 1715-1750: Early break only if `!turnData.turn`
- Lines 1937-1970: Quarter completion check after animation

**Key Point:** This ensures the final turn of each quarter is always animated, providing a complete visual experience for the user.

---

## End of Game System ✅ **COMPLETE** (January 2025)
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

**Clock Preservation for Timeout Navigation:**
- **Location:** `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()` function
- **Logic:** Clock is retrieved using a prioritized fallback chain:
  1. **API Response** (`timeoutResult.clock`): **Most reliable** - backend source of truth, returned by `/api/call-timeout` endpoint at the moment the timeout is called
  2. **DOM Element** (`#game-clock`): What's actually displayed to the user
  3. **scene.simData.clock**: Updated by `updateScoreboard()` as turns are processed (lines 1153-1158 in `gameScene.js`)
  4. **Last Processed Turn**: If turns array exists, get clock from the last turn's `clock` or `game_clock` field
  5. **URL Parameters**: Fallback for initial load scenarios
  6. **Default**: `8:00` if no clock found (should never happen in normal flow)
- **Key Fix (February 2025):** 
  - **Initial Fix:** `scene.simData.clock` was only set on initial load and never updated, causing stale clock values. Fixed by updating `scene.simData.clock` in `updateScoreboard()` whenever a turn's clock is processed.
  - **Final Fix:** The `/api/call-timeout` endpoint now returns the current clock value (`gm.game_state.get("clock")`) in its response, ensuring the frontend always has the accurate clock at the moment the timeout is called. This prevents timing issues where the DOM or scene state might be stale when the timeout button is pressed.

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

# Return timeout response with current clock (backend source of truth)
return {
    "message": f"Timeout called by {calling_team.name}",
    "calling_team": calling_team.name,
    "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
    "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
    "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
    "clock": gm.game_state.get("clock", "8:00"),  # ✅ Current clock at timeout moment
    "time_remaining": gm.game_state.get("time_remaining", 480),  # Also include time_remaining
}
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
  - **Retrieval Priority:** DOM element → scene.simData.clock → last processed turn → URL params → default
  - **Updated in:** `updateScoreboard()` updates `scene.simData.clock` as turns are processed

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

## End of Game System ✅ **COMPLETE** (January 2025)

### Overview

The End of Game System handles game completion, displays final scores, and provides navigation to the Box Score page and appropriate Command Center (Tournament, Franchise, or Mode Select for Single Game).

### Game Completion Flow

**Trigger:**
- Game completes when Q4 ends (or overtime if applicable)
- Detected in `gameScene.js` when `quarter === 4` and game is finalized

**Completion Popup:**
- **Location:** `FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`
- **Display:** Shows final score, "Box Score" button, and "Go To Locker Room" button
- **Parameters Passed:**
  - `gameId` - Game document ID
  - `mode` - Game mode: 'single', 'tournament', or 'franchise'
  - `tournamentId` - Tournament ID (for tournament mode only)
  - `franchiseId` - Franchise ID (for franchise mode only)
  - `teamId` - Team ID (ObjectId) for navigation anchor
  - `finalScore` - Final score object with homeTeam, awayTeam, homeScore, awayScore

### Navigation Anchor Preservation (SS&S - January 2025)

**✅ Complete Navigation Anchor Set:** When a game completes, the completion popup preserves all three navigation parameters:
1. **`mode`** (franchise/tournament/single) - Which collection/endpoints to use
2. **`doc_id`** (franchise_id/tournament_id) - Which document within that collection
3. **`team_id`** (ObjectId string) - Which team within that document (user's team)

**Implementation Flow:**
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

**Benefits:**
- **No Fallback Needed:** Prevents fallback to `/tournament/active?user_team_id=...` which requires ObjectId serialization
- **Complete Context:** All three navigation parameters preserved for seamless return to command center
- **Consistent Pattern:** Matches navigation anchor preservation pattern used throughout the application

### Box Score Navigation

**Box Score URL Construction:**
- **Location:** `gameCompletionPopup.js` (lines 59-64)
- **Parameters Included:**
  - `game_id` - Game document ID
  - `home` - Home team name
  - `away` - Away team name
  - **✅ SS&S (January 2025):** Also includes `mode`, `tournament_id`, `franchise_id`, and `team_id` for proper navigation from Box Score page

**Box Score "Go To Locker Room" Button:**
- **Location:** `FrontEnd/static/box-score.js` - `setupLockerRoomButton()` function
- **Navigation Logic (Priority Order):**
  1. **Mode Parameter (Highest Priority):** If `mode` is set in URL params, use it directly
  2. **ID Parameters:** Check for `tournament_id` or `franchise_id` in URL params
  3. **LocalStorage (Last Resort):** Only check localStorage if URL params are not available (for backward compatibility)
- **Command Center URLs:**
  - **Tournament Mode:** `/static/tournament.html?tournament_id={id}&team_id={id}`
  - **Franchise Mode:** `/static/franchise-command-center.html?franchise_id={id}&team_id={id}`
  - **Single Game Mode:** `/static/mode-select.html`

**Key Fix (January 2025):**
- Box Score page now receives `mode`, `tournament_id`, `franchise_id`, and `team_id` in URL params
- Navigation logic prioritizes URL parameters over localStorage to prevent stale data issues
- Franchise mode uses correct path: `/static/franchise-command-center.html` (not `/franchise/command-center`)

### Backend ObjectId Serialization

- **`/tournament/active` endpoint:** Now serializes all ObjectIds in nested structures using `jsonable_encoder(doc, custom_encoder={ObjectId: str})`
- **Consistent with `/tournament/state`:** Both endpoints use the same serialization pattern
- **Prevents 500 Errors:** Ensures nested ObjectIds (e.g., in `teams` collection) are properly serialized for JSON response

### Key Files

- **`FrontEnd/static/js/phaser/gameScene.js`** - Detects game completion, calls completion popup
- **`FrontEnd/static/js/phaser/utils/gameCompletionPopup.js`** - Creates completion popup, constructs navigation URLs
- **`FrontEnd/static/box-score.js`** - Handles "Go To Locker Room" button navigation
- **`BackEnd/api/api.py`** - ObjectId serialization for tournament/franchise endpoints

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
  },
  "man_defense": {
    "Man": 100
  },
  "slot_assignments": {
    "1": { "section": "motion", "playId": "motion-1", "dropdown": "Inside" },
    "2": { "section": "set-play-inside", "playId": "set-inside-1" },
    // ... other slot assignments
  },
  "motion_dropdowns": {
    "motion-1": "Inside",
    "motion-2": "Attack",
    // ... other motion dropdown selections
  },
  "position_filters": {
    "standard": [],
    "PG": ["68f919f9065f78d452557809", "68f919f9065f78d452557810", ...],  // play_id (ObjectId strings)
    "SG": ["68f919f9065f78d452557811", ...],
    "SF": [...],
    "PF": [...],
    "C": [...]
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

### Position Filter Buttons ✅ **IMPLEMENTED** (January 2025)

**Location:** Header row, horizontally centered below page title  
**Buttons:** "Standard", "PG", "SG", "SF", "PF", "C"  
**Purpose:** Filter offense plays by position to help users organize their playbook

**Button Styling:**
- **Unpressed:** Silver border, clear fill, bold silver copy
- **Selected:** Gold border, dark black fill, bold gold copy
- Same size and shape as the "Back" button

**Selection Rules:**
- Maximum **2 buttons** can be selected at once
- If a third button is selected, the oldest selection is automatically unselected (FIFO - First In, First Out)
- Users can deselect a button by clicking it again

**Filtering Logic:**
- **Initial State:** No buttons selected - **all offense plays are hidden**
- **Single Button Selected:** Shows only plays in that position's array
  - Example: "Standard" selected → shows only Standard plays
  - Example: "PF" selected → shows only PF plays
- **Multiple Buttons Selected:** Uses **union (OR) logic** - play must be in **ANY** selected position array
  - Example: "Standard" and "PF" selected → shows plays in Standard array OR PF array (both sets combined)
  - Example: "PF" and "SG" selected → shows plays in PF array OR SG array (both sets combined)
  - Plays are added cumulatively as buttons are selected
  - Plays are removed when their position button is unselected
- **Defense Plays:** Not affected by position filters (always visible)

**Storage:**
- Position filters are stored per team in `playbook_settings.position_filters`
- Structure:
  ```javascript
  position_filters: {
    "standard": [],  // Empty = show all plays when selected
    "PG": [play_id_1, play_id_2, ...],  // Array of play_id (ObjectId strings)
    "SG": [play_id_3, play_id_4, ...],
    "SF": [play_id_5, play_id_6, ...],
    "PF": [play_id_7, play_id_8, ...],
    "C": [play_id_9, play_id_10, ...]
  }
  ```
- **Play ID Format:** Uses database `play_id` (ObjectId string) for consistency and stability
  - Matches the pattern used for other database object references throughout the game engine
  - Stored as strings in the database (e.g., `"68f919f9065f78d452557809"`)
  - Frontend displays play names, but filtering uses `play_id` for matching

**API Integration:**
- `GET /api/playbooks` returns `position_filters` in the response
- `POST /api/playbooks` saves `position_filters` when included in `playbook_settings`
- Default initialization: All position arrays start empty (can be customized later)

**Initialization and Backward Compatibility:**
- When team objects are created (Single Game, Tournament, Franchise modes), `playbook_settings` is initialized with `position_filters` populated with "Standard" and "PF" plays
- For existing team objects that don't have `playbook_settings` or have a falsy value (None, empty dict), the system automatically:
  1. Checks for missing/falsy `playbook_settings` in `get_playbooks()` endpoint
  2. Creates and saves `playbook_settings` with populated `position_filters` if missing
  3. Reloads the document to ensure fresh data is returned
- This defensive check ensures backward compatibility with team objects created before `position_filters` were introduced
- The check uses `not team_obj.get("playbook_settings")` to handle both missing keys and falsy values (None, empty dict)

**Affected Sections:**
- Position filtering applies to all offense play sections:
  - Motion Offense
  - Set Play Inside Offense
  - Set Play Attack Offense
  - Set Play Outside Offense
- Defense sections are not filtered (always visible)

**Implementation:**
- Frontend: `FrontEnd/static/playbooks.js` - `handlePositionFilterClick()`, `shouldShowPlay()`, `renderSection()`
- Backend: `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()`, `get_playbooks()`, `save_playbooks()`

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
4. Load skeleton data:
   - **Motion:** `base_loop` (direct steps array)
   - **Set Play:** `successful` variant, version v0 from `versions` array (or direct steps for backward compatibility)
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
- **Single Game:** 
  - `games_collection` → `game_doc.teams.{team_id}.playbook_settings` (per game instance)
  - `teams_collection` → `team_doc.playbook_settings` (shared across all Single Game instances for the same team)
  - **Cross-Instance Persistence:** Settings saved to both locations. When loading, checks game document first, then falls back to core `teams` collection if game document has no settings.
- **Tournament:** `tournaments_collection` → `tournament_doc.teams.{team_id}.playbook_settings`
- **Franchise:** `franchises_collection` → `franchise_doc.franchise_teams.{team_id}.playbook_settings`

**Mode Isolation:**
- Each game mode maintains its own playbook settings
- Settings from one mode don't affect another
- Settings persist across games within the same mode
- **Single Game Mode:** Settings persist across Single Game instances for the same team (via core `teams` collection)

**Data Persistence (January 2025, Updated February 2025):**
- ✅ **`playbook_settings` is preserved when saving game state** - When `summarize_game_state()` saves game state (timeouts, quarter breaks, etc.), it loads existing `playbook_settings` from the database and includes them in the `teams.{team_id}` object (or `franchise_teams.{team_id}` for franchise mode)
- ✅ **Settings persist across navigation** - When navigating Playbooks → Game Plan → Lineup → Gameplay, settings are preserved. When returning to Playbooks page, settings are loaded from API and applied to UI state.
- ✅ **Cross-Instance Persistence (Single Game)** - Settings set in one Single Game instance persist to the next Single Game instance for the same team (stored in core `teams` collection)
- ✅ **Mode-Specific Path Handling** - The `get_playbooks()` function correctly uses `franchise_teams.{team_id}` for franchise mode and `teams.{team_id}` for tournament/single mode when initializing missing `playbook_settings` and reloading team objects. This ensures settings saved from Command Centers (FCC/TCC) are correctly loaded during gameplay.
- This ensures `slot_assignments`, percentages, and other playbook settings persist across all game state saves and page navigation
- **Implementation:** 
  - `BackEnd/utils/shared.py` `summarize_game_state()` (lines 659-726) preserves `playbook_settings` from database when `exclude_animations=True` (database saves)
  - `BackEnd/api/gameplan_routes.py` `save_playbooks()` saves to both game document and core `teams` collection (Single Game mode), or to `franchise_teams.{team_id}` (Franchise mode) or `teams.{team_id}` (Tournament mode)
  - `BackEnd/api/gameplan_routes.py` `get_playbooks()` (lines 1070-1095) correctly initializes missing `playbook_settings` using mode-specific paths (`franchise_teams` for franchise, `teams` for tournament/single) and reloads from the correct location
  - `FrontEnd/static/playbooks.js` `loadPlaybookPercentagesFromAPI()` and `loadSlotAssignmentsFromAPI()` load and apply settings to UI state

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
  - Default speed: 450 pixels/second (Normal preset)

- **`getBallDuration(ballSprite, targetX, targetY)`** (`ballTween.js`)
  - Calculates ball movement duration based on distance from current position to target
  - Uses `getBallSpeed()` which checks `window.__GAME_SPEED` for dynamic speed settings
  - Formula: `duration = (distance / speed) * 1000` (converts to milliseconds)
  - Default speed: 450 pixels/second (Normal preset)
  - Clamped between 50ms (minimum) and 1000ms (maximum)

#### Game Speed Integration

**Speed Presets** (`gameSpeedManager.js`):
- **Slow**: 350 pixels/second
- **Normal**: 450 pixels/second (default)
- **Fast**: 550 pixels/second

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
- `timeouts` (int) - Remaining timeouts (default: 4)
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


