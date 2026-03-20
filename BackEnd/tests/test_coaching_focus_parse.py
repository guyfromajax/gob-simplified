"""Tests for coaching_focus normalization (Step 1 wiring for training amplifiers)."""

import unittest

from BackEnd.models.training_execution_v2 import parse_coaching_focus


class TestParseCoachingFocus(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
