from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
sys.modules.pop("test_helpers", None)

from test_helpers import load_mcp_module


class StaffAnyGoogleSheetsServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("staffany_google_sheets_server.py")

    def _token_file(self, tmpdir: str, scopes: list[str] | None = None) -> Path:
        token_file = Path(tmpdir) / "token.json"
        token_file.write_text(
            json.dumps(
                {
                    "token": "access-token",
                    "scopes": scopes
                    or [
                        self.module.SPREADSHEETS_SCOPE,
                        self.module.DRIVE_FILE_SCOPE,
                    ],
                }
            )
        )
        return token_file

    def test_missing_oauth_blocks_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_SHEETS_TOKEN_FILE": str(Path(tmpdir) / "missing-token.json"),
                    "GOOGLE_SHEETS_ACCOUNT_EMAIL": "team@staffany.com",
                    "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS": "ops@staffany.com",
                },
                clear=True,
            ):
                result = self.module.check_google_sheets_output_access("kaiyi@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Missing Google Sheets output OAuth file", result["answer"])

    def test_non_team_account_blocks(self):
        with patch.dict(os.environ, {"GOOGLE_SHEETS_ACCOUNT_EMAIL": "team@staffany.com"}, clear=True):
            result = self.module.check_google_sheets_output_access(
                "kaiyi@staffany.com",
                account_email="other@staffany.com",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"])

    def test_blocks_without_folder_or_share_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = self._token_file(tmpdir)
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_SHEETS_TOKEN_FILE": str(token_file),
                    "GOOGLE_SHEETS_ACCOUNT_EMAIL": "team@staffany.com",
                },
                clear=True,
            ):
                result = self.module.check_google_sheets_output_access("kaiyi@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("GOOGLE_SHEETS_OUTPUT_FOLDER_ID", result["answer"])

    def test_missing_drive_scope_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = self._token_file(tmpdir, scopes=[self.module.SPREADSHEETS_SCOPE])
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_SHEETS_TOKEN_FILE": str(token_file),
                    "GOOGLE_SHEETS_ACCOUNT_EMAIL": "team@staffany.com",
                    "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS": "ops@staffany.com",
                },
                clear=True,
            ):
                result = self.module.check_google_sheets_output_access("kaiyi@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn(self.module.DRIVE_FILE_SCOPE, result["answer"])

    def test_create_spreadsheet_writes_values_moves_and_shares(self):
        calls = []

        def fake_request(method, url, access_token, payload=None, params=None):
            calls.append((method, url, payload, params))
            if method == "POST" and url == self.module.GOOGLE_SHEETS_API_BASE_URL:
                return {
                    "spreadsheetId": "spreadsheet-123",
                    "spreadsheetUrl": "https://docs.google.com/spreadsheets/d/spreadsheet-123/edit",
                }
            return {}

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = self._token_file(tmpdir)
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_SHEETS_TOKEN_FILE": str(token_file),
                    "GOOGLE_SHEETS_ACCOUNT_EMAIL": "team@staffany.com",
                    "GOOGLE_SHEETS_OUTPUT_FOLDER_ID": "folder-123",
                    "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS": "ops@staffany.com",
                    "GOOGLE_SHEETS_OUTPUT_SHARE_ROLE": "writer",
                },
                clear=True,
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.create_spreadsheet_from_rows(
                    "kaiyi@staffany.com",
                    "Bali banner summary",
                    [{"name": "Summary", "rows": [["Org", "Status"], ["A", "No banner"]]}],
                    source="analytics.dim_organisations",
                    scope_note="Bali orgs",
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["spreadsheet_id"], "spreadsheet-123")
        self.assertEqual(result["answer"]["row_count"], 2)
        self.assertTrue(result["answer"]["moved_to_output_folder"])
        self.assertEqual(result["answer"]["shared_target_count"], 1)
        self.assertTrue(any(call[1].endswith("/values:batchUpdate") for call in calls))
        self.assertTrue(any(call[0] == "PATCH" and "addParents" in str(call[3]) for call in calls))
        self.assertTrue(any(call[0] == "POST" and call[1].endswith("/permissions") for call in calls))

    def test_formula_like_cells_are_escaped(self):
        rows = self.module._normalize_rows([["=A1", "+1", "-1", "@here", "safe"]])
        self.assertEqual(rows[0], ["'=A1", "'+1", "'-1", "'@here", "safe"])

    def test_enforces_tab_row_and_cell_caps(self):
        too_many_tabs = [{"name": f"T{i}", "rows": [["x"]]} for i in range(self.module.MAX_TABS + 1)]
        with self.assertRaises(self.module.StaffAnyGoogleSheetsError):
            self.module._normalize_tabs(too_many_tabs)

        too_many_rows = [{"name": "Rows", "rows": [["x"]] * (self.module.MAX_ROWS_PER_TAB + 1)}]
        with self.assertRaises(self.module.StaffAnyGoogleSheetsError):
            self.module._normalize_tabs(too_many_rows)

        too_many_cells = [{"name": "Cells", "rows": [["x"] * 21] * 5000}]
        with self.assertRaises(self.module.StaffAnyGoogleSheetsError):
            self.module._normalize_tabs(too_many_cells)


if __name__ == "__main__":
    unittest.main()
