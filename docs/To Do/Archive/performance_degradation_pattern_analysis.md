# Performance Degradation Pattern Analysis

**Date Created:** January 11, 2026  
**Status:** 🔍 INVESTIGATING  
**Priority:** 🔴 CRITICAL  
**Related:** Task 2 (Database Optimization) from Go Live Plan

## Observed Pattern

### First Game, First Time (Fast ✅)
- Lineup screen: **Fast** (players load immediately)
- Playbooks: **Fast** (loads immediately)
- Game Plan: **Fast** (loads immediately)
- Sim Quarter (Q1): **Fast** (sims quickly)

### First Game, After Q1 (Slow ❌)
- Lineup screen: **Slow** (takes long time to load)
- Playbooks: **Slow** (takes long time to load)
- Game Plan: **Slow** (takes long time to load)
- Play Quarter (Q2): **Slow** (long pauses between turns)

### New Game (Slow from Start ❌)
- Lineup screen: **Slow** (even though it's a new game)
- Playbooks: **Slow**
- Game Plan: **Slow**

---

## Root Cause Analysis

### 1. **Game Document Size Growth** 🔴 CRITICAL

**After Q1 simulation, the game document contains:**
- **50+ turn objects** (each turn has full game state, player data, etc.)
- **Player stats** (accumulated from Q1)
- **Game state data** (scores, fouls, timeouts, etc.)
- **Lineup data** (for both teams)
- **All player energy/attributes** (updated during Q1)

**Size Growth:**
- **New game:** ~10-20 KB
- **After Q1:** ~200-500 KB (10-25x larger!)
- **After Q2:** ~400-1000 KB (20-50x larger!)
- **After Q4:** ~800-2000 KB (40-100x larger!)

**Impact:**
- Loading the full game document takes much longer
- Network transfer time increases (50ms → 500ms+)
- JavaScript processing time increases (parsing larger JSON)
- DOM rendering time increases (more data to process)

---

### 2. **Missing Projections in `/api/game/{game_id}`** 🔴 CRITICAL

**The Problem:**
- `/api/playbooks` uses projections ✅ (only loads `teams`, `home_team_id`, `away_team_id`)
- `/api/gameplan` uses projections ✅ (only loads needed fields)
- `/api/game/{game_id}` does **NOT** use projections ❌ (loads **ENTIRE** game document)

**Code Location:** `BackEnd/api/api.py` line 817
```python
saved = games_collection.find_one({"_id": game_id})  # ❌ NO PROJECTION!
```

**What the Lineup Screen Actually Needs:**
- Player energy levels (`players[].NG`)
- Player stats (`players[].stats`)
- Player attributes (`players[].attributes.EM`, `players[].attributes.MO`)
- Ineligible players (`ineligible_players`)
- **NOT needed:** All turn objects, full game state, etc.

**Fix:**
```python
# Only load what's needed for lineup screen
saved = games_collection.find_one(
    {"_id": game_id},
    {
        "players": 1,           # Player energy/stats
        "ineligible_players": 1, # Fouled out players
        "quarter": 1,           # Current quarter
        "_id": 1
    }
)
```

**Expected Improvement:** 80-95% reduction in data transfer (500KB → 10-50KB)

---

### 3. **Memory/Connection Issues** 🟡 MEDIUM

**The fact that a NEW game is also slow suggests:**
- Database connections might be getting exhausted
- Memory leaks in backend (accumulating data in `ongoing_games` dict)
- Connection pooling issues (stale connections)
- Railway instance might be throttling under load

**Investigation Needed:**
- Check Railway logs for connection errors
- Monitor `ongoing_games` dict size (memory leak?)
- Check MongoDB connection pool settings
- Verify Railway instance isn't being throttled

---

### 4. **Turn-by-Turn Processing Overhead** 🟡 MEDIUM

**Long pauses between turns in Q2 suggests:**
- Each turn loads the full game document (no projection)
- Each turn processes larger game state (more turns in history)
- Each turn saves the full game document (growing document size)
- Stat calculations get slower (more data to process)

**Impact:**
- Turn 1: Fast (small game document)
- Turn 25: Slower (larger game document)
- Turn 50: Very slow (very large game document)

---

## Why First Time Was Fast

**Cold Start Benefits:**
1. **Small game document** (new game, no turns yet)
2. **Fresh database connection** (no connection pool exhaustion)
3. **Clean memory** (no accumulated data in `ongoing_games`)
4. **Railway instance fresh** (no throttling yet)

**After Q1:**
1. **Large game document** (50+ turns, player stats)
2. **Database connections may be stale** (connection pool issues)
3. **Memory may be accumulating** (`ongoing_games` dict growing)
4. **Railway instance may be throttling** (under load)

---

## Why New Game Is Also Slow

**This is the smoking gun!** A new game should be fast (small document), but it's slow. This suggests:

1. **Connection pool exhaustion** - All connections are busy/stale
2. **Memory leaks** - Backend accumulating data from previous games
3. **Railway throttling** - Instance is under load from previous game
4. **Database performance** - MongoDB Atlas may be throttling under load

**Most Likely:** Connection pool or memory leak issues

---

## Fixes Needed (Priority Order)

### Fix 1: Add Projections to `/api/game/{game_id}` 🔴 CRITICAL
**Impact:** 80-95% reduction in data transfer
**Effort:** Low (1-2 hours)
**Risk:** Low (just limiting fields returned)

**What to Project:**
- For lineup screen: `players`, `ineligible_players`, `quarter`
- For box score: `players`, `score`, `quarter`, `turns` (last N turns only)
- For game state: Only what's actually needed

### Fix 2: Investigate Connection Pool Issues 🟡 MEDIUM
**Impact:** Could fix "new game is slow" issue
**Effort:** Medium (2-4 hours)
**Risk:** Medium (requires careful testing)

**Actions:**
- Check MongoDB connection pool settings
- Monitor connection usage
- Add connection pool monitoring/logging
- Verify connections are being closed properly

### Fix 3: Optimize Game Document Structure 🟡 MEDIUM
**Impact:** Reduce document size growth
**Effort:** High (4-8 hours)
**Risk:** High (requires schema changes)

**Options:**
- Don't store all turns in game document (store separately)
- Archive old turns (move to separate collection)
- Use projections more aggressively
- Limit turn history stored in document

### Fix 4: Memory Leak Investigation 🟢 LOW
**Impact:** Could fix "new game is slow" issue
**Effort:** Medium (2-4 hours)
**Risk:** Low (just monitoring)

**Actions:**
- Monitor `ongoing_games` dict size
- Check for objects not being garbage collected
- Add memory profiling
- Verify games are removed from memory when complete

---

## Next Steps

1. **Immediate:** Add projections to `/api/game/{game_id}` endpoint
2. **Then:** Test if this fixes the slowdown after Q1
3. **If new game still slow:** Investigate connection pool/memory issues
4. **If still slow:** Optimize game document structure

---

## Related

- `docs/To Do/frontend_performance_fix_plan.md` - Frontend performance fixes
- `docs/To Do/Task_2_Performance_Investigation_Plan.md` - Performance investigation plan
- `BackEnd/api/api.py` - `/api/game/{game_id}` endpoint (needs projections)

