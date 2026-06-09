"""Tutorial alert schema defaults."""

import unittest

from BackEnd.utils.user_tracking import default_user_tracking, TUTORIAL_ALERT_IDS


class TutorialAlertsSchemaTests(unittest.TestCase):
    def test_default_user_tracking_includes_tutorial_alert_fields(self):
        tracking = default_user_tracking()
        self.assertIsNone(tracking["tutorial_alerts_franchise_id"])
        self.assertEqual(tracking["tutorial_alerts_dismissed"], [])
        self.assertEqual(tracking["tutorial_alerts_games"], 0)
        self.assertEqual(tracking["tutorial_alerts_training_returns"], 0)

    def test_alert_ids_cover_expected_lessons(self):
        self.assertEqual(
            TUTORIAL_ALERT_IDS,
            (
                "player-attributes",
                "training",
                "team-attributes",
                "game-plans",
                "playbooks",
                "scouting",
                "recruiting",
            ),
        )


if __name__ == "__main__":
    unittest.main()
