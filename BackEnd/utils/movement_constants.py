"""Shared movement/clock timing constants for backend clock sync."""

# Movement speed constants in grid-units per game-second.
SPEED_PASS = 20.0
SPEED_OPEN_COURT = 16.0
SPEED_TRANSITION = 12.0
SPEED_PRESS_TRAP = 10.0
SPEED_HALF_COURT = 5.0

# Action overhead constants in game-seconds.
OVERHEAD_PASS = 1.0
OVERHEAD_SHOT = 1.0

# Deterministic elapsed constants for non-movement outcomes.
ELAPSED_REBOUND = 2.0
ELAPSED_DEAD_BALL = 1.5
ELAPSED_FOUL = 1.0
ELAPSED_OPENING_TIP = 2.0

# Active runtime court dimensions (must match Phaser runtime config).
COURT_WIDTH_PX = 1229
COURT_HEIGHT_PX = 768
COURT_WIDTH_UNITS = 100
COURT_HEIGHT_UNITS = 50

# Frontend speed presets in px/sec. Backend receives one of these values per turn request.
GAME_SPEED_PX_PRESETS = {450, 550, 1000}
DEFAULT_GAME_SPEED_PX_PER_SEC = 450


def get_game_speed_px_per_sec(raw_speed):
    """Normalize inbound game speed to a safe px/sec value."""
    try:
        value = int(raw_speed)
    except (TypeError, ValueError):
        return DEFAULT_GAME_SPEED_PX_PER_SEC
    if value <= 0:
        return DEFAULT_GAME_SPEED_PX_PER_SEC
    return value
