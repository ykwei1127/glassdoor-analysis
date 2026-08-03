from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

from glassdoor_analysis.models import CompanySeed, OfficeLocationRecord, RegionSeed, ReviewUrlRecord
from glassdoor_analysis.pipeline import (
    ScrapePipeline,
    build_region_pool_from_inventory,
    detect_access_issue,
    load_office_locations,
    load_region_pool,
    load_review_url_manifest,
    write_outputs,
)
from glassdoor_analysis.seeds import manual_region_seeds


FIXTURES = Path(__file__).parent / "fixtures"


@contextmanager
def workspace_temp_dir(name: str):  # noqa: ANN201
    path = Path(__file__).resolve().parents[1] / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class StubFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str):  # noqa: ANN001
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"missing fixture for {url}")

        class Response:
            def __init__(self, page_url: str, text: str) -> None:
                self.url = page_url
                self.text = text

        return Response(url, self.pages[url])


class PipelineTests(unittest.TestCase):
    def test_detect_access_issue_ignores_normal_page_recaptcha_config(self) -> None:
        html = '<script>window.GD.page={"recaptcha":{"publicKeyForUserAuth":"abc"}};</script>'
        self.assertIsNone(detect_access_issue(html))

    def test_detect_access_issue_flags_explicit_captcha_challenge(self) -> None:
        html = "<html><body>Please complete the CAPTCHA challenge to continue.</body></html>"
        self.assertEqual(detect_access_issue(html), "access_restricted: captcha_detected")

    def test_detect_access_issue_flags_glassdoor_rate_limit_page(self) -> None:
        html = """
            <h1>Help Us Protect Glassdoor</h1>
            <p>We've noticed an unusually high number of requests from your connection.</p>
        """
        self.assertEqual(detect_access_issue(html), "access_restricted: rate_limited")

    def test_detect_access_issue_ignores_localization_bundle_login_strings(self) -> None:
        html = '<script>{"communitycommonui.identity.signin.comment":"Please sign in to comment","resumeupload.youmustbeloggedin":"You must be logged in to upload resume"}</script>'
        self.assertIsNone(detect_access_issue(html))

    def test_rebuild_region_pool_merges_office_locations(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            office_locations_url="https://example.com/office",
        )
        pipeline = ScrapePipeline(StubFetcher({
            "https://example.com/office": (FIXTURES / "office_locations_asus.html").read_text(encoding="utf-8"),
        }))

        regions, attempts = pipeline.build_region_pool(
            companies=[company],
            manual_regions=manual_region_seeds(),
            rebuild_region_pool=True,
        )

        normalized = {region.normalized_label for region in regions}
        self.assertIn("taipei", normalized)
        self.assertIn("shanghai", normalized)
        self.assertEqual(attempts, [])

    def test_region_pool_cache_is_written_and_reused(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            office_locations_url="https://example.com/office",
        )
        pipeline = ScrapePipeline(StubFetcher({
            "https://example.com/office": (FIXTURES / "office_locations_asus.html").read_text(encoding="utf-8"),
        }))
        cache_path = Path(__file__).resolve().parents[1] / "test-region-pool.json"
        try:
            regions, _ = pipeline.build_region_pool(
                companies=[company],
                manual_regions=manual_region_seeds(),
                rebuild_region_pool=True,
                cache_path=cache_path,
            )
            self.assertTrue(cache_path.exists())
            cached_regions = load_region_pool(cache_path)
            self.assertEqual(
                {region.normalized_label for region in regions},
                {region.normalized_label for region in cached_regions},
            )
        finally:
            cache_path.unlink(missing_ok=True)

    def test_cached_region_pool_still_merges_manual_seeds(self) -> None:
        cache_path = Path(__file__).resolve().parents[1] / "test-region-pool.json"
        try:
            cache_path.write_text(
                '[{"raw_label":"Osaka","normalized_label":"osaka","country_or_macro_hint":"APAC","source":"office-location"}]',
                encoding="utf-8",
            )
            pipeline = ScrapePipeline(StubFetcher({}))
            regions, attempts = pipeline.build_region_pool(
                companies=[],
                manual_regions=manual_region_seeds(),
                rebuild_region_pool=False,
                cache_path=cache_path,
            )
            normalized = {region.normalized_label for region in regions}
            self.assertIn("osaka", normalized)
            self.assertIn("global", normalized)
            self.assertIn("taipei", normalized)
            self.assertEqual(attempts, [])
        finally:
            cache_path.unlink(missing_ok=True)

    def test_discover_office_locations_persists_company_specific_inventory(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
        )
        fetcher = StubFetcher({
            company.office_locations_url: (FIXTURES / "office_locations_navigation_live_like.html").read_text(
                encoding="utf-8"
            ),
        })
        cache_path = Path(__file__).resolve().parents[1] / "test-office-locations.json"
        try:
            records, attempts = ScrapePipeline(fetcher).discover_office_locations(
                companies=[company],
                rebuild=True,
                cache_path=cache_path,
            )

            self.assertEqual(attempts, [])
            self.assertTrue(any(record.normalized_label == "fremont ca" for record in records))
            self.assertEqual(load_office_locations(cache_path), records)
            self.assertTrue(cache_path.with_suffix(".csv").exists())
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_suffix(".csv").unlink(missing_ok=True)

    def test_discover_office_locations_treats_valid_empty_page_as_no_result(self) -> None:
        company = CompanySeed(
            display_name="Google",
            office_locations_url="https://www.glassdoor.com/Location/All-Google-Office-Locations-E9079.htm",
        )
        fetcher = StubFetcher({
            company.office_locations_url: "<html><title>All Google Office Locations | Glassdoor</title></html>",
        })
        cache_path = Path(__file__).resolve().parents[1] / "test-empty-office-locations.json"
        try:
            records, attempts = ScrapePipeline(fetcher).discover_office_locations(
                companies=[company],
                rebuild=True,
                cache_path=cache_path,
            )

            self.assertEqual(records, [])
            self.assertEqual(attempts[0].status, "no_result")
            self.assertEqual(attempts[0].failure_reason, "office_locations_empty")
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_suffix(".csv").unlink(missing_ok=True)

    def test_region_pool_is_union_of_company_inventory_and_manual_seeds(self) -> None:
        inventory = [
            OfficeLocationRecord.create(
                company="ASUS",
                raw_label="Fremont, CA",
                normalized_label="fremont ca",
                office_url="https://example.com/fremont",
            ),
            OfficeLocationRecord.create(
                company="NVIDIA",
                raw_label="Yokneam",
                normalized_label="yokneam",
                office_url="https://example.com/yokneam",
            ),
        ]

        regions = build_region_pool_from_inventory(inventory, manual_region_seeds())

        normalized = {region.normalized_label for region in regions}
        self.assertIn("fremont ca", normalized)
        self.assertIn("yokneam", normalized)
        self.assertIn("global", normalized)

    def test_resolve_review_urls_persists_and_reuses_manifest(self) -> None:
        company = CompanySeed(display_name="ASUS", office_locations_url="https://example.com/asus-offices")
        region = RegionSeed("Fremont", "fremont", "Americas", "manual-seed")
        office = OfficeLocationRecord.create(
            company="ASUS",
            raw_label="Fremont, CA",
            normalized_label="fremont ca",
            office_url="https://www.glassdoor.com/Location/ASUS-Fremont-Office-Locations.htm",
        )
        review_url = "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-EI_IE40093.0,4_IL.5,12_IC1147355.htm"
        fetcher = StubFetcher({
            office.office_url: (FIXTURES / "office_fremont_detail_live_like.html").read_text(encoding="utf-8"),
        })
        cache_path = Path(__file__).resolve().parents[1] / "test-review-urls.json"
        try:
            manifest, attempts = ScrapePipeline(fetcher).resolve_review_urls(
                companies=[company],
                regions=[region],
                office_locations=[office],
                rebuild=True,
                cache_path=cache_path,
            )

            self.assertEqual(attempts, [])
            self.assertEqual(manifest[0].review_url, review_url)
            self.assertEqual(manifest[0].status, "resolved")
            self.assertEqual(load_review_url_manifest(cache_path), manifest)

            cached, cached_attempts = ScrapePipeline(StubFetcher({})).resolve_review_urls(
                companies=[company],
                regions=[region],
                office_locations=[office],
                rebuild=False,
                cache_path=cache_path,
            )
            self.assertEqual(cached, manifest)
            self.assertEqual(cached_attempts, [])
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_suffix(".csv").unlink(missing_ok=True)

    def test_extract_stage_fetches_only_resolved_review_url(self) -> None:
        company = CompanySeed(display_name="ASUS")
        region = RegionSeed("Fremont", "fremont", "Americas", "manual-seed")
        review_url = "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-E40093.htm"
        target = ReviewUrlRecord.create(
            company="ASUS",
            requested_region="Fremont",
            normalized_region="fremont",
            region_source="manual-seed",
            office_label="Fremont, CA",
            office_url="https://example.com/fremont-office",
            review_url=review_url,
            status="resolved",
            discovery_mode="office-navigation",
        )
        fetcher = StubFetcher({
            review_url: (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8").replace(
                "ASUS Taipei reviews", "ASUS Fremont reviews"
            ),
        })

        records, _, summary = ScrapePipeline(fetcher).run_from_review_urls(
            companies=[company],
            regions=[region],
            review_urls=[target],
            dry_validate=False,
        )

        self.assertEqual(fetcher.calls, [review_url])
        self.assertEqual(len(records), 1)
        self.assertEqual(summary.success_count, 1)

    def test_incremental_extraction_checkpoints_and_resumes(self) -> None:
        company = CompanySeed(display_name="ASUS")
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        review_url = "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm"
        target = ReviewUrlRecord.create(
            company="ASUS",
            requested_region="Taipei",
            normalized_region="taipei",
            region_source="manual-seed",
            office_label="Taipei",
            office_url="https://example.com/taipei-office",
            review_url=review_url,
            status="resolved",
            discovery_mode="office-navigation",
        )
        page = (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8")

        with workspace_temp_dir("test-incremental-extraction") as output_dir:
            messages: list[str] = []
            fetcher = StubFetcher({review_url: page})
            records, attempts, summary = ScrapePipeline(fetcher).extract_metrics_incremental(
                companies=[company],
                regions=[region],
                review_urls=[target],
                checkpoint_dir=output_dir,
                dry_validate=False,
                progress_every=1,
                status_callback=messages.append,
            )

            self.assertEqual(fetcher.calls, [review_url])
            self.assertEqual(len(records), 1)
            self.assertEqual(attempts[-1].status, "success")
            self.assertEqual(summary.success_count, 1)
            self.assertTrue((output_dir / "reviews_aggregate.json").exists())
            self.assertTrue((output_dir / "reviews_aggregate.csv").exists())
            self.assertTrue((output_dir / "metrics_attempt_log.json").exists())
            self.assertTrue((output_dir / "metrics_attempt_log.csv").exists())
            self.assertTrue(any("Extraction progress: 1/1" in message for message in messages))

            resume_fetcher = StubFetcher({})
            resumed_records, _, resumed_summary = ScrapePipeline(resume_fetcher).extract_metrics_incremental(
                companies=[company],
                regions=[region],
                review_urls=[target],
                checkpoint_dir=output_dir,
                dry_validate=False,
                status_callback=messages.append,
            )

            self.assertEqual(resume_fetcher.calls, [])
            self.assertEqual(len(resumed_records), 1)
            self.assertEqual(resumed_summary.success_count, 1)

            refresh_fetcher = StubFetcher({review_url: page})
            refreshed_records, _, refreshed_summary = ScrapePipeline(
                refresh_fetcher
            ).extract_metrics_incremental(
                companies=[company],
                regions=[region],
                review_urls=[target],
                checkpoint_dir=output_dir,
                dry_validate=False,
                refresh_existing=True,
            )

            self.assertEqual(refresh_fetcher.calls, [review_url])
            self.assertEqual(len(refreshed_records), 1)
            self.assertEqual(refreshed_summary.success_count, 1)

    def test_incremental_extraction_stops_on_rate_limit(self) -> None:
        company = CompanySeed(display_name="ASUS")
        regions = [
            RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed"),
            RegionSeed("Fremont", "fremont", "Americas", "manual-seed"),
        ]
        urls = [
            "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm",
            "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-E40093.htm",
        ]
        targets = [
            ReviewUrlRecord.create(
                company="ASUS",
                requested_region=region.raw_label,
                normalized_region=region.normalized_label,
                region_source=region.source,
                office_label=region.raw_label,
                office_url=f"https://example.com/{region.normalized_label}",
                review_url=url,
                status="resolved",
                discovery_mode="office-navigation",
            )
            for region, url in zip(regions, urls, strict=True)
        ]
        rate_limit_page = "<h1>Help Us Protect Glassdoor</h1><p>temporarily limited your access</p>"

        with workspace_temp_dir("test-extraction-rate-limit") as output_dir:
            messages: list[str] = []
            fetcher = StubFetcher({urls[0]: rate_limit_page})
            records, attempts, summary = ScrapePipeline(fetcher).extract_metrics_incremental(
                companies=[company],
                regions=regions,
                review_urls=targets,
                checkpoint_dir=output_dir,
                dry_validate=False,
                status_callback=messages.append,
            )

            self.assertEqual(fetcher.calls, [urls[0]])
            self.assertEqual(records, [])
            self.assertEqual(attempts[-1].status, "error")
            self.assertIn("rate_limited", attempts[-1].failure_reason)
            self.assertEqual(summary.error_count, 1)
            self.assertTrue(any("current URL remains retryable" in message for message in messages))

    @patch("glassdoor_analysis.pipeline.random.uniform", return_value=0.5)
    @patch("glassdoor_analysis.pipeline.time.sleep")
    def test_incremental_extraction_applies_delay_and_periodic_cooldown(
        self, mock_sleep, _mock_uniform
    ) -> None:
        company = CompanySeed(display_name="ASUS")
        regions = [
            RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed"),
            RegionSeed("Fremont", "fremont", "Americas", "manual-seed"),
        ]
        urls = ["https://example.com/taipei", "https://example.com/fremont"]
        base_page = (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8")
        pages = {
            urls[0]: base_page,
            urls[1]: base_page.replace("ASUS Taipei reviews", "ASUS Fremont reviews"),
        }
        targets = [
            ReviewUrlRecord.create(
                company="ASUS",
                requested_region=region.raw_label,
                normalized_region=region.normalized_label,
                region_source=region.source,
                office_label=region.raw_label,
                office_url=f"https://example.com/{region.normalized_label}-office",
                review_url=url,
                status="resolved",
                discovery_mode="office-navigation",
            )
            for region, url in zip(regions, urls, strict=True)
        ]

        with workspace_temp_dir("test-extraction-throttle") as output_dir:
            ScrapePipeline(StubFetcher(pages)).extract_metrics_incremental(
                companies=[company],
                regions=regions,
                review_urls=targets,
                checkpoint_dir=output_dir,
                dry_validate=False,
                request_delay_seconds=2,
                request_jitter_seconds=1,
                cooldown_every=1,
                cooldown_seconds=10,
            )

        self.assertEqual([call.args[0] for call in mock_sleep.call_args_list], [2.5, 10, 2.5])

    def test_pool_gap_probe_resolves_company_using_another_company_location_id(self) -> None:
        company = CompanySeed(
            display_name="Google",
            company_slug_hint="Google",
            glassdoor_entity_hint="E9079",
        )
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        office = OfficeLocationRecord.create(
            company="ASUS",
            raw_label="Taipei, TPQ",
            normalized_label="taipei tpq",
            office_url=(
                "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-"
                "EI_IE40093.4,8_IL.9,15_IC3271041.htm"
            ),
        )
        candidate_url = (
            "https://www.glassdoor.com/Reviews/Google-Taipei-Reviews-"
            "EI_IE9079.0,6_IL.7,13_IC3271041.htm"
        )
        target = ReviewUrlRecord.create(
            company="Google",
            requested_region="Taipei",
            normalized_region="taipei",
            region_source="manual-seed",
            office_label=None,
            office_url=None,
            review_url=None,
            status="no_result",
            failure_reason="office_location_not_found",
            discovery_mode="office-navigation",
        )
        review_html = (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8").replace(
            "ASUS Taipei reviews", "Google Taipei reviews"
        )
        cache_path = Path(__file__).resolve().parents[1] / "test-gap-review-urls.json"
        try:
            manifest, attempts = ScrapePipeline(StubFetcher({candidate_url: review_html})).probe_review_url_gaps(
                companies=[company],
                regions=[region],
                office_locations=[office],
                review_urls=[target],
                cache_path=cache_path,
            )

            self.assertEqual(manifest[0].status, "resolved")
            self.assertEqual(manifest[0].review_url, candidate_url)
            self.assertEqual(manifest[0].discovery_mode, "pool-location-id")
            self.assertEqual(attempts[0].status, "success")
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_suffix(".csv").unlink(missing_ok=True)

    def test_pool_gap_probe_stops_on_rate_limit_and_keeps_record_retryable(self) -> None:
        company = CompanySeed(display_name="Google", company_slug_hint="Google", glassdoor_entity_hint="E9079")
        taipei = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        fremont = RegionSeed("Fremont", "fremont", "Americas", "manual-seed")
        offices = [
            OfficeLocationRecord.create(
                company="ASUS",
                raw_label="Taipei, TPQ",
                normalized_label="taipei tpq",
                office_url=(
                    "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-"
                    "EI_IE40093.4,8_IL.9,15_IC3271041.htm"
                ),
            ),
            OfficeLocationRecord.create(
                company="ASUS",
                raw_label="Fremont, CA",
                normalized_label="fremont ca",
                office_url=(
                    "https://www.glassdoor.com/Location/All-ASUS-Fremont-Office-Locations-"
                    "EI_IE40093.4,8_IL.9,16_IC1147355.htm"
                ),
            ),
        ]
        targets = [
            ReviewUrlRecord.create(
                company="Google",
                requested_region=region.raw_label,
                normalized_region=region.normalized_label,
                region_source="manual-seed",
                office_label=None,
                office_url=None,
                review_url=None,
                status="no_result",
                failure_reason="office_location_not_found",
                discovery_mode="office-navigation",
            )
            for region in (taipei, fremont)
        ]
        taipei_candidate = (
            "https://www.glassdoor.com/Reviews/Google-Taipei-Reviews-"
            "EI_IE9079.0,6_IL.7,13_IC3271041.htm"
        )
        fetcher = StubFetcher({
            taipei_candidate: "<h1>Help Us Protect Glassdoor</h1><p>temporarily limited your access</p>",
        })
        cache_path = Path(__file__).resolve().parents[1] / "test-rate-limit-review-urls.json"
        try:
            manifest, attempts = ScrapePipeline(fetcher).probe_review_url_gaps(
                companies=[company],
                regions=[taipei, fremont],
                office_locations=offices,
                review_urls=targets,
                cache_path=cache_path,
            )

            self.assertEqual(fetcher.calls, [taipei_candidate])
            self.assertEqual(attempts[0].status, "error")
            self.assertIn("rate_limited", attempts[0].failure_reason)
            self.assertEqual(manifest[0].status, "no_result")
            self.assertEqual(manifest[0].discovery_mode, "office-navigation")
            self.assertEqual(manifest[1].discovery_mode, "office-navigation")
        finally:
            cache_path.unlink(missing_ok=True)
            cache_path.with_suffix(".csv").unlink(missing_ok=True)

    def test_pipeline_accepts_global_and_region_pages(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
            office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
        )
        global_region = RegionSeed("Global", "global", "Global", "manual-seed")
        taipei_region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        pages = {
            "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8"),
            "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": (
                FIXTURES / "office_locations_navigation_live_like.html"
            ).read_text(encoding="utf-8"),
            "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-EI_IE40093.4,8_IL.9,15_IC3271041.htm": """
                <html><body>
                <a class=\"LocationReview_headerLink__heQ0m\" href=\"/Reviews/ASUS-Taipei-Reviews-E40093.htm\">
                <span class=\"SectionHeader_tag__iAKuU\">79 reviews in Taipei</span>
                </a>
                </body></html>
            """,
            "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm": (FIXTURES / "review_asus_taipei.html").read_text(encoding="utf-8"),
        }
        pipeline = ScrapePipeline(StubFetcher(pages))

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[global_region, taipei_region],
            dry_validate=False,
        )

        self.assertEqual(len(records), 2)
        self.assertEqual(summary.success_count, 2)
        self.assertEqual(summary.output_record_count, 2)
        self.assertEqual(attempts[0].status, "success")

    def test_pipeline_uses_global_review_hint_for_global_region(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        pages = {
            "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8"),
        }
        pipeline = ScrapePipeline(StubFetcher(pages))

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(attempts[0].final_url, "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm")

    def test_pipeline_prefers_office_navigation_path_for_region_reviews(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
            office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
        )
        region = RegionSeed("Fremont", "fremont", "United States", "manual-seed")
        fetcher = StubFetcher({
            "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": (
                FIXTURES / "office_locations_navigation_live_like.html"
            ).read_text(encoding="utf-8"),
            "https://www.glassdoor.com/Location/All-ASUS-Fremont-Office-Locations-EI_IE40093.4,8_IL.9,16_IC1147355.htm": (
                FIXTURES / "office_fremont_detail_live_like.html"
            ).read_text(encoding="utf-8"),
            "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-EI_IE40093.0,4_IL.5,12_IC1147355.htm": (
                FIXTURES / "review_asus_taipei.html"
            ).read_text(encoding="utf-8").replace("ASUS Taipei reviews", "ASUS Fremont reviews"),
        })
        pipeline = ScrapePipeline(fetcher)

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(
            fetcher.calls,
            [
                "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
                "https://www.glassdoor.com/Location/All-ASUS-Fremont-Office-Locations-EI_IE40093.4,8_IL.9,16_IC1147355.htm",
                "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-EI_IE40093.0,4_IL.5,12_IC1147355.htm",
            ],
        )
        self.assertEqual(attempts[0].final_url, "https://www.glassdoor.com/Reviews/ASUS-Fremont-Reviews-EI_IE40093.0,4_IL.5,12_IC1147355.htm")

    def test_pipeline_does_not_fallback_to_search_for_region_reviews(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
        )
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        fetcher = StubFetcher({
            "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": "<html><body>No matching office links</body></html>",
        })
        pipeline = ScrapePipeline(fetcher)

        records, _, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.no_result_count, 1)
        self.assertEqual(fetcher.calls, ["https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm"])

    def test_dry_validate_counts_success_without_output_records(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8"),
            })
        )

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=True,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.output_record_count, 0)
        self.assertEqual(attempts[-1].status, "success")

    def test_pipeline_logs_validation_failure_without_writing_main_record(self) -> None:
        company = CompanySeed(display_name="ASUS")
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        pages = {
            "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": (
                FIXTURES / "office_locations_navigation_live_like.html"
            ).read_text(encoding="utf-8"),
            "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-EI_IE40093.4,8_IL.9,15_IC3271041.htm": """
                <html><body>
                <a class=\"LocationReview_headerLink__heQ0m\" href=\"/Reviews/ASUS-Taipei-Reviews-E40093.htm\">
                <span class=\"SectionHeader_tag__iAKuU\">79 reviews in Taipei</span>
                </a>
                </body></html>
            """,
            "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm": (FIXTURES / "review_asus_shanghai.html").read_text(encoding="utf-8"),
        }
        company.office_locations_url = "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm"
        pipeline = ScrapePipeline(StubFetcher(pages))

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.validation_failure_count, 1)
        self.assertEqual(attempts[-1].failure_reason, "region_mismatch")

    def test_attempt_log_preserves_selector_failure_details(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            company_slug_hint="ASUS",
            glassdoor_entity_hint="E40093",
        )
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": (
                    FIXTURES / "office_locations_navigation_live_like.html"
                ).read_text(encoding="utf-8"),
                "https://www.glassdoor.com/Location/All-ASUS-Taipei-Office-Locations-EI_IE40093.4,8_IL.9,15_IC3271041.htm": """
                    <html><body>
                    <a class=\"LocationReview_headerLink__heQ0m\" href=\"/Reviews/ASUS-Taipei-Reviews-E40093.htm\">
                    <span class=\"SectionHeader_tag__iAKuU\">79 reviews in Taipei</span>
                    </a>
                    </body></html>
                """,
                "https://www.glassdoor.com/Reviews/ASUS-Taipei-Reviews-E40093.htm": (FIXTURES / "review_asus_selector_failure.html").read_text(encoding="utf-8"),
            })
        )
        company.office_locations_url = "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm"

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.validation_failure_count, 1)
        self.assertEqual(attempts[-1].missing_fields, "overall")
        self.assertIn("overall:selector_failure", attempts[-1].missing_field_reasons)

    def test_pipeline_logs_no_result_attempt(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
        )
        region = RegionSeed("Tokyo", "tokyo", "APAC", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm": "<html><body>No Tokyo office here</body></html>",
            })
        )

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.no_result_count, 1)
        self.assertEqual(attempts[-1].status, "no_result")

    def test_pipeline_logs_access_restricted_error(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "login_required.html").read_text(encoding="utf-8"),
            })
        )

        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        self.assertEqual(records, [])
        self.assertEqual(summary.error_count, 1)
        self.assertEqual(attempts[-1].failure_reason, "access_restricted: login_required")

    def test_write_outputs_creates_expected_files(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8"),
            })
        )
        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=False,
        )

        output_dir = Path(__file__).resolve().parents[1] / "test-output"
        try:
            output_dir.mkdir(exist_ok=True)
            write_outputs(
                output_dir=output_dir,
                records=records,
                attempts=attempts,
                summary=summary,
                region_pool=[region],
            )
            self.assertTrue((output_dir / "reviews_aggregate.csv").exists())
            self.assertTrue((output_dir / "reviews_aggregate.json").exists())
            self.assertTrue((output_dir / "attempt_log.csv").exists())
            self.assertTrue((output_dir / "run_summary.json").exists())
            self.assertTrue((output_dir / "region_pool.json").exists())
            self.assertIn("output_record_count", (output_dir / "run_summary.json").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_write_outputs_skips_aggregate_files_in_dry_validate_mode(self) -> None:
        company = CompanySeed(
            display_name="ASUS",
            review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        )
        region = RegionSeed("Global", "global", "Global", "manual-seed")
        pipeline = ScrapePipeline(
            StubFetcher({
                "https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm": (FIXTURES / "review_asus_global.html").read_text(encoding="utf-8"),
            })
        )
        records, attempts, summary = pipeline.run(
            companies=[company],
            regions=[region],
            dry_validate=True,
        )

        output_dir = Path(__file__).resolve().parents[1] / "test-output-dry"
        try:
            output_dir.mkdir(exist_ok=True)
            write_outputs(
                output_dir=output_dir,
                records=records,
                attempts=attempts,
                summary=summary,
                region_pool=[region],
                include_aggregate_outputs=False,
            )
            self.assertFalse((output_dir / "reviews_aggregate.csv").exists())
            self.assertFalse((output_dir / "reviews_aggregate.json").exists())
            self.assertTrue((output_dir / "attempt_log.csv").exists())
            self.assertTrue((output_dir / "attempt_log.json").exists())
            self.assertTrue((output_dir / "run_summary.json").exists())
            self.assertTrue((output_dir / "region_pool.json").exists())
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_write_outputs_keeps_aggregate_csv_header_when_no_records(self) -> None:
        output_dir = Path(__file__).resolve().parents[1] / "test-output-empty-aggregate"
        try:
            output_dir.mkdir(exist_ok=True)
            write_outputs(
                output_dir=output_dir,
                records=[],
                attempts=[],
                summary=self._empty_summary(),
                region_pool=[],
                include_aggregate_outputs=True,
            )
            csv_text = (output_dir / "reviews_aggregate.csv").read_text(encoding="utf-8")
            self.assertTrue(csv_text.startswith("company,requested_region,resolved_region,country,review_url,overall"))
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_write_outputs_keeps_attempt_csv_header_when_no_attempts(self) -> None:
        output_dir = Path(__file__).resolve().parents[1] / "test-output-empty-attempts"
        try:
            output_dir.mkdir(exist_ok=True)
            write_outputs(
                output_dir=output_dir,
                records=[],
                attempts=[],
                summary=self._empty_summary(),
                region_pool=[],
                include_aggregate_outputs=False,
            )
            csv_text = (output_dir / "attempt_log.csv").read_text(encoding="utf-8")
            self.assertTrue(csv_text.startswith("company,requested_region,candidate_url,final_url,status"))
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_write_outputs_persists_effective_region_pool(self) -> None:
        output_dir = Path(__file__).resolve().parents[1] / "test-output-region-pool"
        region = RegionSeed("Taipei", "taipei", "Taiwan", "manual-seed")
        try:
            output_dir.mkdir(exist_ok=True)
            write_outputs(
                output_dir=output_dir,
                records=[],
                attempts=[],
                summary=self._empty_summary(),
                region_pool=[region],
                include_aggregate_outputs=False,
            )
            region_pool_text = (output_dir / "region_pool.json").read_text(encoding="utf-8")
            self.assertIn('"raw_label": "Taipei"', region_pool_text)
            self.assertIn('"normalized_label": "taipei"', region_pool_text)
            self.assertIn('"source": "manual-seed"', region_pool_text)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def _empty_summary(self):
        from glassdoor_analysis.models import RunSummary

        return RunSummary(
            company_count=0,
            region_candidate_count=0,
            success_count=0,
            output_record_count=0,
            validation_failure_count=0,
            no_result_count=0,
            error_count=0,
        )


if __name__ == "__main__":
    unittest.main()
