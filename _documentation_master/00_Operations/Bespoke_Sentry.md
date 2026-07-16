# Bespoke Sentry

This file tracks temporary, bespoke Sentry wiring added for targeted debugging. Remove entries once the underlying issue is fixed and verified, so these hooks do not become permanent noise.

## Active Hooks

### UESS playback repeated same step

- **Status:** Active
- **Date added:** 2026-07-16
- **Code location:** `FrontEnd/static/js/phaser/animation/animationPlayback.js`
- **Sentry message:** `UESS playback repeated the same animation step`
- **Tags:**
  - `gob.area = uess_playback`
  - `gob.issue = repeated_same_step`
  - `gob.turn_type`
  - `gob.result_type`
- **Why it exists:** A Fast Break playback instance appeared to nearly infinite-loop by repeatedly resolving the same `currentIndex` instead of advancing through `step.end.next`.
- **What it captures:** `turnIndex`, `currentIndex`, `repeatCount`, `stepsExecuted`, `stepCount`, and the resolved `next` payload. It also logs a copyable `[UESS_PLAYBACK_LOOP_GUARD_JSON]` line in the browser console.
- **Spam guard:** Reports once per `turnIndex/currentTurn/currentIndex` key.
- **Removal condition:** Remove after the bad `next` payload/source emitter is identified, fixed, and prototype testing shows no repeated-step Sentry events across representative Fast Break coverage.

### Fast Break UESS fallback / no animation steps

- **Status:** Active
- **Date added:** 2026-07-16
- **Code location:** `BackEnd/engine/fb_uess_debug.py`
- **Sentry message:** `Fast Break UESS emitted fallback/no animation steps`
- **Tags:**
  - `gob.area = fb_uess`
  - `gob.issue = fast_break_uess_fallback`
  - `gob.fast_break_play`
  - `gob.result_type`
  - `gob.fallback_reason`
  - `gob.next_play_type`
- **Why it exists:** FB UESS migration validation still has rare live edge cases to catch, especially Rim Runner dead-ball, Triangle foul, and block outcomes. The guard reports when a live Fast Break returns through the fallback/no-`animation_steps` path.
- **What it captures:** `game_id`, `fast_break_play`, `result_type`, `next_play_type`, `step_count`, `fb_step_state_count`, clock burn, elapsed time, first/final ball owner, final coord count, fallback reason, and emitter fallback reason.
- **Noise guard:** Skips full simulations and summaries without a real `game_id`, so background CPU/full-sim validation noise does not report. Reports once per `game_id/play/result/fallback/step_count/next_play_type` key.
- **Removal condition:** Remove after representative live Fast Break testing either confirms no events across the remaining edge cases or identifies/fixes the emitter path producing the fallback.

## Removed Hooks

None yet.
