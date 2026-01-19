# Master TODO - Active Tasks & Future Improvements

**Last Updated:** January 2026  
**Purpose:** Consolidated list of active tasks, bugs, and future improvements

---

## 🔴 Active Bugs & Critical Issues

### 1. Active Bugs from bugs.md
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

### 2. Team Structure Unification Performance Issues
**Status:** 🔍 IDENTIFIED - Needs Fix  
**Priority:** 🔴 HIGH - Affecting gameplay transitions  
**Document:** `team_structure_unification_performance_issues.md`

**Problem:** After unifying team structure, slow transitions during gameplay. Legacy code patterns causing performance issues.

**Priorities:**
1. Cache Team Objects in `gameScene.js`
2. Audit and Fix Animation Files
3. Add Performance Logging
4. Remove Redundant Fallbacks

**Progress:** 0% (0/4 priorities completed)

---

### 3. TBTT System SS&S Migration
**Status:** ⚠️ PARTIALLY IMPLEMENTED (~88-94% SS&S)  
**Priority:** 🟡 MEDIUM  
**Document:** `TBTT_SYSTEM_SSS_MIGRATION_PLAN.md`

**Problem:** Fragmented possession flip logic across backend and frontend, causing bugs and maintenance issues.

**Current State:** ~88-94% SS&S with 4 systematic fixes implemented. Target: ~90% SS&S with unified function approach.

**Action:** Complete remaining SS&S improvements.

---

### 4. Timeout System SS&S Improvements
**Status:** ⚠️ PARTIALLY IMPLEMENTED  
**Priority:** 🟡 MEDIUM  
**Document:** `timeout_system_sss_improvements.md`

**Problem:** Scattered inference logic to determine game state (new game vs. resuming vs. timeout resume).

**Current State:** Some improvements implemented, but patchy inference logic still exists.

**Action:** Complete unified game state detection and navigation parameter building.

---

### 5. Team ID Resolution System
**Status:** ⚠️ PARTIALLY IMPLEMENTED - Bug Fixed, Unified Helper Not Implemented  
**Priority:** 🟡 MEDIUM  
**Document:** `team_id_resolution_system.md`

**Problem:** Bug is fixed, but code duplication remains. Unified helper not implemented.

**Current Solution:** Uses `get_user_team_from_franchise()` and `get_user_team_from_tournament()` (SS&S pattern), but unified helper would reduce duplication.

**Action:** Implement unified helper to reduce code duplication.

---

### 6. Final Testing Checklist
**Status:** ⏳ PENDING  
**Document:** `Final_Testing_Checklist.md`

**Purpose:** Manual end-to-end testing to verify full functionality before alpha launch.

**Action:** Complete testing checklist or archive if testing is complete.

---

## 📋 Future Improvements & Enhancements

### 1. Tournament & Franchise Unification
**Status:** 📋 PLANNING  
**Priority:** 🟡 MEDIUM  
**Document:** `Tournament_Franchise_Unification_Plan.md`

**Goal:** Unify Tournament and Franchise modes to use identical code patterns, with only mode variable differences and intentional feature differences.

**Key Areas:**
- Field name standardization (`franchise_teams` → `teams`)
- Frontend roster/stats rendering (extract shared functions)
- API pattern consistency

**Note:** Some unification already completed (team stats refactoring). Continue incrementally.

---

### 2. Team Objects Data Architecture
**Status:** 📋 PLANNING / DISCUSSION  
**Priority:** 🟡 MEDIUM  
**Document:** `team_objects_data.md`

**Problem:** Playbooks page from lineup screen during gameplay - offensive plays not displaying in Franchise Mode.

**Architectural Decision:** Hybrid approach - copy `plays` and `playbook_settings` from franchise document to game document at game start, then use game document as source of truth during gameplay.

**Action:** Review and implement if needed.

---

### 3. Database Query Architecture Overhaul
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

### 4. Data Persistence Caching Strategy
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
2. ✅ **Task 1.1: Go-Live Foundations Verification** - Staging and production environments verified (96% complete)
3. ✅ **Team Stats SS&S Refactoring** - Shared code extracted, ~290 lines of duplication removed
4. ✅ **Playbook Percentage Persistence** - Bug fixes implemented
5. ✅ **Staging Setup** - Staging environment operational
6. ✅ **Railway 502 Solution** - 502 errors resolved
7. ✅ **Tournament Stats Display** - Bug fixes implemented
8. ✅ **Sim Quarter Feature** - Feature implemented and working
9. ✅ **Performance Analysis Docs** - Performance issues resolved (archived analysis docs)
10. ✅ **Franchise Mode Team Stats Isolation** - Franchise stats now isolated from universal teams collection

---

## 📚 Reference Documents

### Active Documentation
- `bugs.md` - Current active bugs and fixed bugs
- `Pre_Launch_Checklist.md` - Pre-launch requirements
- `0_alpha_launch_plan.md` - Alpha launch planning

### Reference / Analysis Documents
These documents provide analysis, comparisons, or strategic guidance but are not active tasks. They are located in `docs/Reference/`:

- `timeout_v_quarterbreak.md` - Comparison of timeout vs quarter break data persistence
- `Tournament_vs_Franchise_Player_Stats_Comparison.md` - Comparison of player stats flow
- `why_performance_issues_surface_in_production.md` - Analysis of production performance issues
- `World_Class_Architecture_Patterns.md` - Strategic reference for architecture decisions

**Note:** These are kept for reference but not tracked as active tasks.

### Archived Documentation
- See `docs/To Do/Archive/` for completed task documentation
- See `docs/Archive/` for historical system documentation

---

## Notes

- **SS&S Principle:** All improvements should follow Simple, Stable, and Scalable principles
- **Priority Levels:** 🔴 HIGH | 🟡 MEDIUM | 🟢 LOW
- **Status Indicators:** ⏳ IN PROGRESS | ✅ COMPLETE | 🔍 INVESTIGATING | 📋 PLANNED

