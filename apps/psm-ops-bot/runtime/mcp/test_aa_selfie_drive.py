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

        self.module = load_mcp_module("aa_selfie_drive.py", "aa_selfie_drive_dedup_test")
        self.module._drive_access_token = lambda: "fake-access-token"

    def _make_response(self, body: dict) -> io.BytesIO:
        wrapper = io.BytesIO(json.dumps(body).encode("utf-8"))
        wrapper.__enter__ = lambda self: self  # type: ignore[attr-defined]
        wrapper.__exit__ = lambda self, *args: None  # type: ignore[attr-defined]
        return wrapper

    def test_upload_aa_selfies_skips_existing_slack_file_id(self):
        captured: list[dict] = []

        def fake_urlopen(request, timeout=None):
            captured.append(
                {
                    "method": request.get_method(),
                    "url": request.full_url,
                    "data": request.data,
                }
            )
            if request.get_method() == "GET":
                return self._make_response(
                    {
                        "files": [
                            {
                                "id": "drive-existing",
                                "name": "kopi-janji_andre.jpg",
                                "webViewLink": "https://drive/existing",
                            }
                        ]
                    }
                )
            return self._make_response({"id": "should-not-happen"})

        with patch.object(self.module.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = self.module.upload_aa_selfies(
                [
                    {
                        "content": b"binary",
                        "name": "selfie.jpg",
                        "mimetype": "image/jpeg",
                        "slack_file_id": "F-existing",
                    }
                ],
                company="Kopi Janji",
                pic="Andre",
            )

        self.assertEqual(len(captured), 1, "should only issue the GET lookup, not POST upload")
        self.assertEqual(captured[0]["method"], "GET")
        self.assertIn("F-existing", captured[0]["url"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["already_present"], True)
        self.assertEqual(result[0]["drive_file_id"], "drive-existing")

    def test_upload_aa_selfies_tags_new_upload_with_slack_file_id(self):
        captured: list[dict] = []

        def fake_urlopen(request, timeout=None):
            captured.append(
                {
                    "method": request.get_method(),
                    "url": request.full_url,
                    "data": request.data,
                }
            )
            if request.get_method() == "GET":
                return self._make_response({"files": []})
            return self._make_response(
                {
                    "id": "drive-new",
                    "name": "kopi-janji_andre.jpg",
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

        self.assertEqual([call["method"] for call in captured], ["GET", "POST"])
        post_body = captured[1]["data"].decode("utf-8", errors="replace")
        self.assertIn("\"slack_file_id\": \"F-new\"", post_body)
        self.assertIn("\"appProperties\"", post_body)
        # Filename suffixes the Slack file id so distinct selfies for the same
        # (company, pic) never share a Drive filename.
        self.assertIn("\"name\": \"kopi-janji_andre__F-new.jpg\"", post_body)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["already_present"], False)
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
