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
                "audit_standup_down_accountability",
                "extract_inbound_lead_alerts",
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

    def test_selected_permalink_can_auto_join_unconfigured_public_channel_when_enabled(self):
        calls = []
        reply_attempts = 0

        def fake_slack_api(method, params):
            nonlocal reply_attempts
            calls.append((method, params))
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "conversations.replies":
                reply_attempts += 1
                if reply_attempts == 1:
                    raise self.module.SlackIntentError("Slack API returned error: not_in_channel")
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1770000000.000000", "user": "U123", "text": "public channel source thread"},
                    ],
                }
            if method == "conversations.join":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C999/p1770000000000000"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "NURTUREANY_SLACK_INTENT_CHANNEL_IDS": "C123",
                "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS": "all",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(
                "https://staffany.slack.com/archives/C999/p1770000000000000"
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(
            [call[0] for call in calls[:4]],
            ["conversations.info", "conversations.replies", "conversations.join", "conversations.replies"],
        )
        self.assertEqual(result["answer"]["message_count"], 1)
        self.assertTrue(result["answer"]["may_join_public_channel"])
        self.assertTrue(result["answer"]["joined_public_channel"])

    def test_selected_permalink_blocks_private_channel_even_when_all_public_enabled(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": True}}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS": "all",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.get_selected_slack_thread_context(
                "https://staffany.slack.com/archives/C999/p1770000000000000"
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual([call[0] for call in calls], ["conversations.info"])
        self.assertIn("public channels", result["answer"])

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

    def test_inbound_alert_extraction_requires_configured_channel(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_INBOUND_ALERT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call Slack")):
            result = self.module.extract_inbound_lead_alerts("C999")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured public inbound channel IDs", result["answer"])

    def test_inbound_alert_extraction_reads_safe_alerts_and_redacts(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "conversations.history":
                self.assertLessEqual(int(params["limit"]), 50)
                return {
                    "ok": True,
                    "messages": [
                        {
                            "ts": "1770000000.000001",
                            "user": "U123",
                            "text": "New incoming RaD from Name: Jane Tan Company: Noci Bakehouse email jane@noci.example phone +65 9123 4567 assign <@UAE123>",
                        }
                    ],
                }
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000001"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_INBOUND_ALERT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.extract_inbound_lead_alerts("C123", current_ts="1770000001.000000", limit=99)

        alert = result["answer"]["alerts"][0]
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["message_count"], 1)
        self.assertFalse(result["answer"]["will_mutate_slack"])
        self.assertFalse(result["answer"]["transcript_persisted"])
        self.assertEqual(alert["source"], "RaD")
        self.assertEqual(alert["tagged_slack_user_ids"], ["UAE123"])
        self.assertEqual(alert["lead_hints"]["email_domain"], "noci.example")
        self.assertEqual(alert["lead_hints"]["phone_hint"], "masked_last4:4567")
        self.assertNotIn("+65 9123 4567", str(result))
        self.assertNotIn("jane@noci.example", str(result))
        self.assertIn("chat.getPermalink", [call[0] for call in calls])

    def test_inbound_alert_extraction_auto_joins_configured_public_channel(self):
        history_attempts = 0

        def fake_slack_api(method, params):
            nonlocal history_attempts
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "conversations.history":
                history_attempts += 1
                if history_attempts == 1:
                    raise self.module.SlackIntentError("Slack API returned error: not_in_channel")
                return {"ok": True, "messages": [{"ts": "1770000000.000001", "user": "U123", "text": "WhatsApp inbound <@UAE123>"}]}
            if method == "conversations.join":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1770000000000001"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_INBOUND_ALERT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.extract_inbound_lead_alerts("C123", current_ts="1770000001.000000")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["joined_public_channel"])
        self.assertEqual(result["answer"]["alerts"][0]["source"], "WhatsApp")

    def test_standup_audit_missing_allowlist_blocks_without_network(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "test-bot-token"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call Slack")
        ):
            result = self.module.audit_standup_down_accountability("C999", "2026-05-16")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS", result["answer"])

    def test_standup_audit_unconfigured_channel_blocks_without_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call Slack")):
            result = self.module.audit_standup_down_accountability("C999", "2026-05-16")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured channel IDs", result["answer"])

    def test_standup_audit_blocks_private_configured_channel(self):
        calls = []

        def fake_slack_api(method, params):
            calls.append((method, params))
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": True}}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.audit_standup_down_accountability("C123", "2026-05-16")

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual([call[0] for call in calls], ["conversations.info"])
        self.assertIn("public Slack channels only", result["answer"])

    def test_standup_audit_blocks_future_date_without_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call Slack")):
            result = self.module.audit_standup_down_accountability("C123", "2999-01-01")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("date cannot be in the future", result["answer"])

    def test_standup_audit_uses_sgt_day_roster_and_safe_status_rows(self):
        calls = []
        history_attempts = 0

        def fake_slack_api(method, params):
            nonlocal history_attempts
            calls.append((method, params))
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "conversations.members":
                return {
                    "ok": True,
                    "members": ["U1", "U2", "U3", "U5", "UBOT", "UDEL"],
                    "response_metadata": {"next_cursor": ""},
                }
            if method == "conversations.history":
                history_attempts += 1
                if history_attempts == 1:
                    raise self.module.SlackIntentError("Slack API returned error: not_in_channel")
                if history_attempts == 2:
                    return {
                        "ok": True,
                        "messages": [
                            {"ts": "1778800000.000001", "user": "U1", "text": "stand up baseline"},
                            {"ts": "1778800000.000002", "user": "U2", "text": "standdown baseline"},
                            {"ts": "1778800000.000003", "user": "U3", "text": "SOD baseline"},
                            {"ts": "1778800000.000004", "user": "U4", "text": "stand up but inactive member"},
                            {"ts": "1778800000.000005", "user": "UBOT", "text": "stand up bot"},
                            {"ts": "1778800000.000006", "user": "UDEL", "text": "stand up deleted"},
                        ],
                        "response_metadata": {"next_cursor": ""},
                    }
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1778889601.000001", "user": "U1", "text": "stand up today test@example.com +65 9123 4567"},
                        {"ts": "1778893201.000001", "user": "U1", "text": "stand down today with confidential body"},
                        {"ts": "1778889601.000002", "user": "U2", "text": "stand up today only"},
                        {"ts": "1778893201.000003", "user": "U3", "text": "EOD only"},
                        {"ts": "1778893201.000004", "user": "U5", "text": "stand up new participant"},
                    ],
                    "response_metadata": {"next_cursor": ""},
                }
            if method == "conversations.join":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "users.info":
                profiles = {
                    "U1": {"real_name": "Alice Sales", "profile": {"title": "Sales AE"}},
                    "U2": {"real_name": "Maya Marketing", "profile": {"title": "Marketing"}},
                    "U3": {"real_name": "Ben Ops", "profile": {"title": "BD Ops"}},
                    "UBOT": {"real_name": "Bot User", "is_bot": True, "profile": {"title": "Sales"}},
                    "UDEL": {"real_name": "Deleted User", "deleted": True, "profile": {"title": "Sales"}},
                }
                user = profiles[params["user"]]
                user.setdefault("id", params["user"])
                return {"ok": True, "user": user}
            if method == "chat.getPermalink":
                return {
                    "ok": True,
                    "permalink": f"https://staffany.slack.com/archives/C123/p{str(params['message_ts']).replace('.', '')}",
                }
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.audit_standup_down_accountability("C123", "2026-05-16", roster_lookback_days=99)

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["joined_public_channel"])
        self.assertEqual(result["scope"]["roster_lookback_days"], self.module.MAX_STANDUP_LOOKBACK_DAYS)
        history_calls = [call for call in calls if call[0] == "conversations.history"]
        self.assertEqual(history_calls[0][1]["latest"], "1778860800.000000")
        self.assertEqual(history_calls[0][1]["oldest"], "1771084800.000000")
        self.assertEqual(history_calls[-1][1]["latest"], "1778947200.000000")
        self.assertEqual(history_calls[-1][1]["oldest"], "1778860800.000000")
        self.assertEqual(result["answer"]["expected_people_count"], 3)
        self.assertEqual(result["answer"]["complete_count"], 1)
        self.assertEqual(result["answer"]["missing_standup_count"], 1)
        self.assertEqual(result["answer"]["missing_standdown_count"], 1)
        self.assertEqual(result["answer"]["missing_both_count"], 0)
        rows_by_user = {row["user_id"]: row for row in result["answer"]["rows"]}
        self.assertEqual(rows_by_user["U1"]["status"], "complete")
        self.assertEqual(rows_by_user["U2"]["status"], "missing_standdown")
        self.assertEqual(rows_by_user["U3"]["status"], "missing_standup")
        self.assertNotIn("UBOT", rows_by_user)
        self.assertNotIn("UDEL", rows_by_user)
        result_json = str(result)
        self.assertNotIn("test@example.com", result_json)
        self.assertNotIn("+65 9123 4567", result_json)
        self.assertNotIn("confidential body", result_json)
        self.assertFalse(result["answer"]["will_post_message"])
        self.assertFalse(result["answer"]["transcript_persisted"])
        self.assertFalse(result["answer"]["raw_note_bodies_returned"])

    def test_standup_audit_marks_unknown_role_needs_check(self):
        def fake_slack_api(method, params):
            if method == "conversations.info":
                return {"ok": True, "channel": {"id": params["channel"], "is_channel": True, "is_private": False}}
            if method == "conversations.members":
                return {"ok": True, "members": ["U1"], "response_metadata": {"next_cursor": ""}}
            if method == "conversations.history":
                text = "stand up baseline" if params["latest"] == "1778860800.000000" else "stand up today"
                return {"ok": True, "messages": [{"ts": "1778800000.000001", "user": "U1", "text": text}], "response_metadata": {"next_cursor": ""}}
            if method == "users.info":
                return {"ok": True, "user": {"id": "U1", "real_name": "Unknown Role", "profile": {"title": "Operations"}}}
            if method == "chat.getPermalink":
                return {"ok": True, "permalink": "https://staffany.slack.com/archives/C123/p1778800000000001"}
            raise AssertionError(f"unexpected method {method}")

        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api):
            result = self.module.audit_standup_down_accountability("C123", "2026-05-16")

        self.assertEqual(result["answer"]["role_needs_check_count"], 1)
        self.assertTrue(result["answer"]["rows"][0]["role_needs_check"])


if __name__ == "__main__":
    unittest.main()
