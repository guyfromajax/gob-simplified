# Full Season Performance Optimization Plan

**Status:** 🔴 **CRITICAL** - Performance issues identified (January 2025)

## Problem Summary

After simulating a full regular season (14 weeks), the franchise document has grown to **402KB**. This is causing severe performance issues:

- **FCC Initial Load**: ~1.2MB transferred (multiple full document loads)
- **Per Quarter During Gameplay**: ~2MB+ transferred (4+ full document loads)
- **After Each Game**: ~402KB for stat finalization

**Root Cause**: Multiple endpoints are loading the **entire 402KB franchise document** when they only need small subsets of data. No projections are being used.

## Performance Impact

### Current Data Transfer Estimates

**FCC Initial Load:**
- `/franchise/state` - 402KB (full doc, no projection)
- `/franchise/command-center/data` - 402KB × 2 (loads twice in same endpoint)
- `/franchise/standings` - 402KB (full doc, no projection)
- `/franchise/schedule` - 402KB (full doc, no projection)
- **Total: ~1.6MB transferred on FCC load**

**Per Quarter During Gameplay:**
- `/api/simulate-quarter` calls `load_team_attributes_from_doc()` × 2 (home + away) = 804KB
- `/api/simulate-quarter` calls `load_team_settings_from_doc()` × 2 (home + away) = 804KB
- `stat_updater.finalize_game()` loads full doc = 402KB
- **Total: ~2MB+ per quarter**

**After Each Game:**
- `stat_updater.finalize_game()` - 402KB

### Why This Is NOT a Dev Stack Issue

- **Railway (Backend)**: Fast, reliable hosting - not the bottleneck
- **Netlify (Frontend)**: Fast CDN - not the bottleneck
- **MongoDB Atlas**: Fast database - not the bottleneck

**The Real Issue**: We're transferring **2MB+ per quarter** unnecessarily. Even with perfect infrastructure, this would be slow.

## Optimization Plan

### Phase 1: Add Projections to High-Frequency Endpoints (Critical)

**Priority: 🔴 CRITICAL - Immediate Impact**

#### 1.1 `/franchise/state` Endpoint
**Current**: Loads full 402KB document  
**Fix**: Add projection to only return needed fields
- **Option A**: Return only `players` object (if that's all that's needed)
- **Option B**: Accept query parameter to specify which fields to return
- **Impact**: Reduce from 402KB to ~50-100KB (80% reduction)

#### 1.2 `/franchise/command-center/data` Endpoint
**Current**: Loads full document twice (lines 854 and 921)  
**Fix**: 
- Load once and reuse
- Add projection: `{"franchise_teams": 1, "training_status": 1, "week": 1, "eos_tournament": 1, "user_team_id": 1, "user_team_object_id": 1}`
- **Impact**: Reduce from 804KB to ~10KB (98% reduction)

#### 1.3 `/franchise/standings` Endpoint
**Current**: Loads full document  
**Fix**: Add projection: `{"schedule": 1, "week": 1, "eos_tournament": 1, "results": 1}`
- **Impact**: Reduce from 402KB to ~20KB (95% reduction)

#### 1.4 `/franchise/schedule` Endpoint
**Current**: Loads full document  
**Fix**: Add projection: `{"schedule": 1, "results": 1, "week": 1}`
- **Impact**: Reduce from 402KB to ~30KB (92% reduction)

#### 1.5 `/franchise/team-data` Endpoint
**Current**: Loads full document  
**Fix**: Add projection: `{"franchise_teams": 1}` (only the specific team)
- **Impact**: Reduce from 402KB to ~15KB (96% reduction)

### Phase 2: Optimize Gameplay Endpoints (Critical)

**Priority: 🔴 CRITICAL - Immediate Impact**

#### 2.1 `load_team_attributes_from_doc()` Function
**Current**: Loads full document, only uses `franchise_teams.{team_id}`  
**Fix**: Add projection: `{"franchise_teams": 1}`
- **Impact**: Reduce from 402KB to ~50KB per call (87% reduction)
- **Total Impact**: 4 calls per quarter = 200KB instead of 1.6MB (87% reduction)

#### 2.2 `load_team_settings_from_doc()` Function
**Current**: Loads full document, only uses `franchise_teams.{team_id}`  
**Fix**: Add projection: `{"franchise_teams": 1}`
- **Impact**: Reduce from 402KB to ~50KB per call (87% reduction)
- **Total Impact**: 4 calls per quarter = 200KB instead of 1.6MB (87% reduction)

#### 2.3 `stat_updater.finalize_game()` Function
**Current**: Loads full document to update player stats  
**Fix**: 
- Use `find_one_and_update()` with projection on return
- Only fetch `players` object: `{"players": 1, "applied_games": 1}`
- **Impact**: Reduce from 402KB to ~300KB (25% reduction - players object is large)

### Phase 3: Caching Strategy (High Priority)

**Priority: 🟡 HIGH - Significant Impact**

#### 3.1 In-Memory Caching During Gameplay
- Cache franchise document in memory during active gameplay session
- Only reload when game completes (for stat updates)
- **Impact**: Eliminate redundant loads during gameplay

#### 3.2 Frontend Caching
- Cache `/franchise/command-center/data` response in `sessionStorage`
- Only refetch when navigating away and back
- **Impact**: Eliminate redundant FCC loads

### Phase 4: Document Structure Optimization (Medium Priority)

**Priority: 🟢 MEDIUM - Long-term Solution**

#### 4.1 Separate Historical Data
- Move old game results to separate collection: `franchise_results`
- Keep only current season data in main franchise document
- **Impact**: Reduce document size from 402KB to ~150KB (62% reduction)

#### 4.2 Remove Career Stats Duplication
- Career stats duplicate season stats (doubles player data)
- Compute career from season when needed, or store separately
- **Impact**: Reduce players object size by ~50%

## Implementation Priority

### Immediate (This Week)
1. ✅ Add projections to `/franchise/state` (Phase 1.1)
2. ✅ Fix `/franchise/command-center/data` double load (Phase 1.2)
3. ✅ Add projections to `load_team_attributes_from_doc()` (Phase 2.1)
4. ✅ Add projections to `load_team_settings_from_doc()` (Phase 2.2)

**Expected Impact**: Reduce FCC load from 1.6MB to ~100KB (94% reduction)  
**Expected Impact**: Reduce gameplay per-quarter from 2MB+ to ~500KB (75% reduction)

### Short-term (Next Week)
5. Add projections to `/franchise/standings` (Phase 1.3)
6. Add projections to `/franchise/schedule` (Phase 1.4)
7. Add projections to `/franchise/team-data` (Phase 1.5)
8. Optimize `stat_updater.finalize_game()` (Phase 2.3)

### Medium-term (Next Month)
9. Implement in-memory caching during gameplay (Phase 3.1)
10. Implement frontend caching for FCC (Phase 3.2)

### Long-term (Future)
11. Separate historical data to new collection (Phase 4.1)
12. Remove career stats duplication (Phase 4.2)

## Success Metrics

- **FCC Initial Load**: < 200KB transferred (currently 1.6MB)
- **Per Quarter During Gameplay**: < 300KB transferred (currently 2MB+)
- **Page Load Time**: < 1 second (currently 3-5 seconds)
- **Turn-to-Turn Delay**: < 100ms (currently 500ms+)

## Notes

- **402KB document size is acceptable** - the issue is loading it too many times
- **Projections are the quick win** - can reduce data transfer by 80-95% immediately
- **Caching will eliminate redundant loads** - but projections are still needed for first load
- **Document structure optimization is long-term** - but projections solve immediate problem

---

## Phase 5: `/franchise/leaders` Endpoint Optimization (Critical)

**Status:** 🔴 **IDENTIFIED** - Performance bottleneck discovered (January 2025)

### Problem

The `/franchise/leaders` endpoint is taking **9.62 seconds** to complete, making it the slowest API call during FCC load.

**Root Cause:**

Line 1319 in `BackEnd/api/franchise_routes.py`:
```python
doc = db.franchises.find_one({"_id": fid}, {"players": 1}) or {}
```

This loads the **entire `players` object** (300KB+ with full season stats) **just to count players**, even though we're using the aggregation pipeline. This happens **6 times** (once per category: PTS, AST, TPM, REB, BLK, STL), wasting ~9 seconds total.

### The Issue

1. **Line 1319**: Loads entire `players` object to count (~1.5s per category × 6 = ~9s)
2. **Line 1330**: Checks `if len(players) <= 50` (96 > 50, so uses aggregation)
3. **Line 1387**: Aggregation pipeline runs (also reads from DB, but efficiently)

**The problem:** We're loading the `players` object 6 times just to count, even though we're using aggregation. The initial `find_one` is completely unnecessary when using aggregation.

### Solution

**Skip the initial `find_one` and go straight to aggregation.**

For franchise mode, we know there are always 96 players (12 per team × 8 teams), so we don't need to count first. The aggregation pipeline will efficiently:
- Read only needed fields (meta + stat value)
- Sort internally (MongoDB C++ vs Python)
- Limit results before returning to Python

**Expected Improvement:**
- Before: ~9.6s (loading full players object 6 times)
- After: ~0.6s (6 categories × 0.1s each using aggregation)
- **94% reduction in leaders endpoint time**

### Implementation

Remove the initial `find_one` and go straight to aggregation for franchise mode:

```python
# ❌ REMOVE: This wasteful load
doc = db.franchises.find_one({"_id": fid}, {"players": 1}) or {}
players = doc.get("players", {}) or {}
players_count = len(players)
if len(players) <= 50:  # Skip this check for franchise mode
    # ... in-memory sort ...

# ✅ REPLACE WITH: Go straight to aggregation for franchise mode
# (Or use MongoDB's $size operator to count efficiently if needed)
```

**Alternative:** If we need the count, use MongoDB's `$size` operator in a projection instead of loading the entire object.

---

## Phase 6: Game Simulation Optimization

**Status:** 🟡 **INVESTIGATION** - Potential optimizations identified (January 2025)

### Overview

Game simulation performance could be improved without compromising features. Several optimization opportunities have been identified:

### Optimization Opportunities

#### 6.1 Skeleton Animation Caching (High Priority)

**Location:** `BackEnd/engine/phase_resolution.py` - `get_hco_skeleton()`, `get_fcp_skeleton()`, `get_hct_skeleton()`

**Current Behavior:**
- Skeleton animations are loaded from database/collections every time they're needed
- Same skeletons may be loaded multiple times per game (HCO, FCP, HCT plays)

**Potential Impact:**
- Cache skeleton animations in memory during game session
- Pre-load common skeletons (HCO base_loop variants) at game start
- **Expected Improvement:** Reduce skeleton lookup time from ~10-50ms to ~0.1ms (in-memory)

**Implementation:**
- Add `skeleton_cache` dict to `GameManager` or `TurnManager`
- Cache skeletons by key: `(playcall_type, result_type, team_id)`
- Clear cache when game completes

**✅ Compatibility with Stopper System:**
- **Yes, caching works with stopper system!**
- The stopper system uses `copy.deepcopy(skeleton)` before modification (line 2613 in `phase_resolution.py`)
- This ensures the cached skeleton remains intact when stopper truncates animations
- Deep copy happens **after** retrieval from cache, so cache is never mutated
- **Conclusion:** Skeleton caching is safe and compatible with stopper system

#### 6.2 Reduce Game State Saves (Medium Priority)

**Location:** `BackEnd/api/api.py` - `simulate_turn_endpoint()` line 2280

**Current Behavior:**
- Game state is saved to database **every 10 turns**
- For a full game (~320 turns), this means ~32 database writes
- Each write includes full game state (~50-100KB)

**Potential Impact:**
- Reduce save frequency to **every 25 turns** (or only on quarter boundaries)
- Use lightweight saves (exclude animations) for intermediate saves
- Full saves only on quarter breaks or game completion
- **Expected Improvement:** Reduce database writes by 60% (32 → 13 writes per game)

**Risks:**
- Slightly higher risk of data loss if game crashes mid-quarter
- **Mitigation:** Current 10-turn saves are already sufficient for crash recovery

#### 6.3 Pre-load Team Plays at Game Start (Medium Priority)

**Location:** `BackEnd/api/api.py` - `simulate_quarter_endpoint()` lines 1075-1089

**Current Behavior:**
- Team plays are loaded from database when game is restored from DB
- Plays may be loaded multiple times during game initialization

**Potential Impact:**
- Load team plays once at game start and cache in `GameManager`
- Reuse cached plays throughout game session
- **Expected Improvement:** Eliminate redundant play loads during game

#### 6.4 Optimize Player Lineup Building (Low Priority)

**Location:** `BackEnd/utils/db_utils.py` - `build_lineup_from_mongo()`

**Current Behavior:**
- Lineups are built by querying `players_collection` for each player
- Multiple database queries per lineup (10 queries for 5-player lineup × 2 teams)

**Potential Impact:**
- Batch load players using `$in` operator (single query for all players)
- Cache player attributes during game session
- **Expected Improvement:** Reduce lineup building from ~100ms to ~20ms

**⚠️ Compatibility with Energy Decay System:**
- **Cannot cache malleable attributes** (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT)
- Energy decay triggers `_rescale_attributes()` which modifies all malleable attributes based on NG
- **Solution Options:**
  1. **Cache base/static attributes only** (name, position, etc.) but NOT malleable attributes
  2. **Cache Player object reference** (object updates in real-time) but avoid deep copying attributes
  3. **Cache `anchor_*` values** but recalculate from NG each time (defeats purpose of caching)
- **Recommendation:** Option 2 - Cache Player object references in `GameManager` during game session
  - Player objects already exist in memory during gameplay
  - Energy decay updates the same object, so no stale data issue
  - Batch load players at game start, store in `GameManager.player_cache`
  - Reuse cached Player objects when building lineups

**Risks:**
- Requires refactoring `build_lineup_from_mongo()` function
- Must ensure Player objects are not deep copied (maintain references)
- Energy decay will update cached objects in real-time (this is desired behavior)

#### 6.5 In-Memory Game State During Turn-by-Turn Mode (Low Priority)

**Location:** `BackEnd/api/api.py` - `simulate_turn_endpoint()`

**Current Behavior:**
- Game state is loaded from `ongoing_games` dict (already in-memory)
- But may reload from DB if game is not in memory

**Potential Impact:**
- Ensure game state stays in memory for entire game session
- Only load from DB if game is truly missing from memory
- **Expected Improvement:** Eliminate redundant DB loads during gameplay

### Implementation Priority

1. **Skeleton Animation Caching** - High impact, low risk, easy implementation
2. **Reduce Game State Saves** - Medium impact, low risk, easy implementation  
3. **Pre-load Team Plays** - Medium impact, low risk, moderate implementation
4. **Optimize Player Lineup Building** - Low impact, medium risk, moderate implementation
5. **In-Memory Game State** - Low impact, low risk, easy implementation (may already be optimized)

### Success Metrics

- **Simulation Speed**: Reduce per-turn processing time by 10-20%
- **Database Load**: Reduce database writes during gameplay by 50-60%
- **Memory Usage**: Increase in-memory caching (acceptable trade-off for speed)
- **Feature Impact**: **Zero** - all optimizations are transparent to gameplay

#### 6.6 Simulation-Specific Optimizations (High Priority)

**Location:** `BackEnd/api/api.py` - `simulate_quarter_endpoint()` and `simulate_turn_endpoint()`

**Current Behavior:**
- All features are executed regardless of `full_sim` flag
- Playcall center, timeout delays, animation generation all run even when simming

**Potential Impact:**
- Skip user-specific UI features when `full_sim=True`:
  - **Playcall Center**: Skip user override checks (lines 311-332 in `turn_manager.py`)
  - **Timeout Button UI**: Skip timeout button enable/disable logic (frontend only, already skipped in simulation)
  - **BIP/SIP Delays**: Skip 2-second pause for timeout button (frontend only, already skipped in simulation)
  - **Animation Generation**: Already skipped with `exclude_animations=True` for DB saves
- **Keep timeout logic** (affects game state):
  - ✅ **Computer Timeout Checks**: Keep `should_computer_call_timeout()` - computer teams need timeouts in simmed games
  - ✅ **User Timeout Logic**: Keep timeout logic for simmed user teams - they should be able to call timeouts too
  - ✅ **Timeout Turn Creation**: Keep timeout turn creation - needed for game state consistency
- **Expected Improvement:** Reduce per-turn processing time by 3-5% during simulation (smaller impact since timeout logic is kept)

**Implementation:**
- Add `if not full_sim:` guards around user-specific UI features only
- Skip playcall center override checks when `full_sim=True`
- **Keep all timeout logic** (computer checks, user timeout calls, timeout turn creation)
- Skip only button-related UI delays and enable/disable logic (frontend only)
- Animation generation already handled via `exclude_animations` parameter

**Risks:**
- Must ensure `full_sim` flag is correctly passed through all simulation paths
- Timeout logic must remain intact for game state consistency
- **Mitigation:** Test thoroughly with both `full_sim=True` and `full_sim=False` paths

**Features to Skip for Full Simulation:**
1. ✅ **Playcall Center Overrides** - User-specific UI, not needed for simulation
2. ✅ **Timeout Button UI Delays** - User-specific UI (2-second pause), already skipped in simulation
3. ✅ **Animation Generation** - Already skipped with `exclude_animations=True`
4. ✅ **Skeleton Loading** - Already skipped with `exclude_animations=True`

**Features to KEEP for Full Simulation:**
1. ✅ **Computer Timeout Checks** - Computer teams need timeouts in simmed games
2. ✅ **User Timeout Logic** - Simmed user teams should be able to call timeouts
3. ✅ **Timeout Turn Creation** - Needed for game state consistency
4. ✅ **Timeout State Management** - Needed for game state persistence

### Notes

- All optimizations are **performance-only** - no gameplay logic changes
- Caching strategies can be easily disabled if issues arise
- Most optimizations leverage existing patterns (already using `ongoing_games` dict)
- **Simulation-specific optimizations** skip user-facing features that don't affect game outcomes
