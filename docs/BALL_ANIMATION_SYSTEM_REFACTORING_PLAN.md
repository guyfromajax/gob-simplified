# Ball Animation System Refactoring Plan

## Executive Summary

**Problem**: The ball animation system has a dual architecture where the new `BallController` system still depends on old system flags (`scene._shotInProgress`, `scene.ballDetached`, etc.), causing bugs in free throws and fast breaks.

**Solution**: Complete the migration by making `BallController` the single source of truth, removing all dependencies on old system flags, and consolidating all ball attachment logic.

**Timeline**: 2-3 weeks (can be done incrementally)

---

## Current State Analysis

### The Dual System Problem

**Old System** (Legacy):
- Uses scene flags: `scene._shotInProgress`, `scene.ballDetached`, `scene._putbackInProgress`
- Functions: `ballTween.js.attachBallToPlayer()`, `ballManager.js.attachBallToPlayer()`
- Callback-based following: `scene._ballFollowing`
- Direct sprite manipulation

**New System** (`BallController`):
- Intended as "Single Source of Truth"
- Has own state: `isAttached`, `isDetached`, `isInFlight`
- **BUT** still checks old flags: `if (this.scene._shotInProgress)` (line 93 in `BallController.js`)
- **Result**: New system blocked by old system state

**Adapter Layer** (`BallControllerAdapter`):
- Tries to bridge both systems
- Adds complexity and sync issues

### Evidence of the Problem

1. **88 references** to state flags across 13 files
2. **4+ different** `attachBallToPlayer` implementations
3. **Free Throw Bug**: `_shotInProgress` flag blocks attachment
4. **Fast Break Bug**: State sync issues between systems
5. **BallController** checks old flags (line 93): `if (this.scene._shotInProgress && !isPutbackAttempt)`

### Current File Structure

```
FrontEnd/static/js/phaser/animation/
├── BallController.js              (New system - core)
├── BallControllerAdapter.js       (Adapter layer)
├── ballTween.js                   (Old system - still used)
├── ballManager.js                 (Old system wrapper)
├── ballAnimationSimple.js         (WIP_GOB system - partially integrated)
└── [30+ files using ball attachment]
```

---

## Target Architecture

### Single Source of Truth: `BallController`

```
BallController (Single Source of Truth)
    ├── Internal State Management
    │   ├── isAttached (boolean)
    │   ├── isDetached (boolean)
    │   ├── isInFlight (boolean)
    │   ├── currentOwner (playerSprite)
    │   └── NO dependency on scene flags
    │
    ├── Public API
    │   ├── attachToPlayer(playerSprite, options)
    │   ├── detachFromPlayer(reason, options)
    │   ├── startFlight(target, options)
    │   ├── stopFlight()
    │   └── getState() → { isAttached, currentOwner, ... }
    │
    └── Lifecycle Hooks
        ├── onShotStart() → sets isInFlight, clears isAttached
        ├── onShotEnd() → clears isInFlight
        ├── onPassStart() → sets isInFlight
        └── onPassEnd() → clears isInFlight, attaches to receiver
```

### Removed Dependencies

**Eliminate:**
- ❌ `scene._shotInProgress` → Use `ballController.isInFlight`
- ❌ `scene.ballDetached` → Use `ballController.isDetached`
- ❌ `scene._putbackInProgress` → Use `ballController.getState().reason === 'putback'`
- ❌ `scene._ballFollowing` → Use `ballController.isAttached && ballController.currentOwner`
- ❌ Old `attachBallToPlayer()` functions → All use `BallController`

---

## Refactoring Phases

### Phase 1: Make BallController Independent (Week 1)

**Goal**: Remove all dependencies on old system flags from `BallController`

#### Step 1.1: Add Internal State Tracking
- [ ] Add `reason` field to track why ball is detached/in flight
- [ ] Add `previousState` for state transitions
- [ ] Add `stateHistory` for debugging
- [ ] Remove checks for `scene._shotInProgress`, `scene._putbackInProgress`

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/BallController.js`

**Code changes:**
```javascript
// BEFORE (line 93):
if (this.scene._shotInProgress && !isPutbackAttempt) {
  return false;
}

// AFTER:
if (this.isInFlight && !isPutbackAttempt) {
  return false;
}
```

#### Step 1.2: Add Lifecycle Methods
- [ ] Add `onShotStart(options)` method
- [ ] Add `onShotEnd()` method
- [ ] Add `onPassStart(options)` method
- [ ] Add `onPassEnd(receiver)` method
- [ ] Add `onPutbackStart()` method
- [ ] Add `onPutbackEnd()` method

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/BallController.js`

**New methods:**
```javascript
onShotStart(options = {}) {
  this.isInFlight = true;
  this.isAttached = false;
  this.detachFromPlayer('shot_start', options);
  this.stateHistory.push({ 
    state: 'IN_FLIGHT', 
    reason: 'shot_start',
    timestamp: Date.now() 
  });
}

onShotEnd() {
  this.isInFlight = false;
  this.stateHistory.push({ 
    state: 'READY', 
    reason: 'shot_end',
    timestamp: Date.now() 
  });
}
```

#### Step 1.3: Update BallControllerAdapter
- [ ] Remove old flag checks from adapter
- [ ] Use `BallController` state instead
- [ ] Update `attachBallToPlayer` to use lifecycle methods

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js`

#### Step 1.4: Testing
- [ ] Test free throw attachment (should work now)
- [ ] Test shot animations
- [ ] Test pass animations
- [ ] Verify no regressions

---

### Phase 2: Update Call Sites to Use Lifecycle Methods (Week 1-2)

**Goal**: Replace old flag manipulation with `BallController` lifecycle methods

#### Step 2.1: Update Shot Animations
- [ ] Find all places that set `scene._shotInProgress = true`
- [ ] Replace with `ballController.onShotStart()`
- [ ] Find all places that set `scene._shotInProgress = false`
- [ ] Replace with `ballController.onShotEnd()`

**Files to search:**
- `FrontEnd/static/js/phaser/animation/ballManager.js` (shootBall function)
- `FrontEnd/static/js/phaser/animation/ballAnimationSimple.js`
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js`

**Example change:**
```javascript
// BEFORE:
scene._shotInProgress = true;
// ... shot animation ...
scene._shotInProgress = false;

// AFTER:
ballController.onShotStart({ shooterId, isPutback: false });
// ... shot animation ...
ballController.onShotEnd();
```

#### Step 2.2: Update Pass Animations
- [ ] Find all places that manipulate ball during passes
- [ ] Use `ballController.onPassStart()` and `onPassEnd()`

**Files to search:**
- `FrontEnd/static/js/phaser/animation/ballTween.js` (runPass function)
- `FrontEnd/static/js/phaser/animation/PassAnimationSystem.js`

#### Step 2.3: Update Putback Animations
- [ ] Find all places that set `scene._putbackInProgress`
- [ ] Replace with `ballController.onPutbackStart()` and `onPutbackEnd()`

**Files to search:**
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js` (handleOrebTurn)
- `FrontEnd/static/js/phaser/animation/ReboundAnimationSystem.js`

#### Step 2.4: Update Free Throw Animations
- [ ] Remove flag checks at start of `runFreeThrowSequence()`
- [ ] Use `ballController.onShotEnd()` to clear state before attaching

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/freeThrow.js`

**Key fix:**
```javascript
// At start of runFreeThrowSequence(), BEFORE attaching ball:
// Clear any lingering shot state
if (ballController.isInFlight) {
  ballController.onShotEnd();
}
// Now attachment will work
ballController.attachToPlayer(shooterSprite);
```

#### Step 2.5: Testing
- [ ] Test all shot scenarios (regular, fast break, putback)
- [ ] Test all pass scenarios (HCO, outlet, kickout)
- [ ] Test free throws (should fix the bug)
- [ ] Test fast breaks (should fix the bug)
- [ ] Test putbacks (should not regress)

---

### Phase 3: Consolidate Attachment Functions (Week 2)

**Goal**: Remove all old `attachBallToPlayer` implementations, use only `BallController`

#### Step 3.1: Update `runPass()` in `ballTween.js`
- [ ] Import `attachBallToPlayer` from `BallControllerAdapter.js`
- [ ] Replace local `attachBallToPlayer` calls (lines 445, 454)
- [ ] Test all pass animations

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/ballTween.js`

#### Step 3.2: Update `freeThrow.js`
- [ ] Replace dynamic import with static import from `BallControllerAdapter.js`
- [ ] Test free throw animations

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/freeThrow.js`

#### Step 3.3: Update `ballManager.js`
- [ ] Remove wrapper `attachBallToPlayer` function
- [ ] Update all call sites to use `BallControllerAdapter`
- [ ] Test all scenarios

**Files to modify:**
- `FrontEnd/static/js/phaser/animation/ballManager.js`

#### Step 3.4: Remove Old Functions
- [ ] Remove `attachBallToPlayer` from `ballTween.js`
- [ ] Remove `attachBallToPlayer` from `ballManager.js`
- [ ] Search codebase for any remaining references
- [ ] Add deprecation warnings if needed

#### Step 3.5: Testing
- [ ] Comprehensive testing of all ball attachment scenarios
- [ ] Verify no regressions
- [ ] Performance check (should be same or better)

---

### Phase 4: Remove Old System Flags (Week 2-3)

**Goal**: Remove all old system flags from the codebase

#### Step 4.1: Remove Flag Declarations
- [ ] Search for `scene._shotInProgress =`
- [ ] Search for `scene.ballDetached =`
- [ ] Search for `scene._putbackInProgress =`
- [ ] Remove all assignments (should be none after Phase 2)

#### Step 4.2: Remove Flag Checks
- [ ] Search for `if (scene._shotInProgress)`
- [ ] Search for `if (scene.ballDetached)`
- [ ] Search for `if (scene._putbackInProgress)`
- [ ] Replace with `BallController` state checks

**Example:**
```javascript
// BEFORE:
if (scene._shotInProgress) {
  return;
}

// AFTER:
const ballController = getBallController();
if (ballController && ballController.isInFlight) {
  return;
}
```

#### Step 4.3: Remove `scene._ballFollowing`
- [ ] Find all references to `scene._ballFollowing`
- [ ] Remove callback setup
- [ ] `BallController` handles following internally

**Files to search:**
- `FrontEnd/static/js/phaser/animation/ballTween.js` (startBallFollowing function)

#### Step 4.4: Testing
- [ ] Full regression test
- [ ] Verify no old flags are set anywhere
- [ ] Performance check

---

### Phase 5: Cleanup and Documentation (Week 3)

**Goal**: Clean up code, update documentation, add tests

#### Step 5.1: Code Cleanup
- [ ] Remove commented-out code
- [ ] Remove unused imports
- [ ] Consolidate helper functions
- [ ] Update code comments

#### Step 5.2: Documentation
- [ ] Update `BallController.js` JSDoc
- [ ] Create migration guide for future developers
- [ ] Update architecture diagrams
- [ ] Document lifecycle methods

#### Step 5.3: Add Tests
- [ ] Unit tests for `BallController` lifecycle methods
- [ ] Integration tests for attachment scenarios
- [ ] Test for free throw bug (should be fixed)
- [ ] Test for fast break bug (should be fixed)

#### Step 5.4: Final Validation
- [ ] Run full test suite
- [ ] Manual testing of all scenarios
- [ ] Performance profiling
- [ ] Code review

---

## Implementation Details

### BallController Lifecycle Methods

```javascript
class BallController {
  // Shot lifecycle
  onShotStart(options = {}) {
    const { shooterId, isPutback = false } = options;
    this.isInFlight = true;
    this.isAttached = false;
    this.detachFromPlayer('shot_start', { reason: 'shot', isPutback });
    this.stateHistory.push({ 
      state: 'IN_FLIGHT', 
      reason: isPutback ? 'putback_shot' : 'shot',
      shooterId,
      timestamp: Date.now() 
    });
  }

  onShotEnd() {
    this.isInFlight = false;
    this.stateHistory.push({ 
      state: 'READY', 
      reason: 'shot_end',
      timestamp: Date.now() 
    });
  }

  // Pass lifecycle
  onPassStart(options = {}) {
    const { passerId, receiverId } = options;
    this.isInFlight = true;
    this.isAttached = false;
    this.detachFromPlayer('pass_start', { reason: 'pass' });
    this.pendingOwner = receiverId ? this.findPlayerSprite(receiverId) : null;
    this.stateHistory.push({ 
      state: 'IN_FLIGHT', 
      reason: 'pass',
      passerId,
      receiverId,
      timestamp: Date.now() 
    });
  }

  onPassEnd(receiverSprite) {
    this.isInFlight = false;
    if (receiverSprite) {
      this.attachToPlayer(receiverSprite, { reason: 'pass_end' });
    }
    this.stateHistory.push({ 
      state: receiverSprite ? 'ATTACHED' : 'DETACHED', 
      reason: 'pass_end',
      timestamp: Date.now() 
    });
  }

  // Putback lifecycle
  onPutbackStart() {
    this.onShotStart({ isPutback: true });
  }

  onPutbackEnd() {
    this.onShotEnd();
  }

  // State query
  getState() {
    return {
      isAttached: this.isAttached,
      isDetached: this.isDetached,
      isInFlight: this.isInFlight,
      currentOwner: this.currentOwner,
      pendingOwner: this.pendingOwner,
      lastStateChange: this.stateHistory[this.stateHistory.length - 1]
    };
  }
}
```

### Free Throw Fix

```javascript
// In freeThrow.js, at start of runFreeThrowSequence()
export async function runFreeThrowSequence(scene, { playerSprites, ballSprite, turnData, ... }) {
  const { getBallController } = await import('./BallControllerAdapter.js');
  const ballController = getBallController();
  
  // ✅ FIX: Clear any lingering shot state before attaching
  if (ballController && ballController.isInFlight) {
    ballController.onShotEnd();
  }
  
  // Now attachment will work
  const shooterSprite = playerSprites[turnData.shooter_id];
  if (shooterSprite && ballController) {
    ballController.attachToPlayer(shooterSprite, { reason: 'free_throw_setup' });
  }
  
  // ... rest of free throw sequence
}
```

### Fast Break Fix

```javascript
// In fastBreak.js, after outlet pass completes
async function animateOutletPhase(...) {
  // ... outlet pass animation ...
  
  // ✅ FIX: Ensure ball is attached to receiver after pass
  const ballController = getBallController();
  if (ballController && receiverSprite) {
    // Pass should have ended and attached ball, but verify
    if (!ballController.isAttached || ballController.currentOwner !== receiverSprite) {
      ballController.attachToPlayer(receiverSprite, { reason: 'fast_break_outlet' });
    }
  }
  
  // ... continue to next phase
}
```

---

## Risk Assessment

### High Risk Areas

1. **Shot Animations** (High)
   - Many call sites
   - Complex state transitions
   - **Mitigation**: Update incrementally, test each scenario

2. **Pass Animations** (Medium)
   - Used in many places
   - **Mitigation**: Update `runPass()` first, test thoroughly

3. **Putback Animations** (Medium)
   - Already has bug fixes in place
   - **Mitigation**: Use lifecycle methods, test carefully

### Low Risk Areas

1. **Free Throw Animations** (Low)
   - Isolated code path
   - Clear fix needed
   - **Mitigation**: Simple state clear before attachment

2. **Fast Break Animations** (Low)
   - Clear attachment point
   - **Mitigation**: Verify attachment after pass

---

## Testing Strategy

### Unit Tests

```javascript
describe('BallController Lifecycle', () => {
  test('onShotStart sets isInFlight and detaches ball', () => {
    const controller = new BallController(scene, ballSprite);
    controller.attachToPlayer(playerSprite);
    controller.onShotStart({ shooterId: 'player1' });
    
    expect(controller.isInFlight).toBe(true);
    expect(controller.isAttached).toBe(false);
  });

  test('onShotEnd clears isInFlight', () => {
    const controller = new BallController(scene, ballSprite);
    controller.onShotStart({ shooterId: 'player1' });
    controller.onShotEnd();
    
    expect(controller.isInFlight).toBe(false);
  });
});
```

### Integration Tests

1. **Free Throw Test**
   - Setup: Shot made with AND-1
   - Action: Free throw sequence starts
   - Verify: Ball attaches to shooter, no teleport

2. **Fast Break Test**
   - Setup: DREB → outlet pass
   - Action: Fast break phase starts
   - Verify: Ball follows receiver, no detachment

3. **Putback Test**
   - Setup: OREB → putback attempt
   - Action: Putback shot animation
   - Verify: No flash before shot, ball animates correctly

### Manual Testing Checklist

- [ ] Free throw after made shot (AND-1)
- [ ] Free throw after foul (regular)
- [ ] Free throw miss rebound
- [ ] Fast break outlet pass
- [ ] Fast break shot
- [ ] Fast break defensive stop
- [ ] OREB putback make
- [ ] OREB putback miss
- [ ] Regular shot animations
- [ ] Pass animations (all types)
- [ ] Rebound animations

---

## Success Criteria

### Phase 1 Complete When:
- ✅ `BallController` has no dependencies on old flags
- ✅ Lifecycle methods implemented
- ✅ Free throw attachment works

### Phase 2 Complete When:
- ✅ All call sites use lifecycle methods
- ✅ No old flag assignments remain
- ✅ Fast break attachment works

### Phase 3 Complete When:
- ✅ Only one `attachBallToPlayer` function exists
- ✅ All code uses `BallControllerAdapter`
- ✅ Old functions removed

### Phase 4 Complete When:
- ✅ No old flags in codebase
- ✅ No `scene._ballFollowing` references
- ✅ All state managed by `BallController`

### Phase 5 Complete When:
- ✅ Documentation updated
- ✅ Tests added
- ✅ Code reviewed
- ✅ All bugs fixed

---

## Timeline

**Week 1**: Phases 1-2 (Make BallController independent, update call sites)
- Days 1-2: Phase 1 (BallController independence)
- Days 3-5: Phase 2 (Update call sites)

**Week 2**: Phases 3-4 (Consolidate functions, remove flags)
- Days 1-3: Phase 3 (Consolidate attachment functions)
- Days 4-5: Phase 4 (Remove old flags)

**Week 3**: Phase 5 (Cleanup, documentation, testing)
- Days 1-2: Code cleanup
- Days 3-4: Documentation and tests
- Day 5: Final validation

**Total**: 15 working days (3 weeks)

---

## Rollback Plan

If issues arise:

1. **Phase 1-2 Issues**: Old flags still exist, can revert to using them
2. **Phase 3 Issues**: Old functions still exist (commented out), can uncomment
3. **Phase 4 Issues**: Can re-add flags temporarily
4. **Git**: Each phase is a separate commit, easy to revert

---

## Notes

- This refactoring can be done incrementally
- Each phase can be tested independently
- Old system remains functional during migration
- Clear rollback path at each phase
- Addresses root cause, not just symptoms
- Will fix both free throw and fast break bugs
- Reduces technical debt significantly

---

## Related Documents

- `BALL_ANIMATION_MIGRATION_PLAN.md` - Previous migration (WIP_GOB system)
- `ball_attachment_consolidation_plan.md` - Consolidation of attachment functions
- `FAST_BREAK_OUTLET_BALL_DETACHMENT_BUG.md` - Fast break bug documentation

---

**Status**: Planning Phase  
**Last Updated**: [Current Date]  
**Owner**: Development Team

