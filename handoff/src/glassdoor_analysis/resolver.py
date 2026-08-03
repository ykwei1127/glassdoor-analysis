from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import unquote, urlparse

from .models import CompanySeed, RegionSeed
from .normalization import normalize_region_label


@dataclass(slots=True)
class ReviewCandidate:
    candidate_url: str
    discovery_mode: str


@dataclass(slots=True)
class PoolLocationHint:
    region_slug: str
    location_id: str
    source_office_url: str


def build_pool_gap_review_url(company: CompanySeed, source_office_url: str) -> str | None:
    company_slug_hint = company.glassdoor_slug_hint or company.company_slug_hint
    if not company_slug_hint or not company.glassdoor_entity_hint:
        return None
    location = extract_pool_location_hint(source_office_url)
    if location is None:
        return None

    company_slug = slugify_glassdoor_fragment(company_slug_hint)
    entity_id = company.glassdoor_entity_hint.removeprefix("E")
    company_end = len(company_slug)
    region_start = company_end + 1
    region_end = region_start + len(location.region_slug)
    return (
        f"https://www.glassdoor.com/Reviews/{company_slug}-{location.region_slug}-Reviews-"
        f"EI_IE{entity_id}.0,{company_end}_IL.{region_start},{region_end}_IC{location.location_id}.htm"
    )


def extract_pool_location_hint(office_url: str) -> PoolLocationHint | None:
    path = unquote(urlparse(office_url).path)
    match = re.search(
        r"/Location/(All-.+?)-Office-Locations-EI_IE\d+\.\d+,\d+_IL\.(\d+),(\d+)_IC(\d+)\.htm$",
        path,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    location_path, start_text, end_text, location_id = match.groups()
    start = int(start_text)
    end = int(end_text)
    region_slug = location_path[start:end]
    if not region_slug:
        return None
    return PoolLocationHint(
        region_slug=region_slug,
        location_id=location_id,
        source_office_url=office_url,
    )


def build_direct_review_url(company: CompanySeed, region: RegionSeed) -> str | None:
    urls = build_direct_review_urls(company, region)
    if not urls:
        return None
    return urls[0]


def build_direct_review_urls(company: CompanySeed, region: RegionSeed) -> list[str]:
    company_slug_hint = company.glassdoor_slug_hint or company.company_slug_hint
    if not company_slug_hint or not company.glassdoor_entity_hint:
        return []

    company_slug = slugify_glassdoor_fragment(company_slug_hint)
    entity = company.glassdoor_entity_hint
    if region.normalized_label == "global":
        return [f"https://www.glassdoor.com/Reviews/{company_slug}-Reviews-{entity}.htm"]

    urls: list[str] = []
    seen: set[str] = set()
    for region_variant in _region_direct_url_terms(region):
        region_slug = slugify_glassdoor_fragment(region_variant)
        url = f"https://www.glassdoor.com/Reviews/{company_slug}-{region_slug}-Reviews-{entity}.htm"
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def slugify_glassdoor_fragment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    return cleaned


def _region_direct_url_terms(region: RegionSeed) -> list[str]:
    if region.normalized_label == "global":
        return ["Global"]

    terms: list[str] = []
    for value in (region.raw_label, _titleize_normalized_label(region.normalized_label)):
        if value and value not in terms:
            terms.append(value)
    return terms


def _titleize_normalized_label(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(part.capitalize() for part in value.split())

