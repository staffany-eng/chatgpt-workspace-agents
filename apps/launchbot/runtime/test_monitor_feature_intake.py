from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("monitor-feature-intake.py")
MCP_DIR = MODULE_PATH.parent / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))


def load_monitor_module():
    name = "launchbot_monitor_feature_intake_under_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LaunchbotFeatureIntakeMonitorTest(unittest.TestCase):
    def setUp(self):
        self.module = load_monitor_module()

    def test_candidate_classifier_catches_feature_requests_and_ignores_noise(self):
        self.assertTrue(self.module.is_candidate_text("can we automate inputting new feature requests into KER"))
        self.assertTrue(self.module.is_candidate_text("Customer needs support for bulk shift edit request"))
        for text in ["ok", "+1", "thanks", "Launchbot automation: Potential KER intake detected."]:
            self.assertFalse(self.module.is_candidate_text(text))

    def test_skips_bot_and_automation_messages(self):
        self.assertTrue(self.module.should_skip_message({"ts": "1.0", "bot_id": "B1", "text": "feature request"}))
        self.assertTrue(self.module.should_skip_message({"ts": "1.0", "user": "U1", "text": "Launchbot automation: Previewed KER intake."}))
        self.assertFalse(self.module.should_skip_message({"ts": "1.0", "user": "U1", "text": "can we automate this feature request"}))

    def test_process_channel_posts_one_preview_and_dedupes_state(self):
        state = {"version": 1, "channels": {}, "sources": {}}
        posted = []

        def fake_history(channel_id, oldest, limit):
            return [
                {"ts": "1778752459.023229", "user": "U1", "text": "can we automate feature request intake into KER"},
                {"ts": "1778752500.000000", "bot_id": "B1", "text": "feature request bot noise"},
            ]

        def fake_preview(**kwargs):
            return {
                "confidence": "verified",
                "answer": {
                    "summary": "Automate feature request intake into KER",
                    "source_permalink": self.module.source_url(kwargs["channel_id"], kwargs["thread_ts"], kwargs["message_ts"]),
                    "duplicate": None,
                },
            }

        with patch.object(self.module, "history_messages", side_effect=fake_history), patch.object(
            self.module.intake_core, "preview_feature_intake_from_slack_thread", side_effect=fake_preview
        ), patch.object(self.module, "slack_post", side_effect=lambda method, body: posted.append((method, body)) or {"ok": True, "ts": "1778752460.000000"}):
            first = self.module.process_channel(state, "CF8PK6V4J", 0, 100, False)
            second = self.module.process_channel(state, "CF8PK6V4J", 0, 100, False)

        self.assertEqual([item["action"] for item in first], ["previewed"])
        self.assertEqual([item["action"] for item in second], ["skipped"])
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0][0], "chat.postMessage")
        self.assertIn("Launchbot automation: Potential KER intake detected.", posted[0][1]["text"])
        source = next(iter(state["sources"].values()))
        self.assertEqual(source["status"], "previewed")
        self.assertIn("safe_summary", source)
        self.assertNotIn("raw_transcript", source)

    def test_duplicate_preview_posts_existing_ker_without_create_prompt(self):
        state = {"version": 1, "channels": {}, "sources": {}}
        posted = []

        def fake_preview(**kwargs):
            return {
                "confidence": "needs-check",
                "answer": {
                    "summary": "Automate feature request intake into KER",
                    "source_permalink": self.module.source_url(kwargs["channel_id"], kwargs["thread_ts"], kwargs["message_ts"]),
                    "duplicate": {
                        "issue_key": "KER-1234",
                        "summary": "Automate feature request intake into KER",
                        "url": "https://staffany.atlassian.net/browse/KER-1234",
                    },
                },
            }

        message = {"ts": "1778752459.023229", "user": "U1", "text": "can we automate feature request intake into KER"}
        with patch.object(self.module.intake_core, "preview_feature_intake_from_slack_thread", side_effect=fake_preview), patch.object(
            self.module, "slack_post", side_effect=lambda method, body: posted.append((method, body)) or {"ok": True, "ts": "1778752460.000000"}
        ):
            result = self.module.process_candidate(state, "CF8PK6V4J", message, False)

        self.assertEqual(result["action"], "duplicate_found")
        self.assertIn("Existing KER intake found", posted[0][1]["text"])
        self.assertNotIn("Reply `create intake`", posted[0][1]["text"])

    def test_exact_create_intake_creates_after_preview(self):
        permalink = "https://staffany.slack.com/archives/CF8PK6V4J/p1778752459023229?thread_ts=1778752459.023229&cid=CF8PK6V4J"
        state = {
            "version": 1,
            "channels": {},
            "sources": {
                permalink: {
                    "channel_id": "CF8PK6V4J",
                    "thread_ts": "1778752459.023229",
                    "message_ts": "1778752459.023229",
                    "permalink": permalink,
                    "safe_summary": "Automate feature request intake into KER",
                    "status": "previewed",
                }
            },
        }
        posted = []

        with patch.object(
            self.module,
            "thread_messages",
            return_value=[
                {"ts": "1778752459.023229", "user": "U1", "text": "can we automate feature request intake into KER"},
                {"ts": "1778752460.000000", "user": "U2", "text": "yes"},
                {"ts": "1778752461.000000", "user": "U2", "text": "create intake"},
            ],
        ), patch.object(
            self.module.intake_core,
            "create_feature_intake_from_slack_thread",
            return_value={
                "confidence": "verified",
                "answer": {
                    "created": True,
                    "issue": {"issue_key": "KER-3000"},
                    "slack_reply": "Launchbot automation: Created KER intake <https://staffany.atlassian.net/browse/KER-3000|KER-3000> - Automate feature request intake into KER",
                },
            },
        ) as create_mock, patch.object(
            self.module, "slack_post", side_effect=lambda method, body: posted.append((method, body)) or {"ok": True, "ts": "1778752462.000000"}
        ):
            result = self.module.process_pending_approvals(state, False)

        self.assertEqual(result[0]["action"], "created")
        self.assertEqual(state["sources"][permalink]["status"], "created")
        self.assertEqual(state["sources"][permalink]["issue_key"], "KER-3000")
        create_mock.assert_called_once()
        self.assertIn("Launchbot automation: Created KER intake", posted[0][1]["text"])

    def test_wrong_confirmation_does_not_create(self):
        permalink = "https://staffany.slack.com/archives/CF8PK6V4J/p1778752459023229?thread_ts=1778752459.023229&cid=CF8PK6V4J"
        state = {
            "version": 1,
            "channels": {},
            "sources": {
                permalink: {
                    "channel_id": "CF8PK6V4J",
                    "thread_ts": "1778752459.023229",
                    "message_ts": "1778752459.023229",
                    "permalink": permalink,
                    "safe_summary": "Automate feature request intake into KER",
                    "status": "previewed",
                }
            },
        }
        with patch.object(
            self.module,
            "thread_messages",
            return_value=[{"ts": "1778752460.000000", "user": "U2", "text": "yes"}],
        ), patch.object(self.module.intake_core, "create_feature_intake_from_slack_thread", side_effect=AssertionError("should not create")):
            result = self.module.process_pending_approvals(state, False)

        self.assertEqual(result[0]["action"], "skipped")
        self.assertEqual(result[0]["reason"], "no-approval")
        self.assertEqual(state["sources"][permalink]["status"], "previewed")


if __name__ == "__main__":
    unittest.main()
