# FCP/HCT Animation Skip Diagnosis

## Problem
FCP/HCT animations are skipping inconsistently. Some instances animate correctly (after OREB Putback, Free Throw), while others fail (after HCO shots).

## Current Pattern (2025-01-XX)

### ✅ Working: After Made OREB Putback
- **Next turn**: `FOUL - PRESS!` (FCP/HCT setup turn)
- **Routes to**: `playTurnAnimation()`
- **Has**: `🔧 [FCP/HCT SETUP TWEEN]` → `🔧 [FCP/HCT TWEEN CLEANUP]` → skeleton animation works ✅

### ✅ Working: After Made Free Throw
- **Next turn**: `FOUL - PRESS!` (FCP/HCT setup turn)
- **Routes to**: `playTurnAnimation()`
- **Has**: `🔧 [FCP/HCT SETUP TWEEN]` → `🔧 [FCP/HCT TWEEN CLEANUP]` → skeleton animation works ✅

### ❌ Failing: After Made HCO Shot
- **Next turn**: `MISS` (FCP/HCT shot attempt) - **⚠️ BUG: Should be setup turn or skeleton animation, not shot attempt**
- **Routes to**: `ShotAnimationSystem` (via `AnimationRouter`)
- **Has**: `🔧 [FCP/HCT TWEEN CLEANUP]` but **NO** `🔧 [FCP/HCT SETUP TWEEN]` → skeleton animation fails ❌

### Root Cause Analysis

**The Issue:**
- **Setup turns** (FOUL, HCO transition) route to `playTurnAnimation()` which runs `runSetupTween()` before the step loop → ✅ works
- **Shot attempts** (MISS/MAKE) route to `ShotAnimationSystem` which should run `runSetupTween()` but it's either:
  - Not executing
  - Not completing
  - Not being waited for properly
  → ❌ fails

**Key Question:**
Why is the next turn after a made HCO shot a `MISS` (shot attempt) instead of a `FOUL - PRESS!` (setup turn) or FCP/HCT skeleton animation turn (HCO/FOUL/TURNOVER)?

**Possible Causes:**
1. **Backend Issue**: Backend is generating a shot attempt instead of an FCP/HCT setup/skeleton turn
2. **Frontend Detection Issue**: Frontend is misidentifying the FCP/HCT setup/skeleton turn as a shot attempt
3. **Missing Turn**: Backend is skipping the FCP/HCT setup turn and going straight to a shot attempt

**Debug Logging Added:**
- `🔍 [NEXT TURN AFTER MADE SHOT]` - Logs what the backend sends as the next turn after a made shot
- This will help identify if the backend is generating the wrong turn type

---

## Previous Problem (Fixed)
FCP/HCT non-shot outcomes (HCO transitions, fouls, turnovers) were skipping animations even after removing SHOT as an option.

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

