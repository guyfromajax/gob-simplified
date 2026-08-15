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

    def test_inseason_practice_player_ranks_full_pool_when_every_total_is_negative(self):
        """The least-negative normalized total still earns the weekly top award."""
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {"1": {a: 50 for a in attrs_keys}, "2": {a: 50 for a in attrs_keys}}
        better_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        worse_attrs = {f"anchor_{a}": 50 for a in attrs_keys}
        better_attrs["anchor_SC"] = 48  # JR normalized total: -2 / 1.1
        worse_attrs["anchor_SC"] = 44   # JR normalized total: -6 / 1.1
        players = [
            {"_id": "1", "first_name": "Least", "last_name": "Negative", "year": "junior", "attributes": better_attrs},
            {"_id": "2", "first_name": "Most", "last_name": "Negative", "year": "junior", "attributes": worse_attrs},
        ]
        sections = build_structured_training_report_notes(
            is_training_camp=False,
            players=players,
            original_player_baselines=base,
            team={"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0},
            plays_data={},
            scouting_data={},
            legacy_energy_notes=[],
        )
        by_title = {s["title"]: s for s in sections}
        self.assertEqual(by_title["Practice Player Of The Week"]["body"], "Least Negative")
        self.assertEqual(by_title["Practice Player Of The Week"]["player_id"], "1")
        self.assertEqual(by_title["Biggest Regression"]["body"], "Most Negative")

    def test_inseason_practice_player_allows_zero_and_preserves_co_winner_ties(self):
        attrs_keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {pid: {a: 50 for a in attrs_keys} for pid in ("1", "2")}
        unchanged = {f"anchor_{a}": 50 for a in attrs_keys}
        players = [
            {"_id": "1", "first_name": "A", "last_name": "Zero", "year": "senior", "attributes": dict(unchanged)},
            {"_id": "2", "first_name": "B", "last_name": "Zero", "year": "freshman", "attributes": dict(unchanged)},
        ]
        sections = build_structured_training_report_notes(
            is_training_camp=False,
            players=players,
            original_player_baselines=base,
            team={"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0},
            plays_data={},
            scouting_data={},
            legacy_energy_notes=[],
        )
        by_title = {s["title"]: s for s in sections}
        award = by_title["Practice Players Of The Week"]
        self.assertEqual(award["body"], "A Zero, B Zero")
        self.assertEqual(award["player_ids"], ["1", "2"])
        self.assertEqual(by_title["Biggest Regression"]["body"], "None")

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

    def _one_player_container_bodies(self, deltas, is_camp):
        keys = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]
        base = {"1": {a: 50 for a in keys}}
        attrs = {f"anchor_{a}": 50 + int(deltas.get(a, 0)) for a in keys}
        players = [{"_id": "1", "first_name": "A", "last_name": "One", "year": "junior", "attributes": attrs}]
        team = {"fb_efficiency": 0, "fb_opp_modifier": 0, "pt_efficiency": 0, "pt_opp_modifier": 0}
        secs = build_structured_training_report_notes(
            is_training_camp=is_camp, players=players, original_player_baselines=base,
            team=team, plays_data={}, scouting_data={}, legacy_energy_notes=[])
        return {s["title"]: s["body"] for s in secs}

    def test_team_strong_container_flags_high_outlier(self):
        # SC spikes team-wide, all else flat → SC is > mean + 1 SD of the 12 attr-sums.
        by = self._one_player_container_bodies({"SC": 30}, is_camp=True)
        self.assertEqual(by["Strong Cumulative Increase"], "SC")

    def test_camp_concerning_progression_flags_low_laggard(self):
        # 11 attrs +10, SH the laggard at -5 (< mean − 1 SD). Camp flags the least-developed.
        deltas = {a: 10 for a in ["SC", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "FT", "ND", "IQ"]}
        deltas["SH"] = -5
        by = self._one_player_container_bodies(deltas, is_camp=True)
        self.assertEqual(by["Concerning Progression"], "SH")

    def test_inseason_regression_fires_on_negative_not_on_positive_laggard(self):
        # In-season Concerning Regression uses the sum < 0 line: a low-but-positive laggard
        # does NOT count as a regression; a negative one does.
        by_pos = self._one_player_container_bodies({"SC": 30, "SH": 2}, is_camp=False)
        self.assertEqual(by_pos["Concerning Regression"], "No Significant Updates")
        by_neg = self._one_player_container_bodies({"SC": 30, "SH": -8}, is_camp=False)
        self.assertEqual(by_neg["Concerning Regression"], "SH")

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

    # ── Team-attribute containers cap at two ────────────────────────────────────────────

    def test_strong_container_caps_at_two_and_keeps_the_largest(self):
        # Four attrs clear the cut; only the two biggest are named.
        by = self._one_player_container_bodies(
            {"SC": 40, "SH": 35, "ID": 30, "OD": 25}, is_camp=True
        )
        self.assertEqual(by["Strong Cumulative Increase"], "SC, SH")

    def test_camp_concerning_progression_caps_at_two_and_keeps_the_lowest(self):
        deltas = {a: 10 for a in ["SC", "ID", "OD", "PS", "BH", "RB", "ST"]}
        deltas.update({"SH": -20, "AG": -15, "FT": -10, "ND": -5})
        by = self._one_player_container_bodies(deltas, is_camp=True)
        self.assertEqual(by["Concerning Progression"], "AG, SH")

    def test_inseason_regression_caps_at_two(self):
        by = self._one_player_container_bodies(
            {"SC": 40, "SH": -20, "AG": -15, "FT": -10, "ND": -5}, is_camp=False
        )
        self.assertEqual(by["Concerning Regression"], "AG, SH")

    def test_boundary_tie_breaks_randomly_and_does_not_always_pick_the_same_attr(self):
        """Three attrs tied at the cut for two slots: the third name must vary across runs.

        A fixed tie-break would name the same attribute every session for an evenly-developed
        team, reading as a pattern that isn't there.
        """
        from BackEnd.models.training_notes import _pick_standouts

        seen = set()
        for _ in range(60):
            seen.add(tuple(_pick_standouts({"SC": 9, "SH": 9, "ID": 9}, strongest=True)))
        self.assertEqual(len(seen), 3, f"expected all three pairs, got {seen}")
        for pair in seen:
            self.assertEqual(len(pair), 2)

    def test_distinct_sums_draw_nothing_from_the_training_stream(self):
        """No tie at the cutoff => no draws, so the training stream is unperturbed."""
        from BackEnd.models.training_notes import _pick_standouts
        from BackEnd.utils.training_random import training_rng

        before = training_rng.getstate()
        picked = _pick_standouts({"SC": 40, "SH": 30, "ID": 20, "OD": 10}, strongest=True)
        self.assertEqual(picked, ["SC", "SH"])
        self.assertEqual(training_rng.getstate(), before)


if __name__ == "__main__":
    unittest.main()
