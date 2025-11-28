# OpenDevin: Fix FCP/HCT Animation Skipping After Made HCO Shots

## Objective

Fix FCP/HCT (Full Court Press / Half Court Trap) skeleton animations that **skip visually** after made HCO (Half Court Offense) shots. The animations work correctly after made Free Throws, OREB putbacks, and Fast Break shots, but consistently fail after made HCO shots.

## The Bug

**Symptom:** After a made HCO shot:
1. ✅ `runInboundSetup()` is called and completes (with 50ms delay)
2. ✅ FCP/HCT state is set correctly (`scene.pressureSequenceActive = true`)
3. ✅ Next turn is detected as FCP/HCT shot attempt
4. ✅ Routes to `AnimationRouter → ShotAnimationSystem`
5. ❌ **`ShotAnimationSystem` doesn't execute** - no logs appear, tweens don't start, animation skips

**Key Characteristics:**
- **ONLY affects FCP/HCT animations after made HCO shots**
- ✅ Works after made Free Throws (has event emissions/state transitions after `runInboundSetup()`)
- ✅ Works after made OREB putbacks (has `announceFromTurnData`, `onUpdate`, `updateDebugScore` after `runInboundSetup()`)
- ✅ Works after made Fast Break shots (has `announceFromTurnData`, `onUpdate`, `updateDebugScore` after `runInboundSetup()`)
- ❌ Fails after made HCO shots (`ShotAnimationSystem.handleMadeShot()` returns immediately after `runInboundSetup()`)

## Critical Context

### Flow Comparison

| Flow | Handler | After `runInboundSetup()` | Next Turn Delay | Result |
|------|---------|---------------------------|-----------------|--------|
| **Made OREB Putback** | `handleOrebTurn()` | `announceFromTurnData()`<br>`onUpdate()`<br>`updateDebugScore()` | ✅ Natural delay | ✅ Works |
| **Made HCO Shot** | `ShotAnimationSystem.handleMadeShot()` | Returns immediately | ❌ No delay | ❌ Fails |
| **Made Free Throw** | `runFreeThrowSequence()` | Event emissions<br>State transitions | ✅ Natural delay | ✅ Works |
| **Made Fast Break Shot** | `animateFastBreakShot()` | Returns to `runFastBreakSequence()`<br>Then: `announceFromTurnData()`<br>`onUpdate()`<br>`updateDebugScore()` | ✅ Natural delay | ✅ Works |

### The Problem

**HCO Shot flow is unique:**
- After `runInboundSetup()` completes, `ShotAnimationSystem.handleMadeShot()` returns immediately
- Next turn starts right away (no additional processing delay)
- `ShotAnimationSystem.processShot()` is called but doesn't execute (no logs appear)
- Tweens are created but don't start (`tweenProgress: 0`)

**Other flows work because:**
- They have natural delays from additional processing (announcements, events, state transitions)
- This gives the tween manager time to fully process `runInboundSetup()` tweens before the next turn starts

### What We've Tried (Didn't Work)

1. ✅ Added 50ms delay after `runInboundSetup()` completes (built into `runInboundSetup()` itself)
2. ✅ Added player tween cleanup to `ShotAnimationSystem.animatePlayerMovement()` (matches `playTurnAnimation`)
3. ✅ Added ball tween cleanup before step loop
4. ✅ State tracking refactor
5. ✅ Pressure state clearing fixes

**Current State:**
- `runInboundSetup()` has built-in 50ms delay for FCP/HCT
- `ShotAnimationSystem.animatePlayerMovement()` has player tween cleanup (kills all player tweens + 50ms delay)
- But `ShotAnimationSystem.processShot()` doesn't execute (no logs appear)

## Files to Focus On

1. **`FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`**
   - `processShot()` - Line 63 (entry point, should log `🏀 SHOT ATTEMPT` but doesn't)
   - `handleMadeShot()` - Line 612 (calls `runInboundSetup()` at line 733, returns immediately)
   - `animatePlayerMovement()` - Line 289 (has cleanup, but never reached)

2. **`FrontEnd/static/js/phaser/animation/AnimationEngine.js`**
   - `handleShotAttempt()` - Line 323 (calls `this.shotSystem.processShot(turnData)`)

3. **`FrontEnd/static/js/phaser/animation/turnAnimation.js`**
   - `runInboundSetup()` - Line 850 (creates many tweens, has 50ms delay for FCP/HCT)

## What to Investigate

**Primary Hypothesis: `ShotAnimationSystem.processShot()` Not Executing**
- `AnimationEngine.handleShotAttempt()` calls `this.shotSystem.processShot(turnData)`
- But no logs appear from `processShot()` (should log `🏀 SHOT ATTEMPT` at line 67)
- This suggests either:
  1. `processShot()` isn't being called (but we see the log from `AnimationEngine`)
  2. `processShot()` is failing silently before the first log
  3. `processShot()` is being called but execution is blocked somehow

**Debugging Steps:**
1. Add logging at the very start of `processShot()` to confirm it's being called
2. Check if `this.shotSystem` is null/undefined in `AnimationEngine`
3. Check if `turnData` is valid when passed to `processShot()`
4. Check if there's an error being caught and swallowed
5. Compare working flows (Free Throw, OREB, Fast Break) to see what's different

**Secondary Hypothesis: Tween Manager Not Ready**
- Even with cleanup and delays, tween manager might not be ready
- Check tween manager state when `processShot()` is called:
  - `scene.tweens.getAll().length`
  - `scene.tweens.isPaused()`
  - `scene.tweens.timeScale`
- Compare to working flows

## Expected Fix

**Goal:** Make FCP/HCT animations work consistently after made HCO shots.

**Approach:**
1. Confirm `processShot()` is being called (add logging)
2. If called but not executing, find what's blocking it
3. If executing but tweens not starting, investigate tween manager state
4. Ensure consistent behavior with other flows (add natural delay or ensure tween manager is ready)

**Success Criteria:**
- `ShotAnimationSystem.processShot()` executes (logs appear)
- FCP/HCT skeleton animations play visually after made HCO shots
- No timeouts occur
- Consistent behavior (matches Free Throw, OREB, Fast Break flows)

## Current Logs (Failed Instance)

```
🎯🎯🎯 SHOT MADE BY: CARLTON BONNER 🎯🎯🎯
🏀 [FCP/HCT MADE SHOT] Calling runInboundSetup (matching HCO approach)
🔧 [FCP/HCT POST-INBOUND DELAY] Waiting 50ms for tween manager to settle
🔧 [FCP/HCT POST-INBOUND DELAY COMPLETE] Tween manager state after delay
✅ [playTurnAnimation - FCP/HCT COMPLETE]
✅ [FCP/HCT ANIMATION COMPLETE]

🎬 Turn 14: MISS - [Base Post Play] ...
🚨🚨🚨 ENTERING FCP/HCT INSTANCE 🚨🚨🚨
🎬 [FCP/HCT SHOT ATTEMPT] Routing through AnimationRouter → ShotAnimationSystem
🎬 AnimationRouter: Starting turn processing
🎯 AnimationRouter: Processing turn directly (no state machine)
🚀 AnimationRouter: Calling animationEngine.processTurn
🎬 AnimationEngine: Processing turn MISS
🎯 AnimationEngine: Using handler for MISS
AnimationEngine: Handling shot attempt with new ShotAnimationSystem
```

**Missing:** No logs from `ShotAnimationSystem.processShot()` - should see `🏀 SHOT ATTEMPT` log but don't.
