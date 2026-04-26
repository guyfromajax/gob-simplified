## Playbooks Page

## Overview

The Playbooks page configures offensive and defensive weighting plus Playcall Center ordering.

Primary frontend:
- `FrontEnd/static/playbooks.js`

Primary backend:
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`

## Current Identity Model

Offensive playbook persistence is now `play_id`-first, and the internal persistence model is the simplified canonical shape.

Current canonical storage shape:

```python
playbook_settings = {
    "motion": {play_id: percentage},
    "set_plays": {play_id: percentage},
    "fast_breaks": {"triangle": 34, "rim_runner": 33, "covert_release": 33},
    "man_defense": {defense_id: percentage},
    "zone_defense": {defense_id: percentage},
    "pc_order": {
        "offense": [play_id_1, play_id_2, ...],
        "defense": [defense_id_1, defense_id_2, ...]
    },
    "position_filters": {...},
    "even_distribution_all": bool,
    "_meta": {...}
}
```

Play-level metadata is stored on the team `plays` objects:
- motion plays use `motion_focus`
- set plays use `target_shooter`

## Play Loading

`GET /api/playbooks` returns offense arrays with both:
- `name`
- `play_id`

The page uses:
- `play_id` for identity, persistence, and matching
- `name` for rendering

## Compatibility

The page and backend still tolerate old name-keyed and legacy-shaped data during rollout, but all internal persistence should normalize into the canonical shape above.

Normalization rules:
- old percentage maps keyed by play name are converted to `play_id`
- old split set-play buckets are merged into `set_plays`
- old `fast_break` maps are normalized to `fast_breaks`
- old `slot_assignments` are treated as compatibility input and normalized into `pc_order`
- old motion dropdown maps keyed by play name are normalized to `play_id` and resolved into play metadata

## Playcall Center Ordering

`pc_order` is the only authoritative persistence model for Playcall Center membership and ordering.

Implications:
- a checked offensive play must exist in `pc_order.offense`
- a checked defensive scheme must exist in `pc_order.defense`
- unchecked rows must be removed from the appropriate list
- gameplay ordering should be restored from `pc_order` first
- `slot_assignments` may still exist as a compatibility output for older callers, but should not be treated as the source of truth

## Position Filters

Position filters currently store arrays of `play_id`.

They are still manually curated and legacy-shaped:
- `standard`
- `PG`
- `SG`
- `SF`
- `PF`
- `C`

They were updated to use stable `play_id` constants so renaming a play does not break filter membership.

## Default Seed Behavior

First-load offense percentages are seeded from a fixed starter offense set identified by `play_id`, not by play name.

That starter set still mirrors the earlier product behavior, but it is now rename-safe.

## Navigation to Play Details

Play Details navigation now prefers:
- `play_id`

and still includes:
- `play_name`

for compatibility fallback.

## Franchise Persistence Policy

Franchise mode now uses a two-stage persistence model:

- **FCC / Pregame**
  - read Playbooks from `FTD`
  - save Playbooks to `FTD`
- **Game Init**
  - copy the user team's Playbooks snapshot from `FTD` into the game doc
- **Active Gameplay**
  - read Playbooks from the game doc
  - save gameplay-scoped Playbooks changes to the game doc only

This applies to:
- offense percentages
- defense percentages
- fast break percentages
- Playcall Center ordering for offense and defense
- motion focus
- target shooter

Gameplay changes do not write back to `FTD`. FCC remains the franchise master editor.

## Rename Safety Status

Rename-safe:
- offense percentages
- Playcall Center ordering (`pc_order`)
- motion-focus persistence
- position filters
- most Play Details navigation

Still compatibility-based:
- some older fallback paths still accept `play_name`
- team `plays` maps may still be name-keyed in stored documents
