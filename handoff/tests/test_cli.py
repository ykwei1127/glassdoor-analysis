from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from glassdoor_analysis.cli import build_company_lookup, build_fetcher, determine_exit_code, main, normalize_company_key
from glassdoor_analysis.models import AttemptLogEntry, RunSummary
from glassdoor_analysis.seeds import COMPANY_SEEDS


class FakePipeline:
    def __init__(self, fetcher):  # noqa: ANN001
        self.fetcher = fetcher
        self.run_kwargs = None

    def discover_office_locations(self, **kwargs):  # noqa: ANN003
        return [], []

    def resolve_review_urls(self, **kwargs):  # noqa: ANN003
        return [], []

    def extract_metrics_incremental(self, **kwargs):  # noqa: ANN003
        self.run_kwargs = kwargs
        return [], [], RunSummary(
            company_count=1,
            region_candidate_count=1,
            success_count=1,
            output_record_count=1,
            validation_failure_count=0,
            no_result_count=0,
            error_count=0,
        )


class ErrorPipeline(FakePipeline):
    def extract_metrics_incremental(self, **kwargs):  # noqa: ANN003
        return [], [], RunSummary(
            company_count=1,
            region_candidate_count=1,
            success_count=0,
            output_record_count=0,
            validation_failure_count=0,
            no_result_count=0,
            error_count=2,
        )


class DiscoveryErrorPipeline(FakePipeline):
    def discover_office_locations(self, **kwargs):  # noqa: ANN003
        return [], [
            AttemptLogEntry.create(
                company="ASUS",
                requested_region="",
                candidate_url="https://example.com/office",
                final_url="https://example.com/office",
                status="error",
                failure_reason="location_discovery_failed",
                header_text="",
                observed_region=None,
            )
        ]


class CliTests(unittest.TestCase):
    def test_normalize_company_key_accepts_slug_like_variants(self) -> None:
        self.assertEqual(normalize_company_key("HP Inc."), "hp inc")
        self.assertEqual(normalize_company_key("hp-inc"), "hp inc")

    def test_build_company_lookup_includes_display_and_slug_variants(self) -> None:
        lookup = build_company_lookup(COMPANY_SEEDS)
        self.assertEqual(lookup["hp inc"].display_name, "HP Inc.")
        self.assertEqual(lookup["trend micro"].display_name, "Trend Micro Inc.")
        self.assertEqual(lookup["msi"].display_name, "Micro-Star International")

    def test_all_company_seeds_have_glassdoor_entry_urls(self) -> None:
        self.assertEqual(len(COMPANY_SEEDS), 18)
        self.assertTrue(all(company.glassdoor_entity_hint for company in COMPANY_SEEDS))
        self.assertTrue(all(company.office_locations_url for company in COMPANY_SEEDS))
        self.assertTrue(all(company.review_url_hint for company in COMPANY_SEEDS))

    def test_determine_exit_code_success(self) -> None:
        summary = RunSummary(1, 1, 1, 1, 0, 0, 0)
        self.assertEqual(determine_exit_code(summary), 0)

    def test_determine_exit_code_error(self) -> None:
        summary = RunSummary(1, 1, 0, 0, 0, 0, 1)
        self.assertEqual(determine_exit_code(summary), 1)

    @patch("glassdoor_analysis.cli.UrlFetcher")
    def test_build_fetcher_uses_http_fetcher_by_default(self, mock_url_fetcher) -> None:
        build_fetcher(session_source=None, browser_cdp_url=None)
        mock_url_fetcher.assert_called_once()

    @patch("glassdoor_analysis.cli.BrowserCdpFetcher")
    def test_build_fetcher_uses_browser_fetcher_when_cdp_url_is_provided(self, mock_browser_fetcher) -> None:
        build_fetcher(session_source="ignored.json", browser_cdp_url="http://127.0.0.1:9223")
        mock_browser_fetcher.assert_called_once_with("http://127.0.0.1:9223")

    @patch("glassdoor_analysis.cli.save_region_pool")
    @patch("glassdoor_analysis.cli.write_outputs")
    @patch("glassdoor_analysis.cli.build_fetcher")
    @patch("glassdoor_analysis.cli.ScrapePipeline", FakePipeline)
    def test_main_returns_zero_when_summary_has_no_errors(
        self, mock_build_fetcher, mock_write_outputs, mock_save_region_pool
    ) -> None:
        exit_code = main(["--companies", "hp-inc", "--dry-validate"])
        self.assertEqual(exit_code, 0)
        mock_build_fetcher.assert_called_once()
        mock_write_outputs.assert_called_once()

    @patch("glassdoor_analysis.cli.save_region_pool")
    @patch("glassdoor_analysis.cli.write_outputs")
    @patch("glassdoor_analysis.cli.build_fetcher")
    def test_main_dedupes_repeated_company_variants(
        self, mock_build_fetcher, mock_write_outputs, mock_save_region_pool
    ) -> None:
        pipeline_instances: list[FakePipeline] = []

        def pipeline_factory(fetcher):  # noqa: ANN001
            pipeline = FakePipeline(fetcher)
            pipeline_instances.append(pipeline)
            return pipeline

        with patch("glassdoor_analysis.cli.ScrapePipeline", side_effect=pipeline_factory):
            exit_code = main(["--companies", "HP Inc.", "hp-inc", "hp inc"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(len(pipeline_instances), 1)
        companies = pipeline_instances[0].run_kwargs["companies"]
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0].display_name, "HP Inc.")
        mock_build_fetcher.assert_called_once()
        mock_write_outputs.assert_called_once()

    @patch("glassdoor_analysis.cli.save_region_pool")
    @patch("glassdoor_analysis.cli.write_outputs")
    @patch("glassdoor_analysis.cli.build_fetcher")
    @patch("glassdoor_analysis.cli.ScrapePipeline", ErrorPipeline)
    def test_main_returns_one_when_summary_has_errors(
        self, mock_build_fetcher, mock_write_outputs, mock_save_region_pool
    ) -> None:
        exit_code = main(["--companies", "ASUS"])
        self.assertEqual(exit_code, 1)
        mock_build_fetcher.assert_called_once()
        mock_write_outputs.assert_called_once()

    @patch("glassdoor_analysis.cli.save_region_pool")
    @patch("glassdoor_analysis.cli.write_outputs")
    @patch("glassdoor_analysis.cli.build_fetcher")
    @patch("glassdoor_analysis.cli.ScrapePipeline", DiscoveryErrorPipeline)
    def test_main_counts_discovery_errors_in_exit_code(
        self, mock_build_fetcher, mock_write_outputs, mock_save_region_pool
    ) -> None:
        exit_code = main(["--companies", "ASUS"])
        self.assertEqual(exit_code, 1)
        written_summary = mock_write_outputs.call_args.kwargs["summary"]
        self.assertEqual(written_summary.error_count, 1)
        mock_build_fetcher.assert_called_once()

    def test_main_rejects_invalid_session_source_json(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / "test-cli-invalid-session"
        session_path = temp_dir / "bad-session.json"
        try:
            temp_dir.mkdir(exist_ok=True)
            session_path.write_text("{bad json", encoding="utf-8")
            with self.assertRaises(SystemExit) as exc:
                main(["--session-source", str(session_path)])
            self.assertEqual(exc.exception.code, 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("glassdoor_analysis.cli.write_outputs")
    @patch("glassdoor_analysis.cli.build_fetcher")
    def test_main_rejects_invalid_region_pool_cache_json(self, mock_build_fetcher, mock_write_outputs) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / "test-cli-invalid-cache"
        cache_path = temp_dir / "bad-region-pool.json"
        review_urls_path = temp_dir / "review-urls.json"
        try:
            temp_dir.mkdir(exist_ok=True)
            cache_path.write_text("{bad json", encoding="utf-8")
            review_urls_path.write_text("[]", encoding="utf-8")
            with self.assertRaises(SystemExit) as exc:
                main([
                    "--companies",
                    "ASUS",
                    "--stage",
                    "extract-metrics",
                    "--region-pool-cache",
                    str(cache_path),
                    "--review-urls-cache",
                    str(review_urls_path),
                ])
            self.assertEqual(exc.exception.code, 2)
            mock_write_outputs.assert_not_called()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_main_rejects_unknown_company(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            main(["--companies", "unknown-company"])
        self.assertEqual(exc.exception.code, 2)

    @patch("glassdoor_analysis.cli.build_fetcher")
    def test_backfill_countries_updates_old_aggregate_without_fetching(self, mock_build_fetcher) -> None:
        output_dir = Path(__file__).resolve().parents[1] / "test-country-backfill"
        aggregate_path = output_dir / "reviews_aggregate.json"
        old_record = {
            "company": "ASUS",
            "requested_region": "Taipei",
            "resolved_region": "Taipei",
            "review_url": "https://example.com/reviews",
            "overall": "4.0",
            "recommend": None,
            "ceo_approval": None,
            "total_reviews": "1",
            "diversity_inclusion": None,
            "work_life_balance": None,
            "compensation_benefits": None,
            "culture_values": None,
            "career_opportunities": None,
            "senior_management": None,
            "header_text": "ASUS Taipei reviews",
            "scraped_at": "2026-06-29T00:00:00+00:00",
            "company_input_source": "seed",
            "region_source": "manual-seed",
            "validation_status": "validated",
        }
        try:
            output_dir.mkdir(exist_ok=True)
            aggregate_path.write_text(json.dumps([old_record]), encoding="utf-8")

            exit_code = main(["--stage", "backfill-countries", "--output-dir", str(output_dir)])

            updated = json.loads(aggregate_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(updated[0]["country"], "Taiwan")
            mock_build_fetcher.assert_not_called()
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
