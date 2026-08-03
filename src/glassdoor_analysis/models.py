from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from typing import Any


@dataclass(slots=True)
class CompanySeed:
    display_name: str
    company_slug_hint: str | None = None
    glassdoor_slug_hint: str | None = None
    glassdoor_entity_hint: str | None = None
    priority: int | None = None
    review_url_hint: str | None = None
    office_locations_url: str | None = None


@dataclass(slots=True)
class RegionSeed:
    raw_label: str
    normalized_label: str
    country_or_macro_hint: str | None
    source: str


@dataclass(slots=True)
class OfficeLocationLink:
    label: str
    url: str


@dataclass(slots=True)
class OfficeLocationRecord:
    company: str
    raw_label: str
    normalized_label: str
    office_url: str
    source: str
    discovered_at: str

    @classmethod
    def create(cls, *, company: str, raw_label: str, normalized_label: str, office_url: str) -> "OfficeLocationRecord":
        return cls(
            company=company,
            raw_label=raw_label,
            normalized_label=normalized_label,
            office_url=office_url,
            source="office-location",
            discovered_at=datetime.now(UTC).isoformat(),
        )


@dataclass(slots=True)
class ReviewUrlRecord:
    company: str
    requested_region: str
    normalized_region: str
    region_source: str
    office_label: str | None
    office_url: str | None
    review_url: str | None
    status: str
    failure_reason: str | None
    discovery_mode: str
    resolved_at: str

    @classmethod
    def create(
        cls,
        *,
        company: str,
        requested_region: str,
        normalized_region: str,
        region_source: str,
        office_label: str | None,
        office_url: str | None,
        review_url: str | None,
        status: str,
        discovery_mode: str,
        failure_reason: str | None = None,
    ) -> "ReviewUrlRecord":
        return cls(
            company=company,
            requested_region=requested_region,
            normalized_region=normalized_region,
            region_source=region_source,
            office_label=office_label,
            office_url=office_url,
            review_url=review_url,
            status=status,
            failure_reason=failure_reason,
            discovery_mode=discovery_mode,
            resolved_at=datetime.now(UTC).isoformat(),
        )


@dataclass(slots=True)
class SessionConfig:
    cookies: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ReviewMetrics:
    overall: str | None = None
    recommend: str | None = None
    ceo_approval: str | None = None
    total_reviews: str | None = None
    diversity_inclusion: str | None = None
    work_life_balance: str | None = None
    compensation_benefits: str | None = None
    culture_values: str | None = None
    career_opportunities: str | None = None
    senior_management: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    missing_field_reasons: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PageValidationResult:
    is_valid: bool
    status: str
    header_text: str
    observed_region: str | None
    failure_reason: str | None = None


@dataclass(slots=True)
class AggregateRecord:
    company: str
    requested_region: str
    resolved_region: str
    country: str | None
    review_url: str
    overall: str | None
    recommend: str | None
    ceo_approval: str | None
    total_reviews: str | None
    diversity_inclusion: str | None
    work_life_balance: str | None
    compensation_benefits: str | None
    culture_values: str | None
    career_opportunities: str | None
    senior_management: str | None
    header_text: str
    scraped_at: str
    company_input_source: str
    region_source: str
    validation_status: str

    @classmethod
    def from_metrics(
        cls,
        *,
        company: str,
        requested_region: str,
        resolved_region: str,
        country: str | None,
        review_url: str,
        header_text: str,
        company_input_source: str,
        region_source: str,
        validation_status: str,
        metrics: ReviewMetrics,
    ) -> "AggregateRecord":
        return cls(
            company=company,
            requested_region=requested_region,
            resolved_region=resolved_region,
            country=country,
            review_url=review_url,
            overall=metrics.overall,
            recommend=metrics.recommend,
            ceo_approval=metrics.ceo_approval,
            total_reviews=metrics.total_reviews,
            diversity_inclusion=metrics.diversity_inclusion,
            work_life_balance=metrics.work_life_balance,
            compensation_benefits=metrics.compensation_benefits,
            culture_values=metrics.culture_values,
            career_opportunities=metrics.career_opportunities,
            senior_management=metrics.senior_management,
            header_text=header_text,
            scraped_at=datetime.now(UTC).isoformat(),
            company_input_source=company_input_source,
            region_source=region_source,
            validation_status=validation_status,
        )


@dataclass(slots=True)
class AttemptLogEntry:
    company: str
    requested_region: str
    candidate_url: str
    final_url: str
    status: str
    failure_reason: str | None
    header_text: str
    observed_region: str | None
    missing_fields: str | None
    missing_field_reasons: str | None
    timestamp: str

    @classmethod
    def create(
        cls,
        *,
        company: str,
        requested_region: str,
        candidate_url: str,
        final_url: str,
        status: str,
        failure_reason: str | None,
        header_text: str,
        observed_region: str | None,
        missing_fields: str | None = None,
        missing_field_reasons: str | None = None,
    ) -> "AttemptLogEntry":
        return cls(
            company=company,
            requested_region=requested_region,
            candidate_url=candidate_url,
            final_url=final_url,
            status=status,
            failure_reason=failure_reason,
            header_text=header_text,
            observed_region=observed_region,
            missing_fields=missing_fields,
            missing_field_reasons=missing_field_reasons,
            timestamp=datetime.now(UTC).isoformat(),
        )


@dataclass(slots=True)
class RunSummary:
    company_count: int
    region_candidate_count: int
    success_count: int
    output_record_count: int
    validation_failure_count: int
    no_result_count: int
    error_count: int


def dataclass_to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
