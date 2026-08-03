from __future__ import annotations

from .models import CompanySeed, RegionSeed
from .normalization import normalize_region_label


COMPANY_SEEDS: list[CompanySeed] = [
    CompanySeed(
        display_name="ASUS",
        company_slug_hint="ASUS",
        glassdoor_entity_hint="E40093",
        priority=1,
        review_url_hint="https://www.glassdoor.com/Reviews/ASUS-Reviews-E40093.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-ASUS-Office-Locations-E40093.htm",
    ),
    CompanySeed(
        display_name="NVIDIA",
        company_slug_hint="NVIDIA",
        glassdoor_entity_hint="E7633",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/NVIDIA-Reviews-E7633.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-NVIDIA-Office-Locations-E7633.htm",
    ),
    CompanySeed(
        display_name="TSMC",
        company_slug_hint="TSMC",
        glassdoor_entity_hint="E4130",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/TSMC-Reviews-E4130.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-TSMC-Office-Locations-E4130.htm",
    ),
    CompanySeed(
        display_name="Micro-Star International",
        company_slug_hint="MSI",
        glassdoor_slug_hint="Micro-Star-International",
        glassdoor_entity_hint="E41141",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Micro-Star-International-Reviews-E41141.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Micro-Star-International-Office-Locations-E41141.htm",
    ),
    CompanySeed(
        display_name="HP Inc.",
        company_slug_hint="HP-Inc",
        glassdoor_entity_hint="E1093161",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/HP-Inc-Reviews-E1093161.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-HP-Inc-Office-Locations-E1093161.htm",
    ),
    CompanySeed(
        display_name="Quanta Computer",
        company_slug_hint="Quanta-Computer",
        glassdoor_entity_hint="E11939",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Quanta-Computer-Reviews-E11939.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Quanta-Computer-Office-Locations-E11939.htm",
    ),
    CompanySeed(
        display_name="Wistron",
        company_slug_hint="Wistron",
        glassdoor_entity_hint="E15218",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Wistron-Reviews-E15218.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Wistron-Office-Locations-E15218.htm",
    ),
    CompanySeed(
        display_name="Compal Electronics",
        company_slug_hint="Compal-Electronics",
        glassdoor_entity_hint="E13464",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Compal-Electronics-Reviews-E13464.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Compal-Electronics-Office-Locations-E13464.htm",
    ),
    CompanySeed(
        display_name="Wiwynn",
        company_slug_hint="Wiwynn",
        glassdoor_entity_hint="E1161475",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Wiwynn-Reviews-E1161475.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Wiwynn-Office-Locations-E1161475.htm",
    ),
    CompanySeed(
        display_name="Delta Electronics",
        company_slug_hint="Delta-Electronics",
        glassdoor_entity_hint="E41146",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Delta-Electronics-Reviews-E41146.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Delta-Electronics-Office-Locations-E41146.htm",
    ),
    CompanySeed(
        display_name="Inventec",
        company_slug_hint="Inventec",
        glassdoor_entity_hint="E13485",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Inventec-Reviews-E13485.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Inventec-Office-Locations-E13485.htm",
    ),
    CompanySeed(
        display_name="Pegatron",
        company_slug_hint="Pegatron",
        glassdoor_entity_hint="E337948",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Pegatron-Reviews-E337948.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Pegatron-Office-Locations-E337948.htm",
    ),
    CompanySeed(
        display_name="AU Optronics",
        company_slug_hint="AU-Optronics",
        glassdoor_entity_hint="E16126",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/AU-Optronics-Reviews-E16126.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-AU-Optronics-Office-Locations-E16126.htm",
    ),
    CompanySeed(
        display_name="Trend Micro Inc.",
        company_slug_hint="Trend-Micro",
        glassdoor_slug_hint="Trend-Micro-Inc",
        glassdoor_entity_hint="E8983",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Trend-Micro-Inc-Reviews-E8983.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Trend-Micro-Inc-Office-Locations-E8983.htm",
    ),
    CompanySeed(
        display_name="Dell Technologies",
        company_slug_hint="Dell-Technologies",
        glassdoor_entity_hint="E1327",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Dell-Technologies-Reviews-E1327.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Dell-Technologies-Office-Locations-E1327.htm",
    ),
    CompanySeed(
        display_name="Acer Group",
        company_slug_hint="Acer-Group",
        glassdoor_entity_hint="E3802",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Acer-Group-Reviews-E3802.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Acer-Group-Office-Locations-E3802.htm",
    ),
    CompanySeed(
        display_name="Lenovo",
        company_slug_hint="Lenovo",
        glassdoor_entity_hint="E8034",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Lenovo-Reviews-E8034.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Lenovo-Office-Locations-E8034.htm",
    ),
    CompanySeed(
        display_name="Google",
        company_slug_hint="Google",
        glassdoor_entity_hint="E9079",
        priority=2,
        review_url_hint="https://www.glassdoor.com/Reviews/Google-Reviews-E9079.htm",
        office_locations_url="https://www.glassdoor.com/Location/All-Google-Office-Locations-E9079.htm",
    ),
]


_MANUAL_REGIONS = [
    ("Global", "Global"),
    ("Taipei", "Taiwan"),
    ("Hsinchu", "Taiwan"),
    ("Taoyuan", "Taiwan"),
    ("Shanghai", "APAC"),
    ("Shenzhen", "APAC"),
    ("Singapore", "APAC"),
    ("Tokyo", "APAC"),
    ("Seoul", "APAC"),
    ("Austin", "Americas"),
    ("San Jose", "Americas"),
    ("Seattle", "Americas"),
    ("London", "EMEA"),
    ("Dublin", "EMEA"),
    ("Munich", "EMEA"),
]


def manual_region_seeds() -> list[RegionSeed]:
    seeds: list[RegionSeed] = []
    for raw_label, macro_hint in _MANUAL_REGIONS:
        normalized = normalize_region_label(raw_label)
        seeds.append(
            RegionSeed(
                raw_label=raw_label,
                normalized_label=normalized,
                country_or_macro_hint=macro_hint,
                source="manual-seed",
            )
        )
    return seeds
