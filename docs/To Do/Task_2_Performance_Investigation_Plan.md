# Task 2: Performance Investigation Plan

**Date Created:** January 11, 2026  
**Status:** ⏳ IN PROGRESS  
**Priority:** 🔴 HIGH - Performance optimization (blocking user experience)  
**Related:** Task 2 from Go Live Plan

## Overview

The staging and production environments are experiencing significant slowness across all game modes. This plan outlines a systematic investigation to identify and fix performance bottlenecks.

## Current Performance Issues

### Reported Symptoms
- Lineup screen loading: **2-3 seconds** (should be <1s)
- Quarter simulations: **3-5 seconds** (should be <2s)
- Playbooks page loading: **2-4 seconds** (should be <1s)
- Game plan page loading: **1-2 seconds** (should be <0.5s)
- Saving settings: **1-2 seconds** (should be <0.5s)

### Affected Environments
- ✅ Staging (Railway + Netlify)
- ✅ Production (Railway + Netlify)

### Affected Game Modes
- Single Game mode (primary focus)
- Franchise mode
- Tournament mode

---

## Performance Fixes Already Implemented

### Phase 1 (Original) - COMPLETE
1. ✅ Fixed N+1 queries in Franchise/Tournament roster endpoints
2. ✅ Removed excessive logging from `gameplan_routes.py`
3. ✅ Fixed team lookup optimization in `/roster/{team_name}`

**Result:** No improvement for Single Game mode (fixes only affected Franchise/Tournament)

### Revised Phase 1 - COMPLETE
1. ✅ Added projections for Single Game mode in `/api/playbooks` and `ensure_team_objects_exist`
2. ✅ Removed excessive logging from `api.py` (290+ calls reduced)

**Expected Impact:** 70-90% improvement for Single Game mode endpoints

---

## Investigation Plan

### Step 1: Measure Current Performance (Baseline)
**Time:** 30 minutes

**Actions:**
1. **Measure endpoint response times** in staging/production:
   - `/api/playbooks` (Single Game mode)
   - `/api/gameplan` (Single Game mode)
   - `/api/simulate-quarter`
   - `/api/game/{game_id}`
   - `/roster/{team_name}`

2. **Measure frontend processing time:**
   - Use browser DevTools Performance tab
   - Identify frontend bottlenecks (see `bugs.md` - lineup screen has 5-10s frontend processing)

3. **Measure database query times:**
   - Check Railway logs for slow queries
   - Identify queries taking >100ms

**Deliverable:** Performance baseline metrics document

---

### Step 2: Identify Remaining Bottlenecks
**Time:** 1-2 hours

**Focus Areas:**

#### A. Database Query Patterns
- [ ] Check for remaining N+1 query patterns
- [ ] Verify database indexes exist (teams.name, players._id, etc.)
- [ ] Check for missing projections in other endpoints
- [ ] Identify sequential queries that could be parallelized

#### B. Network Latency
- [ ] Measure Railway → MongoDB Atlas latency
- [ ] Check if connection pooling is optimized
- [ ] Verify MongoDB Atlas region matches Railway region

#### C. Frontend Processing
- [ ] Profile lineup screen JavaScript execution (5-10s bottleneck per `bugs.md`)
- [ ] Check for synchronous blocking operations
- [ ] Identify DOM rendering bottlenecks
- [ ] Check for inefficient data processing loops

#### D. Backend Processing
- [ ] Profile `/api/simulate-quarter` execution
- [ ] Check for CPU-intensive operations
- [ ] Identify synchronous I/O operations
- [ ] Check for inefficient data transformations

---

### Step 3: Prioritize Fixes
**Time:** 30 minutes

**Criteria:**
1. **Impact:** How much will this improve user experience?
2. **Effort:** How long will this take to implement?
3. **Risk:** What's the risk of breaking something?

**Expected Priority Order:**
1. Frontend processing bottlenecks (lineup screen 5-10s)
2. Missing database indexes
3. Remaining N+1 queries
4. Connection pooling optimization
5. Parallel query execution

---

### Step 4: Implement Fixes
**Time:** 4-8 hours (depending on findings)

**Approach:**
- Fix highest-impact items first
- Test after each fix
- Measure improvement
- Document changes

---

### Step 5: Verify Improvements
**Time:** 30 minutes

**Actions:**
1. Re-measure all endpoints
2. Compare to baseline
3. Verify user experience is acceptable
4. Document final performance metrics

**Target Metrics:**
- Lineup screen: <1 second
- Quarter simulation: <2 seconds
- Playbooks page: <1 second
- Game plan page: <0.5 seconds
- Saving settings: <0.5 seconds

---

## Next Steps

1. **Immediate:** Wait for Revised Phase 1 fixes to deploy and measure improvement
2. **If still slow:** Proceed with Step 1 (Baseline Measurement)
3. **Then:** Execute investigation plan (Steps 2-5)

---

## Related Documents

- `docs/To Do/performance_fix_plan.md` - Original performance fix plan
- `docs/To Do/performance_fix_plan_revised.md` - Revised plan (Single Game mode focus)
- `docs/To Do/bugs.md` - Lineup screen frontend bottleneck documented
- `docs/gameplay_optimization/API_Call_Data_Optimization.md` - API optimization strategies

