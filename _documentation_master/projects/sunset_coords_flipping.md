# Sunset Frontend Coordinate Flipping

**Status:** In progress
**Created:** 2026-06-14  
**Objective:** Make the backend the sole authority for gameplay coordinates and remove frontend coordinate selection and orientation logic.

## Implementation Progress

### 2026-06-14: Final Turn alignment slice completed

- Final Turn `oDestinations` and `dDestinations` now leave the backend in final
  display orientation.
- Away-offense alignment uses the canonical `x_away = 100 - x_home` mirror.
- Final Turn **schema** alignment is skeleton step 0 in ``animation_steps[]`` (UESS playback from index 0). ``runFinalTurnAlignment()`` renders backend ``oDestinations`` / ``dDestinations`` directly (legacy fallback when schema steps are absent) and no longer derives offense orientation or applies ``101 - x``.
- Deterministic tests assert home/away parity for offense alignment, defense
  alignment, representative MAKE/MISS variants, AIRBALL, and BLOCK endpoints.
- The active schema shot path was traced before editing. Shooter endpoints,
  rim targets, block targets, and bounce targets were already backend-owned and
  display-oriented, so that path was not changed.

Remaining work in this project includes broader parity coverage and removal of
any other legacy frontend coordinate logic once each caller is proven covered.

### 2026-06-14: OREB kickout frontend fallback removed

- Deterministic backend tests cover normal and post-block kickouts for home and
  away offense.
- Every covered kickout emits rebound capture, backend-owned positioning, and
  backend-owned pass steps with canonical home/away parity.
- The frontend random outlet selection, `HCO_STRING_SPOTS` lookup, `101 - x`
  mirror, and legacy kickout pass fallback were deleted.
- A step-less `OREB_KICKOUT` now reports a UESS contract error instead of
  silently inventing replacement gameplay coordinates.

### 2026-06-14: General BIP frontend fallback removed

- `runInboundSetup()` now requires backend `ball_spot`, complete
  `oDestinations`, and complete `dDestinations` before mutating animation
  state.
- HCO, FCP, and HCT BIP setup all render the same backend destination fields.
- Frontend random defender retreat, `offense_setup_positions` interpretation,
  `location`/`opp` conversion, and `101 - x` mirroring were removed.
- Legacy make, free-throw, putback, and dead-ball turnover callers no longer
  synthesize a BIP without a dedicated backend turn. Missing routes report a
  UESS contract error and fail closed.
- Deterministic tests cover the baseline ball spot plus full FCP/HCT horizontal
  home/away parity, and static guards prohibit restoring frontend BIP
  coordinate selection.

### 2026-06-17: Fast Break block landing fallback fixed

- Legacy Fast Break `BLOCK` branches now render backend `ball_bounce_x/y`
  directly as the block/landing spot.
- The frontend no longer routes backend block coords through `bounceFromRim()`,
  which treated the supplied coordinate as a rim/origin and invented a second
  frontend landing spot with `bounceArea` variance.
- Normal Fast Break `MISS` behavior still uses the legacy bounce helper until
  the broader Fast Break shot/rebound/get-back audit is completed.

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

- OREB kickout legacy setup: removed after backend schema parity coverage.
- Legacy inbound pressure defender setup: converted to render backend
  `dDestinations` directly; static formations and frontend flipping removed.
- BIP general setup fallback: removed after backend payload and caller tracing.
- Final Turn alignment: **primary** animation is UESS ``animation_steps`` skeleton step 0 (backend archetypes + ``_step_t_floor_game_seconds`` hold). ``runFinalTurnAlignment()`` remains **legacy fallback** only when a Final Turn turn lacks schema steps; it renders backend ``oDestinations`` / ``dDestinations`` directly with no frontend orientation flip.

### Remaining frontend audit targets

These are candidates discovered by the repository-wide follow-up scan. They
are not yet classified as confirmed bugs. Each must be traced through its
backend producer, runtime caller, and position-sync behavior before editing.

1. **Fast Break defensive-stop fallback**
   - File: `FrontEnd/static/js/phaser/animation/fastBreak.js`
   - Function: `animateDefensiveStop()`
   - The function treats animation coordinates as home-oriented for away
     offense and applies `100 - x` for display.
   - It can reject a backend ball-handler endpoint and replace it with a
     frontend-selected top-of-key destination.
   - Trace whether current defensive-stop payloads are already display-oriented
     and whether this fallback is reachable.

2. **Countdown-window player movement**
   - File: `FrontEnd/static/js/phaser/animation/countdownAnimation.js`
   - Functions: `animateCountdownTransition()`, `animateAdvanceUpCourt()`, and
     `animateSideInboundMovement()`
   - Active code selects random offensive and defensive destinations and
     mirrors home-authored spots with `100 - x` for away offense.
   - Trace whether these tweens are cosmetic and fully discarded before
     gameplay resumes, or whether their endpoints affect sprite state,
     ownership, later animations, or backend-coordinate reconciliation.

3. **Fast Break shot, rebound, and get-back fallbacks**
   - File: `FrontEnd/static/js/phaser/animation/fastBreak.js`
   - Candidate branches select attacking rims, shot spots, rebound positions,
     non-participant locations, and get-back bands using frontend team-side
     logic and `Phaser.Math.Between`.
   - 2026-06-17 update: confirmed and fixed the `BLOCK` landing branch where
     backend `ball_bounce_x/y` was incorrectly passed through `bounceFromRim()`
     and shifted again by frontend variance.
   - Trace each branch separately. Some may be unreachable legacy fallbacks;
     others may still replace missing backend payload fields.

4. **Schema shot-stop fallback**
   - File: `FrontEnd/static/js/phaser/animation/animationPlayback.js`
   - Function: `runShotAttempt()`
   - When a schema-rendered arc is absent, the frontend derives the attacking
     rim or made-shot sweet spot from the shooter sprite's team.
   - Trace whether supported shot payloads always provide schema ball-flight
     steps and whether this branch can still own gameplay ball endpoints.

5. **Generic defensive-stop transition**
   - File: `FrontEnd/static/js/phaser/animation/turnAnimation.js`
   - Function: `runDefensiveStopTransition()`
   - The frontend selects a top-of-key target, chooses the nearest defender,
     and creates a contest offset based on the inferred offense side.
   - Establish whether the function is reachable. If active, replace its
     gameplay positioning with backend-emitted endpoints; if unreachable,
     remove it after proving no supported caller depends on it.

### Documentation-only discrepancy found

- `_documentation_master/06_Gameplay_Systems/SIP_System.md` still documents
  `x = 101 - x`.
- Current SIP backend generation uses backend-owned, display-oriented
  coordinates and the frontend renders `oDestinations`, `dDestinations`, and
  `ball_spot`.
- Correct this documentation after the SIP code trace confirms there is no
  remaining supported frontend orientation branch.

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

**Primary:** UESS ``animation_steps`` step 0 (backend-owned alignment + ``_step_t_floor_game_seconds``). **Legacy fallback:** remove offense-team orientation detection and ``flipCoords()`` from ``runFinalTurnAlignment()`` — iterate backend ``oDestinations`` / ``dDestinations``, convert grid to pixels, and animate.

### OREB kickout

The backend transition bridge already contains the kickout spot pools and
same-vertical-half selection rules. Make the schema path authoritative for:

- Receiver outlet selection.
- Passer outlet selection.
- Away orientation.
- Movement timing.
- Pass ownership.

Completed: backend schema coverage proved the helper was only a legacy
fallback. Frontend random spot selection, `HCO_STRING_SPOTS` gameplay lookup,
coordinate flipping, and the fallback pass path were deleted.

### BIP pressure setup

Backend BIP payloads already emit display-oriented destinations and migrated
`animation_steps`.

- Completed: the legacy fallback uses backend `dDestinations` exactly as
  supplied.
- Completed: the frontend static FCP/HCT defender formations and `101 - x`
  mirror were removed.
- Completed: frontend `location` plus `opp` interpretation was removed after
  proving supported BIP payloads provide complete `oDestinations`.
- Do not retain random or static frontend positioning as a silent fallback.

### General inbound fallback

Completed:

- The dedicated `BASELINE_INBOUND` turn is the only supported caller of
  `runInboundSetup()`.
- `PassAnimationSystem.executeInboundSequence()` passes the complete backend
  payload to the renderer.
- Legacy callers after makes, free throws, putbacks, and dead-ball turnovers
  fail closed when the required dedicated next turn is absent.
- SIP remains independently owned by `runSideInboundSetup()`.

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
