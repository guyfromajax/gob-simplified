# Shot Threshold Scale Tuning

> **Canonical scale module:** `BackEnd/constants/shot_threshold_scale.py`  
> **Frontend mirror:** `FrontEnd/static/js/shared/teamShotThresholdScale.js`  
> **Current values:** MIN **−10**, MAX **190**, MID **90** (span always 200; MID = MIN + 100)  
> _Changed 2026-08-11 from 0/200/100, to −30/170/70 on 2026-08-12, then to −10/190/90 on 2026-08-14. Lower raw = easier makes._

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
4. **RE-CUT THE EOG `shot_threshold` BANDS.** ← mandatory, see below
5. Sim / playtest FG%. Adjust **`MIN`** again if needed (and re-cut the bands again if you do).

### 4. Re-cutting the EOG bands — REQUIRED on every scale move

**Moving the window silently breaks the EOG `shot_threshold` bands.** This is not a
nice-to-have step; skipping it has already shipped a broken config once.

**Why.** `shot_threshold` is compared ABSOLUTELY in `made = shot_score >= shot_threshold`, so
the FG%-vs-threshold response is scale-independent — but the **operating point is not**. Move
the window down 30 and every team sits 30 points lower, shoots better, and the neutral band
that used to sit *below* the equilibrium FG% is now *above* it. Every team-game takes the
"shooting well" negative delta and compounds downward.

**Measured instance (2026-08-12):** bands cut at `24/36` for init 95-105 on the old 0-200
scale, then carried through two window moves to `-30..170` / init 65-75 unchanged. Equilibrium
FG% rose 37.1% → 41.4%, above the 36 high cut. Result: **-28 drift per season instead of ~0.**
Re-cut to `26/40` → drift **-0.1**.

**Procedure:**

1. Compute the equilibrium FG% at the new init:
   `FG% = 51.25 - 0.14126 x init_midpoint` — **re-derive this fit if the engine or rosters have
   changed**, it is season-specific (see the corollary below).
2. Position the neutral band so its HIGH cut sits **just below** that equilibrium — roughly
   `equilibrium - 1.5pp` — so the negative branch carries enough mass to offset training's
   steady upward push (+56.4/season measured on the CPU reference plan).
3. Simulate before shipping. 26 weeks x 128 teams from the new init, using the **actual integer
   band ranges** (not continuous draws). Target: |drift| < ~2, sd 18-25, **zero rails**.
4. Update the CURRENT CALIBRATION block in `BackEnd/constants/eog_attr_bands.py` with the new
   numbers, and the band rows in `06_Gameplay_Systems/End_Of_Game_System.md`.

**Reference points for step 2:**

| init midpoint | equilibrium FG% | working band | verified drift |
|---|---|---|---|
| 100 (scale 0-200) | 37.1% | 24 / 36 | +5.6 |
| 70 (scale -30-170) | 41.4% | **26 / 40** | **-0.1** |
| 90 (scale -10-190) | 38.5% *(modeled)* | 22 / 37 | -0.05 modeled → **-30.5 ACTUAL** |
| 90 (scale -10-190) | **45.16% MEASURED** | **40 / 45** | **≈ -21 projected** |

**THE COROLLARY — what a future tuner gets wrong first:**

* **GAIN sets SPEED. BAND POSITION sets WHERE TEAMS SETTLE.**
* ⚠️ **The 2026-08-14 row is the cautionary one.** Its equilibrium was *modeled* at 38.5% and
  the real league shot **45.16%**; drift came in at **-30.5/season** against a modeled -0.05.
  Trust a measured league FG%, never a fitted one. And check BOTH cuts for live mass —
  `FG_PCT_MID = 22` sat at the **0.2nd percentile** and caught 8 team-games in 4,220.
* The 40/45 row is **deliberately not drift-neutral** (owner decision); 35/40 was the neutral
  pair and is the documented fallback.
* The neutral band must sit **BELOW** the equilibrium FG%. Centring it *on* the equilibrium
  makes training dominate and every team drifts up.
* The equilibrium is **SEASON-SPECIFIC**: per-season slopes measured -0.1125 / -0.0691 /
  -0.1413 with non-overlapping 95% CIs, and the LEVEL shifts 6.42pp between code states.
  **Re-derive before re-cutting and never reuse a previous season's fit.**
* `shot_threshold` is tuned to a **VARIANCE** target, not a mean one — near-neutral centre,
  spread that grows, few teams railing. The compounding loop is INTENDED; only its magnitude
  was ever the defect.

**Current calibration (2026-08-14):** the `-10..190` move initializes franchises at
`85..95`. Using the verification season's 3,330 measured FG% residuals and fitted
response (`FG% = 51.24726 - 0.14126 × shot_threshold`), 1,000 modeled seasons with
the actual integer EOG rolls and clamps selected `FG_PCT_MID=22` /
`FG_PCT_HIGH=37`: mean 90.0, drift **-0.05**, sd **20.5**, and zero rails across
128,000 team-seasons. Re-fit after a material engine or roster change.

**Superseded 2026-08-15 — now `FG_PCT_MID=40` / `FG_PCT_HIGH=45`.** The 2026-08-14 cut
went stale exactly as this doc warns: measured against the finished PROD season (4,220
team-games), league FG% came in at mean **45.16**, so `FG_PCT_HIGH=37` sat near the 18th
percentile and `FG_PCT_MID=22` near the 0.2nd — the penalty branch caught 8 team-games out
of 4,220 and was dead. Observed league mean landed at **59.5** against the modeled 90.

The 40/45 re-cut is an **owner decision and is deliberately not drift-neutral**: it
straddles the league mean, which is the centring case `eog_attr_bands.py` warns against.
Projected net **+35.9/season (upward)**, versus **35/40** which projected −5.0.

**Measured decomposition** (persisted records, not modelled): training **+57.2**/team-season, EOG **−87.7**, net **−30.5** — init 90.0 → 59.5, closing exactly. Training pushes shot_threshold *up* (worse) because `_SCRIMMAGE_BASELINE = 1` and `_apply_shot_threshold_training` scores one scrimmage point at `+0..+5`; two points jumps straight to `−3..−8`. No allocation holds still: +65/season or −143/season. **That discontinuity is what these bands are compensating for, and fixing it at the training end would be the more direct repair.** If the league
rails at the 190 ceiling, 35/40 is the fallback. See the band-mass table in
`BackEnd/constants/eog_attr_bands.py`.

**Note:** Existing saved teams keep their stored values until re-seeded or migrated. Moving the window does not retroactively change Mongo team docs. To preserve the same relative position after this `+20` window shift, existing stored `shot_threshold` values require a **+20 migration**; otherwise their absolute shot difficulty is unchanged while the new scale's center moves around them.

## How to experiment (your workflow)

**Yes — you can just tell an agent in chat and point them at this doc.** Example prompt:

> Change team shot_threshold scale to MIN **60** (MAX/MID derive automatically). Follow `_documentation_master/00_Operations/Shot_Threshold_Scale_Tuning.md`. Run parity tests. Do not change runtime modifiers unless I ask.

**What the agent should do:**

0. Read the "Re-cutting the EOG bands" section above — it is a REQUIRED step, not optional.
1. Edit **`MIN`** in `BackEnd/constants/shot_threshold_scale.py` (only `MIN` — `MAX`, `MID`, balancing, franchise init, tutorial, tournament seeds re-derive).
2. Mirror the same **`MIN`** in `FrontEnd/static/js/shared/teamShotThresholdScale.js`.
3. Run `pytest tests/test_shot_threshold_scale.py tests/test_mode_init_system.py -q`.
4. Update the **current scale** line at the top of this doc and the reference table in `Team_Attribute_System.md` (Shooting section) if values changed.
5. Re-cut the EOG `shot_threshold` bands per the procedure above and report the simulated drift.
6. Report back: new MIN/MAX/MID, franchise init range, new EOG band cuts + simulated drift, and
   whether existing Mongo teams need a **+N migration** (see below).

**What you do after:**

- **New franchise / fresh teams:** sim or play a few games; check FG% and pill UI.
- **Existing franchise save:** stored `shot_threshold` values do **not** move with the scale. If you shifted MIN by +40 last time, old teams at ~110 behave ~40 points easier than intended until you migrate (+40 on all persisted values) or start a new franchise.
- **FG% still off after moving the window?** Ask the agent to tune **runtime modifiers** (broken +100, zone deltas, 3PT bump) per the manual checklist below — not another scale move by default.

**Span rule:** delta between lower and upper is always **200**; MID is always **MIN + 100** (= MAX − 100).

## Wired consumers (current scale: −10–190, MID 90)

When **`MIN`** changes, these values re-derive from `BackEnd/constants/shot_threshold_scale.py` (except items in the manual checklist below).

| Area | Current value | Code / notes |
|------|---------------|--------------|
| **Team attribute clamp** (`TEAM_ATTR_RANGES`) | **−10 – 190** | Init, training, EOG clamp |
| **Franchise init** | **85 – 95** | `FRANCHISE_INIT_LO` / `FRANCHISE_INIT_HI` — **MID ± 5** since the 2026-08-11 leveling pass (was MID−20/MID−10) |
| **Single-game init** | **−10 – 190** | Full clamp range, uniform random |
| **Tournament seeds** | See table below | `TOURNAMENT_SEED_ST_RANGES` |
| **Score balancing** | Trailing **−30**, leading **170** | `MIN − 20` / `MAX − 20` |
| **Rim-runner corner FB** | **170 − fb_efficiency** | `FAST_BREAK_CORNER_THRESHOLD_BASE` (`MAX − 20`) |
| **Uncontested-3 make bar** | **190 − CH + round(dist × 2.0)** | `SHOT_THRESHOLD_MAX` in `shot_manager.resolve_shot` — always tracks MAX |
| **FTE tutorial** | User **−10**, computer **90** | `TUTORIAL_USER` (= MIN), `TUTORIAL_COMPUTER` (= MID) |
| **UI pills** | Center **90**, span **−10–190** | `teamShotThresholdScale.js` → FCC, training report, tournament, court, box score |

**Tournament seed shot_threshold ranges:**

| Seed | Range | Notes |
|------|-------|-------|
| 1 | −10 – 90 | Best shooters |
| 2 – 4 | −10 – 140 | |
| 5 – 7 | 40 – 190 | |
| 8 | 90 – 190 | Worst shooters |

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

## ⚠️ Moving the scale INVALIDATES the EOG shot_threshold band calibration

`eog_attr_bands.FG_PCT_MID/HIGH` and the `ST_FG_*` deltas are cut against a MEASURED
FG%-vs-shot_threshold response, and that response is season- and scale-specific. Lowering the
window raises league FG%, which pushes more team-games into the reward band and drives
`shot_threshold` further down — the loop compounds.

The band block in `BackEnd/constants/eog_attr_bands.py` is marked ⚠️ INTERIM for exactly this
reason. **After a scale move, re-derive the slope from a season run under the new scale and
re-cut** (`scripts/eog_band_tuner.py`); do not reuse the previous fit. The relevant history:
per-season slopes measured −0.1125 / −0.0691 / −0.1413 with non-overlapping CIs, and the LEVEL
shifted 6.42pp between code states.

## Docs to update when scale changes

- `Team_Attribute_System.md` — range + pill center
- `Attribute_Clamp_System.md` — clamp row
- `Constants_System.md` — `TEAM_ATTR_RANGES` row
- `Training_System.md` — shooting pill paragraph
- `fte_system.md` — tutorial forced values (if tutorial pins change)

## Related docs

- [Shot_System.md](../06_Gameplay_Systems/Shot_System.md) — resolution flow and threshold modifiers
- [Team_Attribute_System.md](./Team_Attribute_System.md) — init ranges and UI copy
