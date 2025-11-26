# Phase 2 Work Plan Summary

> **Recovered from**: `PHASE_2_INCREMENTAL_MIGRATION_PLAN.md` (commit 73228c9c)  
> **Status**: Phase 2.1-2.5 Complete ✅ | Phase 2.6 In Progress ⏳

## Overview

Phase 2 is an incremental migration strategy to route all animations through `AnimationRouter` as a single entry point, replacing scattered `playTurnAnimation()` calls with a unified architecture.

## Complete Phase Breakdown

### Phase 2.1: Enhance Context Passing (Foundation) ✅ **COMPLETE**

**Goal**: Ensure `AnimationRouter` and `AnimationEngine` can pass all required context to `playTurnAnimation`.

**Tasks Completed**:
- ✅ Enhanced `AnimationRouter.processTurn()` context object
  - Added `turnIndex` (from `turn.index` or loop index)
  - Added `onUpdate` callback
  - Added `simData` reference
  - Ensured `scene.currentTurn` is set before routing
  - Ensured `turn.index` is set on turn object
- ✅ Enhanced `AnimationEngine.processTurn()` context handling
  - Accepts and passes through `turnIndex`, `onUpdate`, `simData`
  - Context passed to all handler methods
  - Updated `handleDefault()` to pass full context to `playTurnAnimation`

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`

---

### Phase 2.2: Extract Pre-Animation Setup (Foundation) ✅ **COMPLETE**

**Goal**: Extract the pre-animation setup logic into a reusable function.

**Tasks Completed**:
- ✅ Created `prepareTurnForAnimation(turn, scene, turnIndex)` function
  - Sets `scene.currentTurn = turnIndex`
  - Sets `turn.index = turnIndex`
  - Calls `updatePlaycallDisplay(turn, ...)`
  - Calls `updateStrategyBars(turn, ...)`
  - Calls `updatePlaycallCenter(turn, ...)` (includes lean score parsing)
  - Calls `announceFromTurnData(turn, 'start', ...)`
  - Calculates and stores `scene._leanScoreToAnimate` and `scene._leanAnimationStep`
- ✅ Created `finalizeTurnAfterAnimation(turn, scene, onUpdate, possessionId)` function
  - Sets `scene._previousTurnWasShot = true` if turn was a shot
  - Calls `onUpdate(turn)` if provided
  - Calls `updateDebugScore(turn, ...)`
  - Calls `announceFromTurnData(turn, 'end', ...)`

**Files Created/Modified**:
- `FrontEnd/static/js/phaser/animation/turnPreparation.js` (new file)
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

---

### Phase 2.3: Integrate Pre/Post Setup into AnimationRouter ✅ **COMPLETE**

**Goal**: Make `AnimationRouter` handle pre-animation setup and post-animation cleanup.

**Tasks Completed**:
- ✅ Updated `AnimationRouter.processTurn()`
  - Calls `prepareTurnForAnimation()` at the start
  - Calls `finalizeTurnAfterAnimation()` at the end (in `finally` block)
  - Ensures `turnIndex` is available (from `turn.index` or parameter)
- ✅ Updated `AnimationEngine` handlers
  - Ensured they don't duplicate pre/post setup
  - Documented that setup is handled by `AnimationRouter`

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

---

### Phase 2.4: Migrate FCP/HCT Foul Turns (First Migration) ✅ **COMPLETE** (December 2024)

**Goal**: Migrate the simplest turn type first to validate the routing path.

**Tasks Completed**:
- ✅ Updated `animateGameTurns` for FCP/HCT foul turns
  - Replaced direct `playTurnAnimation` call with `animationRouter.processTurn(turn)`
  - Removed inline `onAction` wrapper
- ✅ Verified routing
  - `AnimationEngine` routes FCP/HCT fouls to `handleDefault()`
  - `handleDefault()` calls `playTurnAnimation` with all context

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

---

### Phase 2.5: Migrate Standard HCO Turns (Second Migration) ✅ **COMPLETE** (January 2025)

**Goal**: Migrate the most common turn type (HCO shots).

**Tasks Completed**:
- ✅ Updated `animateGameTurns` for standard HCO turns
  - Replaced direct `playTurnAnimation` call with `animationRouter.processTurn(turn)`
  - HCO turns (MAKE/MISS) now route through `AnimationRouter` → `AnimationEngine` → `ShotAnimationSystem`
- ✅ Verified routing
  - `AnimationEngine` routes HCO shots to `ShotAnimationSystem`
  - `ShotAnimationSystem` handles player movement, ball flight, rebounds, and DREB outlet passes
- ✅ Fixed critical bugs
  - Ball detaching after opening tip - Fixed
  - HCO passes teleporting - Fixed via unified pass system (`passDetection.js`)
  - Unified pass system created for all pass types

**Files Modified**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`
- `FrontEnd/static/js/phaser/animation/passDetection.js` (new file)
- `FrontEnd/static/js/phaser/animation/turnAnimation.js`

**Current Status**:
- ✅ HCO shots (MAKE/MISS) fully migrated and working
- ✅ All Phase 2.5 bugs fixed
- ⏳ Some HCO-related turn types still use legacy path (setup turns, turnovers)

---

### Phase 2.6: Migrate Remaining Turn Types ⏳ **IN PROGRESS**

**Goal**: Migrate all remaining turn types to `AnimationRouter`.

**Tasks Remaining**:
- ⏳ Migrate HCO setup turns (`result_type === "HCO"`)
- ⏳ Migrate turnover animations
- ⏳ Migrate other non-shot HCO outcomes
- ⏳ Remove direct `playTurnAnimation` imports (if all migrated)
  - Update `animateGameTurns.js` to remove `playTurnAnimation` import
  - Ensure all animations go through `AnimationRouter`

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` (if needed)

**Success Criteria**:
- All turn types route through `AnimationRouter`
- No direct `playTurnAnimation` calls remain in `animateGameTurns`
- All animations work correctly

---

## Testing Strategy

### After Each Phase

1. **Smoke Test**:
   - Run a full game simulation
   - Verify no console errors
   - Verify no visual glitches

2. **Functional Tests**:
   - **Animation Speeds**: Verify animations play at correct speeds
   - **Possession Flips**: Verify possession changes work correctly
   - **Defender Coords**: Verify defenders are positioned correctly
   - **Step Synchronization**: Verify all players move in sync
   - **Ball Animation**: Verify ball attaches/detaches correctly
   - **Lean Meter**: Verify lean meter animations work (if applicable)

3. **Edge Case Tests**:
   - Fast break transitions
   - Defensive stops
   - OREB sequences
   - Free throw sequences
   - Turnover sequences

### Validation Checklist

After each migration, verify:
- [ ] Animation speeds are correct
- [ ] Possession flips work correctly
- [ ] Defender coords are correct
- [ ] Step synchronization is correct
- [ ] Ball animation is correct
- [ ] Lean meter animations work (if applicable)
- [ ] No console errors
- [ ] No visual glitches
- [ ] Performance is acceptable

## Timeline Estimate

- **Phase 2.1**: 2-3 hours ✅
- **Phase 2.2**: 2-3 hours ✅
- **Phase 2.3**: 1-2 hours ✅
- **Phase 2.4**: 1-2 hours ✅
- **Phase 2.5**: 2-3 hours ✅
- **Phase 2.6**: 3-4 hours ⏳

**Total**: 11-17 hours (Phases 2.1-2.5 complete, Phase 2.6 remaining)

## Success Metrics

1. **Zero regressions**: All animations work identically to before ✅
2. **All turn types routed**: No direct `playTurnAnimation` calls in `animateGameTurns` ⏳ (Phase 2.6)
3. **Clean architecture**: Single entry point through `AnimationRouter` ✅
4. **Maintainable code**: Clear separation of concerns, reusable functions ✅

## Next Steps After Phase 2 Completion

Once Phase 2.6 is complete:
- Proceed with Phase 3: Break up `ballManager.js` into specialized modules
- Continue with remaining phases from `FRONTEND_ORCHESTRATION_CONSOLIDATION_PLAN.md`

---

## Related Documents

- `docs/animation_system.md` - Current animation system documentation
- `docs/ARCHITECTURE_UPDATE_RECOMMENDATIONS.md` - Architecture update recommendations
- `docs/UNIVERSAL_STATE_CLEARING_PATTERN.md` - State clearing pattern documentation

