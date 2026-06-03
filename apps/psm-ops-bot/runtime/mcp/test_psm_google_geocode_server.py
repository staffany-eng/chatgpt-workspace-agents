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
        wrapper.status = 200  # type: ignore[attr-defined]
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

    def test_unresolved_env_placeholders_fall_back_to_default_credentials_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".staffany" / "google-geocode" / "credentials.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"google_geocoding_api_key": "file-key"}), encoding="utf-8")
            with patch.dict(
                os.environ,
                {
                    "HOME": tmpdir,
                    "GOOGLE_GEOCODING_API_KEY": "${GOOGLE_GEOCODING_API_KEY}",
                    "PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE": "${PSM_OPS_GOOGLE_GEOCODE_CREDENTIALS_FILE}",
                    "GEOCODE_CREDENTIALS_FILE": "",
                },
                clear=False,
            ):
                api_key, source = self.module._load_api_key()
        self.assertEqual(api_key, "file-key")
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

    def test_normalize_address_rows_blocks_name_phone_and_vague_hint(self):
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["Rock Productions"])
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["+65 9123 4567"])
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["near Orchard"])

    def test_ambiguous_address_inputs_block_before_external_api(self):
        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key", "SLACK_BOT_TOKEN": "xoxb-secret"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen") as urlopen:
                result = self.module.geocode_slack_addresses(
                    ["Rock Productions", "+65 9123 4567", "near Orchard"],
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1234567890123456",
                )
        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(urlopen.call_count, 0)
        self.assertIn("No explicit postal address", result["answer"]["message"])

    def test_geocode_slack_addresses_uploads_tsv_and_returns_safe_summary(self):
        captured_urls: list[str] = []
        uploaded_bodies: list[bytes] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": True, "upload_url": "https://upload.slack.test/file", "file_id": "F123"})
            if "upload.slack.test" in request.full_url:
                uploaded_bodies.append(request.data)
                return self._response({})
            if "files.completeUploadExternal" in request.full_url:
                body = urllib.parse.parse_qs(request.data.decode("utf-8"))
                self.assertEqual(body["channel_id"], ["C123"])
                self.assertEqual(body["thread_ts"], ["1234567890.123456"])
                self.assertIn("psm-ops-geocoded-addresses-", body["files"][0])
                return self._response({"ok": True, "file": {"permalink": "https://slack/file/F123"}})
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

        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key", "SLACK_BOT_TOKEN": "xoxb-secret"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = self.module.geocode_slack_addresses(
                    [{"address": "1 Raffles Place, Singapore"}],
                    region_bias="sg",
                    country_restriction="SG",
                    language="en",
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1234567890123456",
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertNotIn("rows", result["answer"])
        self.assertEqual(result["answer"]["file"]["file_id"], "F123")
        self.assertEqual(result["answer"]["status_counts"], {"OK": 1})
        self.assertIn(b"address\tlatitude\tlongitude\tgeocode_status", uploaded_bodies[0])
        self.assertIn(b"1.2847\t103.851\tOK", uploaded_bodies[0])
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertNotIn("xoxb-secret", json.dumps(result))
        geocode_url = next(url for url in captured_urls if "maps.googleapis.com" in url)
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(geocode_url).query)
        self.assertEqual(parsed["region"], ["sg"])
        self.assertEqual(parsed["components"], ["country:SG"])

    def test_geocode_slack_addresses_blocks_instead_of_raw_reply_when_slack_upload_missing_scope(self):
        def fake_urlopen(request, timeout=None):
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": False, "error": "missing_scope"})
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

        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key", "SLACK_BOT_TOKEN": "xoxb-secret"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = self.module.geocode_slack_addresses(
                    [{"address": "1 Raffles Place, Singapore"}],
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1234567890123456",
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("files:write", result["answer"]["message"])
        self.assertNotIn("1.2847", json.dumps(result))

    def test_check_google_geocode_access_does_not_call_api(self):
        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen") as urlopen:
                result = self.module.check_google_geocode_access()
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(urlopen.call_count, 0)
        self.assertNotIn("secret-key", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
