# Sim Quarter Feature - Work Plan

**Date Created:** January 11, 2026  
**Date Completed:** January 2026  
**Status:** ✅ COMPLETE  
**Priority:** 🔴 HIGH - Marketing video feature  
**Related:** Feature request to replace "Sim To 4th Quarter" button

**Note:** This feature has been fully implemented and is working in production. The "Sim Quarter" button is functional and allows users to simulate one quarter at a time, navigating to the Lineup Screen after each quarter.

## Overview

Replace the "Sim To 4th Quarter" button with a "Sim Quarter" button that simulates one quarter at a time, then navigates to the Lineup Screen experience after each quarter.

## Current Implementation

### "Sim To 4th Quarter" Button
- **Location:** `FrontEnd/static/js/phaser/bootGame.js` - `handleSimToFourth()` (lines 420-601)
- **Behavior:**
  - Simulates Q1, Q2, Q3 in a loop (full simulation, no animations)
  - After Q3, redirects to `set-lineup.html` for Q4
  - User sets lineup for Q4, then plays Q4 normally

### Button Location
- **HTML:** `FrontEnd/static/court.html` - `.sim-to-fourth-button`
- **CSS/Classes:** Uses existing button styling

## New Feature Requirements

### "Sim Quarter" Button
- **Behavior:**
  1. User clicks "Sim Quarter" button
  2. Simulates the NEXT quarter (current quarter + 1)
  3. Quarter simulates normally (timeouts work for both teams)
  4. Game data persists (saved to database)
  5. After quarter completes, navigate to Lineup Screen (`set-lineup.html`)
  6. User can adjust lineup, game plan, playbooks, view box score
  7. User continues to next quarter from lineup screen
  8. Button should be disabled/hidden when Q4+ is complete

### Key Differences from "Sim To 4th Quarter"
- **Old:** Simulates Q1-Q3 at once, then goes to Q4 lineup
- **New:** Simulates ONE quarter at a time, goes to lineup after each quarter
- **Old:** Only works before Q4 starts
- **New:** Works for any quarter (Q1, Q2, Q3, Q4, OT)

---

## Work Plan

### Phase 1: Backend Verification (No Changes Needed)
**Status:** ✅ VERIFIED  
**Time:** 0 hours (already works)

**Verification:**
- ✅ `/api/simulate-quarter` endpoint already supports single quarter simulation
- ✅ `full_sim=true` parameter works for full simulation (no animations)
- ✅ Timeouts are handled during full simulation
- ✅ Game state persists to database after each quarter
- ✅ Quarter increment logic works correctly

**Conclusion:** Backend already supports this feature - no changes needed

---

### Phase 2: Frontend - Rename Button & Update Handler
**Priority:** 🔴 HIGH  
**Estimated Time:** 1-2 hours

#### 2.1 Update HTML Button Text
**File:** `FrontEnd/static/court.html`

**Changes:**
- Change button text from "Sim To 4th Quarter" → "Sim Quarter"
- Update button class/ID if needed (keep `.sim-to-fourth-button` for backward compatibility OR rename to `.sim-quarter-button`)
- **Recommendation:** Keep existing class for now, update text only (simpler)

**Code Location:**
- Line ~2226: `<button class="sim-to-fourth-button">Sim To 4th Quarter</button>`
- Change to: `<button class="sim-to-fourth-button">Sim Quarter</button>`

#### 2.2 Refactor Handler Function
**File:** `FrontEnd/static/js/phaser/bootGame.js`

**Function:** `handleSimToFourth()` → Rename to `handleSimQuarter()`

**Current Logic (lines 420-601):**
```javascript
async function handleSimToFourth() {
  // Loops through Q1, Q2, Q3
  while (currentQ <= 3) {
    // Simulate quarter with full_sim=true
    // ...
  }
  // Redirect to set-lineup for Q4
}
```

**New Logic:**
```javascript
async function handleSimQuarter() {
  // Simulate ONLY the next quarter (current quarter + 1)
  const nextQuarter = quarter + 1;
  
  // Validate: Don't simulate if game is complete (Q4+ and scores differ)
  if (gameComplete) {
    return; // Button should be disabled, but safety check
  }
  
  // Simulate next quarter with full_sim=true
  // Redirect to set-lineup after simulation
}
```

**Key Changes:**
1. Remove `while` loop (no longer needed)
2. Simulate only `quarter + 1` (next quarter)
3. After simulation, redirect to `set-lineup.html` (same as current)
4. Update URL params to include correct quarter number

#### 2.3 Update Function Name References
**File:** `FrontEnd/static/js/phaser/bootGame.js`

**Changes:**
- Rename `handleSimToFourth` → `handleSimQuarter`
- Update event listener (line ~919): `sim4Btn.addEventListener('click', handleSimQuarter)`

**Files to Check:**
- `bootGame.js` - Function definition and event listener
- `finalizeGame.js` - Any references to "Sim To 4th Quarter" (if any)
- Search codebase for "handleSimToFourth" references

---

### Phase 3: Update Button State Logic
**Priority:** 🔴 HIGH  
**Estimated Time:** 30 minutes

**File:** `FrontEnd/static/js/phaser/bootGame.js`

#### 3.1 Button Visibility/Disable Logic
**Current Logic (lines 914-921):**
```javascript
if (sim4Btn) {
  if (quarter >= 4) {
    sim4Btn.disabled = true;
    sim4Btn.title = 'Already in 4th quarter';
  } else {
    sim4Btn.addEventListener('click', handleSimToFourth);
  }
}
```

**New Logic:**
- Button should be enabled for Q1, Q2, Q3, Q4 (before game is complete)
- Button should be disabled when game is complete (Q4+ and scores differ, or game is final)
- Update button text/title dynamically if needed

**Implementation:**
```javascript
if (simQuarterBtn) {
  // Check if game is complete
  const gameComplete = quarter >= 4 && /* game is final */;
  
  if (gameComplete) {
    simQuarterBtn.disabled = true;
    simQuarterBtn.title = 'Game complete';
  } else {
    simQuarterBtn.disabled = false;
    simQuarterBtn.title = `Sim Quarter ${quarter + 1}`;
    simQuarterBtn.addEventListener('click', handleSimQuarter);
  }
}
```

**Note:** Need to check how game completion is determined in `bootGame.js`

---

### Phase 4: Navigation & URL Parameters
**Priority:** 🔴 HIGH  
**Estimated Time:** 30 minutes

**File:** `FrontEnd/static/js/phaser/bootGame.js`

#### 4.1 Update URL Parameters for Lineup Screen
**Current Logic (lines 566-587):**
- Builds URL params for Q4 redirect
- Includes: `home`, `away`, `mode`, `franchise_id`, `week`, `team_id`, `my_team`, `quarter`, `period`, `game_id`

**New Logic:**
- Same URL params, but `quarter` should be `nextQuarter` (quarter + 1 after simulation)
- `period` should reflect correct period (Q1, Q2, Q3, Q4, OT)

**Key Change:**
```javascript
// After simulating nextQuarter
params.set('quarter', nextQuarter);
params.set('period', `Q${nextQuarter}`); // Or 'OT' for overtime
```

#### 4.2 Verify Lineup Screen Handles Quarter Breaks
**File:** `FrontEnd/static/set-lineup.js`

**Verification:**
- Lineup screen already handles quarter breaks (Q2, Q3, Q4)
- Check that it correctly loads game state for the new quarter
- Verify energy recharge happens correctly (should already work)

**Action:** Test that lineup screen works for Q2, Q3, Q4 after simulation

---

### Phase 5: Testing & Edge Cases
**Priority:** 🔴 HIGH  
**Estimated Time:** 1-2 hours

#### 5.1 Test Cases

**Basic Flow:**
- [ ] Q1: Click "Sim Quarter" → Simulates Q1 → Goes to lineup → User sets lineup → Continues to Q2
- [ ] Q2: Click "Sim Quarter" → Simulates Q2 → Goes to lineup → User sets lineup → Continues to Q3
- [ ] Q3: Click "Sim Quarter" → Simulates Q3 → Goes to lineup → User sets lineup → Continues to Q4
- [ ] Q4: Click "Sim Quarter" → Simulates Q4 → Goes to lineup → User sets lineup → Game completes

**Edge Cases:**
- [ ] Overtime: Q4 ends in tie → OT simulation works
- [ ] Game completion: Button disabled when game is complete
- [ ] Timeouts: Timeouts work during simulation (both user and computer teams)
- [ ] Game data persistence: Verify game state saves after each quarter
- [ ] Mode support: Works in Single Game, Tournament, and Franchise modes
- [ ] Week support: Works in Franchise mode with week parameter
- [ ] Navigation: User can access Game Plan, Playbooks, Box Score from lineup screen

#### 5.2 Regression Testing
- [ ] Verify "Play Quarter" button still works
- [ ] Verify "Sim Full Game" button still works
- [ ] Verify normal turn-by-turn gameplay still works
- [ ] Verify timeout flows still work

---

## Implementation Order

1. **Phase 2.1:** Update HTML button text (5 min)
2. **Phase 2.2:** Refactor handler function (1 hour)
3. **Phase 2.3:** Update function references (15 min)
4. **Phase 3:** Update button state logic (30 min)
5. **Phase 4:** Verify navigation/URL params (30 min)
6. **Phase 5:** Testing (1-2 hours)

**Total Estimated Time:** 3-4 hours

---

## Files to Modify

1. `FrontEnd/static/court.html` - Button text
2. `FrontEnd/static/js/phaser/bootGame.js` - Handler function refactor
3. `FrontEnd/static/js/phaser/finalizeGame.js` - Check for references (if any)

## Files to Test (No Changes Expected)

1. `FrontEnd/static/set-lineup.js` - Verify quarter break handling
2. `BackEnd/api/api.py` - `/api/simulate-quarter` endpoint (no changes needed)
3. `BackEnd/main.py` - `simulate_quarter()` function (no changes needed)

---

## Success Criteria

✅ Button text changed to "Sim Quarter"  
✅ Button simulates only the next quarter (not Q1-Q3)  
✅ After simulation, navigates to lineup screen  
✅ User can adjust lineup, game plan, playbooks, view box score  
✅ Timeouts work during simulation (both teams)  
✅ Game data persists correctly  
✅ Works in all game modes (Single, Tournament, Franchise)  
✅ Button disabled when game is complete  
✅ No regression in existing features  

---

## Notes

- Backend already supports this feature - no backend changes needed
- Current "Sim To 4th Quarter" logic can be largely reused
- Main change: Remove loop, simulate only next quarter
- Navigation to lineup screen already works (just need correct quarter number)
- This is a relatively straightforward refactor

---

## Questions to Resolve During Implementation

1. Should button be visible for Q4, or only Q1-Q3? (Requirement says Q1-Q4, so include Q4)
2. How is game completion determined? (Need to check `bootGame.js` logic)
3. Should button text be dynamic? ("Sim Quarter 2", "Sim Quarter 3", etc.) (Optional enhancement)
4. What happens if user clicks "Sim Quarter" multiple times quickly? (Should disable button during simulation - already handled)

