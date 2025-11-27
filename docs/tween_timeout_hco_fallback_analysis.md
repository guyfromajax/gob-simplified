# Tween Timeout → HCO Fallback Analysis

## User's Questions

1. **Are tween timeouts causing the animation skeleton to be skipped?**
2. **Why are we defaulting to HCO as the next step?**

## Analysis

### Question 1: Are Tween Timeouts Causing Skip?

**Answer: Partially, but not directly.**

**What happens when tweens timeout:**
1. `animateStep` creates tweens for player movement
2. Tweens timeout (after 5 seconds or 2x duration)
3. Timeout handler forces `resolve()` - **the Promise completes**
4. The step loop continues to the next step
5. **BUT**: The visual animation didn't happen (tweens didn't complete)

**So the code flow continues, but visually nothing happens.**

**Why tweens might timeout:**
- Tween manager is paused
- Sprites are already at target positions (zero distance, but check might fail)
- Something is blocking tween updates
- Tween is created but never starts playing

### Question 2: Why Defaulting to HCO?

**Answer: Pressure state is being cleared incorrectly.**

**The Flow:**
1. FCP/HCT turn has `result_type === "HCO"` (press break, transition to HCO)
2. `playTurnAnimation` is called
3. Tweens timeout (visual animation doesn't happen)
4. `playTurnAnimation` completes (timeouts force resolve, so function returns)
5. **Line 975-979**: `shouldClearPressureState` is calculated:
   ```javascript
   const shouldClearPressureState = 
     (turn.result_type === "MAKE" || turn.result_type === "MISS") || 
     (turn.result_type === "HCO" && !turn.fcp_shot && !turn.hct_shot) || // ⚠️ THIS IS TRUE!
     turn.fcp_foul === true || turn.hct_foul === true || 
     turn.result_type === "TURNOVER";
   ```
6. **Line 990-991**: Pressure state is cleared:
   ```javascript
   scene.currentPressureType = null;
   scene.pressureSequenceActive = false;
   ```
7. **Next turn**: Since `pressureSequenceActive === false`, it's detected as HCO instead of FCP/HCT

**The Problem:**
- FCP/HCT turns with `result_type === "HCO"` are clearing pressure state
- But this is the **current** turn's result, not the next turn
- The next turn should still be part of the FCP/HCT sequence (if it has the flags)
- But because pressure state was cleared, it's not detected as FCP/HCT

**The Fix:**
- Don't clear pressure state for FCP/HCT turns with `result_type === "HCO"`
- Only clear it when the sequence actually ends (next turn doesn't have FCP/HCT flags)
- OR: Check next turn's flags before clearing state

## Root Cause

**Two separate issues:**

1. **Tween Timeouts**: Tweens aren't completing, so visual animation doesn't happen
   - This is a symptom, not the root cause
   - Need to fix why tweens aren't starting/completing

2. **Pressure State Clearing**: State is cleared too early
   - Clears on current turn with `result_type === "HCO"`
   - Should only clear when next turn doesn't have FCP/HCT flags
   - This causes next turn to be incorrectly detected as HCO

## Solution

### Fix 1: Don't Clear Pressure State Prematurely

**Current logic (WRONG):**
```javascript
const shouldClearPressureState = 
  (turn.result_type === "HCO" && !turn.fcp_shot && !turn.hct_shot); // Clears on HCO result
```

**Fixed logic (CORRECT):**
```javascript
// Only clear if next turn doesn't have FCP/HCT flags
const nextTurn = i + 1 < turns.length ? turns[i + 1] : null;
const nextTurnIsFCPHCT = nextTurn && (
  nextTurn.fcp_shot === true || nextTurn.hct_shot === true ||
  nextTurn.fcp_foul === true || nextTurn.hct_foul === true ||
  nextTurn.next_defensive_setup === "FCP" || nextTurn.next_defensive_setup === "HCT"
);

const shouldClearPressureState = 
  (turn.result_type === "MAKE" || turn.result_type === "MISS") || 
  (turn.result_type === "HCO" && !nextTurnIsFCPHCT) || // Only clear if next turn isn't FCP/HCT
  turn.fcp_foul === true || turn.hct_foul === true || 
  turn.result_type === "TURNOVER";
```

### Fix 2: Investigate Tween Timeouts

**Need to check:**
- Why are tweens timing out?
- Are they starting but not progressing?
- Is tween manager paused?
- Are sprites already at target positions?

**Add logging to timeout handler to see:**
- `tweenActive` (is tween playing?)
- `tweenProgress` (how far did it get?)
- `distanceToTarget` (is sprite already there?)
- `tweenManagerState` (is manager paused?)

