# Real-Time Countdown Clock Implementation (Current-Code Aligned)

## Purpose
Implement a second-by-second gameplay clock in the frontend while keeping backend time as the source of truth.

This document is a planning spec aligned to the current codebase architecture (router-based turn animation and unified turn finalization flow).

## Current Baseline (As of Now)

### Frontend clock behavior today
- Clock is initialized in `gameScene.create()` from resume/new-game data and written directly to `#game-clock`.
- Clock is updated in `updateScoreboard(turn)` using `turn.clock || turn.game_clock`.
- `updateScoreboard` is invoked through animation finalization (`onUpdate(turn)`), not only from one direct turn loop path.
- Sim-quarter flow (`bootGame.js`) separately updates `#game-clock` as it iterates historical turns.

### Key files in current flow
- `FrontEnd/static/js/phaser/gameScene.js`
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js`
- `FrontEnd/static/js/phaser/animation/turnPreparation.js`
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js`
- `FrontEnd/static/js/phaser/bootGame.js`

### Backend clock authority
- Backend decrements `time_remaining` by `time_elapsed`, clamps to 0, and publishes formatted `clock`.
- `/api/simulate-turn` returns `time_remaining` + `clock` in each response.

## Architecture Notes (Important)
- There is currently no `gameClock.js` module in the repo.
- Animation paths are now routed through `AnimationRouter` and finalized in `finalizeTurnAfterAnimation()`, where `onUpdate(turn)` is called.
- Timeout and foul-out flows may navigate away from gameplay; clock behavior must tolerate scene transitions cleanly.

## Proposed Implementation (Still Minimal)

### 1. Add a dedicated frontend clock module
**Target file:** `FrontEnd/static/js/phaser/utils/gameClock.js` (new)

**Responsibilities**
- Hold a local second counter (`timeRemainingSec`).
- Tick every 1 second while active.
- Write formatted value to the existing DOM clock element (`#game-clock`).
- Pause/resume/stop safely.
- Sync to backend authority after each turn result.
- Ignore duplicate starts and cleanly clear interval on stop/destroy.

**Suggested API**
```javascript
init({ timeRemainingSeconds, clockElement, onZero })
start()
pause(reason)
resume(reason)
stop()
syncWithBackend(timeRemainingSeconds)
getState() // optional debug helper
```

### 2. Integrate into `gameScene` lifecycle
**Primary integration point:** `FrontEnd/static/js/phaser/gameScene.js`

**Where to wire**
- `create()`:
  - Resolve initial authoritative time from available payload.
  - Initialize + start realtime clock module.
- `updateScoreboard(turn)`:
  - Continue existing scoreboard writes.
  - Add backend sync call when `turn.time_remaining` is present.
- Scene teardown/finalize:
  - Stop and clean interval to prevent orphan timers.

### 3. Respect current router/finalization model
Because turn updates are funneled through `AnimationRouter` -> `finalizeTurnAfterAnimation` -> `onUpdate(turn)`, realtime sync should assume:
- Updates can come from many turn types.
- Timeout turns and batch sub-turns can still trigger scoreboard updates.
- The module must be idempotent on repeated sync calls.

### 4. Pause/Resume policy (current game behavior aware)
Clock should pause when gameplay is not actively progressing:
- User presses Pause button (`scene.isPaused` path).
- Timeout/foul-out/quarter-break navigation begins.
- Game end / quarter complete state transition.

Clock should resume when:
- Gameplay scene is active and turn flow continues.
- Timeout/foul-out return path re-enters active gameplay.

### 5. Phase 1 turn time derivation rules (implementation)
These rules define how `time_elapsed` should be derived per turn type in Phase 1.

#### A. Skeleton-based turns (HCO/HCT/FCP)
- For each skeleton step, assign `random.randint(1,5)` seconds.
- Turn `time_elapsed` is the sum of step seconds that occur before/at the shot/action resolution point.
- Cap total turn `time_elapsed` at `30` seconds.
- Defensive movement remains synchronized by using the same per-step timeline as the offense.

#### B. Non-skeleton, cover-ground (CG) turns (e.g., Fast Break)
- Use movement geometry to derive elapsed time for travel-heavy actions.
- For a movement segment from `(x1,y1)` to `(x2,y2)`:
  - `dx = abs(x2 - x1)`
  - `dy = abs(y2 - y1)`
  - `segment_seconds = sqrt((dx/20)^2 + (dy/10)^2)`
- Sum segment times and then add fixed action overhead:
  - `+1s` to throw a pass
  - `+1s` to receive a pass
  - `+1s` to take a shot
- Round at the end, then cap total turn `time_elapsed` at `30` seconds.
- Example:
  - Start `(50,15)` -> End `(90,25)`
  - `dx=40`, `dy=10`
  - `sqrt((40/20)^2 + (10/10)^2) = sqrt(5) ~= 2.24s`

#### C. Non-skeleton, non-CG turns (compressed-area turns; Phase 1 simplification)
- Treat as a single step for now.
- Assign `time_elapsed = random.randint(1,5)`.
- Initial example: OREB turns.
- Additional turn types can be classified/refined later.

## Backend Sync Strategy

### Source of truth
- Backend `time_remaining` is authoritative.
- Frontend realtime countdown is UX smoothing only.

### Sync rule
On every authoritative turn update:
1. If `turn.time_remaining` exists, call `syncWithBackend(turn.time_remaining)`.
2. Do not trust local drift over backend.
3. If currently paused, update stored seconds without auto-resume.

### Formatting rule
- Internal storage: integer seconds.
- Display format: `M:SS` to match existing scoreboard conventions.

## Edge Cases To Handle
- Missing `#game-clock` element: fail soft (no throw, keep game running).
- Duplicate init/start calls: no multiple intervals.
- Scene reload during timeout/foul-out flow: no leaked interval.
- Zero time reached locally before backend sync: stop at `0:00`, then allow backend sync to confirm state.
- Batch turns / rapid updates: last backend sync wins.

## Test Checklist (First Pass)
- Realtime clock ticks each second during active HCO play.
- Backend sync snaps clock correctly after each turn.
- Timeout event pauses clock; resume continues correctly.
- Foul-out flow pauses/tears down without interval leak.
- Quarter break stops clock and next quarter initializes with correct starting time.
- Pause button pauses/resumes realtime clock in step with tween pause state.
- Sim-quarter flow remains unchanged unless intentionally integrated later.

## Implementation Order
1. Add `gameClock.js` module with start/pause/resume/stop/sync primitives.
2. Wire initialization + cleanup in `gameScene`.
3. Wire sync in `updateScoreboard(turn)`.
4. Add pause/resume calls at known gameplay pause boundaries.
5. Verify timeout/foul-out/quarter transitions for interval cleanup.

## Implementation Map (Exact Touchpoints)
Use these as the first-pass integration anchors. Line numbers are current at time of writing and may drift.

### A. Frontend initialization and scoreboard sync
- `FrontEnd/static/js/phaser/gameScene.js:480`
  - `clockEl` lookup (`document.getElementById('game-clock')`).
- `FrontEnd/static/js/phaser/gameScene.js:488`
  - `liveClock` initialization baseline.
- `FrontEnd/static/js/phaser/gameScene.js:505`
  - initial DOM clock write in `create()`.
- `FrontEnd/static/js/phaser/gameScene.js:1335`
  - `updateScoreboard(turn)` definition.
- `FrontEnd/static/js/phaser/gameScene.js:1372`
  - current clock ingestion (`turn.clock || turn.game_clock`).
- `FrontEnd/static/js/phaser/gameScene.js:1393`
  - current DOM clock write (`clockEl.textContent = liveClock`).

### B. Where scoreboard updates are triggered from turn animation
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js:108`
  - router pre-turn setup call (`prepareTurnForAnimation`).
- `FrontEnd/static/js/phaser/animation/AnimationRouter.js:215`
  - router post-turn finalize call (`finalizeTurnAfterAnimation`).
- `FrontEnd/static/js/phaser/animation/turnPreparation.js:303`
  - `onUpdate(turn)` invocation (core hook for scoreboard sync path).
- `FrontEnd/static/js/phaser/gameScene.js:1997`
  - `animateGameTurns(... onUpdate: updateScoreboard)` initial turns.
- `FrontEnd/static/js/phaser/gameScene.js:2116`
  - timeout turn path passes same `onUpdate`.
- `FrontEnd/static/js/phaser/gameScene.js:2155`
  - batch sub-turn path passes same `onUpdate`.
- `FrontEnd/static/js/phaser/gameScene.js:2222`
  - normal single turn path passes same `onUpdate`.

### C. Pause/resume and scene lifecycle touchpoints
- `FrontEnd/static/js/phaser/gameScene.js:1490`
  - scene pause state initialization (`this.isPaused = false`).
- `FrontEnd/static/js/phaser/gameScene.js:1543`
  - pause button handler begins.
- `FrontEnd/static/js/phaser/gameScene.js:1546`
  - pause toggle assignment (`this.isPaused = !this.isPaused`).
- `FrontEnd/static/js/phaser/gameScene.js:1550`
  - tween pause call (`this.tweens.pauseAll()`).
- `FrontEnd/static/js/phaser/gameScene.js:1568`
  - tween resume call (`this.tweens.resumeAll()`).

### D. Timeout/foul-out transition touchpoints
- `FrontEnd/static/js/phaser/gameScene.js:2090`
  - timeout turn detection in turn loop.
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js:563`
  - timeout response clock/time extraction (`_responseData` path).
- `FrontEnd/static/js/phaser/animation/AnimationEngine.js:595`
  - timeout navigation invocation (`showTimeoutPopup(...)`).

### E. Sim-quarter clock path (separate flow)
- `FrontEnd/static/js/phaser/bootGame.js:853`
  - sim-quarter `clockEl` lookup.
- `FrontEnd/static/js/phaser/bootGame.js:895`
  - per-turn clock update in sim-quarter processing.
- `FrontEnd/static/js/phaser/bootGame.js:904`
  - sim-quarter DOM clock write.

### F. Backend authority touchpoints
- `BackEnd/models/turn_manager.py:2975`
  - `update_clock_and_possession(result)` clock decrement entry.
- `BackEnd/models/turn_manager.py:2987`
  - formatted `clock` assignment from `time_remaining`.
- `BackEnd/api/api.py:4056`
  - `/api/simulate-turn` response object starts.
- `BackEnd/api/api.py:4059`
  - authoritative `time_remaining` in response.
- `BackEnd/api/api.py:4060`
  - authoritative `clock` in response.
- `BackEnd/main.py:332`
  - quarter reset logic for `time_remaining` and `clock`.

## Non-Goals (for this pass)
- No backend clock logic changes.
- No shot clock.
- No visual FX/audio on final seconds.
- No sim-quarter UX redesign.

## Notes for Follow-Up Doc
This file is a working implementation plan. Final canonical behavior/spec should be captured in:
- `docs/docs_1_systems/05_GP_Supporting_Systems/Real_Time_Clock_System.md`

## Implementation Principles

### 1. One clock system, two animation styles
- The SS&S clock system must support both step-based turns (HCO/HCT/FCP) and non-step turns (Fast Break/OREB/etc.).
- Clock behavior should be driven by a shared timing contract, not by skeleton-only internals.
- Long-term migration away from skeletons should remain possible without redesigning clock logic.

### 2. Backend authority remains unchanged
- Backend `time_elapsed`, `time_remaining`, and `clock` remain source of truth.
- Frontend clock is presentation/UX pacing only.
- Frontend must sync to backend authoritative time at turn boundaries.

### 3. No extra backend/API load
- Do not add per-step or per-second API calls.
- Keep existing turn-level request model (`/api/simulate-turn` once per turn).
- All countdown pacing/interpolation runs client-side.

### 4. Phase 1 step timing uses literal seconds
- For skeleton turns, each step currently uses literal `random.randint(1,5)` seconds.
- Total turn time is capped at `30` seconds.
- Tempo-based weighting/refinements can be layered later.

### 5. Non-step turns use synthetic phases
- For turns without predefined steps, build timing phases from distance moved + actions taken.
- Example phase types: advance, pass, finish, rebound/reset.

### 6. CG action overhead is explicit
- For CG turns, add fixed action overhead on top of movement time:
  - `+1s` pass throw
  - `+1s` pass receive
  - `+1s` shot attempt
- Apply rounding at the end of total CG calculation, then clamp to `30` seconds.
- Apply the same weighted pacing model used for step turns.

### 6. Game speed controls visible countdown rate
- Clock countdown cadence should scale with user speed settings (`Normal`, `Fast`, `Super Fast`).
- Target behavior: faster modes show 1-second decrements more quickly.
- Countdown must pause/resume with gameplay pause states.

### 7. Real-time UX guardrails
- Preserve smooth game flow; avoid long stalls for high-step turns.
- Keep turn render duration bounded by practical UX limits even when game-seconds are high.
- If needed, compress low-value in-between motion before compressing key actions.

### 8. Drift handling
- Minor client drift is acceptable during animation.
- Hard-correct from backend at turn sync points.
- Optional smoothing can be considered if hard snaps feel jarring.

### 9. Operational/performance safety
- Keep timing math lightweight (precompute once per turn; avoid heavy per-frame work).
- Add basic telemetry for tuning:
  - average real turn duration
  - frame drops / FPS health
  - queue/latency pressure during fast modes
  - timeout/foul-out resume responsiveness
