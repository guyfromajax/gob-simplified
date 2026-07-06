"""Tunable constants for dead-ball turnover fumble micro-animation."""

from BackEnd.constants.announcement_constants import ANNOUNCEMENT_FREEZE_HOLD_MS

# Render-space stumble (FE mirrors defaults in animation_config.js flourish.fumble)
FUMBLE_MAG_PX = 11.0
FUMBLE_FREQ_HZ = 6.0
FUMBLE_WALL_CLOCK_MS = 660

# Whistle headline hold after stumble completes (wall ms)
FUMBLE_ANNOUNCE_HOLD_MS = ANNOUNCEMENT_FREEZE_HOLD_MS
DEAD_BALL_FUMBLE_WHISTLE_SFX = "whistle-1-lowervol.wav"

DEAD_BALL_FUMBLE_HEADLINE = {
    "TRAVEL": "Travel!",
    "DOUBLE_DRIBBLE": "Double Dribble!",
}
