"""Current streak is derived from results and does not change standings order."""

from BackEnd.utils.franchise_standings import current_streaks, standings_display_sort_key


def _game(away, home, away_score, home_score):
    return {
        "away_id": away,
        "home_id": home,
        "away_score": away_score,
        "home_score": home_score,
    }


def test_streak_walks_weeks_in_order():
    results = {
        "2": [_game("a", "b", 80, 70)],
        "1": [_game("a", "b", 60, 70)],
    }
    streaks = current_streaks(results)
    assert streaks["a"] == "W1"
    assert streaks["b"] == "L1"


def test_streak_counts_consecutive_results_and_a_tie_clears_it():
    built = current_streaks({
        "1": [_game("a", "b", 80, 60)],
        "2": [_game("b", "a", 50, 70)],
    })
    assert built["a"] == "W2"
    assert built["b"] == "L2"

    cleared = current_streaks({
        "1": [_game("a", "b", 80, 60)],
        "2": [_game("a", "b", 40, 40)],
    })
    assert cleared == {}


def test_sort_key_ignores_streak():
    row = {"W": 3, "differential": 4, "streak": "L9"}
    assert standings_display_sort_key(row) == (-3, -4)
