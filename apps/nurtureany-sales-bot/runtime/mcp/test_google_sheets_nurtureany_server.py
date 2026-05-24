import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
from test_helpers import load_mcp_module


def load_sheets_module():
    return load_mcp_module("google_sheets_nurtureany_server.py", "google_sheets_nurtureany_server_under_test")


class GoogleSheetsNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_sheets_module()

    def test_preview_validates_without_mutating_google_sheets(self):
        with patch.dict(os.environ, {self.module.SPREADSHEET_ID_ENV: "sheet-123"}), patch.object(
            self.module, "_sheets_request", side_effect=AssertionError("preview must not call Google Sheets API")
        ), patch.object(self.module, "_access_token", side_effect=AssertionError("preview must not load OAuth token")):
            result = self.module.preview_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="luma_rsvp_classification",
                title="AI F&B Workshop RSVP classification",
                idempotency_key="C0B2UGK4DB6-1778798036",
                columns=["company_id", "account", "account_status", "owner", "invited_by", "rsvp_status"],
                rows=[
                    {
                        "company_id": "9003704457",
                        "account": "Noci Bakehouse",
                        "account_status": "customer",
                        "owner": "Jeremy Wong",
                        "invited_by": "Partner",
                        "rsvp_status": "approved",
                    }
                ],
                source_permalink="https://staffany.slack.com/archives/C0B2UGK4DB6/p1778798088431439",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertFalse(result["answer"]["will_mutate_google_sheets"])
        self.assertEqual(result["answer"]["row_count"], 1)
        self.assertTrue(result["answer"]["planned_tab_name"].startswith("AI F&B Workshop RSVP classification-"))

    def test_preview_rejects_unsafe_columns_and_cells(self):
        with patch.dict(os.environ, {self.module.SPREADSHEET_ID_ENV: "sheet-123"}):
            email_column = self.module.preview_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="event",
                columns=["account", "attendee_email"],
                rows=[{"account": "Noci", "attendee_email": "person@example.com"}],
            )
            phone_cell = self.module.preview_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="event",
                columns=["account", "safe_note"],
                rows=[{"account": "Noci", "safe_note": "+65 9123 4567"}],
            )
            raw_transcript = self.module.preview_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="event",
                columns=["account", "safe_note"],
                rows=[{"account": "Noci", "safe_note": "User: export this\nBot: ok"}],
            )

        self.assertEqual(email_column["confidence"], "blocked")
        self.assertIn("Unsafe Sheet export column", email_column["answer"])
        self.assertEqual(phone_cell["confidence"], "blocked")
        self.assertIn("phone number", phone_cell["answer"])
        self.assertEqual(raw_transcript["confidence"], "blocked")
        self.assertIn("raw transcript", raw_transcript["answer"])

    def test_preview_accepts_event_match_action_queue_columns_without_mutating(self):
        columns = [
            "event_id",
            "event_name",
            "rsvp_status",
            "account_name",
            "hubspot_company_link",
            "hubspot_contact_link_if_exact_match",
            "owner",
            "customer_or_prospect",
            "match_level",
            "confidence",
            "root_cause",
            "next_action",
            "action_owner",
            "due_by",
            "status",
            "source_run_link",
        ]
        rows = [
            {
                "event_id": "evt-1",
                "event_name": "AI Workshop",
                "rsvp_status": "approved",
                "account_name": "Exact Cafe",
                "hubspot_company_link": "https://app.hubspot.com/contacts/4137076/record/0-2/123",
                "hubspot_contact_link_if_exact_match": "https://app.hubspot.com/contacts/4137076/record/0-1/456",
                "owner": "Sales Owner",
                "customer_or_prospect": "customer",
                "match_level": "exact_contact_email",
                "confidence": "verified",
                "root_cause": "Approved RSVP matched to scoped HubSpot target account by exact contact email.",
                "next_action": "AE follow up from HubSpot account context.",
                "action_owner": "Sales Owner",
                "due_by": "2026-05-20",
                "status": "not_started",
                "source_run_link": "https://staffany.slack.com/archives/C0B2UGK4DB6/p1779057689264659",
            }
        ]

        with patch.dict(os.environ, {self.module.SPREADSHEET_ID_ENV: "sheet-123"}), patch.object(
            self.module, "_sheets_request", side_effect=AssertionError("preview must not call Google Sheets API")
        ):
            result = self.module.preview_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="event_match_action_queue",
                title="AI Workshop Event Match Action Queue",
                idempotency_key="event-queue-1",
                sheet_tab_name="Event Match Action Queue",
                columns=columns,
                rows=rows,
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["row_count"], 1)
        self.assertFalse(result["answer"]["will_mutate_google_sheets"])

    def test_apply_creates_runs_index_and_updates_run_tab_idempotently(self):
        state = {"sheets": {}, "next_sheet_id": 100, "runs": []}

        def fake_sheets_request(method, spreadsheet_id, suffix, access_token, params=None, body=None):
            self.assertEqual(spreadsheet_id, "sheet-123")
            self.assertEqual(access_token, "token-123")
            if method == "GET" and suffix == "":
                return {
                    "spreadsheetId": spreadsheet_id,
                    "properties": {"title": "NurtureAny Analysis Output"},
                    "sheets": [
                        {"properties": {"sheetId": sheet_id, "title": title, "index": index}}
                        for index, (title, sheet_id) in enumerate(state["sheets"].items())
                    ],
                }
            if method == "POST" and suffix == ":batchUpdate":
                title = body["requests"][0]["addSheet"]["properties"]["title"]
                state["sheets"][title] = state["next_sheet_id"]
                state["next_sheet_id"] += 1
                return {"replies": [{"addSheet": {"properties": {"title": title, "sheetId": state["sheets"][title]}}}]}
            if method == "GET" and suffix.startswith("/values/"):
                return {"values": state["runs"]}
            if method == "PUT" and suffix.startswith("/values/"):
                if "%27Runs%27" in suffix:
                    state["runs"] = body["values"]
                return {"updatedRows": len(body["values"])}
            if method == "POST" and suffix.endswith(":clear"):
                return {}
            raise AssertionError(f"unexpected Sheets call: {method} {suffix}")

        payload = {
            "slack_user_email": "jan-e@staffany.com",
            "analysis_type": "luma_rsvp_classification",
            "title": "AI F&B Workshop RSVP classification",
            "idempotency_key": "C0B2UGK4DB6-1778798036",
            "columns": ["account", "account_status", "owner"],
            "rows": [{"account": "Noci Bakehouse", "account_status": "customer", "owner": "Jeremy Wong"}],
        }
        with patch.dict(os.environ, {self.module.SPREADSHEET_ID_ENV: "sheet-123"}), patch.object(
            self.module, "_access_token", return_value="token-123"
        ), patch.object(self.module, "_sheets_request", side_effect=fake_sheets_request):
            first = self.module.apply_analysis_sheet_export(**payload)
            second = self.module.apply_analysis_sheet_export(**payload)

        self.assertEqual(first["confidence"], "verified")
        self.assertEqual(first["answer"]["runs_index_action"], "created")
        self.assertTrue(first["answer"]["created_run_tab"])
        self.assertEqual(second["confidence"], "verified")
        self.assertEqual(second["answer"]["runs_index_action"], "updated")
        self.assertFalse(second["answer"]["created_run_tab"])
        self.assertEqual(state["runs"][0], self.module.RUNS_HEADER)
        self.assertEqual(len(state["runs"]), 2)

    def test_apply_rejects_spreadsheet_outside_configured_workbook(self):
        with patch.dict(os.environ, {self.module.SPREADSHEET_ID_ENV: "sheet-123"}), patch.object(
            self.module, "_access_token", side_effect=AssertionError("validation should stop before token load")
        ):
            result = self.module.apply_analysis_sheet_export(
                slack_user_email="jan-e@staffany.com",
                analysis_type="event",
                columns=["account"],
                rows=[{"account": "Noci"}],
                spreadsheet_id="other-sheet",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured shared analysis workbook", result["answer"])


if __name__ == "__main__":
    unittest.main()
