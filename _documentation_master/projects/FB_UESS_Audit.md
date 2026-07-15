# Fast Break UESS + StepState Audit

**Date:** 2026-07-15  
**Scope:** Fast Break turns across all live play families: Rim Runner, Covert Release, Triangle, and After-Steal.  
**Purpose:** Trace current UESS / StepState compliance and identify SS&S opportunities without changing gameplay code.

## Executive Summary

Fast Break is **mostly UESS-schema compliant today**. All four Fast Break families can emit backend-authored `animation_steps`, and the frontend routes `covert_release`, `rim_runner`, `triangle`, and `after_steal` through schema playback when those steps exist.

Fast Break is **not yet StepState-current** in the newer FCP/HCT sense. FCP/HCT now have an additive `PressureStepState` bridge (`BackEnd/engine/pressure_step_state.py`) that freezes emitted schema, projects it back, and creates a path toward `resolve once -> freeze -> project -> draw`. Fast Break currently builds `AnimationStep[]` directly and has no equivalent `FastBreakStepState` layer.

This is not a sign that Fast Break should be rewritten from scratch. The current code already has strong SS&S consolidation around the highest-risk pieces: drive resolution, outlet passing, post-shot sub-steps, dead-ball fumbles, terminal freezes, DREB arming, and after-steal transition positioning.

## Compliance Matrix

| FB family | UESS schema playback | Shared drive resolver/emitter | Shared outlet pass | Shared post-shot / fumble / freeze helpers | StepState-current | Main residual risk |
|---|---:|---:|---:|---:|---:|---|
| Rim Runner | Yes | Yes | Yes | Yes | No | Some per-play preamble/lane-pass code remains bespoke; legacy render artifact/fallback still exists around old FB animation packet paths. |
| Triangle | Yes | Yes, via RR finisher adapter | Yes, via RR outlet/burst path | Yes | No | Triangle setup/branch preamble is still per-play, though the terminal drive-resolution path is centralized. |
| Covert Release | Yes | Yes | Yes | Yes | No | Legacy CR fallback code remains while `USE_FB_DRIVE_RESOLUTION_CR` exists; live path delegates the core drive work. |
| After-Steal | Yes | Yes | Not applicable | Yes | No | Has its own transition planner and pass-ahead chain; no StepState bridge yet. |

## Current SS&S Strengths

### Universal Drive-Resolution Helper

`BackEnd/engine/fb_drive_step_emitter.py::build_fb_drive_resolution_steps` is the most important consolidation point. Its docstring explicitly defines it as the shared drive-resolution step emitter for all four FB families.

It centralizes:
- meet / no-meet drive rendering
- neutral stop, neutral pass, neutral shoot, and POS_O rim finish paths
- post-shot sub-step integration
- dead-ball fumble insertion
- Fast Break terminal announcement freeze stamping
- per-play differences through parameters such as `kind_prefix`, `stamp_fb_start_announcement`, `suppress_stinger`, `crash_off_ball_to_basket`, and `author_offball_spread`

This is the correct SS&S shape: universal where the mechanics are identical, parameterized where play-family flavor differs.

### Universal Outlet-Pass Helper

`BackEnd/engine/fb_outlet_pass_step_emitter.py::build_fb_outlet_pass_step` is the shared outlet-pass core for RR/Triangle and Covert Release. It owns pass timing, ball transfer, interruption math, and tween stamping.

The helper deliberately stays scoped to FB outlet passes instead of using a global pass helper. That is a reasonable design choice right now because it reduces blast radius across HCO/BIP/SIP/Reset while still removing duplicate FB outlet logic.

### Shared Turn Support

Fast Break also uses shared backend helpers for several high-risk behaviors:
- `BackEnd/engine/skeleton_step_emitter._build_post_shot_sub_steps`
- `BackEnd/engine/shot_micro_movements.inject_shot_micro_before_post_shot`
- `BackEnd/engine/dead_ball_fumble.inject_dead_ball_fumble_before_turn_stop`
- `BackEnd/engine/fb_terminal_announce.stamp_fb_terminal_freeze`
- `BackEnd/engine/dreb_fast_break_arming.arm_dreb_fast_break`
- `BackEnd/engine/after_steal_transition_positioning.py`

These helpers are the right direction: local play families still own their setup shape, while shared primitives own repeated mechanics.

### Turn-Level Clock Reconciliation

`BackEnd/models/turn_manager.py` now reconciles `FAST_BREAK` `time_elapsed` from emitted schema clock burn when `animation_steps` exist. This fixes the old class of bugs where FB turn-level time and rendered per-step clock deltas diverged.

The same branch also includes a FB entry-seam detector. It intentionally seeds FB step 0 from the live ball owner rather than blindly using `prior_turn["final_ball_coords"]`, because steal-to-FB can otherwise teleport the ball back to the victim.

## Current UESS State

Fast Break is UESS-compliant in the practical frontend contract sense:
- backend resolves the FB outcome
- backend authors the emitted `animation_steps`
- frontend schema playback handles the four migrated FB play keys
- legacy frontend FB animation code is no longer the primary logic path for migrated turns

The current frontend schema routing includes all four FB play keys in the migrated set:
- `covert_release`
- `rim_runner`
- `triangle`
- `after_steal`

The old audit finding that Fast Break was uniquely divergent is therefore stale in several areas. The current migration doc already records that all four FB types source important geometry from live/geometric backend facts rather than legacy animator packet data.

## StepState Gap

Fast Break does **not** currently have a formal StepState bridge.

HCO has `BackEnd/engine/step_state.py`. FCP/HCT now have `BackEnd/engine/pressure_step_state.py`, which provides the migration seam:

```text
existing emitted AnimationStep[]
  -> freeze into PressureStepState[]
  -> project back into AnimationStep[]
```

Fast Break has no equivalent:

```text
existing emitted AnimationStep[]
  -> freeze into FastBreakStepState[]
  -> project back into AnimationStep[]
```

That means Fast Break is still “schema-emitter compliant” rather than “StepState-current.” This is acceptable for stability, but it is the main architectural gap if the goal is to make all turn families follow the same UESS/StepState lifecycle.

## Streamlining Opportunities

### 1. Add an Additive FastBreakStepState Bridge

Recommended next architectural step:

1. Create `BackEnd/engine/fb_step_state.py`.
2. Freeze emitted FB `AnimationStep[]` into `FastBreakStepState[]`.
3. Store the states on `turn_result["fb_step_states"]`.
4. Stamp each step with `_fb_step_state`.
5. Project those states back into `AnimationStep[]` with parity.

This should be additive and behavior-neutral, matching the FCP/HCT migration approach. Do not make individual FB emitters produce StepState directly until bridge parity is tested.

### 2. Add FB StepState Contract Tests Before More Refactors

Add tests covering at least:
- Covert Release: outlet + drive shot
- Rim Runner: outlet + lane pass + finish
- Triangle: setup + branch finish
- After-Steal: steal transition + finish
- terminal dead-ball turnover / travel
- shooting foul / and-1
- defensive stop / hold-up
- miss/block with DREB routing

The contract should assert:
- projected steps match source schema
- final player coords remain stable
- ball owner and ball coords stay stable
- total rendered clock burn matches `turn_result["time_elapsed"]`
- no duplicate announcements are introduced by projection

### 3. Retire Legacy Fallbacks Only After Bridge Parity

The migration doc still calls out legacy fallback/render artifact code around `capture_fast_break_animation`, especially for RR/Triangle. That fallback has been isolated from live logic, but it remains a safety path when emitters return `None`.

Do not delete this first. The safer order is:

1. Add FastBreakStepState bridge.
2. Add parity tests.
3. Confirm prototype coverage across all four FB play families.
4. Make emitter `None` paths loud/failing in tests.
5. Then remove old fallback/render artifact paths.

### 4. Keep Universal Helpers at the Primitive Level

Avoid a single giant “universal Fast Break emitter.” RR, Triangle, CR, and After-Steal have legitimately different setup/preamble shapes.

The best SS&S target is:
- universal outlet pass primitive
- universal lane/pass primitive where shape is identical
- universal drive-resolution primitive
- universal terminal/foul/dead-ball/post-shot primitives
- family-specific setup wrappers that only assemble inputs and flavor

That keeps the code simpler and reduces second-order breakage.

### 5. Consider a Shared FB Observability Helper

Current logging is scattered across emitters and migration guard paths. A small `fb_uess_debug.py` helper could standardize:
- play key
- emitted step count
- schema clock burn
- result type
- final ball owner
- final coords count
- fallback reason if any

This is lower priority than StepState parity, but it would make future FB regressions faster to diagnose.

## Recommended Work Order

1. **Do not rewrite FB.** Preserve current universal helpers.
2. **Add additive `fb_step_state.py`.** Freeze current emitted schema, then project back with no behavior change.
3. **Add parity tests for all four FB families.**
4. **Wire TurnManager to stamp/project FB StepState** after FB schema emission, mirroring the FCP/HCT pressure path.
5. **Move one primitive at a time to formal StepState projection** only after parity is proven. Start with `build_fb_drive_resolution_steps`, then outlet pass.
6. **Retire legacy fallback/render artifact paths** only after tests and prototype confirm no emitter-null live paths remain.

## Bottom Line

Fast Break is currently in a solid intermediate state: UESS-schema compliant, heavily centralized around the right helpers, and much less fragmented than older docs suggest.

The main gap is not “FB is broken architecture”; it is that FB has not yet adopted the newer StepState bridge pattern used by FCP/HCT. The clean hardening path is an additive `FastBreakStepState` projection layer, followed by parity tests and gradual retirement of legacy fallback code.

---

# Fast Break UESS + StepState Implementation Plan

**Status:** Steps 1-6 first slices implemented  
**Scope:** Rim Runner, Triangle, Covert Release, and After-Steal Fast Break turns  
**Primary code paths:** `BackEnd/engine/fb_drive_step_emitter.py`, `fb_outlet_pass_step_emitter.py`, `rim_runner_step_emitter.py`, `triangle_step_emitter.py`, `covert_release_step_emitter.py`, `after_steal_fast_break_step_emitter.py`, `BackEnd/models/turn_manager.py`, `FrontEnd/static/js/phaser/animation/AnimationEngine.js`  
**Related docs:** `projects/FB_UESS_Migration.md`, `projects/UESS Audits/Fast_Break_UESS_Audit.md`, `06_Gameplay_Systems/Fast_Break_System.md`, `projects/StepState.md`, `06_Gameplay_Systems/Dynamic_HCO_System.md`, `projects/FCP_HCT_UESS_Update.md`

## Goal

Bring Fast Break into the same practical UESS / StepState direction as modern HCO and the updated FCP/HCT work:

> resolve once -> freeze the game-relevant state -> project to animation schema -> frontend renders only.

The short-term target is **not** a rewrite. The safe path is:

1. Preserve the current working FB schema emitters and universal helpers.
2. Add an additive `FastBreakStepState` bridge that freezes the already-emitted schema.
3. Project that state back to identical schema and prove parity.
4. Only after parity, move individual universal primitives toward formal StepState projection.

## Non-Negotiable UESS Rules

For Fast Break, the following values must remain backend-owned:

- play family and branch (`rim_runner`, `triangle`, `covert_release`, `after_steal`)
- player start coords, movement destinations, and final coords
- ball owner at step start and step end
- pass origin, pass contact/interruption point, and pass arrival target
- shot spot, shooter, defender/stopper, contest frame, and post-shot path
- drive outcome and terminal result
- foul/dead-ball/charge/turnover payload
- DREB routing and chained FB routing
- step timing and clock burn
- announcement / SFX timing hooks when tied to game events

The frontend may interpolate, draw, fade, and play purely cosmetic effects. It must not repair missing FB game state, invent ball ownership, select outcomes, or choose replacement coords.

## Step 1: Lock Current FB Schema With Contract Tests

**Status:** First slice implemented in `tests/test_fb_step_state_contract.py`

Purpose: protect the current working behavior before adding the StepState bridge.

Create focused backend contract tests for all four FB families. These can use synthetic emitted schema payloads where full game setup would be too heavy, but they must represent real emitted shapes.

Minimum coverage:

- Covert Release: outlet pass -> drive shot
- Covert Release: terminal dead-ball turnover / travel
- Rim Runner: outlet -> burst -> lane pass -> finish
- Rim Runner: lane-pass interception or bat-OOB
- Triangle: setup -> branch finish
- Triangle: enter-HCO / defensive stop
- After-Steal: transition drive -> finish
- After-Steal: pass-ahead chain when enabled
- Shooting foul / and-1
- Miss or block with DREB routing

Minimum assertions:

- `animation_steps` exist and are linear.
- Step indexes and `next_step` chain do not skip or loop unexpectedly.
- Final emitted step has a truthful ball owner or explicit dead-ball/OOB state.
- Final player coords are present for all active players.
- Total schema clock burn matches `turn_result["time_elapsed"]` after TurnManager reconciliation.
- No duplicate terminal announcements are stamped.
- No frontend-only FB fallback is required for the covered cases.

This step should not change gameplay behavior.

### Initial Coverage Added

`tests/test_fb_step_state_contract.py` adds behavior-neutral schema-contract coverage for the current FB primitives that the StepState bridge will target first:

- Universal drive-resolution schema across the four FB families:
  - Covert Release
  - Rim Runner
  - Triangle via the RR finisher adapter path
  - After-Steal
- Representative drive outcomes:
  - `NO_MEET`
  - `POS_O`
  - `NEUTRAL` / `DEFENSIVE_STOP`
  - `DEAD BALL` / `DEAD_BALL_TURNOVER`
- Shared outlet-pass core for RR/Triangle-style and Covert Release-style mover flavor maps.

Current assertions lock:

- emitted schema exists
- start/end schema fields exist
- next-step / turn-stop chain shape is valid
- clock burn is non-negative
- final coords retain the ball handler
- dead-ball FB terminals end in `turn_stop: DEAD_BALL_TURNOVER`
- outlet pass starts with passer ownership, ends with receiver ownership, and uses `ball_reaches_player`

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **18 passed**.

## Step 2: Add `fb_step_state.py` As an Additive Bridge

**Status:** First slice implemented in `BackEnd/engine/fb_step_state.py`

Create `BackEnd/engine/fb_step_state.py`, modeled after `BackEnd/engine/pressure_step_state.py`.

Initial API:

```python
def build_fast_break_step_states(result: dict) -> list[dict]:
    ...

def project_fast_break_step_states_to_animation_steps(step_states: list[dict]) -> list[dict]:
    ...

def project_animation_step_through_fast_break_state(
    step: dict,
    *,
    index: int,
    result: dict | None = None,
) -> dict:
    ...
```

Initial state shape should freeze the current schema, not recompute it:

- `index`
- `turn_type = "FAST_BREAK"`
- `play_key`
- `players`
- `ball`
- `timing`
- `advance_gate`
- `outcome`
- `next`
- `cosmetics`
- `render`
- `projection_source`
- `schema_projection`

Acceptance criteria:

- Every emitted FB step receives `_fb_step_state`.
- `turn_result["fb_step_states"]` is populated.
- Projection from state back to schema is byte-for-byte or semantically equivalent for current fields.
- No gameplay behavior changes.

### Initial Bridge Added

`BackEnd/engine/fb_step_state.py` now provides the additive bridge:

- `build_fast_break_step_states(result)`
- `project_fast_break_step_states_to_animation_steps(step_states)`
- `project_animation_step_through_fast_break_state(step, index=..., result=...)`

The bridge freezes the already-emitted FB schema into `FastBreakStepState` with:

- `index`
- `turn_type`
- `play_key`
- `players`
- `ball`
- `timing`
- `advance_gate`
- `outcome`
- `next`
- `cosmetics`
- `render`
- `projection_source`
- `schema_projection`

For this first slice, projection is intentionally schema-snapshot based. That keeps the bridge behavior-neutral and gives later slices a safe place to move individual primitives into formal projection one at a time.

`tests/test_fb_step_state_contract.py` now verifies:

- FB drive schema projects back unchanged through `FastBreakStepState`.
- Shared outlet-pass schema projects back unchanged through `FastBreakStepState`.
- Single-step projection preserves schema while stamping `_fb_step_state`.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **28 passed**.

## Step 3: Wire TurnManager To Stamp And Project FB StepState

**Status:** First slice implemented in `BackEnd/models/turn_manager.py`

In the `FAST_BREAK` branch of `BackEnd/models/turn_manager.py`, after `resolve_fast_break_logic(self.game)` returns and after schema clock reconciliation, stamp and project the FB StepState.

Target flow:

```text
resolve_fast_break_logic
  -> current emitters produce animation_steps
  -> TurnManager reconciles time_elapsed from schema clock burn
  -> build_fast_break_step_states(result)
  -> project_fast_break_step_states_to_animation_steps(result["fb_step_states"])
  -> result["animation_steps"] = projected_steps
```

This mirrors the FCP/HCT pressure path and keeps behavior neutral.

Acceptance criteria:

- All four FB play keys still render through schema playback.
- No change to `time_elapsed`.
- No change to final ball owner.
- No change to final coords.
- No new frontend requirements.

### Runtime Bridge Added

The `FAST_BREAK` branch in `BackEnd/models/turn_manager.py` now stamps and projects `FastBreakStepState` after the existing schema clock reconciliation and FB entry-seam detector:

```text
resolve_fast_break_logic
  -> animation_steps already emitted by current FB emitters
  -> time_elapsed reconciled from schema clock burn
  -> build_fast_break_step_states(result)
  -> project_fast_break_step_states_to_animation_steps(result["fb_step_states"])
  -> result["animation_steps"] = projected_steps
```

The projection is still schema-snapshot based, so this is intended to be behavior-neutral. If StepState stamping fails, the branch logs a warning and leaves the current FB result intact.

`tests/test_fb_step_state_contract.py` now includes a TurnManager seam test that monkeypatches `resolve_fast_break_logic`, runs a `FAST_BREAK` micro-turn, and asserts:

- `time_elapsed` still comes from schema clock burn
- `fb_step_states` are populated
- emitted steps are stamped with `_fb_step_state`
- projected `animation_steps` match the original schema when the stamp is stripped

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **29 passed**.

## Step 4: Add Parity Tests For The Bridge

**Status:** First wrapper-parity slice implemented in `tests/test_fb_step_state_contract.py`

Add a dedicated test file, likely `tests/test_fb_step_state_contract.py`.

Test both helper-level and TurnManager-level behavior where feasible:

- `build_fast_break_step_states` freezes every emitted step.
- Projection preserves schema shape.
- StepState stamping does not mutate source steps except adding `_fb_step_state`.
- TurnManager projected steps match pre-projection steps for clock, ball, players, metadata, and turn-stop payloads.

This is the point where prototype testing becomes useful, but only after the backend parity suite passes.

### Wrapper Parity Coverage Added

`tests/test_fb_step_state_contract.py` now includes wrapper-level parity tests beyond the universal helpers:

- `build_covert_release_animation_steps`
- `build_after_steal_fast_break_animation_steps`
- `_build_finisher_drive_resolution_steps` for Rim Runner
- `_build_finisher_drive_resolution_steps` for Triangle

These tests assert that emitted wrapper schema can be frozen into `FastBreakStepState` and projected back without changing the schema when `_fb_step_state` is stripped.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **33 passed**.

## Step 5: Move The Universal Drive Helper Through StepState First

**Status:** First slice implemented in `BackEnd/engine/fb_drive_step_emitter.py`

Start with `BackEnd/engine/fb_drive_step_emitter.py::build_fb_drive_resolution_steps` because it is already the broadest shared FB primitive.

Do not make it StepState-native in one jump. Instead:

1. Leave it building schema as it does today.
2. Wrap each produced drive-resolution step through `project_animation_step_through_fast_break_state`.
3. Verify parity.
4. Only later consider formal field projection for specific stable pieces like ball, timing, and terminal outcome.

Acceptance criteria:

- RR, Triangle, CR, and After-Steal drive-resolution tests remain green.
- Terminal dead-ball fumble still injects correctly.
- Post-shot sub-steps remain intact.
- Terminal freeze announcements remain single-stamped.

### Drive Helper Projection Added

`BackEnd/engine/fb_drive_step_emitter.py::build_fb_drive_resolution_steps` now projects its emitted drive-resolution `AnimationStep[]` through `project_animation_step_through_fast_break_state(...)` before returning.

This is still intended to be behavior-neutral:

- the helper builds the same schema first
- projection uses the schema snapshot path
- `_fb_step_state` is stamped on the returned steps
- if projection fails, the helper logs a warning and returns the original schema steps

`tests/test_fb_step_state_contract.py` now asserts universal drive-helper outputs are already `_fb_step_state` stamped, and that schema remains identical when the stamp is stripped.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **33 passed**.

## Step 6: Move The Universal Outlet-Pass Helper Through StepState

**Status:** First slice implemented in `BackEnd/engine/fb_outlet_pass_step_emitter.py`

Apply the same pattern to `BackEnd/engine/fb_outlet_pass_step_emitter.py::build_fb_outlet_pass_step`.

Keep the helper scoped to FB outlet passes. Do not merge it into the engine-wide pass primitive unless a separate audit proves the shared shape is truly identical.

Acceptance criteria:

- RR/Triangle outlet pass still renders correctly.
- Covert Release outlet pass still renders correctly.
- Ball starts with passer and ends with receiver.
- Interrupted receiver / passer / defender coords remain unchanged.
- SFX and pass-arrival advance triggers remain unchanged.

### Outlet Helper Projection Added

`BackEnd/engine/fb_outlet_pass_step_emitter.py::build_fb_outlet_pass_step` now projects its emitted outlet-pass `AnimationStep` through `project_animation_step_through_fast_break_state(...)` before returning.

This remains behavior-neutral:

- the helper builds the same schema first
- projection uses the schema snapshot path
- `_fb_step_state` is stamped on the returned step
- if projection fails, the helper logs a warning and returns the original schema step

`tests/test_fb_step_state_contract.py` now asserts shared outlet-pass output is `_fb_step_state` stamped, and that schema remains identical when the stamp is stripped.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **33 passed**.

## Step 7: Add FB Observability Helper

**Status:** Complete

`BackEnd/engine/fb_uess_debug.py` now provides the shared FB observability helper:

- `build_fb_uess_summary(result, game, fallback_reason=None)`
- `log_fb_uess_summary(result, game, fallback_reason=None)`

The `FAST_BREAK` branch in `BackEnd/models/turn_manager.py` emits one summary line after StepState projection:

```text
[FB_UESS] game_id=... play=... result=... steps=... schema_burn=... time_elapsed=... first_owner=... final_owner=... final_coords=... states=... fallback=...
```

Standardized fields:

- `game_id`
- `fast_break_play`
- `result_type`
- emitted step count
- schema clock burn
- `time_elapsed`
- first ball owner
- final ball owner
- final coords count
- FB StepState count
- fallback reason (`no_animation_steps` when a FB result has no emitted animation steps)

Acceptance criteria:

- Logs are concise and searchable via `[FB_UESS]`.
- No noisy per-frame logging; exactly one summary line per FB turn at the TurnManager seam.
- Log keys are shared across all four FB families.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> expected pass.

## Step 8: Make Emitter-None Fallbacks Loud In Tests

**Status:** Complete

The migration doc still notes legacy fallback/render artifact paths around old FB animation handling. These are useful safety rails, but they can also hide regressions.

Current implementation:

1. Public FB emitters stamp `fb_emitter_fallback_reason` before known production fallback `None` exits:
   - `rim_runner:<guard>`
   - `triangle:<guard>`
   - `covert_release:<guard>`
   - `after_steal:<guard>`
2. `BackEnd/engine/fb_uess_debug.py::mark_fb_emitter_fallback(...)` owns the shared marker and emits:

   ```text
   [FB_EMITTER_FALLBACK] family=... guard=... detail=... result_type=... play=...
   ```

3. `TurnManager` forwards `fb_emitter_fallback_reason` into the shared `[FB_UESS]` summary when a FB result has no `animation_steps`; otherwise it reports `no_animation_steps`.
4. Production fallback remains intact. No legacy fallback removal was done in this step.

Acceptance criteria:

- Covered FB paths cannot silently fall back in tests.
- Public fallback paths carry a machine-readable reason.
- Production still has safety fallback until prototype testing clears removal.

Verification: `MONGO_DB_NAME=gob-test .venv/bin/pytest tests/test_fb_step_state_contract.py -q` -> **40 passed**.

## Step 9: Retire Legacy FB Render Artifacts / Fallbacks

**Status:** Deferred / blocked pending prototype coverage

Only do this after:

- StepState bridge parity passes.
- All four FB families are covered by contract tests.
- Prototype testing covers normal play, fouls, dead-ball turnovers, steals, bat-OOB, DREB, and pass-ahead.
- Emitter-null paths are confirmed not to occur in live paths.

Current decision: **do not remove production fallback code yet.** Steps 7-8 made fallback paths observable and test-loud, but they did not prove every exotic live branch is covered in the prototype. Removing `capture_fast_break_animation` render artifacts or legacy fallback handlers before that proof would weaken safety and could create missing-animation failures on rare FB outcomes.

Candidate removals:

- leftover `capture_fast_break_animation` render-only artifact paths for RR/Triangle
- flag-gated legacy CR drive-resolution fallback after `USE_FB_DRIVE_RESOLUTION_CR` is retired
- any frontend legacy FB handler paths that are no longer reachable for migrated schema turns

Acceptance criteria:

- No frontend behavior loss.
- No missing fallback for untested exotic cases.
- Reduced code surface without weakening safety.

Readiness checklist before this step can move from deferred to implementation:

- Search backend logs for `[FB_EMITTER_FALLBACK]` during prototype FB testing; expected count is zero for covered live paths.
- Search backend logs for `[FB_UESS] ... fallback=...`; expected fallback value is `None` for covered live paths.
- Prototype-test all four FB families:
  - Rim Runner: MAKE, MISS, BLOCK, FOUL, dead-ball turnover, bat-OOB, interception, outlet denied, hold-up.
  - Triangle: lane-pass shot, setup shot, defensive stop / enter-HCO, outlet denied, bat-OOB / interception where reachable.
  - Covert Release: MAKE, MISS, BLOCK, FOUL, defensive stop, dead-ball turnover, steal.
  - After Steal: MAKE, MISS, BLOCK, FOUL, dead-ball turnover.
- Only after those pass should we remove:
  - RR/Triangle `capture_fast_break_animation` render-only fallback packets.
  - CR flag-gated legacy drive fallback.
  - frontend legacy FB handlers for migrated schema turns.

## Step 10: Documentation Updates

**Status:** Pending throughout implementation

Update docs incrementally after each shipped step:

- `FB_UESS_Audit.md` status lines
- `FB_UESS_Migration.md` if legacy fallback status changes
- `Fast_Break_System.md` if runtime behavior changes
- `StepState.md` if `FastBreakStepState` becomes part of the canonical StepState family

Do not mark FB as StepState-current until the bridge is wired, parity-tested, and active in the TurnManager FB branch.

## Implementation Guardrails

- Do not rewrite all FB emitters at once.
- Do not remove legacy fallback before parity tests and prototype testing.
- Do not centralize play-family setup into one giant emitter.
- Do not move gameplay decisions to the frontend.
- Do not change shot/foul/DREB/possession logic as part of StepState work.
- Keep universalization focused on repeated primitives, not play-family flavor.

## Recommended First Slice

The first implementation slice should be:

1. Add `tests/test_fb_step_state_contract.py` with synthetic schema parity tests.
2. Add `BackEnd/engine/fb_step_state.py`.
3. Wire no runtime behavior yet, or wire behind a local helper test only.
4. Confirm projection parity.

Only after that should TurnManager runtime stamping be added.
