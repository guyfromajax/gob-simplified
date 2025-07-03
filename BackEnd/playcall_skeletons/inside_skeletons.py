from BackEnd.constants import HCO_STRING_SPOTS, ACTIONS


INSIDE_SCENE_1 = {
    "name": "Inside_1_HighLowEntry",
    "primary_shooter": "C",
    "screener": "PF",
    "pass_sequence": ["PG", "PF", "C"],
    "steps": [
        {
            "timestamp": 0,
            "pos_actions": {
                "PG": {"action": ACTIONS["HANDLE"], "spot": "key"},
                "SG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SF": {"action": ACTIONS["CUT"], "spot": "lower midBaseline"},
                "PF": {"action": ACTIONS["POST"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 250,
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
            "timestamp": 500,
            "pos_actions": {
                "PG": {"action": ACTIONS["DRIFT"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["SCREEN"], "spot": "upper midCorner"},
                "SF": {"action": ACTIONS["CUT"], "spot": "midLane"},
                "PF": {"action": ACTIONS["HANDLE"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["POST"], "spot": "lower lowPost"}
            },
            "events": []
        },
        {
            "timestamp": 750,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["STAY"], "spot": "upper midCorner"},
                "SF": {"action": ACTIONS["GET_OPEN"], "spot": "lower corner"},
                "PF": {"action": ACTIONS["PASS"], "spot": "upper highPost"},
                "C": {"action": ACTIONS["RECEIVE"], "spot": "lower lowPost"}
            },
            "events": [{"type": "pass", "from": "PF", "to": "C"}]
        },
        {
            "timestamp": 1000,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["STAY"], "spot": "upper midCorner"},
                "SF": {"action": ACTIONS["DRIFT"], "spot": "upper midCorner"},
                "PF": {"action": ACTIONS["SCREEN"], "spot": "topLane"},
                "C": {"action": ACTIONS["POST"], "spot": "midLane"}
            },
            "events": []
        },
        {
            "timestamp": 1250,
            "pos_actions": {
                "PG": {"action": ACTIONS["STAY"], "spot": "upper wing"},
                "SG": {"action": ACTIONS["STAY"], "spot": "upper midCorner"},
                "SF": {"action": ACTIONS["STAY"], "spot": "upper midCorner"},
                "PF": {"action": ACTIONS["REBOUND"], "spot": "topLane"},
                "C": {"action": ACTIONS["SHOOT"], "spot": "midLane"}
            },
            "events": [{"type": "shot", "by": "C"}]
        }
    ]
}

INSIDE_SCENES = [INSIDE_SCENE_1]