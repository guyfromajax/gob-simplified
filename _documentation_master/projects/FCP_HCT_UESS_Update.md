# FCP / HCT UESS + StepState Update Plan

**Status:** Steps 1-7 implemented; Step 8 first + terminal slices implemented  
**Scope:** Dynamic Full-Court Press (FCP) and Half-Court Trap (HCT) turns  
**Primary code paths:** `BackEnd/engine/dynamic_hct.py`, `dynamic_hct_step_emitter.py`, `dynamic_fcp.py`, `dynamic_fcp_step_emitter.py`, `BackEnd/models/turn_manager.py`, `FrontEnd/static/js/phaser/animation/animationPlayback.js`  
**Related docs:** `projects/FCPHCT_UESS_Audit.md`, `projects/StepState.md`, `05_UESS_System/UESS_System.md`, `06_Gameplay_Systems/HCT_System.md`, `06_Gameplay_Systems/Dynamic_HCO_System.md`

---

## Goal

Bring dynamic FCP and HCT into the same practical UESS direction as modern HCO:

> resolve once -> freeze the game-relevant state -> project to animation schema -> frontend renders only.

The short-term target is not a large rewrite. The safe path is:

1. Fix the known correctness gaps in the current schema path.
2. Centralize shared HCT/FCP emission and timing behavior.
3. Then tighten the current segment model into a clearer pressure-turn StepState projection.

FCP delegates into the HCT engine (`compute_dynamic_hct_turn(..., turn_mode="fcp")`), so the same implementation path should cover both.

---

## Current State

### Already Good

- HCT and FCP already emit `animation_steps`.
- FCP reuses the HCT engine and emitter wrapper.
- Normal HCT/FCP passes already use the shared pass-step primitive.
- Backend already owns most game-relevant facts:
  - result type
  - pass-contest outcome
  - steal / foul / dead-ball outcomes
  - segment destinations
  - segment timing
  - movement archetype
  - bat-OOB contact and OOB target

### Not Yet UESS / StepState Complete

- The engine returns `loop_segments`, and the emitter still derives a lot of final schema details from those segments.
- Pass interceptions do not currently emit a real pass-flight-to-interceptor step.
- Batted-OOB now emits a backend-authored schema trajectory in the dynamic HCT/FCP path; the old frontend imperative ball-send remains as fallback only when schema metadata is absent.
- Schema `turn_stop` handlers for `STEAL`, `FOUL`, and `DEAD_BALL_TURNOVER` are cleanup-only finalization paths in `animationPlayback.js`.
- HCT/FCP time-elapsed and clock handling is less centralized than HCO.
- Docs still contain stale references about FCP/HCT migration state.

---

## Non-Negotiable UESS Rules

For FCP/HCT, the following values must be backend-owned:

- player start coords, destinations, and final coords
- ball owner at step start and step end
- ball flight origin, contact point, and arrival target
- step timing and clock burn
- advance trigger
- terminal event and payload
- possession outcome
- stat outcome
- any trigger that affects SFX or announcement timing

The frontend may choose rendering style, interpolation, and purely cosmetic effects. It must not correct game state, invent ball ownership, choose outcomes, or repair missing backend trajectory.

---

## Step 1: Lock Current Behavior With Focused Tests / Debug Fixtures

**Status:** Started / initial emitter-contract coverage added in `tests/test_fcp_hct_uess_contract.py`.

**Purpose:** Before changing the pipeline, make the known terminal cases observable and regression-proof.

Create focused backend tests or fixture assertions for:

- HCT normal pass
- FCP normal pass
- HCT pass interception
- FCP pass interception
- HCT batted-OOB
- FCP batted-OOB
- HCT dead-ball turnover
- FCP dead-ball turnover
- HCT foul
- FCP foul
- HCT/FCP make, miss, block

Minimum assertions:

- `animation_steps` exist.
- step chain is linear and terminates.
- no `next_step` points backward unless explicitly intended.
- terminal step has correct `turn_stop`.
- final step has correct ball owner or ball destination.
- emitted clock burn matches `time_elapsed`.

This step should not change gameplay behavior.

### Initial Coverage Added

`tests/test_fcp_hct_uess_contract.py` uses small synthetic HCT/FCP payloads to exercise the shared dynamic pressure emitter directly. It currently covers:

- HCT/FCP `STEAL` terminal chain shape.
- HCT/FCP `DEAD_BALL_TURNOVER` terminal chain shape.
- HCT/FCP `FOUL` terminal chain shape.
- HCT/FCP normal pass schema shape (`ball_reaches_player`, passer, receiver, end owner).
- HCT/FCP pass interception schema shape (`ball_reaches_player`, passer, stealer, contact target, end owner).
- HCT/FCP batted-OOB schema trajectory to the backend-owned OOB target.

Verification note: the repo-level pytest path may be blocked locally when `tests/conftest.py` attempts Mongo seeding against an unavailable or blocked DB. The direct emitter-contract checks can be run through the repo venv without requiring live DB behavior.

---

## Step 2: Fix Pass Interceptions First

**Status:** Implemented for the emitted schema path.

**Problem:** Current HCT/FCP interception path resolves `INTERCEPT` into an `hct_interception` stopper segment. That produces the outcome, but it does not render the actual pass being intercepted.

Current shape:

```text
pass contest -> INTERCEPT
result_type = STEAL
emit hct_interception stopper
post-steal step later owns ball
```

Desired shape:

```text
pass contest -> INTERCEPT
emit pass-intercept step:
  passer owns ball at start
  ball flies toward contact point
  interceptor reaches / receives at contact point
  ball owner becomes interceptor
then terminal STEAL / post-steal transition
```

Implementation direction:

- Mirror the Rim Runner lane-pass interception pattern.
- Use backend-owned `contact_point`, `stealer_id`, `victim_id`, and current passer.
- Emit a real ball trajectory in schema.
- Avoid a frontend-only steal correction.
- Keep the post-steal HCO/HCT/FCP transition if still needed, but it must start from a truthful final ball owner.

Acceptance criteria:

- No ball teleport from passer to stealer.
- No repeated receive / ball-landing SFX loop.
- `runSteal` can be minimal because the schema step already leaves the ball attached correctly.
- FCP and HCT both pass the same interception fixture.

### Implementation Notes

- `dynamic_hct.py` now stamps pass-interception metadata onto the terminal `hct_interception` segment:
  - `pass_from_pos`
  - `pass_to_pos`
  - `interceptor_pos`
  - `interception_contact`
- `dynamic_hct_step_emitter.py` now projects `hct_interception` into a schema pass-intercept step:
  - ball starts in flight from passer to stealer
  - ball arrival target is the backend-owned contact point
  - stealer moves to the contact point
  - step ends with `ball.owner_player_id = stealer_id`
- The existing post-steal transition remains in place and now starts from a truthful final ball owner.
- `tests/test_fcp_hct_uess_contract.py` now expects the HCT/FCP pass-interception contract to pass.

Remaining related work:

- Pressure StepState is now stamped additively from the emitted schema; Step 8 moves projection upstream.

---

## Step 3: Make Schema `STEAL` Turn Stop Safe

**Status:** Implemented for schema playback cleanup.

**Problem:** `dispatchTurnStop("STEAL")` currently routes to a stub.

The schema should already own the important state, but the terminal handler still needs to be safe:

- clear pending ball-flight state
- ensure the ball controller agrees with the final schema owner
- avoid replaying legacy steal animation
- avoid double announcements if the backend/turn finalization already announced interception

Implementation direction:

- Keep `runSteal` small.
- Treat it as finalization / cleanup, not gameplay logic.
- Do not duplicate legacy `handleSteal` behavior blindly.

Acceptance criteria:

- Schema STEAL turns complete without console stub warnings.
- Ball state after playback matches the final emitted step.
- No duplicate steal/interception announcement.

### Implementation Notes

- `animationPlayback.js` now implements `runSteal` as a cleanup-only schema terminal handler.
- It does **not** replay legacy steal animation or announce anything.
- It resolves the stealer from the backend-authored turn-stop payload first (`stealer_id` / `stealerId`), with conservative fallbacks to turn metadata.
- It clears stale pass/pending-owner state and aligns:
  - BallController current owner
  - legacy `ballHolder`
  - visible ball attachment
- The actual interception pass animation remains backend-authored by Step 2; this handler only finalizes frontend state after schema playback.

---

## Step 4: Move Batted-OOB Ball Flight Into Schema

**Status:** Implemented for dynamic HCT/FCP schema playback.

**Problem:** Backend owns the batted-OOB contact and OOB target, but the frontend still performs an imperative ball-send.

Desired shape:

```text
pass contest -> BAT_OOB
emit backend-authored ball trajectory:
  passer -> contact point -> OOB target
terminal/dead-ball state:
  offense retains
  next play is side inbound
```

Implementation direction:

- Add a dedicated batted-OOB schema step or sub-step in `dynamic_hct_step_emitter.py`.
- Use existing backend fields:
  - `bat_oob_contact`
  - `bat_oob_target`
  - `bat_oob_deflector_pos`
- Keep SFX.
- Remove or demote frontend imperative `_runHctBatOobBallSend` to legacy fallback only.

Acceptance criteria:

- Ball path is fully visible in emitted `animation_steps`.
- Frontend does not need to invent OOB ball motion.
- Offense retains possession correctly.
- No stats are incorrectly awarded.

### Implementation Notes

- `dynamic_hct.py` stamps terminal `hct_bat_oob` segments with:
  - `pass_from_pos`
  - `pass_to_pos`
  - `deflector_pos`
  - `bat_oob_contact`
  - `bat_oob_target`
- `dynamic_hct_step_emitter.py` projects `hct_bat_oob` into two schema steps:
  - contact step: passer -> backend-owned contact point, deflector moves to contact, `block1.wav` contact SFX fires via `sfx_on_ball_arrival`
  - drift step: loose ball moves from contact to backend-owned OOB target and terminates the dead-ball turn
- `phase_resolution.py` passes `bat_oob_target` through both FCP and HCT turn results.
- `AnimationEngine.js` now skips the old HCT/FCP imperative `_runHctBatOobBallSend` when the schema already contains batted-OOB trajectory metadata.
- The old imperative helper remains as fallback only for legacy/missing-schema cases.
- `tests/test_fcp_hct_uess_contract.py` now requires this contract for both HCT and FCP.

---

## Step 5: Make Schema Terminal Handlers Safe For Dead Balls And Fouls

**Status:** Implemented for schema playback cleanup.

`animationPlayback.js` used to have stubs for several `turn_stop` events. HCT/FCP should not depend on legacy handlers when `animation_steps` exist.

Minimum scope:

- `DEAD_BALL_TURNOVER`
- `FOUL`
- `STEAL`

Implementation direction:

- Keep handlers thin.
- Backend payload decides what happened.
- Frontend may display/clean up, but not decide next state.
- Avoid double announcements with the existing turn-preparation finalization path.

Acceptance criteria:

- No schema terminal stub warnings during HCT/FCP turns.
- Dead-ball turnover micro movement still works where expected.
- Shooting foul / non-shooting foul behavior remains unchanged outside terminal cleanup.

### Implementation Notes

- `runFoul` is now cleanup-only:
  - clears stale pass-in-flight state
  - clears pending ball owner
  - does not announce, whistle, navigate, set up FT, or mutate gameplay outcome
- `runDeadBallTurnover` is now cleanup-only:
  - clears stale pass-in-flight state
  - clears pending ball owner
  - does not duplicate dead-ball fumble/OOB visuals or inbound setup
- `runSteal` continues to align final ball ownership to the backend-authored stealer.
- Existing turn finalization remains responsible for foul / turnover announcements and next-turn flow.

---

## Step 6: Centralize HCT/FCP Emission In TurnManager

**Status:** Implemented.

**Problem:** HCO has a cleaner centralized emit path. HCT/FCP emission is branchier and has fallback-specific handling.

Implementation direction:

Add a shared pressure-turn emission helper in `BackEnd/models/turn_manager.py`, conceptually:

```python
_emit_pressure_animation_steps(result, turn_type)
```

Responsibilities:

- choose HCT or FCP emitter
- preserve existing fallback behavior only where needed
- stamp animation steps on result
- derive `time_elapsed` from emitted schema clock burn for all result types
- verify / backfill final coords
- verify / backfill final ball coords
- prepare for pressure StepState stamping

Acceptance criteria:

- HCT and FCP use the same TurnManager emission contract.
- `time_elapsed` matches emitted clock burn for steals, fouls, dead balls, shots, and pressure breaks.
- Existing full sim / no-animation paths remain safe.

### Implementation Notes

- `TurnManager._emit_pressure_animation_steps(result, turn_type)` is now the single FCP/HCT emission path.
- FCP preserves existing behavior:
  - dynamic FCP (`fcp_loop_segments`) uses `build_dynamic_fcp_animation_steps`
  - non-dynamic FCP falls back to `build_skeleton_animation_steps(..., turn_type="FCP")`
- HCT uses `build_dynamic_hct_animation_steps` unless the resolver already stamped `animation_steps`.
- `TurnManager._stamp_schema_clock_contract` now derives `time_elapsed`, `step_clock_seconds`, `resolution_step_index`, and `executed_step_count` from emitted schema for every pressure result type.
- This fixes the previous FCP wrapper-copy seam where dynamic emitter timing mutations could stay on the copied payload.
- The shared pressure helper retains the entry-ball seam detector for both FCP and HCT.
- `tests/test_fcp_hct_uess_contract.py` asserts non-shot HCT/FCP results are stamped from schema clock burn.

---

## Step 7: Define Pressure StepState Shape

**Status:** Implemented additively.

After the visible terminal behavior is stable, formalize the pressure StepState shape.

Recommended structure:

```text
PressureStepState:
  players:
    <player_id>:
      start_coord
      target_dest
      end_coord
      action
      archetype
  ball:
    from_owner
    to_owner
    from_coord
    arrival_coord
    motion_style
    contact_point?
    resolved_by?
  timing:
    step_t
    game_clock_start
    game_clock_end
    shot_clock_start
    shot_clock_end
  advance_gate:
    condition
    target_player?
    target_coord?
  outcome:
    none | steal | bat_oob | foul | dead_ball_turnover | shot | pressure_break
  cosmetics:
    flourish_triggers
    sfx_triggers
    announcement_triggers
```

Important constraint:

- All coords should be in one display frame.
- No consumer should re-flip or reinterpret coordinate frame.

Acceptance criteria:

- StepState is a value, not a computation.
- Emitter can project StepState to schema without re-deciding game-relevant facts.
- FCP and HCT share the same shape.

### Implementation Notes

- Added `BackEnd/engine/pressure_step_state.py`.
- `TurnManager._emit_pressure_animation_steps` now calls `build_pressure_step_states(result, turn_type)` after schema emission and schema clock stamping.
- The current builder is intentionally additive and behavior-neutral:
  - it reads the emitted `animation_steps`
  - freezes schema facts into `result["pressure_step_states"]`
  - stamps each emitted step with `_pressure_step_state`
  - no gameplay or frontend consumer reads it yet
- The frozen shape includes:
  - `players`: start coord, target destination, end coord, action, archetype
  - `ball`: owner/trajectory fields, motion style, contact point, end coord
  - `timing`: step duration, game clock start/end, shot clock start/end
  - `advance_gate`: condition, target player/coord, metadata
  - `outcome`: terminal event payload, pressure break, or none
  - `cosmetics`: SFX / announcement / flourish trigger payloads
- Normal pressure pass steps currently do not always stamp `ball_motion_style`; PressureStepState infers `motion_style="pass"` from `from_player_id` / `to_player_id` / `ball_reaches_player`.
- `tests/test_fcp_hct_uess_contract.py` now asserts:
  - pressure StepState count matches emitted schema step count
  - each step carries `_pressure_step_state`
  - normal HCT/FCP passes freeze passer, receiver, player actions, and timing
  - terminal foul outcomes freeze the backend-authored payload
  - batted-OOB contact/drift freeze contact and OOB ball coords

Remaining related work:

- Step 8 should move the remaining pressure-turn derivations upstream so the emitter projects `PressureStepState -> AnimationStep` instead of freezing schema after the fact.

---

## Step 8: Project Pressure StepState To Animation Schema

**Status:** Projection bridge complete for current HCT/FCP emitted schema; upstream builder rewrite remains.

Once StepState exists, update `dynamic_hct_step_emitter.py` so its primary job is projection:

```text
PressureStepState -> AnimationStep JSON
```

Move out of the emitter any remaining game-relevant derivation:

- ball owner by step
- pass contact / arrival
- step timing
- advance trigger
- terminal payload
- final coords
- final ball coords

Keep in the emitter:

- tween duration as pure function of frozen StepState
- visual interpolation style
- cosmetic SFX file/tier selection if still intentionally carved out

Acceptance criteria:

- The emitter does not need game state except for explicitly allowed cosmetic lookups.
- HCT/FCP animation output remains behaviorally equivalent except for the intentional bug fixes.

### Implementation Notes

- `pressure_step_state.py` now exposes `project_pressure_step_states_to_animation_steps(step_states)`.
- Each stamped pressure StepState carries a transitional `schema_projection` snapshot of the emitted step.
- `TurnManager._emit_pressure_animation_steps` now routes through:

```text
AnimationStep[] -> PressureStepState[] -> AnimationStep[]
```

- This is intentionally a parity bridge, not the final upstream rewrite. It proves the projection seam while preserving exact schema output.
- `tests/test_fcp_hct_uess_contract.py` now asserts projection parity for:
  - HCT/FCP normal pass
  - HCT/FCP pass interception / steal
  - HCT/FCP batted-OOB contact + drift
  - HCT/FCP shot setup paths (`hct_fb_drive`, `hct_ab_drive`, `hct_ab_dish`, `hct_ab_shot`)
  - HCT/FCP shared post-shot sub-steps (`shot_resolved`, make hold, miss bounce, block terminal, bank/rattle/airball variant beats)
- First slice implemented:
  - formal projection is now used for `hct_entry_walkup`, `hct_advance`, `hct_pass`, `hct_interception`, `hct_bat_oob_contact`, and `hct_bat_oob_drift`
  - formal StepState now carries exact schema linkage (`next`), render tween durations, SFX triggers, flourish triggers, and explicit-vs-inferred ball motion fields
  - tests assert at least one first-slice state uses `projection_source="formal"` and still round-trips to the original emitted schema
- First-slice emitter boundary moved:
  - `dynamic_hct_step_emitter.py` now routes those first-slice steps through `project_animation_step_through_pressure_state(...)` before appending them
  - direct HCT/FCP emitter output now carries `_pressure_step_state` on the formal first-slice steps
  - `TurnManager` still keeps the whole-turn projection bridge as a defensive consistency layer while the remaining paths migrate
- Terminal slice implemented:
  - formal projection now covers generic terminal pressure outcomes: `hct_steal`, `hct_foul`, `hct_reach_in`, `hct_dead_ball`, and `hct_dead_ball_turnover`
  - dead-ball fumble beats (`advance_trigger.condition = "dead_ball_fumble"`) are also formal-projected so the appended fumble step and its rewired prior `next` pointer are frozen through StepState
  - formal projection now preserves backend-authored terminal announcements, including the fumble whistle/banner payload
  - `dynamic_hct_step_emitter.py` performs one final projection pass at the return boundary after late helper mutations such as post-steal transition append and dead-ball fumble injection
  - direct HCT/FCP emitter tests assert terminal foul, dead-ball turnover, fumble, and steal paths carry `_pressure_step_state` with `projection_source="formal"`
- Shot-setup slice implemented:
  - formal projection now covers pressure-owned shot setup steps: `hct_fb_drive`, `hct_ab_drive`, `hct_ab_dish`, and `hct_ab_shot`
  - direct HCT/FCP emitter tests assert fast-break drive shot setup, attack-basket shoot-in-place, attack-basket drive, and attack-basket drive-dish setup steps carry formal `_pressure_step_state`
- Post-shot slice implemented:
  - formal projection now covers shared post-shot sub-steps appended by `_build_post_shot_sub_steps(...)`
  - formal sources include `shot_resolved` and variant/follow-up beats stamped through `advance_trigger.metadata.kind`: `make_hold`, `bounce`, `rattle_hop`, `rattle_settle`, `bank_settle`, `bank_graze`, and `airball_oob`
  - formal projection now preserves `timed_sfx` in addition to ball release/arrival SFX, announcements, flourishes, tween durations, explicit ball motion style, and final `next` pointers
  - direct HCT/FCP emitter tests assert make, miss+bounce, block, and bank-make post-shot chains carry formal `_pressure_step_state` and round-trip without schema drift
- Remaining Step 8 work:
  - move individual pressure builders (`_build_loop_step`, pass, interception, batted-OOB, terminal helpers, shot setup, and post-shot integration) to return formal PressureStepState directly instead of building schema then projecting
  - shrink/remove the transitional `schema_projection` once all formal fields project exact schema
  - keep emitter decisions limited to pure render projection and explicitly allowed cosmetic lookup

---

## Step 9: Update Documentation

Update these docs after implementation:

- `projects/FCPHCT_UESS_Audit.md`
  - mark pass-interception gap closed
  - mark terminal handler state
  - mark batted-OOB state
- `05_UESS_System/UESS_System.md`
  - correct FCP/HCT migration table
  - remove stale `skeleton_step_emitter` claim for dynamic FCP
- `06_Gameplay_Systems/HCT_System.md`
  - document shared HCT/FCP pressure StepState path
  - document pass interception and batted-OOB schema behavior
- `projects/StepState.md`
  - add note that HCT/FCP pressure turns now follow the same resolve/freeze/project principle
- any FCP-specific doc that still implies FCP has a separate animation model

---

## Implementation Order

1. Add focused tests / debug fixtures.
2. Fix HCT/FCP pass interception schema.
3. Implement safe schema `STEAL` terminal cleanup.
4. Move HCT/FCP batted-OOB ball flight into schema.
5. Implement safe schema `DEAD_BALL_TURNOVER` and `FOUL` cleanup if still required.
6. Centralize HCT/FCP emission in `TurnManager`.
7. Define/stamp pressure StepState. **Implemented additively.**
8. Convert emitter from segment interpretation to StepState projection. **First slice implemented; upstream builder migration and shot paths remain.**
9. Update documentation.
10. Run regression tests and manual prototype checks.

---

## Manual QA Checklist

Test both HCT and FCP:

- normal pass completes
- pass interception animates ball to defender
- steal finalizes without stub warning
- batted-OOB sends ball to OOB target
- offense retains after batted-OOB
- dead-ball turnover fires correct animation / announcement
- foul fires correct announcement / SFX / next state
- make, miss, block still render correctly
- pressure break into HCO still works
- no duplicate announcements
- no repeated receive SFX loop
- no frozen turn after terminal events

---

## Risk Notes

- The highest-risk area is not the StepState shape itself; it is terminal event handoff between schema playback and legacy frontend handlers.
- Do not remove legacy handlers until schema behavior is verified.
- Do not rewrite all HCT/FCP movement before fixing pass interception and batted-OOB. Those two bugs define the target shape and will de-risk the later StepState work.
- Keep FCP as a wrapper around HCT unless a concrete divergence is required.
