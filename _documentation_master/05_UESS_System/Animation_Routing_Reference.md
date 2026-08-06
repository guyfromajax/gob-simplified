# Animation Routing Reference — Detection + Handlers

**Status:** Merged from `Animation_Detection_Reference.md` + `Animation_Handler_Reference.md` (June 2026); both catalogs re-verified against `animateGameTurns.js` / `AnimationEngine.js` June 2026.

> **Hybrid-layer doc — not the target architecture.** This documents the legacy/hybrid FE routing layer (detection + handlers) that exists during the UESS migration. Schema turns bypass the handlers entirely (see "Schema playback dispatch"); under the pure-renderer end state the `result_type` detection tree collapses and the legacy handlers shrink toward dead code (UESS backlog items 14–15, `projects/UESS_Backlog.md`). When that ships, gut this doc rather than maintain it.

This document covers the full routing pipeline: **Part 1** catalogs every detection point in the turn loop of `FrontEnd/static/js/phaser/animation/animateGameTurns.js`; **Part 2** catalogs every handler registered in `AnimationEngine`.

> **Note:** line numbers drift as files evolve, so both catalogs deliberately list entries by **order, predicate, and handler name** — the durable contract. Search for the predicate if you need the code.

## Architecture

**Flow:**
```
animateGameTurns.js (detection)        ← Part 1
    ↓
AnimationRouter (single entry point)
    ↓
AnimationEngine (routing logic)        ← Part 2
    ↓
Schema playback (animation_steps[]) OR Specialized Handlers
```

## Schema playback dispatch (checked BEFORE handler routing)

`AnimationEngine.processTurn` checks for the UESS schema **before** calling `determineHandler()`:

- If the turn carries `animation_steps[]` **and** is not an un-migrated Fast Break variant, it routes to `runSchemaPlaybackTurn()` → `animationPlayback.playTurn()` (+ `dispatchTurnStop()` when the steps end in a `turn_stop`). The legacy handler **never runs** for these turns.
- `MIGRATED_FB_PLAYS = {covert_release, rim_runner, triangle, after_steal}` — all four FB plays. A `current_turn === "FAST_BREAK"` turn whose `fast_break_play` is *not* in that set falls back to the legacy FB handler even if it carries steps.
- FREE_THROW schema turns additionally run `_finishSchemaFreeThrowTurn()` after playback (active-player display, text scroll, FT_MAKE / pressure announcements, end-of-quarter hold).
- The legacy `_maybeRunDiscreteDrebOutletLeadIn` post-playback hook was **removed** from the schema path (caused double execution of the outlet — the schema DREB turn + HCO entry orchestrator now own rebound capture and the BH → PG handoff); the helper remains in the file but is not invoked.
- Diagnostic logs: `[UESS PLAYBACK] schema:enter/exit`, `[UESS DISPATCH]`, `🏠 [HCO DISPATCH]` (`NEW_PLAYBACK_ENGINE` vs `LEGACY_HANDLER`).

There is no separate "UESS detection" in Part 1 — `animation_steps[]` presence simply widens the FOUL / DEAD BALL / HCO / STEAL gates, and the engine's dispatch above picks the schema playback path.

---

# Part 1 — Detection (turn loop in `animateGameTurns.js`)

## Detection Pattern

All detections follow this pattern:
1. Check turn properties (`result_type`, flags, presence of `animations[]` / `animation_steps[]`)
2. Set `turn.index = preservedTurnIndex` (caller-supplied global index when present, else loop index)
3. Call `await animationRouter.processTurn(turn)`
4. `continue` to next turn (exception: TIMEOUT `break`s the loop)

**Legacy vs schema payloads:** several detections route through the router only when the turn carries animation data — either legacy `animations[]` (un-migrated turns) **or** the unified `animation_steps[]` schema (UESS-migrated turns). Turns with neither fall back to direct announcements + score updates.

## Detection Points (In Order of Execution)

### 1. FREE_THROW
- **Detection:** `turn.result_type === "FREE_THROW"`
- **Routes to:** `AnimationRouter` → `handleFreeThrow()`
- **Notes:** Pre-loop, `annotateFreeThrowTurns()` stamps each FT turn with `ftContext` (`ftIndex`, `ftTotal`, `bonusType`) by grouping consecutive FT rows.

### 2. CHARGE
- **Detection:** `turn.result_type === "CHARGE"`
- **Routes to:** `AnimationRouter` → `handleDefault()` (skeleton animation, no shot)
- **Notes:** Routed so `finalizeTurnAfterAnimation` announces "Charge!" (not "Offensive Foul!").

### 3. FOUL
- **Detection:** `turn.result_type === "FOUL"`
- **Routes to:** `AnimationRouter` → `handleDefault()` when the turn carries legacy `animations[]` (FCP/HCT path) **or** schema `animation_steps[]` (HCO-stopper path); otherwise direct announcements + score updates.
- **Notes:** No longer requires `fcp_foul` / `hct_foul` flags to route — any animated foul routes. Without the `animation_steps` clause, HCO stopper turns would never animate.

### 4. DEAD BALL
- **Detection:** `turn.result_type === "DEAD BALL"`
- **Routes to:** `AnimationRouter` → `handleDefault()` when `animations[]` **or** `animation_steps[]` present; otherwise direct announcements + score updates.
- **Notes:** Previously never routed; schema-rendered dead-ball turnovers (e.g. FB bat-OOB) now animate. Engine registers both `"DEAD BALL"` (backend spelling, with space) and `"DEAD_BALL"`.

### 5. SIDE_INBOUND
- **Detection:** `turn.result_type === "SIDE_INBOUND"`
- **Routes to:** `AnimationRouter` → `handleSideInbound()`
- **Notes:** Every emitted SIP runs in full and is clock-neutral. Backend does not emit SIP when its source is terminal or the game clock is already 0:00.

### 6. BASELINE_INBOUND
- **Detection:** `turn.result_type === "BASELINE_INBOUND"`
- **Routes to:** `AnimationRouter` → `handleBaselineInbound()`
- **Notes:** FCP/HCT state tracking, player animations, and state transitions handled by handler.

### 7. DEFENSIVE_STOP
- **Detection:** `turn.result_type === "DEFENSIVE_STOP"`
- **Routes to:** `AnimationRouter`
- **Notes:** Fast Break defensive stops route to `handleFastBreak()`; non-Fast-Break uses `handleDefensiveStop()`.

### 8. DREB (discrete defensive rebound turn)
- **Detection:** `turn.result_type === "DREB"`
- **Routes to:** `AnimationRouter` → schema playback (`playTurn`)
- **Notes:** Backend emits MISS → DREB → HCO as a discrete schema turn (`animation_steps[]`). Without this branch the loop falls through and the turn never animates. (See the outlet lead-in removal note under "Schema playback dispatch".) A discrete DREB turn with no `animation_steps` falls through to the legacy handler with a console warning.

### 9. TIMEOUT
- **Detection:** `turn.result_type === "TIMEOUT"`
- **Routes to:** `AnimationRouter` → `handleTimeout()`, then **`break`s the turn loop** — no further turns are processed (user navigates to the lineup screen).

### 10. PUTBACK_MAKE / PUTBACK_MISS / OREB_KICKOUT
- **Detection:** `turn.result_type === "PUTBACK_MAKE" || "PUTBACK_MISS" || "OREB_KICKOUT"`
- **Routes to:** `AnimationRouter` → `handlePutback()` (delegates to `handleOrebTurn` in `animateGameTurns.js`)
- **Notes:** All three result types use the same handler. Short-clock putbacks may carry `eoq_shortened_oreb`; their schema preserves the full post-release visual resolution while pinning game-clock boundaries at 0:00. An eligible leading-offense OREB instead arrives as `RUN_OUT_CLOCK` with `oreb_run_out` and uses the Run Out handler.

### 11. TURNOVER
- **Detection:** `turn.result_type === "TURNOVER"`
- **Routes to:** `AnimationRouter` → `handleTurnover()`

### 12. OPENING_TIP
- **Detection:** `turn.result_type === "OPENING_TIP"`
- **Routes to:** `AnimationRouter` → `handleOpeningTip()`
- **Notes:** Handler validates timing (Q1 start or OT start); state transition to HalfCourt handled by handler.

### 13. FAST_BREAK
- **Detection:** `turn.result_type === "FAST_BREAK" || ((turn.result_type === "MAKE" || "MISS" || "BLOCK") && turn.fast_break === true)`
- **Routes to:** `AnimationRouter` → `handleFastBreak()`
- **Notes:** Single detection point — the old duplicate "legacy detection" that called `runFastBreakSequence()` directly was removed. `AnimationEngine.determineHandler()` also checks the `fast_break` flag.

### 14. HCO (setup / outcome turns)
- **Detection:** `turn.result_type === "HCO"`
- **Routes to:** `AnimationRouter` → `handleDefault()` when `animations[]` **or** `animation_steps[]` present; otherwise direct announcements + score updates.
- **Notes:** Includes FCP/HCT → HCO transitions (press break) and regular HCO setup turns. The `animation_steps` clause matters for HCT trap-broken turns, which emit only schema steps after the dynamic_hct refactor.

### 15. Final-turn FOUL
- **Detection:** `turn.final_turn === true && turn.result_type === "FOUL"`
- **Routes to:** `AnimationRouter`
- **Notes:** Final Turn shot blocking foul. (Unreachable for animated fouls — detection 3 catches them first; this catches non-animated final-turn fouls that fell through.)

### 16. Shot attempts (MAKE / MISS / BLOCK, non-fast-break)
- **Detection:** `!turn.fast_break && (turn.result_type === "MAKE" || "MISS" || "BLOCK")`
- **Routes to:** `AnimationRouter` → `AnimationEngine` → `handleShotAttempt()` → `ShotAnimationSystem`
- **Notes:** Catches all half-court shots — HCO and FCP/HCT shot attempts alike (FCP/HCT shots carry `fcp_shot` / `hct_shot` flags and route through the same path). Uses `result_type` directly, not `current_turn === "HCO"`.

### 17. STEAL
- **Detection:** `turn.result_type === "STEAL"`
- **Routes to:** `AnimationRouter` → `handleSteal()` (hybrid: skeleton + steal action) when `animations[]` **or** `animation_steps[]` present (standalone steal turns). Otherwise, if the turn carries a STEAL event (`turn.events` with `event_type === "STEAL"`) and the scene is not in FastBreak state, the steal is handled **inline** via `runPass()` (ball handler → stealer) + `possessionChange` emit — not through the router.

## Detection Summary by Result Type

| Result Type | Routes Through AnimationRouter? | Handler / path |
|------------|--------------------------------|---------|
| `FREE_THROW` | ✅ Yes | `handleFreeThrow()` |
| `CHARGE` | ✅ Yes | `handleDefault()` (Charge announcement via finalize) |
| `FOUL` (with `animations[]` or `animation_steps[]`) | ✅ Yes | `handleDefault()` |
| `FOUL` (non-animated) | ❌ No | Direct announcements |
| `DEAD BALL` (with animation payload) | ✅ Yes | `handleDefault()` |
| `DEAD BALL` (non-animated) | ❌ No | Direct announcements |
| `SIDE_INBOUND` | ✅ Yes | `handleSideInbound()` |
| `BASELINE_INBOUND` | ✅ Yes | `handleBaselineInbound()` |
| `DEFENSIVE_STOP` | ✅ Yes | `handleDefensiveStop()` / `handleFastBreak()` (FB) |
| `DREB` | ✅ Yes | schema playback (`playTurn`) |
| `TIMEOUT` | ✅ Yes | `handleTimeout()`, then loop `break` |
| `PUTBACK_MAKE` / `PUTBACK_MISS` / `OREB_KICKOUT` | ✅ Yes | `handlePutback()` → `handleOrebTurn` |
| `TURNOVER` | ✅ Yes | `handleTurnover()` |
| `OPENING_TIP` | ✅ Yes | `handleOpeningTip()` |
| `FAST_BREAK` (explicit or MAKE/MISS/BLOCK + flag) | ✅ Yes | `handleFastBreak()` |
| `HCO` (with animation payload) | ✅ Yes | `handleDefault()` |
| `HCO` (non-animated) | ❌ No | Direct announcements |
| `FOUL` + `final_turn` | ✅ Yes | router |
| `MAKE`/`MISS`/`BLOCK` (non-FB shot) | ✅ Yes | `handleShotAttempt()` → `ShotAnimationSystem` |
| `STEAL` (with animation payload) | ✅ Yes | router |
| `STEAL` (event within turn) | ❌ No | Inline `runPass()` |

## Detection Order Matters

The order of detections is **critical** because:
1. **Early exits:** Once a detection matches, the turn is processed and the loop `continue`s.
2. **Exclusion by position:** Later detections only see turns not already handled (e.g. the shot-attempt detection only sees non-FB MAKE/MISS/BLOCK because FAST_BREAK matched first).
3. **Loop-level state:** `scene.skipToEnd` is checked at the top of each iteration and after STEAL handling (flushes remaining turns to the scoreboard without animating); TIMEOUT terminates the loop entirely.

## Detection Notes

1. **FCP/HCT no longer has a dedicated detection block.** The old multi-part FCP/HCT detection that routed directly to `playTurnAnimation()` is commented out in the file (kept for reference). FCP/HCT turns now route through `AnimationRouter` like everything else: animated FCP/HCT fouls via detection 3, press-break HCO transitions via detection 14, FCP/HCT shot attempts via detection 17.
2. **`scene._currentTurnBatch`** is set before the loop so the router can pass `nextTurn` to BIP/SIP handlers (Force Foul same-turn defender move).

---

# Part 2 — Handlers (`AnimationEngine`)

Everything below describes the **legacy handler path** — turns with no `animation_steps[]` (or un-migrated FB variants). Schema turns short-circuit at the dispatch described at the top of this doc.

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
| `handleShotAttempt()` | `SHOT_ATTEMPT` (detected) | Shot attempts (MAKE/MISS/BLOCK) | `ShotAnimationSystem` | `playTurnAnimation()` |
| `handleRebound()` | `REBOUND` (detected) | Rebound animations | `ReboundAnimationSystem` | `playTurnAnimation()` |
| `handlePass()` | `PASS` (detected) | Pass animations | `PassAnimationSystem` | `playTurnAnimation()` |
| `handleDefault()` | `HCO`, `DEFAULT`, `FOUL`, `CHARGE`, `DEAD_BALL`, `DEAD BALL` | Default/fallback handler (skeleton) | `playTurnAnimation()` | None |
| `handleTimeout()` | `TIMEOUT` | Timeout handling | Direct implementation | None |
| `handleFinalTurnShot()` | `FINAL_TURN_SHOT` (detected) | Final Turn shot fallback when `animation_steps` missing | `runSchemaPlaybackTurn()` if steps present; else `ShotAnimationSystem` / `playTurnAnimation()` | Normal Final Turn shots with steps never reach this handler — `processTurn` schema gate runs first |

Note: `DEAD BALL` is registered under both spellings — the backend sends `"DEAD BALL"` (with space); `"DEAD_BALL"` is kept defensively. `CHARGE` maps to `handleDefault` (skeleton animation, no shot) so `finalizeTurnAfterAnimation` can announce "Charge!".

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
   - If `turnData.fast_break === true` (or string `"true"`) OR `turnData.result_type === "FAST_BREAK"` → `handleFastBreak()`

2. **Final Turn:**
   - If `final_turn === true` AND `isShotAttempt(turnData)` → `handleFinalTurnShot()`

3. **Specific Result Type:**
   - If `turnData.result_type` exists in `animationHandlers` Map → Use that handler

4. **Shot Attempt Detection:**
   - If `isShotAttempt(turnData)` AND not in non-shot result types → `handleShotAttempt()`
   - `isShotAttempt`: `result_type` MAKE/MISS/BLOCK, or `shooter` present, or `shot_score` defined

5. **Rebound Detection:**
   - If `isRebound(turnData)` → `handleRebound()` (`rebounderId` / `rebound_type` / `result_type` OREB or DREB)

6. **Pass Detection:**
   - If `isPass(turnData)` → `handlePass()` (`passer_id` / `receiver_id` / `pass_type` / `result_type === "PASS"`)

7. **Default Handler:**
   - Otherwise → `handleDefault()`

FCP/HCT has no special routing — FCP/HCT shots hit `SHOT_ATTEMPT`, other FCP/HCT results hit their respective handlers (same as HCO).

**Non-Shot Result Types (Excluded from Shot Attempt Detection):**
- `FOUL`, `FREE_THROW`, `TURNOVER`, `DEAD_BALL`, `DEAD_BALL_TURNOVER`
- `SIDE_INBOUND`, `BASELINE_INBOUND`, `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`
- `DEFENSIVE_STOP`, `OPENING_TIP`, `HCO`, `STEAL`

## Registered Handlers

### 1. `handleFreeThrow()`
**Registered for:** `FREE_THROW`

**What it does:**
- **Schema guard:** if the turn carries `animation_steps[]` (shouldn't normally reach here — processTurn catches it), runs only `_finishSchemaFreeThrowTurn()` and returns
- Updates active player display (shooter)
- Routes to `FreeThrowAnimationSystem` (if available) or falls back to `runFreeThrowSequence()`
- Appends text scroll with free throw result
- On `quarter_ends_after` when `time_remaining == 0` after the last FT: shows 0:00, holds `holdFinalShotMs` (default 2000ms) — no BIP; then `signalQuarterEnded(..., { phase: 'playbackComplete' })`. When clock remains after the last FT in a late-clock chain, normal BIP → FLSS progression applies (see `Situational_Logic_System.md`). Contract-only quarter ends may still horn from `AnimationRouter` `clockTween` phase (see `SFX_System.md`).
- **Note:** `onUpdate` is called inside `runFreeThrowSequence` (no double counting)

**Key Features:**
- Active player display update
- Free throw sequence execution
- Text scroll append
- Handles multiple free throw attempts (via `ftContext`)

### 2. `handleSideInbound()`
**Registered for:** `SIDE_INBOUND`

**What it does:**
- Routes to `PassAnimationSystem` (if available) or falls back to `runSideInboundSetup()`
- Runs every SIP supplied by the backend; the backend terminal-inbound gate prevents post-buzzer SIP payloads
- Sets `scene._previousTurnWasInbound = true` and `scene._previousInboundTurnType = 'SIDE_INBOUND'` so the next HCO lead-in can validate its source-scoped contract

**Key Features:**
- Pass animation system integration
- Fallback to legacy `runSideInboundSetup()`
- Inbound-source stamping for HCO entry validation

### 3. `handleBaselineInbound()`
**Registered for:** `BASELINE_INBOUND`

**What it does:**
- **FCP/HCT State Tracking:** Sets `scene.currentPressureType` and `scene.pressureSequenceActive` when pressure setup detected
- Animates all players to their positions (distance-based AG fallback when `turnData.animations` lacks per-player `game_seconds` — typical for HCO BIP since BIP backend doesn't populate animations array)
- Calls `passSystem.executeInboundSequence(...)` → `runInboundSetup` for the actual BIP pass + setup-tween orchestration
- Transitions state machine to `HalfCourt`
- Sets `scene._previousTurnWasInbound = true` for HCO pre-step setup
- Waits for pass animation to complete before proceeding

**Key Features:**
- FCP/HCT state initialization (single source of truth)
- 2 × 200 ms post-placement holds **removed** (May 2026 BIP responsiveness)
- BIP pass duration **250 ms** (down from 500 ms)
- For HCO bring-up after BIP: `playTurnAnimation`'s `runSetupTween` reads per-player `bringup_per_player_seconds` from turn data so the BH visually moves at the random cruise rate while others stay constant

### 4. `handleTurnover()`
**Registered for:** `TURNOVER`  

**What it does:**
- Routes to `turnoverAdapter.js` for turnover animation handling

**Key Features:**
- Delegates to specialized turnover adapter
- Handles turnover animations

### 5. `handleFastBreak()`
**Registered for:** `FAST_BREAK`  

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

**What it does:**
- Routes to `handleOrebTurn()` function for putback/OREB handling
- Handles PUTBACK_MAKE, PUTBACK_MISS, and OREB_KICKOUT result types

**Key Features:**
- Unified handler for all OREB-related outcomes
- Delegates to specialized OREB handler
- Honors backend-authored shortened OREB schema clocks; the frontend does not truncate or choose the shot

### 7. `handleTimeout()`
**Registered for:** `TIMEOUT`  

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

**What it does:**
- Routes to `ShotAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles HCO and FCP/HCT shot attempts (MAKE/MISS)

**Key Features:**
- Shot animation system integration
- Fallback to legacy `playTurnAnimation()`
- Handles all shot attempt types

### 12. `handleRebound()`
**Registered for:** `REBOUND` (detected)  

**What it does:**
- Routes to `ReboundAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles rebound animations

**Key Features:**
- Rebound animation system integration
- Fallback to legacy `playTurnAnimation()`

### 13. `handlePass()`
**Registered for:** `PASS` (detected)  

**What it does:**
- Routes to `PassAnimationSystem` (if available) or falls back to `playTurnAnimation()`
- Handles pass animations

**Key Features:**
- Pass animation system integration
- Fallback to legacy `playTurnAnimation()`

### 14. `handleDefault()`
**Registered for:** `HCO`, `DEFAULT`, `FOUL`, `CHARGE`, `DEAD_BALL`, `DEAD BALL`

**What it does:**
- Routes to `playTurnAnimation()` for default/fallback handling
- Handles HCO setup turns, animated fouls/charges, schema-less dead balls, and other default cases

**Key Features:**
- Default/fallback handler
- Skeleton animation support
- Handles multiple result types

### 15. `handleFinalTurnShot()`
**Registered for:** `FINAL_TURN_SHOT` (reached via `determineHandler` when `final_turn === true` + shot attempt)

**What it does:**
- **Primary path (UESS):** When `turnData.animation_steps` is present, `processTurn` routes to `runSchemaPlaybackTurn()` before this handler runs — full schema playback from step 0 (alignment + step-0 floor + pass/drive/shoot). Quarter-end hold runs only when `quarter_ends_after` (clock at 0). If clock remains, backend may chain BIP → FLSS or OREB/DREB per `eoq_clock_progression`.
- **Fallback (legacy):** If no schema steps, runs `runFinalTurnAlignment()` + imperative late-pass hold, then `ShotAnimationSystem` / `playTurnAnimation()`.

## Registered Result Types

Full registration list in `initializeDefaultHandlers()` (order doesn't matter — it's a Map):

`FREE_THROW`, `SIDE_INBOUND`, `BASELINE_INBOUND`, `TURNOVER`, `FAST_BREAK`, `SHOT_ATTEMPT`, `REBOUND`, `PASS`, `HCO`, `FOUL`, `CHARGE`, `DEAD_BALL`, `DEAD BALL`, `STEAL`, `DEFAULT`, `PUTBACK_MAKE`, `PUTBACK_MISS`, `OREB_KICKOUT`, `OPENING_TIP`, `DEFENSIVE_STOP`, `TIMEOUT`, `RUN_OUT_CLOCK`, `FINAL_TURN_SHOT`

`RUN_OUT_CLOCK` with `oreb_run_out=true` first tweens the rebounder to
`oreb_capture_coords`, attaches the ball, then carries the ball with that player
through the normal run-out drift. The backend has already suppressed putback
resolution and made the turn terminal.

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
