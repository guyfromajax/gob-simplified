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

    # Base 0-point range (-2,-1) with senior max adjustment +1 -> (-2,0)
    assert calls == [(-2, 0)]


def test_player_attr_range_point_5_sophomore(monkeypatch):
    calls = []

    def fake_randint(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(training.random, "randint", fake_randint)
    player = _make_player(year="sophomore")
    training._apply_player_training_points(player, "SC", 5)

    # Base 5-point range (3,6) with sophomore max adjustment +3 -> (3,9)
    assert calls == [(3, 9)]


def test_pre_training_decay_ranges_by_year():
    assert training._pre_training_decay_range_for_year("freshman") == (-5, -2)
    assert training._pre_training_decay_range_for_year("sophomore") == (-4, -1)
    assert training._pre_training_decay_range_for_year("junior") == (-3, -1)
    assert training._pre_training_decay_range_for_year("senior") == (-2, 0)


def test_pre_training_conditions_use_freshman_decay_range(monkeypatch):
    def fake_randint(a, b):
        assert (a, b) == (-5, -2)
        return -5

    monkeypatch.setattr(training.random, "randint", fake_randint)
    monkeypatch.setattr(training, "TRAINABLE_PLAYER_ATTRS", ["SC"])

    player = _make_player(year="freshman", anchor_val=50)
    players, _team = training.apply_pre_training_conditions([player], {})
    updated = players[0]["attributes"]["anchor_SC"]

    assert updated == 45


def test_rebound_modifier_uses_half_point_accrual_from_rebounding_and_scrimmages(monkeypatch):
    players = [
        {
            "_id": "p1",
            "attributes": {"anchor_SC": 50, "SC": 50, "NG": 1.0},
        }
    ]
    team = {
        "shot_threshold": 100,
        "discipline": 0,
        "fight": 0,
        "rebound_modifier": 0.2,
        "momentum_score": 0,
        "offensive_efficiency": 0,
        "team_chemistry": 10,
        "defensive_efficiency": 0,
        "fb_efficiency": 0,
        "pt_efficiency": 0,
        "fb_opp_modifier": 0,
        "pt_opp_modifier": 0,
    }
    allocations = {
        "player_drills": {
            "technical": {"rebounding": 2},  # 2 * 0.5 => 1 effective point
        },
        "team_drills": {
            "scrimmages": 3,  # 3 * 0.5 => 2 effective points
        },
    }

    rebound_calls = []
    shot_threshold_calls = []

    monkeypatch.setattr(training, "_apply_player_training_points", lambda *args, **kwargs: None)
    monkeypatch.setattr(training, "_apply_team_training_points", lambda *args, **kwargs: None)
    monkeypatch.setattr(training, "_apply_breaks_effect", lambda *args, **kwargs: None)
    monkeypatch.setattr(training, "_apply_ng_reduction_from_scrimmages", lambda *args, **kwargs: [])
    monkeypatch.setattr(training, "_apply_ng_reduction_from_conditioning", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        training,
        "_apply_rebound_modifier_training",
        lambda _team, points, *_args, source="technical_drills", **_kwargs: rebound_calls.append((source, points)),
    )
    monkeypatch.setattr(
        training,
        "_apply_shot_threshold_training",
        lambda _team, points, *_args, **_kwargs: shot_threshold_calls.append(points),
    )

    training.apply_training_points(players, team, allocations)

    assert ("technical_drills", 1) in rebound_calls
    assert ("scrimmages", 2) in rebound_calls
    assert shot_threshold_calls == [3]


def test_fight_and_discipline_share_training_bucket_randint_pairs(monkeypatch):
    calls = []

    def fake_randint(a, b):
        calls.append((a, b))
        return a

    monkeypatch.setattr(training.random, "randint", fake_randint)

    expected_pairs = [(-4, -3), (-3, -1), (-1, 1), (1, 2), (2, 3), (2, 4)]

    team_d = {"discipline": 0}
    for bucket in range(6):
        training._apply_team_training_points(team_d, "discipline", bucket)

    team_f = {"fight": 0}
    for bucket in range(6):
        training._apply_team_training_points(team_f, "fight", bucket)

    assert calls == expected_pairs * 2


def test_training_gain_is_halved_when_player_starts_above_100(monkeypatch):
    monkeypatch.setattr(training.random, "randint", lambda a, b: 5)

    player = _make_player(year="junior", anchor_val=102)
    training._apply_player_training_points(player, "SC", 4, starting_baseline=102)

    assert player["attributes"]["anchor_SC"] == 105
    assert player["attributes"]["SC"] == 105


def test_training_gain_is_not_reduced_when_player_starts_at_99(monkeypatch):
    monkeypatch.setattr(training.random, "randint", lambda a, b: 6)

    player = _make_player(year="junior", anchor_val=99)
    training._apply_player_training_points(player, "SC", 4, starting_baseline=99)

    assert player["attributes"]["anchor_SC"] == 105
    assert player["attributes"]["SC"] == 105
