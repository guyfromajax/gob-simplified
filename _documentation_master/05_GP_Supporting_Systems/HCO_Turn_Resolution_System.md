# HCO Turn Resolution System

## Overview

HCO resolves half-court possessions after playcall selection.

Core responsibilities:
- fetch the correct offensive skeleton
- run foul / steal / turnover gates
- choose the execution variant
- route to shot resolution or non-shot outcomes

Primary files:
- `BackEnd/engine/phase_resolution.py`
- `BackEnd/models/turn_manager.py`

## Play Identity and Skeleton Fetch

Current HCO skeleton resolution is `play_id`-driven.

Runtime flow:
1. HCO receives `game_state["current_playcall"]` as the display name.
2. Runtime resolves the team-owned play copy from `offense_team.plays` using compatibility helpers.
3. It reads `play_id` from that team-owned play copy.
4. It loads the universal play doc from the `plays` collection by `_id`.
5. It selects the correct skeleton variant from the universal doc.

This is implemented in `phase_resolution.py` via:
- team play resolution helpers
- universal play fetch by `play_id`
- per-game skeleton cache

## Set Play Runtime Position Mapping

Set-play documents now store skeleton role keys using aliases:
- `target_shooter`
- `pos1`
- `pos2`
- `pos3`
- `pos4`

The engine does not execute those aliases directly.

Before HCO uses a set-play skeleton, runtime remaps those aliases back to canonical lineup positions:
- `PG`
- `SG`
- `SF`
- `PF`
- `C`

The alias map is derived from the play copy’s `target_shooter`, falling back to the universal play doc’s `target_shooter`.

This remapping applies to:
- `pos_actions` keys
- event position references used by runtime

## Variant Selection

Motion plays:
- use `skeletons.base_loop`
- can use `versions` if present

Set plays:
- use one of:
  - `successful`
  - `mid_play_change`
  - `contested`
  - `broken`
- successful may be stored either as direct `steps` or as a `versions` array

The selected set-play skeleton is remapped to canonical lineup positions after variant selection.

## HCO Outcome Gates

HCO still uses the same high-level gating model:
- standard fouls
- steal attempts
- dead-ball turnovers
- shot-path resolution when no stopper event occurs

Those calculations remain attribute- and strategy-driven.
The play-identity migration did not change the statistical gate formulas.

## Target Shooter Semantics

`target_shooter` means:
- the intended primary recipient / shooter role for the set play
- the stable role used to map set-play aliases at runtime

Important:
- `target_shooter` is not guaranteed to be the actual shooter in failed set-play variants
- this is why the skeleton alias is `target_shooter`, not `shooter`

## Team Overrides

HCO now supports team-specific `target_shooter` overrides because the runtime map prefers the team-owned play copy when present.

That means future UI customization can change a team’s `target_shooter` without changing the universal play doc.

## Rename Safety

HCO is now protected from play renames in the critical fetch path because:
- team play metadata carries `play_id`
- universal skeleton fetch is by `play_id`
- team play resolution supports both name-keyed and `play_id`-keyed storage maps

## Key Files

- `BackEnd/engine/phase_resolution.py`
- `BackEnd/models/turn_manager.py`
- `BackEnd/utils/team_play_utils.py`
