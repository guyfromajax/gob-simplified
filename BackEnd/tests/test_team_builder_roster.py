import unittest

from BackEnd.utils.team_builder_roster import (
    class_year_for_export,
    parse_import_class_year,
)


class TestTeamBuilderRosterHelpers(unittest.TestCase):
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
