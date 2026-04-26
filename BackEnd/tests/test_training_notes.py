"""Tests for structured training report notes."""

import unittest

from BackEnd.models.training_notes import (
    _readiness_label,
    _offensive_play_selection,
    build_structured_training_report_notes,
)


class TestTrainingNotes(unittest.TestCase):
    def test_readiness_labels(self):
        self.assertEqual(_readiness_label(12), "Very Strong")
        self.assertEqual(_readiness_label(11), "Strong")
        self.assertEqual(_readiness_label(4), "Strong")
        self.assertEqual(_readiness_label(0), "Neutral")
        self.assertEqual(_readiness_label(-11), "Weak")
        self.assertEqual(_readiness_label(-12), "Very Weak")

    def test_offensive_greedy_skips_four_way_second_tier(self):
        plays = {
            "A": {"effectiveness": 100},
            "B": {"effectiveness": 90},
            "C": {"effectiveness": 90},
            "D": {"effectiveness": 90},
            "E": {"effectiveness": 90},
        }
        names = _offensive_play_selection(plays)
        self.assertEqual(names, ["A"])

    def test_structured_sections_include_energy_last(self):
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH"]
        base = {"1": {a: 50 for a in attrs_keys}}
        attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        attrs["anchor_SC"] = 55
        attrs["anchor_CH"] = 65
        players = [{"_id": "1", "first_name": "A", "last_name": "One", "attributes": attrs}]
        team = {"fb_efficiency": 2, "fb_opp_modifier": 1, "pt_efficiency": 0, "pt_opp_modifier": 0}
        sections = build_structured_training_report_notes(
            is_training_camp=True,
            players=players,
            original_player_baselines=base,
            team=team,
            plays_data={},
            scouting_data={},
            legacy_energy_notes=["Energy line"],
        )
        self.assertTrue(all("title" in s and "body" in s for s in sections))
        self.assertEqual(sections[-1]["title"], "Player Energy Levels")
        self.assertIn("Energy line", sections[-1]["body"])
        titles = [s["title"] for s in sections]
        self.assertIn("Training Camp MVP", titles)

    def test_ch_is_excluded_from_reporting(self):
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH"]
        base = {"1": {a: 50 for a in attrs_keys}}
        attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        attrs["anchor_CH"] = 90
        players = [{"_id": "1", "first_name": "A", "last_name": "One", "attributes": attrs}]
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        sections = build_structured_training_report_notes(
            is_training_camp=True,
            players=players,
            original_player_baselines=base,
            team=team,
            plays_data={},
            scouting_data={},
            legacy_energy_notes=[],
        )
        strong_cumulative = next(s for s in sections if s["title"] == "Strong Cumulative Increase")
        self.assertEqual(strong_cumulative["body"], "No Significant Updates")
        self.assertEqual(sections[0]["body"], "No Significant Updates")

    def test_freshman_discount_applies_only_to_mvp_selection(self):
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {
            "1": {a: 50 for a in attrs_keys},
            "2": {a: 50 for a in attrs_keys},
        }
        freshman_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        sophomore_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        freshman_attrs["anchor_SC"] = 60
        sophomore_attrs["anchor_SC"] = 57
        sophomore_attrs["anchor_SH"] = 57
        players = [
            {"_id": "1", "first_name": "Fresh", "last_name": "Man", "year": "freshman", "attributes": freshman_attrs},
            {"_id": "2", "first_name": "Junior", "last_name": "Varsity", "year": "junior", "attributes": sophomore_attrs},
        ]
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        sections = build_structured_training_report_notes(
            is_training_camp=True,
            players=players,
            original_player_baselines=base,
            team=team,
            plays_data={},
            scouting_data={},
            legacy_energy_notes=[],
        )
        self.assertEqual(sections[0]["title"], "Training Camp MVP")
        self.assertEqual(sections[0]["body"], "Junior Varsity")

    def test_misc_physique_section_before_energy(self):
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ", "CH"]
        base = {"1": {a: 50 for a in attrs_keys}}
        attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        players = [{"_id": "1", "first_name": "A", "last_name": "One", "attributes": attrs}]
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        physique = ["Test Player grew one inch during the offseason."]
        sections = build_structured_training_report_notes(
            is_training_camp=True,
            players=players,
            original_player_baselines=base,
            team=team,
            plays_data={},
            scouting_data={},
            legacy_energy_notes=["Energy line"],
            training_camp_physique_notes=physique,
        )
        self.assertEqual(sections[-1]["title"], "Player Energy Levels")
        misc = next(s for s in sections if s["title"] == "Misc")
        self.assertEqual(misc["body"], physique[0])
        self.assertLess(sections.index(misc), len(sections) - 1)


if __name__ == "__main__":
    unittest.main()
