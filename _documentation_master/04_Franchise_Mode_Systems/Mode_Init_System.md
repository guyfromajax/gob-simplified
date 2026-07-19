## Mode Initialization System (**verified 2026-06-13**)

> Verified vs code: `initialize_playbook_settings()` (`gameplan_routes.py`) seeds the documented shape (`motion`/`set_plays`/`fast_breaks`/`hc_traps`/`zone_defense`/`man_defense`/`pc_order`/`locks`/`position_filters`/`_meta`) with offense seeded by `play_id` via `SEEDED_OFFENSE_PLAY_IDS`; team play copies (`team_manager.py`) carry `play_focus`, `target_shooter`, and per-team `effectiveness`/`momentum`/`cloaking` + stats containers. (Also `even_distribution_all` + `_meta.schema_version: 2`.)

## Overview

Mode init creates the first persisted team/player state for:
- Single Game
- Tournament
- Franchise

This doc focuses on the parts relevant to the current playbooks / play identity system.

> **Related init docs (init family):** This doc is the **authoritative owner of the `initialize_playbook_settings()` shape + seeded defaults** and the team play-copy field list; the others link here instead of re-describing them.
> - `../05_GP_Supporting_Systems/Game_Init_System.md` — per-game init via `POST /api/init-game` (FTD → game document at game start).
> - `../05_GP_Supporting_Systems/Computer_Team_Game_Init_System.md` — in-`TeamManager` **strategy** defaults when persisted settings are absent (playbook layer defers here).
> - `Season_Init_System.md` — new-season rollover inside an existing franchise instance (what persists / resets).

Primary files:
- `BackEnd/models/team_manager.py`
- `BackEnd/models/player.py`
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/models/franchise_manager.py`
- `BackEnd/tournament/tournament_manager.py`

## Team Play Initialization

When a team object is created, it receives a team-owned copy of the universal offensive play metadata.

Each team-owned play copy includes:
- `play_id`
- `name`
- `play_type`
- `play_focus`
- `target_shooter`
- mutable team values:
  - `effectiveness`
  - `momentum`
  - `cloaking`
- stats containers:
  - `game_stats`
  - `season_stats` where applicable

Important:
- universal play docs remain the source of skeleton truth
- team copies do not own skeleton execution data

## Playbook Settings Initialization

`initialize_playbook_settings()` now seeds the canonical simplified playbook structure using `play_id`-keyed offensive maps.

Current default shape:

```python
{
    "motion": {play_id: percentage},
    "set_plays": {play_id: percentage},
    "fast_breaks": {...},
    "man_defense": {...},
    "zone_defense": {...},
    "pc_order": {
        "offense": [play_id, ...],
        "defense": ["Man", "2-3 Zone", ...]
    },
    "locks": {
        "motion": [],
        "set_plays": [],
        "fast_breaks": [],
        "hc_traps": [],
        "man_defense": [],
        "zone_defense": [],
    },
    "_meta": {...},
    "position_filters": {
        "standard": [play_id, ...],
        "PG": [play_id, ...],
        "SG": [play_id, ...],
        "SF": [play_id, ...],
        "PF": [play_id, ...],
        "C": [play_id, ...]
    }
}
```

Default offense seed behavior:
- uses a fixed starter set identified by stable `play_id`
- does not rely on play names anymore

### Seeded defaults (schema_version 2)

- **offense** (`motion`, `set_plays`): keyed by `play_id`; seeded plays get an **even distribution** (100 split across the seeded set, remainder to alphabetically-first plays). Seeded set = curated starter package via `SEEDED_OFFENSE_PLAY_IDS` (three core motion + three core starter set + the three SF set plays).
- **`fast_breaks`**: `covert_release` 33 / `rim_runner` 33 / `triangle` 34.
- **`zone_defense`**: even split across `zone_23`, `zone_32`, `zone_131`.
- **`man_defense`**: `man_normal` 100 / `man_tight` 0 / `man_loose` 0 (first-class Base/Deny/Loose Man; `man_pressure` folds to `man_tight` on save).
- **`position_filters`**: `standard` + `PG/SG/SF/PF/C`, each storing `play_id` arrays (filtered to plays that exist in the universal collection); legacy-curated, not yet metadata-generated.
- **`pc_order`**: starts empty (`offense: []`, `defense: []`).
- **`locks`**: empty per-section lists (Playbooks redesign durable lock state; UI-only arithmetic).
- **`even_distribution_all`**: macro toggle defaults to `True`.

## Strategy Settings

Mode init still seeds `strategy_settings` normally.
That portion did not materially change in this migration.

## Franchise / Tournament / Single Differences

Single Game:
- team objects are created lazily

Tournament:
- tournament team objects are initialized at tournament creation

Franchise:
- franchise team data (FTD) is initialized up front
- team play copies and playbook settings are part of FTD state

## Rename Safety Status

Mode init is now rename-safe in the important starter paths:
- team play metadata copy includes `play_id`
- playbook percentages seed by `play_id`
- position filters seed by `play_id`

Still deferred:
- full storage migration of all persisted team `plays` maps from name-keyed to `play_id`-keyed
