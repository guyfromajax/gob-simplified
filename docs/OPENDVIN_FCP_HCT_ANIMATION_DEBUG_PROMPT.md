# OpenDevin: Fix Inconsistent FCP/HCT Animation Skipping

## Objective

Fix inconsistent FCP/HCT (Full Court Press / Half Court Trap) **skeleton animation** behavior where **some instances animate correctly** but **others skip visually** and seamlessly default to HCO (Half Court Offense).

**Important:** FCP/HCT **setup turns work correctly** - players animate to their press/trap positions. The issue is with the **skeleton animation** (press break/trap break sequence) that comes **after** the setup.

## The Bug

**Symptom:** FCP/HCT skeleton animations are detected and routed correctly, but **inconsistently**:
- ✅ **Working instances:** Skeleton animations play visually (players move through press break steps, passes animate), completes normally
- ❌ **Skipped instances:** Skeleton animation tweens created but never progress (`tweenProgress: 0`), timeout after 5 seconds, code completes, seamlessly transitions to HCO

**Key Characteristics:**
- **ONLY affects FCP/HCT skeleton animations** (not setup turns, not shot attempts, not HCO, not fast breaks)
- **Setup turns work fine** - players correctly animate to FCP/HCT defensive positions
- **Inconsistent** - some skeleton animations work, some don't (suggests timing/race condition)
- **No visual glitch** - skipped animations complete code-wise, transition is seamless
- **Tweens report as "playing"** but progress stays at 0

## Critical Context

### FCP/HCT Flow
1. Made shot → `runInboundSetup()` called inline (creates 10+ tweens for player positioning + inbound pass)
2. `runInboundSetup()` completes (Promise resolves)
3. **FCP/HCT setup turn:** Players animate to press/trap positions ✅ (THIS WORKS)
4. **Immediately after setup:** FCP/HCT skeleton animation turn starts (`playTurnAnimation()`)
5. Step loop creates new tweens for skeleton animation (press break/trap break sequence)
6. **Problem:** Skeleton animation tweens don't progress (timeout after 5 seconds) ❌

### Why This Suggests Timing Issue
- FCP/HCT skeleton animation starts **immediately** after setup turn completes (which itself comes after `runInboundSetup()`)
- Setup turn creates tweens for player positioning, then skeleton animation tries to create new tweens
- **Inconsistent behavior** = sometimes tween manager is ready for skeleton animation, sometimes it's not
- Other animation types (HCO, fast breaks) don't have this immediate sequence: setup → skeleton animation

### What We've Tried (Didn't Work)
1. Kill lingering ball tweens before step loop
2. Remove ball from tween targets if it has active tweens
3. Fix early exit conditions
4. State tracking refactor
5. Pressure state clearing fixes

## Files to Focus On

1. **`FrontEnd/static/js/phaser/animation/turnAnimation.js`**
   - `playTurnAnimation()` - Line 1404 (FCP/HCT setup turn handler)
   - `runInboundSetup()` - Line 850 (creates many tweens, called before FCP/HCT)

2. **`FrontEnd/static/js/phaser/animation/animateStep.js`**
   - `animateStep()` - Line 35 (creates individual step tweens)

3. **`FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`**
   - `handleMadeShot()` - Line 537 (calls `runInboundSetup()` inline at line 658)

## What to Investigate

**Primary Hypothesis: Timing/Race Condition**
- `runInboundSetup()` completes, but Phaser's tween manager hasn't finished internal cleanup
- Starting new tweens immediately causes conflicts
- **Test:** Compare tween manager state (`scene.tweens.getAll().length`, `isPaused()`, `timeScale`) for working vs skipped instances
- **Test:** Add small delay after `runInboundSetup()` completes, see if animations work consistently

**Secondary Checks:**
- Is `scene.tweens.isPaused()` true when skeleton animation tweens are created?
- Is `scene.tweens.timeScale` 0 or non-1?
- How many active tweens exist when skeleton animation starts? (working vs skipped)
- Timing: How long between setup turn completion and skeleton animation start?
- Are setup turn tweens still active when skeleton animation starts?

## Expected Fix

**Goal:** Make ALL FCP/HCT animations work consistently (not just some).

**Approach:**
1. Compare working vs skipped skeleton animation instances to find the difference
2. Identify what makes working skeleton animations work
3. Ensure all instances have those conditions (likely: wait for setup turn tweens to complete, or wait for tween manager to be ready)

**Success Criteria:**
- All FCP/HCT skeleton animations play visually (setup already works)
- No timeouts occur
- Skeleton animation tweens progress from 0 to 1
- Consistent behavior (no more "sometimes works, sometimes doesn't")

## Current Logs (Skipped Instance)

```
🔍 [BEFORE STEP LOOP] { maxSteps: 8, will_enter_loop: true }
🔍 [LOOP ITERATION START] { stepIndex: 1, maxSteps: 8 }
🔍 [TWEEN START CHECK] Tween created but not playing immediately {
  tweenStartedImmediately: true,      // Reports as playing
  tweenProgressImmediately: 0,        // But progress is 0
  validTargetsCount: 1,
  ballInTargets: false,
  ballHasActiveTween: true
}
animateStep: Timeout - forcing resolve { 
  tweenProgress: 0,                   // Still 0 after 5 seconds
  tweenActive: true,
  distanceToTarget: 159.96
}
```

**Missing:** No logs showing tween manager state (paused, timeScale, total tweens) - need to add this.
