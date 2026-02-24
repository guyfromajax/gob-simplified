# Real Time Clock System

## Purpose
Define the active, backend-authoritative clock contract and frontend execution model for:
- game clock
- shot clock
- turn-level elapsed application

## Current Source of Truth
- Backend is authoritative for clock state at turn boundaries.
- Frontend never infers countdown direction from `result_type`.
- Frontend countdown decisions come from explicit turn contract fields.

## Backend Turn Contract
Every turn should carry:
- `clock_start`
- `clock_end`
- `shot_clock_start`
- `shot_clock_end`
- `shot_clock_reset`
- `clock_contract_source`

Native contract source:
- `BackEnd/models/turn_manager.py` in `update_clock_and_possession()`
- sets `clock_contract_source = "native"`

Fallback contract source:
- `BackEnd/api/api.py` enrichment for turns that bypass native stamping
- sets `clock_contract_source = "fallback"` only when missing

## Backend Clock Application
In `update_clock_and_possession()`:
1. Capture pre-mutation values (`clock_start`, `shot_clock_start`).
2. Apply authoritative `time_elapsed` with legal cap.
3. Update `time_remaining` and `shot_clock_remaining`.
4. Apply shot-clock reset rules.
5. Write post-mutation values (`clock_end`, `shot_clock_end`) and contract source.

No-impact turn families (clock hold behavior):
- `FREE_THROW`
- `SIDE_INBOUND`
- `BASELINE_INBOUND`
- `TIMEOUT`

## Frontend Clock Owner Model
Single writer path for clock state:
- turn-start apply in `FrontEnd/static/js/phaser/animation/turnPreparation.js`
  - `prepareTurnForAnimation(...)`
- turn-end clamp in `FrontEnd/static/js/phaser/animation/turnPreparation.js`
  - `finalizeTurnAfterAnimation(...)`
- `gameScene.updateScoreboard(turn)` is scoreboard/state only during turn finalization (`_skipClockSync: true`).

Router ownership:
- `AnimationRouter` does not mutate clock state.

## Frontend Contract Gate
Clock countdown only runs when all are true:
- `turn.clock_contract_source === "native"`
- finite `clock_start` and `clock_end` (game clock)
- finite `shot_clock_start` and `shot_clock_end` (shot clock value sync)

Shared run/hold behavior (both clocks):
1. `syncWithBackend(clock_start)`
2. Compute one run/hold gate from game clock: `clock_start > clock_end`
3. Apply that run/hold mode to both clocks
4. Use each clock's own end target (`clock_end`, `shot_clock_end`)

If native contract is missing:
- hold clock state for that turn
- emit warning log

Turn-boundary clamp:
- at end of each turn, both clocks are force-stopped
- if native contract exists, both are hard-synced to `clock_end` / `shot_clock_end`
- prevents countdown bleed from turn N into turn N+1

## Critical Stabilizer (Implemented)
`updateScoreboard()` is called in multiple contexts:
1. per-turn animation finalization
2. post-turn summary refresh (scores/fouls/timeouts aggregate payload)

The summary refresh now passes:
- `_skipClockSync: true`

When `_skipClockSync` is true:
- `updateScoreboard()` updates scores/fouls/timeouts only
- game clock and shot clock are not started/stopped/synced

This prevents summary refreshes/finalization from overriding turn-start contract decisions.

## Tick Cadence
- `createGameClock()` tick interval remains fixed at `350ms` per game-second.
- This refactor does not change animation speed functions.

## Expected Behavior After This Update
1. Impact turns with native contract and `start > end`:
- both clocks begin countdown at turn start and stop at turn end target

2. No-impact turns with native contract and `start == end`:
- both clocks hold steady (no countdown)

3. Summary/state refresh calls between turns:
- scores/fouls/timeouts/period update
- clock run/hold state is unaffected

4. Reduced turn-attribution inversion:
- countdown no longer bleeds from one turn window into the next

## Known Remaining Risk Areas
- Any backend flow that emits fallback-only turns for impact cases will still hold (by design of native-only gate).
- Shot clock 0 enforcement behavior depends on backend boundary logic, not this frontend stabilizer.

## Debug Signals
Frontend:
- `⏱️ Missing native game clock contract; holding clock for this turn`
- `⏱️ Missing native shot clock contract; holding shot clock for this turn`

Backend:
- `🧭 [SHOT CLOCK BOUNDARY TRACE] ...`
- `🧭 [ZERO CLOCK TRACE] ...`
- `Batch clock chain mismatch ...`
