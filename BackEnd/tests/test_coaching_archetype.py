"""Tests for the coaching archetype classifier (BackEnd/utils/coaching_archetype.py)."""

import random
import unittest

from BackEnd.utils.coaching_archetype import (
    ARCHETYPE_QUALIFIERS,
    ATTRS_IN_PLAY,
    UNCONVENTIONAL,
    attr_value,
    classify_archetype,
    compute_top_attributes,
    qualifying_archetypes,
)
from BackEnd.utils.user_tracking import ARCHETYPE_KEYS


def lineup_from_totals(totals: dict) -> list[dict]:
    """A single-starter lineup whose per-attribute totals equal `totals`.

    compute_top_attributes sums across the list, so one starter carrying the
    totals (under anchor_ keys) is enough to drive classification deterministically.
    """
    return [{f"anchor_{k}": v for k, v in totals.items()}]


class TestKeySync(unittest.TestCase):
    def test_qualifier_keys_plus_fallback_match_canonical_18(self):
        keys = [k for k, _ in ARCHETYPE_QUALIFIERS] + [UNCONVENTIONAL]
        self.assertEqual(len(keys), 18)
        self.assertEqual(len(keys), len(set(keys)), "duplicate archetype keys")
        self.assertEqual(set(keys), set(ARCHETYPE_KEYS), "classifier keys drifted from user_tracking")


class TestAttrValue(unittest.TestCase):
    def test_prefers_anchor(self):
        self.assertEqual(attr_value({"anchor_SC": 80, "SC": 10}, "SC"), 80.0)

    def test_falls_back_to_live_key(self):
        self.assertEqual(attr_value({"SC": 42}, "SC"), 42.0)

    def test_missing_is_zero(self):
        self.assertEqual(attr_value({}, "SC"), 0.0)

    def test_present_anchor_zero_is_used(self):
        # A present anchor of 0 wins over the live key (mirrors JS ?? semantics).
        self.assertEqual(attr_value({"anchor_SC": 0, "SC": 50}, "SC"), 0.0)


class TestTopThree(unittest.TestCase):
    def test_tie_spill_at_third_rank(self):
        # Spec example: SC=54, SH=ST=IQ=53 -> {SC, SH, ST, IQ}.
        totals = {a: 10 for a in ATTRS_IN_PLAY}
        totals.update({"SC": 54, "SH": 53, "ST": 53, "IQ": 53})
        self.assertEqual(compute_top_attributes(lineup_from_totals(totals)), {"SC", "SH", "ST", "IQ"})

    def test_set_has_at_least_three(self):
        totals = {a: i for i, a in enumerate(ATTRS_IN_PLAY)}  # all distinct
        self.assertGreaterEqual(len(compute_top_attributes(lineup_from_totals(totals))), 3)


class TestQualifiers(unittest.TestCase):
    def test_mr_fundamentals_two_of_ps_bh_rb(self):
        self.assertIn("mr_fundamentals", qualifying_archetypes({"PS", "BH", "IQ"}))
        # Only one of the three -> does not qualify.
        self.assertNotIn("mr_fundamentals", qualifying_archetypes({"PS", "IQ", "ST"}))

    def test_defensive_athleticism_excludes_st(self):
        # (ID|OD) + ST but no AG/ND: the_intimidator fires, defensive_athleticism must NOT.
        pool = qualifying_archetypes({"ID", "ST", "IQ"})
        self.assertIn("the_intimidator", pool)
        self.assertNotIn("defensive_athleticism", pool)

    def test_defensive_athleticism_fires_on_ag_nd(self):
        self.assertIn("defensive_athleticism", qualifying_archetypes({"ID", "AG", "IQ"}))


class TestClassify(unittest.TestCase):
    def test_single_qualifier_is_deterministic(self):
        # {RB, ST, IQ} -> only rebounding_king qualifies.
        totals = {a: 1 for a in ATTRS_IN_PLAY}
        totals.update({"RB": 100, "ST": 100, "IQ": 100})
        self.assertEqual(classify_archetype(lineup_from_totals(totals)), "rebounding_king")

    def test_no_qualifier_falls_back_to_unconventional(self):
        # {AG, IQ, RB} -> nothing qualifies.
        totals = {a: 1 for a in ATTRS_IN_PLAY}
        totals.update({"AG": 100, "IQ": 100, "RB": 100})
        self.assertEqual(classify_archetype(lineup_from_totals(totals)), UNCONVENTIONAL)

    def test_multiple_qualifiers_pick_from_pool(self):
        # {SC, SH, ID} -> {pure_offense, od_balance}.
        totals = {a: 1 for a in ATTRS_IN_PLAY}
        totals.update({"SC": 100, "SH": 100, "ID": 100})
        starters = lineup_from_totals(totals)
        pool = set(qualifying_archetypes(compute_top_attributes(starters)))
        self.assertEqual(pool, {"pure_offense", "od_balance"})
        # Random pick always lands inside the pool, regardless of seed.
        for seed in range(20):
            self.assertIn(classify_archetype(starters, rng=random.Random(seed)), pool)


if __name__ == "__main__":
    unittest.main()
