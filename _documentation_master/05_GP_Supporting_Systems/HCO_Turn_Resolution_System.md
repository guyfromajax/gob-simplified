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

## Playcall strip (court UI)

During **HCO** turns, the lower-third **playcall strip** on the court page (`FrontEnd/static/court.html`, `#playcall-strip`) summarizes the chosen offense play, offensive focus/target, defense call, and **expected value (EV)** for that half-court turn.

### When it appears

- `FrontEnd/static/js/phaser/ui/playcallCenter.js` treats a turn as HCO when turn payload fields such as `offensive_state`, `current_turn`, or `play_type` read as `HCO`, or `playcall === 'HCO'`.
- On each qualifying turn update, `dispatchPlaycallStripShow` fires a window event **`gob:playcall-strip-show`** with `detail`: `offensePlay`, `offenseTarget`, `defensePlay`, and **`ev`** (from `turnData.ev`). Non-HCO turns dispatch **`gob:playcall-strip-hide`** instead.
- `FrontEnd/static/js/phaser/gameScene.js` listens for those events and updates the strip DOM (offense/defense text and the EV meter). **EV is not recomputed in the client**; it is whatever the turn payload supplies, rounded and displayed.

### EV advantage meter (chevrons)

The centered EV control (`#pcs-ev`, class `pcs-ev-meter`) is **presentational only**. It does not change HCO resolution logic.

**Inputs**

- `ev` is parsed as a number. Non-finite values show `--` (gold).
- Otherwise EV is shown as an integer percent in **[-100, +100]** (clamped after `Math.round`).

**Lit slot count**

- There are always **10** chevron slots in one horizontal row (plus the signed percentage).
- **Lit slots** = `Math.round(Math.abs(EV) / 10)`, clamped to **0–10** (each lit chevron represents roughly ten percentage points of advantage magnitude).

**Direction and layout**

- **Positive EV** (offense advantage): solid **left**-pointing chevrons for lit slots; unlit slots use hollow **right**-pointing marks. Layout: **`[+XX%]`** (eight-pixel gap) **chevron row** (number on the **left** of the row).
- **Negative EV** (defense advantage): solid **right**-pointing chevrons for lit slots; unlit slots use hollow **left**-pointing marks. Layout: **chevron row** (gap) **`[-XX%]`** (number on the **right**).
- **EV = 0**: five hollow left-pointing | **`0%`** | five hollow right-pointing (neutral “outward from center” look). The number uses **`0%`** (no plus sign); positive and negative values always include **`+`** or **`-`** on the number.

**Color (matches momentum strip tokens)**

- Lit offense / number on offense side: `#34EC27`
- Lit defense / number on defense side: `#ff4444`
- Unlit stroke/fill base: `rgba(255, 255, 255, 0.10)`

Direction of chevrons and the sign on the percentage are redundant cues (not color-only).

**Animation (on each strip show / EV update)**

- Lit chevrons fade in over ~**250 ms**, staggered **left-to-right** for offense advantage and **right-to-left** for defense advantage. Unlit slots are not animated.
- The percentage uses a short **~150 ms** opacity intro.

Implementation lives in **`renderPlaycallEvMeter`** in `FrontEnd/static/js/phaser/gameScene.js` and the `.pcs-ev-meter*` rules in `FrontEnd/static/court.html`.

## Key Files

- `BackEnd/engine/phase_resolution.py`
- `BackEnd/models/turn_manager.py`
- `BackEnd/utils/team_play_utils.py`
- `FrontEnd/static/js/phaser/ui/playcallCenter.js` (HCO gating and `gob:playcall-strip-show` / `hide` dispatch)
- `FrontEnd/static/js/phaser/gameScene.js` (`showPlaycallStrip`, `renderPlaycallEvMeter`)
- `FrontEnd/static/court.html` (`#playcall-strip`, `#pcs-ev`, meter styles)
