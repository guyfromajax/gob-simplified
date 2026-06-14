# Sunset Frontend Coordinate Flipping

**Status:** Planned migration  
**Created:** 2026-06-14  
**Objective:** Make the backend the sole authority for gameplay coordinates and remove frontend coordinate selection and orientation logic.

## Why This Project Exists

The animation system currently has two horizontal mirror formulas:

- Backend: `x_away = 100 - x_home`
- Several legacy frontend paths: `x_away = 101 - x_home`

The live court coordinate space is `0..100` on the x-axis, with midcourt at
`x=50`. Important mirrored landmarks include:

- Away rim: `x=9`
- Home rim: `x=91`
- Home baseline inbound: `x=3`
- Away baseline inbound: `x=97`

These pairs prove that `100 - x` is the canonical mirror formula. For example,
`100 - 91 = 9` and `100 - 3 = 97`. The `101 - x` formula shifts mirrored
positions by one grid unit and is inconsistent with backend geometry.

The formula mismatch is only one symptom. The larger architectural problem is
that some frontend animation helpers still:

- Decide where players should move.
- Randomly select gameplay destinations.
- Determine whether coordinates need mirroring.
- Convert home-oriented gameplay coordinates into display orientation.

This violates the UESS contract in
[`../05_UESS_System/UESS_System.md`](../05_UESS_System/UESS_System.md):

- The backend owns player coordinates, movement intent, ball state, and timing.
- The frontend is a pure renderer of backend-emitted payloads.

Changing every frontend `101 - x` to `100 - x` would correct the immediate
off-by-one error, but it would preserve the wrong ownership model. This project
must sunset the frontend logic rather than merely standardize its formula.

## Canonical Coordinate Contract

The migration must establish and enforce these rules:

1. Gameplay payload coordinates are emitted in final display orientation.
2. `x=0..100`, `y=0..50`, and midcourt is `x=50`.
3. When conversion from a home-authored template is required, the backend uses
   `x_away = 100 - x_home`.
4. A payload field must not require the frontend to infer its orientation.
5. The frontend may convert grid coordinates to pixels, but it may not select,
   mirror, randomize, clamp for gameplay intent, or otherwise reinterpret them.
6. Backend `Player.coords`, position snapshots, animation step endpoints, and
   frontend sprite endpoints must describe the same display-oriented location.

## Known Scope

### Backend authority

- `BackEnd/utils/shared.py`
  - `get_away_player_coords()`
  - `getAwayTeamCoords()`
- `BackEnd/models/turn_manager.py`
  - BIP and SIP destination generation
  - FCP/HCT inbound setup
  - Final Turn offense and defense alignment
- `BackEnd/engine/phase_resolution.py`
  - Final Turn result construction
- `BackEnd/utils/transition_bridge.py`
  - Backend-selected OREB kickout spots and orientation
- Animation step emitters and position snapshot helpers that consume these
  payloads.

### Frontend logic to retire

The following locations are the initial audit targets in
`FrontEnd/static/js/phaser/animation/turnAnimation.js`:

- `runOffensiveReboundKickoutSetup()` near the current `flipCoords` helper
  around line 2505.
- Legacy inbound pressure defender setup around line 2800.
- BIP `offense_setup_positions` fallback conversion around line 3068.
- `runFinalTurnAlignment()` near the current `flipCoords` helper around line
  6057.

Line numbers will drift. Search for `101 -`, `flipCoords`, frontend
`Phaser.Math.Between` destination generation, and imports of
`HCO_STRING_SPOTS`.

Other frontend coordinate calculations discovered during implementation must
be classified as one of:

- Pixel-only rendering conversion: allowed.
- Cosmetic render-space motion with no gameplay ownership: document and review.
- Gameplay destination/orientation logic: move to backend.
- Unreachable legacy code: prove unreachable, then delete.

## Five-Step Fix Plan

## 1. Make Backend Payloads Display-Oriented

Audit every gameplay payload consumed by the affected frontend helpers and
ensure all coordinates are final display-oriented values before serialization.

For each payload, document:

- Producing backend function.
- Consuming frontend function.
- Current orientation on home offense.
- Current orientation on away offense.
- Whether `Player.coords` and position snapshots use the same endpoint.
- Whether the payload also emits `animation_steps`.

At minimum, cover:

- BIP `ball_spot`, `oDestinations`, `dDestinations`, and
  `offense_setup_positions`.
- SIP `ball_spot`, `oDestinations`, and `dDestinations`.
- Final Turn `oDestinations`, `dDestinations`, `shot_spot`, skeleton-derived
  endpoints, block spot, ball-flight destination, bounce spot, and rebound
  coordinates.
- OREB kickout passer and receiver outlet spots.
- Any fallback payload that currently sends a location name or home-oriented
  template instead of final coordinates.

Backend conversion from reusable home-oriented constants is acceptable, but it
must happen before the payload is emitted. Use the canonical `100 - x` rule.

Do not mutate shared constant dictionaries in place. Copy coordinate objects
before orientation conversion.

### Step 1 acceptance gates

- Every affected payload field has a documented orientation.
- Away-oriented payloads already contain final coordinates.
- No consumer needs team-side knowledge to interpret a coordinate.
- Position snapshots and `Player.coords` match emitted endpoints.
- Emitter failure behavior remains explicit; do not silently reintroduce
  frontend authority as a fallback.

## 2. Update Final Turn Backend Alignment

Final Turn is a focused high-risk path because alignment and shot animation can
currently derive orientation through different mechanisms.

Current backend comments in `turn_manager.py` state that Final Turn offense and
defense alignments are always returned in home-side convention and the frontend
flips them. Replace that contract.

Required changes:

1. Build reusable offense and defense templates as today.
2. Determine whether the offense is the away team on the backend.
3. Convert both `oDestinations` and `dDestinations` to final display orientation
   using `100 - x` when required.
4. Ensure the skeleton, `roles["shot_spot"]`, animation steps, block
   reconciliation, ball flight, bounce, and rebound geometry use the same
   orientation.
5. Ensure the final position snapshot uses those exact endpoints.
6. Mark the payload contract explicitly, preferably with a durable schema
   convention rather than a temporary boolean orientation flag.

Do not fix only the player alignment. The reported edge case is the ball
landing at the wrong end of the court, so the complete shot-coordinate chain
must be traced.

### Final Turn acceptance gates

- Home offense attacks the home rim at `x=91`.
- Away offense attacks the away rim at `x=9`.
- Player alignment, shooter endpoint, rim target, block spot, bounce spot, and
  rebound spot remain on the same attacking end.
- MAKE, MISS, BLOCK, shooting foul, and final-shot rebound outcomes are tested.
- No frontend Final Turn branch mirrors coordinates.

## 3. Remove Frontend Gameplay Coordinate Logic

After backend payload coverage is proven, simplify frontend functions to render
the supplied coordinates.

### Final Turn

Remove offense-team orientation detection and `flipCoords()` from
`runFinalTurnAlignment()`. Iterate over backend `oDestinations` and
`dDestinations`, convert grid coordinates to pixels, and animate.

### OREB kickout

The backend transition bridge already contains the kickout spot pools and
same-vertical-half selection rules. Make the schema path authoritative for:

- Receiver outlet selection.
- Passer outlet selection.
- Away orientation.
- Movement timing.
- Pass ownership.

Remove frontend random spot selection, `HCO_STRING_SPOTS` gameplay lookup, and
coordinate flipping from `runOffensiveReboundKickoutSetup()`. If this helper is
only a legacy fallback, either make it a renderer of explicit payload endpoints
or delete it after proving all callers use schema playback.

### BIP pressure setup

Backend BIP payloads already emit display-oriented destinations and migrated
`animation_steps`.

- Use backend `coords` exactly as supplied.
- Remove the frontend static FCP/HCT defender formations.
- Remove frontend `location` plus `opp` interpretation once no supported
  payload depends on it.
- Do not retain random or static frontend positioning as a silent fallback.

### General inbound fallback

Trace all callers of `runInboundSetup()` and related helpers. Dedicated BIP and
SIP turns should render their own backend steps. For remaining legacy callers:

- Add explicit backend destination payloads first.
- Convert the helper into a renderer of those endpoints.
- Delete frontend destination generation only after caller coverage is tested.

### Step 3 acceptance gates

- No gameplay-facing `101 - x` remains.
- No gameplay destination is selected with frontend randomness.
- No frontend branch uses team identity to mirror backend gameplay coordinates.
- Grid-to-pixel conversion remains frontend-owned.
- Cosmetic-only render offsets are separately documented and do not update
  gameplay coordinate authority.

## 4. Add Home/Away Parity Tests

Tests must prove geometry and contract parity, not merely assert that fields
exist.

### Shared mirror tests

For representative and boundary-safe points:

```text
x_away == 100 - x_home
y_away == y_home
```

Include:

- Rims: `91 ↔ 9`
- Baselines: `3 ↔ 97`
- Midcourt: `50 ↔ 50`
- Representative wings, corners, lane spots, and inbound spots

### Payload tests

Generate equivalent home-offense and away-offense results with deterministic
random seeds and compare:

- BIP HCO setup.
- BIP FCP setup.
- BIP HCT setup.
- SIP setup.
- OREB kickout setup and pass.
- Final Turn alignment and every shot outcome family.

For each player and ball coordinate, assert x parity and identical y.

### Cross-layer tests

Verify that:

- Animation step final coordinates equal backend position snapshots.
- `sync_lineup_coords_from_turn()` produces the same final positions.
- Frontend schema playback consumes coordinates without changing orientation.
- Final Turn alignment does not apply a second mirror.

Add a static regression check that fails when gameplay animation files introduce
new `101 - x` or equivalent frontend mirror logic.

## 5. Correct Documentation

The current documentation contains conflicting rules.

Update at minimum:

- `05_UESS_System/UESS_System.md`
  - Preserve backend authority and pure-renderer rules.
  - Add the canonical display-oriented coordinate contract.
- `05_UESS_System/Core_Animation_System.md`
  - Remove guidance instructing the frontend to flip away-offense gameplay
    coordinates.
  - Replace `101 - x` examples with backend-side `100 - x`.
- `06_Gameplay_Systems/BIP_System.md`
  - Remove the known off-by-one warning after migration.
  - Remove frontend `opp` fallback documentation when retired.
- `06_Gameplay_Systems/SIP_System.md`
  - Correct the stale `101 - x` formula.
  - State that payload coordinates arrive display-oriented.
- Final Turn, OREB, inbound, and animation-routing documentation describing the
  affected helpers.
- `projects/bugs.md`
  - Delete the coordinate-flip cleanup item only after all acceptance gates
    pass.

Documentation must distinguish:

- Home-oriented constants/templates used internally by backend calculations.
- Display-oriented coordinates emitted at the API boundary.
- Pixel coordinates calculated by the frontend renderer.

## Recommended Implementation Order

1. Add parity and payload tests around the current backend behavior.
2. Migrate Final Turn end to end, including ball geometry.
3. Migrate OREB kickout endpoint selection and playback.
4. Remove BIP/SIP pressure and `opp` frontend fallbacks.
5. Convert or retire remaining general inbound fallback callers.
6. Add the static frontend mirror guard.
7. Update documentation and remove the bug tracker item.

Keep each subsystem in a separate change where practical. Do not combine a
global formula replacement with authority migration; that makes regressions
hard to isolate.

## Risks and Second-Order Effects

- **Double flip:** Backend orientation changes while frontend flipping remains.
- **Wrong basket:** Player alignment and ball/shot geometry use different
  conventions.
- **Snapshot drift:** Display endpoints change without updating `Player.coords`
  or position snapshots.
- **Mutable constants:** In-place conversion corrupts shared coordinate maps for
  later turns.
- **Legacy fallback regression:** A schema emitter fails and an old frontend
  fallback expects home-oriented or incomplete data.
- **Possession-side confusion:** Code infers attacking direction from sprite
  team instead of authoritative offense team ID.
- **Inbound boundary regression:** BIP/SIP require out-of-bounds coordinates
  that must not be forced through normal gameplay clamps.
- **Test randomness:** Home/away parity tests must seed or patch random choices
  so they compare equivalent decisions.

## Definition of Done

This project is complete only when:

1. A single canonical formula, `100 - x`, is used for backend orientation.
2. All affected gameplay payloads are emitted in final display orientation.
3. Final Turn player and ball geometry uses one orientation end to end.
4. Frontend gameplay coordinate mirroring and destination selection are removed.
5. Home/away parity tests cover every migrated path.
6. Position snapshots, `Player.coords`, animation endpoints, and rendered
   endpoints agree.
7. No supported path silently falls back to frontend gameplay logic.
8. Conflicting documentation is corrected.
9. The coordinate-flip item is removed from `projects/bugs.md`.

