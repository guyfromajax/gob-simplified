from tests.test_utils import build_mock_game


def _seed_player_ids_and_coords(game):
    for team in (game.home_team, game.away_team):
        for idx, (pos, player) in enumerate((team.lineup or {}).items()):
            player.player_id = f"{team.name}_{pos}"
            player.coords = {"x": 45.0, "y": 10.0 + (5.0 * idx)}
            player.stats["game"].setdefault("MIN", 0)


def _coord_map(game):
    out = {}
    for team in (game.home_team, game.away_team):
        for player in (team.lineup or {}).values():
            out[str(player.player_id)] = dict(player.coords)
    return out


def test_fcp_miss_dreb_promotes_to_discrete_dreb_turn(monkeypatch):
    game = build_mock_game()
    _seed_player_ids_and_coords(game)
    game.game_state["offensive_state"] = "FCP"
    game.game_state["time_remaining"] = 480
    game.game_state["shot_clock_remaining"] = 24
    game.offense_team = game.home_team
    game.defense_team = game.away_team

    rebounder = game.defense_team.lineup["C"]
    shooter = game.offense_team.lineup["SG"]
    defender = game.defense_team.lineup["SG"]
    end_coords = _coord_map(game)
    bounce = {"x": 11.0, "y": 31.0}

    fcp_miss = {
        "current_turn": "FCP",
        "result_type": "MISS",
        "text": "PRESS! Missed jumper.",
        "offense_team_id": game.offense_team.team_id,
        "time_elapsed": 6,
        "possession_flips": True,
        "next_play_type": "FAST_BREAK",
        "rebound_type": "DREB",
        "rebounderId": rebounder.player_id,
        "ball_bounce_x": bounce["x"],
        "ball_bounce_y": bounce["y"],
        "skeleton": {"steps": []},
        "animations": [],
        "roles": {
            "ball_handler": shooter,
            "shooter": shooter,
            "defender": defender,
        },
        "animation_steps": [
            {
                "start": {
                    "coords": end_coords,
                    "ball": {"owner_player_id": shooter.player_id},
                    "clock": {
                        "clock_remaining": 480.0,
                        "shot_clock_remaining": 24.0,
                    },
                },
                "end": {
                    "coords": end_coords,
                    "ball": {"coords": bounce},
                    "time_elapsed": 6.0,
                    "clock": {
                        "clock_remaining": 474.0,
                        "shot_clock_remaining": 18.0,
                    },
                    "next": {
                        "kind": "turn_stop",
                        "event": "SHOT_ATTEMPT",
                        "payload": {"result": "MISS"},
                    },
                },
            }
        ],
    }

    monkeypatch.setattr(game.turn_manager, "run_micro_turn", lambda: fcp_miss)

    result = game.simulate_macro_turn()

    assert result is fcp_miss
    assert fcp_miss["next_play_type"] == "DREB"
    assert fcp_miss["next_turn"] == "DREB"

    assert len(game.turns) == 2
    dreb_turn = game.turns[-1]
    assert dreb_turn["current_turn"] == "DREB"
    assert dreb_turn["result_type"] == "DREB"
    assert dreb_turn["next_play_type"] == "FAST_BREAK"
    assert dreb_turn["next_turn"] == "FAST_BREAK"
    assert dreb_turn["rebounderId"] == rebounder.player_id
    assert dreb_turn["final_ball_handler_id"] == rebounder.player_id
    assert dreb_turn["animation_steps"][-1]["end"]["ball"]["owner_player_id"] == rebounder.player_id
