# FCP/HCT Animation Skip Diagnosis

## Problem
FCP/HCT non-shot outcomes (HCO transitions, fouls, turnovers) are skipping animations even after removing SHOT as an option.

## Root Cause Analysis

### 1. Routing Logic (✅ CORRECT)

**FCP/HCT Non-Shot Outcomes** route through `playTurnAnimation()`:
- **Location**: `animateGameTurns.js` lines 935-970
- **Condition**: `isFCPHCT === true` AND `isFCPHCTShotAttempt === false`
- **Action**: Calls `playTurnAnimation()` with turn data

**This routing is correct.**

---

### 2. Early Exit in playTurnAnimation (❌ PROBLEM)

**Location**: `turnAnimation.js` lines 1511-1518

```javascript
if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak) {
  console.log("⚠️ playTurnAnimation: Skipping - state is FastBreak and turn is not HCO", {
    result_type: turnData.result_type,
    fast_break: turnData.fast_break,
    has_animations: !!turnData.animations?.length
  });
  return; // ❌ EARLY EXIT - SKIPS ANIMATION!
}
```

**The Problem:**
- `isHCOAfterFastBreak` is defined as (line 1506-1509):
  ```javascript
  const isHCOAfterFastBreak = !turnData.fast_break && 
                               (turnData.result_type === "MAKE" || turnData.result_type === "MISS") &&
                               turnData.animations?.length > 0 &&
                               scene.stateMachine?.is(States.FastBreak);
  ```

- **This only allows MAKE/MISS turns to proceed if state is FastBreak**
- **FCP/HCT turns with `result_type === "HCO"`, `"FOUL"`, `"STEAL"`, `"DEAD_BALL"` will be SKIPPED if state is FastBreak!**

**Example Scenario:**
1. Fast break occurs → state machine transitions to `FastBreak`
2. Fast break ends (defensive stop or shot)
3. Next turn: FCP/HCT with `result_type === "HCO"` (press break, transition to HCO)
4. `playTurnAnimation()` is called
5. **State machine is still in FastBreak** (or hasn't transitioned yet)
6. `isHCOAfterFastBreak === false` (because result_type is "HCO", not "MAKE"/"MISS")
7. **Early return → animation skipped!**

---

### 3. Additional Early Exit (❌ PROBLEM)

**Location**: `turnAnimation.js` lines 1594-1608

```javascript
if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
  // ✅ DEBUG: Log if FCP/HCT is being skipped due to skipToEnd or FastBreak state
  if (isFCPHCT) {
    const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
    console.error('❌ [FCP/HCT SKIPPED - EARLY EXIT]', {
      turn_index: turnIndex,
      pressureType,
      result_type: turnData.result_type,
      skipToEnd: scene.skipToEnd,
      isFastBreak: scene.stateMachine?.is(States.FastBreak),
      reason: scene.skipToEnd ? 'skipToEnd flag' : 'FastBreak state'
    });
  }
  return; // ❌ EARLY EXIT - SKIPS ANIMATION!
}
```

**The Problem:**
- This checks `scene.stateMachine?.is(States.FastBreak)` WITHOUT any exception for FCP/HCT turns
- **FCP/HCT turns will be skipped if state is FastBreak, regardless of result_type**

---

### 4. Step Loop Early Exit (❌ PROBLEM)

**Location**: `turnAnimation.js` lines 1669-1683

```javascript
for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++) {
  if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
    // ✅ DEBUG: Log early exit for FCP/HCT
    if (isFCPHCT) {
      const pressureType = turnData.fcp_shot || turnData.fcp_foul || turnData.next_defensive_setup === "FCP" ? 'FCP' : 'HCT';
      console.warn('⚠️ [FCP/HCT STEP LOOP EARLY EXIT]', {
        turn_index: turnIndex,
        pressureType,
        stepIndex,
        maxSteps,
        skipToEnd: scene.skipToEnd,
        isFastBreak: scene.stateMachine?.is(States.FastBreak)
      });
    }
    break; // ❌ BREAKS OUT OF LOOP - SKIPS STEPS!
  }
  // ... rest of step loop
}
```

**The Problem:**
- Even if the function doesn't return early, the step loop will break if state is FastBreak
- **FCP/HCT skeleton animations won't execute**

---

## Solution

### Fix 1: Allow FCP/HCT turns to proceed even if state is FastBreak

**Location**: `turnAnimation.js` line 1511

**Current:**
```javascript
if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak) {
  return;
}
```

**Fixed:**
```javascript
// ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
// FCP/HCT turns can occur after fast breaks (e.g., press break after fast break shot)
const isFCPHCTTurn = turnData.fcp_shot === true || turnData.hct_shot === true ||
                     turnData.fcp_foul === true || turnData.hct_foul === true ||
                     turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                     scene.pressureSequenceActive;

if (scene.stateMachine?.is(States.FastBreak) && !isHCOAfterFastBreak && !isFCPHCTTurn) {
  console.log("⚠️ playTurnAnimation: Skipping - state is FastBreak and turn is not HCO or FCP/HCT", {
    result_type: turnData.result_type,
    fast_break: turnData.fast_break,
    has_animations: !!turnData.animations?.length
  });
  return;
}
```

### Fix 2: Allow FCP/HCT turns in second early exit

**Location**: `turnAnimation.js` line 1594

**Current:**
```javascript
if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
  // ... log and return
}
```

**Fixed:**
```javascript
// ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
const isFCPHCTTurn = turnData.fcp_shot === true || turnData.hct_shot === true ||
                     turnData.fcp_foul === true || turnData.hct_foul === true ||
                     turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                     scene.pressureSequenceActive;

if (scene.skipToEnd || (scene.stateMachine?.is(States.FastBreak) && !isFCPHCTTurn)) {
  // ... log and return
}
```

### Fix 3: Allow FCP/HCT turns in step loop

**Location**: `turnAnimation.js` line 1669

**Current:**
```javascript
if (scene.skipToEnd || scene.stateMachine?.is(States.FastBreak)) {
  break;
}
```

**Fixed:**
```javascript
// ✅ FIX: Allow FCP/HCT turns to proceed even if state is FastBreak
const isFCPHCTTurn = turnData.fcp_shot === true || turnData.hct_shot === true ||
                     turnData.fcp_foul === true || turnData.hct_foul === true ||
                     turnData.next_defensive_setup === "FCP" || turnData.next_defensive_setup === "HCT" ||
                     scene.pressureSequenceActive;

if (scene.skipToEnd || (scene.stateMachine?.is(States.FastBreak) && !isFCPHCTTurn)) {
  break;
}
```

---

## Why This Happens

1. **State Machine Persistence**: After a fast break, the state machine may still be in `FastBreak` state
2. **FCP/HCT Can Follow Fast Breaks**: After a fast break shot (made or missed), the other team may set up FCP/HCT pressure
3. **No Exception for FCP/HCT**: The early exit checks don't account for FCP/HCT turns, which are valid even when state is FastBreak

---

## Testing

After implementing fixes, verify:
1. ✅ FCP/HCT HCO transitions animate correctly
2. ✅ FCP/HCT fouls animate correctly
3. ✅ FCP/HCT turnovers/steals animate correctly
4. ✅ Fast break → FCP/HCT sequence works correctly
5. ✅ State machine transitions correctly after FCP/HCT animations

