# Basketball Game Animation System - A Beginner's Guide

## What This Document Is For

You're a backend Python developer trying to understand how the frontend animation system works. Don't worry - it's actually simpler than it looks! This guide will break it down step by step.

---

## The Big Picture (10,000 Foot View)

Think of the animation system like a **movie production**:

1. **Backend (Python)** = The **Scriptwriter**
   - Writes out everything that happens in the game
   - "Player A passes to Player B at timestamp 0"
   - "Player B shoots at timestamp 800ms"
   - Sends this "script" to the frontend

2. **Frontend (JavaScript)** = The **Director & Animators**
   - Reads the script from the backend
   - Makes the players actually move on screen
   - Shows the ball flying through the air
   - Displays text like "John makes the shot!"

---

## How Data Flows (The Journey of One Play)

```
Backend (Python)                    Frontend (JavaScript)
─────────────────                   ─────────────────────

1. Game simulates a shot
   ↓
2. Creates turn data:
   {
     "result_type": "MAKE",
     "shooter": "John Smith",
     "animations": [...]
   }
   ↓
3. Sends to frontend via API
   ─────────────────────────────────→
                                    4. Frontend receives data
                                       ↓
                                    5. Reads animations array
                                       ↓
                                    6. Moves players on screen
                                       ↓
                                    7. Shows ball flying
                                       ↓
                                    8. Displays "John makes it!"
```

---

## The Core Concept: Turn Data

Every play in the game is a **turn**. Each turn is a Python dictionary that looks like this:

```python
{
    "result_type": "MAKE",              # What happened?
    "shooter": "John Smith",            # Who did it?
    "text": "John makes the shot!",     # What do we tell the user?
    "animations": [                     # HOW do we animate it?
        {
            "playerId": "uuid-123",
            "movement": [
                {"timestamp": 0, "coords": {"x": 10, "y": 20}, "action": "handle_ball"},
                {"timestamp": 800, "coords": {"x": 15, "y": 25}, "action": "shoot"}
            ]
        }
    ]
}
```

The **animations** array is the key - it tells the frontend exactly where each player should be at each moment in time.

---

## Backend: How Animations Are Created

### The Animator Class (`BackEnd/models/animator.py`)

The `Animator` is like a **choreographer** - it plans out where every player should move.

**Example: A Simple Shot**

```python
# Python backend code
animator = Animator(game)

# Generate animation for a shot
animations = animator.capture_shot_animation(
    shooter=john_smith,
    defender=mike_jones,
    screener=bob_wilson
)

# Returns something like:
[
    {
        "playerId": "john-smith-id",
        "movement": [
            {"timestamp": 0, "coords": {"x": 64, "y": 25}, "action": "handle_ball"},
            {"timestamp": 600, "coords": {"x": 64, "y": 25}, "action": "shoot"}
        ]
    },
    {
        "playerId": "mike-jones-id",
        "movement": [
            {"timestamp": 0, "coords": {"x": 68, "y": 27}, "action": "guard_ball"}
        ]
    }
]
```

**What's happening here?**
- John starts at position (64, 25) at time 0ms
- John shoots at the same position at time 600ms
- Mike is guarding him at position (68, 27)

The coordinates are **grid positions** (not pixels) - the frontend converts them to actual screen positions.

---

## Frontend: How Animations Are Played

### The Animation Pipeline

```
Game Data Arrives
    ↓
animateGameTurns.js ← Main loop, processes all turns in order
    ↓
Detects turn type (shot, rebound, fast break, etc.)
    ↓
Routes to specific handler:
    - turnAnimation.js   ← Regular shots, rebounds
    - fastBreak.js       ← Fast breaks
    - freeThrow.js       ← Free throws
    ↓
Each handler:
    1. Reads the "movement" array for each player
    2. Creates Phaser tweens (smooth movements)
    3. Moves sprites across the screen
    4. Shows the ball moving
    5. Updates the UI
```

### What's a Tween?

A **tween** is just a fancy word for "smoothly move from point A to point B over time."

```javascript
// Move player from (64, 25) to (70, 30) over 800ms
scene.tweens.add({
    targets: playerSprite,
    x: 70,
    y: 30,
    duration: 800,
    ease: 'Linear'
});
```

That's it! Phaser (the game framework) handles the smooth movement automatically.

---

## The State Machine: Keeping Track of What's Happening

The **State Machine** (`gameStateMachine.js`) is like a **traffic controller**. It makes sure the game flows correctly:

```
States (different phases of the game):
- Inbound       → Starting a possession
- HalfCourt     → Running offense
- ShotAttempt   → Someone is shooting
- Rebound       → Fighting for the rebound
- FastBreak     → Running down the court
- FreeThrow     → Shooting free throws
- EndQuarter    → Quarter is over
```

**Rules:**
- You can only go from certain states to other states
- Example: You can go from `ShotAttempt` → `Rebound`
- But you CAN'T go from `FreeThrow` → `FastBreak` (that doesn't make sense!)

**Why does this matter?**
If the state machine sees an invalid transition, it throws an error. This helps catch bugs where the animation flow is broken.

---

## Key Files & What They Do

### Backend (Python)

| File | What It Does |
|------|-------------|
| `phase_resolution.py` | Main game logic - decides what happens each turn |
| `animator.py` | Creates the animation data (choreographer) |
| `shot_manager.py` | Handles shot outcomes |
| `rebound_manager.py` | Handles rebound logic |

### Frontend (JavaScript)

| File | What It Does |
|------|-------------|
| `animateGameTurns.js` | **Main controller** - loops through all turns |
| `turnAnimation.js` | Animates regular plays (shots, rebounds, passes) |
| `fastBreak.js` | Animates fast breaks |
| `freeThrow.js` | Animates free throws |
| `ballManager.js` | Controls the ball movement |
| `gameStateMachine.js` | Tracks game state, prevents invalid transitions |

---

## A Complete Example: One Shot From Start to Finish

### Step 1: Backend Creates the Turn

```python
# In shot_manager.py
def resolve_shot(self, shooter, defender):
    made = self.calculate_if_shot_made(shooter, defender)
    
    # Create the turn data
    result = {
        "result_type": "MAKE" if made else "MISS",
        "shooter": shooter,
        "defender": defender,
        "text": f"{shooter.name} makes the shot!" if made else f"{shooter.name} misses"
    }
    
    # Add animations
    animator = Animator(self.game)
    result["animations"] = animator.capture_shot_animation(shooter, defender)
    
    return result
```

### Step 2: Frontend Receives the Data

```javascript
// In gameScene.js - the API call
const response = await fetch('/api/simulate-quarter', {
    method: 'POST',
    body: JSON.stringify({ home_team: "Lakers", away_team: "Celtics" })
});
const simData = await response.json();

// simData contains:
// {
//   turns: [ {...}, {...}, {...} ],  ← All the plays
//   score: { "Lakers": 45, "Celtics": 42 }
// }
```

### Step 3: Frontend Animates Each Turn

```javascript
// In animateGameTurns.js
for (let turn of simData.turns) {
    // Read the animation data
    const animations = turn.animations;
    
    // For each player
    for (let anim of animations) {
        const sprite = playerSprites[anim.playerId];
        const movement = anim.movement;
        
        // Move the sprite through each position
        for (let step of movement) {
            await movePlayerTo(sprite, step.coords, step.timestamp);
        }
    }
    
    // Show the text
    appendToTextScroll(turn.text);  // "John makes the shot!"
}
```

---

## Common Patterns You'll See

### 1. Timestamps (Measured in Milliseconds)

```javascript
// Animation happens in steps
{
    timestamp: 0,      // Start (0ms)
    timestamp: 300,    // 0.3 seconds later
    timestamp: 600,    // 0.6 seconds later
    timestamp: 1800    // 1.8 seconds later (end)
}
```

### 2. Coordinates (Grid System)

```javascript
// Court is a 101 x 50 grid
{
    x: 64,  // Middle of the court (left-right)
    y: 25   // Center (top-bottom)
}

// Frontend converts grid → pixels:
pixelX = gridX * gridSize
pixelY = gridY * gridSize
```

### 3. Actions (What Players Are Doing)

```javascript
"action": "handle_ball"   // Player has the ball
"action": "shoot"         // Player is shooting
"action": "guard_ball"    // Defender guarding ball handler
"action": "guard_offball" // Defender guarding off-ball player
"action": "cut"           // Player cutting to basket
"action": "screen"        // Player setting a screen
```

---

## The Timeline Concept

Think of each turn like a **movie timeline**:

```
0ms         300ms       600ms       900ms      1800ms
|-----------|-----------|-----------|----------|
Player A:   Catch       Dribble     Shoot      Follow
Player B:   Cut         Get open    ---        ---
Player C:   Guard A     Guard A     Contest    ---
Ball:       In A's hand In A's hand Flying     In rim
```

The frontend reads this timeline and makes everything happen smoothly in real-time.

---

## Debugging Tips

### Backend Issues

**Problem:** Animation data looks wrong in the logs
- **Check:** `animator.py` - is it generating the right coordinates?
- **Check:** `phase_resolution.py` - is it calling the animator correctly?

### Frontend Issues

**Problem:** Players not moving
- **Check:** Browser console - any errors?
- **Check:** Is `simData.turns` empty?
- **Check:** Are `playerSprites` loaded?

**Problem:** "Invalid state transition" error
- **Check:** `gameStateMachine.js` - is the transition allowed?
- **Check:** `fastBreak.js` or `turnAnimation.js` - are you transitioning states correctly?

**Problem:** Ball not moving
- **Check:** `ballManager.js` - is the ball attached to the right player?
- **Check:** Animation data - does it have `hasBallAtStep` array?

---

## Next Steps

Now that you understand the basics:

1. **Read a single turn's data** - open browser console, find `simData.turns[0]`, inspect it
2. **Follow one turn through the code** - trace from backend → frontend
3. **Modify something small** - change a coordinate, see what happens
4. **Read the more detailed docs** - `animation_system_guide.md` (when you're ready for advanced topics)

---

## Questions to Test Your Understanding

1. Where does animation data get created? (Answer: Backend, in `animator.py`)
2. What format is the data in? (Answer: A dictionary/object with an "animations" array)
3. What file receives the data on the frontend? (Answer: `gameScene.js` via API call)
4. What file actually moves the players? (Answer: `animateGameTurns.js` → `turnAnimation.js`)
5. What's a tween? (Answer: Smooth movement from A to B)

If you can answer these, you've got the basics down! 🏀

---

## Key Takeaway

**Backend creates the script. Frontend performs the script. That's it!**

Everything else is just details about HOW to create good scripts and HOW to perform them smoothly.

