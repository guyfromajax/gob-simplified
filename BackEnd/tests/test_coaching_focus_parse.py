"""Tests for coaching_focus normalization (Step 1 wiring for training amplifiers)."""

import unittest

from BackEnd.models.training_execution_v2 import (
    parse_coaching_focus,
    _scale_install_training_effectiveness_points,
    PLAYER_MAXIMIZER_RANKING_ATTRS,
    normalize_coaching_focus_custom_by_player,
    _should_amplify_player_attr,
    coaching_focus_leaf_display_name,
)


class TestParseCoachingFocus(unittest.TestCase):
    def test_player_maximizer_ranking_excludes_ch(self):
        self.assertNotIn("CH", PLAYER_MAXIMIZER_RANKING_ATTRS)

    def test_empty(self):
        self.assertEqual(parse_coaching_focus(None), (None, None))
        self.assertEqual(parse_coaching_focus(""), (None, None))
        self.assertEqual(parse_coaching_focus("   "), (None, None))

    def test_archetype_only(self):
        self.assertEqual(parse_coaching_focus("authoritarian"), ("authoritarian", None))
        self.assertEqual(parse_coaching_focus("systems-coach"), ("systems-coach", None))

    def test_authoritarian_leaf(self):
        self.assertEqual(
            parse_coaching_focus("authoritarian-discipline"),
            ("authoritarian", "authoritarian-discipline"),
        )
        self.assertEqual(
            parse_coaching_focus("authoritarian-rebounding"),
            ("authoritarian", "authoritarian-rebounding"),
        )

    def test_systems_coach_leaf(self):
        self.assertEqual(
            parse_coaching_focus("systems-coach-offense"),
            ("systems-coach", "systems-coach-offense"),
        )
        self.assertEqual(
            parse_coaching_focus("systems-coach-press-trap"),
            ("systems-coach", "systems-coach-press-trap"),
        )

    def test_player_maximizer_leaf(self):
        self.assertEqual(
            parse_coaching_focus("player-maximizer-top-3"),
            ("player-maximizer", "player-maximizer-top-3"),
        )
        self.assertEqual(
            parse_coaching_focus("player-maximizer-positional-focus"),
            ("player-maximizer", "player-maximizer-positional-focus"),
        )
        self.assertEqual(
            parse_coaching_focus("player-maximizer-choose-attributes"),
            ("player-maximizer", "player-maximizer-choose-attributes"),
        )

    def test_culture_builder_leaf(self):
        self.assertEqual(
            parse_coaching_focus("culture-builder-inspire"),
            ("culture-builder", "culture-builder-inspire"),
        )

    def test_scale_install_training_effectiveness_points(self):
        self.assertEqual(
            _scale_install_training_effectiveness_points(10, 1.5, True),
            15,
        )
        self.assertEqual(
            _scale_install_training_effectiveness_points(10, 1.5, False),
            10,
        )
        self.assertEqual(
            _scale_install_training_effectiveness_points(10, None, True),
            10,
        )
        self.assertEqual(
            _scale_install_training_effectiveness_points(0, 1.8, True),
            0,
        )

    def test_normalize_custom_focus_ok(self):
        players = [
            {"_id": "p1"},
            {"_id": "p2"},
        ]
        raw = {"p1": ["SC", "SH", "ID"], "p2": ["IQ", "FT", "RB"]}
        out = normalize_coaching_focus_custom_by_player("player-maximizer-custom", raw, players)
        self.assertEqual(out, {"p1": ["SC", "SH", "ID"], "p2": ["IQ", "FT", "RB"]})

    def test_normalize_custom_focus_not_custom_ignores_raw(self):
        players = [{"_id": "p1"}]
        self.assertIsNone(
            normalize_coaching_focus_custom_by_player("player-maximizer-top-3", {"p1": ["SC", "SH", "ID"]}, players),
        )

    def test_normalize_custom_rejects_duplicate_attrs(self):
        players = [{"_id": "p1"}]
        with self.assertRaises(ValueError):
            normalize_coaching_focus_custom_by_player(
                "player-maximizer-custom", {"p1": ["SC", "SH", "SC"]}, players
            )

    def test_normalize_custom_rejects_two_attrs(self):
        players = [{"_id": "p1"}]
        with self.assertRaises(ValueError):
            normalize_coaching_focus_custom_by_player(
                "player-maximizer-custom", {"p1": ["SC", "SH"]}, players
            )

    def test_normalize_custom_rejects_ch(self):
        players = [{"_id": "p1"}]
        with self.assertRaises(ValueError):
            normalize_coaching_focus_custom_by_player(
                "player-maximizer-custom", {"p1": ["SC", "SH", "CH"]}, players
            )

    def test_inspire_does_not_amplify_player_drill_attrs_team_ch_separate(self):
        sub = "culture-builder-inspire"
        self.assertFalse(_should_amplify_player_attr("CH", "culture-builder", sub))
        self.assertFalse(_should_amplify_player_attr("FT", "culture-builder", sub))

    def test_confidence_amplifies_ch_and_ft(self):
        sub = "culture-builder-confidence"
        self.assertTrue(_should_amplify_player_attr("CH", "culture-builder", sub))
        self.assertTrue(_should_amplify_player_attr("FT", "culture-builder", sub))
        self.assertFalse(_should_amplify_player_attr("EM", "culture-builder", sub))

    def test_team_building_no_player_drill_amplify(self):
        sub = "culture-builder-teamwork"
        self.assertFalse(_should_amplify_player_attr("PS", "culture-builder", sub))

    def test_leaf_display_names_teamwork_vs_team_building(self):
        self.assertEqual(
            coaching_focus_leaf_display_name("authoritarian-teamwork"), "Teamwork"
        )
        self.assertEqual(
            coaching_focus_leaf_display_name("culture-builder-teamwork"), "Team Building"
        )
        self.assertIsNone(coaching_focus_leaf_display_name("culture-builder-inspire"))

    def test_positional_focus_leaf_display_name(self):
        self.assertEqual(
            coaching_focus_leaf_display_name("player-maximizer-positional-focus"),
            "Positional Focus",
        )


if __name__ == "__main__":
    unittest.main()
