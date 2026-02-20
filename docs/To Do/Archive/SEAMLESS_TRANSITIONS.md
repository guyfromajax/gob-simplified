# Seamless Turn Transitions: WIP_GOB System Analysis

## Overview

This document analyzes how the WIP_GOB animation system achieved seamless transitions between game turns, creating a continuous visual flow with no pauses or gaps between turns.

## Key Mechanisms

### 1. Sequential Loop with BallSpot Bridging

The WIP_GOB system processes all turns in a single sequential loop:

```typescript
// useFullAnimation.ts (line 29)
for (let progressIndex = 0; progressIndex < userMatch.matchProgress.length; progressIndex++) {
  const matchProgress = userMatch.matchProgress.at(progressIndex)!;
  const nextProgress = userMatch.matchProgress.at(progressIndex + 1); // Get next turn
  
  await continueGame({ 
    scene, 
    homeTeamCoords, 
    awayTeamCoords, 
    matchStatus, 
    beforeTipOff, 
    prevAnimationLastBallHolder, 
    prevMatchStatus, 
    awayTeamStats, 
    homeTeamStats, 
    nextProgress  // Pass next turn for bridging
  });
}
```

**Key Point**: The `nextProgress` is passed to `continueGame`, allowing it to immediately start bridging animations before the next turn begins.

### 2. BallSpot Transition Mechanism

The core seamless transition happens through **BallSpot coordinates** that act as visual bridges between turns.

#### How It Works

After each turn completes (basket or miss), the system checks:

1. Does `currentStep?.ballSpot` exist? (Rebound location, steal spot, etc.)
2. Does `nextProgress` exist? (The next turn is available)

If both conditions are met, the system **immediately** animates:

- The ball to the `ballSpot` location
- The next turn's ball holder to the `ballSpot` location

Both animations happen **concurrently** using `createConcurrentTweens()`.

#### Implementation

```typescript
// useContinueGame.ts (lines 245-295)
// After shot completes (make or miss), handle ball spot if it exists
scene.game.state.signal = "stop"; // Stop idle animations

if (currentStep?.ballSpot && nextProgress && (isBasket == false || isBasket == true)) {
  const nextMatchStatus = nextProgress.matchStatus;
  
  // Get next turn's ball holder
  const { currentStep: nextAnimCurrentStep, ... } = getInitialDetails(nextMatchStatus, 0);
  const { currentBallHolder: nextAnimCurrentBallHolder, ... } = getInitialBallHolders({ ... });
  const { phaserBallHolder: nextAnimPlayerPhaser, ... } = getPhaserBallHolder({ ... });
  
  const targetX = XtoPx({ feet: currentStep.ballSpot.x, total: playGround.xAxis });
  const targetY = YtoPx({ feet: currentStep.ballSpot.y, total: playGround.yAxis });
  
  scene.game.state.isBallSpot = true;
  scene.game.state.ballHolder = nextBallHolderChose;
  
  // Calculate durations
  const duration = getPlayerDuration({ newX: targetX, newY: targetY, phaserPlayer: nextBallHolderChosePhaser });
  const ballDuration = getBallDuration({ basketball: basketBall, newX: targetX, newY: targetY });
  
  // Create concurrent tweens for ball and player
  const ballTweenConfig = {
    targets: [basketBall, scene.game.state.basketBallShadow],
    x: targetX,
    y: targetY,
    scale: 2,
    ease: "Linear",
    duration: ballDuration,
  };
  
  const playerTweenConfig = {
    targets: [nextBallHolderChosePhaser.phaserPlayer, nextBallHolderChosePhaser.jerseyNo],
    x: targetX,
    y: targetY,
    ease: "Linear",
    duration: duration,
  };
  
  // Animate both simultaneously
  createConcurrentTweens({ tweens: [ballTweenConfig, playerTweenConfig], scene })
    .then(() => (scene.game.state.isBallSpot = false));
}
```

### 3. Signal System (Conflict Prevention)

A signal system prevents animation conflicts during transitions:

```typescript
// Stop idle/dribble animations during critical transitions
scene.game.state.signal = "stop";

// Resume idle animations after transition completes
scene.game.state.signal = "start";

// Flag that ballSpot animation is in progress
scene.game.state.isBallSpot = true;
```

**Purpose**: 
- Prevents dribble animations from interfering with ballSpot transitions
- Ensures clean state during turn boundaries
- Allows for coordinated animation starts/stops

### 4. Handling Different Travel Distances

When players have different distances to travel in a turn, WIP_GOB uses **Promise.all()** to wait for all animations to complete.

#### Implementation

```typescript
// usePlayerAnimation.ts (lines 168-225)
const animatePlayerCoords = async ({ scene, phaserPlayers, playersCoords, ... }) => {
  let animationPromises = [];
  
  for (let p in phaserPlayers) {
    // Calculate duration based on distance for THIS player
    currentPlayerDuration = getPlayerDuration({ 
      phaserPlayer: phaserPlayers[p], 
      newX: coordinate.x, 
      newY: coordinate.y 
    });
    
    // Create animation promise for THIS player
    const animationPromise = animatePlayer({
      scene,
      player,
      targetX: coordinate.x,
      targetY: coordinate.y,
      duration: currentPlayerDuration, // Each player gets their own duration
      ...
    });
    
    animationPromises.push(animationPromise);
  }
  
  // ✅ KEY: Wait for ALL players to finish before continuing
  return Promise.all(animationPromises);
}
```

#### What Happens

1. **All players start moving simultaneously** (concurrent start)
2. **Each player gets duration based on their distance**:
   - Short distance: short duration (e.g., 200ms)
   - Long distance: long duration (e.g., 2000ms)
3. **Promise.all() waits for the longest animation** to complete
4. **Next step starts immediately** when all finish (no pause)

#### Why It Feels Seamless

- **Consistent Speed**: Distance-based duration means everyone moves at the same speed (e.g., `velocity.v200`), just different distances
- **Concurrent Start**: All players begin together
- **No Pause Between Steps**: As soon as the longest animation completes, the next step starts immediately
- **Step-by-Step Structure**: Each step is independent, so players don't need to be perfectly synchronized across steps

### 5. Distance-Based Duration Calculations

All animations use distance-based duration for consistent speed:

```typescript
// useDurations.ts
function getPlayerDuration({ newX, newY, phaserPlayer }: PlayerDurationType) {
  const oldX = phaserPlayer.phaserPlayer.x;
  const oldY = phaserPlayer.phaserPlayer.y;
  const { velocity } = phaserPlayer.phaserPlayer.scene.game.state;
  return getDuration({ newX, newY, oldX, oldY, speed: velocity.v200 });
}

function getBallDuration({ basketball, newX, newY }: BallDurationType) {
  if (!basketball) return 0;
  const { velocity } = basketball.scene.game.state;
  const oldX = basketball.x;
  const oldY = basketball.y;
  return getDuration({ newX, newY, oldX, oldY, speed: velocity.v250 });
}

function getDuration({ newX, newY, oldX, oldY, speed }: DurationType) {
  const distance = Phaser.Math.Distance.Between(oldX, oldY, newX, newY);
  const duration = (distance / speed) * 1000;
  return duration;
}
```

**Speed Constants**:
- Players: `velocity.v200` (200 units per second)
- Ball: `velocity.v250` (250 units per second)

### 6. Concurrent Tween System

Multiple tweens can run simultaneously using `Promise.all()`:

```typescript
// useTweens.ts
const createConcurrentTweens = ({ scene, tweens }: RunMultipleTweens) => {
  return Promise.all(tweens.map((tweenConfig) => createTweenPromise({ scene, tweenConfig })));
};

const createTweenPromise = ({ scene, tweenConfig }: CreateTween) => {
  return new Promise((resolve) =>
    scene.tweens.add({
      ...tweenConfig,
      onComplete: resolve,
    })
  );
};
```

## Architecture Flow

### Turn Processing Flow

```
1. Start Turn N
   ↓
2. Process all steps in Turn N sequentially
   ├─ Step 0: Animate all players (Promise.all waits for all)
   ├─ Step 1: Animate all players (Promise.all waits for all)
   └─ Step N: Final step completes
   ↓
3. Turn N completes (basket/miss/rebound/etc.)
   ↓
4. Check: Does currentStep have ballSpot? Does nextProgress exist?
   ↓
5. If YES: Immediately start ballSpot bridging animation
   ├─ Animate ball to ballSpot (concurrent)
   └─ Animate next player to ballSpot (concurrent)
   ↓
6. Wait for ballSpot animations to complete
   ↓
7. Start Turn N+1 immediately (no pause)
```

### Visual Timeline

```
Turn N:         [Step 0][Step 1][Step 2][Shot][BallSpot Animation]───
                                                                    │
Turn N+1:                                                          [Step 0][Step 1]...
                                                                    │
                                              No Gap ───────────────┘
```

## Key Differences from Current System

### Current System (Gob-Simplified)

- ✅ Uses `Promise.all()` for concurrent animations (same pattern)
- ✅ Distance-based duration calculations (same approach)
- ✅ Step-by-step sequential processing (similar structure)
- ❌ **Missing**: BallSpot bridging mechanism between turns
- ❌ **Missing**: Immediate turn transition without API calls
- ❌ **Different**: Processes turns individually with API calls between them

### WIP_GOB System

- ✅ Uses `Promise.all()` for concurrent animations
- ✅ Distance-based duration calculations
- ✅ Step-by-step sequential processing
- ✅ **BallSpot bridging** for seamless turn transitions
- ✅ **Single loop** processes all turns without gaps
- ✅ **Signal system** prevents animation conflicts

## Implementation Requirements for Seamless Transitions

To implement seamless turn transitions in the current system, you would need:

1. **BallSpot Data in Backend**: Ensure backend provides `ballSpot` coordinates at turn boundaries (rebounds, steals, etc.)

2. **Next Turn Preview**: Pass information about the next turn during current turn processing (or ensure all turns are available upfront)

3. **BallSpot Animation Handler**: Create a function similar to WIP_GOB's ballSpot bridging that:
   - Detects when a turn ends with a ballSpot
   - Gets the next turn's ball holder
   - Animates both ball and player to the ballSpot concurrently
   - Uses `createConcurrentTweens()` or `Promise.all()`

4. **Signal System**: Implement a signal system to:
   - Stop idle/dribble animations during transitions (`signal = "stop"`)
   - Resume after transitions complete (`signal = "start"`)
   - Flag ballSpot animations in progress (`isBallSpot = true`)

5. **Single Loop Processing**: Process all turns in a single loop (if possible) or ensure the frontend can queue/preload turns for immediate transition

6. **State Management**: Track `prevAnimationLastBallHolder` and `prevMatchStatus` to properly bridge between turns

## Benefits of Seamless Transitions

1. **Better User Experience**: No jarring pauses between turns
2. **More Realistic**: Mimics continuous basketball gameplay
3. **Visual Flow**: Creates a sense of momentum and continuity
4. **Professional Feel**: Appears more polished and refined
5. **Engagement**: Keeps users focused on the action

## Files Referenced (WIP_GOB)

### Animation System
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/useFullAnimation.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/useContinueGame.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/usePlayerAnimation.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/useScenarios.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/useTweens.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/animations/useDurations.ts`

### Idle Animation System
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/utils/usePhaserPlayers.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/utils/useUpdateStatus.ts`
- `/Users/jamesdavies/WIP_GOB/Frontend/app/components/gamePlay/Hooks/utils/useGeneral.ts`

## Idle Animation System for Waiting Players

WIP_GOB includes a sophisticated idle animation system that makes players who have reached their destination feel alive while waiting for other players to complete their longer animations.

### Overview

When 9 players finish their movement quickly but 1 player still has 25 grid spots to travel, the 9 waiting players don't just stand still. Instead, they perform subtle, organic animations that make the scene feel more natural and engaging.

### Implementation

#### 1. `animatePlayerWhileIdle` Function

Called on every game status update, this function manages idle animations for all players:

```typescript
// usePhaserPlayers.ts (lines 169-197)
const animatePlayerWhileIdle = ({ 
  phaserAwayPlayers, 
  phaserHomePlayers, 
  scene, 
  ballHolder, 
  isPlaying, 
  nextBallHolder, 
  signal 
}: AnimatePlayerIdle) => {
  const combinePlayers = Object.values(phaserAwayPlayers).concat(Object.values(phaserHomePlayers));
  
  combinePlayers.forEach(({ phaserPlayer, jerseyNo, name }) => {
    // Only animate players who are NOT ball holders
    const ballHoldersCheck = ballHolder?.name !== name && nextBallHolder?.name !== name;
    
    // Stop if game is paused or signal is "stop"
    const stopCheck = !isPlaying || signal == "stop";
    
    const playerTweens = scene.tweens?.getTweensOf(phaserPlayer);
    
    if (stopCheck) return stopIdleAnimation({ jerseyNo, name, phaserPlayer, scene });
    
    if (playerTweens.length) {
      // If player has active tweens, stop idle animation
      if (playerTweens.length > 1 || !ballHoldersCheck) {
        stopIdleAnimation({ jerseyNo, name, phaserPlayer, scene });
      }
    } else if (ballHoldersCheck && (signal ? signal == "start" : true)) {
      // Start idle animation if not already running
      if (!scene.game.state.tweenRegistry?.[name]?.length) {
        scene.game.state.tweenRegistry[name] = startIdlePlayerAnimation({ 
          jerseyNo, 
          phaserPlayer, 
          scene 
        });
      }
    }
  });
};
```

**Key Points:**
- Runs continuously on every game status update
- Only animates players who are NOT the ball holder or next ball holder
- Respects the signal system (`signal === "start"` to allow animations)
- Stops idle animations when players need to move again

#### 2. `startIdlePlayerAnimation` Function

Creates subtle, two-part animations for idle players:

```typescript
// usePhaserPlayers.ts (lines 94-147)
const startIdlePlayerAnimation = ({ scene, phaserPlayer, jerseyNo }: StartIdleTweenType) => {
  const { velocity } = scene.game.state;
  const { randomX, randomY } = getRandomCoords(); // ±10 to ±25 pixels
  
  // Part 1: Random position movement (player)
  const playerTween = scene.tweens.add({
    targets: phaserPlayer,
    props: {
      x: { value: `+=${randomX}`, duration: velocity.delays.d600, yoyo: true },
      y: { value: `+=${randomY}`, duration: velocity.delays.d600, yoyo: true },
    },
    ease: "Sine.easeInOut",
    onComplete: () => {
      // Part 2: Scale animation after position movement completes
      const playerScale = scene.tweens.add({
        targets: phaserPlayer,
        props: {
          scale: { value: 1.2, duration: velocity.delays.d300, yoyo: true },
        },
        ease: "Sine.easeInOut",
        repeat: 1,
        onComplete: () => (playerTween.isCompleted = true),
      });
    },
  });
  
  // Part 1: Random position movement (jersey number)
  const jerseyTween = scene.tweens.add({
    targets: jerseyNo,
    props: {
      x: { value: `+=${randomX}`, duration: velocity.delays.d600, yoyo: true },
      y: { value: `+=${randomY}`, duration: velocity.delays.d600, yoyo: true },
    },
    ease: "Sine.easeInOut",
    onComplete: () => {
      // Part 2: Scale animation after position movement completes
      const jerseyScale = scene.tweens.add({
        targets: jerseyNo,
        props: {
          scale: { value: 0.85, duration: velocity.delays.d300, yoyo: true },
        },
        ease: "Sine.easeInOut",
        repeat: 1,
        onComplete: () => (jerseyTween.isCompleted = true),
      });
    },
  });
  
  return [playerTween, jerseyTween];
};
```

**Animation Sequence:**
1. **Position Movement**: Player and jersey number move ±10 to ±25 pixels in a random direction
   - Duration: 600ms
   - Uses `yoyo: true` to return to original position
   - Easing: `Sine.easeInOut`

2. **Scale Animation**: After position movement completes
   - Player scales to 1.2x (slight grow)
   - Jersey number scales to 0.85x (slight shrink)
   - Duration: 300ms
   - Repeats once (total: 2 cycles)
   - Returns to original scale

#### 3. Random Coordinates Generator

Generates subtle random movements:

```typescript
// useGeneral.ts (lines 27-36)
const getRandomCoords = () => {
  // Random direction (positive or negative)
  const willNegativeX = Math.round(Math.random());
  const willNegativeY = Math.round(Math.random());
  
  // Random distance: 10-25 pixels
  let randomX = ~~(Math.random() * (10 + 15) + 10);
  randomX = willNegativeX ? -randomX : randomX;
  
  let randomY = ~~(Math.random() * (10 + 15) + 10);
  randomY = willNegativeY ? -randomY : randomY;
  
  return { randomX, randomY };
};
```

**Range**: ±10 to ±25 pixels in both X and Y directions

#### 4. `stopIdleAnimation` Function

Cleans up idle animations when players need to move:

```typescript
// usePhaserPlayers.ts (lines 149-167)
const stopIdleAnimation = ({ scene, phaserPlayer, jerseyNo, name }: StopIdleTweenType) => {
  scene.game.state.tweenRegistry[name]?.forEach((tween) => {
    try {
      // Reset to original state
      phaserPlayer.setScale(playerScaleFactor);
      jerseyNo.setScale(0.9);
      phaserPlayer.setPosition(phaserPlayer.x, phaserPlayer.y);
      jerseyNo.setPosition(jerseyNo.x, jerseyNo.y);
      
      // Destroy tween if not already destroyed
      if (tween && !tween.isDestroyed()) {
        tween.destroy();
        tween.isCompleted = true;
      }
    } catch (error) {
      gobConsole(error);
    }
  });
};
```

### Integration with Game Status Updates

The idle animation system is called on every game status update:

```typescript
// useUpdateStatus.ts (line 35)
const handleGameStatus = async (scene: ExtendedScene) => {
  // ... other status updates ...
  
  // Update idle animations for all players
  if (phaserAwayPlayers && phaserHomePlayers) {
    animatePlayerWhileIdle({ 
      ballHolder, 
      phaserAwayPlayers, 
      phaserHomePlayers, 
      scene, 
      isPlaying, 
      nextBallHolder, 
      signal 
    });
  }
  
  // ... rest of status updates ...
};
```

### Visual Effect

**What users see:**
- Players who finish early while others are still moving perform subtle animations
- Random small movements (shifting weight, slight repositioning)
- Gentle scaling (breathing, slight grow/shrink effect)
- Continuous looping until players need to move again
- Ball holder and next ball holder don't animate (they get dribble animation or are about to move)

**Why it feels organic:**
- Makes waiting players feel alive, not frozen
- Prevents the "uncanny valley" of players standing perfectly still
- Creates a sense of activity even during waiting periods
- Smoothly transitions when players need to move (animations stop immediately)

### When Idle Animations Are Active

**Start when:**
- Player has completed their movement animation
- Player is NOT the ball holder (ball holder gets dribble animation)
- Player is NOT the next ball holder (about to receive the ball)
- `isPlaying === true` and `signal === "start"`

**Stop when:**
- Player needs to move again (has active movement tweens)
- Player becomes the ball holder
- Player becomes the next ball holder
- `signal === "stop"` (critical animations in progress)
- `isPlaying === false` (game paused or ended)

### Tween Registry System

WIP_GOB uses a tween registry to track idle animations:

```typescript
// Stored in scene.game.state.tweenRegistry[name]
scene.game.state.tweenRegistry = {
  "Player Name": [playerTween, jerseyTween],
  // ... other players ...
};

// Registry cleanup when tweens complete
if (scene.game.state.tweenRegistry) {
  scene.game.state.tweenRegistry = Object.fromEntries(
    Object.entries(scene.game.state.tweenRegistry).map(([key, val]) => {
      if (!val?.length) return [key, []];
      if (!val.some((tween) => tween.isCompleted)) return [key, []];
      else return [key, val];
    })
  );
}
```

**Purpose:**
- Prevents duplicate idle animations
- Allows cleanup of completed animations
- Tracks active animations per player

## Notes

- This analysis was performed on the WIP_GOB codebase for research purposes
- No code changes were made to the current gob-simplified system
- This document serves as a reference for potential future implementation
