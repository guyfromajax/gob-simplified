# FCP/HCT Streamlining Plan: Route Through AnimationRouter

## Goal
Streamline FCP/HCT animation execution to match HCO's stable structure by routing through AnimationRouter, eliminating duplicate code paths and ensuring consistent preparation/finalization.

## Current State Analysis

### HCO Flow (Stable ✅)
```
animateGameTurns.js (line 1038)
  → isHCO detection (simple: !fastBreak && !fcpHct && MAKE/MISS)
  → AnimationRouter.processTurn() (line 1103)
    → prepareTurnForAnimation() (line 107)
    → AnimationEngine.processTurn() (line 158)
      → ShotAnimationSystem (structured handler)
        → runSetupTween() (step 0 positioning)
        → animatePlayerMovement() (skeleton animation)
        → processShot() (result handling)
    → finalizeTurnAfterAnimation() (line 187)
      → announcements, onUpdate, state cleanup
```

### FCP/HCT Flow (Less Stable ⚠️)
```
animateGameTurns.js (line 764)
  → isFCPHCT detection (complex: multiple flags, state checks)
  → playTurnAnimation() DIRECTLY (line 805/844) - BYPASSES AnimationRouter
    → Manual duplicate prevention (scene flags)
    → runSetupTween() (inline, line 1612)
    → Manual step loop (line 1721)
    → Manual result handling (inline)
  → Manual announcements/updates (line 824-832, 895-901)
  → NO prepareTurnForAnimation()
  → NO finalizeTurnAfterAnimation()
```

## Key Issues

1. **Missing Preparation**: FCP/HCT doesn't get `prepareTurnForAnimation()` benefits:
   - No `scene.currentTurn` setup
   - No playcall display updates
   - No strategy bar updates
   - No lean score parsing
   - No turn start announcements

2. **Missing Finalization**: FCP/HCT doesn't get `finalizeTurnAfterAnimation()` benefits:
   - No `_previousTurnWasShot` flag management
   - Manual announcements (inconsistent timing)
   - Manual onUpdate calls (error-prone)
   - No centralized cleanup

3. **Bypassing AnimationRouter**: FCP/HCT calls `playTurnAnimation()` directly:
   - No centralized processing flag (`isProcessing`)
   - Manual duplicate prevention (scene flags)
   - No queue management
   - No error handling wrapper

4. **Complex Detection Logic**: FCP/HCT has 30+ lines of detection logic vs HCO's 1 line

5. **Inconsistent Result Handling**: FCP/HCT handles results inline vs HCO's structured `ShotAnimationSystem.processShot()`

## Migration Plan

### Phase 1: Create PressureAnimationSystem Handler

**Goal**: Create a structured handler for FCP/HCT (similar to ShotAnimationSystem for HCO)

**Steps**:
1. Create `FrontEnd/static/js/phaser/animation/PressureAnimationSystem.js`
   - Similar structure to `ShotAnimationSystem.js`
   - Handles FCP/HCT skeleton animation
   - Handles all result types (MAKE/MISS, FOUL, TURNOVER, STEAL, DEAD_BALL, HCO)
   - Reuses `playTurnAnimation()` logic for skeleton animation
   - Structured result handling (like `ShotAnimationSystem.processShot()`)

2. Register handler in `AnimationEngine.js`
   - Add `PRESSURE` handler to `animationHandlers` map
   - Update `determineHandler()` to detect FCP/HCT and return PRESSURE handler

**Benefits**:
- Structured result handling (can be applied to HCO later)
- Consistent with HCO's ShotAnimationSystem pattern
- Easier to extend for new result types

---

### Phase 2: Simplify Detection Logic

**Goal**: Move FCP/HCT detection into `AnimationEngine.determineHandler()` (centralized)

**Steps**:
1. Move FCP/HCT detection from `animateGameTurns.js` (lines 731-764) to `AnimationEngine.determineHandler()`
   - Simplify to single check: `isFCPHCT(turnData, scene)`
   - Return PRESSURE handler if detected
   - Remove complex detection logic from `animateGameTurns.js`

2. Update `animateGameTurns.js`:
   - Remove FCP/HCT detection block (lines 731-901)
   - Remove manual `playTurnAnimation()` calls for FCP/HCT
   - Let AnimationRouter handle all FCP/HCT turns

**Benefits**:
- Single source of truth for detection
- Consistent with HCO detection pattern
- Easier to maintain and debug

---

### Phase 3: Route FCP/HCT Through AnimationRouter

**Goal**: Make FCP/HCT use the same routing path as HCO

**Steps**:
1. Update `animateGameTurns.js`:
   - Remove FCP/HCT-specific routing (lines 780-901)
   - Remove manual announcements/updates (lines 824-832, 895-901)
   - Let all FCP/HCT turns fall through to AnimationRouter (same as HCO)

2. Update `AnimationRouter.processTurn()`:
   - Ensure it handles FCP/HCT turns (should already work via AnimationEngine)
   - Verify `prepareTurnForAnimation()` is called (already happens)
   - Verify `finalizeTurnAfterAnimation()` is called (already happens)

3. Remove duplicate prevention guards:
   - Remove `_fcpHctPlayAnimation_${turnId}` flags from `playTurnAnimation()`
   - Rely on AnimationRouter's `isProcessing` flag instead

**Benefits**:
- Unified routing path
- Automatic preparation/finalization
- Centralized duplicate prevention
- Consistent error handling

---

### Phase 4: Consolidate Result Handling

**Goal**: Use structured result handlers (like HCO's `ShotAnimationSystem.processShot()`)

**Steps**:
1. In `PressureAnimationSystem`, create structured result handlers:
   - `handleShotResult()` - for MAKE/MISS (reuse ShotAnimationSystem logic)
   - `handleFoulResult()` - for FOUL (structured, can apply to HCO later)
   - `handleTurnoverResult()` - for TURNOVER/STEAL/DEAD_BALL (structured)
   - `handleHCOResult()` - for HCO (press break to HCO)

2. Remove inline result handling from `playTurnAnimation()`:
   - Move all result-specific logic to PressureAnimationSystem
   - Keep `playTurnAnimation()` focused on skeleton animation only

**Benefits**:
- Structured, testable result handling
- Can be applied to HCO later (fouls, turnovers)
- Easier to extend for new result types

---

### Phase 5: State Management Consolidation

**Goal**: Use AnimationRouter's state management instead of manual scene flags

**Steps**:
1. Remove manual pressure state management from `animateGameTurns.js`:
   - Remove `scene.currentPressureType` and `scene.pressureSequenceActive` updates (lines 886-889)
   - Move to `PressureAnimationSystem` or `AnimationEngine`

2. Use AnimationRouter's `isProcessing` flag:
   - Remove `_fcpHctPlayAnimation_${turnId}` flags
   - Remove `_fcpHctSetupTween_${turnId}` flags
   - Rely on AnimationRouter's centralized processing flag

**Benefits**:
- Single source of truth for processing state
- Consistent with HCO's state management
- Easier to debug and maintain

---

### Phase 6: Apply FCP/HCT Result Handling to HCO

**Goal**: Use FCP/HCT's structured result handlers for HCO (fouls, turnovers, etc.)

**Steps**:
1. Extract common result handling logic:
   - Create shared result handlers (fouls, turnovers, etc.)
   - Use by both PressureAnimationSystem and ShotAnimationSystem

2. Update ShotAnimationSystem:
   - Add structured handlers for fouls, turnovers (currently inline)
   - Match FCP/HCT's structured approach

**Benefits**:
- Consistent result handling across all turn types
- Easier to maintain and extend
- Better testability

---

## Implementation Order

1. **Phase 1** (PressureAnimationSystem) - Foundation
2. **Phase 2** (Detection Logic) - Simplification
3. **Phase 3** (AnimationRouter Routing) - Core migration
4. **Phase 4** (Result Handling) - Structure
5. **Phase 5** (State Management) - Cleanup
6. **Phase 6** (HCO Enhancement) - Future work

## Testing Strategy

### After Each Phase:
1. Test FCP/HCT skeleton animations (should work same as before)
2. Test all FCP/HCT result types:
   - MAKE/MISS (shot attempts)
   - FOUL (defensive and offensive)
   - TURNOVER/STEAL/DEAD_BALL
   - HCO (press break)
3. Test state management:
   - Pressure sequence activation/deactivation
   - Duplicate prevention
   - State persistence across turns

### Regression Testing:
1. HCO turns (should remain stable)
2. Fast Break turns (should remain stable)
3. Free Throw turns (should remain stable)
4. Rebound sequences (should remain stable)

## Expected Benefits

1. **Stability**: FCP/HCT will have same stability as HCO (unified code path)
2. **Maintainability**: Single code path, easier to debug and extend
3. **Consistency**: Same preparation/finalization for all turn types
4. **Extensibility**: Structured result handlers can be applied to HCO
5. **Code Reduction**: Remove ~200 lines of duplicate/inline logic

## Risk Mitigation

1. **Backward Compatibility**: Keep old detection logic commented out initially
2. **Gradual Migration**: Phase-by-phase approach allows testing at each step
3. **Feature Flags**: Add flags to toggle between old/new paths if needed
4. **Comprehensive Testing**: Test all result types and edge cases

## Success Criteria

- [ ] FCP/HCT routes through AnimationRouter (same as HCO)
- [ ] FCP/HCT gets `prepareTurnForAnimation()` and `finalizeTurnAfterAnimation()`
- [ ] FCP/HCT uses structured result handlers (not inline)
- [ ] FCP/HCT uses AnimationRouter's duplicate prevention (not manual flags)
- [ ] Detection logic simplified to single check in AnimationEngine
- [ ] All FCP/HCT result types work correctly
- [ ] No regression in HCO, Fast Break, Free Throw, or Rebound animations
- [ ] Code reduction: ~200 lines removed/consolidated

