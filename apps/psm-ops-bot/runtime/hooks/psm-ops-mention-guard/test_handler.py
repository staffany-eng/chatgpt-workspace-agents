from __future__ import annotations

import asyncio
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


HANDLER_PATH = Path(__file__).parent / "handler.py"


def load_handler():
    spec = importlib.util.spec_from_file_location("psm_ops_mention_guard_handler", HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScanResponseTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()

    def test_clean_reply_with_no_mention_returns_no_violations(self):
        violations = self.module.scan_response("Logged this on <https://x/PCO-31|PCO-31>.", sender_user_id="U043M9HRWHG")

        self.assertEqual(violations, [])

    def test_only_tagger_mention_is_allowed(self):
        violations = self.module.scan_response(
            "Hey <@U043M9HRWHG>, noted on <https://x/PCO-31|PCO-31>.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, [])

    def test_non_tagger_mention_is_a_violation(self):
        violations = self.module.scan_response(
            "Hey <@U6E68280P|Kai Yi>, logged this on PCO-31.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P"])

    def test_multiple_non_tagger_mentions_dedup_and_order_preserved(self):
        violations = self.module.scan_response(
            "Hey <@U6E68280P>, FYI <@U05P7PFUWDP> and <@U6E68280P> again.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P", "U05P7PFUWDP"])

    def test_bot_self_reference_is_allowed(self):
        violations = self.module.scan_response(
            "Hey <@U043M9HRWHG>, <@U0B39JHV8TG> here.",
            sender_user_id="u043m9hrwhg",  # lowercased on purpose
            bot_user_id="U0B39JHV8TG",
        )

        self.assertEqual(violations, [])

    def test_workspace_id_w_prefix_is_recognized(self):
        violations = self.module.scan_response(
            "FYI <@W123ABC>.",
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["W123ABC"])

    def test_dict_response_is_scanned_as_string(self):
        violations = self.module.scan_response(
            {"slack_reply": "ping <@U6E68280P>"},
            sender_user_id="U043M9HRWHG",
        )

        self.assertEqual(violations, ["U6E68280P"])


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()

    def test_empty_response_is_skipped(self):
        verdict = self.module.evaluate({"response": "", "user_id": "U043M9HRWHG"})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "empty_response")
        self.assertEqual(verdict["violations"], [])

    def test_cron_output_is_skipped_even_with_stray_mentions(self):
        cron_text = "PSM Ops automation: PCO assignment hygiene - 2026-05-26\n*PS Team: Kai Yi* <@U6E68280P>"
        verdict = self.module.evaluate({"response": cron_text, "user_id": "U043M9HRWHG"})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "cron_output")

    def test_silent_cron_output_is_skipped(self):
        verdict = self.module.evaluate({
            "response": "[SILENT] PSM Ops automation: no PCO assignment hygiene gaps for 2026-05-26.",
            "user_id": "U043M9HRWHG",
        })

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "cron_output")

    def test_non_slack_platform_is_skipped(self):
        verdict = self.module.evaluate({
            "response": "Hey <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "cli",
        })

        self.assertTrue(verdict["skipped"])
        self.assertTrue(verdict["skip_reason"].startswith("non_slack_platform"))

    def test_missing_sender_is_skipped(self):
        verdict = self.module.evaluate({"response": "Hey <@U6E68280P>", "user_id": ""})

        self.assertTrue(verdict["skipped"])
        self.assertEqual(verdict["skip_reason"], "missing_sender")

    def test_violation_yields_expected_fields(self):
        verdict = self.module.evaluate({
            "response": "Hey <@U6E68280P|Kai Yi>, logged on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        })

        self.assertFalse(verdict["skipped"])
        self.assertEqual(verdict["violations"], ["U6E68280P"])
        self.assertEqual(verdict["sender"], "U043M9HRWHG")
        self.assertIn("PCO-31", verdict["response_preview"])


class HandleAlertingTests(unittest.TestCase):
    def setUp(self):
        self.module = load_handler()
        self.env = patch.dict(
            os.environ,
            {
                "PSM_OPS_CENTRAL_SLACK_CHANNEL_ID": "C0B2VT50YT1",
                "SLACK_HOME_CHANNEL": "",
                "SLACK_BOT_TOKEN": "test-fake-bot-token",
                "PSM_OPS_SLACK_BOT_TOKEN": "",
                "PSM_OPS_BOT_USER_ID": "U0B39JHV8TG",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_violation_posts_central_warning(self):
        context = {
            "response": "Hey <@U6E68280P|Kai Yi>, logged on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
            "session_id": "sess-1",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        self.assertEqual(fake_post.call_count, 1)
        verdict = fake_post.call_args[0][0]
        self.assertEqual(verdict["sender"], "U043M9HRWHG")
        self.assertEqual(verdict["violations"], ["U6E68280P"])

    def test_clean_reply_does_not_post(self):
        context = {
            "response": "Hey <@U043M9HRWHG>, noted on PCO-31.",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        fake_post.assert_not_called()

    def test_cron_output_does_not_post(self):
        context = {
            "response": "PSM Ops automation: PCO assignment hygiene - 2026-05-26\n*PS Team: Kai Yi* <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("agent:end", context))

        fake_post.assert_not_called()

    def test_non_agent_end_event_is_ignored(self):
        context = {
            "response": "Hey <@U6E68280P>",
            "user_id": "U043M9HRWHG",
            "platform": "slack",
        }

        with patch.object(self.module, "_post_audit_warning") as fake_post:
            asyncio.run(self.module.handle("session:start", context))

        fake_post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
