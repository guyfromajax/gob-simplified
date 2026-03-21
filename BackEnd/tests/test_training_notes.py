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


if __name__ == "__main__":
    unittest.main()
