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

FCP_1 = {
    "primary_shooter": None,
    "screener": None,
    "kickout_shooters": None,
    # "pass_sequence": ["PG", "PF", "C"],
    "steps": [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "lower apex", "opp": True},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "lower wing", "opp": True},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower wing"}
            },
            "events": []
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "upper apex", "opp": True},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "lower wing", "opp": True},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower wing"}
            },
            "events": []
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "upper apex", "opp": True},
                "SG": {"action": ACTIONS["RECEIVE"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["CUT"], "spot": "deep lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "PG", "to": "SG"}]
        },
        {
            "timestamp": 900,
            "pos_actions": {
                "PG": {"action": ACTIONS["CUT"], "spot": "deep key"},
                "SG": {"action": ACTIONS["HANDLE"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper midPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 1200,
            "pos_actions": {
                "PG": {"action": ACTIONS["RECEIVE"], "spot": "deep key"},
                "SG": {"action": ACTIONS["PASS"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper midPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "SG", "to": "PG"}]
        },
        {
            "timestamp": 1500,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "deep key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper midPost"},
                "C": {"action": ACTIONS["RECEIVE"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "PG", "to": "C"}]
        },

        {
            "timestamp": 1800,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "deep key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "deep upper wing", "opp": True},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "deep lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper midPost"},
                "C": {"action": ACTIONS["SHOOT"], "spot": "lower lowPost"}
            },
            "events": []
        }
    ]
}

FCP_SKELETONS_DICT = {
    "HCO": 1200,
    "Shot": 1800,
    "O_FOUL": 1200,
    "D_FOUL": 1200,
    "DEAD_BALL_TURNOVER": 900,
    "STEAL": 900
}