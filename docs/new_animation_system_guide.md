# New Animation System - Developer Guide

## Overview

Welcome to the new animation system! This guide will help you understand how the basketball game animations work. Think of this system as a well-organized team where each player has a specific job, and they all work together to create smooth, realistic basketball animations.

## 🎯 What This System Does

The new animation system handles all the visual movements in our basketball game:
- **Shots** (regular shots, free throws, putbacks)
- **Passes** (inbound passes, outlet passes, kickouts)
- **Rebounds** (defensive and offensive)
- **Player movements** (running to positions, setting up plays)
- **Ball physics** (flying through the air, bouncing off rims)

## 🏗️ System Architecture

The system is built like a well-organized company with clear roles:

```
┌─────────────────────────────────────────────────────────────┐
│                    GAME SCENE                               │
│  (The basketball court where everything happens)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 ANIMATION ROUTER                            │
│  (The main boss - decides which system handles each turn)  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 ANIMATION ENGINE                            │
│  (The manager - coordinates all the animation systems)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              SPECIALIZED ANIMATION SYSTEMS                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│  │    SHOT     │ │    PASS     │ │   REBOUND   │ │   HCO   │ │
│  │   SYSTEM    │ │   SYSTEM    │ │   SYSTEM    │ │ SYSTEM  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 BALL CONTROLLER                             │
│  (The ball manager - keeps track of who has the ball)      │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Core Components

### 1. AnimationRouter (The Main Boss)
**File:** `AnimationRouter.js`

**What it does:**
- First thing that gets called when a turn needs to be animated
- Looks at the turn data and decides which system should handle it
- Makes sure only one animation runs at a time
- Handles the overall flow of the game

**Key Methods:**
- `processTurn(turnData)` - Main entry point for all animations
- `initialize()` - Sets up the system when the game starts

**Example:**
```javascript
// When a shot happens, the router says:
// "This is a shot, send it to the ShotAnimationSystem"
```

### 2. AnimationEngine (The Manager)
**File:** `AnimationEngine.js`

**What it does:**
- Coordinates all the different animation systems
- Makes sure they have the resources they need (ball, players, scene)
- Routes specific types of animations to the right system

**Key Systems it manages:**
- `shotSystem` - Handles all shots
- `passSystem` - Handles all passes  
- `reboundSystem` - Handles all rebounds
- `freeThrowSystem` - Handles free throws
- `hcoSystem` - Handles Half Court Offense positioning

**Example:**
```javascript
// Engine says: "This is a shot, use the ShotAnimationSystem"
// Engine says: "This is a pass, use the PassAnimationSystem"
```

### 3. BallController (The Ball Manager)
**File:** `BallController.js`

**What it does:**
- **Single source of truth** for who has the ball
- Prevents the ball from floating around or teleporting
- Manages ball attachment/detachment from players
- Tracks ball state (attached, in flight, etc.)

**Key Methods:**
- `attachToPlayer(playerSprite)` - Gives ball to a player
- `detachFromPlayer()` - Takes ball away from current player
- `startFlight()` - Ball is flying through the air
- `endFlight()` - Ball lands somewhere

**Why this is important:**
- Before: Ball could be in multiple places at once (bugs!)
- Now: Ball is always in exactly one place, managed by one system

### 4. Specialized Animation Systems

#### ShotAnimationSystem
**File:** `ShotAnimationSystem.js`

**What it handles:**
- Regular shots (jump shots, layups)
- Putback attempts (shots after offensive rebounds)
- Shot animations with proper ball flight
- Player movement during shots

**Key Process:**
1. Player gets the ball
2. Player moves to shooting position
3. Ball detaches and flies to rim
4. Ball either goes in (MAKE) or bounces off (MISS)
5. Handle the result (score or rebound)

#### PassAnimationSystem  
**File:** `PassAnimationSystem.js`

**What it handles:**
- Inbound passes (after made baskets)
- Outlet passes (after defensive rebounds)
- Regular passes between players

**Key Process:**
1. Player with ball moves to passing position
2. Ball flies from passer to receiver
3. Receiver catches the ball
4. Continue with next play

#### ReboundAnimationSystem
**File:** `ReboundAnimationSystem.js`

**What it handles:**
- Defensive rebounds (team gets ball after opponent misses)
- Offensive rebounds (team gets ball after their own miss)
- Player positioning during rebounds

#### FreeThrowAnimationSystem
**File:** `FreeThrowAnimationSystem.js`

**What it handles:**
- Free throw shots
- Free throw positioning
- Multiple free throw sequences (1+1, 2+1, etc.)

#### HCOAnimationSystem
**File:** `HCOAnimationSystem.js`

**What it handles:**
- Half Court Offense positioning
- The special step where players move to HCO positions
- Outlet passes from rebounders to point guards

## 🔄 How It All Works Together

### Step-by-Step Example: A Shot Animation

1. **Game Turn Starts**
   ```
   Backend sends: { result_type: "MISS", shooter_id: "player123", ... }
   ```

2. **AnimationRouter Gets Called**
   ```javascript
   router.processTurn(turnData)
   // Router says: "This is a shot, send to AnimationEngine"
   ```

3. **AnimationEngine Routes It**
   ```javascript
   engine.handleShotAttempt(turnData)
   // Engine says: "Use ShotAnimationSystem for this"
   ```

4. **ShotAnimationSystem Takes Over**
   ```javascript
   shotSystem.processShot(turnData)
   // Shot system handles the entire shot sequence
   ```

5. **BallController Manages the Ball**
   ```javascript
   ballController.attachToPlayer(shooter)  // Give ball to shooter
   ballController.detachFromPlayer()       // Ball flies to rim
   ballController.startFlight()            // Ball is in the air
   ballController.endFlight()              // Ball lands
   ```

6. **Animation Completes**
   ```
   System reports: "Shot animation finished"
   Game continues to next turn
   ```

## 🎮 Data Flow

### Input: Turn Data
The backend sends data like this:
```javascript
{
  result_type: "MISS",           // What happened
  shooter_id: "player123",       // Who did it
  shot_type: "JUMP_SHOT",        // How they did it
  animations: [...],             // Step-by-step movements
  events: [...]                  // Special events (like putbacks)
}
```

### Processing: Animation Systems
Each system looks at the data and decides:
- What animations to play
- How long they should take
- What the ball should do
- Where players should move

### Output: Visual Animation
- Players move smoothly to positions
- Ball flies realistically to targets
- Everything happens in the right order
- No floating balls or teleports

## 🛠️ Key Benefits of This System

### 1. **Single Source of Truth**
- Only one system manages the ball at a time
- No more "ball teleporting" bugs
- Clear ownership of who has the ball

### 2. **Modular Design**
- Each animation type has its own system
- Easy to add new animation types
- Easy to fix bugs in specific areas

### 3. **Consistent Behavior**
- All shots work the same way
- All passes work the same way
- Predictable, reliable animations

### 4. **Easy to Debug**
- Clear separation of concerns
- Each system has specific responsibilities
- Easy to trace where problems occur

## 🚨 Common Issues and How to Fix Them

### Issue: Ball Not Moving During Animation
**Possible Causes:**
- BallController not properly attached to player
- Wrong ball sprite being used
- Animation system not calling BallController methods

**How to Debug:**
1. Check console logs for BallController messages
2. Verify ball sprite is visible and positioned correctly
3. Make sure animation system is using `this.ballController.ballSprite`

### Issue: Players Not Moving to Correct Positions
**Possible Causes:**
- Player sprite references are wrong
- Animation data is missing or incorrect
- Grid-to-pixel conversion is wrong

**How to Debug:**
1. Check `playerSprites` object has correct player IDs
2. Verify animation data has correct coordinates
3. Test grid-to-pixel conversion with known values

### Issue: Animation System Not Being Called
**Possible Causes:**
- AnimationRouter not routing correctly
- Turn data format is wrong
- System not initialized properly

**How to Debug:**
1. Check AnimationRouter logs
2. Verify turn data has correct `result_type`
3. Make sure all systems are initialized

## 📝 Adding New Animation Types

### Step 1: Create New Animation System
```javascript
// NewAnimationSystem.js
export class NewAnimationSystem {
  constructor(scene, ballController, stateMachine, playerSprites) {
    this.scene = scene;
    this.ballController = ballController;
    // ... other setup
  }
  
  async processNewAnimation(turnData) {
    // Your animation logic here
  }
}
```

### Step 2: Add to AnimationEngine
```javascript
// In AnimationEngine.js
import NewAnimationSystem from './NewAnimationSystem.js';

// In constructor:
this.newSystem = null;

// In injectDependencies:
this.newSystem = new NewAnimationSystem(
  this.scene,
  this.ballController,
  this.stateMachine,
  this.playerSprites
);

// Add handler:
async handleNewAnimation(turnData, context) {
  if (this.newSystem) {
    await this.newSystem.processNewAnimation(turnData);
  }
}
```

### Step 3: Add Routing Logic
```javascript
// In AnimationRouter.js
if (turnData.result_type === 'NEW_ANIMATION_TYPE') {
  await this.animationEngine.handleNewAnimation(turnData, context);
}
```

## 🧪 Testing the System

### Console Logs to Watch For
- `AnimationRouter: Starting turn processing` - System is working
- `BallController: Ball attached to player` - Ball ownership working
- `ShotAnimationSystem: Processing shot` - Shot system working
- `AnimationEngine: Completed [TYPE]` - Animation finished

### Common Test Scenarios
1. **Regular Shot** - Should see ball fly from player to rim
2. **Pass** - Should see ball fly from passer to receiver  
3. **Rebound** - Should see players move to rebound positions
4. **Free Throw** - Should see proper free throw sequence

## 🎯 Best Practices

### 1. Always Use BallController
```javascript
// ✅ Good - Use BallController
this.ballController.attachToPlayer(playerSprite);

// ❌ Bad - Direct ball manipulation
ballSprite.x = playerSprite.x;
```

### 2. Check for Valid Data
```javascript
// ✅ Good - Validate data first
if (!turnData || !turnData.shooter_id) {
  console.error('Invalid turn data');
  return;
}

// ❌ Bad - Assume data is always correct
const shooter = this.playerSprites[turnData.shooter_id];
```

### 3. Use Proper Error Handling
```javascript
// ✅ Good - Handle errors gracefully
try {
  await this.processAnimation(turnData);
} catch (error) {
  console.error('Animation failed:', error);
  // Fallback or recovery logic
}
```

### 4. Log Important Events
```javascript
// ✅ Good - Log key events for debugging
console.log('🎬 Starting shot animation', {
  shooter: turnData.shooter_id,
  result: turnData.result_type
});
```

## 🔍 Debugging Tips

### 1. Enable Debug Logging
```javascript
// In BallController.js
this.debug = true; // Enables detailed logging
```

### 2. Check System Status
```javascript
// Get system status
const status = animationEngine.getStatus();
console.log('System status:', status);
```

### 3. Monitor Ball State
```javascript
// Check ball ownership
console.log('Ball owner:', ballController.currentOwner);
console.log('Ball attached:', ballController.isAttached);
console.log('Ball in flight:', ballController.isInFlight);
```

### 4. Trace Animation Flow
```javascript
// Add logging at key points
console.log('1. Router received turn');
console.log('2. Engine routing to system');
console.log('3. System processing animation');
console.log('4. BallController managing ball');
console.log('5. Animation complete');
```

## 📚 Related Files

### Core System Files
- `AnimationRouter.js` - Main entry point
- `AnimationEngine.js` - System coordinator
- `BallController.js` - Ball management
- `BallControllerAdapter.js` - Backward compatibility

### Animation System Files
- `ShotAnimationSystem.js` - Shot animations
- `PassAnimationSystem.js` - Pass animations
- `ReboundAnimationSystem.js` - Rebound animations
- `FreeThrowAnimationSystem.js` - Free throw animations
- `HCOAnimationSystem.js` - HCO positioning

### Utility Files
- `ballManager.js` - Ball animation utilities
- `turnAnimation.js` - Legacy animation system (being phased out)
- `gridToPixels.js` - Coordinate conversion
- `courtConstants.js` - Court layout constants

### Integration Files
- `animateGameTurns.js` - Main game loop integration
- `gameStateMachine.js` - Game state management

## 🎉 Conclusion

The new animation system is designed to be:
- **Simple** - Clear separation of responsibilities
- **Scalable** - Easy to add new animation types
- **Stable** - Reliable, bug-free animations

Remember: When in doubt, check the console logs. The system is designed to tell you exactly what's happening at each step. If something isn't working, the logs will usually point you in the right direction.

Happy coding! 🏀
