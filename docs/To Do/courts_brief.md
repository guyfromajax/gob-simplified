# Courts Brief

This brief captures the agreed deterministic percentage rules for generating the remaining `119` non-A1 courts.

`Abilene` is the approved template baseline and is not included in these rollout percentages.

## Scope

These rules apply to:
- all remaining non-A1 teams without existing A1 reference courts
- deterministic court generation only
- no center-court logos, secondary logos, or wordmarks in this phase

## Hardwood Variant Distribution

Hardwood variants are defined as:
- `inside 3-point line / outside 3-point line`

Distribution:
- `medium/medium`: `35%`
- `light/light`: `5%`
- `dark/dark`: `10%`
- `medium/light`: `10%`
- `medium/dark`: `10%`
- `light/dark`: `5%`
- `light/medium`: `10%`
- `dark/light`: `5%`
- `dark/medium`: `10%`

These total `100%`.

## Lane Fill Distribution

Distribution:
- `primary color`: `70%`
- `secondary color`: `20%`
- `inside hardwood color`: `10%`

## Semicircle Fill Distribution

This refers to the filled semicircle bordering the lane.

Distribution:
- `primary color`: `45%`
- `secondary color`: `45%`
- `inside hardwood color`: `10%`

## Border / OOB Fill Distribution

This refers to all OOB border fill sections:
- vertical bars
- horizontal top and bottom bars

Distribution:
- `primary color`: `45%`
- `secondary color`: `20%`
- `black`: `20%`
- `outside hardwood color`: `10%`
- `inside hardwood color`: `5%`

## Line Color Distribution

One line color is chosen per court and applied consistently to:
- OOB lines
- free throw line
- 3-point line
- lane borders
- dashed interior free-throw semicircle

Base distribution:
- `dark grey`: `25%`
- `black`: `25%`
- `white`: `25%`
- `primary color`: `25%`

### Line Color Fallback Rule

If the chosen line color is `primary`:
1. If the lane fill or semicircle fill also uses `primary`, do not use `primary` for lines.
2. Fall back to `secondary`.
3. If the lane fill or semicircle fill also uses `secondary`, fall back to `dark grey`.

So the fallback chain is:
- `primary`
- then `secondary`
- then `dark grey`

## Current Template Baseline

`Abilene` is the approved geometry/template baseline for rollout:
- court geometry validated
- basket/backboard/rim placement validated
- OOB line/border geometry validated
- lane / semicircle relationship validated
- dashed interior free-throw semicircle added

## Rollout Note

When rolling to the remaining `119` courts:
- preserve Abilene template geometry exactly
- vary only deterministic assignments:
  - hardwood variant
  - lane fill
  - semicircle fill
  - OOB fill
  - line color
