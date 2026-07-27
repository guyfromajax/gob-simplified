"""Unit tests for Team Builder budget evaluation (§9 revised)."""
from __future__ import annotations

import unittest

from BackEnd.constants.team_builder_budget import (
    PLAYER_ATTR_CEILING,
    PLAYER_ATTR_FLOOR,
    TEAM_ATTR_BUDGET,
    TOP5_ATTR_CAP,
    evaluate_roster_budget,
)


def _attrs(total: int) -> dict:
    """Spread total across core-12 roughly evenly."""
    keys = ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT")
    base, rem = divmod(total, 12)
    out = {k: base for k in keys}
    for i in range(rem):
        out[keys[i]] += 1
    return out


class TestTeamBuilderBudget(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(TEAM_ATTR_BUDGET, 6400)
        self.assertEqual(TOP5_ATTR_CAP, 3950)
        self.assertEqual(PLAYER_ATTR_CEILING, 1035)
        self.assertEqual(PLAYER_ATTR_FLOOR, 24)

    def test_eligible_balanced_roster(self):
        # 12 players at ~400 = 4800 team; top-5 = 2000 — under all caps
        players = [_attrs(400) for _ in range(12)]
        result = evaluate_roster_budget(players)
        self.assertTrue(result["eligible_for_online"])
        self.assertEqual(result["over_top5_by"], 0)
        self.assertEqual(result["roster_shape"]["top5_total"], 2000)

    def test_top5_cap_fails_independently(self):
        # Five maxed stars + weak rest: team under 6400, top-5 over 3950
        stars = [_attrs(1035) for _ in range(5)]  # top-5 = 5175
        rest = [_attrs(50) for _ in range(7)]  # +350 = 5525 team
        result = evaluate_roster_budget(stars + rest)
        self.assertGreater(result["over_top5_by"], 0)
        self.assertEqual(result["over_budget_by"], 0)
        self.assertFalse(result["eligible_for_online"])
        self.assertEqual(result["roster_shape"]["top5_total"], 5175)

    def test_floor_24_allows_weak_but_not_zero(self):
        # Top 12 with one player at 23 fails; at 24 passes (other dims ok)
        roster_bad = [_attrs(400) for _ in range(11)] + [_attrs(23)]
        bad = evaluate_roster_budget(roster_bad)
        self.assertGreater(bad["floor_violations"], 0)
        self.assertFalse(bad["eligible_for_online"])

        roster_ok = [_attrs(400) for _ in range(11)] + [_attrs(24)]
        ok = evaluate_roster_budget(roster_ok)
        self.assertEqual(ok["floor_violations"], 0)


if __name__ == "__main__":
    unittest.main()
