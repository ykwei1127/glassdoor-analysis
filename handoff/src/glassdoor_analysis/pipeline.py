from __future__ import annotations

import csv
import json
import random
import time
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .countries import country_for_region
from .http import FetchError, FetchResponse, UrlFetcher
from .models import (
    AggregateRecord,
    AttemptLogEntry,
    CompanySeed,
    OfficeLocationLink,
    OfficeLocationRecord,
    RegionSeed,
    ReviewUrlRecord,
    RunSummary,
)
from .normalization import normalize_region_label
from .parsers import (
    extract_header_text,
    extract_metrics,
    extract_office_location_links,
    extract_office_locations,
    extract_office_review_links,
)
from .resolver import ReviewCandidate, build_pool_gap_review_url
from .verification import validate_review_page


class ScrapePipeline:
    def __init__(self, fetcher: UrlFetcher) -> None:
        self.fetcher = fetcher
        self._office_location_link_cache: dict[str, list[OfficeLocationLink]] = {}
        self._office_review_link_cache: dict[str, list[str]] = {}
        self._review_page_cache: dict[str, FetchResponse] = {}

    def discover_office_locations(
        self,
        *,
        companies: list[CompanySeed],
        rebuild: bool,
        cache_path: Path,
    ) -> tuple[list[OfficeLocationRecord], list[AttemptLogEntry]]:
        cached_records = [] if not cache_path.exists() else load_office_locations(cache_path)
        selected_companies = {company.display_name for company in companies}
        preserved_records = [record for record in cached_records if record.company not in selected_companies]
        records = [] if rebuild else [record for record in cached_records if record.company in selected_companies]
        completed_companies = {record.company for record in records}
        attempts: list[AttemptLogEntry] = []
        for company in companies:
            if company.display_name in completed_companies:
                continue
            if not company.office_locations_url:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region="",
                        candidate_url="",
                        final_url="",
                        status="no_result",
                        failure_reason="missing_office_locations_url",
                        header_text="",
                        observed_region=None,
                    )
                )
                continue

            try:
                response = self.fetcher.get(company.office_locations_url)
            except FetchError as exc:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region="",
                        candidate_url=company.office_locations_url,
                        final_url=company.office_locations_url,
                        status="error",
                        failure_reason=f"location_discovery_failed: {exc}",
                        header_text="",
                        observed_region=None,
                    )
                )
                save_office_locations(cache_path, [*preserved_records, *records])
                continue

            access_issue = detect_access_issue(response.text)
            if access_issue:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region="",
                        candidate_url=company.office_locations_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=f"location_discovery_failed: {access_issue}",
                        header_text="",
                        observed_region=None,
                    )
                )
                save_office_locations(cache_path, [*preserved_records, *records])
                continue

            links = extract_office_location_links(response.text, response.url)
            if not links:
                is_office_locations_page = "office locations" in response.text.lower()
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region="",
                        candidate_url=company.office_locations_url,
                        final_url=response.url,
                        status="no_result" if is_office_locations_page else "error",
                        failure_reason=(
                            "office_locations_empty"
                            if is_office_locations_page
                            else "location_discovery_failed: office_location_links_not_found"
                        ),
                        header_text="",
                        observed_region=None,
                    )
                )
                save_office_locations(cache_path, [*preserved_records, *records])
                continue

            for link in links:
                records.append(
                    OfficeLocationRecord.create(
                        company=company.display_name,
                        raw_label=link.label,
                        normalized_label=normalize_region_label(link.label),
                        office_url=link.url,
                    )
                )
            save_office_locations(cache_path, [*preserved_records, *records])

        return [*preserved_records, *records], attempts

    def resolve_review_urls(
        self,
        *,
        companies: list[CompanySeed],
        regions: list[RegionSeed],
        office_locations: list[OfficeLocationRecord],
        rebuild: bool,
        cache_path: Path,
    ) -> tuple[list[ReviewUrlRecord], list[AttemptLogEntry]]:
        existing = [] if rebuild or not cache_path.exists() else load_review_url_manifest(cache_path)
        selected_companies = {company.display_name for company in companies}
        selected_regions = {region.normalized_label for region in regions}
        preserved_records = [
            record
            for record in existing
            if record.company not in selected_companies or record.normalized_region not in selected_regions
        ]
        records = [
            record
            for record in existing
            if record.company in selected_companies and record.normalized_region in selected_regions
        ]
        completed_keys = {(record.company, record.normalized_region) for record in records}
        attempts: list[AttemptLogEntry] = []

        locations_by_company: dict[str, list[OfficeLocationRecord]] = {}
        for location in office_locations:
            locations_by_company.setdefault(location.company, []).append(location)

        for company in companies:
            for region in regions:
                key = (company.display_name, region.normalized_label)
                if key in completed_keys:
                    continue
                record, attempt = self._resolve_review_url(
                    company=company,
                    region=region,
                    office_locations=locations_by_company.get(company.display_name, []),
                )
                records.append(record)
                completed_keys.add(key)
                if attempt is not None:
                    attempts.append(attempt)
                save_review_url_manifest(cache_path, [*preserved_records, *records])

        return records, attempts

    def run_from_review_urls(
        self,
        *,
        companies: list[CompanySeed],
        regions: list[RegionSeed],
        review_urls: list[ReviewUrlRecord],
        dry_validate: bool,
    ) -> tuple[list[AggregateRecord], list[AttemptLogEntry], RunSummary]:
        company_lookup = {company.display_name: company for company in companies}
        region_lookup = {region.normalized_label: region for region in regions}
        records: list[AggregateRecord] = []
        attempts: list[AttemptLogEntry] = []
        successes = validation_failures = no_results = errors = 0

        for target in review_urls:
            company = company_lookup.get(target.company)
            region = region_lookup.get(target.normalized_region)
            if company is None or region is None:
                continue
            if target.status != "resolved" or not target.review_url:
                status = "error" if target.status == "error" else "no_result"
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=target.office_url or "",
                        final_url="",
                        status=status,
                        failure_reason=target.failure_reason,
                        header_text="",
                        observed_region=None,
                    )
                )
                if status == "error":
                    errors += 1
                else:
                    no_results += 1
                continue

            try:
                response = self.fetcher.get(target.review_url)
            except FetchError as exc:
                errors += 1
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=target.review_url,
                        final_url=target.review_url,
                        status="error",
                        failure_reason=str(exc),
                        header_text="",
                        observed_region=None,
                    )
                )
                continue

            access_issue = detect_access_issue(response.text)
            if access_issue:
                errors += 1
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=target.review_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=access_issue,
                        header_text="",
                        observed_region=None,
                    )
                )
                continue

            status, aggregate = self._handle_review_response(
                company=company,
                region=region,
                candidate=ReviewCandidate(candidate_url=target.review_url, discovery_mode="review-url-manifest"),
                review_response=response,
                attempts=attempts,
                dry_validate=dry_validate,
            )
            if status == "success":
                successes += 1
                if aggregate is not None:
                    records.append(aggregate)
            else:
                validation_failures += 1

        return records, attempts, RunSummary(
            company_count=len(companies),
            region_candidate_count=len(regions),
            success_count=successes,
            output_record_count=len(records),
            validation_failure_count=validation_failures,
            no_result_count=no_results,
            error_count=errors,
        )

    def probe_review_url_gaps(
        self,
        *,
        companies: list[CompanySeed],
        regions: list[RegionSeed],
        office_locations: list[OfficeLocationRecord],
        review_urls: list[ReviewUrlRecord],
        cache_path: Path,
        retry_failures: bool = False,
        max_probes: int | None = None,
        request_delay_seconds: float = 0,
        request_jitter_seconds: float = 0,
        cooldown_every: int = 0,
        cooldown_seconds: float = 0,
        status_callback: Callable[[str], None] | None = None,
    ) -> tuple[list[ReviewUrlRecord], list[AttemptLogEntry]]:
        selected_companies = {company.display_name: company for company in companies}
        selected_regions = {region.normalized_label: region for region in regions}
        attempts: list[AttemptLogEntry] = []
        processed = 0
        network_requests = 0

        for target in review_urls:
            company = selected_companies.get(target.company)
            region = selected_regions.get(target.normalized_region)
            if company is None or region is None or target.status == "resolved":
                continue
            if target.discovery_mode == "pool-location-id" and not retry_failures:
                continue
            if max_probes is not None and processed >= max_probes:
                break
            processed += 1

            source_office = next(
                (
                    location
                    for location in office_locations
                    if _office_location_matches(region.normalized_label, location.normalized_label)
                ),
                None,
            )
            if source_office is None:
                target.status = "no_result"
                target.failure_reason = "pool_location_id_not_found"
                target.discovery_mode = "pool-location-id"
                target.resolved_at = _utc_now()
                save_review_url_manifest(cache_path, review_urls)
                continue

            candidate_url = build_pool_gap_review_url(company, source_office.office_url)
            if candidate_url is None:
                target.status = "no_result"
                target.failure_reason = "pool_location_candidate_not_buildable"
                target.discovery_mode = "pool-location-id"
                target.resolved_at = _utc_now()
                save_review_url_manifest(cache_path, review_urls)
                continue

            previous_state = (
                target.office_label,
                target.office_url,
                target.review_url,
                target.status,
                target.failure_reason,
                target.discovery_mode,
                target.resolved_at,
            )
            target.office_label = source_office.raw_label
            target.office_url = source_office.office_url
            target.review_url = candidate_url
            target.discovery_mode = "pool-location-id"
            try:
                response = self._review_page_cache.get(candidate_url)
                if response is None:
                    if network_requests > 0 and cooldown_every > 0 and network_requests % cooldown_every == 0:
                        if status_callback:
                            status_callback(f"Cooling down for {cooldown_seconds:g}s after {network_requests} requests.")
                        time.sleep(cooldown_seconds)
                    delay = request_delay_seconds + random.uniform(0, request_jitter_seconds)
                    if delay > 0:
                        time.sleep(delay)
                    response = self.fetcher.get(candidate_url)
                    self._review_page_cache[candidate_url] = response
                    network_requests += 1
            except FetchError as exc:
                target.status = "error"
                target.failure_reason = f"gap_probe_failed: {exc}"
                target.resolved_at = _utc_now()
                attempts.append(_review_url_attempt(target, candidate_url, candidate_url))
                save_review_url_manifest(cache_path, review_urls)
                continue

            access_issue = detect_access_issue(response.text)
            if access_issue:
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=candidate_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=f"gap_probe_stopped: {access_issue}",
                        header_text=extract_header_text(response.text),
                        observed_region=None,
                    )
                )
                (
                    target.office_label,
                    target.office_url,
                    target.review_url,
                    target.status,
                    target.failure_reason,
                    target.discovery_mode,
                    target.resolved_at,
                ) = previous_state
                save_review_url_manifest(cache_path, review_urls)
                if status_callback:
                    status_callback(f"Stopped: {access_issue}. The current record remains retryable.")
                break

            header_text = extract_header_text(response.text)
            metrics = extract_metrics(response.text)
            validation = validate_review_page(
                company_name=company.display_name,
                requested_region=region.raw_label,
                header_text=header_text,
                metrics=metrics,
            )
            target.review_url = response.url
            target.status = "resolved" if validation.is_valid else "validation_failed"
            target.failure_reason = None if validation.is_valid else f"gap_probe_failed: {validation.failure_reason}"
            target.resolved_at = _utc_now()
            attempts.append(
                AttemptLogEntry.create(
                    company=target.company,
                    requested_region=target.requested_region,
                    candidate_url=candidate_url,
                    final_url=response.url,
                    status="success" if validation.is_valid else "validation_failed",
                    failure_reason=target.failure_reason,
                    header_text=header_text,
                    observed_region=validation.observed_region,
                    missing_fields=",".join(metrics.missing_fields) or None,
                    missing_field_reasons=_stringify_missing_field_reasons(metrics.missing_field_reasons),
                )
            )
            save_review_url_manifest(cache_path, review_urls)

        return review_urls, attempts

    def extract_metrics_incremental(
        self,
        *,
        companies: list[CompanySeed],
        regions: list[RegionSeed],
        review_urls: list[ReviewUrlRecord],
        checkpoint_dir: Path,
        dry_validate: bool,
        max_extractions: int | None = None,
        retry_failures: bool = False,
        refresh_existing: bool = False,
        request_delay_seconds: float = 0,
        request_jitter_seconds: float = 0,
        cooldown_every: int = 0,
        cooldown_seconds: float = 0,
        progress_every: int = 10,
        status_callback: Callable[[str], None] | None = None,
    ) -> tuple[list[AggregateRecord], list[AttemptLogEntry], RunSummary]:
        records_path = checkpoint_dir / "reviews_aggregate.json"
        attempts_path = checkpoint_dir / "metrics_attempt_log.json"
        records = load_aggregate_records(records_path) if records_path.exists() else []
        attempts = load_attempt_logs(attempts_path) if attempts_path.exists() else []
        company_lookup = {company.display_name: company for company in companies}
        region_lookup = {region.normalized_label: region for region in regions}
        successful_keys = {(record.company, record.requested_region) for record in records}
        completed_failure_keys = {
            (attempt.company, attempt.requested_region)
            for attempt in attempts
            if attempt.status in {"validation_failed", "no_result"}
        }
        targets = [
            target
            for target in review_urls
            if target.status == "resolved"
            and target.review_url
            and target.company in company_lookup
            and target.normalized_region in region_lookup
            and (
                (refresh_existing and (target.company, target.requested_region) in successful_keys)
                or (not refresh_existing and (target.company, target.requested_region) not in successful_keys)
            )
            and (
                retry_failures
                or (target.company, target.requested_region) not in completed_failure_keys
            )
        ]
        total_pending = len(targets)
        processed = 0
        network_requests = 0
        new_successes = 0
        new_validation_failures = 0
        new_errors = 0
        stopped_for_access = False

        if status_callback:
            status_callback(
                f"Extraction start: {total_pending} pending of "
                f"{sum(1 for target in review_urls if target.status == 'resolved')} resolved URLs."
            )

        for target in targets:
            if max_extractions is not None and processed >= max_extractions:
                break
            company = company_lookup[target.company]
            region = region_lookup[target.normalized_region]
            candidate_url = target.review_url or ""

            try:
                response = self._review_page_cache.get(candidate_url)
                if response is None:
                    if network_requests > 0 and cooldown_every > 0 and network_requests % cooldown_every == 0:
                        if status_callback:
                            status_callback(f"Cooling down for {cooldown_seconds:g}s after {network_requests} requests.")
                        time.sleep(cooldown_seconds)
                    delay = request_delay_seconds + random.uniform(0, request_jitter_seconds)
                    if delay > 0:
                        time.sleep(delay)
                    response = self.fetcher.get(candidate_url)
                    self._review_page_cache[candidate_url] = response
                    network_requests += 1
            except FetchError as exc:
                new_errors += 1
                processed += 1
                failure_reason = f"metrics_fetch_failed: {exc}"
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=candidate_url,
                        final_url=candidate_url,
                        status="error",
                        failure_reason=failure_reason,
                        header_text="",
                        observed_region=None,
                    )
                )
                if status_callback:
                    status_callback(f"Fetch error for {target.company} / {target.requested_region}: {failure_reason}")
                write_extraction_checkpoint(checkpoint_dir, records, attempts, include_records=not dry_validate)
                _report_extraction_progress(
                    status_callback,
                    processed,
                    total_pending,
                    new_successes,
                    new_validation_failures,
                    new_errors,
                    progress_every,
                )
                continue

            access_issue = detect_access_issue(response.text)
            if access_issue:
                new_errors += 1
                attempts.append(
                    AttemptLogEntry.create(
                        company=target.company,
                        requested_region=target.requested_region,
                        candidate_url=candidate_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=f"metrics_extraction_stopped: {access_issue}",
                        header_text=extract_header_text(response.text),
                        observed_region=None,
                    )
                )
                write_extraction_checkpoint(checkpoint_dir, records, attempts, include_records=not dry_validate)
                stopped_for_access = True
                if status_callback:
                    status_callback(f"Stopped: {access_issue}. The current URL remains retryable.")
                break

            before_attempt_count = len(attempts)
            status, aggregate = self._handle_review_response(
                company=company,
                region=region,
                candidate=ReviewCandidate(candidate_url=candidate_url, discovery_mode="review-url-manifest"),
                review_response=response,
                attempts=attempts,
                dry_validate=dry_validate,
            )
            processed += 1
            if status == "success":
                new_successes += 1
                if aggregate is not None:
                    aggregate_key = (aggregate.company, aggregate.requested_region)
                    records = [
                        record
                        for record in records
                        if (record.company, record.requested_region) != aggregate_key
                    ]
                    records.append(aggregate)
                    successful_keys.add(aggregate_key)
            else:
                new_validation_failures += 1
            if len(attempts) == before_attempt_count:
                raise RuntimeError("Metrics extraction did not produce an attempt log entry.")

            write_extraction_checkpoint(checkpoint_dir, records, attempts, include_records=not dry_validate)
            _report_extraction_progress(
                status_callback,
                processed,
                total_pending,
                new_successes,
                new_validation_failures,
                new_errors,
                progress_every,
            )

        latest_attempts = _latest_attempts_by_target(attempts)
        summary = RunSummary(
            company_count=len(companies),
            region_candidate_count=len(regions),
            success_count=len(records) if not dry_validate else sum(
                attempt.status == "success" for attempt in latest_attempts.values()
            ),
            output_record_count=len(records) if not dry_validate else 0,
            validation_failure_count=sum(
                attempt.status == "validation_failed" for attempt in latest_attempts.values()
            ),
            no_result_count=sum(attempt.status == "no_result" for attempt in latest_attempts.values()),
            error_count=sum(attempt.status == "error" for attempt in latest_attempts.values()),
        )
        if status_callback:
            suffix = " (stopped by access restriction)" if stopped_for_access else ""
            status_callback(
                f"Extraction checkpoint: processed={processed}, success={new_successes}, "
                f"validation_failed={new_validation_failures}, errors={new_errors}{suffix}."
            )
        return records, attempts, summary

    def _resolve_review_url(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        office_locations: list[OfficeLocationRecord],
    ) -> tuple[ReviewUrlRecord, AttemptLogEntry | None]:
        if region.normalized_label == "global":
            if company.review_url_hint:
                return ReviewUrlRecord.create(
                    company=company.display_name,
                    requested_region=region.raw_label,
                    normalized_region=region.normalized_label,
                    region_source=region.source,
                    office_label=None,
                    office_url=None,
                    review_url=company.review_url_hint,
                    status="resolved",
                    discovery_mode="review-url-hint",
                ), None
            return self._unresolved_review_url(company, region, "missing_review_url_hint")

        matches = [
            location
            for location in office_locations
            if _office_location_matches(region.normalized_label, location.normalized_label)
        ]
        if not matches:
            reason = "missing_office_locations_url" if not company.office_locations_url else "office_location_not_found"
            return self._unresolved_review_url(company, region, reason)

        office = matches[0]
        try:
            response = self.fetcher.get(office.office_url)
        except FetchError as exc:
            return self._unresolved_review_url(
                company,
                region,
                f"office_navigation_failed: {exc}",
                office=office,
                status="error",
            )
        access_issue = detect_access_issue(response.text)
        if access_issue:
            return self._unresolved_review_url(
                company,
                region,
                f"office_navigation_failed: {access_issue}",
                office=office,
                status="error",
            )
        review_links = extract_office_review_links(response.text, response.url)
        if not review_links:
            return self._unresolved_review_url(company, region, "office_review_link_not_found", office=office)

        return ReviewUrlRecord.create(
            company=company.display_name,
            requested_region=region.raw_label,
            normalized_region=region.normalized_label,
            region_source=region.source,
            office_label=office.raw_label,
            office_url=office.office_url,
            review_url=review_links[0],
            status="resolved",
            discovery_mode="office-navigation",
        ), None

    @staticmethod
    def _unresolved_review_url(
        company: CompanySeed,
        region: RegionSeed,
        reason: str,
        *,
        office: OfficeLocationRecord | None = None,
        status: str = "no_result",
    ) -> tuple[ReviewUrlRecord, AttemptLogEntry]:
        record = ReviewUrlRecord.create(
            company=company.display_name,
            requested_region=region.raw_label,
            normalized_region=region.normalized_label,
            region_source=region.source,
            office_label=office.raw_label if office else None,
            office_url=office.office_url if office else None,
            review_url=None,
            status=status,
            discovery_mode="office-navigation",
            failure_reason=reason,
        )
        attempt = AttemptLogEntry.create(
            company=company.display_name,
            requested_region=region.raw_label,
            candidate_url=office.office_url if office else "",
            final_url="",
            status=status,
            failure_reason=reason,
            header_text="",
            observed_region=None,
        )
        return record, attempt

    def build_region_pool(
        self,
        companies: list[CompanySeed],
        manual_regions: list[RegionSeed],
        rebuild_region_pool: bool,
        cache_path: Path | None = None,
    ) -> tuple[list[RegionSeed], list[AttemptLogEntry]]:
        attempt_logs: list[AttemptLogEntry] = []
        if not rebuild_region_pool and cache_path and cache_path.exists():
            cached_regions = load_region_pool(cache_path)
            return dedupe_regions([*cached_regions, *manual_regions]), attempt_logs
        if not rebuild_region_pool:
            return dedupe_regions(manual_regions), attempt_logs

        discovered: list[RegionSeed] = []
        for company in companies:
            if not company.office_locations_url:
                continue
            try:
                response = self.fetcher.get(company.office_locations_url)
                access_issue = detect_access_issue(response.text)
                if access_issue:
                    attempt_logs.append(
                        AttemptLogEntry.create(
                            company=company.display_name,
                            requested_region="",
                            candidate_url=company.office_locations_url,
                            final_url=response.url,
                            status="error",
                            failure_reason=f"location_discovery_failed: {access_issue}",
                            header_text="",
                            observed_region=None,
                        )
                    )
                    continue
                for location in extract_office_locations(response.text):
                    discovered.append(
                        RegionSeed(
                            raw_label=location,
                            normalized_label=normalize_region_label(location),
                            country_or_macro_hint=None,
                            source="office-location",
                        )
                    )
            except FetchError as exc:
                attempt_logs.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region="",
                        candidate_url=company.office_locations_url,
                        final_url=company.office_locations_url,
                        status="error",
                        failure_reason=f"location_discovery_failed: {exc}",
                        header_text="",
                        observed_region=None,
                    )
                )
        merged_regions = dedupe_regions([*discovered, *manual_regions])
        if cache_path:
            save_region_pool(cache_path, merged_regions)
        return merged_regions, attempt_logs

    def run(
        self,
        *,
        companies: list[CompanySeed],
        regions: list[RegionSeed],
        dry_validate: bool,
    ) -> tuple[list[AggregateRecord], list[AttemptLogEntry], RunSummary]:
        records: list[AggregateRecord] = []
        attempts: list[AttemptLogEntry] = []
        validation_failures = 0
        no_results = 0
        errors = 0
        successful_validations = 0

        for company in companies:
            for region in regions:
                status, aggregate, region_attempts = self._process_company_region(
                    company=company,
                    region=region,
                    dry_validate=dry_validate,
                )
                attempts.extend(region_attempts)
                if status == "success":
                    successful_validations += 1
                    if aggregate is not None:
                        records.append(aggregate)
                elif status == "validation_failed":
                    validation_failures += 1
                elif status == "no_result":
                    no_results += 1
                elif status == "error":
                    errors += 1

        summary = RunSummary(
            company_count=len(companies),
            region_candidate_count=len(regions),
            success_count=successful_validations,
            output_record_count=len(records),
            validation_failure_count=validation_failures,
            no_result_count=no_results,
            error_count=errors,
        )
        return records, attempts, summary

    def _process_company_region(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        dry_validate: bool,
    ) -> tuple[str, AggregateRecord | None, list[AttemptLogEntry]]:
        attempts: list[AttemptLogEntry] = []
        candidates = self._build_review_candidates(company=company, region=region, attempts=attempts)
        saw_validation_failure = False

        for candidate in candidates:
            try:
                response = self.fetcher.get(candidate.candidate_url)
            except FetchError as exc:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region=region.raw_label,
                        candidate_url=candidate.candidate_url,
                        final_url=candidate.candidate_url,
                        status="error",
                        failure_reason=str(exc),
                        header_text="",
                        observed_region=None,
                    )
                )
                continue
            access_issue = detect_access_issue(response.text)
            if access_issue:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region=region.raw_label,
                        candidate_url=candidate.candidate_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=access_issue,
                        header_text="",
                        observed_region=None,
                    )
                )
                return "error", None, attempts

            status, aggregate = self._handle_review_response(
                company=company,
                region=region,
                candidate=candidate,
                review_response=response,
                attempts=attempts,
                dry_validate=dry_validate,
            )
            if status == "continue":
                saw_validation_failure = True
                continue
            return status, aggregate, attempts

        if any(entry.status == "error" for entry in attempts):
            return "error", None, attempts
        if saw_validation_failure:
            return "validation_failed", None, attempts
        attempts.append(
            AttemptLogEntry.create(
                company=company.display_name,
                requested_region=region.raw_label,
                candidate_url=candidates[-1].candidate_url if candidates else "",
                final_url="",
                status="no_result",
                failure_reason="no_matching_review_page_found",
                header_text="",
                observed_region=None,
            )
        )
        return "no_result", None, attempts

    def _build_review_candidates(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        attempts: list[AttemptLogEntry],
    ) -> list[ReviewCandidate]:
        if region.normalized_label == "global":
            if not company.review_url_hint:
                return []
            return [ReviewCandidate(candidate_url=company.review_url_hint, discovery_mode="review-url-hint")]
        return self._build_office_navigation_candidates(company=company, region=region, attempts=attempts)

    def _build_office_navigation_candidates(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        attempts: list[AttemptLogEntry],
    ) -> list[ReviewCandidate]:
        if region.normalized_label == "global" or not company.office_locations_url:
            return []

        office_links = self._get_office_location_links(company=company, region=region, attempts=attempts)
        if not office_links:
            return []

        candidates: list[ReviewCandidate] = []
        seen_urls: set[str] = set()
        for office_link in office_links:
            review_links = self._get_office_review_links(
                company=company,
                region=region,
                office_link=office_link,
                attempts=attempts,
            )
            for review_link in review_links:
                if review_link in seen_urls:
                    continue
                seen_urls.add(review_link)
                candidates.append(
                    ReviewCandidate(
                        candidate_url=review_link,
                        discovery_mode="office-review-link",
                    )
                )
        return candidates

    def _get_office_location_links(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        attempts: list[AttemptLogEntry],
    ) -> list[OfficeLocationLink]:
        if not company.office_locations_url:
            return []
        if company.office_locations_url not in self._office_location_link_cache:
            try:
                response = self.fetcher.get(company.office_locations_url)
            except FetchError as exc:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region=region.raw_label,
                        candidate_url=company.office_locations_url,
                        final_url=company.office_locations_url,
                        status="error",
                        failure_reason=f"office_navigation_failed: {exc}",
                        header_text="",
                        observed_region=None,
                    )
                )
                return []
            access_issue = detect_access_issue(response.text)
            if access_issue:
                attempts.append(
                    AttemptLogEntry.create(
                        company=company.display_name,
                        requested_region=region.raw_label,
                        candidate_url=company.office_locations_url,
                        final_url=response.url,
                        status="error",
                        failure_reason=f"office_navigation_failed: {access_issue}",
                        header_text="",
                        observed_region=None,
                    )
                )
                return []
            self._office_location_link_cache[company.office_locations_url] = extract_office_location_links(
                response.text,
                response.url,
            )

        expected = region.normalized_label
        return [
            link
            for link in self._office_location_link_cache[company.office_locations_url]
            if _office_location_matches(expected, normalize_region_label(link.label))
        ]

    def _get_office_review_links(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        office_link: OfficeLocationLink,
        attempts: list[AttemptLogEntry],
    ) -> list[str]:
        if office_link.url in self._office_review_link_cache:
            return self._office_review_link_cache[office_link.url]

        try:
            response = self.fetcher.get(office_link.url)
        except FetchError as exc:
            attempts.append(
                AttemptLogEntry.create(
                    company=company.display_name,
                    requested_region=region.raw_label,
                    candidate_url=office_link.url,
                    final_url=office_link.url,
                    status="error",
                    failure_reason=f"office_navigation_failed: {exc}",
                    header_text="",
                    observed_region=None,
                )
            )
            return []

        access_issue = detect_access_issue(response.text)
        if access_issue:
            attempts.append(
                AttemptLogEntry.create(
                    company=company.display_name,
                    requested_region=region.raw_label,
                    candidate_url=office_link.url,
                    final_url=response.url,
                    status="error",
                    failure_reason=f"office_navigation_failed: {access_issue}",
                    header_text="",
                    observed_region=None,
                )
            )
            return []

        review_links = extract_office_review_links(response.text, response.url)
        self._office_review_link_cache[office_link.url] = review_links
        return review_links

    def _handle_review_response(
        self,
        *,
        company: CompanySeed,
        region: RegionSeed,
        candidate: ReviewCandidate,
        review_response: FetchResponse,
        attempts: list[AttemptLogEntry],
        dry_validate: bool,
    ) -> tuple[str, AggregateRecord | None]:
        header_text = extract_header_text(review_response.text)
        metrics = extract_metrics(review_response.text)
        validation = validate_review_page(
            company_name=company.display_name,
            requested_region=region.raw_label,
            header_text=header_text,
            metrics=metrics,
        )

        attempts.append(
            AttemptLogEntry.create(
                company=company.display_name,
                requested_region=region.raw_label,
                candidate_url=candidate.candidate_url,
                final_url=review_response.url,
                status="success" if validation.is_valid else validation.status,
                failure_reason=validation.failure_reason,
                header_text=validation.header_text,
                observed_region=validation.observed_region,
                missing_fields=",".join(metrics.missing_fields) or None,
                missing_field_reasons=_stringify_missing_field_reasons(metrics.missing_field_reasons),
            )
        )

        if not validation.is_valid:
            return "continue", None

        if dry_validate:
            return "success", None

        return (
            "success",
            AggregateRecord.from_metrics(
                company=company.display_name,
                requested_region=region.raw_label,
                resolved_region=validation.observed_region or "Global",
                country=country_for_region(region),
                review_url=review_response.url,
                header_text=validation.header_text,
                company_input_source="seed",
                region_source=region.source,
                validation_status=validation.status,
                metrics=metrics,
            ),
        )


def dedupe_regions(regions: list[RegionSeed]) -> list[RegionSeed]:
    deduped: dict[str, RegionSeed] = {}
    for region in regions:
        key = region.normalized_label
        if key not in deduped:
            deduped[key] = region
    return list(deduped.values())


def build_region_pool_from_inventory(
    office_locations: list[OfficeLocationRecord],
    manual_regions: list[RegionSeed],
) -> list[RegionSeed]:
    discovered = [
        RegionSeed(
            raw_label=location.raw_label,
            normalized_label=location.normalized_label,
            country_or_macro_hint=None,
            source=location.source,
        )
        for location in office_locations
    ]
    return dedupe_regions([*discovered, *manual_regions])


def write_outputs(
    *,
    output_dir: Path,
    records: list[AggregateRecord],
    attempts: list[AttemptLogEntry],
    summary: RunSummary,
    region_pool: list[RegionSeed],
    include_aggregate_outputs: bool = True,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    records_payload = [asdict(record) for record in records]
    attempts_payload = [asdict(entry) for entry in attempts]

    save_region_pool(output_dir / "region_pool.json", region_pool)
    (output_dir / "attempt_log.json").write_text(
        json.dumps(attempts_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "run_summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if include_aggregate_outputs:
        (output_dir / "reviews_aggregate.json").write_text(
            json.dumps(records_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_csv(
            output_dir / "reviews_aggregate.csv",
            records_payload,
            fieldnames=_dataclass_fieldnames(AggregateRecord),
        )
    _write_csv(
        output_dir / "attempt_log.csv",
        attempts_payload,
        fieldnames=_dataclass_fieldnames(AttemptLogEntry),
    )


def write_stage_attempts(output_dir: Path, attempts: list[AttemptLogEntry]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = [asdict(entry) for entry in attempts]
    (output_dir / "attempt_log.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_csv(
        output_dir / "attempt_log.csv",
        payload,
        fieldnames=_dataclass_fieldnames(AttemptLogEntry),
    )


def save_region_pool(path: Path, regions: list[RegionSeed]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(region) for region in regions]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_region_pool(path: Path) -> list[RegionSeed]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [RegionSeed(**item) for item in payload]


def save_office_locations(path: Path, records: list[OfficeLocationRecord]) -> None:
    _save_dataclass_records(path, records, OfficeLocationRecord)


def load_office_locations(path: Path) -> list[OfficeLocationRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [OfficeLocationRecord(**item) for item in payload]


def save_review_url_manifest(path: Path, records: list[ReviewUrlRecord]) -> None:
    _save_dataclass_records(path, records, ReviewUrlRecord)


def load_review_url_manifest(path: Path) -> list[ReviewUrlRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [ReviewUrlRecord(**item) for item in payload]


def load_aggregate_records(path: Path) -> list[AggregateRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [AggregateRecord(**({"country": None} | item)) for item in payload]


def save_aggregate_records(path: Path, records: list[AggregateRecord]) -> None:
    _save_dataclass_records(path, records, AggregateRecord)


def load_attempt_logs(path: Path) -> list[AttemptLogEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [AttemptLogEntry(**item) for item in payload]


def write_extraction_checkpoint(
    output_dir: Path,
    records: list[AggregateRecord],
    attempts: list[AttemptLogEntry],
    *,
    include_records: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if include_records:
        _save_dataclass_records(output_dir / "reviews_aggregate.json", records, AggregateRecord)
    _save_dataclass_records(output_dir / "metrics_attempt_log.json", attempts, AttemptLogEntry)


def _save_dataclass_records(path: Path, records: list[object], record_type: type[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(record) for record in records]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(path.with_suffix(".csv"), payload, fieldnames=_dataclass_fieldnames(record_type))


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def detect_access_issue(html_text: str) -> str | None:
    normalized = html_text.lower()
    rate_limit_markers = [
        "help us protect glassdoor",
        "unusually high number of requests",
        "temporarily limited your access",
    ]
    if any(marker in normalized for marker in rate_limit_markers):
        return "access_restricted: rate_limited"
    captcha_markers = [
        "verify you are human",
        "complete the security check",
        "press & hold to confirm you are a human",
        "captcha challenge",
        "please complete the captcha",
        "/captcha/",
    ]
    if any(marker in normalized for marker in captcha_markers):
        return "access_restricted: captcha_detected"
    login_markers = [
        "sign in to continue",
        "create an account to continue",
        "join now to continue",
        "log in to continue",
    ]
    for marker in login_markers:
        if marker in normalized:
            return "access_restricted: login_required"
    return None


def _stringify_missing_field_reasons(reasons: dict[str, str]) -> str | None:
    if not reasons:
        return None
    return ",".join(f"{field}:{reason}" for field, reason in sorted(reasons.items()))


def _review_url_attempt(target: ReviewUrlRecord, candidate_url: str, final_url: str) -> AttemptLogEntry:
    return AttemptLogEntry.create(
        company=target.company,
        requested_region=target.requested_region,
        candidate_url=candidate_url,
        final_url=final_url,
        status=target.status,
        failure_reason=target.failure_reason,
        header_text="",
        observed_region=None,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _latest_attempts_by_target(attempts: list[AttemptLogEntry]) -> dict[tuple[str, str], AttemptLogEntry]:
    latest: dict[tuple[str, str], AttemptLogEntry] = {}
    for attempt in attempts:
        latest[(attempt.company, attempt.requested_region)] = attempt
    return latest


def _report_extraction_progress(
    callback: Callable[[str], None] | None,
    processed: int,
    total: int,
    successes: int,
    validation_failures: int,
    errors: int,
    progress_every: int,
) -> None:
    if callback is None:
        return
    if progress_every > 0 and processed % progress_every != 0 and processed != total:
        return
    callback(
        f"Extraction progress: {processed}/{total} | success={successes} | "
        f"validation_failed={validation_failures} | errors={errors}"
    )

def _office_location_matches(expected_region: str, observed_region: str) -> bool:
    if expected_region == observed_region:
        return True
    if observed_region.startswith(expected_region):
        return True
    return expected_region.startswith(observed_region)


def _dataclass_fieldnames(model: type) -> list[str]:
    return [field.name for field in fields(model)]
