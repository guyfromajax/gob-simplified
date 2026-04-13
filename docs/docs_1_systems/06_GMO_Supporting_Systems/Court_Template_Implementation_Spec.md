# Court Template Implementation Spec

## Purpose

Translate the high-level court template strategy into an implementable coordinate system for deterministic court generation.

This spec is intended to support:

- exact preservation of gameplay-relevant geometry
- controlled decorative variation
- deterministic rendering for all team court images

## Reference Assets

Primary reference set:

- [bentley_truman_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/bentley_truman/bentley_truman_court.jpg)
- [lancaster_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/lancaster/lancaster_court.jpg)
- [four_corners_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/four_corners/four_corners_court.jpg)
- [morristown_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/morristown/morristown_court.jpg)
- [ocean_city_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/ocean_city/ocean_city_court.jpg)
- [little_york_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/little_york/little_york_court.jpg)
- [xavien_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/xavien/xavien_court.jpg)
- [south_lancaster_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/south_lancaster/south_lancaster_court.jpg)

## Fixed Output

- asset key: `court`
- canonical filename: `FrontEnd/static/images/teams/<slug>/<slug>_court.jpg`
- canvas size: `3333 x 2083`

## Coordinate System

Use the same normalized court system already used by gameplay animation:

- X axis: `0 -> 100`
- Y axis: `0 -> 50`
- home offense attacks right

Known runtime anchors from code:

- home rim: `x=91, y=25`
- away rim: `x=9, y=25`
- home top key: `x=64, y=25`
- away top key: `x=36, y=25`
- clamp bounds:
  - `minX=5`
  - `maxX=95`
  - `minY=2`
  - `maxY=49`

Reference files:

- [courtConstants.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/js/phaser/animation/courtConstants.js)
- [courtClamp.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/js/phaser/animation/courtClamp.js)
- [courtPositions.js](/Users/jamesdavies/gob-simplified/FrontEnd/static/js/utils/courtPositions.js)

### Derived Pixel Anchors

Using the current runtime `0-100 x 0-50` court space against the fixed `3333 x 2083` canvas:

- away rim: `x=300, y=1042`
- home rim: `x=3033, y=1042`
- away top key: `x=1200, y=1042`
- home top key: `x=2133, y=1042`
- safe gameplay clamp box:
  - left: `x=167`
  - right: `x=3166`
  - top: `y=83`
  - bottom: `y=2041`

These are the most important translation anchors between the gameplay system and the rendered court template. Any generated court must preserve these relationships exactly.

## Implementation Principle

The court base should not be re-drawn by AI.

Instead:

1. lock one master geometry template
2. apply deterministic recolor masks
3. place logos/wordmarks into approved placement zones
4. export as a final flat JPG

## Fixed Geometry Layer

The following must remain identical across all teams:

- playable floor rectangle
- sidelines / baselines
- half-court line
- center circle
- both 3-point arcs
- both keys / paint rectangles
- free throw circles and dashed arcs
- basket / backboard / rim placement
- surrounding edge margins
- perspective and top-down framing

## Recolorable Regions

These should be implemented as masks or layer fills, not regenerated:

### Region R1: Outer Border / Wall

- left and right vertical border bands
- top and bottom margin glow/background treatment
- side typography color treatment

### Region R2: Paint / Key

- full rectangular lane
- interior semicircle fill
- outline accent where applicable

### Region R3: Hardwood Outer Zone

- the main floor wood tone outside any special interior hardwood treatment

### Region R4: Hardwood Inner Zone

- optional alternate hardwood tone inside the 3-point area or designated interior zone
- only used when a court is assigned the split-hardwood variant

## Decorative Placement Zones

These are first-pass normalized placement zones derived from the reference courts. They are intended as implementation boxes for deterministic composition.

## Bentley-Truman Measured Reference

Bentley-Truman is the best current master for extracting placement boxes because:

- its center mark is large and cleanly isolated
- its secondary marks are mirrored and easy to read
- its paint and border treatment are visually simple

Reference:

- [bentley_truman_court.jpg](/Users/jamesdavies/gob-simplified/FrontEnd/static/images/teams/bentley_truman/bentley_truman_court.jpg)

Measured/estimated placement boxes below are intended to be tight enough to code the first deterministic renderer. Mask extraction can still refine them later.

### Zone Z1: Center Logo Box

Purpose:

- primary center-court team mark

Bentley-Truman measured box:

- pixel box: `x=1325 -> 2006`
- pixel box: `y=689 -> 1348`
- normalized box: `x=39.8 -> 60.2`
- normalized box: `y=16.5 -> 32.4`

Notes:

- centered on midcourt
- can hold either mascot head, badge, monogram, or center wordmark treatment
- should remain inside the center circle height unless intentionally using a wordmark-led layout
- this is the cleanest measured box in the current reference set and should be treated as the default center mascot fit box

### Zone Z2: Left Upper Secondary Mark

Purpose:

- optional small decorative mark inside left 3-point region, upper side

Bentley-Truman estimated fit box:

- pixel box: `x=420 -> 980`
- pixel box: `y=245 -> 760`
- normalized box: `x=12.6 -> 29.4`
- normalized box: `y=5.9 -> 18.2`

Notes:

- actual artwork should fit comfortably inside the box, not touch the arc or top hardwood edge
- intended for small emblem, monogram, or compact badge, not a full mascot head

### Zone Z3: Left Lower Secondary Mark

Purpose:

- optional small decorative mark inside left 3-point region, lower side

Bentley-Truman estimated fit box:

- pixel box: `x=430 -> 985`
- pixel box: `y=1325 -> 1835`
- normalized box: `x=12.9 -> 29.6`
- normalized box: `y=31.8 -> 44.0`

Notes:

- mirrors Z2 across the horizontal centerline
- should stay clear of the lower arc and gloss-hotspot band as much as possible

### Zone Z4: Right Upper Secondary Mark

Purpose:

- optional small decorative mark inside right 3-point region, upper side

Bentley-Truman estimated fit box:

- pixel box: `x=2348 -> 2908`
- pixel box: `y=245 -> 760`
- normalized box: `x=70.5 -> 87.3`
- normalized box: `y=5.9 -> 18.2`

### Zone Z5: Right Lower Secondary Mark

Purpose:

- optional small decorative mark inside right 3-point region, lower side

Bentley-Truman estimated fit box:

- pixel box: `x=2348 -> 2908`
- pixel box: `y=1325 -> 1835`
- normalized box: `x=70.5 -> 87.3`
- normalized box: `y=31.8 -> 44.0`

### Zone Z6: Center Wordmark Box

Purpose:

- optional horizontal wordmark across or near midcourt

Cross-reference fit box from Little York / Xavien:

- pixel box: `x=350 -> 2980`
- pixel box: `y=620 -> 1520`
- normalized box: `x=10.5 -> 89.4`
- normalized box: `y=14.9 -> 36.5`

Notes:

- used for teams like Little York / Xavien style center wordmark treatments
- can overlap the center circle area
- should be visually centered on the midcourt line even when the lettering arcs
- wordmark art may overlap the center circle, but it should not encroach into either key or lane space

### Zone Z7: Right-of-Center Wordmark Box

Purpose:

- optional asymmetrical decorative slot between half-court and right 3-point arc

Estimated fit box:

- pixel box: `x=1650 -> 2625`
- pixel box: `y=725 -> 1460`
- normalized box: `x=49.5 -> 78.8`
- normalized box: `y=17.4 -> 35.0`

Notes:

- use for off-center wordmark, shield, logomark, or compact brand plate
- keep the asset fully clear of the right key outline and right 3-point arc
- this slot should be uncommon and variant-driven, not the default

### Zone Z8: Side Border Typography

Purpose:

- large vertical team name on left/right border bands

Rules:

- mirrored vertical type
- must stay within border bands only
- should never intrude onto the playable hardwood

Estimated border-band box:

- left border typography band: `x=0 -> 190`
- right border typography band: `x=3143 -> 3333`
- top safe inset from video-board trim: `y=120`
- bottom safe inset above lower glow hotspot: `y=1960`

## First-Pass Geometry Boxes

These are not final mask exports, but they are tight enough to drive first implementation.

### G1: Left Paint / Key

- approximate paint box: `x=150 -> 1085`
- approximate paint box: `y=672 -> 1411`

### G2: Right Paint / Key

- approximate paint box: `x=2248 -> 3183`
- approximate paint box: `y=672 -> 1411`

### G3: Main Center Circle Influence Zone

- approximate center circle fit box: `x=1140 -> 2193`
- approximate center circle fit box: `y=515 -> 1568`

### G4: Hardwood-Only Neutral Midcourt Strip

- approximate strip box: `x=1075 -> 2258`
- approximate strip box: `y=420 -> 1663`

Notes:

- this is the safest zone for large center branding
- any split-hardwood or specialty treatment must preserve the geometry edges around this zone and the center circle

## Approved Layout Variants

### Layout A: Center Mark + Two Secondary Marks

Examples:

- Bentley-Truman
- Morristown

Composition:

- Z1 center logo
- one mark in Z2 or Z3
- one mark in Z4 or Z5
- no dominant wordmark

### Layout B: Center Badge + Mirrored Small Marks

Examples:

- Lancaster

Composition:

- simplified Z1 center badge/initial
- mirrored side marks in two small zones

### Layout C: Center Mark + Asymmetrical Wordmark

Examples:

- Ocean City

Composition:

- Z1 center logo
- one or two small secondary marks
- wordmark in Z7

### Layout D: Center Wordmark Dominant

Examples:

- Xavien
- Little York

Composition:

- dominant wordmark in Z6
- optional reduced or absent center mascot
- optional side marks

## Hardwood Variants

### H1: Standard Hardwood

- single wood tone across playable surface

### H2: Split Hardwood

- alternate wood tone in the interior 3-point/half-court-adjacent region
- should be uncommon

### H3: Specialty Hardwood

- only for hand-picked showcase teams
- still must preserve fixed geometry

## Team Inputs Required

Each generated court should be driven by structured inputs:

- `team_name`
- `team_slug`
- `primary_color`
- `secondary_color`
- `paint_color`
- `outer_hardwood_tone`
- `inner_hardwood_tone` (optional)
- `layout_variant`
- `hardwood_variant`
- `center_logo_asset`
- `secondary_mark_asset_1` (optional)
- `secondary_mark_asset_2` (optional)
- `wordmark_asset` (optional)

## Recommended Rendering Pipeline

1. Start from master geometry base.
2. Apply recolor masks for border, paint, and hardwood regions.
3. Place the primary center-court asset in Z1 or Z6 depending on layout.
4. Place optional secondary marks in Z2-Z5.
5. Place optional wordmark in Z6 or Z7.
6. Export flat final JPG at `3333 x 2083`.

## Proof-of-Concept Recommendation

Before league-wide generation:

1. choose Bentley-Truman as the master geometry base
2. define masks for R1-R4
3. define placement boxes Z1-Z8 in code
4. render one non-A1 team court with deterministic composition
5. test it in the live animation system

## Validation Requirement

The proof-of-concept court must be accepted only if:

- animation aligns exactly with all gameplay-relevant lines and baskets
- no gameplay object appears visibly off-template
- decorative variation remains within approved placement boxes
- file dimensions and naming match frontend expectations exactly
