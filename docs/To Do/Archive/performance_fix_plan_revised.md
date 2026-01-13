# Performance Fix Plan - Revised (Single Game Mode Focus)

## Problem Summary
Phase 1 fixes didn't help Single Game mode because:
1. **N+1 query fix** - Only affects Franchise/Tournament roster endpoints, NOT Single Game mode
2. **Logging removal** - Only removed from `gameplan_routes.py`, but `api.py` still has **290 logging calls**
3. **Team lookup fix** - Small improvement, but not the main bottleneck

## Real Bottlenecks for Single Game Mode

### 1. **No Projections for Single Game Mode (CRITICAL)**
**Location**: `BackEnd/api/gameplan_routes.py`

**Problem**:
- `/api/playbooks` (line 1218): `doc = collection.find_one({"_id": doc_id})` - **NO PROJECTION**
- `/api/gameplan` (via `ensure_team_objects_exist`, line 618): `doc = collection.find_one({"_id": doc_id})` - **NO PROJECTION**
- Game documents can be large (especially after Q1+) - loads entire document unnecessarily

**Fix**: Add projection to Single Game mode document loads:
```python
# For /api/playbooks
if mode == "single":
    doc = collection.find_one(
        {"_id": doc_id},
        {"teams": 1, "home_team_id": 1, "away_team_id": 1, "_id": 1}  # Only needed fields
    )

# For ensure_team_objects_exist
if mode == "single":
    doc = collection.find_one(
        {"_id": doc_id},
        {"teams": 1, "_id": 1}  # Only teams field needed
    )
```

**Impact**: 70-90% reduction in data transfer for game documents

---

### 2. **Excessive Logging in api.py (CRITICAL)**
**Location**: `BackEnd/api/api.py`

**Problem**:
- **290 logging calls** still present (print statements + logging.info/warning/debug)
- All logging is synchronous - blocks FastAPI event loop
- Affects ALL endpoints, including `/api/simulate-quarter`, `/api/game/{game_id}`, etc.

**Fix**: Remove or reduce logging:
- Remove debug print statements (use logger instead)
- Change non-critical logging.info() to logger.debug() or remove
- Only keep ERROR and critical WARNING logs

**Impact**: 50-80% reduction in I/O blocking time

---

### 3. **Multiple Sequential Queries in ensure_team_objects_exist**
**Location**: `BackEnd/api/gameplan_routes.py`

**Problem**:
- For Single Game mode, `ensure_team_objects_exist()` loads game document (line 618)
- Then potentially does team name resolution (lines 1003-1020 in `/api/gameplan`)
- Multiple sequential `db.teams.find_one()` queries for team name resolution

**Fix**: 
- Add projection to game document load (already identified above)
- Batch team name lookups if possible
- Cache team name → ObjectId mappings

**Impact**: 30-50% reduction in query time

---

### 4. **Frontend Processing Bottleneck (Separate Issue)**
**Location**: `FrontEnd/static/set-lineup.js`

**Problem**:
- According to `bugs.md`, lineup screen slowness is frontend processing (5-10 seconds after 294ms network request)
- Not a backend issue, but contributes to perceived slowness

**Note**: This is a separate frontend optimization task

---

## Revised Phase 1: Single Game Mode Fixes (Immediate Impact)

### Priority 1: Add Projections for Single Game Mode (30 minutes)
1. **Fix `/api/playbooks` projection** (line 1218)
   - Add projection to game document load
   - Only fetch `teams`, `home_team_id`, `away_team_id`, `_id`
   - **Expected impact**: 70-90% reduction in data transfer

2. **Fix `ensure_team_objects_exist` projection** (line 618)
   - Add projection to game document load for Single Game mode
   - Only fetch `teams`, `_id`
   - **Expected impact**: 70-90% reduction in data transfer

**Total time**: 30 minutes
**Total impact**: 70-90% reduction in `/api/playbooks` and `/api/gameplan` response time

---

### Priority 2: Remove Excessive Logging from api.py (1 hour)
3. **Remove/Reduce logging in `api.py`**
   - Remove debug `print()` statements (use logger instead)
   - Change non-critical `logging.info()` to `logger.debug()` or remove
   - Only keep ERROR and critical WARNING logs
   - Focus on `/api/simulate-quarter`, `/api/game/{game_id}`, `/api/init-game`
   - **Expected impact**: 50-80% reduction in I/O blocking

**Total time**: 1 hour
**Total impact**: 50-80% improvement across ALL endpoints

---

## Expected Results (Revised)

### Before Fixes:
- Lineup screen: 2-3 seconds (backend) + 5-10 seconds (frontend)
- Playbooks page: 2-4 seconds
- Game plan page: 1-2 seconds
- Quarter simulation: 3-5 seconds

### After Revised Phase 1:
- Playbooks page: **0.3-0.6 seconds** (85-90% improvement from projection)
- Game plan page: **0.3-0.6 seconds** (85-90% improvement from projection)
- Quarter simulation: **1-2 seconds** (60% improvement from logging removal)
- Lineup screen: **0.5-1 second** (backend, frontend still needs work)

---

## Files to Modify

### Revised Phase 1:
- `BackEnd/api/gameplan_routes.py` - Add projections for Single Game mode (lines 618, 1218)
- `BackEnd/api/api.py` - Remove excessive logging (focus on simulate-quarter, game endpoints)

---

## Notes

- **Phase 1 original fixes** (N+1 queries, logging in gameplan_routes.py) were good, but didn't address Single Game mode bottlenecks
- **Frontend bottleneck** is a separate issue (see `bugs.md`)
- **Staging environment** might have resource constraints (Railway free tier) that also contribute to slowness
- **Network latency** (Railway → MongoDB Atlas) amplifies all issues (50-100ms per query)

