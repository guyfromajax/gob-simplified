

1. Playcall Override During Opening Tip Sequence -- When a user selects a playcall override during the opening tip sequence (before the game is initialized), the play is highlighted in the playcall center UI but the override never reaches the backend. The frontend `setPlaycallOverride()` function blocks the API call because `game_id` is `null` at that point (the game hasn't been created yet via `/api/simulate-quarter`). The override only works after the first turn is simulated and `game_id` becomes available. **Solution:** Either queue the override and send it after game initialization, or defer the `game_id` check until the first turn is simulated.
2. Defensive Foul on missed shot attempt not announcing via our Announcement System

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

### ✅ Fixed: Player Stats Not Saving for User Games (Race Condition)
- **Root Cause**: Tournament mode was looking up game document from database in `/tournament/save-result`, which could be stale or incomplete due to race condition (save-result called before Q4 save completes). Franchise mode avoided this by accepting `game_document` directly from the request.
- **Fix**: 
  - Added `game_document` field to `TournamentResultRequest` (matches Franchise `CompleteWeekRequest`)
  - Updated `/tournament/save-result` to use `request.game_document` if provided (matches Franchise pattern)
  - Updated `finalizeGame.js` to pass `final_game_document` from `simulate-quarter` response to `/tournament/save-result` (matches Franchise pattern)
- **Result**: Tournament mode now uses the exact same pattern as Franchise mode - receives fresh, complete game document directly from `simulate-quarter` when `is_final=True`, eliminating race conditions and ensuring `finalize_game()` processes complete `box_score` data
- **Status**: ✅ Fixed and committed

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