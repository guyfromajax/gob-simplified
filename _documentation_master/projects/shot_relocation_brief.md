# Shot Relocation Brief

**Status:** ACTIVE / implementation deferred — re-audited 2026-08-08
**Created:** July 23, 2026  
**Scope:** Shot micro-movement release relocation and shot-value preservation  
**Canonical system reference:** [`../06_Gameplay_Systems/Shot_Micro_Movements_System.md`](../06_Gameplay_Systems/Shot_Micro_Movements_System.md)

## Current-code audit (2026-08-08)

This work has **not** been implemented and the brief must remain active:

| Contract | Current implementation |
|---|---|
| Transition-aware outside relocation | Missing. `plan_non_dunk_shot_micro()` still sends every `OUTSIDE_MOVING_FAMILIES` choice to `_pick_outside_dribble_target()`. |
| 80/20 stay/cross-value roll | Missing. No 3→3, 3→2, 2→2, or 2→3 planner or tuning constants exist. |
| Destination catalogs | Missing. Only `OUTSIDE_ARC_SPOT_ORDER` and immediate adjacent-arc selection exist. |
| Inside/attack two-point invariant | Missing for ordinary families. `compute_micro_release_coord()` applies their relative movement and final geometry remains authoritative. |
| Evidence of the edge case | `TestMicroReleaseClassification::test_fade_away_release_can_cross_into_three` explicitly verifies that a two-point start currently becomes a three after the fade. |
| Stopped-Attack exception | Implemented separately and still correct: `plan_stopped_attack_pullup()` freezes the wall coordinate and classifies it geometrically. |
| Relocation telemetry | Missing. The transition/fallback fields and weekly aggregation proposed in §5 Phase 4 do not exist. |

The canonical Shot Micro-Movements document accurately describes the current
adjacent-arc behavior and release-coordinate classification. It should not be
rewritten to describe this proposal until the runtime work is authorized and
implemented.

## 1. Purpose

Correct shot micro-movement relocation that can artificially turn too many
field-goal attempts into three-pointers.

The current system classifies a field goal from its post-micro release
coordinate. This is the correct general contract, but the three relocating
outside families currently move only to named three-point arc spots. A shooter
who begins inside the arc can therefore be moved behind the arc and credited
with a three. Separately, relative displacement by an inside family such as
`fade_away` can cross the arc and reclassify an intended inside shot as a three.

The implementation must preserve the existing micro-family selection, animation,
contest, scoring, and release-coordinate systems while making relocation
intentional and basketball-plausible.

## 2. Locked Decisions

### 2.1 Families in scope

The new relocation selection applies only to the existing outside `move_to`
families:

- `dribble_shoot`
- `dribble_pump_shoot`
- `pump_dribble_shoot`

The following outside families remain static and are excluded from the
relocation probability:

- `set`
- `set_pump`

Static families must never become relocating families.

### 2.2 Other movement families

Existing inside and attack movement geometry remains unchanged.

Inside families:

- `strong_inside`
- `fade_away`
- `jab_step`
- `under_and_up`
- `straight_inside`

Attack families:

- `strong_attack`
- `pullup_attack`

There is no implemented family named `upper_and_under`; `under_and_up` is the
applicable family.

Ordinary semantic `inside` and `attack` movement families must not manufacture
a three through micro displacement. Dunks remain forced-two.

**Implemented exception — stopped Attack pull-up (2026-07-23):** a Tier B/C
drive stop freezes the exact stop coordinate and pins the stationary
`pullup_attack` family. It never enters an outside relocating family, but its
shot value is determined geometrically from the frozen coordinate. Therefore
an inside-arc stop is a two and a genuine behind-arc stop is a three. A
geometric three uses Outside scoring weights and the existing three-point
distance penalty.

### 2.3 Starting-value authority

For an outside relocating family, determine the starting value from the actual
authoritative pre-micro shooter coordinates against the geometric three-point
arc. Do not infer the starting value from the skeleton spot name or semantic
shot type.

### 2.4 Relocation distribution

The 80/20 values are directional tuning targets for relocating families only;
they are not intended as a hard distribution across all shot attempts.

If the pre-micro coordinate is a three:

- 80%: relocate to another three-point location.
- 20%: relocate to a two-point location.

If the pre-micro coordinate is a two:

- 80%: relocate to another two-point location.
- 20%: relocate to a three-point location.

Static outside families do not participate in these rolls.

### 2.5 Vertical regions

Classify vertical region from the pre-micro y coordinate:

- `y < 22`: lower
- `22 <= y <= 28`: center
- `y > 28`: upper

Upper destinations stay upper and lower destinations stay lower unless a
center rule explicitly applies. Center shooters may choose upper or lower
destinations.

### 2.6 Availability

- Only offensive teammates determine whether a target is occupied.
- Retain the current three-grid Euclidean occupancy radius.
- Exclude the shooter's current location from relocation candidates.
- If multiple equally valid candidates remain, choose randomly using the
  simulation RNG.
- If the selected destination category has no legal open destination, use a
  stationary release at the original pre-micro coordinate.
- Do not switch to the opposite value category as a fallback.
- The stationary fallback must retain the value produced by geometric
  classification of its original release coordinate.

## 3. Destination Rules

### 3.1 Three to three

Retain adjacent-arc movement:

- corner -> midCorner
- midCorner -> corner or wing
- wing -> midCorner or midWing
- midWing -> wing or key
- key -> upper or lower midWing

Side-qualified locations remain on their current vertical side. The key is a
center location and may move upper or lower.

If all adjacent arc destinations are occupied, release stationary. Do not
search farther around the arc.

If the shooter is geometrically behind the arc but not at a defined named
three-point spot, find the nearest named three-point spot and use that spot as
the source for adjacency and border mapping.

### 3.2 Three to two

When the roll selects movement inside the arc, use an open bordering location
associated with the nearest/current named three-point source spot:

| Three-point source | Eligible two-point destination families |
|---|---|
| corner | midBaseline, bird |
| midCorner | midBaseline, bird, apex |
| wing | bird, apex, highPost, topLane |
| midWing | bird, apex, highPost, topLane |
| deep wing | bird, apex, highPost, topLane |
| deep baseline | bird, apex, highPost, topLane |
| key | topLane, highPost, apex, bird |
| deep key | topLane, highPost, apex, bird |

Apply the shooter's upper/lower qualifier to all side-specific destinations.
`topLane` is a center destination. Key/deep-key and other center sources may
choose upper or lower variants.

Use the repository's exact canonical names:

- `deep lower wing` / `deep upper wing`
- `deep lower baseline` / `deep upper baseline`
- `deep key`

### 3.3 Two to two

Choose randomly among open two-point locations:

- Any eligible two-point location in the shooter's vertical half.
- Center `topLane`.
- Center `midLane`.

The same-side pool includes:

- highPost
- midPost
- lowPost
- apex
- bird
- midBaseline

It also includes `topLane` and `midLane` as center options.

Exclude:

- `basketSpot`
- The shooter's current location
- Occupied locations
- Locations in the opposite vertical half

Center shooters may choose upper-side, lower-side, or center two-point
destinations.

### 3.4 Two to three

Choose the nearest open named three-point location that is legal for the
shooter’s vertical region:

- Lower shooters may use lower-side arc locations.
- Upper shooters may use upper-side arc locations.
- Center shooters may use upper- or lower-side arc locations, including the
  center key when applicable.

If multiple nearest legal targets are tied, choose randomly. If no legal target
is open, release stationary.

## 4. Recommended Resolution Order

Preserve the existing architecture and change only the destination-planning
seam:

1. Resolve the semantic `shot_type` as today.
2. Select the micro-movement family from the existing family pool as today.
3. If semantic `shot_type` is `inside` or `attack`, preserve its current
   movement and prevent micro displacement from manufacturing a three. The
   implemented stopped-Attack exception instead pins `pullup_attack` and
   classifies the exact frozen stop coordinate geometrically.
4. If the family is static or otherwise not in `OUTSIDE_MOVING_FAMILIES`,
   preserve its current behavior.
5. For an outside relocating family:
   1. Read the authoritative pre-micro coordinate.
   2. Classify that coordinate geometrically as two or three.
   3. Roll the configured stay/cross value category.
   4. Build legal destination candidates for the applicable transition.
   5. Filter the current location and teammate-occupied destinations.
   6. Select among valid candidates according to the locked nearest/adjacent/
      random rule.
   7. Pin the result once as `micro_move_to_coord`.
   8. If none is valid, pin no destination and retain the original coordinate.
6. Compute `micro_release_coord` from that pinned plan.
7. Classify outside shot value from the final release coordinate as today.
8. Reuse the pinned coordinate during schema emission; never re-roll it.

This order preserves downstream shot-score, defense, contest, block, animation,
clock, and telemetry behavior.

## 5. Implementation Plan

No implementation is authorized yet. When resumed:

### Phase 1: Destination catalog and helpers

1. Add explicit named catalogs for:
   - Arc adjacency.
   - Arc-to-two border mappings.
   - Side-specific two-point destinations.
   - Center two-point destinations.
2. Add helpers that:
   - Classify vertical region from y.
   - Resolve canonical side-qualified names.
   - Find the nearest named geometric arc spot.
   - Determine whether two display coordinates represent the same current
     location within the existing occupancy tolerance.
   - Filter teammate-occupied targets.
3. Continue using mirrored display coordinates for away offense through the
   existing `_arc_spot_display_coord`/`get_away_player_coords` contract.

### Phase 2: Outside relocation planner

1. Replace the current unconditional adjacent-arc choice inside the outside
   relocation seam with a transition-aware planner.
2. Run it only for `OUTSIDE_MOVING_FAMILIES`.
3. Use pre-micro geometric classification to choose the 3->3, 3->2, 2->2, or
   2->3 branch.
4. Return a pinned destination or `None` for stationary fallback.
5. Ensure family selection and static fallback selection remain unchanged.

### Phase 3: Inside/attack two-point invariant

1. At final shot-value classification, prevent ordinary `inside`/`attack`
   micro displacement from manufacturing a three. Exempt the implemented
   stopped-Attack pull-up: its frozen stop coordinate remains authoritative
   for 2/3 classification.
2. Preserve current micro release coordinates and animation.
3. Ensure block, foul, PIP, threshold, and stat logic continues to receive the
   same semantic shot type.
4. Confirm fast-break paths that intentionally force at-rim twos remain
   unchanged.

### Phase 4: Telemetry

Add enough temporary or permanent diagnostic data to validate the change:

- `pre_micro_shot_value`
- `post_micro_shot_value`
- `micro_relocation_transition` (`3_to_3`, `3_to_2`, `2_to_2`, `2_to_3`,
  `stationary`, or not applicable)
- Pre-micro coordinate
- Pinned destination
- Micro family
- Stationary fallback reason where useful

Week aggregation should report relocation attempts, successful relocations,
stationary fallbacks, and 2<->3 conversions.

### Phase 5: Documentation

After implementation, update:

- `Shot_Micro_Movements_System.md`
- `Tunable_Constants.md` if the 80/20 probabilities become named constants
- Any shot-classification section in `Shot_System.md`
- Relevant system diagrams and verification checklists

Do not mark this brief implemented until runtime changes and tests are complete.

## 6. Verification Plan

### 6.1 Unit tests

Cover at minimum:

1. Only the three outside moving families invoke relocation planning.
2. `set` and `set_pump` remain stationary.
3. Inside/attack families retain their existing movement coordinates.
4. `fade_away`, `jab_step`, and `under_and_up` cannot become threes.
5. Pre-micro geometric classification, not named shot type, selects the
   relocation branch.
6. All 3->3 adjacency mappings, including key upper/lower behavior.
7. Undefined behind-arc coordinates use the nearest named arc source.
8. Every 3->2 border mapping on upper and lower sides.
9. 2->2 stays same-side or center and excludes `basketSpot`.
10. 2->3 selects the nearest legal open arc spot.
11. Center-band boundaries at y=22 and y=28 are inclusive center.
12. Current location is excluded.
13. Teammate occupancy uses the current three-grid radius.
14. Multiple valid/tied candidates use seeded random selection.
15. No legal destination produces a stationary release without changing value.
16. Away-offense destinations remain on the correct mirrored half.
17. Resolve-time and emit-time release coordinates remain identical.

### 6.2 Integration tests

Verify HCO ball-handler and dish/hot-read shots through `ShotManager.resolve_shot`:

- A two-point start can intentionally remain two or relocate to three.
- A three-point start can remain three or relocate to two.
- Inside/attack attempts always record FGA/FGM as two-point attempts.
- Outside post-release classification writes correct `is_three`, `shot_value`,
  3PA, and 3PM.
- Contest and make/miss outcomes still use the same authoritative release plan.

### 6.3 Simulation validation

Run at least three weekly samples and compare:

- Overall 3PA share.
- HCO 3PA share by early/mid/late tier.
- Relocation transition counts.
- Stationary fallback rate.
- 2->3 and 3->2 net conversion.
- FGA/team, FG%, 3PT%, and 2PT%.
- Blocks/team to ensure the separate block calibration remains stable.

The primary success condition is a reduction in artificial net 2->3
conversions without suppressing total shot volume or changing static-family
selection.

## 7. Non-Goals

- Do not change outside-shot selection weighting in this task.
- Do not change static family frequency.
- Do not make static families relocate.
- Do not change make/miss thresholds or three-point distance penalties.
- Do not redesign inside/attack footwork.
- Do not change contest or block calculations.
- Do not change teammate occupancy radius.
- Do not consider defenders when deciding destination availability.
- Do not alter FT logic.

## 8. Open Items

The behavioral design is fully aligned. No unresolved product questions remain
for the scoped implementation. Work is intentionally paused pending completion
of a separate, more pressing item.
