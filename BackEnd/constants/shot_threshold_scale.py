"""
Canonical team shot_threshold attribute scale.

Lower raw values = easier makes (golf score). UI pills center at MID: decreasing
raw value fills positively to the right; increasing fills negatively to the left.

Change MIN (and only MIN) to retune the scale; MAX, MID, and HALF_SPAN derive from
SPAN. Keep FrontEnd/static/js/shared/teamShotThresholdScale.js in sync.
"""

SPAN = 200
HALF_SPAN = SPAN // 2  # 100 — max pill deviation from center in either direction

MIN = 50
MAX = MIN + SPAN  # 250
MID = MIN + HALF_SPAN  # 150

# Score-balancing one-turn overrides sit 20 below min / 20 below max.
BALANCING_MARGIN = 20
BALANCING_TRAILING = MIN - BALANCING_MARGIN  # 30
BALANCING_LEADING = MAX - BALANCING_MARGIN  # 230

# Franchise new-team init: slightly better than league average (10–20 below MID).
FRANCHISE_INIT_LO = MID - 20  # 130
FRANCHISE_INIT_HI = MID - 10  # 140

# FTE tutorial forced make / average opponent (fte_inject_state.md §3).
TUTORIAL_USER = MIN  # 50 — forced make
TUTORIAL_COMPUTER = MID  # 150 — winnable opponent

# Rim-runner custom corner FB threshold base.
FAST_BREAK_CORNER_THRESHOLD_BASE = MAX - BALANCING_MARGIN  # 230

# Tournament seed shot_threshold ranges (seed 1 = best shooters, 8 = worst).
TOURNAMENT_SEED_ST_RANGES = {
    1: (MIN, MID),
    2: (MIN, MID + 50),
    3: (MIN, MID + 50),
    4: (MIN, MID + 50),
    5: (MID - 50, MAX),
    6: (MID - 50, MAX),
    7: (MID - 50, MAX),
    8: (MID, MAX),
}


def team_attr_range():
    """(min, max) clamp for stored team shot_threshold."""
    return (MIN, MAX)


def clamp(value):
    """Clamp a raw shot_threshold to the team attribute range."""
    return max(MIN, min(MAX, int(value)))


def pill_deviation(raw):
    """UI pill fill axis: positive when raw is below MID (better shooting)."""
    return MID - int(raw)


def to_public_dict():
    """JSON-serializable scale for API / frontend parity tests."""
    return {
        "min": MIN,
        "max": MAX,
        "mid": MID,
        "span": SPAN,
        "half_span": HALF_SPAN,
    }
