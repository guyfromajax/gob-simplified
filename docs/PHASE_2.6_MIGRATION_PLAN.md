# Phase 2.6 Migration Plan

> **Status**: In Progress ⏳  
> **Goal**: Migrate all remaining turn types to `AnimationRouter`

## Overview

Phase 2.6 completes the migration by routing all remaining turn types through `AnimationRouter`, eliminating direct handler calls in `animateGameTurns.js`.

## Current Status

### ✅ Already Migrated (Phase 2.4-2.5)
- **HCO turns (MAKE/MISS)** - Routes through `AnimationRouter` → `ShotAnimationSystem`
- **FCP/HCT foul turns with animations** - Routes through `AnimationRouter`

### ⏳ Still Need Migration

1. **TURNOVER** - Direct call to `handleTurnover()` (line 779)
2. **HCO setup turns** (`result_type === "HCO"`) - Not explicitly handled, falls through to default
3. **FCP/HCT shots** - Direct call to `playTurnAnimation()` (line 890)
4. **SIDE_INBOUND** - Direct call to `runSideInboundSetup()` (line 618)
5. **BASELINE_INBOUND** - Custom logic, not routed (line 631)
6. **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** - Direct call to `handleOrebTurn()` (line 766)
7. **OPENING_TIP** - Direct call to `runOpeningTipSequence()` (line 821)
8. **FAST_BREAK** - Direct call to `runFastBreakSequence()` (line 870)
9. **FREE_THROW** - Direct call to `runFreeThrowSequence()` (line 564)
10. **DEFENSIVE_STOP** - Custom logic, not routed (line 676)
11. **DEAD BALL** - Just announcements, no animation (probably doesn't need routing)

## Migration Strategy

### Priority Order

**High Priority (Simple, Already Have Handlers):**
1. **TURNOVER** - `AnimationEngine` already has `handleTurnover()` handler
2. **HCO setup turns** - `AnimationEngine` already routes to `handleDefault()` for HCO

**Medium Priority (Need Handler Updates):**
3. **FCP/HCT shots** - Should route to `ShotAnimationSystem` (same as HCO shots)
4. **SIDE_INBOUND** - `AnimationEngine` has `handleSideInbound()` but may need updates
5. **BASELINE_INBOUND** - `AnimationEngine` has `handleBaselineInbound()` but may need updates

**Lower Priority (Complex, May Need Special Handling):**
6. **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** - Complex logic, may need new handler
7. **OPENING_TIP** - Special case, may not need routing
8. **FAST_BREAK** - Complex sequence, may not need routing
9. **FREE_THROW** - `AnimationEngine` has `handleFreeThrow()` but may need updates
10. **DEFENSIVE_STOP** - Custom logic, may not need routing

## Implementation Steps

### Step 1: Migrate TURNOVER ✅ (Start Here)

**Current Code** (line 779):
```javascript
if (turn.result_type === "TURNOVER") {
  await handleTurnover(scene, { playerSprites, ballSprite, turnData: turn, onUpdate });
  announceFromTurnData(turn, 'end', scene.simData?.home_team_id, scene);
  if (onUpdate) {
    try {
      onUpdate(turn);
    } catch (err) {
      console.error('Scoreboard update failed:', err);
    }
  }
  updateDebugScore(turn, { turnIndex: i, possessionId });
  continue;
}
```

**New Code**:
```javascript
if (turn.result_type === "TURNOVER") {
  turn.index = i;
  await animationRouter.processTurn(turn);
  // Note: announceFromTurnData, onUpdate, and updateDebugScore are handled by AnimationRouter
  continue;
}
```

**Verification**:
- `AnimationEngine.handleTurnover()` already exists and should work
- Test that turnovers animate correctly
- Verify announcements and score updates still work

### Step 2: Migrate HCO Setup Turns

**Current Code**: Not explicitly handled, falls through to HCO shot detection

**New Code**: Add explicit check:
```javascript
if (turn.result_type === "HCO") {
  turn.index = i;
  await animationRouter.processTurn(turn);
  continue;
}
```

**Verification**:
- `AnimationEngine` routes HCO to `handleDefault()` which calls `playTurnAnimation()`
- Test that HCO setup turns animate correctly

### Step 3: Migrate FCP/HCT Shots

**Current Code** (line 884-918):
```javascript
if (turn.fcp_shot === true || turn.hct_shot === true) {
  // ... calls playTurnAnimation directly
}
```

**New Code**:
```javascript
if (turn.fcp_shot === true || turn.hct_shot === true) {
  turn.index = i;
  await animationRouter.processTurn(turn);
  continue;
}
```

**Verification**:
- Should route to `ShotAnimationSystem` (same as HCO shots)
- Test that FCP/HCT shots animate correctly

### Step 4: Migrate SIDE_INBOUND

**Current Code** (line 616-628):
```javascript
if (turn.result_type === "SIDE_INBOUND") {
  if (!scene.stateMachine?.is(States.FastBreak)) {
    await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
  }
  // ... onUpdate and score updates
}
```

**New Code**:
```javascript
if (turn.result_type === "SIDE_INBOUND") {
  if (!scene.stateMachine?.is(States.FastBreak)) {
    turn.index = i;
    await animationRouter.processTurn(turn);
  }
  // Note: onUpdate and score updates handled by AnimationRouter
  continue;
}
```

**Verification**:
- `AnimationEngine.handleSideInbound()` exists but may need updates
- Test that side inbound passes animate correctly

### Step 5: Migrate BASELINE_INBOUND

**Current Code** (line 631-673):
```javascript
if (turn.result_type === "BASELINE_INBOUND") {
  // Custom player animation logic
  // ... state transitions
}
```

**New Code**:
```javascript
if (turn.result_type === "BASELINE_INBOUND") {
  turn.index = i;
  await animationRouter.processTurn(turn);
  continue;
}
```

**Verification**:
- `AnimationEngine.handleBaselineInbound()` exists but may need updates
- May need to move custom player animation logic to handler
- Test that baseline inbound passes animate correctly

### Step 6-10: Evaluate Complex Cases

For the remaining turn types (PUTBACK, OPENING_TIP, FAST_BREAK, FREE_THROW, DEFENSIVE_STOP), evaluate whether routing through `AnimationRouter` makes sense or if they should remain as special cases.

## Success Criteria

- ✅ All turn types route through `AnimationRouter`
- ✅ No direct `playTurnAnimation` calls remain in `animateGameTurns.js` (except in fallbacks)
- ✅ All animations work correctly
- ✅ Announcements and score updates still work
- ✅ No regressions in existing functionality

## Testing Checklist

After each migration:
- [ ] Animation plays correctly
- [ ] Announcements display correctly
- [ ] Score updates correctly
- [ ] Ball ownership handled correctly
- [ ] State transitions work correctly
- [ ] No console errors
- [ ] No visual glitches

## Files to Modify

- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - Replace direct calls with `animationRouter.processTurn()`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - Update handlers if needed
- Handler files (if needed) - Update to work with AnimationRouter context

## Next Steps

1. Start with Step 1 (TURNOVER) - simplest case
2. Test thoroughly
3. Proceed to next step
4. Continue until all turn types are migrated
5. Remove unused imports from `animateGameTurns.js`

