"""Regression coverage for deferred legacy season-momentum behavior."""

from BackEnd.utils.season_momentum import compute_season_momentum_updates


def test_win_updates_momentum_and_streak():
    winner_attrs = {
        "team_chemistry": 10,
        "momentum_score": 0,
        "distant_win_streak": 0,
    }
    loser_attrs = {
        "team_chemistry": 10,
        "momentum_score": 0,
        "distant_win_streak": 2,
    }

    winner_updates, loser_updates = compute_season_momentum_updates(
        winner_attrs, loser_attrs
    )

    assert winner_updates == {
        "momentum_score": 1.5,
        "distant_win_streak": 1,
        "distant_loss_streak": 0,
    }
    assert loser_updates == {
        "momentum_score": -0.8,
        "distant_win_streak": 0,
        "distant_loss_streak": 1,
    }


def test_loss_after_win_streak_preserves_reset_penalty():
    winner_attrs = {
        "team_chemistry": 10,
        "momentum_score": 0,
        "distant_win_streak": 0,
    }
    loser_attrs = {
        "team_chemistry": 10,
        "momentum_score": 5,
        "distant_win_streak": 4,
    }

    _, loser_updates = compute_season_momentum_updates(winner_attrs, loser_attrs)

    assert abs(float(loser_updates["momentum_score"]) - 2.2) < 0.01
