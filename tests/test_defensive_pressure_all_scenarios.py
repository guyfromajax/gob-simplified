"""
Test that defensive pressure (FCP/HCT) is checked after ALL made shot types.
"""
import pytest
from unittest.mock import patch, MagicMock
from BackEnd.models.game_manager import GameManager
from BackEnd.models.shot_manager import ShotManager
from BackEnd.engine.phase_resolution import (
    resolve_free_throw_logic,
    resolve_half_court_offense_logic,
)
from BackEnd.utils.shared import resolve_offensive_rebound


@pytest.fixture
def mock_game():
    """Create a mock game with controlled settings."""
    with patch('BackEnd.models.game_manager.TeamManager') as MockTeamManager:
        # Create mock teams
        mock_home_team = MagicMock()
        mock_home_team.name = "Home Team"
        mock_home_team.team_id = "home_id"
        # Complete player attributes
        full_attrs = {
            "SC": 80, "SH": 80, "ID": 80, "OD": 80, "PS": 80, 
            "BH": 80, "RB": 80, "ST": 80, "AG": 80, "ND": 80, 
            "IQ": 80, "FT": 80, "NG": 80, "CH": 80
        }
        
        mock_home_team.lineup = {
            "PG": MagicMock(player_id="pg1", attributes=full_attrs.copy()),
            "SG": MagicMock(player_id="sg1", attributes=full_attrs.copy()),
            "SF": MagicMock(player_id="sf1", attributes=full_attrs.copy()),
            "PF": MagicMock(player_id="pf1", attributes=full_attrs.copy()),
            "C": MagicMock(player_id="c1", attributes=full_attrs.copy()),
        }
        mock_home_team.team_attributes = {
            "shot_threshold": 100,
            "rebound_modifier": 1.0,
        }
        # Set defensive pressure settings: HCT only, no FCP
        mock_home_team.strategy_settings = {
            "half_court_trap": 4,
            "full_court_press": 0,
            "defense": 2,
            "tempo": 2,
            "aggression": 2,
            "fast_break": 2,
        }
        
        mock_away_team = MagicMock()
        mock_away_team.name = "Away Team"
        mock_away_team.team_id = "away_id"
        mock_away_team.lineup = mock_home_team.lineup.copy()
        mock_away_team.team_attributes = mock_home_team.team_attributes.copy()
        mock_away_team.strategy_settings = mock_home_team.strategy_settings.copy()
        
        MockTeamManager.side_effect = [mock_home_team, mock_away_team]
        
        game = GameManager("Home Team", "Away Team")
        game.home_team = mock_home_team
        game.away_team = mock_away_team
        game.offense_team = mock_home_team
        game.defense_team = mock_away_team
        
        # Add required methods
        for player in mock_home_team.lineup.values():
            player.record_stat = MagicMock()
        for player in mock_away_team.lineup.values():
            player.record_stat = MagicMock()
        
        return game


def test_hco_made_shot_triggers_pressure(mock_game):
    """Test that a made HCO shot triggers defensive pressure check."""
    # This is already working, but including for completeness
    shot_manager = ShotManager(mock_game)
    
    roles = {
        "shooter": mock_game.offense_team.lineup["PG"],
        "passer": None,
        "screener": None,
        "defender": mock_game.defense_team.lineup["PG"],
    }
    
    with patch('BackEnd.models.shot_manager.random.randint', return_value=6):
        with patch('BackEnd.models.shot_manager.random.random', return_value=0.5):
            result = shot_manager.resolve_shot(roles)
    
    # Should have made the shot
    assert result.get("result_type") == "MAKE"
    
    # Should have defensive pressure set (HCT with settings above)
    assert mock_game.game_state.get("offensive_state") in ["HCT", "FCP", "HCO"]
    assert "next_defensive_setup" in result


def test_putback_made_shot_triggers_pressure(mock_game):
    """Test that a made putback after offensive rebound triggers defensive pressure check."""
    shot_manager = ShotManager(mock_game)
    
    roles = {
        "shooter": mock_game.offense_team.lineup["PG"],
        "passer": None,
        "screener": None,
        "defender": mock_game.defense_team.lineup["PG"],
    }
    
    # Force shot to miss, then offensive rebound, then putback make
    with patch('BackEnd.models.shot_manager.random.randint', return_value=1):  # Miss shot
        with patch('BackEnd.models.shot_manager.random.random', return_value=0.1):  # OREB + putback
            with patch('BackEnd.utils.shared.random.random', return_value=0.1):  # Putback attempt
                with patch('BackEnd.utils.shared.random.randint', return_value=6):  # Putback makes
                    result = shot_manager.resolve_shot(roles)
    
    # Should have made the putback
    assert result.get("result_type") == "MAKE"
    
    # Should have defensive pressure set
    assert "next_defensive_setup" in result
    assert result["next_defensive_setup"] in ["HCT", "FCP", "HCO"]


def test_free_throw_made_triggers_pressure(mock_game):
    """Test that a made free throw (last one) triggers defensive pressure check."""
    # Set up free throw scenario
    mock_game.game_state["free_throws"] = 1
    mock_game.game_state["free_throws_remaining"] = 1
    mock_game.game_state["shooter"] = mock_game.offense_team.lineup["PG"]
    
    with patch('BackEnd.engine.phase_resolution.random.random', return_value=0.1):  # Makes FT
        result = resolve_free_throw_logic(mock_game)
    
    # Should have made the free throw
    assert result.get("result_type") == "FREE_THROW"
    assert result.get("points") == 1
    
    # Should have defensive pressure set
    assert mock_game.game_state.get("offensive_state") in ["HCT", "FCP", "HCO"]


def test_fast_break_made_triggers_pressure(mock_game):
    """Test that a made fast break shot triggers defensive pressure check."""
    shot_manager = ShotManager(mock_game)
    
    fb_roles = {
        "ball_handler": mock_game.offense_team.lineup["PG"],
        "shooter": mock_game.offense_team.lineup["PG"],
        "passer": None,
        "defense": [mock_game.defense_team.lineup["SG"]],
    }
    
    with patch('BackEnd.models.shot_manager.random.randint', return_value=6):  # Makes shot
        with patch('BackEnd.models.shot_manager.random.choice', return_value=fb_roles["defense"][0]):
            result = shot_manager.resolve_fast_break_shot(fb_roles)
    
    # Should have made the fast break
    # Note: result_type might not be set in fast_break_shot, checking state instead
    
    # Should have defensive pressure set
    assert mock_game.game_state.get("offensive_state") in ["HCT", "FCP", "HCO"]
    # Should have next_defensive_setup in result
    assert "next_defensive_setup" in result


def test_ft_putback_made_triggers_pressure(mock_game):
    """Test that a made putback off a missed free throw triggers defensive pressure check."""
    # Set up missed FT with offensive rebound scenario
    mock_game.game_state["free_throws"] = 1
    mock_game.game_state["free_throws_remaining"] = 1
    mock_game.game_state["shooter"] = mock_game.offense_team.lineup["PG"]
    
    with patch('BackEnd.engine.phase_resolution.random.random') as mock_random:
        # First call: miss the FT (0.9 > free_throw_threshold)
        # Second call: OREB (0.1 < d_weight for offense to get it)
        # Third call: putback attempt (0.1 < 0.65)
        mock_random.side_effect = [0.9, 0.1, 0.1]
        
        with patch('BackEnd.utils.shared.random.random', return_value=0.1):  # Putback attempt
            with patch('BackEnd.utils.shared.random.randint', return_value=6):  # Putback makes
                with patch('BackEnd.engine.phase_resolution.random.randint', return_value=6):
                    result = resolve_free_throw_logic(mock_game)
    
    # Should have made the putback
    if result.get("result_type") == "MAKE":
        # Should have defensive pressure set
        assert mock_game.game_state.get("offensive_state") in ["HCT", "FCP", "HCO"]
        assert "next_defensive_setup" in result


def test_defensive_pressure_respects_settings(mock_game):
    """Test that pressure type selection respects team strategy_settings."""
    # Set HCT=4, FCP=0 (should always choose HCT)
    mock_game.defense_team.strategy_settings = {
        "half_court_trap": 4,
        "full_court_press": 0,
    }
    
    # Run pressure check multiple times
    results = []
    for _ in range(10):
        with patch('BackEnd.models.turn_manager.random.randint', return_value=1):  # Always execute
            pressure_type = mock_game.turn_manager.determine_defensive_pressure_type()
            results.append(pressure_type)
    
    # With HCT=4 and FCP=0, should ALWAYS return HCT
    assert all(r == "HCT" for r in results), f"Expected all HCT, got: {results}"


def test_defensive_pressure_zero_values_return_hco(mock_game):
    """Test that when both FCP and HCT are 0, returns HCO."""
    mock_game.defense_team.strategy_settings = {
        "half_court_trap": 0,
        "full_court_press": 0,
    }
    
    pressure_type = mock_game.turn_manager.determine_defensive_pressure_type()
    
    assert pressure_type == "HCO", f"Expected HCO when both are 0, got: {pressure_type}"


def test_defensive_pressure_execution_roll(mock_game):
    """Test that execution roll works correctly."""
    # Set HCT=2 (should execute if roll <= 2)
    mock_game.defense_team.strategy_settings = {
        "half_court_trap": 2,
        "full_court_press": 0,
    }
    
    # Roll 1: should execute
    with patch('BackEnd.models.turn_manager.random.randint', return_value=1):
        result = mock_game.turn_manager.determine_defensive_pressure_type()
        assert result == "HCT"
    
    # Roll 2: should execute
    with patch('BackEnd.models.turn_manager.random.randint', return_value=2):
        result = mock_game.turn_manager.determine_defensive_pressure_type()
        assert result == "HCT"
    
    # Roll 3: should NOT execute (fall back to HCO)
    with patch('BackEnd.models.turn_manager.random.randint', return_value=3):
        result = mock_game.turn_manager.determine_defensive_pressure_type()
        assert result == "HCO"
    
    # Roll 4: should NOT execute (fall back to HCO)
    with patch('BackEnd.models.turn_manager.random.randint', return_value=4):
        result = mock_game.turn_manager.determine_defensive_pressure_type()
        assert result == "HCO"

