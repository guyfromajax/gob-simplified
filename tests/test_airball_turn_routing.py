"""Airball miss routes to BIP (no rebound turn)."""
from unittest.mock import MagicMock, patch

import pytest

from BackEnd.constants.shot_variants import SHOT_VARIANT_AIRBALL
from BackEnd.models.player import Player
from BackEnd.models.team_manager import TeamManager


@pytest.fixture
def mock_game():
    game = MagicMock()

    def create_mock_player(player_id, name, position):
        player = MagicMock(spec=Player)
        player.player_id = player_id
        player.name = name
        player.position = position
        player.attributes = {
            "SC": 75, "SH": 75, "ID": 70, "OD": 70,
            "PS": 65, "BH": 65, "RB": 70, "ST": 60, "AG": 70,
            "FT": 80, "ND": 70, "IQ": 70, "CH": 70,
            "EM": 5, "MO": 5, "NG": 1.0,
        }
        player.record_stat = MagicMock()
        player.record_shot_result = MagicMock()
        player.add_momentum = MagicMock()
        player.coords = {"x": 50, "y": 25}
        return player

    home_lineup = {
        "PG": create_mock_player("h1", "Home PG", "PG"),
        "SG": create_mock_player("h2", "Home SG", "SG"),
        "SF": create_mock_player("h3", "Home SF", "SF"),
        "PF": create_mock_player("h4", "Home PF", "PF"),
        "C": create_mock_player("h5", "Home C", "C"),
    }
    away_lineup = {
        "PG": create_mock_player("a1", "Away PG", "PG"),
        "SG": create_mock_player("a2", "Away SG", "SG"),
        "SF": create_mock_player("a3", "Away SF", "SF"),
        "PF": create_mock_player("a4", "Away PF", "PF"),
        "C": create_mock_player("a5", "Away C", "C"),
    }

    home_team = MagicMock(spec=TeamManager)
    home_team.name = "Home Team"
    home_team.team_id = "home"
    home_team.team_fouls = 0
    home_team.team_attributes = {"shot_threshold": 100, "rebound_modifier": 0}
    home_team.strategy_settings = {
        "defense": 3, "tempo": 3, "rebounding": 2, "fast_breaks": 2,
    }
    home_team.lineup = home_lineup

    away_team = MagicMock(spec=TeamManager)
    away_team.name = "Away Team"
    away_team.team_id = "away"
    away_team.team_fouls = 0
    away_team.team_attributes = {"shot_threshold": 100, "rebound_modifier": 0}
    away_team.strategy_settings = {
        "defense": 3, "tempo": 3, "rebounding": 2, "fast_breaks": 2,
    }
    away_team.lineup = away_lineup

    game.home_team = home_team
    game.away_team = away_team
    game.offense_team = home_team
    game.defense_team = away_team
    game.quarter = 1
    game.game_state = {
        "offensive_state": "HCO",
        "quarter": 1,
        "time_remaining": 600,
        "current_playcall": "Base",
        # Required ShotManager state; real games initialize and set this before HCO.
        "defense_playcall": "man",
    }
    game.turn_manager = MagicMock()
    game.turn_manager.logger = MagicMock()
    game.turn_manager.logger.log = MagicMock()
    game.turn_manager.determine_defensive_pressure_type = MagicMock(return_value="HCO")

    return game


def test_hco_airball_miss_routes_to_baseline_inbound(mock_game):
    from BackEnd.models.shot_manager import ShotManager

    shot_manager = ShotManager(mock_game)
    roles = {
        "shooter": mock_game.offense_team.lineup["PG"],
        "defender": mock_game.defense_team.lineup["PG"],
        "is_three": False,
        "steps": [],
        "shot_type": "outside",
    }

    with patch("BackEnd.models.shot_manager.random.random", return_value=0.9):
        with patch.object(
            shot_manager,
            "calculate_shot_score",
            return_value=(0, 0, 0, False, None, 0),
        ):
            with patch(
                "BackEnd.models.shot_manager.select_shot_variant",
                return_value=SHOT_VARIANT_AIRBALL,
            ):
                result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MISS"
    assert result.get("shot_variant") == SHOT_VARIANT_AIRBALL
    assert result.get("next_play_type") == "BASELINE_INBOUND"
    assert result.get("possession_flips") is True
    assert "rebounderId" not in result
    assert "rebound_type" not in result
    assert "ball_bounce_x" not in result
    assert "ball_bounce_y" not in result


def test_hco_non_airball_miss_still_resolves_rebound(mock_game):
    from BackEnd.models.shot_manager import ShotManager

    shot_manager = ShotManager(mock_game)
    roles = {
        "shooter": mock_game.offense_team.lineup["PG"],
        "defender": mock_game.defense_team.lineup["PG"],
        "is_three": False,
        "steps": [],
        "shot_type": "outside",
    }

    with patch("BackEnd.models.shot_manager.random.random", return_value=0.9):
        with patch.object(
            shot_manager,
            "calculate_shot_score",
            return_value=(0, 0, 0, False, None, 0),
        ):
            with patch(
                "BackEnd.models.shot_manager.select_shot_variant",
                return_value="CLANK",
            ):
                result = shot_manager.resolve_shot(roles)

    assert result["result_type"] == "MISS"
    assert result.get("shot_variant") == "CLANK"
    assert result.get("next_play_type") != "BASELINE_INBOUND"
    assert result.get("rebounderId")
    assert result.get("rebound_type") in ("DREB", "OREB")
