"""Half-court clock violations and over-and-back in the dynamic HCT/FCP loop."""

from BackEnd.engine.dynamic_hct import (
    _crossed_half_court,
    _in_backcourt,
    _select_pass_receiver,
)


def test_crossed_half_court_home_offense():
    assert not _crossed_half_court(49, is_away_offense=False)
    assert _crossed_half_court(50, is_away_offense=False)
    assert _crossed_half_court(64, is_away_offense=False)


def test_crossed_half_court_away_offense():
    assert not _crossed_half_court(51, is_away_offense=True)
    assert _crossed_half_court(50, is_away_offense=True)
    assert _crossed_half_court(36, is_away_offense=True)


def test_in_backcourt_is_complement_of_crossed_half_court():
    for x in (10, 49, 50, 51, 90):
        for away in (False, True):
            assert _in_backcourt(x, away) != _crossed_half_court(x, away)


def test_select_pass_receiver_allows_backcourt_outlet_after_half_court():
    """Illegal over-and-back passes are no longer filtered at selection time."""
    off_coords = {
        "PG": {"x": 55, "y": 25},
        "SG": {"x": 45, "y": 25},
        "SF": {"x": 60, "y": 20},
        "PF": {"x": 58, "y": 30},
        "C": {"x": 62, "y": 25},
    }
    picks = {
        _select_pass_receiver("PG", off_coords, is_away_offense=False)
        for _ in range(30)
    }
    assert "SG" in picks
