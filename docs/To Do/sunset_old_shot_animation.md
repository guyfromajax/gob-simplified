# Sunset Old Shot Animation System

## Current State

The codebase currently has **two shot animation systems**:

1. **New System**: `ShotAnimationSystem` (in `ShotAnimationSystem.js`)
   - Used for regular shot attempts (MAKE/MISS) when available
   - Handled by `AnimationEngine.handleShotAttempt()`
   - ✅ Now includes shooting foul announcement logic for missed shots

2. **Old System**: `playTurnAnimation` (in `turnAnimation.js`)
   - Still used for FCP/HCT shot attempts and setup turns
   - Used as fallback when `ShotAnimationSystem` is unavailable
   - Contains shooting foul announcement logic in `ballManager.js` (via `shootBall()`)

## Why We Can't Sunset Yet

The old system (`playTurnAnimation`) is still actively used for:

### 1. FCP/HCT Shot Attempts
- **Location**: `animateGameTurns.js` lines 884-913
- **Current Behavior**: FCP/HCT shot attempts (MAKE/MISS with `fcp_shot`/`hct_shot` flags) route through `playTurnAnimation` instead of `ShotAnimationSystem`
- **Reason**: FCP/HCT turns need skeleton animation setup that `playTurnAnimation` provides via `runSetupTween()`

### 2. FCP/HCT Setup Turns
- **Location**: `animateGameTurns.js` lines 924-940
- **Current Behavior**: FCP/HCT setup turns (FOUL, HCO, etc.) route through `playTurnAnimation`
- **Reason**: These turns need the same setup tween logic as shot attempts

### 3. Fallback Mechanism
- **Location**: `AnimationEngine.js` line 777
- **Current Behavior**: Falls back to `playTurnAnimation` if `ShotAnimationSystem` is not available
- **Reason**: Safety net in case new system fails to initialize

### 4. Shared Utility Functions
Both systems depend on utility functions from `turnAnimation.js`:
- `runInboundSetup()` - Used by both systems for baseline inbound setup
- `runDefensiveReboundSetup()` - Used by both systems for DREB outlet passes
- `getPlayerDuration()` - Used by both systems for animation timing
- `runSideInboundSetup()` - Used by both systems for side inbound setup

## Steps to Sunset

### Phase 1: Route FCP/HCT Shot Attempts to New System

**Goal**: Make FCP/HCT shot attempts use `ShotAnimationSystem` instead of `playTurnAnimation`

**Tasks**:
1. **Add FCP/HCT skeleton setup to `ShotAnimationSystem`**
   - Extract `runSetupTween()` logic from `playTurnAnimation`
   - Add FCP/HCT detection to `ShotAnimationSystem.processShot()`
   - Ensure players are positioned at step 0 before skeleton animation (same as `playTurnAnimation`)

2. **Update `animateGameTurns.js` routing**
   - Remove FCP/HCT shot attempt routing to `playTurnAnimation` (lines 884-913)
   - Route FCP/HCT shot attempts through `AnimationEngine.handleShotAttempt()` instead
   - Ensure `AnimationEngine` correctly routes to `ShotAnimationSystem` for FCP/HCT shots

3. **Test FCP/HCT shot animations**
   - Verify skeleton animations still work correctly
   - Verify player positioning at step 0
   - Verify shot animations match old system behavior

### Phase 2: Extract Shared Utilities

**Goal**: Move utility functions to a shared module so both systems can use them without depending on `turnAnimation.js`

**Tasks**:
1. **Create `animationUtils.js` module**
   - Move `runInboundSetup()` to shared module
   - Move `runDefensiveReboundSetup()` to shared module
   - Move `getPlayerDuration()` to shared module
   - Move `runSideInboundSetup()` to shared module

2. **Update imports**
   - Update `ShotAnimationSystem.js` to import from `animationUtils.js`
   - Update `FreeThrowAnimationSystem.js` to import from `animationUtils.js`
   - Update `PassAnimationSystem.js` to import from `animationUtils.js`
   - Update `turnAnimation.js` to import from `animationUtils.js` (for backward compatibility)
   - Update `fastBreak.js` to import from `animationUtils.js`
   - Update `freeThrow.js` to import from `animationUtils.js`
   - Update `turnoverAdapter.js` to import from `animationUtils.js`

3. **Test all systems**
   - Verify inbound setups still work
   - Verify defensive rebound setups still work
   - Verify animation timing is correct

### Phase 3: Remove Old System (Optional)

**Goal**: Remove `playTurnAnimation` entirely, keeping only utility functions

**Tasks**:
1. **Verify no remaining dependencies**
   - Search codebase for all `playTurnAnimation` calls
   - Ensure all shot attempts route through `ShotAnimationSystem`
   - Ensure FCP/HCT setup turns have alternative routing

2. **Remove `playTurnAnimation` function**
   - Delete the main `playTurnAnimation` function from `turnAnimation.js`
   - Keep utility functions in `turnAnimation.js` or move to `animationUtils.js`
   - Update any remaining references

3. **Remove fallback mechanism**
   - Remove fallback to `playTurnAnimation` in `AnimationEngine.handleShotAttempt()`
   - Add error handling if `ShotAnimationSystem` is unavailable

4. **Clean up**
   - Remove unused code from `turnAnimation.js`
   - Update documentation
   - Remove any test files specific to `playTurnAnimation`

## Benefits of Sunsetting

1. **Single Source of Truth**: One shot animation system reduces complexity and bugs
2. **Consistent Behavior**: All shots (regular, FCP/HCT) use the same animation logic
3. **Easier Maintenance**: One system to maintain instead of two
4. **Code Reduction**: Remove ~900 lines of duplicate/legacy code from `turnAnimation.js`
5. **Better Feature Parity**: New features only need to be added to one system

## Risks

1. **FCP/HCT Animation Breaking**: FCP/HCT shots might lose skeleton animation setup
2. **Timing Issues**: Animation timing might differ between old and new systems
3. **Edge Cases**: Some edge cases might only work in old system

## Testing Checklist

Before sunsetting, verify:
- [ ] Regular shot attempts (MAKE/MISS) work correctly
- [ ] FCP/HCT shot attempts show skeleton animations
- [ ] Shooting foul announcements work for both made and missed shots
- [ ] Inbound setups work after shots
- [ ] Defensive rebound setups work after missed shots
- [ ] Free throw sequences work after shooting fouls
- [ ] Putback animations work correctly
- [ ] Fast break animations work correctly
- [ ] All game modes (Single, Tournament, Franchise) work correctly

## Notes

- The old system's shooting foul announcement logic in `ballManager.js` (via `shootBall()`) is now replicated in `ShotAnimationSystem.handleMissedShot()`
- FCP/HCT setup turns might still need `playTurnAnimation` even after shot attempts are migrated
- Consider keeping `playTurnAnimation` as a fallback until the new system is fully proven in production

