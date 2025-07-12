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


INSIDE_SCENE_1 = {
    "name": "Inside_1_HighLowEntry",
    "primary_shooter": "C",
    "screener": "PF",
    "pass_sequence": ["PG", "PF", "C"],
    "steps": [
        {
            "timestamp": 300,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower wing"},
                "PF": {"action": ACTIONS["POST"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 600,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower wing"},
                "PF": {"action": ACTIONS["POST"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 900,
            "pos_actions": {
                "PG": {"action": ACTIONS["PASS"], "spot": "key"},
                "SG": {"action": ACTIONS["STAY"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["GET_OPEN"], "spot": "lower corner"},
                "PF": {"action": ACTIONS["RECEIVE"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "PG", "to": "PF"}]
        },
        {
            "timestamp": 1200,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "lower wing"},
                "SG": {"action": ACTIONS["SCREEN"], "spot": "key"},
                "SF": {"action": ACTIONS["CUT"], "spot": "upper corner"},
                "PF": {"action": ACTIONS["HANDLE"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 1500,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "lower corner"},
                "SG": {"action": ACTIONS["STAY"], "spot": "lower wing"},
                "SF": {"action": ACTIONS["GET_OPEN"], "spot": "key"},
                "PF": {"action": ACTIONS["PASS"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["RECEIVE"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "PF", "to": "C"}]
        },
        {
            "timestamp": 1800,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "upper corner"},
                "SG": {"action": ACTIONS["STAY"], "spot": "lower corner"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "key"},
                "PF": {"action": ACTIONS["SCREEN"], "spot": "topLane"},
                "C": {"action": ACTIONS["HANDLE"], "spot": "upper lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 2100,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["STAY"], "spot": "lower wing"},
                "SF": {"action": ACTIONS["STAY"], "spot": "key"},
                "PF": {"action": ACTIONS["REBOUND"], "spot": "topLane"},
                "C": {"action": ACTIONS["SHOOT"], "spot": "upper lowPost"}
            },
            "events": [{"type": "shot", "by": "C"}]
        }
    ]
}

INSIDE_SCENES = [INSIDE_SCENE_1]