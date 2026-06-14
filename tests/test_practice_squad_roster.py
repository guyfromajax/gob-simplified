"""Tests for Practice Squad roster construction."""

from BackEnd.practice_squad.roster import (
    build_locked_tier_roster,
    gather_region_pool,
    ps_team_id,
)


def test_build_locked_tier_roster_takes_twelve():
    pool = []
    for i in range(20):
        pool.append(
            {
                "source": "frd",
                "player_id": f"r{i}",
                "name": f"Player {i}",
                "parent_team_name": None,
                "position_ratings": {
                    "PG": 40 + (i % 5),
                    "SG": 35 + (i % 5),
                    "SF": 30 + (i % 5),
                    "PF": 25 + (i % 5),
                    "C": 20 + (i % 5),
                },
                "best_rt": 40 + (i % 5),
            }
        )
    roster = build_locked_tier_roster(pool)
    assert len(roster) == 12
    assert len(pool) == 8


def test_ps_team_id_format():
    assert ps_team_id("A", 1) == "ps_A_1"
