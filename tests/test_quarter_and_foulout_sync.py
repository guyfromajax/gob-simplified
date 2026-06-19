from types import SimpleNamespace
from unittest.mock import Mock

from BackEnd.models.game_manager import GameManager
from BackEnd.utils.shared import record_team_points


def test_record_team_points_syncs_team_and_game_state_quarters():
    team = SimpleNamespace(name="HOME", points_by_quarter=[0, 0, 0, 0])
    game = SimpleNamespace(
        score={"HOME": 0},
        game_state={"quarter": 2, "points_by_quarter": {"HOME": [0, 0, 0, 0]}},
    )

    record_team_points(game, team, 3)

    assert game.score["HOME"] == 3
    assert team.points_by_quarter == [0, 3, 0, 0]
    assert game.game_state["points_by_quarter"]["HOME"] == [0, 3, 0, 0]


def test_record_team_points_extends_overtime_slots_and_state_mirror():
    team = SimpleNamespace(name="AWAY", points_by_quarter=[0, 0, 0, 0])
    game = SimpleNamespace(
        score={"AWAY": 10},
        game_state={"quarter": 5, "points_by_quarter": {}},
    )

    record_team_points(game, team, 2)

    assert game.score["AWAY"] == 12
    assert team.points_by_quarter == [0, 0, 0, 0, 2]
    assert game.game_state["points_by_quarter"]["AWAY"] == [0, 0, 0, 0, 2]


def test_foul_out_timeout_uses_unified_call_timeout_path():
    away_player = SimpleNamespace(player_id="p-away", team="AWAY")
    away_team = SimpleNamespace(
        name="AWAY",
        team_id="AWAY",
        lineup={},
        get_all_players=lambda: [away_player],
    )
    home_team = SimpleNamespace(
        name="HOME",
        team_id="HOME",
        lineup={},
        get_all_players=lambda: [],
    )

    fake_game = SimpleNamespace(
        home_team=home_team,
        away_team=away_team,
        game_state={"foul_out_context": {"foul_type": "DEFENSIVE", "next_play_type": "SIDE_INBOUND"}},
        game_id=None,
        call_timeout=Mock(return_value={"result_type": "TIMEOUT"}),
    )

    result = {"foul_out_player": {"player_id": "p-away", "name": "Away Player"}}
    GameManager._handle_foul_out_timeout(fake_game, result)

    fake_game.call_timeout.assert_called_once_with(
        calling_team=away_team,
        timeout_reason="FOUL_OUT",
        foul_out_player=away_player,
        foul_out_context={"foul_type": "DEFENSIVE", "next_play_type": "SIDE_INBOUND"},
    )


def test_foul_out_timeout_resolves_player_from_foul_player_id_when_payload_missing():
    away_player = SimpleNamespace(
        player_id="p-away",
        name="Away Player",
        team="AWAY",
        photo="/images/players/p-away.png",
    )
    away_team = SimpleNamespace(
        name="AWAY",
        team_id="AWAY",
        lineup={},
        get_all_players=lambda: [away_player],
    )
    home_team = SimpleNamespace(
        name="HOME",
        team_id="HOME",
        lineup={},
        get_all_players=lambda: [],
    )

    timeout_turn = {"result_type": "TIMEOUT"}
    fake_game = SimpleNamespace(
        home_team=home_team,
        away_team=away_team,
        game_state={"foul_out_context": {"foul_type": "DEFENSIVE", "next_play_type": "SIDE_INBOUND"}},
        game_id=None,
        call_timeout=Mock(return_value=timeout_turn),
    )

    result = {"fouled_out": True, "foul_player_id": "p-away"}
    GameManager._handle_foul_out_timeout(fake_game, result)

    fake_game.call_timeout.assert_called_once_with(
        calling_team=away_team,
        timeout_reason="FOUL_OUT",
        foul_out_player=away_player,
        foul_out_context={"foul_type": "DEFENSIVE", "next_play_type": "SIDE_INBOUND"},
    )
    assert timeout_turn["foul_out_player"] == {
        "player_id": "p-away",
        "name": "Away Player",
        "photo": "/images/players/p-away.png",
        "team": "AWAY",
    }
