from __future__ import annotations

from dataclasses import dataclass
import os
from http.cookiejar import Cookie, CookieJar
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from .models import SessionConfig


_BUNDLED_NODE_DIR = (
    Path.home()
    / ".cache"
    / "codex-runtimes"
    / "codex-primary-runtime"
    / "dependencies"
    / "node"
)
_BUNDLED_NODE_EXECUTABLE = _BUNDLED_NODE_DIR / "bin" / "node.exe"
_BUNDLED_NODE_MODULES = _BUNDLED_NODE_DIR / "node_modules"


class FetchError(RuntimeError):
    """Raised when an HTTP fetch fails."""


@dataclass(slots=True)
class FetchResponse:
    url: str
    status_code: int
    text: str


class UrlFetcher:
    def __init__(self, session: SessionConfig) -> None:
        self._cookie_jar = CookieJar()
        for key, value in session.cookies.items():
            self._cookie_jar.set_cookie(_build_cookie(key, value))
        self._headers = {
            "User-Agent": "glassdoor-analysis/0.1",
            **session.headers,
        }
        self._opener = build_opener(HTTPCookieProcessor(self._cookie_jar))

    def get(self, url: str) -> FetchResponse:
        request = Request(url, headers=self._headers)
        try:
            with self._opener.open(request) as response:
                body = response.read().decode("utf-8", errors="ignore")
                status_code = getattr(response, "status", 200)
                return FetchResponse(url=response.geturl(), status_code=status_code, text=body)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise FetchError(f"HTTP {exc.code} for {url}: {body[:200]}") from exc
        except URLError as exc:
            raise FetchError(f"Failed to fetch {url}: {exc.reason}") from exc


class BrowserCdpFetcher:
    def __init__(self, cdp_url: str, helper_script: Path | None = None) -> None:
        self._cdp_url = cdp_url
        self._helper_script = helper_script or Path(__file__).resolve().parents[2] / "scripts" / "fetch_via_cdp.cjs"
        if not self._helper_script.exists():
            raise ValueError(f"CDP helper script not found: {self._helper_script}")
        self._node_executable = _resolve_node_executable()
        self._node_path = _resolve_node_path()
        self._playwright_module = _resolve_playwright_module()

    def get(self, url: str) -> FetchResponse:
        env = os.environ.copy()
        env["NODE_PATH"] = self._node_path
        env["PLAYWRIGHT_MODULE"] = self._playwright_module
        result = subprocess.run(
            [self._node_executable, str(self._helper_script), self._cdp_url, url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            env=env,
        )
        if result.returncode != 0:
            error_text = (result.stderr or result.stdout).strip()
            raise FetchError(f"Browser CDP fetch failed for {url}: {error_text[:400]}")

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise FetchError(f"Browser CDP fetch returned invalid JSON for {url}") from exc

        return FetchResponse(
            url=str(payload["url"]),
            status_code=int(payload["status_code"]),
            text=str(payload["text"]),
        )


def _build_cookie(name: str, value: str) -> Cookie:
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=".glassdoor.com",
        domain_specified=True,
        domain_initial_dot=True,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
        rfc2109=False,
    )


def _resolve_node_executable() -> str:
    if _BUNDLED_NODE_EXECUTABLE.exists():
        return str(_BUNDLED_NODE_EXECUTABLE)
    return "node"


def _resolve_node_path() -> str:
    bundled_path = str(_BUNDLED_NODE_MODULES)
    existing = os.environ.get("NODE_PATH", "")
    if existing:
        return os.pathsep.join([bundled_path, existing])
    return bundled_path


def _resolve_playwright_module() -> str:
    candidates = sorted(_BUNDLED_NODE_MODULES.glob(".pnpm/playwright@*/node_modules/playwright"))
    if candidates:
        return str(candidates[-1])
    fallback = _BUNDLED_NODE_MODULES / "playwright"
    return str(fallback)
