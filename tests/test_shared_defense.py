import random
from BackEnd.utils.shared_defense import (
    assign_non_bh_defender_coords,
    assign_bh_defender_coords,
    get_spacing,
    verify_defender_closer_to_basket,
    calculate_defender_coords,
)
from BackEnd.utils.shared import get_away_player_coords
from BackEnd.constants import HOME_RIM_COORDS, AWAY_RIM_COORDS


def test_assign_non_bh_defender_coords_away_mirrors_home_spacing():
    random.seed(0)
    o_coords = {"x": 60, "y": 30}
    ball_home = {"x": 70, "y": 25}
    ball_away = get_away_player_coords(ball_home)

    home_def = assign_non_bh_defender_coords(o_coords, ball_home, "normal", False)
    away_def = assign_non_bh_defender_coords(o_coords, ball_away, "normal", True)

    home_diff = home_def["x"] - o_coords["x"]
    away_def_flipped = get_away_player_coords(away_def)
    away_o_flipped = get_away_player_coords(o_coords)
    away_diff = away_def_flipped["x"] - away_o_flipped["x"]

    assert abs(abs(home_diff) - abs(away_diff)) <= 1
    assert home_diff == -away_diff


def test_assign_bh_defender_coords_away_mirrors_home_spacing():
    random.seed(0)
    ball_home = {"x": 70, "y": 25}
    ball_away = get_away_player_coords(ball_home)

    home_def = assign_bh_defender_coords(ball_home, "normal", False)
    away_def = assign_bh_defender_coords(ball_away, "normal", True)

    home_diff_x = home_def["x"] - ball_home["x"]
    away_ball_flipped = get_away_player_coords(ball_away)
    away_diff_x = away_def["x"] - away_ball_flipped["x"]

    assert home_diff_x == away_diff_x


def test_baseline_defense_vertical_not_flipped():
    random.seed(0)
    o_coords = {"x": 88, "y": 6}
    ball_home = {"x": 70, "y": 25}
    ball_away = get_away_player_coords(ball_home)

    home_def = assign_non_bh_defender_coords(o_coords, ball_home, "normal", False)
    away_def = assign_non_bh_defender_coords(o_coords, ball_away, "normal", True)

    away_def_flipped = get_away_player_coords(away_def)
    away_o_flipped = get_away_player_coords(o_coords)

    home_delta_y = home_def["y"] - o_coords["y"]
    away_delta_y = away_def_flipped["y"] - away_o_flipped["y"]

    assert home_delta_y == away_delta_y


# ============================================================================
# PHASE 1: UNIFIED DEFENDER COORDINATE SYSTEM TESTS
# ============================================================================

def test_get_spacing_bh_defenders():
    """Test spacing for ball handler defenders"""
    assert get_spacing("aggressive", is_ball_handler=True) == 2
    assert get_spacing("normal", is_ball_handler=True) == 3
    assert get_spacing("passive", is_ball_handler=True) == 4
    assert get_spacing("invalid", is_ball_handler=True) == 3  # default


def test_get_spacing_non_bh_defenders():
    """Test spacing for non-ball handler defenders"""
    assert get_spacing("aggressive", is_ball_handler=False) == 1
    assert get_spacing("normal", is_ball_handler=False) == 2
    assert get_spacing("passive", is_ball_handler=False) == 3
    assert get_spacing("invalid", is_ball_handler=False) == 2  # default


def test_verify_defender_closer_to_basket():
    """Test verification that defender is closer to basket"""
    basket = {"x": 90, "y": 25}
    
    # Defender closer to basket (should pass)
    assert verify_defender_closer_to_basket(85, 25, 70, 25, basket["x"], basket["y"]) == True
    
    # Defender same distance (should fail - must be closer)
    assert verify_defender_closer_to_basket(70, 25, 70, 25, basket["x"], basket["y"]) == False
    
    # Defender further from basket (should fail)
    assert verify_defender_closer_to_basket(60, 25, 70, 25, basket["x"], basket["y"]) == False


def test_calculate_defender_coords_bh_key():
    """Test BH defender calculation at key spot"""
    random.seed(42)
    bh_coords = {"x": 64, "y": 25}  # Key position
    target_basket = AWAY_RIM_COORDS  # Home team attacking away basket
    
    result = calculate_defender_coords(
        bh_coords, target_basket, "normal", "key", None, is_ball_handler=True
    )
    
    # Defender should be closer to basket than ball handler
    assert verify_defender_closer_to_basket(
        result["x"], result["y"],
        bh_coords["x"], bh_coords["y"],
        target_basket["x"], target_basket["y"]
    )
    assert "x" in result
    assert "y" in result


def test_calculate_defender_coords_bh_corner():
    """Test BH defender in corner - x should equal ball handler x, y follows rules"""
    random.seed(42)
    bh_coords = {"x": 88, "y": 44}  # Upper corner
    target_basket = AWAY_RIM_COORDS
    
    result = calculate_defender_coords(
        bh_coords, target_basket, "normal", "upper corner", None, is_ball_handler=True
    )
    
    # X should equal ball handler x
    assert result["x"] == bh_coords["x"]
    # Y should be lower (defender below ball handler)
    assert result["y"] < bh_coords["y"]


def test_calculate_defender_coords_bh_lower_corner():
    """Test BH defender in lower corner"""
    random.seed(42)
    bh_coords = {"x": 88, "y": 6}  # Lower corner
    target_basket = AWAY_RIM_COORDS
    
    result = calculate_defender_coords(
        bh_coords, target_basket, "normal", "lower corner", None, is_ball_handler=True
    )
    
    # X should equal ball handler x
    assert result["x"] == bh_coords["x"]
    # Y should be higher (defender above ball handler)
    assert result["y"] > bh_coords["y"]


def test_calculate_defender_coords_non_bh_post():
    """Test non-BH defender guarding post player - should stay tight"""
    random.seed(42)
    post_coords = {"x": 86, "y": 19}  # Lower low post
    target_basket = AWAY_RIM_COORDS
    ball_handler_coords = {"x": 64, "y": 25}
    
    result = calculate_defender_coords(
        post_coords, target_basket, "normal", "lower lowPost",
        ball_handler_coords, is_ball_handler=False
    )
    
    # Defender should be on basket side (x should be adjusted)
    # Basket is at x=10, so defender should be at ox - 2 (closer to basket)
    assert result["x"] == post_coords["x"] - 2 or result["x"] == post_coords["x"] + 2


def test_calculate_defender_coords_non_bh_corner():
    """Test non-BH defender in corner - y position rules"""
    random.seed(42)
    corner_coords = {"x": 88, "y": 44}  # Upper corner
    target_basket = AWAY_RIM_COORDS
    ball_handler_coords = {"x": 64, "y": 25}
    
    result = calculate_defender_coords(
        corner_coords, target_basket, "normal", "upper corner",
        ball_handler_coords, is_ball_handler=False
    )
    
    # Upper corner: defender's y should be lower (defender below offensive player)
    assert result["y"] < corner_coords["y"]


def test_calculate_defender_coords_non_bh_lower_corner():
    """Test non-BH defender in lower corner"""
    random.seed(42)
    corner_coords = {"x": 88, "y": 6}  # Lower corner
    target_basket = AWAY_RIM_COORDS
    ball_handler_coords = {"x": 64, "y": 25}
    
    result = calculate_defender_coords(
        corner_coords, target_basket, "normal", "lower corner",
        ball_handler_coords, is_ball_handler=False
    )
    
    # Lower corner: defender's y should be higher (defender above offensive player)
    assert result["y"] > corner_coords["y"]


def test_calculate_defender_coords_home_away_consistency():
    """Test that calculation works for both home and away offense (in HOME orientation)"""
    random.seed(42)
    bh_coords = {"x": 64, "y": 25}
    
    # Home offense: attacking away basket (x=10)
    home_basket = AWAY_RIM_COORDS
    home_result = calculate_defender_coords(
        bh_coords, home_basket, "normal", "key", None, is_ball_handler=True
    )
    
    # Away offense: attacking home basket (x=90) - but coords are in HOME orientation
    # So we'd flip the coords before calling, but the function still works in HOME orientation
    away_basket = HOME_RIM_COORDS
    away_result = calculate_defender_coords(
        bh_coords, away_basket, "normal", "key", None, is_ball_handler=True
    )
    
    # Both should produce valid results
    assert "x" in home_result
    assert "y" in home_result
    assert "x" in away_result
    assert "y" in away_result
    
    # Both should be closer to their respective baskets
    assert verify_defender_closer_to_basket(
        home_result["x"], home_result["y"],
        bh_coords["x"], bh_coords["y"],
        home_basket["x"], home_basket["y"]
    )
    assert verify_defender_closer_to_basket(
        away_result["x"], away_result["y"],
        bh_coords["x"], bh_coords["y"],
        away_basket["x"], away_basket["y"]
    )
