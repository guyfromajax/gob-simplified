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
PUMP_FAKE_FLOURISH_BEAT_T = 1.05  # pump_fake micro beat — aligns ~380ms wall at 1× playback

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

# --- Dunk micro-animation (registered; not in MOVEMENT_POOL — selection is separate) ---
DUNK_FAMILIES = frozenset({"dunk", "drive_dunk"})
DUNK_APPROACH_HOME = {"x": 88.0, "y": 25.0}  # just outside home rim (91)
DUNK_APPROACH_AWAY = {"x": 12.0, "y": 25.0}  # mirror via x → 100 − x
DUNK_WALL_CLOCK_MIN_MS = 640.0
DUNK_WALL_CLOCK_RISE_SLAM_MS = 300.0
DUNK_CLOCK_MS_PER_GAME_SEC = 350.0  # mirrors FE gameClock.tickMs default
DUNK_MOVE_SPOTS_STRONG = 1.0  # × MICRO_STEP_GRID toward rim
DUNK_MOVE_SPOTS_DRIVE = 2.0
# Overridable on step stamp; FE defaults in animation_config.js dunk block
DUNK_RISE_PX = 22.0
DUNK_RATTLE_MAG_PX = 6.0
DUNK_RATTLE_MS = 280.0
DUNK_BALL_RAISE = 0.35  # fraction of player sprite display height above head

# --- Dunk selection (Shot_System.md § Dunk Selection) ---
DUNK_MARGIN_THRESHOLD = 100.0
DUNK_LOCATION_MAX_GRID = 10.0
DUNK_DRIVE_MAX_DIST = 8.0  # ≤ this → family "dunk"; else "drive_dunk"
DUNK_AG_THRESHOLD_DIST_9 = 50.0
DUNK_AG_THRESHOLD_DIST_10 = 75.0

# Height (inches) → feasibility scale (roll = randint(1, 100))
DUNK_HEIGHT_SCALE_BY_INCH = {
    **{h: 0 for h in range(50, 69)},
    69: 1, 70: 1, 71: 1,
    72: 2, 73: 5, 74: 7, 75: 10, 76: 12, 77: 15,
    78: 17, 79: 18, 80: 20, 81: 22, 82: 25,
    **{h: 30 for h in range(83, 120)},
}

# --- Shot ball-arc geometry (tunable; see Shot_Micro_Movements_System.md §7) ---
# Apex height: apex_px = (ARC_BASE + ARC_SLOPE * dist_grid) * style_mult
ARC_BASE = 20.0  # px floor
ARC_SLOPE = 4.5  # px per grid unit (release → attacking rim)
APEX_BIAS = 0.54  # horizontal progress 0→1 where arc peaks (before clamp)
APEX_HEIGHT_REF = 140.0  # px — flatter shots peak later via apex_pos formula

# Per-style height multipliers (on top of distance scaling)
SHOT_ARC_STYLE_MULT = {
    "strong": 0.85,
    "fade": 1.50,
    "pullup": 0.80,
    "set": 0.95,
    "outside": 1.00,
}

# Per micro-movement-family arc probability (missing → no arc roll / flat release)
SHOT_ARC_PROBABILITY = {
    "fade_away": 1.0,
    "jab_step": 0.5,
    "set": 0.5,
    "set_pump": 0.5,
    "dribble_shoot": 0.5,
    "dribble_pump_shoot": 0.5,
    "pump_dribble_shoot": 0.5,
}

# Family → style key for apex_px style_mult lookup
SHOT_ARC_FAMILY_STYLE = {
    "fade_away": "fade",
    "jab_step": "set",
    "set": "set",
    "set_pump": "set",
    "dribble_shoot": "outside",
    "dribble_pump_shoot": "outside",
    "pump_dribble_shoot": "outside",
}
