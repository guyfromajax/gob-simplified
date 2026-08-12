# Balancing Team Attributes

This is the concise balancing map for persisted franchise team attributes after the universal
full-simulation and CPU auto-training rollout.

For exact ranges, thresholds, and formulas, use:

- `04_Franchise_Mode_Systems/Team_Attribute_System.md`
- `06_Gameplay_Systems/End_Of_Game_System.md`
- `09_Training_Systems/Training_System.md`
- `11_Design_Systems/Tunable_Constants.md`

Implementation sources:

- `BackEnd/models/training_execution_v2.py`
- `BackEnd/api/franchise_routes.py`
- `BackEnd/eog_attr_rules.py`
- `BackEnd/constants/eog_attr_bands.py`
- `BackEnd/constants/shot_threshold_scale.py`
- `BackEnd/utils/season_momentum.py`

## Live progression paths

Every eligible team uses the same two progression models:

1. Full-engine end-of-game progression from the canonical game snapshot.
2. The shared `execute_training` engine. CPU teams receive generated allocations and coaching
   focus, with per-team idempotency guarded by `cpu_autotrain_week`.

There is no alternate lightweight game progression branch and no template-training branch.

## Persisted attributes

| Attribute | Range | Better direction | Primary role |
|---|---:|---|---|
| `shot_threshold` | −50–150 | Lower | Shooting difficulty/quality |
| `discipline` | -20–20 | Higher | Fouls, turnovers, pressure checks |
| `fight` | -20–20 | Higher | Physicality and resilience |
| `rebound_modifier` | 0.0–1.0 | Higher | Team rebounding modifier |
| `offensive_efficiency` | -20–20 | Higher | Offensive execution |
| `defensive_efficiency` | -20–20 | Higher | Defensive execution |
| `team_chemistry` | 7–25 | Higher | Team cohesion and shared checks |
| `fb_efficiency` | -20–20 | Higher | Fast-break execution |
| `pt_efficiency` | -20–20 | Higher | Press/trap execution |
| `fb_opp_modifier` | -20–20 | Higher | Fast-break prevention |
| `pt_opp_modifier` | -20–20 | Higher | Press/trap resistance |

## Deferred compatibility fields

`momentum_score`, `distant_win_streak`, and `distant_loss_streak` remain temporarily on franchise
team documents. Regular-season full CPU games still update them through
`BackEnd/utils/season_momentum.py`, but the full game engine does not read them. Their removal is
deferred until the EOG attribute retune so training draw counts and the measured baseline are not
changed during this sunset.

These fields are unrelated to live player momentum (`MO`).

## Balancing workflow

When changing a team attribute:

1. Update the appropriate named constants first.
2. Confirm both user and CPU training consume the intended rule.
3. Confirm EOG uses the canonical full-game snapshot.
4. Run seeded verification with `PYTHONHASHSEED=0`.
5. Use exact diff only when RNG draw counts are unchanged; otherwise follow the poison-stash or
   distributional procedure in `projects/Sim_Perf_Capstone.md`.
6. Update the four source documents listed at the top.
