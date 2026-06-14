## Computer Team Game Init System

**Last verified:** June 2026

**See also (init family):** `Game_Init_System.md` — HTTP **`POST /api/init-game`**, franchise **FTD → game document** seeding, and tournament user-master copy. `../06_GMO_Supporting_Systems/Mode_Init_System.md` — **owner** of the `initialize_playbook_settings` shape + team play-copy fields. `../06_GMO_Supporting_Systems/Season_Init_System.md` — franchise new-season rollover. This document focuses on **in-TeamManager strategy** defaults when persisted settings are absent.

## Overview

Computer team init has two distinct pieces:
- `strategy_settings` initialization
- `playbook_settings` initialization

The strategy layer is still computer-specific.
The playbook layer is now shared across user and computer teams and is built around `play_id`.

Primary files:
- `BackEnd/models/team_manager.py`
- `BackEnd/api/gameplan_routes.py`

## Strategy Settings

Computer teams still get weighted-random strategy settings when no persisted settings are supplied.

Location:
- `TeamManager._init_strategy_settings()`

This controls:
- offense motion vs set-play tendency
- inside / attack / outside focus (uniform 1–4, never 0)
- defense / aggression
- pressure usage (`hc_trap`, `fc_press` — weighted heavily toward 0–1)
- rebounding preference (weighted toward 3–4)

Note: **tempo is not initialized here** — it's rolled per game via `init_tempo_random()`.

This part of init did not change materially during the play identity migration.

## Playbook Settings

The playbook layer (`initialize_playbook_settings()` in `BackEnd/api/gameplan_routes.py`) is now **shared across user and computer teams** and built around `play_id` — computer teams use the same canonical seed as everyone else. **The seeded-default shape (offense even-distribution, `fast_breaks`/`zone_defense`/`man_defense` defaults, `SEEDED_OFFENSE_PLAY_IDS`, `position_filters`, `pc_order`, `even_distribution_all`) is owned by `../06_GMO_Supporting_Systems/Mode_Init_System.md` — see there rather than duplicating it here.**

## Team Play Copies

Team-owned play copies carry their identity + per-team fields (`play_id`, `name`, `play_type`, `play_focus`, `target_shooter`, `effectiveness`, `momentum`, `cloaking`). Full field list + notes: `../06_GMO_Supporting_Systems/Mode_Init_System.md` → Team Play Initialization.

## Rename Safety

Current rename-safe init areas:
- seeded offensive playbook percentages
- position filter initialization
- team play metadata copy

Still compatibility-based:
- some persisted team `plays` maps remain name-keyed until a future storage migration

## Key Files

- `BackEnd/models/team_manager.py`
- `BackEnd/api/gameplan_routes.py`
