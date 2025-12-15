# Foul-Out System Test Plan

## Test Date: [Date]
## Tester: [Name]
## Game ID: [ID]

## Success Criteria

### ✅ Test 1: Navigation Flow (Error-Free)
**Objective:** Verify foul out popup → lineup → game plan → box score → court.html navigation works without errors

**Steps:**
1. Trigger a foul out (player reaches 5 fouls)
2. Verify foul out popup appears
3. Click "Sub Players" button
4. Verify navigation to lineup screen (no console errors)
5. Click "Game Plan" button
6. Verify navigation to game plan screen (no console errors)
7. Make any changes to game plan (optional)
8. Click "Play Game" button
9. Verify navigation back to court.html (no console errors)
10. Click "Box Score" button (if available)
11. Verify navigation to box score (no console errors)
12. Navigate back to court.html
13. Verify game continues normally

**Expected Result:** All navigation flows work without JavaScript errors or broken links

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 2: Lineup Screen Pre-Population
**Objective:** Verify lineup screen shows user's current team lineup

**Steps:**
1. Note the current lineup before foul out (which players are in PG, SG, SF, PF, C)
2. Trigger a foul out
3. Navigate to lineup screen
4. Verify all 5 positions (PG, SG, SF, PF, C) show the same players that were in the lineup before foul out

**Expected Result:** Lineup screen displays user's current team with all positions populated (except foul out player if on user's team)

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 3: Foul Out Player Removal
**Objective:** Verify foul out player is removed from lineup if on user's team

**Steps:**
1. Trigger a foul out for a player on the USER'S team
2. Navigate to lineup screen
3. Verify the foul out player's position is EMPTY (no player selected)
4. Verify all other positions still show their players
5. Verify you can select a replacement player for the empty position

**Alternative Test (CPU Team Foul Out):**
1. Trigger a foul out for a player on the CPU team
2. Navigate to lineup screen
3. Verify user's team lineup is still fully populated (no empty positions)
4. Verify you can still make lineup changes if desired

**Expected Result:** 
- If foul out player is on user's team: That position is empty, all others populated
- If foul out player is on CPU team: User's lineup remains fully populated

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 4: Offensive Foul Possession Flip
**Objective:** Verify possession flips correctly on offensive foul foul out

**Steps:**
1. Note which team has possession before the foul
2. Trigger an OFFENSIVE FOUL that results in a foul out
3. After navigating back from lineup screen, verify:
   - The OTHER team (not the team that committed the foul) now has possession
   - The next turn is a SIDE_INBOUND for the team that now has possession
   - Check backend logs to confirm `game.offense_team` was flipped

**Expected Result:** Possession flips to the defensive team, SIP created for new offense team

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 5: Defensive Foul No Possession Flip
**Objective:** Verify possession does NOT flip on defensive foul foul out

**Steps:**
1. Note which team has possession before the foul
2. Trigger a DEFENSIVE FOUL that results in a foul out
3. After navigating back from lineup screen, verify:
   - The SAME team (the team that was fouled) still has possession
   - Check backend logs to confirm `game.offense_team` was NOT flipped

**Expected Result:** Possession remains with the same team (no flip)

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 6: Next Step Transitions
**Objective:** Verify correct next step is cued based on foul type and context

**Test 6a: Offensive Foul → SIP**
1. Trigger an OFFENSIVE FOUL foul out
2. Navigate back from lineup screen
3. Verify next turn is SIDE_INBOUND (SIP)
4. Verify SIP is for the team that now has possession (after flip)

**Test 6b: Defensive Shooting Foul → Free Throws (2 shots)**
1. Trigger a DEFENSIVE FOUL on a SHOT ATTEMPT that results in a foul out
2. Navigate back from lineup screen
3. Verify next turn is FREE_THROW
4. Verify free throws remaining = 2 (or 3 if it was a 3-point attempt)
5. Verify the shooter is the player who took the shot

**Test 6c: Defensive Non-Shooting Foul + Bonus → Free Throws**
1. Ensure defensive team has 5+ team fouls (bonus situation)
2. Trigger a DEFENSIVE NON-SHOOTING FOUL that results in a foul out
3. Navigate back from lineup screen
4. Verify next turn is FREE_THROW
5. Verify free throws remaining = 1 (1 & 1) or 2 (double bonus if 10+ fouls)
6. Verify the shooter is the player who was fouled (ball handler)

**Test 6d: Defensive Non-Shooting Foul + No Bonus → SIP**
1. Ensure defensive team has <5 team fouls (not in bonus)
2. Trigger a DEFENSIVE NON-SHOOTING FOUL that results in a foul out
3. Navigate back from lineup screen
4. Verify next turn is SIDE_INBOUND (SIP)
5. Verify SIP is for the same team (no possession flip)

**Expected Result:** Next step matches foul type and context:
- O_FOUL → SIP (with possession flip)
- D_FOUL shooting → FREE_THROW (2 or 3 shots)
- D_FOUL non-shooting + bonus → FREE_THROW (1 & 1 or 2 shots)
- D_FOUL non-shooting + no bonus → SIP (no flip)

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 7: Free Throw Shooter Identification
**Objective:** Verify correct player is identified as free throw shooter

**Test 7a: Shooting Foul**
1. Trigger a defensive shooting foul foul out
2. Note which player took the shot (this should be the shooter)
3. Navigate back from lineup screen
4. Verify the free throw turn has the correct shooter
5. Check backend logs to verify `game_state["shooter"]` is set correctly

**Test 7b: Non-Shooting Bonus Foul**
1. Trigger a defensive non-shooting foul in bonus situation
2. Note which player was fouled (ball handler)
3. Navigate back from lineup screen
4. Verify the free throw turn has the correct shooter (the fouled player)
5. Check backend logs to verify `game_state["shooter"]` is set correctly

**Expected Result:** Free throw shooter matches:
- Shooting foul: Player who took the shot
- Non-shooting bonus foul: Player who was fouled (ball handler)

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 8: Game State Preservation
**Objective:** Verify all game state data is preserved through foul out navigation

**Steps:**
1. Before foul out, note:
   - Current score (home and away)
   - Team fouls (home and away)
   - Player stats (points, rebounds, assists, etc. for key players)
   - Time remaining in quarter
   - Current quarter
   - Timeouts remaining (home and away)
2. Trigger a foul out
3. Navigate to lineup screen, then game plan, then back to court.html
4. Verify all of the above data matches exactly:
   - Scores are the same
   - Team fouls are the same
   - Player stats are the same
   - Time remaining is the same
   - Quarter is the same
   - Timeouts are the same

**Expected Result:** All game state data is preserved exactly as it was before foul out

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

### ✅ Test 9: Scoreboard Clock Display
**Objective:** Verify clock displays correctly immediately upon return from foul out

**Steps:**
1. Note the exact clock time when foul out occurs (e.g., "1:00")
2. Trigger a foul out
3. Navigate to lineup screen
4. Navigate back to court.html
5. **IMMEDIATELY** check the scoreboard clock (before any turns are processed)
6. Verify the clock shows the same time as when foul out occurred (e.g., "1:00")
7. Process one turn
8. Verify clock updates correctly (e.g., if 10 seconds elapsed, shows "0:50")

**Expected Result:** 
- Clock displays correct time immediately upon return (no delay)
- Clock does not show stale/old time
- Clock updates correctly as turns are processed

**Actual Result:** [ ] PASS [ ] FAIL
**Notes:** 

---

## Test Summary

**Total Tests:** 9
**Passed:** [ ] / 9
**Failed:** [ ] / 9

**Critical Issues Found:**
1. 
2. 
3. 

**Minor Issues Found:**
1. 
2. 
3. 

**Overall Assessment:**
[ ] All tests passed - System is working correctly
[ ] Some tests failed - Issues need to be addressed
[ ] Major issues found - System needs significant fixes

**Next Steps:**
- [ ] Fix critical issues
- [ ] Re-test failed scenarios
- [ ] Update documentation if needed
- [ ] Mark as complete when all tests pass

