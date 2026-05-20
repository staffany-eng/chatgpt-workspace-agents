from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class AaSelfieDriveTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        profile = Path(self.tmpdir.name) / ".hermes" / "profiles" / "psmopsbot"
        profile.mkdir(parents=True)
        token_path = profile / "drive-token.json"
        token_path.write_text(
            json.dumps(
                {
                    "refresh_token": "refresh-token",
                    "scopes": ["https://www.googleapis.com/auth/drive.file"],
                }
            ),
            encoding="utf-8",
        )
        client_secret_path = profile / "drive-client-secret.json"
        client_secret_path.write_text(
            json.dumps({"installed": {"client_id": "x", "client_secret": "y"}}),
            encoding="utf-8",
        )

        self.env = patch.dict(
            os.environ,
            {
                "HOME": self.tmpdir.name,
                "PSM_OPS_AA_SELFIE_DRIVE_FOLDER_ID": "test-folder-id",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

        self.module = load_mcp_module("aa_selfie_drive.py", "aa_selfie_drive_test")
        self.module._drive_access_token = lambda: "fake-access-token"

    def _make_response(self, body: dict) -> io.BytesIO:
        wrapper = io.BytesIO(json.dumps(body).encode("utf-8"))
        wrapper.__enter__ = lambda self: self  # type: ignore[attr-defined]
        wrapper.__exit__ = lambda self, *args: None  # type: ignore[attr-defined]
        return wrapper

    def test_upload_aa_selfies_posts_with_slack_file_id_in_filename(self):
        captured: list[dict] = []

        def fake_urlopen(request, timeout=None):
            captured.append(
                {
                    "method": request.get_method(),
                    "url": request.full_url,
                    "data": request.data,
                }
            )
            return self._make_response(
                {
                    "id": "drive-new",
                    "name": "kopi-janji_andre__F-new.jpg",
                    "webViewLink": "https://drive/new",
                }
            )

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.module.upload_aa_selfies(
                [
                    {
                        "content": b"binary",
                        "name": "selfie.jpg",
                        "mimetype": "image/jpeg",
                        "slack_file_id": "F-new",
                    }
                ],
                company="Kopi Janji",
                pic="Andre",
            )

        self.assertEqual([call["method"] for call in captured], ["POST"])
        post_body = captured[0]["data"].decode("utf-8", errors="replace")
        # Slack id suffixed into the filename so distinct selfies for the same
        # (company, pic) never share a Drive filename.
        self.assertIn("\"name\": \"kopi-janji_andre__F-new.jpg\"", post_body)
        # No appProperties / no Drive list lookup — keeping the path simple.
        self.assertNotIn("appProperties", post_body)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["drive_file_id"], "drive-new")

    def test_build_filename_uses_slack_file_id_suffix_when_present(self):
        name = self.module._build_filename(
            "Kopi Janji",
            "Andre",
            "image/jpeg",
            "selfie.jpg",
            1,
            slack_file_id="F0B4XL0RL8Z",
        )
        self.assertEqual(name, "kopi-janji_andre__F0B4XL0RL8Z.jpg")

    def test_build_filename_falls_back_to_sequence_when_slack_file_id_missing(self):
        first = self.module._build_filename("Kopi Janji", "Andre", "image/jpeg", "selfie.jpg", 1)
        second = self.module._build_filename("Kopi Janji", "Andre", "image/jpeg", "selfie.jpg", 2)
        self.assertEqual(first, "kopi-janji_andre.jpg")
        self.assertEqual(second, "kopi-janji_andre-2.jpg")

    def test_health_check_reports_ok_when_about_call_succeeds(self):
        def fake_urlopen(request, timeout=None):
            self.assertIn("/about", request.full_url)
            return self._make_response(
                {"user": {"emailAddress": "drive-bot@staffany.com"}}
            )

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            report = self.module.health_check()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["user_email"], "drive-bot@staffany.com")
        self.assertEqual(report["folder_id"], "test-folder-id")
        self.assertIn("https://www.googleapis.com/auth/drive.file", report["scopes"])

    def test_health_check_reports_refresh_failed_when_token_refresh_raises(self):
        def fail_token():
            raise self.module.AaSelfieDriveError("Google OAuth refresh failed: 400 invalid_grant")

        self.module._drive_access_token = fail_token

        report = self.module.health_check()
        self.assertEqual(report["status"], "refresh_failed")
        self.assertIn("invalid_grant", report["last_error"])

    def test_health_check_reports_api_unauthorized_on_401(self):
        def fake_urlopen(request, timeout=None):
            raise self.module.urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(b'{"error": "Invalid Credentials"}'),
            )

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            report = self.module.health_check()

        self.assertEqual(report["status"], "api_unauthorized")
        self.assertIn("401", report["reason"])

    def test_upload_aa_selfies_detailed_reports_drive_status_when_upload_fails(self):
        def fake_urlopen(request, timeout=None):
            raise self.module.urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(b'{"error": "Invalid Credentials"}'),
            )

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.module.upload_aa_selfies_detailed(
                [
                    {
                        "content": b"binary",
                        "name": "selfie.jpg",
                        "mimetype": "image/jpeg",
                        "slack_file_id": "F-fail",
                    }
                ],
                company="Kopi Janji",
                pic="Andre",
            )

        self.assertEqual(result["uploaded"], [])
        self.assertEqual(result["drive_status"], "upload_failed")
        self.assertEqual(result["failure_count"], 1)
        self.assertIn("401", result["drive_reason"])
        self.assertIn("Drive upload failed", result["last_error"])

    def test_upload_aa_selfies_detailed_reports_missing_token_without_attempting_upload(self):
        token_path = (
            Path(self.tmpdir.name)
            / ".hermes"
            / "profiles"
            / "psmopsbot"
            / "drive-token.json"
        )
        token_path.unlink()

        with patch.object(self.module.urllib.request, "urlopen", side_effect=AssertionError("upload must not be attempted")):
            result = self.module.upload_aa_selfies_detailed(
                [
                    {
                        "content": b"binary",
                        "name": "selfie.jpg",
                        "mimetype": "image/jpeg",
                        "slack_file_id": "F-skip",
                    }
                ],
                company="Kopi Janji",
                pic="Andre",
            )

        self.assertEqual(result["uploaded"], [])
        self.assertEqual(result["drive_status"], "missing_token")
        self.assertIn("drive-token.json", result["drive_reason"])

    def test_configuration_status_reports_missing_token(self):
        token_path = (
            Path(self.tmpdir.name)
            / ".hermes"
            / "profiles"
            / "psmopsbot"
            / "drive-token.json"
        )
        token_path.unlink()
        code, reason = self.module.configuration_status()
        self.assertEqual(code, "missing_token")
        self.assertIn("drive-token.json", reason)


if __name__ == "__main__":
    unittest.main()
