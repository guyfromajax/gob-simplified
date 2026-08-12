# EOG Persistence — Tier 3 Work Plan

**Status:** Active, partially implemented. Phase 0 instrumentation is shipped; Phases 1–3 are not
implemented. Do not start semantic refactoring until the Phase 0 traffic evidence and a fresh
post-N+1-fix timing baseline are captured.

**Scope:** CPU-week persistence in `_complete_week_finish_cpu_and_persist`
(`BackEnd/api/franchise_routes.py`). Tiers 1–2 and the batched static-team lookup fix are already
shipped. The current measured history and verification rules live in
[`Sim_Perf_Capstone.md`](Sim_Perf_Capstone.md).

## Current state

The CPU simulation itself runs in parallel, but successful full-game results still pass through a
sequential persistence loop. That loop writes the game, calls `stat_updater.finalize_game`, records
the result, applies EOG team-attribute/play/scouting updates, and applies momentum.

The canonical `games.eog_inputs` snapshot already exists and team-attribute formulas consume it,
but `update_team_attributes_after_game()` first reloads the game and only then builds/persists the
snapshot. Other consumers still perform their own game reads and `_id` resolution:

| Consumer | Current reason for reading |
|---|---|
| `stat_updater.finalize_game` | Stat rollup, idempotency claims, and legacy `_id` fallback/freshness checks |
| `_save_game_result` | Result persistence and legacy `_id` resolution |
| `update_team_attributes_after_game` | Richer-doc selection, `eog_inputs`, team deltas, and play/scouting decay |

These reads include February 2026 guardrails from the string/ObjectId duplicate-game incident.
They may only be bypassed where production evidence proves the fallback is dormant.

## Goal

For the trusted CPU-week caller, construct one frozen EOG work item from the already-available
in-memory summary, preserve every existing write and idempotency guarantee, and reduce redundant
reads/writes. After equivalence is proven, overlap only persistence work demonstrated to be
independent and thread-safe.

This extends rather than replaces the canonical EOG rule in
[`End_Of_Game_System.md`](../06_Gameplay_Systems/End_Of_Game_System.md): team-attribute calculations
read from one frozen `games.eog_inputs` snapshot.

## RNG constraint

EOG attribute changes and offensive/defensive effectiveness decay consume the global `random`
stream. This has two consequences:

1. A seeded old/new comparison is exact only if draw count and order are identical.
2. Moving those draws into concurrent threads would make cross-game draw assignment
   schedule-dependent. Phase 3 therefore cannot simply thread the current whole persistence body.

Keep the existing serial draw order for the equivalence refactor. Before parallel flush, either
materialize all RNG-dependent outputs serially or separately approve and verify a dedicated,
per-game EOG RNG design. A dedicated RNG migration is not implicitly authorized by this plan.

## Phase 0 — instrumentation and evidence (implemented; evidence gate open)

The following log-only instrumentation is present:

- `[EOG-IDGUARD-FIRED]` in `stat_updater.finalize_game` when ObjectId fallback is required.
- `[EOG-IDGUARD-FIRED]` in `update_team_attributes_after_game` when a duplicate exists or the
  ObjectId document wins richer-doc selection.
- `[EOG-IDGUARD-FIRED]` in `_save_game_result` when its ObjectId fallback is required.
- `[CPU-PERSIST-TIMING]`, `[CPU-PERSIST-SUBTIMING]`, and `[FINALIZE-SUBTIMING]` for the persistence
  baseline and attribution.

Required evidence before Phase 1:

- Capture counts by `site` across representative regular-season and EOS week advances.
- Record whether any guard fired and preserve every firing guard in the trusted path.
- Capture a fresh timing baseline after the shipped `_build_franchise_team_maps_from_ftd` batch
  fix; the original ~95-second loop and ~82-second `finalize_game` figures are historical, not a
  valid current baseline.
- Confirm `[EOG-ATTR-FAILURE]` remains zero during the sample.

## Phase 1 — trusted one-snapshot work item (not started)

- Define a CPU-week-only work item containing the frozen game summary, canonical IDs, scores,
  week, franchise ID, and prebuilt `eog_inputs`.
- Persist the game and `eog_inputs` together rather than writing the game and then rereading it to
  construct the snapshot.
- Add optional trusted-input entry points to shared functions. Defaults must preserve today's
  behavior for user games and tournaments.
- Bypass only `_id` fallback reads proven dormant in Phase 0. Preserve any guard that fired.
- Preserve postseason weeks 27–34 exactly: write `team_attribute_changes: {}` and do not mutate
  EOG team attributes or play/scouting effectiveness.
- Preserve global RNG call count and order.
- Accumulate compatible updates where doing so is byte-equivalent; do not assume separate FTD
  operations can be merged without proving Mongo update semantics and clamping order match.

## Phase 2 — equivalence gate (not started)

Build a harness that applies current and proposed EOG paths to isolated copies of the same inputs
under identical RNG state, then compares all resulting game, FPD, FTD, and franchise writes.

Coverage must include:

- regular season and postseason-freeze games;
- string-ID and retained legacy ObjectId/duplicate-doc cases;
- repeat application/idempotency behavior;
- EOS bracket/result synchronization;
- one normal full CPU week with all matchups represented.

Assert identical RNG state after each path. If a surface intentionally changes draw count/order,
it is outside the equivalence refactor and requires poison testing plus an explicitly approved
basketball change.

## Phase 3 — safe parallel flush (not started)

- First separate serial RNG-dependent calculation and shared/idempotency claims from I/O-only
  writes.
- Inventory write keys, not just team membership. Team-specific FTD/FPD writes are usually
  disjoint because each team plays once, but franchise results, CPU-job state, aggregate claims,
  and EOS bracket structures are shared.
- Parallelize only the proven-disjoint I/O units with a bounded thread pool. PyMongo is
  thread-safe, but verify the Mongo connection-pool capacity is at least the chosen worker count.
- Keep shared writes serial or atomic, then run the normal week-completeness/finalization gate.
- Re-run the Phase 2 equivalence suite plus failure-injection tests before enabling the path.
- Ship behind a kill switch and compare timing/error telemetry before changing the default.

## Exit criteria

- No dropped, duplicated, or double-applied game/stat/team updates.
- Byte-equivalent writes and unchanged RNG state for the behavior-preserving path.
- Postseason freeze and EOS bracket behavior unchanged.
- All retained `_id` guardrails still work under explicit legacy fixtures.
- A measured end-to-end improvement on the current staging baseline large enough to justify the
  added orchestration complexity.

Integrity remains more important than the latency target. If the current post-fix measurement no
longer justifies Tier 3, retain Phase 0 telemetry and close the optimization without refactoring.
