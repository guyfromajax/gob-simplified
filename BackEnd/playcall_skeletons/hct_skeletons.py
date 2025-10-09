from BackEnd.constants import HCO_STRING_SPOTS, ACTIONS

# HCO_STRING_SPOTS = {
#     "key": {"x": 64, "y": 25},
#     "upper midWing": {"x": 68, "y": 36}, 
#     "lower midWing": {"x": 68, "y": 14},
#     "upper wing": {"x": 73, "y": 40}, 
#     "lower wing": {"x": 73, "y": 10},
#     "upper midCorner": {"x": 81, "y": 43}, 
#     "lower midCorner": {"x": 81, "y": 7},
#     "upper corner": {"x": 88, "y": 44}, 
#     "lower corner": {"x": 88, "y": 6},
#     "upper highPost": {"x": 74, "y": 32}, 
#     "lower highPost": {"x": 74, "y": 19},
#     "upper midPost": {"x": 80, "y": 32}, 
#     "lower midPost": {"x": 80, "y": 19},
#     "upper lowPost": {"x": 86, "y": 32}, 
#     "lower lowPost": {"x": 86, "y": 19}, 
#     "topLane": {"x": 74, "y": 25},
#     "midLane": {"x": 80, "y": 25}, 
#     "upper apex": {"x": 80, "y": 36}, 
#     "lower apex": {"x": 80, "y": 15},
#     "upper midBaseline": {"x": 89, "y": 36}, 
#     "lower midBaseline": {"x": 89, "y": 15},
    # "deep key": {"x": 57, "y": 25},
    # "deep lower wing": {"x": 57, "y": 15},
    # "deep lower baseline": {"x": 57, "y": 5},
    # "deep upper wing": {"x": 57, "y": 35},
    # "deep upper baseline": {"x": 57, "y": 45}
# }

#Options: HCO, Shot, O_FOUL, D_FOUL, DEAD_BALL_TURNOVER, STEAL

HCT_1 = {
    "primary_shooter": None,
    "screener": None,
    "kickout_shooters": None,
    # "pass_sequence": ["PG", "PF", "C"],
    "steps": [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "deep key", "opp": True},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing", "opp": True},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper apex"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower apex"}
            },
            "events": []
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "deep key", "opp": True},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing", "opp": True},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower apex"}
            },
            "events": []
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "deep key", "opp": True},
                "SG": {"action": ACTIONS["RECEIVE"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing", "opp": True},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower apex"}
            },
            "events": [{"type": "pass", "from": "PG", "to": "SG"}]
        },
        {
            "timestamp": 900,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "SG": {"action": ACTIONS["HANDLE"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "key",},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower midBaseline"}
            },
            "events": []
        },
        {
            "timestamp": 1200,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "SG": {"action": ACTIONS["PASS"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["RECEIVE"], "spot": "key",},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower midBaseline"}
            },
            "events": [{"type": "pass", "from": "SG", "to": "SF"}]
        },
        {
            "timestamp": 1500,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["PASS"], "spot": "key",},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["RECEIVE"], "spot": "lower midBaseline"}
            },
            "events": [{"type": "pass", "from": "SF", "to": "C"}]
        },

        {
            "timestamp": 1800,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key",},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "C": {"action": ACTIONS["SHOOT"], "spot": "lower midBaseline"}
            },
            "events": []
        }
    ]
}

FCP_SKELETONS_DICT = {
    "HCO": 1200,
    "Shot": 1800,
    "O_FOUL": 1200,
    "D_FOUL": 900,
    "DEAD_BALL_TURNOVER": 900,
    "STEAL": 900
}