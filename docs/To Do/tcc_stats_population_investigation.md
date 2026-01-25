# TCC Stats Population Investigation

## Problem
Stats are not populating in the Roster and Stats tabs in Tournament Command Center after playing the first round.

## Code Path Analysis

### 1. Stats Saving Flow (Game → Tournament Document)

**Path:** `finalize_game()` → `tournament.players[playerId].season[stat]`

**Location:** `BackEnd/utils/stat_updater.py:finalize_game()` (lines 1066-1360)

**Process:**
1. Extracts `box_score` from game document
2. For each player in `box_score`, builds `$inc` operations: `players.{pid_str}.season.{stat}`
3. Executes single MongoDB update with `$inc` operations
4. Checks `applied_games` array for idempotency

**Potential Issues:**
- `box_score` might be empty or malformed
- Player IDs in `box_score` might not match `tournament.players` keys
- Idempotency check might be preventing update (game already in `applied_games`)
- `inc_doc` might be empty (logged at line 1238-1248)

### 2. Roster Tab Flow

**Path:** `loadRoster()` → `/roster/{team_name}` → `/tournament/state` → merge stats

**Location:** `FrontEnd/static/tournament.js:loadRoster()` (lines 1394-1658)

**Process:**
1. Fetches roster from `/roster/{team_name}?tournament_id={id}`
2. Fetches tournament document from `/tournament/state`
3. Merges `tournament.players[playerId].season` into `rosterData.players[].stats.season`
4. Renders roster with merged stats

**Potential Issues:**
- Player ID mismatch between roster and tournament document (logged at line 1542-1547)
- Tournament document not loaded (logged at line 1611-1617)
- Stats exist but are all zeros (checked at line 1555)

### 3. Stats Tab Flow

**Path:** `refreshTeamStats()` → `/tournament/team-stats` → aggregator → render

**Location:** 
- Frontend: `FrontEnd/static/tournament.js:refreshTeamStats()` (lines 737-758)
- Backend: `BackEnd/api/tournament_routes.py:tournament_team_stats()` (lines 74-105)
- Aggregator: `BackEnd/utils/team_stats_aggregator.py` (uses `3PTM`/`3PTA` after our fix)

**Process:**
1. Fetches from `/tournament/team-stats?tournament_id={id}`
2. Aggregator reads `tournament.players[pid].season` stats
3. Maps `3PTM` → `3PTM` (no translation after our fix)
4. Returns aggregated team stats

**Potential Issues:**
- No players in `tournament.players` (aggregator skips them)
- All player stats are zero (aggregator still processes, but result is zeros)
- Field name mismatch (should be fixed by our `3PTM` standardization)

## Diagnostic Steps

### Step 1: Check if `finalize_game()` is being called

**Check Railway logs for:**
```
🔍 [FINALIZE_GAME] Processed X players, Y stat increments
```

If this log is missing, `finalize_game()` is not being called.

### Step 2: Check if `box_score` has data

**Check Railway logs for:**
```
⚠️ [FINALIZE_GAME] inc_doc is EMPTY - no stats to increment!
```

If this appears, `box_score` is empty or malformed.

### Step 3: Check if stats are in tournament document

**Query MongoDB directly:**
```javascript
db.tournaments.findOne(
  {_id: ObjectId("TOURNAMENT_ID")},
  {"players": 1}
)
```

Check if `players` object exists and has `season` stats with non-zero values.

### Step 4: Check player ID matching

**Check browser console for:**
```
⚠️ [DEBUG loadRoster] Player ID X not found in tournament.players
```

If this appears, player IDs don't match between roster and tournament document.

## Test File

Created `tests/test_tcc_stats_population.py` to verify end-to-end flow:
1. Creates tournament
2. Simulates game
3. Finalizes game
4. Verifies stats in tournament document
5. Tests aggregator
6. Verifies field names (3PTM/3PTA)

**To run:** Requires proper Python environment with BackEnd imports.

## Most Likely Root Causes

1. **`finalize_game()` skipped due to missing game document** - At line 402-404 in `tournament_routes.py`, if `summary.get("_id")` is falsy, `finalize_game()` is skipped with error: "Skipping finalize_game - game document not found"
2. **Empty `box_score`** - Game document might not have proper `box_score` structure
3. **Player ID mismatch** - Roster uses different player ID format than tournament document
4. **Idempotency preventing update** - Game already in `applied_games`, update skipped

## Critical Finding

**Location:** `BackEnd/api/tournament_routes.py:save_result()` (lines 390-404)

The code checks:
```python
if summary and summary.get("_id"):
    stat_updater.finalize_game(...)
else:
    logger.error("Skipping finalize_game - game document not found")
```

**If `summary` doesn't have `_id`, stats will NEVER be saved!**

**Check Railway logs for:**
```
❌ [SAVE-RESULT] Skipping finalize_game - game document not found. Stats will not be applied.
```

If this error appears, the game document is not being passed correctly to `save_result()`.

## Next Steps

1. Check Railway logs for `finalize_game()` execution
2. Query tournament document directly to see if stats exist
3. Check browser console for player ID mismatch warnings
4. Verify `box_score` structure in game document

