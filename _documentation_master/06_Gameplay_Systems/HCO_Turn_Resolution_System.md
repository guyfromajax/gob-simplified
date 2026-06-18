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

**Momentum (MO):** when a set play resolves as the **`successful`** variant and the shot is a **MAKE**, the shooter (the target_shooter by construction in this variant) gets **+1 MO** (`MO_SET_PLAY_DELTA`, applied in `resolve_half_court_offense_logic` right after `resolve_shot`). Motion offense has no target shooter and no such bonus. See [Player_Momentum_System.md](Player_Momentum_System.md).

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

### EV advantage meter (chevrons + pivot)

The centered EV control (`#pcs-ev`, class `pcs-ev-meter`) is **presentational only**. It does not change HCO resolution logic.

**Inputs**

- `ev` is parsed as a number. Non-finite values show `--` (gold).
- Otherwise EV is shown as an integer percent in **[-100, +100]** (clamped after `Math.round`).

**Lit slot count**

- Two rows of **10** chevrons each (**20** total), flanking a fixed **EV** pivot (small label + hairline ticks). **Lit count per advantaged row** = `Math.round(Math.abs(EV) / 10)`, clamped to **0–10** (the opposite row stays fully unlit).

**Direction and layout**

- Fixed **five columns**: `[number-left]` · `[left chevrons ×10]` · **`EV` pivot** · `[right chevrons ×10]` · `[number-right]`. Outer number slots keep **stable width** so the strip does not jump when the sign flips.
- **Positive EV**: **`+XX%`** in the left slot; **left** row uses solid **◀** for lit slots (filled from the slot **nearest the pivot** outward toward the number); **right** row is all hollow **▷** (unlit). **EV** pivot is always visible (muted typography + ticks).
- **Negative EV**: **`−XX%`** in the right slot; **right** row uses solid **▶** for lit slots (filled from the pivot outward); **left** row is all hollow **◁**. **EV** pivot unchanged.
- **EV = 0**: both number slots empty; **10** hollow **◁** left of pivot and **10** hollow **▷** right of pivot; **`0%`** sits beside the **EV** label (gold). No plus sign on zero.

**Color (matches momentum strip tokens)**

- Lit offense / number on offense side: `#34EC27`
- Lit defense / number on defense side: `#ff4444`
- Unlit stroke/fill base: `rgba(255, 255, 255, 0.10)`

Direction of chevrons, the **EV** pivot, and the sign on the percentage are redundant cues (not color-only).

**Animation (on each strip show / EV update)**

- Lit chevrons fade in over ~**250 ms**: offense row staggered **right-to-left** from the pivot; defense row **left-to-right** from the pivot. Unlit slots are not animated.
- The percentage uses a short **~150 ms** opacity intro.

Implementation lives in **`renderPlaycallEvMeter`** / **`pcsEvPivotMarkup`** in `FrontEnd/static/js/phaser/gameScene.js` and the `.pcs-ev-meter*` rules in `FrontEnd/static/court.html`.

## Key Files

- `BackEnd/engine/phase_resolution.py`
- `BackEnd/models/turn_manager.py`
- `BackEnd/utils/team_play_utils.py`
- `FrontEnd/static/js/phaser/ui/playcallCenter.js` (HCO gating and `gob:playcall-strip-show` / `hide` dispatch)
- `FrontEnd/static/js/phaser/gameScene.js` (`showPlaycallStrip`, `renderPlaycallEvMeter`)
- `FrontEnd/static/court.html` (`#playcall-strip`, `#pcs-ev`, meter styles)
