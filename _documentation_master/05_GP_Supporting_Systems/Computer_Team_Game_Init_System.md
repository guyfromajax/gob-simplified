## Computer Team Game Init System

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
- inside / attack / outside focus
- defense / aggression
- pressure usage
- rebounding preference

This part of init did not change materially during the play identity migration.

## Playbook Settings

Playbook initialization changed materially.

Location:
- `BackEnd/api/gameplan_routes.py`
- `initialize_playbook_settings()`

Current behavior:
- offense percentage maps are keyed by `play_id`, not play name
- slot assignments start empty
- motion dropdowns start empty
- position filters store `play_id` arrays

Default seeded offense behavior:
- a curated starter offense set is seeded using stable `play_id` constants
- this replaced name-based seeding so play renames do not break defaults

Starter seeded offense set:
- the three core motion plays
- the three core starter set plays
- the three SF set plays used in the original starter package

Position filters:
- `standard`, `PG`, `SG`, `SF`, `PF`, `C`
- each stores stable `play_id` values
- these are still legacy-curated filters and are not yet generated dynamically from metadata

## Team Play Copies

When team plays are initialized, each team-owned play copy includes:

```python
{
    "play_id": str(play["_id"]),
    "name": play["name"],
    "play_type": play["play_type"],
    "play_focus": play["play_focus"],
    "target_shooter": play.get("target_shooter"),
    "effectiveness": ...,
    "momentum": ...,
    "cloaking": ...
}
```

Notes:
- `target_shooter` is now part of init for team-owned play copies
- that allows future per-team customization without mutating the universal play doc

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
