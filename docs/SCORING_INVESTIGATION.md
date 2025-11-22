# Scoring Investigation: Team Points vs Player Points Mismatch

## Issue
Team points in Box Score don't match the sum of player points, indicating instances where baskets are made and team points are incremented, but player stats are not.

## Scoring Scenarios to Review

### 1. HCO (Half Court Offense) Shots
**Location:** `BackEnd/models/shot_manager.py:332`
**Code:**
```python
apply_scoring(self.game, off_team, shooter, points, stats)
```
✅ **Status:** Uses `apply_scoring` correctly

### 2. Free Throws
**Location:** `BackEnd/engine/phase_resolution.py:542`
**Code:**
```python
apply_scoring(game, off_team, shooter, 1, ["FTM"])
```
✅ **Status:** Uses `apply_scoring` correctly

### 3. OREB Putbacks
**Location:** `BackEnd/utils/shared.py:177`
**Code:**
```python
apply_scoring(game, off_team, rebounder, 2, ["FGM"])
```
✅ **Status:** Uses `apply_scoring` correctly

### 4. Fast Break Shots
**Location:** `BackEnd/models/shot_manager.py:922`
**Code:**
```python
apply_scoring(self.game, off_team, shooter, points, ["FGM"])
```
✅ **Status:** Uses `apply_scoring` correctly

### 5. FCP/HCT (Full Court Press / Half Court Trap) Shots
**Location:** `BackEnd/engine/phase_resolution.py:1333` and `1908`
**Code:**
```python
shot_result = game.shot_manager.resolve_shot(shot_roles)
```
**Status:** Calls `resolve_shot` which should use `apply_scoring` ✅ (verified at line 332)

## How `apply_scoring` Works
**Location:** `BackEnd/utils/shared.py:377-396`

1. Records player stats via `player.record_stat(stat)` for each stat in the stats list
2. Records team points via `record_team_points(game, team, points)`

The `record_stat` function (in `BackEnd/models/player.py:79-83`) automatically calculates PTS when FGM, 3PTM, or FTM are recorded:
```python
s["PTS"] = (2 * s["FGM"]) + s["3PTM"] + s["FTM"]
```

## Potential Issues to Check

1. **AND-1 Situations:** When a basket is made with a foul, free throws may be awarded. Need to verify that the free throw points are also recorded correctly.

2. **Result dict `points` field:** The `result["points"]` field is set for display purposes, but this shouldn't affect actual scoring.

3. **Deltas tracking:** Need to verify that all `apply_scoring` calls are properly reflected in the `deltas` dict for stat persistence.

4. **Player lineup issues:** If a player is `None` or not in the lineup when `apply_scoring` is called, the stat might not be recorded.

5. **Fast Break Points tracking:** Fast break points are tracked separately (`FB_PTS`) - need to verify this doesn't interfere with regular PTS tracking.

6. **Points In The Paint (PIP):** PIP is tracked separately via `shooter.record_stat("PIP", amount=points)` - this is separate from PTS.

## Next Steps
1. Add logging to `apply_scoring` to track all calls
2. Add logging to `record_team_points` to track all team point additions
3. Verify that player objects are not None when `apply_scoring` is called
4. Check if there are any direct calls to `record_team_points` without `apply_scoring`
5. Verify deltas are being created correctly for all scoring events

