# Coordinate Orientation Audit

**Location:** `docs/docs_1_systems/00_General_Systems/Coordinate_Orientation_Audit.md` (moved from `docs/To Do/`). Relative links below resolve to repo-root `BackEnd/`.

## Purpose

Document how backend runtime coordinates are being set relative to frontend animation coordinates, and identify where the codebase is mixing:

- `HOME orientation` coords for backend logic
- `current display orientation` coords for animation / away-offense presentation

This is the working audit for the shot-location / opposite-side-defender bug.

## Current Intended Contract

The codebase clearly wants this rule:

- Core court spot constants are defined in `HOME orientation`
- Away offense is represented by flipping x with `100 - x`
- Some backend gameplay logic assumes stored runtime coords are in `HOME orientation`
- Animation systems often operate in current display orientation

Relevant flip helper:

- [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): `get_away_player_coords()` at lines 2086-2100
- [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): `getAwayTeamCoords()` at lines 2102-2110

## Main Finding

The backend does **not** maintain one consistent orientation contract for `player.coords`.

The dominant failure pattern is:

1. Animation generation flips coords into away/display orientation when away is on offense.
2. Animation sync writes those animation-final coords directly into `player.coords`.
3. Later backend logic sometimes reads those stored coords as if they are canonical `HOME orientation`.
4. Other code paths then mix those stored coords with freshly derived `HOME`-based spot coords or shot spots.

That creates:

- defenders on the opposite side of the floor
- mixed shooter/defender spatial truth at shot time
- fallback shot spots like `(25, 50)` being used when real shot coords were not resolved

## Highest-Risk Leak Point

### Animation finals are written directly into runtime coords

`apply_coords_from_animations_list()` takes the final animation row and writes it straight into `player.coords` with no normalization:

- [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): lines 2265-2290

This is the most important write in the system, because animation rows are frequently built in away/display orientation when away is on offense.

## HCO Shot Path

HCO currently does this:

1. Build animations from skeleton
2. Sync animation finals into lineup player coords
3. Override only the shooter from the skeleton last-step shot location
4. Resolve the shot

Relevant code:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 4806-4880
- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): `set_shooter_coords_from_skeleton_last_step()` lines 3629-3663

Implication:

- defenders come from animation-final synced coords
- shooter may come from skeleton-derived shot coords

If the animation-final defender coords were persisted in away/display orientation and later logic assumes HOME orientation, HCO shot resolution becomes spatially inconsistent.

## Where Away-Offense Animation Coords Are Explicitly Flipped

### Offensive animation build

In `Animator.skeleton_to_animations()`, location-based coords are flipped for away offense:

- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1271-1278

This means offensive animation movement rows are intentionally stored in away/display orientation when away is on offense.

### Zone defensive animation build

Zone defensive placement explicitly says:

- offensive coords are stored in away orientation if away offense
- zone functions return HOME orientation
- then defensive coords are flipped back into away orientation to match offensive animation coords

Relevant code:

- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1723-1733
- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1821-1829
- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1853-1861

This is internally coherent for animation, but it becomes dangerous once those animation finals are later written into canonical runtime state.

## Shared Defense Contract

`get_defender_coords()` says:

- input may be home or away orientation
- internal math happens in HOME orientation
- output is returned in the same orientation as input

Relevant code:

- [BackEnd/utils/shared_defense.py](../../../BackEnd/utils/shared_defense.py): lines 1521-1622

This is a valid contract for a wrapper, but it only works if callers know what orientation their input coords are in.

Right now the codebase often does not.

## Fast Break Contract Mismatch

Fast break logic contains explicit HOME-orientation assumptions:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 1395-1432

But the same fast-break path falls back to `player.coords` if release/get-back coords are unavailable:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 1218-1236

That is a concrete bug risk:

- if `player.coords` previously came from synced animation finals in away/display orientation
- and this fast-break code assumes HOME orientation
- then the fallback reads the wrong side of the court

Fast-break animation code is also mixed:

- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 93-128

That function says outlet start is "guaranteed HOME orientation", but coordinate flipping there was commented out. So FB depends heavily on upstream writers being correct and consistent.

## Coordinate Writers Inventory

### Category A: Writers that are likely meant to be canonical / logic-safe

These appear to write explicit gameplay positions rather than FE-facing animation positions.

- [BackEnd/models/shot_manager.py](../../../BackEnd/models/shot_manager.py): lines 1218-1265, 1348-1388, 1668-1708
  - get-back, release, rebounder staging coords
- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 1688-1700
  - fast-break shot spot written to shooter
- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 2087-2091, 5686-5690, 6890-6894
  - stealer coords written from stored or extracted locations
- [BackEnd/utils/quarter_start.py](../../../BackEnd/utils/quarter_start.py): lines 136, 152
  - quarter-start destinations

These still need orientation review, but they are not the main leak.

### Category B: Writers that are clearly dangerous

- [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): lines 2265-2290
  - syncs animation finals directly into `player.coords`
- [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): lines 2293-2350
  - `sync_lineup_coords_from_turn()` also persists animation finals and overlay coords directly into `player.coords`

These are the most likely places where display-oriented coords are contaminating backend runtime state.

### Category C: Ambiguous / mixed-orientation writers

- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1230-1282
  - offensive animation coords built from HOME spots then flipped for away offense
- [BackEnd/models/animator.py](../../../BackEnd/models/animator.py): lines 1718-1861
  - zone defender animation built from orientation-aware logic and then flipped again for away offense
- [BackEnd/engine/rim_runner_fast_break.py](../../../BackEnd/engine/rim_runner_fast_break.py): lines 263-266, 409, 950-952, 1140-1142, 1193-1195, 1323-1325
  - fast-break writers that may be fine if their source payload is canonical, but need contract review

## Specific Answer To "Skipped Flip Or Double Flip?"

It is **not** one clean single skipped flip.

The more accurate diagnosis is:

- animation/display orientation is intentionally created in several places
- that orientation then leaks into runtime `player.coords`
- later logic sometimes treats leaked coords as HOME orientation

So the observed bug behaves like:

- missed normalization in some paths
- mixed orientation in others
- effective double-flip symptoms in still others

The codebase is currently doing all three.

## The Two Most Important Bugs

### Bug 1: Runtime coords are not canonical

`player.coords` is sometimes being used as:

- canonical backend logic coords
- and also as FE-facing animation/display coords

That has to stop.

### Bug 2: HCO shot resolution uses mixed spatial sources

At shot time:

- defenders are synced from animation-final coords
- shooter may be overridden from skeleton shot spot

That means shot resolution does not use a single authoritative release frame.

## Recommended Cleanup Rule

Pick one invariant and enforce it everywhere:

### Recommended invariant

- `player.coords` is always stored in `HOME orientation`
- animation payloads may be flipped for frontend display
- any sync from animation back into backend must normalize to HOME orientation before writing to `player.coords`

This matches the assumptions already present in several gameplay systems and avoids poisoning runtime logic with presentation orientation.

## Recommended Next Audit Steps

1. Audit every writer to `player.coords` and mark:
   - writes HOME orientation
   - writes display/current orientation
   - ambiguous

2. Review `apply_coords_from_animations_list()` and `sync_lineup_coords_from_turn()` first.
   - These are the most dangerous writers.

3. For HCO, verify one full bad possession across these three snapshots:
   - animation final frame
   - post-sync `player.coords`
   - coords actually used by `resolve_shot()`

4. Remove silent fallback semantics for shot locations.
   - `(25, 50)` and similar fallback centers should be treated as degraded state, not valid release locations.

5. Define one shot-time "release frame" object for:
   - shooter
   - defenders
   - rebounder / putback shooter

No shot logic should mix skeleton shot spot, synced animation coords, and old lineup coords ad hoc.

## Working Conclusion

The backend/frontend sync did not fail because animation is wrong.

It failed because:

- animation orientation and runtime logic orientation were never cleanly separated
- and the system writes one into the other without normalization

That is the real bug class to fix.

## Implementation Work Plan

This is the recommended execution order. The goal is to fix the coordinate contract without breaking animation rendering or special-case branches.

### Phase 1: Lock the Runtime Invariant

**Decision:**

- `player.coords` must always be stored in `HOME orientation`
- FE animation payloads may remain in display/current orientation
- any animation-to-backend sync must normalize before writing runtime coords

**Do not change yet:**

- frontend animation payload format
- shot contest thresholds
- defender stat attribution logic

Those are downstream concerns.

### Phase 2: Fix the Two Poisoning Sync Points First

These two functions should be treated as the primary entry points where display-oriented coords leak into backend runtime state:

1. `apply_coords_from_animations_list()`
   - [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): lines 2265-2290
2. `sync_lineup_coords_from_turn()`
   - [BackEnd/utils/shared.py](../../../BackEnd/utils/shared.py): lines 2293-2350

**Required change conceptually:**

- when reading animation-final coords, determine whether they are in away/display orientation
- if so, normalize them back to HOME orientation before writing `player.coords`

**Validation goal after Phase 2:**

- after any turn sync, `player.coords` should be HOME-oriented regardless of who was on offense

### Phase 3: Define an Explicit Normalization Boundary

Do not let orientation decisions remain implicit.

Introduce and use one explicit mental model:

- `animation coords`: may be current/display orientation
- `runtime coords`: always HOME orientation

Every handoff must choose one of these intentionally.

**Likely affected call sites after Phase 2:**

- any function that currently assumes animation-final coords can safely become runtime coords
- any fast-break or stopper path that reads `player.coords` after an animation sync

### Phase 4: Reconcile HCO Shot Resolution Around One Spatial Truth

After runtime coords are normalized, re-check HCO shot resolution:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 4876-4879

Current sequence:

- sync defenders from animations
- override shooter from skeleton shot spot

That may still be acceptable if both are now effectively HOME-oriented and represent the same release frame.

If not, the next step is:

- make release-frame coords explicit for all ten players
- stop mixing synced lineup coords with independently-derived shooter coords ad hoc

But this should only be addressed **after** Phase 2 normalization is complete.

### Phase 5: Review Fast Break Fallbacks

Fast break is the next highest-risk branch because it explicitly assumes HOME orientation in places while also falling back to `player.coords`.

Key fallback:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 1232-1236

Key assumption:

- [BackEnd/engine/phase_resolution.py](../../../BackEnd/engine/phase_resolution.py): lines 1395-1432

After Phase 2:

- re-verify that FB fallback reads now see HOME-oriented runtime coords
- remove any compensating logic that only existed because runtime coords were inconsistent

### Phase 6: Re-Test In Priority Order

Re-test in gameplay volume order, not code complexity order:

1. HCO
2. Fast Break
3. OREB Putback Attempt
4. FCP/HCT Shot
5. Final Shot Scenario

**What to verify first:**

- no more opposite-side defender clusters in HCO shot debug
- far fewer `no_defender_shots`
- `25,50` fallback usage becomes rare and attributable

### Phase 7: Only Then Revisit Secondary Systems

Only after coord normalization is stable:

- defender attribution refinement
- contest-box calibration
- secondary defender stat rules
- fallback shot-location hardening

Those should not be the first fix layer.

## Minimal Confirmation Debugging To Keep

Broad logging should now stop expanding. The only debugging worth keeping during implementation is:

1. one log that states whether synced animation coords were normalized before writing runtime state
2. one log for fallback shot-location usage (`25,50` / center fallback)
3. one HCO shot-time sample log to confirm:
   - shooter runtime coords
   - defender runtime coords
   - all in HOME orientation before contest check

Anything broader than that will add noise faster than signal.

## Recommended First Code Change

If implementation starts, the first code change should be:

- normalize coords inside `apply_coords_from_animations_list()` before writing to `player.coords`

The second should be:

- apply the same normalization rule inside `sync_lineup_coords_from_turn()`

That is the narrowest, highest-leverage place to begin.
