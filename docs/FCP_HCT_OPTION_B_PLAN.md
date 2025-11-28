# Option B: Route All FCP/HCT Through ShotAnimationSystem

## Goal
Route ALL FCP/HCT turns (shot attempts AND non-shot outcomes) through `ShotAnimationSystem`, removing the problematic `playTurnAnimation()` path for FCP/HCT.

## Why This Works
- HCO shots work perfectly through `ShotAnimationSystem`
- FCP/HCT has identical structure: skeleton animation → outcome (shot, foul, turnover, HCO transition)
- Uses proven, working code path
- Removes complexity of dual paths

## Current State

### What Works
- HCO shots: `AnimationRouter` → `ShotAnimationSystem` ✅
- FCP/HCT shot attempts: `AnimationRouter` → `ShotAnimationSystem` ✅ (when routed correctly)

### What Doesn't Work
- FCP/HCT non-shot outcomes: `playTurnAnimation()` ❌ (tweens not starting)

## Implementation Plan

### Step 1: Extend ShotAnimationSystem to Handle Non-Shot Outcomes

**File:** `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`

**Changes:**
1. In `executeCompleteShotSequence()`:
   - After skeleton animation completes, check if there's a shot
   - If `result_type === "MAKE"` or `"MISS"` → handle shot (existing logic)
   - If `result_type === "FOUL"` → handle foul outcome
   - If `result_type === "TURNOVER"` → handle turnover outcome
   - If `result_type === "HCO"` → handle HCO transition (press broken)

2. Add outcome handlers:
   - `handleFoulOutcome()` - for FCP/HCT fouls
   - `handleTurnoverOutcome()` - for FCP/HCT turnovers
   - `handleHCOTransition()` - for FCP/HCT press break outcomes

**Key Point:** The skeleton animation is identical - only the outcome handling differs.

### Step 2: Route All FCP/HCT Through AnimationRouter

**File:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

**Changes:**
1. Remove the `playTurnAnimation()` path for FCP/HCT (lines 946-980)
2. Route ALL FCP/HCT turns through `AnimationRouter`:
   ```javascript
   if (isFCPHCT) {
     turn.index = i;
     await animationRouter.processTurn(turn);
     continue;
   }
   ```

3. Keep the improved detection logic (uncommitted changes are good)

### Step 3: Update AnimationEngine to Route FCP/HCT to SHOT_ATTEMPT

**File:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

**Changes:**
1. Modify `determineHandler()` to route FCP/HCT turns to `SHOT_ATTEMPT` handler
2. Even if `result_type !== "MAKE" || "MISS"`, if it's FCP/HCT, route to `SHOT_ATTEMPT`
3. `ShotAnimationSystem` will handle the outcome appropriately

**Alternative:** Create a new `FCP_HCT` handler that routes to `ShotAnimationSystem`, but that adds complexity. Better to use existing `SHOT_ATTEMPT` handler.

### Step 4: Remove FCP/HCT-Specific Code from playTurnAnimation

**File:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`

**Changes:**
1. Remove FCP/HCT cleanup code (lines 1719-1785) - no longer needed
2. Remove FCP/HCT detection in `playTurnAnimation()` - FCP/HCT won't route here anymore
3. Keep the function for other use cases (HCO setup turns, etc.)

### Step 5: Simplify State Management

**File:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

**Changes:**
1. Keep state tracking for detection (`scene.currentPressureType`, `scene.pressureSequenceActive`)
2. But we don't need it for routing anymore - all FCP/HCT goes through same path
3. State is still useful for:
   - Detecting FCP/HCT turns
   - Clearing state when sequence ends

## Benefits

1. **Uses Working Code Path**: `ShotAnimationSystem` works perfectly for HCO
2. **Removes Problematic Path**: No more `playTurnAnimation()` for FCP/HCT
3. **Unified System**: All FCP/HCT outcomes use same animation system
4. **Simpler**: One path instead of two
5. **Proven**: Based on working HCO implementation

## Testing Checklist

- [ ] FCP/HCT shot attempts animate correctly
- [ ] FCP/HCT fouls animate correctly
- [ ] FCP/HCT turnovers animate correctly
- [ ] FCP/HCT press break (HCO transition) animates correctly
- [ ] State clears correctly when sequence ends
- [ ] Regular HCO shots still work
- [ ] No regressions in other animation paths

## Rollback Plan

If this doesn't work:
1. Revert changes to `animateGameTurns.js` (keep detection improvements)
2. Revert changes to `ShotAnimationSystem.js`
3. Revert changes to `AnimationEngine.js`
4. Consider Option A or Option C (revert to previous working version)

## Files to Modify

1. `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` - Add outcome handlers
2. `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - Route all FCP/HCT through AnimationRouter
3. `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - Route FCP/HCT to SHOT_ATTEMPT handler
4. `FrontEnd/static/js/phaser/animation/turnAnimation.js` - Remove FCP/HCT-specific code (optional cleanup)

## Estimated Complexity

- **Low-Medium**: Most code already exists in `ShotAnimationSystem`
- **Main Work**: Adding outcome handlers (foul, turnover, HCO transition)
- **Risk**: Low - we're using proven code path

