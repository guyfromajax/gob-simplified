from tests.test_utils import build_mock_game
from BackEnd.models.animator import Animator
from BackEnd.models.team_manager import TeamManager
from BackEnd import db
import pytest

BALL_ACTIONS = {"handle_ball", "receive", "shoot"}

def test_capture_halfcourt_animation_ball_assignment(monkeypatch):
    monkeypatch.setattr(TeamManager, "_load_roster", lambda self: [])
    monkeypatch.setattr(TeamManager, "_load_lineup", lambda self: {})
    dummy_collection = type("Dummy", (), {"find": lambda self, q=None: [], "find_one": lambda self, q=None: None})()
    monkeypatch.setattr(db, "players_collection", dummy_collection)
    monkeypatch.setattr(db, "teams_collection", dummy_collection)
    import BackEnd.models.team_manager as tm
    monkeypatch.setattr(tm, "players_collection", dummy_collection)
    monkeypatch.setattr(tm, "teams_collection", dummy_collection)
    import BackEnd.models.turn_manager as trm
    monkeypatch.setattr(trm, "players_collection", dummy_collection)
    monkeypatch.setattr(trm, "teams_collection", dummy_collection)
    game = build_mock_game()
    # Ensure mock players have coordinates for animation logic
    for player in game.home_team.lineup.values():
        player.coords = {"x": 25, "y": 50}
        player.player_id = player.get_name()
    for player in game.away_team.lineup.values():
        player.coords = {"x": 25, "y": 50}
        player.player_id = player.get_name()
    roles = game.turn_manager.assign_roles()
    animator = Animator(game)
    animations = animator.capture_halfcourt_animation(roles)

    step_count = len(roles["steps"])
    offense_ids = [p.player_id for p in game.offense_team.lineup.values()]
    defense_ids = [p.player_id for p in game.defense_team.lineup.values()]

    anim_map = {a["playerId"]: a for a in animations}

    # Validate offensive ball ownership
    for idx in range(step_count):
        owners = [pid for pid in offense_ids if anim_map[pid]["hasBallAtStep"][idx]]
        assert len(owners) == 1
        owner_anim = anim_map[owners[0]]
        action = owner_anim["movement"][idx]["action"]
        assert action in BALL_ACTIONS

    # Defensive players should not have the ball
    for pid in defense_ids:
        hb = anim_map[pid].get("hasBallAtStep", [])
        if hb:
            assert not any(hb)
