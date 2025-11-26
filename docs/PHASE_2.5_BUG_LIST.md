# Phase 2.5 Bug List (Micro Items)

> **Status**: 2 of 4 bugs fixed ✅ | 2 remaining ⏳  
> **Last Updated**: January 2025

## Overview

After Phase 2.5 migration (HCO turns routed through AnimationRouter), four critical bugs were identified that needed to be fixed before the migration could be considered complete.

## Bug List

### ✅ Bug 1: Ball Detaching Post-Opening Tip (FIXED)

**Symptom**: Ball detaches from player every time after opening tip when entering HCO.

**Root Cause**: Opening tip positions ball manually, then HCO turn tries to attach via BallController, creating conflict.

**Fix Applied**:
- Modified `openingTip.js` to attach the ball to the tip winner using `BallController.attachToPlayer()`
- Set `scene._previousTurnWasOpeningTip = true` at the end of opening tip sequence
- Updated `turnAnimation.js` to check this flag and prevent hiding/re-attaching the ball at step 0 if coming from an opening tip

**Status**: ✅ **FIXED** (January 2025)

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/openingTip.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`

---

### ✅ Bug 2: HCO Passes Teleporting (FIXED)

**Symptom**: Many HCO passes teleport instead of animating smoothly. The ball appears to instantly jump from passer to receiver without the smooth arc animation.

**Root Cause**: Pass detection and `runPass()` call were missing in `ShotAnimationSystem.animatePlayerMovement()`. HCO turns resulting in shots are routed to `ShotAnimationSystem`, not `playTurnAnimation`, so the pass handling logic was missing.

**Fix Applied**:
- Created unified pass system (`passDetection.js`) with `detectPassAtStep()` and `handlePassAnimation()` functions
- Integrated pass detection into `ShotAnimationSystem.animatePlayerMovement()`
- Integrated pass detection into `turnAnimation.js` step loop
- Unified all pass animations (HCO, inbound, opening tip, DREB outlet) under the same system
- Added `scene._passHandledForNextStep` flag to prevent `updateBallOwnership` from interfering

**Status**: ✅ **FIXED** (January 2025)

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/passDetection.js` (new file)
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`
- `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js`

---

### ⏳ Bug 3: Slow Animation Speed (NEXT)

**Symptom**: Overall animation feels slow, "stuck in the mud", throwing off movement syncing.

**Potential Root Causes**:
- Routing layer adding delays
- Duration calculations incorrect
- Missing parallelization
- Network delays (but user confirmed network is fine)

**Investigation Needed**:
1. Profile animation durations - compare old vs new path
2. Check for unnecessary `await` calls or sequential operations that could be parallel
3. Verify duration calculations in `getPlayerDuration()` haven't changed
4. Check if routing layer adds any delays
5. Compare animation speeds between:
   - Old path (direct `playTurnAnimation` calls)
   - New path (AnimationRouter → ShotAnimationSystem)

**Status**: ⏳ **PENDING** - Next on the list

**Files to Investigate**:
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- `FrontEnd/static/js/phaser/animation/animateStep.js`
- `FrontEnd/static/js/phaser/animation/animation_config.js`

---

### ⏳ Bug 4: Some Passes in HCO Situations Being Skipped

**Symptom**: Some passes in HCO situations are being skipped entirely.

**Potential Root Causes**:
- Pass detection logic not catching all pass scenarios
- Timing issues with pass detection
- Pass actions not present in animation data
- Edge cases in `passDetection.js` logic

**Investigation Needed**:
1. Verify pass detection is working for all HCO pass scenarios
2. Check if pass actions are present in `turnData.animations` for skipped passes
3. Review `detectPassAtStep()` logic for edge cases
4. Compare working passes vs skipped passes to identify pattern

**Status**: ⏳ **PENDING**

**Note**: This may be related to Bug 2 (HCO Passes Teleporting) - if passes are being detected but not animated, that was Bug 2. If passes are not being detected at all, that's Bug 4.

**Files to Investigate**:
- `FrontEnd/static/js/phaser/animation/passDetection.js`
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`

---

## Progress Summary

- ✅ **Bug 1**: Ball Detaching Post-Opening Tip - **FIXED**
- ✅ **Bug 2**: HCO Passes Teleporting - **FIXED**
- ⏳ **Bug 3**: Slow Animation Speed - **NEXT**
- ⏳ **Bug 4**: Some Passes Being Skipped - **PENDING**

## Next Steps

1. **Investigate Bug 3 (Animation Speed)**:
   - Profile animation durations
   - Compare old vs new animation paths
   - Identify bottlenecks
   - Implement fixes

2. **Investigate Bug 4 (Skipped Passes)**:
   - Verify pass detection coverage
   - Check for edge cases
   - Fix any gaps in detection logic

---

## Related Documents

- `docs/PHASE_2_WORK_PLAN_SUMMARY.md` - Overall Phase 2 plan
- `docs/animation_system.md` - Animation system documentation
- `docs/UNIVERSAL_STATE_CLEARING_PATTERN.md` - State clearing patterns

