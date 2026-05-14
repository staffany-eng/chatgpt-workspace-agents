import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from test_helpers import load_mcp_module


def load_slack_module():
    return load_mcp_module("slack_nurtureany_server.py", "slack_nurtureany_server_under_test")


class SlackNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_slack_module()

    def test_exposes_read_only_context_tool_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            [
                "get_current_slack_thread_context",
                "get_selected_slack_thread_context",
                "read_recent_slack_intent_context",
            ],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "update", "delete"]:
            self.assertNotIn(forbidden, tool_names)

    def test_missing_token_blocks_without_network(self):
        with patch.dict(os.environ, {"NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call Slack")
        ):
            result = self.module.read_recent_slack_intent_context("C123", current_ts="1770000000.000000")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("SLACK_BOT_TOKEN", result["answer"])

    def test_unconfigured_channel_blocks_without_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call Slack")):
            result = self.module.read_recent_slack_intent_context("C999", current_ts="1770000000.000000")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured channel IDs", result["answer"])

    def test_history_reads_are_capped_and_redacted(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.history":
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": "1770000000.000001",
                            "user": "U123",
                            "text": "can check jeremy WhatsApp count today? email test@example.com +65 9123 4567",
                        }
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000001"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.read_recent_slack_intent_context(
                "C123", current_ts="1770000000.000002", limit=99, lookback_minutes=99
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["requested_limit"], self.module.MAX_CONTEXT_MESSAGES)
        self.assertEqual(result["scope"]["lookback_minutes"], self.module.MAX_LOOKBACK_MINUTES)
        self.assertEqual(calls[0][0], "conversations.history")
        self.assertEqual(calls[0][1]["channel"], "C123")
        message = result["answer"]["messages"][0]
        self.assertIn("[email]", message["summary"])
        self.assertIn("[phone]", message["summary"])
        self.assertEqual(message["permalink"], "https://staffany.slack.com/archives/C123/p1770000000000001")
        self.assertFalse(result["answer"]["will_post_message"])
        self.assertFalse(result["answer"]["transcript_persisted"])

    def test_thread_replies_path(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1769999900.000000", "user": "UOLD", "text": "old"},
                        {"ts": "1770000000.000000", "user": "U123", "text": "run this quick check"},
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.read_recent_slack_intent_context(
                "C123", thread_ts="1769999999.000000", current_ts="1770000000.000000", lookback_minutes=1
            )

        self.assertEqual(calls[0][0], "conversations.replies")
        self.assertEqual(result["answer"]["message_count"], 1)
        self.assertEqual(result["answer"]["messages"][0]["summary"], "run this quick check")

    def test_current_thread_reads_are_capped_and_redacted(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": "1770000000.000000",
                            "user": "U123",
                            "text": "thread context for test@example.com +65 9123 4567",
                        }
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_current_slack_thread_context(
                "C123", "1770000000.000000", current_ts="1770000001.000000", limit=99
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["requested_limit"], self.module.MAX_THREAD_CONTEXT_MESSAGES)
        self.assertEqual(calls[0][0], "conversations.replies")
        self.assertEqual(calls[0][1]["channel"], "C123")
        self.assertEqual(calls[0][1]["ts"], "1770000000.000000")
        message = result["answer"]["messages"][0]
        self.assertIn("[email]", message["summary"])
        self.assertIn("[phone]", message["summary"])
        self.assertFalse(result["answer"]["will_mutate_slack"])
        self.assertFalse(result["answer"]["will_post_message"])
        self.assertFalse(result["answer"]["transcript_persisted"])

    def test_selected_permalink_thread_reads_parse_thread_ts(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1770000000.000000", "user": "U123", "text": "root"},
                        {"ts": "1770000002.000000", "user": "U456", "text": "reply"},
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        permalink = "https://staffany.slack.com/archives/C123/p1770000002000000?thread_ts=1770000000.000000&cid=C123"
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(permalink, limit=2)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "conversations.replies")
        self.assertEqual(calls[0][1]["channel"], "C123")
        self.assertEqual(calls[0][1]["ts"], "1770000000.000000")
        self.assertEqual(result["answer"]["message_count"], 2)

    def test_selected_permalink_uses_separate_thread_context_channel_allowlist(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1770000000.000000", "user": "U123", "text": "source thread from another channel"},
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C999/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123",
                "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS": "C999",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(
                "https://staffany.slack.com/archives/C999/p1770000000000000"
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "conversations.replies")
        self.assertEqual(calls[0][1]["channel"], "C999")
        self.assertEqual(result["answer"]["messages"][0]["summary"], "source thread from another channel")

    def test_selected_permalink_auto_joins_configured_public_channel_before_retry(self):
        calls = []
        reply_attempts = 0

        def fake_slack_api(method, params):
            nonlocal reply_attempts
            calls.append((method, params))
            if method == "conversations.replies":
                reply_attempts += 1
                if reply_attempts == 1:
                    raise self.module.SlackIntentError("Slack API returned error: not_in_channel")
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1770000000.000000", "user": "U123", "text": "joined public channel thread"},
                    ],
                }
            if method == "conversations.join":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True}}
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C999/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123",
                "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS": "C999",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(
                "https://staffany.slack.com/archives/C999/p1770000000000000"
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual([call[0] for call in calls[:3]], ["conversations.replies", "conversations.join", "conversations.replies"])
        self.assertEqual(calls[1][1]["channel"], "C999")
        self.assertIn("conversations.join", result["source"])
        self.assertTrue(result["answer"]["joined_public_channel"])
        self.assertEqual(result["answer"]["messages"][0]["summary"], "joined public channel thread")

    def test_selected_permalink_blocks_malformed_without_network(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "test-bot-token"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call Slack")
        ):
            result = self.module.get_selected_slack_thread_context("https://staffany.slack.com/not-a-thread")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Malformed Slack permalink", result["answer"])

    def test_selected_permalink_blocks_unconfigured_channel_without_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call Slack")):
            result = self.module.get_selected_slack_thread_context(
                "https://staffany.slack.com/archives/C999/p1770000000000000"
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured thread-context channel IDs", result["answer"])


if __name__ == "__main__":
    unittest.main()
