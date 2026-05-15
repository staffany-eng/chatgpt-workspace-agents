import json
import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
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

    def test_read_nurture_material_registry_returns_rows_from_one_sheet(self):
        calls = []

        def fake_sheets(spreadsheet_id, path, params, access_token):
            calls.append((spreadsheet_id, path, params, access_token))
            if path == "":
                return {
                    "properties": {"title": "NurtureAny Materials"},
                    "sheets": [{"properties": {"title": "Materials", "sheetId": 1}}],
                }
            return {
                "values": [
                    list(self.module.MATERIAL_REGISTRY_FIELDS),
                    [
                        "mat-1",
                        "case_study",
                        "F&B case",
                        "https://example.com/case",
                        "active",
                        "Singapore",
                        "food, beverage",
                        "restaurant",
                        "decision_maker",
                        "2026-01-01",
                        "2026-12-31",
                        "nurture_material_share_v1",
                        "first_name,account_name,material_title,material_url",
                        "similar F&B operators",
                        "RevOps",
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
                    "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID": "sheet-123",
                },
            ), patch.object(self.module, "_request_sheets_json", side_effect=fake_sheets):
                result = self.module.read_nurture_material_registry("ae@staffany.com", tabs=["Materials"])

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["row_count"], 1)
        self.assertEqual(result["answer"]["rows"][0]["material_id"], "mat-1")
        self.assertEqual(result["answer"]["rows"][0]["source_tab"], "Materials")
        self.assertEqual(calls[0][0], "sheet-123")
        self.assertIn("/values/", calls[1][1])

    def test_read_nurture_material_registry_accepts_kns_golden_dataset_schema(self):
        def fake_sheets(spreadsheet_id, path, params, access_token):
            if path == "":
                return {
                    "properties": {"title": "NurtureAny KNS Materials Golden Dataset"},
                    "sheets": [{"properties": {"title": "Materials", "sheetId": 1}}],
                }
            return {
                "values": [
                    [
                        "material_id",
                        "status",
                        "title",
                        "kns_pillar",
                        "pillar_summary",
                        "buyer_value",
                        "ae_use_case",
                        "whatsapp_script",
                        "message_hook",
                        "match_country",
                        "match_industry",
                        "match_concept",
                        "match_persona",
                        "source_evidence_url",
                        "asset_url",
                        "talk_track",
                        "valid_from",
                        "valid_until",
                        "owner",
                    ],
                    [
                        "case-study:bmc-populus-staffany-scheduling",
                        "approved",
                        "BMC: Populus",
                        "Knowledge",
                        "Public BMC operator example.",
                        "Scheduling dropped from hours to minutes.",
                        "knowledge_touch, pre_demo",
                        "Hi {{first_name}}, thought of {{company_name}}...",
                        "Populus: StaffAny cut scheduling from about 2 hours to around 10 minutes.",
                        "Singapore",
                        "F&B - cafe/restaurant",
                        "fnb, cafe, scheduling",
                        "decision_maker, operations",
                        "research/raw/online/populus.md:201 00:03:11",
                        "https://www.youtube.com/watch?v=vN3T0oL_X8I",
                        "Use as an analogy only.",
                        "2026-05-13",
                        "",
                        "repo_case_study_catalog",
                    ],
                    [
                        "kns:network-community-peer-talent-collaboration",
                        "approved",
                        "Network: Community, peer, talent, and collaboration matching",
                        "Network",
                        "Network means event invites, peer matching, talent matching, and customer collaboration.",
                        "StaffAny becomes the connector to useful operators, HR peers, hiring leads, and collaboration opportunities.",
                        "daily_nurture, pre_demo, event_followup",
                        "Hi {{first_name}}, thought of {{company_name}} because there may be a useful peer or talent match here. {{message_hook}}",
                        "Network offer: invite them to HHH/LL/cozy dinners, introduce relevant peers, match hiring/talent asks, or create customer collaboration.",
                        "Singapore, Malaysia, Indonesia",
                        "all",
                        "event, happy-hr-hour, leaders-lounge, cozy-dinner, peer-matching, talent-matching, collaboration",
                        "decision_maker, influencer, operations, hr",
                        "skills/nurtureany-sales-bot/references/sales-best-practices.md",
                        "",
                        "Use as Network. Do not confuse direct speaker/venue support for the buyer with Network.",
                        "2026-05-15",
                        "",
                        "nurtureany_packet",
                    ],
                    [
                        "kns:support-speaker-venue-outlet",
                        "approved",
                        "Support: Speaker, venue, meal, or outlet support",
                        "Support",
                        "Support means featuring or supporting the buyer/account directly, not generic networking.",
                        "Boss and HR contacts can get a speaker slot, future-speaker sourcing, venue support, small peer meal, or visible outlet/product support.",
                        "daily_nurture, pre_demo, event_followup",
                        "Hi {{first_name}}, thought of {{company_name}} because we may be able to support your venue or feature your team. {{message_hook}}",
                        "Support offer: ask boss/HR to speak, ask who they want to hear from for future speakers, use/support their venue, host a simple meal there, buy their product, or reference visible outlet demand.",
                        "Singapore, Malaysia, Indonesia",
                        "f&b, retail, services, shift-work",
                        "speaker, future-speaker, venue, simple-meal, leaders-lounge, happy-hr-hour, outlet-support, buy-product, long-queue",
                        "decision_maker, owner, founder, boss, hr",
                        "skills/nurtureany-sales-bot/references/sales-best-practices.md",
                        "",
                        "Use as Support, not Support Network. Boss variant maps to Leaders Lounge; HR variant maps to Happy HR Hour. Ask who they want to hear from for future speakers is Support, not Network.",
                        "2026-05-15",
                        "",
                        "nurtureany_packet",
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
                    "NURTUREANY_MATERIAL_REGISTRY_SPREADSHEET_ID": "sheet-123",
                },
            ), patch.object(self.module, "_request_sheets_json", side_effect=fake_sheets):
                result = self.module.read_nurture_material_registry("ae@staffany.com", tabs=["Materials"])

        row = result["answer"]["rows"][0]
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(row["category"], "case_study")
        self.assertEqual(row["url"], "https://www.youtube.com/watch?v=vN3T0oL_X8I")
        self.assertEqual(row["country_scope"], "Singapore")
        self.assertEqual(row["industry_tags"], "F&B - cafe/restaurant")
        self.assertEqual(row["concept_tags"], "fnb, cafe, scheduling")
        self.assertEqual(row["persona_tags"], "decision_maker, operations")
        self.assertEqual(row["template_name"], "nurture_material_share_v1")
        self.assertIn("material_url", row["template_params_schema"])
        self.assertEqual(row["kns_pillar"], "Knowledge")
        self.assertEqual(row["talk_track"], "Use as an analogy only.")
        rows_by_id = {item["material_id"]: item for item in result["answer"]["rows"]}
        self.assertEqual(rows_by_id["kns:network-community-peer-talent-collaboration"]["kns_pillar"], "Network")
        self.assertIn("talent-matching", rows_by_id["kns:network-community-peer-talent-collaboration"]["concept_tags"])
        self.assertEqual(rows_by_id["kns:support-speaker-venue-outlet"]["kns_pillar"], "Support")
        self.assertNotIn("Support Network", rows_by_id["kns:support-speaker-venue-outlet"]["title"])

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

    def test_read_google_slides_deck_exports_text_with_team_oauth(self):
        request_calls = []

        def fake_request(path, params, access_token):
            request_calls.append((path, params, access_token))
            return {
                "id": "1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y",
                "name": "Pre Demo Nurturing",
                "mimeType": self.module.GOOGLE_SLIDES_MIME_TYPE,
                "webViewLink": "https://docs.google.com/presentation/d/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y/edit",
                "modifiedTime": "2026-05-11T12:00:00Z",
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
                self.module, "_request_export_text", return_value="Hook\n\nKNS\n\n14 day cadence"
            ) as export:
                result = self.module.read_google_slides_deck(
                    "kerren.fong@staffany.com",
                    "https://docs.google.com/presentation/d/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y/edit?slide=id.p7#slide=id.p7",
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["presentation"]["name"], "Pre Demo Nurturing")
        self.assertEqual(result["answer"]["slide_text"], "Hook\n\nKNS\n\n14 day cadence")
        self.assertEqual(result["source"], "Google Drive presentation text extraction")
        self.assertEqual(result["answer"]["extraction_method"], "google_slides_export_text")
        self.assertEqual(result["scope"]["drive_access_mode"], "team_oauth_drive_readonly")
        self.assertEqual(request_calls[0][0], "/files/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y")
        export.assert_called_once_with("1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y", "access-token")
        self.assertNotIn("Anyone with the link", json.dumps(result))

    def test_read_google_slides_deck_extracts_pptx_text_transiently(self):
        request_calls = []

        def fake_request(path, params, access_token):
            request_calls.append((path, params, access_token))
            return {
                "id": "1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y",
                "name": "2. 20260330 Training Module 1: Pre-Demo Nurturing Training.pptx",
                "mimeType": self.module.POWERPOINT_MIME_TYPE,
                "webViewLink": "https://docs.google.com/presentation/d/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y/edit",
                "modifiedTime": "2026-05-11T12:00:00Z",
                "size": "123456",
            }

        pptx = io.BytesIO()
        with zipfile.ZipFile(pptx, "w") as archive:
            archive.writestr(
                "ppt/slides/slide1.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>KNS</a:t></a:r></a:p>
                  <a:p><a:r><a:t>14 day cadence</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld>
                </p:sld>""",
            )
        pptx_bytes = pptx.getvalue()

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
                self.module, "_download_drive_file_bytes", return_value=(pptx_bytes, self.module.POWERPOINT_MIME_TYPE)
            ) as download:
                result = self.module.read_google_slides_deck(
                    "kerren.fong@staffany.com",
                    "https://docs.google.com/presentation/d/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y/edit",
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["extraction_method"], "pptx_transient_zip_xml_text")
        self.assertFalse(result["answer"]["raw_file_retained"])
        self.assertIn("Slide 1", result["answer"]["slide_text"])
        self.assertIn("KNS", result["answer"]["slide_text"])
        self.assertIn("14 day cadence", result["answer"]["slide_text"])
        self.assertNotIn("PK", json.dumps(result))
        download.assert_called_once_with(
            "1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y",
            "access-token",
            self.module.MAX_PRESENTATION_BYTES,
        )
        self.assertEqual(request_calls[0][0], "/files/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y")

    def test_read_google_slides_deck_blocks_inaccessible_deck_without_public_sharing_advice(self):
        def fake_request(path, params, access_token):
            raise self.module.GoogleDriveError("Google Drive API failed: 403 permission denied", 403)

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
                self.module, "_request_export_text", side_effect=AssertionError("should not export inaccessible deck")
            ):
                result = self.module.read_google_slides_deck(
                    "kerren.fong@staffany.com",
                    "https://docs.google.com/presentation/d/1DiK3PffYE79r7ZxTLHzi9NPw9ZPVMs8Y/edit",
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"])
        self.assertIn("do not request public link sharing", result["answer"])
        self.assertNotIn("Anyone with the link", json.dumps(result))

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
        self.assertEqual(result["answer"]["registration_rows_returned"], 0)
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
        self.assertNotIn("email_hash", payload)
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
