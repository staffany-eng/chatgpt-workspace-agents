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

    def _bytes_response(self, payload: bytes):
        wrapper = io.BytesIO(payload)
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

    def test_normalize_address_rows_preserves_duplicate_inputs_and_rejects_empty(self):
        rows = self.module._normalize_address_rows(
            [
                {"label": "A", "address": "  1 Raffles Place, Singapore  "},
                "1 Raffles Place, Singapore",
                {"address": ""},
                {"outlet_address": "10 Anson Road Singapore"},
            ]
        )
        self.assertEqual(
            [row["address"] for row in rows],
            ["1 Raffles Place, Singapore", "1 Raffles Place, Singapore", "10 Anson Road Singapore"],
        )
        self.assertEqual([row["label"] for row in rows], ["A", "", ""])

    def test_normalize_address_rows_blocks_name_phone_and_vague_hint(self):
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["Rock Productions"])
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["+65 9123 4567"])
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "No explicit postal address"):
            self.module._normalize_address_rows(["near Orchard"])

    def test_parse_address_file_requires_address_column(self):
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "address column"):
            self.module._parse_address_file(b"customer\tpostal\nA\t1 Raffles Place, Singapore\n", filename="sample.tsv")

    def test_parse_address_file_rejects_empty_address_row(self):
        with self.assertRaisesRegex(self.module.GoogleGeocodeError, "sample.tsv: row 3"):
            self.module._parse_address_file(
                b"customer\taddress\nOutlet A\t1 Raffles Place, Singapore\nOutlet B\t\n",
                filename="sample.tsv",
            )

    def test_parse_address_file_preserves_metadata(self):
        rows = self.module._parse_address_file(
            b"customer\taddress\tsource\nOutlet A\t1 Raffles Place, Singapore\trow-a\n",
            filename="sample.tsv",
            mimetype="text/tab-separated-values",
        )
        self.assertEqual(rows, [{"address": "1 Raffles Place, Singapore", "label": "Outlet A", "source": "row-a"}])

    def test_download_slack_file_rejects_untrusted_hosts_before_token_lookup(self):
        with patch.object(self.module, "_slack_token", side_effect=AssertionError("token lookup should not run")):
            with self.assertRaisesRegex(self.module.GoogleGeocodeError, "trusted Slack file host"):
                self.module._download_slack_file("https://example.com/addresses.tsv")

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
        self.assertIn(b"label\tsource\taddress\tlatitude\tlongitude\tgeocode_status", uploaded_bodies[0])
        self.assertIn(b"1.2847\t103.851\tOK", uploaded_bodies[0])
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertNotIn("xoxb-secret", json.dumps(result))
        geocode_url = next(url for url in captured_urls if "maps.googleapis.com" in url)
        self.assertEqual(sum(1 for url in captured_urls if "files.getUploadURLExternal" in url), 2)
        self.assertLess(
            next(index for index, url in enumerate(captured_urls) if "files.getUploadURLExternal" in url),
            captured_urls.index(geocode_url),
        )
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(geocode_url).query)
        self.assertEqual(parsed["region"], ["sg"])
        self.assertEqual(parsed["components"], ["country:SG"])

    def test_geocode_slack_addresses_marks_partial_match_for_review(self):
        uploaded_bodies: list[bytes] = []

        def fake_urlopen(request, timeout=None):
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": True, "upload_url": "https://upload.slack.test/file", "file_id": "F123"})
            if "upload.slack.test" in request.full_url:
                uploaded_bodies.append(request.data)
                return self._response({})
            if "files.completeUploadExternal" in request.full_url:
                body = urllib.parse.parse_qs(request.data.decode("utf-8"))
                self.assertIn("Geocoded 0/1 address rows", body["initial_comment"][0])
                return self._response({"ok": True, "file": {"permalink": "https://slack/file/F123"}})
            return self._response(
                {
                    "status": "OK",
                    "results": [
                        {
                            "formatted_address": "1 Raffles Pl, Singapore",
                            "place_id": "place-1",
                            "partial_match": True,
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

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "needs-check")
        self.assertEqual(result["answer"]["ok_count"], 0)
        self.assertEqual(result["answer"]["total_count"], 1)
        self.assertEqual(result["answer"]["status_counts"], {"OK": 1})
        self.assertIn("(0/1 OK)", result["answer"]["slack_reply"])
        self.assertIn("partial_match=true", result["caveat"])
        self.assertIn(b"\ttrue\t", uploaded_bodies[0])

    def test_geocode_slack_addresses_marks_ok_without_coordinates_for_review(self):
        uploaded_bodies: list[bytes] = []

        def fake_urlopen(request, timeout=None):
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": True, "upload_url": "https://upload.slack.test/file", "file_id": "F123"})
            if "upload.slack.test" in request.full_url:
                uploaded_bodies.append(request.data)
                return self._response({})
            if "files.completeUploadExternal" in request.full_url:
                body = urllib.parse.parse_qs(request.data.decode("utf-8"))
                self.assertIn("Geocoded 0/1 address rows", body["initial_comment"][0])
                return self._response({"ok": True, "file": {"permalink": "https://slack/file/F123"}})
            return self._response(
                {
                    "status": "OK",
                    "results": [
                        {
                            "formatted_address": "1 Raffles Pl, Singapore",
                            "place_id": "place-1",
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

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["status"], "needs-check")
        self.assertEqual(result["answer"]["ok_count"], 0)
        self.assertEqual(result["answer"]["status_counts"], {"OK": 1})
        self.assertIn("(0/1 OK)", result["answer"]["slack_reply"])
        self.assertIn(b"1 Raffles Place, Singapore\t\t\tOK", uploaded_bodies[0])

    def test_geocode_slack_addresses_blocks_instead_of_raw_reply_when_slack_upload_missing_scope(self):
        captured_urls: list[str] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
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
        self.assertFalse(any("maps.googleapis.com" in url for url in captured_urls))

    def test_geocode_slack_addresses_rejects_non_https_upload_url_before_google_call(self):
        captured_urls: list[str] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": True, "upload_url": "http://upload.slack.test/file", "file_id": "F123"})
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
        self.assertIn("https", result["answer"]["message"])
        self.assertFalse(any("maps.googleapis.com" in url for url in captured_urls))

    def test_geocode_slack_address_file_downloads_tsv_and_uploads_result(self):
        captured_urls: list[str] = []
        uploaded_bodies: list[bytes] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            if "conversations.history" in request.full_url:
                return self._response(
                    {
                        "ok": True,
                        "messages": [
                            {
                                "ts": "1234567890.123456",
                                "files": [
                                    {
                                        "id": "F-addresses",
                                        "name": "addresses.tsv",
                                        "mimetype": "text/tab-separated-values",
                                        "filetype": "tsv",
                                        "url_private_download": "https://files.slack.com/addresses.tsv",
                                    }
                                ],
                            }
                        ],
                    }
                )
            if "conversations.replies" in request.full_url:
                return self._response({"ok": True, "messages": []})
            if "files.slack.com/addresses.tsv" in request.full_url:
                auth = request.headers.get("Authorization") or request.headers.get("authorization")
                self.assertEqual(auth, "Bearer xoxb-secret")
                return self._bytes_response(b"customer\taddress\nOutlet A\t1 Raffles Place, Singapore\n")
            if "files.getUploadURLExternal" in request.full_url:
                return self._response({"ok": True, "upload_url": "https://upload.slack.test/file", "file_id": "F123"})
            if "upload.slack.test" in request.full_url:
                uploaded_bodies.append(request.data)
                return self._response({})
            if "files.completeUploadExternal" in request.full_url:
                body = urllib.parse.parse_qs(request.data.decode("utf-8"))
                self.assertEqual(body["channel_id"], ["C123"])
                self.assertEqual(body["thread_ts"], ["1234567890.123456"])
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
                result = self.module.geocode_slack_address_file(
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1234567890123456",
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["input_file"]["name"], "addresses.tsv")
        self.assertIn("Uploaded geocoded TSV file", result["answer"]["slack_reply"])
        self.assertIn(b"Outlet A", uploaded_bodies[0])
        self.assertIn(b"addresses.tsv: row 2", uploaded_bodies[0])
        self.assertIn(b"1.2847\t103.851\tOK", uploaded_bodies[0])
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertEqual(sum(1 for url in captured_urls if "maps.googleapis.com" in url), 1)

    def test_geocode_slack_address_file_blocks_missing_address_column_before_google(self):
        captured_urls: list[str] = []

        def fake_urlopen(request, timeout=None):
            captured_urls.append(request.full_url)
            if "conversations.history" in request.full_url:
                return self._response(
                    {
                        "ok": True,
                        "messages": [
                            {
                                "ts": "1234567890.123456",
                                "files": [
                                    {
                                        "id": "F-addresses",
                                        "name": "addresses.csv",
                                        "mimetype": "text/csv",
                                        "filetype": "csv",
                                        "url_private": "https://files.slack.com/addresses.csv",
                                    }
                                ],
                            }
                        ],
                    }
                )
            if "conversations.replies" in request.full_url:
                return self._response({"ok": True, "messages": []})
            if "files.slack.com/addresses.csv" in request.full_url:
                return self._bytes_response(b"customer,postal\nOutlet A,1 Raffles Place Singapore\n")
            return self._response({"ok": True})

        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key", "SLACK_BOT_TOKEN": "xoxb-secret"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = self.module.geocode_slack_address_file(
                    slack_thread_url="https://staffany.slack.com/archives/C123/p1234567890123456",
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("address column", result["answer"]["message"])
        self.assertFalse(any("maps.googleapis.com" in url for url in captured_urls))
        self.assertFalse(any("files.getUploadURLExternal" in url for url in captured_urls))

    def test_check_google_geocode_access_does_not_call_api(self):
        with patch.dict(os.environ, {"GOOGLE_GEOCODING_API_KEY": "secret-key"}, clear=False):
            with patch.object(self.module.urllib.request, "urlopen") as urlopen:
                result = self.module.check_google_geocode_access()
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(urlopen.call_count, 0)
        self.assertNotIn("secret-key", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
