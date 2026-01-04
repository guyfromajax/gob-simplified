# Master Game Documentation

> **Last Updated:** January 2025
> **Previously:** `docs/Animation_System/animation_system.md`

This document provides comprehensive documentation of the **GOB** game system, including animation, transitions, game flows, and system architecture.

---

**Note:** Turn Data Structure documentation has been moved to:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md`

---


**Note:** Universal Plays and Defenses Collections documentation has been moved to:
- `docs/docs_1_systems/00_Data_Systems/O_&_D_Collections.md`

---

### Animation Preview System ✅ **NEW** (January 2025)

#### Overview
The Play Builder includes an animation preview system that allows users to visualize their plays before saving. The system behaves differently for Motion plays vs Set Plays.

#### Animation Controls

**Variant Selector:**
- **Motion Plays**: Variant selector is hidden - automatically uses `base_loop` variant
- **Set Plays**: Variant selector is shown - user must select from available variants (`successful`, `mid_play_change`, `contested`, `broken`)
- **Dropdown Population**: `updateAnimationVariantDropdown()` populates options based on play type and available steps

**Animate Button:**
- **Motion Plays**: No variant selection required - button works immediately if `base_loop` has steps
- **Set Plays**: Requires variant selection from dropdown before animating
- **Validation**: Checks that selected variant has at least one step before starting animation

#### Animation Behavior

**Set Plays:**
- Animates through all steps sequentially
- Stops at the end of the animation
- Shows step counter: "Animating Step X of Y"

**Motion Plays - Infinite Loop:**
- Animates through all steps sequentially
- **Loop Detection**: When final step (`is_final_step: true`) is reached, automatically loops back to step 0
- **Fallback Loop**: If no final step is marked, loops back to step 0 at the end of all steps
- **Continuous Animation**: Animation continues indefinitely until manually stopped
- **Status Display**: Shows "Animating Step X of Y (Final Step - will loop)" when final step is reached

#### Animation Functions

**`startAnimation()`:**
- **Motion Plays**: Automatically uses `base_loop` variant (no selection needed)
- **Set Plays**: Uses selected variant from dropdown
- **Validation**: Checks for variant existence and step count before starting
- **UI Updates**: Hides animate button, shows stop button, displays status

**`animateNextStep(selectedVariant)`:**
- **Step Rendering**: Updates player positions and actions for current step
- **Loop Logic** (Motion only):
  - Detects when `is_final_step: true` is reached
  - Resets `animationStepIndex` to 0 to loop back
  - If no final step marked, loops at end of steps array
- **Set Play Logic**: Stops animation when all steps are complete
- **Timing**: 1 second delay between steps
- **Status Updates**: Updates status message with current step and loop indication

**`stopAnimation()`:**
- Stops the animation loop
- Clears animation interval
- Resets UI (shows animate button, hides stop button)
- Works for both Motion and Set Plays

#### Key Implementation Details

1. **Variant Selection**: Motion plays bypass variant selection entirely, using `base_loop` automatically
2. **Loop Detection**: Uses `step.is_final_step === true` to identify the loop end point
3. **Index Management**: `animationStepIndex` is reset to 0 when loop condition is met
4. **Status Messages**: Provides clear feedback about current step and loop behavior
5. **Continuous Play**: Motion plays can run indefinitely until user stops them

### Key Files

**Frontend**:
- `FrontEnd/static/play-builder-v2.html` - Main play builder interface
- `FrontEnd/static/play-builder.html` - Legacy play builder (Set Plays only)

**Backend**:
- `BackEnd/api/play_routes.py` - API endpoints for play CRUD operations
- `BackEnd/db.py` - MongoDB connection and `plays_collection` definition

### Future Enhancements

- [x] Animation preview for Motion plays ✅ **COMPLETE** (January 2025)
- [ ] Loop visualization (show loop path)
- [ ] Version cloning between variants
- [ ] Bulk import/export of plays
- [ ] Play templates library

---

**Note:** Core animation system documentation has been moved to dedicated files:
- `docs/docs_1_systems/05_Animation_System/Core_Animation_System.md` - Core architecture and components
- `docs/docs_1_systems/05_Animation_System/Animation_Detection_Reference.md` - Detection point catalog
- `docs/docs_1_systems/05_Animation_System/Animation_Handler_Reference.md` - Handler documentation

---

### State Tracking System ✅ **CORE COMPONENT** (January 2025)

**Status:** Fundamental architectural pattern - used throughout animation system

State tracking is a **core component** of the animation system, following the SS&S principle of single source of truth. This pattern ensures reliable state management across turns and operations.

**Core Principles:**

1. **Single Source of Truth**: One place tracks state (no scattered flags or duplicate state)
2. **Lifecycle Methods**: Explicit state transitions (start/end methods)
3. **Scene-Level State**: Track cross-turn context on scene object
4. **State Clearing**: Always clear state before transitions

**Architecture:**

#### BallController (Ball State)
- **Purpose**: Single source of truth for ball ownership and flight state
- **State Tracked**: `isAttached`, `isInFlight`, `isMoving`, `reason`, `currentOwner`
- **Lifecycle Methods**: `onShotStart()`, `onShotEnd()`, `onPassStart()`, `onPassEnd()`, `onPutbackStart()`, `onPutbackEnd()`
- **Location**: `BallController.js`

**Example:**
```javascript
// BallController tracks ball state
ballController.onShotStart(); // Set isInFlight = true
// ... shot animation ...
ballController.onShotEnd(); // Clear state before next operation
```

#### Scene-Level State (Cross-Turn Context)
- **Purpose**: Track state that persists across multiple turns
- **Pattern**: Store on `scene` object for easy access and debugging

**Examples:**
- `scene.currentPressureType` - Tracks FCP/HCT pressure sequences ("FCP" | "HCT" | null)
- `scene.pressureSequenceActive` - Boolean flag for active pressure sequence
- `scene.currentOffenseTeamId` - Current offensive team
- `scene.gameState.ballHolder` - Ball holder ID (synchronized with BallController)

**Example (FCP/HCT State Tracking):**
```javascript
// Set state when pressure setup detected
if (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT") {
  scene.currentPressureType = turn.next_defensive_setup;
  scene.pressureSequenceActive = true;
}

// Use state for routing (simple check, no complex flag inheritance)
const isFCPHCT = scene.pressureSequenceActive && 
                 (turn.fcp_shot || turn.hct_shot || turn.fcp_foul || turn.hct_foul);

// Clear state when sequence completes
if (turn.result_type === "HCO" && !turn.fcp_shot && !turn.hct_shot) {
  scene.currentPressureType = null;
  scene.pressureSequenceActive = false;
}
```

**Benefits:**
- ✅ **Simple**: One state variable instead of complex flag detection
- ✅ **Reliable**: Doesn't depend on backend flags being present
- ✅ **Maintainable**: Easy to debug (check scene state)
- ✅ **Consistent**: Same pattern everywhere (matches BallController)
- ✅ **SS&S Aligned**: Single source of truth, scalable, sustainable

**State Clearing Pattern:**
Always clear state **before** transitioning to next operation:

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

**Key Files:**
- `BallController.js` - Ball state management
- `animateGameTurns.js` - Scene-level state tracking (FCP/HCT, offense team)
- `ballAnimationSimple.js` - Ball holder state synchronization

**See:**
- `UNIVERSAL_STATE_CLEARING_PATTERN.md` - Detailed state clearing patterns
- `FCP_HCT_STATE_TRACKING_PROPOSAL.md` - FCP/HCT state tracking implementation
- `docs/Animation_System/animation_system.md` - BallController state management (see "State Management Patterns" section)

#### Multi-Turn Sequence State Tracking Pattern ✅ **REPLICABLE** (January 2025)

**Purpose**: Track state across multiple turns for sequences that span multiple turns (e.g., FCP/HCT pressure sequences, HCO sequences with fouls/turnovers, Fast Break sequences, OREB putback sequences).

**Current Implementation**: FCP/HCT pressure sequences (January 2025)

**Pattern Overview**:

1. **State Initialization**: Set scene-level state when sequence begins
2. **State Detection**: Use scene state + turn flags to detect sequence turns
3. **State Persistence**: Keep state active across multiple turns in sequence
4. **State Clearing**: Clear state when sequence completes (not on intermediate turns)

**FCP/HCT Implementation Example**:

```javascript
// 1. STATE INITIALIZATION (in animateGameTurns.js)
// Set state when pressure setup detected (BASELINE_INBOUND with next_defensive_setup)
if (turn.next_play_type === "BASELINE_INBOUND" && 
    (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT")) {
  scene.currentPressureType = turn.next_defensive_setup; // "FCP" or "HCT"
  scene.pressureSequenceActive = true;
}

// Also set state when runInboundSetup() is called inline (for made shots)
// This happens in turnAnimation.js when a made shot sets up the next FCP/HCT turn
if (pressureType) {
  scene.currentPressureType = pressureType;
  scene.pressureSequenceActive = true;
}

// 2. STATE DETECTION (in animateGameTurns.js)
// Detect FCP/HCT turns using explicit flags OR scene state
const hasExplicitFCPHCTFlags = turn.fcp_shot === true || turn.hct_shot === true ||
                               turn.fcp_foul === true || turn.hct_foul === true ||
                               (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));

// For press break outcomes, detect using scene state
const isPressBreakOutcome = (turn.result_type === "HCO" || turn.result_type === "TURNOVER") && 
                            scene.pressureSequenceActive;

// For press break shot attempts, detect using scene state
const isPressBreakShotAttempt = scene.pressureSequenceActive && 
                                 (turn.result_type === "MAKE" || turn.result_type === "MISS");

const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;

// 3. STATE PERSISTENCE (in animateGameTurns.js)
// Don't clear state on intermediate turns (e.g., made shot that sets up next FCP/HCT turn)
const isSettingUpNextFCPHCT = (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
                              (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT");
const shouldClearPressureState = 
  ((turn.result_type === "MAKE" || turn.result_type === "MISS") && !nextTurnIsFCPHCT && !isSettingUpNextFCPHCT) ||
  (turn.result_type === "HCO" && !nextTurnIsFCPHCT) ||
  turn.fcp_foul === true || turn.hct_foul === true ||
  turn.result_type === "TURNOVER";

// 4. STATE CLEARING (in animateGameTurns.js)
// Only clear when sequence actually completes
if (shouldClearPressureState && scene.pressureSequenceActive) {
  scene.currentPressureType = null;
  scene.pressureSequenceActive = false;
}
```

**Key Design Decisions**:

1. **Scene-Level State**: Store on `scene` object for easy access and debugging
   - `scene.currentPressureType` - Type of pressure ("FCP" | "HCT" | null)
   - `scene.pressureSequenceActive` - Boolean flag for active sequence

2. **Multi-Source Detection**: Use explicit flags OR scene state
   - Explicit flags: `fcp_shot`, `hct_shot`, `fcp_foul`, `hct_foul`, `next_defensive_setup`
   - Scene state: `scene.pressureSequenceActive` for press break outcomes/shot attempts

3. **State Persistence**: Don't clear state on intermediate turns
   - Made shot that sets up next FCP/HCT turn: Keep state active
   - Press break shot attempt: Keep state active (detected via scene state)
   - Only clear when sequence completes (HCO transition, foul, turnover)

4. **Detection Logic**: Three-part detection
   - Explicit flags (for setup turns and explicit FCP/HCT outcomes)
   - Press break outcomes (HCO/TURNOVER during active sequence)
   - Press break shot attempts (MAKE/MISS during active sequence)

**Replication Guide for Other Use Cases**:

**For HCO Sequences with Fouls/Turnovers**:
```javascript
// 1. Initialize state when HCO sequence begins
scene.hcoSequenceActive = true;
scene.hcoSequenceType = "HCO"; // Could track specific HCO type

// 2. Detect HCO sequence turns
const isHCOSequence = scene.hcoSequenceActive && 
                     (turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                      turn.result_type === "HCO" || turn.o_foul === true ||
                      turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns (e.g., foul during HCO sequence)

// 4. Clear state when sequence completes
if (turn.result_type === "DREB" || turn.result_type === "OREB") {
  scene.hcoSequenceActive = false;
  scene.hcoSequenceType = null;
}
```

**For Fast Break Sequences**:
```javascript
// 1. Initialize state when fast break begins
scene.fastBreakSequenceActive = true;

// 2. Detect fast break sequence turns
const isFastBreakSequence = scene.fastBreakSequenceActive && 
                            (turn.result_type === "FAST_BREAK" ||
                             turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                             turn.fast_break_foul === true || turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns

// 4. Clear state when sequence completes
if (turn.result_type === "HCO" || turn.result_type === "DREB") {
  scene.fastBreakSequenceActive = false;
}
```

**For OREB Putback Sequences**:
```javascript
// 1. Initialize state when OREB occurs
scene.orebSequenceActive = true;

// 2. Detect OREB sequence turns
const isOREBSequence = scene.orebSequenceActive && 
                      (turn.result_type === "OREB" ||
                       turn.result_type === "MAKE" || turn.result_type === "MISS" ||
                       turn.oreb_foul === true || turn.result_type === "TURNOVER");

// 3. Persist state across multiple turns
// Don't clear on intermediate turns

// 4. Clear state when sequence completes
if (turn.result_type === "DREB" || turn.result_type === "HCO") {
  scene.orebSequenceActive = false;
}
```

**Benefits of This Pattern**:
- ✅ **Simple Detection**: One scene state variable instead of complex flag inheritance
- ✅ **Reliable**: Doesn't depend on backend flags being present on every turn
- ✅ **Maintainable**: Easy to debug (check scene state in console)
- ✅ **Scalable**: Easy to extend to other multi-turn sequences
- ✅ **SS&S Aligned**: Single source of truth, scalable, sustainable

**Key Files**:
- `animateGameTurns.js` - FCP/HCT state tracking implementation
- `turnAnimation.js` - State initialization via `runInboundSetup()`

**Future Work**:
- Replicate pattern for HCO sequences with fouls/turnovers
- Replicate pattern for Fast Break sequences
- Replicate pattern for OREB putback sequences

#### Offensive State Values ✅ **REFERENCE** (January 2025)

**Purpose**: `offensive_state` is the **routing state** that determines which logic function handles each turn in the backend.

**All Possible Values**:

1. **`"HCO"`** - Half Court Offense (default)
   - **When set**: Default state, regular half-court possessions, after side inbounds, after turnovers (dead ball), after defensive stops
   - **Routes to**: `resolve_half_court_offense()` in `turn_manager.py`
   - **Set by**: Default initialization, `game_manager.py` (after side inbound), `phase_resolution.py` (after turnovers, defensive stops), `shot_manager.py` (after missed fast break shots)

2. **`"FREE_THROW"`** - Free Throw Situation
   - **When set**: AND-1 situations, shooting fouls, bonus free throws
   - **Routes to**: `resolve_free_throw()` in `turn_manager.py`
   - **Set by**: `shot_manager.py` (AND-1, shooting fouls), `phase_resolution.py` (bonus free throws)

3. **`"FAST_BREAK"`** - Fast Break Situation
   - **When set**: After defensive rebounds with defense release, after steals with fast break chance
   - **Routes to**: `resolve_fast_break_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (after DREB with defense release), `phase_resolution.py` (after steals with fast break chance)

4. **`"FCP"`** - Full Court Press
   - **When set**: After made shots when defense applies full court press
   - **Routes to**: `resolve_full_court_press_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (made shots), `turn_manager.py` (OREB putbacks), `phase_resolution.py` (after free throws)

5. **`"HCT"`** - Half Court Trap
   - **When set**: After made shots when defense applies half court trap
   - **Routes to**: `resolve_half_court_trap_logic()` in `phase_resolution.py`
   - **Set by**: `shot_manager.py` (made shots), `turn_manager.py` (OREB putbacks), `phase_resolution.py` (after free throws)

**Important Notes**:
- `offensive_state` is **persistent** across API calls (stored in `game_state`)
- `offensive_state` is **NOT** set on every turn - it's only set when the state needs to change
- If `offensive_state` is not set, it defaults to `"HCO"` (line 261 in `turn_manager.py`)
- `offensive_state` is the **single source of truth** for routing - handlers set it, `turn_manager.py` reads it

**Debugging**:
- Debug logs are added at transition points in `turn_manager.py`:
  - **Before routing** (`🔄 [OFFENSIVE_STATE TRANSITION] Turn #X - BEFORE ROUTING`):
    - `previous_offensive_state`: The state from the previous turn
    - `current_offensive_state`: The state being used to route this turn
    - `transition`: Shows the transition (e.g., `"HCO → FREE_THROW"`)
  - **After handler** (`🔄 [OFFENSIVE_STATE TRANSITION] Turn #X - AFTER HANDLER`):
    - `current_offensive_state`: The state that was used to route this turn
    - `next_offensive_state`: The state that will be used to route the next turn (set by handler)
    - `transition`: Shows the transition (e.g., `"FREE_THROW → HCO"`)
    - `state_changed`: Boolean indicating if the handler changed the state
    - `next_play_type`: Informational only (not used for routing)
- Look for `🔄 [OFFENSIVE_STATE TRANSITION]` in logs to trace state changes across turns
- The logs show the complete flow: `previous → current → next` for each turn

---

#### Backend State Preservation Pattern ✅ **CRITICAL** (January 2025)

**Purpose**: Ensure the backend generates the correct turn sequence by preserving `offensive_state` after generating intermediate turns (e.g., BASELINE_INBOUND).

**Why This Matters**:
After a made shot, the backend generates a separate BASELINE_INBOUND turn. To ensure the next API call generates the correct follow-up turn (FCP/HCT setup turn or regular HCO turn), the backend must preserve `offensive_state` after generating the BASELINE_INBOUND turn.

**The Pattern**:

1. **Made Shot Sets State**: When a shot is made, the backend sets `offensive_state` based on defensive pressure type:
   ```python
   # In shot_manager.py (HCO makes)
   pressure_type = self.game.turn_manager.determine_defensive_pressure_type()  # "FCP", "HCT", or "HCO"
   self.game_state["offensive_state"] = pressure_type
   result["next_defensive_setup"] = pressure_type
   ```

2. **Generate BASELINE_INBOUND Turn**: After the made shot, generate a separate BASELINE_INBOUND turn:
   ```python
   # In game_manager.py
   if (result.get("result_type") == "MAKE" and 
       result.get("next_play_type") == "BASELINE_INBOUND"):
       next_defensive_setup = result.get("next_defensive_setup")
       inbound_payload = self.turn_manager.setup_baseline_inbound(next_defensive_setup=next_defensive_setup)
       self.turns.append(inbound_payload)
   ```

3. **Preserve State for Next API Call**: After generating BASELINE_INBOUND, preserve `offensive_state` so the next API call generates the correct turn:
   ```python
   # In game_manager.py (CRITICAL)
   if next_defensive_setup:
       self.game_state["offensive_state"] = next_defensive_setup
   ```

**Complete Flow Example**:

**HCO Make → FCP Setup**:
1. Made shot sets `offensive_state = "FCP"` and `next_defensive_setup = "FCP"`
2. Backend generates BASELINE_INBOUND turn with `next_defensive_setup = "FCP"`
3. Backend preserves `offensive_state = "FCP"` after generating BASELINE_INBOUND
4. Next API call sees `offensive_state == "FCP"` → Generates FCP setup turn (FOUL/HCO/TURNOVER)

**HCO Make → HCO (No Pressure)**:
1. Made shot sets `offensive_state = "HCO"` and `next_defensive_setup = "HCO"`
2. Backend generates BASELINE_INBOUND turn with `next_defensive_setup = "HCO"`
3. Backend preserves `offensive_state = "HCO"` after generating BASELINE_INBOUND
4. Next API call sees `offensive_state == "HCO"` → Generates regular HCO turn

**Consistency Across All Made Shot Types**:

This pattern is used consistently across all made shot types:

- **OREB Putback**: Sets `offensive_state = pressure_type` in `resolve_offensive_rebound_turn()` → Preserved automatically
- **Free Throw**: Sets `offensive_state = pressure_type` in `resolve_free_throw_logic()` → Preserved automatically
- **HCO Make**: Sets `offensive_state = pressure_type` in `shot_manager.py` → **Now explicitly preserved** in `game_manager.py` after BASELINE_INBOUND

**Why HCO Makes Needed Explicit Preservation**:

OREB putback and Free Throw don't generate separate BASELINE_INBOUND turns, so `offensive_state` is preserved automatically. HCO makes generate a separate BASELINE_INBOUND turn, so we must explicitly preserve `offensive_state` after generating it.

**Benefits**:
- ✅ **Consistent Pattern**: Same behavior across all made shot types (HCO, OREB, Free Throw)
- ✅ **Correct Turn Generation**: Next API call generates the correct follow-up turn
- ✅ **SS&S Aligned**: Explicit state preservation, no reliance on defaults
- ✅ **Maintainable**: Clear, uniform logic that's easy to understand and debug

**Key Files**:
- `BackEnd/models/game_manager.py` - State preservation after BASELINE_INBOUND generation
- `BackEnd/models/shot_manager.py` - Initial state setting for HCO makes
- `BackEnd/models/turn_manager.py` - State setting for OREB putbacks
- `BackEnd/engine/phase_resolution.py` - State setting for Free Throws

**See**:
- `docs/FCP_HCT_FLOW_COMPARISON.md` - Comparison of made shot flows

---

**Detection Architecture:**

**Flow:**
```
animateGameTurns.js (detection)  ← STEP 1
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)
    ↓
Specialized Handlers (execution)
```

**Detection Pattern:**
All detections follow this pattern:
1. Check turn properties (`result_type`, flags, state)
2. Set `turn.index = i`
3. Call `await animationRouter.processTurn(turn)`
4. `continue` to next turn

**Detection Points (In Order of Execution):**

1. **FREE_THROW** (Line 560)
   - Detection: `turn.result_type === "FREE_THROW"`
   - Routes to: `AnimationRouter` → `handleFreeThrow()`
   - Notes: Active player display, free throw sequence, and text scroll handled by handler

2. **FOUL (FCP/HCT with animations)** (Line 571-573)
   - Detection: `turn.result_type === "FOUL" && (turn.fcp_foul === true || turn.hct_foul === true) && turn.animations && turn.animations.length > 0`
   - Routes to: `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
   - Notes: Only FCP/HCT fouls with animations route through AnimationRouter; non-animated fouls just do announcements

3. **DEAD BALL** (Line 596)
   - Detection: `turn.result_type === "DEAD BALL"`
   - Routes to: Direct announcements (no AnimationRouter)
   - Notes: No animation, just announcements and score updates

4. **SIDE_INBOUND** (Line 611)
   - Detection: `turn.result_type === "SIDE_INBOUND" && !scene.stateMachine?.is(States.FastBreak)`
   - Routes to: `AnimationRouter` → `handleSideInbound()`
   - Notes: Skips animation if in FastBreak state; still does announcements/updates

5. **BASELINE_INBOUND** (Line 633)
   - Detection: `turn.result_type === "BASELINE_INBOUND"`
   - Routes to: `AnimationRouter` → `handleBaselineInbound()`
   - Notes: FCP/HCT state tracking, player animations, and state transitions handled by handler

6. **DEFENSIVE_STOP** (Line 644)
   - Detection: `turn.result_type === "DEFENSIVE_STOP"`
   - Routes to: `AnimationRouter` → `handleDefensiveStop()`
   - Notes: Fast Break defensive stops route to `handleFastBreak()`; non-Fast Break uses `handleDefensiveStop()`

7. **PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT** (Line 655)
   - Detection: `turn.result_type === "PUTBACK_MAKE" || turn.result_type === "PUTBACK_MISS" || turn.result_type === "OREB_KICKOUT"`
   - Routes to: `AnimationRouter` → `handlePutback()`
   - Notes: All three result types use the same handler; includes debug logging for putback/OREB path tracking

8. **FCP/HCT Detection (Complex)** (Line 707-1055)
   - Detection: Multi-part detection logic
   - Routes to: `playTurnAnimation()` directly (not through AnimationRouter)
   - Detection Logic:
     ```javascript
     // Part 1: Explicit flags
     const hasExplicitFCPHCTFlags = 
       turn.fcp_shot === true || turn.hct_shot === true ||
       turn.fcp_foul === true || turn.hct_foul === true ||
       (isBaselineInbound && (turn.next_defensive_setup === "FCP" || turn.next_defensive_setup === "HCT"));
     
     // Part 2: Press break outcomes
     const isPressBreakOutcome = 
       (turn.result_type === "HCO" || turn.result_type === "TURNOVER") && 
       scene.pressureSequenceActive;
     
     // Part 3: Press break shot attempts
     const isPressBreakShotAttempt = 
       scene.pressureSequenceActive && 
       (turn.result_type === "MAKE" || turn.result_type === "MISS") &&
       (turn.fcp_shot === true || turn.hct_shot === true);
     
     const isFCPHCT = hasExplicitFCPHCTFlags || isPressBreakOutcome || isPressBreakShotAttempt;
     ```
   - Notes: Uses scene-level state; routes directly to `playTurnAnimation()` (not through AnimationRouter); handles both setup turns and shot attempts

9. **TURNOVER** (Line 1057)
   - Detection: `turn.result_type === "TURNOVER"`
   - Routes to: `AnimationRouter` → `handleTurnover()`
   - Notes: Only detected if not already caught by FCP/HCT detection above

10. **OPENING_TIP** (Line 1078)
    - Detection: `turn.result_type === "OPENING_TIP"`
    - Routes to: `AnimationRouter` → `handleOpeningTip()`
    - Notes: Handler validates timing (Q1 start or OT start); state transition to HalfCourt handled by handler

11. **FAST_BREAK (Legacy Detection)** (Line 1104)
    - Detection: `turn.fast_break === true || turn.result_type === "FAST_BREAK"`
    - Routes to: Direct call to `runFastBreakSequence()` (legacy path)
    - Notes: Legacy code that should be removed in favor of detection at line 1141

12. **FAST_BREAK (New Detection)** (Line 1141)
    - Detection: `turn.result_type === "FAST_BREAK" || ((turn.result_type === "MAKE" || turn.result_type === "MISS") && turn.fast_break === true)`
    - Routes to: `AnimationRouter` → `handleFastBreak()`
    - Notes: Handles both explicit FAST_BREAK turns and MAKE/MISS with fast_break flag

13. **HCO Setup Turns** (Line 1156-1166)
    - Detection: `turn.result_type === "HCO" && !(turn.result_type === "MAKE" || turn.result_type === "MISS") && !isFCPHCTTurnForHCO`
    - Routes to: `AnimationRouter` → `handleDefault()` → `playTurnAnimation()`
    - Notes: Excludes FCP/HCT turns and shot attempts; only detects pure HCO setup turns

14. **HCO Shots (MAKE/MISS)** (Line 1068-1153)
    - Detection: `const isHCO = !isFastBreak && (turn.result_type === "MAKE" || turn.result_type === "MISS")`
    - Routes to: `AnimationRouter` → `AnimationEngine` → `handleShotAttempt()` → `ShotAnimationSystem`
    - Notes: Uses `result_type` check directly (not `current_turn === "HCO"`). Excludes fast breaks and FCP/HCT turns. Standard half-court offense shots.

15. **STEAL (Standalone Turn)** (Line 1290)
    - Detection: `!scene.stateMachine?.is(States.FastBreak) && turn.result_type === "STEAL"`
    - Routes to: `AnimationRouter` → `handleSteal()`
    - Notes: Only routes standalone STEAL turns; STEAL events within other turns are handled inline

16. **STEAL (Event Within Turn)** (Line 1296)
    - Detection: `!scene.stateMachine?.is(States.FastBreak) && stealEvent` (where `stealEvent = turn.events?.find(e => e.event_type === "STEAL")`)
    - Routes to: Direct call to `runPass()` (inline, not through AnimationRouter)
    - Notes: Not a standalone turn, so doesn't route through AnimationRouter; handled inline with pass animation

**Detection Summary by Result Type:**

| Result Type | Detection Line | Routes Through AnimationRouter? | Handler |
|------------|---------------|--------------------------------|---------|
| `FREE_THROW` | 560 | ✅ Yes | `handleFreeThrow()` |
| `FOUL` (FCP/HCT with animations) | 571 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `FOUL` (non-animated) | 571 | ❌ No | Direct announcements |
| `DEAD BALL` | 596 | ❌ No | Direct announcements |
| `SIDE_INBOUND` | 611 | ✅ Yes | `handleSideInbound()` |
| `BASELINE_INBOUND` | 633 | ✅ Yes | `handleBaselineInbound()` |
| `DEFENSIVE_STOP` | 644 | ✅ Yes | `handleDefensiveStop()` |
| `PUTBACK_MAKE` | 655 | ✅ Yes | `handlePutback()` |
| `PUTBACK_MISS` | 655 | ✅ Yes | `handlePutback()` |
| `OREB_KICKOUT` | 655 | ✅ Yes | `handlePutback()` |
| FCP/HCT (any type) | 707-1055 | ❌ No | Direct to `playTurnAnimation()` |
| `TURNOVER` | 1057 | ✅ Yes | `handleTurnover()` |
| `OPENING_TIP` | 1078 | ✅ Yes | `handleOpeningTip()` |
| `FAST_BREAK` (explicit) | 1141 | ✅ Yes | `handleFastBreak()` |
| `MAKE`/`MISS` (fast_break) | 1141 | ✅ Yes | `handleFastBreak()` |
| `HCO` (setup turn) | 1156 | ✅ Yes | `handleDefault()` → `playTurnAnimation()` |
| `MAKE`/`MISS` (HCO shot) | 1069 | ✅ Yes | `handleShotAttempt()` → `ShotAnimationSystem` |
| `STEAL` (standalone) | 1290 | ✅ Yes | `handleSteal()` |
| `STEAL` (event) | 1296 | ❌ No | Direct to `runPass()` |

**Detection by Flag/Property:**

**By `result_type`:**
- `FREE_THROW` → Line 568
- `FOUL` → Line 579
- `DEAD BALL` → Line 614
- `SIDE_INBOUND` → Line 648
- `BASELINE_INBOUND` → Line 670
- `DEFENSIVE_STOP` → Line 681
- `PUTBACK_MAKE` → Line 692
- `PUTBACK_MISS` → Line 692
- `OREB_KICKOUT` → Line 692
- `TURNOVER` → Line 932
- `OPENING_TIP` → Line 953
- `FAST_BREAK` → Line 984
- `HCO` → Line 1006 (result_type check only, not routing)
- `MAKE` → Line 984 (fast break) or 1069 (HCO) or 812 (FCP/HCT)
- `MISS` → Line 984 (fast break) or 1069 (HCO) or 812 (FCP/HCT)
- `STEAL` → Line 1157

**By Flag:**
- `turn.fast_break === true` → Line 1104 (legacy) or 1141 (new)
- `turn.fcp_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.hct_foul === true` → Line 571 (FOUL) or 707 (FCP/HCT detection)
- `turn.fcp_shot === true` → Line 707 (FCP/HCT detection)
- `turn.hct_shot === true` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "FCP"` → Line 707 (FCP/HCT detection)
- `turn.next_defensive_setup === "HCT"` → Line 707 (FCP/HCT detection)

**By State:**
- `scene.pressureSequenceActive === true` → Line 707 (FCP/HCT detection)
- `scene.stateMachine?.is(States.FastBreak)` → Line 611 (SIDE_INBOUND skip), 1290 (STEAL skip)

**By Event:**
- `turn.events?.find(e => e.event_type === "STEAL")` → Line 1296 (inline STEAL event)

**Special Cases:**

1. **FCP/HCT Detection (Not Through AnimationRouter)**
   - **Why:** FCP/HCT turns route directly to `playTurnAnimation()` instead of through `AnimationRouter`
   - **Reason:** Historical implementation - could be migrated in future phase

2. **STEAL Events (Not Through AnimationRouter)**
   - **Why:** STEAL events within other turns are not standalone turns, so they don't need routing
   - **Reason:** Events are handled inline as part of the parent turn's animation

3. **Legacy FAST_BREAK Detection**
   - **Why:** Two detection points for fast breaks (line 1104 and 1141)
   - **Reason:** Line 1104 is legacy code that should be removed

**Detection Order Matters:**

The order of detections is **critical** because:
1. **Early exits:** Once a detection matches, the turn is processed and the loop `continue`s
2. **Exclusion logic:** Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT)
3. **State dependencies:** Some detections depend on state set by previous detections (e.g., FCP/HCT uses `scene.pressureSequenceActive`)

**Current Order (as executed):**
1. FREE_THROW (Line 568)
2. FOUL (Line 579)
3. DEAD BALL (Line 614)
4. SIDE_INBOUND (Line 648)
5. BASELINE_INBOUND (Line 670)
6. DEFENSIVE_STOP (Line 681)
7. PUTBACK_MAKE/MISS/OREB_KICKOUT (Line 692)
8. FCP/HCT (complex detection, Line 707-928)
9. TURNOVER (Line 932)
10. OPENING_TIP (Line 953)
11. FAST_BREAK (Line 984)
12. HCO result_type check (Line 1006 - debug only, not routing)
13. HCO shots (MAKE/MISS) (Line 1069 - uses `result_type` check, not `current_turn`)
14. STEAL (standalone) (Line 1157)
15. STEAL (event) (Line 1178)

**Important Notes:**

1. **HCO Routing:** Uses `result_type === "MAKE" || result_type === "MISS"` check (not `current_turn === "HCO"`). This is more permissive and catches all HCO shots, including those where `current_turn` might not be set correctly.

2. **FCP/HCT Routing:** Currently routes directly to `playTurnAnimation()` (not through AnimationRouter). This is historical implementation - could be migrated in future phase.

3. **Detection Order Matters:** Early exits prevent double processing. Later detections exclude turns already handled (e.g., HCO detection excludes FCP/HCT).

---

**Note:** Turn-by-Turn Simulation System documentation has been moved to:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md`

---

**Note:** Timeout System documentation has been moved to:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Timeout_System.md`

**Note:** Playbooks Page documentation has been moved to:
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Playbooks_Page.md`

**Note:** Animation Handler documentation has been moved to:
- `docs/docs_1_systems/05_Animation_System/Animation_Handler_Reference.md`

---

## Key Files
   - **Captures `timeout_offense_team_id`** before creating timeout turn (`BackEnd/models/game_manager.py` line 272)
   - Creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`
   - **✅ CRITICAL FIX (January 2025):** Immediately saves game state to database (same pattern as user-initiated timeout)
   - Frontend navigates with `resume_from_timeout=true` flag (`FrontEnd/static/js/phaser/utils/foulOutPopup.js`)

**Timeout Turn Payload:**

```python
{
    "result_type": "TIMEOUT",
    "current_turn": "TIMEOUT",
    "timeout_reason": "USER" | "COMPUTER" | "FOUL_OUT" | "QUARTER_END",
    "next_play_type": "SIDE_INBOUND" | "FREE_THROW" | "BASELINE_INBOUND",
    "next_turn": "SIDE_INBOUND" | "FREE_THROW" | "BASELINE_INBOUND",
    "offense_team_id": game.offense_team.team_id,
    "quarter": game.quarter,
    "text": "Timeout called by [Team Name]",
    "time_elapsed": 0,  # Timeouts don't consume game time
    "possession_flips": False,
    "timeout_calling_team": {
        "name": calling_team.name,
        "team_id": calling_team.team_id
    },
    "home_team_timeouts": gm.home_team.timeouts,
    "away_team_timeouts": gm.away_team.timeouts
}
```

**Next Play Type Determination:**

The `next_play_type` in the timeout turn is **always** `"SIDE_INBOUND"` (except when free throws are pending):

1. **`"SIDE_INBOUND"` (Always for timeouts):**
   - Timeouts always resume with SIP (Side Inbound Pass)
   - Team that had possession when timeout was called gets the ball back
   - Creates SIP turn after timeout resume
   - SIP transitions to HCO (defense calls play in HCO)

2. **`"FREE_THROW"` (Special case):**
   - Used when timeout is called during free throw sequence
   - Free throw sequence continues after timeout resume

**Note:** Quarter breaks (Q2/Q3/Q4) use BIP (Baseline Inbound Pass), but this is handled separately in `simulate_quarter()` and is not part of the timeout system.

**Transition System Integration:**

Timeouts use the same centralized transition system as all other turns:

**Backend (`BackEnd/models/game_manager.py` `determine_next_turn()`):**
```python
# TIMEOUT → SIP/Free Throw/BIP (based on next_play_type in timeout turn)
if current == "TIMEOUT":
    return result.get("next_play_type", "SIDE_INBOUND")
```

**Frontend (`FrontEnd/static/js/phaser/animation/animateGameTurns.js`):**
```javascript
if (turn.result_type === "TIMEOUT") {
    turn.index = i;
    await animationRouter.processTurn(turn);
    console.log('⏸️ TIMEOUT: Stopping animation loop - user will navigate to lineup screen');
    break; // Exit the loop - don't process any more turns
}
```

**Key Point:** Timeouts are routed through `AnimationRouter.processTurn()` just like all other turn types, ensuring consistent handling and data flow.

### Game Start and Resume Transitions

The system handles different transition types based on game state. All navigation uses the unified Timeout Navigation Helper for consistent parameter building.

#### 1. **Game Start (Q1) and Overtime**
- **Initial Turn:** Opening Tip
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 392-401)
- **Logic:** Q1 or any OT period → creates opening tip turn
- **Data:** No special state needed (new game)
- **Navigation:** Helper does NOT pass `game_id` for new Q1 game start
- **Frontend:** `set-lineup.js` "Play Now" button, `game-plan.js` "Play Game" button

#### 2. **Quarter Break Returns (Q2, Q3, Q4)**
- **Initial Turn:** BASELINE_INBOUND (BIP)
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 402-443, 444-468, 469-493)
- **Logic:** Quarter break → creates BIP turn with correct possession team
- **Data:** Uses `opening_tip_winner` from game_state to determine possession
- **Navigation:** Helper passes `game_id` (quarter > 1), does NOT set `resume_from_timeout`
- **Frontend:** `gameScene.js` quarter end navigation, `set-lineup.js` "Play Now" button
- **Note:** Not part of timeout system - handled separately

#### 3. **Timeout Returns (Any Quarter)**
- **Initial Turn:** SIDE_INBOUND (SIP)
- **Location:** `BackEnd/main.py` `simulate_quarter()` (lines 281-332)
- **Logic:** Timeout resume → creates SIP turn with team that had possession
- **Data:** Restores `timeout_next_play_type` and `timeout_offense_team_id` from database
- **Navigation:** Helper passes `game_id` AND sets `resume_from_timeout=true` (any quarter)
- **Frontend:** `timeoutButtonManager.js` timeout button, `set-lineup.js` "Play Now" button, `game-plan.js` "Play Game" button
- **Note:** Supports Q1-Q4 and OT (removed Q1-only restriction)

#### 4. **Player Foul Out Returns (Any Quarter)** ✅ **UPDATED** (January 2025)
- **Initial Turn:** SIDE_INBOUND (SIP) or FREE_THROW (based on foul context)
- **Location:** Same as timeout returns (uses timeout system)
- **Logic:** Foul out resume → creates SIP or FREE_THROW turn based on foul context
- **Data:** Uses same timeout resume system, captures `timeout_offense_team_id` in `game_manager.py`
- **Navigation:** Helper passes `game_id` AND sets `resume_from_timeout=true` (any quarter)
- **Frontend:** `foulOutPopup.js` navigation to lineup
- **Note:** Supports Q1-Q4 and OT (uses same system as timeout)

**Foul Out Context System:**
- **Purpose:** Stores detailed foul information to guide next play type determination
- **Location:** `game_state["foul_out_context"]` dictionary
- **Contents:**
  - `foul_type`: "OFFENSIVE" or "DEFENSIVE"
  - `is_shooting_foul`: Boolean (True for shooting fouls, False for non-shooting)
  - `is_bonus`: Boolean (True if team is in bonus situation)
  - `next_play_type`: "SIDE_INBOUND" or "FREE_THROW" (determined by foul context)
  - `shooter`: Player object (for shooting fouls, stores shooter for free throw resume)
- **Set By:** Foul resolution logic in `phase_resolution.py` (non-shooting fouls) and `shot_manager.py` (shooting fouls)
- **Used By:** `turn_manager.py` `setup_timeout_turn()` to determine `next_play_type` for foul-out timeouts

**Possession Flip Logic:**
- **Offensive Fouls:** Possession flips during SIP setup (not during foul resolution)
  - Location: `phase_resolution.py` `resolve_non_shooting_foul()` sets `possession_flips: True` (line ~384)
  - **✅ FIX (January 2025):** Does NOT call `game.switch_possession()` in `resolve_non_shooting_foul()`
  - Actual flip happens in `game_manager.py` `simulate_macro_turn()` before `setup_side_inbound()` (line ~300)
  - This prevents double-flipping and ensures consistent behavior (same pattern as dead ball turnovers)
  - **Flow:**
    1. HCO turn with offensive foul: `offense_team_id` = team that committed foul (e.g., "BENTLEY_TRUMAN")
    2. `resolve_non_shooting_foul()` sets `possession_flips: True` but does NOT flip `game.offense_team`
    3. `game_manager.py` checks `possession_flips=True` and calls `game.switch_possession()`
    4. SIP turn created: `offense_team_id` = new offense team (e.g., "LANCASTER")
  - Next step: SIDE_INBOUND (with new offense team after flip)
- **Defensive Fouls:** No possession flip
  - If Shooting Foul: Next step: FREE_THROW (the shooting player shoots)
  - If Non-Shooting Foul:
    - If Bonus Situation: Next step: FREE_THROW (the player the fouling player was guarding shoots)
    - If Non-Bonus Situation: Next step: SIDE_INBOUND

**Next Play Type Determination:**
- **Location:** `turn_manager.py` `setup_timeout_turn()` (lines 1611-1676)
- **Logic:**
  1. For foul-out timeouts: Uses `foul_out_context` to determine `next_play_type`
  2. For regular timeouts with free throws: Uses `free_throws_remaining` to set `next_play_type = "FREE_THROW"`
  3. For regular timeouts: Defaults to `next_play_type = "SIDE_INBOUND"`
- **Stored In:** `game_state["timeout_next_play_type"]` for resume

**Lineup Screen Population:**
- **Location:** `FrontEnd/static/js/phaser/utils/foulOutPopup.js` `showFoulOutPopup()` function
- **Logic:**
  1. Fetches current lineup from URL parameters (same as timeout flow)
  2. Removes **only** the fouled-out player from the user's team lineup
  3. Leaves the fouled-out player's position empty (not replaced)
  4. Passes populated lineup (minus foul out player) to `TimeoutNavigationHelper`
- **Key Point:** Only removes the fouled-out player if they're on the user's team; other team's lineup is preserved

**Clock Display:**
- **Location:** `FrontEnd/static/js/phaser/gameScene.js` (lines 392-410)
- **Logic:** Clock is initialized immediately on page load using first turn's clock data from backend
- **Ensures:** Correct time remaining displays immediately when returning from lineup/game plan screens, not a stale value that updates only after the next turn

**Clock Preservation for Timeout Navigation:**
- **Location:** `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()` function
- **Logic:** Clock is retrieved using a prioritized fallback chain:
  1. **API Response** (`timeoutResult.clock`): **Most reliable** - backend source of truth, returned by `/api/call-timeout` endpoint at the moment the timeout is called
  2. **DOM Element** (`#game-clock`): What's actually displayed to the user
  3. **scene.simData.clock**: Updated by `updateScoreboard()` as turns are processed (lines 1153-1158 in `gameScene.js`)
  4. **Last Processed Turn**: If turns array exists, get clock from the last turn's `clock` or `game_clock` field
  5. **URL Parameters**: Fallback for initial load scenarios
  6. **Default**: `8:00` if no clock found (should never happen in normal flow)
- **Key Fix (February 2025):** 
  - **Initial Fix:** `scene.simData.clock` was only set on initial load and never updated, causing stale clock values. Fixed by updating `scene.simData.clock` in `updateScoreboard()` whenever a turn's clock is processed.
  - **Final Fix:** The `/api/call-timeout` endpoint now returns the current clock value (`gm.game_state.get("clock")`) in its response, ensuring the frontend always has the accurate clock at the moment the timeout is called. This prevents timing issues where the DOM or scene state might be stale when the timeout button is pressed.

**Key Files:**
- `BackEnd/engine/phase_resolution.py` - Foul resolution and `foul_out_context` storage (non-shooting fouls)
- `BackEnd/models/shot_manager.py` - Shooting foul resolution and `foul_out_context` storage
- `BackEnd/models/game_manager.py` - Foul-out timeout creation and immediate database save (lines 245-304)
- `BackEnd/models/turn_manager.py` - `setup_timeout_turn()` with `foul_out_context` support
- `FrontEnd/static/js/phaser/utils/foulOutPopup.js` - Lineup population and navigation
- `FrontEnd/static/js/phaser/gameScene.js` - Clock initialization on timeout resume

### Data Management: Database, LocalStorage, and URL

#### Database (Single Source of Truth)

**When Timeout is Called:**

**User-Initiated Timeout (`BackEnd/api/api.py` `call_timeout_endpoint()`):**
```python
# Save timeout state to database
gm.game_state["timeout_next_play_type"] = "SIDE_INBOUND"  # Always SIP (except free throws)
gm.game_state["timeout_offense_team_id"] = gm.offense_team.team_id  # Capture possession team

db_summary = summarize_game_state(gm, exclude_animations=True)
games_collection.update_one({"_id": game_id}, {"$set": db_summary}, upsert=True)

# Return timeout response with current clock (backend source of truth)
return {
    "message": f"Timeout called by {calling_team.name}",
    "calling_team": calling_team.name,
    "timeouts_remaining": getattr(calling_team, 'timeouts', 4),
    "home_team_timeouts": getattr(gm.home_team, 'timeouts', 4),
    "away_team_timeouts": getattr(gm.away_team, 'timeouts', 4),
    "clock": gm.game_state.get("clock", "8:00"),  # ✅ Current clock at timeout moment
    "time_remaining": gm.game_state.get("time_remaining", 480),  # Also include time_remaining
}
```

**Foul-Out Timeout (`BackEnd/models/game_manager.py` `simulate_macro_turn()`):**
```python
# ✅ CRITICAL FIX (January 2025): Save timeout state immediately when foul-out timeout is created
# This ensures timeout state persists even if user navigates away before simulate-turn saves
if self.game_id:
    db_summary = summarize_game_state(self, exclude_animations=True)
    games_collection.update_one({"_id": self.game_id}, {"$set": db_summary}, upsert=True)
```

**Persisted Timeout Data:**
- `timeout_next_play_type`: Always `"SIDE_INBOUND"` (or `"FREE_THROW"` if free throws pending)
- `timeout_offense_team_id`: Team that had possession when timeout was called
- `clock`: Current game clock
- `time_remaining`: Time remaining in seconds
- All other game state (scores, fouls, timeouts, lineups, player stats)

**Key Fix:** Foul-out timeouts now save immediately to database (same as user-initiated timeouts), preventing timeout state loss when "Sim to 4th Quarter" or other operations overwrite game state before the timeout is processed.

**When Timeout Resumes (`BackEnd/main.py` `simulate_quarter()`):**
```python
# After creating SIP turn, clear timeout state from database
games_collection.update_one(
    {"_id": game_id},
    {"$unset": {"timeout_next_play_type": "", "timeout_offense_team_id": ""}}
)
```

**Database Access by Mode:**
- **Single Game:** `games_collection` document
- **Tournament Game:** Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
  - **Game Document Fields:** `tournament_id` and `mode` are always set in `games_collection` documents (matches Franchise pattern)
  - **Implementation:** `BackEnd/api/api.py:1636-1650` - `simulate_quarter_endpoint()` adds `tournament_id` and `mode` when saving game state
- **Franchise Game:** Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)
  - **Game Document Fields:** `franchise_id` and `week` are always set in `games_collection` documents
  - **Implementation:** `BackEnd/api/franchise_routes.py:365-366` - Adds `franchise_id` and `week` when saving game state

#### URL Parameters (Navigation Only)

**Purpose:** URL parameters are used for navigation/routing, not business logic. Database is the source of truth.

**Unified Navigation Helper System (SS&S - December 2025):**

All frontend navigation now uses a unified helper (`FrontEnd/static/js/shared/timeoutNavigationHelper.js`) for consistent parameter building across all entry points.

**Helper Functions:**
- `buildGameNavigationParams()`: Builds URL parameters with consistent SS&S logic
- `getResumeFromTimeout()`: Extracts `resume_from_timeout` from URL params
- `getGameId()`: Gets game ID from URL or localStorage

**Navigation Entry Points Using Helper:**
- `set-lineup.js`: "Play Now" button, "Game Plan" button, "Box Score" button
- `game-plan.js`: `navigateToCourt()`, `navigateBack()`, `navigateToCommandCenter()`, Playbooks button navigation
  - **Navigation Source Detection:** Detects `from` URL parameter (`lineup` vs `command_center`)
  - **Button Visibility:** Shows "Back To Lineup" or "Back To Locker Room" based on navigation source
  - **Button Text:** "Play Game" (from lineup) or "Save Game Plan" (from command center)
  - **Team ID Resolution:** Uses `user_team_id` when from command center, `home_id`/`away_id` when from lineup
- `playbooks.js`: `navigateToPlayDetails()`, `handleBack()` (navigation to/from play-details and game-plan)
- `play-details.html`: `goBack()` (navigation back to playbooks)
- `box-score.js`: `setupLockerRoomButton()` (back navigation from lineup/game-plan)
- `timeoutButtonManager.js`: `showTimeoutPopup()` (timeout button navigation)
- `foulOutPopup.js`: Foul out navigation to lineup
- `gameScene.js`: Quarter end navigation

**Critical Update (January 2025):**
All navigation functions now use `TimeoutNavigationHelper` to ensure consistent parameter preservation, including `resume_from_timeout` and `clock` parameters. This fixes issues where game state was lost during navigation chains (e.g., Foul Out → Lineup → Game Plan → Playbooks → Play Details → back to court).

**Previously Manual Navigation (Now Using Helper):**
- `playbooks.js` `handleBack()`: Now uses helper for game-plan navigation (preserves timeout state)
- `playbooks.js` `navigateToPlayDetails()`: Now uses helper (preserves timeout state)
- `play-details.html` `goBack()`: Now uses helper (preserves timeout state)
- `game-plan.js` Playbooks button: Now uses helper (preserves timeout state)

**Helper Logic (SS&S Rules):**

1. **Game ID Logic:**
   - Pass `game_id` if: `quarter > 1` OR `resumeFromTimeout === true`
   - NOT for new Q1 game start

2. **Resume From Timeout Logic:**
   - Set `resume_from_timeout=true` if: `resumeFromTimeout === true` AND `gameId` exists
   - NOT for quarter breaks (Q2-Q4 without timeout)
   - NOT for new game start
   - **Supports any quarter** (Q1-Q4, OT) - removed Q1-only restriction

3. **Quarter/Period Logic:**
   - Always sets `quarter` and `period` (Q1-Q4 or OT1+)
   - Automatically calculates period label

4. **Parameter Preservation:**
   - Preserves all team info, mode, tournament/franchise IDs
   - Preserves lineup, clock, special params
   - Preserves debug flags

**URL Parameters Used:**
- `resume_from_timeout=true`: Navigation flag (convenience, not source of truth)
- `game_id`: Game identifier
- `quarter`: Quarter number
- `period`: Period label (Q1-Q4 or OT1+)
- `mode`: Game mode (single/tournament/franchise)
- `tournament_id`: Tournament identifier (if applicable)
- `franchise_id`: Franchise identifier (if applicable)
- `week`: Week number (franchise mode)
- Lineup parameters: `home_pg`, `home_sg`, etc.
- `clock`: Clock time (preserved for foul out/timeout)
  - **Retrieval Priority:** DOM element → scene.simData.clock → last processed turn → URL params → default
  - **Updated in:** `updateScoreboard()` updates `scene.simData.clock` as turns are processed

**Frontend Resilience:**
- Frontend checks database as fallback if URL parameter is missing (`bootGame.js` lines 825-841)
- This provides resilience if URL parameter is lost during navigation
- Helper ensures consistent parameter building even if some params are missing

**Critical Frontend Pattern:**
- All navigation functions read URL params directly from `window.location.search` when called
- Does NOT rely on module-level variables that might be stale (especially after async delays)
- Helper ensures `game_id` and `resume_from_timeout` are always current when navigating
- Prevents params from being lost during navigation chain: lineup → game-plan → playbooks → play-details → box-score → court
- **All navigation functions MUST use `TimeoutNavigationHelper`** - manual parameter preservation is fragile and can lose critical state (e.g., `clock` parameter)

**Foul Out Navigation Fix (January 2025):**
- Fixed issue where quarter time reset to 8 minutes after navigating through playbooks/play-details pages
- Root cause: Manual parameter preservation only preserved params if they were truthy (`if (value)`)
- Solution: All navigation functions now use `TimeoutNavigationHelper` which explicitly preserves `resume_from_timeout` and `clock` parameters
- Affected functions: `playbooks.js` `handleBack()`, `playbooks.js` `navigateToPlayDetails()`, `play-details.html` `goBack()`, `game-plan.js` Playbooks button

**Playcall Center Player Image Assignment (SS&S - January 2025):**

Player images in the Playcall Center are assigned once when returning to `court.html` from lineup/game plan screens (all timeout navigation entry points). This ensures stable, predictable behavior.

**When Images Are Set:**
- On `court.html` page load (all game entry/re-entry instances)
- Works for all timeout navigation entry points:
  - Game start / Opening Tip
  - Quarter breaks (Q2-Q4)
  - Timeout breaks (any quarter)
  - Player foul out breaks (any quarter)
  - Overtime breaks

**How Images Are Assigned:**
1. **Read Lineup from URL Params:** Lineup data is preserved by `TimeoutNavigationHelper` in URL params (`home_pg`, `home_sg`, etc. or `away_pg`, `away_sg`, etc.)
2. **Get User Team Side:** From `my_team` URL param ("home" or "away")
3. **Fetch Play Documents:** For each of the 6 offense plays, fetches play document from `/api/play/{play_name}`
4. **Determine Play Type:**
   - Checks `play.play_type` to determine if it's a Motion play or Set Play
   - Uses different logic based on play type
5. **Set Plays - Extract Intended Shooter from Skeleton:**
   - Gets successful skeleton from `play.skeletons.successful`
   - Extracts intended shooter position from final step's `pos_actions` where `action == "shoot"`
   - Uses same logic as backend `phase_resolution.py` (lines 1011-1017)
6. **Motion Plays - Analyze Steps 1-10 for Most Likely Shooter:**
   - Gets `base_loop` skeleton from `play.skeletons.base_loop`
   - Analyzes steps 1-10 (excluding step 0) to count shot opportunities for each player
   - **Inside Shots:** Player with most opportunities (handles ball at inside spot OR receives pass at inside spot)
   - **Outside/Attack Shots:** Player who handles ball at outside shot spot the most
   - If tie, chooses randomly
7. **Map Position to Player ID:** Maps shooter position to player ID from user's lineup
8. **Set Image Once:** Image path is `/static/images/players/{playerId}.png`
9. **Images Remain Static:** No mid-game changes during gameplay

**Why This Is SS&S:**
- **Single Point of Assignment:** Images set once at timeout navigation return
- **Stable During Gameplay:** Images don't change mid-game (no confusion)
- **Correct Timing:** Lineups are locked at timeout navigation points
- **Clear Data Flow:** Lineup → play skeleton → intended shooter position → player ID → image
- **Works for All Entry Points:** All use `TimeoutNavigationHelper` which preserves lineup params
- **Matches Backend Logic:** Uses same skeleton extraction logic as backend and playcall popup
- **Single Source of Truth:** Uses actual intended shooter from play skeletons, not hardcoded mapping

**Implementation:**
- Location: `FrontEnd/static/court.html` `populatePlayHeadshots()` function (lines 2484-2570)
- Fetches play documents from `/api/play/{play_name}` for each of the 6 offensive plays
- Extracts intended shooter from successful skeleton's final step (same logic as backend)
- Function is async to handle API calls
- Runs on page load (immediate execution)
- Falls back to default image if player image fails to load
- Matches backend logic in `BackEnd/engine/phase_resolution.py` (lines 1004-1020)

#### LocalStorage (Frontend State Only)

**Purpose:** LocalStorage is used for frontend convenience, not business logic.

**Stored Data:**
- `game_id`: Current game identifier (for navigation)
- `game_home`: Home team name (for matchup validation)
- `game_away`: Away team name (for matchup validation)
- `franchise_id`: Franchise identifier (if applicable)
- `franchise_week`: Current week (if applicable)

**New Game Detection:**
- Frontend clears `game_id` from localStorage when starting a new game (`gameScene.js` lines 213-220)
- Prevents stale `game_id` from being passed to backend for new games

**Note:** LocalStorage is not used for timeout state - database is the source of truth.

### Resume Flow

1. **User navigates to lineup screen** (with `resume_from_timeout=true` URL parameter)
   - Navigation uses unified helper (`timeoutNavigationHelper.js`)
   - Helper ensures `game_id` and `resume_from_timeout` are passed correctly
   - Works from any entry point (timeout button, foul out popup)

2. **User makes lineup/game plan changes** (or keeps current settings)
   - Can navigate between Lineup, Game Plan, Playbooks, and Play Details screens
   - Helper preserves all parameters during all navigation (including `resume_from_timeout` and `clock`)
   - All navigation functions use `TimeoutNavigationHelper` for consistency
   - Parameters maintained correctly through entire navigation chain

3. **User navigates back to court** (with `resume_from_timeout=true` flag in URL)
   - Navigation uses unified helper for consistency
   - Helper ensures all parameters are passed correctly

4. **Backend checks database for timeout state** (single source of truth, regardless of URL parameter)
   - Always checks database if `game_id` exists
   - Validates quarter match to prevent stale data
   - Defensively clears `resume_from_timeout` flag if no valid timeout state found

5. **Backend restores timeout state from database:**
   - `timeout_next_play_type` → Always `"SIDE_INBOUND"` (or `"FREE_THROW"`)
   - `timeout_offense_team_id` → Restores possession team
   - `clock` and `time_remaining` → Restores game clock

6. **Backend applies state to GameManager** (whether in memory or newly loaded)
   - Uses `apply_timeout_resume_state_to_gm()` helper
   - Works for both in-memory and newly-loaded games

7. **Backend creates SIP turn** with correct possession team
   - Uses `timeout_offense_team_id` to ensure correct team has possession
   - SIP transitions to HCO (defense calls play)

8. **Backend clears timeout state from database** (defensive cleanup)
   - Uses `$unset` to remove `timeout_next_play_type` and `timeout_offense_team_id`
   - Prevents stale timeout state from affecting future games

9. **Frontend auto-starts game** (bypasses pre-game buttons)
   - Game continues seamlessly

10. **Game continues** with SIP → HCO transition

### Computer Team Lineup Management (January 2025)

The computer team automatically adjusts its lineup during timeouts and at quarter breaks based on player energy levels and foul counts. This ensures the computer team makes strategic lineup decisions without user intervention.

**When Lineups Are Rebuilt:**

1. **During Timeouts:**
   - When the user calls a timeout, the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/api/api.py` `call_timeout_endpoint()` (lines 195-210)
   - Only the computer team's lineup is adjusted (user team lineup remains unchanged)
   - Uses current game state to apply energy and foul filtering rules

2. **At Quarter Breaks:**
   - At the start of each new quarter (Q2, Q3, Q4, OT), the computer team's lineup is automatically rebuilt
   - Location: `BackEnd/main.py` `simulate_quarter()` (lines 402-443, 444-468, 469-493)
   - Ensures the computer team starts each quarter with an optimal lineup based on current player conditions

**Player Eligibility Filtering:**

The system uses `is_player_eligible_for_lineup()` (`BackEnd/utils/db_utils.py`) to filter players based on:

1. **Energy (NG) Filtering:**
   - **Default:** Exclude players with NG < 80% (0.8)
   - **Q4 < 4min or OT:** Exclude players with NG < 69% (0.69)
   - Allows computer team to rest fatigued players during normal play, but be more aggressive in late-game situations

2. **Foul-Based Filtering (by Quarter):**
   - **Q1:** Exclude if player fouls > 1
   - **Q2:** Exclude if player fouls > 2
   - **Q3:** Exclude if player fouls > 3
   - **Q4:** Exclude if player fouls > 3 AND > 4 minutes remaining (no exclusion if ≤ 4 minutes remaining)
   - **Overtime:** No foul exclusion for active players
   - Prevents computer team from playing players in foul trouble early, but allows them to play through foul trouble in critical moments

3. **Fouled Out Players:**
   - Players with 5 or more fouls are always excluded (not considered active)
   - Applied regardless of quarter or time remaining

**Implementation Details:**

- **Function:** `build_lineup_from_mongo(team, game_state=None)` (`BackEnd/utils/db_utils.py`)
  - Accepts `game_state` parameter to access current quarter, time remaining, and player stats
  - Filters `available_players` using `is_player_eligible_for_lineup(player, game_state)`
  - Only applies filtering to computer teams (user team lineups are not modified)

- **Lineup Completion:** `ensure_complete_lineup(team, game_state)` (`BackEnd/utils/db_utils.py`)
  - Ensures lineup has exactly 5 players
  - Uses same eligibility filtering if additional players are needed
  - Falls back to any available players if filtered list is insufficient

- **Game State Access:**
  - `game_state["quarter"]` - Current quarter number
  - `game_state["time_remaining"]` - Time remaining in seconds
  - `player.fouls` - Player's current foul count
  - `player.NG` - Player's current energy level (Nerve/Game)

**Key Features:**
- Only affects computer team (user team lineups are never auto-adjusted)
- Respects explicit lineup choices (doesn't overwrite if lineup is explicitly provided)
- Uses current game state for accurate filtering (quarter, time remaining, player stats)
- Includes error handling and logging for debugging
- Works consistently across all game modes (single, tournament, franchise)

**Backend Locations:**
- `BackEnd/utils/db_utils.py`: `is_player_eligible_for_lineup()`, `build_lineup_from_mongo()`, `ensure_complete_lineup()`
- `BackEnd/api/api.py`: Timeout lineup rebuild logic (`call_timeout_endpoint()`)
- `BackEnd/main.py`: Quarter break lineup rebuild logic (`simulate_quarter()`)

### Unified Timeout Resume Architecture (Structural Fix - January 2025)

The timeout resume system uses a unified architecture that works consistently across all game modes and memory states.

**Core Principle:** Always use the database as the single source of truth for timeout state, regardless of whether the game is in memory or not.

**Two Helper Functions:**

1. **`restore_timeout_resume_state()`** (`BackEnd/api/api.py` lines 296-395)
   - Loads timeout state from the correct document location based on game mode
   - **Single Game**: `games_collection` document
   - **Tournament Game**: Nested in `tournaments_collection.games.{round}.{game_id}` (with fallback to `games_collection`)
   - **Franchise Game**: Nested in `franchises_collection.games.week_{week}.{game_id}` (with fallback to `games_collection`)
   - Validates that `timeout_next_play_type` exists in saved document
   - Returns saved document with timeout state, or `None` if not found

2. **`apply_timeout_resume_state_to_gm()`** (`BackEnd/api/api.py` lines 397-430)
   - Applies restored state to GameManager instance
   - Restores `timeout_next_play_type` to `gm.game_state`
   - Restores `timeout_offense_team_id` and flips possession if needed
   - Restores `clock` and `time_remaining`
   - Works for both in-memory and newly-loaded games

**Unified Flow (`BackEnd/api/api.py` `simulate_quarter_endpoint()`):**

```python
# Step 1: Always check database for timeout state if game_id exists
# Don't skip Q1 - we could be resuming from a timeout in Q1!
# The database is the source of truth - if timeout_next_play_type exists, we're resuming
if game_id:
    # Step 2: Load timeout state from database (single source of truth)
    timeout_saved_state = restore_timeout_resume_state(game_id, request, games_collection)
else:
    timeout_saved_state = None  # No game_id = brand new game

# Step 3: Validate and apply timeout state (if found)
if timeout_saved_state:
    # Validate quarter match to prevent stale data from affecting new games
    saved_quarter = timeout_saved_state.get("quarter", 0)
    timeout_next_play_type = timeout_saved_state.get("timeout_next_play_type")
    
    if timeout_next_play_type and saved_quarter == request.quarter:
        # Valid timeout state - apply it
        request.resume_from_timeout = True
        if gm is not None:
            # Step 4a: Apply to in-memory game (if exists)
    apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
        # Step 4b: If game not in memory, will apply after DB load (see Step 6)
    else:
        # Stale timeout data (quarter mismatch) - ignore it
        timeout_saved_state = None

# Step 5: If game not in memory, load from DB
if gm is None:
    # ... load game from DB ...
    # Step 6: Apply timeout state to newly loaded game (if found and valid)
    if timeout_saved_state:
        # Quarter validation already done in Step 3
        apply_timeout_resume_state_to_gm(gm, timeout_saved_state)
        request.resume_from_timeout = True

# Step 7: Continue with simulate_quarter()
simulate_quarter(gm, ..., resume_from_timeout=request.resume_from_timeout)
```

**Key Benefits:**
- **Single code path** for all modes (single, tournament, franchise)
- **Works regardless of memory state** (game in memory or not)
- **Works for all quarters** (including Q1 timeout resumes, even if game was evicted from memory)
- **Mode-specific document access** (checks correct location for each mode)
- **Less fragile** (no assumptions about memory state or quarter)
- **Consistent behavior** across all game modes
- **New game protection** (only checks timeout state if game_id exists)
- **Stale data prevention** (validates quarter match before using timeout state)

**Mode-Specific Document Access:**

The system automatically determines the correct document location:

- **Single Mode**: Checks `games_collection` only
- **Tournament Mode**: Checks nested structure first (`tournaments.games.{round}.{game_id}`), then falls back to `games_collection`
- **Franchise Mode**: Checks nested structure first (`franchises.games.week_{week}.{game_id}`), then falls back to `games_collection`

This ensures timeout state is found regardless of where the game document is stored, while maintaining the database as the single source of truth.

**Timeout State Cleanup:**

After resuming from timeout, the system clears timeout state from both memory and database:

```python
# Clear from memory
gm.game_state.pop("timeout_next_play_type", None)
gm.game_state.pop("timeout_offense_team_id", None)

# Clear from database (defensive cleanup)
games_collection.update_one(
    {"_id": game_id},
    {"$unset": {"timeout_next_play_type": "", "timeout_offense_team_id": ""}}
)
```

This prevents stale timeout state from affecting future games.

### Scoreboard Display Immediacy System

**Problem:** Scoreboard items (scores, fouls, timeouts, clock) need to display immediately when resuming from timeout, not wait for the next turn to complete.

**Solution:** Direct DOM updates with team object priority.

**Initial Value Extraction (`FrontEnd/static/js/phaser/gameScene.js`):**

All scoreboard items check team objects first (authoritative source), then fall back to game object:

```javascript
// Scores: Check team objects first (same pattern as timeouts)
const homeScoreFromData = homeTeamObj?.score ?? simData.score?.[homeTeam];
const awayScoreFromData = awayTeamObj?.score ?? simData.score?.[awayTeam];

// Fouls: Check team objects first (same pattern as timeouts)
const homeFoulsFromData = homeTeamObj?.team_fouls ?? simData.fouls?.home;
const awayFoulsFromData = awayTeamObj?.team_fouls ?? simData.fouls?.away;

// Timeouts: Check team objects first (already working)
const homeTimeoutsFromData = homeTeamObj?.timeouts ?? simData.timeouts?.home ?? simData.home_team_timeouts;
const awayTimeoutsFromData = awayTeamObj?.timeouts ?? simData.timeouts?.away ?? simData.away_team_timeouts;
```

**Immediate DOM Update (`FrontEnd/static/js/phaser/gameScene.js` `updateScoreboard()`):**

All scoreboard items use direct DOM manipulation (consistent pattern):

```javascript
// Direct DOM updates for all scoreboard items (consistent pattern)
if (homeScoreEl) homeScoreEl.textContent = liveScore[homeTeam];
if (awayScoreEl) awayScoreEl.textContent = liveScore[awayTeam];
if (homeFoulsEl) homeFoulsEl.textContent = `F: ${liveHomeFouls}`;
if (awayFoulsEl) awayFoulsEl.textContent = `F: ${liveAwayFouls}`;
if (homeTolEl) homeTolEl.textContent = `TOL: ${liveHomeTimeouts}`;
if (awayTolEl) awayTolEl.textContent = `TOL: ${liveAwayTimeouts}`;
if (clockEl) clockEl.textContent = liveClock;
if (quarterEl) quarterEl.textContent = livePeriodLabel;
```

**Initial Call (`FrontEnd/static/js/phaser/gameScene.js`):**

When resuming from timeout, `updateScoreboard()` is called with initial values:

```javascript
updateScoreboard({
    score: liveScore,
    homeFouls: liveHomeFouls,
    awayFouls: liveAwayFouls,
    homeTimeouts: liveHomeTimeouts,
    awayTimeouts: liveAwayTimeouts,
    clock: liveClock,
    quarter: liveQuarter,
    period_label: livePeriodLabel,
});
```

**Why Team Objects First?**

Turn data provides values from team objects:
- `turn.homeFouls` = `self.game.home_team.team_fouls` (from team object)
- `turn.home_team_timeouts` = `getattr(gm.home_team, 'timeouts', 5)` (from team object)
- `turn.score` = `game.score.get(team_name, 0)` (from game object, but team objects also have `score`)

Checking team objects first ensures consistency with how turn data provides these values.

### Lineup and Game Plan Pre-Population

**Lineup Pre-Population:**

When navigating to the lineup screen during a timeout, the current lineup is fetched and pre-populated:

**Backend (`BackEnd/api/api.py` `/api/game/{game_id}/lineup` endpoint):**
```python
@app.get("/api/game/{game_id}/lineup")
def get_game_lineup(game_id: str):
    # Returns current lineups for both teams
    return {
        "home_lineup": gm.home_lineup,
        "away_lineup": gm.away_lineup
    }
```

**Frontend (`FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()`):**
```javascript
// Fetch current lineup for both teams
const lineupResponse = await fetch(`/api/game/${gameId}/lineup`);
const lineupData = await lineupResponse.json();
homeLineup = lineupData.home_lineup || {};
awayLineup = lineupData.away_lineup || {};

// Add lineup params to URL
Object.entries(homeLineup).forEach(([pos, playerId]) => {
    params.set(`home_${pos.toLowerCase()}`, playerId);
});
Object.entries(awayLineup).forEach(([pos, playerId]) => {
    params.set(`away_${pos.toLowerCase()}`, playerId);
});
```

**Frontend (`FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`):**
```javascript
function restoreLineupFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const positions = ['PG', 'SG', 'SF', 'PF', 'C'];
    
    positions.forEach(pos => {
        const homeId = urlParams.get(`home_${pos.toLowerCase()}`);
        const awayId = urlParams.get(`away_${pos.toLowerCase()}`);
        if (homeId) {
            // Pre-populate home lineup slot
            document.querySelector(`#home-${pos.toLowerCase()}`).value = homeId;
        }
        if (awayId) {
            // Pre-populate away lineup slot
            document.querySelector(`#away_${pos.toLowerCase()}`).value = awayId;
        }
    });
}
```

**Game Plan Pre-Population:**

Current game plan settings are fetched and passed to the game plan screen:

**Frontend (`FrontEnd/static/js/phaser/utils/timeoutButtonManager.js` `showTimeoutPopup()`):**
```javascript
// Fetch current game plan settings for the user's team
const gpResponse = await fetch(`/api/gameplan?${gpParams.toString()}`);
gamePlanSettings = await gpResponse.json();

// Add game plan settings to URL
if (gamePlanSettings) {
    params.set('game_plan_settings', JSON.stringify(gamePlanSettings));
}
```

**Frontend (`FrontEnd/static/game-plan.js` `loadSettings()`):**
```javascript
function loadSettings() {
    const urlParams = new URLSearchParams(window.location.search);
    const gamePlanSettingsParam = urlParams.get('game_plan_settings');
    
    if (gamePlanSettingsParam) {
        // Parse and apply game plan settings from URL
        const settings = JSON.parse(gamePlanSettingsParam);
        // Apply settings to form
    }
}
```

### Timeout Button Functionality

**Feature Flag:**

The timeout button is controlled by a feature flag for easy enabling/disabling:

**Location:** `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`

```javascript
const ENABLE_TIMEOUT_BUTTON = true; // Feature flag for modularity
```

**Button State:**

- **Live:** Button is enabled and clickable (during 2.5-second pause window)
- **Dead:** Button is disabled with reduced opacity (all other times)

**Button Initialization:**

```javascript
function initTimeoutButton() {
    if (!ENABLE_TIMEOUT_BUTTON) {
        // Hide button if feature is disabled
        return;
    }
    
    const button = document.getElementById('timeout-btn');
    if (!button) return;
    
    // Set initial state (dead)
    updateTimeoutButtonState(false, 'Initial state');
    
    // Attach click listener
    button.addEventListener('click', handleTimeoutButtonClick);
}
```

**2.5-Second Pause Window:**

The timeout button is live during a mandatory 2.5-second pause at the start of SIP and BIP turns:

**Location:** `FrontEnd/static/js/phaser/animation/turnAnimation.js`

```javascript
// In runSideInboundSetup() and runInboundSetup()
if (ENABLE_TIMEOUT_BUTTON && isTimeoutEligible) {
    // Start 2.5-second pause (button becomes live immediately)
    await startTimeoutPause(scene);
    
    // Position players (happens in parallel with pause)
    await Promise.all(playerPromises);
    
    // Mark players positioned (if pause already complete, button stays live)
    markPlayersPositioned();
    
    // Mark inbound pass started (button becomes dead, hide progress bar)
    markInboundPassStarted();
}
```

**Progress Bar:**

A visual countdown progress bar appears during the 2.5-second pause:

- **Appearance:** Orange fill with green border
- **Animation:** Starts full width, reduces proportionally to time remaining
- **Visibility:** Only visible when button is live

**Timeout Eligibility:**

The button is live for all SIP and BIP turns if:
- The turn is a SIP or BIP turn
- The team has timeouts remaining (checked via `/api/call-timeout` endpoint)

**Timeout Button Click Handler:**

```javascript
async function handleTimeoutButtonClick() {
    // Get game context from scene
    const gameId = scene.gameId || scene.simData?.game_id;
    const myTeamSide = scene.userTeamSide || urlParams.get('my_team');
    
    // Call timeout API
    const response = await fetch('/api/call-timeout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            game_id: gameId,
            calling_team: myTeamSide, // 'home' or 'away'
        }),
    });
    
    // Navigate to lineup screen
    await showTimeoutPopup(result, gameId, scene);
}
```

**Animation Freezing:**

When timeout button is pressed, all animations are immediately paused:

**Location:** `FrontEnd/static/js/phaser/animation/AnimationEngine.js`

```javascript
async handleTimeout(turnData, context) {
    // Pause all tweens immediately when timeout is called
    if (this.scene.tweens) {
        this.scene.tweens.pauseAll();
    }
    // Set flag to stop the main animation loop
    this.scene.timeoutCalled = true;
    
    // Show timeout popup and navigate to lineup screen
    await showTimeoutPopup(timeoutResult, gameId, this.scene);
}
```

**Location:** `FrontEnd/static/js/phaser/animation/animateGameTurns.js`

```javascript
if (turn.result_type === "TIMEOUT") {
    turn.index = i;
    await animationRouter.processTurn(turn);
    console.log('⏸️ TIMEOUT: Stopping animation loop');
    break; // Exit the loop - don't process any more turns
}
```

### Comparison: Timeout vs Quarter Break vs Foul Out

**Similarities:**

All three flows use the same core systems:
- **Data Persistence:** Same `summarize_game_state()` and database save/load pattern
- **Resume Flow:** Same `resume_from_timeout` / `resume_from_foul_out` flag pattern
- **Auto-Start:** Same pre-game button bypass logic
- **State Restoration:** Same game state restoration from database
- **Lineup Pre-Population:** Same lineup fetching and URL parameter passing

**Differences:**

| Feature | Timeout | Quarter Break | Foul Out |
|---------|---------|--------------|----------|
| **Turn Type** | `TIMEOUT` | `BASELINE_INBOUND` | `TIMEOUT` (with `timeout_reason="FOUL_OUT"`) |
| **Next Turn** | SIP (default) | BIP (quarter start) | SIP (default) |
| **Timeout Count** | Reduced by 1 | Not affected | Not affected |
| **User Initiation** | User presses button | Automatic (quarter ends) | Automatic (player fouls out) |
| **Animation Freeze** | Yes (immediate pause) | No (seamless transition) | Yes (immediate pause) |
| **Pre-Game Buttons** | Hidden (auto-start) | Hidden (auto-start) | Hidden (auto-start) |
| **Initial Turn Creation** | In `simulate_quarter()` | In `simulate_quarter()` | In `simulate_quarter()` |
| **Offensive State Reset** | Yes (reset to HCO for SIP) | No (preserved) | Yes (reset to HCO for SIP) |

**Key Implementation Details:**

1. **Timeout Resume:**
   - Clears `gm.turns` before creating SIP turn (prevents old turns from being returned)
   - Resets `offensive_state` to `"HCO"` (prevents FCP/HCT from carrying over)
   - Creates SIP turn directly in `simulate_quarter()` (same pattern as quarter breaks create BIP turns)

2. **Quarter Break:**
   - Creates BIP turn directly in `simulate_quarter()` (quarter start logic)
   - Preserves `offensive_state` (defensive pressure can carry over to quarter start)
   - No timeout count reduction

3. **Foul Out:**
   - Same as timeout (creates `TIMEOUT` turn with `timeout_reason="FOUL_OUT"`)
   - No timeout count reduction
   - Includes `foul_out_player` data in timeout turn payload

### Key Files

**Backend:**
- `BackEnd/models/turn_manager.py` `setup_timeout_turn()`: Creates timeout turn payload
- `BackEnd/models/game_manager.py` `determine_next_turn()`: Routes TIMEOUT → next turn
- `BackEnd/api/api.py` `call_timeout_endpoint()`: Handles user-initiated timeouts
- `BackEnd/api/api.py` `simulate_quarter_endpoint()`: Handles timeout resume flow
- `BackEnd/main.py` `simulate_quarter()`: Creates initial turn after timeout resume
- `BackEnd/utils/shared.py` `summarize_game_state()`: Saves game state to database

**Frontend:**
- `FrontEnd/static/js/phaser/utils/timeoutButtonManager.js`: Timeout button logic and state management
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` `handleTimeout()`: Handles timeout turn
- `FrontEnd/static/js/phaser/animation/animateGameTurns.js`: Stops animation loop on timeout
- `FrontEnd/static/js/phaser/gameScene.js`: Scoreboard immediate update logic
- `FrontEnd/static/js/phaser/bootGame.js`: Auto-start logic for timeout resume
- `FrontEnd/static/set-lineup.js` `restoreLineupFromUrl()`: Pre-populates lineup from URL
- `FrontEnd/static/game-plan.js` `loadSettings()`: Pre-populates game plan from URL
- `FrontEnd/static/court.html`: Timeout button and progress bar HTML/CSS

**Tests:**
- `tests/test_timeout_functionality.py`: Comprehensive tests for timeout system

---

### Persistence Layer

**Current Implementation:**
- **UI State:** localStorage (`gob_playbooks` key) - for UI state persistence
- **Playbook Settings:** ✅ Database storage via `POST /api/playbooks` - saves percentages to team documents

**Game Initialization and Playbook Settings Persistence:**
- When a game is initialized via `/api/init-game`, the game document is created with `mode`, `tournament_id` (for tournament mode), or `franchise_id` (for franchise mode) fields
- These fields are set on the game document at initialization time (not just at game completion) to ensure playbook settings can be loaded during active gameplay
- **Update (January 2025):** `tournament_id` and `mode` are now also set during `simulate_quarter_endpoint()` saves, ensuring they are always present in game documents regardless of game creation path (matches Franchise mode pattern where `franchise_id` and `week` are always set during saves)
- **Frontend:** `set-lineup.js` passes `mode`, `tournament_id`, and `franchise_id` (when available) to `/api/init-game`
- **Backend:** `/api/init-game` stores these fields on the game document:
  - `mode`: "single", "tournament", or "franchise"
  - `tournament_id`: Set if `mode === "tournament"` (string format)
  - `franchise_id`: Set if `mode === "franchise"` (string format)
- **During Gameplay:** `_load_playbook_settings()` in `turn_manager.py` uses these fields to:
  1. Check the game document for `mode` and `tournament_id`/`franchise_id`
  2. Load the appropriate tournament/franchise document
  3. Retrieve `playbook_settings` from `teams.{team_id}.playbook_settings` (or `franchise_teams.{team_id}.playbook_settings` for franchise mode)
- This ensures that playbook settings submitted from the Command Center (Tournament or Franchise) persist and are used when playing games in those modes

**API Endpoints:**
- `GET /api/playbooks` - Loads plays from database (organized by type and focus)
  - Resolves team names to team_id automatically
  - Returns plays organized by motion, set_play_inside, set_play_attack, set_play_outside
  - **Single Game Mode:** Handles both string and ObjectId formats for game_id
    - First attempts lookup with game_id as string
    - Falls back to ObjectId conversion if string lookup fails
    - This supports both UUID strings and MongoDB ObjectId formats
  - **Tournament/Franchise Mode:** Uses ObjectId for document lookup
  - Ensures team objects exist before loading plays (creates with defaults if missing)
  - Reloads document after ensuring team objects to get updated data
- `POST /api/playbooks` - Saves playbook settings (percentages) to `teams.{team_id}.playbook_settings` (or `franchise_teams.{team_id}.playbook_settings` for franchise mode)
  - Request body: `{ mode, team_id, game_id/tournament_id/franchise_id, playbook_settings }`
  - Resolves team names to team_id automatically for all modes (single, tournament, franchise)
  - **Franchise Mode:** Uses the same team name resolution logic as GET endpoint:
    1. Direct lookup in document's `franchise_teams` collection
    2. Iterating through `franchise_teams` to match by name
    3. Looking up in `teams` collection by name and matching back to document
  - Ensures team objects exist before saving
  - Validates required parameters based on mode
  - **Single Game Mode:** Handles both string and ObjectId formats for game_id
    - First attempts update with game_id as string
    - Falls back to ObjectId conversion if string update fails (matched_count == 0)
    - This supports both UUID strings and MongoDB ObjectId formats
  - **Tournament/Franchise Mode:** Uses ObjectId for document lookup
  - Includes detailed logging for team_id resolution and document operations

**Storage Structure:**
```javascript
teams.{team_id}.playbook_settings = {
  "motion": {
    "3-2 Motion": 20,
    "4-1 Motion": 30,
    "5-0 Motion": 50
  },
  "set_play_inside": {
    "Base Post Play": 100
  },
  "set_play_attack": {...},
  "set_play_outside": {...},
  "zone_defense": {
    "2-3 Zone": 40,
    "3-2 Zone": 35,
    "1-3-1 Zone": 25
  },
  "man_defense": {
    "Man": 100
  },
  "slot_assignments": {
    "1": { "section": "motion", "playId": "motion-1", "dropdown": "Inside" },
    "2": { "section": "set-play-inside", "playId": "set-inside-1" },
    // ... other slot assignments
  },
  "motion_dropdowns": {
    "motion-1": "Inside",
    "motion-2": "Attack",
    // ... other motion dropdown selections
  },
  "position_filters": {
    "standard": [],
    "PG": ["68f919f9065f78d452557809", "68f919f9065f78d452557810", ...],  // play_id (ObjectId strings)
    "SG": ["68f919f9065f78d452557811", ...],
    "SF": [...],
    "PF": [...],
    "C": [...]
  }
}
```

**Persistence Interface (`PlaybooksPersistence` class):**
- `load()` - Loads UI state from localStorage
- `save(data)` - Saves UI state to localStorage
- `savePlaybookSettings()` - Saves playbook percentages to database via API

**Data Serialization:**
```javascript
{
  sections: {
    motion: { [playId]: { percentage: number, slot: number | null } },
    'set-play-inside': { [playId]: { percentage: number, slot: number | null } },
    // ... other sections
  },
  slotAssignments: {
    [slotNumber]: { section: string, playId: string, dropdown?: string }
  },
  motionDropdowns: { [playId]: 'Inside' | 'Attack' | 'Outside' }
}
```

### Motion Offense Dropdowns

**Behavior:**
- Each Motion row includes dropdown with options: **- / Inside / Attack / Outside**
- **Default State:** Dropdown defaults to **"-"** (explicit unselected state)
  - Users must explicitly select "Inside", "Attack", or "Outside"
  - Makes it clear when a selection has been made vs. default state
- **Persistence:** Selection persists when changed (stored in `motionDropdowns` state)
  - Dropdown value is updated immediately in UI when changed
  - State is saved to localStorage and synced to database
- **Default Preservation:** When loading persisted state, defaults are merged with saved values (not overwritten)
  - Ensures new Motion plays always default to "-" even after loading persisted state
  - Saved user selections take precedence, but defaults remain for plays without saved values
  - All motion plays are initialized with "-" if no value exists
- **Display:** Dropdown shows current selection immediately when changed

**Integration with Slot Assignment:**
- Motion slot assignments are keyed by dropdown variant
- Example: "5-0 Motion (Inside)" and "5-0 Motion (Attack)" are separate assignable targets
- Slot assignment key format: `motion:${playId}:${dropdown}`

**Integration with Playcall Center:**
- Slot assignments (1-6) determine the order of plays in the Playcall Center
- Slot 1 = First play displayed in Playcall Center (shown by default on page load)
- Slot 2 = Second play, etc.
- Navigation buttons respect slot order:
  - **Up button (▲)**: Navigates to previous slot (1→2→3→4→5→6, wraps to 6)
  - **Down button (▼)**: Navigates to next slot (6→5→4→3→2→1, wraps to 1)
- Plays are automatically reordered when slot assignments are loaded from playbooks
- Unassigned plays appear at the end (after slots 1-6)
- **Loading Implementation:**
  - `loadAndApplySlotAssignments()` function in `court.html` loads slot assignments on page load
  - Fetches from `GET /api/playbooks` endpoint with mode, team_id, and mode-specific ID
  - **Team ID Resolution:** Checks multiple URL parameters in order:
    1. `team_id` (primary)
    2. `user_team_id` (used by Game Plan page)
    3. `home_id` (fallback)
    4. `away_id` (fallback)
  - Maps frontend playIds (like "motion-1") to play names from API response
  - Matches plays by name and focus (for Motion plays, also matches dropdown variant)
  - Reorders DOM elements based on slot assignments (1-6)
  - Dispatches `playcall-center-reordered` event when complete
  - Navigation code listens for event and updates play options/show first play
  - **Event-Based Synchronization:** Prevents race conditions where navigation might show wrong play before reordering completes

### Priority Slots 1-6 (Offense Only)

**Location:** Right column of every Motion and Set Play row  
**Alignment:** Single vertical column of 6 slot controls (aligned across all rows)

**Rules:**
- Each slot number (1-6) can be assigned only **once** across ALL offense play call rows
- If Slot 1 is assigned to one row and user assigns Slot 1 to another row, it auto-unassigns from first and assigns to second
- **Motion Complication:** Slot assignments must support dropdown variants
  - Users can assign Slot 1 to "Motion (Inside)", Slot 2 to "Motion (Attack)", Slot 3 to "Motion (Outside)"
  - Motion slot assignments tracked as distinct targets: `(motionRowId + selectedDropdownFocus)`

**Slot UI/UX:**
- Each slot rendered as small toggle "pill/chip" control
- **When assigned:**
  - **Set Plays:** Normal selected styling (gold background)
  - **Motion:** Selected styling + small badge indicating I/A/O (derived from assigned dropdown variant)
- **Badge Colors:**
  - **Inside (I):** Blue (`#4a90e2`)
  - **Attack (A):** Orange (`#ff7a00`)
  - **Outside (O):** Green (`#4caf50`)
- All slot controls aligned vertically for consistent column reading

**Slot Persistence:**
- Slots remain assigned when dropdown changes
- Example: If Slot 1 is assigned to "5-0 Motion (Inside)" and user changes dropdown to "Attack", checkbox stays highlighted with "I" badge (showing it's still assigned to Inside variant)
- Badge shows the **assigned** dropdown variant, not the current dropdown selection

### Position Filter Buttons ✅ **IMPLEMENTED** (January 2025)

**Location:** Header row, horizontally centered below page title  
**Buttons:** "Standard", "PG", "SG", "SF", "PF", "C"  
**Purpose:** Filter offense plays by position to help users organize their playbook

**Button Styling:**
- **Unpressed:** Silver border, clear fill, bold silver copy
- **Selected:** Gold border, dark black fill, bold gold copy
- Same size and shape as the "Back" button

**Selection Rules:**
- Maximum **2 buttons** can be selected at once
- If a third button is selected, the oldest selection is automatically unselected (FIFO - First In, First Out)
- Users can deselect a button by clicking it again

**Filtering Logic:**
- **Initial State:** No buttons selected - **all offense plays are hidden**
- **Single Button Selected:** Shows only plays in that position's array
  - Example: "Standard" selected → shows only Standard plays
  - Example: "PF" selected → shows only PF plays
- **Multiple Buttons Selected:** Uses **union (OR) logic** - play must be in **ANY** selected position array
  - Example: "Standard" and "PF" selected → shows plays in Standard array OR PF array (both sets combined)
  - Example: "PF" and "SG" selected → shows plays in PF array OR SG array (both sets combined)
  - Plays are added cumulatively as buttons are selected
  - Plays are removed when their position button is unselected
- **Defense Plays:** Not affected by position filters (always visible)

**Storage:**
- Position filters are stored per team in `playbook_settings.position_filters`
- Structure:
  ```javascript
  position_filters: {
    "standard": [],  // Empty = show all plays when selected
    "PG": [play_id_1, play_id_2, ...],  // Array of play_id (ObjectId strings)
    "SG": [play_id_3, play_id_4, ...],
    "SF": [play_id_5, play_id_6, ...],
    "PF": [play_id_7, play_id_8, ...],
    "C": [play_id_9, play_id_10, ...]
  }
  ```
- **Play ID Format:** Uses database `play_id` (ObjectId string) for consistency and stability
  - Matches the pattern used for other database object references throughout the game engine
  - Stored as strings in the database (e.g., `"68f919f9065f78d452557809"`)
  - Frontend displays play names, but filtering uses `play_id` for matching

**API Integration:**
- `GET /api/playbooks` returns `position_filters` in the response
- `POST /api/playbooks` saves `position_filters` when included in `playbook_settings`
- Default initialization: All position arrays start empty (can be customized later)

**Initialization and Backward Compatibility:**
- When team objects are created (Single Game, Tournament, Franchise modes), `playbook_settings` is initialized with `position_filters` populated with "Standard" and "PF" plays
- For existing team objects that don't have `playbook_settings` or have a falsy value (None, empty dict), the system automatically:
  1. Checks for missing/falsy `playbook_settings` in `get_playbooks()` endpoint
  2. Creates and saves `playbook_settings` with populated `position_filters` if missing
  3. Reloads the document to ensure fresh data is returned
- This defensive check ensures backward compatibility with team objects created before `position_filters` were introduced
- The check uses `not team_obj.get("playbook_settings")` to handle both missing keys and falsy values (None, empty dict)

**Affected Sections:**
- Position filtering applies to all offense play sections:
  - Motion Offense
  - Set Play Inside Offense
  - Set Play Attack Offense
  - Set Play Outside Offense
- Defense sections are not filtered (always visible)

**Implementation:**
- Frontend: `FrontEnd/static/playbooks.js` - `handlePositionFilterClick()`, `shouldShowPlay()`, `renderSection()`
- Backend: `BackEnd/api/gameplan_routes.py` - `initialize_playbook_settings()`, `get_playbooks()`, `save_playbooks()`

### Assigned Plays 1-6 List

**Location:** Bottom of Offense column  
**Structure:** Simple 6-row list (rows labeled 1-6)

**Display Format:**
- Each row shows: `"Slot Number: Play Name (Focus)"`
- **Motion examples:**
  - `"1: 5-0 Motion (Inside)"`
  - `"2: 4-1 Motion (Outside)"`
- **Set Play examples:**
  - `"3: Base Post Play (Inside)"`
  - `"4: Pick & Roll (Lower Wing) (Attack)"`
- **Unassigned:** Shows `"Unassigned"` in muted/italic text

**Behavior:**
- Updates live as slot assignments change
- Reflects current state of all 6 slot assignments
- Format: `"Play Name (Focus)"` where Focus is:
  - For Motion: The dropdown variant (Inside/Attack/Outside)
  - For Set Plays: The section focus (Inside/Attack/Outside)

### State Model

**Clean state shape supporting:**
- Six independent section totals + validation state
- Slot uniqueness across offense (enforced via `slotAssignments` object)
- Motion slot assignment keyed by dropdown focus
- Easy serialization/deserialization to save payload

**State Structure (`PlaybooksState` class):**
```javascript
{
  sections: {
    [sectionKey]: {
      [playId]: {
        percentage: number,
        slot: number | null  // For set plays only
      }
    }
  },
  slotAssignments: {
    [slotNumber]: {
      section: string,
      playId: string,
      dropdown?: string  // For motion plays
    }
  },
  motionDropdowns: {
    [playId]: 'Inside' | 'Attack' | 'Outside'
  }
}
```

### Visual and Interaction Quality

**Typography Hierarchy:**
- Page title: 2.5rem, gold color (`#FFD700`)
- Section titles: 1.125rem, white
- Row labels: 0.9375rem, white
- Helper text: 0.875rem, muted white

**Input Alignment:**
- Labels left-aligned
- Inputs right-aligned
- Totals consistent positioning

**Error Handling:**
- Inline section-level error messages (avoid global error dumps)
- Warning states with subtle color changes
- Fast and predictable editing experience (no jank)

**Accessibility:**
- Keyboard navigation support
- Focus states on all interactive elements
- Readable contrast ratios
- ARIA labels where appropriate

### Key Files

**Frontend:**
- `FrontEnd/static/playbooks.html` - Main page structure
- `FrontEnd/static/playbooks.css` - Styling and layout
- `FrontEnd/static/playbooks.js` - State management, validation, and UI logic

**Key Classes:**
- `PlaybooksState` - State management and validation
- `PlaybooksPersistence` - Load/save interface (localStorage + API ready)
- `PlaybooksUI` - UI controller and rendering logic

### Implementation Details

**Backend Files:**
- `BackEnd/api/gameplan_routes.py` - Contains `/api/playbooks` endpoint
- `BackEnd/api/api.py` - Router registration

**Frontend Files:**
- `FrontEnd/static/playbooks.html` - Page structure
- `FrontEnd/static/playbooks.css` - Styling
- `FrontEnd/static/playbooks.js` - State management and API integration

**Key Features:**
- ✅ Loads plays dynamically from database based on game mode
- ✅ Supports 6 motion offense slots (fills with "To Be Added" if needed)
- ✅ Supports 2 slots per Set Play focus (fills with "To Be Added" if needed)
- ✅ "To Be Added" placeholders are disabled (no percentage input, no slot assignment)
- ✅ Mode-aware: Works with single game, tournament, and franchise modes
- ✅ Back button with smart navigation to return to previous page
- ✅ Save functionality with error handling and validation

**Navigation Entry Points:**
- **Game Plan Screen:** Playbooks button links to playbooks.html with mode, team_id, and mode-specific ID
  - **Team ID Resolution (Multiple Fallbacks):**
    1. Primary: `teamId` (derived from `myTeamSide` - `homeId` or `awayId`)
    2. Fallback 1: `userTeamIdParam` (from URL parameter)
    3. Fallback 2: `homeId` or `awayId` (direct from URL parameters)
  - **Additional Parameters:**
    - Also passes `home_id` and `away_id` as fallbacks in URL for playbooks.js to use
    - Falls back to localStorage for `game_id` if not in URL (single mode)
    - Includes debug logging (`🔍 [GAME-PLAN] Navigating to playbooks with params:`) for troubleshooting
  - **Location:** `FrontEnd/static/game-plan.js` - `btnPlaybooks` click handler
- **Tournament Command Center:** Playbooks button links to playbooks.html with tournament_id and team_id
  - **Location:** `FrontEnd/static/tournament.js` - `playbooks-tournament` button handler
- **Franchise Command Center:** Playbooks button links to playbooks.html with franchise_id and team_id
  - **Location:** `FrontEnd/static/franchise-command-center.js` - `playbooks-franchise` button handler

### Game Engine Integration

**✅ Implemented:**
- Playbook percentages are used for weighted random selection when choosing plays
- Motion plays: Uses percentages from `playbook_settings.motion`
- Set plays: Uses percentages from `playbook_settings.set_play_{focus}` (inside/attack/outside)
- Zone defense: Uses percentages from `playbook_settings.zone_defense`
- "To Be Added" plays are excluded from selection
- CPU teams use equal weights (playbook settings only apply to user teams)
- Falls back to equal weights if no playbook settings exist

**Selection Logic:**
- When `set_playcalls()` is called, it loads playbook settings from the team document
- Uses `weighted_random_from_dict()` to select plays based on percentages
- Man defense: Currently only one option ("Man"), so no weighting needed

### Future Enhancements

**Pending:**
- Link priority slots (1-6) to playcall selection order
- Support custom plays (user-created plays per team)
- Motion dropdown focus integration (currently only used for Playcall Center display)

---

**Note:** Sim Playcalling System documentation has been moved to:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Sim_Playcalling_System.md`

---

### 4. `handleTurnover()`
**Registered for:** `TURNOVER`  
**Location:** `AnimationEngine.js` line 369  
**What it does:**
- Routes to `turnoverAdapter.js` `handleTurnover()` function
- Handles turnover animations and possession changes

**Key Features:**
- Delegates to specialized turnover handler
- Handles possession flips

---

### 5. `handleFastBreak()`
**Registered for:** `FAST_BREAK`  
**Location:** `AnimationEngine.js` line 381  
**What it does:**
- Updates active player display (ball handler and defender)
- Routes to `runFastBreakSequence()` for fast break animations
- Sets `scene._previousTurnWasShot = true` if turn is a shot (MAKE/MISS)

**Key Features:**
- Active player display update
- Fast break sequence execution
- Shot flag setting for next turn

---

### 6. `handlePutback()`
**Registered for:** `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`  
**Location:** `AnimationEngine.js` line 410  
**What it does:**
- Routes to `handleOrebTurn()` function (from `animateGameTurns.js`)
- Handles putback shot attempts and OREB kickout passes

**Key Features:**
- Delegates to specialized OREB handler
- Handles PUTBACK_MAKE, PUTBACK_MISS, and OREB_KICKOUT
- Includes shot animations, rebounds, and inbound setups

---

### 7. `handleOpeningTip()`
**Registered for:** `OPENING_TIP`  
**Location:** `AnimationEngine.js` line 429  
**What it does:**
- Validates opening tip timing (Q1 start or OT start only)
- Routes to `runOpeningTipSequence()` for opening tip animations
- Transitions state machine to `HalfCourt` after completion

**Key Features:**
- Timing validation (prevents mid-game opening tips)
- Opening tip sequence execution
- State machine transition

---

### 8. `handleDefensiveStop()`
**Registered for:** `DEFENSIVE_STOP`  
**Location:** `AnimationEngine.js` line 474  
**What it does:**
- Checks if Fast Break defensive stop (routes to `runFastBreakSequence()`) or standard defensive stop (routes to `runDefensiveStopTransition()`)
- Appends text scroll with defensive stop message

**Key Features:**
- Fast Break vs standard defensive stop routing
- Defensive stop transition animations
- Text scroll append

---

### 9. `handleSteal()`
**Registered for:** `STEAL`  
**Location:** `AnimationEngine.js` line 509  
**What it does:**
- Checks FastBreak state (skips if in FastBreak)
- Executes pass animation from ball handler to stealer using `runPass()`
- Emits `possessionChange` event after pass completes

**Key Features:**
- FastBreak state check
- Steal pass animation
- Possession change emission

---

### 10. `handleShotAttempt()`
**Registered for:** `SHOT_ATTEMPT` (detected via `isShotAttempt()`)  
**Location:** `AnimationEngine.js` line 565  
**What it does:**
- Routes to `ShotAnimationSystem.processShot()` (if available) or falls back to `playTurnAnimation()`
- Handles HCO and FCP/HCT shot attempts (MAKE/MISS)

**Key Features:**
- Shot animation system integration
- Player movement, ball flight, and rebound handling
- Fallback to legacy `playTurnAnimation()`

**Used by:**
- HCO shots (MAKE/MISS)
- FCP/HCT shots (MAKE/MISS) - when routed through AnimationRouter

---

### 11. `handleRebound()`
**Registered for:** `REBOUND` (detected via `isRebound()`)  
**Location:** `AnimationEngine.js` line 599  
**What it does:**
- Routes to `ReboundAnimationSystem.processRebound()` (if available) or falls back to `playTurnAnimation()`
- Handles rebound animations

**Key Features:**
- Rebound animation system integration
- Fallback to legacy `playTurnAnimation()`

**Status:** Handler exists but `ReboundAnimationSystem` may not be fully implemented yet

---

### 12. `handlePass()`
**Registered for:** `PASS` (detected via `isPass()`)  
**Location:** `AnimationEngine.js` line 629  
**What it does:**
- Routes to `PassAnimationSystem.processPass()` (if available) or falls back to `playTurnAnimation()`
- Handles pass animations

**Key Features:**
- Pass animation system integration
- Fallback to legacy `playTurnAnimation()`

**Status:** Handler exists but `PassAnimationSystem` may not be fully implemented yet

---

### 13. `handleDefault()`
**Registered for:** `HCO`, `DEFAULT`  
**Location:** `AnimationEngine.js` line 653  
**What it does:**
- Routes to `playTurnAnimation()` for HCO setup turns and other default animations
- Used as fallback for turn types without specific handlers

**Key Features:**
- Default handler for unhandled turn types
- HCO setup turn execution
- Delegates to `playTurnAnimation()`

**Used by:**
- HCO setup turns (`result_type === "HCO"` but not MAKE/MISS)
- FCP/HCT fouls (with animations)
- Any turn type without a specific handler

---

---

---

---

## Key Files

- `FrontEnd/static/js/phaser/animation/AnimationEngine.js` - All handler implementations
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js` - Handler invocation
- `FrontEnd/static/js/phaser/animation/ShotAnimationSystem.js` - Shot handler system
- `FrontEnd/static/js/phaser/animation/turnAnimation.js` - `playTurnAnimation()` (used by `handleDefault()`)

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

### Distance-Based Animation Speed System ✅ **COMPLETE** (January 2025)

**Status:** Fully implemented and operational

The animation system uses a unified distance-based duration calculation that ensures consistent speeds across all animations and respects game speed settings (Slow/Normal/Fast).

**Architecture:**

#### Core Functions

- **`getPlayerDuration(sprite, targetX, targetY, isTransition = false)`** (`turnAnimation.js`)
  - Calculates player movement duration based on distance from current sprite position to target
  - Uses `getPlayerSpeed()` which checks `window.__GAME_SPEED` for dynamic speed settings
  - Formula: `duration = (distance / speed) * 1000` (converts to milliseconds)
  - **Note**: The `isTransition` parameter is accepted but currently unused (distance fully determines time, no upper cap)
  - Minimum duration: 50ms (to avoid zero-length tweens)
  - Default speed: 450 pixels/second (Normal preset)

- **`getBallDuration(ballSprite, targetX, targetY)`** (`ballTween.js`)
  - Calculates ball movement duration based on distance from current position to target
  - Uses `getBallSpeed()` which checks `window.__GAME_SPEED` for dynamic speed settings
  - Formula: `duration = (distance / speed) * 1000` (converts to milliseconds)
  - Default speed: 450 pixels/second (Normal preset)
  - Clamped between 50ms (minimum) and 1000ms (maximum)

#### Game Speed Integration

**Speed Presets** (`gameSpeedManager.js`):
- **Slow**: 350 pixels/second
- **Normal**: 450 pixels/second (default)
- **Fast**: 550 pixels/second

**How It Works**:
1. User selects speed via UI buttons (Slow/Normal/Fast)
2. `gameSpeedManager.setGameSpeed()` updates `window.__GAME_SPEED`
3. `getPlayerSpeed()` and `getBallSpeed()` check `window.__GAME_SPEED` before falling back to defaults
4. All duration calculations automatically use the current speed setting

#### Where It's Used

**Player Animations**:
- ✅ HCO turn animations (`ShotAnimationSystem.animatePlayerMovement()`)
- ✅ Transition animations (IP→HCO, DREB→HCO)
- ✅ Inbound pass setup animations
- ✅ Opening tip player movements
- ✅ Free throw player movements
- ✅ Fast break player movements
- ✅ **Setup tweens** (`runSetupTween()` in `turnAnimation.js` and `ShotAnimationSystem.js`) - Fixed January 2025
- ✅ **Get-back players** during shot attempts - Fixed January 2025
  - Stop on MISS when rebound is secured
  - Stop on MAKE after rim hold (1s HCO, 2s fast break)
- ✅ **Rebound positioning animations** - Fixed January 2025
  - Rebounder to ball bounce
  - Non-rebounders collapse (stop when rebounder secures ball)
  - Player to rebound spot

**Ball Animations**:
- ✅ Pass animations (`passDetection.js`)
- ✅ Opening tip ball movements
- ✅ All ball tweens via `getBallDuration()`

#### Benefits

- ✅ **Consistent Speeds**: All animations use the same distance-based calculation
- ✅ **Game Speed Support**: Slow/Normal/Fast buttons work across all animations
- ✅ **Smooth Transitions**: Distance-based calculation ensures smooth movement regardless of timestamp gaps
- ✅ **No More "Stuck in Mud"**: Replaced slow timestamp-based calculations with responsive distance-based ones
- ✅ **Unified System**: Single source of truth for duration calculations

#### Migration History

**Before (Bug 3 - Fixed January 2025)**:
- `ShotAnimationSystem` used timestamp-based calculation: `(nextStep.timestamp - step.timestamp) * 3`
- Hardcoded speeds in `passDetection.js` and `openingTip.js`
- Game speed buttons had no effect
- Inconsistent speeds between HCO and transitions

**After (Fixed January 2025)**:
- All animations use `getPlayerDuration()` or `getBallDuration()`
- Game speed settings respected everywhere
- Consistent speeds across all animation types
- **Recent Fixes (January 2025)**:
  - `runSetupTween()` now uses distance-based timing (was hardcoded 1000ms)
  - Get-back players use distance-based timing with early termination
  - Rebound animations use distance-based timing and stop when rebounder secures ball
  - BIP → HCO transitions are smooth and consistent

**See:**
- `docs/PHASE_2.5_BUG_LIST.md` - Bug 3 fix details
- `docs/To Do/distance_based_animation_audit.md` - Comprehensive audit and implementation details
- `docs/To Do/animation_speed_edge_cases.md` - Previous edge cases (now resolved)

---

### Shot Resolution Process ✅ **COMPLETE** (January 2025)

**Status:** Fully unified and operational

All made shots (HCO, Fast Break, Putback, Free Throw) now use a consistent resolution process that ensures the ball lands and holds at the correct rim coordinates.

#### Rim Coordinates

**Constants** (`courtConstants.js`):
- **Home Rim**: `{ x: 91, y: 25 }` (grid coordinates)
- **Away Rim**: `{ x: 9, y: 25 }` (grid coordinates)

**Rule**: Teams shoot at their own basket
- Home team shoots at home rim (x: 91)
- Away team shoots at away rim (x: 9)

#### Resolution Process

**For All Made Shots** (HCO, Fast Break, Putback, Free Throw):

1. **Ball Animation to Rim**
   - Ball animates from shooter to rim coordinates using `animateBallFlight()` or `animateShotToRim()`
   - Animation completes when ball reaches rim position
   - Ball remains visible at rim coordinates

2. **Rim Hold (1 Second)**
   - Ball holds at rim coordinates for **1 second** (1000ms)
   - Allows "It's Good!" announcement to display
   - Ball stays visible during this hold period
   - Implemented via `scene.time.delayedCall(1000, resolve)` or `wait(scene, 1000)`

3. **State Cleanup**
   - `ballController.onShotEnd()` is called to clear in-flight state
   - Ball visibility is managed by the specific animation system
   - HCO makes: Ball is explicitly hidden after 1 second hold
   - Fast Break/Putback/Free Throw: Ball remains visible until next play begins

4. **Transition to Next Play**
   - Regular makes: Transition to inbound pass (BASELINE_INBOUND)
   - AND-1 makes: Transition to free throw (FREE_THROW)
   - Ball state is cleared before transition

#### Implementation by Shot Type

**HCO Made Shots** (`ShotAnimationSystem.js`):
- Uses `animateBallFlight()` to animate ball to rim
- `handleMadeShot()` holds ball at rim for 1 second
- Ball is explicitly hidden after 1 second hold
- Then calls `onShotEnd()` and transitions

**Fast Break Made Shots** (`fastBreak.js`):
- Uses `animateShotToRim()` to animate ball to rim (exact rim coordinates, no adjustment)
- Shows announcement
- Waits 1 second (ball remains visible at rim)
- Calls `onShotEnd()` and transitions to inbound

**Putback Made Shots** (`ballManager.js`):
- Uses `animateShotToRim()` to animate ball to rim
- Shows announcement
- Waits 1 second (ball remains visible at rim)
- Calls `onShotEnd()` and resolves

**Free Throw Made Shots** (`freeThrow.js`):
- Uses `animateShotToRim()` to animate ball to rim
- Shows announcement
- Waits `animationConfig.freeThrow.rimHoldMs` (typically 1000ms)
- Ball remains visible at rim during hold
- Calls `onShotEnd()` and continues to next attempt or ends

#### Key Features

- ✅ **Consistent Rim Hold**: All made shots hold at rim for 1 second
- ✅ **Correct Rim Coordinates**: Home team at home rim, away team at away rim
- ✅ **No Manual Repositioning**: Ball lands at exact final position of flight animation
- ✅ **Smooth Transitions**: State cleanup before transitioning to next play
- ✅ **Unified Behavior**: All shot types use the same resolution pattern

#### Benefits

- ✅ **Visual Consistency**: All made shots look the same (ball holds at rim)
- ✅ **Correct Positioning**: Ball always lands at correct rim coordinates
- ✅ **No Teleporting**: Ball stays at rim position throughout hold period
- ✅ **Maintainable**: Single pattern for all shot types

**Key Files:**
- `ShotAnimationSystem.js` - HCO shot resolution
- `fastBreak.js` - Fast break shot resolution
- `ballManager.js` - Putback shot resolution
- `freeThrow.js` - Free throw resolution
- `courtConstants.js` - Rim coordinate constants

**See:**
- `FrontEnd/static/js/phaser/animation/courtConstants.js` - Rim coordinate definitions

---

---

**Note:** Defensive Player + Pass Animation Synchronization bug documentation has been moved to:
- `docs/To Do/hco_animation_sync_bug.md`

**Note:** Game Mode Systems documentation has been moved to dedicated files:
- `docs/docs_1_systems/01_Game_Mode_Systems/Single_Game_Systems.md` - Single Game Mode documentation
- `docs/docs_1_systems/01_Game_Mode_Systems/Tournament_Mode_Systems.md` - Tournament Mode documentation
- `docs/docs_1_systems/01_Game_Mode_Systems/Franchise_Mode_Systems.md` - Franchise Mode documentation

---
---

**Note:** Data Persistence documentation has been moved to:
- `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md`

---

**Note:** Team Objects and Coaching Attributes System documentation has been moved to:
- `docs/docs_1_systems/00_Data_Systems/Database_System.md`

---

**Note:** Resolution System documentation has been moved to:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Turn_by_Turn_System.md`

---


