"""Tunable constants for shot micro-movements (v1 defaults from design sandbox)."""

# Contest margin thresholds (offense pre-defense vs raw primary defense roll)
CONTEST_OFFENSE_WIN_THRESHOLD = 150.0
CONTEST_DEFENSE_WIN_THRESHOLD = -150.0

# Footwork geometry
MICRO_STEP_GRID = 4.5
JAB_STEP_GRID = 2.0
JAB_COUNTER_MULTIPLIER = 2.0

# Defender track / contact gaps (grid units)
DEFENDER_TRACK_GAP = 2.4
DEFENDER_GLUE_GAP = DEFENDER_TRACK_GAP * 0.3
DEFENDER_STICK_GAP = DEFENDER_TRACK_GAP * 0.62
DEFENDER_WALL_GAP = DEFENDER_TRACK_GAP * 0.5
DEFENDER_GLUE_CLAMP_MIN = 1.3

# Muscle-loss completion fraction (defense_win bucket A)
MUSCLE_LOSS_COMPLETION = 0.11

# Step timing floors (game-seconds)
MICRO_MOVE_STEP_T_FLOOR = 0.15
MICRO_FLOURISH_BEAT_T = 0.4

# Outside arc occupancy: teammate within this euclidean distance blocks a spot
ARC_SPOT_OCCUPIED_RADIUS = 3.0

# Ordered arc spots (low y → high y) for adjacent dribble targets — home orientation
OUTSIDE_ARC_SPOT_ORDER = (
    "lower corner",
    "lower midCorner",
    "lower wing",
    "lower midWing",
    "key",
    "upper midWing",
    "upper wing",
    "upper midCorner",
    "upper corner",
)

MOVEMENT_POOL_BY_SHOT_TYPE = {
    "inside": (
        "strong_inside",
        "fade_away",
        "jab_step",
        "under_and_up",
        "straight_inside",
    ),
    "attack": (
        "strong_attack",
        "pullup_attack",
    ),
    "outside": (
        "set",
        "set_pump",
        "dribble_shoot",
        "dribble_pump_shoot",
        "pump_dribble_shoot",
    ),
}

OUTSIDE_MOVING_FAMILIES = frozenset({
    "dribble_shoot",
    "dribble_pump_shoot",
    "pump_dribble_shoot",
})

OUTSIDE_STATIC_FALLBACK_FAMILIES = ("set", "set_pump")

# Shooter displacement on the terminal [shoot] step above this → travel+shoot
# (FB drive / sprint-to-spot). Micro inserts after travel; in-place shoots replace.
TRAVEL_SHOOT_MIN_GRID = 1.5
