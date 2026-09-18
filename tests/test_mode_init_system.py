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

