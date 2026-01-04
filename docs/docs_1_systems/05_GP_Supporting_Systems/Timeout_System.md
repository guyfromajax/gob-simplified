## Timeout System ✅ **COMPLETE** (January 2025)

**Base Constants**

1. **Timeout Turn Type**: `TIMEOUT`
2. **Timeout Reasons**:
   - `"USER"` - User-initiated timeout (via timeout button)
   - `"COMPUTER"` - AI-initiated timeout
   - `"FOUL_OUT"` - Player fouls out (automatic timeout)
   - `"QUARTER_END"` - Quarter end timeout (currently not used)
3. **Next Play Types**: `"SIDE_INBOUND"` (default), `"FREE_THROW"` (special case)
4. **API Endpoints**:
   - `POST /api/call-timeout` - User-initiated timeout
   - `GET /api/game/{game_id}/lineup` - Fetch current lineups
   - `GET /api/gameplan` - Fetch game plan settings
5. **Database Storage**: `timeout_next_play_type`, `timeout_offense_team_id` in game document
6. **Navigation Helper**: `TimeoutNavigationHelper` (unified parameter building)
7. **Button Window**: 2.5-second pause during SIP/BIP turns

**System Flow (10 Steps)**

1. **Timeout Initiation** - User presses button or player fouls out
2. **Turn Creation** - Backend creates `TIMEOUT` turn via `setup_timeout_turn()`
3. **State Persistence** - Save `timeout_next_play_type` and `timeout_offense_team_id` to database
4. **Animation Freeze** - Frontend pauses all animations and stops animation loop
5. **Navigation** - User navigates to lineup screen (with `resume_from_timeout=true`)
6. **User Actions** - User makes lineup/game plan changes (or keeps current)
7. **Return Navigation** - User navigates back to court (helper preserves all params)
8. **State Restoration** - Backend restores timeout state from database (validates quarter)
9. **Turn Creation** - Backend creates SIP turn with correct possession team
10. **State Cleanup** - Backend clears timeout state from database, game continues

**Long Form Documentation**

### Overview

The timeout system allows game pauses for strategic adjustments, lineup changes, and game plan modifications. Timeouts are treated as standard game turns and integrate seamlessly with the existing transition system.

**Key Features:**
- Timeouts are standard game turns (same data structure and flow)
- Game state persists across timeout (scores, clock, fouls, timeouts, lineups)
- Lineup and game plan screens pre-populated with current settings
- Scoreboard displays immediately on timeout resume
- Uses same transition system as other game flows
- Database is single source of truth for timeout state
- Works consistently across all game modes (single, tournament, franchise)

### Timeout Turn Creation

**User-Initiated Timeout:**
- User presses timeout button during SIP/BIP turn (2.5-second pause window)
- Frontend calls `/api/call-timeout` endpoint
- Backend creates `TIMEOUT` turn via `turn_manager.setup_timeout_turn()`
- `TIMEOUT` turn appended to `gm.turns` array

**Foul-Out Timeout:**
- Player fouls out during shot resolution
- `result["fouled_out"] = True` set in `shot_manager.py`
- `game_manager.simulate_macro_turn()` detects `fouled_out` flag
- Captures `timeout_offense_team_id` before creating timeout turn
- Creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`
- **✅ CRITICAL FIX (January 2025):** Immediately saves game state to database (same pattern as user-initiated timeout)

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

### Next Play Type Determination

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

**Location:** `turn_manager.py` `setup_timeout_turn()` (lines 1611-1676)

**Logic:**
1. For foul-out timeouts: Uses `foul_out_context` to determine `next_play_type`
2. For regular timeouts with free throws: Uses `free_throws_remaining` to set `next_play_type = "FREE_THROW"`
3. For regular timeouts: Defaults to `next_play_type = "SIDE_INBOUND"`

**Stored In:** `game_state["timeout_next_play_type"]` for resume

### Foul Out Context System

**Purpose:** Stores detailed foul information to guide next play type determination

**Location:** `game_state["foul_out_context"]` dictionary

**Contents:**
- `foul_type`: "OFFENSIVE" or "DEFENSIVE"
- `is_shooting_foul`: Boolean (True for shooting fouls, False for non-shooting)
- `is_bonus`: Boolean (True if team is in bonus situation)
- `next_play_type`: "SIDE_INBOUND" or "FREE_THROW" (determined by foul context)
- `shooter`: Player object (for shooting fouls, stores shooter for free throw resume)

**Set By:** Foul resolution logic in `phase_resolution.py` (non-shooting fouls) and `shot_manager.py` (shooting fouls)

**Used By:** `turn_manager.py` `setup_timeout_turn()` to determine `next_play_type` for foul-out timeouts

### Possession Flip Logic

**Offensive Fouls:** Possession flips during SIP setup (not during foul resolution)
- Location: `phase_resolution.py` `resolve_non_shooting_foul()` sets `possession_flips: True`
- **✅ FIX (January 2025):** Does NOT call `game.switch_possession()` in `resolve_non_shooting_foul()`
- Actual flip happens in `game_manager.py` `simulate_macro_turn()` before `setup_side_inbound()`
- This prevents double-flipping and ensures consistent behavior (same pattern as dead ball turnovers)

**Defensive Fouls:** No possession flip
- If Shooting Foul: Next step: FREE_THROW (the shooting player shoots)
- If Non-Shooting Foul:
  - If Bonus Situation: Next step: FREE_THROW (the player the fouling player was guarding shoots)
  - If Non-Bonus Situation: Next step: SIDE_INBOUND

### Transition System Integration

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
    "time_remaining": gm.game_state.get("time_remaining", 480),
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
- **Franchise Game:** Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)

#### URL Parameters (Navigation Only)

**Purpose:** URL parameters are used for navigation/routing, not business logic. Database is the source of truth.

**Unified Navigation Helper System (SS&S - December 2025):**

All frontend navigation now uses a unified helper (`FrontEnd/static/js/shared/timeoutNavigationHelper.js`) for consistent parameter building across all entry points.

**Helper Functions:**
- `buildGameNavigationParams()`: Builds URL parameters with consistent SS&S logic
- `getResumeFromTimeout()`: Extracts `resume_from_timeout` from URL params
- `getGameId()`: Gets game ID from URL or localStorage

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

**Critical Frontend Pattern:**
- All navigation functions read URL params directly from `window.location.search` when called
- Does NOT rely on module-level variables that might be stale (especially after async delays)
- Helper ensures `game_id` and `resume_from_timeout` are always current when navigating
- **All navigation functions MUST use `TimeoutNavigationHelper`** - manual parameter preservation is fragile and can lose critical state (e.g., `clock` parameter)

#### LocalStorage (Frontend State Only)

**Purpose:** LocalStorage is used for frontend convenience, not business logic.

**Stored Data:**
- `game_id`: Current game identifier (for navigation)
- `game_home`: Home team name (for matchup validation)
- `game_away`: Away team name (for matchup validation)
- `franchise_id`: Franchise identifier (if applicable)
- `franchise_week`: Current week (if applicable)

**New Game Detection:**
- Frontend clears `game_id` from localStorage when starting a new game
- Prevents stale `game_id` from being passed to backend for new games

**Note:** LocalStorage is not used for timeout state - database is the source of truth.

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

### Timeout Button Functionality

**Feature Flag:**
- Location: `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`
- `ENABLE_TIMEOUT_BUTTON = true` (feature flag for modularity)

**Button State:**
- **Live:** Button is enabled and clickable (during 2.5-second pause window)
- **Dead:** Button is disabled with reduced opacity (all other times)

**2.5-Second Pause Window:**
- The timeout button is live during a mandatory 2.5-second pause at the start of SIP and BIP turns
- Location: `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- Progress bar appears during pause (orange fill with green border)
- Button becomes dead when inbound pass starts

**Timeout Eligibility:**
- The button is live for all SIP and BIP turns if:
  - The turn is a SIP or BIP turn
  - The team has timeouts remaining (checked via `/api/call-timeout` endpoint)

**Animation Freezing:**
- When timeout button is pressed, all animations are immediately paused
- Location: `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- Sets `scene.timeoutCalled = true` to stop the main animation loop

### Scoreboard Display Immediacy System

**Problem:** Scoreboard items (scores, fouls, timeouts, clock) need to display immediately when resuming from timeout, not wait for the next turn to complete.

**Solution:** Direct DOM updates with team object priority.

**Initial Value Extraction (`FrontEnd/static/js/phaser/gameScene.js`):**

All scoreboard items check team objects first (authoritative source), then fall back to game object:

```javascript
// Scores: Check team objects first
const homeScoreFromData = homeTeamObj?.score ?? simData.score?.[homeTeam];
const awayScoreFromData = awayTeamObj?.score ?? simData.score?.[awayTeam];

// Fouls: Check team objects first
const homeFoulsFromData = homeTeamObj?.team_fouls ?? simData.fouls?.home;
const awayFoulsFromData = awayTeamObj?.team_fouls ?? simData.fouls?.away;

// Timeouts: Check team objects first
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

**Clock Preservation for Timeout Navigation:**
- Location: `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()` function
- Clock is retrieved using a prioritized fallback chain:
  1. **API Response** (`timeoutResult.clock`): **Most reliable** - backend source of truth, returned by `/api/call-timeout` endpoint at the moment the timeout is called
  2. **DOM Element** (`#game-clock`): What's actually displayed to the user
  3. **scene.simData.clock**: Updated by `updateScoreboard()` as turns are processed
  4. **Last Processed Turn**: If turns array exists, get clock from the last turn's `clock` or `game_clock` field
  5. **URL Parameters**: Fallback for initial load scenarios
  6. **Default**: `8:00` if no clock found (should never happen in normal flow)

**Key Fix (February 2025):**
- **Initial Fix:** `scene.simData.clock` was only set on initial load and never updated, causing stale clock values. Fixed by updating `scene.simData.clock` in `updateScoreboard()` whenever a turn's clock is processed.
- **Final Fix:** The `/api/call-timeout` endpoint now returns the current clock value (`gm.game_state.get("clock")`) in its response, ensuring the frontend always has the accurate clock at the moment the timeout is called. This prevents timing issues where the DOM or scene state might be stale when the timeout button is pressed.

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
- Fetches current lineup for both teams
- Adds lineup params to URL (`home_pg`, `home_sg`, etc.)

**Frontend (`FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`):**
- Restores lineup from URL parameters on page load
- Pre-populates lineup slots with current players

**Game Plan Pre-Population:**

Current game plan settings are fetched and passed to the game plan screen:

**Frontend (`FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()`):**
- Fetches current game plan settings for the user's team
- Adds game plan settings to URL as JSON string

**Frontend (`FrontEnd/static/game-plan.js` `loadSettings()`):**
- Parses and applies game plan settings from URL on page load

**Lineup Screen Population (Foul Out):**
- Location: `FrontEnd/static/js/phaser/utils/foulOutPopup.js` `showFoulOutPopup()` function
- Fetches current lineup from URL parameters (same as timeout flow)
- Removes **only** the fouled-out player from the user's team lineup
- Leaves the fouled-out player's position empty (not replaced)
- Passes populated lineup (minus foul out player) to `TimeoutNavigationHelper`
- **Key Point:** Only removes the fouled-out player if they're on the user's team; other team's lineup is preserved

### Computer Team Lineup Management (January 2025)

The computer team automatically adjusts its lineup during timeouts and at quarter breaks based on player energy levels and foul counts.

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

2. **Foul-Based Filtering (by Quarter):**
   - **Q1:** Exclude if player fouls > 1
   - **Q2:** Exclude if player fouls > 2
   - **Q3:** Exclude if player fouls > 3
   - **Q4:** Exclude if player fouls > 3 AND > 4 minutes remaining (no exclusion if ≤ 4 minutes remaining)
   - **Overtime:** No foul exclusion for active players

3. **Fouled Out Players:**
   - Players with 5 or more fouls are always excluded (not considered active)

**Implementation Details:**
- **Function:** `build_lineup_from_mongo(team, game_state=None)` (`BackEnd/utils/db_utils.py`)
- **Lineup Completion:** `ensure_complete_lineup(team, game_state)` (`BackEnd/utils/db_utils.py`)
- Only affects computer team (user team lineups are never auto-adjusted)
- Works consistently across all game modes (single, tournament, franchise)

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
- `BackEnd/models/game_manager.py` `call_timeout()`: Unified timeout creation method
- `BackEnd/api/api.py` `call_timeout_endpoint()`: Handles user-initiated timeouts
- `BackEnd/api/api.py` `simulate_quarter_endpoint()`: Handles timeout resume flow
- `BackEnd/api/api.py` `restore_timeout_resume_state()`: Loads timeout state from database
- `BackEnd/api/api.py` `apply_timeout_resume_state_to_gm()`: Applies timeout state to GameManager
- `BackEnd/main.py` `simulate_quarter()`: Creates initial turn after timeout resume
- `BackEnd/utils/shared.py` `summarize_game_state()`: Saves game state to database
- `BackEnd/utils/db_utils.py`: Computer team lineup management functions

**Frontend:**
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`: Timeout button logic and state management
- `FrontEnd/static/js/phaser/utils/foulOutPopup.js`: Foul out popup and navigation
- `FrontEnd/static/js/shared/timeoutNavigationHelper.js`: Unified navigation helper
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleTimeout()`: Handles timeout turn
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`: Stops animation loop on timeout
- `FrontEnd/static/js/phaser/gameScene.js`: Scoreboard immediate update logic
- `FrontEnd/static/js/phaser/bootGame.js`: Auto-start logic for timeout resume
- `FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`: Pre-populates lineup from URL
- `FrontEnd/static/game-plan.js` `loadSettings()`: Pre-populates game plan from URL
- `FrontEnd/static/court.html`: Timeout button and progress bar HTML/CSS

**Tests:**
- `tests/test_timeout_functionality.py`: Comprehensive tests for timeout system

