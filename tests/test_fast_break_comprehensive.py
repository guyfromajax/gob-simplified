"""
Comprehensive tests for Fast Break instances from HCO shot attempt → DREB → Fast Break flow.

Tests cover:
1. Home team on offense during fast break (away team shot in HCO)
2. Away team on offense during fast break (home team shot in HCO)
3. Defensive Stop results
4. Shot Attempt results

Success Criteria:

**Get-Back Player Coordinate Ranges (Offensive players getting back on defense):**
- If home team will be offense on fast break (away team is shooting):
  - X: 40-55 (or 45-55 if IQ > 50)
  - Y: 14-36
- If away team will be offense on fast break (home team is shooting):
  - X: 45-60 (or 45-55 if IQ > 50)
  - Y: 14-36

**Defensive Release Player Coordinate Ranges (Defensive players releasing for fast break):**
- If home team will be offense on fast break (away team is shooting):
  - X: 40-60 (or 50-60 if IQ > 50)
  - Y: 14-36 (or 20-30 if IQ > 50)
- If away team will be offense on fast break (home team is shooting):
  - X: 40-60 (or 40-50 if IQ > 50)
  - Y: 14-36 (or 20-30 if IQ > 50)

**Home Team on Offense (Fast Break):**
- Previous HCO turn: offense_team_id = away team
- Fast Break turn: offense_team_id = home team
- Defensive Stop: ball handler x at stop point > ball handler x at starting spot (moving right toward x=90)
- Shot Attempt: shooter x coord near home rim (x=90), defender x coord is 1-6 less than shooter's x

**Away Team on Offense (Fast Break):**
- Previous HCO turn: offense_team_id = home team
- Fast Break turn: offense_team_id = away team
- Defensive Stop: ball handler x at stop point < ball handler x at starting spot (moving left toward x=10 in HOME orientation)
- Shot Attempt: shooter x coord near away rim (x=10 in HOME orientation), defender x coord is 1-6 greater than shooter's x
"""

import pytest
from unittest.mock import patch, MagicMock
from BackEnd.models.game_manager import GameManager
from BackEnd.models.turn_manager import TurnManager
from tests.test_utils import build_mock_game


def simulate_hco_shot_miss_dreb_fastbreak(game, shooting_team_is_home=True):
    """
    Simulate HCO turn with shot miss, DREB, and Fast Break.
    
    Args:
        game: GameManager instance
        shooting_team_is_home: If True, home team shoots; if False, away team shoots
    
    Returns:
        Tuple of (HCO turn result, Fast Break turn result)
    """
    # Set shooting team
    if shooting_team_is_home:
        game.offense_team = game.home_team
        game.defense_team = game.away_team
    else:
        game.offense_team = game.away_team
        game.defense_team = game.home_team
    
    # Set high tempo for defense to trigger release player
    game.defense_team.strategy_settings["tempo"] = 4  # 100% release chance
    # Set low aggression to prevent defensive fouls
    game.defense_team.strategy_settings["aggression"] = 0  # Lowest aggression = minimal fouls
    # Set rebounding for offense to trigger get-back players
    game.offense_team.strategy_settings["rebounding"] = 3  # 80% chance of 1 get-back
    
    # Force shot miss, DREB, Fast Break
    # random.random() calls in order:
    # 1. defense_releases check
    # 2. offense_getback check
    # 3. shot make/miss (we want miss)
    # 4. block check (if missed)
    # 5. rebound team selection (we want DREB)
    # 6. Fast break check (defense_release_list exists, so Fast Break)
    
    # Mock random values to force: release player, get-back player, miss, no block, DREB
    # Also mock defensive foul check to prevent fouls
    with patch('BackEnd.models.shot_manager.ShotManager.check_defensive_foul_on_shot') as mock_foul_check:
        mock_foul_check.return_value = (False, None)  # No foul
        
        with patch('BackEnd.models.shot_manager.random.random') as mock_random:
            # Force release player (tempo=4 means 100% chance, but still need random < 1.0)
            # Force get-back (rebounding=3 means 80% chance of 1 get-back)
            # Force miss (shot_score < shot_threshold)
            # Force no block
            # Force DREB (d_weight typically ~0.7, so need < 0.7)
            mock_random.side_effect = [
                0.5,  # defense_releases check (50% chance, but tempo=4 overrides to 100%)
                0.3,  # offense_getback check (30% < 80% = 1 get-back)
                0.99, # shot make/miss (99% = miss)
                0.1,  # block check (10% = no block)
                0.3,  # rebound team selection (30% < d_weight ~0.7 = DREB)
            ]
            
            # Also need to mock random.randint for get-back coordinate calculation
            with patch('BackEnd.models.shot_manager.random.randint') as mock_randint:
                # Mock get-back coordinates (will be validated in tests)
                def randint_side_effect(a, b):
                    if a == 40 and b == 55:  # Home offense get-back X (low IQ)
                        return 50
                    elif a == 45 and b == 60:  # Away offense get-back X (low IQ)
                        return 52
                    elif a == 45 and b == 55:  # High IQ get-back X
                        return 50
                    elif a == 14 and b == 36:  # Get-back Y
                        return 25
                    else:
                        return (a + b) // 2  # Default to middle
                mock_randint.side_effect = randint_side_effect
                
                # Run HCO turn
                hco_result = game.turn_manager.run_micro_turn()
    
    # Verify HCO turn result
    assert hco_result["result_type"] == "MISS", "HCO turn should result in MISS"
    assert hco_result.get("rebound_type") == "DREB", "Should be DREB"
    assert hco_result.get("next_play_type") == "FAST_BREAK", "Next play should be FAST_BREAK"
    assert "offense_getback" in hco_result, "Should have offense_getback list"
    assert "offense_getback_coords" in hco_result, "Should have offense_getback_coords"
    assert "defense_release" in hco_result, "Should have defense_release list"
    
    return hco_result


def simulate_fast_break_turn(game, force_defensive_stop=True, is_home_offense=True):
    """
    Simulate Fast Break turn with controlled outcome.
    
    Args:
        game: GameManager instance
        force_defensive_stop: If True, force defensive stop; if False, force shot attempt
        is_home_offense: If True, home team on offense; if False, away team on offense
    
    Returns:
        Fast Break turn result
    """
    # Set offense team
    if is_home_offense:
        game.offense_team = game.home_team
        game.defense_team = game.away_team
    else:
        game.offense_team = game.away_team
        game.defense_team = game.home_team
    
    # Set up DREB → Fast Break
    game.game_state["last_rebound"] = "DREB"
    if is_home_offense:
        game.game_state["last_rebounder"] = game.home_team.lineup["C"]
    else:
        game.game_state["last_rebounder"] = game.away_team.lineup["C"]
    game.game_state["offensive_state"] = "FAST_BREAK"
    
    # Set release player (outlet receiver)
    release_player = game.offense_team.lineup["PG"]
    game.game_state["last_release_player"] = release_player
    
    # Mock outlet pass and outcome
    # Use a callable that handles any number of defenders
    call_index = [0]  # Track call order using list for mutability
    
    with patch('BackEnd.engine.phase_resolution.random.randint') as mock_randint:
        def randint_side_effect(a, b):
            idx = call_index[0]
            call_index[0] += 1
            
            if idx == 0:  # First call: ball_handler_move_x
                return 7  # Ball handler moves 7 spots
            elif idx == 1:  # Second call: ball_handler_move_y
                return 0  # No y movement
            elif idx % 2 == 0:  # Even indices after first 2: defender x positions
                if is_home_offense:
                    # Home offense: ball handler outlet x ~57 (50 + 7), defenders at 50-65
                    # Force defensive stop: x=60 (ahead, 60 >= 57)
                    # Force shot: x=50 (behind, 50 < 57)
                    return 60 if force_defensive_stop else 50
                else:
                    # Away offense: ball handler outlet x ~45 (52 - 7), defenders at 35-50
                    # Force defensive stop: x=40 (ahead, 40 <= 45)
                    # Force shot: x=50 (behind, 50 > 45)
                    return 40 if force_defensive_stop else 50
            else:  # Odd indices after first 2: defender y positions
                return 25  # Defender outlet y (15-35)
        
        mock_randint.side_effect = randint_side_effect
        
        # Mock shot resolution if shot attempt
        if not force_defensive_stop:
            with patch('BackEnd.models.shot_manager.ShotManager.resolve_fast_break_shot') as mock_shot:
                mock_shot.return_value = {
                    "result_type": "MISS",
                    "text": "Fast break shot missed",
                    "time_elapsed": 3
                }
                fb_result = game.turn_manager.run_micro_turn()
        else:
            fb_result = game.turn_manager.run_micro_turn()
    
    return fb_result


@pytest.mark.integration
class TestFastBreakComprehensive:
    """Comprehensive tests for Fast Break flow."""
    
    def test_home_offense_defensive_stop_coordinates(self):
        """
        Test home team on offense, defensive stop:
        - Validate offense team IDs
        - Validate get-back coordinates are used as starting positions
        - Validate ball handler movement direction (x increases toward x=90)
        """
        game = build_mock_game()
        
        # Simulate away team shooting (home team will be offense on fast break)
        hco_result = simulate_hco_shot_miss_dreb_fastbreak(
            game, shooting_team_is_home=False
        )
        
        # Validate HCO turn
        assert hco_result["result_type"] == "MISS", "HCO turn should result in MISS"
        assert hco_result.get("rebound_type") == "DREB", "Should be DREB"
        assert hco_result.get("next_play_type") == "FAST_BREAK", "Next play should be FAST_BREAK"
        
        # Validate offense team IDs
        assert hco_result.get("offense_team_id") == game.away_team.team_id, \
            "HCO turn should have away team on offense"
        
        # Validate get-back coordinates
        getback_coords = hco_result.get("offense_getback_coords", {})
        assert len(getback_coords) > 0, "Should have get-back coordinates"
        
        for player_id, coords in getback_coords.items():
            x = coords.get("x")
            y = coords.get("y")
            # Home team will be offense on fast break (away team is shooting)
            # Get-back: X 40-55 (or 45-55 if IQ > 50), Y 14-36
            assert 40 <= x <= 55, f"Get-back X should be 40-55, got {x}"
            assert 14 <= y <= 36, f"Get-back Y should be 14-36, got {y}"
        
        # Simulate Fast Break turn with defensive stop
        fb_result = simulate_fast_break_turn(
            game, force_defensive_stop=True, is_home_offense=True
        )
        
        # Validate Fast Break turn
        assert fb_result.get("offense_team_id") == game.home_team.team_id, \
            "Fast Break turn should have home team on offense"
        assert fb_result.get("result_type") == "DEFENSIVE_STOP", \
            "Should be defensive stop"
        
        # Validate ball handler used get-back coordinates
        fb_roles = fb_result.get("roles", {})
        ball_handler_id = fb_roles.get("outlet_receiver")
        assert ball_handler_id is not None, "Should have outlet receiver"
        
        # Check if outlet receiver is a get-back player
        if ball_handler_id in getback_coords:
            getback_start_x = getback_coords[ball_handler_id]["x"]
            ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
            # Outlet x should be > get-back start x (moved right toward basket)
            assert ball_handler_outlet_x > getback_start_x, \
                f"Ball handler should move right: outlet_x={ball_handler_outlet_x} > start_x={getback_start_x}"
        
        # Validate animation data: ball handler stop point > starting spot
        animations = fb_result.get("animations", [])
        ball_handler_anim = None
        for anim in animations:
            if anim.get("playerId") == ball_handler_id:
                ball_handler_anim = anim
                break
        
        if ball_handler_anim and ball_handler_anim.get("movement"):
            movement = ball_handler_anim["movement"]
            if len(movement) >= 2:
                start_coords = movement[0].get("coords", {})
                end_coords = movement[-1].get("coords", {})
                start_x = start_coords.get("x")
                end_x = end_coords.get("x")
                # For home offense, end_x should be > start_x (moving right)
                assert end_x > start_x, \
                    f"Ball handler should move right: end_x={end_x} > start_x={start_x}"
    
    def test_home_offense_shot_attempt_coordinates(self):
        """
        Test home team on offense, shot attempt:
        - Validate offense team IDs
        - Validate get-back coordinates are used as starting positions
        - Validate shooter near home rim (x=90)
        - Validate defender 1-6 less than shooter's x
        """
        game = build_mock_game()
        
        # Simulate away team shooting (home team will be offense on fast break)
        hco_result = simulate_hco_shot_miss_dreb_fastbreak(
            game, shooting_team_is_home=False
        )
        
        # Validate get-back coordinates
        getback_coords = hco_result.get("offense_getback_coords", {})
        for player_id, coords in getback_coords.items():
            x = coords.get("x")
            y = coords.get("y")
            assert 40 <= x <= 55, f"Get-back X should be 40-55, got {x}"
            assert 14 <= y <= 36, f"Get-back Y should be 14-36, got {y}"
        
        # Simulate Fast Break turn with shot attempt
        fb_result = simulate_fast_break_turn(
            game, force_defensive_stop=False, is_home_offense=True
        )
        
        # Validate Fast Break turn
        assert fb_result.get("offense_team_id") == game.home_team.team_id
        assert fb_result.get("result_type") in ["MAKE", "MISS"], \
            "Should be shot attempt"
        
        # Validate shooter and defender positions in animation data
        animations = fb_result.get("animations", [])
        shooter_id = fb_result.get("shooter_id")
        shooter_anim = None
        defender_anim = None
        
        for anim in animations:
            if anim.get("playerId") == shooter_id:
                shooter_anim = anim
            elif anim.get("playerId") != shooter_id and anim.get("playerId") in [d.player_id for d in game.defense_team.lineup.values()]:
                defender_anim = anim
        
        if shooter_anim and shooter_anim.get("movement"):
            movement = shooter_anim["movement"]
            if len(movement) >= 2:
                shooter_end = movement[-1].get("coords", {})
                shooter_x = shooter_end.get("x")
                # Shooter should be near home rim (x=90)
                assert 80 <= shooter_x <= 95, \
                    f"Shooter should be near home rim (x=90), got {shooter_x}"
                
                # Defender should be 1-6 less than shooter's x
                if defender_anim and defender_anim.get("movement"):
                    def_movement = defender_anim["movement"]
                    if len(def_movement) >= 2:
                        defender_end = def_movement[-1].get("coords", {})
                        defender_x = defender_end.get("x")
                        x_diff = shooter_x - defender_x
                        assert 1 <= x_diff <= 6, \
                            f"Defender should be 1-6 less than shooter: diff={x_diff}, shooter_x={shooter_x}, defender_x={defender_x}"
    
    def test_away_offense_defensive_stop_coordinates(self):
        """
        Test away team on offense, defensive stop:
        - Validate offense team IDs
        - Validate get-back coordinates are used as starting positions
        - Validate ball handler movement direction (x decreases toward x=10 in HOME orientation)
        """
        game = build_mock_game()
        
        # Simulate home team shooting (away team will be offense on fast break)
        hco_result = simulate_hco_shot_miss_dreb_fastbreak(
            game, shooting_team_is_home=True
        )
        
        # Validate offense team IDs
        assert hco_result.get("offense_team_id") == game.home_team.team_id, \
            "HCO turn should have home team on offense"
        
        # Validate get-back coordinates
        getback_coords = hco_result.get("offense_getback_coords", {})
        assert len(getback_coords) > 0, "Should have get-back coordinates"
        
        for player_id, coords in getback_coords.items():
            x = coords.get("x")
            y = coords.get("y")
            # Away team will be offense on fast break (home team is shooting)
            # Get-back: X 45-60 (or 45-55 if IQ > 50), Y 14-36
            assert 45 <= x <= 60, f"Get-back X should be 45-60, got {x}"
            assert 14 <= y <= 36, f"Get-back Y should be 14-36, got {y}"
        
        # Simulate Fast Break turn with defensive stop
        fb_result = simulate_fast_break_turn(
            game, force_defensive_stop=True, is_home_offense=False
        )
        
        # Validate Fast Break turn
        assert fb_result.get("offense_team_id") == game.away_team.team_id, \
            "Fast Break turn should have away team on offense"
        assert fb_result.get("result_type") == "DEFENSIVE_STOP", \
            "Should be defensive stop"
        
        # Validate ball handler used get-back coordinates
        fb_roles = fb_result.get("roles", {})
        ball_handler_id = fb_roles.get("outlet_receiver")
        
        # Check if outlet receiver is a get-back player
        if ball_handler_id and ball_handler_id in getback_coords:
            getback_start_x = getback_coords[ball_handler_id]["x"]
            ball_handler_outlet_x = fb_roles.get("ball_handler_outlet_x")
            # Outlet x should be < get-back start x in HOME orientation (moved left toward basket)
            # Note: After coordinate flip, this becomes moving right in away orientation
            assert ball_handler_outlet_x < getback_start_x, \
                f"Ball handler should move left (HOME): outlet_x={ball_handler_outlet_x} < start_x={getback_start_x}"
        
        # Validate animation data: ball handler stop point < starting spot (in HOME orientation)
        animations = fb_result.get("animations", [])
        ball_handler_anim = None
        for anim in animations:
            if anim.get("playerId") == ball_handler_id:
                ball_handler_anim = anim
                break
        
        if ball_handler_anim and ball_handler_anim.get("movement"):
            movement = ball_handler_anim["movement"]
            if len(movement) >= 2:
                start_coords = movement[0].get("coords", {})
                end_coords = movement[-1].get("coords", {})
                # Animation coordinates are already in HOME orientation (flipped by build_movement)
                start_x = start_coords.get("x")
                end_x = end_coords.get("x")
                # For away offense, end_x should be < start_x in HOME orientation (moving left toward x=10)
                assert end_x < start_x, \
                    f"Ball handler should move left (HOME): end_x={end_x} < start_x={start_x}"
    
    def test_away_offense_shot_attempt_coordinates(self):
        """
        Test away team on offense, shot attempt:
        - Validate offense team IDs
        - Validate get-back coordinates are used as starting positions
        - Validate shooter near away rim (x=10 in HOME orientation)
        - Validate defender 1-6 greater than shooter's x (in HOME orientation)
        """
        game = build_mock_game()
        
        # Simulate home team shooting (away team will be offense on fast break)
        hco_result = simulate_hco_shot_miss_dreb_fastbreak(
            game, shooting_team_is_home=True
        )
        
        # Validate get-back coordinates
        getback_coords = hco_result.get("offense_getback_coords", {})
        for player_id, coords in getback_coords.items():
            x = coords.get("x")
            y = coords.get("y")
            assert 45 <= x <= 60, f"Get-back X should be 45-60, got {x}"
            assert 14 <= y <= 36, f"Get-back Y should be 14-36, got {y}"
        
        # Simulate Fast Break turn with shot attempt
        fb_result = simulate_fast_break_turn(
            game, force_defensive_stop=False, is_home_offense=False
        )
        
        # Validate Fast Break turn
        assert fb_result.get("offense_team_id") == game.away_team.team_id
        assert fb_result.get("result_type") in ["MAKE", "MISS"], \
            "Should be shot attempt"
        
        # Validate shooter and defender positions in animation data
        animations = fb_result.get("animations", [])
        shooter_id = fb_result.get("shooter_id")
        shooter_anim = None
        defender_anim = None
        
        for anim in animations:
            if anim.get("playerId") == shooter_id:
                shooter_anim = anim
            elif anim.get("playerId") != shooter_id and anim.get("playerId") in [d.player_id for d in game.defense_team.lineup.values()]:
                defender_anim = anim
        
        if shooter_anim and shooter_anim.get("movement"):
            movement = shooter_anim["movement"]
            if len(movement) >= 2:
                shooter_end = movement[-1].get("coords", {})
                # Animation coordinates are already in HOME orientation (flipped by build_movement)
                shooter_x = shooter_end.get("x")
                # Shooter should be near away rim (x=10 in HOME orientation)
                assert 5 <= shooter_x <= 15, \
                    f"Shooter should be near away rim (x=10 HOME), got {shooter_x}"
                
                # Defender should be 1-6 greater than shooter's x (in HOME orientation)
                if defender_anim and defender_anim.get("movement"):
                    def_movement = defender_anim["movement"]
                    if len(def_movement) >= 2:
                        defender_end = def_movement[-1].get("coords", {})
                        defender_x = defender_end.get("x")
                        x_diff = defender_x - shooter_x
                        assert 1 <= x_diff <= 6, \
                            f"Defender should be 1-6 greater than shooter (HOME): diff={x_diff}, shooter_x={shooter_x}, defender_x={defender_x}"

