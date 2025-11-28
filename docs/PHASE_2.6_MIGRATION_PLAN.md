# Phase 2.6 Migration Plan (Revised)

> **Status**: In Progress ⏳  
> **Goal**: Migrate all remaining direct calls to `AnimationRouter`

## Organization Strategy

**Organize by migration status and handler availability**, not by "turn types" vs "outcomes":

1. **What needs migration** (has direct call, not routed through AnimationRouter)
2. **Handler availability** (has handler in AnimationEngine vs needs handler)
3. **Complexity** (simple vs complex)

This approach is more practical because:
- Some outcomes (like TURNOVER) have handlers even though they're not "play types"
- Some play types (like Fast Break) are complex sequences that may not need routing
- The goal is to eliminate direct calls, not categorize by type

---

## Current Status

### ✅ Already Migrated (through AnimationRouter)

1. **HCO shots (MAKE/MISS)** → `AnimationRouter` → `ShotAnimationSystem`
2. **FCP/HCT shots (MAKE/MISS)** → `AnimationRouter` → `ShotAnimationSystem`
3. **FCP/HCT fouls (with animations)** → `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
4. **TURNOVER** → `AnimationRouter` → `handleTurnover()` ✅ (already migrated at line 1164)

### ⏳ Needs Migration (Direct Calls)

**Group 1: Has Handler, Simple Migration**
- ✅ **TURNOVER** - Already migrated! (line 1164)
- **SIDE_INBOUND** - Has `handleSideInbound()`, direct call at line 621
- **BASELINE_INBOUND** - Has `handleBaselineInbound()`, custom logic at line 634
- **HCO setup turns** (`result_type === "HCO"`) - Routes to `handleDefault()`, not explicitly handled

**Group 2: Has Handler, May Need Updates**
- **FREE_THROW** - Has `handleFreeThrow()`, direct call at line 567
- **FAST_BREAK** - Has `handleFastBreak()`, direct call at line 1246

**Group 3: No Handler, Needs Handler**
- **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** - Direct call to `handleOrebTurn()` at line 788
- **OPENING_TIP** - Direct call to `runOpeningTipSequence()` at line 1197

**Group 4: Event-Based Animations (Not Turn Types)**
- **STEAL events** - Direct call to `runPass()` at line 1425
  - Triggered by `result_type === "STEAL"` or `stealEvent` in turn.events
  - Uses `runPass()` utility function directly
  - **Question**: Should this be routed? Or is it fine as-is since it's an event, not a turn type?

**Group 5: No Animation, Just Announcements**
- **DEAD BALL** - Just announcements, no animation (line 604)
- **DEFENSIVE_STOP** - Custom logic, uses `runDefensiveStopTransition()` at line 726
  - **Question**: Should `runDefensiveStopTransition()` be routed? Or is it fine as utility function?
- **Non-animated FOUL** - Just announcements, no animation (line 588)

**Group 6: Sub-Animations (Utility Functions)**
These are called *within* handlers, not as standalone turn animations:
- `shootBall()` - Called by `handleOrebTurn()` for putback shots
- `runInboundSetup()` - Called by `handleOrebTurn()` for putback makes
- `animateRebound()` - Called by `handleOrebTurn()` for putback misses
- `runDefensiveReboundSetup()` - Called by `handleOrebTurn()` for DREB after putback miss
- `animateKickoutReset()` - Called by `handleOrebTurn()` for OREB kickouts
- `runPass()` - Called for STEAL events and other pass animations
- `runDefensiveStopTransition()` - Called for DEFENSIVE_STOP

**Note**: These utility functions are fine to call directly - they're building blocks used by handlers, not turn-level animations that need routing.

---

## Migration Priority

### Priority 1: Simple, Has Handler ✅ **START HERE**

1. **SIDE_INBOUND** (line 621)
   - **Current**: Direct call to `runSideInboundSetup()`
   - **Handler**: `handleSideInbound()` exists
   - **Action**: Replace with `animationRouter.processTurn(turn)`
   - **Complexity**: Low

2. **BASELINE_INBOUND** (line 634)
   - **Current**: Custom logic with FCP/HCT state tracking
   - **Handler**: `handleBaselineInbound()` exists
   - **Action**: Move FCP/HCT state tracking to handler, route through AnimationRouter
   - **Complexity**: Medium (needs to preserve state tracking logic)

3. **HCO setup turns** (`result_type === "HCO"`)
   - **Current**: Falls through to HCO shot detection
   - **Handler**: Routes to `handleDefault()` → `playTurnAnimation()`
   - **Action**: Add explicit check, route through AnimationRouter
   - **Complexity**: Low

### Priority 2: Has Handler, May Need Updates

4. **FREE_THROW** (line 567)
   - **Current**: Direct call to `runFreeThrowSequence()`
   - **Handler**: `handleFreeThrow()` exists
   - **Action**: Replace with `animationRouter.processTurn(turn)`
   - **Complexity**: Medium (may need to verify handler works correctly)

5. **FAST_BREAK** (line 1246)
   - **Current**: Direct call to `runFastBreakSequence()`
   - **Handler**: `handleFastBreak()` exists
   - **Action**: Replace with `animationRouter.processTurn(turn)`
   - **Complexity**: Medium (complex sequence, may need verification)

### Priority 3: Needs Handler

6. **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** (line 788)
   - **Current**: Direct call to `handleOrebTurn()`
   - **Handler**: None (needs new handler or route to existing system)
   - **Action**: Create handler or route to appropriate system
   - **Complexity**: High (complex logic)

7. **OPENING_TIP** (line 1197)
   - **Current**: Direct call to `runOpeningTipSequence()`
   - **Handler**: None (special case, may not need routing)
   - **Action**: Evaluate if routing makes sense (special case)
   - **Complexity**: Medium (special case)

### Priority 4: No Animation Needed

8. **DEAD BALL** (line 604)
   - **Current**: Just announcements
   - **Handler**: None needed
   - **Action**: No migration needed (no animation)
   - **Complexity**: N/A

9. **DEFENSIVE_STOP** (line 698)
   - **Current**: Custom logic, may trigger Fast Break
   - **Handler**: None
   - **Action**: Evaluate if routing makes sense
   - **Complexity**: Medium (custom logic)

10. **Non-animated FOUL** (line 588)
    - **Current**: Just announcements
    - **Handler**: None needed
    - **Action**: No migration needed (no animation)
    - **Complexity**: N/A

---

## Implementation Steps

### Step 1: Migrate SIDE_INBOUND ✅ **START HERE**

**Current Code** (line 619-631):
```javascript
if (turn.result_type === "SIDE_INBOUND") {
  if (!scene.stateMachine?.is(States.FastBreak)) {
    await runSideInboundSetup({ scene, ballSprite, playerSprites, turnData: turn });
  }
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
if (turn.result_type === "SIDE_INBOUND") {
  if (!scene.stateMachine?.is(States.FastBreak)) {
    turn.index = i;
    await animationRouter.processTurn(turn);
    // Note: onUpdate and updateDebugScore handled by AnimationRouter
  }
  continue;
}
```

**Verification**:
- `AnimationEngine.handleSideInbound()` should handle the FastBreak state check
- Test that side inbound passes animate correctly
- Verify announcements and score updates still work

---

### Step 2: Migrate BASELINE_INBOUND

**Current Code** (line 634-673):
```javascript
if (turn.result_type === "BASELINE_INBOUND") {
  // Custom player animation logic
  // FCP/HCT state tracking
  // State transitions
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
- Move FCP/HCT state tracking to `handleBaselineInbound()` handler
- Test that baseline inbound passes animate correctly
- Verify FCP/HCT state is still set correctly

---

### Step 3: Migrate HCO Setup Turns

**Current Code**: Not explicitly handled, falls through to HCO shot detection

**New Code**:
```javascript
if (turn.result_type === "HCO" && !(turn.result_type === "MAKE" || turn.result_type === "MISS")) {
  turn.index = i;
  await animationRouter.processTurn(turn);
  continue;
}
```

**Verification**:
- `AnimationEngine` routes HCO to `handleDefault()` which calls `playTurnAnimation()`
- Test that HCO setup turns animate correctly

---

### Step 4: Migrate FREE_THROW

**Current Code** (line 559-576):
```javascript
if (turn.result_type === "FREE_THROW") {
  // Update active player display
  await runFreeThrowSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, ftContext: turn.ftContext });
  // Announcements and updates
  continue;
}
```

**New Code**:
```javascript
if (turn.result_type === "FREE_THROW") {
  turn.index = i;
  await animationRouter.processTurn(turn);
  // Note: Active player display, announcements, and updates handled by AnimationRouter/handler
  continue;
}
```

**Verification**:
- `AnimationEngine.handleFreeThrow()` should handle all free throw logic
- Test that free throws animate correctly
- Verify active player display updates correctly

---

### Step 5: Migrate FAST_BREAK

**Current Code** (line 1230-1258):
```javascript
if (turn.fast_break === true || turn.result_type === "FAST_BREAK") {
  // Update active player display
  await runFastBreakSequence(scene, { playerSprites, ballSprite, turnData: turn, onUpdate, turnIndex: i });
  // Announcements and updates
  continue;
}
```

**New Code**:
```javascript
if (turn.fast_break === true || turn.result_type === "FAST_BREAK") {
  turn.index = i;
  await animationRouter.processTurn(turn);
  // Note: Active player display, announcements, and updates handled by AnimationRouter/handler
  continue;
}
```

**Verification**:
- `AnimationEngine.handleFastBreak()` should handle all fast break logic
- Test that fast breaks animate correctly
- Verify active player display updates correctly

---

### Step 6-7: Evaluate Complex Cases

For PUTBACK and OPENING_TIP, evaluate whether routing through `AnimationRouter` makes sense or if they should remain as special cases.

### Step 8: Evaluate Event-Based Animations

**STEAL events** (line 1412):
- Currently uses `runPass()` directly
- **Question**: Should STEAL be a turn type with a handler? Or is it fine as an event that triggers a pass animation?
- **Recommendation**: If STEAL can occur as a standalone turn (`result_type === "STEAL"`), it should have a handler. If it's always an event within another turn, current approach is fine.

**DEFENSIVE_STOP** (line 698):
- Currently uses `runDefensiveStopTransition()` directly
- **Question**: Should this be routed? Or is `runDefensiveStopTransition()` fine as a utility function?
- **Recommendation**: If DEFENSIVE_STOP is a turn type, it should be routed. If it's just a transition utility, current approach is fine.

---

## Success Criteria

- ✅ All turn types route through `AnimationRouter` (where it makes sense)
- ✅ No direct handler calls remain in `animateGameTurns.js` (except in fallbacks)
- ✅ All animations work correctly
- ✅ Announcements and score updates still work
- ✅ No regressions in existing functionality

---

## Testing Checklist

After each migration:
- [ ] Animation plays correctly
- [ ] Announcements display correctly
- [ ] Score updates correctly
- [ ] Ball ownership handled correctly
- [ ] State transitions work correctly
- [ ] No console errors
- [ ] No visual glitches

---

## Files to Modify

- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` - Replace direct calls with `animationRouter.processTurn()`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - Update handlers if needed
- Handler files (if needed) - Update to work with AnimationRouter context

---

## Key Insight

**TURNOVER is already migrated!** (line 1164) It was prioritized because it's simple and has a handler, but it's already done. The migration plan should focus on the remaining direct calls, organized by:
1. Handler availability
2. Complexity
3. Frequency/importance

This approach is more practical than organizing by "turn types" vs "outcomes" because the goal is to eliminate direct calls, not categorize by type.

---

## Completeness Check: Will Entire System Be Migrated?

### After Phase 2.6 Completion

**✅ All Turn-Level Animations Will Route Through AnimationRouter:**
1. HCO shots (MAKE/MISS) ✅
2. FCP/HCT shots (MAKE/MISS) ✅
3. FCP/HCT fouls (with animations) ✅
4. TURNOVER ✅
5. SIDE_INBOUND (after migration)
6. BASELINE_INBOUND (after migration)
7. HCO setup turns (after migration)
8. FREE_THROW (after migration)
9. FAST_BREAK (after migration)
10. PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT (after migration)
11. OPENING_TIP (after migration, if applicable)

**⏳ Event-Based Animations (May Not Need Routing):**
- STEAL events - Uses `runPass()` utility directly
  - **Decision needed**: Is STEAL a turn type or just an event?
- DEFENSIVE_STOP - Uses `runDefensiveStopTransition()` utility directly
  - **Decision needed**: Should this be routed or remain as utility?

**✅ Utility Functions (Fine to Call Directly):**
- `shootBall()`, `runPass()`, `animateRebound()`, `runInboundSetup()`, etc.
- These are building blocks used *within* handlers, not turn-level animations
- They don't need routing - they're called by handlers that are already routed

**✅ No Animation (Just Announcements):**
- DEAD BALL, Non-animated FOUL
- These don't need routing - they're just announcements

### Result

**After Phase 2.6 completion, ALL turn-level animations will route through `AnimationRouter`**, except:
- Event-based animations (STEAL, DEFENSIVE_STOP) - if they're not turn types
- Utility functions (called within handlers)
- Announcement-only turns (no animation)

**The entire animation system will be unified through `AnimationRouter` as the single entry point for all turn-level animations.**

