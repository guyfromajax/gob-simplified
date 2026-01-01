# Animation Debugging

The front-end animation stack now exposes a shared `DEBUG_ANIM` flag that
controls verbose logging across the Phaser animation helpers. By default the
flag is disabled. Toggle it at runtime from the browser console:

```js
// Enable detailed animation tracing and the new runner in one go
window.DEBUG_ANIM = true;
window.FEATURE_POSSESSION_RUNNER = true;

// Disable everything when you are done
window.DEBUG_ANIM = false;
window.FEATURE_POSSESSION_RUNNER = false;
```

Both flags are also exposed via `debugFlags.js` for module consumers:

```js
import {
  setAnimationDebugEnabled,
  setPossessionRunnerEnabled,
} from 'FrontEnd/static/js/phaser/utils/debugFlags';

setAnimationDebugEnabled(true);
setPossessionRunnerEnabled(true);
```

Enabling the flag unlocks a series of structured diagnostics that are emitted
with the `ANIM` prefix. These logs summarize how possessions, steps, and ball
transitions are processed while a simulation plays out.

## Step ingestion telemetry

Both `animateGameTurns` and `runFastBreakSequence` emit a step record for every
backend payload they consume. Each entry includes:

- `turnIndex`, `turnId`, and the `possessionId`
- `stepIndex` and the first timestamp observed for that step
- A list of `{ playerId, action }` pairs participating in the step

The step logger (shared by the legacy orchestrators and the runner) enforces a
per-possession monotonicity check. If a subsequent step reports a lower
`stepIndex` than the last processed value for that possession you will see a
warning similar to:

```
ANIM: stepIndex regression { fromState: ..., lastStepIndex: 12, stepIndex: 10, ... }
```

Use this to quickly spot gaps or out-of-order movement data from the simulator.
When `FEATURE_POSSESSION_RUNNER` is enabled the same warning will also include
the offending node id and graph edge so you can track the regression back to
the possession graph.

## Runner-specific tracing

`PossessionRunner` adds a layer of instrumentation that surfaces under the
`ANIM` prefix when both `DEBUG_ANIM` and `FEATURE_POSSESSION_RUNNER` are true.
Key entries include:

- `ANIM runner:graph-loaded` – prints the possession id, node/edge counts, and
  whether the graph passed validation.
- `ANIM runner:phase-enter` / `ANIM runner:phase-exit` – documents which phase
  is active and how long the previous phase took.
- `ANIM runner:step-start` / `ANIM runner:step-complete` – log the node id,
  backend step index, and resolved tween duration. Use these to correlate
  runner scheduling with sprite motion.
- `ANIM runner:ball-transfer` – highlights ball ownership changes, including
  assists, rebounds, and turnovers detected mid-sequence.

Each runner hook mirrors the event emitter outlined in
`docs/Animation_System/animations-roadmap.md`. If you only see the events without their paired
`ANIM` log entries, double-check that `DEBUG_ANIM` and
`FEATURE_POSSESSION_RUNNER` are both enabled.

## Tween and pass summaries

Three hotspots now produce post-action summaries:

- `animateStep` logs `ANIM step summary` entries when each player tween
  completes, including the resolved owner, `passInFlight`/`ballDetached` state,
  and any scoreboard delta detected for the turn.
- `tweenPlayerTo` produces `ANIM tween summary` records with the tween
  duration, easing, start/target coordinates, and the same ownership metadata.
- `runPass` emits `ANIM pass summary` once the pass resolves (or if it aborts),
  indicating the involved player ids, pass duration, and ball state.

All three helpers compare the actual sprite delta against the planned tween
length. When the ball or sprite travels further than expected you will see a
one-line warning:

```
ANIM teleport suspicion { plannedDistance: 180, actualDistance: 360, ... }
```

The warning highlights the IDs involved along with the start/target
coordinates so you can trace unexpected teleports. When the runner is active it
also annotates the graph node that triggered the discrepancy. Treat repeated
teleport warnings as blockers before promoting the runner flag to wider
audiences.

## FSM transition tracing

Every state-machine transition now flows through a shared helper that reports
`{ fromState, toState, event, ...payload }` when `DEBUG_ANIM` is active. This
covers both `safeTransition` calls and any direct `transition(...)` invocations
on the scene state machine, giving you a chronological view of inbound/outlet
state changes.

## Scoreboard deltas

Whenever a turn updates the scoreboard, the debug logger records the delta in
`ANIM: score update` along with the full score snapshot. The latest delta is
also folded into the step, tween, and pass summaries so you can correlate ball
movement with scoring plays.

## Tips

- The logs stream to `console.log` only when `DEBUG_ANIM` is true. Existing
  feature flags such as `PASS_DEBUG` and `DebugFlags.OUTLET` still gate their
  respective sections but now require `DEBUG_ANIM` to be enabled before they
  print.
- Use `DebugFlags.ANIM` / `DebugFlags.FEATURE_POSSESSION_RUNNER` from the
  console to confirm flag state if you suspect conflicting overrides.
- You can reset any accumulated step state by toggling either flag off and back
  on; new possessions start with a fresh monotonicity tracker.
