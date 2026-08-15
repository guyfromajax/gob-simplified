"""EOG team-attribute band configuration — the single source of truth for band
thresholds, delta ranges, and label strings.

Imported by `BackEnd/eog_attr_rules.py` (the band-selection logic that production
runs) and `scripts/team_attr_season_dry_run.py` (the model harness). The labels
also flow into the `[EOG-BAND]` instrumentation. Keep NO band vocabulary or
threshold literals anywhere else — divergent copies are how the drifted-duplicate
bug happened (EOG Structural Pass, Task 7/8).

LEVELING PASS (2026-08-11): thresholds re-cut to measured p33/p67 and midpoints
retuned against the identity season (36,608 team-game rows). Verify any change with

    python scripts/eog_band_tuner.py <season log> --validate     # must be 100%
    python scripts/eog_band_tuner.py <season log> --config <candidate>

The tuner mirrors eog_attr_rules.py and computes expected drift offline in seconds —
do NOT re-run a 2-hour season to evaluate a band change.

TWO CONSTANTS ARE MARKED ⚠️ INTERIM below (FG_PCT_*, OFF_CONC_*). They are cut
against inputs we already plan to change; each records what it was cut against and
its measured value at cut time. A material shift in either input requires re-running
the tuner — the cuts will otherwise invert the problem they solved.

discipline and fight deltas are DELIBERATELY UNTUNED — their season drift is
training-driven, not EOG-driven. See projects/bugs.md.

Design notes (see EOG Structural Pass):
- Concentration reward/middle/penalty deltas average ~-0.5/game ≈ -13/season at
  roughly even thirds — chosen to cancel training's ~+13/season at 1 point.
- The volume ladder deltas do NOT have that property (~-0.1/game); they will
  likely deepen in the leveling phase. Left as specced for this pass.
- fb/pt concentration thresholds are higher than offense's because 3-4 plays floor
  max_share at 0.33/0.25 (offense's 0.30 reward would never fire). Recorded
  inconsistency: FB reward 0.45 = 1.35x its 0.334 floor, P/T reward 0.50 = 2.0x
  its 0.25 floor — more permissive; not principled, revisit after archetypes.
- P/T concentration is built over the 3 HCT variant `A` counts + `fcp_used` (NOT
  fcp_press_plays variant A, whose counter is dead — see eog_attr_rules). Valid
  only while FCP has one live variant; revisit when FCP variants expand.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────────────────────────────────────

# shot_threshold — team FG% bands (golf score: lower = better shooting mindset)
#
# ⚠️ INTERIM — RE-DERIVE BEFORE REUSING. The whole block below is calibrated against ONE
# season's measured FG%-vs-shot_threshold response, and that response is SEASON-SPECIFIC
# (see the corollary). The shot-tuning pass invalidates it by construction.
#
# HOW THIS ATTRIBUTE DIFFERS FROM THE OTHER TEN
# ---------------------------------------------
# shot_threshold is the only attribute whose band INPUT it also DETERMINES. It is the bar a
# shot must clear, so it sets team FG%, and FG% selects the band that moves it. That loop is
# INTENDED — it is the compounding effect of game performance — so the band is not a defect
# and must not be removed from EOG or inverted. The fault was magnitude only: at ±85/season
# on a 0-200 range it saturated inside a season (123 of 128 teams railed at the ceiling).
#
# Because the loop compounds, this attribute is tuned to a VARIANCE target, not a mean one:
# near-neutral centre, spread that grows meaningfully, few teams reaching either rail. The
# other ten want slightly-positive mean drift; this one does not.
#
# THE COROLLARY — what a future tuner will get wrong first
# --------------------------------------------------------
#   * GAIN sets SPEED. BAND POSITION sets WHERE TEAMS SETTLE.
#   * The neutral band must sit BELOW the equilibrium FG% so the negative branch carries
#     more mass and offsets training's steady upward push (+56.4/season measured). Centring
#     the neutral band ON the equilibrium makes training dominate and every team drifts up.
#   * The equilibrium FG% is SEASON-SPECIFIC. RE-DERIVE IT BEFORE RE-CUTTING AND NEVER
#     REUSE A PREVIOUS SEASON'S FIT.
#
# Evidence for that last point: fitting FG% = a + b*shot_threshold per season gives
# b = -0.1125 (baseline), -0.0691 (identity), -0.1413 (verification) — non-overlapping 95%
# CIs. Pooling them produces a chord between clouds at different equilibria, not a response
# curve. Binning by shot_threshold shows the LEVEL shifts too: mean cross-season spread
# 6.42pp, max 9.15pp (at S=80-99: baseline 43.7%, identity 40.1%, verification 39.0%).
#
# CURRENT CALIBRATION (re-cut 2026-08-14 for the -10..190 scale)
#   basis      FG% = 51.25 - 0.14126 * shot_threshold, residual sd 7.67pp. The fit is
#              SCALE-INDEPENDENT — shot_threshold is compared absolutely in
#              `made = shot_score >= shot_threshold` — but the OPERATING POINT is not:
#              at the current init 85-95 the fitted equilibrium is 38.5% FG.
#   ⚠️ THIS IS WHY A SCALE MOVE FORCES A BAND RE-CUT. Cut at 24/36 for init 95-105, then
#      left alone across the two scale moves, these bands drifted teams -28/season instead
#      of ~0: FG at the new init sat ABOVE the high cut, so most team-games took the
#      negative delta and compounded downward. The -30..170 calibration was 26/40.
#      See the scale-change checklist in 00_Operations/Shot_Threshold_Scale_Tuning.md.
#   simulated  1,000 x (26 weeks x 128 teams), ACTUAL integer band ranges and clamps,
#              from init 85-95, bootstrapping the 3,330 measured residuals:
#              mean 90.0, sd 20.5, drift -0.05, ZERO rails across 128,000 team-seasons.
#   chosen      22/37. Nearby 23/37 drifted +1.01 with one rail; 24/37 drifted +2.43
#              with eight rails. Re-fit from a fresh season if engine/roster inputs change.
FG_PCT_HIGH = 37
FG_PCT_MID = 22

# discipline — team (F+TO) vs opponent (F+TO) + buffer
DISCIPLINE_OPP_BUFFER = 8

# rebound_modifier — differential (treb - opp_treb) band boundaries.
# >= BIG: dominant; MID..BIG-1: solid; within ±EVEN: even; mirror below.
# Widened from 8/4/3: at those cuts 65.5% of team-games landed in the two extreme
# bands (|diff| >= 8), so the ladder's tails dominated the drift. Measured p20/p80
# of the differential are -14/+14, so 14/7/3 gives roughly even fifths.
REBOUND_BIG_MARGIN = 14
REBOUND_MID_MARGIN = 7
REBOUND_EVEN_MARGIN = 3

# offensive_efficiency — concentration (largest play's share of offensive possessions)
#
# ⚠️ INTERIM — CUT AGAINST A CAPPED INPUT.
#   cut against : max_share over 3,328 team-games (identity season, 2026-08-10)
#   measured    : mean 0.273, median 0.265, p33 0.233, p67 0.300
#   cap          : the playbook generator ceilings any single set play at 20% once
#                  a team runs 4+ set plays — a DEFERRED fix. The observed spread
#                  is therefore compressed by the generator, not by coaching.
# At 0.30/0.45 the old cuts put 68% in the reward band and 2% in the penalty band.
# WHEN THE CONCENTRATION CAP IS LIFTED these cuts become far too tight.
# Re-run scripts/eog_band_tuner.py against a fresh season log and re-cut.
OFF_CONC_REWARD = 0.23
OFF_CONC_MIDDLE = 0.30

# defensive_efficiency — max share among HCO defense rows (unchanged this pass)
# Re-cut to measured p33/p67 (0.424 / 0.569); at 0.39/0.49 the penalty band took 51%.
DEF_MAX_SHARE_REWARD = 0.42
DEF_MAX_SHARE_MIDDLE = 0.57

# fb_efficiency — concentration over CR/RR/Triangle (after_steal excluded)
# Re-cut to measured p33/p67 (0.444 / 0.533).
FB_CONC_REWARD = 0.44
FB_CONC_MIDDLE = 0.53

# pt_efficiency — concentration over [3 HCT variant A's + fcp_used]
# Re-cut to measured p33/p67 (0.500 / 0.700).
PT_CONC_REWARD = 0.50
PT_CONC_MIDDLE = 0.70

# fb_opp_modifier — opponent fast-break VOLUME (after_steal excluded)
FB_OPP_HEALTHY_BAND = (7, 13)   # (lo, hi) inclusive; measured p33/p67 = 7/12

# pt_opp_modifier — opponent press/trap VOLUME (hct_used + fcp_used)
# Opponent pressure volume is strongly BIMODAL once identity is live: press-vision
# teams generate a median of 15 pressure possessions, everyone else 4-6 (measured
# 2026-08-10, 3.0x separation, press p10 = 9). The old 7-14 band sat in the valley
# between the two modes, penalising commitment — 53.7% of press games scored as
# overuse. 9-20 makes the healthy band mean "you faced a real press", which is what
# an opponent-pressure modifier should reward.
PT_HEALTHY_BAND = (9, 20)

# team_chemistry — national-rank thresholds (lower rank int = better)
CHEM_TOP_RANK = 10
CHEM_LOW_RANK_MIN = 100
CHEM_LOW_RANK_MAX = 128

# ─────────────────────────────────────────────────────────────────────────────
# Band delta ranges — (lo, hi) for random.randint. rebound is /100 (see rules).
# ─────────────────────────────────────────────────────────────────────────────

# shot_threshold
# Narrowed alongside the FG threshold re-cut. Symmetric about the middle band so
# EOG nets ~0 across the league; shot_threshold's residual season drift is now
# training-driven, not EOG-driven. Label names still say 50/45 — they are band
# IDs in the instrumentation vocabulary, not thresholds.
# gain 6: means -4 / 0 / +4 across the three bands. Label names still say 50/45 — they are
# band IDs in the instrumentation vocabulary, not thresholds.
ST_FG_GT_50 = (-6, -2)
ST_FG_45_TO_50_WIN = (-1, 0)
ST_FG_45_TO_50_LOSS = (0, 1)
ST_FG_LE_45 = (2, 6)

# discipline
# DISC_ABOVE deepened -1..-2 -> -1..-3 so EOG nets +10/season instead of +14, landing
# discipline's combined drift with the rest of the pack once training was corrected
# from -91.6 (measured) to -4.7.
DISC_BELOW = (1, 2)
DISC_ABOVE = (-3, -1)
DISC_EQUAL = (-1, 0)

# fight
FIGHT_WIN = (0, 2)
FIGHT_LOSS = (-2, 0)

# rebound_modifier (5-band ladder; values are hundredths, applied as /100)
#
# NAMES ARE DELIBERATELY THRESHOLD-FREE. The previous set (REB_OUTREBOUND_GT_8,
# REB_OUTREBOUND_4_7 ...) baked margins into the identifiers and then went stale:
# `outrebound_gt_8` actually fired at a differential of 14 and `outrebound_4_7` at
# 7-13. Same failure as `fg_gt_50` firing at 40% FG. The margins live in
# REBOUND_BIG_MARGIN / REBOUND_MID_MARGIN / REBOUND_EVEN_MARGIN and are meant to be
# re-tuned; the names must survive that.
#
# NARROWED 2026-08-14. On a 0.0-1.0 scale the old ranges moved up to 0.14 in a single
# game against training's ~0.04 per WEEK, so EOG was the dominant term and a short
# rebounding run could cross half the range. Measured at week 13-27 of two seasons:
# 28-31 teams sat at exactly 1.0 and 17-30 at exactly 0.0 — roughly 40% of the league
# railed, after which the attribute carries no information.
#
# Each band is now tighter and the two outer bands no longer overlap the middle ones,
# so a blowout is still worth more than a solid edge but cannot lurch the attribute.
REB_DOMINANT = (5, 10)        # +0.05 .. +0.10   outrebounded them by BIG_MARGIN+
REB_STRONG = (1, 5)           # +0.01 .. +0.05   by MID_MARGIN..BIG_MARGIN
REB_EVEN = (-3, 3)            # -0.03 .. +0.03   within EVEN_MARGIN
REB_WEAK = (-8, -4)           # -0.08 .. -0.04   outrebounded by MID..BIG
REB_DOMINATED = (-12, -8)     # -0.12 .. -0.08   outrebounded by BIG_MARGIN+

# concentration bands shared by offense / fb / pt
# Shifted up one notch. At the OLD thresholds these averaged -0.5/game; once the
# thresholds are cut at even thirds that becomes -13/season, over-cancelling
# training's ~+7.5 and leaving every concentration attribute net negative.
CONC_REWARD_DELTA = (0, 2)
CONC_MIDDLE_DELTA = (-1, 1)
CONC_PENALTY_DELTA = (-2, -1)
CONC_ATROPHY_DELTA = (-1, 0)        # zero-volume atrophy (fb/pt only)

# defensive_efficiency (same shape as concentration reward/middle/penalty)
DEF_REWARD_DELTA = (0, 2)
DEF_MIDDLE_DELTA = (-1, 1)
DEF_PENALTY_DELTA = (-2, -1)

# volume ladder (fb_opp / pt_opp)
VOL_ATROPHY_DELTA = (-1, 0)
VOL_UNDER_DELTA = (-1, 0)
VOL_HEALTHY_DELTA = (0, 1)
VOL_OVER_DELTA = (-1, 0)
# (unchanged — the volume ladders land in target once their bands are re-cut)

# team_chemistry
# Lifted across the board. The loss bands were deep enough that ALL 128 teams hit
# the 7 floor by week 2 on an 18-point range (7-25). Losing to a stronger team no
# longer costs chemistry outright; only losing to a much weaker one does.
CHEM_BEAT_LOWER = (0, 2)
CHEM_BEAT_HIGHER_NON_TOP10 = (1, 3)
CHEM_BEAT_TOP10 = (2, 5)
CHEM_LOSE_TO_TOP10 = (0, 1)
CHEM_LOSE_TO_HIGHER_NON_TOP10 = (-1, 1)
CHEM_LOSE_TO_100_128 = (-4, -2)
CHEM_LOSE_TO_OTHER_LOWER = (-2, -1)

# ─────────────────────────────────────────────────────────────────────────────
# Band label vocabulary (single source). {label: (lo, hi)} per attribute — the
# dry-run harness picks a band from these; eog_attr_rules emits the same labels.
# ─────────────────────────────────────────────────────────────────────────────

EOG_BANDS = {
    "shot_threshold": [
        ("fg_gt_50", ST_FG_GT_50),
        ("fg_45_to_50", (ST_FG_45_TO_50_WIN[0], ST_FG_45_TO_50_LOSS[1])),  # W/L-narrowed at roll time
        ("fg_le_45", ST_FG_LE_45),
    ],
    "discipline": [
        ("below_opp_plus_8", DISC_BELOW),
        ("above_opp_plus_8", DISC_ABOVE),
        ("equal_buffered", DISC_EQUAL),
    ],
    "rebound_modifier": [
        ("reb_dominant", REB_DOMINANT),
        ("reb_strong", REB_STRONG),
        ("reb_even", REB_EVEN),
        ("reb_weak", REB_WEAK),
        ("reb_dominated", REB_DOMINATED),
    ],
    "offensive_efficiency": [
        ("conc_le_30", CONC_REWARD_DELTA),
        ("conc_le_45", CONC_MIDDLE_DELTA),
        ("conc_gt_45", CONC_PENALTY_DELTA),
    ],
    "defensive_efficiency": [
        ("def_max_le_39", DEF_REWARD_DELTA),
        ("def_max_le_49", DEF_MIDDLE_DELTA),
        ("def_max_gt_49", DEF_PENALTY_DELTA),
    ],
    "fb_efficiency": [
        ("fb_atrophy", CONC_ATROPHY_DELTA),
        ("fb_conc_le_45", CONC_REWARD_DELTA),
        ("fb_conc_le_60", CONC_MIDDLE_DELTA),
        ("fb_conc_gt_60", CONC_PENALTY_DELTA),
    ],
    "pt_efficiency": [
        ("pt_atrophy", CONC_ATROPHY_DELTA),
        ("pt_conc_le_50", CONC_REWARD_DELTA),
        ("pt_conc_le_75", CONC_MIDDLE_DELTA),
        ("pt_conc_gt_75", CONC_PENALTY_DELTA),
    ],
    "fb_opp_modifier": [
        ("fb_opp_atrophy", VOL_ATROPHY_DELTA),
        ("fb_opp_under", VOL_UNDER_DELTA),
        ("fb_opp_healthy", VOL_HEALTHY_DELTA),
        ("fb_opp_over", VOL_OVER_DELTA),
    ],
    "pt_opp_modifier": [
        ("pt_opp_atrophy", VOL_ATROPHY_DELTA),
        ("pt_opp_under", VOL_UNDER_DELTA),
        ("pt_opp_healthy", VOL_HEALTHY_DELTA),
        ("pt_opp_over", VOL_OVER_DELTA),
    ],
}

# W/L-gated (fight) and rank-gated (chemistry) — the harness handles these specially.
FIGHT_BANDS = {
    True: ("win", FIGHT_WIN),
    False: ("loss", FIGHT_LOSS),
}

CHEMISTRY_BANDS = {
    True: [
        ("beat_lower_ranked", CHEM_BEAT_LOWER),
        ("beat_higher_non_top10", CHEM_BEAT_HIGHER_NON_TOP10),
        ("beat_top10", CHEM_BEAT_TOP10),
    ],
    False: [
        ("lose_to_top10", CHEM_LOSE_TO_TOP10),
        ("lose_to_higher_non_top10", CHEM_LOSE_TO_HIGHER_NON_TOP10),
        ("lose_to_100_128", CHEM_LOSE_TO_100_128),
        ("lose_to_other_lower", CHEM_LOSE_TO_OTHER_LOWER),
    ],
}
