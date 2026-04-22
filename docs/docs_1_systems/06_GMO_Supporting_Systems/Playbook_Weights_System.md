## Playbook Weights System

## Overview

The Playbook Weights System derives two position-level shot-weight outputs from the user team's offensive configuration:

- `Playbooks`
- `Playcall Center`

These values answer a narrow question:

> Based on the user's current offensive play weighting and offensive Playcall Center assignments, how likely is each position (`PG`, `SG`, `SF`, `PF`, `C`) to end up as the shot-taker?

These values are:

- derived from play definitions and user settings
- not influenced by player personnel
- stored as backend-derived cached values inside canonical `playbook_settings`
- intended to be read by multiple pages without re-running the calculation in the frontend

Current implementation files:

- Backend route integration: [gameplan_routes.py](/Users/jamesdavies/gob-simplified/BackEnd/api/gameplan_routes.py)
- Weight calculator: [playbook_weights_utils.py](/Users/jamesdavies/gob-simplified/BackEnd/utils/playbook_weights_utils.py)
- Canonical playbook settings model: [playbook_settings_utils.py](/Users/jamesdavies/gob-simplified/BackEnd/utils/playbook_settings_utils.py)

## Purpose

This system exists so the product can show stable, shared offense-shot weighting values across:

- Set Lineup
- FCC Playbooks tab
- Playbooks page
- future GMO / coaching surfaces

The key design rule is:

- pages should read the cached backend-derived values
- pages should not independently re-derive these weights client-side

## Source Inputs

The calculation uses three sources:

1. `playbook_settings`
- `motion`
- `set_plays`
- `pc_order.offense`

2. Team play metadata
- `target_shooter` on set plays
- `motion_focus` is not part of this weighting math

3. Universal play definitions from `plays_collection`
- `target_shooter`
- explicit non-success shooter fields if present: `pos1`, `pos2`, `pos3`, `pos4`
- `skeletons`

## Canonical Storage Location

The derived cache is stored inside canonical `playbook_settings` as:

```python
playbook_settings["position_shot_weights"] = {
    "playbooks": {
        "PG": int,
        "SG": int,
        "SF": int,
        "PF": int,
        "C": int,
    },
    "playcall_center": {
        "PG": int,
        "SG": int,
        "SF": int,
        "PF": int,
        "C": int,
    },
    "_meta": {
        "algorithm_version": int,
        "source_hash": str,
        "computed_at": iso_datetime,
    },
}
```

Each of:

- `playbooks`
- `playcall_center`

must sum to exactly `100`.

## Per-Play Calculation Rules

Each offensive play is first converted into a per-play position distribution.

### 1. Resolve Target Shooter

The system resolves the canonical `target_shooter` in this priority:

1. successful skeleton shooter, if one can be derived
2. team play `target_shooter`
3. universal play `target_shooter`

This means successful-skeleton resolution wins any conflict.

### 2. Ignore Success Skeletons for the Remaining 40%

The success skeletons are not used to distribute the remaining weight.

Reason:

- the target shooter already receives the fixed success share

### 3. Target Shooter Gets 60%

For normal plays:

- `target_shooter = 60%`

### 4. Remaining 40% Comes from Non-Success Shooter Frequency

The remaining `40%` is distributed by frequency across non-success shooter instances.

Preferred source:

- explicit play-definition fields: `pos1`, `pos2`, `pos3`, `pos4`

Fallback source:

- non-success skeleton variants:
  - `mid_play_change`
  - `contested`
  - `broken`

The implementation prefers explicit DB fields when they exist, and falls back to skeleton parsing when they do not.

### 5. Zero Non-Success Shooter Case

If a play has zero non-success shooter instances:

- `target_shooter = 100%`

## Set Play Position Remapping

Set-play shot weights must reflect the user's saved `target_shooter`, not just the raw builder template.

To accomplish that, the weighting system mirrors the same alias-remap model used at gameplay runtime:

- `target_shooter`
- `pos1`
- `pos2`
- `pos3`
- `pos4`

These aliases are mapped into canonical positions (`PG`, `SG`, `SF`, `PF`, `C`) before shooter extraction.

This keeps the weights aligned with actual user settings.

## Playbooks Aggregation

`Playbooks` weights are aggregated from:

- `motion`
- `set_plays`

Rules:

- only plays with percentage `> 0` contribute
- each play contributes according to the user's saved playbook percentage
- user percentages are used directly
- no additional normalization is applied because the save contract already requires the total to equal `100`

Example:

- a play with a derived `SG = 72%` and `PF = 20%`
- weighted at `20%` in Playbooks

contributes:

- `SG += 14.4`
- `PF += 4.0`

## Playcall Center Aggregation

`Playcall Center` weights are aggregated from:

- `pc_order.offense`

Rules:

- only assigned offensive plays contribute
- each assigned offensive play is weighted evenly
- the divisor is the actual number of assigned plays

Examples:

- `8 plays` => `12.5%` each
- `2 plays` => `50%` each

## Rounding Rule

Internal aggregation is performed with floats.

Stored output is integer percentages.

After float aggregation:

- each position is floored first
- the remaining difference to `100` is distributed by largest remainder

This guarantees:

- `Playbooks` totals sum to `100`
- `Playcall Center` totals sum to `100`

## Refresh / Invalidation Model

The cache is designed to stay dynamic in two ways:

### User-driven changes

The cache is recomputed whenever the user saves Playbooks through:

- `POST /api/playbooks`

This includes:

- percentage changes
- Playcall Center ordering changes
- set-play `target_shooter` changes

### Play-definition changes

Universal play DB changes can alter the derived result even if the user changes nothing.

To handle that, the system stores:

- `algorithm_version`
- `source_hash`

`GET /api/playbooks` recomputes a fresh result and compares the cache metadata.

If the cache is missing or stale:

- it refreshes `playbook_settings.position_shot_weights`
- it persists the updated cache back through canonical `playbook_settings`

## Franchise / Tournament / Single-Game Behavior

The cache follows the same persistence location as canonical `playbook_settings`.

That means:

- Franchise FCC / pregame reads and writes use the franchise master source (`FTD`)
- active franchise gameplay uses the game-doc snapshot
- tournament behavior follows the same master-vs-game-doc split already used for Playbooks
- single-game mode stores against the game doc

The weight cache does not introduce a separate persistence model.

## API Contract

`GET /api/playbooks` now returns:

- `position_shot_weights`

This is the resolved cached output the frontend should consume.

## Implementation Notes

- The system currently only derives offense shot weights.
- Defensive schemes do not participate.
- `motion_focus` does not affect the weighting calculation in this version.
- The calculator uses explicit `pos1..pos4` DB fields if present, and only falls back to skeleton parsing when needed.
- The current algorithm version is `1`.

## Usage Guidance

If a page needs these values:

- read `position_shot_weights` from the Playbooks payload
- do not recreate the weighting logic in the page

This keeps all consumers aligned to one backend-derived source of truth.

## Future Audit Note

Any page or backend flow that currently derives similar shot-distribution logic independently should be audited and pointed at this shared cached output.

Primary expected consumers:

- Playbooks page
- FCC Playbooks tab
- Set Lineup
- future coaching / GMO support surfaces
