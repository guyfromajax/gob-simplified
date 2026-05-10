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
    "FB_A", "FB_S",
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

# Token in STRATEGY_CALL_DICTS["defense"] lists → expand via weighted zone picker (`defense_id` slugs).
STRATEGY_DEFENSE_ZONE_SENTINEL = "__strategy_zone__"

STRATEGY_CALL_DICTS = {
    "defense": {
        0: ["man"],
        1: ["man", "man", STRATEGY_DEFENSE_ZONE_SENTINEL],
        2: ["man", STRATEGY_DEFENSE_ZONE_SENTINEL],
        3: ["man", STRATEGY_DEFENSE_ZONE_SENTINEL, STRATEGY_DEFENSE_ZONE_SENTINEL],
        4: [STRATEGY_DEFENSE_ZONE_SENTINEL],
    },
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

# Ball rest position after a make (grid coords, one step toward center from each hoop).
# Must stay in sync with FrontEnd/static/js/phaser/animation/courtConstants.js
MADE_SHOT_SWEET_SPOT_HOME_RIM = {"x": 90, "y": 25}  # hoop at HOME_RIM_COORDS (91)
MADE_SHOT_SWEET_SPOT_AWAY_RIM = {"x": 10, "y": 25}  # hoop at AWAY_RIM_COORDS (9)

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
HARD_PROB = 0.7  # When defense_score < hard_threshold, call shooting foul with this probability (reduces automatic fouls)
SOFT_PROB = 0.16

# Shooting Foul Calibration constants (chance that a defensive shooting foul forces a miss)
THREE_POINTER_FOUL_MISS_CHANCE = 0.4  # 40% chance foul forces miss on 3-pointers
TWO_POINTER_FOUL_MISS_CHANCE = 0.2    # 20% chance foul forces miss on 2-pointers
# After primary FT roll (1–100 vs ft_shot_score), if miss: this probability upgrades miss → make (baseline;
# home crowd / other systems can substitute an adjusted value at call site).
FREE_THROW_MISS_TO_MAKE_SECOND_CHANCE = 0.40
# Three-point shot threshold modifier: shot_threshold += (THREE_POINT_SHOT_THRESHOLD_INCREASE - (random(1,5)*momentum))
THREE_POINT_SHOT_THRESHOLD_INCREASE = 40

# HCO Resolution System constants
# Target averages per game:
# - 60 field goal attempts per team per game
# - Average target FG% of 45%
STANDARD_D_FOUL = 95 #changed from 94 to accommodate over the back fouls
STANDARD_O_FOUL = 5 #changed from 6 to accommodate over the back fouls
HARD_STEAL = -135
SOFT_STEAL = -35
HARD_FOUL = 250
SOFT_FOUL = 150
STEAL_ATTEMPT = 30
DEAD_BALL_TURNOVER = 10

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
    # Last 30s Force Foul: True if 0 < Score Delta < 9 (see Situational_Logic_System.md); force_lo=0 + strict < gives delta 1..8
    # Quick Shot applies only when trailing by more than 3 (delta <= -4). Down exactly 3 stays eligible for Final Shot.
    (0, 30, {"slow_min": 1, "quick_lo": -9, "quick_hi": -3, "last_30_quick": True, "outside_if_delta_below": -3, "force_foul_lo": 0, "force_foul_hi": 9}),
)
# Legacy: used only if a caller expects single ratio; bands above define explicit outside/attack/inside
SITUATIONAL_QUICK_SHOT_ATTACK_RATIO = 0.75
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MIN = 1
SITUATIONAL_FORCE_FOUL_TIME_ELAPSED_MAX = 3
# Inbound pass receiver position for Force Foul (BIP/SIP)
SITUATIONAL_BIP_RECEIVER_POS = "SG"
SITUATIONAL_SIP_RECEIVER_POS = "SG"

# Movement rates. Legacy per-archetype pace constants were retired in Phase 4d
# (see Movement_Rate_Refactor.md) — they're now derived per-player from AG via
# ``calc_ag_segment_seconds`` and ``ag_to_grid_per_game_sec``, and the cruise
# baseline lives in ``CRUISE_BASELINE_GRID_PER_GAME_SEC`` below. Pass speed
# stays a constant — ball physics, not player AG.
PASS_GRID_SPOTS_PER_GAME_SECOND = 36  # Pass (ball in air): Euclidean

# ---- Movement Rate Refactor (see Movement_Rate_Refactor.md) ---------------
# New two-tier model: cruise-speed steps (HCO/HCT bring-up) vs AG-driven steps.
# Phase 1 ships these constants without wiring them; helpers in shared.py
# accept them but route to the legacy pace constants until Phase 2/4 land.
CRUISE_BASELINE_GRID_PER_GAME_SEC = 16  # Cruise baseline for non-BH movers
BH_CRUISE_MIN_GRID_PER_GAME_SEC   = 8   # BH random low end during bring-up
BH_CRUISE_MAX_GRID_PER_GAME_SEC   = 16  # BH random high end during bring-up
DRIVE_MULTIPLIER                  = 0.75   # Drive = 0.75 × free-running AG rate
SHOT_MOTION_MULTIPLIER            = 0.625  # Shot motion = 0.625 × free-running AG rate
# Sprint = max-effort fast-break movement (RR burst, BH cover-ground in open
# court, FB shot motion). Tentative starting value at 1.25×; calibrate against
# today's visual pacing in Phase 3c when frontend tweens consume game_seconds.
# At AG=50, 16 × 1.25 = 20 grid/sec — matches the retired OPEN_FLOOR_RATE that
# was the closest legacy analog for max-effort movement.
SPRINT_MULTIPLIER                 = 1.25

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
    "center court": {"x": 50, "y": 25},
    "upper center court wing": {"x": 50, "y": 35},
    "upper center court baseline": {"x": 50, "y": 45},
    "lower center court wing": {"x": 50, "y": 15},
    "lower center court baseline": {"x": 50, "y": 5},
    # Inbound positions (for FCP/HCT skeletons after made baskets)
    "inbound_left": {"x": 3, "y": 25},    # Left of center baseline
    "inbound_right": {"x": 97, "y": 25},   # Right of center baseline
    # HCT inbound-side setup spots for PG/SG (home orientation). Sit near the
    # inbounder so dynamic-HCT step 1 always advances forward from a consistent
    # low-x starting point (see Dynamic_HCT_Turns.md, bug #2).
    "hct_inbound_pg": {"x": 10, "y": 25},
    "hct_inbound_sg": {"x": 15, "y": 35},
}

# ---- HCO Setup Positions ---------------------------------------------------
# Used by Fast Break Defensive Stop step-back step (and any future pre-HCO
# transition setup). See:
#   _documentation_master/05_Animation_System/Advance_Triggers.md
#   (Covert Release → Defensive Stop branch).
#
# Convention: BH(s) excluded from pos slots via the standard alias mapping
# (`_alias_map` in dynamic_hct.py / `_build_set_play_alias_map` in
# playbook_weights_utils.py).
#
#   - Single-BH case (FB BH == HCO BH): the BH goes to a randomly chosen
#     deep frontcourt spot (HCO_SETUP_OFFENSE_BH_DEEP_SPOTS); the other 4
#     supporting players fill pos1..pos4.
#   - Two-BHs case (FB BH != HCO BH): the FB BH goes to a deep frontcourt
#     spot; the HCO BH goes within HCO_SETUP_HCO_BH_RADIUS grid units of
#     the FB BH AND on the same horizontal half (home offense → x ≥ 50;
#     away offense → x ≤ 50, to avoid an over-and-back violation). The
#     remaining 3 supporting players fill pos1..pos3 (pos4 is dropped).
#
# Defenders mirror the offensive setup with same-lineup-position matchup
# (def_PG → off_PG's spot, etc.). The 5 spots form a 2-3 zone footprint
# by construction.
HCO_SETUP_OFFENSE_BH_DEEP_SPOTS = ("deep key", "deep upper wing", "deep lower wing")
HCO_SETUP_OFFENSE_POS_SPOTS = {
    "pos1": "upper wing",
    "pos2": "lower wing",
    "pos3": "upper lowPost",
    "pos4": "lower lowPost",  # dropped when FB BH != HCO BH
}
HCO_SETUP_HCO_BH_RADIUS = 10  # max grid units from FB BH for HCO BH placement


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

# All HCT variants use the same starting positions.
# PG/SG sit on the inbound side near the inbounder so dynamic-HCT step 1
# always advances forward from a consistent low-x starting point. See
# Dynamic_HCT_Turns.md (bug #2) for why we replaced prior-turn carry-over.
HCT_SETUP_POSITIONS = {
    "PG": "hct_inbound_pg",
    "SG": "hct_inbound_sg",
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
    fast_break_shot_defender_end_coords,
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
    "shot_threshold": (10, 210),
    "rebound_modifier": (0.0, 0.4),
}
