"""Edges for season leader qualification."""

import pytest

from BackEnd.constants.leader_qualification import LEADER_QUALIFICATION_FLOORS, qualifies


@pytest.mark.parametrize("stat,floor", list(LEADER_QUALIFICATION_FLOORS.items()))
def test_exactly_at_the_floor_qualifies(stat, floor):
    team_games = 10
    assert qualifies(stat, floor * team_games, team_games) is True


@pytest.mark.parametrize("stat,floor", list(LEADER_QUALIFICATION_FLOORS.items()))
def test_one_below_the_floor_does_not_qualify(stat, floor):
    team_games = 10
    assert qualifies(stat, floor * team_games - 1, team_games) is False


@pytest.mark.parametrize("stat", list(LEADER_QUALIFICATION_FLOORS))
def test_zero_team_games_never_qualifies(stat):
    assert qualifies(stat, 500, 0) is False
    assert qualifies(stat, 0, 0) is False
