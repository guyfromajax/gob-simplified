# Live Clock System

## Purpose
Define the current, implemented clock contract between backend and frontend for:
- game clock
- shot clock
- per-turn elapsed timing

This document reflects the active code path (`BackEnd/api/api.py`, `BackEnd/models/turn_manager.py`, `FrontEnd/static/js/phaser/gameScene.js`, `FrontEnd/static/js/phaser/animation/AnimationRouter.js`, `FrontEnd/static/js/phaser/utils/gameClock.js`).

## Current Authority Model
- Backend is authoritative for turn-level clock state.
- Frontend renders clocks from backend turn contracts.
- Frontend no longer treats router-level live clock control as primary when contract fields exist.

## Turn Clock Contract (Per Turn)
Every turn is expected to carry:
- `clock_start`
- `clock_end`
- `shot_clock_start`
- `shot_clock_end`
- `shot_clock_reset`

Primary source:
- `BackEnd/models/turn_manager.py` in `update_clock_and_possession()`

Fallback source:
- `BackEnd/api/api.py` simulate-turn response enrichment pass fills missing clock fields for synthetic/batch turns without overwriting existing values.

## Backend Clock Processing
In `update_clock_and_possession()`:
1. Capture pre-mutation values:
- `clock_start = game_state["time_remaining"]`
- `shot_clock_start = game_state["shot_clock_remaining"]`
2. Apply `time_elapsed` (with legal cap and no-impact handling).
3. Update game clock and shot clock.
4. Apply shot clock reset rules and set `shot_clock_reset`.
5. Write contract fields to turn payload.

No-impact turns (clock holds):
- `FREE_THROW`
- `SIDE_INBOUND`
- `BASELINE_INBOUND`
- `TIMEOUT`

## Frontend Clock Consumption
In `gameScene.js` `updateScoreboard(turn)`:
- If contract fields exist:
1. `syncWithBackend(clock_start)`
2. `runToTarget(clock_end)` (or hold if equal)
3. same pattern for shot clock
- If contract fields are missing:
fallback to legacy `time_remaining`/`clock` and `shot_clock_remaining`.

Clock engine:
- `createGameClock()` in `gameClock.js`
- default tick interval: `350ms` per game-second
- supports `runToTarget()` and hard sync.

## Router Clock Guard (Important)
`AnimationRouter` contains legacy clock control logic, but now:
- when game clock contract fields are present, router does not control game clock
- when shot clock contract fields are present, router does not control shot clock

This avoids dual-writer clock drift between router and scoreboard update flow.

## Timeout Click Reconciliation
In `/api/call-timeout`:
- reconcile to the more elapsed user-visible values before save:
  - effective game time: min(backend, displayed)
  - effective shot clock: min(backend shot, displayed shot, effective game time)
- timeout response includes shot clock contract context.

## Batch Turns
When multiple subturns are returned:
- backend emits `result_type: "BATCH"` with `batch_turns`.
- chain verification logs warning if `clock_end` of subturn N does not match `clock_start` of N+1.
- API enrichment pass fills missing clock contract fields per subturn.

## Speed Input for Elapsed Computation
- Frontend sends `game_speed_px_per_sec` on `/api/simulate-turn`.
- Backend stores normalized value in `gm.game_state["game_speed_px_per_sec"]`.
- Movement-based elapsed helpers use this value where integrated.

## Current Known Gaps
- Shot clock expiry enforcement at 0 is still inconsistent in gameplay behavior.
- Some transition flows remain sensitive to missing/partial animation payloads.
- Final-shot visual pacing may still feel off in edge sequences even when backend boundary decisions are correct.

## Operational Debug Signals
Backend logs:
- `🧭 [SHOT CLOCK BOUNDARY TRACE] ...`
- `🧭 [ZERO CLOCK TRACE] ...`
- `Batch clock chain mismatch ...`

Frontend logs:
- `🔵🔵🔵🔵🔵 Turn #..., Frontend Actual Clock Elapsed = ..., Backend Estimate Time Elapsed = ..., Delta = ...`

