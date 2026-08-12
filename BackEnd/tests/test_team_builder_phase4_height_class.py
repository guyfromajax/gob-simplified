"""Phase 4 — height/class budgets + seeded weight (§10)."""
from __future__ import annotations

import unittest
import uuid

from BackEnd.constants.team_builder_budget import (
    class_rank_from_year,
    evaluate_mode_roster,
    roster_shape_from_attrs,
)
from BackEnd.utils.player_generation import weight_from_height


class TestPhase4HeightClass(unittest.TestCase):
    def test_weight_seeded_from_player_id_is_stable(self):
        pid = str(uuid.uuid4())
        a = weight_from_height(77, player_id=pid)
        b = weight_from_height(77, player_id=pid)
        self.assertEqual(a, b)
        # Different ids diverge for the same height (almost always).
        other = weight_from_height(77, player_id=str(uuid.uuid4()))
        # Allow rare collision but assert both are in the calibrated band.
        for w in (a, other):
            self.assertGreaterEqual(w, 209 - 12)
            self.assertLessEqual(w, 210 + 12)

    def test_weight_scales_with_height(self):
        pid = str(uuid.uuid4())
        short = weight_from_height(66, player_id=pid)
        tall = weight_from_height(84, player_id=pid)
        self.assertLess(short, tall)

    def test_inherited_shape_budgets_cover_fifteen(self):
        from BackEnd.utils.team_builder_roster import compute_inherited_shape_budgets

        core = [{"height": 76, "year": "Senior"} for _ in range(12)]
        walk = [{"height": 70, "year": "Freshman"} for _ in range(3)]
        shape = compute_inherited_shape_budgets(core, walk)
        self.assertEqual(shape["height_budget"], 12 * 76 + 3 * 70)
        self.assertEqual(shape["class_budget"], 12 * 4 + 3 * 1)
        self.assertEqual(shape["class_rank"]["SR"], 4)
        self.assertEqual(shape["height_min_in"], 66)

    def test_class_rank_fr_to_sr(self):
        self.assertEqual(class_rank_from_year("FR"), 1)
        self.assertEqual(class_rank_from_year("Freshman"), 1)
        self.assertEqual(class_rank_from_year("SR"), 4)
        self.assertEqual(class_rank_from_year("JH"), 0)

    def test_roster_shape_records_height_and_class(self):
        attrs = [{"SC": 5} for _ in range(3)]
        # Pad to look like core-12 keys aren't required for total helper.
        shape = roster_shape_from_attrs(
            attrs,
            heights=[70, 72, 74],
            class_years=["FR", "SO", "SR"],
        )
        self.assertEqual(shape["height_total"], 216)
        self.assertEqual(shape["class_total"], 1 + 2 + 4)

    def test_evaluate_reports_height_over_and_class_delta(self):
        players = [{} for _ in range(2)]
        result = evaluate_mode_roster(
            attribute_mode="capped",
            player_attrs=players,
            heights=[80, 80],
            class_years=["SR", "SR"],
            height_budget=150,
            class_budget=6,
        )
        self.assertEqual(result["height_over_by"], 10)
        self.assertEqual(result["class_delta"], 2)
        self.assertEqual(result["roster_shape"]["height_total"], 160)
        self.assertEqual(result["roster_shape"]["class_total"], 8)

    def test_uncapped_skips_height_class_enforcement_fields(self):
        result = evaluate_mode_roster(
            attribute_mode="uncapped",
            player_attrs=[{}],
            heights=[90],
            class_years=["SR"],
            height_budget=10,
            class_budget=1,
            team_pool=99999,
        )
        # Uncapped: over/delta stay 0 — budgets do not apply.
        self.assertEqual(result["height_over_by"], 0)
        self.assertEqual(result["class_delta"], 0)


if __name__ == "__main__":
    unittest.main()
