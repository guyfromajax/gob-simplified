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

    def test_year_normalization_applies_to_mvp_selection(self):
        # Freshman gains +10 raw; Junior gains +14 raw. Year-normalized: FR 10/1.5=6.67
        # vs JR 14/1.1=12.7 → Junior is the MVP (a freshman's raw gain is expected larger).
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {
            "1": {a: 50 for a in attrs_keys},
            "2": {a: 50 for a in attrs_keys},
        }
        freshman_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        junior_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        freshman_attrs["anchor_SC"] = 60
        junior_attrs["anchor_SC"] = 57
        junior_attrs["anchor_SH"] = 57
        players = [
            {"_id": "1", "first_name": "Fresh", "last_name": "Man", "year": "freshman", "attributes": freshman_attrs},
            {"_id": "2", "first_name": "Junior", "last_name": "Varsity", "year": "junior", "attributes": junior_attrs},
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

    def test_biggest_regression_uses_year_normalization_symmetrically(self):
        # The fix: the loser award is year-normalized too (was raw). Freshman loses 15
        # raw, Senior loses 12 raw. RAW min = freshman; year-normalized FR -15/1.5=-10 vs
        # SR -12/1.0=-12 → the SENIOR's regression is the notable one and wins the award.
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {"1": {a: 50 for a in attrs_keys}, "2": {a: 50 for a in attrs_keys}}
        fr_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        sr_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        fr_attrs["anchor_SC"] = 35   # -15
        sr_attrs["anchor_SC"] = 38   # -12
        players = [
            {"_id": "1", "first_name": "Fresh", "last_name": "Man", "year": "freshman", "attributes": fr_attrs},
            {"_id": "2", "first_name": "Old", "last_name": "Guy", "year": "senior", "attributes": sr_attrs},
        ]
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        sections = build_structured_training_report_notes(
            is_training_camp=False,
            players=players,
            original_player_baselines=base,
            team=team,
            plays_data={},
            scouting_data={},
            legacy_energy_notes=[],
        )
        by_title = {s["title"]: s for s in sections}
        self.assertEqual(by_title["Biggest Regression"]["body"], "Old Guy")

    def _camp_sections(self, players):
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        base = {p["_id"]: {a: 50 for a in
                           ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]}
                for p in players}
        return build_structured_training_report_notes(
            is_training_camp=True, players=players, original_player_baselines=base,
            team={**team}, plays_data={}, scouting_data={}, legacy_energy_notes=[])

    @staticmethod
    def _jr(pid, sc):
        keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        a = {f"anchor_{k}": 50 for k in keys}
        a["anchor_SC"] = sc
        return {"_id": str(pid), "first_name": f"P{pid}", "last_name": "X", "year": "junior", "attributes": a}

    def test_camp_biggest_concern_flags_year_normalized_laggard(self):
        # Camp has no decay, so nobody is negative. Three developers (+20), one laggard (+2).
        # median normalized gain ≈ 18.2; threshold 0.5×median ≈ 9.1; only the laggard is below.
        players = [self._jr(1, 70), self._jr(2, 70), self._jr(3, 70), self._jr(4, 52)]
        by_title = {s["title"]: s for s in self._camp_sections(players)}
        self.assertEqual(by_title["Biggest Concern"]["body"], "P4 X")

    def test_camp_biggest_concern_none_when_squad_develops_evenly(self):
        players = [self._jr(1, 70), self._jr(2, 70), self._jr(3, 70)]  # all +20
        by_title = {s["title"]: s for s in self._camp_sections(players)}
        self.assertEqual(by_title["Biggest Concern"]["body"], "None")

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
