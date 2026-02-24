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
Single writer for clock state:
- `FrontEnd/static/js/phaser/gameScene.js`
- function: `updateScoreboard(turn)`

Router ownership:
- `AnimationRouter` does not mutate clock state.

## Frontend Contract Gate
Clock countdown only runs when all are true:
- `turn.clock_contract_source === "native"`
- finite `clock_start` and `clock_end` (game clock)
- finite `shot_clock_start` and `shot_clock_end` (shot clock)

Game clock behavior:
1. `syncWithBackend(clock_start)`
2. if `clock_start > clock_end`: `runToTarget(clock_end)`
3. else: hold at `clock_end`

Shot clock behavior:
1. `syncWithBackend(shot_clock_start)`
2. if `shot_clock_start > shot_clock_end`: `runToTarget(shot_clock_end)`
3. else: hold at `shot_clock_end`

If native contract is missing:
- hold clock state for that turn
- emit warning log

## Critical Stabilizer (Implemented)
`updateScoreboard()` is called in two contexts:
1. per-turn animation finalization (contract-bearing turn payload)
2. post-turn summary refresh (scores/fouls/timeouts aggregate payload)

The summary refresh now passes:
- `_skipClockSync: true`

When `_skipClockSync` is true:
- `updateScoreboard()` updates scores/fouls/timeouts only
- game clock and shot clock are not started/stopped/synced

This prevents summary refreshes from overriding contract-driven countdown decisions.

## Tick Cadence
- `createGameClock()` tick interval remains fixed at `350ms` per game-second.
- This refactor does not change animation speed functions.

## Expected Behavior After This Update
1. Impact turns with native contract and `start > end`:
- both clocks count down normally for that turn window

2. No-impact turns with native contract and `start == end`:
- both clocks hold steady (no countdown)

3. Summary/state refresh calls between turns:
- scores/fouls/timeouts/period update
- clock run/hold state is unaffected

4. Reduced false warnings and oscillation:
- no more clock stop/start flips caused by non-contract summary payloads

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
