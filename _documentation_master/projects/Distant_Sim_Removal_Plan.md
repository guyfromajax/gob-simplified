# Distant Game Sim — Removal Plan

**Status (2026-07-26): NOT sunset.** Distant game sim is still live. It's gated by flag `FRANCHISE_ALL_GAMES_FULL_SIM` ([franchise_routes.py:3983](../../BackEnd/api/franchise_routes.py#L3983)) which **defaults OFF and is unset in prod**, so out-of-conference regular-season games + EOS games still run the distant engine.

**Decisions (owner):** sequence = **sunset-then-remove**; `momentum_score` + `distant_win/loss_streak` = **remove entirely**; EOS games = **force full turn-by-turn sim**.

## ⚠️ Naming — three unrelated "distant"/"momentum" things
| Thing | Scope | Identifiers |
|---|---|---|
| Distant **game sim** | **REMOVE** | `distant_sim_engine.py`, `distant_game_stats.py`, `constants/distant_sim.py`, `simulation_engine=="distant"` |
| Distant **training** | **KEEP** (separate CPU-training system) | `_apply_franchise_distant_cpu_training`, `distant_training` collection, `Distant_Team_Training_System.md` |
| Player `team_momentum` (engine, −50..+50) | **KEEP** (unrelated to FTD `momentum_score` −10..10) | `constants/momentum.py`, `utils/player_momentum.py`, `add_momentum` |

---

## Phase A — Complete the sunset (behavioral, revertible, NO deletion)
Prove full-sim replaces distant everywhere before deleting the fallback.

- **A1.** Route ALL games to full TbT under one revertible flag:
  - Regular season (Path A): already covered — set `FRANCHISE_ALL_GAMES_FULL_SIM=1` + `FRANCHISE_CPU_SIM_USE_POOL=1` in prod.
  - EOS is **not** flag-covered today (Path A EOS block [6466-6540](../../BackEnd/api/franchise_routes.py#L6466-L6540); Path B `sim_rest_of_tournament` [14737-14790](../../BackEnd/api/franchise_routes.py#L14737-L14790), both via `_should_use_tbt_for_eos_game`). Small change: make `_should_use_tbt_for_eos_game` return True when `_franchise_all_games_full_sim()` — so ONE flag forces every game to full sim, still flip-back-able.
- **A2.** Validate a full season with the flag ON (staging / controlled franchise): pool perf within [[project_sim_perf_optimization]] targets for 63+ full games/wk; out-of-conf + EOS box scores sane; `simulation_engine=="distant"` count == 0.
- **A3.** Bake in prod for an agreed window; confirm zero distant games in logs.
- **Synergy:** capture the EOG band-measurement season (see [[project_eog_attr_retune]]) with the flag ON, so tuning data reflects the distant-free target world (no `distant_uniform` bands).

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

## Phase C — Documentation
- **C1. Delete:** `04_Franchise_Mode_Systems/Distant_Game_Sim_System.md`, `Distant_Game_Sim_Player_Stats.md` (tuning history already in `Z-Completed/Distant_Sim_Tuning.md`).
- **C2. Targeted edits** (remove momentum_score/streaks + `simulation_engine=="distant"` mentions): Team_Attribute_System.md, Training_System.md, projects/balancing_team_attributes.md, Box_Score_System.md, End_Of_Game_System.md, Tunable_Constants.md, Attribute_Clamp_System.md, Database_System.md, Franchise_Tournament_System.md, Rank_Prestige_System.md.
- **C3.** Add a one-line disambiguation note wherever distant **training** remains, so future agents don't reconflate it.

## Verification / exit gate
- After B: `grep -rin distant BackEnd/ | grep -vi train` returns nothing (only distant-training survives).
- Full-sim path is isolated `sim_rng`; confirm no seed regressions post-removal.
- Behavior-change surface (Phase A) is the only place that alters game outcomes; Phase B/C are dead-code + docs only.
