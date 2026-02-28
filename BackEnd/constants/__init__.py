import random
import os

# Debug flag - set DISABLE_DEBUG=1 environment variable to suppress verbose output
# Defaults to True (debug enabled) unless DISABLE_DEBUG is set
DEBUG = os.environ.get("DISABLE_DEBUG", "").lower() not in ["1", "true", "yes"]

ALL_ATTRS = [
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT",  # malleable
    "ND", "IQ", "CH", "EM", "MO"  # static or macro-adjusted
    ]

BOX_SCORE_KEYS = [
    "FGA", "FGM", "3PTA", "3PTM", "FTA", "FTM",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN", "PTS", "PIP", "FB_PTS", "POT",
    "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S",
    # Fast Break stats
    "Outlet_A", "Outlet_S", "Outlet_Score", "Outlet_Score_List", "Outlet_Score_Cum",
    "FB_A", "FB_S", "FB_F", "FB_N",
    "FB_A_D", "FB_S_D", "FB_F_D",
    # FCP/HCT stats
    "HCT_A", "HCT_S", "HCT_A_D", "HCT_S_D",
    "FCP_A", "FCP_S", "FCP_A_D", "FCP_S_D"
]


PLAYCALL_ATTRIBUTE_WEIGHTS = {
    "Base": {"SH": 2, "SC": 2, "AG": 2, "ST": 2, "IQ": 1, "CH": 1},
    "Freelance": {"SH": 2, "SC": 2, "AG": 1, "ST": 1, "IQ": 3, "CH": 1},
    "Inside": {"SC": 6, "ST": 2, "IQ": 1, "CH": 1},
    "Attack": {"SC": 5, "AG": 2, "ST": 1, "IQ": 1, "CH": 1},
    "Outside": {"SH": 8, "IQ": 1, "CH": 1},
    "Set": "Same as Attack"
}

THREE_POINT_PROBABILITY = {
    "Outside": 0.8,
    "Base": 0.4,
    "Freelance": 0.2
    # All others default to 0.0
}

# Spots that are three-point shots (outside the arc) - case insensitive
THREE_POINT_SPOTS = {
    "key",
    "deep key",
    "upper wing",
    "deep upper wing",
    "lower wing",
    "deep lower wing",
    "upper midwing",
    "lower midwing",
    "lower midcorner",
    "upper midcorner",
    "upper corner",
    "lower corner",
    "deep upper baseline",
    "deep lower baseline",
}

# Spots that are points in the paint (PIP) - case insensitive
PAINT_SPOTS = {
    "lower lowpost",
    "lower midpost",
    "upper lowpost",
    "upper midpost",
    "midlane",
    "basketspot",
}

BLOCK_PROBABILITY = {
    "Inside": 0.2,
    "Attack": 0.1,
    "Base": 0.1,
    "Freelance": 0.1
    # All others default to 0.0
}

# Block reconciliation (blocks on shot attempts): diff = shot_score_pre_defense - defense_block_score
# If diff > BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD → shooting foul; if diff < BLOCK_RECONCILIATION_BLOCK_THRESHOLD → block; else → standard shot
# Thresholds are independent: adjust either without affecting the other.
BLOCK_RECONCILIATION_SHOOTING_FOUL_THRESHOLD = 150
BLOCK_RECONCILIATION_BLOCK_THRESHOLD = -150
# Block attempt roll: y = random.randint(BLOCK_Y_ROLL_MIN, BLOCK_Y_ROLL_MAX); attempt when y < aggression
BLOCK_Y_ROLL_MIN = 1
BLOCK_Y_ROLL_MAX = 4
# Secondary block attempt roll: z = random.randint(BLOCK_FIGHT_RANGE_MIN, BLOCK_FIGHT_RANGE_MAX); attempt when z < defense fight
BLOCK_FIGHT_RANGE_MIN = 0
BLOCK_FIGHT_RANGE_MAX = 15

MALLEABLE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT"]

PLAYCALLS = ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]

STRATEGY_CALL_DICTS = {
    "defense": {
        0: ["Man"],
        1: ["Man", "Man", "Zone"],  # Zone will be randomly selected as 2-3 or 3-2
        2: ["Man", "Zone"],
        3: ["Man", "Zone", "Zone"],
        4: ["Zone"]},  # Zone will be randomly selected as 2-3 or 3-2
    "tempo": {
        0: ["slow"],
        1: ["slow", "normal"],
        2: ["normal"],
        3: ["normal", "fast"],
        4: ["fast"],
    },
    "aggression": {
        0: ["passive"],
        1: ["passive", "normal"],
        2: ["normal"],
        3: ["normal", "aggressive"],
        4: ["aggressive"],
    },
}

TEMPO_PASS_DICT = {
    "slow": random.randint(1,6),
    "normal": random.randint(2,4),
    "fast": random.randint(1,3)
}

TURNOVER_CALC_DICT = {
    0: ["PG"],
    1: ["PG", "SG"],
    2: ["PG", "SG", "PG"],
    3: ["PG", "SG", "SF", "PG"],
    4: ["PG", "SG", "SF", "PF", "PG"],
    5: ["PG", "SG", "SF", "PF", "C", "PG"],
    6: ["PG", "SG", "SF", "PF", "C", "PG", "PG"]
}

POSITION_LIST = ["PG", "SG", "SF", "PF", "C"]

# Ball landing adjustment for made shots (grid units closer to shooter)
MADE_SHOT_BALL_OFFSET = 1

# constants/strategy_factors.py
AGGRESSION_FOUL_MULTIPLIER = {
    0: 0.8,
    1: 0.9,
    2: 1,
    3: 1.1,
    4: 1.2,
}

# Shooting Foul System constants
HARD_SHOOTING_FOUL_THRESHOLD = 50
SOFT_SHOOTING_FOUL_THRESHOLD = 110
SOFT_PROB = 0.16

# Shooting Foul Calibration constants (chance that a defensive shooting foul forces a miss)
THREE_POINTER_FOUL_MISS_CHANCE = 0.4  # 40% chance foul forces miss on 3-pointers
TWO_POINTER_FOUL_MISS_CHANCE = 0.2    # 20% chance foul forces miss on 2-pointers
# Three-point shot threshold modifier: shot_threshold += (THREE_POINT_SHOT_THRESHOLD_INCREASE - (random(1,5)*momentum))
THREE_POINT_SHOT_THRESHOLD_INCREASE = 40

# HCO Resolution System constants
# Target averages per game:
# - 60 field goal attempts per team per game
# - Average target FG% of 45%
STANDARD_D_FOUL = 95
STANDARD_O_FOUL = 5
HARD_STEAL = -135
SOFT_STEAL = -35
HARD_FOUL = 250
SOFT_FOUL = 150
STEAL_ATTEMPT = 30
DEAD_BALL_TURNOVER = 30  # temp change from 7

# Charge/Blocking Foul (drive reconciliation thresholds)
# reconciliation = offense_score - defense_score
# < CHARGE_THRESHOLD → charge (offensive foul); > BLOCKING_FOUL_THRESHOLD → blocking foul (defensive foul)
CHARGE_THRESHOLD = -240
BLOCKING_FOUL_THRESHOLD = 220

# Situational Logic (Q4/OT): time-band table (see docs/.../Situational_Logic_System.md)
# Each entry: (min_sec, max_sec, config). Time remaining in quarter (seconds). Bands: 2:01-3:00, 1:01-2:00, 0:31-1:00, 0:01-0:30.
SITUATIONAL_TIME_BANDS = (
    (121, 180, {"slow_min": 12, "quick_lo": -24, "quick_hi": -12, "outside": 0.60, "attack": 0.20, "inside": 0.20, "force_foul": False}),
    (61, 120, {"slow_min": 9, "quick_lo": -18, "quick_hi": -9, "outside": 0.70, "attack": 0.20, "inside": 0.10, "force_foul": False}),
    (31, 60, {"slow_min": 3, "quick_lo": -12, "quick_hi": -3, "outside": 0.80, "attack": 0.15, "inside": 0.05, "force_foul_lo": 3, "force_foul_hi": 12}),
    (0, 30, {"slow_min": 1, "quick_lo": -9, "quick_hi": -1, "last_30_quick": True, "outside_if_delta_below": -2, "force_foul_lo": 1, "force_foul_hi": 9}),
)
# Legacy: used only if a caller expects single ratio; bands above define explicit outside/attack/inside
SITUATIONAL_QUICK_SHOT_ATTACK_RATIO = 0.75
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN = 1
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX = 3
# Inbound pass receiver position for Force Foul (BIP/SIP)
SITUATIONAL_BIP_RECEIVER_POS = "SG"
SITUATIONAL_SIP_RECEIVER_POS = "SG"

# Movement rates (game seconds vs grid distance); see Real_Time_Clock_System.md
# Doc lists rate as x/y; segment formula uses x rate: sqrt(dx^2+dy^2)/x
OPEN_FLOOR_GRID_PER_GAME_SECOND = 20  # OF (20/20): bring-up, fallback
CHALLENGED_OPEN_FLOOR_GRID_PER_GAME_SECOND = 18  # COF (18/18): HCT/FCP steps, Fast Break
ATTACK_DRIVE_GRID_SPOTS_PER_GAME_SECOND = 12  # Drive (12/12): attack to basket
COMPRESSED_HCO_GRID_PER_GAME_SECOND = 16  # Compressed HCO (16/16): non-drive non-shoot
HCO_SHOT_GRID_PER_GAME_SECOND = 14  # HCO shot with movement (14/14); stationary = 1 sec
PASS_GRID_SPOTS_PER_GAME_SECOND = 36  # Pass (ball in air): Euclidean

HCO_STRING_SPOTS = {
    "key": {"x": 64, "y": 25},
    "upper midWing": {"x": 68, "y": 36}, 
    "lower midWing": {"x": 68, "y": 14},
    "upper wing": {"x": 73, "y": 40}, 
    "lower wing": {"x": 73, "y": 10},
    "upper midCorner": {"x": 81, "y": 43}, 
    "lower midCorner": {"x": 81, "y": 7},
    "upper corner": {"x": 88, "y": 44}, 
    "lower corner": {"x": 88, "y": 6},
    "upper highPost": {"x": 74, "y": 32}, 
    "lower highPost": {"x": 74, "y": 19},
    "upper midPost": {"x": 80, "y": 32}, 
    "lower midPost": {"x": 80, "y": 19},
    "upper lowPost": {"x": 86, "y": 32}, 
    "lower lowPost": {"x": 86, "y": 19}, 
    "topLane": {"x": 74, "y": 25},
    "midLane": {"x": 80, "y": 25}, 
    "basketSpot": {"x": 87, "y": 25},
    "upper apex": {"x": 80, "y": 36}, 
    "lower apex": {"x": 80, "y": 15},
    "upper bird": {"x": 85, "y": 36},
    "lower bird": {"x": 85, "y": 15},
    "upper midBaseline": {"x": 89, "y": 36}, 
    "lower midBaseline": {"x": 89, "y": 15},
    "deep key": {"x": 57, "y": 25},
    "deep lower wing": {"x": 57, "y": 15},
    "deep lower baseline": {"x": 57, "y": 5},
    "deep upper wing": {"x": 57, "y": 35},
    "deep upper baseline": {"x": 57, "y": 45},
    # Inbound positions (for FCP/HCT skeletons after made baskets)
    "inbound_left": {"x": 3, "y": 25},    # Left of center baseline
    "inbound_right": {"x": 97, "y": 25}    # Right of center baseline
}

# FCP/HCT setup positions (step 0 extracted from skeletons)
# These positions are used during BASELINE_INBOUND setup before skeleton animation
# All FCP variants use the same starting positions
FCP_SETUP_POSITIONS = {
    "PG": "lower bird",
    "SG": "upper midBaseline",
    "SF": "inbound_left",
    "PF": "deep key",
    "C": "key"
}

# All HCT variants use the same starting positions
HCT_SETUP_POSITIONS = {
    "PG": "lower bird",
    "SG": "upper highPost",
    "SF": "inbound_left",
    "PF": "deep upper wing",
    "C": "deep lower wing"
}

# Offset positions for collision handling (when two players at same spot)
OFFSET_SPOTS = {
    # Center spots: x + 3, y same
    "deep key": {"x": 60, "y": 25},
    "key": {"x": 67, "y": 25},
    "topLane": {"x": 77, "y": 25},
    "midLane": {"x": 83, "y": 25},
    
    # Upper wing/apex spots: x + 3, y - 3
    "deep upper wing": {"x": 60, "y": 32},
    "upper midWing": {"x": 71, "y": 33},
    "upper wing": {"x": 76, "y": 37},
    "upper apex": {"x": 83, "y": 33},
    
    # Upper corner/baseline spots: x same, y - 3
    "upper corner": {"x": 88, "y": 41},
    "upper midCorner": {"x": 81, "y": 40},
    "deep upper baseline": {"x": 57, "y": 42},
    "upper midBaseline": {"x": 89, "y": 33},
    
    # Lower wing/apex spots: x + 3, y + 3
    "deep lower wing": {"x": 60, "y": 18},
    "lower midWing": {"x": 71, "y": 17},
    "lower wing": {"x": 76, "y": 13},
    "lower apex": {"x": 83, "y": 18},
    
    # Lower corner/baseline spots: x same, y + 3
    "lower corner": {"x": 88, "y": 9},
    "lower midCorner": {"x": 81, "y": 10},
    "deep lower baseline": {"x": 57, "y": 8},
    "lower midBaseline": {"x": 89, "y": 18},
    
    # Upper post spots: x - 3, y + 3
    "upper lowPost": {"x": 83, "y": 35},
    "upper midPost": {"x": 77, "y": 35},
    "upper highPost": {"x": 71, "y": 35},
    
    # Lower post spots: x + 3, y - 3
    "lower lowPost": {"x": 89, "y": 16},
    "lower midPost": {"x": 83, "y": 16},
    "lower highPost": {"x": 77, "y": 16}
}

# Shared court coordinates
HOME_RIM_COORDS = {"x": 91, "y": 25}
AWAY_RIM_COORDS = {"x": 9, "y": 25}
HOME_TOP_KEY = {"x": 64, "y": 25}
AWAY_TOP_KEY = {"x": 36, "y": 25}
HOME_INBOUND_LEFT = {"x": 97, "y": 20}  # Home team inbounding from left side (under away basket)
AWAY_INBOUND_LEFT = {"x": 3, "y": 20}   # Away team inbounding from left side (under home basket)

RIM_COORDS = HOME_RIM_COORDS
TOP_KEY_COORDS = HOME_TOP_KEY

ACTIONS = {
    "HANDLE": "handle_ball",
    "PASS": "pass",
    "RECEIVE": "receive",
    "POST_UP": "post_up",
    "SHOOT": "shoot",
    "DRIVE": "drive",
    "SCREEN": "screen",
    "CUT": "cut",
    "GET_OPEN": "get_open",
    "DRIFT": "drift",
    "HOLD": "stationary",
    # 🛡️ Defensive actions
    "GUARD_BALL": "guard_ball",
    "GUARD_OFFBALL": "guard_offball"
}

# Import fast break constants
from BackEnd.constants.fast_break_constants import (
    BALL_HANDLER_MOVE_X_MIN,
    BALL_HANDLER_MOVE_X_MAX,
    BALL_HANDLER_MOVE_Y_RANGE,
    STOPPER_OFFSET_MIN,
    STOPPER_OFFSET_MAX,
    SHOT_DEFENDER_X_OFFSET,
    SHOT_DEFENDER_Y_RANGE,
    REBOUNDER_X_MIN,
    REBOUNDER_X_MAX,
    REBOUNDER_Y_RANGE,
    SHOT_ATTEMPT_REBOUNDER_Y_RANGE,
    OUTLET_PASSER_MOVE_X,
    DEFENSIVE_STOP_Y_RANGE,
    STEAL_ENTRY_MOVE_X_MIN,
    STEAL_ENTRY_MOVE_X_MAX,
    STEAL_ENTRY_MOVE_Y_RANGE,
    STEAL_ENTRY_Y_MIN,
    STEAL_ENTRY_Y_MAX,
    STEAL_HCO_SETUP_MOVE_X_MIN,
    STEAL_HCO_SETUP_MOVE_X_MAX,
    STEAL_HCO_SETUP_MOVE_Y_RANGE,
    STEAL_HCO_SETUP_Y_MIN,
    STEAL_HCO_SETUP_Y_MAX,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MIN,
    STEAL_HCO_SETUP_OTHER_PLAYERS_MOVE_X_MAX,
)

# Tempo time elapsed: get_time_elapsed(tempo_call) uses these (mean, std, min, max → gauss then clamp).
# Values previously in jamies-cc; now canonical here. See docs Constants_System.md.
TEMPO_PARAMS = {
    "slow": {"mean": 20, "std": 6, "min": 5, "max": 30},
    "normal": {"mean": 15, "std": 6, "min": 5, "max": 30},
    "fast": {"mean": 10, "std": 4, "min": 4, "max": 15},
}

# Team attribute clamps (min, max) for shot_threshold and rebound_modifier. Used by team init and training.
TEAM_ATTR_RANGES = {
    "shot_threshold": (0, 200),
    "rebound_modifier": (0.0, 0.4),
}
