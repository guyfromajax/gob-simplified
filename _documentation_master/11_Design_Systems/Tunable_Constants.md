# Tunable Constants

Central registry of tunable game-logic constants — the knobs for balancing gameplay. Each entry lists the constant, its current value, and a one-line effect.

**Workflow:** edit values here first → agents implement in code and keep this file in sync. **Scope:** live game + franchise EOG + training. **Geometry** and **`USE_*` feature flags** are out of the main console for now. Inventory by turn type: **HCO → HCT → FCP → FB → OREB → DREB** (Sessions 1–6). Inline literals awaiting named constants are tracked in **Promotion Pass** below (status board); per-turn Inline Magic tables keep file/context detail.

## Promotion Pass

**Own section** — the queue for lifting inline magic into named constants. Per-turn “Inline Magic” tables below remain the detailed source (file + effect); this section is the **value + status board** for the pass.

### Rules

1. **Promote at current literal** — create the proposed name in code with the value listed here; do **not** retune in the same change.
2. **Then sync** — move the row into the appropriate named-dial table above/below, set Status → `done`, and drop (or mark done) the per-turn Inline Magic row.
3. **Retunes** happen after promotion: edit the named value in this file first, then implement.
4. Status: `pending` | `done` | `skip` (geometry / cosmetic / duplicate of an existing named dial).

### HCO

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `DESPERATION_BH_SHOT_FRAC` | `0.75` | volume | pending |
| `DESPERATION_CLOCK_MULT` | `4` | volume | pending |
| `DISRUPTION_SUBTLE_FRAC` | `0.50` | volume | pending |
| `DISRUPTION_FF_BASE` / `_AGGR_DELTA` | `0.20` / `±0.10` | TO / volume | pending |
| `DISRUPTION_NONE_BASE` / `_AGGR_DELTA` | `0.30` / `∓0.10` | volume | pending |
| `NEUTRAL_PASS_BASE` / `_OFF_AGGR_DELTA` / `_DEF_AGGR_DELTA` | `0.50` / `±0.20` / `∓0.20` | volume / intercept | pending |
| `NEUTRAL_PASS_CLAMP` | `(0.10, 0.90)` | volume | pending |
| `STRATEGY_EMPHASIS_POINTS_PER_LEVEL` | `10` | volume / FG% | pending |
| `SHOT_CLOCK_TIER_EARLY_MIN` / `_MID` / `_LATE` / `_VERY_LATE` | `23` / `15` / `6` / `1` | volume | pending |
| `ALTERING_TURN_ROLL_SIDES` | `randint(1,5) ≤ alterations` | volume | pending |
| `DEFENSE_PRESSURE_ROLL_SIDES` | `randint(0,4) ≤ aggression` | contest / volume | pending |
| `ALTERED_PERFORM_IQ_WEIGHT` / `_CH_WEIGHT` | `0.8` / `0.2` | volume | pending |
| `ALTERED_READ_FLAT_FALLBACK` | `110.0` | contest | pending |
| `DRIVE_DOUBLE_TEAM_SHOOT_PROB` | `0.25` | volume / drive | pending |
| `DRIVE_OPEN_RIM_SHOOT_PROB` | `1.0` | volume / drive | pending |
| `DRIVE_SINGLE_GUARD_SHOOT_PROB` | `0.75` | volume / drive | pending |
| `DRIVE_DOUBLE_TEAM_DEFENSE_BONUS` | `100` | FG% / contest | pending |
| `DRIVE_DISH_PREFER_INTERIOR_PROB` | `0.75` | volume | pending |
| `DRIVE_EFF_ROLL_RANGE` | `randint(1,3)` | drive | pending |
| `MOTION_DEFENSE_BONUS_SHOT_SCALE` | `0.2` | FG% | pending |
| `CONTEST_LOSS_SHOT_PENALTY` | `100` | FG% / contest | pending |
| `BLOCK_COMPOSITE_HEIGHT_W` / `_ID_W` / `_IQ_W` | `0.4` / `0.4` / `0.2` | contest / foul | pending |
| `BLOCK_COMPOSITE_ROLL` | `randint(1,6)` | contest / foul | pending |
| `AND_ONE_FINISH_THRESHOLD` | `250` | foul / FG% | pending |
| `AND_ONE_FINISH_ST_W` / `_SC_W` / `_HEIGHT_W` / `_IQ_W` | `0.4` / `0.3` / `0.2` / `0.1` | foul / FG% | pending |
| `PASSER_ASSIST_PS_W` / `_IQ_W` / `_ASSIST_SHARE` | `0.8` / `0.2` / `0.2` | FG% | pending |
| `DRIBBLE_AG_W` / `_IQ_W` / `_DRIBBLE_SHARE` | `0.8` / `0.2` / `0.2` | FG% | pending |
| `SECOND_DEFENDER_IMPACT_FRAC` | `0.35` | contest / FG% | pending |
| `DEFENSE_SCORE_TO_SHOT_SCALE` | `0.2` | FG% | pending |
| `ZONE_23_INSIDE_DELTA` / `_ATTACK` / `_OUTSIDE` | `+25` / `+10` / `−25` | FG% | pending |
| `ZONE_32_INSIDE_DELTA` / `_ATTACK` / `_OUTSIDE` | `−30` / `−30` / `+50` | FG% | pending |

### HCT / shared moment

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `HCT_DFOUL_FRONTCOURT_P` | `0.10` | foul | pending |
| `HCT_TRAPPER_PRESSURE_FRAC` | `0.5` | foul / steal / TO / contest | pending |
| `HCT_CHEM_GATE_DIVISOR` | `4` (`chem/4`) | foul / steal / TO / drive | pending |
| `HCT_STEAL_CREDIT_OD_W` / `_AG_W` / `_IQ_W` | `0.4` / `0.4` / `0.2` | steal | pending |
| `HCT_BH_SECURE_CH_W` / `_BH_W` / `_IQ_W` | `0.4` / `0.4` / `0.2` | steal | pending |
| `HCT_BH_HANDLE_BH_W` / `_CH_W` / `_IQ_W` | `0.4` / `0.3` / `0.3` | TO | pending |
| `BALL_HANDLING_BH_W` / `_AG_W` / `_IQ_W` / `_CH_W` | `0.5` / `0.2` / `0.2` / `0.1` | foul / steal / TO / drive | pending |
| `DEF_PRESSURE_OD_W` / `_AG_W` / `_IQ_W` / `_CH_W` | `0.3` / `0.3` / `0.2` / `0.2` | foul / steal / TO / drive | pending |
| `PLAYER_READ_IQ_W` / `_CH_W` | `0.8` / `0.2` | volume / drive / FG% | pending |
| `HCT_ABA_LOW_TIER_COIN` | `50/50` (`getrandbits(1)`) | volume / FG% | pending |
| `HCT_SHOT_TREE_SUBOPTIMAL_POOL` | `("shoot","drive","pass")` equal | volume / FG% / drive | pending |
| `HCT_PFC_DENY_INTERP` | `0.6` | intercept / contest | pending |

### FCP

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `FCP_ENGAGEMENT_MIN_SECONDS` | `0.4` | volume / TO | pending |
| `FCP_ZONE_DENY_FRAC` | `0.6` | intercept / contest | pending |
| `FCP_PASS_FLIGHT_MIN_SEC` | `0.3` | volume / intercept | pending |
| `FCP_STOPPER_HOLD_SEC` | `0.5` | volume / TO | pending |

### FB

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `FB_CHARGE_READ_MIN_X_HOME` / `_MAX_X_AWAY` | `64.0` / `37.0` | foul / drive | pending |
| `FB_STEAL_MEET_MIN_X_AHEAD` | `1.0` | drive | pending |
| `FB_STOP_PASS_SH_MIN` | `49` (`SH > 49`) | volume | pending |
| `FB_OUTLET_SCORE_PS_W` / `_ST_W` / `_IQ_W` | `0.6` / `0.2` / `0.2` | contest / drive | pending |
| `FB_CR_BH_FALLBACK_WEIGHTS` | `PG/SG/SF = 75/15/10` | volume | pending |
| `FB_CR_SHARP_STOP_READ_MULT` | `3` (`outlet_score × 3`) | drive / contest | pending |
| `FB_CR_OUTLET_CUTOFF_X_OFFSET` | `2` | drive | pending |
| `FB_DEFENDER_TARGET_X_OFFSET` | `2.0` | contest | pending |
| `RR_OUTLET_CONTEST_RANGE` | `10.0` | TO / volume | pending |
| `RR_OUTLET_OFF_PS_W` / `_ST_W` / `_IQ_W` | `0.5` / `0.3` / `0.2` | TO / volume | pending |
| `RR_OUTLET_DEF_IQ_W` / `_OD_W` / `_ST_W` | `0.5` / `0.3` / `0.2` | TO / volume | pending |
| `RR_OUTLET_OFF_SCORE_MULT` / `_FB_EFF_MULT` / `_FB_OPP_MULT` | `1.5` / `3` / `2` | TO / volume | pending |
| `RR_LANE_READ_BASE` / `_FB_EFF_COEF` | `200` / `5` | volume / intercept | pending |
| `RR_MISREAD_AGGRESSION_MIN` | `3` | volume / intercept | pending |
| `RR_OPEN_LANE_MAX_THREATS` / `_PASSIVE` | `1` / `0` | volume / intercept | pending |
| `RR_LANE_INT_OD_W` / `_AG_W` / `_IQ_W` | `0.6` / `0.2` / `0.2` | intercept / steal | pending |
| `RR_LANE_TIER_HI_BASE` / `_MID_BASE` | `250` / `200` | intercept / steal | pending |
| `RR_SHOT_THRESH_MULTI_DEF_ADD` / `_FIGHT_MULT` | `100` / `2` | FG% | pending |
| `TRIANGLE_DECISION_D8` | `randint(1,8)` tree | volume / FG% / drive | pending |
| `TRIANGLE_DRIVE_DECISION_D5` | `randint(1,5)` tree | volume / FG% / drive | pending |
| `RR_BURST_AG_W` / `_IQ_W` / `_CH_W` | `0.6` / `0.2` / `0.2` | contest / intercept | pending |
| `RR_BURST_DX_SUCCESS` / `_FAIL` | `20–25` / `9–14` | contest / intercept | pending |

### OREB / shared rebound

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `OREB_PUTBACK_PCT_AGGRESSIVE` / `_NORMAL` / `_PASSIVE` | `90` / `75` / `60` | volume | pending |
| `OREB_MIN_SHOT_CLOCK_FOR_ATTEMPT` | `2` | TO / possession | pending |
| `OTB_MAX_EUCLIDEAN` | `4` | foul | pending |
| `OTB_OFFENSE_THRESHOLD_BASE` | `90` | foul | pending |
| `OTB_DEFENSE_THRESHOLD_BASE` | `10` | foul | pending |
| `OTB_IQ_GATE_ROLL` | `≤ foul_player.IQ` on `1–100` | foul | pending |
| `OTB_FINAL_CALL_SIDES` | `50%` (`randint(1,2)`) | foul | pending |
| `REBOUND_ATTR_RB_W` / `_ST_W` / `_IQ_W` / `_CH_W` | `0.5` / `0.3` / `0.1` / `0.1` | oreb | pending |
| `REBOUND_SCORE_ROLL` | `randint(1,6)` | oreb | pending |
| `REBOUND_UPPER_HALF_DEFAULT` | `12` | oreb | pending |
| `REBOUND_LOWER_DISCOUNT_STRONG` / `_WEAK` | `0.7` / `0.95` | oreb | pending |
| `REBOUND_UPPER_COUNT_FOR_STRONG` | `2` | oreb | pending |
| `REBOUND_SHOOTER_PUTBACK_SCORE_PENALTY` | `0.8` | oreb | pending |
| `REBOUND_FALLBACK_START` / `_STEP` / `_MAX` | `20` / `5` / `150` | oreb | pending |
| `OFFENSE_GETBACK_CHANCES` | `{0:1; 1:.5/.5; 2:.25/.75; 3:.1/.8/.1; 4:0/.5/.5}` | oreb | pending |
| `PUTBACK_INSIDE_HARD_FOUL_BASE` / `_SOFT_FOUL_BASE` | `35` / `105` | foul | pending |
| `PUTBACK_PAINT_DEF_ID_W` / `_ST_W` / `_IQ_W` / `_CH_W` | `0.6` / `0.2` / `0.1` / `0.1` | contest / FG% / foul | pending |
| `BOUNCE_VAR_*` tiers | see OREB Inline Magic | oreb | pending |

### DREB

| Proposed name | Current value | Affects | Status |
|---|---|---|---|
| `DREB_TURN_TIME_ELAPSED_FLOOR` | `1` game-sec | possession | pending |
| `DREB_EMERGENCY_GETBACK_ROLL` | `randint(0,10) ≤ fb_opp` | contest / drive / possession | pending |
| `DREB_CR_RELEASE_IQ_READ` | `randint(1,100) < release.IQ` | contest / drive | pending |
| `DREB_CR_GETBACK_IQ_READ` | `randint(1,100) < getback.IQ` | contest / drive | pending |
| `DREB_CR_RELEASE_AG_X_MIN_HI` / `_MID` / `_LO` | `50` / `47` / `45` | contest / drive | pending |
| `DREB_CR_GETBACK_AG_X_MIN_HI` / `_MID` / `_LO` | `55` / `53` / `50` | contest / drive | pending |
| `DREB_HCO_OUTLET_RX_X_OFFSET` / `_Y_JITTER` | `randint(3,6)` / `randint(−6,6)` | possession | pending |
| `DREB_HCO_OUTLET_BOUNCE_REANCHOR_XY` | `±3` x / `±5` y | possession | pending |
| `FB_MISS_FRONTCOURT_X_SPLIT` | `50` (home ≥ / away ≤) | dreb | pending |

### Already named (do not re-promote)

| Name | Value | Note |
|---|---|---|
| `FB_CONTEST_MAX_X_TRAIL` | `3` | Already a named constant in `fast_break_constants.py`; consolidate duplicate defs only. |

## FLSS (Forced Last Second Shot)

| Constant | Value | Effect |
|---|---|---|
| `FLSS_DEEP_KEY_X_HOME` | 57 | Home x-band floor for penalty-zone FLSS (away mirrors); below → heave zone. |
| `FLSS_NORMAL_SHOT_MIN_X_HOME` | 64 | Home x minimum for normal-zone FLSS (full shot pipeline); away mirrors. |
| `FLSS_HEAVE_MAX_X_HOME` | 50 | Home x at/beyond which heave coach VO may include `duke-heave.mp3`; away mirrors. |
| `FLSS_HEAVE_MISS_RATTLE_MAX` | 5 | Heave miss margin ≤ this → random LITTLE/NORMAL/HEAVY rattle rim action. |
| `FLSS_HEAVE_MISS_RIM_BOUNCE_MAX` | 15 | Heave miss margin 6–15 → BACK_OF_RIM bounce-off-rim animation. |
| `FLSS_HEAVE_MISS_BACKBOARD_MAX` | 30 | Heave miss margin 16–30 → BANK_MISS off-backboard animation; above → AIRBALL (SFX only, no headline). |
| `FLSS_AIRBALL_LAND_X_OFFSET_MIN` | 2 | FLSS AIRBALL only: min x grid distance from attacking basket for short landing before OOB tween. |
| `FLSS_AIRBALL_LAND_X_OFFSET_MAX` | 5 | FLSS AIRBALL only: max x grid distance from attacking basket for short landing before OOB tween. |
| `FLSS_AIRBALL_LAND_Y_VARIANCE` | 5 | FLSS AIRBALL only: landing y = basket y ± this (OOB continuation uses same y). |

## HC Trap

| Constant | File | Value | Effect |
|---|---|---|---|
| `TRAP_MOMENT_RANGE` | dynamic_hct.py | `5` | Max grid distance a defender can be from the ball-handler to count toward an HC trap/pressure double-team. Tighter than general HCT `MOMENT_RANGE` (11) used for pass-guard / shot-tree “in range”. |

## HCO Step Logic

The universal HCO shoot decision evaluates candidates at each reached skeleton step. Outside
attempts must first pass a clock-tier nearest-defender separation gate; this applies to optimal
self-shots, optimal dish/catch-and-shoot candidates, and random-tier self-shots. Inside and attack
candidates are unaffected. At outside/attack locations, the outside candidate score is multiplied
by 0.55 before weighted selection; the downstream acceptance gate is 100% at every tier, preserving
shot timing and volume instead of rejecting selected outside shots. The random percentage is evaluated only after the random reader chooses
`shoot` from `shoot / hold / pass`, so its direct-shot probability per evaluation is one-third of
the configured value. Subtle-movement precedence may suppress the evaluation on reading turns.

| Constant | File | Value | Effect |
|---|---|---|---|
| `OUTSIDE_SHOT_MIN_GAP_BY_TIER` | motion_step_decision.py | `{early:11, mid:7, late:3, very_late:0, forced:0}` | Minimum distance in grid units from the candidate to the nearest defender for an outside shot to be eligible. Tiers: early 23–30s, mid 15–22s, late 6–14s, very late 1–5s, forced <1s. |
| `OUTSIDE_SHOT_SELECTION_MULTIPLIER` | motion_step_decision.py | `0.55` | Multiplies the outside score in the shared attack-vs-outside weighted pick. Lower values redirect more outside-location decisions into attack shots without suppressing the shot attempt. This applies at every tier, with most aggregate impact in early/mid HCO because those tiers contain most HCO attempts. Recalibrated from `0.75`. |
| `OUTSIDE_SHOT_ACCEPTANCE_PCT_BY_TIER` | motion_step_decision.py | `{early:100, mid:100, late:100, very_late:100, forced:100}` | Downstream acceptance dial for selected outside shots. All tiers currently preserve the selection; lowering a tier would reject shots and continue the HCO walk. |
| `RANDOM_TIER_SHOOT_PCT[early]` | motion_step_decision.py | `{slow:10, normal:20, fast:30}` | Random reader's conditional shoot percentage in the 23–30s tier, after choosing the `shoot` option. Effective direct-shot rates are 3.3% / 6.7% / 10.0% per evaluation. |
| `RANDOM_TIER_SHOOT_PCT[mid]` | motion_step_decision.py | `{slow:20, normal:35, fast:50}` | Conditional percentage in the 15–22s tier. Effective direct-shot rates are 6.7% / 11.7% / 16.7%. |
| `RANDOM_TIER_SHOOT_PCT[late]` | motion_step_decision.py | `{slow:95, normal:95, fast:95}` | Conditional percentage in the 6–14s tier. Effective direct-shot rate is 31.7% for every tempo. |
| `RANDOM_TIER_SHOOT_PCT[very_late]` | motion_step_decision.py | `{slow:95, normal:95, fast:95}` | Conditional percentage in the 1–5s tier. Effective direct-shot rate is 31.7% for every tempo. |
| `SM_PRECEDENCE_TEMPOS` | motion_step_decision.py | `early: all; mid: slow+normal; late: slow; very_late: none` | On an `offense_reads` turn, these tempos run subtle movement before evaluating a shot at that tier. |
| `OPTIMAL_BAR_STEEPNESS` | motion_step_decision.py | `2.0` | Multiplier in `optimal bar = shot clock × steepness × tempo multiplier`; higher values demand stronger looks or later shots. |
| `OPTIMAL_BAR_TEMPO_MULT` | motion_step_decision.py | `{slow:1.2, normal:1.0, fast:0.8}` | Slow raises the optimal-look bar; fast lowers it. |
| `SHOT_CLOCK_START` | motion_step_decision.py | `30` | Clamp ceiling for shot-clock-scaled optimal bar. |
| `SHOOT_READ_RIGHT` | motion_step_decision.py | `200` | Read tier above this → “right” (take optimal look / dish). |
| `SHOOT_READ_SAFE` | motion_step_decision.py | `125` | Read tier above this → “safe” (clock-cascade hold/pass); else “random”. |
| `SAFE_HOLD_CLOCK` | motion_step_decision.py | `20.0` | Safe tier: clock > this → hold (never shoot). |
| `SAFE_PASS_CLOCK` | motion_step_decision.py | `10.0` | Safe tier: (PASS, HOLD] → hold-or-pass only; ≤ PASS → 3-way shoot/hold/pass. |
| `MOTION_READ_THRESHOLD` | motion_step_decision.py | `110` | Shared beat/read bar: defender beaten if `(read_raw + def_eff)×d6 ≤ 110`; also alias for desperation ceiling; openness lag scale mirrors this. |
| `DESPERATION_OFFENSE_CEILING` | motion_step_decision.py | `= MOTION_READ_THRESHOLD` (`110`) | If offense read score < this, clock-desperation forced-shot path can fire. |
| `KICKOUT_MAX_DIST` | motion_step_decision.py | `10` | Max Euclidean grid for desperation kick-out receiver (25% branch). |
| `TEMPO_MOD` | motion_step_decision.py | `{slow:-25, normal:0, fast:25}` | Added to desperation roll vs `4 × shot_clock`. |
| `SUBTLE_FORCED_SHOT_PENALTY` | motion_step_decision.py | `50` | Subtracted from `shot_score` when subtle movement burns clock to expiry. |
| `READ_THRESHOLD` | motion_read_map.py | `15` | Mismatch score must clear this to flag hot-read / optimal quality path. |

## Shot Distance Threshold Adjustments

These use Euclidean distance from the classified release coordinate to the attacking basket.
Threshold reductions make the shot easier. The inside/two-point bonuses affect standard threshold
comparisons; the universal uncontested inside/attack helper retains its separate make roll.

| Constant | File | Value | Effect |
|---|---|---|---|
| `THREE_POINT_DISTANCE_THRESHOLD_MULTIPLIER` | shot_manager.py | `2.0` | Three-point threshold penalty is `round(distance × 2.0)`; also used by the bespoke undefended-outside make bar. |
| `INSIDE_SHOT_CLOSE_DISTANCE` / `INSIDE_SHOT_CLOSE_THRESHOLD_BONUS` | shot_manager.py | `≤12` / `-40` | Two-point shots at or within 12 grid units reduce the shot threshold by 40. |
| `INSIDE_SHOT_MID_DISTANCE` / `INSIDE_SHOT_MID_THRESHOLD_BONUS` | shot_manager.py | `>12–19 inclusive` / `-20` | Two-point shots beyond 12 through 19 grid units reduce the shot threshold by 20. Above 19 receives no inside-distance bonus. |

## Free Throw Resolution

These constants govern the second-chance roll attempted only after a primary FT miss. The final
threshold is `crowd base + (2 × MO) × randint(1,3)`, clamped to 0–100, and the second-chance
`randint(1,100)` must be strictly below it.

| Constant | File | Value | Effect |
|---|---|---|---|
| `FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE` | constants/__init__.py | `0.60` | Home shooters and away shooters at crowd factor 1 use a base 60% miss-to-make threshold. |
| Away FT crowd tiers | home_crowd.py | `factor 2–3: 0.50; factor 4–5: 0.40` | Reduces the miss-to-make base for away shooters in stronger crowd environments. |
| `MO_FT_SECOND_CHANCE_MULTIPLIER` | constants/momentum.py | `2` | Doubles the shooter's signed momentum before applying the random factor. |
| `MO_FT_SECOND_CHANCE_ROLL` | constants/momentum.py | `(1,3)` | Random multiplier applied to doubled MO for each primary miss. |

## Block System

Blocks use a funnel: contested inside/attack eligibility → one of three attempt triggers →
reconciliation. Reconciliation computes `diff = shot_score_pre_defense − defense_block_score`;
high positive diff creates a shooting foul, sufficiently negative diff creates a block, and the
middle band falls back to ordinary shot resolution. The two outcome thresholds are independent.

| Constant / variable | File | Value | Effect |
|---|---|---|---|
| `BLOCK_RECONCILIATION_BLOCK_THRESHOLD` | constants/__init__.py | `-50` | A reconciliation blocks when `diff < -50`. Raising toward zero creates more blocks; lowering creates fewer. Recalibrated from `-100` after the three-week sample averaged about 0.97 blocks per team-game. |
| `BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD` | constants/__init__.py | `150` | A reconciliation creates a shooting foul when `diff > 150`. Independent of the block threshold. |
| `BLOCK_Y_ROLL_MIN` / `BLOCK_Y_ROLL_MAX` | constants/__init__.py | `0 / 4` | First trigger rolls this inclusive range against defensive aggression; `roll <= aggression` reaches reconciliation. Default aggression 2 therefore passes 60%. |
| Defensive `aggression` | team strategy | `0–4` | First-trigger comparison value. Higher aggression sends more eligible shots into reconciliation. Slow-It-Down can temporarily force this to 0. |
| `BLOCK_FIGHT_RANGE_MIN` / `BLOCK_FIGHT_RANGE_MAX` | constants/__init__.py | `0 / 10` | Second trigger, attempted only after aggression misses: `roll <= defense fight`. |
| Defensive `fight` | team attribute | live team value | Second-trigger comparison value; higher fight produces more reconciliation attempts. |
| `BLOCK_PLAYER_ROLL_MIN` / `BLOCK_PLAYER_ROLL_MAX` | constants/__init__.py | `1 / 300` | Third trigger, after aggression and fight miss, rolls against `defender ID + defensive_efficiency × height_rating`. Lowering the maximum increases individual rim-protector attempts. |
| Height rating | shared.py | `≤72:0; 73–81:1–9; ≥82:10` | Feeds both the third attempt trigger and reconciliation. In reconciliation it becomes `height_rating × 10 + randint(-9,9)` and receives 40% weight. |
| Defender block composite | shot_manager.py | `height 40% + ID 40% + IQ 20%`, then `× randint(1,6)` | Determines `defense_block_score`; higher attributes or roll make negative reconciliation diff and blocks more likely. |
| Contest-result eligibility | shot_micro_movements constants | `neutral` or `defense_win`; boundaries `±150` | `offense_win` shots do not enter the block funnel. Changing contest boundaries changes the eligible population. |
| Shooter finish threshold | shot_manager.py | `250` | When reconciliation lands in the foul band, shooter finish score above 250 makes the basket for an and-one. Does not affect block volume. |
| `MO_BLOCK_DELTA` | constants/momentum.py | `1` | Actual block gives blocker +1 player momentum and blocked shooter −1. Does not affect block probability. |
| Block contact spot | shared.py | x `2–15` behind shooter; y `±6` | Controls block/rebound animation geography only, not outcome probability. |

`block_funnel_tracking` is diagnostic-only and reports eligible shots, reconciliation reached,
foul/fallback/block bands, actual blocks, and foul-owned block contacts in both end-of-game and
week-aggregate shot reports.

## Dynamic HCO Defense (Pass Interception)

The HCO pass-contest funnel runs on every HCO pass: **Gate 1** geometry (defender in the lane) → **Gate 2** attempt (aggression) → **Gate 3a** passer safety (clean pass?) → **Gate 3b** deflection threshold (`intercept_score > tier_mid` → DEFLECTED, else the pass completes) → **Gate 3c** deflection KIND (a `CH+IQ` vs d`PASS_DEFLECT_KIND_D` roll splits INTERCEPT vs BAT_OOB). HCO uses its own base/tier (below); the composite weights, d6 roll, and the split live in `pass_contest.py` and are **shared with HCT/FCP**. Feature flag: `GOB_DYNAMIC_HCO_DEFENSE` (falsy = off).

> **Model note (commit `8d86c6abd`):** the old *two-tier* band (HI = INTERCEPT, (MID, HI] = BAT_OOB) was replaced. There is now a **single deflection threshold** (`tier_mid`) plus a separate **KIND split** (Gate 3c). `TIER_HI` is **retired** (accepted for back-compat, unused) — tuning it does nothing. To move the **INTERCEPT/BAT_OOB ratio**, use `PASS_DEFLECT_KIND_D`; to move **how often** passes deflect at all, use `HCO_PASS_SAFETY_BASE` + `HCO_PASS_INTERCEPT_TIER_MID`.

Scores (both rolled once, `rand(1,6)`):
- `pass_score = ((PS·0.6 + CH·0.2 + IQ·0.2) + offensive_efficiency) × rand(1,6)` — offense (Gate 3a)
- `intercept_score = ((OD·0.6 + CH·0.2 + IQ·0.2) + defensive_efficiency) × rand(1,6)` — defender (Gate 3b)

`*_efficiency` = the team's `offensive_efficiency` / `defensive_efficiency` attribute (~−10..+10); it is added to the composite **and** subtracted from the bar/tiers, so a strong team is favored twice.

| Constant | File | Value | Effect |
|---|---|---|---|
| `INTERCEPT_ATTEMPT_PCT_BY_CALL` | phase_resolution.py | `{aggressive:80, normal:40, passive:0}` | **Gate 2** — % chance an in-lane defender actually *attempts* the pick, by `aggression_call`. Volume throttle before the contest. ↑ = more attempts feed Gate 3 = more picks. Passive never gambles. |
| `HCO_PASS_LANE_DIST_BY_AGGRESSION` | phase_resolution.py | `{passive:6.0, aggressive:5.0}` (normal = `randint(5,6)`/game) | **Gate 1** — perpendicular lane distance (grid) a defender must be within to count as "in the lane." ↑ = defenders contest from farther = more in-lane opportunities. Tighter than HCT/FCP (8.0). |
| `HCO_PASS_SAFETY_BASE` | phase_resolution.py | `175.0` | **Gate 3a** — clean-pass bar: passer is safe (no interception) if `pass_score > (BASE − offensive_efficiency)`. **↓ = passer safer = FEWER picks; ↑ = harder to complete = MORE picks.** (Shared HCT/FCP default: 200.) |
| `HCO_PASS_INTERCEPT_TIER_HI` | phase_resolution.py | `200.0` | **RETIRED (unused, `8d86c6abd`)** — was the old two-tier INTERCEPT threshold; kept for back-compat callers only. Changing it has **no effect**. Use `PASS_DEFLECT_KIND_D` for the INTERCEPT/BAT_OOB ratio. (Shared default: 250.) |
| `HCO_PASS_INTERCEPT_TIER_MID` | phase_resolution.py | `170.0` | **Gate 3b — the deflection threshold**: `intercept_score > (MID − defensive_efficiency)` → the pass is DEFLECTED (kind then decided by Gate 3c); else it completes (miss). **↓ = more deflections** (more picks + bat-OOBs combined). (Shared HCT/FCP default: 200.) |
| `PASS_DEFLECT_KIND_D` | pass_contest.py | `200` | **Gate 3c — INTERCEPT vs BAT_OOB split** (shared). On a deflection: `rand(1, D) < (CH + IQ)` → clean **INTERCEPT** (steal + TO); else **BAT_OOB** (knocked out, offense retains, no stats). This is the **ratio** dial, independent of deflection frequency. **↑ D = more BAT_OOB; ↓ D = more INTERCEPTs.** Good defenders (high CH+IQ) skew toward INTERCEPT. Sim baseline ≈ 46% BAT_OOB of deflections. |
| `PASS_INTERCEPT_OD_WEIGHT` / `_CH_WEIGHT` / `_IQ_WEIGHT` | pass_contest.py | `0.6 / 0.2 / 0.2` | Interceptor composite weights (defender OD / CH / IQ). Shared. |
| `PASS_SAFETY_PS_WEIGHT` / `_CH_WEIGHT` / `_IQ_WEIGHT` | pass_contest.py | `0.6 / 0.2 / 0.2` | Passer composite weights (PS / CH / IQ). Shared. |
| `PASS_INTERCEPT_ROLL_MIN` / `_MAX` | pass_contest.py | `1 / 6` | The `rand(min,max)` multiplier on both composites (3a and 3b). Wider band = more variance in who beats the bar. Shared. |
| `PASS_IQ_ANTICIPATION_MAX_SEC` | pass_contest.py | `0.15` | **Gate 1 (temporal)** — max reaction head-start (game-seconds, scaled by IQ/100) a defender gets in the ball's arrival-time race. ↑ = defenders reach more lanes in time. Shared. |
| `PASS_LANE_DIST` | pass_contest.py | `8.0` | HCT/FCP lane distance + the shared param default. HCO overrides it via `HCO_PASS_LANE_DIST_BY_AGGRESSION`. |

## HCO Micro Movements (Dynamic MM — S1 Openness)

The **openness primitive** (Dynamic_MM_Brief §7, Stage 1): a defender who loses his reactive read on a positional step **lags** toward his man (Part B) → his Euclidean gap to the man grows → the shot contest **scales down** by that gap (Part C). One signal (defender-to-man distance on the frozen grid), read by the shot contest + the dish/hot-read gate. Dynamic HCO activation remains gated by `GOB_DYNAMIC_HCO_DEFENSE` and is **MAN defense only** (zone openness = Stage 4 parity). OREB putbacks reuse the Part-C proximity curve independently of that feature flag: the nearest defender is assigned, scaled through 11 grid units, and has zero shot impact beyond 11. Tune HCO beat frequency with `scripts/s1_openness_monte_carlo.py`.

The beat roll (shared with the subtle-movement freeze): `(player_read_raw + defensive_efficiency) × rand(1,6)`; **beaten if ≤ `MOTION_READ_THRESHOLD`**. The |margin| below the bar drives how far the defender lags (owner-locked: harder beat → more open).

| Constant | File | Value | Effect |
|---|---|---|---|
| `OPENNESS_LAG_MAX` | animator.py | `0.8` | **Part B** — worst-beat lag: a fully-beaten defender tracks only `(1 − 0.8) = 20%` of the way toward his man (holds 80% of the opened gap). **↑ = beaten man more open** (bigger FG swing on beats). Primary openness dial. |
| `OPENNESS_LAG_MARGIN_SCALE` | animator.py | `110.0` | **Part B** — the \|read-miss margin\| at which lag saturates to `LAG_MAX` (= `MOTION_READ_THRESHOLD`). Lag = `LAG_MAX × min(1, \|margin\|/SCALE)`. **↓ = marginal misses lag harder** (openness saturates sooner). |
| `OPENNESS_ANCHOR_MOVE_EPS` | animator.py | `1.0` | **Part B** — the guarded man must travel more than this many grid for a beat to open space; a stationary man never opens (no lag). ↑ = only bigger cuts open space. |
| `PROXIMITY_CONTEST_NEAR_DIST` | shot_manager.py | `3.0` | **Part C, HCO + OREB** — defender ≤ this grid from the shot spot = **full contest** (factor 1.0). Owner spec: ≤3 = major defensive advantage. |
| `PROXIMITY_CONTEST_OPEN_DIST` | shot_manager.py | `9.0` | **Part C, HCO + OREB** — defender ≥ this grid = the wide-open floor; contest ramps linearly down from NEAR to here. **↓ = shots open up at closer range = more openness** (secondary dial; MC-sensitive). |
| `PROXIMITY_CONTEST_OPEN_FLOOR` | shot_manager.py | `0.15` | **Part C, HCO + OREB** — residual defensive weight from `OPEN_DIST` out to the contest radius (9–11 grid = "not open, low impact"). ↑ = far defenders still bother the shot. Beyond `CONTEST_EUCLIDEAN_RADIUS` (11) → 0 (uncontested). |

> **MC finding (2026-07-13, model):** S1's FG% impact is **bottlenecked by beat-frequency (~14% of possessions), not by `LAG_MAX`** — sweeping `LAG_MAX` 0.5→0.95 moves FG only +0.6→+1.5, and `OPEN_DIST` 11→7 moves it +0.9→+1.9. To make openness matter more, raise how often defenders get beaten (the `MOTION_READ_THRESHOLD` bar / how often men move), not just how far they lag. Confirm beat-frequency + the live baseline in-app before committing values.

## HCO 3-Tier Drives (Dynamic MM — S2)

The **drive contest** (Dynamic_MM_Brief §S2): a drive to the rim resolves through the shared `_resolve_moment` (FB/HCT model) in ONE roll → a **tier** (A blow-by / B contested-neutral pull-up / C clean stop) + optional **contact** (D_FOUL / O_FOUL charge / DEAD BALL turnover). On a Tier-A blow-by, a **help defender** may rotate to cut off the drive (S2c) — the same contest vs the cutoff defender, demoting the blow-by. All gated by `GOB_DYNAMIC_HCO_DEFENSE`. Tune with `scripts/s2_drive_monte_carlo.py` (reuses the real contest + cutoff functions).

| Constant | File | Value | Effect |
|---|---|---|---|
| `DRIVE_NEUTRAL_BAND` | attack_drive_clearance.py | `100.0` | **Primary tier dial** — the win/lose gate half-width (o_score/d_score pts) passed to `_resolve_moment(neutral_band=…)`. The shared chem+eff default (~few pts) makes B vanish (near-binary A-vs-C); **~100 gives B a plurality at even matchups** (MC: A/B/C ≈ 21/50/21%). ↑ squeezes A+C into B (more pull-ups, fewer clean blow-bys *and* clean stops); ↓ → binary. |
| `DRIVE_NEUTRAL_STOP_FRACTION` | attack_drive_clearance.py | `0.5` | Tier-B stop point — a contested-neutral drive pulls up ~midway to the rim (S2d truncates the path here). Cosmetic (shot difficulty follows from the reclassified pull-up distance), not an outcome-rate knob. |
| `DRIVE_STOPPED_MAX_GRID` | attack_drive_clearance.py | `2.0` | Tier-C clean stop: BH advances at most this many grid before the wall. |
| `ATTACK_DRIVE_INSIDE_RADIUS` | attack_drive_clearance.py | `15.0` | Drive stop coords ≤ this of basket → classified inside (else attack/outside by geo). |
| `ATTACK_DRIVE_CONTEST_RADIUS` | attack_drive_clearance.py | `= CONTEST_EUCLIDEAN_RADIUS` (`11`) | Rim-guardian radius for dish/shoot pressure after the drive. |
| `PERIMETER_OFFENSE_READ_BASE` | attack_drive_clearance.py | `150` | Perimeter offense read threshold base (− chem − off_eff). Used on flag-off / legacy drive paths. |
| `PERIMETER_DEFENSE_READ_BASE` | attack_drive_clearance.py | `125` | Perimeter defense read threshold base (legacy/flag-off path). |
| `HELP_READ_BASE` | attack_drive_clearance.py | `100` | Help-side read threshold base (legacy/flag-off path). |
| `READ_THRESHOLD_FLOOR` | attack_drive_clearance.py | `-3` | Floor clamp on perimeter/help thresholds. |
| `DRIVE_CONTEST_DEF_BONUS_MULTIPLIER` | attack_drive_clearance.py | `2` | Legacy drive score path: `def_bonus = 2×(chem+eff)`. |
| `HCO_CUTOFF_PATH_CORRIDOR` | attack_drive_clearance.py | `11.0` | **S2c** — a help defender must be within this perpendicular grid of the drive line to attempt a cutoff. ↑ = wider net = more cutoffs. MC note: **rarely the binding constraint** (help defenders that matter sit close to the path); aggression dominates. |
| `HCO_CUTOFF_DEFENDER_TIME_SLACK` | attack_drive_clearance.py | `1.0` | **S2c** — arrival-time credit in the race (>1 = the defender gets extra time budget → more cutoffs). `1.0` = a clean blow-by outruns late help. |
| `HCO_CUTOFF_STOP_ATTEMPT_PROB` | attack_drive_clearance.py | `{passive:0, normal:.5, aggressive:1}` | **S2c primary dial** — per-defender probability of even attempting the rotation, by defensive aggression. MC: blow-by demotion ≈ 0% / 60% / 82% across the three — **aggression, not corridor, is the cutoff lever**. |
| `HCO_DRIVE_SFX_FIRE_PROB` | skeleton_step_emitter.py | `0.5` | Cosmetic — chance a drive-start VO cue fires on an attack shot (seeded coin, separate salt from the braddock/sammy pick). ↓ = quieter/rarer drive cues. |

> **MC finding (2026-07-14, model — `scripts/s2_drive_monte_carlo.py`):** at the shipped `DRIVE_NEUTRAL_BAND=100`, even matchups land **A/B/C ≈ 21/50/21%** with ~8% contact; matchup lean shifts A↔C (offense-favored → 33/47/11, defense-favored → 11/47/34) while B stays broad by design. S2c blow-by demotion is driven by **aggression** (~60% normal / 82% aggressive), not corridor. Absolute rates depend on the mock attribute spread + model layout — trust the sweep deltas, and confirm the tier mix + drive FG% against the live baseline before committing.

## HCO Altered Actions + Posture Placement (Dynamic MM — S3)

Man defense only (zone = S4). Spec of record: `Dynamic_HCO_System.md` § Altered Actions. Placement is `shared_defense.py` (`_apply_defender_posture`); altered actions are `phase_resolution.py`.

**Posture-driven defender placement** (aggression retired for the HCO path). On-ball = sit N grid off the BH toward the rim; off-ball tight = deny (ball-side), normal/loose = help (`man + sag·(ball−man) + shade·(basket−man)`, per-dim anchored by the man's basket-offset).

| Constant | File | Value | Effect |
|---|---|---|---|
| `ONBALL_POSTURE_DIST` | shared_defense.py | `{tight:2.5, normal:3.5, loose:4.5}` | on-ball cushion (grid) toward the rim, by posture. ↑ = looser on-ball D. |
| `HELP_SAG` | shared_defense.py | `{normal:0.30, loose:0.55}` | off-ball: how far the defender sits from his man **toward the ball** (help degree). ↑ = deeper help. |
| `HELP_SAG_JITTER` | shared_defense.py | `0.10` | ±0–10% human randomization on the sag (resolved once + frozen → UESS-safe). |
| `HELP_BASKET_SHADE` | shared_defense.py | `0.20` | off-ball shade toward the basket, as a fraction of the man→basket distance. |
| `HELP_ANCHOR_FLOOR` | shared_defense.py | `0.30` | min follow in the man's **basket-aligned** axis ("comes off it some", never locks). |
| `POSTURE_DENY_DISTANCE` | shared_defense.py | `2.0` | tight/deny: grid off the man on the ball side (in the passing lane). |

**Altered-action trigger + selection** (per non-BH player, each of the BH's SM steps, on an altering turn):

| Constant / rule | Value | Effect |
|---|---|---|
| altering-turn gate | `alterations × 20%` (`randint(1,5) ≤ setting`) | 0→0% (run the set) … 4→80% freelance turns. The strategic lever. *(Inline — proposed `ALTERING_TURN_ROLL_SIDES` below.)* |
| perform roll | `randint(1,100) < 0.8·IQ + 0.2·CH + off_eff` | smart players attempt altered actions more often; else stationary. *(Inline — proposed `ALTERED_PERFORM_*` weights below.)* |
| selection | random by location | inside → {post up, flash}; outside → {backdoor, jab step}. |

**Dynamic defender good-read threshold** (the two non-inside actions; `d` = defender's frozen-grid distance to his man — reflects posture). Replaces the flat 110. Defender read = `(0.8·IQ + 0.2·CH + def_eff) × d6` vs the threshold; good ≥ threshold → cover, poor → the action springs.

| Constant | File | Value | Effect |
|---|---|---|---|
| `BACKDOOR_READ_BASE` | phase_resolution.py | `150.0` | backdoor threshold = `BASE − COEF·d` → **close/deny defender = harder read → backdoor opens** (backdoors beat deny). |
| `JAB_READ_BASE` | phase_resolution.py | `100.0` | jab threshold = `BASE + COEF·d` → **loose defender = harder read → bites → pop open** (jabs beat loose). |
| `ALTERED_READ_PROX_COEF` | phase_resolution.py | `8.0` | per-grid distance swing. At `8` the threshold moves ~24 pts across 2–5 grid (~0.4 of a d6 pip) — a clearly noticeable distance effect. |
| `ALTERED_ZONE_READ_THRESHOLD` | phase_resolution.py | `110.0` | Zone altered-action flat read bar (adjust vs hold). |
| `BACKDOOR_TRIGGER_BAR` | phase_resolution.py | `4.0` | Min denial (grid) before a backdoor is eligible. |
| `BACKDOOR_LANDING_OPEN_RADIUS` | phase_resolution.py | `8.0` | Defender within this of rim → help protects → no backdoor. |
| `BACKDOOR_OPENNESS_MIN` | phase_resolution.py | `3.0` | Cushion below which backdoor quality lift = 0. |
| `BACKDOOR_OPENNESS_OPEN` | phase_resolution.py | `8.0` | Cushion at/above which backdoor lift saturates. |
| `BACKDOOR_QUALITY_LIFT_MAX` | phase_resolution.py | `30.0` | Max `should_shoot` quality lift from an open backdoor. |
| `STEP_IN_OPENNESS_MIN` | phase_resolution.py | `5.0` | Cushion below which step-in quality lift = 0. |
| `STEP_IN_OPENNESS_OPEN` | phase_resolution.py | `10.0` | Cushion at/above which step-in lift saturates. |
| `STEP_IN_QUALITY_LIFT_MAX` | phase_resolution.py | `20.0` | Max `should_shoot` quality lift from step-in openness. |
| `JAB_STEP_MIN_GRID` / `JAB_STEP_MAX_GRID` | phase_resolution.py | `4.0` / `5.0` | Beaten jab defender “bite” distance (opens jabber). |
| `FLASH_GREAT_READ` / `FLASH_GOOD_READ` | phase_resolution.py | `200.0` / `110.0` | Flash defender: great→fronts, good→behind, else open. |
| `FLASH_FRONT_GRID` | phase_resolution.py | `1.5` | Fronting defender steps this far ball-side. |
| `POST_UP_ADVANTAGE_LIFT` | phase_resolution.py | `20.0` | Poor inside-D → post-up openness bonus to shoot quality. |

## HCO Moments & Dead Ball

On-ball moments reuse HCT `_resolve_moment` with an HCO `event_scalar`. Dead-ball / freelance-vs-trap reads sit on the dynamic HCO walk.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `HCO_MOMENT_SCALAR` | phase_resolution.py | `0.5` | foul / steal / TO | Scales HCT moment `p_event`/`p_dfoul` for man HCO. |
| `HCO_ZONE_MOMENT_SCALAR` | phase_resolution.py | `0.5` | foul / steal / TO | Same for zone HCO moments. |
| `MOMENT_ENGAGEMENT_PCT_BY_AGGRESSION` | phase_resolution.py | `{0:5, 1:20, 2:35, 3:50, 4:75}` | foul / steal / TO | % of possessions that engage any on-ball moment contest. |
| `HCO_OPEN_LANE_BONUS` | phase_resolution.py | `15.0` | TO / volume | Per open teammate lane → offense score in freelance-vs-dead-ball read. |
| `HCO_DENY_PRESSURE_BASE` | phase_resolution.py | `20.0` | TO | Per denied lane → defense score in same read. |
| `HCO_DEAD_BALL_TURNOVER_PCT` | phase_resolution.py | `50` | TO / volume | Fully denied BH: % held-ball/5-sec TO vs desperation shot. |
| `HCO_DEAD_BALL_FORCED_SHOT_PENALTY` | phase_resolution.py | `50.0` | FG% | Shot-score penalty on that desperation shot. |

## HCO Freelance

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `FREELANCE_RELOCATE_RADIUS` | motion_freelance.py | `9.0` | volume | Freelance relocate search radius (grid). |
| `UNIQUE_LOCATION_THRESHOLD` | motion_freelance.py | `15` | other | `off_eff + chem > 15` → unique relocate targets. |
| `FREELANCE_SUBTLE_PROB` | motion_freelance.py | `0.5` | volume | Else relocate. |
| `FREELANCE_MAX_CYCLES` | motion_freelance.py | `6` | volume | Cap; last cycle forces shot. |
| `FREELANCE_PASS_PROB` | motion_freelance.py | `0.80` | volume / intercept | When BH doesn’t shoot: pass vs hold. |
| `FREELANCE_PASS_RADIUS` | motion_freelance.py | `20.0` | volume / intercept | Max pass distance in freelance. |

## HCO Shot Pipeline (shared FG% dials)

Global shot/foul/contest dials that dominate HCO makes and volume. Listed here so FG% tuning starts from one place; values live in shared modules.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `CONTEST_EUCLIDEAN_RADIUS` | constants/__init__.py | `11` | contest / FG% | Beyond this → uncontested / zero proximity weight. |
| `CONTEST_OFFENSE_WIN_THRESHOLD` | shot_micro_movements_constants.py | `150` | contest / foul | Contest margin ≥ this → offense_win (skips block funnel). |
| `CONTEST_DEFENSE_WIN_THRESHOLD` | shot_micro_movements_constants.py | `-150` | contest / foul | Contest margin ≤ this → defense_win; else neutral. |
| `UNCONTESTED_INSIDE_ATTACK_MAX_DIST` | uncontested_shot.py | `11.0` | FG% | Geo gate for universal uncontested inside/attack make helper. |
| `UNCONTESTED_MAKE_THRESHOLD_BASE` | uncontested_shot.py | `99.0` | FG% | Base make bar for that helper. |
| `AGGRESSION_FOUL_MULTIPLIER` | constants/__init__.py | `{0:0.8 … 4:1.2}` | foul | Scales shooting-foul chance by aggression slider. |
| `HARD_SHOOTING_FOUL_THRESHOLD` / `SOFT_SHOOTING_FOUL_THRESHOLD` | constants/__init__.py | `50` / `110` | foul | Defense-score bands for hard/soft shooting foul rolls. |
| `HARD_PROB` / `SOFT_PROB` | constants/__init__.py | `0.7` / `0.16` | foul | Probabilities inside those bands. |
| `THREE_POINTER_FOUL_MISS_CHANCE` / `TWO_POINTER_FOUL_MISS_CHANCE` | constants/__init__.py | `0.4` / `0.2` | foul / FG% | Chance shooting foul forces a miss. |
| `PLAYCALL_ATTRIBUTE_WEIGHTS` | constants/__init__.py | (see file) | FG% | Shot-score attribute weights by playcall (Base/Attack/Outside/…). |
| `THREE_POINT_PROBABILITY` | constants/__init__.py | `{Outside:0.8, Base:0.4, Freelance:0.2}` | volume / FG% | Chance an outside look is taken as a 3. |
| `DUNK_MARGIN_THRESHOLD` (+ by aggression) | shot_micro_movements_constants.py | `100` / map | FG% / volume | Dunk vs non-dunk family gate. |
| `CHARGE_THRESHOLD` / `BLOCKING_FOUL_THRESHOLD` | constants/__init__.py | `-240` / `220` | foul / drive | Drive reconciliation charge vs blocking. |
| `MO_SHOT_ROLL_BASE` / `_POSITIVE` / `_NEGATIVE` | momentum.py | `(1,6)` / `(2,6)` / `(1,5)` | FG% | Momentum-modified shot d6 ranges. |
| `MO_SHOT_IMPACT_PCT_PER_LEVEL` | momentum.py | `20` | FG% | P(modified roll) = \|MO\| × 20% (100% at \|MO\|=5). |

## HCO Inline Magic (proposed names — document only)

Literals awaiting promotion. **Status board + values:** [Promotion Pass](#promotion-pass). This table keeps file/context detail.
| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `DESPERATION_BH_SHOT_FRAC` | motion_step_decision.py `_forced_action` | `0.75` | volume | Forced clock: 75% BH shoots / 25% kick-out. |
| `DESPERATION_CLOCK_MULT` | motion_step_decision.py desperation pre-check | `4` | volume | Forced if `roll + TEMPO_MOD > 4 × shot_clock`. |
| `DISRUPTION_SUBTLE_FRAC` | motion_step_decision.py `_disruption_branch` | `0.50` (residual) | volume | Defense-won: base subtle share. |
| `DISRUPTION_FF_BASE` / `_AGGR_DELTA` | motion_step_decision.py `_disruption_branch` | `0.20` / `±0.10` | TO / volume | Freelance-forced share by def aggression. |
| `DISRUPTION_NONE_BASE` / `_AGGR_DELTA` | motion_step_decision.py `_disruption_branch` | `0.30` / `∓0.10` | volume | “None/advance” share by def aggression. |
| `NEUTRAL_PASS_BASE` / `_OFF_AGGR_DELTA` / `_DEF_AGGR_DELTA` | motion_step_decision.py `_neutral_branch` | `0.50` / `±0.20` / `∓0.20` | volume / intercept | Neutral branch pass vs subtle. |
| `NEUTRAL_PASS_CLAMP` | motion_step_decision.py `_neutral_branch` | `(0.10, 0.90)` | volume | Clamp on that pass %. |
| `STRATEGY_EMPHASIS_POINTS_PER_LEVEL` | motion_step_decision.py `_weighted_attack_or_outside` | `10` | volume / FG% | `attack`/`outside` setting 0–4 adds `×10` to weighted shot-type pick. |
| `SHOT_CLOCK_TIER_EARLY_MIN` / `_MID` / `_LATE` / `_VERY_LATE` | motion_step_decision.py `_shot_clock_tier` | `23` / `15` / `6` / `1` | volume | Clock-tier boundaries for random % / SM precedence / outside gap. Described in prose; not extractable dials yet. |
| `ALTERING_TURN_ROLL_SIDES` | phase_resolution.py altering gate | `randint(1,5) ≤ alterations` | volume | Strategic lever (also noted in Altered Actions prose). |
| `DEFENSE_PRESSURE_ROLL_SIDES` | phase_resolution.py | `randint(0,4) ≤ aggression` | contest / volume | Gates disruption/subtle matrix. |
| `ALTERED_PERFORM_IQ_WEIGHT` / `_CH_WEIGHT` | phase_resolution.py `_hco_select_altered_action` | `0.8` / `0.2` | volume | Perform altered action if `rand(1,100) < 0.8·IQ+0.2·CH+off_eff`. |
| `ALTERED_READ_FLAT_FALLBACK` | phase_resolution.py altered read | `110.0` | contest | Non-backdoor/jab altered read fallback. |
| `DRIVE_DOUBLE_TEAM_SHOOT_PROB` | attack_drive_clearance.py dish/shoot | `0.25` | volume / drive | Double-team: P(driver shoots) on flag-off path. |
| `DRIVE_OPEN_RIM_SHOOT_PROB` | attack_drive_clearance.py dish/shoot | `1.0` | volume / drive | 0 guardians → always shoot. |
| `DRIVE_SINGLE_GUARD_SHOOT_PROB` | attack_drive_clearance.py dish/shoot | `0.75` | volume / drive | Single guardian shoot %. |
| `DRIVE_DOUBLE_TEAM_DEFENSE_BONUS` | attack_drive_clearance.py | `100` | FG% / contest | Added defense bonus when double-teamed & driver shoots. |
| `DRIVE_DISH_PREFER_INTERIOR_PROB` | attack_drive_clearance.py | `0.75` | volume | Prefer interior dish target (legacy dish path). |
| `DRIVE_EFF_ROLL_RANGE` | attack_drive_clearance.py legacy drive score | `randint(1,3)` | drive | Legacy drive score team-eff multiplier. |
| `MOTION_DEFENSE_BONUS_SHOT_SCALE` | shot_manager.py | `0.2` | FG% | `shot_score -= motion_defense_bonus × 0.2`. |
| `CONTEST_LOSS_SHOT_PENALTY` | shot_manager.py | `100` | FG% / contest | Flat subtract on contest-loss path (context-gated). |
| `BLOCK_COMPOSITE_HEIGHT_W` / `_ID_W` / `_IQ_W` | shot_manager.py block recon | `0.4` / `0.4` / `0.2` | contest / foul | Block reconciliation defender composite. |
| `BLOCK_COMPOSITE_ROLL` | shot_manager.py | `randint(1,6)` | contest / foul | Multiplier on that composite. |
| `AND_ONE_FINISH_THRESHOLD` | shot_manager.py | `250` | foul / FG% | Finish score > 250 → and-one make. *(Named in Block prose only.)* |
| `AND_ONE_FINISH_ST_W` / `_SC_W` / `_HEIGHT_W` / `_IQ_W` | shot_manager.py | `0.4` / `0.3` / `0.2` / `0.1` | foul / FG% | And-one finish composite weights. |
| `PASSER_ASSIST_PS_W` / `_IQ_W` / `_ASSIST_SHARE` | shot_manager.py | `0.8` / `0.2` / `0.2` | FG% | Passer contribution into shot score. |
| `DRIBBLE_AG_W` / `_IQ_W` / `_DRIBBLE_SHARE` | shot_manager.py | `0.8` / `0.2` / `0.2` | FG% | Attack/dribble contribution into shot score. |
| `SECOND_DEFENDER_IMPACT_FRAC` | shot_manager.py | `0.35` | contest / FG% | Secondary defender score scaled into contest. |
| `DEFENSE_SCORE_TO_SHOT_SCALE` | shot_manager.py legacy path | `0.2` | FG% | `shot_score -= defense_score × 0.2`. |
| `ZONE_23_INSIDE_DELTA` / `_ATTACK` / `_OUTSIDE` | shot_manager.py `_hco_zone_shot_threshold_delta` | `+25` / `+10` / `−25` | FG% | 2-3 zone shot-threshold deltas. |
| `ZONE_32_INSIDE_DELTA` / `_ATTACK` / `_OUTSIDE` | shot_manager.py `_hco_zone_shot_threshold_delta` | `−30` / `−30` / `+50` | FG% | 3-2 zone shot-threshold deltas. |

### Unsure / needs judgment (HCO inventory)

- **Perimeter read bases / `DRIVE_CONTEST_DEF_BONUS_MULTIPLIER`:** still on flag-off / legacy drive paths; three-tier path uses `_resolve_moment`. Confirm production default before heavy retunes.
- **`PLAYCALL_ATTRIBUTE_WEIGHTS` / `MO_SHOT_*`:** global; listed under HCO Shot Pipeline for FG% priority, not HCO-exclusive.
- **Clock-tier boundaries (23/15/6/1):** proposed as named dials above; still hardcoded in `_shot_clock_tier`.
- **`HCT_D8_*`:** shared contact model — documented under **HCT Moment Contact (D8)** below (HCO drives/moments inherit via `event_scalar` / `neutral_band`).

## HCT Moment Contact (D8)

Shared `_resolve_moment` contact model in `dynamic_hct.py`. **HCT/FCP** call it at full strength (`event_scalar` default / `HCT_D8_GLOBAL_SCALAR`). **HCO** moments/drives inherit the same dials but scale fire rates with `HCO_MOMENT_SCALAR` / `HCO_ZONE_MOMENT_SCALAR` and often override the neutral band with `DRIVE_NEUTRAL_BAND`.

Default HCT/FB neutral half-width is **inline** `chem/4 + pt_eff/pt_opp` (near-binary A/C) — see proposed `HCT_CHEM_GATE_DIVISOR` under HCT Inline Magic.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `HCT_D8_DB_W0` | dynamic_hct.py | `50.0` | TO | Even-matchup weight for **DEAD BALL** among D-win events. |
| `HCT_D8_STEAL_W0` | dynamic_hct.py | `30.0` | steal | Even-matchup weight for **STEAL** among D-win events. |
| `HCT_D8_OFOUL_W0` | dynamic_hct.py | `20.0` | foul | Even-matchup weight for **O_FOUL** (charge) among D-win events. |
| `HCT_D8_AGG_MULT` | dynamic_hct.py | `{passive:0.7, normal:1.0, aggressive:1.3}` | foul / steal / TO | Scales D-win `p_event`, steal factor, and offense-win `p_dfoul`. |
| `HCT_D8_GLOBAL_SCALAR` | dynamic_hct.py | `1.0` | foul / steal / TO | Master multiplier on per-moment event fire + D_FOUL (HCT/FCP typically `event_scalar=1.0`). |
| `HCT_D8_DEF_WIN_BASE` | dynamic_hct.py | `0.25` | foul / steal / TO | Base P(any D-win event) at a full decisive D-win before margin/agg/fight. |
| `HCT_D8_P_EVENT_MAX` | dynamic_hct.py | `0.60` | foul / steal / TO | Cap on per-moment D-win event probability. |
| `HCT_D8_M_REF` | dynamic_hct.py | `25.0` | foul / steal / TO / drive | Margin that saturates “decisive” win; also clean-stop path fraction when `clean_stop=True` (HCO). |
| `HCT_D8_REF` | dynamic_hct.py | `50.0` | foul / steal / TO | League-average attribute center for steal/DB/O_FOUL/AG-gap factors. |
| `HCT_D8_F_MIN` / `HCT_D8_F_MAX` | dynamic_hct.py | `0.3` / `2.5` | foul / steal / TO | Clamp on attribute multipliers before weighting outcomes. |
| `HCT_D8_S_SENS` | dynamic_hct.py | `1.2` | steal | Steal-weight sensitivity to (def steal composite − BH secure). |
| `HCT_D8_DB_SENS` | dynamic_hct.py | `1.0` | TO | Dead-ball weight sensitivity to weak BH handle vs `REF`. |
| `HCT_D8_O_SENS_IQ` | dynamic_hct.py | `0.8` | foul | Charge (O_FOUL) sensitivity to (credited def IQ − BH IQ). |
| `HCT_D8_O_SENS_DISC` | dynamic_hct.py | `0.5` | foul | Charge sensitivity to team `discipline`. |
| `HCT_D8_DISC_SCALE` | dynamic_hct.py | `20.0` | foul | Normalizer for discipline in O_FOUL factor. |
| `HCT_D8_W_PTEFF` | dynamic_hct.py | `0.04` | steal | Def `pt_efficiency` → steal factor. |
| `HCT_D8_W_PTOPP` | dynamic_hct.py | `0.04` | TO | Off `pt_opp_modifier` → resist self-TO (dead ball). |
| `HCT_D8_W_FIGHT` | dynamic_hct.py | `0.04` | foul / steal / TO | Offense `fight` → fewer D-win events. |
| `HCT_D8_DFOUL_BASE` | dynamic_hct.py | `0.25` | foul | Base P(D_FOUL / reach) on a decisive offense blow-by. |
| `HCT_D8_W_DISC_REACH` | dynamic_hct.py | `0.04` | foul | Team discipline → fewer reach fouls. |
| `HCT_D8_W_AG_BEATEN` | dynamic_hct.py | `0.6` | foul | Defender AG deficit vs BH → more reach fouls. |
| `HCT_DFOUL_PRIMARY_P` | dynamic_hct.py | `0.60` | foul | Credited fouler is on-ball defender (true reach-in). |
| `HCT_DFOUL_BACKCOURT_P` | dynamic_hct.py | `0.30` | foul | Credited fouler is backcourt help / trapper; residual **0.10** → frontcourt (proposed `HCT_DFOUL_FRONTCOURT_P`). |

## HCT Reads, Loop & Shot Tree

Detect→act loop + ABA (after-broken-attack) leaf selection in `dynamic_hct.py`.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `MOMENT_RANGE` | dynamic_hct.py | `11` | intercept / volume / drive | General in-range radius (pass interceptor exclusion, ABA open-floor drive, etc.). Trap/pressure uses tighter `TRAP_MOMENT_RANGE` (5). |
| `READ_ATTACK_THRESHOLD` | dynamic_hct.py | `200` | volume / drive | Normal read ≥ this → attack (or inverted pass if weak handler). |
| `READ_PASS_THRESHOLD` | dynamic_hct.py | `120` | volume / intercept | Normal read above this (below attack) → pass (or inverted attack). |
| `BROKEN_READ_ATTACK_THRESHOLD` | dynamic_hct.py | `175` | volume / drive | Open-floor (`moment==none`) attack bar. |
| `BROKEN_READ_PASS_THRESHOLD` | dynamic_hct.py | `110` | volume / intercept | Open-floor mid-tier pass bar. |
| `READ_STRONG_HANDLER_SUM` | dynamic_hct.py | `80` | volume / drive | `BH+AG` above this → strong-handler mapping; else inverted high/mid reads. |
| `READ_LOW_TIER_CHOICES` | dynamic_hct.py | `("hold","hold","attack","pass")` | volume / drive | Low-read pool → **50% hold / 25% attack / 25% pass**. |
| `HOLD_SECONDS_MIN` / `HOLD_SECONDS_MAX` | dynamic_hct.py | `1` / `2` | volume / TO | Hold burn (feeds 10-sec / shot-clock pressure). |
| `HCT_TEN_SECOND_LIMIT` | dynamic_hct.py | `10.0` | TO | Backcourt 10-second violation gate (elapsed game-sec). |
| `MAX_LOOP_ITERATIONS` | dynamic_hct.py | `15` | volume | Hard cap on detect→act loop (forces exit). |
| `GOAL_ACHIEVEMENT_READ_THRESHOLD` | dynamic_hct.py | `200` | volume / FG% | ABA: read > this → head-count-optimal HCO vs FB. |
| `ABA_READ_MID_THRESHOLD` | dynamic_hct.py | `125` | volume / FG% | ABA: mid band → HCO unless offense aggression=`aggressive` → FB; ≤ mid → 50/50 (inline coin). |
| `SHOOT_SH_THRESHOLD` | dynamic_hct.py | `80` | volume / FG% | Optimal ABA leaf: `SH > 80` → shoot. |
| `DRIVE_SCAG_THRESHOLD` | dynamic_hct.py | `105` | volume / drive | Else if `SC+AG > 105` → drive; else pass. |
| `TOP_PASS_OPEN_RIM_RADIUS` | dynamic_hct.py | `9` | volume / intercept | Open-rim dish override: teammate ≤9 from rim with no D within 9. |
| `HCT_DRIFT_PROBABILITY` | constants/__init__.py | `0.5` | contest / FG% | Per off-ball player: P(drift toward rim) on broken drive / ABA FB drive (feeds rim-race contest geometry). |

## HCT Denial / Recovery Placement

Placement dials that change who is in the lane / covered (intercept + contest), not pure spot tables.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `STRAIGHT_PRESSURE_DENY_FRACTION` | dynamic_hct.py | `0.6` | intercept / contest | Straight Pressure deny spot = 60% along BH→man. |
| `DEFENSE_RECOVERY_DENY_FRACTION` | dynamic_hct.py | `0.6` | intercept / contest | Mid-court recovery deny fraction. |
| `DEFENSE_RECOVERY_GUARDED_RADIUS` | dynamic_hct.py | `8.0` | intercept / contest | Offender within this of a non-stranded D target counts “covered”. |

**Pass contest:** HCT uses shared `PASS_*` defaults (`PASS_SAFETY_BASE=200`, `PASS_INTERCEPT_TIER_MID=200`, `PASS_LANE_DIST=8`, …) documented under **Dynamic HCO Defense** — HCO overrides to tighter safety/mid/lane; HCT does not. **Cutoff:** broken-HCT drive cutoff uses shared `best_cutoff_on_drive` with **no** `HCO_CUTOFF_*` gates (every AG-reachable help defender can cut; default time slack `1.0`).

## HCT Inline Magic (proposed names — document only)

**Status board + values:** [Promotion Pass](#promotion-pass). File/context detail below. (`FB_CONTEST_MAX_X_TRAIL` is already named — listed under Already named.)

| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `HCT_DFOUL_FRONTCOURT_P` | dynamic_hct.py D_FOUL spread | `0.10` (= `1 − 0.60 − 0.30`) | foul | Residual D_FOUL attribution to PF/C help. |
| `HCT_TRAPPER_PRESSURE_FRAC` | `_resolve_moment` | `0.5` | foul / steal / TO / contest | Trap: `d_score += 0.5 × trapper pressure`. |
| `HCT_CHEM_GATE_DIVISOR` | `_resolve_moment` | `/ 4` | foul / steal / TO / drive | Default neutral-band half-width = `chem/4 + pt_eff/pt_opp` (HCT/FB; HCO overrides with `DRIVE_NEUTRAL_BAND`). |
| `HCT_STEAL_CREDIT_OD_W` / `_AG_W` / `_IQ_W` | `_steal_credit_defender` / steal_factor | `0.4 / 0.4 / 0.2` | steal | Steal credit + steal composite in D8. |
| `HCT_BH_SECURE_CH_W` / `_BH_W` / `_IQ_W` | `_resolve_moment` | `0.4 / 0.4 / 0.2` | steal | BH “secure” vs steal factor. |
| `HCT_BH_HANDLE_BH_W` / `_CH_W` / `_IQ_W` | `_resolve_moment` | `0.4 / 0.3 / 0.3` | TO | BH handle vs dead-ball factor. |
| `BALL_HANDLING_BH_W` / `_AG_W` / `_IQ_W` / `_CH_W` | shared.py `calculate_ball_handling_score` | `0.5 / 0.2 / 0.2 / 0.1` | foul / steal / TO / drive | Moment `o_score` core (× d6). Shared across turns. |
| `DEF_PRESSURE_OD_W` / `_AG_W` / `_IQ_W` / `_CH_W` | shared.py `defender_pressure_raw` | `0.3 / 0.3 / 0.2 / 0.2` | foul / steal / TO / drive | Moment `d_score` core (× d6). |
| `PLAYER_READ_IQ_W` / `_CH_W` | dynamic_hct.py `_player_read` | `0.8 / 0.2` | volume / drive / FG% | Read roll `(IQ·0.8+CH·0.2)×d6`. |
| `HCT_ABA_LOW_TIER_COIN` | `_aba_hco_or_fb` | `getrandbits(1)` | volume / FG% | read ≤ mid → 50/50 HCO vs FB. |
| `HCT_SHOT_TREE_SUBOPTIMAL_POOL` | `_choose_shot_attempt` | `("shoot","drive","pass")` equal | volume / FG% / drive | read ≤ 200 with D in range → uniform random leaf. |
| `HCT_PFC_DENY_INTERP` | `_pfc_help_denial` | `0.6` | intercept / contest | PF/C deny spot at 60% BH→deep offender. |
| `FB_CONTEST_MAX_X_TRAIL` | fast_break_constants.py (also HCT FB rim) | `3` | contest / FG% | Defender must trail ≤3 x behind shooter (+ `CONTEST_EUCLIDEAN_RADIUS`). Canonical home is **FB** section below; HCT/legacy race reuses the same value. |

### Unsure / needs judgment (HCT inventory)

- **Brief vs code:** `Dynamic_HCT_Brief` historically listed `DEF_WIN_BASE=0.45`, `DFOUL_BASE=0.12`; live code is **`0.25` / `0.25`**. Brief now has a value-drift banner; this console follows code.
- **`MOMENT_RANGE` (11) vs `TRAP_MOMENT_RANGE` (5):** different “in range” meanings — do not collapse.
- **Default chem/4 neutral band vs HCO `DRIVE_NEUTRAL_BAND=100`:** intentional near-binary trap moments vs wide HCO drive B band — confirm before retuning D8 for HCO.
- **Deny fractions / drift:** included as contest/intercept levers; pure advance x/y jitter omitted (geometry).

## FCP (Full-Court Press)

Live path (`USE_DYNAMIC_FCP`) is a thin wrapper: `dynamic_fcp` → `compute_dynamic_hct_turn(..., turn_mode="fcp")`. **Outcomes mostly inherit HCT** — D8 at full strength (`event_scalar=1.0`, default chem/4 neutral band), shared `PASS_*` defaults (no FCP safety/mid/lane overrides), shared cutoff (no `HCO_CUTOFF_*` gates), and HCT reads/ABA/shot-tree dials. FCP-only gameplay levers are **read mix**, **engagement close**, **SF pass eligibility**, **press-break / PF–C zone**, plus shared **OOB pass awareness**.

Cross-ref: **HCT Moment Contact (D8)**, **HCT Reads / Loop / Shot Tree**, **HCT Denial / Recovery**, **Dynamic HCO Defense** (`PASS_*` defaults).

### FCP-specific named dials

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `FCP_READ_STRONG_HANDLER_SUM` | dynamic_hct.py | `130` | volume / drive / intercept | FCP strong-handler bar (`BH+AG`); HCT uses `80`. Above → high read attacks / mid passes; at/below → inverted. |
| `FCP_READ_LOW_TIER_CHOICES` | dynamic_hct.py | `hold×10, pass×7, attack×3` | volume / drive / intercept | Low-read mix **50% hold / 35% pass / 15% attack** (HCT: 50/25/25). |
| `FCP_ENGAGEMENT_X_SPACING` | dynamic_hct.py | `2` | contest | Engagement closer lands **2** grid from the other player’s setup x (aggression matrix decides who closes). Sets first-contact geometry before converge. |
| `FCP_PRESS_BREAK_PROGRESS` | fcp_pf_c_zone.py | `64` | volume / FG% / drive / contest | Home progress x ≥ 64 → press broken: PF/C zone off, man-glue release, ABA / HCO–FB goal path. |
| `FCP_ZONE_COMPRESS_START` | fcp_pf_c_zone.py | `36` | contest / intercept | Below this progress: wide PF/C help zone; at/above: compressing zone begins. |
| `FCP_ZONE_COMPRESS_STOP` | fcp_pf_c_zone.py | `50` | contest / intercept | End of sliding compress band; then fixed rear→front zone until press break. |
| `FCP_ZONE_SLIDE_WIDTH` | fcp_pf_c_zone.py | `14` | contest / intercept | Compressing zone depth = progress + 14 (capped by front). |
| `FCP_ZONE_FRONT_CAP` / `FCP_ZONE_REAR` | fcp_pf_c_zone.py | `64` / `50` | contest / intercept | Zone x front/rear bounds (who counts “in zone” for denial). |
| `FCP_SF_PASS_CLEAR_X_MIN` / `_MAX` | fcp_inbound_release.py | `14` / `20` | volume / intercept | Per-possession `clear_x = randint(14,20)`; SF excluded from pass targets until progress ≥ `clear_x`. |
| `FCP_SF_RELEASE_X_HOME` | fcp_inbound_release.py | `34` | volume / intercept | SF staging x after BIP (when he becomes eligible + lane geometry). |
| `OOB_PASS_PS_WEIGHT` / `OOB_PASS_CH_WEIGHT` | over_and_back.py | `0.8` / `0.2` | volume / intercept | Shared FCP+HCT: awareness floor `0.8·PS+0.2·CH`; pass only if `randint(1,100) > floor` (else hold). |

### FCP Inline Magic (proposed names — document only)

**Status board + values:** [Promotion Pass](#promotion-pass).

| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `FCP_ENGAGEMENT_MIN_SECONDS` | dynamic_hct.py `_apply_fcp_engagement` | `max(0.4, …)` | volume / TO | Floor on engagement beat game-seconds (feeds 10-sec / shot clock). |
| `FCP_ZONE_DENY_FRAC` | fcp_pf_c_zone.py `_fcp_help_denial` | `0.6` | intercept / contest | Deeper zone offender → deny spot at 60% BH→offender (same number as proposed `HCT_PFC_DENY_INTERP`). |
| `FCP_PASS_FLIGHT_MIN_SEC` | dynamic_hct.py pass branch | `max(0.3, dist/…)` | volume / intercept | Shared HCT/FCP pass-flight floor (clock + defense close race). |
| `FCP_STOPPER_HOLD_SEC` | dynamic_hct.py `_emit_stopper` | `0.5` | volume / TO | Shared terminal whistle/steal beat length. |

### Unsure / needs judgment (FCP inventory)

- **Legacy BSM/DST** (`USE_DYNAMIC_FCP=False`): still in `resolve_full_court_press_logic`; production default is dynamic — **omitted** (same policy as sunset HCO turn-level tables).
- **`DEFAULT_FCP_PRESS_WEIGHTS`:** unused until PR3 (trap/diamond); PR1 is Straight Pressure only — omitted until those plays ship.
- **Zone / SF release x:** included as contest/intercept/volume levers; pure setup spot tables (`FCP_*_SETUP_RANGES`, tier y tables) omitted as geometry.
- **Pass contest turn_type `"HCT"`:** FCP hardcodes HCT modifier key (`pt_opp_modifier`) — intentional; no separate FCP key.

## FB (Fast Break)

Live spine: after-steal / Covert Release / Rim Runner / Triangle route through **`resolve_fb_drive_step`**. Meet contact is **HCT D8** via `resolve_cutoff_contest` → `_resolve_moment(..., exclude_steal=True)` (default chem/4 band, `event_scalar=1.0` — **not** HCO `DRIVE_NEUTRAL_BAND`). Live cutoff uses `FB_DRIVE_CUTOFF_*` with **no** aggression `stop_attempt_prob` gate (unlike HCO).

Cross-ref: **HCT Moment Contact (D8)**, `CHARGE_THRESHOLD` / `BLOCKING_FOUL_THRESHOLD`, HCT ABA read bars (NEUTRAL stop tree), shared shot pipeline / uncontested / `CONTEST_EUCLIDEAN_RADIUS`.

### Shared drive / outlet / contest

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `FB_DRIVE_CUTOFF_PATH_CORRIDOR` | fast_break_constants.py | `14` | drive / contest | Perp corridor for live FB drive cutoff. Wider than HCO `HCO_CUTOFF_PATH_CORRIDOR` (11). |
| `FB_DRIVE_CUTOFF_TIME_SLACK` | fast_break_constants.py | `1.0` | drive / contest | Defender arrival-time credit on live FB cutoff race. |
| `FB_SHOOT_GEO_RADIUS` | fast_break_constants.py | `24` | volume / FG% | NEUTRAL stop: BH may shoot (or pass-target near basket) if ≤24 to rim (else spot-label exceptions). |
| `FB_POS_O_SHIMMY_MAGNITUDE` | fast_break_constants.py | `2` | drive / contest | POS_O dodge knot distance from meet/stopper (path + cascade re-rank). |
| `FB_CONTEST_MAX_X_TRAIL` | fast_break_constants.py | `3` | contest / FG% | Live drive finish: defender must trail ≤3 x behind shooter (+ contest radius 11). |
| `FB_PASS_GRID_SPOTS_PER_GAME_SECOND` | constants/__init__.py | `40` | contest / TO | Sharp FB outlet/pass ball speed (hang time). Faster than HCO `PASS_GRID_*` (24). |
| `FB_PASS_GRID_SPOTS_PER_GAME_SECOND_SLOPPY` | constants/__init__.py | `30` | contest / TO | Sloppy outlet hang time when `outlet_score <` threshold. |
| `FB_OUTLET_QUALITY_THRESHOLD` | constants/__init__.py | `50` | contest / drive | Sharp vs sloppy split; also gates CR getback “read to stop” path. |
| `FB_PASS_MIN_GAME_SECONDS` | constants/__init__.py | `0.5` | TO | Floor on FB pass-step game-seconds. |
| `FAST_BREAK_CORNER_THRESHOLD_BASE` | shot_threshold_scale.py | `180` | FG% | Triangle custom-corner override base: `180 − fb_efficiency`. |
| `DEFENDER_FREEZE_CLAMP_GRID_SPOTS` | fast_break_shot_geometry.py | `6` | contest / FG% | Non-first-arriver freeze: no closer than 6 to basket. |

### Initiation / routing

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `SLIDER_TO_FAST_BREAK_PROB` | shared.py | `{0:0, 1:0.25, 2:0.5, 3:0.75, 4:1.0}` | volume | DREB → FB initiation from `fast_breaks` slider (also CR release chances). |
| `STEAL_FB_PROB_BY_POTENTIAL_CUTOFFS` | fast_break_constants.py | see Effect | volume | Steal → FB vs HCO by potential-cutoff count × aggression 0–4. **0 cutoffs:** `.50/.80/.85/.90/.99`; **1:** `0/.20/.40/.60/.80`; **2+:** `0/.10/.20/.30/.40`. |
| `FB_MISS_DREB_FB_GETBACK_COUNT` | dreb_fast_break_arming.py | `2` | contest / drive | FB-miss → next Covert: up to 2 getbacks already beating the outlet. *(Also relevant to DREB inventory.)* |
| `FT_DREB_FB_GETBACK_COUNT` | dreb_fast_break_arming.py | `1` | contest / drive | FT → Covert getback count. *(Also relevant to DREB inventory.)* |

### After-steal

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `FB_AS_PASS_AHEAD_PROB` | fast_break_constants.py | `0.75` | volume / intercept | Given open ahead teammate on NO_MEET/POS_O, P(dish ahead) vs finish. |
| `FB_AS_MAX_PASS_AHEAD` | fast_break_constants.py | `2` | volume / intercept | Max pass-ahead hops per possession. |
| `FB_AS_MAX_CUTOFF_ATTEMPTS` | fast_break_constants.py | `None` | drive | POS_O cascade cap (`None` = uncapped, one attempt per on-floor D). |
| `FB_AS_LEAD_DEF_X_OFFSET` | fast_break_constants.py | `2` | contest | Lead defender sits 2 x ball-side of man. |
| `FB_AS_NO_MEET_CHASE_X_BEHIND` | fast_break_constants.py | `3` | contest / FG% | Unstopped BH’s defender trail chase x behind finish. |

### Rim Runner / Triangle

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `RR_LANE_PASS_THREAT_DIST` | rim_runner_fast_break.py | `8.0` | intercept / volume | Perp lane gate for BH→RR steal/bat + open-lane read (same number as `PASS_LANE_DIST`, separate constant). |

### FB Inline Magic (proposed names — document only)

**Status board + values:** [Promotion Pass](#promotion-pass).

| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `FB_CHARGE_READ_MIN_X_HOME` / `_MAX_X_AWAY` | fb_drive_resolution.py | `64.0` / `37.0` | foul / drive | Charge/block only if meet is past this x toward attacking basket. |
| `FB_STEAL_MEET_MIN_X_AHEAD` | fb_geo_helpers.py | `1.0` | drive | After-steal: meet must be ≥1 x toward basket from BH start or stopper skipped. |
| `FB_STOP_PASS_SH_MIN` | fb_stop_decision.py | `SH > 49` | volume | Teammate needs SH > 49 to be a NEUTRAL stop pass target. |
| `FB_OUTLET_SCORE_PS_W` / `_ST_W` / `_IQ_W` | shared.py `calculate_outlet_pass_score` | `0.6 / 0.2 / 0.2` | contest / drive | Outlet composite × d6 → scaled 1–100 (sharp/sloppy + CR stop read). |
| `FB_CR_BH_FALLBACK_WEIGHTS` | covert_release_drive_integration.py | `PG/SG/SF = 75/15/10` | volume | If no `last_release_player`, random BH by position. |
| `FB_CR_SHARP_STOP_READ_MULT` | covert_release_step_emitter.py | `outlet_score * 3` | drive / contest | Sharp outlet: getback must `player_read ≥ outlet_score×3` to sprint to cutoff. |
| `FB_CR_OUTLET_CUTOFF_X_OFFSET` | covert_release_step_emitter.py | `2` | drive | Stop target x = receiver x ± 2 toward basket. |
| `FB_DEFENDER_TARGET_X_OFFSET` | fast_break_shot_geometry.py | `2.0` | contest | Shot-race defender converge: 2 closer to basket than shooter. |
| `RR_OUTLET_CONTEST_RANGE` | rim_runner_fast_break.py | `10.0` | TO / volume | Outlet D must be ≤10 Euclidean of rebounder or auto-complete. |
| `RR_OUTLET_OFF_PS_W` / `_ST_W` / `_IQ_W` | rim_runner_fast_break.py | `0.5 / 0.3 / 0.2` | TO / volume | Outlet offense base × d6. |
| `RR_OUTLET_DEF_IQ_W` / `_OD_W` / `_ST_W` | rim_runner_fast_break.py | `0.5 / 0.3 / 0.2` | TO / volume | Outlet defense base × d6 (in range only). |
| `RR_OUTLET_OFF_SCORE_MULT` / `_FB_EFF_MULT` / `_FB_OPP_MULT` | rim_runner_fast_break.py | `1.5` / `3` / `2` | TO / volume | Complete if `1.5·off_score + 3·fb_eff > def_score + 2·fb_opp`. |
| `RR_LANE_READ_BASE` / `_FB_EFF_COEF` | rim_runner_fast_break.py | `200` / `5` | volume / intercept | Correct read if `(IQ+fb_eff)×d6 > 200 − 5×fb_eff`. |
| `RR_MISREAD_AGGRESSION_MIN` | rim_runner_fast_break.py | `aggression >= 3` | volume / intercept | Misread: aggressive → pass with 2/3; else 50/50. |
| `RR_OPEN_LANE_MAX_THREATS` / `_PASSIVE` | rim_runner_fast_break.py | `≤1` / `≤0` | volume / intercept | Objective open lane; passive offense holds if any threat. |
| `RR_LANE_INT_OD_W` / `_AG_W` / `_IQ_W` | rim_runner_fast_break.py | `0.6 / 0.2 / 0.2` | intercept / steal | Primary D lane-pass intercept composite × d6. |
| `RR_LANE_TIER_HI_BASE` / `_MID_BASE` | rim_runner_fast_break.py | `250` / `200` | intercept / steal | Steal if score > `250−fb_opp`; bat OOB if > `200−fb_opp`; else complete. |
| `RR_SHOT_THRESH_MULTI_DEF_ADD` / `_FIGHT_MULT` | rim_runner_fast_break.py | `+100` / `fight×2` | FG% | Open-lane finish threshold: 0 D → easy; ≥2 D → `base+100+chem−2·fight`. |
| `TRIANGLE_DECISION_D8` | rim_runner_fast_break.py | `randint(1,8)` | volume / FG% / drive | 1–2 post; 3 corner-3; 4 wing-3; 5–6 drive subtree; 7–8 → HCO. |
| `TRIANGLE_DRIVE_DECISION_D5` | rim_runner_fast_break.py | `randint(1,5)` | volume / FG% / drive | Drive subtree: 1–2 BH drive; 3–4 RR feed; 5 corner kick. |
| `RR_BURST_AG_W` / `_IQ_W` / `_CH_W` | rim_runner_fast_break.py | `0.6 / 0.2 / 0.2` | contest / intercept | Burst vs sprint: `randint(1,100) < composite`. |
| `RR_BURST_DX_SUCCESS` / `_FAIL` | rim_runner_fast_break.py | `20–25` / `9–14` | contest / intercept | Burst x advance range on success/fail. |

### Omitted (sunset / geometry)

- **`STEAL_ENTRY_*`:** unused (steal short-circuits to after-steal).
- **`FB_CUTOFF_*_STEAL` / `_DREB` + legacy CR stop-attempt gate:** flag-off / unreachable under live drive resolution.
- Spot/tier tables (`FB_AS_*_SPOTS`, shot-spot ranges, etc.) — geometry.
- Animation ms / SFX / announce holds.

### Unsure / needs judgment (FB inventory)

- **Dual `FB_CONTEST_MAX_X_TRAIL` definitions** (constants vs shot_geometry) — both `3`; promote one source of truth on a promotion pass.
- **`RR_LANE_PASS_THREAT_DIST` (8) vs `PASS_LANE_DIST` (8):** intentional twin or should RR import shared?
- **Getback counts:** listed under FB initiation; cross-check again in **DREB** session.
- **CR sharp-outlet `×3` read:** emit-then-resolve seeds cutoff — treated as live dial here.

## OREB (Offensive Rebound)

OREB turn resolves after a miss awards an offensive rebounder: **putback vs kickout**, then putback FG%/foul/contest (or kickout → HCO). Board-win scoring is shared with DREB (`select_rebounder_by_score`); the primary OREB% dial is `OREB_REBOUND_SCORE_DISCOUNT`. Putbacks reuse Part-C proximity + Inside shot math but **skip the block funnel**. Tip-out is not a rebound mechanic.

Cross-ref: **HCO Micro Movements** (`PROXIMITY_CONTEST_*`), `CONTEST_EUCLIDEAN_RADIUS`, **HCO Shot Pipeline** (Inside weights, `HARD_PROB`/`SOFT_PROB`, uncontested helpers, dunk gate). Shared rebound primitives listed for **DREB** follow-up.

### Named dials

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `OREB_REBOUND_SCORE_DISCOUNT` | constants/__init__.py | `0.8` | oreb | Offensive candidates’ final rebound score ×0.8 in `select_rebounder_by_score` (box-out edge). Tune vs ~30% OREB%; `1.0` = no discount. Applies on all paths using this helper (HCO/FT/FB/HCT + putback-miss chains). |
| `REBOUND_TEAM_CHEMISTRY_FACTOR` | constants/__init__.py | `0.5` | rebound outcomes | Scales the team component of every eligible player's rebound score: `0.5 × team_chemistry × rebound_modifier`. |
| `OREB_PUTBACK_ONLY_THRESHOLD` | eoq_clock_progression.py | `6` | volume / possession | `time_remaining < 6` → force putback (no kickout), including chained OREBs. |
| `OREB_PUTBACK_MIN_TIME_ELAPSED` | constants/__init__.py | `2` | possession | Floor on putback `time_elapsed` after schema burn. Kickout is **not** floored. |
| `NEAR_BOUNCE_REBOUND_ATTEMPTOR_DISTANCE` | shared.py | `20` | oreb | Putback-miss first-pass Euclidean candidate radius; upper-half = `20 × 0.5 = 10`. Also failed-attemptor collect radius (shared with DREB). |
| `MO_OREB_DELTA` | momentum.py | `1` | other | +MO on OREB once threshold met. |
| `MO_OREB_THRESHOLD` | momentum.py | `3` | other | +`MO_OREB_DELTA` on a player’s **3rd** OREB and each after. |
| `TEAM_ATTR_RANGES["rebound_modifier"]` | constants/__init__.py | `(0.0, 0.4)` | oreb | Feeds `REBOUND_TEAM_CHEMISTRY_FACTOR × team_chemistry × rebound_modifier` into rebound score + first tie-break. |

### OREB Inline Magic (proposed names — document only)

**Status board + values:** [Promotion Pass](#promotion-pass).

| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `OREB_PUTBACK_PCT_AGGRESSIVE` / `_NORMAL` / `_PASSIVE` | shared.py `resolve_offensive_rebound` | `90` / `75` / `60` | volume | Offense `aggression_call` → P(putback) on `randint(1,100)`; else kickout. |
| `OREB_MIN_SHOT_CLOCK_FOR_ATTEMPT` | turn_manager.py OREB turn | `2` | TO / possession | Entering OREB with shot clock ≤2 → dead-ball shot-clock TO. |
| `OTB_MAX_EUCLIDEAN` | shared.py `resolve_over_the_back_foul` | `4` | foul | Nearest opponent farther than 4 → no over-the-back. |
| `OTB_OFFENSE_THRESHOLD_BASE` | same | `90` | foul | Offensive OTB if `roll > 90 + offense discipline`. |
| `OTB_DEFENSE_THRESHOLD_BASE` | same | `10` | foul | Defensive OTB if `roll < 10 − defense discipline`. |
| `OTB_IQ_GATE_ROLL` | same | `randint(1,100) ≤ foul_player.IQ` | foul | Pass IQ gate → foul cancelled. |
| `OTB_FINAL_CALL_SIDES` | same | `randint(1,2) == 1` | foul | Final 50% call after IQ gate. |
| `REBOUND_ATTR_RB_W` / `_ST_W` / `_IQ_W` / `_CH_W` | shared.py `calculate_rebound_score` | `0.5 / 0.3 / 0.1 / 0.1` | oreb | Base rebound composite before d6. **Shared with DREB.** |
| `REBOUND_SCORE_ROLL` | same | `randint(1, 6)` | oreb | Multiplier on composite. **Shared with DREB.** |
| `REBOUND_UPPER_HALF_DEFAULT` | `select_rebounder_by_score` | `12` | oreb | Default upper-half distance (HCO/FT when not overridden). **Shared.** |
| `REBOUND_LOWER_DISCOUNT_STRONG` / `_WEAK` | same | `0.7` / `0.95` | oreb | Lower-half score mult when ≥2 / &lt;2 players in upper half. **Shared.** |
| `REBOUND_UPPER_COUNT_FOR_STRONG` | same | `2` | oreb | Threshold for strong vs weak lower-half discount. **Shared.** |
| `REBOUND_SHOOTER_PUTBACK_SCORE_PENALTY` | same | `0.8` | oreb | Penalized shooter / putback-shooter final score ×0.8. **Shared.** |
| `REBOUND_FALLBACK_START` / `_STEP` / `_MAX` | same | `20` / `5` / `150` | oreb | Empty pool → expand Euclidean radius until a winner. **Shared.** |
| `OFFENSE_GETBACK_CHANCES` | getback_selection.py | `{0: none1; 1: .5/.5; 2: .25/.75; 3: .1/.8/.1; 4: 0/.5/.5}` | oreb | HCO get-back slider shrinks who crashes for OREB on HCO misses. |
| `PUTBACK_INSIDE_HARD_FOUL_BASE` / `_SOFT_FOUL_BASE` | shot_manager.py inside foul path | `35` / `105` | foul | Putbacks force `shot_type="inside"`; thresholds then − defense discipline (global named foul thresholds are 50/110 — putbacks use these bases). |
| `PUTBACK_PAINT_DEF_ID_W` / `_ST_W` / `_IQ_W` / `_CH_W` | `calculate_shot_score` `is_paint=True` | `0.6 / 0.2 / 0.1 / 0.1` | contest / FG% / foul | Putback → ID-heavy defense score (then × proximity). |
| `BOUNCE_VAR_*` tiers | shared.py `_bounce_variance_for_shot_distance` | `<15→(2,6,±6)`; `≤20→(2,8,±8)`; `≤30→(3,14,±10)`; `≤45→(5,22,±12)`; else `(8,min(40,0.55·d),±14)` | oreb | Bounce geography for next board battle. **Shared with DREB** (Rebound_System.md tiers stale). |

### Shared with DREB (detail in DREB session)

Bounce spot / variance, `determine_rebounder` → `select_rebounder_by_score` → `calculate_rebound_score`, `OREB_REBOUND_SCORE_DISCOUNT` (OREB% on every miss path), `NEAR_BOUNCE_*`, OTB foul resolver, team `rebound_modifier` / chem tie-breaks.

### Omitted

- Kickout outlet spot pools (geometry); UESS step ms / SFX
- Dead: `ReboundManager.handle_rebound`, unused `oreb_shot_attempt()`
- Tip-out rebound mechanic (does not exist)
- Zone / inside-distance shot-threshold bonuses — **not applied** on putback path

### Unsure / needs judgment (OREB inventory)

- Bounce-variance tiers documented here as shared; expand under **DREB** if that session needs more.
- `OREB_PUTBACK_MIN_TIME_ELAPSED`: gameplay dial vs clock-presentation floor.
- Inside foul bases `35`/`105` vs global `HARD/SOFT_SHOOTING_FOUL_THRESHOLD` (`50`/`110`) — intentional putback path difference.

## DREB (Defensive Rebound)

After the board is won by the defense: **OTB check**, capture clock, then **HCO outlet** or **FB arm** (Covert / Rim Runner / Triangle). Board-win scoring is shared with OREB (cross-ref below). Primary post-board levers are FB initiation, getback/release placement, and outlet contract.

Cross-ref: **OREB** shared rebound scoring / bounce / OTB / `OREB_REBOUND_SCORE_DISCOUNT`; **FB** `SLIDER_TO_FAST_BREAK_PROB`, outlet quality / CR stop dials, getback counts, live `FB_DRIVE_CUTOFF_*`.

### Named dials

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `DREB_OUTLET_PASSER_BOUNCE_MISMATCH_THRESHOLD` | shot_manager.py | `12.0` | possession | DREB→HCO outlet: if rebounder `coords.x` vs bounce x differs by >12, passer is re-anchored near bounce before receiver target. |
| `FAST_BREAK_REBOUND_GEO_DISTANCE` | shared.py | `25` | dreb | FB-miss (and after-steal FB miss) first-pass Euclidean candidate radius; upper-half = `12.5`. Who wins the board on FB miss. |
| `FREE_THROW_REBOUND_MAX_X_DELTA` | shared.py | `20` | dreb | Last-FT miss: only players with `\|x − bounce_x\| ≤ 20` eligible (then shared score). |
| `FT_DREB_FB_GETBACK_COUNT` | dreb_fast_break_arming.py | `1` | contest / drive | FT→Covert: up to 1 getback nearest center. *(Also under FB initiation.)* |
| `FB_MISS_DREB_FB_GETBACK_COUNT` | dreb_fast_break_arming.py | `2` | contest / drive | FB-miss→Covert: up to 2 getbacks already beating the outlet toward the new rim. *(Also under FB.)* |
| `DEFAULT_DREB_FAST_BREAK_WEIGHTS` | fast_break_play_types.py | `{covert:33, rim_runner:33, triangle:34}` | volume / possession | Fallback play-mix when playbook `fast_breaks` weights missing/zero. |
| `POST_DREB_FLSS_MIN_CLOCK` | eoq_clock_progression.py | `2` | possession | Post-DREB FLSS eligibility requires `time_remaining > 2`. |
| `HCO_STEP_T_FLOOR_GAME_SECONDS` | constants/__init__.py | `0.5` | possession | Discrete DREB capture step T floors at 0.5 (AG sprint travel); turn then stamps `time_elapsed ≥ 1` (inline below). |

### DREB Inline Magic (proposed names — document only)

**Status board + values:** [Promotion Pass](#promotion-pass).

| Proposed name | File / context | Current literal | Affects | Effect |
|---|---|---|---|---|
| `DREB_TURN_TIME_ELAPSED_FLOOR` | game_manager.py `_build_dreb_turn_from_miss` | `≥ 1` game-sec | possession | Discrete DREB always burns ≥1 game-second on the master clock (even if schema T is 0.5–0.99). |
| `DREB_EMERGENCY_GETBACK_ROLL` | getback_selection.py `try_emergency_getback_vs_poised_fb` | `randint(0,10) ≤ fb_opp_modifier` | contest / drive / possession | If offense sent **0** getbacks but defense armed DREB→FB, shooting team may still force 1 getback via `fb_opp`. |
| `DREB_CR_RELEASE_IQ_READ` | shot_manager.py Covert prep | `randint(1,100) < release.IQ` | contest / drive | Good vs bad release-coord band for Covert outlet receiver. |
| `DREB_CR_GETBACK_IQ_READ` | shot_manager.py getback coords | `randint(1,100) < getback.IQ` | contest / drive | Good vs bad getback-coord band for each retreat defender. |
| `DREB_CR_RELEASE_AG_X_MIN_HI` / `_MID` / `_LO` | covert_release.py | `AG≥80→50`; `≥60→47`; else `45` | contest / drive | HOME-orientation x floor for release spot. |
| `DREB_CR_GETBACK_AG_X_MIN_HI` / `_MID` / `_LO` | covert_release.py | `AG≥80→55`; `≥60→53`; else `50` | contest / drive | Same for getback defenders (ahead of release). |
| `DREB_HCO_OUTLET_RX_X_OFFSET` / `_Y_JITTER` | shot_manager.py outlet target | `randint(3,6)` toward basket; `randint(−6,6)` y | possession | HCO half-court outlet receive spot vs passer. |
| `DREB_HCO_OUTLET_BOUNCE_REANCHOR_XY` | same (mismatch branch) | passer `x = bounce±3`; `y = bounce±5` | possession | When mismatch threshold trips, outlet passer snaps near bounce. |
| `FB_MISS_FRONTCOURT_X_SPLIT` | shot_manager.py FB rebound eligibility | home shoot `x≥50`; away `x≤50` | dreb | Prefilter before `FAST_BREAK_REBOUND_GEO_DISTANCE` scoring on FB miss. |

### Cross-ref (do not retune here)

- **Board win:** OREB section shared scoring (`REBOUND_ATTR_*`, discounts, bounce tiers, `NEAR_BOUNCE_*`).
- **OTB on discrete DREB turn:** OREB `OTB_*` stack — cancels outlet / FB continuation.
- **FB vs HCO:** `SLIDER_TO_FAST_BREAK_PROB`; Slow-It-Down / Force Foul can suppress FB after DREB.
- **Getbacks (pool + OREB%):** OREB `OFFENSE_GETBACK_CHANCES`.
- **Outlet / CR stop:** FB `FB_OUTLET_*`, `FB_CR_SHARP_STOP_READ_MULT`, live drive cutoff.

### Omitted

- Rebounder paint clusters / attemptor jitter (geometry); CR good/bad y-band interiors beyond AG floors
- Announce suppress / hold_ms / SFX
- Legacy: `ReboundManager.handle_rebound`, `FB_CUTOFF_*_DREB`, `DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET`

### Unsure / needs judgment (DREB inventory)

- HCO shot path = one FB roll; FT/putback/FB-miss = `arm_dreb_fast_break` re-rolls — intentional dual initiation?
- `HCO_STEP_T_FLOOR` + hard `time_elapsed ≥ 1`: presentation vs true possession dial?
- Covert AG x_min bands: contest levers vs pure geometry on promotion?
- **Turn-type inventory complete.** Next work: execute **Promotion Pass** (status board near top of this file) and/or edit already-named dial values.

---

## Sim Game Experience

Playback pacing for the **Sim Full Game / Sim Rest of Game** broadcast overlay (Act 2). All six live at the top of `FrontEnd/static/js/phaser/utils/simGamePresentation.js`. Stat bars, on-court lineups, worm, scoreboard, and spotlight all update **together, once per emitted turn** (one frame = one `turns[]` entry); a quarter is normalized to `QUARTER_MS` regardless of how many turns it contains.

| Constant | File | Value | Affects | Effect |
|---|---|---|---|---|
| `QUARTER_MS` | simGamePresentation.js | `18000` | playback | Each quarter stretched across ~18s. Per-turn hold = `QUARTER_MS ÷ turns-in-quarter`, clamped to [`FRAME_MIN_MS`, `FRAME_MAX_MS`]. |
| `FRAME_MIN_MS` | simGamePresentation.js | `130` | playback | Fastest a single turn can tick (dense-quarter clamp). |
| `FRAME_MAX_MS` | simGamePresentation.js | `900` | playback | Slowest a single turn can tick (sparse-quarter clamp). |
| `PRETIP_MS` | simGamePresentation.js | `2200` | playback | Tip-off / pre-tip zero-state hold. |
| `BREAK_MS` | simGamePresentation.js | `2800` | playback | Quarter-break summary card hold. |
| `FINAL_MS` | simGamePresentation.js | `2600` | playback | Final hold before handoff to the existing completion popup. |
| `LINEUP_CHANGE_MS` | simGamePresentation.js | `1000` | playback | Extra hold on a frame where the on-court five changed (foul-out swap / sub) so the swap reads. Overrides the normal per-turn hold on those frames, so a quarter with lineup changes runs slightly over `QUARTER_MS` (≈ `LINEUP_CHANGE_MS − normal per-turn hold` per change). |

**Whole game ≈ ~80–85s** (4 × ~18s + three break cards + tip-off + final). Bars ease via a 0.5s CSS `width` transition between emitted values; reduced-motion fast-forwards (live ~40ms, holds ~400ms).

---

## Player Attribute Recalibration (pass 1 — position ratings, generation, height re-band)

Constants landed by the Player Attribute Recalibration merge (design `Player_Attribute_Recalibration_Design.md`). This pass covers the RT formula (§3.6), interim position-intent generation (§11.2), the pool remap (§11.3) and the downstream height re-band (§11.2). Growth-model knobs (peaks, family timing/curves, offseason split, accumulator, RT compression) are **deferred** to the offseason-development task and intentionally NOT implemented here.

### Position rating formula — `BackEnd/utils/position_ratings.py`

`RT_pos = weighted_attribute_mean(pos) × height_fitness(pos, height)`, clamped lower 1, uncapped above.

| Constant | Value | Effect |
|---|---|---|
| `POSITION_WEIGHTS` | 5 vectors, §3.6.1 (each sums to 1.0) | attribute mix per position; one table for players+recruits |
| `HEIGHT_FITNESS` | (ideal, short/in, tall/in): PG 73.5/.020/.050 · SG 76/.030/.045 · SF 78.5/.035/.035 · PF 80.5/.050/.025 · C 82.5/.060/.010 | multiplicative height gate, all 5 positions |
| `HEIGHT_FITNESS_FLOOR` / `_CAP` | 0.50 / 1.15 | fitness clamp (peak 1.0 at ideal; cap is a guard) |

### Interim generation — `BackEnd/utils/player_generation.py`

| Constant | Value | Effect |
|---|---|---|
| `JH_ANCHOR_BY_TIER` | Poor 20 · BelowAverage 25 · Average 30 · Good 35 · Great 40 · Elite 50 | JH-rung RT anchor per tier (§4.1) |
| `TIER_FREQUENCY` | .07 / .20 / .40 / .20 / .11 / .02 | share of generated players per tier (§4.1). Supersedes the 4-value `TIER_FREQUENCY` in design §12. |
| `RUNG_MULTIPLIERS` | JH 1.00 · FR 1.17 · SO 1.43 · JR 1.80 · SR 2.00 | class-year ladder; target RT = anchor × rung (§4.2) |
| `POSITION_INTENT_SHARE` | 0.20 | ~even position intent |
| `HEIGHT_IDEAL_IN` | = fitness ideals | per-position height mean (§11.2) |
| `HEIGHT_SD_IN` | 2.1 | per-position height sd (league aggregate ≈ mean 78, sd 3.6) |
| `PROFILE_FILLER` | 0.45 | unweighted-attr baseline as fraction of signature attr |
| `PROFILE_ND_BASE` | 0.60 | ND baseline (ND is not in any RT vector) |
| `ATTR_NOISE_SD` | 0.13 | per-attribute spread → tweener/tie rate (sharper identities per decision #7; ≥100 ≈ 5.7%) |

### Pool remap — `scripts/regenerate_universal_pool.py`

| Constant | Value | Effect |
|---|---|---|
| `INTENT_BANDS` | C/PF/SF each 0.20 (tallest→shortest), guards = rest | height-band position-intent assignment (§11.3 step 1) |
| `IDENTITY_STRENGTH` | 0.15 | how much a player's old attribute shape modulates the new position profile ("a shooter stays a shooter"); 0.35 imported the old SH-spike artifact (≥100 12.6%→6.4% at 0.15) |

### Height re-band (§11.2 — league median 72 → 78)

| Constant / location | Value | Effect |
|---|---|---|
| `LEAGUE_MEDIAN_HEIGHT_IN` (`constants/__init__.py`) | 78 | single home for missing-height fallback (was 72/75/76 scattered) |
| `height_to_block_score` (`utils/shared.py`) | `≤MED→0`, `h−MED`, `≥MED+10→10` (MED=78) | offsets from `LEAGUE_MEDIAN_HEIGHT_IN`; preserves ~1.68 league-mean block score (measured 1.69) |
| `get_height_scale_value` (`utils/opening_tip.py`) | thresholds +3 (centre-fed: 82→8) | **left as literals** — anchored to the *centre* median (+3), not the league median; do not re-express against `LEAGUE_MEDIAN_HEIGHT_IN` |
| `WEIGHT_BY_HEIGHT_BANDS` (`player_generation.py`) | `MED−4 / MED / MED+4` | offsets from `LEAGUE_MEDIAN_HEIGHT_IN`; walk-ons now use the generator (Poor tier) |
| training-camp weight gates (`training_execution_v2.py`) | `>MED+3`, `>MED` | offsets from `LEAGUE_MEDIAN_HEIGHT_IN` |

> **Pass-2 watch — existing (old-scale) saves lose shot-blocking.** `height_to_block_score` now
> returns 0 at ≤ median (78), but old-scale rosters top out at **p90 height 78**, so nearly every
> player on a pre-recalibration franchise scores 0 → blocks collapse toward zero there. **Known and
> accepted** (recalibration is new-franchises-only; new-pool rosters have the height to block).
> Recorded so a pass-2 tester report of "no blocks on my existing save" is not misdiagnosed as a bug.

### Deferred to later tasks (documented in design §12, NOT implemented this pass)
`PEAK_COUNT_DISTRIBUTION`, `PEAK_RUNG_WEIGHTS`, `PEAK_MULTIPLIER`, `CH_PEAK_WEIGHTING`, `FAMILY_TIMING_WEIGHTS`, `FAMILY_CURVES`, `RT_COMPRESSION_THRESHOLD`, `RT_SOFT_CAP`, `NON_CORE_GROWTH_MULTIPLIER`, `WEEKLY_DECAY_BY_YEAR`, `OFFSEASON_INSEASON_SPLIT`, `ACCUMULATOR_WEIGHT`. CH stays flat `randint(1,100)` (§8); `CAMP_BONUS_CH_BANDS` unchanged.

---

## Player Growth Model (pass 2 — offseason development, wired into finish_season)

Fitted offline against 10k Monte Carlo careers (`scripts/mc_growth_fit.py`) over the real
module `BackEnd/utils/player_development.py`; wired into `finish_season` (the season
rollover), which runs `develop_one_offseason` per player after the year bump and before
Training Camp. Camp's CH bonus, year bonus and FR/SO HT/WT growth were **deleted** — the
offseason event owns them; camp keeps only its 30-point allocation and decay skip.

### Exposed for tuning

| Constant | Value | Effect |
|---|---|---|
| `PEAK_BONUS` | +0.30 × JH anchor (fixed per peak) | career multiple = 1.7 + 0.30·peaks (→ 1.7/2.0/2.3/2.6) |
| `STD_RUNG_INCREMENT` | FR .17 / SO .20 / JR .15 / SR .18 (Σ .70) | 0-peak ladder shape; no dead rung (min +5 RT) |
| `CH_PEAK_LOW` / `CH_PEAK_HIGH` | (.38,.52,.10,0) → (.02,.58,.34,.06) | the CH→peak-count spread; midpoint = 20/55/22/3 |
| `OFFSEASON_SPLIT` | 0.70 | offseason-vs-in-season distribution blend |
| `FAMILY_CURVES` | FR 3.0/1.0/.30 · SO 2.0/1.2/.60 · JR .60/1.3/2.2 · SR .35/1.2/3.2 | per-rung weight multipliers (phys/skill/mental) → physical-early, mental-late |
| `HT_TOTAL_MEAN` / `HT_TOTAL_SD` | 3.2 / 1.9 (clamp [0,8]) | career HT gain (p50 ~3in) |
| `HT_CURVE_BY_TIMING` | early 55/30/12/3 · standard 40/30/20/10 · late 15/25/35/25 | when HT arrives, by physical timing |
| `HT_PER_RUNG_CAP` | 3 | ≤~2.5in/summer intent; raised from 2 (which clipped p90 to 5in vs 6) |

### Not exposed (fixed / not target-fittable)
`FAMILY_TIMING_WEIGHTS`, `FAMILY_TIMING_SHIFT`, `INTRA_FAMILY_GAMMA` (0.20), `NON_CORE_GROWTH_MULTIPLIER` (0.06), `PEAK_RUNG_WEIGHTS`, `PEAK_COUNT_DISTRIBUTION`, `RT_COMPRESSION_THRESHOLD`/`RT_SOFT_CAP` (95/130, near-inactive guard). `ACCUMULATOR_WEIGHT` and the precise in-season net share are live-tuning knobs (a 26-week season, not offline).

### Weekly decay (in-season, §7.2)
`PRE_TRAINING_DECAY_BY_YEAR` reduced to FR/SO (-2,0), JR/SR (-1,0) (was FR (-5,-2) … SR (-2,0)) so in-season is a light drag, not a treadmill. The offseason event owns career growth. The exact ~30% in-season share is a live-tuning follow-up (not offline-verifiable).

### Legacy-player caveat (existing saves, not backfilled) — READ BEFORE DEBUGGING
A player with no `development` subdoc (a save that predates pass 2) is **lazy-backfilled** at his first rollover: a profile rolled once from his live CH (frozen as `ch_seed`), peaks restricted to his remaining rungs, and persisted so it never re-rolls. His `entry_tier` — if absent — is **derived from his current top RT**, which is *systematically low for old-scale bigs* whose RT collapsed under height gating (§3.6.7): a distorted big reads as a lower tier and develops on a lower ladder, compounding the degradation. This is accepted (recalibration is new-franchises-only, §14); new franchises never hit this path (entry_tier is carried pool→FPD). Do not diagnose a stunted legacy big as a bug.
