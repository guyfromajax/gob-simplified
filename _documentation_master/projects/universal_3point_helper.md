# Universal 3-Point Helper

## Goal

Replace skeleton-name-based 3-point detection with a coordinate-based helper that can work across all turn types: HCO, FCP, HCT, Final Turn, Fast Breaks, and future procedural shot systems.

## Current Problem

The current 3-point detection depends on finding the shooter's final `shoot` action in `roles["steps"]`, then checking the skeleton location name against `THREE_POINT_SPOTS`.

That works when the turn passes complete skeleton steps into `ShotManager.resolve_shot()`, but it can fail for turn types that have real shooter coordinates but do not include `roles["steps"]`. In those cases, a beyond-the-arc shot can be treated as a 2-pointer.

## Proposed Rule

Use the shooter's coordinates to determine whether the shot is behind the 3-point line.

The home/right-attacking 3-point line is represented by these existing court spots:

| Arc Point | Coords |
|---|---:|
| lower corner | `(88, 6)` |
| lower midCorner | `(81, 7)` |
| lower wing | `(73, 10)` |
| lower midWing | `(68, 14)` |
| key | `(64, 25)` |
| upper midWing | `(68, 36)` |
| upper wing | `(73, 40)` |
| upper midCorner | `(81, 43)` |
| upper corner | `(88, 44)` |

For a home/right-attacking offense, a shot is a 3-pointer if the shooter is at or farther from the basket than the boundary x-value at the shooter's y-value.

## Orientation Handling

Use one home/right-attacking geometry model.

Before testing:

- If the offense is home/right-attacking, use shooter coords as-is.
- If the offense is away/left-attacking, mirror x into home/right-attacking orientation:

```python
normalized_x = 100 - shooter_x
normalized_y = shooter_y
```

Then run the same 3-point boundary test.

## Boundary Test

1. Normalize shooter coords into home/right-attacking orientation.
2. Sort the arc points by y-value.
3. Given shooter `y`, find the two neighboring arc points around that y-value.
4. Linearly interpolate the boundary x-value at the shooter's y-value.
5. If `normalized_x <= boundary_x`, the shot is a 3-pointer.

Corner handling:

- If `y <= 6`, use the lower corner boundary: 3-pointer if `normalized_x <= 88`.
- If `y >= 44`, use the upper corner boundary: 3-pointer if `normalized_x <= 88`.

## Suggested Helper

```python
def is_three_point_shot_from_coords(coords, is_away_offense) -> bool:
    ...
```

## ShotManager Integration Plan

Update `ShotManager.is_three_point_shot()` to prefer coordinate geometry:

1. Use `roles["shot_spot"]` if present.
2. Otherwise use `shooter.coords` if present.
3. Fall back to the existing skeleton location-name check only if usable coords are missing.

This preserves the old behavior as a safety fallback while making coordinates the source of truth.

## Expected Benefit

All turn types can classify 3-point shots consistently as long as they provide accurate shooter coordinates. This avoids silent 2-point scoring when a turn has correct shot geometry but incomplete skeleton step data.
