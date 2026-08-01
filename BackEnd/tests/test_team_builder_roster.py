import unittest

from BackEnd.utils.team_builder_roster import (
    ROSTER_CSV_HEADERS,
    class_year_for_export,
    parse_import_class_year,
)


class TestTeamBuilderRosterHelpers(unittest.TestCase):
    def test_csv_headers_drop_intangibles(self):
        self.assertEqual(
            ROSTER_CSV_HEADERS[:3],
            ("first_name", "last_name", "class_year"),
        )
        self.assertEqual(
            ROSTER_CSV_HEADERS[-3:],
            ("ND", "IQ", "FT"),
        )
        for banned in ("CH", "EM", "MO"):
            self.assertNotIn(banned, ROSTER_CSV_HEADERS)

    def test_parse_import_class_year(self):
        self.assertEqual(parse_import_class_year("FR"), "Freshman")
        self.assertEqual(parse_import_class_year("so"), "Sophomore")
        self.assertEqual(parse_import_class_year("Junior"), "Junior")
        self.assertIsNone(parse_import_class_year("Freshmen"))
        self.assertIsNone(parse_import_class_year("JH"))
        self.assertIsNone(parse_import_class_year(""))

    def test_class_year_for_export(self):
        self.assertEqual(class_year_for_export("Freshman"), "FR")
        self.assertEqual(class_year_for_export("Senior"), "SR")
        self.assertEqual(class_year_for_export("JH"), "")


if __name__ == "__main__":
    unittest.main()
