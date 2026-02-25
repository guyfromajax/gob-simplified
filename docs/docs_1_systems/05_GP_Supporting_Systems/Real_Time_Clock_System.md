# Real Time Clock System

## Purpose
Define how gameplay turns map to clock countdown behavior using four clock categories:
- `Skeleton`
- `CG` (Cover-Ground; user note said `CB`, treated here as CG)
- `non-CG`
- `No Impact`

## Clock Categories

### 1. Skeleton
Used for turn types with skeleton steps (`HCO`, `FCP`, `HCT`).

Clock calculation:
- For each executed skeleton step: `step_seconds = 1`
- Backend emits per-step timing contract:
  - `step_clock_seconds[]`
  - `resolution_step_index`
  - `executed_step_count`
- Turn elapsed: `time_elapsed = sum(step_clock_seconds)`
- Cap per turn: `min(sum_steps, 30)`
- HCO step-1 bring-up overhead:
  - Add movement-based overhead seconds to step 0 timing (setup-to-step1 bring-up), then apply cap.
  - Overhead uses distance rule aligned with CG scaling and rounds to nearest second.

Execution:
- Backend computes authoritative `time_elapsed`
- Frontend animates each step using backend `step_clock_seconds[]` (not guessed durations)
- Frontend movement speed remains distance-based/consistent (not stretched to fill step)
- After a player reaches step destination, they hold until next step boundary
- Non-ball-handler overrun rule: if a move exceeds step budget, movement is clipped at boundary and continues next step from live position
- Ball-handler exception: if ball-handler move exceeds step budget, the step window extends until ball-handler movement completes
- Frontend countdown is presentation only, then syncs to backend `time_remaining` at turn end

### 2. CG (Cover-Ground)
Used for non-skeleton turns that travel significant court distance (`FAST_BREAK`).

Clock calculation (per movement segment):
- `dx = abs(x2 - x1)`
- `dy = abs(y2 - y1)`
- `segment_seconds = sqrt((dx/20)^2 + (dy/10)^2)`
- Turn elapsed = sum of all segment seconds (plus optional small action costs if enabled later)

Execution:
- Build movement segment timeline from start/end points
- Use segment time totals as turn `time_elapsed`
- Frontend countdown follows turn timeline and hard-syncs to backend at turn end

### 3. non-CG
Used for non-skeleton turns in compressed space with local action (`OPENING_TIP`, `OREB`).

Clock calculation:
- Treat as one step for now
- `time_elapsed = random.randint(1,5)`

Execution:
- Single-phase countdown for the turn
- Sync to backend authoritative clock/time_remaining after turn resolution

### 4. No Impact
Used for turn types that should not reduce game clock (`INBOUND_PASS`, `SIDE_INBOUND_PASS`, `FREE_THROW` per current plan).

Clock calculation:
- `time_elapsed = 0`

Execution:
- No countdown decrement during turn
- Clock display remains unchanged except for backend sync if response includes updated clock context
- Frontend realtime countdown is explicitly frozen during no-impact turns to prevent local drift
- Realtime clock start is deferred until first impact turn (non no-impact), preventing pre-turn drift on page load/resume flows

## Turn Classification Matrix

1. `OPENING_TIP`: `non-CG`
2. `INBOUND_PASS` (BIP): `No Impact`
3. `SIDE_INBOUND_PASS` (SIP): `No Impact`
4. `HCO`: `Skeleton`
5. `OREB`: `non-CG`
6. `FREE_THROW`: `No Impact`
7. `FAST_BREAK`: `CG`
8. `FCP`: `Skeleton`
9. `HCT`: `Skeleton`

## System Rules
- Backend `time_elapsed`, `time_remaining`, and `clock` are authoritative.
- Frontend countdown is UX pacing only.
- No additional API calls for per-step/per-second updates.
- One turn response syncs the clock state (`time_remaining`/`clock`) at turn boundaries.
- Frontend must freeze realtime countdown when `time_elapsed = 0` (no-impact turns).
- For skeleton turns, frontend must consume backend `step_clock_seconds[]` so per-step animation time and elapsed clock time are aligned.

## Live clock end-of-turn snap
The frontend snaps the shot clock using the same pattern as the game clock: use turn’s explicit field when present (`shot_clock_remaining`), else use the contract end value **`shot_clock_end`** (on every turn with a contract). No extra backend fields; reset and shot-clock violation remain backend-only. See `clock_sync_system.md` §9.

## Implementation Plan

### Phase 1: Backend Time Elapsed Derivation (SS&S Source of Truth)
Goal: compute `time_elapsed` on backend for every turn using the clock category rules.

1. Add a centralized clock-time resolver in backend turn resolution flow.
2. Route each turn through the resolver based on turn classification:
- `Skeleton`: per-step `random.randint(1,5)`, sum to resolution point, cap at `30`.
- `CG`: segment formula sum, round once at end, cap at `30`.
- `non-CG`: single `random.randint(1,5)`.
- `No Impact`: `0`.
3. Ensure CG uses round-at-end:
- `total_seconds = sum(segment_seconds)`
- `time_elapsed = min(30, round(total_seconds))`
4. Keep all existing clock decrement mechanics unchanged after `time_elapsed` is set:
- backend continues to update `time_remaining` and formatted `clock` as today.
5. Include derived `time_elapsed` in turn payload (already standard) for frontend use and debugging.
6. For skeleton turns, include per-step timing contract fields in payload:
- `step_clock_seconds[]`
- `resolution_step_index`
- `executed_step_count`

### Phase 2: Frontend Real-Time Countdown Module
Goal: add UX countdown that follows gameplay without changing backend authority.

1. Add `gameClock` module in frontend:
- initialize/start/pause/resume/stop/sync APIs.
2. Clock display cadence (temporary global setting):
- visible `1` game-second decrement every `700ms`.
3. Wire into gameplay scene lifecycle:
- initialize from authoritative backend time at scene start.
- pause/resume with gameplay pause conditions.
- stop/cleanup on scene teardown/navigation.
4. Use reason-based pause tokens so multiple pause causes do not conflict:
- `user_pause`: controlled by Pause/Resume button.
- `no_impact_turn`: applied during no-impact turns, removed on impact turns.
- Clock runs only when no pause tokens are active.
5. Keep existing scoreboard updates; add sync call at turn boundaries using backend `time_remaining`.

### Phase 3: Animation Synchronization
Goal: align visual countdown progression with movement/action progression.

1. Skeleton turns:
- use backend `step_clock_seconds[]` per executed step.
- apply `step_budget_ms = step_clock_seconds[i] * clock_second_ms` per step.
- animate movement at normal distance-based speed.
- hold remaining step time when movement finishes early.
- clip non-ball-handler movement at boundary if movement would exceed budget.
- extend step if ball-handler movement exceeds budget.
- keep backend turn-end sync as guardrail only (should be near no-op when aligned).
2. CG turns:
- use movement segments for animation timing and clock progression.
3. non-CG turns:
- treat as one phase for countdown progression.
4. No Impact turns:
- no decrement animation (clock remains static during turn).

### Phase 4: Validation and Tuning
Goal: ensure correctness, responsiveness, and stable UX.

1. Functional validation:
- each turn type produces expected `time_elapsed`.
- no-impact turns always produce `0`.
- CG rounding behaves as expected (example `2.24 -> 2`).
2. Integration validation:
- frontend countdown always re-syncs to backend on turn completion.
- timeout/foul-out/quarter transitions do not leak timers.
3. Performance validation:
- no additional API volume.
- no visible animation stutter attributable to countdown logic.
4. Tuning pass:
- keep temporary `700ms` cadence now.
- later split cadence by speed settings (`Normal`, `Fast`, `Super Fast`).

## Acceptance Criteria
- Every simulated turn has deterministic category-based `time_elapsed` logic applied on backend.
- `Skeleton` and `CG` turns never exceed `30` seconds elapsed.
- CG calculation uses `sqrt((dx/20)^2 + (dy/10)^2)` with round-at-end and cap.
- `INBOUND_PASS`, `SIDE_INBOUND_PASS`, and `FREE_THROW` always return `time_elapsed = 0`.
- Frontend countdown runs continuously during active play, pauses correctly, and syncs at turn boundaries.
- No increase in backend/API call frequency.

## Timeout Click Clock Reconciliation (February 2026)

### Problem
During live countdown, a timeout click can happen between backend turn boundaries. In that gap, backend `game_state.time_remaining` may still be slightly higher than the user-visible clock on `court.html`. If timeout save uses backend-only time, lineup can show the expected value while return-to-court resumes from an earlier (higher) time.

### Rule
At timeout click, backend reconciles clocks using:
- `effective_game_time = min(backend_time_remaining, displayed_time_remaining)`
- `effective_shot_clock = min(backend_shot_clock_remaining, displayed_shot_clock_remaining, effective_game_time)`

Both are clamped to `>= 0`.

### Execution Flow
1. Frontend sends timeout click payload with:
- `displayed_clock`
- `displayed_time_remaining`
- `displayed_shot_clock_remaining`
- `timeout_trace_id`
2. `/api/call-timeout` applies the min-reconciliation before `gm.call_timeout(...)`.
3. Timeout snapshot persisted to DB uses reconciled values.
4. Resume (`/api/simulate-quarter?resume_from_timeout=true`) restores from that saved snapshot.

### Notes
- Backend remains source of truth for persisted state.
- Frontend remains presentation clock; click capture prevents drift at timeout boundary.
- This reconciliation is surgical and only applies on timeout-click save path.

## Shot Clock Rules

Whenever the game clock is running, the shot clock runs.

### Backend: Shot clock derivation (same delta as game clock)

The backend does **not** track shot clock independently. For each turn it derives shot clock end from the game clock delta:

1. **Current turn’s contract**
   - `game_seconds_elapsed = clock_start - clock_end` (e.g. 11 seconds for 4:01 → 3:50).
   - `shot_clock_end = shot_clock_start - game_seconds_elapsed`, clamped to 0.
   - Example: clock 4:01→3:50 (11 sec), shot clock start 30 → shot clock end 19.
   - The **clock contract** attached to the turn uses this derived `shot_clock_end` so the frontend animates from `shot_clock_start` to `shot_clock_end` during the turn.

2. **Reset only affects the next turn**
   - Reset logic (make, miss with possession change, steal, dead ball, etc.) must **not** change the current turn’s `shot_clock_end`.
   - After the contract is attached, the backend sets `game_state["shot_clock_remaining"] = 30` (or min(30, time_remaining)) so that the **next** turn’s `shot_clock_start` is 30.
   - Order of operations: compute derived `shot_clock_end` → attach contract (so current turn shows start→end) → then, if reset, set game_state for next turn to 30.

3. **Shot clock at 0**
   - If the derived `shot_clock_end` would be 0 and the turn is in a clock-enforced state (HCO, FCP, HCT, FAST_BREAK), the backend triggers shot clock violation / forced shot logic instead of using that result.

### Shot clock reset instances

1. All shot attempts — reset at rim hold of make or miss; shot clock restarts when game clock restarts.
2. Offensive foul.
3. Defensive foul.
4. Steal.
5. Dead ball turnover.
6. Shot clock violation.

### Shot clock carryover between turns

1. FCP/HCT to HCO (with no foul or turnover in between).
2. Steal to HCO (with no foul or turnover in between).
3. OREB Kickout to HCO (with no foul or turnover in between).

