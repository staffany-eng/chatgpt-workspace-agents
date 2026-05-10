import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_helpers import load_mcp_module


def load_drive_module():
    return load_mcp_module("google_drive_nurtureany_server.py", "google_drive_nurtureany_server_under_test")


class GoogleDriveNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_drive_module()

    def test_missing_token_returns_blocked_without_calling_google(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {
                "GOOGLE_DRIVE_TOKEN_FILE": str(Path(tmpdir) / "missing-token.json"),
                "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
            },
        ), patch.object(self.module, "_request_json", side_effect=AssertionError("should not call Google")):
            result = self.module.list_drive_folder_images("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Missing Google Drive OAuth file", result["answer"])

    def test_list_caps_scope_and_returns_metadata_only(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append((path, params, access_token))
            if path.startswith("/files/"):
                return {
                    "id": self.module.DEFAULT_DRIVE_FOLDER_ID,
                    "name": "all-random",
                    "mimeType": "application/vnd.google-apps.folder",
                    "webViewLink": "https://drive.google.com/drive/folders/folder",
                }
            return {
                "files": [
                    {
                        "id": "file-1",
                        "name": "2026-05-10T10:00:00Z-U123-photo.jpg",
                        "mimeType": "image/jpeg",
                        "createdTime": "2026-05-10T10:01:00Z",
                        "modifiedTime": "2026-05-10T10:02:00Z",
                        "webViewLink": "https://drive.google.com/file/d/file-1/view",
                        "md5Checksum": "abc123",
                        "size": "12345",
                        "thumbnailLink": "private-thumbnail",
                    }
                ],
                "nextPageToken": "next",
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_TOKEN_FILE": str(token_file),
                    "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request), patch.object(
                self.module, "_slack_user_profile", return_value={"id": "U123", "name": "Uploader One", "profile_source": "slack_users_info"}
            ):
                result = self.module.list_drive_folder_images("ae@staffany.com", limit=999)

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["requested_limit"], self.module.MAX_DRIVE_FILES)
        self.assertTrue(result["has_more"])
        self.assertTrue(calls[0][0].startswith("/files/"))
        self.assertEqual(calls[1][0], "/files")
        self.assertEqual(calls[1][2], "access-token")
        self.assertIn("'1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-' in parents", calls[1][1]["q"])
        self.assertIn("mimeType contains 'image/'", calls[1][1]["q"])
        self.assertEqual(calls[1][1]["pageSize"], self.module.MAX_DRIVE_FILES)
        file = result["answer"][0]
        self.assertEqual(file["id"], "file-1")
        self.assertEqual(file["md5Checksum"], "abc123")
        self.assertNotIn("thumbnailLink", file)
        self.assertEqual(file["source_timestamp"], "2026-05-10T10:00:00Z")
        self.assertEqual(file["slack_user_id"], "U123")
        self.assertEqual(file["slack_uploader_name"], "Uploader One")
        self.assertEqual(file["original_filename"], "photo.jpg")
        self.assertEqual(result["scope"]["folder"]["name"], "all-random")

    def test_refuses_non_team_account(self):
        with patch.dict(os.environ, {"GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Google")
        ):
            result = self.module.list_drive_folder_images("ae@staffany.com", account_email="other@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"])

    def test_blocks_token_missing_drive_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}')
            with patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=AssertionError("should not call Google")
            ):
                result = self.module.list_drive_folder_images("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("drive.readonly", result["answer"])

    def test_blocks_inaccessible_folder_before_listing(self):
        def fake_request(path, params, access_token):
            if path.startswith("/files/"):
                raise self.module.GoogleDriveError("Google Drive API failed: 404 File not found", 404)
            raise AssertionError("should not list folder contents")

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ):
                result = self.module.list_drive_folder_images("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("File not found", result["answer"])

    def test_refreshes_token_after_401(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append(access_token)
            if path.startswith("/files/") and len(calls) == 1:
                raise self.module.GoogleDriveError("expired", 401)
            if path.startswith("/files/"):
                return {
                    "id": self.module.DEFAULT_DRIVE_FOLDER_ID,
                    "name": "all-random",
                    "mimeType": "application/vnd.google-apps.folder",
                }
            return {"files": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"old-token","refresh_token":"refresh","client_id":"id","client_secret":"secret","scopes":["https://www.googleapis.com/auth/drive.readonly"]}'
            )
            with patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ), patch.object(self.module, "_refresh_access_token", return_value="new-token"):
                result = self.module.list_drive_folder_images("ae@staffany.com")

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(calls, ["old-token", "new-token", "new-token"])

    def test_extract_drive_image_clues_downloads_transiently_and_returns_only_clues(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_TOKEN_FILE": str(token_file),
                    "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
                    "ANTHROPIC_API_KEY": "test-key",
                },
            ), patch.object(
                self.module,
                "_download_drive_file_bytes",
                return_value=(b"not-returned-image-bytes", "image/jpeg"),
            ) as download, patch.object(
                self.module,
                "_run_anthropic_vision",
                return_value={
                    "company_names": ["Fei Siong"],
                    "contact_names": ["Jane Tan"],
                    "ocr_text": "Jane Tan Fei Siong",
                    "needs_human_clue": False,
                },
            ) as vision:
                result = self.module.extract_drive_image_clues(
                    "ae@staffany.com",
                    [
                        {
                            "id": "file-1",
                            "name": "2026-05-10T10:00:00Z-U123-photo.jpg",
                            "mimeType": "image/jpeg",
                        }
                    ],
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["answer"]["processed_count"], 1)
        self.assertFalse(result["answer"]["raw_image_retained"])
        self.assertEqual(result["answer"]["image_clues"][0]["vision_clues"]["company_names"], ["Fei Siong"])
        self.assertNotIn("not-returned-image-bytes", json.dumps(result))
        download.assert_called_once_with("file-1", "access-token", self.module.MAX_IMAGE_BYTES)
        vision.assert_called_once()

    def test_extract_drive_image_clues_blocks_without_vision_key_before_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_TOKEN_FILE": str(token_file),
                    "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
                },
                clear=True,
            ), patch.object(self.module, "_download_drive_file_bytes", side_effect=AssertionError("should not download")):
                result = self.module.extract_drive_image_clues(
                    "ae@staffany.com",
                    [{"id": "file-1", "name": "photo.jpg", "mimeType": "image/jpeg"}],
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("ANTHROPIC_API_KEY", result["answer"])

    def test_extract_drive_image_clues_skips_unsupported_media_without_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_TOKEN_FILE": str(token_file),
                    "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
                    "ANTHROPIC_API_KEY": "test-key",
                },
            ), patch.object(self.module, "_download_drive_file_bytes", side_effect=AssertionError("should not download")):
                result = self.module.extract_drive_image_clues(
                    "ae@staffany.com",
                    [{"id": "file-1", "name": "photo.heic", "mimeType": "image/heic"}],
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(result["answer"]["skipped"][0]["reason"], "unsupported_image_type")

    def test_registration_attendance_fallback_returns_safe_rows_and_match_keys(self):
        calls = []

        def fake_sheets_request(spreadsheet_id, path, params, access_token):
            calls.append((spreadsheet_id, path, params, access_token))
            if path == "":
                return {
                    "properties": {"title": self.module.ID_REV_EVENTS_SPREADSHEET_TITLE},
                    "sheets": [
                        {"properties": {"sheetId": 113156488, "title": "HHH Bali 7 May - Rsvp", "index": 98}},
                        {"properties": {"sheetId": 780592408, "title": "HHH Bali 7 May - Feedback", "index": 99}},
                    ],
                }
            return {
                "values": [
                    [
                        "Name",
                        "Email",
                        "Phone Number",
                        "Approval\nStatus",
                        "Job Role",
                        "Job Title",
                        "Company Name",
                        "Industry",
                        "Total\nEmployees",
                        "Account\nMapping",
                        "RSVPs Confirmation",
                        "WA\nConfirm",
                        "Attend\nThe Event",
                        "QO Set",
                        "Remarks",
                    ],
                    [
                        "Marini",
                        "hr@sevnlegian.com",
                        "+6281338337762",
                        "approved",
                        "HR Manager",
                        "HR Lead",
                        "Sevn Legian",
                        "Hospitality",
                        "51-100",
                        "Simone",
                        "New Prospect",
                        "Yes",
                        "TRUE",
                        "",
                        "",
                    ],
                    [
                        "Nia",
                        "nia@gmail.com",
                        "+6287800048999",
                        "approved",
                        "Others",
                        "HR Supervisor",
                        "Biru Laut Abadi",
                        "Retail",
                        "101-200",
                        "Khrisna",
                        "New Prospect",
                        "Yes",
                        "FALSE",
                        "",
                        "",
                    ],
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text('{"token":"access-token","scopes":["https://www.googleapis.com/auth/drive.readonly"]}')
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DRIVE_TOKEN_FILE": str(token_file),
                    "GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_sheets_json", side_effect=fake_sheets_request):
                result = self.module.read_indonesia_event_registration_attendance(
                    "kaiyi@staffany.com",
                    event_name="StaffAny Happy HR Hour (HHH) - Bali",
                    event_date="2026-05-07",
                    event_tags=["Bali", "HR Happy Hour"],
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["sheet_name"], "HHH Bali 7 May - Rsvp")
        self.assertEqual(result["answer"]["counts"]["attended_rows"], 1)
        self.assertEqual(result["answer"]["registration_rows_returned"], 1)
        self.assertTrue(result["answer"]["row_details_truncated"])
        self.assertNotIn("registration_rows", result["answer"])
        self.assertIn("registration_rows_sample", result["answer"])
        self.assertIn("sevnlegian.com", result["answer"]["match_keys"]["attended_email_domains"])
        self.assertNotIn("gmail.com", result["answer"]["match_keys"]["email_domains"])
        self.assertIn("Sevn Legian", result["answer"]["match_keys"]["attended_company_name_candidates"])
        payload = json.dumps(result)
        self.assertLess(len(payload), 20_000)
        self.assertNotIn("+6281338337762", payload)
        self.assertNotIn("hr@sevnlegian.com", payload)
        self.assertIn("email_hash", payload)
        self.assertEqual(calls[0][0], self.module.ID_REV_EVENTS_SPREADSHEET_ID)
        self.assertIn("/values/", calls[1][1])

    def test_registration_attendance_fallback_restricts_spreadsheet(self):
        with patch.dict(os.environ, {"GOOGLE_DRIVE_ACCOUNT_EMAIL": "team@staffany.com"}), patch.object(
            self.module, "_request_sheets_json", side_effect=AssertionError("should not call Google")
        ):
            result = self.module.read_indonesia_event_registration_attendance(
                "kaiyi@staffany.com",
                spreadsheet_id="other-spreadsheet",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("ID REV - LL & HHH EVENTS", result["answer"])


if __name__ == "__main__":
    unittest.main()
