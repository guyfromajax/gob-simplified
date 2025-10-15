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
# }


#frequencyoptions are strong offense, neutral, strong defense
PICK_AND_ROLL = {
    "primary_shooter": "SF",
    "screener": "PF",
    # "kickout_shooters": ["PG", "SG", "SF"],
    "pass_sequence": ["PG", "SF", "SG"],
    "steps": [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "deep key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper apex"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower apex"}
            },
            "events": []
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "deep key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"},
                "PF": {"action": ACTIONS["SCREEN"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["SCREEN"], "spot": "lower lowPost"}
            },
            "events": [{"type": "screen", "by": "PG", "for": "SG"}, 
                       {"type": "screen", "from": "PF", "to": "C"}]
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["CUT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"}
            },
            "events": [{"type": "screen", "by": "PG", "for": "SF"}]
        },
        {
            "timestamp": 900,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["RECEIVE"], "spot": "lower wing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower lowPost"}
            },
            "events": [{"type": "screen", "by": "PG", "for": "SF"}]
        },
        {
            "timestamp": 1200,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["HANDLE"], "spot": "lower midWing"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower corner"}
            },
            "events": []
        },
        {
            "timestamp": 1500,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["HANDLE"], "spot": "lower midWing"},
                "PF": {"action": ACTIONS["SCREEN"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower corner"}
            },
            "events": [{"type": "screen", "by": "PF", "for": "SF"}]
        },
        {
            "timestamp": 1800,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower lowPost"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower corner"}
            },
            "events": []
        },
        {
            "timestamp": 2100,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["SHOOT"], "spot": "lower lowPost"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower corner"}
            },
            "events": [{"type": "shot", "by": "SF"}]
        }
    ]
}

SET_PLAY_SCENES = [PICK_AND_ROLL]