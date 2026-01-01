# Animation System Roadmap

> **Status:** ⚠️ **FUTURE PLANNING** - This document describes planned future work, not the current state of the system.  
> **Current System:** The production animation system uses `AnimationRouter`, `AnimationEngine`, and specialized animation systems (Shot, Pass, Rebound, FreeThrow, HCO). See `animation_system.md` for current implementation details.  
> **Last Updated:** 2025-10-21

## Context
The backend simulation already emits authoritative `turns[]` with ordered `steps[]`, rosters, and scoring updates. The Phaser front end can reliably animate half-court sets, inbound plays, free throws, rebounds, and shot attempts, but it is fragile when stitching those pieces together—especially on fast-break possessions and offensive-rebound continuations. The immediate objective is to stabilize transitions while keeping tweening smooth, timings centralized, and game modes (Single, Tournament, Franchise) intact.

## Guiding Principles
- **Hybrid rebuild:** Keep proven low-level utilities (grid conversion, tween primitives, timing config) while replacing brittle orchestration code with a declarative runner.
- **Single source of truth for timing:** All durations/easings remain in `animation_config.js`.
- **Deterministic transitions:** Respect backend order without injecting random offsets or illegal FSM jumps.
- **Instrumentation first:** High-signal, opt-in logging to expose readiness and teleport bugs before refactors.
- **Incremental rollout:** Migrate possession types one at a time behind feature flags/debug toggles.

## Near-Term Actions (0–2 sprints)
1. **Ship DEBUG_ANIM instrumentation**
   - Gate existing noisy logs behind a shared flag.
   - Emit structured traces on step receipt, FSM transitions, and post-step outcomes.
   - Add monotonicity/teleport detectors and document the workflow in `docs/Animation_System/animation_system.md` (see Debugging section).

2. **Patch known blockers**
   - Provide a Phaser timeline compatibility shim so fast breaks no longer crash on `createTimeline`.
   - Fix fast-break outlet orientation so rebound teams attack their own rim.
   - Harden fast-break FSM transitions to avoid illegal `HalfCourt → FastBreakOutlet` hops.

3. **Capture baseline recordings**
   - Save representative seeds for: defensive rebound → half-court reset, defensive rebound → fast break, offensive rebound → putback, offensive rebound → kick-out.
   - Use the new instrumentation to mark where transitions diverge from expected flow.

## Migration Plan (High Level)
1. **Normalize turns into action graphs**
   - Parse each backend turn into deterministic phases (setup, movement, ball events, resolution) keyed by backend timestamps.
   - Attach metadata for upcoming possession type (half-court, fast break, free throw, etc.) to guide FSM decisions.

2. **Introduce a `PossessionRunner` timeline**
   - Consume the normalized graph and schedule tweens via a single Phaser timeline per possession.
   - Emit canonical events for state changes (setup complete, pass started, shot resolved, possession change).
   - Ship behind `FEATURE_POSSESSION_RUNNER` so the legacy orchestrators remain available while we validate parity.

3. **Centralize FSM control**
   - Route all state transitions through the runner, allowing it to look ahead and select the correct next state (e.g., stay in Rebound, enter FastBreak, return to HalfCourt).
   - Remove ad-hoc `safeTransition` calls scattered across helpers.

4. **Port flows incrementally**
   - Start with half-court possessions (existing stable path) under a feature flag.
   - Extend to fast breaks and offensive rebounds, ensuring they reuse the same runner primitives instead of bespoke logic.

5. **Retire legacy orchestrators**
   - After each flow is validated, delete redundant pathways (`animateGameTurns` branches, bespoke fast-break scripts) to reduce maintenance surface.

## Reuse vs. Replace
- **Reuse:** `ballManager.js`, `ballTween.js`, `animation_config.js`, sprite factories, and grid helpers. These already enforce smooth tweening and centralized timing.
- **Replace:** High-level orchestrators (`animateGameTurns`, `turnAnimation` rebound/fast-break branches, free-floating FSM transitions) that currently duplicate logic and introduce race conditions.

## Possession graph format

The runner consumes a normalized possession graph produced by the backend transformer. Each graph is a deterministic DAG:

- **`nodes[]`** – ordered structures with `{ id, phase, stepIndex, payload }`. `phase` enumerates `setup`, `movement`, `ball-event`, `resolution`, and future fast-break specializations.
- **`edges[]`** – directional transitions describing legal successors. Edges capture `{ from, to, condition }` where `condition` can include shot or rebound outcomes.
- **`meta`** – possession-level hints including `possessionType`, `expectedNextType`, and shot/clock timestamps.

Nodes preserve backend timestamps so the runner can compute tween durations deterministically. The format is forward-compatible with additional metadata (e.g., foul sequences) so long as new phases map to the same schema.

## Runner event hooks

`PossessionRunner` exposes a thin event emitter to make instrumentation and HUD updates predictable. When `FEATURE_POSSESSION_RUNNER` is active the following hooks fire:

- **`runner:graph-loaded`** – emitted once a possession graph is parsed and validated.
- **`runner:phase-enter` / `runner:phase-exit`** – payload includes `{ phase, turnId, possessionId }`.
- **`runner:step-start` / `runner:step-complete`** – includes `{ nodeId, stepIndex, activePlayers }`.
- **`runner:ball-transfer`** – fired whenever ball ownership changes, including rebounds and steals.
- **`runner:possession-complete`** – final summary with scoreboard deltas and the announced `expectedNextType`.

Consumers (HUD, overlays, debug panels) should subscribe to these events instead of tapping internal tween helpers. Each hook logs through `DEBUG_ANIM` when animation debugging is enabled to maintain a single source of truth for timeline tracing.

## Risk & Mitigation
- **Complexity risk:** The runner introduces new abstractions—mitigate by shipping instrumentation and feature flags first.
- **Regression risk:** Incremental rollout with baseline recordings lets us compare old vs. new flows turn by turn.
- **Schedule risk:** Prioritize the minimum features needed for tournament stability (half-court, fast break, offensive rebound) before layering exotic scenarios.

## Open Questions / Follow-Ups
- Do we need additional backend hints (e.g., explicit `next_possession_type`) to simplify lookahead logic?
- Should the runner own score/clock updates or delegate to existing HUD utilities?
- When should we expose developer tooling (e.g., playback scrubber) to accelerate regression testing once the runner is in place?

Document owner: Frontend Animation Team
Last updated: 2025-10-21
