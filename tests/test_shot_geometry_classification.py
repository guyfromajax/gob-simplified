from BackEnd.utils.shot_geometry import classify_shot_value


def test_classify_home_coord_beyond_arc_as_three():
    result = classify_shot_value(
        {"x": 50, "y": 25},
        is_away_offense=False,
    )

    assert result["points"] == 3
    assert result["shot_value"] == 3
    assert result["is_three_point_shot"] is True
    assert result["classification_coord"] == {"x": 50.0, "y": 25.0}
    assert result["normalized_coord"] == {"x": 50.0, "y": 25.0}
    assert result["classification_source"] == "coords"


def test_classify_home_coord_inside_arc_as_two():
    result = classify_shot_value(
        {"x": 85, "y": 25},
        is_away_offense=False,
    )

    assert result["points"] == 2
    assert result["shot_value"] == 2
    assert result["is_three_point_shot"] is False


def test_classify_away_coord_mirrors_for_geometry():
    result = classify_shot_value(
        {"x": 36, "y": 25},
        is_away_offense=True,
    )

    assert result["points"] == 3
    assert result["is_three_point_shot"] is True
    assert result["classification_coord"] == {"x": 36.0, "y": 25.0}
    assert result["normalized_coord"] == {"x": 64.0, "y": 25.0}


def test_classify_forced_two_bypasses_geometry():
    result = classify_shot_value(
        {"x": 50, "y": 25},
        is_away_offense=False,
        allow_three=False,
    )

    assert result["points"] == 2
    assert result["is_three_point_shot"] is False
    assert result["classification_source"] == "forced_two"


def test_classify_forced_one_for_free_throw_contract():
    result = classify_shot_value(
        None,
        is_away_offense=False,
        forced_points=1,
    )

    assert result["points"] == 1
    assert result["shot_value"] == 1
    assert result["is_three_point_shot"] is False
    assert result["classification_source"] == "forced_one"
