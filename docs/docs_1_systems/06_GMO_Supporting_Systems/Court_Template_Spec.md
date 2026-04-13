# Court Template Spec

## Purpose

Define a deterministic system for generating team court images that preserve the exact geometry required by the animation system while allowing controlled variation in colors, center-court branding, and optional decorative marks.

This spec is based on the 8 existing Conference A1 reference courts:

- Bentley-Truman
- Lancaster
- Four Corners
- Morristown
- Ocean City
- Little York
- Xavien
- South Lancaster

## Non-Negotiable Constraint

Court images must be generated with exact placement of all gameplay-relevant elements. AI image generation should not be used for the court base layout.

The court base must be deterministic.

## Confirmed Shared Base

All 8 reference courts share the same canvas size:

- `3333 x 2083`

And visually they share the same fixed geometry for:

- outer court rectangle
- center line
- center circle
- both 3-point arcs
- both lane / paint boxes
- free throw circles and dashed arcs
- basket / backboard / rim placement
- surrounding margin / border composition

This means the correct implementation path is:

1. lock one master court geometry template
2. vary only approved decorative and color layers

## Fixed Geometry Layer

The following should be treated as pixel-locked and identical across every team court:

- canvas dimensions
- court floor rectangle position
- key / paint dimensions and position
- 3-point line and arc position
- free throw line / semicircle position
- center line and center circle position
- basket / backboard / rim placement
- edge spacing around the court
- playable safe area used by animation

This layer should come from a master source asset, not be regenerated.

## Variable Decoration Layer

The references show consistent variation in decorative elements while preserving geometry.

### Always Present

- team-colored lane / paint treatment
- side-wall team name typography
- center-court team identity treatment

### Sometimes Present

- small secondary logos inside the 3-point area and outside the lane
- wordmark or mascot wordmark between the center line and one of the 3-point arcs
- logomark-only layouts
- center-logo-only layouts

## Hardwood Color System

Hardwood treatment should be modeled as its own controlled variable layer, separate from:

- border / wall color
- paint / key color
- logo / wordmark placement

The reference courts show that hardwood can vary independently across teams.

### Hardwood Variants

#### Variant H1: Standard Hardwood

- one continuous hardwood tone across the playable floor
- most common default

#### Variant H2: Split Hardwood

- one hardwood tone outside the 3-point area
- a second hardwood tone inside the 3-point area or adjacent interior floor zone
- should be used more sparingly
- intended to feel more special and less common across the league

#### Variant H3: Specialty Hardwood

- reserved for hand-picked showcase teams only
- may include more custom hardwood treatment, but must still preserve the exact fixed geometry

### Hardwood Rules

- hardwood variation must never alter line placement, basket placement, or any gameplay-relevant geometry
- hardwood regions should be implemented as deterministic mask/fill zones
- split-hardwood treatment should be uncommon and intentionally assigned, not randomly scattered across all teams
- the system should allow independent control of:
  - outer hardwood tone
  - inner hardwood tone
  - paint color
  - border / wall color

## Observed Layout Families

The 8 references suggest a small set of reusable decoration templates:

### Variant A: Center Mascot + Two Small Side Marks

Examples:

- Bentley-Truman
- Morristown

Characteristics:

- large center mascot/logo at midcourt
- one small decorative mark per half in the open area outside the lane
- no large horizontal wordmark at center

### Variant B: Center Initial / Badge + Side Marks

Examples:

- Lancaster

Characteristics:

- simpler center mark, often letterform-based
- mirrored small marks in each half

### Variant C: Center Mascot + One Horizontal Wordmark

Examples:

- Ocean City

Characteristics:

- large center logo
- wordmark placed off-center between midcourt and arc
- optional smaller side marks

### Variant D: Center Wordmark Dominant

Examples:

- Xavien
- Little York

Characteristics:

- large horizontal wordmark through center circle area
- optional small side marks
- center logo may be absent or reduced

## Recommended Build System

Use layered deterministic composition, not AI generation.

### Base Assets

- master court geometry template
- optional mask layers for:
  - paint areas
  - inner hardwood zone
  - outer hardwood zone
  - line overlays
  - border / wall background
  - lighting / floor gloss overlays

### Team Inputs

- primary color
- secondary color
- hardwood variant
- outer hardwood tone
- inner hardwood tone, when applicable
- center-court logo
- optional small secondary logo
- optional wordmark / logomark
- assigned court layout variant

### Output

- `FrontEnd/static/images/teams/<slug>/<slug>_court.jpg`

## Proposed Rendering Rules

1. Start from a master geometry template.
2. Apply team color mapping only to approved recolorable regions.
3. Place center-court mark inside a fixed placement box.
4. Place optional side marks inside fixed placement boxes.
5. Place optional wordmark inside a fixed placement box.
6. Export to the exact reference canvas size.

## What Must Be Measured Next

This first-pass spec confirms the architecture, but the implementation still needs exact placement coordinates.

We still need to document:

- exact center-court logo bounding box
- exact side-mark bounding boxes
- exact optional wordmark bounding boxes
- exact hardwood mask regions for standard vs split-hardwood variants
- exact recolorable regions
- exact line / paint mask boundaries

## Proof-of-Concept Plan

Before scaling to all teams:

1. choose one reference court as the master geometry source
2. map its fixed zones and placement boxes
3. generate one non-A1 team court deterministically
4. verify it in the live animation system

Only after that should we scale across the full league.

## Current Conclusion

Yes, it should be possible to create all remaining team courts with 100% precision, but only if:

- geometry is template-based
- all line and basket positions remain fixed
- only color and branding layers vary
- decorative variation is constrained to a small approved set of layouts
