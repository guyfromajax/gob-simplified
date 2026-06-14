# Core Animation System

**Status:** ✅ **PRODUCTION** — fully operational. Re-verified June 2026. (Major architectural changes: Movement Rate Refactor May 2026; UESS schema playback dispatch.)

The core animation system provides a unified, predictable architecture for all turn animations, following SS&S principles (Simple, Stable, Scalable).

## Architecture Overview

```
animateGameTurns.js (detection)
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Schema playback (animation_steps[])  ←  UESS-migrated turns
    OR
Specialized Handlers (execution)     ←  legacy turns
```

**Two execution paths.** `AnimationEngine.processTurn` checks for the UESS schema **before** legacy handler routing: turns carrying `animation_steps[]` (everything except Opening Tip, Timeout, and un-migrated FB variants) render via `animationPlayback.playTurn()` and never touch the specialized handlers. The handler layer below is the legacy path, shrinking as migration proceeds (UESS backlog items 14–15). See `Animation_Routing_Reference.md` § Schema playback dispatch and `../00_General_Systems/UESS_System.md` for the schema contract.

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

## Tween Duration Authority (Movement Rate Refactor)

**Status:** ✅ Production (Phase 3a/3b/4, May 2026). See `_documentation_master/projects/Movement_Rate_Refactor.md` for design history.

Per-tween durations are now **backend-authoritative** for the synced turn types. Backend computes per-player game-seconds; frontend converts to wall-time via `clockSecondMs` (the gameClock tick rate). Visual and game-clock advance in lockstep by construction.

### Authoritative source by turn type

| Turn type | Authority | Field on payload |
|---|---|---|
| **Any UESS schema turn** | Per-step `T_game_seconds` embedded in the steps (playback engine converts via `clockSecondMs`) | `turn.animation_steps[]` |
| HCT (steps 1, 2, 3) | Per-waypoint `game_seconds` field | `turn.animations[i].movement[j].game_seconds` |
| HCO bring-up | Per-player `bringup_per_player_seconds` dict | `turn.bringup_per_player_seconds[pos]` |
| HCO step movement (post-bring-up) | `step_clock_seconds[stepIndex]` (per-step) | `turn.step_clock_seconds[]` |
| FCP/HCT skeleton steps (post-step-1 for HCT) | Same as HCO step movement | `turn.step_clock_seconds[]` |
| Legacy fast break, free throw, putback, pass, etc. | Distance-based AG fallback | (frontend computes) |

Rows below the first apply to the **legacy `playTurnAnimation` path** — turns without `animation_steps[]`.

### Frontend resolution order

In `playTurnAnimation`'s step loop ([turnAnimation.js](FrontEnd/static/js/phaser/animation/turnAnimation.js)):

1. If `curr.game_seconds` is finite and ≥ 0 → `duration = max(50, round(game_seconds × clockSecondMs))`
2. Else legacy fallback: distance-based AG-px-per-sec via `getPlayerDuration(sprite, targetX, targetY)`

In `runSetupTween` (HCO bring-up, just before HCO step 0):

1. If `turnData.bringup_per_player_seconds[playerInfo.pos]` is finite → `duration = max(50, round(× clockSecondMs))`
2. Else legacy fallback: distance-based AG-px-per-sec

### Why this matters

Pre-refactor, backend computed `step_clock_seconds[]` from pace constants × grid distance, while frontend computed tween durations from sprite px-distance ÷ AG-px-per-sec. The two could (and often did) diverge — `step_clock_seconds[]` was used as a tolerance check, not a duration source. The Movement Rate Refactor inverted this so backend is the source of truth, eliminating the drift class of bugs.

### See also

- `../00_General_Systems/UESS_System.md` §3.4 / §9.3 — canonical AG curve and archetype rate table.
- `_documentation_master/projects/Z-Completed/Movement_Rate_Refactor.md` — phase-by-phase implementation history.

## Coordinate Orientation (Court Side)

**Rule:** One attacking side — both offense and defense are drawn on the same attacking half. The backend performs any required orientation before emitting gameplay coordinates.

- **Home team on offense:** Use backend positions as-is. Both teams set up on the home side.
- **Away team on offense:** Backend-authored templates are mirrored with `x_away = 100 - x_home`, with `y` unchanged, before payload emission.

Backend-authoritative gameplay payloads send final display-oriented coordinates. Reusable templates such as HCO string spots may remain home-authored internally, but the backend mirrors them with `x_away = 100 - x_home` before emission when the away team is attacking. Final Turn follows this contract. The frontend converts grid coordinates to pixels and must not infer orientation or mirror gameplay coordinates. Remaining legacy-path migrations are tracked in `../projects/sunset_coords_flipping.md`.

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

## Consistent Heartbeat System

**Status:** ✅ Production (render-only visual layer)

Heartbeat is applied consistently to active player sprites as a visual micro-movement layer, with tempo scaled by `NG`.

- **NG tempo contract:** `NG=1.00 -> 75 BPM`, `NG=0.01 -> 750 BPM`
- **Mapping:** linear interpolation in BPM space between the above anchors
- **Cycle timing:** `halfCycleMs = 30000 / BPM` (full cycle = `60000 / BPM`)
- **Visual movement:** render-space drift only (no gameplay coordinate ownership changes)
- **Safety:** type-safe target selection for sprite/container-backed players; heartbeat never mutates authoritative gameplay `x/y` used by movement systems

### Implementation Points

- `FrontEnd/static/js/phaser/animation/arrivalHeartbeat.js`
  - `ensureConsistentHeartbeat()` starts/maintains heartbeat across active player sprites
  - resolves compatible tween target properties per render object type
  - restores visual target state safely on cleanup
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
  - heartbeat refresh at turn processing entry
  - teardown cleanup on scene shutdown/destroy
- `FrontEnd/static/js/phaser/animation/animation_config.js`
  - heartbeat config: `minBpm`, `maxBpm`, `amplitudePx`, `jitterPx`

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

All turn types route through AnimationRouter. **Schema turns short-circuit** at `AnimationEngine.processTurn` → `animationPlayback.playTurn()` before reaching the handlers below — the listed handler routes apply to turns without `animation_steps[]` (legacy path):

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

**Schema playback:**
- `animationPlayback.js` - UESS schema playback engine (`playTurn`, `dispatchTurnStop`)

**Detection:**
- `animateGameTurns.js` - Turn detection and routing (simplified)

## See Also

- `Animation_Routing_Reference.md` — Detection point catalog + complete handler documentation
- `../00_General_Systems/UESS_System.md` §3.4 / §9.3 — AG-driven timing curve + archetype rates (backend canon)
- `Transition_Systems.md` — Hold times and delay reference
- `_documentation_master/projects/Z-Completed/Movement_Rate_Refactor.md` — Phase-by-phase implementation history of the May 2026 backend-authority shift
- `docs/Animation_System/animation_system.md` — Older comprehensive doc (may have stale claims; cross-reference against the docs above)
