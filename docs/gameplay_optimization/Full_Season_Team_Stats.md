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
