from __future__ import annotations

import os
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


def support_item(item_id: str, title: str, description: str, source_type: str = "intercom_conversation_part"):
    return {
        "source_type": source_type,
        "id": item_id,
        "ticket_id": item_id,
        "part_id": f"part_{item_id}" if source_type == "intercom_conversation_part" else "",
        "conversation_id": f"conv_{item_id}",
        "title": title,
        "body": description,
        "tags": "payroll",
        "state": "open",
        "open": True,
        "team_assignee_id": "team_1",
        "admin_assignee_id": "admin_1",
        "created_at": "2026-05-01 01:00:00 UTC",
        "updated_at": "2026-05-01 01:01:00 UTC",
        "company_name": "Example Customer",
        "organisation_id": "org_1",
        "organisation_name": "Example Org",
    }


class LaunchbotSupportWatchServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_support_watch_server.py")

    def test_exposes_read_only_preview_tool_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["preview_weekly_support_watch_report"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "create", "update", "assign", "tag", "delete"]:
            self.assertNotIn(forbidden, tool_names)

    def test_missing_bigquery_cli_blocks_before_dedupe_network(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module.core.shutil, "which", return_value=None
        ), patch.object(
            self.module.core.urllib.request, "urlopen", side_effect=AssertionError("should not call network")
        ):
            result = self.module.preview_weekly_support_watch_report(
                window_start_iso="2026-05-01T00:00:00Z",
                window_end_iso="2026-05-08T00:00:00Z",
                include_traces=False,
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("BigQuery Intercom conversations source unavailable", result["answer"])
        self.assertFalse(result["scope"]["will_post_message"])

    def test_bigquery_query_uses_conversations_parts_and_org_mapping(self):
        query = self.module.core.build_intercom_conversations_query()

        self.assertIn("intercom.conversations", query)
        self.assertIn("intercom.conversation_parts", query)
        self.assertIn("analytics.dim_org_company", query)
        self.assertIn("candidate_score", query)
        self.assertIn("REGEXP_CONTAINS", query)
        self.assertNotIn("tickets" + "/search", query)

    def test_default_whatsapp_source_is_native_bigquery_table(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                self.module.core.whatsapp_bigquery_view(),
                "analytics.support_watch_whatsapp_ticket_logs",
            )
            query = self.module.core.build_whatsapp_counts_query()

        self.assertIn("analytics.support_watch_whatsapp_ticket_logs", query)
        self.assertNotIn("gsheets.", query)

    def test_bigquery_timeout_kills_query_process_group(self):
        class FakeProcess:
            pid = 12345
            returncode = None

            def __init__(self):
                self.calls = 0

            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired(["bq"], timeout)
                self.returncode = -15
                return "", ""

        fake_process = FakeProcess()
        with patch.dict(os.environ, {"LAUNCHBOT_SUPPORT_WATCH_BQ_TIMEOUT_SECONDS": "5"}, clear=True), patch.object(
            self.module.core.shutil,
            "which",
            return_value="/usr/bin/bq",
        ), patch.object(self.module.core.subprocess, "Popen", return_value=fake_process), patch.object(
            self.module.core.os,
            "killpg",
        ) as killpg:
            with self.assertRaises(self.module.core.LaunchbotSupportWatchError) as raised:
                self.module.core.run_bigquery_query("SELECT 1", {}, project="staffany-warehouse")

        self.assertIn("BigQuery query timed out after 5 seconds", str(raised.exception))
        killpg.assert_called()

    def test_bigquery_source_combines_intercom_and_whatsapp_status(self):
        calls = []

        def fake_bigquery(query, params, project=""):
            calls.append(query)
            if "total_conversations" in query:
                return [{"total_conversations": "478", "total_conversation_parts": "5416"}]
            if "total_whatsapp_rows" in query:
                return [{"total_whatsapp_rows": "42", "latest_reported_date": "2026-05-07"}]
            if "conversation_parts" in query:
                return [support_item("1001", "Payroll blocked", "cannot run payroll error E101")]
            return [support_item("wa-1", "Payroll blocked again", "cannot run payroll error E101", source_type="whatsapp_ticket_log")]

        with patch.object(self.module.core, "run_bigquery_query", side_effect=fake_bigquery):
            rows, status = self.module.core.search_bigquery_support_items(
                datetime(2026, 5, 1, tzinfo=timezone.utc),
                datetime(2026, 5, 8, tzinfo=timezone.utc),
                max_items=2,
            )

        self.assertEqual([row["ticket_id"] for row in rows], ["1001", "wa-1"])
        self.assertEqual(status["intercom_conversations"]["row_count"], 1)
        self.assertEqual(status["intercom_conversations"]["total_conversations"], 478)
        self.assertEqual(status["intercom_conversations"]["total_conversation_parts"], 5416)
        self.assertEqual(status["whatsapp_ticket_logs"]["row_count"], 1)
        self.assertEqual(status["whatsapp_ticket_logs"]["total_matching_rows"], 42)
        self.assertEqual(status["whatsapp_ticket_logs"]["latest_reported_date"], "2026-05-07")

    def test_preview_clusters_redacts_and_dedupes_without_mutation(self):
        raw_tickets = [
            support_item("1001", "Payroll blocked for user@example.com", "cannot run payroll error E101 for +65 9123 4567"),
            support_item("1002", "Payroll blocked", "cannot run payroll error E101"),
            support_item("1003", "Payroll blocked", "cannot run payroll error E101"),
        ]

        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module.core,
            "search_bigquery_support_items",
            return_value=(raw_tickets, {"intercom_conversations": {"status": "verified", "row_count": 3}}),
        ), patch.object(self.module.core, "fetch_slack_dedupe_texts", return_value=([], "verified")), patch.object(
            self.module.core, "fetch_edt_issues", return_value=([], "verified")
        ), patch.object(
            self.module.core,
            "trace_code_evidence",
            return_value={"status": "verified", "matches": [{"path": "apps/payroll/index.ts", "line": "42"}], "recent_changes": []},
        ):
            result = self.module.preview_weekly_support_watch_report(
                window_start_iso="2026-05-01T00:00:00Z",
                window_end_iso="2026-05-08T00:00:00Z",
            )

        self.assertEqual(result["confidence"], "verified")
        answer = result["answer"]
        self.assertEqual(answer["ticket_count"], 3)
        self.assertEqual(answer["source_status"]["intercom_conversations"]["row_count"], 3)
        self.assertEqual(len(answer["new_findings"]), 1)
        finding = answer["new_findings"][0]
        self.assertEqual(finding["product_area"], "PayrollAny")
        self.assertEqual(finding["ticket_ids"], ["1001", "1002", "1003"])
        self.assertIn("[email]", finding["evidence_tickets"][0]["title"])
        self.assertIn("[phone]", finding["evidence_tickets"][0]["summary"])
        self.assertTrue(answer["slack_report"].startswith("Launchbot automation:"))
        self.assertFalse(answer["will_post_message"])
        self.assertFalse(answer["will_create_ticket"])
        self.assertFalse(answer["will_tag_engineer"])
        self.assertFalse(answer["raw_transcript_persisted"])

    def test_slack_or_edt_match_dedupes_finding(self):
        finding = {
            "signature": "payroll|topic|payroll|blocked",
            "search_terms": ["payroll", "blocked"],
            "ticket_ids": ["1001"],
        }
        with patch.object(
            self.module.core,
            "fetch_slack_dedupe_texts",
            return_value=([{"channel_id": "C123", "ts": "1.0", "text": "payroll blocked already in duty"}], "verified"),
        ), patch.object(self.module.core, "fetch_edt_issues", return_value=([], "verified")):
            new_findings, deduped, sources = self.module.core.dedupe_findings(
                [finding],
                datetime(2026, 5, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(new_findings, [])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["dedupe_match"]["source"], "slack")
        self.assertEqual(sources["slack"], "verified")

    def test_resolve_slack_channel_id_uses_public_channel_lookup_only(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            return {
                "channels": [
                    {"name": "all-bugs-production", "id": "CBUGS"},
                ],
                "response_metadata": {"next_cursor": ""},
            }

        with patch.object(self.module.core, "slack_api", side_effect=fake_slack_api):
            channel_id = self.module.core.resolve_slack_channel_id("all-bugs-production")

        self.assertEqual(channel_id, "CBUGS")
        self.assertEqual(calls[0][0], "conversations.list")
        self.assertEqual(calls[0][1]["types"], "public_channel")
        self.assertNotIn("private_channel", calls[0][1]["types"])

    def test_dedupe_channel_ids_resolve_default_public_channel_name(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module.core,
            "resolve_slack_channel_id",
            return_value="CDUTY",
        ):
            self.assertEqual(self.module.core.dedupe_channel_ids(), ["CDUTY"])

    def test_dedupe_channel_ids_preserve_explicit_ids_and_add_name_resolution(self):
        with patch.dict(
            os.environ,
            {
                "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS": "CEXPLICIT",
                "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_NAMES": "team-cs-eng-duty",
            },
            clear=True,
        ), patch.object(
            self.module.core,
            "resolve_slack_channel_id",
            return_value="CDUTY",
        ):
            self.assertEqual(self.module.core.dedupe_channel_ids(), ["CEXPLICIT", "CDUTY"])


if __name__ == "__main__":
    unittest.main()
