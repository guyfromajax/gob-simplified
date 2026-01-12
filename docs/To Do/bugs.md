

1. Playcall Override During Opening Tip Sequence -- When a user selects a playcall override during the opening tip sequence (before the game is initialized), the play is highlighted in the playcall center UI but the override never reaches the backend. The frontend `setPlaycallOverride()` function blocks the API call because `game_id` is `null` at that point (the game hasn't been created yet via `/api/simulate-quarter`). The override only works after the first turn is simulated and `game_id` becomes available. **Solution:** Either queue the override and send it after game initialization, or defer the `game_id` check until the first turn is simulated.
2. Defensive Foul on missed shot attempt not announcing via our Announcement System
3. Scouting Report button does not appear in the TCC
4. Next column on Standings tab not populating on the Standings tab on FCC
5. Since going to production, Playcall Center overrides are not working
6. Since going to production, the computer is calling timeouts for the user team
7. Elminate "Simulating Q5..."
8. Tournament Mode -- Non user game team and player stats are not populating on the Stats tab, and no team's player stats are populating on the team roster pages.
9. Pre-game buttons missing after "Play Quarter" - After playing a quarter with "Play Quarter" button, the next quarter break does not show the pre-game buttons ("Play Quarter", "Sim Quarter", "Sim Rest of Game"). The game auto-starts instead. This only happens after using "Play Quarter" - if you use "Sim Quarter", the pre-game buttons appear correctly at the next quarter break. **Root Cause**: The `resume_from_timeout` URL parameter is being set to `true` when it should be `false` for quarter breaks. Multiple attempts to fix this have been made (ensuring `gameScene.js` sets it to `false`, updating `set-lineup.js` to force `false` for quarter breaks, updating `bootGame.js` DB fallback logic), but the parameter still shows as `true` when `court.html` loads. **Investigation Needed**: Need to trace the full navigation chain to identify where `resume_from_timeout` is being set to `true` - check URL when `set-lineup.html` loads, check debug logs from `set-lineup.js` when building params, check if any code is reading from localStorage or database and overriding the URL param.

## Fixed Bugs (January 2025)

✅ **Tournament Command Center Stats Bugs** (Fixed: January 2025)
- **Totals showing "undefined"**: Fixed missing W/L initialization in totals object
- **Player stats not populating on Roster tab**: ✅ **FIXED** - Refactored Tournament mode to match Franchise pattern exactly
  - `loadRoster()` now merges stats from tournament document into roster data (matches Franchise pattern)
  - `renderRoster()` now calls `renderRosterStats()` internally (matches Franchise `renderTeam()` pattern)
  - Removed old `renderStats()` function that used separate stats array
  - Updated HTML to use `roster-stats-body` instead of `stats-body` (matches Franchise)
- **Team stats container scroll issue**: Fixed by removing `scroll-x` wrapper and using inline overflow styling
- **Teams from user's game not populating on Stats tab**: ✅ **FIXED** - Now using shared `TeamStatsTable` module (same as Franchise)
- **Note**: Computer teams showing 2 games is a backend issue (likely double finalization) - needs backend investigation

✅ **Team Stats SS&S Refactoring** (Completed: January 2025)
- **Frontend**: Extracted shared `teamStatsTable.js` module (~160 lines of duplicate code removed)
  - Both Tournament and Franchise modes now use `TeamStatsTable.renderTeamStatsTable()` and `TeamStatsTable.sortTeamStats()`
  - Removed unnecessary roster refresh logic from Tournament `refreshTeamStats()`
- **Backend**: Extracted shared `team_stats_aggregator.py` utility (~130 lines of duplicate code removed)
  - Both Tournament and Franchise endpoints now use `aggregate_team_stats_from_players()`
  - Single source of truth for team stats aggregation logic
- **Total Reduction**: ~290 lines of duplicate code eliminated
- **Benefits**: One fix applies to both modes, prevents future bugs, ensures consistent behavior

✅ **Tournament Mode Roster/Stats Refactoring** (Completed: January 2025)
- **Refactored to match Franchise pattern exactly**: Tournament mode now uses identical code structure as Franchise mode
  - `loadRoster()`: Loads roster, loads tournament doc, merges stats into roster data (matches Franchise exactly)
  - `renderRoster()`: Calls `renderRosterStats()` internally (matches Franchise `renderTeam()` pattern)
  - Removed old `renderStats()` and `renderStatsTable()` functions that used separate stats array
  - Updated HTML: Changed `stats-body` to `roster-stats-body` to match Franchise
  - **Result**: Tournament and Franchise modes now use the exact same execution pattern with only variable names different (`tournament_id` vs `franchise_id`, `tournament.players` vs `franchise.players`)

✅ **Tournament Player Stats Not Saving - SS&S Refactoring** (Fixed: January 2025)
  - **Issue**: Player stats remained at zero after Tournament games, even though games were played
  - **Root Cause**: Tournament mode used per-player update pattern with complex nested path queries, while Franchise mode used single atomic update
  - **Fix**: Refactored Tournament mode's `finalize_game()` to match Franchise mode's pattern exactly:
    - Single atomic MongoDB update for all players (instead of per-player updates)
    - Document-level `applied_games` check (removed complex nested path queries)
    - Uses `$setOnInsert` for automatic player initialization
    - Processes all players from `box_score` in one operation
  - **Result**: Tournament and Franchise modes now use identical execution patterns, ensuring consistent behavior and eliminating zero stats issues
  - **Documentation**: See `docs/To Do/Tournament_vs_Franchise_Player_Stats_Comparison.md` for detailed comparison

## Current Investigation (January 2025)

### ✅ Fixed: Duplicate Teams Bug
- **Root Cause**: When `team_id_str` was not a valid ObjectId (e.g., "BENTLEY_TRUMAN"), the code still added it to output, creating duplicates
- **Fix**: Updated `BackEnd/utils/team_stats_aggregator.py` to resolve non-ObjectId team IDs to ObjectIds before adding to output, or skip them if they can't be resolved
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Mode Field Missing)
- **Root Cause**: Frontend was not passing `tournament_id` and `mode` in `/api/simulate-quarter` request payload, causing backend to default to `mode: "single"` instead of `mode: "tournament"`. When `finalize_game()` was called with `mode="tournament"`, the game document had `mode: "single"`, causing a mismatch and potentially skipping Tournament processing.
- **Fix**: 
  - Added `tournament_id` and `mode` to payload in `gameScene.js` (main gameplay flow)
  - Added `tournament_id` and `mode` to payload in `bootGame.js` (sim-to-4th and sim-full-game flows)
  - This ensures backend correctly sets `mode: "tournament"` on game document, allowing `finalize_game()` to process Tournament stats correctly
- **Result**: Game documents now have correct `mode: "tournament"` field, ensuring `finalize_game()` processes player stats correctly for Tournament mode
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Mode Field Missing)
- **Root Cause**: Frontend was not passing `tournament_id` and `mode` in `/api/simulate-quarter` request payload, causing backend to default to `mode: "single"` instead of `mode: "tournament"`. When `finalize_game()` was called with `mode="tournament"`, the game document had `mode: "single"`, causing a mismatch and potentially skipping Tournament processing.
- **Fix**: 
  - Added `tournament_id` and `mode` to payload in `gameScene.js` (main gameplay flow)
  - Added `tournament_id` and `mode` to payload in `bootGame.js` (sim-to-4th and sim-full-game flows)
  - This ensures backend correctly sets `mode: "tournament"` on game document, allowing `finalize_game()` to process Tournament stats correctly
- **Result**: Game documents now have correct `mode: "tournament"` field, ensuring `finalize_game()` processes player stats correctly for Tournament mode
- **Status**: ✅ Fixed and committed

### ✅ Fixed: Player Stats Not Saving for User Games (Race Condition + Missing game_document)
- **Root Cause**: Two issues prevented player stats from saving:
  1. **Race Condition**: Tournament mode was looking up game document from database in `/tournament/save-result`, which could be stale or incomplete (save-result called before Q4 save completes). Franchise mode avoided this by accepting `game_document` directly from the request.
  2. **Missing game_document in Sim Full Game**: When using "Sim Full Game" in `bootGame.js`, the fetched game document wasn't being passed as `game_document` to `finalizeGame()`, so `finalizeGame()` couldn't detect it and pass it to the backend.
- **Fix**: 
  - **Frontend (`finalizeGame.js`)**: Added logic to detect if `simData` itself is a complete game document (has `box_score` and `game_id`) and use it directly as `game_document` when calling `/tournament/save-result`. This handles the "Sim Full Game" flow from `bootGame.js`.
  - **Backend (`tournament_routes.py`)**: 
    - Added `game_document` field to `TournamentResultRequest` (matches Franchise `CompleteWeekRequest`)
    - Updated `/tournament/save-result` to use `request.game_document` if provided (matches Franchise pattern)
    - Added logic to save `game_document` to database before calling `finalize_game()` to ensure complete data is available
  - **Frontend (`finalizeGame.js`)**: Updated to pass `final_game_document` from `simulate-quarter` response to `/tournament/save-result` (matches Franchise pattern)
- **Result**: Tournament mode now uses the exact same pattern as Franchise mode - receives fresh, complete game document directly from frontend, saves it to database, and `finalize_game()` processes complete `box_score` data. Player stats now save correctly for both regular gameplay and "Sim Full Game" flows.
- **Status**: ✅ Fixed and committed (January 2025)

### 🔍 Investigating: Formatting Bug (Team Stats Table)
- **Current State**: 
  - HTML has `overflow-x: auto` on wrapper div (line 143 in tournament.html)
  - CSS has `min-width: 800px` on `.stats-table` (line 425 in tournament.css)
  - Structure matches Franchise mode
- **Possible Causes**:
  1. CSS not being applied correctly
  2. Container width constraint
  3. Browser caching
- **Next Steps**: Verify CSS is loading and container width is correct

### 🔍 Investigating: Continuous 404 Requests for Player Tooltip Images (court.html)
- **Issue**: Continuous stream of 404 requests for player headshot images (`/images/players/${playerId}.png` and `/images/players/default.png`) even when game is paused
- **Location**: `FrontEnd/static/js/phaser/gameScene.js` lines 519-523 (player tooltip image loading)
- **Root Cause**:
  1. Tooltip tries to load player image: `/images/players/${playerId}.png` (UUID-based filenames)
  2. When that fails (404), `onerror` handler tries fallback: `/images/players/default.png`
  3. Fallback also doesn't exist (404), creating a retry loop
  4. `mousemove` event listener (lines 673-683) is active even when paused, continuously triggering tooltip updates and image load attempts
- **Impact**:
  - Unnecessary network requests (continuous 404s)
  - Console noise
  - Potential performance impact from repeated failed requests
  - May contribute to slow initial game download
- **Expected Behavior**:
  - Image should load once when tooltip is first shown
  - Should fail gracefully if missing (hide image or show placeholder)
  - Should not retry continuously after failure
  - Tooltips should be disabled when game is paused
- **Fix Required**:
  1. Add flag to prevent retries after first failure
  2. Hide image element on error instead of trying non-existent fallback
  3. Optionally disable tooltips when game is paused
  4. Ensure tooltip image only loads once per tooltip show, not on every mousemove

### 🔍 Investigating: Slow Lineup Screen Load in Single Game Mode
- **Issue**: Lineup screen takes 5-10 seconds to load player data when starting a Single Game, despite network request completing in only 294ms (49.4 kB response). The delay occurs after the network response is received, indicating a frontend processing bottleneck.
- **Location**: `FrontEnd/static/set-lineup.js` - Likely contains the bottleneck
- **Environment**: Staging
- **Mode**: Single Game Mode
- **Symptoms**:
  - Network request completes quickly (294ms)
  - Response size: 49.4 kB (reasonable)
  - UI takes 5-10 seconds to appear after network completion
  - Users see loading state for extended period
- **Root Cause Analysis (Initial)**:
  - **Network is NOT the bottleneck** - Request completes in 294ms
  - **Frontend processing is the bottleneck** - 4.7-9.7 seconds of blocking JavaScript execution
  - Likely causes:
    1. Heavy synchronous data processing (player stats/attributes/energy calculations)
    2. Inefficient DOM rendering (creating many player elements in loop, no batching)
    3. Sequential blocking operations (for loops, synchronous await calls)
    4. Missing optimization patterns (no debouncing, no requestAnimationFrame, no lazy loading)
- **Investigation Needed**:
  1. Check browser performance profiler to identify where time is spent (scripting vs rendering)
  2. Review `set-lineup.js` for synchronous loops processing player data
  3. Check for DOM thrashing (too many DOM updates causing reflows)
  4. Identify any hidden sequential operations happening after network request
- **Expected Behavior**: Lineup screen should load and display player data within 1-2 seconds after network request completes.