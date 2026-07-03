import math

import pytest

from BackEnd.constants import HCO_STRING_SPOTS
from BackEnd.constants.fast_break_constants import FB_SHOOT_GEO_RADIUS
from BackEnd.utils.fb_geo_helpers import (
    attacking_basket_coord,
    compute_perpendicular_shimmy_point,
    compute_pos_o_shimmy_from_segment,
    compute_pos_o_shimmy_point,
    defender_x_trail_spots,
    euclidean_to_basket,
    fb_defender_contests_shot,
    fb_pass_receiver_geo_eligible,
    fb_shoot_geo_eligible,
    nearest_spot_label,
    pick_nearest_contesting_defender,
    steal_meet_x_ahead_valid,
)


def test_attacking_basket_home_and_away():
    assert attacking_basket_coord(is_away_offense=False) == {"x": 91.0, "y": 25.0}
    assert attacking_basket_coord(is_away_offense=True) == {"x": 9.0, "y": 25.0}


def test_euclidean_to_basket_key_is_27_home():
    key = HCO_STRING_SPOTS["key"]
    dist = euclidean_to_basket(key, is_away_offense=False)
    assert dist == pytest.approx(27.0)


def test_nearest_spot_label_at_key():
    assert nearest_spot_label(HCO_STRING_SPOTS["key"]) == "key"


def test_fb_shoot_geo_eligible_by_distance():
    # topLane is 17 from home basket — inside 24 radius
    coord = HCO_STRING_SPOTS["topLane"]
    assert euclidean_to_basket(coord, is_away_offense=False) < FB_SHOOT_GEO_RADIUS
    assert fb_shoot_geo_eligible(coord, is_away_offense=False)


def test_fb_shoot_geo_eligible_by_key_label_despite_distance():
    key = HCO_STRING_SPOTS["key"]
    assert euclidean_to_basket(key, is_away_offense=False) > FB_SHOOT_GEO_RADIUS
    assert fb_shoot_geo_eligible(key, is_away_offense=False)


def test_fb_shoot_geo_eligible_midwing_label():
    wing = HCO_STRING_SPOTS["upper midWing"]
    assert fb_shoot_geo_eligible(wing, is_away_offense=False)


def test_fb_shoot_geo_ineligible_deep_backcourt():
    deep = {"x": 40.0, "y": 25.0}
    assert not fb_shoot_geo_eligible(deep, is_away_offense=False)


def test_fb_pass_geo_by_wing_label_without_shoot_eligibility():
    # Far enough from rim for distance gate (>24), nearest label is pass-only (not shoot labels).
    coord = {"x": 71.0, "y": 40.0}
    assert nearest_spot_label(coord) == "upper wing"
    assert euclidean_to_basket(coord, is_away_offense=False) > FB_SHOOT_GEO_RADIUS
    assert fb_pass_receiver_geo_eligible(coord, is_away_offense=False)
    assert not fb_shoot_geo_eligible(coord, is_away_offense=False)


def test_fb_shoot_geo_away_backcourt_near_home_spot_is_ineligible():
    # Regression: an AWAY-offense meet at (70, 16) sits right on the HOME-side
    # "lower midWing" spot, but it is ~62 units from the AWAY basket (x=9) — the
    # backcourt. The spot-label branch must be measured in the attacking-basket
    # frame, so this is NOT shoot-eligible for away offense (was the "shot from
    # the complete other side of the court" bug).
    coord = {"x": 70.0, "y": 16.0}
    assert nearest_spot_label(coord) == "lower midWing"  # home-frame label
    assert euclidean_to_basket(coord, is_away_offense=True) > FB_SHOOT_GEO_RADIUS
    assert not fb_shoot_geo_eligible(coord, is_away_offense=True)
    assert not fb_pass_receiver_geo_eligible(coord, is_away_offense=True)
    # Same raw coord IS a legit perimeter shot for HOME offense (attacking x=91).
    assert fb_shoot_geo_eligible(coord, is_away_offense=False)


def test_fb_shoot_geo_away_at_mirrored_key_is_eligible():
    # The AWAY equivalent of the home "key" (x=64) is its mirror about mid-court
    # (x=36). From there an away BH attacks x=9 and should be shoot-eligible via
    # the (mirrored) key label despite being >24 from the basket.
    coord = {"x": 36.0, "y": 25.0}
    assert euclidean_to_basket(coord, is_away_offense=True) > FB_SHOOT_GEO_RADIUS
    assert fb_shoot_geo_eligible(coord, is_away_offense=True)


def test_home_defender_contests_within_radius_and_x_trail():
    shooter = {"x": 88.0, "y": 25.0}
    assert fb_defender_contests_shot({"x": 87.0, "y": 25.0}, shooter, is_away_offense=False)
    assert fb_defender_contests_shot({"x": 85.0, "y": 25.0}, shooter, is_away_offense=False)
    assert not fb_defender_contests_shot({"x": 84.0, "y": 25.0}, shooter, is_away_offense=False)
    assert fb_defender_contests_shot({"x": 90.0, "y": 25.0}, shooter, is_away_offense=False)


def test_away_defender_contests_within_radius_and_x_trail():
    shooter = {"x": 12.0, "y": 25.0}
    assert fb_defender_contests_shot({"x": 13.0, "y": 25.0}, shooter, is_away_offense=True)
    assert not fb_defender_contests_shot({"x": 16.0, "y": 25.0}, shooter, is_away_offense=True)


def test_euclidean_gate_blocks_contest_despite_x_trail():
    shooter = {"x": 88.0, "y": 25.0}
    assert not fb_defender_contests_shot({"x": 85.0, "y": 36.0}, shooter, is_away_offense=False)


def test_defender_x_trail_spots_home():
    assert defender_x_trail_spots(85.0, 88.0, is_away_offense=False) == 3.0
    assert defender_x_trail_spots(90.0, 88.0, is_away_offense=False) == 0.0


def test_steal_meet_x_ahead_valid_home():
    bh_start = {"x": 70.0, "y": 25.0}
    assert steal_meet_x_ahead_valid({"x": 71.0, "y": 25.0}, bh_start, is_away_offense=False)
    assert not steal_meet_x_ahead_valid({"x": 70.0, "y": 25.0}, bh_start, is_away_offense=False)
    assert not steal_meet_x_ahead_valid({"x": 69.0, "y": 25.0}, bh_start, is_away_offense=False)


def test_steal_meet_x_ahead_valid_away():
    bh_start = {"x": 30.0, "y": 25.0}
    assert steal_meet_x_ahead_valid({"x": 29.0, "y": 25.0}, bh_start, is_away_offense=True)
    assert not steal_meet_x_ahead_valid({"x": 30.0, "y": 25.0}, bh_start, is_away_offense=True)
    assert not steal_meet_x_ahead_valid({"x": 31.0, "y": 25.0}, bh_start, is_away_offense=True)


def test_horizontal_drive_shimmy_offsets_y():
    meet = {"x": 75.0, "y": 25.0}
    stopper = {"x": 76.0, "y": 25.0}
    shimmy = compute_pos_o_shimmy_point(meet, stopper, drive_dx=10.0, drive_dy=0.0)
    assert shimmy["x"] == meet["x"]
    assert abs(shimmy["y"] - meet["y"]) == pytest.approx(2.0)
    assert math.hypot(shimmy["x"] - stopper["x"], shimmy["y"] - stopper["y"]) > math.hypot(
        meet["x"] - stopper["x"], meet["y"] - stopper["y"]
    )


def test_vertical_drive_shimmy_offsets_x():
    meet = {"x": 88.0, "y": 20.0}
    stopper = {"x": 88.0, "y": 22.0}
    shimmy = compute_pos_o_shimmy_point(meet, stopper, drive_dx=0.0, drive_dy=8.0)
    assert shimmy["y"] == meet["y"]
    assert abs(shimmy["x"] - meet["x"]) == pytest.approx(2.0)


def test_diagonal_drive_shimmy_moves_both_axes():
    meet = {"x": 70.0, "y": 25.0}
    stopper = {"x": 71.0, "y": 26.0}
    shimmy = compute_pos_o_shimmy_point(meet, stopper, drive_dx=5.0, drive_dy=5.0)
    assert shimmy["x"] != meet["x"]
    assert shimmy["y"] != meet["y"]
    dist = math.hypot(shimmy["x"] - meet["x"], shimmy["y"] - meet["y"])
    assert dist == pytest.approx(2.0, abs=0.01)


def test_shimmy_from_segment_matches_explicit_drive():
    meet = {"x": 75.0, "y": 25.0}
    stopper = {"x": 76.0, "y": 25.0}
    start = {"x": 65.0, "y": 25.0}
    a = compute_pos_o_shimmy_from_segment(meet, stopper, start)
    b = compute_pos_o_shimmy_point(meet, stopper, 10.0, 0.0)
    assert a == b


def test_perpendicular_shimmy_magnitude():
    meet = {"x": 50.0, "y": 25.0}
    stopper = {"x": 51.0, "y": 26.0}
    shimmy = compute_perpendicular_shimmy_point(meet, stopper, 3.0, 4.0, magnitude=2.0)
    assert math.hypot(shimmy["x"] - meet["x"], shimmy["y"] - meet["y"]) == pytest.approx(
        2.0, abs=0.01
    )


def test_pick_nearest_contesting_defender():
    shooter = {"x": 88.0, "y": 25.0}
    positions = {
        "d1": {"x": 87.0, "y": 25.0},
        "d2": {"x": 86.0, "y": 25.0},
        "d3": {"x": 50.0, "y": 25.0},
    }
    contested, best = pick_nearest_contesting_defender(
        positions, shooter, is_away_offense=False
    )
    assert contested is True
    assert best == "d1"
