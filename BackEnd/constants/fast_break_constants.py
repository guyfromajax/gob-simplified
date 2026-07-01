"""
Fast Break System Constants

These constants define movement ranges, offsets, and coordinate ranges used throughout
the Fast Break system (DREB → Fast Break, Steal → Fast Break).

All coordinates are in HOME orientation (basket at x=91 for home, x=9 for away).
"""

import random

# Ball Handler Movement (Defensive Stop / Shot Attempt)
BALL_HANDLER_MOVE_X_MIN = 5
BALL_HANDLER_MOVE_X_MAX = 10
BALL_HANDLER_MOVE_Y_RANGE = 3  # ±3 y-coords

# Stopper Positioning (Defensive Stop)
STOPPER_OFFSET_MIN = 1
STOPPER_OFFSET_MAX = 3

# Shot Spot (when ball handler beats defender: shoot from near rim, not confrontation spot)
FB_SHOT_SPOT_X_MIN = 1  # Min x-distance from rim (spots)
FB_SHOT_SPOT_X_MAX = 4  # Max x-distance from rim (spots)
FB_SHOT_SPOT_Y_RANGE = 3  # ±y from rim center

# Defender Positioning (Shot Attempt)
# Primary shot defender sits two x-spots behind the shooter relative to the offense basket.
# Home offense attacks right, so defender x = shooter x - 2.
# Away offense attacks left, so defender x = shooter x + 2.
SHOT_DEFENDER_X_OFFSET = 2
SHOT_DEFENDER_Y_RANGE = 2  # Defender y within ±2 of shooter y
SECONDARY_SHOT_DEFENDER_Y_OFFSET = 3


def fast_break_shot_defender_end_coords(
    shooter_x: float,
    shooter_y: float,
    is_away_offense: bool,
) -> dict:
    """
    Grid destination for the primary fast-break shot contest defender vs the shooter's final spot (HOME grid).

    Rule:
    - Home offense: defender x = shooter x - SHOT_DEFENDER_X_OFFSET
    - Away offense: defender x = shooter x + SHOT_DEFENDER_X_OFFSET
    - Defender y = shooter y + uniform integer in [-SHOT_DEFENDER_Y_RANGE, SHOT_DEFENDER_Y_RANGE]
    """
    x_delta = SHOT_DEFENDER_X_OFFSET if is_away_offense else -SHOT_DEFENDER_X_OFFSET
    defender_x = float(shooter_x) + x_delta
    defender_x = int(max(4, min(97, round(defender_x))))
    defender_y_off = random.randint(-SHOT_DEFENDER_Y_RANGE, SHOT_DEFENDER_Y_RANGE)
    defender_y = int(max(1, min(49, round(float(shooter_y) + defender_y_off))))
    return {"x": defender_x, "y": defender_y}


def fast_break_secondary_shot_defender_end_coords(
    primary_defender_x: float,
    primary_defender_y: float,
    secondary_source_y: float,
) -> dict:
    """
    Grid destination for the secondary fast-break shot defender (beat-stopper path).

    Rule:
    - same x as the primary shot defender
    - y = primary defender y + 3 when the secondary defender starts below that y
      otherwise y = primary defender y - 3
    """
    defender_x = int(max(4, min(97, round(float(primary_defender_x)))))
    y_delta = (
        SECONDARY_SHOT_DEFENDER_Y_OFFSET
        if float(secondary_source_y) > float(primary_defender_y)
        else -SECONDARY_SHOT_DEFENDER_Y_OFFSET
    )
    defender_y = int(max(1, min(49, round(float(primary_defender_y) + y_delta))))
    return {"x": defender_x, "y": defender_y}


# Rebounder Positioning
REBOUNDER_X_MIN = 40
REBOUNDER_X_MAX = 60
REBOUNDER_Y_RANGE = 6  # ±6 y-coords from starting position (defensive stop)

# Shot Attempt Rebounder Positioning
SHOT_ATTEMPT_REBOUNDER_Y_RANGE = 10  # ±10 y-coords from rim (shot attempt)

# Outlet Passer Movement
OUTLET_PASSER_MOVE_X = 7  # Moves forward 7 x-coords toward basket (+7 for home, -7 for away)

# Defensive Stop Determination (legacy y-band — superseded by path cutoff for CR)
DEFENSIVE_STOP_Y_RANGE = 6  # Steal → FB: legacy reference; steal uses after_steal resolver
DEFENSIVE_STOP_Y_RANGE_DREB_OUTLET = 8  # Legacy y-band reference (path cutoff replaces geography gate)

# Unified drive-cutoff tuning (``cutoff_resolution.best_cutoff_on_drive``)
FB_CUTOFF_PATH_CORRIDOR_DREB = 14  # DREB/outlet — wider floor than HCT trap (~11 implicit)
FB_CUTOFF_PATH_CORRIDOR_STEAL = 11  # Legacy steal-entry path through resolve_fast_break_logic
FB_CUTOFF_DEFENDER_TIME_SLACK_DREB = 1.15  # Defenders get 15% arrival-time credit on DREB breaks
FB_CUTOFF_DEFENDER_TIME_SLACK_STEAL = 1.0

# FB Drive Cutoff & Stop Decision (June 2026 — see FB_Drive_Cutoff_Work_Plan.md)
FB_DRIVE_CUTOFF_PATH_CORRIDOR = 14
FB_DRIVE_CUTOFF_TIME_SLACK = 1.0
FB_SHOOT_GEO_RADIUS = 24  # Euclidean to attacking basket OR shoot spot-label exception
FB_POS_O_SHIMMY_MAGNITUDE = 2
FB_CONTEST_MAX_X_TRAIL = 3  # FB-only; pairs with CONTEST_EUCLIDEAN_RADIUS (11)

FB_SHOOT_GEO_SPOT_LABELS = frozenset(
    {"key", "upper midWing", "lower midWing"},
)
FB_PASS_GEO_SPOT_LABELS = frozenset(
    {
        "key",
        "upper midWing",
        "lower midWing",
        "upper wing",
        "lower wing",
        "upper midCorner",
        "lower midCorner",
        "upper corner",
        "lower corner",
    },
)

# Steal Entry Movement (Steal → Fast Break)
STEAL_ENTRY_MOVE_X_MIN = 5  # Minimum x movement toward basket
STEAL_ENTRY_MOVE_X_MAX = 10  # Maximum x movement toward basket
STEAL_ENTRY_MOVE_Y_RANGE = 4  # ±4 y-coords
STEAL_ENTRY_Y_MIN = 3  # Minimum y-coord (clamped)
STEAL_ENTRY_Y_MAX = 47  # Maximum y-coord (clamped)

# Steal HCO Setup Movement (Steal → HCO)
STEAL_HCO_SETUP_MOVE_X_MIN = 3  # Minimum x movement away from basket (ball handler)
STEAL_HCO_SETUP_MOVE_X_MAX = 7  # Maximum x movement away from basket (ball handler)
STEAL_HCO_SETUP_MOVE_Y_RANGE = 3  # ±3 y-coords (ball handler)
STEAL_HCO_SETUP_Y_MIN = 3  # Minimum y-coord (clamped)
STEAL_HCO_SETUP_Y_MAX = 47  # Maximum y-coord (clamped)

# Other Players Movement (Steal HCO Setup - all 9 other players)
STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN = 15  # Minimum x movement toward new offense basket
STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX = 30  # Maximum x movement toward new offense basket
STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_Y_RANGE = 6  # ±6 y-coords
STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MIN = 4  # Minimum y-coord (clamped)
STEAL_HCO_SETUP_OTHER_PLAYERS_Y_MAX = 46  # Maximum y-coord (clamped)
