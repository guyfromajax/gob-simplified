# Bug Fix: Franchise Mode Team Stats Isolation

**Date:** January 10, 2026  
**Priority:** 🔴 HIGH - Data integrity issue  
**Status:** ⏳ FIX DRAFTED

## Problem

Franchise mode team stats (W/L, PF/PA) are incorrectly reading from and writing to the universal `teams` collection, causing stats to be shared across different game modes and franchise instances.

**Symptoms:**
- Single Game mode (or other franchise instances) updating the universal `teams` collection causes incorrect stats to appear in Franchise mode
- Team records show wrong W/L counts
- Stats from one franchise affect other franchises

**Root Cause:**
1. **Writes:** Franchise mode writes W/L and PF/PA to universal `teams` collection via:
   - `_apply_team_result()` in `BackEnd/api/franchise_routes.py` (lines 244-252)
   - Direct updates in `save_result()` (lines 534-539)
   - `_apply_team_result()` in `BackEnd/models/franchise_manager.py` (lines 286-300)
   
2. **Reads:** Franchise mode reads W/L and PF/PA from universal `teams` collection in:
   - `aggregate_team_stats_from_players()` in `BackEnd/utils/team_stats_aggregator.py` (lines 206-217, fallback path for franchise mode)

**Expected Behavior:**
- Franchise mode should store W/L and PF/PA in the franchise document (in `franchise.results` which already exists)
- Franchise mode should calculate W/L and PF/PA from `franchise.results`, not from universal `teams` collection
- Franchise mode should NOT write to universal `teams` collection
- Each franchise instance should have isolated stats

## Solution

### 1. Remove Writes to Universal Teams Collection

**Files to modify:**
- `BackEnd/api/franchise_routes.py`
  - Remove `_apply_team_result()` function (lines 244-252) - no longer needed
  - Remove direct `db.teams.update_one()` calls in `save_result()` (lines 534-539)
  - Remove `_apply_team_result()` calls from `_save_game_result()` (lines 280, 300, 305)
  
- `BackEnd/models/franchise_manager.py`
  - Remove `_apply_team_result()` method (lines 286-300) - no longer needed
  - Remove `_apply_team_result()` calls from `_save_game_result()` (lines 313, 324)

**Note:** `_save_game_result()` in `franchise_routes.py` still needs to save game results to `games` collection, but should NOT update `teams` collection. The function can be simplified to just save game documents.

### 2. Calculate W/L and PF/PA from Franchise Results

**File to modify:**
- `BackEnd/utils/team_stats_aggregator.py`
  - Update `aggregate_team_stats_from_players()` to calculate franchise W/L and PF/PA from `franchise.results`
  - Add parameter: `franchise_results: Dict[str, Any] | None = None`
  - For franchise mode (when `collection_type == 'franchise'` and `franchise_results` is provided):
    - Calculate W/L and PF/PA by iterating through `franchise.results` (similar to tournament bracket logic)
    - Build `standings_data` from results instead of reading from `teams` collection

**File to update:**
- `BackEnd/api/franchise_routes.py`
  - Update `team_stats()` endpoint to pass `franchise.results` to `aggregate_team_stats_from_players()`
  - Query `franchise.results` along with `players` and `franchise_teams`

### 3. Data Structure

**Franchise results structure (already exists):**
```python
franchise.results = {
    "1": [
        {"away_id": "ObjectId1", "home_id": "ObjectId2", "away_score": 75, "home_score": 68},
        ...
    ],
    "2": [...],
    ...
}
```

**Calculation logic:**
- For each week in `results`:
  - For each game result:
    - Increment winner's W and loser's L
    - Add scores to PF/PA for both teams
- Build `standings_data` dict: `{team_id_str: {"W": int, "L": int, "PF": int, "PA": int}}`

## Implementation Plan

1. ✅ **Remove writes to teams collection from franchise routes**
   - Remove `_apply_team_result()` function
   - Remove calls to `_apply_team_result()` in `_save_game_result()`
   - Remove direct `db.teams.update_one()` in `save_result()`
   - Simplify `_save_game_result()` to only save game documents

2. ✅ **Update team_stats_aggregator to calculate from franchise.results**
   - Add `franchise_results` parameter
   - Implement calculation logic (similar to tournament bracket logic)
   - Remove fallback to `teams` collection for franchise mode

3. ✅ **Update franchise team_stats endpoint**
   - Query `franchise.results` 
   - Pass `franchise.results` to `aggregate_team_stats_from_players()`

4. ✅ **Remove unused code from franchise_manager**
   - Remove `_apply_team_result()` method (if no longer used)
   - Remove calls to `_apply_team_result()` (if any)

5. ✅ **Test**
   - Verify franchise stats are isolated (play game in one franchise, check another)
   - Verify Single Game mode doesn't affect franchise stats
   - Verify W/L and PF/PA are calculated correctly from results

## Files to Modify

1. `BackEnd/api/franchise_routes.py`
   - Remove `_apply_team_result()` function
   - Update `_save_game_result()` to remove `_apply_team_result()` calls
   - Update `save_result()` to remove `db.teams.update_one()` calls
   - Update `team_stats()` to query and pass `franchise.results`

2. `BackEnd/utils/team_stats_aggregator.py`
   - Add `franchise_results` parameter to `aggregate_team_stats_from_players()`
   - Implement franchise results calculation logic
   - Remove fallback to `teams` collection

3. `BackEnd/models/franchise_manager.py` (if needed)
   - Remove `_apply_team_result()` method if no longer used

## Testing Checklist

- [ ] Create franchise, play 2 weeks, verify stats
- [ ] Play Single Game mode with same teams, verify franchise stats unchanged
- [ ] Create second franchise, verify stats are isolated
- [ ] Verify W/L and PF/PA match results in `franchise.results`
- [ ] Verify team stats endpoint returns correct data

