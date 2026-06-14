## Offense Plays System (**verified 2026-06-13**)

> Verified vs code: set-play aliases `SET_PLAY_POSITION_ALIASES = ("target_shooter", "pos1", "pos2", "pos3", "pos4")` (`playbook_weights_utils.py` L24); play routes in `play_routes.py` (`POST /api/plays` L59, `GET /api/plays` L134, `GET /api/play/{play_name}` L154, `GET /api/plays/{play_id}` L187, `DELETE /api/plays/{play_id}` L212); `plays_effectiveness_changes` built in `training_execution_v2.py` (~L149-164); set-play variants `successful`/`mid_play_change`/`contested`/`broken` (shot_manager.py L617-620, playbook_weights_utils.py L23); `play-builder-v2.html` + `skeletons.base_loop` confirmed. Team play-copy field list is owned by `Mode_Init_System.md`. **The former `Play_Builder_System.md` was merged into this doc (Play Builder section) and deleted, 2026-06-13.**

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

## Play Builder (authoring)

The offensive **Play Builder** authors/manages the universal `plays` library (the source of the Universal Play Model above).

- Frontend: `FrontEnd/static/play-builder-v2.html`
- Backend: `BackEnd/api/play_routes.py`

### Motion vs set plays

Motion plays:
- `play_type = "motion"`, `play_focus = null`
- animation stored under `skeletons.base_loop`; may use direct `steps` or `versions`

Set plays:
- `play_type = "set_play"`, require `play_focus`
- store the four standard skeleton variants: `successful`, `mid_play_change`, `contested`, `broken`
- carry a universal `target_shooter` (intended primary shooter role, one of `PG/SG/SF/PF/C`); team copies inherit it, and HCO uses it to remap the set-play skeleton role aliases (`target_shooter`/`pos1`–`pos4` → `PG/SG/SF/PF/C` — see Universal Play Model above)

### Builder routes

- `GET /api/plays` — list
- `GET /api/plays/{play_id}` — preferred fetch
- `GET /api/play/{play_name}` — compatibility (name-based)
- `POST /api/plays` — save / upsert
- `DELETE /api/plays/{play_id}`

### Upsert / rename behavior

Builder save is still a **name-based upsert** in the route layer, so renaming a play creates rename sensitivity in the builder save path. This is separate from the runtime/playbooks migration, which is now mostly `play_id`-driven.

## Training / Reporting

Training and reporting now carry `play_id` with each offensive play row.

Important rule:
- offensive deltas in `plays_effectiveness_changes` are keyed by `play_id`
- UI still renders the play `name`

## Related Docs

- `../05_GP_Supporting_Systems/HCO_Turn_Resolution_System.md`
- `../05_GP_Supporting_Systems/Sim_Playcalling_System.md`
- `../00_General_Systems/Plays_Page_System.md`
