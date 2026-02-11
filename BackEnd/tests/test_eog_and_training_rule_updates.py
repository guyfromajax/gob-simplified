import random
import unittest
from unittest.mock import patch

from BackEnd.models.training_execution_v2 import (
    _apply_player_training_points,
    _apply_training_camp_bonus,
    _pre_training_decay_range_for_year,
)
from BackEnd.eog_attr_rules import calculate_fb_opp_modifier_change, calculate_pt_opp_modifier_change
from BackEnd.eog_attr_rules import (
    calculate_special_situations_from_sources,
    calculate_team_totals_from_sources,
)


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

    def test_eog_totals_source_prefers_team_totals_over_box_score(self):
        team_totals_obj = {
            "Morristown": {"FGM": 10, "FGA": 20, "TO": 3, "STL": 4, "DREB": 8, "OREB": 2}
        }
        box_score_obj = {
            "MORRISTOWN": {
                "p1": {"FGM": 1, "FGA": 1, "TO": 1, "STL": 1, "DREB": 1, "OREB": 1}
            }
        }
        totals = calculate_team_totals_from_sources("MORRISTOWN", "Morristown", team_totals_obj, box_score_obj)
        self.assertEqual(totals["FGM"], 10)
        self.assertEqual(totals["FGA"], 20)
        self.assertEqual(totals["TO"], 3)

    def test_eog_totals_falls_back_to_box_score_aggregation(self):
        team_totals_obj = {}
        box_score_obj = {
            "MORRISTOWN": {
                "p1": {"FGM": 2, "FGA": 5, "TO": 1, "STL": 0, "DREB": 3, "OREB": 1},
                "p2": {"FGM": 4, "FGA": 7, "TO": 2, "STL": 2, "DREB": 4, "OREB": 0},
            }
        }
        totals = calculate_team_totals_from_sources("MORRISTOWN", "Morristown", team_totals_obj, box_score_obj)
        self.assertEqual(totals["FGM"], 6)
        self.assertEqual(totals["FGA"], 12)
        self.assertEqual(totals["TO"], 3)
        self.assertEqual(totals["STL"], 2)
        self.assertEqual(totals["DREB"], 7)
        self.assertEqual(totals["OREB"], 1)

    def test_eog_special_situations_prefers_team_stats_over_scouting(self):
        team_stats_obj = {
            "Morristown": {
                "offense": {"Fast_Break_Entries": 10, "Fast_Break_Success": 4},
                "defense": {
                    "HCT": {"used": 7, "success": 5},
                    "FCP": {"used": 1, "success": 0},
                },
            }
        }
        team_obj = {
            "scouting": {
                "offense": {"Fast_Break_Entries": 99, "Fast_Break_Success": 99},
                "defense": {"HCT": {"used": 99, "success": 99}, "FCP": {"used": 99, "success": 99}},
            }
        }
        special = calculate_special_situations_from_sources("Morristown", team_obj, team_stats_obj)
        self.assertEqual(special["fb_entries"], 10)
        self.assertEqual(round(special["fb_rate"], 2), 40.0)
        self.assertEqual(special["pt_total_attempts"], 8)
        self.assertEqual(round(special["pt_combined_rate"], 2), 62.5)

    def test_eog_special_situations_falls_back_to_team_scouting(self):
        team_stats_obj = {}
        team_obj = {
            "scouting": {
                "offense": {"Fast_Break_Entries": 5, "Fast_Break_Success": 1},
                "defense": {
                    "HCT": {"used": 4, "success": 1},
                    "FCP": {"used": 2, "success": 1},
                },
            }
        }
        special = calculate_special_situations_from_sources("Morristown", team_obj, team_stats_obj)
        self.assertEqual(special["fb_entries"], 5)
        self.assertEqual(round(special["fb_rate"], 2), 20.0)
        self.assertEqual(special["pt_total_attempts"], 6)
        self.assertEqual(round(special["pt_combined_rate"], 2), 33.33)

    def test_eog_special_situations_supports_team_id_keyed_team_stats(self):
        team_stats_obj = {
            "MORRISTOWN": {
                "offense": {"Fast_Break_Entries": 8, "Fast_Break_Success": 2},
                "defense": {
                    "HCT": {"used": 5, "success": 3},
                    "FCP": {"used": 3, "success": 3},
                },
            }
        }
        # Empty scouting fallback should not matter when team_stats has canonical team_id key.
        team_obj = {}
        special = calculate_special_situations_from_sources(
            "Morristown", team_obj, team_stats_obj, team_id_label="MORRISTOWN"
        )
        self.assertEqual(special["fb_entries"], 8)
        self.assertEqual(round(special["fb_rate"], 2), 25.0)
        self.assertEqual(special["pt_total_attempts"], 8)
        self.assertEqual(round(special["pt_combined_rate"], 2), 75.0)


if __name__ == "__main__":
    unittest.main()
