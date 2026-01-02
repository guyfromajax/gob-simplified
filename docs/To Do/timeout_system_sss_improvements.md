# Timeout System SS&S Improvements

> **Status:** ⚠️ **Partially Implemented**  
> **Priority:** Medium  
> **Created:** January 2025  
> **Last Updated:** February 2025

## Overview

This document tracks SS&S improvements for the Timeout System across two layers:
1. **Backend**: Unified Game State Detection (determining game state explicitly)
2. **Frontend**: Unified Navigation Parameter Building (using helper consistently)

---

# Part 1: Backend - Unified Game State Detection

## Problem Statement

The current timeout system works but relies on **scattered inference logic** to determine game state (new game vs. resuming vs. timeout resume). This creates fragility and maintenance challenges.

### Current State: Patchy Inference Logic ⚠️ **STILL EXISTS**

**Frontend (`gameScene.js` lines 220-226):**
```javascript
const isNewGameStart = !this.gameId || 
                      (this.quarter === 1 && !urlGameId && !resumeFromTimeout);
```

**Backend (`api.py` lines 936-978):**
```python
# Multiple places check timeout state and set resume_from_timeout flag
# Uses inference logic: checking quarter, saved game state, timeout_next_play_type
```

**Backend (`api.py` line 1163):**
```python
is_new_game = (request.quarter == 1 and saved_quarter > 1) and not request.resume_from_timeout
```

**Status:** ⚠️ **NOT IMPLEMENTED** - System still uses scattered inference logic. The unified `GameState` enum and `determine_game_state()` function do not exist.

### Issues with Current Approach

1. **No Single Source of Truth**: Three different places infer "is this a new game?" from different signals
2. **Fragile**: If assumptions change, we have to update multiple places
3. **Hard to Debug**: When something breaks, it's unclear which inference logic is wrong
4. **Inconsistent**: Different code paths use different heuristics

## Proposed Solution: Unified Game State Detection System

### Core Principle

**Explicit state over inferred state.** Instead of inferring game state from multiple signals, we should have a clear, explicit game state that both frontend and backend can use.

### Architecture

#### 1. Game State Enum

```python
# BackEnd/utils/game_state.py
from enum import Enum

class GameState(Enum):
    """Unified game state types"""
    NEW_GAME = "new_game"              # Brand new game start (Q1, opening tip)
    RESUMING = "resuming"               # Resuming existing game (quarter break, normal resume)
    TIMEOUT_RESUME = "timeout_resume"   # Resuming from timeout (SIP)
    FOUL_OUT_RESUME = "foul_out_resume" # Resuming from player foul out (SIP)
    QUARTER_BREAK = "quarter_break"     # Quarter break (Q2/Q3/Q4, BIP)
```

#### 2. Unified Detection Function

```python
# BackEnd/api/api.py
def determine_game_state(
    request: QuarterSimulationRequest,
    saved: dict | None,
    gm: GameManager | None,
    games_collection
) -> GameState:
    """
    Unified function to determine game state.
    Single source of truth for all game state detection.
    
    Returns:
        GameState enum indicating the current game state
    """
    # Priority 1: Explicit flags from request
    if request.resume_from_timeout:
        return GameState.TIMEOUT_RESUME
    
    if request.resume_from_foul_out:  # Future: player foul out resume
        return GameState.FOUL_OUT_RESUME
    
    # Priority 2: Check database for timeout state
    if request.game_id:
        timeout_state = restore_timeout_resume_state(request.game_id, request, games_collection)
        if timeout_state and timeout_state.get("timeout_next_play_type"):
            # Validate quarter matches (prevent stale data)
            saved_quarter = timeout_state.get("quarter", 0)
            if saved_quarter == request.quarter:
                return GameState.TIMEOUT_RESUME
    
    # Priority 3: Quarter-based detection
    if request.quarter == 1:
        # Q1: Check if this is a new game or resuming
        if not request.game_id:
            return GameState.NEW_GAME  # No game_id = new game
        
        if saved:
            saved_quarter = saved.get("quarter", 1)
            if saved_quarter > 1:
                return GameState.NEW_GAME  # Requesting Q1 but saved game is Q2+ = new game
            else:
                return GameState.RESUMING  # Same quarter = resuming
        else:
            # No saved game found = new game
            return GameState.NEW_GAME
    
    elif request.quarter > 1:
        # Q2/Q3/Q4: Quarter break
        return GameState.QUARTER_BREAK
    
    # Default: Resuming
    return GameState.RESUMING
```

#### 3. Frontend Explicit State Passing

```javascript
// FrontEnd/static/js/phaser/gameScene.js
// When starting a new game, explicitly set flag
const isNewGame = !this.gameId || 
                  (this.quarter === 1 && !urlParams.get('game_id') && !resumeFromTimeout);

const payload = {
  home_team: homeTeam,
  away_team: awayTeam,
  quarter: this.quarter,
  is_new_game: isNewGame  // ✅ Explicit flag instead of inferring
};

// Only pass game_id if it's not a new game
if (this.gameId && !isNewGame) {
  payload.game_id = this.gameId;
}
```

#### 4. Backend State-Based Routing

```python
# BackEnd/api/api.py
@app.post("/api/simulate-quarter")
def simulate_quarter_endpoint(request: QuarterSimulationRequest, ...):
    # Determine game state using unified function
    game_state = determine_game_state(request, saved, gm, games_collection)
    
    # Route based on explicit state
    if game_state == GameState.NEW_GAME:
        # New game: Generate new game_id, create opening tip
        if request.game_id:
            # Frontend passed game_id but this is a new game - ignore it
            game_id = generate_game_id()
        else:
            game_id = generate_game_id()
        # ... create new game ...
    
    elif game_state == GameState.TIMEOUT_RESUME:
        # Timeout resume: Restore timeout state, create SIP
        timeout_state = restore_timeout_resume_state(...)
        apply_timeout_resume_state_to_gm(gm, timeout_state)
        request.resume_from_timeout = True
    
    elif game_state == GameState.QUARTER_BREAK:
        # Quarter break: Create BIP
        # ... quarter break logic ...
    
    elif game_state == GameState.RESUMING:
        # Normal resume: Continue existing game
        # ... resume logic ...
    
    # Call simulate_quarter with explicit state
    simulate_quarter(gm, ..., game_state=game_state)
```

#### 5. Simulate Quarter State-Based Logic

```python
# BackEnd/main.py
def simulate_quarter(
    gm: GameManager,
    ...,
    game_state: GameState | None = None,  # ✅ Explicit state parameter
):
    # Use explicit state instead of inferring
    if game_state == GameState.TIMEOUT_RESUME:
        # Create SIP turn
        ...
    elif game_state == GameState.NEW_GAME:
        # Create opening tip (Q1) or BIP (OT)
        ...
    elif game_state == GameState.QUARTER_BREAK:
        # Create BIP for Q2/Q3/Q4
        ...
    # etc.
```

## Benefits of Unified System

1. **Single Source of Truth**: One function determines game state
2. **Explicit Over Inferred**: Clear state instead of scattered conditionals
3. **Easier to Debug**: One place to check when something breaks
4. **Easier to Extend**: Adding new game states is straightforward
5. **Consistent**: All code paths use the same logic
6. **Testable**: Can unit test the state detection function

## Current Implementation Status

### ❌ Not Implemented

**Status:** The unified game state detection system has NOT been implemented. The system still uses scattered inference logic.

**What Still Exists:**
- ✅ `restore_timeout_resume_state()` function exists (`api.py:392-491`) - unified function for restoring timeout state from DB
- ✅ `apply_timeout_resume_state_to_gm()` function exists (`api.py:493-513`) - applies timeout state to GameManager
- ❌ `GameState` enum does NOT exist
- ❌ `determine_game_state()` function does NOT exist
- ❌ Frontend still uses inference logic (`gameScene.js:220-226`)
- ❌ Backend still uses inference logic (`api.py:936-978, 1163`)

**Current Workarounds (Still in Use):**
1. **Frontend**: Clears stale `game_id` for new games (prevents stale data) - `gameScene.js:228-235`
2. **Backend**: Clears timeout state from DB after resume (defensive cleanup) - `api.py:967-977`
3. **Backend**: Validates quarter match before using timeout state (prevents stale data) - `api.py:1145-1159`

**Note:** The current system works but uses inference logic. The unified system would replace this with explicit state management.

## Migration Plan

### Phase 1: Create Infrastructure ❌ **NOT DONE**
1. ❌ Create `GameState` enum
2. ❌ Create `determine_game_state()` function
3. ❌ Add `game_state` parameter to `simulate_quarter()`

**Status:** Not implemented

### Phase 2: Frontend Updates ❌ **NOT DONE**
1. ❌ Add `is_new_game` flag to `QuarterSimulationRequest`
2. ❌ Update frontend to explicitly set `is_new_game` flag
3. ❌ Remove inference logic from frontend

**Status:** Not implemented - frontend still uses inference logic

### Phase 3: Backend Refactor ❌ **NOT DONE**
1. ❌ Replace all inference logic with `determine_game_state()` calls
2. ❌ Update `simulate_quarter()` to use explicit `game_state` parameter
3. ❌ Remove scattered `is_new_game` / `should_check_timeout` conditionals

**Status:** Not implemented - backend still uses inference logic

### Phase 4: Testing & Validation ❌ **NOT DONE**
1. ❌ Test all game state transitions
2. ❌ Verify timeout resume works correctly
3. ❌ Verify new game starts work correctly
4. ❌ Verify quarter breaks work correctly

**Status:** Not applicable - system not implemented

---

# Part 2: Frontend - Unified Navigation Parameter Building

## Problem Statement

The Timeout Navigation System has a strong SS&S foundation with the unified `TimeoutNavigationHelper`, but **4 places in `gameScene.js` still build URL parameters manually** instead of using the helper. This plan migrates those remaining manual builds to use the helper, achieving ~95% SS&S.

## Current State Analysis

### ✅ What's Working (~80% SS&S)

**Unified Helper Usage:**
- ✅ `set-lineup.js`: "Play Now" button (line 838)
- ✅ `set-lineup.js`: "Game Plan" button (line 876)
- ✅ `game-plan.js`: `navigateToCourt()` (line 357)
- ✅ `game-plan.js`: `navigateBack()` (line 414)
- ✅ `timeoutButtonManager.js`: `showTimeoutPopup()` (line 300)
- ✅ `foulOutPopup.js`: Foul out navigation (line 42)
- ✅ `gameScene.js`: Quarter end navigation (line 1585) - **ONE place using helper** ✅ **MIGRATED**

### ⚠️ What's Not Working (~20% Manual Builds)

**Manual Parameter Building in `gameScene.js`:**

1. **Lines 1496-1499:** Locker room popup (quarter complete) ⚠️ **STILL MANUAL**
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextQ);
   params.set('period', `Q${nextQ}`);
   ```

2. **Lines 2056-2059:** Overtime start (OT1) ⚠️ **STILL MANUAL**
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextQ);
   params.set('period', 'OT1');
   ```

3. **Lines 2088-2091:** Overtime continuation (OT2+) ⚠️ **STILL MANUAL**
   ```javascript
   const params = new URLSearchParams(window.location.search);
   params.set('game_id', this.gameId);
   params.set('quarter', nextOT);
   params.set('period', `OT${nextOTNumber}`);
   ```

4. **Lines 2182-2185:** Regular quarter complete (fallback path) ⚠️ **STILL MANUAL**
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

## Current Implementation Status

### ✅ Completed Items

1. **Phase 1: Identify All Manual Builds** ✅ **COMPLETE**
   - Identified 4 manual builds in `gameScene.js`
   - Verified locations: lines 1496-1499, 2056-2059, 2088-2091, 2182-2185

2. **One Location Migrated** ✅ **COMPLETE**
   - `gameScene.js` line 1585: Quarter end navigation uses helper
   - **Status:** Successfully migrated to use `TimeoutNavigationHelper.buildGameNavigationParams()`

### ⚠️ Outstanding Items

1. **4 Manual Builds Still Exist:**
   - Lines 1496-1499: Locker room popup (quarter complete)
   - Lines 2056-2059: Overtime start (OT1)
   - Lines 2088-2091: Overtime continuation (OT2+)
   - Lines 2182-2185: Regular quarter complete (fallback path)

2. **Phase 2-4: Not Started**
   - Manual builds not yet migrated to helper
   - Validation and testing not done
   - Documentation not updated

## Migration Plan

### Phase 1: Identify All Manual Builds ✅ **COMPLETE**

**Action Items:**
1. ✅ **Complete** - Identified 4 manual builds in `gameScene.js`
2. ✅ **Complete** - Verified no other manual builds exist in codebase
3. ✅ **Complete** - Documented context for each manual build

**Files Checked:**
- ✅ `FrontEnd/static/js/phaser/gameScene.js` (lines 1496-1499, 2056-2059, 2088-2091, 2182-2185)
- ✅ Verified one location (line 1585) already uses helper

---

### Phase 2: Migrate Manual Builds to Helper ⚠️ **PARTIALLY DONE**

**Goal:** Replace all 4 manual parameter builds with `TimeoutNavigationHelper.buildGameNavigationParams()`

**Current Status:** 1 of 5 locations migrated (quarter end navigation at line 1585)

#### Step 2.1: Migrate Locker Room Popup (Lines 1496-1499) ❌ **NOT DONE**

**Current Code (Lines 1496-1499):**
```javascript
const nextQ = this.quarter + 1;
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', `Q${nextQ}`);
```

**Status:** ❌ **NOT MIGRATED** - Still uses manual parameter building

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

#### Step 2.2: Migrate Overtime Start (Lines 2056-2059) ❌ **NOT DONE**

**Current Code (Lines 2056-2059):**
```javascript
const nextQ = nextQuarterNumber; // Should be 5 (first OT)
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', 'OT1');
```

**Status:** ❌ **NOT MIGRATED** - Still uses manual parameter building

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

#### Step 2.3: Migrate Overtime Continuation (Lines 2088-2091) ❌ **NOT DONE**

**Current Code (Lines 2088-2091):**
```javascript
const currentOTNumber = quarterThatJustFinished - 4;
const nextOTNumber = currentOTNumber + 1;
const nextOT = nextQuarterNumber; // Should be the next OT quarter number
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextOT);
params.set('period', `OT${nextOTNumber}`);
```

**Status:** ❌ **NOT MIGRATED** - Still uses manual parameter building

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

#### Step 2.4: Migrate Regular Quarter Complete (Lines 2182-2185) ❌ **NOT DONE**

**Current Code (Lines 2182-2185):**
```javascript
const nextQ = this.quarter + 1;
const params = new URLSearchParams(window.location.search);
params.set('game_id', this.gameId);
params.set('quarter', nextQ);
params.set('period', `Q${nextQ}`);
```

**Status:** ❌ **NOT MIGRATED** - Still uses manual parameter building

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

### Phase 3: Validation & Testing ❌ **NOT DONE**

**Goal:** Ensure all migrations work correctly and no parameters are lost.

**Status:** Not applicable - migrations not complete

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

### Phase 4: Documentation Update ❌ **NOT DONE**

**Goal:** Update documentation to reflect 95% SS&S status.

**Status:** Not applicable - migrations not complete

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

### Part 1: Backend Game State Detection

- ❌ `GameState` enum created
- ❌ `determine_game_state()` function implemented
- ❌ All inference logic replaced with explicit state
- ❌ Frontend passes explicit `is_new_game` flag
- ❌ Backend routes based on explicit `GameState`

### Part 2: Frontend Navigation Parameters

### Code Quality
- ⚠️ All 4 manual parameter builds replaced with helper calls (1 of 5 done)
- ⚠️ Consistent pattern across all navigation entry points
- ⚠️ No duplicate parameter building logic
- ⚠️ Helper error handling in all places

### Functionality
- ⚠️ All quarter transitions work correctly (Q1→Q2, Q2→Q3, Q3→Q4) (1 of 4 done)
- ⚠️ Overtime transitions work correctly (Q4→OT1, OT1→OT2, etc.) (0 of 2 done)
- ⚠️ All parameters preserved (mode, tournament_id, franchise_id, etc.)
- ✅ No regressions in existing functionality

### SS&S Metrics
- **Part 1 (Backend):** ❌ **0%** - Not implemented
- **Part 2 (Frontend):** ⚠️ **~80% SS&S** (1 of 5 locations migrated)
- **Target:** ~95% SS&S for frontend, 100% for backend

---

## Related Systems

- **Timeout Resume System**: Uses both parts for timeout resume detection and navigation
- **Quarter Break System**: Uses both parts for quarter break detection and navigation
- **Game Initialization**: Uses Part 1 for new game detection
- **Navigation System**: Uses Part 2 for consistent parameter building

---

## Notes

- **Part 1 (Backend)**: Not urgent - current system works, but structural improvement would make system more maintainable
- **Part 2 (Frontend)**: Partially implemented - 1 of 5 locations migrated
- Both parts can be done incrementally without breaking existing functionality
- Should be done when we have time for structural improvements

---

## Next Steps

1. **Part 1 (Backend):** Review and approve unified game state detection approach
2. **Part 2 (Frontend):** Continue migrating remaining 4 manual builds to helper
3. **Both Parts:** Track progress against success criteria
4. **Both Parts:** Document lessons learned for future SS&S improvements

