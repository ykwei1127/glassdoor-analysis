from __future__ import annotations

import re


def normalize_region_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    aliases = {
        "taipei city": "taipei",
        "new taipei": "taipei",
        "hsinchu city": "hsinchu",
        "san jose ca": "san jose",
        "global": "global",
    }
    return aliases.get(normalized, normalized)


def region_matches(expected_region: str, observed_region: str | None) -> bool:
    expected = normalize_region_label(expected_region)
    observed = normalize_region_label(observed_region or "")
    if expected == "global":
        return observed in {"", "global"}
    if expected == observed:
        return True
    if expected.startswith(observed) and observed:
        return True
    if observed.startswith(expected) and expected:
        return True
    return False
