from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_DIR = Path(__file__).parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import psm_slack_notifier  # noqa: E402


class PsmSlackNotifierTest(unittest.TestCase):
    def setUp(self):
        importlib.reload(psm_slack_notifier)

    def test_parse_slack_permalink(self):
        parsed = psm_slack_notifier.parse_slack_permalink(
            "https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579?thread_ts=1778205303.989579&channel=C0B2VT50YT1"
        )

        self.assertEqual(parsed["channel_id"], "C0B2VT50YT1")
        self.assertEqual(parsed["message_ts"], "1778205303.989579")
        self.assertEqual(parsed["thread_ts"], "1778205303.989579")

    def test_build_audit_text_redacts_tokens_and_truncates(self):
        text = psm_slack_notifier.build_ps_wee_audit_text(
            "ticket_created",
            source_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
            issue_key="PCO-789",
            issue_url="https://staffany.atlassian.net/browse/PCO-789",
            requester="psm@staffany.com",
            customer="Fei Siong",
            summary="xoxb-secret-token should not leak",
            jira_payload={"JIRA_API_TOKEN": "secret-value", "summary": "Payroll blocked"},
        )

        self.assertIn("PSM Ops automation: PS WEE audit - ticket_created", text)
        self.assertIn("Source thread:", text)
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-789|PCO-789>", text)
        self.assertNotIn("xoxb-secret-token", text)
        self.assertNotIn("secret-value", text)

    def test_post_uses_bot_token_only_and_skips_without_it(self):
        with patch.dict(os.environ, {"SLACK_USER_TOKEN": "xoxp-user", "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C123"}, clear=True):
            result = psm_slack_notifier.post_ps_wee_audit("ticket_created")

        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "missing Slack bot token or central channel")

    def test_post_sends_chat_post_message_with_transcript_fetch_result(self):
        posts = []

        def fake_post(method, body):
            posts.append((method, body))
            return {"ok": True, "channel": body["channel"], "ts": "123.456"}

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "xoxb-test",
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C123",
                "PSM_OPS_CENTRAL_FETCH_SLACK_THREAD": "false",
            },
            clear=True,
        ):
            psm_slack_notifier._slack_post = fake_post
            result = psm_slack_notifier.post_ps_wee_audit(
                "ticket_update_synced",
                source_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
                issue_key="PCO-789",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(posts[0][0], "chat.postMessage")
        self.assertEqual(posts[0][1]["channel"], "C123")
        self.assertIn("ticket_update_synced", posts[0][1]["text"])

    def test_post_replaces_unresolved_requester_id_with_source_thread_poster(self):
        posts = []

        def fake_get(method, params):
            if method == "conversations.replies":
                return {
                    "ok": True,
                    "messages": [
                        {"ts": "1778766368.220149", "user": "U6E68280P", "text": "<@U0B39JHV8TG> please create ticket"}
                    ],
                }
            if method == "users.info" and params.get("user") == "U04NWSJ0LJE":
                raise RuntimeError("Slack API failed: user_not_found")
            if method == "users.info" and params.get("user") == "U6E68280P":
                return {
                    "ok": True,
                    "user": {
                        "id": "U6E68280P",
                        "real_name": "Kai Yi Lee",
                        "profile": {"real_name": "Kai Yi Lee", "display_name": "Kai Yi", "email": "kaiyi@staffany.com"},
                    },
                }
            raise AssertionError((method, params))

        def fake_post(method, body):
            posts.append((method, body))
            return {"ok": True, "channel": body["channel"], "ts": "123.456"}

        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test", "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C123"}, clear=True):
            psm_slack_notifier._slack_get = fake_get
            psm_slack_notifier._slack_post = fake_post
            result = psm_slack_notifier.post_ps_wee_audit(
                "ticket_created",
                source_thread_url="https://staffany.slack.com/archives/C0AGERBVB0C/p1778766368220149",
                requester="u04nwsj0lje",
            )

        self.assertTrue(result["ok"])
        self.assertIn("Requester: Kai Yi Lee <@U6E68280P> kaiyi@staffany.com", posts[0][1]["text"])
        self.assertNotIn("Requester: u04nwsj0lje", posts[0][1]["text"])

    def test_record_adoption_event_writes_only_when_path_configured(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            metrics_path = Path(tmpdir) / "adoption.jsonl"
            with patch.dict(os.environ, {"PSM_OPS_ADOPTION_METRICS_PATH": str(metrics_path)}, clear=True):
                psm_slack_notifier.record_adoption_event("ticket_created", {"issue_key": "PCO-789"})

            text = metrics_path.read_text(encoding="utf-8")
            self.assertIn("ticket_created", text)
            self.assertIn("PCO-789", text)


if __name__ == "__main__":
    unittest.main()
