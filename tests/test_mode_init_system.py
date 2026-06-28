"""
Regression tests for Mode Initialization System (Mode_Init_System.md).
Covers TeamManager.init_team_attributes for single, franchise, and tournament (seed-based).
"""
import pytest
from BackEnd.models.team_manager import TeamManager
from BackEnd.constants.shot_threshold_scale import (
    FRANCHISE_INIT_HI,
    FRANCHISE_INIT_LO,
    MAX,
    MIN,
    TOURNAMENT_SEED_ST_RANGES,
)

A_GROUP_KEYS = [
    "discipline", "fight", "offensive_efficiency", "defensive_efficiency",
    "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier",
]


def _assert_a_group_in_range(attrs, lo, hi):
    for k in A_GROUP_KEYS:
        assert attrs[k] >= lo and attrs[k] <= hi, f"{k}={attrs[k]} not in [{lo}, {hi}]"


def test_init_team_attributes_single_returns_all_keys():
    attrs = TeamManager.init_team_attributes(mode="single")
    expected = set(A_GROUP_KEYS) | {"shot_threshold", "team_chemistry", "rebound_modifier"}
    assert set(attrs.keys()) == expected


def test_init_team_attributes_single_ranges():
    for _ in range(100):
        attrs = TeamManager.init_team_attributes(mode="single")
        _assert_a_group_in_range(attrs, -10, 10)
        assert 7 <= attrs["team_chemistry"] <= 25
        assert 0 <= attrs["rebound_modifier"] <= 0.4
        assert MIN <= attrs["shot_threshold"] <= MAX


def test_init_team_attributes_franchise_returns_all_keys():
    attrs = TeamManager.init_team_attributes(mode="franchise")
    expected = set(A_GROUP_KEYS) | {"shot_threshold", "team_chemistry", "rebound_modifier"}
    assert set(attrs.keys()) == expected


def test_init_team_attributes_franchise_ranges():
    for _ in range(100):
        attrs = TeamManager.init_team_attributes(mode="franchise")
        _assert_a_group_in_range(attrs, -1, 1)
        assert 7 <= attrs["team_chemistry"] <= 10
        assert attrs["rebound_modifier"] == 0.2
        assert FRANCHISE_INIT_LO <= attrs["shot_threshold"] <= FRANCHISE_INIT_HI


# Tournament seed-based ranges (derived from shot_threshold_scale)
TOURNAMENT_SEED_RANGES = {
    1: {"a": (5, 10), "tc": (20, 25), "rm": (0.30, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[1]},
    2: {"a": (-2, 10), "tc": (12, 25), "rm": (0.15, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[2]},
    3: {"a": (-2, 10), "tc": (12, 25), "rm": (0.15, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[3]},
    4: {"a": (-2, 10), "tc": (12, 25), "rm": (0.15, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[4]},
    5: {"a": (-8, 5), "tc": (8, 18), "rm": (0.01, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[5]},
    6: {"a": (-8, 5), "tc": (8, 18), "rm": (0.01, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[6]},
    7: {"a": (-8, 5), "tc": (8, 18), "rm": (0.01, 0.40), "st": TOURNAMENT_SEED_ST_RANGES[7]},
    8: {"a": (-10, -2), "tc": (7, 12), "rm": (0.01, 0.20), "st": TOURNAMENT_SEED_ST_RANGES[8]},
}


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6, 7, 8])
def test_init_team_attributes_tournament_seed_ranges(seed):
    r = TOURNAMENT_SEED_RANGES[seed]
    a_lo, a_hi = r["a"]
    tc_lo, tc_hi = r["tc"]
    rm_lo, rm_hi = r["rm"]
    st_lo, st_hi = r["st"]
    for _ in range(50):
        attrs = TeamManager.init_team_attributes(mode="tournament", tournament_seed=seed)
        _assert_a_group_in_range(attrs, a_lo, a_hi)
        assert tc_lo <= attrs["team_chemistry"] <= tc_hi, (
            f"seed={seed} team_chemistry={attrs['team_chemistry']} not in {r['tc']}"
        )
        assert rm_lo <= attrs["rebound_modifier"] <= rm_hi, (
            f"seed={seed} rebound_modifier={attrs['rebound_modifier']} not in {r['rm']}"
        )
        assert st_lo <= attrs["shot_threshold"] <= st_hi, (
            f"seed={seed} shot_threshold={attrs['shot_threshold']} not in {r['st']}"
        )


def test_init_team_attributes_tournament_without_seed_fallback():
    """Tournament without seed uses single-game-style fallback."""
    for _ in range(50):
        attrs = TeamManager.init_team_attributes(mode="tournament")
        _assert_a_group_in_range(attrs, -10, 10)
        assert 7 <= attrs["team_chemistry"] <= 25
        assert 0 <= attrs["rebound_modifier"] <= 0.4
        assert MIN <= attrs["shot_threshold"] <= MAX


def test_init_team_attributes_tournament_invalid_seed_ignored():
    """tournament_seed outside 1-8 is ignored; fallback ranges used."""
    for bad_seed in (0, -1, 9, 10, None):
        attrs = TeamManager.init_team_attributes(mode="tournament", tournament_seed=bad_seed)
        _assert_a_group_in_range(attrs, -10, 10)
        assert 7 <= attrs["team_chemistry"] <= 25


def test_tournament_create_tournament_teams_use_seed_based_attributes():
    """Integration: create_tournament produces 8 teams with seed-ordered attributes (1=best, 8=worst)."""
    import pymongo.errors
    from unittest.mock import patch, MagicMock
    from bson import ObjectId
    from BackEnd.tournament.tournament_manager import TournamentManager
    from BackEnd.db import teams_collection, players_collection

    names = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]
    try:
        teams_collection.delete_many({"name": {"$in": names}})
    except (pymongo.errors.ConfigurationError, pymongo.errors.ServerSelectionTimeoutError) as e:
        pytest.skip(f"MongoDB not available: {e}")
    # Ensure 8 teams exist
    for n in names:
        teams_collection.insert_one({"name": n})
    # Minimal player per team so create_tournament can load rosters
    players_collection.delete_many({"team": {"$in": names}})
    for n in names:
        players_collection.insert_one({
            "first_name": "P", "last_name": n, "team": n,
            "attributes": {"SC": 50, "SH": 50, "ID": 50, "OD": 50, "PS": 50, "BH": 50, "RB": 50, "ST": 50, "AG": 50, "ND": 50, "IQ": 50, "FT": 50},
            "position_ratings": {},
        })

    mock_tournaments = MagicMock()
    mock_tournaments.insert_one.return_value.inserted_id = ObjectId()
    # Freeze shuffle so doc order = team list order → first team = seed 1, etc.
    with patch("BackEnd.tournament.tournament_manager.random.shuffle"):
        manager = TournamentManager(
            user_team_id="T1",
            tournaments_collection=mock_tournaments,
            team_ids=names,
        )
        tournament = manager.create_tournament()

    teams_in_order = list(tournament["teams"].values())  # insertion order = seed 1..8
    assert len(teams_in_order) == 8
    for seed, team in enumerate(teams_in_order, start=1):
        r = TOURNAMENT_SEED_RANGES[seed]
        a_lo, a_hi = r["a"]
        for k in A_GROUP_KEYS:
            assert a_lo <= team[k] <= a_hi, f"seed={seed} {k}={team[k]} not in {r['a']}"
        assert r["tc"][0] <= team["team_chemistry"] <= r["tc"][1]
        assert r["rm"][0] <= team["rebound_modifier"] <= r["rm"][1]
        assert r["st"][0] <= team["shot_threshold"] <= r["st"][1]

    # Cleanup
    teams_collection.delete_many({"name": {"$in": names}})
    players_collection.delete_many({"team": {"$in": names}})
