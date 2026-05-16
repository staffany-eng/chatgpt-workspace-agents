from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


SOURCE_PERMALINK = "https://staffany.slack.com/archives/C0A0V39AK44/p1778814810682959"


class StaffAnySlackContextServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("staffany_slack_context_server.py")

    def test_exposes_selected_thread_read_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["get_current_slack_thread_context", "get_selected_slack_thread_context"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "search", "react", "pin", "join", "delete"]:
            self.assertNotIn(forbidden, tool_names)

    def test_missing_token_blocks_without_network(self):
        with patch.dict(os.environ, {"STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS": "C123"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call Slack")
        ):
            result = self.module.get_current_slack_thread_context("C123", "1770000000.000000")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("SLACK_BOT_TOKEN", result["answer"])

    def test_unconfigured_channel_blocks_without_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=AssertionError("should not call Slack")):
            result = self.module.get_selected_slack_thread_context(SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured public/source channel IDs", result["answer"])

    def test_selected_permalink_thread_reads_are_capped_and_redacted(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": "1778814810.682959",
                            "user": "U123",
                            "text": "can check BigQuery for test@example.com and +65 9123 4567 from this thread?",
                        }
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": SOURCE_PERMALINK}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS": "C0A0V39AK44",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(SOURCE_PERMALINK, limit=99)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["requested_limit"], self.module.MAX_THREAD_CONTEXT_MESSAGES)
        self.assertEqual(calls[0][0], "conversations.replies")
        self.assertEqual(calls[0][1]["channel"], "C0A0V39AK44")
        self.assertEqual(calls[0][1]["ts"], "1778814810.682959")
        message = result["answer"]["messages"][0]
        self.assertIn("[email]", message["summary"])
        self.assertIn("[phone]", message["summary"])
        self.assertEqual(message["permalink"], SOURCE_PERMALINK)
        self.assertFalse(result["answer"]["will_post_message"])
        self.assertFalse(result["answer"]["will_search_workspace"])
        self.assertFalse(result["answer"]["will_add_reaction"])
        self.assertFalse(result["answer"]["will_pin_message"])
        self.assertFalse(result["answer"]["transcript_persisted"])

    def test_current_thread_uses_home_channel_fallback(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {"ok": True, "messages": [{"ts": "1770000000.000000", "user": "U1", "text": "home thread"}]}
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C0AU19E6T0C/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "SLACK_HOME_CHANNEL": "C0AU19E6T0C"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_current_slack_thread_context("C0AU19E6T0C", "1770000000.000000")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "conversations.replies")


if __name__ == "__main__":
    unittest.main()
