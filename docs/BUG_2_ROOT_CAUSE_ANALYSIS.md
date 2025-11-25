# Bug 2: HCO Passes Teleporting - Root Cause Analysis

## Problem Statement
Many HCO passes teleport instead of animating smoothly. The ball appears to instantly jump from passer to receiver without the smooth arc animation.

## Root Cause

### The Broken Flow

1. **`animateStep` detects pass action** (line 285-298 in `animateStep.js`):
   - When `nextStep.action === 'pass'`, it calls `onAction("pass", sprite, timestamp)`
   - This happens in the `onStart` callback (for non-delayed passes) or `onComplete` callback (for delayed first-step passes)

2. **`onAction` only does visual effects** (`onAction.js` lines 17-26):
   - When action is "pass", it only animates a scale effect on the passer sprite
   - **It does NOT call `runPass()`** to animate the ball

3. **`updateBallOwnership` detects pass and returns early** (`BallControllerAdapter.js` lines 440-446):
   ```javascript
   // Check if pass is happening at this step
   if (stepIndex !== undefined) {
     const passHappening = animations.some(
       anim => anim.movement?.[stepIndex]?.action === "pass"
     );
     if (passHappening) return;  // ❌ RETURNS EARLY - DOES NOTHING!
   }
   ```
   - When a pass is detected, it returns early without calling `runPass()`
   - This means the ball ownership changes but the ball never animates

4. **Result**: Ball teleports from passer to receiver position (via `updateBallOwnership`'s `setPosition` call at line 484) instead of animating smoothly

### Why Inbound Passes Work

Inbound passes work because they **explicitly call `runPass()`**:
- `runInboundSetup` (line 1260 in `turnAnimation.js`) calls `await runPass(scene, { fromId: sfId, toId: pgId, ... })`
- `runSideInboundSetup` (line 331 in `turnAnimation.js`) calls `await runPass(scene, { fromId: sfId, toId: pgId, ... })`

HCO passes rely on the `onAction` callback system, which doesn't call `runPass()`.

### Evidence from Test Scene

`testScene.js` (lines 89-101) shows the intended pattern:
```javascript
onAction: (action, sprite, timestamp) => {
  onAction(action, sprite, timestamp);  // Visual effects
  
  if (action === "pass") {
    passBall({  // ✅ ACTUALLY ANIMATES THE PASS
      scene: this,
      ballSprite: this.ballSprite,
      fromCoords: passStep.coords,
      toCoords: receiveStep.coords,
      ...
    });
  }
}
```

The test scene shows that `onAction` should trigger the actual pass animation, but the production `onAction` function doesn't do this.

## The Fix Strategy

### Option 1: Enhance `onAction` to Call `runPass` (RECOMMENDED)
**Pros**: 
- Matches the pattern shown in `testScene.js`
- Centralizes pass animation logic
- Works for all pass types (HCO, inbound, etc.)

**Cons**:
- Need to determine receiver from animation data
- Need to handle timing (when to call `runPass`)

**Implementation**:
1. Modify `onAction` in `onAction.js` to detect "pass" action
2. Find the receiver from `turnData.animations` (player with `action === "receive"` at same step)
3. Call `runPass(scene, { fromId: passerId, toId: receiverId })`
4. Keep visual effects for passer sprite

### Option 2: Modify `updateBallOwnership` to Call `runPass`
**Pros**:
- Already has access to animation data
- Already knows which step has the pass

**Cons**:
- `updateBallOwnership` is called frequently - need to ensure `runPass` is only called once
- Mixes ownership tracking with animation triggering (separation of concerns)

**Implementation**:
1. When `updateBallOwnership` detects a pass (line 442-445), instead of returning early:
   - Find passer (player with `action === "pass"` at this step)
   - Find receiver (player with `action === "receive"` at this step)
   - Call `runPass(scene, { fromId: passerId, toId: receiverId })`
   - Return early (don't update ownership - `runPass` handles that)

### Option 3: Add Pass Detection in `playTurnAnimation` Step Loop
**Pros**:
- Clear separation: step loop detects passes, triggers animations
- Easy to add logging/debugging

**Cons**:
- Duplicates pass detection logic (already in `animateStep` and `updateBallOwnership`)
- Need to ensure timing is correct

**Implementation**:
1. In `playTurnAnimation` step loop (line 1471+), before calling `animateStep`:
   - Check if any player has `action === "pass"` at this step
   - If yes, find receiver and call `runPass()` before animating steps
   - This ensures pass animation happens before player movements

## Recommended Solution: Option 1 (Enhance `onAction`)

**Why**: 
- Matches the intended pattern (test scene shows this)
- Centralizes pass animation logic
- Works for all pass types
- `onAction` is already being called at the right time

**Implementation Details**:

1. **Modify `onAction.js`**:
   - Import `runPass` from `ballTween.js`
   - When `action === "pass"`:
     - Find receiver from scene's current turn data
     - Call `runPass(scene, { fromId: sprite.playerId, toId: receiverId })`
     - Keep existing visual effects

2. **Challenge: Finding the receiver**:
   - Need access to `turnData.animations` to find receiver
   - Receiver has `action === "receive"` at the same step
   - May need to pass `turnData` or `animations` to `onAction` callback
   - OR: Store current turn data on scene (e.g., `scene.currentTurnData`)

3. **Timing considerations**:
   - `onAction` is called from `animateStep.onStart` (for non-delayed) or `onComplete` (for delayed)
   - `runPass` should be called at the same time
   - Need to ensure `runPass` doesn't conflict with player movement tweens

## Files to Modify

1. **`FrontEnd/static/js/phaser/animation/onAction.js`**:
   - Add pass detection and `runPass` call
   - Need to determine how to access receiver information

2. **`FrontEnd/static/js/phaser/animation/turnAnimation.js`**:
   - May need to pass `turnData` or `animations` to `onAction` callback
   - OR: Set `scene.currentTurnData = turnData` before step loop

3. **`FrontEnd/static/js/phaser/animation/BallControllerAdapter.js`**:
   - May need to adjust `updateBallOwnership` logic if `runPass` is now handling ownership

## Testing Strategy

1. Test HCO passes (multiple passes in one possession)
2. Test first-step HCO passes (delayed passes)
3. Test inbound passes (ensure they still work)
4. Test outlet passes (ensure they still work)
5. Verify ball animates smoothly with arc, not teleporting
6. Verify ball ownership is correct after pass completes

## Risk Assessment

**Risk Level**: Medium
- Changing `onAction` affects all action types
- Need to ensure `runPass` timing doesn't conflict with player movements
- Need to ensure receiver detection is reliable

**Mitigation**:
- Add extensive logging to trace pass detection and `runPass` calls
- Test thoroughly with different pass scenarios
- Keep visual effects separate from animation logic

