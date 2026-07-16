ur a# Fast Break UESS + StepState Audit

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

