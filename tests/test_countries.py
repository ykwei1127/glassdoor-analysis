from __future__ import annotations

import unittest

from glassdoor_analysis.countries import REGION_COUNTRY_MAP, country_for_region_label


class CountryMappingTests(unittest.TestCase):
    def test_mapping_covers_current_region_pool(self) -> None:
        self.assertEqual(len(REGION_COUNTRY_MAP), 136)

    def test_mapping_handles_ambiguous_place_names(self) -> None:
        self.assertEqual(country_for_region_label("Canada, KY"), "United States")
        self.assertEqual(country_for_region_label("India, TX"), "United States")
        self.assertEqual(country_for_region_label("San Jose, MP"), "Costa Rica")

    def test_mapping_handles_manual_and_office_labels(self) -> None:
        self.assertEqual(country_for_region_label("Taipei"), "Taiwan")
        self.assertEqual(country_for_region_label("Taipei, TPQ"), "Taiwan")
        self.assertEqual(country_for_region_label("Global"), "Global")


if __name__ == "__main__":
    unittest.main()
