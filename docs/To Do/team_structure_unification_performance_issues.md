# Team Structure Unification - Performance Issues

**Date:** January 2026  
**Status:** 🔍 Identified - Needs Fix  
**Priority:** High (affecting gameplay transitions)  
**Last Updated:** January 2026

## Completion Status

**Overall Progress:** 0% (0/4 priorities completed)

- [ ] **Priority 1:** Cache Team Objects in `gameScene.js` - ⏳ Not Started
- [ ] **Priority 2:** Audit and Fix Animation Files - ⏳ Not Started  
- [ ] **Priority 3:** Add Performance Logging - ⏳ Not Started (Approach documented ✅)
- [ ] **Priority 4:** Remove Redundant Fallbacks - ⏳ Not Started

**Testing Status:** Not Started (0/7 tests completed)

## Problem Statement

After unifying the team structure (moving from `home_team`/`away_team` objects to `teams[home_team_id]`/`teams[away_team_id]`), we're experiencing slow transitions during gameplay. The unification was architecturally correct, but legacy code patterns are causing performance issues.

## Root Cause

The unified structure changed how team data is accessed:
- **Old:** `simData.home_team.name` (direct access)
- **New:** `simData.teams[simData.home_team_id].name` (nested access)

Many code paths still use old patterns or have complex fallback chains that execute repeatedly during gameplay, causing performance degradation.

## Issues Identified

### 1. ⚠️ **Critical: `applyTeamStats` Called on Every Turn**

**Location:** `FrontEnd/static/js/phaser/gameScene.js` (lines 1030-1088, called at line 1215)

**Problem:**
- Called during turn animations (potentially every frame)
- Performs 4+ conditional checks and property access chains on EVERY call:
  ```javascript
  if (!localHomeTeamObj && simData.home_team_id && simData.teams) {
    localHomeTeamObj = simData.teams[simData.home_team_id];
  }
  if (!localHomeTeamObj) {
    localHomeTeamObj = typeof simData.home_team === 'object' ? simData.home_team : null;
  }
  // ... repeats for away team
  ```
- Team objects should be resolved ONCE at initialization, not on every turn

**Impact:** High - This is likely the primary cause of slow transitions

### 2. **158 Legacy Access Patterns Found**

**Location:** Multiple files across `FrontEnd/static/js/phaser/`

**Problem:**
- Many files still access `simData.home_team.name` or `simData.away_team.name`
- Each access may:
  - Return `undefined` (causing errors/retries)
  - Trigger fallback logic chains
  - Cause UI updates with missing data

**Files with potential issues:**
- `animation/fastBreak.js` (10 matches)
- `animation/ShotAnimationSystem.js` (6 matches)
- `animation/FreeThrowAnimationSystem.js` (6 matches)
- `animation/turnAnimation.js` (9 matches)
- `animation/animateGameTurns.js` (9 matches)
- `utils/announcements.js` (6 matches)
- And 13 more files...

**Impact:** Medium - Accumulated overhead from repeated property lookups

### 3. **Animation Loop Overhead**

**Problem:**
- Animation files access team data repeatedly during animation frames
- If using old patterns, fallback logic runs on every frame
- No caching of resolved team objects

**Impact:** Medium - Affects animation smoothness

## Fix Plan (Prioritized)

### ⏳ **Priority 1: Cache Team Objects in `gameScene.js`** - Status: Not Started

**Goal:** Resolve team objects ONCE at initialization, reuse in `applyTeamStats`  
**Completion:** [ ] Not Started | [ ] In Progress | [ ] Completed | [ ] Tested

**Changes:**
1. In `create()` method, after `simData` is loaded:
   ```javascript
   // Resolve team objects ONCE
   const homeTeamId = simData.home_team_id;
   const awayTeamId = simData.away_team_id;
   const teamsObj = simData.teams || {};
   this.homeTeamObj = (homeTeamId && teamsObj[homeTeamId]) || 
                      (typeof simData.home_team === 'object' ? simData.home_team : null);
   this.awayTeamObj = (awayTeamId && teamsObj[awayTeamId]) || 
                      (typeof simData.away_team === 'object' ? simData.away_team : null);
   ```

2. Simplify `applyTeamStats` to use cached objects:
   ```javascript
   const applyTeamStats = (turn = {}) => {
     // Use cached team objects (no fallback logic needed)
     const homeAttrs = this.homeTeamObj?.attributes || {};
     const awayAttrs = this.awayTeamObj?.attributes || {};
     // ... rest of function
   };
   ```

**Expected Impact:** Eliminates 4+ conditional checks per turn → significant performance improvement

### ⏳ **Priority 2: Audit and Fix Animation Files** - Status: Not Started

**Goal:** Update animation files to use unified structure (or cached team objects)  
**Completion:** [ ] Not Started | [ ] In Progress | [ ] Completed | [ ] Tested

**Approach:**
1. Search for `simData.home_team` and `simData.away_team` patterns in animation files
2. Update to use `simData.teams[simData.home_team_id]` or pass cached team objects
3. Focus on files called during animation loops:
   - `animation/fastBreak.js`
   - `animation/ShotAnimationSystem.js`
   - `animation/FreeThrowAnimationSystem.js`
   - `animation/turnAnimation.js`

**Expected Impact:** Reduces property lookup overhead during animations

### ⏳ **Priority 3: Add Performance Logging** - Status: Not Started (Approach Documented ✅)

**Goal:** Measure actual impact of fixes and verify caching strategy works  
**Completion:** [ ] Not Started | [ ] In Progress | [ ] Completed | [ ] Tested  
**Note:** Implementation approach and code examples are fully documented below.

**Approach:** Add debug logging using Performance API to measure execution times

**Implementation Options:**

#### Option 1: Simple Timing (Recommended for initial testing)
```javascript
const applyTeamStats = (turn = {}) => {
  const startTime = performance.now(); // Start timer
  
  // ... existing code ...
  
  const endTime = performance.now();
  const duration = endTime - startTime;
  
  if (duration > 1) { // Only log if > 1ms (threshold for concern)
    console.warn(`⚠️ [PERF] applyTeamStats took ${duration.toFixed(2)}ms`, {
      turn: turn.index,
      hasTeamStats: !!turn.team_stats,
      hasTeamTotals: !!turn.team_totals
    });
  }
};
```

#### Option 2: Call Counter + Average Timing (Better for analysis)
```javascript
// At module level
let applyTeamStatsCallCount = 0;
let applyTeamStatsTotalTime = 0;

const applyTeamStats = (turn = {}) => {
  const startTime = performance.now();
  applyTeamStatsCallCount++;
  
  // ... existing code ...
  
  const duration = performance.now() - startTime;
  applyTeamStatsTotalTime += duration;
  
  // Log average every 10 calls
  if (applyTeamStatsCallCount % 10 === 0) {
    const avgTime = applyTeamStatsTotalTime / applyTeamStatsCallCount;
    console.log(`📊 [PERF] applyTeamStats: ${applyTeamStatsCallCount} calls, avg ${avgTime.toFixed(2)}ms`);
  }
};
```

#### Option 3: Before/After Comparison (Best for validation)
```javascript
// Before caching fix - logs resolution overhead
const applyTeamStats = (turn = {}) => {
  const startTime = performance.now();
  
  // Log if resolution is happening (indicates no cache)
  if (!homeTeamObj) {
    console.log('⚠️ [PERF] applyTeamStats: Resolving team objects (no cache)', {
      turn: turn.index,
      resolutionTime: performance.now() - startTime
    });
  }
  
  // ... existing code ...
  
  const duration = performance.now() - startTime;
  if (duration > 1) {
    console.warn(`⚠️ [PERF] applyTeamStats took ${duration.toFixed(2)}ms`);
  }
};

// After caching fix - same logging will show improved times
// No "Resolving team objects" logs should appear
```

**Metrics to Track:**
1. **Execution time per call:** How long `applyTeamStats` takes (target: < 1ms after caching)
2. **Call frequency:** How many times called per turn/quarter
3. **Resolution overhead:** Time spent on fallback logic (before cache)
4. **Total impact:** Cumulative time across a quarter

**Where to Add:**
- In `gameScene.js` around `applyTeamStats` function (line 1030)
- Optionally at call site (line 1215) to measure total turn processing time
- Use flag: `const PERF_LOGGING = urlParams.has('perf') || DEBUG;` to enable only when needed

**What to Look For:**
- **Before caching:** Higher execution times (likely 2-10ms per call), logs showing "Resolving team objects" repeatedly
- **After caching:** Lower execution times (< 1ms per call), no resolution logs, noticeable reduction in total time

**Expected Impact:** Validates fixes and identifies any remaining bottlenecks. Provides quantitative proof that caching strategy works.

### ⏳ **Priority 4: Remove Redundant Fallbacks** - Status: Not Started

**Goal:** Clean up code after caching is in place  
**Completion:** [ ] Not Started | [ ] In Progress | [ ] Completed | [ ] Tested  
**Note:** This depends on Priority 1 completion.

**Approach:**
- After team objects are cached, simplify all access patterns
- Remove unnecessary fallback chains
- Update documentation

**Expected Impact:** Cleaner code, easier maintenance

## Testing Checklist

- [ ] Verify team data loads correctly on game start
- [ ] Verify team stats update correctly during gameplay
- [ ] Measure transition times before fix
- [ ] Measure transition times after Priority 1 fix
- [ ] Verify no regressions in timeout navigation
- [ ] Verify no regressions in box score display
- [ ] Test with both unified and legacy game documents (backward compatibility)

## Notes

- The unification was architecturally correct - this is about optimizing access patterns
- Backward compatibility is important - must support both old and new structures
- Focus on high-frequency code paths first (turn processing, animations)
- Low-frequency code paths (timeout navigation, finalize game) are less critical but should still be updated

## Related Files

- `FrontEnd/static/js/phaser/gameScene.js` - Primary fix location
- `FrontEnd/static/js/phaser/animation/*` - Secondary fix locations
- `docs/To Do/team_objects_data.md` - Original unification documentation

## Implementation Notes

**Date:** (Add date when starting implementation)

### Priority 1 Implementation
- [ ] Code changes made
- [ ] Code reviewed
- [ ] Tested locally
- [ ] Committed to git

**Notes:**

---

### Priority 2 Implementation
- [ ] Code audit completed
- [ ] Files updated
- [ ] Code reviewed
- [ ] Tested locally
- [ ] Committed to git

**Files Updated:**
- (List files as they're updated)

**Notes:**

---

### Priority 3 Implementation
- [ ] Performance logging added
- [ ] Baseline measurements taken
- [ ] Post-fix measurements taken
- [ ] Results documented
- [ ] Logging removed/commented out for production

**Measurement Results:**
- **Before fix:** (Add average execution time, call count, etc.)
- **After Priority 1 fix:** (Add average execution time, call count, etc.)
- **Improvement:** (Calculate percentage improvement)

**Notes:**

---

### Priority 4 Implementation
- [ ] Redundant fallbacks identified
- [ ] Code cleaned up
- [ ] Documentation updated
- [ ] Tested for regressions
- [ ] Committed to git

**Notes:**

---
