# Playcall Override Test Tracking

This document tracks all playcall override paths that have been tested to ensure overrides persist correctly through turn transitions.

## Test Configuration

Each scenario should be tested with three configurations:
- ✅ **Offense Only** - User sets only an offensive playcall override
- ✅ **Defense Only** - User sets only a defensive playcall override
- ✅ **Both** - User sets both offensive and defensive playcall overrides

## Test Scenarios

### Scenario 1: BIP → HCT (trap break) → HCO (offense) → SIP → HCO (defense)

**Description:** User sets override at BIP, goes through HCT trap break, then two HCO turns (one on offense, one on defense after SIP).

**Flow:**
- A. Set override at BIP step
- B. HCT - trap break result (no HCO call here)
- C. HCO - **Offense override should be applied** → Made shot, no foul
- D. SIP (no playcall check)
- E. HCO - **Defense override should be applied** (user now on defense)

**Test Status:**
- [ ] Offense Only
- [ ] Defense Only
- [ ] Both Overrides

**Notes:**
- 

---

### Scenario 2: BIP → HCT (dead ball turnover) → SIP → HCO (defense) → Fast Break → HCO (offense)

**Description:** User sets override at BIP, goes through HCT dead ball turnover, then HCO on defense, then Fast Break, then HCO on offense.

**Flow:**
- A. Set override at BIP step
- B. HCT - dead ball turnover result (possession flips)
- C. SIP (possession still with opponent)
- D. HCO - **Defense override should be applied** (user on defense) → Miss, DREB
- E. Fast Break → Defensive Stop (possession flips back)
- F. HCO - **Offense override should be applied** (user back on offense)

**Test Status:**
- [ ] Offense Only
- [ ] Defense Only
- [ ] Both Overrides

**Notes:**
- 

---

### Scenario 3: BIP → HCO (offense) → Free Throw → BIP → HCT → HCO (defense)

**Description:** User sets override at BIP, goes through HCO on offense, Free Throw, then BIP, HCT, and HCO on defense.

**Flow:**
- A. Set override at BIP step
- B. HCO - **Offense override should be applied** → Made Shot, Defensive Foul
- C. Free Throw → Made Shot result (possession flips)
- D. BIP (possession with opponent)
- E. HCT → Trap Break result
- F. HCO - **Defense override should be applied** (user on defense)

**Test Status:**
- [ ] Offense Only
- [ ] Defense Only
- [ ] Both Overrides

**Notes:**
- 

---

### Scenario 4: HCT (user has ball) → HCO (offense) → HCO (defense)

**Description:** User has possession during HCT, goes through trap break, then two consecutive HCO turns (offense then defense).

**Flow:**
- A. HCT (user team has the ball) → trap break result
- B. HCO - **Offense override should be applied** → Missed shot, DREB
- C. HCO - **Defense override should be applied** (possession flips, user now on defense)

**Test Status:**
- [ ] Offense Only
- [ ] Defense Only
- [ ] Both Overrides

**Notes:**
- 

---

### Scenario 5: HCO → Fast Break → BIP → FCP → SIP → HCO (offense) → HCO (defense)

**Description:** Complex flow with multiple transitions including Fast Break, FCP, and two HCO turns.

**Flow:**
- A. HCO → missed shot, DREB result
- B. Fast Break → Shot Make result (possession flips)
- C. BIP (possession with opponent)
- D. FCP → Defensive Foul Result
- E. SIP (possession still with opponent)
- F. HCO - **Offense override should be applied** (possession flips back, user on offense) → Missed shot, DREB
- G. HCO - **Defense override should be applied** (possession flips, user now on defense)

**Test Status:**
- [ ] Offense Only
- [ ] Defense Only
- [ ] Both Overrides

**Notes:**
- 

---

## Additional Test Cases

### Edge Cases

#### Test Case: Override Set During Timeout
- [ ] Set offense override during timeout → verify applied at next HCO
- [ ] Set defense override during timeout → verify applied at next HCO when on defense
- [ ] Set both during timeout → verify both applied correctly

#### Test Case: Override Set During Quarter Break
- [ ] Set offense override at quarter break → verify applied in next quarter
- [ ] Set defense override at quarter break → verify applied in next quarter when on defense
- [ ] Set both at quarter break → verify both applied correctly

#### Test Case: Override Cleared After Use
- [ ] Set offense override → verify used once, then cleared (not used again)
- [ ] Set defense override → verify used once, then cleared (not used again)
- [ ] Set both → verify both used once, then both cleared

#### Test Case: Zone Defense Conversion
- [ ] Set "Zone" defense override → verify converts to specific zone type ("2-3 Zone", "3-2 Zone", or "1-3-1 Zone")
- [ ] Verify converted zone type is tracked in stats correctly

#### Test Case: Override Persistence Through Non-HCO Turns
- [ ] Set override → go through FREE_THROW, BASELINE_INBOUND, FCP, HCT → verify override still present at next HCO
- [ ] Verify override not cleared by non-HCO turns

---

## Test Results Summary

### Overall Status
- **Total Scenarios:** 5
- **Total Configurations:** 15 (5 scenarios × 3 configurations)
- **Tested:** 0/15
- **Passed:** 0/15
- **Failed:** 0/15

### Known Issues
- 

### Fixed Issues
- ✅ **2025-01-XX:** Fixed defense override detection when user is on offense (now checks user team's strategy_calls regardless of current offense/defense position)
- ✅ **2025-01-XX:** Fixed zone defense override tracking (added zone conversion in defense-only override path)
- ✅ **2025-01-XX:** Fixed offensive playcall override stat tracking (added tracking before early return)

---

## Testing Instructions

1. Start a game in the prototype
2. Set the appropriate override(s) in the Playcall Center
3. Play through the scenario, noting when overrides should be applied
4. Verify:
   - Override is detected and applied at the expected HCO turn
   - Override is cleared after use (check strategy_calls or verify it's not used again)
   - Stats are tracked correctly (check box score)
   - Zone defense converts to specific zone type if applicable
5. Update this document with test results

---

## Notes

- Overrides are stored in `team.strategy_calls["offense_call"]` and `team.strategy_calls["defense_call"]`
- Overrides persist until used, then are automatically cleared
- `set_playcalls()` is called during HCO turns to determine playcalls
- Overrides are checked from the user team's `strategy_calls` regardless of current offense/defense position

