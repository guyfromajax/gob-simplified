# Shot Threshold Scale Tuning

> **Canonical scale module:** `BackEnd/constants/shot_threshold_scale.py`  
> **Frontend mirror:** `FrontEnd/static/js/shared/teamShotThresholdScale.js`  
> **Current values:** MIN **0**, MAX **200**, MID **100** (span always 200; MID = MIN + 100)

## What this attribute is

`shot_threshold` is a **team** attribute used in shot resolution:

```text
made = shot_score >= shot_threshold
```

**Lower raw value = easier makes** (golf score). UI pills center at **MID**: as raw decreases, fill moves **right** (positive/green); as raw increases, fill moves **left** (negative/red).

## Changing the scale (one-knob workflow)

1. Edit **`MIN`** in `BackEnd/constants/shot_threshold_scale.py` only.  
   `MAX`, `MID`, `HALF_SPAN`, balancing overrides, franchise init, tutorial pins, and tournament seed ranges **derive automatically**.
2. Mirror **`MIN`** (and derived constants) in `FrontEnd/static/js/shared/teamShotThresholdScale.js`.
3. Run parity tests:
   ```bash
   pytest tests/test_shot_threshold_scale.py tests/test_mode_init_system.py -q
   ```
4. Sim / playtest FG%. Adjust **`MIN`** again if needed.

**Note:** Existing saved teams keep their stored values until re-seeded or migrated. Moving the window does not retroactively change Mongo team docs.

## How to experiment (your workflow)

**Yes — you can just tell an agent in chat and point them at this doc.** Example prompt:

> Change team shot_threshold scale to MIN **60** (MAX/MID derive automatically). Follow `_documentation_master/00_Operations/Shot_Threshold_Scale_Tuning.md`. Run parity tests. Do not change runtime modifiers unless I ask.

**What the agent should do:**

1. Edit **`MIN`** in `BackEnd/constants/shot_threshold_scale.py` (only `MIN` — `MAX`, `MID`, balancing, franchise init, tutorial, tournament seeds re-derive).
2. Mirror the same **`MIN`** in `FrontEnd/static/js/shared/teamShotThresholdScale.js`.
3. Run `pytest tests/test_shot_threshold_scale.py tests/test_mode_init_system.py -q`.
4. Update the **current scale** line at the top of this doc and the reference table in `Team_Attribute_System.md` (Shooting section) if values changed.
5. Report back: new MIN/MAX/MID, franchise init range, and whether existing Mongo teams need a **+N migration** (see below).

**What you do after:**

- **New franchise / fresh teams:** sim or play a few games; check FG% and pill UI.
- **Existing franchise save:** stored `shot_threshold` values do **not** move with the scale. If you shifted MIN by +40 last time, old teams at ~110 behave ~40 points easier than intended until you migrate (+40 on all persisted values) or start a new franchise.
- **FG% still off after moving the window?** Ask the agent to tune **runtime modifiers** (broken +100, zone deltas, 3PT bump) per the manual checklist below — not another scale move by default.

**Span rule:** delta between lower and upper is always **200**; MID is always **MIN + 100** (= MAX − 100).

## Wired consumers (current scale: 0–200, MID 100)

When **`MIN`** changes, these values re-derive from `BackEnd/constants/shot_threshold_scale.py` (except items in the manual checklist below).

| Area | Current value | Code / notes |
|------|---------------|--------------|
| **Team attribute clamp** (`TEAM_ATTR_RANGES`) | **0 – 200** | Init, training, EOG clamp |
| **Franchise init** | **80 – 90** | `FRANCHISE_INIT_LO` / `FRANCHISE_INIT_HI` — 10–20 below MID |
| **Single-game init** | **0 – 200** | Full clamp range, uniform random |
| **Tournament seeds** | See table below | `TOURNAMENT_SEED_ST_RANGES` |
| **Score balancing** | Trailing **−20**, leading **180** | `MIN − 20` / `MAX − 20` |
| **Rim-runner corner FB** | **180 − fb_efficiency** | `FAST_BREAK_CORNER_THRESHOLD_BASE` (`MAX − 20`) |
| **Uncontested-3 make bar** | **200 − CH + round(dist × 2.0)** | `SHOT_THRESHOLD_MAX` in `shot_manager.resolve_shot` — always tracks MAX |
| **FTE tutorial** | User **0**, computer **100** | `TUTORIAL_USER` (= MIN), `TUTORIAL_COMPUTER` (= MID) |
| **UI pills** | Center **100**, span **0–200** | `teamShotThresholdScale.js` → FCC, training report, tournament, court, box score |

**Tournament seed shot_threshold ranges:**

| Seed | Range | Notes |
|------|-------|-------|
| 1 | 0 – 100 | Best shooters |
| 2 – 4 | 0 – 150 | |
| 5 – 7 | 50 – 200 | |
| 8 | 100 – 200 | Worst shooters |

## Frontend files (import shared scale — do not hardcode MID)

| File | Usage |
|------|--------|
| `franchise-command-center.js` | `getTeamAttrVisualConfig` |
| `training-report.js` | `createPill`, delta sign invert |
| `tournament.js` | `createPill` |
| `court.html` / `court (1).html` | `createAttrPill` |
| `box-score.js` | attribute-change delta pills |

HTML pages load `/js/shared/teamShotThresholdScale.js` before the page script.

## Manual checklist (does NOT auto-derive from MIN)

When retuning feel beyond moving the storage window, grep and revisit:

| Pattern / area | Notes |
|----------------|--------|
| `balancing_shot_threshold_override` | Uses derived `BALANCING_*` if wired through scale module |
| `shot_threshold += 100` (broken variant) | Runtime modifier in `shot_manager.py` — not part of attribute scale |
| Zone threshold deltas (+25/−25 etc.) | `shot_manager._hco_zone_shot_threshold_delta` |
| Distance threshold adjustment | `resolve_shot`: threes add `round(Euclid × 2.0)` via `THREE_POINT_DISTANCE_THRESHOLD_MULTIPLIER`, including the undefended-outside make bar. Twos subtract 40 at or within 12 grid and subtract 20 beyond 12 through 19 grid on standard threshold comparisons. |
| Home crowd shot deltas | `home_crowd.py` |
| EOG / training **delta magnitudes** (+5, −10, etc.) | Same numeric delta = different feel if MID moved |
| SFX tiers **101 / 210** on `shot_score_pre_defense` | **Not** team attribute scale — `gameSfx.js`, `ShotAnimationSystem.js` |
| HCT/FCP read thresholds (110, 175, 200) | Motion reads — unrelated |
| `SOFT_SHOOTING_FOUL_THRESHOLD = 110` | Foul math — unrelated |

## Docs to update when scale changes

- `Team_Attribute_System.md` — range + pill center
- `Attribute_Clamp_System.md` — clamp row
- `Constants_System.md` — `TEAM_ATTR_RANGES` row
- `Training_System.md` — shooting pill paragraph
- `fte_system.md` — tutorial forced values (if tutorial pins change)

## Related docs

- [Shot_System.md](../06_Gameplay_Systems/Shot_System.md) — resolution flow and threshold modifiers
- [Team_Attribute_System.md](./Team_Attribute_System.md) — init ranges and UI copy
