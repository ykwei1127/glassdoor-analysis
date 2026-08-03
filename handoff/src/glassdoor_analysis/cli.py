from __future__ import annotations

import argparse
from pathlib import Path
import re

from .http import BrowserCdpFetcher, UrlFetcher
from .countries import country_for_region_label, save_region_country_map
from .models import CompanySeed, RunSummary
from .pipeline import (
    ScrapePipeline,
    build_region_pool_from_inventory,
    load_office_locations,
    load_aggregate_records,
    load_region_pool,
    load_review_url_manifest,
    save_region_pool,
    save_aggregate_records,
    write_outputs,
    write_stage_attempts,
)
from .seeds import COMPANY_SEEDS, manual_region_seeds
from .session import load_session_config
from .normalization import normalize_region_label


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Glassdoor aggregate review metrics.")
    parser.add_argument("--companies", nargs="*", help="Subset of company names to run.")
    parser.add_argument("--regions", nargs="*", help="Subset of raw or normalized region names to run.")
    parser.add_argument("--session-source", help="Path to session JSON or cookie header text file.")
    parser.add_argument(
        "--browser-cdp-url",
        help="Optional Chrome remote debugging URL, for example http://127.0.0.1:9223.",
    )
    parser.add_argument("--output-dir", default="artifacts", help="Directory for CSV/JSON outputs.")
    parser.add_argument(
        "--region-pool-cache",
        help="Optional path to a persisted region pool JSON file. Defaults to <output-dir>/region_pool.json.",
    )
    parser.add_argument(
        "--rebuild-region-pool",
        action="store_true",
        help="Rebuild office location inventory and the merged region pool.",
    )
    parser.add_argument(
        "--rebuild-review-urls",
        action="store_true",
        help="Discard the cached company-region review URL manifest and resolve it again.",
    )
    parser.add_argument(
        "--stage",
        choices=(
            "all",
            "discover-locations",
            "resolve-review-urls",
            "probe-review-url-gaps",
            "extract-metrics",
            "backfill-countries",
        ),
        default="all",
        help="Run all stages or stop at one specific pipeline stage.",
    )
    parser.add_argument(
        "--office-locations-cache",
        help="Defaults to <output-dir>/office_locations.json.",
    )
    parser.add_argument(
        "--review-urls-cache",
        help="Defaults to <output-dir>/company_region_review_urls.json.",
    )
    parser.add_argument(
        "--max-gap-probes",
        type=int,
        help="Maximum unresolved company-region records to process in one gap-probe run.",
    )
    parser.add_argument(
        "--retry-gap-failures",
        action="store_true",
        help="Retry records already attempted by the pool location-ID gap probe.",
    )
    parser.add_argument(
        "--max-extractions",
        type=int,
        help="Maximum resolved review URLs to extract in one run.",
    )
    parser.add_argument(
        "--retry-extraction-failures",
        action="store_true",
        help="Retry review URLs with a previous validation failure.",
    )
    parser.add_argument(
        "--refresh-existing-metrics",
        action="store_true",
        help="Re-extract and replace only records already present in reviews_aggregate.json.",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=4.0,
        help="Base delay between probe or extraction requests. Defaults to 4 seconds.",
    )
    parser.add_argument(
        "--request-jitter-seconds",
        type=float,
        default=2.0,
        help="Random additional delay between requests. Defaults to 0-2 seconds.",
    )
    parser.add_argument(
        "--cooldown-every",
        type=int,
        default=25,
        help="Pause after this many probe or extraction requests. Defaults to 25.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=8.0,
        help="Periodic cooldown duration. Defaults to 8 seconds.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print extraction progress after this many processed URLs. Defaults to 10; use 0 to disable.",
    )
    parser.add_argument(
        "--dry-validate",
        action="store_true",
        help="Validate candidate pages without writing successful aggregate records.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    for name in (
        "request_delay_seconds",
        "request_jitter_seconds",
        "cooldown_every",
        "cooldown_seconds",
        "progress_every",
    ):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be zero or greater")
    if args.max_extractions is not None and args.max_extractions < 0:
        parser.error("--max-extractions must be zero or greater")

    company_lookup = build_company_lookup(COMPANY_SEEDS)
    if args.companies:
        companies = []
        seen_companies: set[str] = set()
        for name in args.companies:
            company = company_lookup.get(normalize_company_key(name))
            if company is None:
                parser.error(f"Unknown company: {name}")
            company_key = company.display_name.lower()
            if company_key in seen_companies:
                continue
            seen_companies.add(company_key)
            companies.append(company)
    else:
        companies = COMPANY_SEEDS

    output_dir = Path(args.output_dir)
    region_pool_cache = Path(args.region_pool_cache) if args.region_pool_cache else output_dir / "region_pool.json"
    office_locations_cache = (
        Path(args.office_locations_cache) if args.office_locations_cache else output_dir / "office_locations.json"
    )
    review_urls_cache = (
        Path(args.review_urls_cache) if args.review_urls_cache else output_dir / "company_region_review_urls.json"
    )
    if args.stage == "backfill-countries":
        aggregate_path = output_dir / "reviews_aggregate.json"
        if not aggregate_path.exists():
            parser.error(f"Aggregate output not found: {aggregate_path}")
        records = load_aggregate_records(aggregate_path)
        missing_regions: set[str] = set()
        for record in records:
            record.country = country_for_region_label(record.requested_region)
            if record.country is None:
                missing_regions.add(record.requested_region)
        save_aggregate_records(aggregate_path, records)
        if region_pool_cache.exists():
            save_region_country_map(output_dir / "region_country_map.json", load_region_pool(region_pool_cache))
        print(f"Country backfill complete: {len(records)} records, {len(missing_regions)} unmapped regions.")
        if missing_regions:
            print("Unmapped regions: " + ", ".join(sorted(missing_regions)))
            return 1
        return 0
    try:
        fetcher = build_fetcher(
            session_source=args.session_source,
            browser_cdp_url=args.browser_cdp_url,
        )
        pipeline = ScrapePipeline(fetcher)

        if args.stage in {"extract-metrics", "probe-review-url-gaps"}:
            if not region_pool_cache.exists():
                parser.error(f"Region pool cache not found: {region_pool_cache}")
            if not review_urls_cache.exists():
                parser.error(f"Review URL cache not found: {review_urls_cache}")
            regions = load_region_pool(region_pool_cache)
            review_urls = load_review_url_manifest(review_urls_cache)
            if args.stage == "probe-review-url-gaps":
                pool_keys = {region.normalized_label for region in regions}
                manifest_keys = {record.normalized_region for record in review_urls}
                missing_keys = sorted(manifest_keys - pool_keys)
                if missing_keys:
                    sample = ", ".join(missing_keys[:5])
                    parser.error(
                        f"Region pool is incomplete: {len(missing_keys)} manifest regions are missing "
                        f"(for example: {sample}). Rebuild region_pool.json from office_locations.json."
                    )
            run_regions = select_regions(regions, args.regions, parser)
            discovery_attempts = []
            resolution_attempts = []
            if args.stage == "probe-review-url-gaps":
                if not office_locations_cache.exists():
                    parser.error(f"Office locations cache not found: {office_locations_cache}")
                office_locations = load_office_locations(office_locations_cache)
                review_urls, gap_attempts = pipeline.probe_review_url_gaps(
                    companies=companies,
                    regions=run_regions,
                    office_locations=office_locations,
                    review_urls=review_urls,
                    cache_path=review_urls_cache,
                    retry_failures=args.retry_gap_failures,
                    max_probes=args.max_gap_probes,
                    request_delay_seconds=args.request_delay_seconds,
                    request_jitter_seconds=args.request_jitter_seconds,
                    cooldown_every=args.cooldown_every,
                    cooldown_seconds=args.cooldown_seconds,
                    status_callback=print,
                )
                write_stage_attempts(output_dir, gap_attempts)
                return 1 if any(attempt.status == "error" for attempt in gap_attempts) else 0
        else:
            office_locations, discovery_attempts = pipeline.discover_office_locations(
                companies=companies,
                rebuild=args.rebuild_region_pool,
                cache_path=office_locations_cache,
            )
            regions = build_region_pool_from_inventory(office_locations, manual_region_seeds())
            save_region_pool(region_pool_cache, regions)
            run_regions = select_regions(regions, args.regions, parser)

            if args.stage == "discover-locations":
                write_stage_attempts(output_dir, discovery_attempts)
                return 1 if any(attempt.status == "error" for attempt in discovery_attempts) else 0

            review_urls, resolution_attempts = pipeline.resolve_review_urls(
                companies=companies,
                regions=run_regions,
                office_locations=office_locations,
                rebuild=args.rebuild_review_urls,
                cache_path=review_urls_cache,
            )
            if args.stage == "resolve-review-urls":
                stage_attempts = [*discovery_attempts, *resolution_attempts]
                write_stage_attempts(output_dir, stage_attempts)
                return 1 if any(attempt.status == "error" for attempt in stage_attempts) else 0
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    records, attempts, summary = pipeline.extract_metrics_incremental(
        companies=companies,
        regions=run_regions,
        review_urls=review_urls,
        checkpoint_dir=output_dir,
        dry_validate=args.dry_validate,
        max_extractions=args.max_extractions,
        retry_failures=args.retry_extraction_failures,
        refresh_existing=args.refresh_existing_metrics,
        request_delay_seconds=args.request_delay_seconds,
        request_jitter_seconds=args.request_jitter_seconds,
        cooldown_every=args.cooldown_every,
        cooldown_seconds=args.cooldown_seconds,
        progress_every=args.progress_every,
        status_callback=print,
    )
    summary.error_count += sum(1 for attempt in discovery_attempts if attempt.status == "error")
    write_outputs(
        output_dir=output_dir,
        records=records,
        attempts=[*discovery_attempts, *attempts],
        summary=summary,
        region_pool=regions,
        include_aggregate_outputs=not args.dry_validate,
    )
    return determine_exit_code(summary)


def select_regions(regions, requested, parser):  # noqa: ANN001, ANN201
    if not requested:
        return regions
    lookup = {region.normalized_label: region for region in regions}
    selected = []
    seen: set[str] = set()
    for value in requested:
        key = normalize_region_label(value)
        region = lookup.get(key)
        if region is None:
            matches = [candidate for candidate in regions if candidate.normalized_label.startswith(key)]
            if len(matches) == 1:
                region = matches[0]
        if region is None:
            parser.error(f"Unknown or ambiguous region: {value}")
        if region.normalized_label not in seen:
            seen.add(region.normalized_label)
            selected.append(region)
    return selected


def determine_exit_code(summary: RunSummary) -> int:
    if summary.error_count > 0:
        return 1
    return 0


def build_fetcher(*, session_source: str | None, browser_cdp_url: str | None):
    if browser_cdp_url:
        return BrowserCdpFetcher(browser_cdp_url)
    session = load_session_config(session_source)
    return UrlFetcher(session)


def build_company_lookup(companies: list[CompanySeed]) -> dict[str, CompanySeed]:
    lookup: dict[str, CompanySeed] = {}
    for company in companies:
        for value in (
            company.display_name,
            company.company_slug_hint,
            _de_slugify_hint(company.company_slug_hint),
        ):
            if not value:
                continue
            lookup[normalize_company_key(value)] = company
    return lookup


def normalize_company_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.strip().lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _de_slugify_hint(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"[-_]+", " ", value).strip()
