from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import RegionSeed
from .normalization import normalize_region_label


_REGIONS_BY_COUNTRY: dict[str, set[str]] = {
    "Argentina": {"buenos aires c", "mart nez b", "vicente l pez b"},
    "Australia": {"notting hill vic", "sydney nsw"},
    "Brazil": {"campinas sp", "indaiatuba sp", "itu sp", "s o paulo sp", "sorocaba sp"},
    "Canada": {"kanata on", "markham on", "toronto on"},
    "Chile": {"santiago rm"},
    "China": {
        "beijing 22",
        "changping 22",
        "haidian 22",
        "pudong 23",
        "shanghai",
        "shanghai 23",
        "shenzhen",
        "shenzhenzhen 02",
        "wuhan 12",
        "xiamen 07",
    },
    "Costa Rica": {"san jose mp"},
    "Czechia": {"moravsk ostrava mo"},
    "France": {"boulogne billancourt a8", "meudon a8", "noisy le grand a8", "paris a8"},
    "Germany": {"frankfurt am main he", "munich", "munich by", "ratingen nw", "stuttgart bw"},
    "Global": {"global"},
    "Hong Kong": {"hong kong"},
    "Hungary": {"budapest bu"},
    "India": {"bengaluru ka", "domlur ka", "mumbai mh", "pune mh", "whitefield ka"},
    "Indonesia": {"jakarta jk"},
    "Ireland": {"cork m", "dublin"},
    "Italy": {"milan lom"},
    "Japan": {"tokyo", "tokyo 40"},
    "Malaysia": {"kuala lumpur 14"},
    "Mexico": {"ciudad de mexico mex", "guadalajara jal", "tlaquepaque jal", "zapopan jal"},
    "Netherlands": {"emmen dr", "hoofddorp nh"},
    "Peru": {"san isidro huc"},
    "Philippines": {"manila d9"},
    "Poland": {"warsaw mz"},
    "Romania": {"bucharest b"},
    "Russia": {"moscow 48"},
    "Singapore": {"singapore", "tuas w"},
    "Slovakia": {"bratislava 02"},
    "South Korea": {"seoul", "seoul 11"},
    "Spain": {"barcelona ct", "sant cugat del vall s ct"},
    "Switzerland": {"z rich zh"},
    "Taiwan": {"hsinchu", "hsinchu txg", "taipei", "taipei tpq", "taoyuan"},
    "Thailand": {"bangkok 10"},
    "Turkey": {"sk dar t34"},
    "United Arab Emirates": {"dubai du"},
    "United Kingdom": {
        "cambridge eng",
        "hemel hempstead eng",
        "london",
        "london eng",
        "paddington eng",
        "reading eng",
    },
    "United States": {
        "aliso ca",
        "austin",
        "austin tx",
        "beaverton or",
        "bedford ma",
        "bellevue wa",
        "boise id",
        "boston ma",
        "boydton va",
        "cambridge ma",
        "canada ky",
        "canton ma",
        "cedar park tx",
        "chicago il",
        "corvallis or",
        "durham nc",
        "fort collins co",
        "framingham ma",
        "franklin ma",
        "fremont ca",
        "fuquay varina nc",
        "georgetown tx",
        "hillsboro or",
        "hopkinton ma",
        "houston tx",
        "india tx",
        "irving tx",
        "jeffersonville in",
        "jersey city nj",
        "lake forest ca",
        "land o lakes fl",
        "leander tx",
        "morrisville nc",
        "palo alto ca",
        "pflugerville tx",
        "portland or",
        "quincy ma",
        "redmond wa",
        "rolling meadows il",
        "round rock tx",
        "saint louis mo",
        "san diego ca",
        "san francisco ca",
        "san jose",
        "san marcos tx",
        "santa clara ca",
        "satellite beach fl",
        "seattle",
        "spring tx",
        "sunnyvale ca",
        "vancouver wa",
        "wellesley ma",
        "westford ma",
    },
}


REGION_COUNTRY_MAP = {
    normalized_region: country
    for country, normalized_regions in _REGIONS_BY_COUNTRY.items()
    for normalized_region in normalized_regions
}


def country_for_region_label(region_label: str) -> str | None:
    return REGION_COUNTRY_MAP.get(normalize_region_label(region_label))


def country_for_region(region: RegionSeed) -> str | None:
    country = REGION_COUNTRY_MAP.get(region.normalized_label)
    if country:
        return country
    if region.country_or_macro_hint not in {None, "APAC", "Americas", "EMEA"}:
        return region.country_or_macro_hint
    return None


def save_region_country_map(path: Path, regions: list[RegionSeed]) -> None:
    rows = [
        {
            "raw_label": region.raw_label,
            "normalized_label": region.normalized_label,
            "country": country_for_region(region),
        }
        for region in regions
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with path.with_suffix(".csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["raw_label", "normalized_label", "country"])
        writer.writeheader()
        writer.writerows(rows)
