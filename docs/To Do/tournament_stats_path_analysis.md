# Tournament Stats Path Analysis - Team Name vs Team ID Usage

## Full Path: Game Completion → Stats Display

### 1. Game Completion & Stats Saving

**Path:** `finalizeGame.js` → `/tournament/save-result` → `finalize_game()` → `tournament.players[playerId].season[stat]`

**Files:**
- `FrontEnd/static/js/phaser/finalizeGame.js` (lines 91-118)
- `BackEnd/api/tournament_routes.py:save_result()` (lines 225-422)
- `BackEnd/utils/stat_updater.py:finalize_game()` (lines 1066-1506)

**Team Name Usage:**
1. ✅ **`box_score` structure uses team names as keys**: `box_score["Bentley-Truman"] = {...}`
   - Location: `GameManager.get_box_score()` → `BackEnd/models/game_manager.py:830-876`
   - Issue: Team names are used as keys, not `team_id`

2. ✅ **`finalize_game()` extracts team names from `box_score` keys**:
   - Location: `BackEnd/utils/stat_updater.py:1127-1231`
   - Process: Extracts `home_team_name` and `away_team_name` from `box_score` keys
   - Fallback: Looks up team names from `home_team_id`/`away_team_id` using `teams_collection.find_one({"team_id": ...})`
   - Final fallback: Uses `box_score` keys directly if team names are still None

3. ✅ **`team_name_to_id` map built for metadata**:
   - Location: `BackEnd/utils/stat_updater.py:1248-1259`
   - Process: Looks up team names from `tournament.teams` ObjectIds → builds `team_name_to_id` map
   - Usage: Sets `players.{pid}.meta.team_id` using this map (line 1322)

4. ✅ **Processing loop uses team names**:
   - Location: `BackEnd/utils/stat_updater.py:1270-1325`
   - Process: Iterates `for team_name in [home_team_name, away_team_name]` → `box_score.get(team_name, {})`
   - Issue: Relies on team names matching `box_score` keys exactly

**Current Status:** ⚠️ **BREAKING** - If team names don't match `box_score` keys, stats won't be saved

---

### 2. Roster Tab - Loading & Displaying Stats

**Path:** `loadRoster()` → `/roster/{team_name}` → `/tournament/state` → merge stats → render

**Files:**
- `FrontEnd/static/tournament.js:loadRoster()` (lines 1394-1658)
- `BackEnd/api/tournament_routes.py:get_tournament_roster()` (lines 785-889)

**Team Name Usage:**
1. ❌ **`/roster/{team_name}` endpoint requires team name**:
   - Location: `BackEnd/api/tournament_routes.py:785-832`
   - Process: Takes `team_name` parameter, looks up team by name using multiple strategies
   - Issue: **Cannot use `team_id` directly** - must look up team name first

2. ✅ **Frontend uses `userTeamName` for roster endpoint**:
   - Location: `FrontEnd/static/tournament.js:1416`
   - Process: `fetch(/roster/${userTeamName}?tournament_id=...)`
   - Status: Works, but requires team name lookup

3. ✅ **Stats merging uses player IDs (not team names)**:
   - Location: `FrontEnd/static/tournament.js:1528-1627`
   - Process: Merges `tournament.players[playerId].season` into roster data
   - Status: ✅ **Uses player IDs** - no team name dependency here

**Current Status:** ⚠️ **BREAKING** - `/roster/{team_name}` endpoint requires team name, not `team_id`

---

### 3. Stats Tab - Aggregating & Displaying Team Stats

**Path:** `refreshTeamStats()` → `/tournament/team-stats` → `aggregate_team_stats_from_players()` → render

**Files:**
- `FrontEnd/static/tournament.js:refreshTeamStats()` (lines 737-758)
- `BackEnd/api/tournament_routes.py:tournament_team_stats()` (lines 75-105)
- `BackEnd/utils/team_stats_aggregator.py:aggregate_team_stats_from_players()` (lines 13-383)

**Team Name Usage:**
1. ✅ **Aggregator uses `team_id` (ObjectId) as keys**:
   - Location: `BackEnd/utils/team_stats_aggregator.py:42-54`
   - Process: Iterates `tournament.teams` which uses ObjectId strings as keys
   - Status: ✅ **Uses `team_id`** - no team name dependency

2. ⚠️ **Aggregator resolves team names for display**:
   - Location: `BackEnd/utils/team_stats_aggregator.py:225`
   - Process: Calls `resolve_team_name(team_id_str, teams_collection, 'tournament')`
   - Usage: Only for display purposes (team name in output)
   - Status: ⚠️ **Team name lookup required for display**, but not for aggregation logic

3. ✅ **Frontend displays team names from aggregator output**:
   - Location: `FrontEnd/static/js/shared/teamStatsTable.js`
   - Process: Uses `team` field from aggregator output (which is team name)
   - Status: ✅ **Works** - team name is resolved by aggregator

**Current Status:** ✅ **WORKING** - Aggregation uses `team_id`, only resolves names for display

---

## Summary: Team Name Dependencies

### ❌ **BREAKING Dependencies (Must Fix for SS&S)**

1. **`box_score` structure uses team names as keys**
   - Location: `GameManager.get_box_score()`
   - Impact: `finalize_game()` must extract team names to match `box_score` keys
   - Fix: Change `box_score` to use `team_id` as keys: `box_score["BENTLEY_TRUMAN"] = {...}`

2. **`/roster/{team_name}` endpoint requires team name**
   - Location: `BackEnd/api/tournament_routes.py:get_tournament_roster()`
   - Impact: Frontend must pass team name, not `team_id`
   - Fix: Change endpoint to `/roster/{team_id}` or accept both

3. **`finalize_game()` processing loop uses team names**
   - Location: `BackEnd/utils/stat_updater.py:1270`
   - Impact: Must match team names to `box_score` keys
   - Fix: Use `team_id` directly if `box_score` uses `team_id` keys

### ⚠️ **Non-Breaking Dependencies (Display Only)**

1. **Aggregator resolves team names for display**
   - Location: `BackEnd/utils/team_stats_aggregator.py:225`
   - Impact: Only affects display, not logic
   - Status: Can keep as-is (lookup is fine for display)

2. **`team_name_to_id` map for metadata**
   - Location: `BackEnd/utils/stat_updater.py:1248-1259`
   - Impact: Only used to set `meta.team_id` (which is good!)
   - Status: Can keep as-is (conversion is fine)

---

## Recommended Fixes for SS&S Alignment

### Priority 1: Fix `box_score` Structure
- Change `GameManager.get_box_score()` to use `team_id` as keys instead of `team.name`
- Update `finalize_game()` to use `team_id` directly from `home_team_id`/`away_team_id`
- Remove team name extraction logic

### Priority 2: Fix `/roster/` Endpoint
- Change endpoint to accept `team_id` parameter: `/roster/{team_id}`
- Or add support for both: `/roster/{team_id_or_name}` with fallback logic
- Update frontend to use `team_id` instead of `team_name`

### Priority 3: Update Frontend
- Change `loadRoster()` to use `userTeamId` instead of `userTeamName`
- Update all roster endpoint calls to use `team_id`

---

## Current Workarounds (Temporary)

The current fixes we've added are workarounds:
1. ✅ Team name lookup from `team_id` in `finalize_game()` (fallback)
2. ✅ Case-insensitive matching for `box_score` keys (fallback)
3. ✅ Using `box_score` keys as team names if extraction fails (fallback)

These workarounds prevent immediate breakage but don't align with SS&S goals.

