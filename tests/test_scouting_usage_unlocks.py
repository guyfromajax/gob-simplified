from BackEnd.api.franchise_routes import _scouting_usage_unlocks_for_week


def test_regular_season_scouting_usage_requires_film_study():
    assert _scouting_usage_unlocks_for_week(12, 0) == (False, False)
    assert _scouting_usage_unlocks_for_week(12, 1) == (True, False)
    assert _scouting_usage_unlocks_for_week(12, 2) == (True, True)


def test_tournament_scouting_usage_is_fully_unlocked_without_training():
    for week in range(27, 35):
        assert _scouting_usage_unlocks_for_week(week, 0) == (True, True)

