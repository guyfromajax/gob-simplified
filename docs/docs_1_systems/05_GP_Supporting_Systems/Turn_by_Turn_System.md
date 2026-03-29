# Turn-by-Turn System ✅ **COMPLETE** (February 2025)

## Canonical Turn Types

Use this list as the canonical turn-type set across backend/frontend docs.

- `HCO`
- `FCP`
- `HCT`
- `FAST_BREAK`
- `OREB`
- `OPENING_TIP`
- `BASELINE_INBOUND` (**BIP**)
- `SIDE_INBOUND` (**SIP**)
- `FREE_THROW`
- `TIMEOUT`

## Base Constants

**Purpose:** The turn-by-turn system processes gameplay one turn at a time, allowing for real-time animation and user interaction. Each turn is fetched from the backend, animated, and then the next turn is requested.

**Turn Data Structure:** Every turn result contains data organized into three distinct buckets:
1. **Bucket 1 (Standard/Universal Fields)** - Always present, core game state and routing
2. **Bucket 2 (Bespoke/Turn-Specific Fields)** - Conditional, handler-specific data
3. **Bucket 3 (Animation Data)** - Always present structure, contents vary by turn type

**Resolution System:** Centralized approach to determining turn outcomes across all major turn types (HCO, Fast Break, HCT, FCP) using base statistical values modified by team attributes.

**Team Attributes Used in Resolution:**
- `offensive_efficiency` - Offensive team's efficiency rating (-10 to +10)
- `defensive_efficiency` - Defensive team's efficiency rating (-10 to +10)
- `discipline` - Team's turnover tendency modifier (formerly `turnover_modifier`, -10 to +10)
- `fight` - Team's foul tendency modifier (formerly `foul_modifier`, -10 to +10)
- `fb_efficiency` - Fast break efficiency (for Fast Break turns, -10 to +10)
- `pt_efficiency` - Press/Trap efficiency (for HCT/FCP turns, -10 to +10)

**Key Files:**
- `BackEnd/models/turn_manager.py` - Standard fields (Bucket 1), turn creation
- `BackEnd/models/game_manager.py` - `_append_turn()` (single funnel for appending turns + **player coords sync**)
- `BackEnd/utils/shared.py` - `sync_lineup_coords_from_turn()`, `apply_coords_from_animations_list()`
- `BackEnd/models/shot_manager.py` - Shot-specific fields (Bucket 2)
- `BackEnd/engine/phase_resolution.py` - FCP/HCT/Free Throw fields (Bucket 2), resolution calculations
- `BackEnd/models/animator.py` - Animation data creation (Bucket 3)
- `FrontEnd/static/js/phaser/gameScene.js` - `simulateTurnByTurn()` method

## System Flow

1. **Backend Turn Creation**: Handler creates result with Bucket 2 (bespoke fields)
2. **Turn Manager Processing**: Adds Bucket 1 (standard fields) and calls Animator for Bucket 3
3. **Turn Append + Coords Sync**: `GameManager._append_turn()` appends the turn, then runs `sync_lineup_coords_from_turn()` so all **10 active players**’ `Player.coords` match the same spatial data the frontend uses for that turn (see **Player coordinates sync** below).
4. **Result Serialization**: Complete turn data serialized to JSON and sent to frontend
5. **Frontend Animation**: Receives turn data, uses all three buckets for routing, animation, and UI updates
6. **Quarter Completion**: Final turn of quarter animated before quarter completion handling

## Long Form Documentation

### Overview

The Turn-by-Turn System is the core gameplay loop that processes each possession one turn at a time. It consists of three main components:

1. **Turn Data Structure** - Three-bucket organization for clear separation of concerns
2. **Turn-by-Turn Simulation** - Frontend loop that fetches, animates, and processes turns sequentially
3. **Resolution System** - Backend logic for determining turn outcomes based on team attributes and game state

**Status:** ✅ Fully implemented and operational

---

### Turn Data Structure: Three Data Buckets

Every turn result from the backend contains data organized into **three distinct buckets**:

#### Bucket 1: Standard/Universal Fields ✅ **Always Present**

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

#### Bucket 2: Bespoke/Turn-Specific Fields ⚠️ **Conditional**

**Set by:** Handlers (`shot_manager.py`, `phase_resolution.py`, `turn_manager.py`) - Added only when relevant

**Shot Results (MAKE/MISS):**
- `shooter`, `shooter_id`, `shooter_pos` - Shooter information
- `ball_handler`, `passer`, `screener`, `defender` - Participant names
- `points`, `scoring_team` - Scoring data (if made)
- `next_play_type` - "BASELINE_INBOUND", "HCO", "FAST_BREAK", "FREE_THROW", etc.
- `dreb_outlet_pass` - `{passer_id, receiver_id}` outlet contract for `MISS/BLOCK -> DREB -> {HCO|HCT|FCP}` transitions
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

#### Bucket 3: Animation Data ✅ **Always Present (but may be empty)**

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

#### Data Flow Pattern

```
1. Handler (shot_manager.py, phase_resolution.py, etc.)
   ↓ Creates result dict with Bucket 2 (bespoke fields)
   
2. turn_manager.py::run_micro_turn()
   ↓ Adds Bucket 1 (standard fields) to result
   ↓ Calls Animator to create Bucket 3 (animation data)
   
3. game_manager.py::_append_turn(result)
   ↓ Appends to turns + text_log
   ↓ sync_lineup_coords_from_turn(game, result)  ← aligns Player.coords for all 10 lineup players
   
4. Result serialized to JSON
   ↓ Sent to frontend
   
5. Frontend receives complete turn data
   ↓ Uses all three buckets for routing, animation, and UI updates
```

#### Player coordinates sync (backend) ✅

**Problem solved:** Logic that reads `Player.coords` on the next turn must match the floor layout implied by the turn the client just animated. Previously, only players appearing in `animations[]` had `coords` updated (`update_player_coords_from_animations`), and explicit maps such as **`offense_getback_coords`** / **`defense_release_coords`** were not applied to `Player.coords`, so some location-based logic could run on **stale** coordinates.

**Single end-of-turn sync:** After every turn is appended via **`GameManager._append_turn()`**, **`sync_lineup_coords_from_turn(game, turn_result)`** (`BackEnd/utils/shared.py`) updates **all five home + five away** lineup players (non-`None` slots) using this **merge order**:

1. **Carry forward** — Start from each player’s current `Player.coords` (default `50, 25` if missing).
2. **Animations** — For each row in `turn_result["animations"]`, set final `{x, y}` from `end` if present, else from the **last** `movement[]` step’s `coords` (same family as the frontend track).
3. **Explicit overlays** (fixed order; later wins for the same `player_id`): **`defense_release_coords`**, then **`offense_getback_coords`**.

**Mid-turn shot resolution:** Before **`resolve_shot()`** in a few **`phase_resolution`** paths (HCO skeleton, FCP shot, HCT shot), **`apply_coords_from_animations_list(game, animations)`** applies only the animation list to matching players so shot/block math sees updated positions; the full **10-player** sync still runs when the turn is appended.

**Quarter / bypass turns:** `BackEnd/main.py` routes opening tip, quarter-start baseline inbound, and timeout SIP turns through **`_append_turn`** so they receive the same sync (carry-forward if a turn has no spatial deltas).

**Removed:** `update_player_coords_from_animations` and the duplicate coords call at the end of `run_micro_turn()` (replaced by the append-funnel sync).

#### Key Design Principles

1. **Bucket 1 (Standard):** Single source of truth for game state, routing, and universal context
2. **Bucket 2 (Bespoke):** Handler-specific data - only present when relevant
3. **Bucket 3 (Animation):** Always present structure, but contents vary by turn type

**Benefits:**
- ✅ Clear separation of concerns (universal vs. turn-specific vs. animation)
- ✅ Frontend can always rely on Bucket 1 being present
- ✅ Handlers only add what they need (no bloated data)
- ✅ Animation data structure is consistent (even if empty)

---

### Turn-by-Turn Simulation Flow

The turn-by-turn simulation system processes gameplay one turn at a time, allowing for real-time animation and user interaction. Each turn is fetched from the backend, animated, and then the next turn is requested.

**Frontend Implementation:**
- **Location:** `FrontEnd/static/js/phaser/gameScene.js` - `simulateTurnByTurn()` method
- **Flow:**
  1. Fetch turn from backend via `/api/simulate-turn` endpoint
  2. Check if turn exists (`turnData.turn`)
  3. If no turn, break immediately (quarter already ended)
  4. Animate the turn using all three data buckets
  5. Check for `quarter_complete` flag AFTER animation
  6. If `quarter_complete: True`, handle quarter completion
  7. Request next turn and repeat

#### Quarter Completion Handling

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

### Resolution System

The Resolution System is a centralized, unified approach to determining turn outcomes across all major turn types: **HCO (Half Court Offense)**, **Fast Break**, **HCT (Half Court Trap)**, and **FCP (Full Court Press)**.

**Status:** ✅ Fully implemented and operational

#### Design Principles

- **Strategic**: Outcomes reflect matchup quality, team attributes, and tactical decisions
- **Simple**: Single calculation, linear modifications, one decision point
- **Transparent**: Clear logic flow, easy to understand and tune
- **SS&S**: One system for all turn types, easy to extend and maintain

#### Team Attributes Used

The following team attributes are used in resolution calculations, with a range of **-10 to 10**:

- `offensive_efficiency` - Offensive team's efficiency rating
- `defensive_efficiency` - Defensive team's efficiency rating
- `discipline` - Team's turnover tendency modifier (formerly `turnover_modifier`)
- `fight` - Team's foul tendency modifier (formerly `foul_modifier`)
- `fb_efficiency` - Fast break efficiency (for Fast Break turns)
- `pt_efficiency` - Press/Trap efficiency (for HCT/FCP turns)

**Note**: Positive values are always positive for the team, negative values are always negative. The system must be mindful of when to add or subtract attribute modifications from base result values.

#### Base Statistical Values

The system uses **base statistical values** derived from D1 Men's College Basketball statistics, which are then modified by team attributes and in-game settings to produce final resolution values. These values are treated as **absolute base values** (not percentages), so while they may start aggregating to 100, they don't need to stay at 100 as modifications are applied.

#### Attribute Inversion

When possession changes and the other team has the ball, team attributes are **inverted** (offense & defense roles swap). The team that was on offense becomes the defense team, and vice versa.

#### Minimum Values

All resolution result values have a **minimum value of 2**. There are no maximum values.

#### Implementation

**Location:** `BackEnd/engine/phase_resolution.py` - `resolve_hco_outcome()` and related functions

**Process:**
1. Calculate base statistical values for each outcome type
2. Apply team attribute modifications (offensive_efficiency, defensive_efficiency, discipline, fight)
3. Apply in-game settings modifications (aggression level, tempo, etc.)
4. Enforce minimum values (all values ≥ 2)
5. Use weighted random selection to determine outcome

**Example (HCO Resolution):**
- Base values: Shot=70, O_Foul=7, D_Foul=10, TO=7, Steal=6
- Apply team attributes: Add/subtract based on offensive_efficiency, defensive_efficiency, discipline, fight
- Apply aggression setting: Modify defensive foul and steal likelihoods
- Enforce minimums: Ensure all values ≥ 2
- Weighted random: Select outcome based on final values

**For detailed resolution logic, see:** `docs/docs_1_systems/05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md`

---

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` - Standard fields (Bucket 1), turn creation (lines 423-650)
- `BackEnd/models/shot_manager.py` - Shot-specific fields (Bucket 2)
- `BackEnd/engine/phase_resolution.py` - FCP/HCT/Free Throw fields (Bucket 2), resolution calculations
- `BackEnd/models/animator.py` - Animation data creation (Bucket 3, lines 512-522)

**Frontend:**
- `FrontEnd/static/js/phaser/gameScene.js` - `simulateTurnByTurn()` method (lines 1715-1750, 1937-1970)

**Reference Documentation:**
- `docs/GP_Core_Docs/TURN_SYSTEM.md` - Complete turn data structure and execution patterns reference
- `docs/UNIFIED_DATA_STRUCTURE_ANALYSIS.md` - Analysis of data structure patterns
- `docs/docs_1_systems/05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md` - Detailed HCO resolution logic

