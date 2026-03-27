# Core Animation System

**Status:** ✅ **PRODUCTION** - Fully operational (January 2025)

The core animation system provides a unified, predictable architecture for all turn animations, following SS&S principles (Simple, Stable, Scalable).

## Architecture Overview

```
animateGameTurns.js (detection)
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Specialized Handlers (execution)
```

## Core Components

### 1. AnimationRouter
**Location:** `AnimationRouter.js`  
**Purpose:** Single entry point for all animations

**Responsibilities:**
- Handles pre/post setup via `prepareTurnForAnimation()` and `finalizeTurnAfterAnimation()`
- Manages turn queuing to prevent concurrent processing
- Integrates BallController and AnimationEngine
- Provides consistent error handling and state management

### 2. AnimationEngine
**Location:** `AnimationEngine.js`  
**Purpose:** Routes turns to appropriate handlers

**Responsibilities:**
- Determines which handler to use based on turn type via `determineHandler()`
- Maintains a registry of handlers (`animationHandlers` Map)
- Routes to specialized animation systems when available

### 3. Specialized Animation Systems

#### BallController
**Location:** `BallController.js`  
**Status:** ✅ Single source of truth for ball state

**Features:**
- Manages ball ownership, attachment/detachment, and flight state
- Lifecycle methods: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`
- Internal state: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
- **BallControllerAdapter** provides backward compatibility layer

**Benefits:**
- ✅ Single source of truth (no ownership conflicts)
- ✅ No ball teleports (Phaser handles sync automatically)
- ✅ Lifecycle methods for clean state management
- ✅ Better performance (no update callbacks)

#### Unified Pass System
**Location:** `passDetection.js`  
**Status:** ✅ Fully unified and operational

**Features:**
- Centralized pass detection and handling utility
- `detectPassAtStep()` - Detects passes from animation data
- `handlePassAnimation()` - Executes pass animation with distance-based duration
- Works for all pass types: HCO passes, fast break outlet passes, side/baseline inbound passes, opening tip passes, DREB outlet passes

**Benefits:**
- ✅ Single source of truth for all pass animations
- ✅ Consistent behavior across all pass types
- ✅ Automatic pass detection from animation data
- ✅ Future-proof: Ready for dynamic inbound passes

#### ShotAnimationSystem
**Location:** `ShotAnimationSystem.js`  
**Status:** ✅ Fully implemented

**Features:**
- Handles HCO and FCP/HCT shot attempts (MAKE/MISS)
- Player movement, ball flight, rebounds
- DREB outlet pass handling

#### FreeThrowAnimationSystem
**Location:** `FreeThrowAnimationSystem.js`  
**Status:** ✅ Fully implemented

**Features:**
- Handles free throw sequences
- Multiple attempts, rim hold, state transitions

#### ReboundAnimationSystem
**Location:** `ReboundAnimationSystem.js`  
**Status:** ✅ Fully implemented and operational

**Features:**
- Handles rebound positioning and player movement
- Defensive rebounds (positioning and HCO outlet setup)
- Offensive rebounds (positioning only)
- Player collapse animations
- Ball attachment to rebounders

#### PassAnimationSystem
**Location:** `PassAnimationSystem.js`  
**Status:** ✅ Fully implemented and operational

**Features:**
- Handles all pass animations (inbound passes, outlet passes, regular passes)
- Universal pass animation handler
- Consistent ball flight behavior
- Proper receiver positioning

## Coordinate Flipping (Court Side)

**Rule:** One attacking side — both offense and defense are drawn on the same (attacking) half of the court. No flip when the home team is on offense; flip when the away team is on offense.

- **Home team on offense:** Use backend positions as-is. Both teams set up on the home side.
- **Away team on offense:** Flip coordinates for both offense and defense (e.g. `x → 101 − x`, `y` unchanged) so the whole setup is on the away (attacking) side.

Backend sends positions in a single convention (e.g. home-side) where applicable (e.g. Final Turn alignment, HCO string spots). The frontend derives “away offense” (e.g. `offenseTeamId !== homeTeamId`) and applies one flip to both offense and defense when true. This keeps the rule consistent across turn types (HCO entry, Final Turn setup, etc.) without special cases.

## Universal Court Clamp Policy

**Status:** ✅ Production (frontend Phase 1 + backend response sanitation)

Animation-facing player coordinates use one canonical grid clamp policy:

- **x bounds:** `9..91` (between basket x spots)
- **y bounds:** `2..49`

### Exemptions

The clamp is intentionally skipped for turn types that need out-of-bounds lanes:

- `SIDE_INBOUND` (SIP)
- `BASELINE_INBOUND` (BIP)
- `TIMEOUT` (reserved future sideline movement)

### Implementation Contract

- **Frontend clamp source of truth:** `FrontEnd/static/js/phaser/animation/courtClamp.js`
  - `clampGridCoords()`
  - `isClampExempt()`
- **Backend response sanitation:** `BackEnd/utils/shared.py`
  - `sanitize_turn_animation_payload()`
  - Applied at `/api/simulate-turn` response boundary (including timeout and batch turn payloads)
- **Rule:** clamp in grid-space before/at payload consumption; avoid ad-hoc `Math.min/Math.max` clamp variants in feature code.

## State Tracking System

**Status:** ✅ **CORE COMPONENT** - Fundamental architectural pattern

### Core Principles

1. **Single Source of Truth**: One place tracks state (no scattered flags)
2. **Lifecycle Methods**: Explicit state transitions (start/end methods)
3. **Scene-Level State**: Track cross-turn context on scene object
4. **State Clearing**: Always clear state before transitions

### BallController State
- **Purpose**: Single source of truth for ball ownership and flight state
- **State Tracked**: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
- **Lifecycle Methods**: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`

### Scene-Level State
- **Purpose**: Track state that persists across multiple turns
- **Examples**:
  - `scene.currentPressureType` - Tracks FCP/HCT pressure sequences ("FCP" | "HCT" | null)
  - `scene.pressureSequenceActive` - Boolean flag for active pressure sequence
  - `scene.currentOffenseTeamId` - Current offensive team
  - `scene.gameState.ballHolder` - Ball holder ID (synchronized with BallController)

### State Clearing Pattern

**Critical:** Always clear state **before** transitioning to next operation:

```javascript
// ✅ CORRECT
await completeCurrentOperation();
this.ballController.onShotEnd(); // Clear state
await handleNextOperation();

// ❌ WRONG
await completeCurrentOperation();
await handleNextOperation(); // State not cleared!
this.ballController.onShotEnd(); // Too late!
```

## Complete Routing Flow

All turn types route through AnimationRouter:

1. **HCO shots (MAKE/MISS)** → `AnimationRouter` → `AnimationEngine` → `ShotAnimationSystem`
2. **FCP/HCT shots (MAKE/MISS)** → `AnimationRouter` → `AnimationEngine` → `ShotAnimationSystem`
3. **FCP/HCT fouls** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`
4. **FCP/HCT setup turns** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`
5. **FREE_THROW** → `AnimationRouter` → `AnimationEngine` → `handleFreeThrow()`
6. **FAST_BREAK** → `AnimationRouter` → `AnimationEngine` → `handleFastBreak()`
7. **PUTBACK_MAKE/PUTBACK_MISS/OREB_KICKOUT** → `AnimationRouter` → `AnimationEngine` → `handlePutback()`
8. **OPENING_TIP** → `AnimationRouter` → `AnimationEngine` → `handleOpeningTip()`
9. **DEFENSIVE_STOP** → `AnimationRouter` → `AnimationEngine` → `handleDefensiveStop()`
10. **STEAL** (standalone turn) → `AnimationRouter` → `AnimationEngine` → `handleSteal()`
11. **TURNOVER** → `AnimationRouter` → `AnimationEngine` → `handleTurnover()`
12. **SIDE_INBOUND** → `AnimationRouter` → `AnimationEngine` → `handleSideInbound()`
13. **BASELINE_INBOUND** → `AnimationRouter` → `AnimationEngine` → `handleBaselineInbound()`
14. **HCO setup turns** → `AnimationRouter` → `AnimationEngine` → `handleDefault()` → `playTurnAnimation()`

## Benefits

**Simple:**
- ✅ Single Pattern: All animations follow the same flow
- ✅ Clear Separation: Detection → Routing → Execution
- ✅ One Mental Model: "Find the turn type → route through AnimationRouter → handler executes"

**Stable:**
- ✅ Centralized Routing: All routing logic in one place
- ✅ Consistent Error Handling: AnimationRouter provides uniform error handling
- ✅ Isolated Handlers: Bugs in one handler don't affect others

**Scalable:**
- ✅ Easy Extension: Adding new turn types requires only adding a handler
- ✅ No Core Changes: New turn types don't require modifying `animateGameTurns.js`
- ✅ Clear Extension Points: Handlers are isolated and can be refactored independently

## Key Files

**Core Architecture:**
- `AnimationRouter.js` - Main entry point (single source of truth for routing)
- `AnimationEngine.js` - Turn routing logic and handler registry
- `turnPreparation.js` - Pre/post setup utilities

**Specialized Systems:**
- `BallController.js` - Ball state management
- `ShotAnimationSystem.js` - Shot handler (HCO and FCP/HCT)
- `FreeThrowAnimationSystem.js` - Free throw handler
- `ReboundAnimationSystem.js` - Rebound handler
- `PassAnimationSystem.js` - Pass handler
- `passDetection.js` - Unified pass detection and handling

**Detection:**
- `animateGameTurns.js` - Turn detection and routing (simplified)

## See Also

- `Animation_Detection_Reference.md` - Detailed detection point catalog
- `Animation_Handler_Reference.md` - Complete handler documentation
- `docs/Animation_System/animation_system.md` - Complete animation system documentation

