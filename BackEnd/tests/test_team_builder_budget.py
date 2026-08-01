"""Unit tests for Team Builder attribute model (v2 §4)."""
from __future__ import annotations

import unittest

from BackEnd.constants.team_builder_budget import (
    ATTR_MAX,
    ATTR_MIN,
    CAPPED_PLAYER_CEILING,
    CORE_12_ATTRS,
    TOPUP_FLOOR,
    UNCAPPED_TEAM_POOL,
    apply_capped_topup,
    capped_budget_for_inherited,
    core12_total,
    evaluate_mode_roster,
    online_eligible_for_mode,
    roster_shape_from_attrs,
)


def _attrs(total: int) -> dict:
    """Spread total across core-12 roughly evenly."""
    base, rem = divmod(total, 12)
    out = {k: base for k in CORE_12_ATTRS}
    for i in range(rem):
        out[CORE_12_ATTRS[i]] += 1
    return out


# Jason Potter (Concord) — largest league top-up shortfall (24 → 60 = +36).
JASON_POTTER = {
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
        self.assertEqual(UNCAPPED_TEAM_POOL, 7027)
        self.assertEqual(CAPPED_PLAYER_CEILING, 1035)
        self.assertEqual(ATTR_MIN, 5)
        self.assertEqual(ATTR_MAX, 99)
        self.assertTrue(online_eligible_for_mode("capped"))
        self.assertFalse(online_eligible_for_mode("uncapped"))

    def test_mode_determines_eligibility(self):
        # Uncapped is ineligible even when totals would have passed the old caps.
        players = [_attrs(400) for _ in range(12)]
        capped = evaluate_mode_roster(attribute_mode="capped", player_attrs=players)
        uncapped = evaluate_mode_roster(attribute_mode="uncapped", player_attrs=players)
        self.assertTrue(capped["online_eligible"])
        self.assertFalse(uncapped["online_eligible"])
        self.assertEqual(capped["roster_shape"]["team_total"], 4800)

    def test_no_top5_cap_in_evaluation(self):
        stars = [_attrs(1035) for _ in range(5)]
        rest = [_attrs(50) for _ in range(7)]
        result = evaluate_mode_roster(attribute_mode="capped", player_attrs=stars + rest)
        self.assertTrue(result["online_eligible"])
        self.assertNotIn("over_top5_by", result)
        self.assertEqual(result["roster_shape"]["top5_total"], 5175)

    def test_concord_potter_topup(self):
        self.assertEqual(core12_total(JASON_POTTER), 24)
        self.assertEqual(capped_budget_for_inherited(24), 60)
        result = apply_capped_topup(JASON_POTTER)
        self.assertTrue(result["topped_up"])
        self.assertEqual(result["raw_total"], 24)
        self.assertEqual(result["budget"], 60)
        self.assertEqual(core12_total(result["attrs"]), 60)
        for key in CORE_12_ATTRS:
            self.assertGreaterEqual(result["attrs"][key], ATTR_MIN)
            self.assertLessEqual(result["attrs"][key], ATTR_MAX)

    def test_roster_shape_post_topup(self):
        """§4.3 / acceptance #11: shape records post-top-up values."""
        roster = [_attrs(400) for _ in range(11)] + [JASON_POTTER]
        pre = roster_shape_from_attrs(roster)
        self.assertEqual(pre["team_total"], 400 * 11 + 24)

        post_attrs = [_attrs(400) for _ in range(11)] + [apply_capped_topup(JASON_POTTER)["attrs"]]
        post = roster_shape_from_attrs(post_attrs)
        self.assertEqual(post["team_total"], pre["team_total"] + 36)
        self.assertEqual(post["team_total"] - pre["team_total"], 36)

    def test_no_topup_when_at_or_above_floor(self):
        raw = _attrs(400)
        result = apply_capped_topup(raw)
        self.assertFalse(result["topped_up"])
        self.assertEqual(result["budget"], 400)
        self.assertEqual(core12_total(result["attrs"]), 400)


if __name__ == "__main__":
    unittest.main()
