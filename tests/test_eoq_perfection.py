"""Tests for EOQ perfection helpers (run-out clock, FLSS zones, inside paint)."""

from BackEnd.constants import is_inside_paint_grid
from BackEnd.engine.eoq_perfection import (
    classify_flss_zone,
    flss_heave_sfx_eligible,
    strip_terminal_rebound_fields,
)
from BackEnd.utils import situational_logic as sl


class _Team:
    def __init__(self, name, score):
        self.name = name
        self.team_id = name
        self.lineup = {}
        self.team_attributes = {"team_chemistry": 15}
        self.is_home_team = name == "Home"


class _Game:
    def __init__(self, quarter, off_score, def_score):
        self.quarter = quarter
        self.offense_team = _Team("Home", off_score)
        self.defense_team = _Team("Away", def_score)
        self.home_team = self.offense_team
        self.away_team = self.defense_team
        self.score = {"Home": off_score, "Away": def_score}
        self.game_state = {}


def test_is_inside_paint_grid_home_basket():
    assert is_inside_paint_grid(87, 25, home_basket=True) is True
    assert is_inside_paint_grid(80, 19, home_basket=True) is True
    assert is_inside_paint_grid(70, 25, home_basket=True) is False


def test_classify_flss_zone_home():
    assert classify_flss_zone(70, is_home_offense=True) == "normal"
    assert classify_flss_zone(60, is_home_offense=True) == "penalty"
    assert classify_flss_zone(40, is_home_offense=True) == "heave"


def test_classify_flss_zone_away():
    assert classify_flss_zone(30, is_home_offense=False) == "normal"
    assert classify_flss_zone(43, is_home_offense=False) == "penalty"
    assert classify_flss_zone(55, is_home_offense=False) == "heave"


def test_flss_heave_sfx_eligible():
    assert flss_heave_sfx_eligible(45, is_home_offense=True) is True
    assert flss_heave_sfx_eligible(55, is_home_offense=False) is True
    assert flss_heave_sfx_eligible(55, is_home_offense=True) is False


def test_should_run_out_clock_q4():
    g = _Game(4, 80, 70)
    assert sl.should_run_out_clock(g, 25) is True
    g2 = _Game(4, 50, 80)
    assert sl.should_run_out_clock(g2, 25) is True
    g3 = _Game(4, 70, 68)
    assert sl.should_run_out_clock(g3, 25) is False
    g4 = _Game(2, 80, 70)
    assert sl.should_run_out_clock(g4, 25) is False


def test_strip_terminal_rebound_fields():
    payload = {
        "rebounderId": "p1",
        "rebound_type": "DREB",
        "ball_bounce_x": 85,
        "result_type": "MISS",
    }
    strip_terminal_rebound_fields(payload)
    assert "rebounderId" not in payload
    assert "rebound_type" not in payload
    assert payload["ball_bounce_x"] == 85
