# Master TODO - Active Tasks & Future Improvements

**Last Updated:** January 2026  
**Purpose:** Consolidated list of active tasks, bugs, and future improvements

---

## 🔴 Active Bugs & Critical Issues

### 1. Franchise Mode Team Stats Isolation
**Status:** ⏳ FIX DRAFTED  
**Priority:** 🔴 HIGH - Data integrity issue  
**Document:** `bug_fix_franchise_team_stats_isolation.md`

**Problem:** Franchise mode team stats (W/L, PF/PA) are incorrectly reading from and writing to the universal `teams` collection, causing stats to be shared across different game modes and franchise instances.

**Solution:** 
- Remove writes to universal `teams` collection from franchise routes
- Calculate W/L and PF/PA from `franchise.results` instead
- Update `team_stats_aggregator.py` to support franchise results calculation

**Files to Modify:**
- `BackEnd/api/franchise_routes.py`
- `BackEnd/utils/team_stats_aggregator.py`
- `BackEnd/models/franchise_manager.py`

---

### 2. Active Bugs from bugs.md
**Document:** `bugs.md`

**Current Active Bugs:**
1. Playcall Override During Opening Tip Sequence
2. Defensive Foul on missed shot attempt not announcing via Announcement System
3. Scouting Report button does not appear in the TCC
4. Next column on Standings tab not populating on the Standings tab on FCC
5. Since going to production, Playcall Center overrides are not working
6. Since going to production, the computer is calling timeouts for the user team
7. Eliminate "Simulating Q5..."
8. Tournament Mode -- Non user game team and player stats are not populating on the Stats tab, and no team's player stats are populating on the team roster pages
10. User is still able to put fouled out players into the lineup on the Lineup Selection screen

**See:** `bugs.md` for detailed descriptions and fixes

---

## ⚠️ In Progress / Needs Verification

### 1. Frontend Performance Fix Plan
**Status:** ⏳ IN PROGRESS  
**Priority:** 🔴 CRITICAL - Blocking user experience  
**Document:** `frontend_performance_fix_plan.md`

**Problem:** Lineup screen takes 5-10 seconds to display after network request completes (294ms). Frontend JavaScript processing bottleneck.

**Key Bottlenecks Identified:**
- Nested loops in `loadRoster()` (O(n²) complexity)
- Inefficient DOM manipulation
- Large roster data processing

**Action:** Review current status and verify if fixes have been implemented.

---

### 2. Final Testing Checklist
**Status:** ⏳ PENDING  
**Document:** `Final_Testing_Checklist.md`

**Purpose:** Manual end-to-end testing to verify full functionality before alpha launch.

**Action:** Complete testing checklist or archive if testing is complete.

---

## 📋 Future Improvements & Enhancements

### 1. Database Query Architecture Overhaul
**Status:** 🔍 STRATEGIC PLANNING  
**Priority:** 🟡 MEDIUM - Scalability improvement  
**Document:** `Database_Query_Architecture_Overhaul.md` (archived)

**Goal:** Redesign data access layer to minimize database calls through strategic batching, caching, and data structure optimization.

**Key Issues:**
- Too many database calls per page load (15-20+ queries)
- N+1 query patterns
- Missing projections

**Note:** This is a strategic planning document. Consider implementing incrementally as performance issues arise.

---

### 2. Data Persistence Caching Strategy
**Status:** 📋 PROPOSED ENHANCEMENT  
**Priority:** 🟡 MEDIUM  
**Document:** `data_persistence_caching_strategy.md` (archived)

**Problem:** After removing localStorage caching, we've achieved data consistency but introduced performance trade-offs (page load delays, flash of empty state).

**Proposed Solutions:**
- Client-side cache with TTL
- Stale-while-revalidate pattern
- Selective caching strategy

**Note:** Consider implementing if performance issues persist.

---

### 3. Animation System Improvements
**Status:** ⚠️ PARTIALLY DONE  
**Document:** `Future_Improvements.md`

**Remaining Tasks:**
1. **Consolidate Text Scroll** - Move all text scroll appends to `AnimationRouter` for consistency
2. **Handler Documentation** - Add complete JSDoc comments to all handlers

**Files to Update:**
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`

---

## ✅ Completed Items (Archived)

The following items have been completed and moved to `docs/To Do/Archive/`:

1. ✅ **Phase 5: Production Deployment** - Production environment fully deployed
2. ✅ **Playbook Percentage Persistence** - Bug fixes implemented
3. ✅ **Staging Setup** - Staging environment operational
4. ✅ **Railway 502 Solution** - 502 errors resolved
5. ✅ **Tournament Stats Display** - Bug fixes implemented
6. ✅ **Sim Quarter Feature** - Feature implemented and working
7. ✅ **Performance Analysis Docs** - Performance issues resolved (archived analysis docs)

---

## 📚 Reference Documents

### Active Documentation
- `bugs.md` - Current active bugs and fixed bugs
- `Pre_Launch_Checklist.md` - Pre-launch requirements
- `0_alpha_launch_plan.md` - Alpha launch planning

### Archived Documentation
- See `docs/To Do/Archive/` for completed task documentation
- See `docs/Archive/` for historical system documentation

---

## Notes

- **SS&S Principle:** All improvements should follow Simple, Stable, and Scalable principles
- **Priority Levels:** 🔴 HIGH | 🟡 MEDIUM | 🟢 LOW
- **Status Indicators:** ⏳ IN PROGRESS | ✅ COMPLETE | 🔍 INVESTIGATING | 📋 PLANNED

