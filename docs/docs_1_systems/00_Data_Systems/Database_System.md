# Database System

## Overview

The database layer uses:
- universal collections for baseline definitions
- mode-specific documents for team-owned state and progression

Relevant collections:
- `plays`
- `defenses`
- `teams`
- `players`
- `games`
- `tournaments`
- `franchise_team_data`
- `franchises`

The older docs described offensive play storage as "references only." That is no longer fully accurate.

Current offensive model:
- universal `plays` holds the canonical baseline play doc
- mode-specific team docs hold lightweight team-owned play copies
- those team-owned copies carry mutable values like `effectiveness`, `momentum`, `cloaking`, and `target_shooter`

## Current Identity Rules

Use this consistently:
- Mongo `_id` stays `ObjectId` in the universal collection
- `play_id` is the stringified `_id` used everywhere else in app/runtime logic
- `name` is display text, not the canonical identity

This now matches the general app pattern used for team/player identifiers.

## Universal Offensive Play Schema

Universal play docs include:
- `_id`
- `name`
- `play_type`
- `play_focus`
- `target_shooter`
- `skeletons`
- optional `copy`
- baseline `effectiveness`
- baseline `momentum`
- baseline `cloaking`

Set-play note:
- set-play skeletons in staging now use role aliases like `target_shooter` and `pos1` through `pos4`
- runtime remaps those aliases back to real lineup positions before role assignment

## Team-Owned Offensive Play Schema

Current team play copies include:

```json
{
  "play_id": "mongo_object_id_as_string",
  "name": "Base Post Play",
  "play_type": "set_play",
  "play_focus": "inside",
  "target_shooter": "C",
  "effectiveness": 0,
  "momentum": 0,
  "cloaking": 0,
  "game_stats": {},
  "season_stats": {}
}
```

Important notes:
- some stored team `plays` maps are still keyed by play name during the compatibility phase
- runtime helpers support both name-keyed and `play_id`-keyed team `plays` maps

## Playbook Settings Schema

Current offensive playbook persistence is `play_id`-first:

```json
{
  "motion": {"play_id": 33},
  "set_play_inside": {"play_id": 50},
  "set_play_attack": {"play_id": 50},
  "set_play_outside": {"play_id": 50},
  "zone_defense": {"2-3 Zone": 40},
  "man_defense": {"Man": 100},
  "slot_assignments": {
    "1": {"section": "motion", "playId": "play_id", "playName": "display name"}
  },
  "motion_dropdowns": {"play_id": "inside"},
  "position_filters": {"standard": ["play_id"]},
  "even_distribution_all": true
}
```

Notes:
- offensive percentages, slot assignments, motion dropdowns, and position filters are now `play_id`-based
- defensive weighting is still defense-name keyed

## Training / Reporting Persistence

Training report offensive deltas are now keyed by `play_id`:
- `plays_effectiveness_changes`

UI/report rows still display the play `name`.

## Related Docs

- `docs/docs_1_systems/00_Data_Systems/O_&_D_Plays_Collections.md`
- `docs/docs_1_systems/03_Data_Persistence/Data_Persistence_System.md`
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Mode_Init_System.md`
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Playbooks_Page.md`
