# Final End-to-End Testing Checklist

**Purpose:** Manual testing to verify full functionality before alpha launch  
**Approach:** Play through the full game flow in each mode to catch any issues  
**Estimated Time:** 1-2 hours  

---

## Testing Approach

**Manual Testing** - You'll play through the full game prototype to verify:
- All game modes work correctly
- Navigation flows correctly
- Data persists properly
- No critical errors occur
- Performance is acceptable

This is **not** automated testing - you'll manually click through and play the game as a user would.

---

## Pre-Testing Setup

- [ ] Confirm staging environment is accessible
- [ ] Clear browser cache or use incognito/private window
- [ ] Open browser console to monitor for errors
- [ ] Have Railway logs open for backend monitoring

---

## Testing Checklist by Game Mode

### 1. Single Game Mode

#### Game Creation & Setup
- [ ] Navigate to Single Game mode
- [ ] Select a team (home and away)
- [ ] Verify team selection works correctly
- [ ] Lineup screen loads without delays
- [ ] Verify all 5 positions are selectable
- [ ] Select players for lineup
- [ ] Navigate to Game Plan screen
- [ ] Modify game plan settings
- [ ] Click "Save Game Plan" - verify save succeeds
- [ ] Navigate to Playbooks screen (if applicable)
- [ ] Modify playbooks
- [ ] Click "Save Playbooks" - verify save succeeds
- [ ] Return to Lineup screen
- [ ] Verify lineup selections persisted

#### Gameplay - Play Quarter Flow
- [ ] Click "Play Quarter" button for Q1
- [ ] Verify pre-game popup appears with buttons (Play Quarter, Sim Quarter, Sim Rest of Game)
- [ ] Click "Play Quarter" to start Q1
- [ ] Game loads and plays correctly
- [ ] Quarter completes normally
- [ ] **CRITICAL:** After Q1 completes, verify "Go To Locker Room" popup appears
- [ ] Click "Go To Locker Room"
- [ ] **CRITICAL:** Verify pre-game buttons appear for Q2 (Play Quarter, Sim Quarter, Sim Rest of Game)
- [ ] **CRITICAL:** Verify game does NOT auto-start Q2
- [ ] Click "Play Quarter" to start Q2
- [ ] Game loads and continues correctly
- [ ] Repeat for Q3 and Q4
- [ ] Verify game completes correctly after Q4

#### Gameplay - Sim Quarter Flow
- [ ] Start a new game
- [ ] Click "Sim Quarter" for Q1
- [ ] Verify quarter sims quickly
- [ ] Verify pre-game buttons appear for Q2
- [ ] Click "Sim Quarter" for Q2, Q3
- [ ] For Q4, verify "Sim Quarter" button is enabled (not disabled)
- [ ] Complete Q4 and verify game ends correctly

#### Game Completion
- [ ] After final quarter, verify end-of-game popup appears
- [ ] Verify final score is correct
- [ ] Navigate to Box Score
- [ ] Verify box score data is correct
- [ ] Verify player stats are correct
- [ ] Verify team stats are correct

---

### 2. Tournament Mode

#### Tournament Setup
- [ ] Navigate to Tournament mode
- [ ] Create or select a tournament
- [ ] Select teams for tournament
- [ ] Verify tournament bracket displays correctly

#### Tournament Gameplay
- [ ] Start tournament game
- [ ] Verify Lineup screen loads with tournament context
- [ ] Set lineup and game plan
- [ ] Play or sim tournament game
- [ ] Complete tournament game
- [ ] Verify stats are saved to tournament document
- [ ] Verify tournament bracket updates correctly
- [ ] Continue tournament (play next round if applicable)
- [ ] Verify tournament completion works

#### Tournament Stats
- [ ] Navigate to Tournament Command Center
- [ ] Verify team stats display correctly
- [ ] Verify player stats display correctly
- [ ] Verify tournament standings are correct

---

### 3. Franchise Mode

#### Franchise Setup
- [ ] Navigate to Franchise mode
- [ ] Create or select a franchise
- [ ] Navigate to Franchise Command Center
- [ ] Verify franchise data displays correctly

#### Franchise Gameplay
- [ ] Start a franchise game (select week/opponent)
- [ ] Verify Lineup screen loads with franchise context
- [ ] Set lineup and game plan
- [ ] Play or sim franchise game
- [ ] Complete franchise game
- [ ] Verify stats are saved to franchise document
- [ ] Verify franchise record updates correctly
- [ ] Verify player stats accumulate correctly

#### Franchise Stats
- [ ] Navigate to Franchise Command Center
- [ ] Verify team stats display correctly
- [ ] Verify player stats display correctly
- [ ] Verify standings are correct

---

## Critical Bug Verification

### Bug #9 Fix Verification (Play Quarter Quarter Breaks)
- [ ] Start new game in any mode
- [ ] Play Q1 using "Play Quarter" button
- [ ] After Q1 completes, click "Go To Locker Room"
- [ ] **VERIFY:** Pre-game buttons appear for Q2 (Play Quarter, Sim Quarter, Sim Rest of Game)
- [ ] **VERIFY:** Game does NOT auto-start Q2
- [ ] Repeat for Q2 → Q3 and Q3 → Q4 transitions
- [ ] **VERIFY:** All quarter breaks show pre-game buttons correctly

### Performance Verification
- [ ] Lineup screen loads quickly (< 2 seconds)
- [ ] Game Plan screen loads quickly
- [ ] Playbooks screen loads quickly
- [ ] "Sim Quarter" completes quickly
- [ ] Game animations are smooth
- [ ] No noticeable delays during gameplay

---

## Data Persistence Verification

### Game Plan Persistence
- [ ] Modify game plan settings
- [ ] Click "Save Game Plan"
- [ ] Navigate away from Game Plan screen
- [ ] Return to Game Plan screen
- [ ] **VERIFY:** Settings persisted correctly

### Playbooks Persistence
- [ ] Modify playbooks
- [ ] Click "Save Playbooks"
- [ ] Navigate away from Playbooks screen
- [ ] Return to Playbooks screen
- [ ] **VERIFY:** Playbooks persisted correctly

### Stats Persistence
- [ ] Complete a game
- [ ] Refresh the page
- [ ] Navigate back to Box Score or Stats screen
- [ ] **VERIFY:** Stats are still present and correct

---

## Error Handling Verification

- [ ] Monitor browser console for errors
- [ ] Monitor Railway logs for backend errors
- [ ] Verify no critical errors appear during normal gameplay
- [ ] Test error scenarios:
  - [ ] Network interruption (if possible)
  - [ ] Invalid team selection
  - [ ] Missing lineup selections

---

## Performance Verification

- [ ] Lineup screen: < 2 seconds to load
- [ ] Game Plan screen: < 1 second to load
- [ ] Playbooks screen: < 1 second to load
- [ ] Sim Quarter: < 5 seconds for full quarter
- [ ] Game animations: Smooth, no lag
- [ ] API responses: Fast, no noticeable delays

---

## Final Verification

### Before Launch
- [ ] All game modes work correctly
- [ ] All critical bugs fixed and verified
- [ ] Performance is acceptable
- [ ] No critical errors in console or logs
- [ ] Data persistence works correctly
- [ ] Navigation flows work correctly

### Launch Readiness
- [ ] Staging environment is stable
- [ ] Production environment is ready (if deploying)
- [ ] Monitoring is set up (Railway logs, Netlify logs)
- [ ] Ready to announce launch

---

## Issues Found

**Document any issues found during testing:**

1. **Issue:** [Description]
   - **Severity:** [Critical/High/Medium/Low]
   - **Steps to Reproduce:** [List steps]
   - **Expected:** [What should happen]
   - **Actual:** [What actually happened]
   - **Status:** [Unfixed/In Progress/Fixed]

---

## Notes

- Test in staging environment first
- Use browser console to catch JavaScript errors
- Monitor Railway logs for backend errors
- Test with realistic gameplay (don't just click through)
- Verify data persists across page refreshes
- Pay special attention to quarter break navigation (Bug #9 fix)

