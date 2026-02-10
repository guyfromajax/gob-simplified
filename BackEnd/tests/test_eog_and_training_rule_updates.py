import random
import unittest
from unittest.mock import patch

from BackEnd.models.training_execution_v2 import (
    _apply_player_training_points,
    _apply_training_camp_bonus,
    _pre_training_decay_range_for_year,
)
from BackEnd.eog_attr_rules import calculate_fb_opp_modifier_change, calculate_pt_opp_modifier_change


class TestEOGAndTrainingRuleUpdates(unittest.TestCase):
    def test_fb_opp_modifier_uses_low_rate_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return a

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_fb_opp_modifier_change({"fb_rate": 10, "fb_entries": 5})
        self.assertEqual(change, 0)
        self.assertEqual(calls[-1], (0, 2))

    def test_fb_opp_modifier_uses_high_volume_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return a

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_fb_opp_modifier_change({"fb_rate": 40, "fb_entries": 13})
        self.assertEqual(change, -3)
        self.assertEqual(calls[-1], (-3, -2))

    def test_fb_opp_modifier_uses_mid_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return b

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_fb_opp_modifier_change({"fb_rate": 35, "fb_entries": 8})
        self.assertEqual(change, 0)
        self.assertEqual(calls[-1], (-1, 0))

    def test_pt_opp_modifier_uses_low_rate_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return b

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_pt_opp_modifier_change({"pt_combined_rate": 10, "pt_total_attempts": 2})
        self.assertEqual(change, 2)
        self.assertEqual(calls[-1], (1, 2))

    def test_pt_opp_modifier_uses_high_volume_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return b

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_pt_opp_modifier_change({"pt_combined_rate": 35, "pt_total_attempts": 13})
        self.assertEqual(change, -2)
        self.assertEqual(calls[-1], (-3, -2))

    def test_pt_opp_modifier_uses_mid_branch(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return a

        with patch.object(random, "randint", side_effect=fake_randint):
            change = calculate_pt_opp_modifier_change({"pt_combined_rate": 35, "pt_total_attempts": 8})
        self.assertEqual(change, -2)
        self.assertEqual(calls[-1], (-2, -1))

    def test_pre_training_decay_ranges_match_doc(self):
        self.assertEqual(_pre_training_decay_range_for_year("freshman"), (-5, -2))
        self.assertEqual(_pre_training_decay_range_for_year("sophomore"), (-4, -1))
        self.assertEqual(_pre_training_decay_range_for_year("junior"), (-3, -1))
        self.assertEqual(_pre_training_decay_range_for_year("senior"), (-2, 0))
        self.assertEqual(_pre_training_decay_range_for_year("unknown"), (-3, -1))

    def test_player_training_points_base_and_year_adjustment(self):
        calls = []

        def fake_randint(a, b):
            calls.append((a, b))
            return b

        player = {
            "year": "senior",
            "attributes": {"anchor_SC": 50, "SC": 50},
        }

        with patch.object(random, "randint", side_effect=fake_randint):
            _apply_player_training_points(player, "SC", points=2, archetype=None, sub_option=None, multiplier=1.0)

        self.assertEqual(calls[-1], (2, 4))
        self.assertEqual(player["attributes"]["anchor_SC"], 54)
        self.assertEqual(player["attributes"]["SC"], 54)

    def test_training_camp_bonus_applies_for_high_ch_pg(self):
        player = {
            "position_ratings": {"PG": 90, "SG": 80, "SF": 70, "PF": 60, "C": 50},
            "attributes": {
                "anchor_CH": 85,
                "CH": 85,
                "anchor_PS": 50, "PS": 50,
                "anchor_BH": 50, "BH": 50,
                "anchor_IQ": 50, "IQ": 50,
            },
        }
        with patch.object(random, "randint", return_value=3):
            _apply_training_camp_bonus([player])

        self.assertEqual(player["attributes"]["anchor_PS"], 53)
        self.assertEqual(player["attributes"]["anchor_BH"], 53)
        self.assertEqual(player["attributes"]["anchor_IQ"], 53)

    def test_training_camp_bonus_sf_uses_ag_plus_two_random_attrs(self):
        player = {
            "position_ratings": {"PG": 70, "SG": 75, "SF": 90, "PF": 60, "C": 55},
            "attributes": {
                "anchor_CH": 65,
                "CH": 65,
                "anchor_AG": 40, "AG": 40,
                "anchor_SC": 40, "SC": 40,
                "anchor_SH": 40, "SH": 40,
                "anchor_ID": 40, "ID": 40,
                "anchor_OD": 40, "OD": 40,
            },
        }
        with patch.object(random, "sample", return_value=["SC", "ID"]), patch.object(random, "randint", return_value=2):
            _apply_training_camp_bonus([player])

        self.assertEqual(player["attributes"]["anchor_AG"], 42)
        self.assertEqual(player["attributes"]["anchor_SC"], 42)
        self.assertEqual(player["attributes"]["anchor_ID"], 42)
        self.assertEqual(player["attributes"]["anchor_SH"], 40)
        self.assertEqual(player["attributes"]["anchor_OD"], 40)


if __name__ == "__main__":
    unittest.main()
