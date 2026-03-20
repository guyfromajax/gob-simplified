"""Tests for coaching_focus normalization (Step 1 wiring for training amplifiers)."""

import unittest

from BackEnd.models.training_execution_v2 import (
    parse_coaching_focus,
    _scale_install_training_effectiveness_points,
    PLAYER_MAXIMIZER_RANKING_ATTRS,
    normalize_coaching_focus_custom_by_player,
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
        raw = {"p1": ["SC", "SH"], "p2": ["IQ", "FT"]}
        out = normalize_coaching_focus_custom_by_player("player-maximizer-custom", raw, players)
        self.assertEqual(out, {"p1": ["SC", "SH"], "p2": ["IQ", "FT"]})

    def test_normalize_custom_focus_not_custom_ignores_raw(self):
        players = [{"_id": "p1"}]
        self.assertIsNone(
            normalize_coaching_focus_custom_by_player("player-maximizer-top-3", {"p1": ["SC", "SH"]}, players),
        )

    def test_normalize_custom_rejects_duplicate_attrs(self):
        players = [{"_id": "p1"}]
        with self.assertRaises(ValueError):
            normalize_coaching_focus_custom_by_player(
                "player-maximizer-custom", {"p1": ["SC", "SC"]}, players
            )

    def test_normalize_custom_rejects_ch(self):
        players = [{"_id": "p1"}]
        with self.assertRaises(ValueError):
            normalize_coaching_focus_custom_by_player(
                "player-maximizer-custom", {"p1": ["SC", "CH"]}, players
            )


if __name__ == "__main__":
    unittest.main()
