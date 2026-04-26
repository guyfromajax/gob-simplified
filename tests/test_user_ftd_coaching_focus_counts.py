"""Lazy season totals for coaching archetype picks on user-team FTD."""

from unittest.mock import patch

from BackEnd.utils.franchise_coaching_focus_counts import (
    carryover_coaching_focus_counts_for_new_season,
    user_ftd_coaching_focus_increment,
)


def test_increment_maps_archetypes_to_ftd_subkeys():
    assert user_ftd_coaching_focus_increment("authoritarian-discipline") == {
        "coaching_focus.authoritarian": 1
    }
    assert user_ftd_coaching_focus_increment("systems-coach-offense") == {
        "coaching_focus.systems_coach": 1
    }
    assert user_ftd_coaching_focus_increment("player-maximizer-custom") == {
        "coaching_focus.player_maximizer": 1
    }
    assert user_ftd_coaching_focus_increment("culture-builder-inspire") == {
        "coaching_focus.culture_builder": 1
    }


@patch("BackEnd.utils.franchise_coaching_focus_counts.random.randint", return_value=3)
def test_training_camp_uses_random_weight_2_to_4(mock_randint):
    out = user_ftd_coaching_focus_increment(
        "systems-coach-offense",
        training_camp_first_week=True,
    )
    assert out == {"coaching_focus.systems_coach": 3}
    mock_randint.assert_called_once_with(2, 4)


def test_increment_none_or_unmapped_returns_none():
    assert user_ftd_coaching_focus_increment(None) is None
    assert user_ftd_coaching_focus_increment("") is None
    assert user_ftd_coaching_focus_increment("not-a-real-archetype-leaf") is None


def test_season_carryover_reduces_by_seventy_five_percent_rounded():
    assert carryover_coaching_focus_counts_for_new_season(
        {"authoritarian": 100, "systems_coach": 7, "player_maximizer": 1, "culture_builder": 0}
    ) == {
        "authoritarian": 25,
        "systems_coach": 2,
        "player_maximizer": 0,
        "culture_builder": 0,
    }


def test_season_carryover_empty_or_invalid():
    assert carryover_coaching_focus_counts_for_new_season(None) == {
        "authoritarian": 0,
        "systems_coach": 0,
        "player_maximizer": 0,
        "culture_builder": 0,
    }
