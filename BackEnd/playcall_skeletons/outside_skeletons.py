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
OUTSIDE_CORNER_CROSS = {
    "primary_shooter": "SG",
    "screener": "PF",
    # "kickout_shooters": ["PG", "SG", "SF"],
    "pass_sequence": ["PG", "SF", "SG"],
    "steps": [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower wing"},
                "PF": {"action": ACTIONS["POST_UP"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["POST_UP"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper corner"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "PF": {"action": ACTIONS["POST_UP"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["POST_UP"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["CUT"], "spot": "upper lowPost"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "PF": {"action": ACTIONS["SCREEN"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower highPost"}
            },
            "events": [{"type": "screen", "by": "PF", "for": "SG"}]
        },
        {
            "timestamp": 900,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["CUT"], "spot": "lower lowPost"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower highPost"}
            },
            "events": []
        },
        {
            "timestamp": 1200,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["CUT"], "spot": "lower wing"},
                "SF": {"action": ACTIONS["RECEIVE"], "spot": "key"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "lower highPost"}
            },
            "events": [{"type": "pass", "from": "PG", "to": "SF"}]
        },
        {
            "timestamp": 1500,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["RECEIVE"], "spot": "lower wing"},
                "SF": {"action": ACTIONS["PASS"], "spot": "key"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "upper highPost"}
            },
            "events": [{"type": "pass", "from": "SF", "to": "SG"}]
        },
        {
            "timestamp": 1800,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["SHOOT"], "spot": "lower wing"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "PF": {"action": ACTIONS["DRIFT"], "spot": "upper lowPost"},
                "C": {"action": ACTIONS["DRIFT"], "spot": "upper highPost"}
            },
            "events": [{"type": "shot", "by": "SG"}]
        }
    ]
}

OUTSIDE_SCENES = [OUTSIDE_CORNER_CROSS]