# CPU Auto-Train — design brief

**Status:** Completed and archived. Implemented as authoritative; template training was removed on 2026-07-28.

**Goal:** replace the CPU **Distant Training System** with real per-team auto-train, so all 128
teams train the same surfaces the user does. Fixes a documented competitive-balance bug and runs
in parallel via the existing process pool.

**Status:** design approved 2026-07-21. Not yet built. Flag-gated, default OFF.

## Why (not just cleanup)

`Training_Comparison.md`: distant training updates player/team attrs + position ratings, but
**never** offensive-play effectiveness or defensive-scouting effectiveness. User Auto-Train trains
all of those. Over a season the user compounds a play/defense advantage CPU teams literally cannot
build → the blowout pattern (Lancaster `shot_threshold` 0.00 vs CPU avg 71). Running real
auto-train for CPU teams closes the gap.

## What changes

| Team | Today | After |
|---|---|---|
| User (1) | manual/auto real training | **unchanged** — keeps manual control |
| CPU (127) | distant template deltas (no play/scouting) | **real `execute_training`** with a per-team auto-train roll |

Each CPU team makes its **own independent roll** — its own allocation + its own coaching focus. No
universal/shared roll.

## Architecture

**Unit of work — auto-train ONE cpu team** (self-contained, parallelizable):
1. Load that team's FPD roster + FTD (plays / strategy / playbook / scouting / team_attributes)
2. `allocations = generate_random_training_allocations(points)` — **exists** at
   `franchise_routes.py:1955` (defined, no live callers — the waiting stub). `points` = 30 (wk-1
   camp) else 24. Per-team roll.
3. `coaching_focus = rng.choice(auto_train_focus_options)` — per-team roll
4. `execute_training(players, team, allocations, coaching_focus, plays_data=…, strategy_settings=…,
   playbook_settings=…, scouting_data=…, playbook_training_mode="current-playbooks",
   skip_pre_training_depreciation=is_first_training)` — the **same pure engine** the user uses
   (`training_execution_v2.py:49`; reads/writes only its dict args, no DB, no other team)
5. Recompute `compute_position_ratings` per player
6. Write results to **that team's** FPD (`{franchise_id, player_id}`) + FTD
   (`{franchise_id, team_id}`) — disjoint from every other team

**Two tiers** (the safety boundary):

| Tier | Work | Execution |
|---|---|---|
| **Parallel** | 127 CPU auto-trains (pure `execute_training` + disjoint per-team writes) | process pool — reuse `BackEnd/utils/cpu_week_pool.py` |
| **Serialized once (orchestrator)** | franchise-doc `training_status`/`latest_training`; recruiting invites (wks 20–26, `_process_weekly_recruiting_invites`); camp cuts (wk 1); community-engagement; PS-game trigger | after the parallel batch — **never inside the per-team loop** |

The serialized items touch shared docs (the single `db.franchises` doc, league-wide recruiting)
and must run exactly once.

## Key risks / decisions

1. **⚠️ Training is DELTA-based, not idempotent like games.** A game re-runs safely (overwrite);
   training *adds* to attributes, so a blind retry **double-trains**. Carry over distant training's
   per-FTD marker (`cpu_distant_trained_week` → e.g. `cpu_autotrain_week`): skip a team already
   trained this week; set the marker only after its FPD+FTD writes succeed. The pool failure-ladder
   must **not** blindly re-run a half-written team — retry only teams with no marker set. This is
   the one genuinely tricky part; a bug here silently corrupts attributes league-wide.

2. **RNG.** `execute_training` draws from the global `random` module at ~60 sites. In separate pool
   processes that works but is non-reproducible and lights the leak guard. Give training its **own
   dedicated stream** `training_rng` (same pattern as `sim_rng`, NOT shared with it) — training runs
   concurrently with sims, so sharing `sim_rng` would couple training activity to sim draws (the
   pymongo-non-determinism disease, readmitted). Seed per team `seed = base + team_index` →
   independent rolls AND reproducible for balance auditing. General rule: each independent subsystem
   gets its own RNG stream.

3. **Coordination with PS games.** Same trigger (user runs training) wants two pool batches: 127
   auto-trains + 24 PS games. Run as two sequential pool batches sharing one serialized post-step.
   Worker budget must respect that the **user is actively in their session** (unlike the CPU week,
   which owns the box).

4. **Execution/timing model.** 127 trainings are lighter than games (no turn-by-turn), likely
   ~sub-second each → the whole batch may fit in one request, but PS already uses background+poll
   (`max_games=1`); fold into that phased flow rather than a single long blocking request.

## Rollout

`FRANCHISE_ALL_TEAMS_AUTOTRAIN`, **default OFF** — safe deploy, env-flippable, distant training
stays as instant fallback (same pattern as the CPU-game sunset `FRANCHISE_ALL_GAMES_FULL_SIM`).

## Build order (phased — correctness before parallelism)

1. **`auto_train_one_cpu_team(...)`** behind the flag, run **serially** (127 in a loop). Verify a
   CPU team now trains play/scouting effectiveness (the balance fix) — compare deltas to
   `scripts/training_delta_dry_run.py`. No parallelism yet.
2. **Parallelize** across the pool once single-team output is proven correct.
3. **Coordinate** with PS games + the serialized post-steps.
4. **RNG → dedicated `training_rng`** (its own stream, NOT sim_rng) for reproducibility (can fold into 1).

Do NOT parallelize before step 1 proves training correctness — the delta/idempotency issue means a
bug corrupts every team's attributes, far worse than a wrong game score.

## Pointers

- Engine: `BackEnd/models/training_execution_v2.py:49` `execute_training` (pure)
- Orchestrator to mirror: `_run_franchise_training_impl` (`franchise_routes.py:12620`) — user load
  → execute → ratings → FPD/FTD persist
- Allocation stub: `generate_random_training_allocations` (`franchise_routes.py:1955`)
- Distant system to sunset: `_apply_franchise_distant_cpu_training` (`franchise_routes.py:12133`)
- Dry-run model / verifier: `scripts/training_delta_dry_run.py` (`_auto_train_allocations`,
  `_simulate_user_training`)
- Pool: `BackEnd/utils/cpu_week_pool.py`
