# Timeout Navigation System - 75% → 95% SS&S Migration Plan

> **Status:** Planning  
> **Current:** ~75% SS&S  
> **Target:** ~95% SS&S  
> **Gap:** 4 manual parameter builds in `gameScene.js`

## Overview

The Timeout Navigation System has a strong SS&S foundation with the unified `TimeoutNavigationHelper`, but **4 places in `gameScene.js` still build URL parameters manually** instead of using the helper. This plan migrates those remaining manual builds to use the helper, achieving ~95% SS&S.

---

## Current State Analysis

### ✅ What's Working (75% SS&S)

**Unified Helper Usage:**
- ✅ `set-lineup.js`: "Play Now" button (line 838)
- ✅ `set-lineup.js`: "Game Plan" button (line 876)
- ✅ `game-plan.js`: `navigateToCourt()` (line 357)
- ✅ `game-plan.js`: `navigateBack()` (line 414)
- ✅ `timeoutButtonManager.js`: `showTimeoutPopup()` (line 300)
- ✅ `foulOutPopup.js`: Foul out navigation (line 42)
- ✅ `gameScene.js`: Quarter end navigation (line 1528) - **ONE place using helper**

### ⚠️ What's Not Working (25% Manual Builds)

**Manual Parameter Building in `gameScene.js`:**

1. **Lines 1451-1454:** Locker room popup (quarter complete)
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextQ);
   params.set('period', `Q${nextQ}`);
   ```

2. **Lines 1904-1907:** Overtime start (OT1)
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextQ);
   params.set('period', 'OT1');
   ```

3. **Lines 1936-1939:** Overtime continuation (OT2+)
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextOT);
   params.set('period', `OT${nextOTNumber}`);
   ```

4. **Lines 2029-2031:** Regular quarter complete (fallback path)
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextQ);
   params.set('period', `Q${nextQ}`);
   ```

**Impact:**
- Inconsistent parameter building
- Risk of missing parameters (mode, tournament_id, franchise_id, lineup, etc.)
- Not leveraging helper's SS&S logic
- Potential for bugs if helper logic changes

---

## Migration Plan

### Phase 1: Identify All Manual Builds

**Action Items:**
1. ✅ **Complete** - Identified 4 manual builds in `gameScene.js`
2. Verify no other manual builds exist in codebase
3. Document context for each manual build

**Files to Check:**
- `FrontEnd/static/js/phaser/gameScene.js` (lines 1451-1454, 1904-1907, 1936-1939, 2029-2031)
- Any other files that build URL parameters manually

---

### Phase 2: Migrate Manual Builds to Helper

**Goal:** Replace all 4 manual parameter builds with `TimeoutNavigationHelper.buildGameNavigationParams()`

#### Step 2.1: Migrate Locker Room Popup (Lines 1451-1454)

**Current Code:**
```javascript
const nextQ = this.quarter + 1;
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', `Q${nextQ}`);
```

**Target Code:**
```javascript
const nextQ = this.quarter + 1;
const urlParams = new URLSearchParams(window.location.search);

// ✅ SS&S: Use unified Timeout Navigation Helper
const helper = window.TimeoutNavigationHelper;
if (!helper) {
  console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
  return;
}

const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: nextQ,
  gameId: this.gameId,
  resumeFromTimeout: false, // Quarter break, not timeout
  lineup: {}, // Lineup will be set on lineup screen
  myTeamSide: urlParams.get('my_team')
});
```

**Context:**
- Quarter complete (Q1→Q2, Q2→Q3, Q3→Q4)
- Shows locker room popup
- Navigates to lineup screen

**Action Items:**
1. Replace manual build with helper call
2. Ensure all parameters are preserved (mode, tournament_id, franchise_id, etc.)
3. Test quarter transitions (Q1→Q2, Q2→Q3, Q3→Q4)

#### Step 2.2: Migrate Overtime Start (Lines 1904-1907)

**Current Code:**
```javascript
const nextQ = nextQuarterNumber; // Should be 5 (first OT)
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', 'OT1');
```

**Target Code:**
```javascript
const nextQ = nextQuarterNumber; // Should be 5 (first OT)
const urlParams = new URLSearchParams(window.location.search);

// ✅ SS&S: Use unified Timeout Navigation Helper
const helper = window.TimeoutNavigationHelper;
if (!helper) {
  console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
  return;
}

const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: nextQ,
  gameId: this.gameId,
  resumeFromTimeout: false, // Overtime start, not timeout
  lineup: {}, // Lineup will be set on lineup screen
  myTeamSide: urlParams.get('my_team')
});
```

**Context:**
- Q4 tied → OT1
- Shows locker room popup
- Navigates to lineup screen

**Action Items:**
1. Replace manual build with helper call
2. Ensure helper correctly calculates `period: 'OT1'` for quarter 5
3. Test Q4 tied → OT1 transition

#### Step 2.3: Migrate Overtime Continuation (Lines 1936-1939)

**Current Code:**
```javascript
const currentOTNumber = quarterThatJustFinished - 4;
const nextOTNumber = currentOTNumber + 1;
const nextOT = nextQuarterNumber; // Should be the next OT quarter number
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextOT);
params.set('period', `OT${nextOTNumber}`);
```

**Target Code:**
```javascript
const nextOT = nextQuarterNumber; // Should be the next OT quarter number
const urlParams = new URLSearchParams(window.location.search);

// ✅ SS&S: Use unified Timeout Navigation Helper
const helper = window.TimeoutNavigationHelper;
if (!helper) {
  console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
  return;
}

const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: nextOT,
  gameId: this.gameId,
  resumeFromTimeout: false, // Overtime continuation, not timeout
  lineup: {}, // Lineup will be set on lineup screen
  myTeamSide: urlParams.get('my_team')
});
```

**Context:**
- OT1 tied → OT2, OT2 tied → OT3, etc.
- Shows locker room popup
- Navigates to lineup screen
- Helper automatically calculates `period: 'OT2'`, `period: 'OT3'`, etc.

**Action Items:**
1. Replace manual build with helper call
2. Remove manual OT number calculation (helper handles it)
3. Test OT1 tied → OT2 transition

#### Step 2.4: Migrate Regular Quarter Complete (Lines 2029-2031)

**Current Code:**
```javascript
const nextQ = this.quarter + 1;
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', `Q${nextQ}`);
```

**Target Code:**
```javascript
const nextQ = this.quarter + 1;
const urlParams = new URLSearchParams(window.location.search);

// ✅ SS&S: Use unified Timeout Navigation Helper
const helper = window.TimeoutNavigationHelper;
if (!helper) {
  console.error('❌ [GAMESCENE] TimeoutNavigationHelper not loaded!');
  return;
}

const params = helper.buildGameNavigationParams({
  sourceParams: urlParams,
  targetQuarter: nextQ,
  gameId: this.gameId,
  resumeFromTimeout: false, // Quarter break, not timeout
  lineup: {}, // Lineup will be set on lineup screen
  myTeamSide: urlParams.get('my_team')
});
```

**Context:**
- Fallback path for quarter complete
- Shows locker room popup
- Navigates to lineup screen

**Action Items:**
1. Replace manual build with helper call
2. Ensure this path is consistent with Step 2.1
3. Test all quarter transitions

---

### Phase 3: Validation & Testing

**Goal:** Ensure all migrations work correctly and no parameters are lost.

#### Step 3.1: Parameter Preservation Testing

**Test Scenarios:**
1. **Quarter Break (Q1→Q2):**
   - Verify `game_id` is preserved
   - Verify `mode` is preserved
   - Verify `tournament_id` / `franchise_id` is preserved (if applicable)
   - Verify `quarter` and `period` are set correctly
   - Verify `resume_from_timeout` is NOT set (quarter break)

2. **Quarter Break (Q2→Q3, Q3→Q4):**
   - Same as above
   - Verify all parameters preserved

3. **Overtime Start (Q4→OT1):**
   - Verify `game_id` is preserved
   - Verify `mode` is preserved
   - Verify `tournament_id` / `franchise_id` is preserved (if applicable)
   - Verify `quarter: 5` and `period: 'OT1'` are set correctly
   - Verify `resume_from_timeout` is NOT set (overtime start)

4. **Overtime Continuation (OT1→OT2, OT2→OT3):**
   - Same as above
   - Verify `period` is calculated correctly (`OT2`, `OT3`, etc.)

**Action Items:**
1. Test each scenario manually
2. Verify URL parameters in browser dev tools
3. Verify backend receives correct parameters
4. Document any issues found

#### Step 3.2: Integration Testing

**Test Scenarios:**
1. **Full Game (Q1→Q2→Q3→Q4):**
   - Play full game, verify all quarter transitions work
   - Verify no parameters lost between quarters

2. **Overtime Game (Q1→Q2→Q3→Q4→OT1):**
   - Play game to OT, verify OT1 transition works
   - Verify all parameters preserved

3. **Multi-OT Game (Q1→Q2→Q3→Q4→OT1→OT2):**
   - Play game to OT2, verify OT2 transition works
   - Verify all parameters preserved

4. **Tournament Mode:**
   - Test quarter transitions in tournament mode
   - Verify `tournament_id` is preserved

5. **Franchise Mode:**
   - Test quarter transitions in franchise mode
   - Verify `franchise_id` and `week` are preserved

**Action Items:**
1. Test each scenario manually
2. Verify no regressions in existing functionality
3. Document any issues found

#### Step 3.3: Code Review

**Review Checklist:**
- ✅ All 4 manual builds replaced with helper calls
- ✅ Helper error handling added (check for `window.TimeoutNavigationHelper`)
- ✅ All parameters preserved (mode, tournament_id, franchise_id, etc.)
- ✅ Consistent pattern across all 4 migrations
- ✅ No duplicate code

**Action Items:**
1. Code review of all 4 migrations
2. Verify consistency with existing helper usage
3. Verify error handling is appropriate

---

### Phase 4: Documentation Update

**Goal:** Update documentation to reflect 95% SS&S status.

#### Step 4.1: Update `master_game_doc.md`

**Action Items:**
1. Update Timeout Navigation System section
2. Document that ALL navigation uses unified helper
3. Remove references to manual parameter building
4. Update SS&S percentage to 95%

#### Step 4.2: Update `NAVIGATION_HELPER_DESIGN.md`

**Action Items:**
1. Document all navigation entry points using helper
2. Document quarter transition scenarios
3. Document overtime transition scenarios

---

## Success Criteria

### Code Quality
- ✅ All 4 manual parameter builds replaced with helper calls
- ✅ Consistent pattern across all navigation entry points
- ✅ No duplicate parameter building logic
- ✅ Helper error handling in all places

### Functionality
- ✅ All quarter transitions work correctly (Q1→Q2, Q2→Q3, Q3→Q4)
- ✅ Overtime transitions work correctly (Q4→OT1, OT1→OT2, etc.)
- ✅ All parameters preserved (mode, tournament_id, franchise_id, etc.)
- ✅ No regressions in existing functionality

### SS&S Metrics
- ✅ **Before:** ~75% SS&S (4 manual builds)
- ✅ **After:** ~95% SS&S (all navigation uses helper)
- ✅ **Remaining 5%:** Edge cases, error handling, future enhancements

---

## Migration Timeline

### Day 1: Migrate Locker Room Popup
- **Morning:** Migrate lines 1451-1454
- **Afternoon:** Test Q1→Q2, Q2→Q3, Q3→Q4 transitions

### Day 2: Migrate Overtime Start
- **Morning:** Migrate lines 1904-1907
- **Afternoon:** Test Q4→OT1 transition

### Day 3: Migrate Overtime Continuation
- **Morning:** Migrate lines 1936-1939
- **Afternoon:** Test OT1→OT2 transition

### Day 4: Migrate Regular Quarter Complete
- **Morning:** Migrate lines 2029-2031
- **Afternoon:** Test all quarter transitions

### Day 5: Validation & Testing
- **Morning:** Integration testing (full game, OT game, tournament mode, franchise mode)
- **Afternoon:** Code review, bug fixes, documentation updates

---

## Risk Mitigation

### Risk 1: Missing Parameters
**Mitigation:**
- Helper automatically preserves all parameters from `sourceParams`
- Test all scenarios to verify parameter preservation
- Add logging to verify parameters are correct

### Risk 2: Breaking Existing Functionality
**Mitigation:**
- Gradual migration (one build at a time)
- Test each migration before moving to next
- Rollback plan if issues arise

### Risk 3: Helper Not Loaded
**Mitigation:**
- Add error handling (check for `window.TimeoutNavigationHelper`)
- Verify helper is loaded in `court.html`
- Add fallback if helper not available

---

## Expected Outcome

### Before Migration (75% SS&S)
- ❌ 4 manual parameter builds in `gameScene.js`
- ❌ Risk of missing parameters
- ❌ Inconsistent parameter building
- ❌ Not leveraging helper's SS&S logic

### After Migration (95% SS&S)
- ✅ All navigation uses unified helper
- ✅ All parameters automatically preserved
- ✅ Consistent parameter building pattern
- ✅ Leveraging helper's SS&S logic
- ✅ Easy to maintain and extend

---

## Next Steps

1. **Review this plan** with team
2. **Approve migration timeline**
3. **Begin Day 1: Migrate Locker Room Popup**
4. **Track progress** against success criteria
5. **Document lessons learned** for future SS&S improvements

---

## Notes

### Why 95% and Not 100%?

The remaining 5% accounts for:
- Edge cases and error handling
- Future enhancements (new navigation scenarios)
- Helper function itself (not counted as "using" the system)
- Potential future optimizations

### Future Enhancements (Beyond 95%)

To reach 100% SS&S:
- Add helper support for new navigation scenarios
- Add helper support for special cases (if any)
- Optimize helper performance
- Add helper unit tests

