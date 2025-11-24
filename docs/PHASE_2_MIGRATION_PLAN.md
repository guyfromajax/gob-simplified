# Phase 2 Migration Plan: Standardize on AnimationRouter

## Current State Analysis

### playTurnAnimation Function Scope (~640 lines)
The `playTurnAnimation` function handles:
1. **Initialization** (~50 lines)
   - Ball holder state initialization
   - State machine checks (FastBreak → HalfCourt transitions)
   - Ball ownership clearing
   - Team ID resolution

2. **Step 0 Setup** (~100 lines)
   - Ball attachment at step 0
   - Pre-step setup (inbound carryover, defensive positioning)
   - Active player display updates

3. **Step-by-Step Animation Loop** (~300 lines)
   - Iterates through all steps (1 to maxSteps)
   - Ball ownership updates per step
   - Player movement animations (via `animateStep`)
   - Shot detection and execution
   - Lean meter animation at middle step
   - Active player display updates

4. **Shot Handling** (~100 lines)
   - Shot parameter preparation
   - Audible/hot read detection
   - `shootBall()` call
   - Rebound handling after shot

5. **Post-Animation** (~90 lines)
   - Kickout reset handling
   - State cleanup
   - Turn completion

### Current Call Sites
- `animateGameTurns.js`: 3 calls (main production path)
- `AnimationEngine.js`: 4 calls (fallbacks for shot/rebound/pass/default)
- `ShotAnimationSystem.js`: 1 call
- `testScene.js`: 1 call (testing)

### Existing Systems
- `HCOAnimationSystem.js`: Exists but only handles HCO outlet pass steps
- `AnimationEngine.js`: Has specialized systems but falls back to `playTurnAnimation`
- `AnimationRouter.js`: Exists and ready, but not used by `animateGameTurns.js`

## Migration Strategy

### Step 1: Enhance HCOAnimationSystem (Medium Complexity)
**Goal**: Move step-by-step animation logic from `playTurnAnimation` to `HCOAnimationSystem`

**Tasks**:
1. Add `processHCOPossession()` method to handle full HCO turns
2. Migrate step-by-step loop logic
3. Migrate shot detection and handling
4. Migrate ball ownership tracking
5. Keep existing `processHCO()` for outlet pass steps

**Files**:
- `FrontEnd/static/js/phaser/animation/HCOAnimationSystem.js` (enhance)

### Step 2: Update AnimationEngine Routing (Low Complexity)
**Goal**: Route HCO turns to `HCOAnimationSystem` instead of `playTurnAnimation`

**Tasks**:
1. Add HCO detection logic to `determineHandler()`
2. Create `handleHCO()` method that calls `HCOAnimationSystem.processHCOPossession()`
3. Remove `playTurnAnimation` fallbacks from shot/rebound/pass handlers (keep for now, remove later)
4. Update `handleDefault()` to route HCO turns to HCO system

**Files**:
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` (modify)

### Step 3: Update animateGameTurns.js (Low Complexity)
**Goal**: Use `AnimationRouter` instead of calling `playTurnAnimation` directly

**Tasks**:
1. Initialize `AnimationRouter` in `animateGameTurns`
2. Replace 3 `playTurnAnimation` calls with `animationRouter.processTurn()`
3. Remove `playTurnAnimation` import
4. Test thoroughly

**Files**:
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` (modify)

### Step 4: Remove playTurnAnimation from AnimationEngine (Low Complexity)
**Goal**: Remove all `playTurnAnimation` fallbacks once HCO system is working

**Tasks**:
1. Remove `playTurnAnimation` imports from `AnimationEngine.js`
2. Remove fallback calls (4 locations)
3. Ensure all specialized systems handle their cases

**Files**:
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` (cleanup)

### Step 5: Testing and Validation (Critical)
**Goal**: Ensure all animation paths work correctly

**Test Cases**:
1. Standard HCO possession (MAKE/MISS)
2. HCO with audible/hot read
3. HCO after fast break defensive stop
4. HCO outlet pass (existing functionality)
5. Shot animations
6. Rebound animations
7. Pass animations

## Risk Mitigation

1. **Keep playTurnAnimation as backup**: Don't delete it initially, just stop calling it
2. **Incremental migration**: Test after each step
3. **Feature flag**: Consider adding a flag to toggle between old/new system during migration
4. **Rollback plan**: Each step can be reverted independently

## Success Criteria

1. ✅ `animateGameTurns.js` uses `AnimationRouter.processTurn()` for all turns
2. ✅ `AnimationEngine` routes HCO turns to `HCOAnimationSystem`
3. ✅ No `playTurnAnimation` calls in production code (except testScene.js)
4. ✅ All animation paths work correctly
5. ✅ Code is simpler and more maintainable

## Timeline Estimate

- Step 1: 2-3 hours (enhance HCOAnimationSystem)
- Step 2: 1 hour (update AnimationEngine routing)
- Step 3: 1 hour (update animateGameTurns.js)
- Step 4: 30 minutes (remove fallbacks)
- Step 5: 1-2 hours (testing)

**Total**: ~6-8 hours

