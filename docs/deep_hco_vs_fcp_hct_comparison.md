# Deep Comparison: HCO Shots vs FCP/HCT Shots

## Critical Question: Why Does One Work and the Other Doesn't?

Based on the logs, FCP/HCT shots:
1. ✅ Are detected correctly
2. ✅ Route through AnimationRouter → ShotAnimationSystem
3. ✅ Skip ball attachment (correctly)
4. ✅ Detect and call pass animation
5. ❌ **But then stop - no step loop execution logs**

---

## Execution Flow Comparison

### Phase 1: Detection & Routing

**HCO Shot:**
```
animateGameTurns.js:1222
→ isHCO = !turn.fast_break && !isFCPHCTTurn && (MAKE || MISS)
→ Routes to: animationRouter.processTurn(turn)
```

**FCP/HCT Shot:**
```
animateGameTurns.js:882
→ isFCPHCTShotAttempt = scene.pressureSequenceActive && (MAKE || MISS) && (fcp_shot || hct_shot || ...)
→ Routes to: animationRouter.processTurn(turn)
```

**Status:** ✅ IDENTICAL - Both route through AnimationRouter

---

### Phase 2: AnimationRouter Processing

**Both paths:**
```
AnimationRouter.processTurn()
→ prepareTurnForAnimation() (sets scene.currentTurn, turn.index)
→ animationEngine.processTurn()
→ determineHandler() → routes to SHOT_ATTEMPT
→ handleShotAttempt() → shotSystem.processShot()
```

**Status:** ✅ IDENTICAL - Same routing path

---

### Phase 3: ShotAnimationSystem.processShot()

**Both paths:**
```
ShotAnimationSystem.processShot()
→ validateShotData()
→ executeCompleteShotSequence()
```

**Status:** ✅ IDENTICAL - Same entry point

---

### Phase 4: executeCompleteShotSequence() - INITIALIZATION

**HCO Shot:**
```javascript
// Line 122: initializeBallHolderState(scene)
// Line 125-128: Reset flags (passInFlight, rebounderId)
// Line 131-134: Clear ball state (if not from inbound/tip)
// Line 142-148: Calculate maxSteps
// Line 151: runSetupTween() - Move players to step 0
// Line 155-163: updateBallOwnership() at step 0
// Line 174-177: Attach ball at step 0 (if not from inbound/tip)
```

**FCP/HCT Shot:**
```javascript
// Line 122: initializeBallHolderState(scene)
// Line 125-128: Reset flags (passInFlight, rebounderId)
// Line 131-134: Clear ball state (if not from inbound/tip)
// Line 142-148: Calculate maxSteps
// Line 151: runSetupTween() - Move players to step 0
// Line 155-163: updateBallOwnership() at step 0
// Line 174-177: Attach ball at step 0 (if not from inbound/tip)
```

**Status:** ✅ IDENTICAL - Same initialization

**BUT WAIT:** The logs show:
- "🏀 ShotAnimationSystem: Skipping step 0 ball attachment - previous turn was a shot"
- "🏀 ShotAnimationSystem: Skipping step 0 ball attachment" (fromInbound check)

This means:
- `previousTurnWasShot === true` (previous turn was a shot)
- `fromInbound === true` (coming from inbound)

**Question:** Why is `previousTurnWasShot === true` for FCP/HCT shots? They come after BASELINE_INBOUND, not after a shot!

---

### Phase 5: animatePlayerMovement() - THE STEP LOOP

**HCO Shot:**
```javascript
// Line 284: for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++)
// Line 288: updateBallOwnership() for this step
// Line 296: detectPassAtStep() - detect passes
// Line 298-340: Loop through animations, create animateStep() promises
// Line 342: await Promise.all(promises) - Wait for all player movements
// Line 346-350: handlePassAnimation() - Handle pass if detected
// Line 353-355: handleShotAtStep() - Handle shot if detected
```

**FCP/HCT Shot:**
```javascript
// Line 284: for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++)
// Line 288: updateBallOwnership() for this step
// Line 296: detectPassAtStep() - detect passes
// Line 298-340: Loop through animations, create animateStep() promises
// Line 342: await Promise.all(promises) - Wait for all player movements
// Line 346-350: handlePassAnimation() - Handle pass if detected
// Line 353-355: handleShotAtStep() - Handle shot if detected
```

**Status:** ✅ IDENTICAL - Same step loop logic

**BUT:** The logs show NO step loop execution logs! No "🎬 [FCP/HCT STEP EXECUTING]" logs appear.

---

## Key Differences Found

### 1. Scene State Before Turn

**HCO Shot:**
- Previous turn: Usually DREB, HCO setup, or other non-shot turn
- `scene._previousTurnWasShot`: Usually `false`
- `scene._previousTurnWasInbound`: Usually `false`
- `scene.pressureSequenceActive`: `false`
- Players: Already positioned from previous play

**FCP/HCT Shot:**
- Previous turn: **BASELINE_INBOUND** (with FCP/HCT setup)
- `scene._previousTurnWasShot`: **`true`** ❓ (Why? Previous was inbound, not shot!)
- `scene._previousTurnWasInbound`: **`true`** ✅ (Correct - previous was inbound)
- `scene.pressureSequenceActive`: **`true`** ✅ (Correct - FCP/HCT active)
- Players: Just positioned by `runInboundSetup()` with FCP/HCT defensive positions

**CRITICAL QUESTION:** Why is `_previousTurnWasShot === true` when the previous turn was BASELINE_INBOUND, not a shot?

---

### 2. maxSteps Calculation

**HCO Shot:**
```javascript
const maxSteps = turnData.animations && turnData.animations.length > 0
  ? Math.max(
      ...turnData.animations
        .filter(anim => anim.movement && Array.isArray(anim.movement))
        .map(anim => anim.movement.length)
    )
  : 0;
```

**FCP/HCT Shot:**
```javascript
// Same calculation
const maxSteps = turnData.animations && turnData.animations.length > 0
  ? Math.max(
      ...turnData.animations
        .filter(anim => anim.movement && Array.isArray(anim.movement))
        .map(anim => anim.movement.length)
    )
  : 0;
```

**Status:** ✅ IDENTICAL - Same calculation

**CRITICAL QUESTION:** What is `maxSteps` for FCP/HCT shots? If it's 0 or 1, the loop won't execute!

---

### 3. Step Loop Execution

**HCO Shot:**
- Loop executes: `for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++)`
- If `maxSteps = 3`, loop runs for `stepIndex = 1, 2`
- Logs show step execution

**FCP/HCT Shot:**
- Loop should execute: `for (let stepIndex = 1; stepIndex < maxSteps; stepIndex++)`
- **BUT:** No logs appear, suggesting loop doesn't execute
- **Possible reasons:**
  1. `maxSteps <= 1` (loop condition fails immediately)
  2. `this.scene.skipToEnd === true` (early return)
  3. Loop executes but tweens don't start (timeout issues)

---

### 4. Missing Debug Logs

**playTurnAnimation has:**
```javascript
// Line 1651-1666: Logs FCP/HCT step loop start with maxSteps, will_execute, loop_range
// Line 1686-1696: Logs FCP/HCT step execution for ALL steps
// Line 1859-1870: Logs FCP/HCT step completion
```

**ShotAnimationSystem does NOT have:**
- No step loop start log
- No step execution log
- No step completion log

**This makes debugging impossible!** We can't see if the loop is executing.

---

### 5. updateBallOwnership() Call Order

**playTurnAnimation:**
```javascript
// Line 1719-1732: updateBallOwnership() called INSIDE step loop
// Line 1723: Skips if passHappeningAtThisStep || scene.passInFlight
// Line 1733-1737: Clears passInFlight flag after skipping
```

**ShotAnimationSystem:**
```javascript
// Line 288: updateBallOwnership() called INSIDE step loop
// BUT: No check for passHappeningAtThisStep or passInFlight!
// This could cause conflicts if a pass just completed
```

**KEY DIFFERENCE:** `ShotAnimationSystem` doesn't skip `updateBallOwnership()` when a pass is happening or just completed!

---

### 6. Pass Handling

**playTurnAnimation:**
```javascript
// Line 1873-1896: Handle passes AFTER Promise.all(promises)
// Line 1881-1886: Uses handlePassAnimation() utility
// Line 1887-1896: Logs when passInfo is null but pass action exists
```

**ShotAnimationSystem:**
```javascript
// Line 346-350: Handle passes AFTER Promise.all(promises)
// Line 346-350: Uses handlePassAnimation() utility
// BUT: No logging when passInfo is null
```

**Status:** ✅ IDENTICAL - Same pass handling

**BUT:** The logs show "🏀 [PASS ANIMATION] Calling runPass" which means a pass was detected and is being handled. But then... nothing. The step loop doesn't continue.

---

## Root Cause Hypothesis

**The problem is likely one of these:**

1. **maxSteps is 0 or 1** - Loop doesn't execute because `stepIndex < maxSteps` fails immediately
2. **Tweens aren't starting** - `animateStep()` creates tweens but they don't start, causing timeouts
3. **updateBallOwnership() conflicts** - Called during/after pass, causing ball state conflicts
4. **Missing debug logs** - We can't see what's happening in the step loop

**Most likely:** `maxSteps <= 1` or tweens aren't starting because of ball state conflicts from `updateBallOwnership()` being called at the wrong time.

---

## What We Need to Check

1. **What is `maxSteps` for FCP/HCT shots?** - Add logging to see the value
2. **Does the step loop execute?** - Add logging at the start of the loop
3. **Do tweens start?** - Check if `animateStep()` actually creates and starts tweens
4. **Is `updateBallOwnership()` causing conflicts?** - Check if it's being called during/after passes
5. **What is the turn data structure?** - Compare HCO vs FCP/HCT turn data to see if animations array is different

---

## Next Steps

1. Add comprehensive debug logging to `ShotAnimationSystem.animatePlayerMovement()` to match `playTurnAnimation`
2. Check `maxSteps` value for FCP/HCT shots
3. Check if `updateBallOwnership()` should skip when passes are happening (like `playTurnAnimation` does)
4. Compare actual turn data structures between working HCO shots and failing FCP/HCT shots

