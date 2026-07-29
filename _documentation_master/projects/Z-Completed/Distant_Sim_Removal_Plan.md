# Distant Systems — Final Sunset and Removal Plan

**Status:** Complete and archived on 2026-07-28. Deployment smoke/performance validation remains
the normal release gate.
**Scope:** Distant franchise game simulation **and** distant/template CPU training.
**Implementation status:** Full turn-by-turn CPU games and real CPU auto-training are now
authoritative in source. The two semantic environment flags and their routing branches are gone.
The CPU-training compatibility URL and legacy completion/resume names are removed. Legacy momentum
fields remain deliberately deferred. The distant game engine, fabricated
stats builder, constants, EOG branch, tests, calibration script, and live system docs are removed.
No database data has been deleted.

This document supersedes separate game-sim and training removal notes. It is the single execution
plan for both systems.

## Final product decisions

- Every franchise CPU game, including every regular-season and EOS matchup, uses the full
  turn-by-turn engine.
- Every eligible CPU team uses real auto-training through `execute_training`; template training is
  removed.
- `momentum_score`, `distant_win_streak`, and `distant_loss_streak` remain temporarily as
  output-only compatibility fields. Their removal is deferred until the EOG attribute retune;
  they are unrelated to live player/team momentum.
- Historical game documents are not deleted merely because
  `simulation_engine == "distant"`. Database cleanup is a separate, explicitly authorized
  operation.
- The semantic rollout flags are temporary and must disappear after validation:
  - `FRANCHISE_ALL_GAMES_FULL_SIM`
  - `FRANCHISE_ALL_TEAMS_AUTOTRAIN`
- Operational execution controls may remain:
  - `FRANCHISE_CPU_SIM_USE_POOL`
  - `FRANCHISE_CPU_SIM_MAX_WORKERS`

Operational controls may change *how* required work runs, but may not select a different
basketball or training model.

## Systems that must not be confused

| System | Final disposition | Primary identifiers |
|---|---|---|
| Distant game simulation | Remove | `distant_sim_engine.py`, `distant_game_stats.py`, `constants/distant_sim.py`, `simulation_engine == "distant"` |
| Distant/template CPU training | Remove | `distant_training` collection, `_apply_franchise_distant_cpu_training`, `cpu_distant_*` fields |
| Full CPU game simulation | Keep; becomes universal | `_run_franchise_cpu_full_simulation_core`, CPU-week orchestration |
| Real CPU auto-training | Keep; becomes universal | `auto_train_one_cpu_team`, `_run_all_cpu_autotrain`, `execute_training` |
| Live player/team momentum | Keep | `constants/momentum.py`, `utils/player_momentum.py`, `add_momentum` |

## Current routing truth

The replacement paths are complete enough to validate:

- `_franchise_all_games_full_sim()` controls regular-season routing and
  `_should_use_tbt_for_eos_game()` covers both EOS entry points.
- `_franchise_all_teams_autotrain()` redirects the existing CPU-training orchestrator to
  `_run_all_cpu_autotrain()`.
- Real CPU auto-training uses the user training engine and persists player attributes, position
  ratings, team attributes, play effectiveness, scouting effectiveness, training reports, and an
  idempotency marker.

The repository defaults both semantic flags to false. Therefore, source inspection alone cannot
prove that staging or production is already distant-free. Effective deployment configuration and
runtime output must be audited first.

---

## Phase 0 — Deployment-state audit (read-only)

**Purpose:** Establish what staging and production actually run before changing behavior.

1. Record the effective boolean and raw deployment value for:
   - `FRANCHISE_ALL_GAMES_FULL_SIM`
   - `FRANCHISE_ALL_TEAMS_AUTOTRAIN`
   - `FRANCHISE_CPU_SIM_USE_POOL`
   - `FRANCHISE_CPU_SIM_MAX_WORKERS`
2. Inspect recent complete-week logs:
   - full CPU game count
   - distant game count
   - CPU-sim errors/fallbacks
   - elapsed full-week time
3. Inspect recent training logs:
   - `CPU-AUTOTRAIN-TIMING`
   - trained/skipped/error counts
   - any `DISTANT TRAINING` template activity
4. Inspect fresh franchise data for:
   - `simulation_engine` values on CPU games
   - `cpu_autotrain_week`
   - `training_reports.<week>`
   - legacy `cpu_distant_trained_week`
5. Record findings in this document before Phase 1.

### Phase 0 exit gate

- Deployment truth is known for both environments.
- No behavior or database state has been changed.
- Any current error or performance blocker has an owner before the rollout begins.

---

## Phase 1 — Revertible replacement validation

**Purpose:** Run the target world while retaining immediate flag rollback. No code deletion.

1. Enable together in staging:
   - `FRANCHISE_ALL_GAMES_FULL_SIM=1`
   - `FRANCHISE_ALL_TEAMS_AUTOTRAIN=1`
2. Use the process pool only if its deployed spawn path has already been validated. Otherwise use
   the serial/thread execution path for correctness validation first.
3. Run a fresh controlled franchise through a complete season, including:
   - training camp
   - regular-season weeks
   - Practice Squad weeks
   - every EOS phase
   - eliminated-team training exclusions
   - retry/resume paths
4. Validate games:
   - zero new `simulation_engine == "distant"` game documents
   - zero CPU-job rows with engine `distant`
   - out-of-conference games have full box scores and player statistics
   - regular-season standings and every EOS bracket advance correctly
   - no duplicate results on retry
5. Validate training:
   - every eligible CPU FTD reaches `cpu_autotrain_week == week`
   - every trained CPU FTD receives `training_reports.<week>`
   - play and scouting effectiveness can change
   - zero template reads or `DISTANT TRAINING` applications
   - partial retries do not double-train teams
6. Validate performance:
   - full-week CPU simulation stays within the agreed budget
   - CPU auto-training stays within the agreed budget
   - Practice Squad performance does not regress
   - persistence time is measured separately from engine time
7. Repeat the same rollout in production and retain both rollback flags for an agreed bake window.

### Phase 1 exit gate

- At least one fresh full season passes in staging.
- Production bake window passes.
- Zero distant games and zero template training are observed.
- CPU game, training, EOS, retry, and performance requirements are accepted.

**Stop condition:** Any distant output, missing CPU training, EOS progression error, duplicate
training, or unacceptable performance returns the affected environment to the previous flag state.
Do not begin deletion.

---

## Phase 2 — Collapse semantic routing (behavioral SS&S)

**Purpose:** Make the validated replacements authoritative in code before deleting their fallbacks.

**Implementation checkpoint (2026-07-28):** Complete in source. A fresh pre-change reference was
cut with `PYTHONHASHSEED=0`, seed `20260720`, and four CPU games. The matching post-change arm was
byte-identical across all eight team-stat rows and both arms reported zero global RNG leaks.
Focused EOS routing and training-state tests pass. Prototype runs verified regular-season CPU
games, real CPU auto-training, Practice Squad games, and the normal EOS completion path. The
eliminated-team `sim-rest-of-tournament` run also routed through `cpu_full` and advanced the region
bracket. It exposed regulation summaries persisted with `is_final=False`; the two direct
`run_simulation` persistence boundaries now explicitly stamp completed summaries final while
preserving their played quarter. Prototype re-test confirmed regulation `quarter=4`,
`is_final=True`, `source=cpu_full`, successful week advancement, and no distant routing.

### Games

1. Route every non-user CPU matchup directly into the full-job pipeline.
2. Make both EOS entry points unconditionally use full turn-by-turn simulation.
3. Delete the regular-season `is_distant` decision ladder from live routing.
4. Remove ranked-matchup promotion logic; all matchups are already full simulations.
5. Remove `_franchise_all_games_full_sim()` and
   `FRANCHISE_ALL_GAMES_FULL_SIM`.
6. Preserve existing CPU-job idempotency, retry, sequential persistence, and bracket advancement.

### Training

1. Rename `_apply_franchise_distant_cpu_training` to a neutral CPU-training orchestration name.
2. Route it unconditionally to `_run_all_cpu_autotrain`.
3. Add `/franchise/run-training/cpu-train` and move the frontend caller to it. Retain
   `/franchise/run-training/distant-cpu` temporarily as a hidden compatibility alias.
4. Remove `_franchise_all_teams_autotrain()` and
   `FRANCHISE_ALL_TEAMS_AUTOTRAIN`.
5. Defer completion/resume state renames:
   - `training_status.cpu_distant_complete_week`
   - `cpu_distant_trained_week`
   - `distant_training_resume`
6. Do not migrate or dual-write those fields during the routing collapse. Their existing names
   preserve in-progress franchise compatibility and will be handled as a separate B8 cleanup.

### Phase 2 exit gate

- Unsetting either retired semantic flag cannot change behavior.
- All game and training entry points use one authoritative model.
- A fresh season and an in-progress-franchise resume both pass.
- Pool-off and pool-on modes, where supported, produce the same functional workflow.

---

## Phase 3 — Remove the distant game system

**Implementation checkpoint (2026-07-28):** Complete in source. The live engine, fabricated
box-score builder, constants, routing/persistence helpers, EOG uniform override, tournament source
arm, dedicated tests, Monte Carlo artifacts, and live system docs are removed. The output-only
legacy season-momentum calculation was copied unchanged into `BackEnd/utils/season_momentum.py`
because removal of its fields and training allocation is explicitly deferred until the EOG
attribute retune. Historical Mongo game documents are untouched and remain readable.

1. Delete:
   - `BackEnd/distant_sim_engine.py`
   - `BackEnd/models/distant_game_stats.py`
   - `BackEnd/constants/distant_sim.py`
2. Remove from `franchise_routes.py`:
   - distant score wrappers
   - distant FPD/FTD batch-preparation helpers
   - `_run_distant_game_sim`
   - `_persist_distant_franchise_game`
   - distant standings-cache helpers
   - distant game-summary imports
   - distant counters and observability arms
3. Remove the distant branch from end-of-game team-attribute updates and EOG band instrumentation.
4. Remove `"distant"` as a live tournament-progression source.
5. **Deferred until the EOG attribute retune:** remove `momentum_score`,
   `distant_win_streak`, and `distant_loss_streak` from:
   - constants/clamps
   - team initialization and rollover
   - FTD projections
   - training/report payloads
   - API response key lists
   - tests and instrumentation
6. Do not delete historical game documents. Readers should tolerate old documents without keeping
   a live distant execution path.

### Phase 3 exit gate

- No production code can create a distant game.
- Full CPU games still finalize attributes, standings, results, awards, and EOS brackets.
- Focused game-routing, CPU-week, EOG, and EOS test suites pass.

---

## Phase 4 — Remove the distant training system

**Implementation checkpoint (2026-07-28):** Complete in source. There was no remaining live
template branch or collection read after Phase 2. Obsolete template generation/replacement/dry-run
scripts and the retired system document are deleted. The compatibility URL is removed; frontend
and backend use `/franchise/run-training/cpu-train`. Week completion/resume state now uses
`cpu_training_complete_week` / `cpu_training_resume`; per-team idempotency remains
`cpu_autotrain_week`. No Mongo collection was dropped and no data migration was run.

1. Delete the template-delta branch and all reads from `db["distant_training"]`.
2. Remove legacy fields after the Phase 2 compatibility method has completed:
   - `cpu_distant_trained_week`
   - `training_status.cpu_distant_complete_week`
   - distant resume/status names
3. Delete obsolete scripts:
   - `scripts/generate_distant_training_templates.py`
   - `scripts/replace_gob_distant_training_from_staging.py`
   - `scripts/test_distant_training_dry_run.py`
   - template-comparison scripts whose only purpose is distant training
4. Remove distant-training-specific tests and replace them with universal CPU auto-training tests.
5. Optionally drop the MongoDB `distant_training` collection only after:
   - all deployed code versions have stopped reading it
   - rollback to a template-dependent release is no longer required
   - the user explicitly authorizes the destructive database operation

### Phase 4 exit gate

- No production code or operational script reads distant training templates.
- Every eligible CPU team uses real auto-training.
- Idempotency, retry, training camp, elimination, play/scouting training, and reports are covered by
  tests.

---

## Phase 5 — Tests, scripts, and operational cleanup

**Implementation checkpoint (2026-07-28):** Complete locally. Retired tests, Monte Carlo artifacts,
template scripts, and comparison tooling are deleted. EOG analyzers now assume one full-engine
dataset and no longer split or gate on a retired engine marker. Full-sim verification and
pool/determinism tooling remain. Focused CPU-week, EOS, EOG, training-state, and Practice Squad
suites pass. The broad suite is currently blocked by unrelated stale imports and pre-existing
after-steal test drift. Staging full-season and performance measurements remain deployment
validation, not local code cleanup.

1. Delete distant-only tests and Monte Carlo/tuning scripts:
   - `tests/test_distant_sim.py`
   - `tests/test_distant_sim_integration.py`
   - `scripts/distant_sim_monte_carlo.py`
   - generated distant-sim result artifacts
2. Update shared tests that currently exercise both distant and full paths.
3. Update performance and EOG measurement scripts so full simulation and real CPU training are
   assumptions, not required semantic flags.
4. Retain full-sim verification tools, poison-stash/determinism checks, CPU pool tests, and
   auto-training retry tests.
5. Run with `PYTHONHASHSEED=0` and follow the RNG verification rules in
   `Sim_Perf_Capstone.md`.

### Required verification

- Focused CPU full-sim suite
- CPU-week orchestration and retry suite
- CPU auto-training and training-state suite
- EOS/tournament progression suite
- EOG team-attribute suite
- Practice Squad regression suite
- Full relevant backend suite
- Staging full-season smoke run
- Full-week and training performance measurements

---

## Phase 6 — Documentation cleanup

**Implementation checkpoint (2026-07-28):** Complete. Retired system documents are deleted; live
training, EOG, box-score, team-attribute, database, rank/prestige, Practice Squad, tunable, and
performance docs describe the universal full-engine/CPU-auto-training architecture. Historical
studies and this plan are archived under `projects/Z-Completed`. The deferred output-only momentum
fields are explicitly documented and are not confused with live player momentum.

Delete the retired system documents:

- `04_Franchise_Mode_Systems/Distant_Game_Sim_System.md`
- `04_Franchise_Mode_Systems/Distant_Game_Sim_Player_Stats.md`
- `04_Franchise_Mode_Systems/Distant_Team_Training_System.md`

Update live documentation to remove distant routing, momentum/streak fields, template training, and
semantic flags:

- Team Attribute System
- Training System
- Box Score System
- End of Game System
- Tunable Constants
- Attribute Clamp System
- Database/Data Persistence systems
- Franchise Tournament/EOS systems
- Rank and Prestige systems
- simulation-performance and operational runbooks
- `projects/balancing_team_attributes.md`

Keep archived tuning history under `projects/Z-Completed` only when it is clearly marked historical.
Add a note to the Player Momentum System that live player/team momentum is unrelated to—and survives
the removal of—the old distant franchise momentum fields.

---

## Final completion gate

The sunset is complete only when all statements are true:

- Full turn-by-turn simulation is the only live franchise CPU game engine.
- Real auto-training is the only live CPU training engine.
- No semantic environment variable can reactivate distant behavior.
- No live backend/frontend path, worker, or script reads the distant systems.
- New game documents never use `simulation_engine == "distant"`.
- CPU training produces no distant/template markers.
- Regular season, EOS, retries, and in-progress training resumes are verified.
- Performance budgets are accepted.
- Operational documentation describes one authoritative game model and one authoritative training
  model.
- Optional database deletion, if desired, is performed separately with explicit authorization and
  verified backups/targets.

## Execution rule

Do not combine Phase 1 validation with Phase 3/4 deletion in one deployment. The only intentional
behavior change is replacement activation and routing collapse. Code deletion follows only after
the replacement world has been observed and accepted.
