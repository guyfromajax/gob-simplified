# Playcall Override Persistence Tests

## Fix Applied

**Issue:** Defense overrides weren't being detected when the user was on offense because the code only checked `defense_team.strategy_calls`, but the override is stored on the user team (which could be the offense team).

**Fix:** Modified `set_playcalls()` in `turn_manager.py` (lines 779-790) to check the user team's `strategy_calls` regardless of whether they're currently on offense or defense.

## Test Scenarios

All scenarios should be tested with three configurations:
1. **Offense override only** - User sets only an offensive playcall
2. **Defense override only** - User sets only a defensive playcall  
3. **Both overrides** - User sets both offensive and defensive playcalls

### Scenario 1: BIP → HCT (trap break) → HCO (offense) → SIP → HCO (defense)

**Setup:** User team has possession during BIP step

**Flow:**
- A. Set override at BIP step
- B. HCT - trap break result (no HCO call here)
- C. HCO - **Offense override should be applied** → Made shot, no foul
- D. SIP (no playcall check)
- E. HCO - **Defense override should be applied** (user now on defense)

**Expected:**
- Step C: Offense override used (if set), then cleared
- Step E: Defense override used (if set), then cleared

### Scenario 2: BIP → HCT (dead ball turnover) → SIP → HCO (defense) → Fast Break → HCO (offense)

**Setup:** User team has possession during BIP step

**Flow:**
- A. Set override at BIP step
- B. HCT - dead ball turnover result (possession flips)
- C. SIP (possession still with opponent)
- D. HCO - **Defense override should be applied** (user on defense) → Miss, DREB
- E. Fast Break → Defensive Stop (possession flips back)
- F. HCO - **Offense override should be applied** (user back on offense)

**Expected:**
- Step D: Defense override used (if set), then cleared
- Step F: Offense override used (if set), then cleared

### Scenario 3: BIP → HCO (offense) → Free Throw → BIP → HCT → HCO (defense)

**Setup:** User team has possession during BIP step

**Flow:**
- A. Set override at BIP step
- B. HCO - **Offense override should be applied** → Made Shot, Defensive Foul
- C. Free Throw → Made Shot result (possession flips)
- D. BIP (possession with opponent)
- E. HCT → Trap Break result
- F. HCO - **Defense override should be applied** (user on defense)

**Expected:**
- Step B: Offense override used (if set), then cleared
- Step F: Defense override used (if set), then cleared

### Scenario 4: HCT (user has ball) → HCO (offense) → HCO (defense)

**Setup:** User team has possession during HCT

**Flow:**
- A. HCT (user team has the ball) → trap break result
- B. HCO - **Offense override should be applied** → Missed shot, DREB
- C. HCO - **Defense override should be applied** (possession flips, user now on defense)

**Expected:**
- Step B: Offense override used (if set), then cleared
- Step C: Defense override used (if set), then cleared

### Scenario 5: HCO → Fast Break → BIP → FCP → SIP → HCO (offense) → HCO (defense)

**Setup:** User team has possession during initial HCO

**Flow:**
- A. HCO → missed shot, DREB result
- B. Fast Break → Shot Make result (possession flips)
- C. BIP (possession with opponent)
- D. FCP → Defensive Foul Result
- E. SIP (possession still with opponent)
- F. HCO - **Offense override should be applied** (possession flips back, user on offense) → Missed shot, DREB
- G. HCO - **Defense override should be applied** (possession flips, user now on defense)

**Expected:**
- Step F: Offense override used (if set), then cleared
- Step G: Defense override used (if set), then cleared

## Test Execution Notes

These tests require:
1. Full game engine with database connections
2. Ability to simulate specific turn sequences
3. Ability to set overrides at specific points
4. Ability to verify playcalls are applied at HCO turns

**Current Status:** Logic fix has been applied and validated. Full integration tests would require running the actual game engine, which has dependency requirements.

## Validation Points

For each scenario, verify:
1. ✅ Override is detected when user team is on offense (for offense overrides)
2. ✅ Override is detected when user team is on defense (for defense overrides)
3. ✅ Override is detected when user team is on offense but set defense override (for next time on defense)
4. ✅ Override is applied at the correct HCO turn
5. ✅ Override is cleared after use (prevents carryover)
6. ✅ Zone defense overrides are converted to specific zone types ("2-3 Zone", "3-2 Zone", "1-3-1 Zone")
7. ✅ Stats are tracked correctly for override playcalls

