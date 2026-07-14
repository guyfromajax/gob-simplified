from BackEnd.utils.position_ratings import compute_position_ratings


def test_mid_range_ratings():
    player = {
        "height": 74,
        "attributes": {
            "SC": 65,
            "SH": 65,
            "ID": 65,
            "OD": 65,
            "PS": 65,
            "BH": 65,
            "RB": 65,
            "AG": 65,
            "ST": 65,
            "IQ": 65,
            "FT": 65,
        },
    }
    ratings = compute_position_ratings(player)
    for pos_rating in ratings.values():
        assert 35 <= pos_rating <= 80


def test_height_clamps():
    low = {"height": 50, "attributes": {}}
    high = {"height": 90, "attributes": {}}
    low_center = compute_position_ratings(low)["C"]
    high_center = compute_position_ratings(high)["C"]
    assert low_center == 1
    # C rating weights height at 40%; max C height rating 100 -> 40 when other attrs are 0
    assert high_center == 40


def test_power_forward_regular_uses_height():
    player = {"height": 90, "attributes": {}}
    # PF-specific height caps at 75 and regular PF weights height at 10%.
    assert compute_position_ratings(player)["PF"] == 8


def test_pf_and_c_use_position_specific_height_conversions():
    attrs = {}
    assert compute_position_ratings({"height": 71, "attributes": attrs})["PF"] == 1
    assert compute_position_ratings({"height": 72, "attributes": attrs})["PF"] == 2
    assert compute_position_ratings({"height": 75, "attributes": attrs})["PF"] == 2
    assert compute_position_ratings({"height": 76, "attributes": attrs})["PF"] == 8

    assert compute_position_ratings({"height": 75, "attributes": attrs})["C"] == 1
    assert compute_position_ratings({"height": 76, "attributes": attrs})["C"] == 10
    assert compute_position_ratings({"height": 77, "attributes": attrs})["C"] == 20
    assert compute_position_ratings({"height": 78, "attributes": attrs})["C"] == 30
    assert compute_position_ratings({"height": 79, "attributes": attrs})["C"] == 40


def test_recruit_power_forward_weights_reduce_height():
    player = {"height": 90, "attributes": {"RB": 100, "ST": 100}}
    ratings = compute_position_ratings(player, profile="recruit")
    assert ratings["PF"] == 68


def test_recruit_center_weights_scoring_and_inside_defense_more_than_height():
    player = {"height": 90, "attributes": {"SC": 100, "ID": 100}}
    ratings = compute_position_ratings(player, profile="recruit")
    assert ratings["C"] == 70


def test_short_recruit_pf_and_c_drop_height_weight_from_sum():
    """Height < 71 in.: PF/C use 0% height; tall recruit still applies 10% height to PF/C."""
    tall = {"height": 84, "attributes": {}}
    short = {"height": 70, "attributes": {}}
    assert compute_position_ratings(tall, profile="recruit")["PF"] == 8
    assert compute_position_ratings(short, profile="recruit")["PF"] == 1
    assert compute_position_ratings(tall, profile="recruit")["C"] == 10
    assert compute_position_ratings(short, profile="recruit")["C"] == 1


def test_player_short_height_does_not_use_recruit_short_pf_weights():
    """Roster players always use POSITION_WEIGHTS (no <71 recruit branch)."""
    player = {"height": 70, "attributes": {"RB": 100, "ST": 100}}
    recruit = {"height": 70, "attributes": {"RB": 100, "ST": 100}}
    assert compute_position_ratings(player)["PF"] == 55
    assert compute_position_ratings(recruit, profile="recruit")["PF"] == 70
