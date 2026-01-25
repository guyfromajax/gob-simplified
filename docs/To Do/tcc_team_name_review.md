# TCC Team Name Usage Review

## Summary
After transitioning to `team_id` as the universal identifier, reviewed all TCC functionality to identify remaining team name dependencies.

## Issues Found & Fixed

### ✅ Fixed Issues

1. **`/tournament/scouting-report` endpoint**
   - **Issue:** Only accepted `team_name` parameter
   - **Fix:** Now accepts `team_id` (ObjectId or string) with `team_name` fallback
   - **Location:** `BackEnd/api/tournament_routes.py:723-763`
   - **Status:** ✅ Fixed

2. **`/tournament/roster` endpoint**
   - **Issue:** Only accepted `team_name` parameter
   - **Fix:** Now accepts `team_id` (ObjectId or string) with `team_name` fallback
   - **Location:** `BackEnd/api/tournament_routes.py:803-860`
   - **Status:** ✅ Fixed (Note: TCC uses app-level `/roster/` endpoint, not this one)

### ✅ Already Working

1. **`/tournament/team-data` endpoint**
   - **Status:** ✅ Already accepts `team_id` parameter with `team_name` fallback
   - **Location:** `BackEnd/api/tournament_routes.py:608-719`

2. **`/roster/` app-level endpoint**
   - **Status:** ✅ Already fixed to accept `team_id` (ObjectId/string) with `team_name` fallback
   - **Location:** `BackEnd/api/api.py:3930-4072`

3. **Frontend `loadRoster()`**
   - **Status:** ✅ Already updated to use `team_id` (ObjectId)
   - **Location:** `FrontEnd/static/tournament.js:1394-1500`

4. **Frontend `loadTeamData()`**
   - **Status:** ✅ Already uses `team_id` (ObjectId)
   - **Location:** `FrontEnd/static/tournament.js:2112-2192`

### ⚠️ Acceptable Team Name Usage (Display Only)

1. **Scouting Report - `upcomingOpponent`**
   - **Status:** ⚠️ Uses team name from bracket (acceptable)
   - **Location:** `FrontEnd/static/tournament.js:1997-2041`
   - **Note:** Backend endpoints accept `team_name` as fallback, so this works. Could be improved by resolving `team_id` from name, but not breaking.

2. **Bracket comparisons**
   - **Status:** ⚠️ Uses team names (acceptable - bracket stores team names)
   - **Location:** `FrontEnd/static/tournament.js:44-47, 1136-1137`
   - **Note:** Bracket structure uses team names, not ObjectIds. This is acceptable for display/comparison purposes.

3. **Team color cache**
   - **Status:** ⚠️ Uses team names as keys (acceptable - display only)
   - **Location:** `FrontEnd/static/tournament.js:646-656`
   - **Note:** Only used for display (leaderboard highlighting). Not breaking.

## Remaining Work

### Optional Improvements (Not Breaking)

1. **Resolve `team_id` from `upcomingOpponent` name in scouting report**
   - Could look up team ObjectId from team name before calling endpoints
   - Not necessary since backend accepts `team_name` as fallback
   - **Priority:** Low

2. **Bracket structure migration**
   - Bracket currently stores team names, not ObjectIds
   - Would require database migration and bracket generation logic changes
   - **Priority:** Low (bracket is display-only, team names work fine)

## Conclusion

All **breaking** team name dependencies in TCC have been fixed. Remaining team name usage is:
- ✅ Acceptable (display-only, bracket comparisons)
- ✅ Backward compatible (backend accepts `team_name` as fallback)

The TCC should now work correctly with the `team_id` transition.

