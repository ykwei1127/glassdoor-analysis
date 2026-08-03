from __future__ import annotations

import json
from pathlib import Path

from .models import SessionConfig


def load_session_config(path: str | None) -> SessionConfig:
    if not path:
        return SessionConfig()

    session_path = Path(path)
    raw_text = session_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return SessionConfig()

    if raw_text.startswith("{") or raw_text.startswith("["):
        payload = json.loads(raw_text)
        return parse_session_payload(payload)

    cookies: dict[str, str] = {}
    for chunk in raw_text.split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        cookies[key.strip()] = value.strip()
    return SessionConfig(cookies=cookies)


def parse_session_payload(payload: object) -> SessionConfig:
    if isinstance(payload, list):
        return SessionConfig(cookies=_parse_cookie_collection(payload))

    if not isinstance(payload, dict):
        raise ValueError("Session payload must be a JSON object, JSON array, or cookie header string.")

    raw_cookies = payload.get("cookies", {})
    raw_headers = payload.get("headers", {})
    if not isinstance(raw_headers, dict):
        raise ValueError("Session headers must be a JSON object.")

    return SessionConfig(
        cookies=_parse_cookie_collection(raw_cookies),
        headers={str(k): str(v) for k, v in raw_headers.items()},
    )


def _parse_cookie_collection(raw_cookies: object) -> dict[str, str]:
    if isinstance(raw_cookies, dict):
        return {str(k): str(v) for k, v in raw_cookies.items()}

    if isinstance(raw_cookies, list):
        cookies: dict[str, str] = {}
        for cookie in raw_cookies:
            if not isinstance(cookie, dict):
                raise ValueError("Each cookie entry must be a JSON object.")
            name = cookie.get("name")
            value = cookie.get("value")
            if not name or value is None:
                raise ValueError("Each cookie entry must include both 'name' and 'value'.")
            cookies[str(name)] = str(value)
        return cookies

    raise ValueError("Cookies must be a JSON object or an array of cookie objects.")
