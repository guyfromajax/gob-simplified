# Pressure State Clearing Scenarios

## What Happens Without the Fallback to HCO?

### Scenario 1: FCP/HCT Turn → Next Turn is Also FCP/HCT ✅

**Example:** Press break → Press break (multiple turns in sequence)

**Before Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Clears pressure state ❌
- Turn 2: Should be FCP but detected as HCO (incorrect) ❌

**After Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Checks next turn
- Next turn has FCP flags → **Keeps pressure state active** ✅
- Turn 2: Correctly detected as FCP ✅

---

### Scenario 2: FCP/HCT Turn → Next Turn is Regular HCO ✅

**Example:** Press break → Regular half court offense shot

**Before Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Clears pressure state
- Turn 2: Detected as HCO (correct, but for wrong reason) ✅

**After Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Checks next turn
- Next turn has NO FCP/HCT flags → **Clears pressure state** ✅
- Turn 2: Correctly detected as HCO ✅

---

### Scenario 3: FCP/HCT Shot Attempt ✅

**Example:** Press break → Shot attempt (MAKE/MISS)

**Before Fix:**
- Turn 1: FCP shot → Clears pressure state ✅
- Turn 2: Detected as inbound/rebound (correct) ✅

**After Fix:**
- Turn 1: FCP shot → Clears pressure state ✅
- Turn 2: Detected as inbound/rebound (correct) ✅
- **No change** - shot attempts always clear state

---

### Scenario 4: FCP/HCT Foul or Turnover ✅

**Example:** Press break → Foul or turnover

**Before Fix:**
- Turn 1: FCP foul/turnover → Clears pressure state ✅
- Turn 2: Detected as inbound/free throw (correct) ✅

**After Fix:**
- Turn 1: FCP foul/turnover → Clears pressure state ✅
- Turn 2: Detected as inbound/free throw (correct) ✅
- **No change** - fouls/turnovers always clear state

---

### Scenario 5: Edge Case - No Next Turn (End of Quarter/Game) ✅

**Example:** Last turn of quarter is FCP/HCT

**Before Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Clears pressure state
- No next turn → State is cleared (correct) ✅

**After Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Checks next turn
- `nextTurn === null` → `nextTurnIsFCPHCT === false` → **Clears pressure state** ✅
- **No change** - edge case handled correctly

---

### Scenario 6: Edge Case - Backend Sends HCO Without Flags ⚠️

**Example:** Backend sends turn with `result_type === "HCO"` but no FCP/HCT flags

**Before Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Clears pressure state
- Turn 2: Has no flags → Detected as HCO (might be incorrect if it should be FCP) ⚠️

**After Fix:**
- Turn 1: FCP with `result_type === "HCO"` → Checks next turn
- Next turn has NO FCP/HCT flags → **Clears pressure state** ✅
- Turn 2: Detected as HCO (correct, since it has no flags) ✅

**Note:** If backend should have sent FCP/HCT flags but didn't, that's a backend issue, not frontend.

---

## Summary

**The fix ensures:**
1. ✅ Pressure state persists across multiple FCP/HCT turns in a sequence
2. ✅ Pressure state clears when sequence actually ends (next turn isn't FCP/HCT)
3. ✅ Shot attempts, fouls, and turnovers always clear state (unchanged)
4. ✅ Edge cases (no next turn, missing flags) are handled correctly

**The only potential issue:**
- If backend sends a turn that should be FCP/HCT but doesn't have the flags, it will be detected as HCO
- This is a backend data issue, not a frontend routing issue
- The frontend correctly uses the flags it receives

**Result:** The fix prevents premature state clearing while still correctly clearing when the sequence ends.

