## Playbooks Page

## Overview

The Playbooks page configures offensive and defensive weighting plus Playcall Center slot assignments.

Primary frontend:
- `FrontEnd/static/playbooks.js`

Primary backend:
- `BackEnd/api/gameplan_routes.py`
- `BackEnd/utils/playbook_settings_utils.py`

## Current Identity Model

Offensive playbook persistence is now `play_id`-first.

Current offensive storage shape:

```python
playbook_settings = {
    "motion": {play_id: percentage},
    "set_play_inside": {play_id: percentage},
    "set_play_attack": {play_id: percentage},
    "set_play_outside": {play_id: percentage},
    "slot_assignments": {
        "1": {"section": "motion", "playId": play_id, "playName": display_name}
    },
    "motion_dropdowns": {play_id: dropdown_value}
}
```

Defense remains name-keyed because the defense library is still name-based.

## Play Loading

`GET /api/playbooks` returns offense arrays with both:
- `name`
- `play_id`

The page uses:
- `play_id` for identity, persistence, and matching
- `name` for rendering

## Compatibility

The page and backend still tolerate old name-keyed data during rollout.

Normalization rules:
- old percentage maps keyed by play name are converted to `play_id`
- old `slot_assignments` keyed by display names are normalized to `playId`
- old motion dropdown maps keyed by play name are normalized to `play_id`

## Slot Assignments

Playcall Center slot assignments now persist by `playId`.

`playName` is still stored for:
- display
- compatibility fallback
- human readability in docs / DB inspection

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

## Rename Safety Status

Rename-safe:
- offense percentages
- slot assignments
- motion dropdowns
- position filters
- most Play Details navigation

Still compatibility-based:
- some older fallback paths still accept `play_name`
- team `plays` maps may still be name-keyed in stored documents
