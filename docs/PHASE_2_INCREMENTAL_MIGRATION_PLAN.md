# Phase 2 Incremental Migration Plan: AnimationRouter Integration

## Problem Statement

The previous attempt to route all animations through `AnimationRouter` caused multiple bugs:
- **Animation speeds were off** - timing issues with animation durations
- **Skipping appropriate next steps** - step synchronization problems
- **Possession flips were off** - possession change logic disrupted
- **Defender placement coords had bugs** - players jetting to wrong end of court
- **Missing context** - setup that happens in `animateGameTurns` before calling `playTurnAnimation` was not being passed through

## Root Cause Analysis

### Missing Context in AnimationRouter Path

When `animateGameTurns` calls `playTurnAnimation` directly, it provides:
1. **Pre-animation setup**:
   - `scene.currentTurn = i` (set before each turn)
   - `updatePlaycallDisplay(turn, ...)` 
   - `updateStrategyBars(turn, ...)`
   - `updatePlaycallCenter(turn, ...)` (includes lean score parsing and storage)
   - `announceFromTurnData(turn, 'start', ...)`
   - `scene._leanScoreToAnimate` and `scene._leanAnimationStep` (calculated and stored)

2. **Turn data preparation**:
   - `turn.index = i` (set on turn object)
   - `possessionId` calculation
   - Debug logging setup

3. **Post-animation cleanup**:
   - `scene._previousTurnWasShot = true` (set after shot turns)
   - `onUpdate(turn)` callback
   - `updateDebugScore(turn, ...)`
   - `announceFromTurnData(turn, 'end', ...)`

4. **Scene state dependencies**:
   - `scene.simData` (set at start of `animateGameTurns`)
   - `scene.stateMachine` (used by `playTurnAnimation` for state checks)
   - `scene._previousTurnWasInbound` (used by `playTurnAnimation`)

### What Went Wrong

The `AnimationRouter` → `AnimationEngine` → `playTurnAnimation` path was:
- Missing pre-animation setup (playcall display, strategy bars, lean score)
- Not setting `scene.currentTurn` before routing
- Not setting `turn.index` on the turn object
- Missing post-animation cleanup (flag setting, announcements)
- Not passing all required context through the routing layers

## Solution: Incremental Migration Strategy

Instead of routing everything at once, we'll:
1. **Enhance context passing** - Ensure all required context flows through routing layers
2. **Migrate one turn type at a time** - Test each migration before moving to the next
3. **Maintain backward compatibility** - Keep direct `playTurnAnimation` calls as fallback
4. **Validate at each step** - Test animation speeds, possession flips, defender coords after each change

## Implementation Plan

### Phase 2.1: Enhance Context Passing (Foundation)

**Goal**: Ensure `AnimationRouter` and `AnimationEngine` can pass all required context to `playTurnAnimation`.

**Tasks**:
1. **Enhance `AnimationRouter.processTurn()` context object**:
   - Add `turnIndex` (from `turn.index` or loop index)
   - Add `onUpdate` callback
   - Add `simData` reference
   - Ensure `scene.currentTurn` is set before routing
   - Ensure `turn.index` is set on turn object

2. **Enhance `AnimationEngine.processTurn()` context handling**:
   - Accept and pass through `turnIndex`, `onUpdate`, `simData`
   - Ensure context is passed to all handler methods
   - Update `handleDefault()` to pass full context to `playTurnAnimation`

3. **Update `playTurnAnimation()` signature** (if needed):
   - Ensure it accepts `turnIndex` and `onUpdate` (may already be optional)
   - Document all required context parameters

4. **Test**: Verify that when `AnimationEngine.handleDefault()` calls `playTurnAnimation`, all context is available.

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` (documentation only)

**Success Criteria**:
- `AnimationEngine.handleDefault()` can call `playTurnAnimation` with all required context
- No missing parameter errors
- Context flows correctly through all layers

---

### Phase 2.2: Extract Pre-Animation Setup (Foundation)

**Goal**: Extract the pre-animation setup logic into a reusable function that can be called before routing.

**Tasks**:
1. **Create `prepareTurnForAnimation(turn, scene, turnIndex)` function**:
   - Set `scene.currentTurn = turnIndex`
   - Set `turn.index = turnIndex`
   - Call `updatePlaycallDisplay(turn, ...)`
   - Call `updateStrategyBars(turn, ...)`
   - Call `updatePlaycallCenter(turn, ...)` (includes lean score parsing)
   - Call `announceFromTurnData(turn, 'start', ...)`
   - Calculate and store `scene._leanScoreToAnimate` and `scene._leanAnimationStep`
   - Return prepared turn object

2. **Create `finalizeTurnAfterAnimation(turn, scene, onUpdate, possessionId)` function**:
   - Set `scene._previousTurnWasShot = true` if turn was a shot
   - Call `onUpdate(turn)` if provided
   - Call `updateDebugScore(turn, ...)`
   - Call `announceFromTurnData(turn, 'end', ...)`

3. **Update `animateGameTurns` to use new functions**:
   - Call `prepareTurnForAnimation()` before `playTurnAnimation`
   - Call `finalizeTurnAfterAnimation()` after `playTurnAnimation`

4. **Test**: Verify animations still work correctly with extracted functions.

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` (extract functions)
- Create `FrontEnd/static/js/phaser/animation/turnPreparation.js` (new file)

**Success Criteria**:
- All animations work exactly as before
- Pre-animation setup is now reusable
- Post-animation cleanup is now reusable

---

### Phase 2.3: Integrate Pre/Post Setup into AnimationRouter

**Goal**: Make `AnimationRouter` handle pre-animation setup and post-animation cleanup.

**Tasks**:
1. **Update `AnimationRouter.processTurn()`**:
   - Call `prepareTurnForAnimation()` at the start
   - Call `finalizeTurnAfterAnimation()` at the end (in `finally` block)
   - Ensure `turnIndex` is available (from `turn.index` or parameter)

2. **Update `AnimationEngine` handlers**:
   - Ensure they don't duplicate pre/post setup
   - Document that setup is handled by `AnimationRouter`

3. **Test**: Create a test route that goes through `AnimationRouter` for a simple turn type (e.g., FCP/HCT foul with animations).

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

**Success Criteria**:
- `AnimationRouter` handles all pre/post setup
- No duplicate setup calls
- Test route works correctly

---

### Phase 2.4: Migrate FCP/HCT Foul Turns (First Migration)

**Goal**: Migrate the simplest turn type first to validate the routing path.

**Tasks**:
1. **Update `animateGameTurns` for FCP/HCT foul turns**:
   - Replace direct `playTurnAnimation` call with `animationRouter.processTurn(turn)`
   - Remove the inline `onAction` wrapper (use the one from `onAction.js`)

2. **Verify routing**:
   - Ensure `AnimationEngine` routes FCP/HCT fouls to `handleDefault()`
   - Ensure `handleDefault()` calls `playTurnAnimation` with all context

3. **Test thoroughly**:
   - Animation speeds are correct
   - Possession flips work correctly
   - Defender coords are correct
   - No visual glitches

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

**Success Criteria**:
- FCP/HCT foul animations work identically to before
- All context is passed correctly
- No bugs introduced

---

### Phase 2.5: Migrate Standard HCO Turns (Second Migration)

**Goal**: Migrate the most common turn type (HCO shots).

**Tasks**:
1. **Update `animateGameTurns` for standard HCO turns**:
   - Find the code path that handles standard HCO turns (not fast breaks, not free throws, not fouls)
   - Replace direct `playTurnAnimation` call with `animationRouter.processTurn(turn)`

2. **Verify routing**:
   - Ensure `AnimationEngine` routes HCO turns correctly
   - May need to enhance `determineHandler()` logic

3. **Test thoroughly**:
   - Animation speeds are correct
   - Possession flips work correctly
   - Defender coords are correct
   - Lean meter animations work
   - Shot animations work correctly

**Files to Modify**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` (if routing logic needs updates)

**Success Criteria**:
- Standard HCO turn animations work identically to before
- All context is passed correctly
- No bugs introduced

---

### Phase 2.6: Migrate Remaining Turn Types (Final Migration)

**Goal**: Migrate all remaining turn types that use `playTurnAnimation`.

**Tasks**:
1. **Identify remaining turn types**:
   - Review `animateGameTurns` for all `playTurnAnimation` calls
   - List each turn type that still uses direct calls

2. **Migrate each turn type**:
   - Replace direct `playTurnAnimation` call with `animationRouter.processTurn(turn)`
   - Test each migration individually

3. **Remove direct `playTurnAnimation` imports** (if all migrated):
   - Update `animateGameTurns.js` to remove `playTurnAnimation` import
   - Ensure all animations go through `AnimationRouter`

4. **Final testing**:
   - Test all turn types
   - Verify no regressions
   - Performance check

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
   - **Animation Speeds**: Verify animations play at correct speeds (no stuttering, no rushing)
   - **Possession Flips**: Verify possession changes work correctly (no double flips, no missed flips)
   - **Defender Coords**: Verify defenders are positioned correctly (no jetting to wrong end of court)
   - **Step Synchronization**: Verify all players move in sync (no skipping steps)
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

## Risk Mitigation

### Rollback Plan

If any phase introduces bugs:
1. **Immediate**: Revert the specific phase changes
2. **Investigation**: Identify root cause
3. **Fix**: Address the issue before proceeding
4. **Re-test**: Verify fix before moving to next phase

### Incremental Validation

- **Never migrate multiple turn types at once** - Always test one at a time
- **Always test after each phase** - Don't skip validation steps
- **Keep direct calls as fallback** - Don't remove until all migrations are complete and tested

## Timeline Estimate

- **Phase 2.1**: 2-3 hours (context passing enhancement)
- **Phase 2.2**: 2-3 hours (extract pre/post setup)
- **Phase 2.3**: 1-2 hours (integrate into AnimationRouter)
- **Phase 2.4**: 1-2 hours (migrate FCP/HCT fouls) + testing
- **Phase 2.5**: 2-3 hours (migrate HCO turns) + testing
- **Phase 2.6**: 3-4 hours (migrate remaining types) + testing

**Total**: 11-17 hours

## Success Metrics

1. **Zero regressions**: All animations work identically to before
2. **All turn types routed**: No direct `playTurnAnimation` calls in `animateGameTurns`
3. **Clean architecture**: Single entry point through `AnimationRouter`
4. **Maintainable code**: Clear separation of concerns, reusable functions

## Next Steps After Completion

Once Phase 2 is complete:
- Proceed with Phase 3: Break up `ballManager.js` into specialized modules
- Continue with remaining phases from `FRONTEND_ORCHESTRATION_CONSOLIDATION_PLAN.md`

