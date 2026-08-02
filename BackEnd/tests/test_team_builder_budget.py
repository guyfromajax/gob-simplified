"""Unit tests for Team Builder attribute model (v2 §4)."""
from __future__ import annotations

import unittest

from BackEnd.constants.team_builder_budget import (
    ATTR_MAX,
    ATTR_MIN,
    CORE_12_ATTRS,
    TOPUP_FLOOR,
    apply_capped_topup,
    capped_budget_for_inherited,
    core12_total,
    evaluate_mode_roster,
    force_core12_to_budget,
    online_eligible_for_mode,
    resolve_online_eligible,
    roster_shape_from_attrs,
)


def _attrs(total: int) -> dict:
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    return out


# Synthetic below-floor player (acceptance #11) — not tied to live Concord data.
SYNTHETIC_BELOW_FLOOR = {
    "SC": 4,
    "SH": 2,
    "ID": 8,
    "OD": 1,
    "PS": 1,
    "BH": 1,
    "RB": 1,
    "ST": 1,
    "AG": 1,
    "ND": 2,
    "IQ": 1,
    "FT": 1,
}


class TestTeamBuilderBudget(unittest.TestCase):
    def test_constants_v2(self):
        self.assertEqual(TOPUP_FLOOR, 60)
        self.assertEqual(ATTR_MIN, 5)
        self.assertEqual(ATTR_MAX, 99)
        self.assertTrue(online_eligible_for_mode("capped"))
        self.assertFalse(online_eligible_for_mode("uncapped"))

    def test_mode_determines_eligibility(self):
        players = [_attrs(400) for _ in range(12)]
        capped = evaluate_mode_roster(
            attribute_mode="capped", player_attrs=players, team_pool=9000, team_median=5000
        )
        uncapped = evaluate_mode_roster(
            attribute_mode="uncapped", player_attrs=players, team_pool=9000, team_median=5000
        )
        self.assertTrue(capped["online_eligible"])
        self.assertFalse(uncapped["online_eligible"])
        self.assertEqual(capped["roster_shape"]["team_total"], 4800)

    def test_no_top5_cap_in_evaluation(self):
        stars = [_attrs(900) for _ in range(5)]
        rest = [_attrs(50) for _ in range(7)]
        result = evaluate_mode_roster(
            attribute_mode="capped",
            player_attrs=stars + rest,
            team_pool=9000,
            team_median=5000,
        )
        self.assertTrue(result["online_eligible"])
        self.assertNotIn("over_top5_by", result)
        self.assertEqual(result["roster_shape"]["top5_total"], 4500)

    def test_acceptance_11_synthetic_topup(self):
        """Acceptance #11: synthetic 24 → 60 (+36). Not a live Concord check."""
        self.assertEqual(core12_total(SYNTHETIC_BELOW_FLOOR), 24)
        self.assertEqual(capped_budget_for_inherited(24), 60)
        result = apply_capped_topup(SYNTHETIC_BELOW_FLOOR)
        self.assertTrue(result["topped_up"])
        self.assertEqual(result["raw_total"], 24)
        self.assertEqual(result["budget"], 60)
        self.assertEqual(core12_total(result["attrs"]), 60)
        for key in CORE_12_ATTRS:
            self.assertGreaterEqual(result["attrs"][key], ATTR_MIN)
            self.assertLessEqual(result["attrs"][key], ATTR_MAX)

        roster = [_attrs(400) for _ in range(11)] + [SYNTHETIC_BELOW_FLOOR]
        pre = roster_shape_from_attrs(roster)
        post_attrs = [_attrs(400) for _ in range(11)] + [result["attrs"]]
        post = roster_shape_from_attrs(post_attrs)
        self.assertEqual(post["team_total"] - pre["team_total"], 36)

    def test_force_core12_to_budget_blocks_cross_player_inflation(self):
        forced = force_core12_to_budget(_attrs(600), 400)
        self.assertEqual(core12_total(forced), 400)

    def test_uncapped_over_pool_reported_against_runtime_pool(self):
        players = [_attrs(600) for _ in range(12)]  # 7200
        result = evaluate_mode_roster(
            attribute_mode="uncapped",
            player_attrs=players,
            team_pool=5000,
            team_median=4000,
        )
        self.assertEqual(result["over_pool_by"], 2200)
        self.assertEqual(result["team_pool"], 5000)
        self.assertFalse(result["online_eligible"])

    def test_resolve_online_eligible_prefers_spec_field(self):
        self.assertTrue(resolve_online_eligible({"online_eligible": True, "online_eligibility": False}))
        self.assertFalse(resolve_online_eligible({"online_eligible": False, "online_eligibility": True}))
        self.assertFalse(resolve_online_eligible({"online_eligibility": False}))
        self.assertTrue(resolve_online_eligible({}))


if __name__ == "__main__":
    unittest.main()
