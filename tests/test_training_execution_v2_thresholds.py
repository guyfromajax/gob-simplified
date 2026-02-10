import BackEnd.models.training_execution_v2 as training


def _make_player(year="junior", anchor_val=50):
    return {
        "_id": "p1",
        "year": year,
        "attributes": {
            "anchor_SC": anchor_val,
            "SC": anchor_val,
        },
    }


def test_player_attr_range_point_1_freshman(monkeypatch):
    calls = []

    def fake_randint(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(training.random, "randint", fake_randint)
    player = _make_player(year="freshman")
    training._apply_player_training_points(player, "SC", 1)

    # Base 1-point range (0,1) with freshman max adjustment +5 -> (0,6)
    assert calls == [(0, 6)]


def test_player_attr_range_point_0_includes_year_max_adjustment(monkeypatch):
    calls = []

    def fake_randint(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(training.random, "randint", fake_randint)
    player = _make_player(year="senior")
    training._apply_player_training_points(player, "SC", 0)

    # Base 0-point range (-2,-1) with senior max adjustment +2 -> (-2,1)
    assert calls == [(-2, 1)]


def test_player_attr_range_point_5_sophomore(monkeypatch):
    calls = []

    def fake_randint(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(training.random, "randint", fake_randint)
    player = _make_player(year="sophomore")
    training._apply_player_training_points(player, "SC", 5)

    # Base 5-point range (3,6) with sophomore max adjustment +4 -> (3,10)
    assert calls == [(3, 10)]


def test_pre_training_decay_ranges_by_year():
    assert training._pre_training_decay_range_for_year("freshman") == (-5, -1)
    assert training._pre_training_decay_range_for_year("sophomore") == (-4, -1)
    assert training._pre_training_decay_range_for_year("junior") == (-3, 0)
    assert training._pre_training_decay_range_for_year("senior") == (-2, 0)


def test_pre_training_conditions_use_freshman_decay_range(monkeypatch):
    def fake_randint(a, b):
        assert (a, b) == (-5, -1)
        return -5

    monkeypatch.setattr(training.random, "randint", fake_randint)
    monkeypatch.setattr(training, "TRAINABLE_PLAYER_ATTRS", ["SC"])

    player = _make_player(year="freshman", anchor_val=50)
    players, _team = training.apply_pre_training_conditions([player], {})
    updated = players[0]["attributes"]["anchor_SC"]

    assert updated == 45
