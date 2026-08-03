from __future__ import annotations

import unittest

from glassdoor_analysis.models import CompanySeed, RegionSeed
from glassdoor_analysis.resolver import (
    build_direct_review_url,
    build_direct_review_urls,
    build_pool_gap_review_url,
    extract_pool_location_hint,
    slugify_glassdoor_fragment,
)


class ResolverTests(unittest.TestCase):
    def test_slugify_glassdoor_fragment(self) -> None:
        self.assertEqual(slugify_glassdoor_fragment("HP Inc."), "HP-Inc")
        self.assertEqual(slugify_glassdoor_fragment("New Taipei"), "New-Taipei")

    def test_build_direct_review_url_for_global(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        self.assertEqual(
            build_direct_review_url(company, region),
            "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )

    def test_build_direct_review_url_for_region(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
        )
        region = RegionSeed("New Taipei", "new taipei", "Taiwan", "manual-seed")
        self.assertEqual(
            build_direct_review_url(company, region),
            "https://www.glassdoor.com/Reviews/ASUS-New-Taipei-Reviews-E40093.htm",
        )

    def test_build_direct_review_urls_include_normalized_variant_when_needed(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
        )
        region = RegionSeed("Taipei City", "taipei", "Taiwan", "manual-seed")
        urls = build_direct_review_urls(company, region)
        self.assertEqual(
            urls,
            [
                "https://www.glassdoor.com/Reviews/ASUS-Taipei-City-Reviews-E40093.htm",
                "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm",
            ],
        )

    def test_build_pool_gap_review_url_reuses_location_id(self) -> None:
        company = CompanySeed(
            display_name="Google",
            company_slug_hint="Google",
            glassdoor_entity_hint="E9079",
        )
        office_url = (
            "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-"
            "EI_IE40093.4,8_IL.9,15_IC3271041.htm"
        )

        location = extract_pool_location_hint(office_url)
        review_url = build_pool_gap_review_url(company, office_url)

        self.assertEqual(location.region_slug, "Taipei")
        self.assertEqual(location.location_id, "3271041")
        self.assertEqual(
            review_url,
            "https://www.glassdoor.com/Reviews/Google-Taipei-Reviews-"
            "EI_IE9079.0,6_IL.7,13_IC3271041.htm",
        )


if __name__ == "__main__":
    unittest.main()
