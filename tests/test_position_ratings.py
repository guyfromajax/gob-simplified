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
        assert 40 <= pos_rating <= 80


def test_height_clamps():
    low = {"height": 50, "attributes": {}}
    high = {"height": 90, "attributes": {}}
    low_center = compute_position_ratings(low)["C"]
    high_center = compute_position_ratings(high)["C"]
    assert low_center == 1
    # C rating weights height at 40%; max height rating 100 → 40 when other attrs are 0
    assert high_center == 40
