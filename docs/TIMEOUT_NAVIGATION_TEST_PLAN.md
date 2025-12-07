# Timeout Navigation System - Test Plan

## Overview
This document outlines comprehensive test scenarios for the unified Timeout Navigation Helper system. The system handles all game navigation scenarios with consistent SS&S (Streamlined Systematic Structure) logic.

## Test Scenarios

### 1. Game Start (New Q1 Game)
**Scenario:** Starting a brand new game (Q1)
**Expected Behavior:**
- ✅ Opening Tip (not SIP or BIP)
- ✅ No `game_id` passed (new game)
- ✅ No `resume_from_timeout` flag
- ✅ Data persists correctly

**Test Steps:**
1. Navigate to game selection
2. Select teams and start new game
3. Verify opening tip appears
4. Verify no `game_id` in URL
5. Play a few turns
6. Verify data persists

**Entry Points:**
- Set Lineup screen → "Play Now" button
- Set Lineup screen → "Game Plan" button → "Play Game" button

---

### 2. Quarter Break (Q2, Q3, Q4)
**Scenario:** Advancing to next quarter after quarter ends
**Expected Behavior:**
- ✅ Baseline Inbound Pass (BIP) - not Opening Tip or SIP
- ✅ `game_id` passed (existing game)
- ✅ No `resume_from_timeout` flag (quarter break, not timeout)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game and play through Q1
2. Let quarter end naturally
3. Verify navigation to lineup screen
4. Verify BIP appears (not Opening Tip or SIP)
5. Verify `game_id` in URL
6. Verify no `resume_from_timeout` in URL
7. Play through Q2, Q3, Q4
8. Verify same behavior for each quarter break

**Entry Points:**
- Quarter end → Auto-navigation to Set Lineup screen
- Set Lineup screen → "Play Now" button
- Set Lineup screen → "Game Plan" button → "Play Game" button

---

### 3. Timeout Resume (Q1)
**Scenario:** Calling timeout in Q1 and resuming
**Expected Behavior:**
- ✅ Side Inbound Pass (SIP) - not Opening Tip or BIP
- ✅ `game_id` passed (existing game)
- ✅ `resume_from_timeout=true` flag present
- ✅ Correct possession team (team that had ball when timeout called)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game in Q1
2. Play a few turns
3. Call timeout during SIP/BIP turn
4. Navigate to lineup screen
5. Verify `game_id` and `resume_from_timeout=true` in URL
6. Return to court
7. Verify SIP appears (not Opening Tip or BIP)
8. Verify correct team has possession
9. Verify all game data persisted (scores, clock, fouls, etc.)

**Entry Points:**
- Timeout button → Set Lineup screen → "Play Now" button
- Timeout button → Set Lineup screen → "Game Plan" button → "Play Game" button
- Timeout button → Set Lineup screen → "Game Plan" button → "Back To Lineup" → "Play Now" button

---

### 4. Timeout Resume (Q2+)
**Scenario:** Calling timeout in Q2, Q3, or Q4 and resuming
**Expected Behavior:**
- ✅ Side Inbound Pass (SIP) - not BIP or Opening Tip
- ✅ `game_id` passed (existing game)
- ✅ `resume_from_timeout=true` flag present
- ✅ Correct possession team (team that had ball when timeout called)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game and play through Q1
2. Start Q2 (or Q3/Q4)
3. Play a few turns
4. Call timeout during SIP/BIP turn
5. Navigate to lineup screen
6. Verify `game_id` and `resume_from_timeout=true` in URL
7. Return to court
8. Verify SIP appears (not BIP or Opening Tip)
9. Verify correct team has possession
10. Verify all game data persisted

**Entry Points:**
- Timeout button → Set Lineup screen → "Play Now" button
- Timeout button → Set Lineup screen → "Game Plan" button → "Play Game" button
- Timeout button → Set Lineup screen → "Game Plan" button → "Back To Lineup" → "Play Now" button

---

### 5. Foul Out Resume (Q1)
**Scenario:** Player fouls out in Q1 and resuming
**Expected Behavior:**
- ✅ Side Inbound Pass (SIP) - not Opening Tip or BIP
- ✅ `game_id` passed (existing game)
- ✅ `resume_from_timeout=true` flag present (foul out uses timeout system)
- ✅ Correct possession team (team that had ball when foul out occurred)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game in Q1
2. Play until a player reaches 5 fouls
3. Verify foul out popup appears
4. Navigate to lineup screen
5. Verify `game_id` and `resume_from_timeout=true` in URL
6. Return to court
7. Verify SIP appears (not Opening Tip or BIP)
8. Verify correct team has possession
9. Verify all game data persisted

**Entry Points:**
- Foul out popup → Set Lineup screen → "Play Now" button
- Foul out popup → Set Lineup screen → "Game Plan" button → "Play Game" button

---

### 6. Foul Out Resume (Q2+)
**Scenario:** Player fouls out in Q2, Q3, or Q4 and resuming
**Expected Behavior:**
- ✅ Side Inbound Pass (SIP) - not BIP or Opening Tip
- ✅ `game_id` passed (existing game)
- ✅ `resume_from_timeout=true` flag present (foul out uses timeout system)
- ✅ Correct possession team (team that had ball when foul out occurred)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game and play through Q1
2. Start Q2 (or Q3/Q4)
3. Play until a player reaches 5 fouls
4. Verify foul out popup appears
5. Navigate to lineup screen
6. Verify `game_id` and `resume_from_timeout=true` in URL
7. Return to court
8. Verify SIP appears (not BIP or Opening Tip)
9. Verify correct team has possession
10. Verify all game data persisted

**Entry Points:**
- Foul out popup → Set Lineup screen → "Play Now" button
- Foul out popup → Set Lineup screen → "Game Plan" button → "Play Game" button

---

### 7. Overtime Start (OT1+)
**Scenario:** Starting overtime after Q4 ends tied
**Expected Behavior:**
- ✅ Opening Tip (not SIP or BIP)
- ✅ `game_id` passed (existing game)
- ✅ No `resume_from_timeout` flag (overtime start, not timeout)
- ✅ Data persists correctly

**Test Steps:**
1. Start a game and play through Q4
2. End Q4 with a tie
3. Verify navigation to lineup screen for OT1
4. Verify Opening Tip appears (not SIP or BIP)
5. Verify `game_id` in URL
6. Verify no `resume_from_timeout` in URL
7. Play through OT1
8. Verify data persists

**Entry Points:**
- Quarter end (Q4 tied) → Auto-navigation to Set Lineup screen
- Set Lineup screen → "Play Now" button
- Set Lineup screen → "Game Plan" button → "Play Game" button

---

### 8. Back Navigation (Lineup ↔ Game Plan)
**Scenario:** Navigating back and forth between Lineup and Game Plan screens
**Expected Behavior:**
- ✅ All URL parameters preserved correctly
- ✅ `game_id` preserved
- ✅ `resume_from_timeout` preserved (if present)
- ✅ Lineup preserved
- ✅ Game context preserved

**Test Steps:**
1. Start a game or call timeout
2. Navigate to Game Plan screen
3. Verify all parameters in URL
4. Navigate back to Lineup screen
5. Verify all parameters preserved
6. Navigate to Game Plan again
7. Verify all parameters still preserved
8. Return to court
9. Verify game resumes correctly

**Entry Points:**
- Set Lineup screen → "Game Plan" button → "Back To Lineup" button
- Set Lineup screen → "Game Plan" button → "Play Game" button
- Set Lineup screen → "Game Plan" button → "Back To Lineup" → "Game Plan" → "Play Game"

---

### 9. Cross-Mode Consistency
**Scenario:** Verify system works consistently across all game modes
**Expected Behavior:**
- ✅ Single Game mode works correctly
- ✅ Tournament mode works correctly
- ✅ Franchise mode works correctly
- ✅ All navigation scenarios work in all modes

**Test Steps:**
1. Test all 8 scenarios above in Single Game mode
2. Test all 8 scenarios above in Tournament mode
3. Test all 8 scenarios above in Franchise mode
4. Verify consistent behavior across all modes

**Entry Points:**
- All entry points from scenarios 1-8, tested in each mode

---

## Test Checklist

### Pre-Test Setup
- [ ] Clear browser cache
- [ ] Clear localStorage
- [ ] Clear database (if testing fresh)
- [ ] Verify helper script is loaded (`window.TimeoutNavigationHelper` exists)

### Test Execution
- [ ] Test 1: Game Start (New Q1 Game)
- [ ] Test 2: Quarter Break (Q2, Q3, Q4)
- [ ] Test 3: Timeout Resume (Q1)
- [ ] Test 4: Timeout Resume (Q2+)
- [ ] Test 5: Foul Out Resume (Q1)
- [ ] Test 6: Foul Out Resume (Q2+)
- [ ] Test 7: Overtime Start (OT1+)
- [ ] Test 8: Back Navigation (Lineup ↔ Game Plan)
- [ ] Test 9: Cross-Mode Consistency (Single, Tournament, Franchise)

### Verification Points
For each test, verify:
- [ ] Correct initial turn type (Opening Tip / BIP / SIP)
- [ ] Correct `game_id` handling (present/absent as expected)
- [ ] Correct `resume_from_timeout` flag (present/absent as expected)
- [ ] Correct possession team
- [ ] Data persistence (scores, clock, fouls, timeouts, lineups)
- [ ] URL parameters are correct
- [ ] No console errors
- [ ] No data loss

---

## Known Issues / Edge Cases

### Edge Case 1: Stale `resume_from_timeout` Flag
**Issue:** If `resume_from_timeout=true` is incorrectly preserved across quarter boundaries
**Expected Fix:** Backend should defensively clear the flag if no valid timeout state exists in DB
**Test:** Start Q1 timeout, complete Q1, start Q2 - verify Q2 uses BIP (not SIP)

### Edge Case 2: Stale `game_id` in localStorage
**Issue:** Old `game_id` from previous game session
**Expected Fix:** Frontend should detect new game start and clear `game_id`
**Test:** Complete a game, start a new game - verify new game doesn't use old `game_id`

### Edge Case 3: Browser Back Button
**Issue:** Using browser back button might lose URL parameters
**Expected Fix:** System should use database as source of truth, not just URL params
**Test:** Call timeout, navigate to lineup, use browser back button - verify system still works

---

## Test Results Template

```
Test #: [1-9]
Scenario: [Description]
Mode: [Single/Tournament/Franchise]
Date: [Date]
Tester: [Name]

Results:
- Initial Turn: [Opening Tip/BIP/SIP] ✅/❌
- game_id: [Present/Absent] ✅/❌
- resume_from_timeout: [Present/Absent] ✅/❌
- Possession Team: [Correct/Incorrect] ✅/❌
- Data Persistence: [Yes/No] ✅/❌
- URL Parameters: [Correct/Incorrect] ✅/❌
- Console Errors: [None/Errors listed] ✅/❌

Notes:
[Any additional observations]
```

---

## Success Criteria

All tests pass when:
1. ✅ All 9 scenarios work correctly
2. ✅ All entry points work correctly
3. ✅ All game modes work correctly
4. ✅ No data loss occurs
5. ✅ No console errors
6. ✅ URL parameters are correct
7. ✅ Backend defensive checks work
8. ✅ Frontend helper is used consistently

---

## Post-Test Actions

After completing all tests:
1. Document any failures
2. Create bug reports for any issues
3. Update this test plan with any new edge cases discovered
4. Update documentation if behavior changes

