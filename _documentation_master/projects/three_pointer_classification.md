# Three-Pointer Classification Work Plan

## Purpose

Define the work plan for hardening how the backend classifies made and missed shot attempts as 1-point, 2-point, or 3-point attempts across HCO, Dynamic HCT, FCP, Fast Break, OREB, Free Throw, and Final Shot paths.

This document was created after observed mismatches:

- Some visually apparent 2-point shots triggered made-three SFX.
- A visually apparent 3-point step-back shot registered as a 2-pointer and did not trigger made-three SFX.

The frontend is a UESS renderer only. It should not decide whether a shot is worth 2 or 3. Classification must be backend-owned and carried through scoring, stats, payload fields, and backend-stamped announcement/SFX metadata.

This replaces the older `universal_3point_helper.md` project brief. The still-valid pieces from that brief are preserved here:

- Coordinate-based classification should replace skeleton-name-based classification.
- One home/right-attacking 3-point geometry model should be normalized for away offense by mirroring x.
- `roles["shot_spot"]` should be the preferred classification input when it contains explicit coords.
- Shooter model coords are an acceptable fallback.
- Skeleton location-name classification should be a last-resort legacy fallback only.

## Implementation Work Plan

### Phase 1: Fix Dynamic HCO coordinate handoff

Immediate bug target:

- Dynamic HCO can create procedural shot coordinates that differ from named skeleton spots.
- `set_shooter_coords_from_skeleton_last_step()` must support explicit coord-based shoot steps and prefer those coords over named `location` / `spot` lookups.
- Before `ShotManager.resolve_shot(roles)` runs, the canonical final shot coordinate must be written into:
  - `shooter.coords`
  - `roles["shot_spot"]`

This phase should confirm the coordinate frame used by Dynamic HCO/UESS shoot-step coords. Do not blindly mirror explicit coords unless the pipeline confirms they are stored in home-oriented space.

### Phase 2: Create a richer backend classification wrapper

Keep `BackEnd.utils.shot_geometry.is_three_point_shot_from_coords()` as the geometry primitive, but wrap it with a single shot-value classifier that returns a self-describing payload:

```python
{
    "points": 3 or 2,
    "is_three_point_shot": True/False,
    "shot_value": 3 or 2,
    "classification_coord": {"x": ..., "y": ...},
    "normalized_coord": {"x": ..., "y": ...},
    "boundary_x": ...,
    "classification_source": "coords" | "forced_two" | "forced_one" | "legacy_spot_fallback",
    "allow_three": True/False,
}
```

Free throws should be represented as a forced-one path, not a forced-two path.

Implementation status:

- `BackEnd/utils/shot_geometry.py` now exposes `classify_shot_value(...)`.
- `ShotManager.resolve_shot()` now builds a `shot_classification` payload before shot math and stamps the final turn result with:
  - `is_three_point_shot`
  - `shot_value`
  - `shot_spot`
  - `shot_classification_coord`
  - `shot_classification`
  - `shot_classification_source`
- Fast Break field-goal attempts preserve the existing outside-shot gate by passing `allow_three=False` unless the branch is explicitly stamped as outside.

### Phase 3: Standardize canonical shot-coordinate priority

Every field-goal shot path should resolve one canonical shot coordinate before scoring:

1. Explicit procedural `roles["shot_spot"]` coords.
2. Dynamic HCO motion final shot coord.
3. Terminal UESS shoot-step end coord.
4. Shooter model `coords`.
5. Legacy skeleton spot name as last-resort fallback only.

The classifier should not infer from frontend state.

### Phase 4: Classify once and carry the result everywhere

After classification, shot results should consistently carry:

- `shot_spot`
- `shot_classification_coord`
- `shot_classification`
- `is_three_point_shot`
- `shot_value`
- `points` when the shot is made
- `shot_type`
- `classification_source`

Use this classification result for:

- Score changes.
- `3PTA` / `3PTM`.
- Shooting foul FT count.
- Shot text.
- Made-three SFX.
- Animation and announcement payload metadata.

Implementation status:

- `ShotManager.resolve_shot()` now stamps the canonical classification payload on normal shot results and the block-reconciliation shooting-foul early return.
- Dynamic HCT attack-basket shot paths now build a `shot_classification` payload from the procedural `shot_spot` and stamp it on the turn result.
- OREB putback attempts now stamp a forced-two classification payload.

### Phase 5: Preserve explicit forced-value contracts

Some paths should not use 3-point geometry:

- Free throws: forced 1.
- OREB putbacks: forced 2.
- Steal Fast Break rim finishes: forced 2.
- Rim Runner / Covert Release rim finishes: forced 2 unless explicitly designed as outside attempts.

These paths should still stamp classification metadata so downstream systems can see why geometry was bypassed.

### Phase 6: Move made-three SFX to the classification flag

Made-three SFX should be stamped from:

```python
turn_result.get("is_three_point_shot") is True
```

not from raw `points == 3`.

This keeps UESS intact: backend classifies, frontend renders.

Implementation status:

- `skeleton_step_emitter.py` now stamps `meta.sfx = "three_make"` only when `turn_result["is_three_point_shot"] is True`.

### Phase 7: Add regression tests

Required test coverage:

- Arc boundary:
  - Lower corner straight-line segment.
  - Upper corner straight-line segment.
  - Interpolated wing/midwing/key sections.
  - One point just inside and just outside each segment.
- Home/away parity:
  - `x_away = 100 - x_home`.
- HCO:
  - Coordinate-based step-back from inside the arc can classify as 3.
  - Coordinate-based step-in from outside the arc can classify as 2.
  - Named spot fallback still works when explicit coords are missing.
- Dynamic HCT:
  - Procedural `shot_spot` drives points and `is_three_point_shot`.
- Fast Break:
  - Triangle outside branches classify by coordinate.
  - Rim/post branches force 2.
- OREB:
  - Putbacks force 2.
- Free Throw:
  - Free throws force 1.
- SFX:
  - Made 3 stamps `meta.sfx = "three_make"`.
  - Made 2 never stamps `three_make`.

### Phase 8: Canonical documentation update

After implementation, move the final rules into `_documentation_master/06_Gameplay_Systems/Shot_System.md`.

This project doc can then be archived or deleted.

## Current 3-Point Arc Model

The current universal helper is `BackEnd.utils.shot_geometry.is_three_point_shot_from_coords()`.

The helper models the 3-point line as a piecewise boundary in home-offense/right-attacking orientation:

| Boundary point | x | y |
|---|---:|---:|
| lower corner | 88 | 6 |
| lower midCorner | 81 | 7 |
| lower wing | 73 | 10 |
| lower midWing | 68 | 14 |
| key | 64 | 25 |
| upper midWing | 68 | 36 |
| upper wing | 73 | 40 |
| upper midCorner | 81 | 43 |
| upper corner | 88 | 44 |

This is not a perfect mathematical arc. It behaves as:

- A straight corner/baseline segment at the lower edge: if `y <= 6`, boundary x is `88`.
- A curved/interpolated segment from lower corner through key to upper corner.
- A straight corner/baseline segment at the upper edge: if `y >= 44`, boundary x is `88`.

For home/right-attacking orientation, the shot is classified as a three when `normalized_x <= boundary_x` at the shot's `y`.

Away offense is normalized by mirroring x:

```python
normalized_x = 100 - shooter_x
normalized_y = shooter_y
```

The helper expects display-oriented court coordinates, then internally normalizes away offense into the home/right-attacking geometry model.

## Current Source Of Truth

Documented source of truth:

- `BackEnd.utils.shot_geometry.is_three_point_shot_from_coords()`

Current `ShotManager.is_three_point_shot()` behavior:

1. If `roles["shot_spot"]` exists and is a coordinate dict, run the universal coordinate helper.
2. Otherwise, fall back to the skeleton shoot-location name via `THREE_POINT_SPOTS`.

This fallback is the main weakness.

Named skeleton spots were good enough when every shot occurred exactly at a named spot. Dynamic HCO Motion now allows procedural grid movement, including ball-handler step-backs and subtle/freelance movement. A player may begin from a named 2-point spot such as `key`, move a few x-spots backward, and take a shot from a true 3-point coordinate. If classification still uses the skeleton location name instead of the final shot coordinate, the backend can score that as a 2.

## Path Review

### HCO

Path:

- `resolve_half_court_offense()` in `phase_resolution.py`
- Applies animation coords.
- Calls `set_shooter_coords_from_skeleton_last_step(...)`.
- Calls `ShotManager.resolve_shot(roles)`.

Current behavior:

- `set_shooter_coords_from_skeleton_last_step()` stamps `roles["shot_spot"]` from the skeleton shoot step.
- `ShotManager.is_three_point_shot()` uses `roles["shot_spot"]` when present.
- If `roles["shot_spot"]` is missing, it falls back to skeleton spot-name classification.

Gap:

- Dynamic HCO Motion can create procedural shot coordinates that are not simply the skeleton shoot location.
- If the procedural final shot coordinate is not written into `roles["shot_spot"]`, classification may use the old named location.
- This can explain a step-back from `key` being visually behind the arc while scoring as 2.

Risk:

- High. HCO is the main location where Dynamic HCO Motion can produce non-named shot coords.

### Final Shot

Path:

- `resolve_final_turn_shot_logic()` in `phase_resolution.py`
- Builds a final-turn skeleton.
- Calls `set_shooter_coords_from_skeleton_last_step(...)`.
- Calls `ShotManager.resolve_shot(roles)`.

Current behavior:

- Final Shot uses the same `ShotManager` path as HCO after stamping `roles["shot_spot"]`.

Gap:

- Same as HCO if Final Shot later supports procedural/motion offsets.
- Current final-turn skeleton appears more controlled, but the same helper/fallback risk exists if shot coords and named spots diverge.

Risk:

- Medium. Less dynamic than HCO, but shares the same classification path.

### FCP

Path:

- FCP shot branches in `phase_resolution.py`
- Build `shot_roles`.
- Call `_ensure_skeleton_shot_role_positions(...)`.
- Apply animation coords.
- Call `set_shooter_coords_from_skeleton_last_step(...)`.
- Call `ShotManager.resolve_shot(shot_roles)`.

Current behavior:

- FCP uses `ShotManager.resolve_shot()` and therefore `ShotManager.is_three_point_shot()`.
- If `roles["shot_spot"]` is correctly stamped from the shot step, it uses coordinate geometry.

Gap:

- FCP is planned to be sunset, so this is lower priority.
- If FCP procedural shot positions exist without a correct `roles["shot_spot"]`, it can hit the same fallback weakness.

Risk:

- Low to medium, mostly because FCP is being sunset.

### Dynamic HCT

Path:

- `BackEnd/engine/dynamic_hct_shot.py`
- Dynamic HCT procedural shot paths bypass `ShotManager.resolve_shot()`.
- They call `is_three_point_shot_from_coords(shot_spot, is_away_offense=...)` directly.
- `is_three` is then carried into scoring, `3PTA`, `3PTM`, points, and free-throw count.

Current behavior:

- Stronger than HCO for coordinate-based classification because it directly uses the universal helper with an explicit procedural `shot_spot`.

Gap:

- Must ensure the `shot_spot` passed to the helper is in the expected display-oriented coordinate frame.
- Current code appears intentionally coordinate-based and stamps `is_three_point_shot`.

Risk:

- Lower than HCO. The main risk is coordinate orientation/frame mismatch, not named-spot fallback.

### Fast Break

There are multiple Fast Break families.

#### Steal Fast Break

Path:

- `BackEnd/engine/after_steal_fast_break.py`

Current behavior:

- Shot type is hard-coded as `inside`.
- `is_three = False`.
- Made shots stamp `points = 2`.

Gap:

- None for standard steal FB at-rim finishes, assuming these are never designed as 3-point attempts.

Risk:

- Low.

#### Rim Runner Fast Break

Path:

- `BackEnd/engine/rim_runner_fast_break.py`
- Calls `ShotManager.resolve_shot(roles)`.
- Universal FB geometry may override `roles["shot_spot"]`.

Current behavior:

- Most RR finishes are intended as 2-point at-rim attempts.
- Explicit geometry paths set `roles["shot_spot"]`.
- `ShotManager` only allows FB threes when `shot_type_hint == "outside"` and coordinate geometry says three.

Gap:

- If an RR shot is outside but `shot_type` is not stamped as `"outside"`, `ShotManager` will force it to a 2.
- For normal RR design this is likely correct.

Risk:

- Low for intended RR behavior.

#### Covert Release Fast Break

Path:

- `phase_resolution.py` CR logic.
- Universal CR geometry overrides `roles["shot_spot"]` and defender.
- Calls `ShotManager.resolve_shot(roles)`.

Current behavior:

- CR appears intended as a rim/transition finish, not a three.
- If the CR resolver ever creates outside attempts, it must stamp both `shot_type = "outside"` and a coordinate `shot_spot`.

Gap:

- Same FB gate: `shot_type_hint == "outside"` is required before a FB can classify as a three.

Risk:

- Low for current design.

#### Triangle Fast Break

Path:

- `BackEnd/engine/rim_runner_fast_break.py`
- Triangle branches explicitly set `shot_type` and `shot_spot`.
- Outside branches include `triangle_corner_three`, `triangle_bh_wing_three`, and `triangle_drive_corner_kick`.

Current behavior:

- Stronger than legacy FB paths because outside Triangle branches pass coordinate `shot_spot` and `shot_type = "outside"` into `ShotManager`.

Gap:

- If a Triangle outside branch's `shot_spot` is wrong or not display-oriented, it can misclassify.
- Otherwise this path is aligned with the helper.

Risk:

- Medium-low.

### OREB

Path:

- `resolve_offensive_rebound()` in `BackEnd/utils/shared.py`
- `resolve_offensive_rebound_turn()` in `turn_manager.py`

Current behavior:

- Putbacks are always `shot_type = "inside"`.
- Made putbacks call `apply_scoring(..., 2, ["FGM"])`.
- The OREB result payload carries `points = 2`.

Gap:

- None for 3-point classification. OREB putbacks should never classify as threes.

Risk:

- Low.

### Free Throw

Path:

- `resolve_free_throw_logic()` in `phase_resolution.py`
- FT step emitter paths.

Current behavior:

- Free throws are always 1 point.
- No 2/3 classification applies.

Gap:

- None.

Risk:

- Low.

## Current Bugs / Gaps

### 1. Coordinate helper exists but is not universal in practice

The helper is present and documented, but `ShotManager.is_three_point_shot()` can still fall back to named spot classification.

This fallback is dangerous for dynamic/procedural movement because the named skeleton spot can differ from the final shot coordinate.

### 2. HCO Dynamic Motion can create real shot coords that differ from skeleton spots

`Z-Completed/Dynamic_HCO_Motion_Brief.md` explicitly allows:

- Ball-handler step-backs.
- Side dribbles.
- Subtle movement.
- Freelance movement to arbitrary nearby grid locations.
- Hot-read shots from grid spots, not just named spots.

Therefore HCO classification must be pure coordinate geometry once any dynamic movement is involved.

### 3. SFX stamping currently keys from `points`

The schema make-hold step stamps made-three SFX when `turn_result["points"] == 3`.

That is not ideal. SFX should follow the canonical classification field:

```python
turn_result["is_three_point_shot"] is True
```

`points` should match classification, but using it as the SFX gate hides the source of truth and makes debugging harder.

### 4. Shot result payloads are not consistently self-describing

Some paths stamp `is_three_point_shot`; others do not.

For example:

- Dynamic HCT stamps `is_three_point_shot`.
- HCO via `ShotManager.resolve_shot()` currently does not consistently stamp it in the final result payload.

Every shot result should expose:

- `shot_spot`
- `shot_classification_coord`
- `is_three_point_shot`
- `points`
- `shot_type`
- `classification_source`

### 5. Fast Breaks have a second gate beyond coordinate geometry

For Fast Breaks, `ShotManager` only allows a three if:

```python
shot_type_hint == "outside" and coordinate helper says True
```

This is probably intentional for RR/CR/Steal FB rim attacks, but it means a Fast Break with a true outside coordinate can still become a 2 if `shot_type` was not stamped as `"outside"`.

## Proposed Bulletproof System

### Principle

Every shot attempt should resolve through one backend classification primitive before scoring, stats, text, SFX, and payload generation.

Frontend should only render the backend's classification.

### Step 1: Create a canonical shot classification helper

Add a backend helper with a richer return object, not just a bool:

```python
def classify_shot_value(
    *,
    coords: dict | None,
    is_away_offense: bool,
    shot_family: str,
    shot_type: str | None = None,
    allow_three: bool = True,
) -> dict:
    ...
```

Return:

```python
{
    "points": 3 or 2,
    "is_three_point_shot": True/False,
    "shot_value": 3 or 2,
    "classification_coord": {"x": ..., "y": ...},
    "normalized_coord": {"x": ..., "y": ...},
    "boundary_x": ...,
    "classification_source": "coords" | "forced_two" | "legacy_spot_fallback",
    "allow_three": True/False,
}
```

### Step 2: Resolve canonical shot coords before classification

Every shot path should provide the final shot coordinate explicitly.

Priority order:

1. Explicit procedural `roles["shot_spot"]`.
2. Dynamic HCO motion final shot coord.
3. Terminal UESS shoot step end coord.
4. Shooter model `coords`.
5. Legacy skeleton spot name as a last-resort fallback only.

For Dynamic HCO Motion, the final procedural coordinate must be written into `roles["shot_spot"]` before `ShotManager.resolve_shot()`.

### Step 3: Classify once, then carry the result everywhere

After classification:

```python
result["shot_spot"] = classification["classification_coord"]
result["is_three_point_shot"] = classification["is_three_point_shot"]
result["points"] = classification["points"] if made else None
result["shot_value"] = classification["points"]
result["shot_classification"] = classification
```

Use `shot_value`/`is_three_point_shot` for:

- Scoring.
- `3PTA` / `3PTM`.
- Shot threshold modifier.
- Zone-vs-3 modifier.
- Shooting foul FT count.
- Text: "drains a 3!" vs "makes the shot."
- Made-three SFX.

### Step 4: Explicitly opt out for impossible three paths

Some shot families should never be threes:

- OREB putbacks.
- Free throws.
- Steal FB rim finishes.
- RR rim-runner rim finishes.
- CR rim finishes, unless later designed as outside attempts.

Those paths should call/record classification with `allow_three=False`, so the payload still explains why the result is a 2:

```python
"classification_source": "forced_two"
```

### Step 5: SFX should use classification, not points

The schema make-hold SFX stamp should change from:

```python
if int(turn_result.get("points") or 0) == 3:
```

to:

```python
if turn_result.get("is_three_point_shot") is True:
```

This preserves UESS: backend decides, frontend renders.

### Step 6: Add tests around the boundary and path contracts

Needed tests:

- Arc boundary:
  - Lower corner straight-line segment.
  - Upper corner straight-line segment.
  - Interpolated wing/midwing/key sections.
  - One point just inside and just outside each segment.
- Home/away parity:
  - `x_away = 100 - x_home`.
- HCO:
  - Named key is 3 only at/beyond the helper boundary.
  - Step-back from key can become a 3 if final coord is behind the line.
  - Step-in from a wing can become a 2 if final coord is inside the line.
- Dynamic HCT:
  - Procedural `shot_spot` drives points and SFX.
- Triangle FB:
  - Outside branches classify by coordinate.
  - Rim/post branches force 2.
- OREB:
  - Putbacks always force 2.
- SFX:
  - Made 3 stamps `meta.sfx = "three_make"`.
  - Made 2 never stamps `three_make`.

## Current Diagnostic Logs

Temporary logs currently in place:

### `[3PT-READ]`

Added in `ShotManager.resolve_shot()` for HCO outside/motion/coordinate shot cases.

Useful fields:

- `resolved_is_three`
- `coord_is_three`
- `role_spot_is_three`
- `spot_name_is_three`
- `roles_shot_spot`
- `resolved_xy`
- `shooter_model_coord`
- `motion_playcall`
- `motion_shot_type`
- `motion_geometry`
- `forced_shot`
- `shot_step_index`
- `variant`

Expected smoking gun for the step-back bug:

```text
resolved_is_three=False coord_is_three=True
```

That means the final coordinate says 3, but the active classification resolved 2.

### `[3PT-SFX-STAMP]`

Added in schema make-hold stamping when the backend emits `meta.sfx = "three_make"`.

Useful fields:

- `points`
- `is_three_point_shot`
- `shot_type`
- `schema_shooter_coord`
- `shooter_model_coord`
- `ball_coord`
- HCT/FB target fields where present

Expected smoking gun for false positive SFX:

```text
points=3 but schema_shooter_coord is inside the arc
```

or:

```text
points=3 is_three_point_shot=False/None
```

## Recommendation

Do not patch the frontend.

The correct fix is backend-only:

1. Make every shot path resolve a canonical final shot coordinate before scoring.
2. Make every shot path classify from that coordinate or explicitly force 2.
3. Stamp `is_three_point_shot`, `shot_value`, `shot_spot`, and classification metadata onto every shot result.
4. Make made-three SFX read `is_three_point_shot`, not raw `points`.
5. Remove or demote skeleton spot-name fallback once Dynamic HCO Motion is fully coordinate-safe.
