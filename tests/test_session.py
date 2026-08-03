from __future__ import annotations

from pathlib import Path
import shutil
import unittest

from glassdoor_analysis.session import load_session_config, parse_session_payload


RUNTIME_DIR = Path(__file__).resolve().parents[1] / "test-session-runtime"


class SessionTests(unittest.TestCase):
    def test_parse_session_payload_with_cookie_dict(self) -> None:
        session = parse_session_payload(
            {
                "cookies": {"tldp": "abc", "sess": "xyz"},
                "headers": {"User-Agent": "test-agent"},
            }
        )
        self.assertEqual(session.cookies["tldp"], "abc")
        self.assertEqual(session.headers["User-Agent"], "test-agent")

    def test_parse_session_payload_with_cookie_array(self) -> None:
        session = parse_session_payload(
            {
                "cookies": [
                    {"name": "tldp", "value": "abc"},
                    {"name": "sess", "value": "xyz"},
                ]
            }
        )
        self.assertEqual(session.cookies, {"tldp": "abc", "sess": "xyz"})

    def test_parse_session_payload_with_top_level_cookie_array(self) -> None:
        session = parse_session_payload(
            [
                {"name": "tldp", "value": "abc"},
                {"name": "sess", "value": "xyz"},
            ]
        )
        self.assertEqual(session.cookies, {"tldp": "abc", "sess": "xyz"})

    def test_parse_session_payload_rejects_invalid_cookie_entry(self) -> None:
        with self.assertRaises(ValueError):
            parse_session_payload({"cookies": [{"name": "tldp"}]})

    def test_load_session_config_supports_cookie_header_text(self) -> None:
        session_path = RUNTIME_DIR / "session.txt"
        try:
            RUNTIME_DIR.mkdir(exist_ok=True)
            session_path.write_text("tldp=abc; sess=xyz", encoding="utf-8")
            session = load_session_config(str(session_path))
            self.assertEqual(session.cookies, {"tldp": "abc", "sess": "xyz"})
        finally:
            shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def test_load_session_config_supports_browser_export_json(self) -> None:
        session_path = RUNTIME_DIR / "session.json"
        try:
            RUNTIME_DIR.mkdir(exist_ok=True)
            session_path.write_text(
                '[{"name":"tldp","value":"abc"},{"name":"sess","value":"xyz"}]',
                encoding="utf-8",
            )
            session = load_session_config(str(session_path))
            self.assertEqual(session.cookies, {"tldp": "abc", "sess": "xyz"})
        finally:
            shutil.rmtree(RUNTIME_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
