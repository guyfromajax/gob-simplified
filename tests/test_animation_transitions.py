import random
from BackEnd.models.animator import Animator
from BackEnd.constants import ACTIONS, HCO_STRING_SPOTS
from BackEnd.utils.shared import update_player_coords_from_animations

class DummyPlayer:
    def __init__(self, pid):
        self.player_id = pid
        self.coords = {"x": 25, "y": 50}

class DummyTeam:
    def __init__(self, name, tid):
        self.name = name
        self.team_id = tid
        self.lineup = {pos: DummyPlayer(f"{name}_{pos}") for pos in ["PG","SG","SF","PF","C"]}
        self.strategy_calls = {"aggression_call": "normal"}

class GameStub:
    def __init__(self):
        self.home_team = DummyTeam("home", "H")
        self.away_team = DummyTeam("away", "A")
        self.offense_team = self.home_team
        self.defense_team = self.away_team


def build_roles(game):
    steps = [
        {"timestamp": 0, "pos_actions": {}},
        {"timestamp": 200, "pos_actions": {}}
    ]
    timeline = {}
    for player in game.offense_team.lineup.values():
        timeline[player] = [
            (0, ACTIONS["HANDLE"], "key"),
            (200, ACTIONS["STAY"], "key"),
        ]
    bh = game.offense_team.lineup["PG"]
    return {
        "steps": steps,
        "action_timeline": timeline,
        "shooter": bh,
        "ball_handler": bh,
    }


def test_first_movement_frame_uses_previous_end():
    random.seed(0)
    game = GameStub()
    animator = Animator(game)
    roles = build_roles(game)

    # First turn
    first = animator.capture_halfcourt_animation(roles)
    update_player_coords_from_animations(game, first)

    # Record updated positions
    expected_start = {}
    for team in [game.home_team, game.away_team]:
        for p in team.lineup.values():
            expected_start[p.player_id] = dict(p.coords)

    # Second turn
    second = animator.capture_halfcourt_animation(roles)
    for anim in second:
        start = anim["movement"][0]
        assert start["timestamp"] == 0
        assert start["coords"] == expected_start[anim["playerId"]]
