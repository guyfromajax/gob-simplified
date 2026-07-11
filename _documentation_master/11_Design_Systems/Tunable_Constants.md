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

The HCO pass-contest funnel runs on every HCO pass: **Gate 1** geometry (defender in the lane) → **Gate 2** attempt (aggression) → **Gate 3a** passer safety (clean pass?) → **Gate 3b** interceptor band (INTERCEPT / BAT_OOB / miss). HCO uses its own tiers/base (below); the composite weights + d6 roll live in `pass_contest.py` and are **shared with HCT/FCP**. Feature flag: `GOB_DYNAMIC_HCO_DEFENSE` (falsy = off).

Scores (both rolled once, `rand(1,6)`):
- `pass_score = ((PS·0.6 + CH·0.2 + IQ·0.2) + offensive_efficiency) × rand(1,6)` — offense (Gate 3a)
- `intercept_score = ((OD·0.6 + CH·0.2 + IQ·0.2) + defensive_efficiency) × rand(1,6)` — defender (Gate 3b)

`*_efficiency` = the team's `offensive_efficiency` / `defensive_efficiency` attribute (~−10..+10); it is added to the composite **and** subtracted from the bar/tiers, so a strong team is favored twice.

| Constant | File | Value | Effect |
|---|---|---|---|
| `INTERCEPT_ATTEMPT_PCT_BY_CALL` | phase_resolution.py | `{aggressive:80, normal:40, passive:0}` | **Gate 2** — % chance an in-lane defender actually *attempts* the pick, by `aggression_call`. Volume throttle before the contest. ↑ = more attempts feed Gate 3 = more picks. Passive never gambles. |
| `HCO_PASS_LANE_DIST_BY_AGGRESSION` | phase_resolution.py | `{passive:6.0, aggressive:5.0}` (normal = `randint(5,6)`/game) | **Gate 1** — perpendicular lane distance (grid) a defender must be within to count as "in the lane." ↑ = defenders contest from farther = more in-lane opportunities. Tighter than HCT/FCP (8.0). |
| `HCO_PASS_SAFETY_BASE` | phase_resolution.py | `175.0` | **Gate 3a** — clean-pass bar: passer is safe (no interception) if `pass_score > (BASE − offensive_efficiency)`. **↓ = passer safer = FEWER picks; ↑ = harder to complete = MORE picks.** (Shared HCT/FCP default: 200.) |
| `HCO_PASS_INTERCEPT_TIER_HI` | phase_resolution.py | `200.0` | **Gate 3b** — INTERCEPT (steal + TO) if `intercept_score > (HI − defensive_efficiency)`. ↓ = more steals. (Shared HCT/FCP default: 250.) |
| `HCO_PASS_INTERCEPT_TIER_MID` | phase_resolution.py | `170.0` | **Gate 3b** — BAT_OOB (deflected out, offense retains, no stats) if `intercept_score > (MID − defensive_efficiency)` and ≤ HI; else the pass completes (miss). ↓ = more deflections. (Shared HCT/FCP default: 200.) |
| `PASS_INTERCEPT_OD_WEIGHT` / `_CH_WEIGHT` / `_IQ_WEIGHT` | pass_contest.py | `0.6 / 0.2 / 0.2` | Interceptor composite weights (defender OD / CH / IQ). Shared. |
| `PASS_SAFETY_PS_WEIGHT` / `_CH_WEIGHT` / `_IQ_WEIGHT` | pass_contest.py | `0.6 / 0.2 / 0.2` | Passer composite weights (PS / CH / IQ). Shared. |
| `PASS_INTERCEPT_ROLL_MIN` / `_MAX` | pass_contest.py | `1 / 6` | The `rand(min,max)` multiplier on both composites (3a and 3b). Wider band = more variance in who beats the bar. Shared. |
| `PASS_IQ_ANTICIPATION_MAX_SEC` | pass_contest.py | `0.15` | **Gate 1 (temporal)** — max reaction head-start (game-seconds, scaled by IQ/100) a defender gets in the ball's arrival-time race. ↑ = defenders reach more lanes in time. Shared. |
| `PASS_LANE_DIST` | pass_contest.py | `8.0` | HCT/FCP lane distance + the shared param default. HCO overrides it via `HCO_PASS_LANE_DIST_BY_AGGRESSION`. |
