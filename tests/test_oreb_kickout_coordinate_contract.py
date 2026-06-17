"""OREB kickout schema completeness and home/away coordinate parity."""

import random
from unittest.mock import patch

import pytest

from BackEnd.models.game_manager import GameManager
from BackEnd.models.player import Player
from BackEnd.models.turn_manager import TurnManager


POSITIONS = ("PG", "SG", "SF", "PF", "C")


def _player(team_name, position):
    return Player(
        {
            "_id": f"{team_name}_{position}",
            "first_name": team_name,
            "last_name": position,
            "team": team_name,
            "attributes": {
                key: 50
                for key in (
                    "SC",
                    "SH",
                    "ID",
                    "OD",
                    "PS",
                    "BH",
                    "RB",
                    "AG",
                    "ST",
                    "ND",
                    "IQ",
                    "FT",
                    "NG",
                    "CH",
                )
            },
        }
    )


def _build_game(*, away_offense):
    game = GameManager("Home", "Away")
    game.home_team.team_id = "home"
    game.away_team.team_id = "away"
    for team in (game.home_team, game.away_team):
        team.lineup = {
            position: _player(team.name, position) for position in POSITIONS
        }

    game.offense_team = game.away_team if away_offense else game.home_team
    game.defense_team = game.home_team if away_offense else game.away_team
    game.turn_manager = TurnManager(game)
    game.game_state["time_remaining"] = 300
    game.game_state["shot_clock_remaining"] = 20

    for team in (game.home_team, game.away_team):
        for index, player in enumerate(team.lineup.values()):
            home_x = 72.0 + index * 2.0
            player.coords = {
                "x": 100.0 - home_x if away_offense else home_x,
                "y": 9.0 + index * 8.0,
            }

    rebounder = game.offense_team.lineup["C"]
    bounce = {"x": 16.0 if away_offense else 84.0, "y": 25.0}
    final_coords = {
        str(player.player_id): dict(player.coords)
        for team in (game.home_team, game.away_team)
        for player in team.lineup.values()
    }
    game.turns = [
        {
            "result_type": "BLOCK",
            "current_turn": "HCO",
            "ball_bounce_x": bounce["x"],
            "ball_bounce_y": bounce["y"],
            "final_coords": final_coords,
            "offense_rebounders": [rebounder.player_id],
            "defense_rebounders": [],
        }
    ]
    game.game_state["pending_oreb"] = {
        "rebounder": rebounder,
        "rebounder_id": rebounder.player_id,
        "from_block": False,
    }
    return game


def _resolve_kickout(*, away_offense, from_block, seed):
    game = _build_game(away_offense=away_offense)
    game.game_state["pending_oreb"]["from_block"] = from_block
    rebounder = game.game_state["pending_oreb"]["rebounder"]
    pg = game.offense_team.lineup["PG"]

    kickout_event = {
        "event_type": "KICKOUT_RESET",
        "rebounderId": rebounder.player_id,
        "pgId": pg.player_id,
        "pass": {
            "fromCoords": dict(rebounder.coords),
            "toCoords": dict(pg.coords),
            "duration": 2,
        },
        "timeElapsed": 2,
        "position_snapshots": [],
    }

    random.seed(seed)
    with patch(
        "BackEnd.utils.shared.resolve_offensive_rebound",
        return_value=kickout_event,
    ):
        result = game.turn_manager.resolve_offensive_rebound_turn()
    return result


def _assert_complete_kickout(result):
    assert result["result_type"] == "OREB_KICKOUT"
    steps = result.get("animation_steps")
    assert isinstance(steps, list)
    assert len(steps) == 1

    rebounder_id = str(result["rebounderId"])
    assert steps[0]["end"]["ball"]["owner_player_id"] == rebounder_id
    assert steps[0]["end"]["next"] == {"kind": "next_step", "index": 999}
    assert result.get("pgId") is None
    assert result.get("kickout_deferred_to_hco_entry") is True
    assert steps[0]["start"]["advance_trigger"]["condition"] == "player_reaches_position"


@pytest.mark.parametrize("from_block", [False, True])
def test_oreb_kickout_always_emits_complete_schema(from_block):
    for away_offense in (False, True):
        result = _resolve_kickout(
            away_offense=away_offense,
            from_block=from_block,
            seed=4815,
        )
        _assert_complete_kickout(result)


@pytest.mark.parametrize("from_block", [False, True])
def test_oreb_kickout_home_away_steps_are_mirrored(from_block):
    home = _resolve_kickout(
        away_offense=False,
        from_block=from_block,
        seed=9917,
    )
    away = _resolve_kickout(
        away_offense=True,
        from_block=from_block,
        seed=9917,
    )

    _assert_complete_kickout(home)
    _assert_complete_kickout(away)

    home_steps = home["animation_steps"]
    away_steps = away["animation_steps"]
    assert len(home_steps) == len(away_steps)

    for home_step, away_step in zip(home_steps, away_steps):
        for phase in ("start", "end"):
            home_coords = home_step[phase]["coords"]
            away_coords = away_step[phase]["coords"]
            assert home_coords.keys() == away_coords.keys()
            for player_id, home_coord in home_coords.items():
                counterpart_id = (
                    player_id.replace("Home_", "Away_", 1)
                    if player_id.startswith("Home_")
                    else player_id.replace("Away_", "Home_", 1)
                )
                away_coord = away_coords[counterpart_id]
                assert away_coord["x"] == pytest.approx(100.0 - home_coord["x"])
                assert away_coord["y"] == pytest.approx(home_coord["y"])
