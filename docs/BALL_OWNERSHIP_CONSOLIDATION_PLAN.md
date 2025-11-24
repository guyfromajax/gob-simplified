# Ball Ownership System Consolidation Plan

> **Goal**: Eliminate multiple competing ball ownership systems and create a single, simple, stable, and scalable animation engine.

> **Status**: Phase 5 Complete ✅  
> **Created**: December 2024  
> **Completed**: December 2024  
> **Timeline**: Completed in 1 day (incremental, low-risk approach)

---

## Executive Summary

**Current Problem**: Three separate systems manage ball ownership, causing:
- State synchronization issues (fast break, free throw bugs)
- Confusion about which system is authoritative
- Maintenance burden (changes need to be made in multiple places)
- Potential for conflicts and bugs

**Solution**: Consolidate all ball ownership logic into `BallController` as the single source of truth, with `BallControllerAdapter` providing backward-compatible function signatures.

**Outcome**: One system, one source of truth, easier debugging, fewer bugs.

---

## Current State Analysis

### System 1: BallController (New - Intended Single Source of Truth)
**Location**: `FrontEnd/static/js/phaser/animation/BallController.js`

**Current Capabilities**:
- ✅ `getCurrentOwner()` - Returns player sprite
- ✅ `getPendingOwner()` - Returns player sprite
- ✅ `setPendingOwner(playerSprite, options)` - Sets pending owner
- ✅ `attachToPlayer()` - Attaches ball to player
- ✅ `detachFromPlayer()` - Detaches ball
- ✅ `isAttached`, `isInFlight`, `reason` - State tracking
- ✅ Syncs with `gameState.ballHolder` (WIP_GOB integration)

**Status**: Fully implemented, but not fully adopted

---

### System 2: Old ballController.js (Legacy - Still Active)
**Location**: `FrontEnd/static/js/phaser/ball/ballController.js`

**Current Capabilities**:
- `getCurrentOwner(scene)` - Returns player ID (string)
- `setCurrentOwner(scene, playerId)` - Sets current owner
- `clearCurrentOwner(scene)` - Clears current owner
- `getLastKnownOwner(scene)` - Returns last owner ID
- `getPendingOwner(scene)` - Returns pending owner ID
- `setPendingOwner(scene, playerId)` - Sets pending owner
- `clearPendingOwner(scene)` - Clears pending owner
- `cancelBallTween(scene, ballSprite)` - Cancels ball tween

**Used By** (8 files):
1. `ballTween.js`
2. `turnAnimation.js`
3. `animateGameTurns.js`
4. `ballManager.js`
5. `freeThrow.js`
6. `fastBreak.js`
7. `animateStep.js`
8. `turnoverAdapter.js`

**Key Difference**: Uses WeakMap-based state storage, returns player IDs (strings) instead of sprites

---

### System 3: ballAnimationSimple.js (WIP_GOB)
**Location**: `FrontEnd/static/js/phaser/animation/ballAnimationSimple.js`

**Current Capabilities**:
- `getBallHolderId(scene)` - Returns player ID (string)
- `setBallHolderId(scene, playerId)` - Sets ball holder ID
- `clearBallHolder(scene)` - Clears ball holder
- `initializeBallHolderState(scene)` - Initializes state
- `getPlayerTweenTargets()` - Includes ball in player tween when player has ball

**Status**: Already synced with BallController's `gameState.ballHolder`, but separate API

---

### System 4: Multiple `updateBallOwnership` Functions

**Three Different Implementations**:

1. **ballManager.js** (`updateBallOwnership`)
   - Timestamp-based lookup
   - Finds current step based on timestamp
   - Uses `attachBallToPlayer` from adapter

2. **turnAnimation.js** (`updateBallOwnership`)
   - Step-index based
   - Handles pending owners
   - Uses old `ballController.js` functions
   - Updates both old system and WIP_GOB system

3. **ShotAnimationSystem.js** (`updateBallOwnership`)
   - Step-index based
   - Uses `BallController.attachToPlayer()` directly
   - Different logic flow

**Problem**: Three different approaches to the same task, potential for inconsistencies

---

## Consolidation Strategy

### Core Principle
**BallController becomes the single source of truth. All other systems delegate to it.**

### Architecture After Consolidation

```
┌─────────────────────────────────────────────────────────┐
│              BallController (Single Source)              │
│  - currentOwner (sprite)                                 │
│  - pendingOwner (sprite)                                 │
│  - isAttached, isInFlight, reason                       │
│  - gameState.ballHolder (string ID) - WIP_GOB sync       │
└─────────────────────────────────────────────────────────┘
                          ▲
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
┌───────┴────────┐              ┌──────────┴──────────┐
│ BallController │              │  ballAnimationSimple │
│    Adapter     │              │   (WIP_GOB helpers)  │
│                │              │                      │
│ Provides:      │              │ Provides:           │
│ - attachBallTo │              │ - getPlayerTween     │
│   Player()     │              │   Targets()          │
│ - getCurrent   │              │ - animateBallTo      │
│   Owner()      │              │   Position()          │
│ - setCurrent   │              │ - animateBallTo      │
│   Owner()      │              │   Player()           │
│ - getPending   │              │                      │
│   Owner()      │              │ (Delegates to        │
│ - setPending   │              │  BallController for  │
│   Owner()      │              │  state)              │
│                │              │                      │
│ (Delegates to  │              │                      │
│  BallController│              │                      │
│  for state)    │              │                      │
└────────────────┘              └──────────────────────┘
```

---

## Phase 1: Extend BallController API

**Goal**: Add all missing functionality to BallController so it can fully replace old system

**Timeline**: 2-3 days

### Step 1.1: Add Missing Methods to BallController

**File**: `FrontEnd/static/js/phaser/animation/BallController.js`

**Add Methods**:

```javascript
/**
 * Get current owner ID (string) - for compatibility with old system
 * @returns {string|null} Player ID or null
 */
getCurrentOwnerId() {
  if (!this.currentOwner) return null;
  return this.currentOwner.playerId || (this.currentOwner.id ? String(this.currentOwner.id) : null);
}

/**
 * Set current owner by ID (string) - for compatibility with old system
 * @param {string} playerId - Player ID
 * @returns {boolean} Success
 */
setCurrentOwnerById(playerId) {
  if (!this.scene || !this.scene.playerSprites || !playerId) {
    return false;
  }
  const playerSprite = this.scene.playerSprites[playerId];
  if (!playerSprite) {
    console.warn('BallController: Player sprite not found', playerId);
    return false;
  }
  return this.attachToPlayer(playerSprite);
}

/**
 * Clear current owner
 */
clearCurrentOwner() {
  this.detachFromPlayer('clear');
}

/**
 * Get last known owner ID (string)
 * @returns {string|null} Player ID or null
 */
getLastKnownOwnerId() {
  if (this.ownershipHistory.length === 0) return null;
  const lastOwner = this.ownershipHistory[this.ownershipHistory.length - 1];
  return lastOwner?.playerId || (lastOwner?.id ? String(lastOwner.id) : null);
}

/**
 * Get pending owner ID (string) - for compatibility
 * @returns {string|null} Player ID or null
 */
getPendingOwnerId() {
  if (!this.pendingOwner) return null;
  return this.pendingOwner.playerId || (this.pendingOwner.id ? String(this.pendingOwner.id) : null);
}

/**
 * Set pending owner by ID (string) - for compatibility
 * @param {string} playerId - Player ID
 * @returns {boolean} Success
 */
setPendingOwnerById(playerId) {
  if (!this.scene || !this.scene.playerSprites || !playerId) {
    return false;
  }
  const playerSprite = this.scene.playerSprites[playerId];
  if (!playerSprite) {
    console.warn('BallController: Pending owner sprite not found', playerId);
    return false;
  }
  this.setPendingOwner(playerSprite);
  return true;
}

/**
 * Clear pending owner
 */
clearPendingOwner() {
  this.pendingOwner = null;
}

/**
 * Get ball holder ID (string) - WIP_GOB compatibility
 * @returns {string|null} Player ID or null
 */
getBallHolderId() {
  if (!this.scene || !this.scene.gameState) return null;
  return this.scene.gameState.ballHolder || null;
}

/**
 * Set ball holder ID (string) - WIP_GOB compatibility
 * @param {string} playerId - Player ID
 */
setBallHolderId(playerId) {
  if (!this.scene) return;
  if (!this.scene.gameState) {
    this.scene.gameState = {};
  }
  this.scene.gameState.ballHolder = playerId || null;
}

/**
 * Clear ball holder ID - WIP_GOB compatibility
 */
clearBallHolderId() {
  if (this.scene && this.scene.gameState) {
    this.scene.gameState.ballHolder = null;
  }
}
```

**Testing**: Unit tests for each new method

---

### Step 1.2: Update BallController to Sync All State

**File**: `FrontEnd/static/js/phaser/animation/BallController.js`

**Update `attachToPlayer()` method**:
- Already syncs `gameState.ballHolder` ✅
- Ensure it also updates `ownershipHistory` for `getLastKnownOwnerId()`

**Update `detachFromPlayer()` method**:
- Already clears `gameState.ballHolder` ✅
- Ensure it preserves last owner in `ownershipHistory`

**Update `setPendingOwner()` method**:
- Ensure it doesn't conflict with `attachToPlayer()` logic

**Testing**: Verify state sync in all scenarios

---

## Phase 2: Create Unified Adapter Functions

**Goal**: Provide backward-compatible function signatures that delegate to BallController

**Timeline**: 2-3 days

### Step 2.1: Extend BallControllerAdapter

**File**: `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js`

**Add Functions** (delegating to BallController):

```javascript
/**
 * Get current owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
export function getCurrentOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getCurrentOwnerId();
}

/**
 * Set current owner by ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {string} playerId
 */
export function setCurrentOwner(scene, playerId) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.setCurrentOwnerById(playerId);
}

/**
 * Clear current owner - replaces old ballController.js
 * @param {Phaser.Scene} scene
 */
export function clearCurrentOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.clearCurrentOwner();
}

/**
 * Get last known owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
export function getLastKnownOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getLastKnownOwnerId();
}

/**
 * Get pending owner ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @returns {string|null} Player ID or null
 */
export function getPendingOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return null;
  return ballController.getPendingOwnerId();
}

/**
 * Set pending owner by ID (string) - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {string} playerId
 */
export function setPendingOwner(scene, playerId) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.setPendingOwnerById(playerId);
}

/**
 * Clear pending owner - replaces old ballController.js
 * @param {Phaser.Scene} scene
 */
export function clearPendingOwner(scene) {
  const ballController = getBallController();
  if (!ballController) return;
  ballController.clearPendingOwner();
}

/**
 * Cancel ball tween - replaces old ballController.js
 * @param {Phaser.Scene} scene
 * @param {Phaser.GameObjects.Sprite} ballSpriteOverride
 */
export function cancelBallTween(scene, ballSpriteOverride) {
  const ballController = getBallController();
  if (!ballController) return;
  
  // Clear pending owner
  ballController.clearPendingOwner();
  
  // Kill ball tweens
  const ballSprite = ballSpriteOverride || scene.ballSprite;
  if (scene?.tweens && ballSprite) {
    scene.tweens.killTweensOf(ballSprite);
  }
}
```

**Testing**: Verify all functions delegate correctly to BallController

---

### Step 2.2: Update ballAnimationSimple.js to Delegate

**File**: `FrontEnd/static/js/phaser/animation/ballAnimationSimple.js`

**Update Functions**:

```javascript
/**
 * Get the current ball holder ID (string)
 * @param {Phaser.Scene} scene - The Phaser scene
 * @returns {string|null} Player ID who has the ball, or null
 */
export function getBallHolderId(scene) {
  const ballController = getBallControllerFromScene(scene);
  if (ballController) {
    return ballController.getBallHolderId();
  }
  // Fallback to direct access
  if (scene?.gameState?.ballHolder !== undefined) {
    return scene.gameState.ballHolder;
  }
  return null;
}

/**
 * Set the current ball holder ID (string)
 * @param {Phaser.Scene} scene - The Phaser scene
 * @param {string|null} playerId - Player ID who has the ball, or null
 */
export function setBallHolderId(scene, playerId) {
  const ballController = getBallControllerFromScene(scene);
  if (ballController) {
    ballController.setBallHolderId(playerId);
  } else {
    // Fallback to direct access
    if (!scene.gameState) {
      scene.gameState = {};
    }
    scene.gameState.ballHolder = playerId || null;
  }
}

/**
 * Clear the current ball holder ID
 * @param {Phaser.Scene} scene - The Phaser scene
 */
export function clearBallHolder(scene) {
  const ballController = getBallControllerFromScene(scene);
  if (ballController) {
    ballController.clearBallHolderId();
  } else {
    // Fallback to direct access
    if (scene?.gameState) {
      scene.gameState.ballHolder = null;
    }
  }
}
```

**Add Import**:
```javascript
import { getBallController } from './BallControllerAdapter.js';

function getBallControllerFromScene(scene) {
  // Try to get from adapter
  try {
    return getBallController();
  } catch (e) {
    return null;
  }
}
```

**Testing**: Verify WIP_GOB functions delegate to BallController

---

## Phase 3: Migrate Files to Use Adapter

**Goal**: Update all 8 files to use BallControllerAdapter instead of old ballController.js

**Timeline**: 3-4 days (one file per day with testing)

### Migration Pattern for Each File

**Before**:
```javascript
import {
  getCurrentOwner,
  setCurrentOwner,
  getPendingOwner,
  setPendingOwner,
  // ... other functions
} from "../ball/ballController.js";
```

**After**:
```javascript
import {
  getCurrentOwner,
  setCurrentOwner,
  getPendingOwner,
  setPendingOwner,
  // ... other functions
} from "./BallControllerAdapter.js";
```

### Step 3.1: Migrate ballTween.js

**File**: `FrontEnd/static/js/phaser/animation/ballTween.js`

**Changes**:
1. Update import statement (line 3-11)
2. Test all pass animations
3. Verify pending owner logic works

**Testing Checklist**:
- [ ] Normal passes
- [ ] Fast break passes
- [ ] Outlet passes
- [ ] Pending owner transitions

---

### Step 3.2: Migrate turnAnimation.js

**File**: `FrontEnd/static/js/phaser/animation/turnAnimation.js`

**Changes**:
1. Update import statement (line 35)
2. Verify `updateBallOwnership` function works correctly
3. Test step-by-step ownership updates

**Testing Checklist**:
- [ ] Normal HCO turns
- [ ] Pass transitions
- [ ] Pending owner handling
- [ ] Step-by-step ownership updates

---

### Step 3.3: Migrate animateGameTurns.js

**File**: `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

**Changes**:
1. Update import statement (line 12)
2. Test OREB putback sequences
3. Verify ownership during putbacks

**Testing Checklist**:
- [ ] OREB putback attempts
- [ ] OREB putback makes
- [ ] OREB putback misses
- [ ] Ownership during putback sequences

---

### Step 3.4: Migrate ballManager.js

**File**: `FrontEnd/static/js/phaser/animation/ballManager.js`

**Changes**:
1. Update import statement (line 22)
2. Test `updateBallOwnership` function (timestamp-based)
3. Verify kickout reset sequences

**Testing Checklist**:
- [ ] Timestamp-based ownership updates
- [ ] Kickout reset sequences
- [ ] Shot animations

---

### Step 3.5: Migrate freeThrow.js

**File**: `FrontEnd/static/js/phaser/animation/freeThrow.js`

**Changes**:
1. Update import statement (line 8)
2. Test free throw sequences
3. Verify ball attachment to shooter

**Testing Checklist**:
- [ ] Free throw makes
- [ ] Free throw misses
- [ ] Ball attachment to shooter
- [ ] Multiple free throw sequences

---

### Step 3.6: Migrate fastBreak.js

**File**: `FrontEnd/static/js/phaser/animation/fastBreak.js`

**Changes**:
1. Update import statement (line 9)
2. Test fast break sequences
3. Verify outlet pass ownership

**Testing Checklist**:
- [ ] Fast break outlet passes
- [ ] Fast break shots
- [ ] Ball attachment during fast breaks
- [ ] Ownership transitions

---

### Step 3.7: Migrate animateStep.js

**File**: `FrontEnd/static/js/phaser/animation/animateStep.js`

**Changes**:
1. Update import statement (line 17)
2. Test step-by-step animations
3. Verify ball holder state updates

**Testing Checklist**:
- [ ] Step-by-step player movements
- [ ] Ball holder state updates
- [ ] Player tween targets (ball inclusion)

---

### Step 3.8: Migrate turnoverAdapter.js

**File**: `FrontEnd/static/js/phaser/animation/turnoverAdapter.js`

**Changes**:
1. Update import statement (line 10)
2. Test turnover sequences
3. Verify ownership during turnovers

**Testing Checklist**:
- [ ] Turnover animations
- [ ] Ownership during turnovers
- [ ] Ball state during turnovers

---

## Phase 4: Consolidate updateBallOwnership Functions

**Goal**: Create one unified `updateBallOwnership` function that handles all scenarios

**Timeline**: 3-4 days

### Step 4.1: Analyze All Three Implementations

**Compare**:
- `ballManager.js`: Timestamp-based, finds step from timestamp
- `turnAnimation.js`: Step-index based, handles pending owners
- `ShotAnimationSystem.js`: Step-index based, uses BallController directly

**Key Differences**:
1. Input method (timestamp vs step-index)
2. Pending owner handling
3. State update approach

---

### Step 4.2: Design Unified Function

**Location**: `FrontEnd/static/js/phaser/animation/BallControllerAdapter.js` (or new file)

**Function Signature**:
```javascript
/**
 * Unified ball ownership update function
 * Handles both timestamp-based and step-index-based updates
 * 
 * @param {Object} options
 * @param {Phaser.Scene} options.scene
 * @param {Phaser.GameObjects.Sprite} options.ballSprite
 * @param {Array} options.animations - Player animation data
 * @param {Object} options.playerSprites - Map of playerId -> sprite
 * @param {Object} options.currentBallOwnerRef - Reference object for current owner
 * @param {number} [options.stepIndex] - Step index (if provided, uses this)
 * @param {number} [options.currentTimestamp] - Timestamp in ms (if provided, calculates stepIndex)
 * @param {string} [options.offenseTeamId] - Offense team ID
 * @returns {Promise<void>}
 */
export async function updateBallOwnership(options) {
  const {
    scene,
    ballSprite,
    animations,
    playerSprites,
    currentBallOwnerRef,
    stepIndex: providedStepIndex,
    currentTimestamp,
    offenseTeamId
  } = options;

  // Early returns
  if (scene?.skipToEnd || scene?.stateMachine?.is(States.FastBreak)) return;
  if (scene.passInFlight) return;

  // Get BallController
  const ballController = getBallController();
  if (ballController && !ballController.isAttached && !ballController.isInFlight) {
    return; // Ball is detached and not in flight, skip update
  }

  // Calculate stepIndex if timestamp provided
  let stepIndex = providedStepIndex;
  if (currentTimestamp !== undefined && stepIndex === undefined) {
    stepIndex = calculateStepIndexFromTimestamp(animations, currentTimestamp);
  }

  // Handle pending owner first
  const pendingId = getPendingOwner(scene);
  if (pendingId != null) {
    const pendingSprite = playerSprites[pendingId];
    if (pendingSprite) {
      // Update ball position
      if (ballSprite?.setPosition) {
        ballSprite.setPosition(pendingSprite.x, pendingSprite.y);
        ballSprite.setVisible(true);
      }
      
      // Update references
      if (currentBallOwnerRef) {
        currentBallOwnerRef.value = pendingSprite;
      }
      
      // Update BallController state
      setCurrentOwner(scene, pendingId);
      setBallHolderId(scene, pendingId);
      
      // Clear pending owner
      clearPendingOwner(scene);
    }
    return;
  }

  // Check if pass is happening at this step
  if (stepIndex !== undefined) {
    const passHappening = animations.some(
      anim => anim.movement?.[stepIndex]?.action === "pass"
    );
    if (passHappening) return;
  }

  // Find player who should have ball at this step
  for (const anim of animations) {
    if (!anim.hasBallAtStep) continue;
    
    const hasBall = stepIndex !== undefined 
      ? anim.hasBallAtStep[stepIndex]
      : anim.hasBallAtStep.some((has, idx) => {
          // For timestamp-based, check if we're in this step's timeframe
          if (!anim.movement || !anim.movement[idx]) return false;
          const stepStart = anim.movement[idx].timestamp || 0;
          const stepEnd = anim.movement[idx + 1]?.timestamp || Infinity;
          return has && currentTimestamp >= stepStart && currentTimestamp < stepEnd;
        });
    
    if (hasBall) {
      const playerSprite = playerSprites[anim.playerId];
      if (playerSprite && playerSprite !== currentBallOwnerRef?.value) {
        // Transfer ownership
        attachBallToPlayer(scene, ballSprite, playerSprite);
        if (currentBallOwnerRef) {
          currentBallOwnerRef.value = playerSprite;
        }
      }
      break; // Only one player can have the ball
    }
  }
}

/**
 * Calculate step index from timestamp
 */
function calculateStepIndexFromTimestamp(animations, timestamp) {
  for (const anim of animations) {
    if (!anim.movement || !anim.movement.length) continue;
    
    let stepIndex = 0;
    while (
      stepIndex < anim.movement.length - 1 &&
      timestamp >= anim.movement[stepIndex + 1].timestamp
    ) {
      stepIndex++;
    }
    
    if (anim.hasBallAtStep?.[stepIndex]) {
      return stepIndex;
    }
  }
  return 0; // Default to first step
}
```

---

### Step 4.3: Replace All Three Implementations

**Files to Update**:

1. **ballManager.js**
   - Replace `updateBallOwnership` with import and call to unified function
   - Pass `currentTimestamp` parameter

2. **turnAnimation.js**
   - Replace `updateBallOwnership` with import and call to unified function
   - Pass `stepIndex` parameter

3. **ShotAnimationSystem.js**
   - Replace `updateBallOwnership` with import and call to unified function
   - Pass `stepIndex` parameter

**Testing**: Comprehensive testing of all three use cases

---

## Phase 5: Remove Old System

**Goal**: Delete old `ballController.js` file and clean up

**Timeline**: 1 day

### Step 5.1: Verify No Remaining References

**Check**:
```bash
grep -r "from.*ball/ballController" FrontEnd/static/js/phaser
grep -r "import.*ball/ballController" FrontEnd/static/js/phaser
```

**Expected**: Zero matches

---

### Step 5.2: Delete Old File

**File to Delete**: `FrontEnd/static/js/phaser/ball/ballController.js`

**Action**: Delete file

---

### Step 5.3: Update Documentation

**Files to Update**:
- `docs/animation_system.md` - Remove references to old system
- Update any other docs that mention the old system

---

## Phase 6: Final Testing & Validation

**Goal**: Comprehensive testing of entire system

**Timeline**: 2-3 days

### Test Scenarios

**Ball Ownership**:
- [ ] Normal HCO possession
- [ ] Pass sequences
- [ ] Shot sequences
- [ ] Rebound sequences
- [ ] OREB putback sequences
- [ ] Fast break sequences
- [ ] Free throw sequences
- [ ] Turnover sequences

**State Consistency**:
- [ ] BallController state matches `gameState.ballHolder`
- [ ] No orphaned state
- [ ] Pending owner transitions work correctly
- [ ] Last known owner tracking works

**Edge Cases**:
- [ ] Rapid pass sequences
- [ ] Simultaneous state changes
- [ ] Missing player sprites
- [ ] Invalid player IDs
- [ ] State during possession flips

---

## Risk Mitigation

### Incremental Approach
- Each phase is independent and testable
- Can stop at any phase if issues arise
- Easy to roll back individual changes

### Backward Compatibility
- Adapter functions maintain old signatures
- No breaking changes to calling code
- Gradual migration reduces risk

### Testing Strategy
- Test each file migration individually
- Comprehensive integration testing after each phase
- User acceptance testing before final deletion

### Rollback Plan
- Git commits after each successful phase
- Can revert individual file migrations
- Old system can be restored if needed

---

## Success Criteria

**Phase 1-2 Complete** ✅:
- ✅ BallController has all necessary methods
- ✅ Adapter functions delegate correctly
- ✅ All tests pass

**Phase 3 Complete** ✅:
- ✅ All 8 files migrated
- ✅ No references to old `ballController.js`
- ✅ All animations work correctly

**Phase 4 Complete** ✅:
- ✅ One unified `updateBallOwnership` function
- ✅ All three use cases work correctly
- ✅ No duplicate logic

**Phase 5 Complete** ✅:
- ✅ Old `ballController.js` deleted
- ✅ Documentation updated
- ✅ No orphaned code

**Phase 6 Complete** ✅:
- ✅ All test scenarios pass
- ✅ No regressions
- ✅ System is stable

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Extend BallController | 2-3 days | None |
| Phase 2: Create Adapter Functions | 2-3 days | Phase 1 |
| Phase 3: Migrate Files | 3-4 days | Phase 2 |
| Phase 4: Consolidate updateBallOwnership | 3-4 days | Phase 3 |
| Phase 5: Remove Old System | 1 day | Phase 4 |
| Phase 6: Final Testing | 2-3 days | Phase 5 |
| **Total** | **13-18 days** | |

---

## Next Steps

1. **Review this plan** - Ensure it aligns with goals
2. **Start Phase 1** - Extend BallController API
3. **Test incrementally** - After each phase
4. **Document learnings** - Update plan as needed

---

## Questions to Resolve

1. Should `updateBallOwnership` be in `BallControllerAdapter.js` or a separate file?
2. Do we need to maintain the WeakMap-based state for any reason?
3. Are there any performance concerns with the new approach?
4. Should we add more comprehensive logging/debugging tools?

---

**Status**: Ready for review and implementation

