"""Team Builder v2 §5.1 — conference geography map."""
from __future__ import annotations

import unittest

from BackEnd.constants.conference_geography import (
    CONFERENCE_GEOGRAPHY,
    conferences_for_geography,
    distinct_geographies,
)


class TestConferenceGeography(unittest.TestCase):
    def test_distinct_count_is_exactly_56(self):
        geos = distinct_geographies()
        self.assertEqual(len(geos), 56)
        self.assertEqual(len(set(geos)), 56)

    def test_sixteen_conferences(self):
        self.assertEqual(sorted(CONFERENCE_GEOGRAPHY.keys()), list(range(1, 17)))

    def test_texas_and_california_span_two_conferences(self):
        self.assertEqual(conferences_for_geography("Texas"), [11, 12])
        self.assertEqual(conferences_for_geography("California"), [15, 16])

    def test_non_us_entries_present(self):
        geos = set(distinct_geographies())
        for label in (
            "East Canada",
            "Central Canada",
            "West Canada",
            "Europe",
            "Asia",
            "Australia",
        ):
            self.assertIn(label, geos)


if __name__ == "__main__":
    unittest.main()
