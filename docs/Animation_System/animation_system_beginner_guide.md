# Animation System - Beginner's Guide

> A comprehensive guide for developers new to the animation system, combining simple concepts with practical technical details.

---

## Table of Contents

1. [The Big Picture](#the-big-picture)
2. [Simple Concepts (Like You're 11 Years Old)](#simple-concepts)
3. [How Data Flows](#how-data-flows)
4. [Backend: Creating Animations](#backend-creating-animations)
5. [Frontend: Playing Animations](#frontend-playing-animations)
6. [Key Components](#key-components)
7. [Complete Example](#complete-example)
8. [Common Patterns](#common-patterns)
9. [Debugging Tips](#debugging-tips)

---

## The Big Picture

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

**Key Takeaway:** Backend creates the script. Frontend performs the script. That's it!

---

## Simple Concepts

### 1. AnimationRouter 🚦
**What it is:** The traffic director

**What it does:**
- When something happens in the game (like a shot or a pass), AnimationRouter is the first person to see it
- It's like a teacher at recess who decides: "Okay, you need to go to the basketball court, you need to go to the soccer field"
- It makes sure only ONE thing happens at a time (no crashes!)
- It also does "setup" work - like making sure the scoreboard is ready before the play starts

**Real example:**
```
Player shoots the ball → AnimationRouter says "Okay, I'll handle this!"
→ AnimationRouter tells the right person what to do
→ AnimationRouter makes sure everything finishes properly
```

### 2. AnimationEngine 🧠
**What it is:** The decision maker

**What it does:**
- AnimationRouter asks AnimationEngine: "What should we do with this play?"
- AnimationEngine looks at what happened and decides: "This is a shot, so send it to the Shot Person!"
- It's like a smart assistant who knows: "If it's a shot, use the shot system. If it's a pass, use the pass system."

**Real example:**
```
AnimationEngine sees: "Player made a shot"
→ AnimationEngine thinks: "This is a shot, so I'll send it to ShotAnimationSystem"
→ ShotAnimationSystem does the work
```

### 3. BallController 🏀
**What it is:** The ball tracker

**What it does:**
- Keeps track of ONE important thing: "Who has the ball RIGHT NOW?"
- It's like having a friend who always knows: "Player 5 has the ball!" or "The ball is flying through the air!"
- It prevents bugs like the ball being in two places at once (that would be weird!)

**Real example:**
```
Player 3 has the ball → BallController remembers: "Player 3 has it"
→ Player 3 passes to Player 7 → BallController updates: "Now Player 7 has it"
→ Player 7 shoots → BallController says: "Ball is flying, nobody has it right now"
```

### 4. Specialized Systems 👷
**What they are:** Different workers who do different jobs

**The Workers:**
- **ShotAnimationSystem** - Handles shots (makes the ball fly to the hoop)
- **ReboundAnimationSystem** - Handles rebounds (when someone catches a missed shot)
- **PassAnimationSystem** - Handles passes (when someone throws the ball to a teammate)
- **FreeThrowAnimationSystem** - Handles free throws (when someone shoots from the free throw line)

**What they do:**
- Each one is really good at ONE specific job
- Like having a plumber for pipes, an electrician for wires, and a carpenter for wood
- They each know exactly how to do their job perfectly

**Real example:**
```
ShotAnimationSystem:
→ Moves players to their positions
→ Makes the ball fly from the shooter to the hoop
→ Shows if it goes in or misses
→ Handles rebounds if it misses
```

### 5. playTurnAnimation() 🎬
**What it is:** The old way of doing things

**What it does:**
- This is like the "old school" way of animating
- Some plays still use this because they're complicated (like FCP/HCT pressure plays)
- It can do EVERYTHING: move players, animate passes, shoot the ball, all in one function
- It's like a Swiss Army knife - can do many things, but not as organized as having separate tools

**Why we still use it:**
- Some plays (like FCP/HCT) need to do skeleton animations (press break sequences) AND shots
- The new systems are great at ONE thing, but these plays need EVERYTHING
- So we still use the old way for those special cases

### 6. State Tracking 🧭
**What it is:** Remembering what's happening

**What it does:**
- The game needs to remember things across multiple plays
- Like: "Are we in a Full Court Press right now?" or "Who has the ball?"
- It's like keeping a notebook that says: "Current situation: FCP is active, Player 5 has the ball"

**Real example:**
```
Turn 1: FCP starts → State says: "FCP is active!"
Turn 2: Player breaks the press → State still says: "FCP is active!" (we remember!)
Turn 3: Player shoots → State says: "FCP is active, and now there's a shot"
Turn 4: Shot goes in → State clears: "FCP is done, back to normal"
```

---

## How Data Flows

### The Journey of One Play

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

### The Core Concept: Turn Data

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

## Backend: Creating Animations

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

### Key Backend Files

| File | What It Does |
|------|-------------|
| `phase_resolution.py` | Main game logic - decides what happens each turn |
| `animator.py` | Creates the animation data (choreographer) |
| `shot_manager.py` | Handles shot outcomes |
| `rebound_manager.py` | Handles rebound logic |
| `turn_manager.py` | Orchestrates turn execution and adds standard fields |

---

## Frontend: Playing Animations

### The Animation Pipeline

```
Game Data Arrives
    ↓
animateGameTurns.js ← Main loop, processes all turns in order
    ↓
AnimationRouter ← Routes to the right system
    ↓
AnimationEngine ← Decides which specialized system to use
    ↓
Routes to specific handler:
    - ShotAnimationSystem.js   ← Regular shots
    - ReboundAnimationSystem.js ← Rebounds
    - PassAnimationSystem.js   ← Passes
    - FreeThrowAnimationSystem.js ← Free throws
    - playTurnAnimation()      ← FCP/HCT (legacy)
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

### The State Machine: Keeping Track of What's Happening

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

### Key Frontend Files

| File | What It Does |
|------|-------------|
| `animateGameTurns.js` | **Main controller** - loops through all turns |
| `AnimationRouter.js` | Routes turns to the right animation system |
| `AnimationEngine.js` | Decides which specialized system to use |
| `ShotAnimationSystem.js` | Animates shots |
| `ReboundAnimationSystem.js` | Animates rebounds |
| `PassAnimationSystem.js` | Animates passes |
| `FreeThrowAnimationSystem.js` | Animates free throws |
| `ballManager.js` | Controls the ball movement |
| `gameStateMachine.js` | Tracks game state, prevents invalid transitions |

---

## How It All Works Together

### Example: A Normal Shot

1. **Something happens:** Player shoots the ball
2. **AnimationRouter** sees it: "Okay, I'll handle this!"
3. **AnimationRouter** asks **AnimationEngine**: "What should we do?"
4. **AnimationEngine** decides: "This is a shot, send it to ShotAnimationSystem!"
5. **ShotAnimationSystem** does the work:
   - Moves players
   - Uses **BallController** to track the ball
   - Animates the ball flying to the hoop
   - Shows if it goes in or misses
6. **AnimationRouter** finishes up: "Okay, that's done! Update the scoreboard!"

### Example: A Complicated FCP/HCT Play

1. **Something happens:** FCP pressure starts, then player shoots
2. **AnimationRouter** would normally handle it, BUT...
3. **FCP/HCT plays** are special - they use **playTurnAnimation()** directly
4. **playTurnAnimation()** does EVERYTHING:
   - Animates the press break (players moving to break the press)
   - Then animates the shot
   - All in one function!
5. **State Tracking** remembers: "We're in FCP mode" so the next play knows

---

## Complete Example

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
    // AnimationRouter handles routing
    await AnimationRouter.handleTurn(turn, context);
    
    // Show the text
    appendToTextScroll(turn.text);  // "John makes the shot!"
}
```

---

## Common Patterns

### 1. Timestamps (Measured in Milliseconds)

```javascript
// Animation happens in steps
{
    timestamp: 0,      // Start (0ms)
    timestamp: 300,    // 0.3 seconds later
    timestamp: 600,    // 0.6 seconds later
    timestamp: 1800   // 1.8 seconds later (end)
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

### 4. The Timeline Concept

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
- **Check:** Animation systems - are you transitioning states correctly?

**Problem:** Ball not moving
- **Check:** `ballManager.js` - is the ball attached to the right player?
- **Check:** Animation data - does it have `hasBallAtStep` array?

**Problem:** Animation routing not working
- **Check:** `AnimationRouter.js` - is it receiving the turn data?
- **Check:** `AnimationEngine.js` - is it correctly identifying the turn type?

### Using Debug Flags

Enable detailed animation logging in the browser console:

```javascript
// Enable detailed animation tracing
window.DEBUG_ANIM = true;
window.FEATURE_POSSESSION_RUNNER = true;

// Disable when done
window.DEBUG_ANIM = false;
window.FEATURE_POSSESSION_RUNNER = false;
```

See `docs/Animation_System/animation-debug.md` for more debugging information.

---

## The Big Idea

**Before (Old Way):**
- Everything was mixed together
- Hard to fix bugs
- Like having all your toys in one big messy box

**Now (New Way):**
- Everything has a job
- Easy to fix bugs (just fix the one thing that's broken)
- Like having organized drawers: "Shots go here, Passes go here, Rebounds go here"

**But:**
- Some things (like FCP/HCT) are still in the old way because they're complicated
- We're slowly moving them to the new way, one at a time

---

## Next Steps

Now that you understand the basics:

1. **Read a single turn's data** - open browser console, find `simData.turns[0]`, inspect it
2. **Follow one turn through the code** - trace from backend → frontend
3. **Modify something small** - change a coordinate, see what happens
4. **Read the detailed docs** - `docs/Animation_System/animation_system.md` (when you're ready for advanced topics)

---

## Questions to Test Your Understanding

1. Where does animation data get created? (Answer: Backend, in `animator.py`)
2. What format is the data in? (Answer: A dictionary/object with an "animations" array)
3. What file receives the data on the frontend? (Answer: `gameScene.js` via API call)
4. What file actually moves the players? (Answer: `animateGameTurns.js` → `AnimationRouter` → specialized systems)
5. What's a tween? (Answer: Smooth movement from A to B)
6. What does AnimationRouter do? (Answer: Routes turns to the right animation system)
7. What does BallController do? (Answer: Tracks who has the ball)

If you can answer these, you've got the basics down! 🏀

---

## Summary

- **AnimationRouter** = Traffic director (decides who handles what)
- **AnimationEngine** = Decision maker (figures out what type of play it is)
- **BallController** = Ball tracker (remembers who has the ball)
- **Specialized Systems** = Workers (each does one job really well)
- **playTurnAnimation()** = Old way (still used for complicated plays)
- **State Tracking** = Memory (remembers what's happening)

All together, they make the game look smooth and work correctly! 🎮🏀

