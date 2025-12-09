"""
Fast Break System Constants

These constants define movement ranges, offsets, and coordinate ranges used throughout
the Fast Break system (DREB → Fast Break, Steal → Fast Break).

All coordinates are in HOME orientation (basket at x=90 for home, x=10 for away).
"""

# Ball Handler Movement (Defensive Stop / Shot Attempt)
BALL_HANDLER_MOVE_X_MIN = 5
BALL_HANDLER_MOVE_X_MAX = 10
BALL_HANDLER_MOVE_Y_RANGE = 3  # ±3 y-coords

# Stopper Positioning (Defensive Stop)
STOPPER_OFFSET_MIN = 1
STOPPER_OFFSET_MAX = 3

# Defender Positioning (Shot Attempt)
DEFENDER_X_OFFSET = 6  # Defender positioned 6 x-coords behind ball handler

# Rebounder Positioning
REBOUNDER_X_MIN = 40
REBOUNDER_X_MAX = 60
REBOUNDER_Y_RANGE = 6  # ±6 y-coords from starting position (defensive stop)

# Shot Attempt Rebounder Positioning
SHOT_ATTEMPT_REBOUNDER_Y_RANGE = 10  # ±10 y-coords from rim (shot attempt)

# Outlet Passer Movement
OUTLET_PASSER_MOVE_X = 7  # Moves forward 7 x-coords toward basket (+7 for home, -7 for away)

# Defensive Stop Determination
DEFENSIVE_STOP_Y_RANGE = 6  # Defender must be within ±6 y-coords of outlet receiver to force stop

