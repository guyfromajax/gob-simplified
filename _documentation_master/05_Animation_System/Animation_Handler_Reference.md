# Animation Handler Reference

**Status:** ✅ **COMPLETE** (January 2025)

This document catalogs every handler that executes turn animations after routing through `AnimationRouter` and `AnimationEngine`.

## Handler Architecture

**Flow:**
```
animateGameTurns.js (detection)  ← STEP 1
    ↓
AnimationRouter (single entry point)  ← STEP 2
    ↓
AnimationEngine (routing logic)  ← STEP 2
    ↓
Specialized Handlers (execution)  ← STEP 3
```

## Handler Registration

All handlers are registered in `AnimationEngine.initializeDefaultHandlers()` and stored in `this.animationHandlers` Map.

## Handler Pattern

All handlers follow this pattern:
1. Receive `turnData` and `context` parameters
2. Execute turn-specific animation logic
3. Handle announcements, score updates, and state transitions (or delegate to AnimationRouter)
4. Return Promise (async/await)

## Handler Summary Table

| Handler | Registered For | Primary Function | System Used | Fallback |
|---------|---------------|------------------|-------------|----------|
| `handleFreeThrow()` | `FREE_THROW` | Free throw sequences | `FreeThrowAnimationSystem` | `runFreeThrowSequence()` |
| `handleSideInbound()` | `SIDE_INBOUND` | Side inbound passes | `PassAnimationSystem` | `runSideInboundSetup()` |
| `handleBaselineInbound()` | `BASELINE_INBOUND` | Baseline inbound passes | Direct implementation | None |
| `handleTurnover()` | `TURNOVER` | Turnover animations | `turnoverAdapter.js` | None |
| `handleFastBreak()` | `FAST_BREAK` | Fast break sequences | `runFastBreakSequence()` | None |
| `handlePutback()` | `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT` | Putback shots and OREB kickouts | `handleOrebTurn()` | None |
| `handleOpeningTip()` | `OPENING_TIP` | Opening tip sequences | `runOpeningTipSequence()` | None |
| `handleDefensiveStop()` | `DEFENSIVE_STOP` | Defensive stop transitions | `runFastBreakSequence()` or `runDefensiveStopTransition()` | None |
| `handleSteal()` | `STEAL` | Steal pass animations | `runPass()` | None |
| `handleShotAttempt()` | `SHOT_ATTEMPT` (detected) | Shot attempts (MAKE/MISS) | `ShotAnimationSystem` | `playTurnAnimation()` |
| `handleRebound()` | `REBOUND` (detected) | Rebound animations | `ReboundAnimationSystem` | `playTurnAnimation()` |
| `handlePass()` | `PASS` (detected) | Pass animations | `PassAnimationSystem` | `playTurnAnimation()` |
| `handleDefault()` | `HCO`, `DEFAULT`, `FOUL`, `DEAD_BALL` | Default/fallback handler | `playTurnAnimation()` | None |
| `handleTimeout()` | `TIMEOUT` | Timeout handling | Direct implementation | None |

## Handler Responsibilities

**What Handlers Do:**
- ✅ Execute turn-specific animation logic
- ✅ Handle active player display updates (where applicable)
- ✅ Execute animation sequences (player movement, ball flight, etc.)
- ✅ Handle state transitions (where applicable)
- ✅ Append text scroll (where applicable)
- ✅ Set scene flags (where applicable)

**What Handlers DON'T Do (Handled by AnimationRouter):**
- ❌ Pre-turn setup (`prepareTurnForAnimation()`)
- ❌ Post-turn finalization (`finalizeTurnAfterAnimation()`)
- ❌ Announcements (`announceFromTurnData()`)
- ❌ Score updates (`onUpdate()`)
- ❌ Debug score updates (`updateDebugScore()`)
- ❌ Turn queuing and concurrency management

**Exception:** Some handlers (like `handleFreeThrow()`, `handleDefensiveStop()`, `handleTimeout()`) append text scroll directly because the logic was moved from `animateGameTurns.js` during migration.

## Handler Routing Logic

**How `AnimationEngine.determineHandler()` Routes:**

1. **Fast Break Detection (Highest Priority):**
   - If `turnData.fast_break === true` OR `turnData.result_type === "FAST_BREAK"` → `handleFastBreak()`

2. **Specific Result Type:**
   - If `turnData.result_type` exists in `animationHandlers` Map → Use that handler

3. **Shot Attempt Detection:**
   - If `isShotAttempt(turnData)` AND not in non-shot result types → `handleShotAttempt()`

4. **Rebound Detection:**
   - If `isRebound(turnData)` → `handleRebound()`

5. **Pass Detection:**
   - If `isPass(turnData)` → `handlePass()`

6. **Default Handler:**
   - Otherwise → `handleDefault()`

**Non-Shot Result Types (Excluded from Shot Attempt Detection):**
- `FOUL`, `FREE_THROW`, `TURNOVER`, `DEAD_BALL`, `DEAD_BALL_TURNOVER`
- `SIDE_INBOUND`, `BASELINE_INBOUND`, `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`
- `DEFENSIVE_STOP`, `OPENING_TIP`, `HCO`, `STEAL`

## Registered Handlers

### 1. `handleFreeThrow()`
**Registered for:** `FREE_THROW`  
**Location:** `AnimationEngine.js` line 237

**What it does:**
- Updates active player display (shooter)
- Routes to `FreeThrowAnimationSystem` (if available) or falls back to `runFreeThrowSequence()`
- Appends text scroll with free throw result
- **Note:** `onUpdate` is called inside `runFreeThrowSequence` (no double counting)

**Key Features:**
- Active player display update
- Free throw sequence execution
- Text scroll append
- Handles multiple free throw attempts (via `ftContext`)

### 2. `handleSideInbound()`
**Registered for:** `SIDE_INBOUND`  
**Location:** `AnimationEngine.js` line 271

**What it does:**
- Checks FastBreak state (skips animation if in FastBreak)
- Routes to `PassAnimationSystem` (if available) or falls back to `runSideInboundSetup()`
- Handles side inbound pass animations

**Key Features:**
- FastBreak state check (matches original logic)
- Pass animation system integration
- Fallback to legacy `runSideInboundSetup()`

### 3. `handleBaselineInbound()`
**Registered for:** `BASELINE_INBOUND`  
**Location:** `AnimationEngine.js` line 297

**What it does:**
- **FCP/HCT State Tracking:** Sets `scene.currentPressureType` and `scene.pressureSequenceActive` when pressure setup detected
- Animates all players to their positions using distance-based duration
- Transitions state machine to `HalfCourt`
- Sets `scene._previousTurnWasInbound = true` for HCO pre-step setup
- Executes inbound pass animation via `PassAnimationSystem`
- Waits for pass animation to complete before proceeding

**Key Features:**
- FCP/HCT state initialization (single source of truth)
- Player position animations (distance-based duration)
- State machine transition
- Scene flag for HCO setup
- Pass completion wait logic

### 4. `handleTurnover()`
**Registered for:** `TURNOVER`  
**Location:** `AnimationEngine.js` line 411

**What it does:**
- Routes to `turnoverAdapter.js` for turnover animation handling

**Key Features:**
- Delegates to specialized turnover adapter
- Handles turnover animations

### 5. `handleFastBreak()`
**Registered for:** `FAST_BREAK`  
**Location:** `AnimationEngine.js` line 423

**What it does:**
- Updates active player display (ball handler and defender)
- Routes to `runFastBreakSequence()` for fast break animation
- Sets `scene._previousTurnWasShot = true` if this was a shot turn

**Key Features:**
- Active player display update
- Fast break sequence execution
- Shot turn flag setting

### 6. `handlePutback()`
**Registered for:** `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`  
**Location:** `AnimationEngine.js` line 452

**What it does:**
- Routes to `handleOrebTurn()` function for putback/OREB handling
- Handles PUTBACK_MAKE, PUTBACK_MISS, and OREB_KICKOUT result types

**Key Features:**
- Unified handler for all OREB-related outcomes
- Delegates to specialized OREB handler

### 7. `handleTimeout()`
**Registered for:** `TIMEOUT`  
**Location:** `AnimationEngine.js` line 471

**What it does:**
- Pauses all tweens immediately when timeout is called
- Sets `scene.timeoutCalled = true` to stop main animation loop
- Appends timeout text to text scroll
- Navigates to lineup screen (for computer timeouts)

**Key Features:**
- Immediate tween pausing
- Animation loop stopping
- Text scroll append
- Navigation handling

### 8. `handleOpeningTip()`
**Registered for:** `OPENING_TIP`  
**Location:** `AnimationEngine.js` line 532

**What it does:**
- Validates opening tip timing (Q1 start or OT start)
- Routes to `runOpeningTipSequence()` for opening tip animation
- Transitions state machine to `HalfCourt` after completion

**Key Features:**
- Timing validation
- Opening tip sequence execution
- State machine transition

### 9. `handleDefensiveStop()`
**Registered for:** `DEFENSIVE_STOP`  
**Location:** `AnimationEngine.js` line 577

**What it does:**
- Checks if this is a Fast Break defensive stop (`turnData.fast_break === true`)
- Routes to `runFastBreakSequence()` for Fast Break stops or `runDefensiveStopTransition()` for standard stops
- Appends text scroll with defensive stop message

**Key Features:**
- Fast Break detection
- Conditional routing based on fast_break flag
- Text scroll append

### 10. `handleSteal()`
**Registered for:** `STEAL`  
**Location:** `AnimationEngine.js` line 620

**What it does:**
- **Hybrid Approach:** Plays skeleton animation (if exists) then animates steal result
- If skeleton exists: Plays skeleton animation (includes steal action), attaches ball to stealer after completion
- If no skeleton: Animates steal pass (ball changes hands), attaches ball to stealer after pass
- Possession flip handled by universal transition

**Key Features:**
- Skeleton animation support (FCP/HCT press break sequences)
- Standalone steal animation (no skeleton)
- Ball attachment handling
- Possession flip via universal transition

### 11. `handleShotAttempt()`
**Registered for:** `SHOT_ATTEMPT` (detected)  
**Location:** `AnimationEngine.js` line 758

**What it does:**
- Routes to `ShotAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles HCO and FCP/HCT shot attempts (MAKE/MISS)

**Key Features:**
- Shot animation system integration
- Fallback to legacy `playTurnAnimation()`
- Handles all shot attempt types

### 12. `handleRebound()`
**Registered for:** `REBOUND` (detected)  
**Location:** `AnimationEngine.js` line 792

**What it does:**
- Routes to `ReboundAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles rebound animations

**Key Features:**
- Rebound animation system integration
- Fallback to legacy `playTurnAnimation()`

### 13. `handlePass()`
**Registered for:** `PASS` (detected)  
**Location:** `AnimationEngine.js` line 822

**What it does:**
- Routes to `PassAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles pass animations

**Key Features:**
- Pass animation system integration
- Fallback to legacy `playTurnAnimation()`

### 14. `handleDefault()`
**Registered for:** `HCO`, `DEFAULT`, `FOUL`, `DEAD_BALL`  
**Location:** `AnimationEngine.js` line 846

**What it does:**
- Routes to `playTurnAnimation()` for default/fallback handling
- Handles HCO setup turns, FCP/HCT fouls, and other default cases

**Key Features:**
- Default/fallback handler
- Skeleton animation support
- Handles multiple result types

## Handler Registration Order

Handlers are registered in this order (in `initializeDefaultHandlers()`):
1. `FREE_THROW`
2. `SIDE_INBOUND`
3. `BASELINE_INBOUND`
4. `TURNOVER`
5. `FAST_BREAK`
6. `SHOT_ATTEMPT`
7. `REBOUND`
8. `PASS`
9. `HCO`
10. `DEFAULT`
11. `PUTBACK_MAKE`
12. `PUTBACK_MISS`
13. `OREB_KICKOUT`
14. `OPENING_TIP`
15. `DEFENSIVE_STOP`
16. `STEAL`
17. `TIMEOUT`

**Note:** Registration order doesn't matter for routing (handlers are stored in a Map), but it's listed here for reference.

## Specialized Animation Systems

Some handlers route to specialized animation systems (if available):

1. **`ShotAnimationSystem`** - Used by `handleShotAttempt()`
   - Handles HCO and FCP/HCT shot attempts
   - Player movement, ball flight, rebounds
   - **Status:** ✅ Fully implemented

2. **`FreeThrowAnimationSystem`** - Used by `handleFreeThrow()`
   - Handles free throw sequences
   - Multiple attempts, rim hold, state transitions
   - **Status:** ✅ Fully implemented

3. **`ReboundAnimationSystem`** - Used by `handleRebound()`
   - Handles rebound animations
   - **Status:** ✅ Fully implemented and operational

4. **`PassAnimationSystem`** - Used by `handleSideInbound()`, `handleBaselineInbound()`, and `handlePass()`
   - Handles pass animations (inbound passes, outlet passes, regular passes)
   - **Status:** ✅ Fully implemented and operational

**Fallback Pattern:**
All specialized systems have fallbacks to legacy functions (`playTurnAnimation()`, `runFreeThrowSequence()`, etc.) if the system is not available.

