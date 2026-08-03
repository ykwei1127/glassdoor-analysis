from __future__ import annotations

import re

from .models import PageValidationResult, ReviewMetrics
from .normalization import normalize_region_label, region_matches


def validate_review_page(
    *,
    company_name: str,
    requested_region: str,
    header_text: str,
    metrics: ReviewMetrics,
) -> PageValidationResult:
    normalized_header = normalize_region_label(header_text)
    company_token = normalize_region_label(company_name)
    if company_token not in normalized_header:
        return PageValidationResult(
            is_valid=False,
            status="validation_failed",
            header_text=header_text,
            observed_region=None,
            failure_reason="company_mismatch",
        )

    observed_region = infer_region_from_header(company_name, header_text)
    if not region_matches(requested_region, observed_region):
        return PageValidationResult(
            is_valid=False,
            status="validation_failed",
            header_text=header_text,
            observed_region=observed_region,
            failure_reason="region_mismatch",
        )

    if metrics.overall is None:
        return PageValidationResult(
            is_valid=False,
            status="validation_failed",
            header_text=header_text,
            observed_region=observed_region,
            failure_reason="missing_target_metrics",
        )

    return PageValidationResult(
        is_valid=True,
        status="validated",
        header_text=header_text,
        observed_region=observed_region,
    )


def infer_region_from_header(company_name: str, header_text: str) -> str | None:
    pattern = rf"^{re.escape(company_name)}\s*(.*?)\s*reviews$"
    match = re.match(pattern, header_text, flags=re.IGNORECASE)
    if not match:
        return None
    region = match.group(1).strip()
    if not region:
        return "Global"
    return region

