from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin

from .models import OfficeLocationLink, ReviewMetrics


def extract_office_locations(html_text: str) -> list[str]:
    matches = re.findall(r'data-test="office-location"[^>]*>(.*?)<', html_text, flags=re.IGNORECASE | re.DOTALL)
    if not matches:
        matches = re.findall(r'<li[^>]*class="[^"]*office-location[^"]*"[^>]*>(.*?)</li>', html_text, flags=re.IGNORECASE | re.DOTALL)
    if not matches:
        matches = re.findall(
            r'data-test="location-row"[^>]*>.*?LocationRow_cityName[^>]*>(.*?)</span>',
            html_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return _clean_text_list(matches)


def extract_office_location_links(html_text: str, base_url: str) -> list[OfficeLocationLink]:
    matches = re.findall(
        r'<a[^>]*data-test="location-row"[^>]*href="([^"]+)"[^>]*>.*?LocationRow_cityName[^>]*>(.*?)</span>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    links: list[OfficeLocationLink] = []
    seen_urls: set[str] = set()
    for href, label in matches:
        url = urljoin(base_url, html.unescape(href))
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append(OfficeLocationLink(label=_clean_text(label), url=url))
    return links


def extract_review_links(html_text: str, base_url: str) -> list[str]:
    hrefs = re.findall(r'href="([^"]*Reviews/[^"]+)"', html_text, flags=re.IGNORECASE)
    unique: list[str] = []
    for href in hrefs:
        url = urljoin(base_url, html.unescape(href))
        if url not in unique:
            unique.append(url)
    return unique


def extract_office_review_links(html_text: str, base_url: str) -> list[str]:
    patterns = [
        r'<a[^>]*class="[^"]*LocationReview_headerLink[^"]*"[^>]*href="([^"]+)"[^>]*>.*?reviews in',
        r'<a[^>]*href="([^"]*Reviews/[^"]+)"[^>]*>.*?reviews in',
    ]
    for pattern in patterns:
        hrefs = re.findall(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if hrefs:
            return _unique_joined_urls(hrefs, base_url)
    return []


def extract_header_text(html_text: str) -> str:
    patterns = [
        r'data-test="employerReviewsHeader"[^>]*>(.*?)<',
        r'<h1[^>]*>(.*?)</h1>',
        r'"pageHeader"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group(1))
    return ""


def extract_metrics(html_text: str) -> ReviewMetrics:
    metrics = ReviewMetrics()
    unescaped_html = html.unescape(html_text)
    invalid_fields: set[str] = set()

    json_blob = _extract_json_payload(html_text)
    if json_blob:
        metrics.overall = _first_value(json_blob, ["overallRating", "ratingOverall"])
        metrics.recommend = _first_value(json_blob, ["recommendToFriend", "ratingRecommendToFriend"])
        metrics.ceo_approval = _first_value(json_blob, ["ceoApproval", "ratingCeo"])
        metrics.total_reviews = _first_value(json_blob, ["reviewCount", "totalReviews"])
        metrics.diversity_inclusion = _first_value(json_blob, ["diversityAndInclusionRating"])
        metrics.work_life_balance = _first_value(json_blob, ["workLifeBalanceRating"])
        metrics.compensation_benefits = _first_value(json_blob, ["compensationAndBenefitsRating"])
        metrics.culture_values = _first_value(json_blob, ["cultureAndValuesRating"])
        metrics.career_opportunities = _first_value(json_blob, ["careerOpportunitiesRating"])
        metrics.senior_management = _first_value(json_blob, ["seniorManagementRating"])
        invalid_fields.update(_clear_invalid_metric_values(metrics))

    flight_ratings = _extract_next_flight_ratings(html_text)
    if flight_ratings:
        metrics.overall = _number_as_text(flight_ratings.get("overallRating"))
        metrics.recommend = _fraction_as_percent(flight_ratings.get("recommendToFriendRating"))
        metrics.ceo_approval = _fraction_as_percent(flight_ratings.get("ceoRating"))
        metrics.total_reviews = _number_as_text(flight_ratings.get("reviewCount"))
        metrics.diversity_inclusion = _number_as_text(flight_ratings.get("diversityAndInclusionRating"))
        metrics.work_life_balance = _number_as_text(flight_ratings.get("workLifeBalanceRating"))
        metrics.compensation_benefits = _number_as_text(flight_ratings.get("compensationAndBenefitsRating"))
        metrics.culture_values = _number_as_text(flight_ratings.get("cultureAndValuesRating"))
        metrics.career_opportunities = _number_as_text(flight_ratings.get("careerOpportunitiesRating"))
        metrics.senior_management = _number_as_text(flight_ratings.get("seniorManagementRating"))

    category_ratings = _extract_category_ratings(unescaped_html)
    for field_name, value in category_ratings.items():
        if getattr(metrics, field_name) is None:
            setattr(metrics, field_name, value)

    label_map = {
        "overall": "Overall",
        "recommend": "Recommend",
        "ceo_approval": "CEO Approval",
        "total_reviews": "Total Reviews",
        "diversity_inclusion": "Diversity & Inclusion",
        "work_life_balance": "Work/Life Balance",
        "compensation_benefits": "Compensation and Benefits",
        "culture_values": "Culture & Values",
        "career_opportunities": "Career Opportunities",
        "senior_management": "Senior Management",
    }
    for field_name, label in label_map.items():
        current_value = getattr(metrics, field_name)
        if current_value is None:
            setattr(metrics, field_name, _extract_labeled_value(unescaped_html, label))

    live_page_fallbacks = {
        "overall": _extract_live_review_overall(unescaped_html),
        "recommend": _extract_live_review_percent(unescaped_html, "recommendToFriend", "would recommend to a friend"),
        "ceo_approval": _extract_live_review_percent(unescaped_html, "ceoApproval", "approve of CEO"),
        "total_reviews": _extract_live_total_reviews(unescaped_html),
    }
    for field_name, value in live_page_fallbacks.items():
        if getattr(metrics, field_name) is None and value is not None:
            setattr(metrics, field_name, value)

    invalid_fields.update(_clear_invalid_metric_values(metrics))
    for field_name, label in label_map.items():
        if getattr(metrics, field_name) is None:
            metrics.missing_fields.append(field_name)
            metrics.missing_field_reasons[field_name] = (
                "invalid_value" if field_name in invalid_fields else _classify_missing_field(unescaped_html, label)
            )
    return metrics


def _clear_invalid_metric_values(metrics: ReviewMetrics) -> set[str]:
    rating_fields = {
        "overall",
        "diversity_inclusion",
        "work_life_balance",
        "compensation_benefits",
        "culture_values",
        "career_opportunities",
        "senior_management",
    }
    percent_fields = {"recommend", "ceo_approval"}
    invalid: set[str] = set()
    for field_name in rating_fields | percent_fields | {"total_reviews"}:
        value = getattr(metrics, field_name)
        if value is None:
            continue
        if field_name in rating_fields:
            is_valid = _is_number_in_range(value, minimum=0, maximum=5)
        elif field_name in percent_fields:
            is_valid = bool(re.fullmatch(r"\d+(?:\.\d+)?%", value)) and _is_number_in_range(
                value[:-1], minimum=0, maximum=100
            )
        else:
            is_valid = bool(re.fullmatch(r"\d[\d,]*", value))
        if not is_valid:
            setattr(metrics, field_name, None)
            invalid.add(field_name)
    return invalid


def _extract_next_flight_ratings(html_text: str) -> dict[str, object] | None:
    script_pattern = r'<script[^>]*>\s*(self\.__next_f\.push\(\[1,.*?\]\))\s*</script>'
    for script_call in re.findall(script_pattern, html_text, flags=re.DOTALL):
        argument_match = re.fullmatch(r'self\.__next_f\.push\((\[1,.*\])\)', script_call, flags=re.DOTALL)
        if not argument_match:
            continue
        try:
            flight_entry = json.loads(argument_match.group(1))
        except json.JSONDecodeError:
            continue
        if len(flight_entry) < 2 or not isinstance(flight_entry[1], str):
            continue
        ratings_match = re.search(r'"ratings":\{(.*?)\},"reviews":', flight_entry[1], flags=re.DOTALL)
        if not ratings_match:
            continue
        ratings: dict[str, object] = {}
        for key in (
            "careerOpportunitiesRating",
            "ceoRating",
            "compensationAndBenefitsRating",
            "cultureAndValuesRating",
            "diversityAndInclusionRating",
            "overallRating",
            "recommendToFriendRating",
            "reviewCount",
            "seniorManagementRating",
            "workLifeBalanceRating",
        ):
            value_match = re.search(
                rf'"{re.escape(key)}":(null|true|false|-?\d+(?:\.\d+)?|"(?:\\.|[^"\\])*")',
                ratings_match.group(1),
            )
            if value_match:
                ratings[key] = json.loads(value_match.group(1))
        filtered_count_matches = re.findall(
            r'"filteredReviewsCount":(\d+)',
            flight_entry[1][: ratings_match.start()],
        )
        if filtered_count_matches:
            ratings["reviewCount"] = int(filtered_count_matches[-1])
        if ratings:
            return ratings
    return None


def _extract_category_ratings(unescaped_html: str) -> dict[str, str]:
    label_to_field = {
        "diversity & inclusion": "diversity_inclusion",
        "work/life balance": "work_life_balance",
        "compensation and benefits": "compensation_benefits",
        "culture & values": "culture_values",
        "career opportunities": "career_opportunities",
        "senior management": "senior_management",
    }
    item_pattern = (
        r'<div[^>]*class="[^"]*RatingsByCategory_ratingItem[^"]*"[^>]*>'
        r'.*?<p[^>]*class="[^"]*RatingsByCategory_rating__[^"]*"[^>]*>\s*([0-5](?:\.\d+)?)\s*</p>'
        r'.*?<p[^>]*class="[^"]*RatingsByCategory_ratingLabel[^"]*"[^>]*>(.*?)</p>'
        r'.*?</div>'
    )
    ratings: dict[str, str] = {}
    for value, raw_label in re.findall(item_pattern, unescaped_html, flags=re.IGNORECASE | re.DOTALL):
        field_name = label_to_field.get(_clean_text(raw_label).lower())
        if field_name:
            ratings[field_name] = value
    return ratings


def _number_as_text(value: object | None) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _fraction_as_percent(value: object | None) -> str | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    percent = float(value) * 100 if 0 <= float(value) <= 1 else float(value)
    if not 0 <= percent <= 100:
        return None
    return f"{percent:g}%"


def _is_number_in_range(value: str, *, minimum: float, maximum: float) -> bool:
    try:
        number = float(value)
    except ValueError:
        return False
    return minimum <= number <= maximum


def _extract_json_payload(html_text: str) -> dict[str, str] | None:
    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>\s*(\{.*?\})\s*</script>', html_text, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    flattened: dict[str, str] = {}
    _flatten_json("", payload, flattened)
    return flattened


def _flatten_json(prefix: str, value: object, target: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten_json(key if not prefix else f"{prefix}.{key}", child, target)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _flatten_json(f"{prefix}[{index}]", child, target)
        return
    if prefix:
        target[prefix.split(".")[-1]] = str(value)


def _first_value(payload: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _extract_labeled_value(unescaped_html: str, label: str) -> str | None:
    pattern = rf'data-label="{re.escape(label)}"[^>]*data-value="([^"]+)"'
    match = re.search(pattern, unescaped_html, flags=re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))

    alt_pattern = rf'{re.escape(label)}\s*</[^>]+>\s*<[^>]+>\s*([^<]+)\s*<'
    match = re.search(alt_pattern, unescaped_html, flags=re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))
    return None


def _classify_missing_field(unescaped_html: str, label: str) -> str:
    if re.search(rf'data-label="{re.escape(label)}"', unescaped_html, flags=re.IGNORECASE):
        return "selector_failure"
    if re.search(re.escape(label), unescaped_html, flags=re.IGNORECASE):
        return "selector_failure"
    return "page_missing"


def _extract_live_review_overall(unescaped_html: str) -> str | None:
    patterns = [
        r'ReviewOverview_overallRating[^>]*>.*?aria-valuenow="([^"]+)"',
        r'ReviewOverview_overallRating[^>]*>.*?RatingText[^>]*>([^<]+)<',
        r'"ratingValue"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, unescaped_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group(1))
    return None


def _extract_live_review_percent(unescaped_html: str, data_test: str, suffix: str) -> str | None:
    patterns = [
        rf'data-test="{re.escape(data_test)}"[^>]*>\s*([^<]+?)\s*</',
        rf'(\d+%)\s+{re.escape(suffix)}',
    ]
    for pattern in patterns:
        match = re.search(pattern, unescaped_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            text = _clean_text(match.group(1))
            percent_match = re.search(r"\d+%", text)
            if percent_match:
                return percent_match.group(0)
    return None


def _extract_live_total_reviews(unescaped_html: str) -> str | None:
    patterns = [
        r'ReviewOverview_count[^>]*>\(([\d,]+)\s+total reviews',
        r'"ratingCount"\s*:\s*"([^"]+)"',
        r'\(([\d,]+)\s+total reviews\)',
    ]
    for pattern in patterns:
        match = re.search(pattern, unescaped_html, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return _clean_text(match.group(1))
    return None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _clean_text_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _unique_joined_urls(hrefs: list[str], base_url: str) -> list[str]:
    unique: list[str] = []
    for href in hrefs:
        url = urljoin(base_url, html.unescape(href))
        if url not in unique:
            unique.append(url)
    return unique
