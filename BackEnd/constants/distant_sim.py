"""Distant franchise game sim tunables — single source of truth.

Keep in sync with:
  - _documentation_master/04_Franchise_Mode_Systems/Distant_Game_Sim_System.md
  - _documentation_master/projects/Distant_Sim_Tuning.md

Calibrated via scripts/distant_sim_monte_carlo.py (Phase 4, 2026-07-04, seed 42).
"""

# Chemistry clamp for record-momentum multiplier lookup
DISTANT_CHEMISTRY_MIN = 7
DISTANT_CHEMISTRY_MAX = 25

# Base score: prestige + int(DISTANT_TALENT_ATTR_MULT × talent_signal)
DISTANT_TALENT_ATTR_MULT = 0.20

# (exclusive upper bound on clamped chemistry, multiplier)
# Franchise init chemistry 7–10 → 8× (Phase 4 calibration).
DISTANT_MO_MULT_BANDS: list[tuple[int, int]] = [
    (11, 8),  # 7–10
    (16, 10),  # 11–15
    (21, 12),  # 16–20
    (25, 16),  # 21–24
    (26, 22),  # 25
]

# Compounding season momentum (FTD team_attributes.momentum_score)
DISTANT_MO_WIN_GAIN = 1.5
DISTANT_MO_LOSS_DECAY = 0.8
DISTANT_MO_SCORE_WEIGHT = 28
DISTANT_MO_STREAK_WIN_BONUS = 0.5  # per streak level above 2 on a win
DISTANT_MO_STREAK_LOSS_RESET = 2.0  # extra penalty when loss ends win streak >= 3

DISTANT_MOMENTUM_SCORE_MIN = -10
DISTANT_MOMENTUM_SCORE_MAX = 10

# Record-momentum streak bonus (additive on W−L momentum; uses distant_win/loss_streak FTD fields)
DISTANT_STREAK_MIN = 3
DISTANT_STREAK_BONUS = 22
DISTANT_STREAK_PENALTY = 18

# Tier amplification — applied after enough games for stable win pct (week gate)
DISTANT_TIER_WEEK_GATE = 5
# (minimum win pct inclusive, multiplier) — first match wins
DISTANT_TIER_BANDS: list[tuple[float, float]] = [
    (0.750, 7.00),
    (0.650, 3.25),
    (0.550, 1.00),
    (0.450, 0.45),
    (0.000, 0.25),
]

# Phase 5: promote ranked distant matchups to full CPU sim (both teams natl_rank ≤ cap).
# Set to 0 to disable. ~2–4 extra full sims/week when cap=15.
DISTANT_RANKED_FULLSIM_MAX_RANK = 15
