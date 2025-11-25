# Bug 2: HCO Passes Teleporting - Comparison Analysis

## Working Cases vs Broken Case

### ✅ WORKING: Shots (HCO Shots Animate Properly)

**Flow in `turnAnimation.js` (lines 1504-1644)**:

1. **Detection in Step Loop** (line 1551):
   ```javascript
   if (nextStep.action === "shoot") {
     shotInfo = { step: nextStep, playerId: anim.playerId, stepIndex };
   }
   ```
   - Detects shoot action during step loop
   - Stores shot info (step, playerId, stepIndex)

2. **Player Movements Complete** (line 1570):
   ```javascript
   await Promise.all(promises);  // All player movements finish
   ```

3. **Explicit Animation Call** (line 1572-1644):
   ```javascript
   if (shotInfo) {
     // Build shootParams with all necessary data
     const shootParams = { scene, ballSprite, fromCoords, ... };
     // Explicitly call shootBall
     const shotResult = await shootBall(shootParams);
   }
   ```
   - **Does NOT rely on `onAction` callback**
   - Explicitly calls `shootBall()` after movements complete
   - Has all necessary data (coords, shooterId, etc.)

### ✅ WORKING: Fast Break Outlet Passes

**Flow in `fastBreak.js` (lines 120-267)**:

1. **Direct Access to Passer/Receiver** (lines 121-124):
   ```javascript
   const passerId = turnData.roles.outlet_passer;
   const receiverId = turnData.roles.outlet_receiver;
   const passerSprite = playerSprites[passerId];
   const receiverSprite = playerSprites[receiverId];
   ```
   - Has explicit passer and receiver IDs from `turnData.roles`

2. **Player Movements Complete** (line 259):
   ```javascript
   await Promise.all(promises);  // All movements finish
   ```

3. **Explicit Animation Call** (lines 262-267):
   ```javascript
   await runPass(scene, {
     fromId: passerId,
     toId: receiverId,
     duration: 500,
     easing: "Sine.easeInOut"
   });
   ```
   - **Does NOT rely on `onAction` callback**
   - Explicitly calls `runPass()` with known passer/receiver IDs
   - Called after all player movements complete

### ✅ WORKING: Inbound Passes

**Flow in `turnAnimation.js` (lines 790-1284)**:

1. **Direct Access to Passer/Receiver** (lines 1239-1241):
   ```javascript
   const sfId = offenseIds["SF"];
   const pgId = offenseIds["PG"];
   attachBallToPlayer(scene, ballSprite, sfSprite);
   ```

2. **Explicit Animation Call** (lines 1260-1265):
   ```javascript
   await runPass(scene, {
     fromId: sfId,
     toId: pgId,
     duration: 500,
     easing: "Sine.easeInOut"
   });
   ```
   - **Does NOT rely on `onAction` callback**
   - Explicitly calls `runPass()` with known passer/receiver IDs

### ❌ BROKEN: HCO Passes

**Flow in `turnAnimation.js` (lines 1475-1568)**:

1. **Detection in Step Loop** (line 1555):
   ```javascript
   const promise = animateStep({
     scene,
     sprite,
     step: prev,
     nextStep: curr,  // Contains action: "pass"
     ...
     onAction,  // Callback passed in
     stepIndex
   });
   ```

2. **`animateStep` Calls `onAction`** (lines 285-298 in `animateStep.js`):
   ```javascript
   if (currentAction && onAction && !shouldDelayPass) {
     await onAction(currentAction, sprite, nextStep?.timestamp || step.timestamp);
   }
   ```

3. **`onAction` Only Does Visual Effects** (`onAction.js` lines 17-26):
   ```javascript
   case "pass":
     // Quick scale-out and in
     scene.tweens.add({
       targets: sprite,
       scale: 1.2,
       duration: 100,
       yoyo: true,
       ease: "Quad.easeInOut"
     });
     break;
   ```
   - **Does NOT call `runPass()`**
   - Only animates scale effect on passer sprite

4. **`updateBallOwnership` Detects Pass and Returns Early** (`BallControllerAdapter.js` lines 440-446):
   ```javascript
   const passHappening = animations.some(
     anim => anim.movement?.[stepIndex]?.action === "pass"
   );
   if (passHappening) return;  // ❌ RETURNS EARLY - DOES NOTHING!
   ```

5. **Result**: Ball teleports via `setPosition()` (line 484) instead of animating

## Key Differences

| Aspect | Shots (✅) | Fast Break Outlet (✅) | Inbound (✅) | HCO Passes (❌) |
|--------|-----------|------------------------|-------------|-----------------|
| **Detection** | In step loop, stores `shotInfo` | Direct from `turnData.roles` | Direct from `turnData` | Via `onAction` callback |
| **Animation Trigger** | Explicit `shootBall()` call | Explicit `runPass()` call | Explicit `runPass()` call | `onAction()` only does visual effects |
| **Timing** | After `Promise.all(promises)` | After `Promise.all(promises)` | After setup complete | During `animateStep.onStart` |
| **Data Access** | Has all data (coords, shooterId) | Has passer/receiver IDs | Has passer/receiver IDs | Only has passer sprite, no receiver info |
| **Relies on `onAction`?** | ❌ No | ❌ No | ❌ No | ✅ Yes (but `onAction` doesn't call `runPass`) |

## The Pattern

**All working cases follow this pattern:**
1. Detect action (shoot/pass) during step loop or setup
2. Store necessary data (player IDs, coords, etc.)
3. Wait for player movements to complete
4. **Explicitly call animation function** (`shootBall()` or `runPass()`)

**HCO passes break this pattern:**
1. Detect action via `onAction` callback
2. `onAction` only does visual effects
3. No explicit `runPass()` call
4. Ball teleports instead of animating

## Validated Hypothesis

✅ **My hypothesis is CORRECT**: HCO passes teleport because `runPass()` is never called.

The comparison confirms:
- Shots work because they explicitly call `shootBall()` after detecting the action
- Fast break outlet passes work because they explicitly call `runPass()` with known IDs
- Inbound passes work because they explicitly call `runPass()` with known IDs
- HCO passes fail because they rely on `onAction` callback, which doesn't call `runPass()`

## Recommended Fix (Validated by Comparison)

**Follow the shot pattern** - detect passes in step loop, store pass info, then explicitly call `runPass()`:

1. **In `turnAnimation.js` step loop** (around line 1551):
   ```javascript
   let passInfo = null;
   if (nextStep.action === "pass") {
     // Find receiver (player with action === "receive" at same step)
     const receiverAnim = turnData.animations.find(anim => 
       anim.movement?.[stepIndex]?.action === "receive"
     );
     if (receiverAnim) {
       passInfo = {
         passerId: anim.playerId,
         receiverId: receiverAnim.playerId,
         stepIndex
       };
     }
   }
   ```

2. **After player movements complete** (after line 1570):
   ```javascript
   await Promise.all(promises);
   
   // Handle passes (like shots)
   if (passInfo) {
     await runPass(scene, {
       fromId: passInfo.passerId,
       toId: passInfo.receiverId,
       duration: 500,  // Or calculate from distance
       easing: "Sine.easeInOut"
     });
   }
   
   // Handle shots (existing code)
   if (shotInfo) {
     await shootBall(shootParams);
   }
   ```

This matches the exact pattern used for shots, which works correctly.

