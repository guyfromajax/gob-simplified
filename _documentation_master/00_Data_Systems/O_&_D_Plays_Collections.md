# Offense & Defense Collections

## Overview

The universal `plays` and `defenses` collections are the source of truth for baseline offensive and defensive definitions.

Current architecture:
- universal collections store full baseline definitions
- team documents store team-owned copies with mutable team data
- runtime fetches universal play/defense definitions when full skeleton or zone data is needed

This is no longer a pure "reference only" system for offense. Team docs now store lightweight play metadata plus team-specific values.

## Universal `plays` Collection

Each offensive play document includes:
- `_id` as Mongo `ObjectId`
- `name`
- `play_type`
- `play_focus`
- `target_shooter`
- `skeletons`
- optional `copy`
- baseline `effectiveness`, `momentum`, `cloaking`

Set-play notes:
- set plays now carry universal `target_shooter`
- staging set-play skeletons use role aliases like `target_shooter`, `pos1`, `pos2`, `pos3`, `pos4`
- runtime remaps those aliases back to `PG/SG/SF/PF/C`

Motion-play notes:
- motion plays still use `skeletons.base_loop`
- they do not use `target_shooter`

## Universal `defenses` Collection

Each defense document includes:
- `_id`
- `defense_id`
- `name`
- `defense_type`
- `zone_definitions` / `shift_triggers` when applicable
- baseline `effectiveness`, `momentum`, `cloaking`

Defense identity is still primarily name-based in most persisted settings.

## Team-Owned Offensive Play Copies

Mode-specific team docs currently store offensive plays as lightweight team-owned play objects.

Current play copy shape:

```json
{
  "play_id": "mongo_object_id_as_string",
  "name": "Base Post Play",
  "play_type": "set_play",
  "play_focus": "inside",
  "target_shooter": "C",
  "motion_focus": null,
  "effectiveness": 0,
  "momentum": 0,
  "cloaking": 0,
  "game_stats": {},
  "season_stats": {}
}
```

Important notes:
- `play_id` is the canonical stable identity
- `name` is display text
- some persisted team `plays` maps are still keyed by play name during the compatibility phase
- runtime helpers support both name-keyed and `play_id`-keyed team `plays` maps

## Team-Owned Defensive Copies

Team docs still store defense effectiveness/momentum/cloaking and stats under `scouting_data["defense"]`.

Those entries remain defense-name keyed.

**Gameplay contract:** Persisted rows may omit duplicate or legacy fields. When a live `TeamManager` is built, **`normalize_scouting_data_for_gameplay`** (`BackEnd/models/team_manager.py`) merges stored `scouting_data` onto the **cached template** so each standard defense row (Man, zones, etc.) always has top-level **`used` / `success`** plus nested **`game_stats`** and **`season_stats`**, matching what `run_micro_turn` and stat tracking increment. Franchise new-game seeding uses the same merge in **`prepare_ftd_for_new_game`** before zeroing per-game defense counters.

## Runtime Access Pattern

Current offensive flow:
1. Resolve the team-owned play copy from the team document.
2. Read `play_id` from that team-owned copy.
3. Fetch the universal play doc by `_id`.
4. Use team-owned metadata like `effectiveness`, `momentum`, `cloaking`, and `target_shooter`.

Current defensive flow:
1. Resolve defense settings from team scouting data and playbook settings.
2. Use the defense name / defense type to fetch universal defense definitions when needed.

## Persistence Notes

Playbook persistence changed materially:
- offensive percentage maps are keyed by `play_id`
- offensive slot assignments persist `playId`
- motion dropdowns persist by `play_id`
- position filters now store `play_id` arrays

Training/report notes:
- offensive training deltas are emitted in `plays_effectiveness_changes` keyed by `play_id`
- UI surfaces render display names from team play objects

## Related Docs

- `_documentation_master/00_Data_Systems/Database_System.md`
- `_documentation_master/05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md`
- `_documentation_master/05_GP_Supporting_Systems/Sim_Playcalling_System.md`
- `_documentation_master/06_GMO_Supporting_Systems/Playbooks_Page.md`
- `_documentation_master/06_GMO_Supporting_Systems/Play_Builder_System.md`
