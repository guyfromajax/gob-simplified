# Tournament Mode Game Order Fix Plan

## Problem Statement
Tournament mode currently simulates and finalizes computer games BEFORE the user's game, causing:
- Only 5 players showing stats (lineup players from early games)
- Team stats grid empty (players not properly initialized)
- Leaders only showing 5 players (same reason)
- Leaders not styled (userTeamName not set correctly)

Franchise mode does it correctly: user game first, then computer games. This ensures consistent player initialization and stats aggregation.

## Goal
Re-order tournament mode to match Franchise mode pattern: finalize user's game FIRST, then simulate/finalize computer games.

---

## Task 1: Re-order Game Finalization in `/tournament/save-result`

**Current Flow:**
1. Save user's game result to bracket
2. Loop through matchups, simulate computer games, finalize them
3. Finalize user's game (if game document found)

**Target Flow (matches Franchise):**
1. Save user's game result to bracket
2. **Finalize user's game FIRST** (apply stats, initialize players)
3. Then simulate and finalize computer games

**Files to Modify:**
- `BackEnd/api/tournament_routes.py` - `save_result()` function

**Changes:**
1. Move user's game finalization to happen immediately after saving result to bracket
2. Ensure `finalize_game()` is called for user's game BEFORE the computer game simulation loop
3. Keep computer game simulation/finalization in the loop (unchanged)

**Validation:**
- User's game appears in `applied_games` before computer games
- Backend logs show user's game finalized first
- All 12 players from user's team have stats entries

---

## Task 2: Verify `_ensure_all_roster_players_initialized` Works Correctly

**Current Issue:**
- Function may not be logging or may be failing silently
- Need to verify it's being called and working

**Files to Check:**
- `BackEnd/utils/stat_updater.py` - `_ensure_all_roster_players_initialized()`
- `BackEnd/utils/stat_updater.py` - `apply_stats_from_summary()`

**Changes:**
1. Add print statements to verify function is called
2. Verify it's using `$setOnInsert` correctly (already fixed)
3. Ensure it's called after `apply_stats_from_summary` processes game players

**Validation:**
- Backend logs show `✅ [ENSURE-ROSTER] Initialized X roster players...`
- All 12 players from both teams have entries in tournament document

---

## Task 3: Fix Leaders Styling (Bold + Primary Color)

**Current Issue:**
- User team players not showing in bold with primary color
- `userTeamName` may not be set when `renderLeaderboards()` runs

**Files to Modify:**
- `FrontEnd/static/tournament.js` - `renderLeaderboards()` function
- `FrontEnd/static/tournament.js` - `refreshLeaders()` function

**Changes:**
1. Ensure `userTeamName` is set before `renderLeaderboards()` is called
2. Verify team name matching logic (ObjectId vs team name)
3. Add fallback to check both `userTeamName` and `userTeamId`
4. Ensure primary color is loaded before rendering

**Validation:**
- User team players appear in bold with primary color in all leader categories
- Matches FCC styling exactly

---

## Task 4: Fix Team Stats Grid

**Current Issue:**
- Team stats grid is empty
- Endpoint may not be returning data or frontend not rendering

**Files to Check:**
- `BackEnd/api/tournament_routes.py` - `tournament_team_stats()` endpoint
- `FrontEnd/static/tournament.js` - `refreshTeamStats()` and `renderTeamStats()` functions

**Changes:**
1. Verify endpoint is being called (add logging)
2. Verify endpoint returns data (check response structure)
3. Verify frontend renders the data (check `renderTeamStatsTable()`)
4. Ensure all players have `meta.team_id` set (required for aggregation)

**Validation:**
- Team stats grid shows all 8 teams with aggregated stats
- Stats match sum of individual player stats

---

## Task 5: Verify All 12 Players Show on Team Tab

**Current Issue:**
- Console shows 12 rows added, but only 5 visible
- May be multiple render calls or CSS issue

**Files to Check:**
- `FrontEnd/static/tournament.js` - `renderRosterStats()` and `renderRosterStatsTable()`
- Check for multiple calls or race conditions

**Changes:**
1. Add logging to track all calls to `renderRosterStats`
2. Verify no filtering is happening
3. Check if CSS is hiding rows
4. Ensure `loadTeamData()` completes before rendering

**Validation:**
- All 12 players visible in Team tab stats table
- All players show stats (some may be zeros, which is correct)

---

## Task 6: Verify Leaders Show All Players

**Current Issue:**
- Only 5 players appear in leaders (those who played)
- Should show all players, even with zeros

**Files to Check:**
- `BackEnd/utils/stat_updater.py` - `recompute_tournament_leaders()`
- Verify filtering logic (should include all players for counting stats)

**Changes:**
1. Verify leaders endpoint includes all players (not just those with non-zero stats)
2. For percentage stats (FG%, FT%, TPM), filtering is correct (only show if attempts > 0)
3. For counting stats (PTS, REB, AST, etc.), show all players

**Validation:**
- All players appear in counting stat leaders (PTS, REB, AST, STL, BLK)
- Percentage stat leaders only show players with attempts (correct)

---

## Implementation Order

1. **Task 1** (Re-order finalization) - This is the core fix
2. **Task 2** (Verify initialization) - Ensure it works with new order
3. **Task 3** (Leaders styling) - Simple fix once data is correct
4. **Task 4** (Team stats grid) - Should work once players are initialized
5. **Task 5** (Team tab players) - Debug why 12 rows added but only 5 visible
6. **Task 6** (Leaders all players) - Verify filtering logic

---

## Success Criteria

✅ User's game finalized before computer games (matches Franchise pattern)
✅ All 12 players from user's team have stats entries
✅ All 12 players visible on Team tab
✅ All players appear in leaders (counting stats)
✅ User team players styled in bold + primary color
✅ Team stats grid populated with all 8 teams
✅ Backend logs show proper initialization order

---

## Notes

- This aligns Tournament mode with Franchise mode's proven pattern
- Should eliminate race conditions and initialization issues
- Makes debugging easier (same pattern = same behavior)
- SS&S: Simple (replicate working pattern), Stable (proven approach), Scalable (consistent across modes)

