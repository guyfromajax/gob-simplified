# OpenDevin Debug Prompt: FCP/HCT Animation Skipping Issue

## TL;DR - Quick Summary

**Problem:** FCP/HCT setup turn animations are created but never play visually. Tweens report as "playing" but progress stays at 0, then timeout after 5 seconds. Code completes, turn transitions seamlessly to HCO. This ONLY affects FCP/HCT animations - HCO shots, fast breaks, and OREB putbacks all work fine.

**Key Clue:** FCP/HCT setup turns start immediately after `runInboundSetup()` completes (which creates many tweens). The tween manager might still be processing those tweens when FCP/HCT starts.

**What We Need:** Fix FCP/HCT animations so they play visually, or identify if this is actually a routing/state issue rather than a tweening issue.

---

## Context: What We're Trying to Accomplish

We're building a basketball game animation system. The game has different play types:
- **HCO (Half Court Offense)**: Regular half-court plays that end in shots
- **FCP (Full Court Press)**: Defensive pressure where offense tries to break the press
- **HCT (Half Court Trap)**: Defensive trap at half-court where offense tries to break the trap

**FCP/HCT Flow:**
1. Made shot → `runInboundSetup()` called inline (positions players, does inbound pass)
2. Next turn: FCP/HCT setup turn (press break/trap break sequence with skeleton animation)
3. If press is broken: Shot attempt or transition to HCO

**The Goal:** FCP/HCT setup turns should animate their skeleton sequences (player movements, passes) just like HCO shots do, then either:
- Transition to a shot attempt (if press is broken with a shot)
- Transition to HCO (if press is broken without a shot)
- Result in a foul, turnover, or steal

## The Problem

**Symptom:** FCP/HCT setup turns are **skipping their animations visually** but the code completes, then seamlessly defaults to HCO on the next turn.

**What We See:**
- FCP/HCT setup turn is detected correctly (`🚨🚨🚨 ENTERING FCP/HCT INSTANCE`)
- `playTurnAnimation()` is called with correct turn data
- Step loop starts (`🔍 [BEFORE STEP LOOP]`, `🔍 [LOOP ITERATION START]`)
- Tweens are created (`🔍 [TWEEN START CHECK] Tween created but not playing immediately`)
- Tweens timeout (`animateStep: Timeout - forcing resolve`)
- Turn completes (code-wise)
- Next turn is detected as HCO (seamlessly, no visual glitch)

**Key Clue:** This **ONLY affects FCP/HCT animations**. HCO shots, fast breaks, OREB putbacks all work fine.

**Another Clue:** FCP/HCT setup turns come **immediately after** `runInboundSetup()` completes (which creates many tweens for player positioning and inbound pass).

## Key Files and Functions

### Main Animation Entry Point
- **File:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- **Function:** `animateGameTurns()` - Main loop that processes all game turns
- **Key Logic:**
  - Lines 815-970: FCP/HCT detection and routing
  - Lines 979-1006: Pressure state clearing logic
  - FCP/HCT setup turns route to `playTurnAnimation()` (line 954)
  - FCP/HCT shot attempts route to `AnimationRouter` → `ShotAnimationSystem` (line 933)

### FCP/HCT Setup Turn Animation
- **File:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- **Function:** `playTurnAnimation()` - Handles step-by-step skeleton animations
- **Key Logic:**
  - Lines 1535-1541: Kills ball tweens at start
  - Lines 1685-1714: Ball tween cleanup before step loop (our recent fix)
  - Lines 1716-2000: Step loop that calls `animateStep()` for each step
  - Lines 1844-1900: Player movement animation via `animateStep()`

### Individual Step Animation
- **File:** `FrontEnd/static/js/phaser/animation/animateStep.js`
- **Function:** `animateStep()` - Creates Phaser tweens for player movement
- **Key Logic:**
  - Lines 35-577: Main tween creation and management
  - Lines 193-215: Valid targets filtering (removes ball if it has active tweens)
  - Lines 265-405: Tween config creation
  - Lines 419-577: Tween creation, start verification, timeout handling
  - Lines 72-93: Timeout handler (forces resolve after 5 seconds)

### Inbound Setup (Called Before FCP/HCT)
- **File:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- **Function:** `runInboundSetup()` - Positions players and does inbound pass
- **Key Logic:**
  - Lines 850-1387: Main function
  - Lines 1025-1102: Creates many tweens for defensive/offensive player positioning
  - Lines 1192-1305: Creates tweens for inbound player positioning
  - Lines 1307-1315: `await Promise.all()` - waits for all tweens to complete
  - Lines 1351-1368: Inbound pass animation
  - **Called inline from:** `ShotAnimationSystem.handleMadeShot()` (line 658)

### Shot Animation System (For FCP/HCT Shot Attempts)
- **File:** `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- **Function:** `animatePlayerMovement()` - Handles step-by-step movement for shots
- **Key Logic:**
  - Lines 281-370: Step loop similar to `playTurnAnimation()`
  - Lines 283-290: Ball tween cleanup before step loop (our recent fix)

### State Management
- **File:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- **State Variables:**
  - `scene.currentPressureType` - "FCP" | "HCT" | null
  - `scene.pressureSequenceActive` - boolean
- **Set When:** `BASELINE_INBOUND` has `next_defensive_setup === "FCP"` or `"HCT"` (line 630-640)
- **Also Set When:** `runInboundSetup()` is called inline with `pressureType` (line 871-873 in turnAnimation.js)
- **Cleared When:** Shot completes, foul occurs, turnover occurs, or transition to HCO (lines 987-1006)

## What We've Tried

1. **Ball Tween Cleanup:** Added code to kill lingering ball tweens before step loop starts (lines 1695-1714 in turnAnimation.js, lines 283-290 in ShotAnimationSystem.js)
2. **Ball Conflict Prevention:** Added code to remove ball from tween targets if it has active tweens (lines 193-215 in animateStep.js)
3. **Early Exit Fixes:** Modified early exit conditions to allow FCP/HCT turns even when state machine is in FastBreak
4. **State Tracking Refactor:** Migrated from complex flag-based detection to scene-level state tracking
5. **Pressure State Clearing Fix:** Modified to only clear state when next turn doesn't have FCP/HCT flags

**None of these fixes have resolved the issue.**

## Current Logs Show

```
🔍 [BEFORE STEP LOOP] { maxSteps: 8, will_enter_loop: true, ... }
🔍 [LOOP ITERATION START] { stepIndex: 1, maxSteps: 8, ... }
🔍 [TWEEN START CHECK] Tween created but not playing immediately {
  tweenStartedImmediately: true,      // ⚠️ Reports as playing
  tweenProgressImmediately: 0,        // ⚠️ But progress is 0
  validTargetsCount: 1,                // ✅ Only player sprite in targets
  ballInTargets: false,                // ✅ Ball correctly excluded
  ballHasActiveTween: true            // ⚠️ Ball has lingering tween
}
animateStep: Timeout - forcing resolve { 
  tweenProgress: 0,                   // ⚠️ Still 0 after 5 seconds
  tweenActive: true,                  // ⚠️ Still reports as active
  distanceToTarget: 159.96            // ✅ Real distance to travel
}
```

**Key Observations:**
- Tweens report as "playing" (`tweenStartedImmediately: true`) but progress is 0
- Ball has active tweens but is correctly excluded from targets
- Tweens timeout after 5 seconds (never progress)
- Step loop completes (code-wise) via timeouts
- **Missing:** No logs showing tween manager state (paused, timeScale, total tweens)

## Hypotheses to Test

### Hypothesis 1: Tween Manager Bottleneck
**Theory:** `runInboundSetup()` creates many tweens (10+ players + ball). When it completes, the tween manager is still processing/cleaning up those tweens. When FCP/HCT starts immediately after, new tweens are created but the manager can't process them yet.

**Test:** Check `scene.tweens.getAll().length` and `scene.tweens.isPaused()` right before FCP/HCT step loop starts. Add a delay after `runInboundSetup()` completes and see if animations work.

### Hypothesis 2: Tween Manager Not Updating
**Theory:** The tween manager is paused or not processing updates for some reason, but `tween.isPlaying()` still returns true (stale state).

**Test:** Check `scene.tweens.isPaused()`, `scene.tweens.timeScale`, and `scene.scene.isPaused()` when tweens are created. Manually call `tween.play()` or `tween.restart()` and see if that helps.

### Hypothesis 3: Timing/Race Condition
**Theory:** `runInboundSetup()` completes (Promise resolves), but Phaser's tween manager hasn't finished its internal cleanup. Starting new tweens immediately causes conflicts.

**Test:** Add `await new Promise(resolve => scene.time.delayedCall(100, resolve))` after `runInboundSetup()` completes, before FCP/HCT starts.

### Hypothesis 4: Wrong Function Being Called
**Theory:** FCP/HCT setup turns are routing to the wrong animation function, or the function is being called with incorrect parameters.

**Test:** Verify `playTurnAnimation()` is actually being called (logs show it is). Check if turn data has correct `animations` array with movement steps.

### Hypothesis 5: State Management Issue
**Theory:** Pressure state is being cleared prematurely, causing next turn to be misrouted as HCO instead of continuing FCP/HCT sequence.

**Test:** Check if `scene.pressureSequenceActive` is still `true` when FCP/HCT setup turn starts. Check if it's being cleared during the turn.

## Questions to Investigate

1. **Why do tweens report as "playing" but never progress?**
   - Is `scene.tweens.isPaused()` true?
   - Is `scene.tweens.timeScale` 0 or non-1?
   - Is `scene.scene.isPaused()` true?
   - Are there too many active tweens (`scene.tweens.getAll().length`)?
   - Is the tween manager actually processing updates?

2. **Why does this ONLY affect FCP/HCT?**
   - What's different about FCP/HCT vs HCO/fast breaks?
   - Is it the timing (immediately after `runInboundSetup()`)?
   - Is it the state (`pressureSequenceActive`)?
   - Is it the routing path?

3. **Why does it seamlessly default to HCO?**
   - Is pressure state being cleared during the turn?
   - Is the next turn correctly detected as FCP/HCT?
   - Is there a fallback routing to HCO when FCP/HCT fails?

## What We Need

**Primary Goal:** Fix FCP/HCT animations so they play visually (not just complete code-wise).

**Secondary Goals:**
- Understand why this only affects FCP/HCT
- Understand why tweens report as playing but don't progress
- Understand why it seamlessly defaults to HCO

## Action Plan - What to Do

1. **Add Diagnostic Logging:**
   ```javascript
   // In playTurnAnimation(), right before step loop starts (line ~1695)
   console.log('🔍 [TWEEN MANAGER STATE]', {
     totalTweens: scene.tweens.getAll().length,
     isPaused: scene.tweens.isPaused(),
     timeScale: scene.tweens.timeScale,
     scenePaused: scene.scene.isPaused(),
     ballActiveTweens: scene.tweens.getTweensOf(ballSprite).length
   });
   ```

2. **Test Timing Hypothesis:**
   - Add a small delay after `runInboundSetup()` completes (in `ShotAnimationSystem.handleMadeShot()` line ~669)
   - See if animations work with delay

3. **Test Tween Manager State:**
   - Check if tween manager is paused when tweens are created
   - Check if manually calling `tween.play()` or `tween.restart()` helps

4. **Verify Routing:**
   - Confirm `playTurnAnimation()` is being called with correct data
   - Check if `turnData.animations` has valid movement steps

5. **Check State Management:**
   - Log `scene.pressureSequenceActive` at start and end of FCP/HCT setup turn
   - Verify state isn't being cleared prematurely

## Additional Context

- **Phaser Version:** We're using Phaser 3 for animations
- **Tween Manager:** `scene.tweens` is the Phaser tween manager
- **Animation Pattern:** Step-synchronized animations (all players move for step N, then step N+1)
- **Ball Management:** Uses `BallController` and `ballAnimationSimple.js` for ball state
- **State Machine:** Uses a custom state machine for game states (HalfCourt, FastBreak, Inbound, etc.)

## Files to Focus On (Priority Order)

1. **`FrontEnd/static/js/phaser/animation/turnAnimation.js`**
   - `playTurnAnimation()` - Lines 1404-2487 (FCP/HCT setup turn handler)
   - `runInboundSetup()` - Lines 850-1387 (called before FCP/HCT, creates many tweens)
   - Check line 1695-1714 (ball tween cleanup before step loop)

2. **`FrontEnd/static/js/phaser/animation/animateStep.js`**
   - `animateStep()` - Lines 35-577 (creates individual step tweens)
   - Check lines 193-215 (ball conflict prevention)
   - Check lines 419-577 (tween creation and start verification)

3. **`FrontEnd/static/js/phaser/animation/animateGameTurns.js`**
   - `animateGameTurns()` - Lines 351-1374 (main turn processing loop)
   - Check lines 815-970 (FCP/HCT detection and routing)
   - Check lines 979-1006 (pressure state clearing)

4. **`FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`**
   - `handleMadeShot()` - Lines 537-675 (calls `runInboundSetup()` inline)
   - `animatePlayerMovement()` - Lines 281-370 (for FCP/HCT shot attempts)

## Expected vs Actual Behavior

### Expected Behavior ✅
**FCP/HCT Setup Turn Should:**
1. Detect as FCP/HCT correctly ✅ (working)
2. Route to `playTurnAnimation()` ✅ (working)
3. Start step loop ✅ (working)
4. **Animate each step visually** ❌ (NOT working - tweens timeout)
5. Complete and transition to next turn ✅ (working, but animation was skipped)

**What Should Happen:**
- Players should move through their skeleton steps (get open, cut, screen, etc.)
- Passes should animate between steps
- Visual animation should complete before moving to next turn
- Each step should take ~300-2000ms depending on distance

### Actual Behavior ❌
**What Actually Happens:**
- Step loop runs (code-wise) ✅
- Tweens are created ✅
- Tweens report as "playing" but progress stays at 0 ❌
- Timeouts force completion after 5 seconds ❌
- Next turn starts (seamlessly, but animation was skipped) ❌

**Success Criteria:**
- Tweens should progress from 0 to 1
- Players should move visually on screen
- Animation should complete in reasonable time (< 5 seconds per step)
- No timeouts should occur

