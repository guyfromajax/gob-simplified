## Mode Initialization System

## Overview

Mode init creates the first persisted team/player state for:
- Single Game
- Tournament
- Franchise

This doc focuses on the parts relevant to the current playbooks / play identity system.

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

`initialize_playbook_settings()` now seeds offense using `play_id`-keyed maps.

Current default shape:

```python
{
    "motion": {play_id: percentage},
    "set_play_inside": {play_id: percentage},
    "set_play_attack": {play_id: percentage},
    "set_play_outside": {play_id: percentage},
    "fast_break": {...},
    "zone_defense": {...},
    "man_defense": {...},
    "slot_assignments": {},
    "motion_dropdowns": {},
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
