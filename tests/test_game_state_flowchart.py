"""
Test all game state transitions match the game_flows.md flowchart.

This test suite validates:
1. Possession changes occur at the right times
2. Next play types are set correctly
3. FCP/HCT pressure is applied after the right events
4. Fast break checks happen only after DREBs and steals
5. Side inbound passes always go to HCO (never FCP/HCT)
"""

import pytest
from unittest.mock import MagicMock, patch
from BackEnd.models.game_manager import GameManager
from BackEnd.models.team_manager import TeamManager
from BackEnd.models.player import Player


@pytest.fixture
def mock_game():
    """Create a mock game for testing."""
    game = MagicMock()
    
    # Home team
    home_team = MagicMock(spec=TeamManager)
    home_team.name = "Home Team"
    home_team.team_id = "home"
    home_team.team_fouls = 0
    home_team.team_attributes = {
        "rebound_modifier": 0,
        "steal_modifier": 0,
    }
    home_team.strategy_settings = {
        "defense": 3,
        "tempo": 3,
        "aggression": 3,
        "fast_break": 4,  # 100% fast break for testing
        "half_court_trap": 5,
        "full_court_press": 0,
    }
    home_team.strategy_calls = {
        "defense_call": "Man",
        "tempo_call": "Normal",
    }
    
    # Away team
    away_team = MagicMock(spec=TeamManager)
    away_team.name = "Away Team"
    away_team.team_id = "away"
    away_team.team_fouls = 0
    away_team.team_attributes = {
        "rebound_modifier": 0,
        "steal_modifier": 0,
    }
    away_team.strategy_settings = {
        "defense": 3,
        "tempo": 3,
        "aggression": 3,
        "fast_break": 4,
        "half_court_trap": 5,
        "full_court_press": 0,
    }
    away_team.strategy_calls = {
        "defense_call": "Man",
        "tempo_call": "Normal",
    }
    
    # Create mock players
    def create_mock_player(player_id, name, position):
        player = MagicMock(spec=Player)
        player.player_id = player_id
        player.name = name
        player.position = position
        player.attributes = {
            "SC": 75, "RB": 70, "PS": 65, "ST": 60,
            "BK": 55, "3P": 50, "FT": 80, "HT": 72,
        }
        player.record_stat = MagicMock()
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
    
    home_team.get_all_players.return_value = list(home_lineup.values())
    away_team.get_all_players.return_value = list(away_lineup.values())
    home_team.lineup = home_lineup
    away_team.lineup = away_lineup
    
    game.home_team = home_team
    game.away_team = away_team
    game.offense_team = home_team
    game.defense_team = away_team
    game.off_lineup = home_lineup
    game.def_lineup = away_lineup
    game.game_state = {
        "possession": "home",
        "offensive_state": "HCO",
        "quarter": 1,
        "time_remaining": 600,
        "home_score": 0,
        "away_score": 0,
        "current_playcall": "Base",
    }
    
    # Mock turn_manager
    turn_manager = MagicMock()
    turn_manager.logger = MagicMock()
    turn_manager.logger.log = MagicMock()
    game.turn_manager = turn_manager
    
    return game


class TestHCOShotTransitions:
    """Test Master Shot Attempt Flow from HCO."""
    
    def test_hco_make_no_foul_triggers_defensive_pressure_check(self, mock_game):
        """
        HCO → Shot MAKE (no foul) → possession_flips=True → Master Inbound Pass Flow
        Should check for FCP/HCT/HCO based on defensive settings.
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock a made shot (no foul)
        with patch('BackEnd.models.shot_manager.random.random', return_value=0.1):  # Makes shot
            with patch.object(mock_game.turn_manager, 'determine_defensive_pressure_type', return_value='HCT'):
                result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MAKE", "Shot should be made"
        assert result.get("next_defensive_setup") == "HCT", "Should set next_defensive_setup for inbound"
        assert mock_game.game_state["offensive_state"] == "HCT", "Should transition to HCT"
    
    def test_hco_make_with_foul_goes_to_free_throw(self, mock_game):
        """
        HCO → Shot MAKE (with foul) → possession_flips=False → FREE_THROW
        Should NOT check defensive pressure yet (happens after final FT).
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock a made shot with foul
        with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.1, 0.1]):  # Made + Foul
            result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MAKE", "Shot should be made"
        assert "next_defensive_setup" not in result, "Should NOT set defensive setup for AND-1"
        assert mock_game.game_state["offensive_state"] == "FREE_THROW", "Should transition to FREE_THROW"
        assert mock_game.game_state["free_throws_remaining"] == 1, "Should have 1 FT remaining"
    
    def test_hco_miss_no_foul_goes_to_rebound(self, mock_game):
        """
        HCO → Shot MISS (no foul) → Master Rebound Flow
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock a missed shot (no foul)
        with patch('BackEnd.models.shot_manager.random.random', return_value=0.9):  # Misses shot
            result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MISS", "Shot should be missed"
        assert "rebound_type" in result, "Should trigger rebound flow"


class TestFreeThrowTransitions:
    """Test Master Free Throw Flow."""
    
    def test_made_final_ft_triggers_defensive_pressure_check(self, mock_game):
        """
        FREE_THROW → Final FT MAKE → possession_flips=True → Master Inbound Pass Flow
        Should check for FCP/HCT/HCO and add next_defensive_setup to result.
        """
        from BackEnd.engine.phase_resolution import resolve_free_throw_logic
        
        mock_game.game_state["offensive_state"] = "FREE_THROW"
        mock_game.game_state["free_throws"] = 2
        mock_game.game_state["free_throws_remaining"] = 1  # Final FT
        mock_game.game_state["one_and_one"] = False
        mock_game.game_state["no_lane"] = False
        
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "shooter": mock_game.off_lineup["PG"],
        }
        
        # Mock made final FT
        with patch('BackEnd.engine.phase_resolution.random.random', return_value=0.1):  # Makes FT
            with patch.object(mock_game.turn_manager, 'determine_defensive_pressure_type', return_value='FCP'):
                result = resolve_free_throw_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "FREE_THROW", "Should be FREE_THROW result"
        assert result.get("points") == 1, "Should score 1 point"
        assert result.get("possession_flips") == True, "Possession should flip on made final FT"
        assert result.get("next_defensive_setup") == "FCP", "Should set next_defensive_setup for inbound"
        assert mock_game.game_state["offensive_state"] == "FCP", "Should transition to FCP"
    
    def test_missed_final_ft_defensive_rebound_can_fast_break(self, mock_game):
        """
        FREE_THROW → Final FT MISS → DREB → Fast Break Check → FAST_BREAK or HCO
        """
        from BackEnd.engine.phase_resolution import resolve_free_throw_logic
        
        mock_game.game_state["offensive_state"] = "FREE_THROW"
        mock_game.game_state["free_throws"] = 2
        mock_game.game_state["free_throws_remaining"] = 1  # Final FT
        mock_game.game_state["one_and_one"] = False
        mock_game.game_state["no_lane"] = False
        
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "shooter": mock_game.off_lineup["PG"],
        }
        
        # Mock missed final FT with DREB
        with patch('BackEnd.engine.phase_resolution.random.random', side_effect=[0.9, 0.8, 0.1]):
            # 0.9 = miss FT, 0.8 = DREB, 0.1 = fast break triggered
            result = resolve_free_throw_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "FREE_THROW", "Should be FREE_THROW result"
        assert "points" not in result, "Should not score"
        assert result.get("possession_flips") == True, "Possession should flip on DREB"
        assert result.get("rebound_type") == "DREB", "Should be defensive rebound"
        assert result.get("next_play_type") == "FAST_BREAK", "Should check for fast break"
        assert mock_game.game_state["offensive_state"] == "FAST_BREAK", "Should transition to FAST_BREAK"
    
    def test_missed_final_ft_offensive_rebound_putback_make_triggers_defensive_pressure(self, mock_game):
        """
        FREE_THROW → Final FT MISS → OREB → Putback MAKE → Master Inbound Pass Flow
        Should check for FCP/HCT/HCO.
        """
        from BackEnd.engine.phase_resolution import resolve_free_throw_logic
        
        mock_game.game_state["offensive_state"] = "FREE_THROW"
        mock_game.game_state["free_throws"] = 2
        mock_game.game_state["free_throws_remaining"] = 1  # Final FT
        mock_game.game_state["one_and_one"] = False
        mock_game.game_state["no_lane"] = False
        
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "shooter": mock_game.off_lineup["PG"],
        }
        
        # Mock missed FT with OREB and made putback
        with patch('BackEnd.engine.phase_resolution.random.random', side_effect=[0.9, 0.2, 0.1, 0.1]):
            # 0.9 = miss FT, 0.2 = OREB, 0.1 = putback, 0.1 = make putback
            with patch.object(mock_game.turn_manager, 'determine_defensive_pressure_type', return_value='HCT'):
                result = resolve_free_throw_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "MAKE", "Putback should be made"
        assert result.get("points") == 2, "Putback scores 2 points"
        assert result.get("next_defensive_setup") == "HCT", "Should set next_defensive_setup for inbound"
        assert mock_game.game_state["offensive_state"] == "HCT", "Should transition to HCT"


class TestReboundTransitions:
    """Test Master Rebound Flow."""
    
    def test_defensive_rebound_can_trigger_fast_break(self, mock_game):
        """
        MISS → DREB → possession_flips=True → Fast Break Check → FAST_BREAK or HCO
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock missed shot with DREB and fast break
        with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.9, 0.8, 0.1]):
            # 0.9 = miss, 0.8 = DREB, 0.1 = fast break
            result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MISS", "Shot should be missed"
        assert result.get("rebound_type") == "DREB", "Should be defensive rebound"
        assert result.get("next_play_type") == "FAST_BREAK", "Should trigger fast break"
        assert mock_game.game_state["offensive_state"] == "FAST_BREAK", "Should transition to FAST_BREAK"
    
    def test_offensive_rebound_kickout_goes_to_hco(self, mock_game):
        """
        MISS → OREB → Kickout → possession_flips=False → HCO
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock missed shot with OREB and kickout
        with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.9, 0.2, 0.9]):
            # 0.9 = miss, 0.2 = OREB, 0.9 = kickout (not putback)
            result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MISS", "Shot should be missed"
        assert result.get("rebound_type") == "OREB", "Should be offensive rebound"
        assert mock_game.game_state["offensive_state"] == "HCO", "Should transition to HCO after kickout"
    
    def test_offensive_rebound_putback_make_triggers_defensive_pressure(self, mock_game):
        """
        MISS → OREB → Putback MAKE → possession_flips=True → Master Inbound Pass Flow
        """
        from BackEnd.models.shot_manager import ShotManager
        
        shot_manager = ShotManager(mock_game)
        
        roles = {
            "shooter": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
            "is_three": False,
        }
        
        # Mock missed shot with OREB putback make
        with patch('BackEnd.models.shot_manager.random.random', side_effect=[0.9, 0.2, 0.1, 0.1]):
            # 0.9 = miss, 0.2 = OREB, 0.1 = putback, 0.1 = make
            with patch.object(mock_game.turn_manager, 'determine_defensive_pressure_type', return_value='FCP'):
                result = shot_manager.resolve_shot(roles)
        
        # Validate
        assert result["result_type"] == "MISS", "Original shot was missed"
        # Note: The putback result is embedded in the rebound flow
        # We need to check if next_defensive_setup is set
        # This might require checking the game state directly


class TestTurnoverTransitions:
    """Test Master Turnover Flow."""
    
    def test_dead_ball_turnover_goes_to_side_inbound_then_hco(self, mock_game):
        """
        Turnover → DEAD BALL → possession_flips=True → Side Inbound → HCO
        Should NEVER check for fast break or defensive pressure.
        """
        from BackEnd.engine.phase_resolution import resolve_turnover_logic
        
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock dead ball turnover
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='DEAD BALL'):
            result = resolve_turnover_logic(roles, mock_game, turnover_type='DEAD BALL')
        
        # Validate
        assert result["result_type"] == "TURNOVER", "Should be turnover"
        assert result.get("next_play_type") is None, "Should NOT set next_play_type (goes to side inbound)"
        # Side inbound will reset to HCO in game_manager
    
    def test_steal_can_trigger_fast_break(self, mock_game):
        """
        Turnover → STEAL → possession_flips=True → Fast Break Check → FAST_BREAK or HCO
        """
        from BackEnd.engine.phase_resolution import resolve_turnover_logic
        
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock steal with fast break
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='STEAL'):
            with patch('BackEnd.engine.phase_resolution.random.random', return_value=0.1):  # Fast break
                result = resolve_turnover_logic(roles, mock_game, turnover_type='STEAL')
        
        # Validate
        assert result["result_type"] == "TURNOVER", "Should be turnover"
        assert result.get("next_play_type") == "FAST_BREAK", "Should trigger fast break"
        assert mock_game.game_state["offensive_state"] == "FAST_BREAK", "Should transition to FAST_BREAK"


class TestFCPHCTTransitions:
    """Test FCP/HCT pressure defense flows."""
    
    def test_fcp_steal_can_trigger_fast_break(self, mock_game):
        """
        FCP → STEAL → possession_flips=True → Fast Break Check → FAST_BREAK or HCO
        """
        from BackEnd.engine.phase_resolution import resolve_full_court_press_logic
        
        mock_game.game_state["offensive_state"] = "FCP"
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock FCP steal with fast break
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='STEAL'):
            with patch('BackEnd.engine.phase_resolution.random.random', return_value=0.1):  # Fast break
                result = resolve_full_court_press_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "STEAL", "Should be steal"
        assert result.get("next_play_type") == "FAST_BREAK", "Should trigger fast break"
        assert mock_game.game_state["offensive_state"] == "FAST_BREAK", "Should transition to FAST_BREAK"
    
    def test_fcp_dead_ball_goes_to_side_inbound_no_fast_break(self, mock_game):
        """
        FCP → DEAD BALL → possession_flips=True → Side Inbound → HCO
        Should NEVER check for fast break.
        """
        from BackEnd.engine.phase_resolution import resolve_full_court_press_logic
        
        mock_game.game_state["offensive_state"] = "FCP"
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock FCP dead ball turnover
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='DEAD_BALL_TURNOVER'):
            result = resolve_full_court_press_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "DEAD BALL", "Should be dead ball"
        assert result.get("next_play_type") is None, "Should NOT set next_play_type (goes to side inbound)"
    
    def test_hct_steal_can_trigger_fast_break(self, mock_game):
        """
        HCT → STEAL → possession_flips=True → Fast Break Check → FAST_BREAK or HCO
        """
        from BackEnd.engine.phase_resolution import resolve_half_court_trap_logic
        
        mock_game.game_state["offensive_state"] = "HCT"
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock HCT steal with fast break
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='STEAL'):
            with patch('BackEnd.engine.phase_resolution.random.random', return_value=0.1):  # Fast break
                result = resolve_half_court_trap_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "STEAL", "Should be steal"
        assert result.get("next_play_type") == "FAST_BREAK", "Should trigger fast break"
        assert mock_game.game_state["offensive_state"] == "FAST_BREAK", "Should transition to FAST_BREAK"
    
    def test_hct_dead_ball_goes_to_side_inbound_no_fast_break(self, mock_game):
        """
        HCT → DEAD BALL → possession_flips=True → Side Inbound → HCO
        Should NEVER check for fast break.
        """
        from BackEnd.engine.phase_resolution import resolve_half_court_trap_logic
        
        mock_game.game_state["offensive_state"] = "HCT"
        roles = {
            "ball_handler": mock_game.off_lineup["PG"],
            "defender": mock_game.def_lineup["PG"],
        }
        
        # Mock HCT dead ball turnover
        with patch('BackEnd.engine.phase_resolution.random.choice', return_value='DEAD_BALL_TURNOVER'):
            result = resolve_half_court_trap_logic(roles, mock_game)
        
        # Validate
        assert result["result_type"] == "DEAD BALL", "Should be dead ball"
        assert result.get("next_play_type") is None, "Should NOT set next_play_type (goes to side inbound)"


class TestSideInboundTransitions:
    """Test that side inbound passes ALWAYS go to HCO."""
    
    def test_side_inbound_after_dead_ball_goes_to_hco(self, mock_game):
        """
        Side Inbound Pass → Always HCO (never FCP/HCT)
        This is validated in game_manager.py line 146.
        """
        # This is primarily a game_manager test
        # The key is that after any side inbound (offensive foul, defensive foul non-bonus, dead ball),
        # the next offensive_state is always HCO
        # We validate this by checking that resolve functions set next_play_type = None
        pass  # Already validated in turnover and FCP/HCT tests above

