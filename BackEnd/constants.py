import random

ALL_ATTRS = [
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT",  # malleable
    "ND", "IQ", "CH", "EM", "MO"  # static or macro-adjusted
    ]

BOX_SCORE_KEYS = [
    "FGA", "FGM", "3PTA", "3PTM", "FTA", "FTM",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN", "PTS", "PIP",
    "DEF_A", "DEF_S", "HELP_D", "SCR_A", "SCR_S"
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
}

BLOCK_PROBABILITY = {
    "Inside": 0.2,
    "Attack": 0.1,
    "Base": 0.1,
    "Freelance": 0.1
    # All others default to 0.0
}

MALLEABLE_ATTRS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT"]

PLAYCALLS = ["Base", "Freelance", "Inside", "Attack", "Outside", "Set"]

STRATEGY_CALL_DICTS = {
    "defense": {
        0: ["Man"],
        1: ["Man", "Man", "Zone"],
        2: ["Man", "Zone"],
        3: ["Man", "Zone", "Zone"],
        4: ["Zone"]},
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
    "upper apex": {"x": 80, "y": 36}, 
    "lower apex": {"x": 80, "y": 15},
    "upper midBaseline": {"x": 89, "y": 36}, 
    "lower midBaseline": {"x": 89, "y": 15},
    "deep key": {"x": 57, "y": 25},
    "deep lower wing": {"x": 57, "y": 15},
    "deep lower baseline": {"x": 57, "y": 5},
    "deep upper wing": {"x": 57, "y": 35},
    "deep upper baseline": {"x": 57, "y": 45}
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
HOME_RIM_COORDS = {"x": 90, "y": 25}
AWAY_RIM_COORDS = {"x": 10, "y": 25}
HOME_TOP_KEY = {"x": 64, "y": 25}
AWAY_TOP_KEY = {"x": 36, "y": 25}

RIM_COORDS = HOME_RIM_COORDS
TOP_KEY_COORDS = HOME_TOP_KEY

ACTIONS = {
    "HANDLE": "handle_ball",
    "PASS": "pass",
    "RECEIVE": "receive",
    "POST_UP": "post_up",
    "SHOOT": "shoot",
    "SCREEN": "screen",
    "CUT": "cut",
    "GET_OPEN": "get_open",
    "DRIFT": "drift",
    "HOLD": "stationary",
    # 🛡️ Defensive actions
    "GUARD_BALL": "guard_ball",
    "GUARD_OFFBALL": "guard_offball"
}

