import random
from BackEnd.engine.phase_resolution import get_in_play_defenders
from BackEnd.models.player import Player


def make_player(x):
    data = {
        "first_name": "P",
        "last_name": str(x),
        "AG": 50,
        "BH": 50,
        "OD": 50,
    }
    p = Player(data)
    p.coords = {"x": x, "y": 0}
    return p


def test_get_in_play_defenders_home_and_away():
    bh = make_player(50)
    d_ahead = make_player(60)
    d_behind = make_player(40)
    lineup = {"PG": d_ahead, "SG": d_behind}

    home_defenders = get_in_play_defenders(bh, lineup, target_is_away=False)
    assert d_ahead in home_defenders
    assert d_behind not in home_defenders

    away_defenders = get_in_play_defenders(bh, lineup, target_is_away=True)
    assert d_behind in away_defenders
    assert d_ahead not in away_defenders
