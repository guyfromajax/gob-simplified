# Animation System Overview

> **Last Updated:** January 2025

This document provides an overview of the front-end animation stack for **GOB**, including both the production system and experimental components.

---

## Production Animation System

### Ball Animation System ✅ **COMPLETE**

**Status:** Fully refactored and operational (December 2024)

The ball animation system uses a unified architecture with **BallController** as the single source of truth for ball ownership and state. This system integrates with the WIP_GOB approach for player movement synchronization.

**Architecture:**
- **BallController** (`BallController.js`) - Single source of truth for ball state
  - Manages ball ownership, attachment/detachment, and flight state
  - Lifecycle methods: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`
  - Internal state: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
  
- **BallControllerAdapter** (`BallControllerAdapter.js`) - Backward compatibility layer
  - Provides `attachBallToPlayer()` function with old signature
  - Handles state synchronization with WIP_GOB system
  
- **WIP_GOB Integration** (`ballAnimationSimple.js`)
  - **Ball Holder State:** `scene.gameState.ballHolder` (string ID) - synchronized with BallController
- **Conditional Targets:** `getPlayerTweenTargets()` - includes ball in player tween when player has ball
- **Simple Movement:** `animateBallToPosition()`, `animateShotToRim()` - distance-based duration, arc support

**Key Files:**
- `BallController.js` - Core state management
- `BallControllerAdapter.js` - Compatibility layer
- `ballAnimationSimple.js` - WIP_GOB integration
- `ballTween.js` - Pass animations (uses BallControllerAdapter)
- `ballManager.js` - Shot animations (uses BallControllerAdapter)
- `freeThrow.js`, `fastBreak.js` - Special animations (use BallControllerAdapter)

**Benefits:**
- ✅ Single source of truth (BallController)
- ✅ No ownership conflicts
- ✅ No ball teleports (Phaser handles sync automatically)
- ✅ Lifecycle methods for clean state management
- ✅ Better performance (no update callbacks)
- ✅ Easier debugging (one place to check state)
- ✅ Full WIP_GOB integration for player movement

**See:** 
- `Historical/BALL_ANIMATION_SYSTEM_REFACTORING_PLAN.md` - Complete refactoring details (December 2024)
- `Historical/BALL_ANIMATION_MIGRATION_PLAN.md` - WIP_GOB migration details (earlier work)
- `BALL_OWNERSHIP_CONSOLIDATION_PLAN.md` - Ball ownership system consolidation (December 2024)

---

### Ball Ownership Consolidation ✅ **COMPLETE** (December 2024)

**Summary**: Successfully consolidated three competing ball ownership systems into a single, unified architecture.

**What Was Consolidated**:
1. **Old `ballController.js`** (WeakMap-based system) - ❌ **Removed**
2. **BallController** (Class-based system) - ✅ **Now single source of truth**
3. **ballAnimationSimple.js** (WIP_GOB system) - ✅ **Delegates to BallController**

**What Was Accomplished**:
- ✅ Extended BallController API with all compatibility methods
- ✅ Created unified adapter layer (`BallControllerAdapter`) for backward compatibility
- ✅ Migrated all 8 animation files to use adapter
- ✅ Consolidated 3 different `updateBallOwnership` implementations into one unified function
- ✅ Removed old `ball/ballController.js` file (no longer needed)
- ✅ Reduced code duplication by ~200+ lines
- ✅ Eliminated state synchronization issues

**Result**: 
- **Single source of truth**: `BallController` only
- **Simpler**: One system instead of three
- **More stable**: No state conflicts
- **More scalable**: Easier to extend and maintain
- **Better performance**: Reduced logging overhead

**For Details**: See `BALL_OWNERSHIP_CONSOLIDATION_PLAN.md` for complete migration plan and implementation details.

---

### Defender Coordinate System ✅ **COMPLETE** (December 2024)

**Status:** Fully refactored and operational

The defender coordinate system uses a unified architecture with **`get_defender_coords()`** as the single entry point for all defender positioning (ball handler defenders, non-ball handler defenders, and zone defenders).

**Architecture:**
- **`get_defender_coords()`** (`BackEnd/utils/shared_defense.py`) - Public API wrapper
  - Handles coordinate orientation transformation automatically
  - Accepts coordinates in any orientation (home or away)
  - Returns coordinates in same orientation as input
  - Delegates to `calculate_defender_coords()` for core logic
  
- **`calculate_defender_coords()`** (`BackEnd/utils/shared_defense.py`) - Core unified function
  - Works internally in HOME orientation
  - Handles both BH and non-BH defenders
  - Uses geometric calculation for positioning
  - Implements complex non-BH defender logic (ball_spot/o_spot combinations)

**Key Features:**
- ✅ Single unified function for all defender types
- ✅ Automatic coordinate orientation handling (no manual flipping)
- ✅ Geometric calculation (x_direction from coordinates, not flags)
- ✅ BH defenders always closer to basket
- ✅ Non-BH defenders positioned correctly relative to assignment
- ✅ Full zone defense support (2-3, 3-2, 1-3-1)

**Benefits:**
- ✅ Single source of truth (one function instead of two)
- ✅ No coordinate flipping bugs (handled automatically)
- ✅ Fixed x_direction bug (geometric calculation)
- ✅ Simpler call sites (no manual coordinate transformations)
- ✅ Easier to maintain and extend
- ✅ More testable and debuggable

**See:** 
- `DEFENDER_COORDINATE_SYSTEM_REFACTORING_PLAN.md` - Complete refactoring details (December 2024)

---

### Unified Pass System ✅ **COMPLETE** (January 2025)

**Status:** Fully unified and operational

All pass animations now use a single, centralized system (`passDetection.js`) that provides consistent behavior across all pass types and turn scenarios.

**Architecture:**
- **`passDetection.js`** - Centralized pass detection and handling utility
  - `detectPassAtStep()` - Detects passes from animation data by looking for `action: "pass"` and `action: "receive"` at the same step
  - `handlePassAnimation()` - Executes pass animation using `runPass()` with distance-based duration calculation
  - Sets `scene.passInFlight = true` to prevent `updateBallOwnership` from interfering
  
**Pass Types Unified:**
1. **HCO Passes** - Passes within half-court offense turn animations
   - Used by: `playTurnAnimation()`, `ShotAnimationSystem.animatePlayerMovement()`
   - Detects passes from turn animation data automatically
   
2. **Fast Break Outlet Passes** - Outlet passes during fast break sequences
   - Used by: `fastBreak.js` (via `passDetection.js`)
   - Distance-based duration for smooth animation
   
3. **Side Inbound Passes** (SIDE_INBOUND)
   - Used by: `runSideInboundSetup()`
   - Checks `turnData.animations` for pass actions, falls back to hardcoded SF→PG if not found
   
4. **Baseline Inbound Passes** (BASELINE_INBOUND)
   - Used by: `runInboundSetup()`
   - Checks `turnData.animations` for pass actions, falls back to hardcoded SF→PG if not found
   
5. **Opening Tip → PG Pass**
   - Used by: `openingTip.js`
   - Automatically finds PG for tip winner's team and executes pass
   - Uses synthetic `passInfo` since opening tip doesn't have animation data with pass actions
   
6. **DREB Outlet Passes** (Defensive Rebound → HCO)
   - Used by: `runDefensiveReboundSetup()`
   - Checks `turnData.animations` for pass actions, creates synthetic `passInfo` if not found
   - Maintains backward compatibility with existing outlet pass logic

**Key Features:**
- ✅ Single source of truth for all pass animations
- ✅ Consistent behavior across all pass types
- ✅ Automatic pass detection from animation data
- ✅ Fallback to hardcoded passes when animation data doesn't have pass actions
- ✅ Distance-based duration calculation (300-800ms based on distance)
- ✅ Prevents `updateBallOwnership` from teleporting ball during/after passes
- ✅ Future-proof: When backend adds pass actions to animation data, passes work automatically

**Benefits:**
- ✅ **Consistency**: All passes animate the same way
- ✅ **Maintainability**: Fix bugs or improve pass animation in one place
- ✅ **Scalability**: Easy to add new pass types without duplicating code
- ✅ **Future-proof**: Ready for dynamic inbound passes (when backend provides pass actions)
- ✅ **Backward compatible**: Works with current hardcoded passes and future data-driven passes

**Implementation Details:**
- Pass detection looks for `action: "pass"` in one player's movement step
- Finds corresponding `action: "receive"` in another player's movement at the same step
- Calculates pass duration: `Math.max(300, Math.min(800, (distance / 350) * 1000))`
- Uses `runPass()` from `ballTween.js` for actual animation
- Sets `scene.passInFlight = true` to prevent ball ownership updates during pass

**Key Files:**
- `passDetection.js` - Core pass detection and handling
- `turnAnimation.js` - Uses pass detection in step loop and inbound setups
- `ShotAnimationSystem.js` - Uses pass detection in player movement animation
- `openingTip.js` - Uses pass detection for tip winner → PG pass
- `ballTween.js` - `runPass()` function (used by all passes)

**See:**
- `FrontEnd/static/js/phaser/animation/passDetection.js` - Complete implementation

---

### Animation Routing System ✅ **IN PROGRESS** (Phase 2.5 - January 2025)

**Status:** Partially migrated - HCO turns (MAKE/MISS) now route through AnimationRouter

The animation routing system provides a unified entry point for all turn animations, replacing scattered animation logic with a clean, centralized architecture.

**Architecture:**
- **`AnimationRouter`** (`AnimationRouter.js`) - Single entry point for all animations
  - Handles pre/post setup via `prepareTurnForAnimation()` and `finalizeTurnAfterAnimation()`
  - Manages turn queuing to prevent concurrent processing
  - Integrates BallController and AnimationEngine
  
- **`AnimationEngine`** (`AnimationEngine.js`) - Routes turns to appropriate handlers
  - Determines which handler to use based on turn type
  - Handlers: `ShotAnimationSystem`, `ReboundAnimationSystem`, `PassAnimationSystem`, `FreeThrowAnimationSystem`, `HCOAnimationSystem`
  - Fallback to `playTurnAnimation()` for legacy turn types
  
- **Specialized Animation Systems:**
  - `ShotAnimationSystem` - Handles HCO shots (MAKE/MISS)
  - `ReboundAnimationSystem` - Handles rebounds
  - `PassAnimationSystem` - Handles inbound passes
  - `FreeThrowAnimationSystem` - Handles free throws
  - `HCOAnimationSystem` - Handles HCO outlet passes

**Current Migration Status:**
- ✅ **Phase 2.4**: FCP/HCT foul turns migrated (December 2024)
- ✅ **Phase 2.5**: Standard HCO turns (MAKE/MISS) migrated (January 2025)
- ⏳ **Pending**: Other turn types still use legacy `playTurnAnimation()` path

**Benefits:**
- ✅ Single entry point for all animations
- ✅ Consistent pre/post setup across all turn types
- ✅ Proper ball ownership handling via BallController
- ✅ Easier to maintain and extend
- ✅ Better error handling and debugging

**Key Files:**
- `AnimationRouter.js` - Main entry point
- `AnimationEngine.js` - Turn routing logic
- `turnPreparation.js` - Pre/post setup utilities
- `ShotAnimationSystem.js` - HCO shot handler
- `playTurnAnimation()` - Legacy handler (still used for non-migrated turn types)

**See:**
- `FRONTEND_ORCHESTRATION_CONSOLIDATION_PLAN.md` - Overall migration plan
- `PHASE_2_INCREMENTAL_MIGRATION_PLAN.md` - Incremental migration strategy
- `PHASE_2.5_BUG_FIX_PLAN.md` - HCO migration details

---

### Player Animation System

**Status:** Already using WIP_GOB approach

Player animations already use the simplified approach:
- `animateStep()` uses `getPlayerTweenTargets()` for conditional ball inclusion
- Distance-based duration calculation
- Simple Phaser tweens (no complex following systems)

**Notes:**
- `tweenPlayerTo()` in `ballTween.js` still uses `onUpdate` callback for ball following (only used for fast break outlet passes - low priority cleanup)
- Old system flags (`_shotInProgress`, `ballDetached`, `_putbackInProgress`) are no longer **set** anywhere, but may still be **read** in debug logging or dead code checks
- All ball state is managed by `BallController` - old flags are legacy references only

---

## Experimental Animation System - PossessionRunner

> ⚠️ **IMPORTANT**: This section describes an **experimental animation system** (PossessionRunner) 
> that is **currently DEPRECATED and disabled**. The production system uses the approach documented above. 
> 
> **Status:** PossessionRunner has been removed from production. The code still exists but is not used.
> - `FEATURE_POSSESSION_RUNNER` flag always returns `false`
> - All animation now uses the standard animation path
> 
> **For all development work, refer to the production system above.**

This section gives incoming contributors a concise tour of the **experimental** front-end
animation stack for **GOB**. It covers the architectural goals, the current
state of the migration, and the major components for the PossessionRunner system.

## Goals

- **Deterministic timelines** – drive every possession strictly from backend
  timestamps so replays, debugging, and automated tests are repeatable.
- **Single orchestration path** – replace ad-hoc tween chains with a single
  runner that controls the finite-state machine (FSM), ball ownership, and
  sprite motion.
- **Progressive rollout** – keep the legacy animation path available behind
  `window.FEATURE_POSSESSION_RUNNER` so QA/gameplay can fall back while we port
  additional scenarios.

## Migration Plan (snapshot)

1. **Normalize backend data** into deterministic action graphs.
   - `FrontEnd/static/js/phaser/animation/possession/normalizeTurn.js`
   - Already landed; generates frame-by-frame positions, passes, and terminal
     metadata.
2. **PossessionRunner** consumes normalized graphs, schedules tweens on a
   Phaser timeline, and emits canonical events.
   - `FrontEnd/static/js/phaser/animation/possession/PossessionRunner.js`
   - Implementation is present; still tuning timings, FSM transitions, and
     timeline creation so freezes don’t occur.
3. **Centralise FSM control** around the runner for rebounds/fast breaks.
   - Current focus once runner stability improves.
4. **Port remaining flows** (fast breaks, offensive rebounds) to the runner
   path.
5. **Add diagnostics** (DEBUG_ANIM hooks, teleport detection, etc.).
   - Many hooks exist; we continue to expand them as issues surface.

## Key Modules (Experimental)

- **PossessionRunner** – orchestrates half-court possessions, manages ball
  ownership, queues player tweens, and transitions the FSM. Emits
  `possessionRunner:*` events when `DEBUG_ANIM` is true.
- **Timeline factory** – `animationTimeline.js` produces a Phaser timeline when
  available, falling back to `timelinePolyfill.js` for test environments.
- **Ball helpers** – `ballManager.js` handles passes, rebounds, and shot arcs,
  and integrates with the runner via injected helper callbacks.
- **Fast break / inbound adapters** – legacy systems still handle special
  flows; we're gradually routing them through the runner or compatible
  timelines.

**Note:** The production ball animation system (WIP_GOB approach) is separate from PossessionRunner and is fully operational. See the "Production Animation System" section above.

## Current Challenges

- **Timeline fallback** – on some builds Phaser’s tween manager does not expose
  `createTimeline`, so we fall back to the polyfill. This causes choppy motion
  and can deadlock if helper promises never resolve. Short-term plan: detect
  the correct tween plugin (`scene.sys.tweens`) and prefer it before the
  polyfill.
- **FSM noise** – duplicate `ShotAttempt` transitions and “duplicate possession
  change” warnings indicate the runner and legacy helpers are both emitting
  state changes. We’ve added guards to skip redundant transitions, but more
  cleanup is needed as we centralise control.
- **Telemetry** – instrumentation now reports timeline steps, pending helper
  counts, and delay scheduling, which helps diagnose freezes. Continue to use
  `DEBUG_ANIM` when testing.

## Getting Started

1. Enable debug flags:
   ```js
   window.DEBUG_ANIM = true;
   window.FEATURE_POSSESSION_RUNNER = true;
   ```
2. Run a possession and watch the console for `possessionRunner:*` events,
   timeline warnings, and FSM transitions.
3. If animation freezes, capture the current scene’s tween capabilities to
   confirm whether the native timeline is available.
4. Iterate on the PossessionRunner/timeline factory to keep the timeline
   running exclusively through Phaser’s tween manager.

This overview should help new developers orient themselves quickly. Dive into
the files listed above, keep `DEBUG_ANIM` running, and feel free to expand this
document as the migration advances.

