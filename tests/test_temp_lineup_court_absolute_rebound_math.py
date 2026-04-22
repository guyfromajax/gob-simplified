"""Regression: away-offense runtime coords vs court-absolute bounce for rebound selection."""

from BackEnd.utils.shared import temp_lineup_court_absolute_for_away_rebound_math


class _Pl:
    def __init__(self, pid, x):
        self.player_id = pid
        self.coords = {"x": x, "y": 25}


class _Tm:
    def __init__(self, pid, x):
        self.lineup = {"PG": _Pl(pid, x)}


class _Game:
    def __init__(self):
        self.home_team = _Tm("h1", 73)
        self.away_team = _Tm("a1", 11)


def test_temp_lineup_court_absolute_flips_and_restores_for_away():
    g = _Game()
    hp = g.home_team.lineup["PG"]
    ap = g.away_team.lineup["PG"]
    with temp_lineup_court_absolute_for_away_rebound_math(g, True):
        assert hp.coords["x"] == 27
        assert ap.coords["x"] == 89
    assert hp.coords["x"] == 73
    assert ap.coords["x"] == 11


def test_temp_lineup_court_absolute_noop_when_home_offense():
    g = _Game()
    hp = g.home_team.lineup["PG"]
    with temp_lineup_court_absolute_for_away_rebound_math(g, False):
        assert hp.coords["x"] == 73


def test_temp_lineup_court_absolute_noop_when_game_none():
    with temp_lineup_court_absolute_for_away_rebound_math(None, True):
        pass
