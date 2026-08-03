from __future__ import annotations

import json
from pathlib import Path
import unittest

from glassdoor_analysis.parsers import (
    extract_header_text,
    extract_metrics,
    extract_office_location_links,
    extract_office_locations,
    extract_office_review_links,
)


FIXTURES = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_extract_office_locations(self) -> None:
        html = (FIXTURES / "office_locations_asus.html").read_text(encoding="utf-8")
        self.assertEqual(extract_office_locations(html), ["Taipei", "Shanghai", "Austin"])

    def test_extract_metrics(self) -> None:
        html = (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8")
        metrics = extract_metrics(html)
        self.assertEqual(metrics.overall, "4.1")
        self.assertEqual(metrics.recommend, "82%")
        self.assertEqual(metrics.missing_fields, [])

    def test_extract_header_text(self) -> None:
        html = (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8")
        self.assertEqual(extract_header_text(html), "ASUS reviews")

    def test_extract_metrics_reports_missing_field_reasons(self) -> None:
        html = (FIXTURES / "review_asus_missing_metrics.html").read_text(encoding="utf-8")
        metrics = extract_metrics(html)
        self.assertIn("overall", metrics.missing_fields)
        self.assertEqual(metrics.missing_field_reasons["overall"], "page_missing")

    def test_extract_metrics_reports_selector_failure_reason(self) -> None:
        html = (FIXTURES / "review_asus_selector_failure.html").read_text(encoding="utf-8")
        metrics = extract_metrics(html)
        self.assertIn("overall", metrics.missing_fields)
        self.assertEqual(metrics.missing_field_reasons["overall"], "selector_failure")

    def test_extract_metrics_supports_live_like_review_markup(self) -> None:
        html = (FIXTURES / "review_asus_live_like.html").read_text(encoding="utf-8")
        metrics = extract_metrics(html)
        self.assertEqual(metrics.overall, "3.6")
        self.assertEqual(metrics.recommend, "58%")
        self.assertEqual(metrics.ceo_approval, "75%")
        self.assertEqual(metrics.total_reviews, "1,501")

    def test_extract_metrics_rejects_non_numeric_rating_payload(self) -> None:
        html = """
            <script id="__NEXT_DATA__" type="application/json">
              {"props":{"workLifeBalanceRating":"and just use all the benefits"}}
            </script>
        """

        metrics = extract_metrics(html)

        self.assertIsNone(metrics.work_life_balance)
        self.assertIn("work_life_balance", metrics.missing_fields)
        self.assertEqual(metrics.missing_field_reasons["work_life_balance"], "invalid_value")

    def test_extract_metrics_supports_next_flight_location_ratings(self) -> None:
        flight_payload = (
            '12:{"filteredReviewsCount":148,"ratings":{"careerOpportunitiesRating":4.1,"ceoRating":0.82,'
            '"compensationAndBenefitsRating":4.6,"cultureAndValuesRating":4.3,'
            '"diversityAndInclusionRating":4.6,"overallRating":4.4,'
            '"ratedCeo":{"name":"Example CEO"},"recommendToFriendRating":0.94,'
            '"reviewCount":148,"seniorManagementRating":3.9,"workLifeBalanceRating":4.3},'
            '"reviews":[]}'
        )
        html = f"<script>self.__next_f.push({json.dumps([1, flight_payload])})</script>"

        metrics = extract_metrics(html)

        self.assertEqual(metrics.overall, "4.4")
        self.assertEqual(metrics.recommend, "94%")
        self.assertEqual(metrics.ceo_approval, "82%")
        self.assertEqual(metrics.total_reviews, "148")
        self.assertEqual(metrics.diversity_inclusion, "4.6")
        self.assertEqual(metrics.work_life_balance, "4.3")
        self.assertEqual(metrics.compensation_benefits, "4.6")
        self.assertEqual(metrics.culture_values, "4.3")
        self.assertEqual(metrics.career_opportunities, "4.1")
        self.assertEqual(metrics.senior_management, "3.9")

    def test_extract_metrics_prefers_filtered_location_review_count(self) -> None:
        flight_payload = (
            '12:{"filteredReviewsCount":5,"ratings":{"overallRating":2.4,'
            '"reviewCount":8},"reviews":[]}'
        )
        html = f"<script>self.__next_f.push({json.dumps([1, flight_payload])})</script>"

        metrics = extract_metrics(html)

        self.assertEqual(metrics.overall, "2.4")
        self.assertEqual(metrics.total_reviews, "5")

    def test_extract_metrics_supports_ratings_by_category_markup(self) -> None:
        html = """
            <div class="RatingsByCategory_ratingItem__4EMZd">
              <p class="RatingsByCategory_rating__T0v8N">2.4</p>
              <p class="RatingsByCategory_ratingLabel__o3Me9">Work/Life balance</p>
            </div>
            <div class="RatingsByCategory_ratingItem__4EMZd">
              <p class="RatingsByCategory_rating__T0v8N">1.5</p>
              <p class="RatingsByCategory_ratingLabel__o3Me9">Compensation and benefits</p>
            </div>
        """

        metrics = extract_metrics(html)

        self.assertEqual(metrics.work_life_balance, "2.4")
        self.assertEqual(metrics.compensation_benefits, "1.5")

    def test_extract_office_locations_supports_live_like_location_rows(self) -> None:
        html = (FIXTURES / "office_locations_live_like.html").read_text(encoding="utf-8")
        self.assertEqual(extract_office_locations(html), ["Ciudad de Mexico, MEX", "Fremont, CA"])

    def test_extract_office_location_links(self) -> None:
        html = (FIXTURES / "office_locations_navigation_live_like.html").read_text(encoding="utf-8")
        links = extract_office_location_links(html, "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm")
        self.assertEqual(links[0].label, "Fremont, CA")
        self.assertEqual(
            links[0].url,
            "https://www.glassdoor.com/Location/All-ASUS-Fremont-Office-Locations-EI_IE40093.4,8_IL.9,16_IC1147355.htm",
        )

    def test_extract_office_review_links(self) -> None:
        html = (FIXTURES / "office_fremont_detail_live_like.html").read_text(encoding="utf-8")
        links = extract_office_review_links(
            html,
            "https://www.glassdoor.com/Location/All-ASUS-Fremont-Office-Locations-EI_IE40093.4,8_IL.9,16_IC1147355.htm",
        )
        self.assertEqual(
            links,
            ["https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-EI_IE40093.0,4_IL.5,12_IC1147355.htm"],
        )


if __name__ == "__main__":
    unittest.main()
