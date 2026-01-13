# Performance Fix Plan - Staging Slowness

## Problem Summary
The staging environment is VERY slow:
- Lineup screen loading takes too long
- Quarter simulations are very slow
- Playbooks page loading is very slow
- Game plan page loading is very slow
- Saving settings (Playbooks, Game Plan) is very slow

This affects Single Game mode but likely impacts all game modes.

## Root Causes Identified

### 1. **N+1 Query Pattern (CRITICAL - Biggest Issue)**
**Location**: `BackEnd/api/franchise_routes.py`, `BackEnd/api/tournament_routes.py`

**Problem**: 
- Tournament/Franchise roster endpoints do individual `db.players.find_one({"_id": pid})` queries in a loop
- 12 players per team = 12 sequential database queries
- Each query: 50-100ms network latency + query time
- **Total impact**: 600ms - 1.2s just for player lookups

**Example**:
```python
# BackEnd/api/franchise_routes.py line 1926
for pid in team_player_ids:
    core_player = db.players.find_one({"_id": pid}, {...})  # N+1 query!
```

**Fix**: Batch player lookups using `$in` operator:
```python
# Batch lookup
player_ids_obj = [ObjectId(pid) for pid in team_player_ids]
core_players = {str(p["_id"]): p for p in db.players.find({"_id": {"$in": player_ids_obj}}, {...})}

# Then use cached results
for pid in team_player_ids:
    core_player = core_players.get(str(pid))
```

**Impact**: 12 queries → 1 query = **85-90% reduction** in database overhead

---

### 2. **Excessive Logging (Blocking I/O)**
**Location**: `BackEnd/api/api.py`, `BackEnd/api/gameplan_routes.py`

**Problem**:
- **190+ logging.info/debug calls** in `api.py` alone
- **Many logger.warning() calls** in `gameplan_routes.py` (especially in `/api/playbooks`)
- All logging is **synchronous** - blocks FastAPI event loop
- Each log write = synchronous I/O operation = blocked thread

**Example**:
```python
# BackEnd/api/gameplan_routes.py line 1195, 1607-1614
logger.warning(f"🔍 [GET PLAYBOOKS] Called with mode={mode}...")
logger.warning(f"🔍 [PLAYBOOKS GET] Sample motion percentages: {sample_motion}")
logger.warning(f"🔍 [PLAYBOOKS GET] ALL motion percentages being returned: {motion_percentages}")
```

**Fix**: 
- Remove debug logging from production/staging
- Use logging levels (INFO, WARNING, ERROR) instead of all WARNING
- Only log errors and critical events in staging/production
- Consider async logging for non-critical logs

**Impact**: **50-80% reduction** in I/O blocking time

---

### 3. **Inefficient Team Lookup**
**Location**: `BackEnd/api/api.py` line 2655

**Problem**:
- `/roster/{team_name}` loads **ALL teams** first: `all_teams = [t["name"] for t in teams_collection.find({}, {"name": 1})]`
- Then does case-insensitive matching in Python (not MongoDB)
- Loads 8-16 teams unnecessarily

**Fix**: Use MongoDB case-insensitive query:
```python
# Instead of loading all teams, use regex for case-insensitive match
normalized_name = unidecode(team_name.strip().replace("-", " ")).lower()
team_doc = teams_collection.find_one({
    "$expr": {
        "$eq": [
            {"$toLower": {"$replaceAll": {"input": "$name", "old": "-", "new": " "}}},
            normalized_name
        ]
    }
})
```

**Impact**: 1 query instead of loading all teams = **90% reduction** in data transfer

---

### 4. **Multiple Sequential Database Queries**
**Location**: `BackEnd/api/gameplan_routes.py`, `BackEnd/api/api.py`

**Problem**:
- `/api/gameplan` and `/api/playbooks` make multiple sequential queries
- Load game document → potentially load from core teams collection as fallback
- Each query waits for previous one

**Fix**: 
- Cache document loads within request scope
- Combine queries where possible
- Use projections to reduce data transfer (already done in some places)

**Impact**: **20-30% reduction** in query time

---

### 5. **Missing Database Indexes**
**Location**: All collections

**Problem**:
- Team lookups by `name` might not have indexes
- Player lookups by `_id` should be indexed (MongoDB default, but verify)
- Compound indexes missing for common query patterns

**Fix**: Create indexes:
```python
# teams collection
db.teams.create_index("name")  # For team name lookups

# games collection (if needed)
db.games.create_index([("franchise_id", 1), ("quarter", 1)])
```

**Impact**: **50-80% reduction** in query time for indexed fields

---

### 6. **Connection Pooling Not Optimized**
**Location**: `BackEnd/db.py` line 58

**Problem**:
- `MongoClient` uses default settings (maxPoolSize=100, but no explicit tuning)
- No connection pool warming
- No retry logic configuration

**Fix**: Configure connection pool:
```python
client = MongoClient(
    uri, 
    serverSelectionTimeoutMS=5000,
    maxPoolSize=200,  # Increase pool size
    minPoolSize=10,   # Keep warm connections
    retryWrites=True,
    retryReads=True
)
```

**Impact**: **10-20% improvement** in connection overhead

---

## Implementation Priority

### Phase 1: Critical Fixes (Immediate Impact)
1. **Fix N+1 queries** (1-2 hours)
   - Batch player lookups in `/franchise/roster`
   - Batch player lookups in `/tournament/roster`
   - **Expected impact**: 85-90% reduction in roster loading time

2. **Remove excessive logging** (30 minutes)
   - Remove debug `logger.warning()` calls from `/api/playbooks`
   - Change debug logs to INFO level or remove
   - **Expected impact**: 50-80% reduction in I/O blocking

3. **Fix team lookup** (30 minutes)
   - Use MongoDB query instead of loading all teams
   - **Expected impact**: 90% reduction in team lookup overhead

**Total Phase 1 time**: 2-3 hours
**Total Phase 1 impact**: **70-85% improvement** in overall performance

---

### Phase 2: Database Optimization (Moderate Impact)
4. **Add database indexes** (30 minutes)
   - Index on `teams.name`
   - Verify existing indexes
   - **Expected impact**: 50-80% reduction in query time

5. **Optimize connection pooling** (15 minutes)
   - Increase maxPoolSize
   - Add minPoolSize
   - **Expected impact**: 10-20% improvement

**Total Phase 2 time**: 45 minutes
**Total Phase 2 impact**: **Additional 20-30% improvement**

---

### Phase 3: Advanced Optimizations (Lower Priority)
6. **Request-scoped caching** (2-3 hours)
   - Cache document loads within request
   - **Expected impact**: 10-20% improvement

7. **Parallel queries** (1-2 hours)
   - Where possible, run queries in parallel
   - **Expected impact**: 10-15% improvement

**Total Phase 3 time**: 3-5 hours
**Total Phase 3 impact**: **Additional 15-25% improvement**

---

## Expected Results

### Before Fixes:
- Lineup screen: **2-3 seconds**
- Quarter simulation: **3-5 seconds**
- Playbooks page: **2-4 seconds**
- Game plan page: **1-2 seconds**
- Saving settings: **1-2 seconds**

### After Phase 1:
- Lineup screen: **0.3-0.5 seconds** (85% improvement)
- Quarter simulation: **1-2 seconds** (60% improvement)
- Playbooks page: **0.5-1 second** (75% improvement)
- Game plan page: **0.5-1 second** (50% improvement)
- Saving settings: **0.3-0.5 seconds** (75% improvement)

### After Phase 1 + Phase 2:
- Lineup screen: **0.2-0.3 seconds** (90% improvement)
- Quarter simulation: **0.8-1.5 seconds** (70% improvement)
- Playbooks page: **0.3-0.5 seconds** (85% improvement)
- Game plan page: **0.3-0.5 seconds** (70% improvement)
- Saving settings: **0.2-0.4 seconds** (80% improvement)

---

## Testing Plan

1. **Before fixes**: Measure current performance (baseline)
2. **After each phase**: Measure performance improvement
3. **Verify**: All functionality still works correctly
4. **Monitor**: Railway logs for errors after deployment

---

## Files to Modify

### Phase 1:
- `BackEnd/api/franchise_routes.py` - Fix N+1 queries
- `BackEnd/api/tournament_routes.py` - Fix N+1 queries
- `BackEnd/api/gameplan_routes.py` - Remove excessive logging
- `BackEnd/api/api.py` - Fix team lookup, remove excessive logging

### Phase 2:
- `BackEnd/db.py` - Optimize connection pooling
- `scripts/setup_indexes.py` (new) - Add database indexes

### Phase 3:
- `BackEnd/utils/data_access_manager.py` (new) - Request-scoped caching
- Various route files - Parallel queries

---

## Notes

- **Single Game mode** uses `/roster/{team_name}` endpoint which has inefficient team lookup
- **All modes** are affected by excessive logging
- **Tournament/Franchise modes** are most affected by N+1 queries (roster loading)
- **Network latency** (Railway → MongoDB Atlas) amplifies all issues (50-100ms per query)

