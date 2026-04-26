## Play Builder System

## Overview

The offensive Play Builder manages the universal `plays` library.

Primary frontend:
- `FrontEnd/static/play-builder-v2.html`

Primary backend:
- `BackEnd/api/play_routes.py`

## Universal Play Doc Shape

Universal offensive plays are stored in the `plays` collection.

Core fields:

```json
{
  "_id": "ObjectId",
  "name": "Display Name",
  "play_type": "motion|set_play",
  "play_focus": "inside|attack|outside|null",
  "target_shooter": "PG|SG|SF|PF|C|null",
  "skeletons": {...},
  "copy": {...}
}
```

## Motion Plays

Motion plays:
- use `play_type = "motion"`
- keep `play_focus = null`
- store their animation under `skeletons.base_loop`
- may use either direct `steps` or `versions`

## Set Plays

Set plays:
- use `play_type = "set_play"`
- require `play_focus`
- store the standard four variants:
  - `successful`
  - `mid_play_change`
  - `contested`
  - `broken`

## Target Shooter

Set plays now carry a universal `target_shooter` field.

Meaning:
- the intended primary shooter role for the play
- one of `PG`, `SG`, `SF`, `PF`, `C`

Runtime use:
- team copies inherit this field
- HCO uses it to remap alias role keys inside set-play skeletons

## Set-Play Skeleton Role Keys

Set-play skeleton documents in staging now store role aliases instead of canonical lineup positions:
- `target_shooter`
- `pos1`
- `pos2`
- `pos3`
- `pos4`

This is intentional.
The engine remaps those aliases back to `PG/SG/SF/PF/C` at runtime.

## Save / Load Identity

Current route support:
- `GET /api/plays`
- `GET /api/plays/{play_id}`
- `GET /api/play/{play_name_or_id}`
- `POST /api/plays`

Compatibility note:
- the older name route still exists
- the ID route should be treated as the preferred fetch path

## Upsert Behavior

Builder save is still name-based upsert in the current route layer.

Implication:
- changing a play name creates rename sensitivity in the builder save path unless handled intentionally
- that is separate from the runtime/playbooks migration, which is now mostly `play_id`-driven
