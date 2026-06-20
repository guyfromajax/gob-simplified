from types import SimpleNamespace

from BackEnd.constants.fast_break_play_types import default_fast_break_plays
from BackEnd.engine.after_steal_fast_break import (
    _record_after_steal_fast_break_stats,
    resolve_after_steal_fast_break,
)
from tests.test_utils import build_mock_game


class _Player:
    def __init__(self, player_id):
        self.player_id = player_id
        self.stats = {}

    def record_stat(self, stat, amount=1):
        self.stats[stat] = self.stats.get(stat, 0) + amount


def _team():
    return SimpleNamespace(
        scouting_data={
            "offense": {
                "Fast_Break_Success": 0,
                "fast_break_plays": default_fast_break_plays(),
            },
            "defense": {
                "vs_Fast_Break": {"used": 1, "success": 0},
            },
        }
    )


def _game():
    return SimpleNamespace(
        offense_team=_team(),
        defense_team=_team(),
        game_state={},
    )


def test_after_steal_make_records_shared_player_and_team_stats():
    game = _game()
    stealer = _Player("stealer")
    defenders = [_Player(f"defender-{index}") for index in range(5)]

    _record_after_steal_fast_break_stats(
        game,
        {"result_type": "MAKE"},
        stealer,
        defenders,
    )

    assert stealer.stats == {"FB_A": 1, "FB_S": 1}
    assert game.offense_team.scouting_data["offense"]["Fast_Break_Success"] == 1
    assert (
        game.offense_team.scouting_data["offense"]["fast_break_plays"]["after_steal"]["S"]
        == 1
    )
    assert game.defense_team.scouting_data["defense"]["vs_Fast_Break"]["success"] == 0
    for defender in defenders:
        assert defender.stats == {"FB_A_D": 1, "FB_F_D": 1}


def test_after_steal_miss_records_shared_defensive_success_stats():
    game = _game()
    stealer = _Player("stealer")
    defenders = [_Player(f"defender-{index}") for index in range(5)]

    _record_after_steal_fast_break_stats(
        game,
        {"result_type": "MISS"},
        stealer,
        defenders,
    )

    assert stealer.stats == {"FB_A": 1}
    assert game.offense_team.scouting_data["offense"]["Fast_Break_Success"] == 0
    assert (
        game.offense_team.scouting_data["offense"]["fast_break_plays"]["after_steal"]["S"]
        == 0
    )
    assert game.defense_team.scouting_data["defense"]["vs_Fast_Break"]["success"] == 1
    for defender in defenders:
        assert defender.stats == {"FB_A_D": 1, "FB_F_D": 1}


def _seed_lineup_ids_and_runtime_methods(game):
    for team in (game.home_team, game.away_team):
        team.players = {}
        for pos, player in team.lineup.items():
            player.player_id = f"{team.name}-{pos}"
            player.coords = {"x": 50.0, "y": 25.0}
            player.record_shot_result = lambda *_args, **_kwargs: None
            player.add_momentum = lambda *_args, **_kwargs: None
            team.players[player.player_id] = player


def test_after_steal_miss_stamps_near_bounce_rebound_attemptors(monkeypatch):
    game = build_mock_game()
    _seed_lineup_ids_and_runtime_methods(game)
    game.offense_team = game.home_team
    game.defense_team = game.away_team
    game.game_state["last_stealer"] = game.offense_team.lineup["PG"]
    game.game_state["last_stealer_coords"] = {"x": 50.0, "y": 25.0}
    game.game_state["offensive_state"] = "FAST_BREAK"

    bounce = {"x": 89.0, "y": 25.0}
    near_off = game.offense_team.lineup["SG"]
    far_off = game.offense_team.lineup["SF"]
    near_def = game.defense_team.lineup["SG"]
    dreb_rebounder = game.defense_team.lineup["C"]

    near_off.coords = {"x": 80.0, "y": 25.0}
    far_off.coords = {"x": 70.0, "y": 25.0}
    near_def.coords = {"x": 89.0, "y": 40.0}
    dreb_rebounder.coords = {"x": 89.0, "y": 24.0}

    monkeypatch.setattr(
        "BackEnd.utils.fast_break_shot_geometry.compute_fb_shot_geometry",
        lambda **_kwargs: {
            "shooter_target": {"x": 88.0, "y": 25.0},
            "defender_target": {"x": 90.0, "y": 25.0},
            "defender_end_coords": {
                player.player_id: dict(player.coords)
                for player in game.defense_team.lineup.values()
            },
            "first_arriver_id": game.defense_team.lineup["PG"].player_id,
            "contested": True,
            "shot_defender_id": game.defense_team.lineup["PG"].player_id,
            "t_shooter_game_seconds": 1.0,
        },
    )
    monkeypatch.setattr(
        game.shot_manager,
        "calculate_shot_score",
        lambda *_args, **_kwargs: (1, 1, 0, False, None),
    )
    monkeypatch.setattr(
        "BackEnd.utils.shared.calculate_bounce_spot",
        lambda *_args, **_kwargs: bounce,
    )
    monkeypatch.setattr(
        "BackEnd.utils.shared.determine_rebounder",
        lambda *_args, **_kwargs: (dreb_rebounder, game.defense_team, "DREB"),
    )

    result = resolve_after_steal_fast_break(game)

    assert result["result_type"] == "MISS"
    assert result["rebound_type"] == "DREB"
    assert result["rebounderId"] == dreb_rebounder.player_id
    assert result["ballSpot"] == bounce
    assert near_off.player_id in result["offense_rebounders"]
    assert far_off.player_id not in result["offense_rebounders"]
    assert near_def.player_id in result["defense_rebounders"]
    assert dreb_rebounder.player_id not in result["defense_rebounders"]
