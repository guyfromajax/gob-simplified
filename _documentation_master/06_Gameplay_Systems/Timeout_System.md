## Timeout System (Jan 2025 + Feb 2026 additions; **verified + fixed 2026-06-13**)

> **Note (2026-06-13):** Architecture verified accurate against code (unified `handle_timeout_save_and_response`, DB-as-source-of-truth resume, URL-param-as-frontend-truth, eligibility system). Backend line numbers refreshed where verified; inline frontend `(lines …)` citations are approximate and were **not** exhaustively re-verified — treat them as hints, prefer the function names. Single Game / Tournament mode references are tagged sunset (see `Sunset_Modes.md` / `bugs.md` `[CODE-CLEANUP]`).

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
- Works consistently across all game modes (franchise is live; **single / tournament are SUNSET** — see `Sunset_Modes.md`)
- **Player Momentum (MO):** a regular timeout decays each active player's MO toward 0 by `randint(0,1)` (the smallest of the break decay ranges — 0 means a timeout may leave MO unchanged; bench → 0). **Foul-out timeouts do NOT reset MO.** See [Player_Momentum_System.md](Player_Momentum_System.md).

### Player Attribute Persistence Across Resume (fixed 2026-06-22)

A timeout resume **always force-reloads the game from MongoDB** (`api.py` ~line 2714, `_drop_cached_game()` even when the game is warm in `ongoing_games`). This builds fresh `Player` objects whose attributes start from the **base roster record**, so any in-game attribute value not explicitly restored from the saved game doc is lost.

Two classes of attributes, restored differently in the resume loop (`api.py` `simulate_quarter_endpoint`, ~line 3064):

| Attribute class | Persisted? | How it survives resume |
|---|---|---|
| `NG` (energy) | yes | restored directly, then `_rescale_attributes()` |
| Malleable (`SC, SH, ID, OD, PS, BH, RB, ST, AG, FT`) | derived | recomputed as `anchor_X * NG` by `_rescale_attributes()` — never persisted individually |
| `MO, EM, CH` (dynamic, non-malleable) | yes | **must be restored directly** — NOT derived from anchors, so `_rescale_attributes()` does not reconstruct them |

**The bug (pre-2026-06-22):** `summarize_game_state()` correctly saved `MO`/`EM`/`CH` to the game doc, but the resume loop only read back `NG`. The `_initialize_game_stats` MO-restore branch (`main.py` ~line 98) was also skipped because `game_stats_initialized` is restored `True` on resume. Result: **MO (and EM/CH) reverted to base roster values on every timeout resume.**

**The fix:** the resume loop now also assigns `MO`/`EM`/`CH` from `saved_player_data["attributes"]` and syncs their `anchor_*` values (mirroring `_initialize_game_stats`). See [Data_Persistence_System.md](../01_Data_Persistence/Data_Persistence_System.md) for the persistence contract.

### Timeout Turn Creation

**User-Initiated Timeout:**
- User presses timeout button (always live, no restrictions)
- Frontend calls `/api/call-timeout` endpoint
- Backend creates `TIMEOUT` turn via `turn_manager.setup_timeout_turn()`
- `TIMEOUT` turn appended to `gm.turns` array
- Uses unified `handle_timeout_save_and_response()` helper function

**Computer-Initiated Timeout:**
- Computer AI detects timeout conditions during game simulation
- Backend creates `TIMEOUT` turn via `turn_manager.setup_timeout_turn()` in `simulate-turn` endpoint
- `TIMEOUT` turn appended to `gm.turns` array
- Uses unified `handle_timeout_save_and_response()` helper function (same as user timeout)

**Foul-Out Timeout:**
- Player fouls out during shot resolution
- `result["fouled_out"] = True` set in `shot_manager.py` (or added by `_check_lineups_for_foul_out` in game_manager)
- `game_manager.simulate_macro_turn()` detects `fouled_out` flag
- Uses the same unified timeout pipeline as all other timeouts:
  - `game_manager.call_timeout(...)`
  - `turn_manager.setup_timeout_turn(...)`
- **Possession for resume:** `timeout_offense_team_id` is set in `call_timeout()`. For **offensive foul** (charge or HCO o-foul), possession *flips* after the foul turn but we save state *before* that flip; so we explicitly set `timeout_offense_team_id = self.defense_team.team_id` when `foul_out_context.foul_type == "OFFENSIVE"`. For defensive foul-out (e.g. shooting foul) we use current offense. See `docs/To Do/player_foul_out_bug.md` (Solution summary) for edge cases.
- **FREE_THROW resume:** When next play is free throw (5th foul on shooting foul), we persist `timeout_free_throws_remaining`, `timeout_shooter_id`, etc.; on return we restore `offensive_state`, `shooter`, and FT count so the first `simulate_turn` creates the free throw.
- Creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"` and standard timeout payload fields
- Persists state using the same timeout save path used by regular timeouts

**Foul-Out Team Behavior Split:**
- **User team foul-out:** timeout pauses gameplay and routes user through lineup flow before resume.
- **Computer team foul-out:** timeout still uses unified backend turn creation/state persistence, but lineup is auto-rebuilt and gameplay continues without user intervention.

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

**Location:** `turn_manager.py` `setup_timeout_turn()` (~L3417)

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

### Foul Out Popup – Player Image

**Purpose:** Show the **fouling-out** player’s headshot in the foul-out modal (the player who has 5 fouls and is ejected). Works for every foul-out type: offensive foul, non-shooting defensive foul, shooting defensive foul, etc.

**How it works (same as Defensive Foul announcement):**
- **Id only for the image.** Do not use `player.photo` or any other field for the image URL. The image is built from the fouling-out player’s id and the path only.
- **Id from the turn.** Call sites pass `foulOutPlayerId` from the turn: `turn.foul_out_player?.player_id ?? turn.foul_out_player?.playerId` (gameScene) or `turnData.foul_out_player?.player_id ?? turnData.foul_out_player?.playerId` (AnimationEngine). If that’s missing, the popup falls back to `player?.player_id ?? player?.playerId ?? player?.id` for the image id.
- **Image path:** `/images/players/{foulOutPlayerId}.png` (string id; same as API `player_id`). Fallback: `/images/players/generic_headshot.png` on img `onerror`.
- **Static prefix:** On localhost/127.0.0.1 prepend `/static`. On Netlify and production use no prefix (site root is the static publish folder).

**Frontend (popup):**
- **File:** `FrontEnd/static/js/phaser/utils/foulOutPopup.js`
- **Logic:** `imagePlayerId` = `foulOutPlayerIdFromTurn` when present, else from `player`. `photoUrl` = `playerId ? staticPrefix + '/images/players/' + playerId + '.png' : ''`. No use of `player.photo` or `player.image_url` for the image.
- **Call sites:** `gameScene.js` and `AnimationEngine.js` pass `foulOutPlayerId` from the turn so the image is always wired to the fouling-out player’s id. The backend sets `foul_out_player` for every foul-out type, so this works universally.

### Foul Out Player Lineup Removal & Visual Indicators

**Purpose:** Removes fouled-out players from lineup and visually disables them on lineup screen

**Backend Implementation:**

**Ineligible Players Tracking:**
- Location: `game_state["ineligible_players"]` array
- Set By: `check_and_handle_foul_out()` in `phase_resolution.py` (line 135-136)
- Contains: Array of player IDs with 5+ fouls
- Persisted: Saved to database via `summarize_game_state()` and returned in `/api/game/{game_id}` response

**API Response:**
- Location: `BackEnd/api/api.py` `/api/game/{game_id}` endpoint
- **✅ FIX (January 2025):** Added `ineligible_players` to response in all three paths:
  - In-memory path (line ~1215): `"ineligible_players": gm.game_state.get("ineligible_players", [])`
  - Database path (line ~1479): `"ineligible_players": saved.get("ineligible_players", [])`
  - New game path (line ~1334): `"ineligible_players": []` (empty for new games)

**Frontend Implementation:**

**Lineup Removal:**
- Location: `FrontEnd/static/set-lineup.js` `removeIneligiblePlayersFromLineup()` (lines 1167-1206)
- Called: After `restoreLineupFromUrl()` to ensure fouled-out players are removed even if they were in URL params
- Logic:
  1. Iterates through all lineup positions (PG, SG, SF, PF, C)
  2. Finds player in roster by ID
  3. If player has `fouled_out` or `ineligible` flag, removes from lineup (sets position to `null`)
  4. Clears slot display (removes player card, marks slot as empty, disables drag)

**Visual Indicators:**
- Location: `FrontEnd/static/set-lineup.js` and `FrontEnd/static/set-lineup.css`
- Grid View (lines 513-519):
  - Adds `.ineligible` class to table row
  - Grey background: `#d3d3d3`
  - Opacity: `0.7`
  - `pointer-events: none` (disables interactions)
  - `cursor: not-allowed`
  - `draggable: false`
- Player View (lines 1731-1737):
  - Adds `.ineligible` class to player card
  - Same styling as Grid view (grey background, opacity, disabled interactions)
  - `draggable: false`
  - Click handler disabled (cannot fill slot)

**Player Marking:**
- Location: `FrontEnd/static/set-lineup.js` `loadRoster()` (lines 347-369)
- Logic:
  1. Fetches game data from `/api/game/{game_id}` endpoint
  2. Extracts `ineligible_players` array from response
  3. Marks matching players in roster with `fouled_out = true` and `ineligible = true`
  4. Re-renders views to show visual indicators

**Diagnostic Helper:**
- Location: `FrontEnd/static/set-lineup.js` (added after `removeIneligiblePlayersFromLineup()`)
- Function: `window.checkFoulOutStatus()`
- Usage: Run in browser console to verify foul-out status
- Returns: Object with fouled-out player count, names, positions, and lineup state
- Purpose: Helps debug foul-out lineup removal issues

**Flow:**
1. Player fouls out → Added to `game_state["ineligible_players"]` in backend
2. Game state saved to database → `ineligible_players` array persisted
3. User navigates to lineup screen → Frontend calls `/api/game/{game_id}`
4. API returns `ineligible_players` → Frontend receives array of player IDs
5. Frontend marks players → Sets `fouled_out = true` and `ineligible = true` in roster
6. Frontend removes from lineup → `removeIneligiblePlayersFromLineup()` clears position
7. Frontend applies visual indicators → Grey overlay and disabled interactions
8. User sees empty position → Can select replacement player

**Key Files:**
- `BackEnd/engine/phase_resolution.py` `check_and_handle_foul_out()`: Adds player to `ineligible_players`
- `BackEnd/api/api.py` `/api/game/{game_id}`: Returns `ineligible_players` in response
- `FrontEnd/static/set-lineup.js` `loadRoster()`: Marks fouled-out players
- `FrontEnd/static/set-lineup.js` `removeIneligiblePlayersFromLineup()`: Removes from lineup
- `FrontEnd/static/set-lineup.js` `renderRoster()` and `renderPlayerView()`: Apply visual indicators
- `FrontEnd/static/set-lineup.css`: Styles for `.ineligible` class

### Designated Free Throw Shooter Lock (added 2026-06-16)

**Rule:** When the first turn out of the Set Lineup screen is a **free throw**, the designated FT shooter **cannot be removed** from the active lineup. They **can** still be reordered (slid up/down) into different positions.

**Why it can occur on the user's own lineup:** on any foul-out stoppage the user is shown their own Set Lineup screen. If the user's team is the one owed the free throws, their FT shooter is in the active lineup and must not be benched before shooting.

**Designated shooter source:** `pending_ft_shooter_id(game_state)` (`BackEnd/utils/db_utils.py`) — pending when `offensive_state == "FREE_THROW"` or `timeout_next_play_type == "FREE_THROW"`; shooter id from live `game_state["shooter"]` or persisted `timeout_shooter_id`. Covers all pending FTs (shooting, bonus/one-and-one, technical).

**Computer-sim autoset guard:** `build_lineup_from_mongo()` derives the pending FT shooter and passes it as `force_include_ids` to `build_unified_autoset_lineup_from_eligible()`, which seats forced players into their best open slot before normal fill. This also covers the user-pressed Autoset (same `/api/autoset-lineup` → `build_lineup_from_mongo` path).

**Live-game UX lock:** `set-lineup.js` calls `GET /api/game/{game_id}/ft-lock` on timeout resume → `{ next_turn_is_free_throw, ft_shooter_id }`. When active, `updateSlotDisplay()` hides/disables that slot's remove button and renders a `Free Throw Shooter` overlay (`.ft-shooter-lock-overlay`); `clearSlot()` hard-refuses removal as a backstop. The slot stays draggable so reordering (a swap, which keeps the shooter in the lineup) still works; `assignToSlot()` already bails on a filled slot so a bench player can't overwrite the locked shooter.

**Key Files:**
- `BackEnd/utils/db_utils.py` `pending_ft_shooter_id()`, `build_lineup_from_mongo()`, `build_unified_autoset_lineup_from_eligible(force_include_ids=...)`
- `BackEnd/api/api.py` `GET /api/game/{game_id}/ft-lock`
- `FrontEnd/static/set-lineup.js` `loadFtShooterLock()`, `isFtLockedPlayer()`, `updateSlotDisplay()`, `clearSlot()`
- `FrontEnd/static/set-lineup.css`: `.slot.ft-shooter-locked`, `.ft-shooter-lock-overlay`
- Autoset algorithm detail: see `Lineup_Selection_Screen.md` § Auto-Set Lineup Feature

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

**Unified Timeout Handler (`BackEnd/api/api.py` `handle_timeout_save_and_response()`):**
```python
def handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="USER"):
    """
    Unified timeout save and response handler.
    Used by both user and computer timeouts to ensure identical behavior.
    """
    # Save to DB (same for both user and computer timeouts)
    db_summary = summarize_game_state(gm, exclude_animations=True)
    games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)
    
    # Return consistent response format (same for both user and computer)
    # Use saved data (db_summary) to ensure response matches what was saved to DB
    return {
        "turn": timeout_turn,
        "clock": db_summary.get("clock", gm.game_state.get("clock", "8:00")),
        "time_remaining": db_summary.get("time_remaining", gm.game_state.get("time_remaining", 480)),
        "quarter": db_summary.get("quarter", gm.quarter),
        "quarter_complete": False,  # Always False for timeout (not quarter end)
        "home_score": db_summary.get("score", {}).get(gm.home_team.name, 0),
        "away_score": db_summary.get("score", {}).get(gm.away_team.name, 0),
        "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
        "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
        # ... additional fields
    }
```

**User-Initiated Timeout (`BackEnd/api/api.py` `call_timeout_endpoint()`):**
```python
# Create timeout turn
timeout_turn = gm.call_timeout(
    calling_team=calling_team,
    timeout_reason="USER",
    rebuild_both_lineups=False,
    game_id=None  # Don't save here - we'll save below
)

# ✅ UNIFIED: Use shared helper function for timeout save and response
timeout_response = handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="USER")

# Return response with additional fields for user timeout endpoint compatibility
return {
    "message": f"Timeout called by {calling_team.name}",
    "calling_team": calling_team.name,
    "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
    "clock": timeout_response["clock"],  # ✅ Use saved data from DB (not cache)
    "time_remaining": timeout_response["time_remaining"],  # ✅ Use saved data from DB (not cache)
    # ... additional fields from timeout_response
}
```

**Computer-Initiated Timeout (`BackEnd/api/api.py` `simulate_turn_endpoint()`):**
```python
# Create timeout turn
timeout_turn = gm.call_timeout(
    calling_team=calling_team,
    timeout_reason="COMPUTER",
    rebuild_both_lineups=True,
    game_id=game_id
)

# Remove the TIMEOUT turn from turns so next API call can simulate the actual next turn
timeout_turn = gm.turns.pop()

# ✅ UNIFIED: Use shared helper function (same as user timeout)
timeout_response = handle_timeout_save_and_response(gm, timeout_turn, game_id, timeout_reason="COMPUTER")

# Return response (same format as user timeout)
return timeout_response
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

**Database Access by Mode:** _(Single / Tournament are SUNSET modes — retained while code remains; see `Sunset_Modes.md`)_
- **Single Game (sunset):** `games_collection` document
- **Tournament Game (sunset):** Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
- **Franchise Game:** Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)

#### URL Parameters (Single Source of Truth for Frontend Detection)

**Purpose:** URL parameters are used for navigation/routing AND as the single source of truth for frontend timeout resume detection. Database is used by backend for state restoration, but frontend relies exclusively on URL param for UI decisions.

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
   - Set `resume_from_timeout=false` if: `resumeFromTimeout === false` AND `gameId` exists (quarter break)
   - NOT for new game start (param intentionally omitted when no `gameId`)
   - **Supports any quarter** (Q1-Q4, OT) - removed Q1-only restriction
   - **Always set when `gameId` exists** - ensures param is never ambiguous

3. **Quarter/Period Logic:**
   - Always sets `quarter` and `period` (Q1-Q4 or OT1+)
   - Automatically calculates period label

4. **Parameter Preservation:**
   - Preserves all team info, mode, tournament/franchise IDs
   - Preserves lineup, clock, special params
   - Preserves debug flags

**URL Parameters Used:**
- `resume_from_timeout=true`: Timeout resume flag (frontend single source of truth for UI decisions)
- `resume_from_timeout=false`: Quarter break flag (explicitly set to avoid ambiguity)
- `game_id`: Game identifier
- `quarter`: Quarter number
- `period`: Period label (Q1-Q4 or OT1+)
- `mode`: Game mode (single/tournament/franchise)
- `tournament_id`: Tournament identifier (if applicable)
- `franchise_id`: Franchise identifier (if applicable)
- `week`: Week number (franchise mode)
- Lineup parameters: `home_pg`, `home_sg`, etc.
- `clock`: Clock time (preserved for foul out/timeout); **required for lineup header** when `resume_from_timeout=true` (lineup page reads clock from URL for the header).
- `home_score`, `away_score`: Optional; when present the lineup page uses them for the header so it shows what the user saw at timeout (same source as clock).

**Frontend Detection Logic (SS&S - January 2025):**

**Location:** `FrontEnd/static/js/phaser/bootGame.js` `initGame()`

**Pattern:**
```javascript
// URL param is single source of truth - no database fallback
const urlResumeFromTimeoutParam = urlParams.get('resume_from_timeout');
const resumeFromTimeout = urlResumeFromTimeoutParam === 'true';

// Safe default: If param is missing, treat as false (quarter break, not timeout resume)
// This is safe because:
// 1. If it's a new Q1 game, param is intentionally omitted → false is correct
// 2. If gameId exists but param is missing (stale URL), false is safer than true
// 3. If it's truly a timeout resume, the helper should have set it to 'true'
```

**Lineup page header:** When `resume_from_timeout=true`, the lineup page displays **clock** (and when present **scores**) from the URL for the header. Timeout navigation must therefore include `clock` (and optionally `home_score`/`away_score`) in the lineup URL so the header matches the state at the moment the user entered the timeout.

**Key Principles:**
- **No Database Fallback:** Frontend does NOT check database for timeout state - relies exclusively on URL param
- **Safe Default:** Missing param = `false` (quarter break), never `true` (timeout resume)
- **Explicit Setting:** Helper always sets param to `'true'` or `'false'` when `gameId` exists (never ambiguous)
- **UI Decision Only:** URL param determines whether to show/hide pre-game buttons (backend still uses database for state restoration)
- **Parameter Preservation:** `resume_from_timeout` parameter is preserved through entire navigation chain (timeout → lineup → court)
- **Quarter Independence:** Timeouts work in all quarters (Q1-Q4, OT) - parameter is preserved regardless of quarter

**Why No Database Fallback:**
- **Stale State Risk:** Database may contain `timeout_next_play_type` from previous timeout that hasn't been cleared yet
- **Quarter Ambiguity:** Stale timeout state in database doesn't indicate which quarter it applies to
- **Race Conditions:** After timeout resume, `timeout_next_play_type` may persist until turn completes, causing false positives
- **Complexity:** Database fallback adds unnecessary complexity and creates multiple sources of truth
- **Reliability:** URL param is set correctly by helper in all navigation paths - no need for fallback

**Critical Frontend Pattern:**
- All navigation functions read URL params directly from `window.location.search` when called
- Does NOT rely on module-level variables that might be stale (especially after async delays)
- Helper ensures `game_id` and `resume_from_timeout` are always current when navigating
- **All navigation functions MUST use `TimeoutNavigationHelper`** - manual parameter preservation is fragile and can lose critical state (e.g., `clock` parameter)

**Critical Fixes (January 2025):**

1. **Unified Timeout Handler:**
   - **Problem:** User and computer timeouts had duplicate code paths for saving game state and building responses, leading to inconsistencies and bugs.
   - **Root Cause:** Two separate endpoints (`/api/call-timeout` for user, `/api/simulate-turn` for computer) each had their own save/response logic, even though they used the same `gm.call_timeout()` method.
   - **Solution:** Created unified `handle_timeout_save_and_response()` helper function that both endpoints call:
     - Saves game state to database using `summarize_game_state()`
     - Returns consistent response format with `clock`, `time_remaining`, `quarter`, `scores`, etc. from saved DB data
     - Ensures response always matches what was saved to DB
   - **Impact:** User and computer timeouts now work identically - same save logic, same response format, same behavior
   - **Location:** `BackEnd/api/api.py` `handle_timeout_save_and_response()` (~L1131)
   - **Applied To:** 
     - `/api/call-timeout` endpoint (user timeout)
     - `/api/simulate-turn` endpoint (computer timeout)
   - **Frontend Changes:** 
     - Updated `gameScene.js` to store full response data in `turn._responseData` for computer timeouts
     - Updated `AnimationEngine.handleTimeout()` to extract `clock` and `time_remaining` from `turnData._responseData`
     - **✅ FIX (January 2025):** `AnimationEngine.handleTimeout()` branches on `timeout_reason`: **USER** → skip navigation (handled by `showUserTimeoutPopup` button click). **FOUL_OUT** → show foul-out popup via `showFoulOutPopup()` (popup handles navigation to lineup; no "team calls timeout" message). **COMPUTER** → automatic navigation via `showTimeoutPopup()`.

2. **Computer Timeout State Restoration Bug Fix:**
   - **Problem:** When computer called timeout, game state was saved to DB correctly, but when user returned, if game was still in `ongoing_games` (in-memory cache), the system would use stale in-memory state instead of loading the saved DB state. This caused incorrect scores, clock, and other game state to be restored.
   - **Root Cause:** `apply_timeout_resume_state_to_gm()` only restored timeout-specific fields (`timeout_next_play_type`, `clock`, `time_remaining`), but didn't restore scores, fouls, and timeouts from the saved document. When game was in memory, stale values persisted.
   - **Solution:** Updated `apply_timeout_resume_state_to_gm()` to restore ALL critical game state from saved document:
     - Scores (overwrites stale in-memory scores)
     - Team fouls (overwrites stale in-memory fouls)
     - Team timeouts (overwrites stale in-memory timeouts)
     - Clock and time_remaining (already restored, but now with logging)
   - **Impact:** Computer timeouts now correctly restore all game state, matching user timeout behavior
   - **Location:** `BackEnd/api/api.py` `apply_timeout_resume_state_to_gm()` (~L1357)
   - **Applied To:** Both in-memory games and newly-loaded games (in `simulate_quarter_endpoint`)

3. **Q2-Q4 Timeout Resume Parameter Preservation:**
   - **Location:** `FrontEnd/static/set-lineup.js` (lines 1078-1088)
   - **Problem:** Previous logic forced `resumeFromTimeout = false` for ALL quarters > 1, treating timeouts in Q2-Q4 as quarter breaks
   - **Solution:** Only force `resumeFromTimeout = false` if URL param is already false/missing (true quarter break). Preserve `resumeFromTimeout = true` when URL param indicates timeout resume (any quarter)
   - **Impact:** Pre-game popup now only appears after quarter breaks, not after timeouts in Q2-Q4
   - **Pattern:**
     ```javascript
     // Only force to false if URL param is already false/missing (true quarter break)
     if (quarter > 1 && !resumeFromTimeout) {
       resumeFromTimeout = false;
     } else if (quarter > 1 && resumeFromTimeout) {
       // Preserve timeout resume even in Q2-Q4
       // resumeFromTimeout stays true
     }
     ```

4. **Prevent Game Reset During Timeout Resume:**
   - **Location:** `FrontEnd/static/set-lineup.js` (lines 126-174)
   - **Problem:** `init-game` was being called when resuming from timeout, creating a new game and resetting all state (scores, clock, quarter)
   - **Solution:** Skip `init-game` call if `game_id` exists in URL OR if `resume_from_timeout=true`
   - **Impact:** Game state is preserved when resuming from timeout (no reset to 0-0, 8:00, Q1)
   - **Pattern:**
     ```javascript
     // Only init if: no game_id exists AND not resuming from timeout
     const resumeFromTimeout = urlParams.get('resume_from_timeout') === 'true';
     const shouldInitGame = !gameId && homeTeam && awayTeam && !resumeFromTimeout;
     
     if (shouldInitGame) {
       // Call /api/init-game
     }
     ```
   - **Why This Works:** If `game_id` exists, a game already exists. If `resume_from_timeout=true`, we're resuming an existing game. In both cases, we should NOT create a new game.

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

1. **`restore_timeout_resume_state()`** (`BackEnd/api/api.py` ~L1031)
   - Loads timeout state from the correct document location based on game mode _(Single / Tournament sunset)_
   - **Single Game (sunset)**: `games_collection` document
   - **Tournament Game (sunset)**: Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
   - **Franchise Game**: Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)
   - Validates that `timeout_next_play_type` exists in saved document
   - Returns saved document with timeout state, or `None` if not found

2. **`apply_timeout_resume_state_to_gm()`** (`BackEnd/api/api.py` ~L1357)
   - Applies restored state to GameManager instance
   - **✅ CRITICAL FIX (January 2025):** Restores ALL critical game state from saved document, not just timeout-specific fields
   - This ensures that if the game is still in `ongoing_games` with stale state, we overwrite it with the correct saved state
   - This fixes the bug where computer timeouts would resume with incorrect scores/clock when game was still in memory
   - Restores:
     - `timeout_next_play_type` to `gm.game_state`
     - `timeout_offense_team_id` to `gm.game_state`
     - `clock` and `time_remaining` (critical for timeout resume)
     - **Scores** from saved document (overwrites stale in-memory scores)
     - **Team fouls** from saved document (overwrites stale in-memory fouls)
     - **Team timeouts** from saved document (overwrites stale in-memory timeouts)
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
- **✅ CRITICAL FIX (January 2025):** Overwrites stale in-memory state with saved DB state
  - Fixes bug where computer timeouts would resume with incorrect scores/clock when game was still in `ongoing_games`
  - Ensures saved state (from timeout save) always takes precedence over in-memory state
  - Applies to both user and computer timeouts for consistency

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
   - **✅ CRITICAL FIX (January 2025):** Lineup screen skips `init-game` call when `game_id` exists or `resume_from_timeout=true`
   - This prevents creating a new game (which would reset scores, clock, quarter) when resuming from timeout

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
   - **✅ CRITICAL FIX (January 2025):** Also restores scores, fouls, and timeouts from saved document
   - This ensures saved state overwrites any stale in-memory state (fixes computer timeout bug)

6. **Backend applies state to GameManager** (whether in memory or newly loaded)
   - Uses `apply_timeout_resume_state_to_gm()` helper
   - **✅ CRITICAL FIX (January 2025):** Restores ALL critical game state, not just timeout-specific fields
   - This ensures that if game is still in `ongoing_games` with stale state, we overwrite it with correct saved state
   - Works for both in-memory and newly-loaded games
   - Applied early in the flow if game is in memory, or after DB load if not (both in `simulate_quarter_endpoint`)

7. **Backend creates SIP turn** with correct possession team
   - Uses `timeout_offense_team_id` to ensure correct team has possession
   - SIP transitions to HCO (defense calls play)

8. **Backend clears timeout state from database** (defensive cleanup)
   - Uses `$unset` to remove `timeout_next_play_type` and `timeout_offense_team_id`
   - Prevents stale timeout state from affecting future games

9. **Frontend auto-starts game** (bypasses pre-game buttons)
   - **Location:** `FrontEnd/static/js/phaser/bootGame.js` `initGame()`
   - Pre-game container is explicitly hidden when `resumeFromTimeout === true`
   - Pre-game container is explicitly shown when `resumeFromTimeout === false` or missing
   - Auto-starts game by calling `handleButtonClick(true)` when resuming from timeout
   - Game continues seamlessly

10. **Game continues** with SIP → HCO transition

### Timeout Button Functionality

**Feature Flag:**
- Location: `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`
- `ENABLE_TIMEOUT_BUTTON = true` (feature flag for modularity)

**Button State:**
- **Always Live:** Button is always enabled and clickable (no restrictions during gameplay)
- **Disabled When:** User team has 0 timeouts remaining (button is greyed out and not clickable)
- **Highlighted:** When user presses button, green highlight effect appears (indicates timeout is queued)
- **Toggleable:** User can press button again to cancel timeout queue (removes highlight)

**✅ SIMPLIFIED APPROACH (January 2025):**
- **Single Execution Point:** Timeouts only execute at the start of eligible turns, never mid-turn
- **Linear Flow:** Button click → Queue timeout → Wait for next eligible turn → Execute at turn start
- **No Mid-Turn Execution:** Removed complex logic for immediate execution during active turns
- **Benefits:**
  - Simpler code (one execution path instead of two)
  - No mid-turn state management
  - Clearer logic (eligibility check → queued check → execute or continue)
  - Easier to debug (timeouts only happen at turn boundaries)

**Timeout Eligibility System:**
- **Single Source of Truth:** Eligibility is determined once at the start of each turn and stored in `scene.currentTurnTimeoutEligible`
- **Location:** Set in `FrontEnd/static/js/phaser/animation/AnimationRouter.js` `processTurn()` at the start of each turn
- **Eliminates Stale Data:** By determining eligibility once with fresh `turnData` from AnimationRouter, we avoid issues with stale data when the button is pressed mid-turn
- **Used By:**
  - Queued timeout checker (`checkAndExecuteQueuedTimeout`) - reads flag to determine if queued timeout should execute at start of turn

**Eligibility Criteria (`checkTimeoutEligibility()` function):**
- **Two-step check (in order):**
  1. **BIP/SIP Check:** If turn is `BASELINE_INBOUND` or `SIDE_INBOUND` AND user's team is on offense, timeout is eligible (checked first)
  2. **DREB => HCO Transition Check:** If current turn is `HCO` AND previous turn was `MISS` with `rebound_type: "DREB"` AND `next_play_type: "HCO"` AND user's team is on offense, timeout is eligible
- **Exclusion:** MISS turns with `rebound_type: "DREB"` are explicitly excluded (timeout waits for the next HCO turn after DREB animation completes)
- **Field Resolution:**
  - Uses `offense_team_id` as primary field (SS&S canonical field, set for all turns)
  - Falls back to `possession_team_id` for backward compatibility (deprecated, only set for some turn types)
  - **Note:** `possession_team_id` is not set for `BASELINE_INBOUND` turns, so `offense_team_id` is required
- **Eligible Turns:**
  - Any `BASELINE_INBOUND` (BIP) turn with user's team on offense
  - Any `SIDE_INBOUND` (SIP) turn with user's team on offense
  - `DREB => HCO` transition when user's team is on offense (defensive rebound leading to half-court offense)
- **Not Eligible:**
  - MISS turns with `rebound_type: "DREB"` (timeout waits for next HCO turn)
  - `DREB => Fast Break` transitions (even if user team is on offense)
  - Any other turn types
  - HCO turns that didn't come from DREB (e.g., normal HCO after a made shot)

**Execution Flow:**
- **Button Click:** User presses button → Plays sound effect → Toggles `timeoutQueued` flag → Updates button highlight → Returns (never executes immediately)
- **Turn Start Check:** At start of each turn, `checkAndExecuteQueuedTimeout()` is called:
  - If `timeoutQueued = true` AND `scene.currentTurnTimeoutEligible = true`:
    - Pause all animations (before they start)
    - Stop animation loop (`scene.timeoutCalled = true`)
    - Execute timeout (call API, show popup, play airhorn sound)
    - Return `true` (stop processing this turn)
  - If not eligible, turn processes normally and timeout waits for next eligible turn
- **Key Point:** Timeouts only execute at turn boundaries (start of eligible turns), never mid-turn, even if the current turn is eligible

**Turn Execution (Simplified):**
- When timeout executes at start of eligible turn, animations are stopped before they start:
  - All tweens are paused (`scene.tweens.pauseAll()`) - prevents any animations from playing
  - Animation loop is stopped (`scene.timeoutCalled = true`) - prevents turn processing from continuing
  - Timeout API is called → Popup appears → User clicks "Go To Timeout" → Navigation to lineup screen
  - User experience: Turn stops before animations play → Popup appears → User navigates to lineup
- **Key Point:** Timeouts only execute at turn boundaries (start of eligible turns), never mid-turn. This ensures clean execution and prevents animation conflicts.

**User Timeout Navigation Flow:**
- **Step 1:** User presses timeout button → `handleTimeoutButtonClick()` is called
- **Step 2:** API is called (`/api/call-timeout`) → Timeout turn is created and saved to database
- **Step 3:** `showUserTimeoutPopup()` displays popup with "Go To Timeout" button
- **Step 4:** User clicks "Go To Timeout" button → Sets `scene.userTimeoutButtonClicked = true` → Calls `showTimeoutPopup()` with `computerTimeout=false`
- **Step 5:** `showTimeoutPopup()` checks guards:
  - Safeguard 1: Checks if popup still exists (should be removed by button click)
  - Safeguard 2: Checks if `scene.userTimeoutButtonClicked === true` (set by button click)
  - If both pass, navigation proceeds to lineup screen
- **Step 6:** `AnimationEngine.handleTimeout()` is called for the timeout turn → Branches on `timeout_reason`: USER → skip (popup already handled); FOUL_OUT → show foul-out popup; COMPUTER → navigate via `showTimeoutPopup()`
- **Key Point:** USER timeout navigation is handled by the popup button click. FOUL_OUT uses the foul-out popup (not the generic "team calls timeout" flow). Only COMPUTER timeouts trigger automatic navigation via `showTimeoutPopup()`.

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
- The chosen clock is placed in the lineup URL; the **lineup page** then reads the `clock` URL param for its header when `resume_from_timeout=true`.
- **User timeout:** Clock is taken from a prioritized chain so the lineup shows **what the user saw**: (1) **DOM** (`#game-clock`), (2) **scene.simData.clock**, (3) API response, (4) last processed turn, (5) URL params, (6) default `8:00`. Preferring DOM/simData over API avoids showing a clock one turn behind when the next simulate_turn is in flight.
- **Computer timeout:** API response is used first (same request that triggered navigation), then the same fallbacks as above.
- Scores are also passed in the URL (`home_score`, `away_score`) when available (DOM or timeout response) so the lineup header can show the same state the user saw.

**Applies to:** Timeout resume, quarter-break return, and foul-out return (any time the user returns to court with an existing `game_id`). The same scoreboard source (simData / first turn) is used so scores, clock, TOL, and fouls show correctly as soon as the overlay hides.

### Player and Team Box Score Force-Update on Resume (February 2026)

**Problem:** When returning to court from a timeout, quarter break, or player foul-out, the scoreboard showed correct data (scores, clock, TOL, fouls) but the **Player Box Score** and **Team Box Score** (S1, S2, S3 tabs) showed stale data (e.g. start-of-quarter stats, all zeroes, 100% energy) until the first turn completed.

**Cause:** The game scene initializes box scores from `simData.start_box_score` (start of quarter) and empty team totals. The scoreboard is driven from current simData/turn state, but the box score tables are only updated incrementally by `applyPlayerStats(turn)` and `applyTeamStats(turn)` on each turn. So on resume, box scores were one sync step behind. Additionally, the API returns `box_score` keyed by **team_id** (not team name); the initial implementation looked up by team name and thus never read any player data.

**Solution:** When the scene has a `game_id` (resumed game), after the initial table setup and first `updateScoreboard()` call, the frontend fetches current game state from `GET /api/game/{game_id}` and **only** forces an update of:

1. **Player Box Score** – `this.playerStats` and the stats table DOM cells are overwritten from `gameData.box_score`; **energy (NG)** is applied from `gameData.players` so row colors show correct energy on resume. `window.currentPlayerStats` is set so the stats toggle stays in sync. No other court UI is changed.
2. **Team Box Score** – `window.setTeamBoxData()` is called with `gameData.team_totals`, `gameData.team_stats`, and team attributes so S1, S2, and S3 tabs show current data.

No force-updates are applied to the scoreboard, lineup, buttons, sprites, or any other court state at this point; the scoreboard is already correct from the existing flow.

**Implementation details (Player Box Score):**
- **box_score keys:** The API (and backend `get_box_score()`) return `box_score` keyed by **team_id** (`gameData.home_team_id`, `gameData.away_team_id`), not by team name. The frontend uses `boxScore[gameData.home_team_id]` / `boxScore[gameData.away_team_id]` when present, with fallback to team name for backward compatibility.
- **Player matching:** For each stat block in the box score, the scene resolves `playerId` from `statBlock.playerId` or `statBlock.player_id` when present, otherwise `this.nameToId[statBlock.name]`, then updates `this.playerStats[playerId]` and the corresponding DOM cells.
- **Energy on resume:** After applying stats, the scene iterates `gameData.players` (which includes `NG` and `attributes.NG` from the saved document), sets `ps.NG` on each `this.playerStats[playerId]`, and applies the same energy color logic used during gameplay (`getEnergyColor(ng)`) to the player’s row cells and name cell so energy displays correctly before the first turn.

**Location:** `FrontEnd/static/js/phaser/gameScene.js` – inside `create()`, immediately after the initial Team Box Score init block, when `this.gameId && homeTeam && awayTeam`. Uses `fetchGameState()` from `./utils/loadGameStats.js`.

**Applies to:** Timeout resume, quarter-break return, and foul-out return (same as scoreboard immediacy). Ensures all three—scoreboard, player box, and team box—reflect the same current game state (including player energy) as soon as the user sees the court.

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

**Game Plan & Playbook Settings Persistence:**
- Settings persistence uses unified functions for consistent behavior across all modes
- **Franchise/Tournament (single source of truth, February 2026):** Settings are always read from and written to the master store (FTD for franchise, tournament doc for tournament)—both before the game and during gameplay (lineup, timeout). The game document is not used for these settings. Timeout resume loads from the same master store, so settings persist automatically.
- **Single Game:** Settings are stored in and loaded from the game document when a game is in progress.
- **Team ID Resolution:** Master docs use ObjectId keys; single-game game docs use canonical keys
- **See:** `../03_Data_Persistence/Data_Persistence_System.md` - "Game Plan & Playbook Settings Persistence" section for complete documentation

**Lineup Screen Population (Foul Out):**
- Location: `FrontEnd/static/js/phaser/utils/foulOutPopup.js` `showFoulOutPopup()` function
- Fetches current lineup from URL parameters (same as timeout flow)
- Removes **only** the fouled-out player from the user's team lineup
- Leaves the fouled-out player's position empty (not replaced)
- Passes populated lineup (minus foul out player) to `TimeoutNavigationHelper`
- **Key Point:** Only removes the fouled-out player if they're on the user's team; other team's lineup is preserved

### Computer Team Lineup and Strategy Management (January 2025, Updated February 2025)

The computer team automatically adjusts its lineup and strategy settings during timeouts, at quarter breaks, and during foul out instances based on player energy levels, foul counts, and game situation.

**When Lineups Are Rebuilt:**

1. **During Timeouts:**
   - When the user calls a timeout, the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/models/game_manager.py` `call_timeout()` (~L239)
   - Only the computer team's lineup is adjusted (user team lineup remains unchanged)
   - Uses current game state to apply energy and foul filtering rules
   - **Strategy Settings:** Computer team's strategy settings are automatically regenerated using weighted randomization (same logic as initial strategy settings)

2. **At Quarter Breaks:**
   - At the start of each new quarter (Q2, Q3, Q4, OT), the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/main.py` `simulate_quarter()` (~L336)
   - Ensures the computer team starts each quarter with an optimal lineup based on current player conditions
   - **Strategy Settings:** Computer team's strategy settings are automatically regenerated using weighted randomization (same logic as initial strategy settings)

3. **During Foul Out Instances:**
   - When a player fouls out, the computer team's lineup is automatically rebuilt (if computer team player fouled out)
   - Location: `BackEnd/models/game_manager.py` `call_timeout()` with `timeout_reason="FOUL_OUT"` (~L239)
   - **Strategy Settings:** Computer team's strategy settings are automatically regenerated using weighted randomization (same logic as initial strategy settings)

**Player Eligibility Filtering:**

The system uses `is_player_eligible_for_lineup()` (`BackEnd/utils/db_utils.py`) to filter players based on:

1. **Energy (NG) Filtering:**
   - **Default:** Exclude players with NG < 80% (0.8)
   - **Q4 < 4min (`time_remaining < 240`) or OT:** Exclude players with NG < 64% (0.64)

2. **Foul-Based Filtering (by Quarter):**
   - **Q1:** Exclude if player fouls > 1
   - **Q2:** Exclude if player fouls > 2
   - **Q3:** Exclude if player fouls > 3
   - **Q4:** Exclude if player fouls > 3 AND > 4 minutes remaining (no exclusion if ≤ 4 minutes remaining)
   - **Overtime:** No foul exclusion for active players

3. **Fouled Out Players:**
   - Players with 5 or more fouls are always excluded (not considered active)

**Implementation Details:**
- **Lineup Function:** `build_lineup_from_mongo(team, game_state=None)` (`BackEnd/utils/db_utils.py`)
- **Strategy Function:** `autoset_strategy_settings(team)` (`BackEnd/utils/db_utils.py`)
  - Regenerates strategy settings using `TeamManager._init_strategy_settings()` method
  - Uses same weighted randomization logic as initial strategy settings
  - Only applies to computer teams (user team strategy settings are never auto-adjusted)
- **Lineup Completion:** `_ensure_complete_lineup(...)` (`BackEnd/main.py`) with gap-filling via `fill_unified_lineup_gaps(...)` (`BackEnd/utils/db_utils.py`)
- Only affects computer team (user team lineups and strategy settings are never auto-adjusted)
- Works consistently across all game modes (franchise is live; **single / tournament are SUNSET** — see `Sunset_Modes.md`)

**Tactical reset on timeout / foul-out** (`GameManager.call_timeout()`):
- **Clears** the user's tactical overrides for **both** teams: `aggression_override`, `tempo_override`, `press_trap_override` (offense/defense play overrides are intentionally left untouched). Mirrors the quarter-transition reset.
- **Re-rolls** both teams' per-break aggression via `GameManager.roll_aggression_calls()` → `strategy_calls["aggression_roll"]`. Aggression is rolled per break (game start / quarter break / timeout / foul-out), not per turn; `set_strategy_calls()` resolves the effective `aggression_call` each turn as (user override if set, else `aggression_roll`). See `Turn_by_Turn_System.md` and `Playcall_Center.md`.
- Applies to **both** user and computer teams (unlike `autoset_strategy_settings`, which is computer-only — the roll itself just draws from each team's existing `aggression` slider).

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
   - Includes real `foul_out_player` identity in timeout turn payload (`player_id`, `name`, `team`, optional `photo`). The backend must resolve this from the original foul result / `foul_player_id` before creating the timeout turn; `Unknown` placeholder payloads are an error fallback, not valid expected behavior.

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` `setup_timeout_turn()`: Creates timeout turn payload
- `BackEnd/models/game_manager.py` `determine_next_turn()`: Routes TIMEOUT → next turn
- `BackEnd/models/game_manager.py` `call_timeout()`: Unified timeout creation method (used by both user and computer timeouts)
- `BackEnd/api/api.py` `handle_timeout_save_and_response()`: **Unified helper function** for saving game state and building response (used by both user and computer timeouts)
- `BackEnd/api/api.py` `call_timeout_endpoint()`: Handles user-initiated timeouts (calls unified helper)
- `BackEnd/api/api.py` `simulate_turn_endpoint()`: Handles computer timeouts (calls unified helper)
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
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleTimeout()`: Branches on `timeout_reason` (USER skip / FOUL_OUT show foul-out popup / COMPUTER navigate); extracts clock/time_remaining from response data
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`: Stops animation loop on timeout
- `FrontEnd/static/js/phaser/gameScene.js`: Scoreboard immediate update logic, stores response data in `turn._responseData` for computer timeouts
- `FrontEnd/static/js/phaser/bootGame.js`: Auto-start logic for timeout resume, pre-game container visibility control
- `FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`: Pre-populates lineup from URL, preserves `resume_from_timeout` parameter for timeouts in all quarters
- `FrontEnd/static/set-lineup.js` `loadRoster()`: Skips `init-game` call when `game_id` exists or `resume_from_timeout=true` to prevent game state reset
- `FrontEnd/static/game-plan.js` `loadSettings()`: Pre-populates game plan from URL
- `FrontEnd/static/court.html`: Timeout button and progress bar HTML/CSS

**Tests:**
- `tests/test_timeout_resume_missing_next_play_type.py`, `tests/test_timeout_resume_gate_behavior.py`, `tests/test_foul_out_timeout_persistence.py`, `tests/test_user_team_sim_timeouts.py` (the old `test_timeout_functionality.py` no longer exists)
