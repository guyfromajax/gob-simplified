# Phase 2.5 Bug Fix Plan

## Current Status
Phase 2.5 (HCO Migration) is partially complete but has introduced regressions:
- ✅ HCO turns route through `AnimationRouter`
- ❌ But still use old `playTurnAnimation()` via `handleDefault()`
- ❌ Critical bugs affecting user experience

## Critical Bugs to Fix

### Bug 1: Ball Detaching Post-Opening Tip (HIGH PRIORITY)
**Symptom**: Ball detaches from player every time after opening tip when entering HCO
**Root Cause**: Opening tip positions ball manually, then HCO turn tries to attach via BallController, creating conflict
**Fix Strategy**:
1. Ensure opening tip uses `BallController.attachToPlayer()` instead of manual positioning
2. Verify `BallController` state is properly initialized after opening tip
3. Add defensive check in first HCO turn to ensure ball is attached

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/openingTip.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (first step ball attachment)
- `FrontEnd/static/js/phaser/animation/BallController.js`

### Bug 2: HCO Passes Teleporting (HIGH PRIORITY)
**Symptom**: Many HCO passes teleport instead of animating smoothly
**Root Cause**: Likely timing/context issues in routing layer or missing pass animation triggers
**Fix Strategy**:
1. Verify `onAction` callback is being called for pass steps
2. Check if `PassAnimationSystem` is being used for HCO passes (or if it's falling back to old system)
3. Ensure pass animation duration is calculated correctly
4. Check if `animateStep` is receiving correct `nextStep` for pass detection

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (pass handling in step loop)
- `FrontEnd/static/js/phaser/animation/animateStep.js` (pass action triggering)
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` (context passing)
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js`

### Bug 3: Slow Animation Speed (MEDIUM PRIORITY)
**Symptom**: Overall animation feels slow, "stuck in the mud", throwing off movement syncing
**Root Cause**: Could be:
- Routing layer adding delays
- Duration calculations incorrect
- Missing parallelization
- Network delays (but user said network is fine)
**Fix Strategy**:
1. Profile animation durations - compare old vs new path
2. Check for unnecessary `await` calls or sequential operations that could be parallel
3. Verify duration calculations in `getPlayerDuration()` haven't changed
4. Check if routing layer adds any delays

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (duration calculations)
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js` (routing overhead)
- `FrontEnd/static/js/phaser/animation/animateStep.js` (tween durations)

### Bug 4: Skipped Passes in HCO (MEDIUM PRIORITY)
**Symptom**: Some passes in HCO situations are being skipped entirely
**Root Cause**: Similar to previous skipped step issues - state not cleared or transition logic incorrect
**Fix Strategy**:
1. Check if previous operation's state is cleared before pass step
2. Verify pass steps are being detected correctly in step loop
3. Check if `onAction` is being called for all pass steps
4. Look for early returns or condition checks that might skip passes

**Files to Check**:
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (step loop, pass detection)
- `FrontEnd/static/js/phaser/animation/animateStep.js` (pass action triggering)
- `FrontEnd/static/js/phaser/animation/BallController.js` (state clearing)

## Investigation Order

1. **Bug 1 (Ball Detaching)** - Most visible, specific root cause
2. **Bug 2 (Teleporting Passes)** - High impact on user experience
3. **Bug 4 (Skipped Passes)** - Related to Bug 2, might be same root cause
4. **Bug 3 (Slow Speed)** - Lower priority, might resolve after fixing others

## Testing Strategy

After each fix:
1. Test opening tip → HCO transition (ball attachment)
2. Test full HCO possession with multiple passes
3. Test HCO → shot transition
4. Compare animation speed to previous working version
5. Verify no passes are skipped

## Decision Point

After fixing these bugs:
- **Option A**: Continue Phase 2.5 migration (complete HCOAnimationSystem for full possessions)
- **Option B**: Revert Phase 2.5 changes and fix bugs in old system first, then re-attempt migration
- **Option C**: Pause migration entirely and focus on stabilizing current state

**Recommendation**: Fix bugs first, then reassess. If bugs are in routing layer, we may need to revert Phase 2.5 and fix the old system first.

