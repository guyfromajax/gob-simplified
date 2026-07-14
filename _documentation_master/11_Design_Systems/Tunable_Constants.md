# Tunable Constants

Central registry of tunable game-logic constants — the knobs for balancing gameplay. Each entry lists the constant, its current value, and a one-line effect.

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

| Constant | Value | Effect |
|---|---|---|
| `TRAP_MOMENT_RANGE` | 5 | Max grid distance a defender can be from the ball-handler to count toward an HC trap/pressure double-team. |

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

The **openness primitive** (Dynamic_MM_Brief §7, Stage 1): a defender who loses his reactive read on a positional step **lags** toward his man (Part B) → his Euclidean gap to the man grows → the shot contest **scales down** by that gap (Part C). One signal (defender-to-man distance on the frozen grid), read by the shot contest + the dish/hot-read gate. Gated by `GOB_DYNAMIC_HCO_DEFENSE` (posture set); **MAN defense only** (zone openness = Stage 4 parity). Tune with `scripts/s1_openness_monte_carlo.py` (reuses these exact functions).

The beat roll (shared with the subtle-movement freeze): `(player_read_raw + defensive_efficiency) × rand(1,6)`; **beaten if ≤ `MOTION_READ_THRESHOLD`**. The |margin| below the bar drives how far the defender lags (owner-locked: harder beat → more open).

| Constant | File | Value | Effect |
|---|---|---|---|
| `OPENNESS_LAG_MAX` | animator.py | `0.8` | **Part B** — worst-beat lag: a fully-beaten defender tracks only `(1 − 0.8) = 20%` of the way toward his man (holds 80% of the opened gap). **↑ = beaten man more open** (bigger FG swing on beats). Primary openness dial. |
| `OPENNESS_LAG_MARGIN_SCALE` | animator.py | `110.0` | **Part B** — the \|read-miss margin\| at which lag saturates to `LAG_MAX` (= `MOTION_READ_THRESHOLD`). Lag = `LAG_MAX × min(1, \|margin\|/SCALE)`. **↓ = marginal misses lag harder** (openness saturates sooner). |
| `OPENNESS_ANCHOR_MOVE_EPS` | animator.py | `1.0` | **Part B** — the guarded man must travel more than this many grid for a beat to open space; a stationary man never opens (no lag). ↑ = only bigger cuts open space. |
| `PROXIMITY_CONTEST_NEAR_DIST` | shot_manager.py | `3.0` | **Part C** — defender ≤ this grid from the shot spot = **full contest** (factor 1.0). Owner spec: ≤3 = major defensive advantage. |
| `PROXIMITY_CONTEST_OPEN_DIST` | shot_manager.py | `9.0` | **Part C** — defender ≥ this grid = the wide-open floor; contest ramps linearly down from NEAR to here. **↓ = shots open up at closer range = more openness** (secondary dial; MC-sensitive). |
| `PROXIMITY_CONTEST_OPEN_FLOOR` | shot_manager.py | `0.15` | **Part C** — residual defensive weight from `OPEN_DIST` out to the contest radius (9–11 grid = "not open, low impact"). ↑ = far defenders still bother the shot. Beyond `CONTEST_EUCLIDEAN_RADIUS` (11) → 0 (uncontested). |

> **MC finding (2026-07-13, model):** S1's FG% impact is **bottlenecked by beat-frequency (~14% of possessions), not by `LAG_MAX`** — sweeping `LAG_MAX` 0.5→0.95 moves FG only +0.6→+1.5, and `OPEN_DIST` 11→7 moves it +0.9→+1.9. To make openness matter more, raise how often defenders get beaten (the `MOTION_READ_THRESHOLD` bar / how often men move), not just how far they lag. Confirm beat-frequency + the live baseline in-app before committing values.

## HCO 3-Tier Drives (Dynamic MM — S2)

The **drive contest** (Dynamic_MM_Brief §S2): a drive to the rim resolves through the shared `_resolve_moment` (FB/HCT model) in ONE roll → a **tier** (A blow-by / B contested-neutral pull-up / C clean stop) + optional **contact** (D_FOUL / O_FOUL charge / DEAD BALL turnover). On a Tier-A blow-by, a **help defender** may rotate to cut off the drive (S2c) — the same contest vs the cutoff defender, demoting the blow-by. All gated by `GOB_DYNAMIC_HCO_DEFENSE`. Tune with `scripts/s2_drive_monte_carlo.py` (reuses the real contest + cutoff functions).

| Constant | File | Value | Effect |
|---|---|---|---|
| `DRIVE_NEUTRAL_BAND` | attack_drive_clearance.py | `100.0` | **Primary tier dial** — the win/lose gate half-width (o_score/d_score pts) passed to `_resolve_moment(neutral_band=…)`. The shared chem+eff default (~few pts) makes B vanish (near-binary A-vs-C); **~100 gives B a plurality at even matchups** (MC: A/B/C ≈ 21/50/21%). ↑ squeezes A+C into B (more pull-ups, fewer clean blow-bys *and* clean stops); ↓ → binary. |
| `DRIVE_NEUTRAL_STOP_FRACTION` | attack_drive_clearance.py | `0.5` | Tier-B stop point — a contested-neutral drive pulls up ~midway to the rim (S2d truncates the path here). Cosmetic (shot difficulty follows from the reclassified pull-up distance), not an outcome-rate knob. |
| `HCO_CUTOFF_PATH_CORRIDOR` | attack_drive_clearance.py | `11.0` | **S2c** — a help defender must be within this perpendicular grid of the drive line to attempt a cutoff. ↑ = wider net = more cutoffs. MC note: **rarely the binding constraint** (help defenders that matter sit close to the path); aggression dominates. |
| `HCO_CUTOFF_DEFENDER_TIME_SLACK` | attack_drive_clearance.py | `1.0` | **S2c** — arrival-time credit in the race (>1 = the defender gets extra time budget → more cutoffs). `1.0` = a clean blow-by outruns late help. |
| `HCO_CUTOFF_STOP_ATTEMPT_PROB` | attack_drive_clearance.py | `{passive:0, normal:.5, aggressive:1}` | **S2c primary dial** — per-defender probability of even attempting the rotation, by defensive aggression. MC: blow-by demotion ≈ 0% / 60% / 82% across the three — **aggression, not corridor, is the cutoff lever**. |
| `HCO_DRIVE_SFX_FIRE_PROB` | skeleton_step_emitter.py | `0.5` | Cosmetic — chance a drive-start VO cue fires on an attack shot (seeded coin, separate salt from the braddock/sammy pick). ↓ = quieter/rarer drive cues. |

> **MC finding (2026-07-14, model — `scripts/s2_drive_monte_carlo.py`):** at the shipped `DRIVE_NEUTRAL_BAND=100`, even matchups land **A/B/C ≈ 21/50/21%** with ~8% contact; matchup lean shifts A↔C (offense-favored → 33/47/11, defense-favored → 11/47/34) while B stays broad by design. S2c blow-by demotion is driven by **aggression** (~60% normal / 82% aggressive), not corridor. Absolute rates depend on the mock attribute spread + model layout — trust the sweep deltas, and confirm the tier mix + drive FG% against the live baseline before committing.
