# Universal State Clearing Pattern

## The Fix That Stopped Skipping Rebound Steps

### What We Changed

In `ShotAnimationSystem.handleMissedShot()` (line 499-542), we added:

```javascript
// Animate ball bounce from rim
await this.animateBallBounce(rimCoords, turnData);

// ✅ PRIORITY 1 FIX: Call onShotEnd() to clear in-flight state before rebound
// This matches the pattern in ballManager.js (line 626)
// The ball is no longer in flight, so clear the state to allow attachment to rebounder
this.ballController.onShotEnd();

// Check if this shot turn includes rebound data
if (turnData.rebounderId && turnData.rebound_type) {
  // Handle the rebound within the shot turn
  await this.handleEmbeddedRebound(turnData);
}
```

### Key Insight

**The critical fix**: Calling `onShotEnd()` BEFORE checking for rebound data and handling the rebound.

**Why this works**:
1. `onShotEnd()` clears the `isInFlight` state in BallController
2. This allows the ball to be properly attached to the rebounder
3. Without clearing state first, the ball remains in "in-flight" state, which blocks attachment
4. This causes the rebound handling to fail silently or skip steps

---

## Universal Pattern: State Clearing Before Transition

### Pattern Definition

**Always clear the current operation's state BEFORE transitioning to the next operation.**

### The Pattern

```javascript
// 1. Complete current operation
await completeCurrentOperation();

// 2. Clear state via lifecycle method (CRITICAL - must be before next operation)
this.ballController.onShotEnd(); // or onPassEnd(), onPutbackEnd(), etc.

// 3. Validate data for next operation
if (hasDataForNextOperation) {
  // 4. Proceed to next operation
  await handleNextOperation();
}
```

### Why This Matters

**State conflicts cause skipped steps**:
- If state isn't cleared, the next operation can't properly initialize
- BallController's internal state (`isInFlight`, `reason`, etc.) blocks operations
- Operations fail silently when state is incorrect

**Sequencing is critical**:
- State must be cleared AFTER current operation completes
- State must be cleared BEFORE next operation starts
- Validation must happen AFTER state is cleared

---

## Application Across Animation Systems

### Pattern 1: Shot → Rebound

```javascript
// ✅ CORRECT
async handleMissedShot() {
  await animateBallBounce();
  this.ballController.onShotEnd(); // Clear shot state
  if (hasReboundData) {
    await handleRebound(); // Can now attach ball to rebounder
  }
}

// ❌ WRONG
async handleMissedShot() {
  await animateBallBounce();
  if (hasReboundData) {
    await handleRebound(); // State still in-flight, attachment fails
  }
  this.ballController.onShotEnd(); // Too late!
}
```

### Pattern 2: Rebound → Outlet Pass

```javascript
// ✅ CORRECT
async handleDefensiveRebound() {
  await attachBallToRebounder();
  // State is already cleared by onShotEnd() above
  if (nextPlayType === 'HCO' || 'HCT' || 'FCP') {
    await runDefensiveReboundSetup(); // Can proceed with outlet pass
  }
}
```

### Pattern 3: Pass → Next Operation

```javascript
// ✅ CORRECT
async executePass() {
  this.ballController.onPassStart({ passerId, receiverId });
  await animatePassFlight();
  this.ballController.onPassEnd(receiverSprite); // Clear pass state
  // Ball is now attached to receiver, ready for next operation
}
```

### Pattern 4: Putback → Rebound

```javascript
// ✅ CORRECT (from handleOrebTurn)
async handlePutbackMiss() {
  await animatePutback();
  this.ballController.onPutbackEnd(); // Clear putback state
  if (hasReboundData) {
    await handleRebound(); // Can now attach ball to rebounder
  }
}
```

---

## Lifecycle Methods Reference

### BallController Lifecycle Methods

| Method | When to Call | Clears State | Next Operation |
|--------|--------------|--------------|----------------|
| `onShotStart()` | When shot begins | Sets `isInFlight = true` | Shot animation |
| `onShotEnd()` | After shot completes | Clears `isInFlight` | Rebound or inbound |
| `onPassStart()` | When pass begins | Sets `isInFlight = true` | Pass animation |
| `onPassEnd()` | After pass completes | Clears `isInFlight`, attaches to receiver | Next operation |
| `onPutbackStart()` | When putback begins | Sets `isInFlight = true` | Putback animation |
| `onPutbackEnd()` | After putback completes | Clears `isInFlight` | Rebound or inbound |

### State Transitions

```
IDLE → onShotStart() → IN_FLIGHT (shot) → onShotEnd() → IDLE → attachToPlayer() → ATTACHED
IDLE → onPassStart() → IN_FLIGHT (pass) → onPassEnd() → ATTACHED (to receiver)
IDLE → onPutbackStart() → IN_FLIGHT (putback) → onPutbackEnd() → IDLE → attachToPlayer() → ATTACHED
```

---

## Validation Pattern

### Always Validate After State Clearing

```javascript
// ✅ CORRECT
this.ballController.onShotEnd(); // Clear state first
if (turnData.rebounderId && turnData.rebound_type) {
  // Data is validated, state is clear, proceed
  await handleRebound();
}

// ❌ WRONG
if (turnData.rebounderId && turnData.rebound_type) {
  // State not cleared yet, validation happens but operation may fail
  await handleRebound();
  this.ballController.onShotEnd(); // Too late!
}
```

---

## Common Mistakes

### Mistake 1: Forgetting to Clear State

```javascript
// ❌ WRONG
async handleMissedShot() {
  await animateBallBounce();
  // Missing: this.ballController.onShotEnd();
  await handleRebound(); // Fails because state is still in-flight
}
```

### Mistake 2: Clearing State Too Late

```javascript
// ❌ WRONG
async handleMissedShot() {
  await animateBallBounce();
  await handleRebound(); // Tries to attach ball while still in-flight
  this.ballController.onShotEnd(); // Too late!
}
```

### Mistake 3: Clearing State in Wrong Order

```javascript
// ❌ WRONG
async handleMissedShot() {
  this.ballController.onShotEnd(); // Too early! Shot bounce hasn't completed
  await animateBallBounce();
  await handleRebound();
}
```

---

## Implementation Checklist

When implementing a new animation operation:

- [ ] Identify the lifecycle method to call (`onShotEnd()`, `onPassEnd()`, etc.)
- [ ] Call it AFTER the current operation completes
- [ ] Call it BEFORE the next operation starts
- [ ] Validate data AFTER state is cleared
- [ ] Test that state transitions work correctly
- [ ] Verify no skipped steps occur

---

## Examples from Codebase

### ✅ Correct: ballManager.js (line 626)

```javascript
if (ballController) {
  ballController.onShotEnd(); // Called after shot result determined
}

if (result === "MAKE") {
  // Handle make
} else if (result === "MISS") {
  // Handle miss - state is already cleared
  await bounceFromRim();
  // Rebound handling can proceed
}
```

### ✅ Correct: ShotAnimationSystem.js (line 513)

```javascript
async handleMissedShot() {
  await this.animateBallBounce();
  this.ballController.onShotEnd(); // Clear state before rebound
  if (turnData.rebounderId && turnData.rebound_type) {
    await this.handleEmbeddedRebound(); // Can proceed
  }
}
```

### ✅ Correct: handleOrebTurn (line 240)

```javascript
if (ballController) {
  ballController.onPutbackEnd(); // Clear putback state
}

// Then proceed with DREB setup
await runDefensiveReboundSetup();
```

---

## Universal Application

This pattern should be applied to:

1. **All shot types** → Rebound transitions
2. **All pass types** → Next operation transitions
3. **All putback types** → Rebound transitions
4. **All rebound types** → Outlet pass transitions
5. **Any operation** → Next operation transition

**The rule**: Always clear state before transitioning to the next operation.

---

*Document created: Based on Priority 1 fix that resolved skipped rebound steps*

