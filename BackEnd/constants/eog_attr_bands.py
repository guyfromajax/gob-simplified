"""EOG team-attribute band configuration — the single source of truth for band
thresholds, delta ranges, and label strings.

Imported by `BackEnd/eog_attr_rules.py` (the band-selection logic that production
runs) and `scripts/team_attr_season_dry_run.py` (the model harness). The labels
also flow into the `[EOG-BAND]` instrumentation. Keep NO band vocabulary or
threshold literals anywhere else — divergent copies are how the drifted-duplicate
bug happened (EOG Structural Pass, Task 7/8).

ALL NUMBERS HERE ARE PROVISIONAL. This pass lands mechanism, not magnitude; the
leveling phase retunes after re-measuring with CPU archetypes. Change values here,
never inline in a branch.

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
FG_PCT_HIGH = 50
FG_PCT_MID = 45

# discipline — team (F+TO) vs opponent (F+TO) + buffer
DISCIPLINE_OPP_BUFFER = 8

# rebound_modifier — differential (treb - opp_treb) band boundaries.
# >= BIG: dominant; MID..BIG-1: solid; within ±EVEN: even; mirror below.
REBOUND_BIG_MARGIN = 8
REBOUND_MID_MARGIN = 4
REBOUND_EVEN_MARGIN = 3

# offensive_efficiency — concentration (largest play's share of offensive possessions)
OFF_CONC_REWARD = 0.30
OFF_CONC_MIDDLE = 0.45

# defensive_efficiency — max share among HCO defense rows (unchanged this pass)
DEF_MAX_SHARE_REWARD = 0.39
DEF_MAX_SHARE_MIDDLE = 0.49

# fb_efficiency — concentration over CR/RR/Triangle (after_steal excluded)
FB_CONC_REWARD = 0.45
FB_CONC_MIDDLE = 0.60

# pt_efficiency — concentration over [3 HCT variant A's + fcp_used]
PT_CONC_REWARD = 0.50
PT_CONC_MIDDLE = 0.75

# fb_opp_modifier — opponent fast-break VOLUME (after_steal excluded)
FB_OPP_HEALTHY_BAND = (5, 10)   # (lo, hi) inclusive healthy band

# pt_opp_modifier — opponent press/trap VOLUME (hct_used + fcp_used)
PT_HEALTHY_BAND = (7, 14)       # median measured 6.0 → likely penalizes ~56% for now

# team_chemistry — national-rank thresholds (lower rank int = better)
CHEM_TOP_RANK = 10
CHEM_LOW_RANK_MIN = 100
CHEM_LOW_RANK_MAX = 128

# ─────────────────────────────────────────────────────────────────────────────
# Band delta ranges — (lo, hi) for random.randint. rebound is /100 (see rules).
# ─────────────────────────────────────────────────────────────────────────────

# shot_threshold
ST_FG_GT_50 = (-10, -5)
ST_FG_45_TO_50_WIN = (-5, 0)
ST_FG_45_TO_50_LOSS = (0, 5)
ST_FG_LE_45 = (5, 10)

# discipline
DISC_BELOW = (1, 2)
DISC_ABOVE = (-2, -1)
DISC_EQUAL = (-1, 0)

# fight
FIGHT_WIN = (0, 2)
FIGHT_LOSS = (-2, 0)

# rebound_modifier (5-band ladder; values are hundredths, applied as /100)
REB_OUTREBOUND_GT_8 = (2, 12)       # +0.02 .. +0.12
REB_OUTREBOUND_4_7 = (0, 5)         # 0.00 .. +0.05
REB_WITHIN_3 = (-8, -2)             # -0.02 .. -0.08  (stored lo<hi; negative)
REB_OUTREBOUNDED_4_7 = (-10, -5)    # -0.05 .. -0.10
REB_OUTREBOUNDED_GT_8 = (-25, -15)  # -0.15 .. -0.25

# concentration bands shared by offense / fb / pt
CONC_REWARD_DELTA = (0, 1)
CONC_MIDDLE_DELTA = (-1, 0)
CONC_PENALTY_DELTA = (-2, -1)
CONC_ATROPHY_DELTA = (-1, 0)        # zero-volume atrophy (fb/pt only)

# defensive_efficiency (same shape as concentration reward/middle/penalty)
DEF_REWARD_DELTA = (0, 1)
DEF_MIDDLE_DELTA = (-1, 0)
DEF_PENALTY_DELTA = (-2, -1)

# volume ladder (fb_opp / pt_opp)
VOL_ATROPHY_DELTA = (-1, 0)
VOL_UNDER_DELTA = (-1, 0)
VOL_HEALTHY_DELTA = (0, 1)
VOL_OVER_DELTA = (-1, 0)

# team_chemistry
CHEM_BEAT_LOWER = (0, 1)
CHEM_BEAT_HIGHER_NON_TOP10 = (1, 2)
CHEM_BEAT_TOP10 = (2, 4)
CHEM_LOSE_TO_TOP10 = (-1, 0)
CHEM_LOSE_TO_HIGHER_NON_TOP10 = (-2, 0)
CHEM_LOSE_TO_100_128 = (-5, -3)
CHEM_LOSE_TO_OTHER_LOWER = (-3, -2)

# Historical distant-sim uniform band (retained until the EOG cleanup phase).
DISTANT_UNIFORM = (-2, 1)

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
        ("outrebound_gt_8", REB_OUTREBOUND_GT_8),
        ("outrebound_4_7", REB_OUTREBOUND_4_7),
        ("within_3", REB_WITHIN_3),
        ("outrebounded_4_7", REB_OUTREBOUNDED_4_7),
        ("outrebounded_gt_8", REB_OUTREBOUNDED_GT_8),
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

# The 6 efficiency attributes that use usage/concentration measures (non-distant).
# In distant games all six draw the single DISTANT_UNIFORM band instead.
DISTANT_UNIFORM_ATTRS = (
    "offensive_efficiency", "defensive_efficiency", "fb_efficiency",
    "fb_opp_modifier", "pt_efficiency", "pt_opp_modifier",
)
