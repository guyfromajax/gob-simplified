import random
from BackEnd.utils.shared_defense import (
    assign_non_bh_defender_coords,
    assign_bh_defender_coords,
)
from BackEnd.utils.shared import get_away_player_coords


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
