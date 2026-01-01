# Sprite Cleanup Fix for Quarter Transitions

## Problem
When using "Sim to 4th Quarter", extra player sprites from Q1-Q3 lineups were persisting when Q4 animation started. These ghost sprites had no position labels or jersey numbers and would animate alongside the actual Q4 players.

## Root Cause
When Phaser's `scene.restart()` is called (line 297 of `bootGame.js`), it recreates the scene but does NOT automatically destroy sprites from the previous scene instance. The old sprites remained in the scene's children list even though new sprites were being created.

## Solution

### 1. Added `shutdown()` Lifecycle Method
Added a `shutdown()` method to `GameScene` that Phaser automatically calls before restarting the scene:

```javascript
shutdown() {
  if (DEBUG_FLOW) console.log("🧹 GameScene shutdown - cleaning up sprites");
  
  // Destroy all player sprites
  if (this.playerSprites) {
    Object.values(this.playerSprites).forEach(sprite => {
      if (sprite && sprite.destroy) {
        sprite.destroy();
      }
    });
    this.playerSprites = {};
  }
  
  // Destroy ball sprite if it exists
  if (this.ballSprite && this.ballSprite.destroy) {
    this.ballSprite.destroy();
    this.ballSprite = null;
  }
  
  // Clear other references
  this.nameToId = {};
  this.playerInfo = {};
  this.playerStats = {};
  
  console.log("✅ GameScene cleanup complete");
}
```

### 2. Added Defensive Cleanup in `create()`
Added additional cleanup at the start of `create()` to ensure a clean slate even if `shutdown()` wasn't called:

```javascript
// Ensure clean slate - destroy any existing sprites before creating new ones
if (this.playerSprites) {
  Object.values(this.playerSprites).forEach(sprite => {
    if (sprite && sprite.destroy) {
      sprite.destroy();
    }
  });
}
```

### 3. Added Diagnostic Logging
Added logging to track sprite counts before and after creation:
- `🔍 PRE-CREATION: Existing containers in scene: X`
- `🔍 POST-CREATION: Total containers in scene: Y`
- `🔍 POST-CREATION: playerSprites object size: Z`

This helps verify that:
- Old sprites are properly destroyed (PRE-CREATION should be 0 on Q4)
- New sprites are created correctly (POST-CREATION should equal 10: 5 home + 5 away)
- The playerSprites object matches the scene's children count

## Expected Behavior
After this fix:
1. When Q4 starts, `shutdown()` destroys all Q1-Q3 sprites
2. `create()` verifies no old sprites exist
3. Only 10 player sprites are created (5 per team)
4. Animation proceeds with clean sprite state

## Testing
To verify the fix works:
1. Start a game and press "Sim to 4th Quarter"
2. When Q4 animation begins, check console logs for:
   - `🧹 GameScene shutdown - cleaning up sprites`
   - `✅ GameScene cleanup complete`
   - `🔍 PRE-CREATION: Existing containers in scene: 0`
   - `🔍 POST-CREATION: Total containers in scene: 10`
3. Visually verify only 10 player sprites animate (no ghost sprites)

## Files Modified
- `FrontEnd/static/js/phaser/gameScene.js`
  - Added `shutdown()` method (lines 82-107)
  - Added defensive cleanup in `create()` (lines 132-139)
  - Added diagnostic logging (lines 385-402)

