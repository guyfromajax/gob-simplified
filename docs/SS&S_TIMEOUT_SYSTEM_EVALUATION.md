# SS&S Timeout System Evaluation - SS&S Analysis

**Date:** January 2025  
**Purpose:** Evaluate Single Source & System (SS&S) consistency across all game entry/resume scenarios

## Executive Summary

This document evaluates the timeout turns system for SS&S consistency across:
1. **Game Start** (Q1, OT)
2. **Quarter Breaks** (Q2, Q3, Q4)
3. **Timeouts** (User/Computer initiated)
4. **Player Foul Out** scenarios

And checks consistency across all navigation entry points:
- Set Lineup screen
- Game Plan screen
- Back navigation
- Game re-entry points

---

## Scenario Analysis

### 1. Game Start (Q1, OT)

**Backend:**
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 318-401)
- **Initial Turn:** `OPENING_TIP`
- **Play Type:** Opening Tip → HCO
- **Data Required:** None (new game)
- **URL Parameters:** No `game_id`, no `resume_from_timeout`

**Frontend:**
- **Navigation:** Direct from lineup selection
- **Entry Point:** `set-lineup.js` "Play Now" button
- **URL Parameters:** Only team/lineup info, no `game_id` for new Q1

**Status:** ✅ **CONSISTENT** - No timeout system involvement

---

### 2. Quarter Breaks (Q2, Q3, Q4)

**Backend:**
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 402-493)
- **Initial Turn:** `BASELINE_INBOUND` (BIP)
- **Play Type:** BIP → HCO/HCT/FCP (based on defensive pressure)
- **Data Required:** `opening_tip_winner` from `game_state`
- **URL Parameters:** `game_id` required, `resume_from_timeout` should be **FALSE/absent**

**Frontend Navigation:**
- **Quarter End:** `gameScene.js` line 1515-1525 - Clears `resume_from_timeout` ✅
- **Set Lineup:** `set-lineup.js` - Only preserves `resume_from_timeout` for Q1 ✅
- **Game Plan:** `game-plan.js` - Only preserves `resume_from_timeout` for Q1 ✅

**Status:** ✅ **CONSISTENT** - All navigation functions correctly handle quarter breaks

---

### 3. Timeouts (User/Computer Initiated)

**Backend:**
- **Location:** `BackEnd/models/turn_manager.py` `setup_timeout_turn()` (lines 1344-1410)
- **Initial Turn:** `TIMEOUT`
- **Next Play Type:** `SIDE_INBOUND` (SIP) or `FREE_THROW` (if FTs pending)
- **Data Stored:**
  - `timeout_next_play_type` in `game_state`
  - `timeout_offense_team_id` in `game_state` (captured in `call_timeout_endpoint`)
- **Resume Logic:** `BackEnd/main.py` `simulate_quarter()` (lines 281-350)
  - Checks `resume_from_timeout=True`
  - Validates `timeout_next_play_type` exists
  - Creates SIP turn with correct possession team

**Frontend Navigation:**
- **Timeout Call:** `timeoutButtonManager.js` - Sets `resume_from_timeout=true` in URL ✅
- **Set Lineup:** `set-lineup.js` - Preserves `resume_from_timeout` for Q1 only ✅
- **Game Plan:** `game-plan.js` - Preserves `resume_from_timeout` for Q1 only ✅
- **Court Entry:** `gameScene.js` - Passes `resume_from_timeout` to backend ✅

**Status:** ✅ **CONSISTENT** - Unified timeout resume system

---

### 4. Player Foul Out Scenario

**Backend:**
- **Location:** `BackEnd/models/game_manager.py` `simulate_macro_turn()` (lines 226-259)
- **Initial Turn:** `TIMEOUT` (with `timeout_reason="FOUL_OUT"`)
- **Next Play Type:** `SIDE_INBOUND` (SIP) or `FREE_THROW` (if FTs pending)
- **Data Stored:**
  - `timeout_next_play_type` in `game_state` ✅
  - **MISSING:** `timeout_offense_team_id` - Not captured for foul out! ❌
- **Resume Logic:** Uses same `resume_from_timeout` path as regular timeouts

**Frontend Navigation:**
- **Foul Out Popup:** `foulOutPopup.js` - Navigates to lineup screen
- **URL Parameters:** 
  - ✅ Sets `game_id`
  - ✅ Sets `quarter`
  - ✅ Sets `clock` (preserves clock time)
  - ❌ **MISSING:** Does NOT set `resume_from_timeout=true` ❌
- **Set Lineup:** Would need `resume_from_timeout` to resume correctly
- **Game Plan:** Would need `resume_from_timeout` to resume correctly

**Status:** ❌ **INCONSISTENT** - Foul out uses timeout system but doesn't set resume flag

---

## Navigation Function Analysis

### Set Lineup Screen (`set-lineup.js`)

**Functions:**
1. **"Play Now" button** (lines 823-890)
   - ✅ Checks `resume_from_timeout` from URL
   - ✅ Only preserves for Q1 (`shouldPreserveTimeoutFlag`)
   - ✅ Passes `game_id` for Q2+ or Q1 timeout
   - ✅ Preserves `clock` time
   - ✅ Preserves lineup params

2. **"Game Plan" button** (lines 896-960)
   - ✅ Checks `resume_from_timeout` from URL
   - ✅ Only preserves for Q1 (`shouldPreserveTimeoutFlag`)
   - ✅ Passes `game_id` for Q2+ or Q1 timeout
   - ✅ Preserves lineup params

**Status:** ✅ **CONSISTENT** - Both functions use same pattern

---

### Game Plan Screen (`game-plan.js`)

**Functions:**
1. **`navigateToCourt()`** (lines 311-441)
   - ✅ Reads URL params directly from `window.location.search`
   - ✅ Checks `resume_from_timeout` from URL
   - ✅ Only preserves for Q1 (`shouldPreserveTimeoutFlag`)
   - ✅ Passes `game_id` for Q2+ or Q1 timeout
   - ✅ Preserves `clock` time
   - ✅ Preserves lineup params
   - ✅ Preserves `start_with_inbound` and `starting_possession`

2. **`navigateBack()`** (lines 443-525)
   - ✅ Reads URL params directly from `window.location.search`
   - ✅ Checks `resume_from_timeout` from URL
   - ✅ Only preserves for Q1 (`shouldPreserveTimeoutFlag`)
   - ✅ Passes `game_id` for Q2+ or Q1 timeout
   - ✅ Preserves lineup params

**Status:** ✅ **CONSISTENT** - Both functions use same pattern

---

### Foul Out Popup (`foulOutPopup.js`)

**Function:**
- **`showFoulOutPopup()`** (lines 17-207)
  - ✅ Sets `game_id`
  - ✅ Sets `quarter`
  - ✅ Sets `clock` (preserves clock time)
  - ✅ Sets team info
  - ✅ Sets mode/tournament/franchise IDs
  - ❌ **MISSING:** Does NOT set `resume_from_timeout=true` ❌

**Status:** ❌ **INCONSISTENT** - Should set `resume_from_timeout=true` to match timeout system

---

## Backend Consistency Analysis

### Timeout State Storage

**Regular Timeouts:**
- ✅ `timeout_next_play_type` stored in `game_state`
- ✅ `timeout_offense_team_id` stored in `game_state` (in `call_timeout_endpoint`)
- ✅ Both saved to database via `summarize_game_state()`

**Foul Out:**
- ✅ `timeout_next_play_type` stored in `game_state`
- ❌ `timeout_offense_team_id` **NOT stored** - Missing! ❌

**Status:** ❌ **INCONSISTENT** - Foul out doesn't capture possession team

---

### Resume Logic

**Location:** `BackEnd/main.py` `simulate_quarter()` (lines 281-350)

**Checks:**
1. ✅ `resume_from_timeout=True` from request
2. ✅ `timeout_next_play_type` exists in `game_state`
3. ✅ Validates before creating SIP turn
4. ✅ Clears timeout state after resume
5. ✅ Clears timeout state from database

**Status:** ✅ **CONSISTENT** - Unified resume logic for all timeout types

---

## Issues Identified

### Critical Issues

1. **Foul Out Missing `resume_from_timeout` Flag**
   - **Location:** `FrontEnd/static/js/phaser/utils/foulOutPopup.js`
   - **Issue:** Foul out popup doesn't set `resume_from_timeout=true` in URL
   - **Impact:** Backend won't know to resume from timeout, may treat as new quarter
   - **Fix:** Add `resume_from_timeout=true` to URL params

2. **Foul Out Missing `timeout_offense_team_id`**
   - **Location:** `BackEnd/models/game_manager.py` `simulate_macro_turn()` (line 252)
   - **Issue:** Foul out creates timeout turn but doesn't capture `timeout_offense_team_id`
   - **Impact:** Possession team may be incorrect on resume
   - **Fix:** Capture `game.offense_team.team_id` before creating timeout turn

### Minor Issues

3. **Code Duplication in Navigation Functions**
   - **Location:** `set-lineup.js`, `game-plan.js`
   - **Issue:** Similar parameter handling logic duplicated across multiple functions
   - **Impact:** Maintenance burden, risk of inconsistencies
   - **Fix:** Create unified navigation helper function

---

## Recommended SS&S Improvements

### 1. Unified Navigation Helper Function

Create a shared function for consistent parameter handling:

```javascript
// FrontEnd/static/js/shared/navigationHelpers.js
export function buildGameNavigationParams(options) {
  const {
    sourceUrlParams,  // URLSearchParams from current page
    targetQuarter,
    gameId,
    resumeFromTimeout = false,
    clock = null,
    lineup = {},
    // ... other params
  } = options;
  
  const params = new URLSearchParams();
  
  // Core game params
  params.set('quarter', String(targetQuarter));
  params.set('period', `Q${targetQuarter}`);
  
  // Game ID logic (Q2+ OR Q1 timeout)
  const shouldPassGameId = gameId && (targetQuarter > 1 || (resumeFromTimeout && targetQuarter === 1));
  if (shouldPassGameId) {
    params.set('game_id', gameId);
  }
  
  // Resume from timeout (Q1 only)
  if (resumeFromTimeout && targetQuarter === 1) {
    params.set('resume_from_timeout', 'true');
  }
  
  // Clock preservation
  if (clock) {
    params.set('clock', clock);
  }
  
  // ... other params
  
  return params;
}
```

### 2. Unified Timeout State Capture

Ensure all timeout scenarios capture the same state:

```python
# BackEnd/models/game_manager.py
def simulate_macro_turn(self):
    # ... existing code ...
    
    if result.get("fouled_out"):
        # ✅ SS&S: Capture possession team BEFORE creating timeout turn
        self.game_state["timeout_offense_team_id"] = self.offense_team.team_id
        
        timeout_turn = self.turn_manager.setup_timeout_turn(
            timeout_reason="FOUL_OUT",
            calling_team=None,
            foul_out_player=foul_out_player
        )
        # ... rest of code ...
```

### 3. Unified Resume Detection

Backend already has unified resume logic, but frontend should be consistent:

```javascript
// FrontEnd/static/js/phaser/utils/foulOutPopup.js
export function showFoulOutPopup({ ... }) {
  // ... existing code ...
  
  // ✅ SS&S: Set resume_from_timeout for foul out (same as regular timeout)
  params.set('resume_from_timeout', 'true');
  
  // ... rest of code ...
}
```

---

## Test Scenarios

### Test 1: Game Start (Q1)
- [ ] New game starts with opening tip
- [ ] No `game_id` in URL
- [ ] No `resume_from_timeout` in URL
- [ ] Backend creates opening tip turn

### Test 2: Quarter Break (Q2)
- [ ] Q1 ends, navigate to Q2
- [ ] `game_id` present in URL
- [ ] `resume_from_timeout` NOT in URL
- [ ] Backend creates BIP turn
- [ ] Correct possession team (non-opening tip winner)

### Test 3: Quarter Break (Q3)
- [ ] Q2 ends, navigate to Q3
- [ ] `game_id` present in URL
- [ ] `resume_from_timeout` NOT in URL
- [ ] Backend creates BIP turn
- [ ] Correct possession team (non-opening tip winner)

### Test 4: Timeout Resume (Q1)
- [ ] Call timeout in Q1
- [ ] Navigate to lineup screen
- [ ] `game_id` present in URL
- [ ] `resume_from_timeout=true` in URL
- [ ] Navigate to game plan (preserves flag)
- [ ] Navigate to court (preserves flag)
- [ ] Backend creates SIP turn
- [ ] Correct possession team

### Test 5: Foul Out Resume (Q1)
- [ ] Player fouls out in Q1
- [ ] Navigate to lineup screen
- [ ] `game_id` present in URL
- [ ] `resume_from_timeout=true` in URL (after fix)
- [ ] Navigate to game plan (preserves flag)
- [ ] Navigate to court (preserves flag)
- [ ] Backend creates SIP turn
- [ ] Correct possession team

### Test 6: Foul Out Resume (Q2+)
- [ ] Player fouls out in Q2
- [ ] Navigate to lineup screen
- [ ] `game_id` present in URL
- [ ] `resume_from_timeout=true` in URL (after fix)
- [ ] Navigate to game plan (preserves flag)
- [ ] Navigate to court (preserves flag)
- [ ] Backend creates SIP turn
- [ ] Correct possession team

### Test 7: Back Navigation (Set Lineup → Game Plan → Set Lineup)
- [ ] All parameters preserved correctly
- [ ] `resume_from_timeout` preserved for Q1 only
- [ ] `game_id` preserved correctly
- [ ] Lineup params preserved

### Test 8: Back Navigation (Game Plan → Set Lineup → Game Plan)
- [ ] All parameters preserved correctly
- [ ] `resume_from_timeout` preserved for Q1 only
- [ ] `game_id` preserved correctly
- [ ] Lineup params preserved

---

## Next Steps

1. **Fix Foul Out Issues:**
   - Add `resume_from_timeout=true` to `foulOutPopup.js`
   - Capture `timeout_offense_team_id` in `game_manager.py` for foul out

2. **Create Unified Navigation Helper:**
   - Extract common parameter handling logic
   - Update all navigation functions to use helper

3. **Write Comprehensive Tests:**
   - Test all 8 scenarios above
   - Verify SS&S consistency across all entry points

4. **Documentation Update:**
   - Update `master_game_doc.md` with unified system
   - Document foul out as part of timeout system

---

## Conclusion

**Current Status:**
- ✅ Game Start: Consistent
- ✅ Quarter Breaks: Consistent
- ✅ Timeouts: Consistent
- ❌ Foul Out: **2 critical issues** - Missing `resume_from_timeout` flag and `timeout_offense_team_id`

**Overall SS&S Score:** 75% - Good foundation, but foul out needs alignment with timeout system.

**Recommended Priority:**
1. **High:** Fix foul out issues (breaks resume functionality)
2. **Medium:** Create unified navigation helper (reduces maintenance burden)
3. **Low:** Documentation updates (improves clarity)

