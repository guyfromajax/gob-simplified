# Distant Systems — Removal Plan (game sim + training)

**Status (2026-07-26): NEITHER is actually sunset.** Both are staged behind **default-OFF flags that are unset in prod**, so both are still live:
- Distant **game sim** — flag `FRANCHISE_ALL_GAMES_FULL_SIM` ([franchise_routes.py:3983](../../BackEnd/api/franchise_routes.py#L3983)). Out-of-conf regular-season + EOS games still run the distant engine.
- Distant **training** — flag `FRANCHISE_ALL_TEAMS_AUTOTRAIN` ([franchise_routes.py:3996](../../BackEnd/api/franchise_routes.py#L3996)). CPU teams still train from the `distant_training` template collection; the real per-team auto-train replacement (`_run_all_cpu_autotrain`) has never been enabled.

⚠️ Removing either before flipping its flag + validating the replacement breaks prod (no game scorer / no CPU training).

**Decisions (owner):** sequence = **sunset-then-remove** (both); `momentum_score` + `distant_win/loss_streak` = **remove entirely**; EOS games = **force full turn-by-turn sim**; distant **training** = **remove** (folded into this plan).

## ⚠️ Naming — the "distant"/"momentum" collisions
| Thing | Scope | Identifiers |
|---|---|---|
| Distant **game sim** | **REMOVE** (flag `FRANCHISE_ALL_GAMES_FULL_SIM`) | `distant_sim_engine.py`, `distant_game_stats.py`, `constants/distant_sim.py`, `simulation_engine=="distant"` |
| Distant **training** | **REMOVE** (flag `FRANCHISE_ALL_TEAMS_AUTOTRAIN`; separate system, separate track) | `_apply_franchise_distant_cpu_training`, `distant_training` collection, `cpu_distant_*` fields, `Distant_Team_Training_System.md` |
| Player `team_momentum` (engine, −50..+50) | **KEEP** (unrelated to FTD `momentum_score` −10..10) | `constants/momentum.py`, `utils/player_momentum.py`, `add_momentum` |

---

## Phase A — Complete both sunsets (behavioral, revertible, NO deletion)
Prove the real replacements work everywhere before deleting the fallbacks. Flip **both** flags together (they jointly make CPU teams "real"), keep flip-back until validated.

- **A1. Games → full TbT** under one revertible flag:
  - Regular season (Path A): set `FRANCHISE_ALL_GAMES_FULL_SIM=1` + `FRANCHISE_CPU_SIM_USE_POOL=1` in prod.
  - EOS is **not** flag-covered today (Path A EOS block [6466-6540](../../BackEnd/api/franchise_routes.py#L6466-L6540); Path B `sim_rest_of_tournament` [14737-14790](../../BackEnd/api/franchise_routes.py#L14737-L14790), both via `_should_use_tbt_for_eos_game`). Small change: make `_should_use_tbt_for_eos_game` return True when `_franchise_all_games_full_sim()` — one flag forces every game to full sim, still revertible.
- **A2. CPU training → real auto-train:** set `FRANCHISE_ALL_TEAMS_AUTOTRAIN=1` in prod → `_apply_franchise_distant_cpu_training` routes to `_run_all_cpu_autotrain` (parallel per-team, `cpu_week_pool.py` autotrain worker) instead of `distant_training` templates.
- **A3. Validate a full season** with all flags ON (staging / controlled franchise): pool perf within [[project_sim_perf_optimization]] targets for 63+ full games/wk; out-of-conf + EOS box scores sane; `simulation_engine=="distant"` count == 0; CPU teams show real play/scouting-effectiveness training deltas (not template deltas); no `distant_training` reads.
- **A4. Bake** in prod for an agreed window; confirm zero distant games + zero distant-template training in logs.
- **Synergy:** capture the EOG band-measurement season (see [[project_eog_attr_retune]]) with the flags ON, so tuning data reflects the distant-free target world (no `distant_uniform` bands; CPU teams trained realistically).

## Phase B — Delete distant code (mechanical, after A proven)
- **B1. Routing collapse:** delete the `is_distant` ladder ([6543-6644](../../BackEnd/api/franchise_routes.py#L6543-L6644)) + EOS distant block (6466-6540) + Path B distant block (14737-14790); remove flag `_franchise_all_games_full_sim` (behavior becomes unconditional full-sim), `distant_sim_should_promote_ranked_fullsim`, `_cpu_distant_count` timing arm.
- **B2. Delete whole files:** `BackEnd/distant_sim_engine.py`, `BackEnd/models/distant_game_stats.py`, `BackEnd/constants/distant_sim.py` (momentum removed too → nothing survives).
- **B3. Delete franchise_routes wrappers:** `_distant_sim_*` helpers (2829-3030), `_run_distant_game_sim`, `_persist_distant_franchise_game`, `_distant_sim_persist_momentum_score_updates`, the `build_distant_game_summary` import (63).
- **B4. Prune shared functions' distant arms** (do NOT delete the functions):
  - `update_team_attributes_after_game`: remove `is_distant_sim` ([1582](../../BackEnd/api/franchise_routes.py#L1582)) + the distant efficiency branch (1754-1770) + the `is_distant_sim`/`distant_uniform` arm of the Phase-0 EOG band instrumentation (all games are non-distant now).
  - `franchise_tournament_progression.py`: drop `"distant"` from `source in (...)`.
  - `api.py:4737` comment cleanup.
- **B5. Remove momentum_score + streaks** (per decision):
  - `momentum_score` out of `TEAM_ATTR_CLAMPS` ([training_execution_v2.py:297](../../BackEnd/models/training_execution_v2.py#L297)) + training allocation/report echoes (franchise_routes 14243/14389).
  - Remove `momentum_score`/`distant_win_streak`/`distant_loss_streak` from FTD init (team_manager 818-820, franchise_manager 599-601, api.py 757, gameplan_routes 1116/2362) **and** from `init_franchise_rollover_team_attributes` (added in [[project_eog_attr_retune]]).
  - Remove from projections (6339-6341, 14717-14719) + attr-key lists.
  - Optional `$unset` migration on existing FTD docs (separate, non-destructive; do not wipe).
- **B6. Tests/scripts:** delete `tests/test_distant_sim.py`, `tests/test_distant_sim_integration.py`, `scripts/distant_sim_monte_carlo.py` (+results); prune passing mentions.

### Distant TRAINING track (parallel; do a full inventory at execution time like the game-sim one)
- **B7. Routing collapse:** in `_apply_franchise_distant_cpu_training` ([12962](../../BackEnd/api/franchise_routes.py#L12962)) delete the template-delta branch (12982-13088) and the flag `_franchise_all_teams_autotrain` ([3996](../../BackEnd/api/franchise_routes.py#L3996)) — behavior becomes unconditional `_run_all_cpu_autotrain`. Rename the function/route off "distant" (`/franchise/run-training/distant-cpu` → e.g. `/cpu-train`; keep it working as the CPU-train trigger).
- **B8. Drop the template collection + data fields:** stop reading `db["distant_training"]`; remove `cpu_distant_trained_week` / `training_status.cpu_distant_complete_week` / `distant_training_resume` (rename to `cpu_autotrain_*` or drop) — audit `franchise_training_state.py:30`, franchise_routes 7949/13133/13224/13376/13521/14018.
- **B9. Delete distant-training scripts:** `generate_distant_training_templates.py`, `replace_gob_distant_training_from_staging.py`, `test_distant_training_dry_run.py`. Optional: drop the `distant_training` Mongo collection (separate, non-destructive).

## Phase C — Documentation
- **C1. Delete:** `04_Franchise_Mode_Systems/Distant_Game_Sim_System.md`, `Distant_Game_Sim_Player_Stats.md`, **`Distant_Team_Training_System.md`** (tuning history already in `Z-Completed/Distant_Sim_Tuning.md`).
- **C2. Targeted edits** (remove momentum_score/streaks, `simulation_engine=="distant"`, and distant-training mentions): Team_Attribute_System.md, Training_System.md, projects/balancing_team_attributes.md, Box_Score_System.md, End_Of_Game_System.md, Tunable_Constants.md, Attribute_Clamp_System.md, Database_System.md, Franchise_Tournament_System.md, Rank_Prestige_System.md.
- **C3.** With distant **training** now also removed, `team_momentum` (player momentum) is the only surviving "momentum/distant"-adjacent system — leave a one-line note in `Player_Momentum_System.md` so future agents don't hunt for a removed sibling.

## Verification / exit gate
- After B (both tracks): `grep -rin distant BackEnd/ scripts/` returns nothing.
- Full-sim + real-autotrain paths are isolated `sim_rng`/`training_rng`; confirm no seed regressions post-removal.
- Behavior-change surface (Phase A: both flags) is the only place that alters outcomes; Phase B/C are dead-code + docs only.
