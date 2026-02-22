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
- For each executed skeleton step: `step_seconds = random.randint(1,5)`
- Turn elapsed: sum of step seconds up to the resolution point
- Cap per turn: `min(sum_steps, 30)`

Execution:
- Backend computes authoritative `time_elapsed`
- Frontend animates steps in sync with the step timeline
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
4. Keep existing scoreboard updates; add sync call at turn boundaries using backend `time_remaining`.

### Phase 3: Animation Synchronization
Goal: align visual countdown progression with movement/action progression.

1. Skeleton turns:
- use step timeline so offense and defense remain synchronized to the same step clock.
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
