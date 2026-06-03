from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class PsmGoogleGeocodeServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("psm_google_geocode_server.py")

    def _response(self, payload: dict):
        wrapper = io.BytesIO(json.dumps(payload).encode("utf-8"))
        wrapper.__enter__ = lambda self: self  # type: ignore[attr-defined]
        wrapper.__exit__ = lambda self, *args: None  # type: ignore[attr-defined]
        return wrapper

    def test_load_api_key_from_local_credentials_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "credentials.json"
            path.write_text(json.dumps({"google_geocoding_api_key": "secret-key"}), encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_GEOCODING_API_KEY": "",
                    "PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE": str(path),
                },
                clear=False,
            ):
                api_key, source = self.module._load_api_key()
        self.assertEqual(api_key, "secret-key")
        self.assertIn("file:", source)

    def test_normalize_address_rows_deduplicates_and_rejects_empty(self):
        rows = self.module._normalize_address_rows(
            [
                {"label": "A", "address": "  1 Raffles Place, Singapore  "},
                "1 Raffles Place, Singapore",
                {"address": ""},
                {"outlet_address": "10 Anson Road Singapore"},
            ]
        )
        self.assertEqual([row["address"] for row in rows], ["1 Raffles Place, Singapore", "10 Anson Road Singapore"])

    def test_geocode_slack_addresses_returns_safe_rows(self):
        captured_urls: list[str] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            return self._response(
                {
                    "status": "OK",
                    "results": [
                        {
                            "formatted_address": "1 Raffles Pl, Singapore",
                            "place_id": "place-1",
                            "geometry": {"location": {"lat": 1.2847, "lng": 103.851}},
                        }
                    ],
                }
            )

        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = self.module.geocode_slack_addresses(
                    [{"address": "1 Raffles Place, Singapore"}],
                    region_bias="sg",
                    country_restriction="SG",
                    language="en",
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1",
                )

        self.assertEqual(result["confidence"], "verified")
        row = result["answer"]["rows"][0]
        self.assertEqual(row["latitude"], 1.2847)
        self.assertEqual(row["longitude"], 103.851)
        self.assertNotIn("secret-key", json.dumps(result))
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(captured_urls[0]).query)
        self.assertEqual(parsed["region"], ["sg"])
        self.assertEqual(parsed["components"], ["country:SG"])

    def test_check_google_geocode_access_does_not_call_api(self):
        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen") as urlopen:
                result = self.module.check_google_geocode_access()
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(urlopen.call_count, 0)
        self.assertNotIn("secret-key", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
