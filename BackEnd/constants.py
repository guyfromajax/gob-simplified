import random

ALL_ATTRS = [
    "SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT",  # malleable
    "ND", "IQ", "CH", "EM", "MO"  # static or macro-adjusted
    ]

BOX_SCORE_KEYS = [
    "FGA", "FGM", "3PTA", "3PTM", "FTA", "FTM",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "F", "MIN", "PTS",
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