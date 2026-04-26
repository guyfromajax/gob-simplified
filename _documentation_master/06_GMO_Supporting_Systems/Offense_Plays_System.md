## Offense Plays System

## Overview

The offensive play system now splits identity, display, and execution concerns more cleanly:
- `play_id` is the canonical identity for persistence and runtime lookup
- `name` is display text
- `target_shooter` is part of set-play metadata

Primary related systems:
- playbook weighting
- HCO play resolution
- Play Details / Play Builder
- Training Report / scouting / summaries

## Universal Play Model

Universal offensive play docs live in the `plays` collection and include:
- `_id`
- `name`
- `play_type`
- `play_focus`
- `target_shooter`
- `skeletons`
- optional `copy`

Set-play note:
- staging set-play skeletons use `target_shooter/pos1/pos2/pos3/pos4` aliases
- runtime remaps those aliases back to `PG/SG/SF/PF/C`

## Team-Owned Play Model

Mode-specific team docs store lightweight team-owned play copies with:
- `play_id`
- `name`
- `play_type`
- `play_focus`
- `target_shooter`
- `effectiveness`
- `momentum`
- `cloaking`
- stats buckets

Current compatibility note:
- some stored team `plays` maps are still keyed by play name
- runtime helpers support both name-keyed and `play_id`-keyed maps

## Selection / Persistence Rules

Current playbook persistence:
- offense percentages are keyed by `play_id`
- slot assignments persist `playId`
- motion dropdowns persist by `play_id`
- position filters store `play_id` arrays

Current runtime selection:
- gameplay still carries the current offensive call as display name text
- backend resolves that display name to the correct team-owned play copy
- universal skeleton fetch then happens by `play_id`

## Details / Builder Routing

Preferred details fetch path:
- `GET /api/plays/{play_id}`

Compatibility path:
- `GET /api/play/{play_name_or_id}`

The Play Details page now prefers `play_id` and only falls back to `play_name`.

## Training / Reporting

Training and reporting now carry `play_id` with each offensive play row.

Important rule:
- offensive deltas in `plays_effectiveness_changes` are keyed by `play_id`
- UI still renders the play `name`

## Related Docs

- `docs/docs_1_systems/05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md`
- `docs/docs_1_systems/05_GP_Supporting_Systems/Sim_Playcalling_System.md`
- `docs/docs_1_systems/06_GMO_Supporting_Systems/Play_Builder_System.md`
- `docs/docs_1_systems/00_General_Systems/Plays_Page_System.md`
