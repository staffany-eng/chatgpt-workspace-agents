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
                "ticket_ready",
                source_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
                issue_key="PCO-789",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(posts[0][0], "chat.postMessage")
        self.assertEqual(posts[0][1]["channel"], "C123")
        self.assertIn("ticket_ready", posts[0][1]["text"])

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
