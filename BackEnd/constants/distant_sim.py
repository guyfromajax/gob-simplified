"""Distant franchise game sim tunables — single source of truth.

Keep in sync with:
  - _documentation_master/04_Franchise_Mode_Systems/Distant_Game_Sim_System.md
  - _documentation_master/projects/Distant_Sim_Tuning.md
"""

# Chemistry clamp for record-momentum multiplier lookup
DISTANT_CHEMISTRY_MIN = 7
DISTANT_CHEMISTRY_MAX = 25

# (exclusive upper bound on clamped chemistry, multiplier)
# Franchise init chemistry 7–10 → 3× (not 1×).
DISTANT_MO_MULT_BANDS: list[tuple[int, int]] = [
    (11, 3),  # 7–10
    (16, 4),  # 11–15
    (21, 5),  # 16–20
    (25, 6),  # 21–24
    (26, 8),  # 25
]

# Compounding season momentum (FTD team_attributes.momentum_score)
DISTANT_MO_WIN_GAIN = 1.5
DISTANT_MO_LOSS_DECAY = 0.8
DISTANT_MO_SCORE_WEIGHT = 8
DISTANT_MO_STREAK_WIN_BONUS = 0.5  # per streak level above 2 on a win
DISTANT_MO_STREAK_LOSS_RESET = 2.0  # extra penalty when loss ends win streak >= 3

DISTANT_MOMENTUM_SCORE_MIN = -10
DISTANT_MOMENTUM_SCORE_MAX = 10
