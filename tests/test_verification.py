from __future__ import annotations

import unittest

from glassdoor_analysis.models import ReviewMetrics
from glassdoor_analysis.normalization import normalize_region_label, region_matches
from glassdoor_analysis.verification import infer_region_from_header, validate_review_page


class VerificationTests(unittest.TestCase):
    def test_region_normalization(self) -> None:
        self.assertEqual(normalize_region_label("Taipei City"), "taipei")

    def test_infer_global_region(self) -> None:
        self.assertEqual(infer_region_from_header("ASUS", "ASUS reviews"), "Global")

    def test_region_matches_city_with_city_and_state_code(self) -> None:
        self.assertTrue(region_matches("Fremont, CA", "Fremont"))

    def test_validate_region_mismatch(self) -> None:
        metrics = ReviewMetrics(overall="4.0")
        validation = validate_review_page(
            company_name="ASUS",
            requested_region="Taipei",
            header_text="ASUS Shanghai reviews",
            metrics=metrics,
        )
        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.failure_reason, "region_mismatch")

    def test_validate_missing_metrics(self) -> None:
        validation = validate_review_page(
            company_name="ASUS",
            requested_region="Taipei",
            header_text="ASUS Taipei reviews",
            metrics=ReviewMetrics(),
        )
        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.failure_reason, "missing_target_metrics")


if __name__ == "__main__":
    unittest.main()
