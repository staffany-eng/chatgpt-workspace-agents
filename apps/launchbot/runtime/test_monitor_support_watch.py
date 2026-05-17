from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("monitor-support-watch.py")
MCP_DIR = MODULE_PATH.parent / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))


def load_monitor_module():
    name = "launchbot_monitor_support_watch_under_test"
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def args_for(state_path: str, dry_run: bool = False):
    return argparse.Namespace(
        dry_run=dry_run,
        window_start="2026-05-01T00:00:00Z",
        window_end="2026-05-08T00:00:00Z",
        lookback_days=7,
        max_tickets=50,
        state_path=state_path,
        skip_traces=False,
    )


def report_with_findings(signature: str = "payroll|cannotrunpayroll|payroll|blocked"):
    return {
        "window": {"start": "2026-05-01T00:00:00Z", "end": "2026-05-08T00:00:00Z"},
        "ticket_count": 3,
        "source_status": {
            "intercom_conversations": {"status": "verified", "row_count": 2},
            "whatsapp_ticket_logs": {"status": "verified", "row_count": 1},
        },
        "new_findings": [
            {
                "signature": signature,
                "summary": "PayrollAny support signal: cannot run payroll",
                "product_area": "PayrollAny",
                "severity": "high",
                "signal": "shared_error_phrase",
                "ticket_count": 3,
                "ticket_ids": ["1001", "1002", "1003"],
            }
        ],
        "deduped_findings": [],
        "report_signature": signature,
        "slack_report": "Launchbot automation: Weekly support watch found new production-bug signals.",
        "will_post_message": False,
        "will_create_ticket": False,
        "will_tag_engineer": False,
        "raw_transcript_persisted": False,
    }


class LaunchbotSupportWatchMonitorTest(unittest.TestCase):
    def setUp(self):
        self.module = load_monitor_module()

    def test_no_new_findings_means_no_slack_post_but_state_advances(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME": "all-bugs-production"},
            clear=True,
        ), patch.object(
            self.module.support_core,
            "preview_weekly_support_watch_report",
            return_value={
                "confidence": "needs-check",
                "answer": {
                    "window": {"start": "2026-05-01T00:00:00Z", "end": "2026-05-08T00:00:00Z"},
                    "ticket_count": 2,
                    "new_findings": [],
                    "deduped_findings": [],
                    "report_signature": "",
                    "slack_report": "Launchbot automation: Weekly support watch found no new untracked production-bug signals.",
                },
            },
        ), patch.object(self.module, "slack_post", side_effect=AssertionError("should not post")):
            state_path = str(Path(tmp) / "support-watch-state.json")
            result = self.module.run_monitor(args_for(state_path))

            state = json.loads(Path(state_path).read_text(encoding="utf-8"))

        self.assertEqual(result["action"], "skipped")
        self.assertEqual(result["reason"], "no-new-findings")
        self.assertFalse(result["will_post_message"])
        self.assertEqual(state["last_window_end"], "2026-05-08T00:00:00Z")
        self.assertNotIn("raw_transcript", json.dumps(state))

    def test_new_findings_post_to_all_bugs_production_and_persist_safe_state(self):
        posted = []

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME": "all-bugs-production",
                "LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID": "CBUGS",
            },
            clear=True,
        ), patch.object(
            self.module.support_core,
            "preview_weekly_support_watch_report",
            return_value={"confidence": "verified", "answer": report_with_findings()},
        ), patch.object(
            self.module,
            "slack_post",
            side_effect=lambda method, body: posted.append((method, body)) or {"ok": True, "ts": "1778752460.000000"},
        ):
            state_path = str(Path(tmp) / "support-watch-state.json")
            result = self.module.run_monitor(args_for(state_path))
            state = json.loads(Path(state_path).read_text(encoding="utf-8"))

        self.assertEqual(result["action"], "posted")
        self.assertEqual(result["output_channel_name"], "all-bugs-production")
        self.assertEqual(posted[0][0], "chat.postMessage")
        self.assertEqual(posted[0][1]["channel"], "CBUGS")
        self.assertTrue(posted[0][1]["text"].startswith("Launchbot automation:"))
        self.assertFalse(result["will_create_ticket"])
        self.assertFalse(result["will_tag_engineer"])
        self.assertFalse(result["transcript_persisted"])
        self.assertEqual(result["source_status"]["intercom_conversations"]["row_count"], 2)
        self.assertIn("payroll|cannotrunpayroll|payroll|blocked", state["finding_signatures"])
        self.assertNotIn("raw_transcript", json.dumps(state))

    def test_prior_state_dedupe_skips_repeat_signature(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID": "CBUGS"},
            clear=True,
        ), patch.object(
            self.module.support_core,
            "preview_weekly_support_watch_report",
            return_value={"confidence": "verified", "answer": report_with_findings()},
        ), patch.object(self.module, "slack_post", side_effect=AssertionError("should not post duplicate")):
            state_path = Path(tmp) / "support-watch-state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "reports": [],
                        "posted_report_signatures": {},
                        "finding_signatures": {"payroll|cannotrunpayroll|payroll|blocked": {"summary": "already posted"}},
                    }
                ),
                encoding="utf-8",
            )
            result = self.module.run_monitor(args_for(str(state_path)))

        self.assertEqual(result["action"], "skipped")
        self.assertEqual(result["reason"], "no-new-findings")
        self.assertEqual(result["new_finding_count"], 0)

    def test_dry_run_does_not_post_or_write_state(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True), patch.object(
            self.module.support_core,
            "preview_weekly_support_watch_report",
            return_value={"confidence": "verified", "answer": report_with_findings()},
        ), patch.object(self.module, "slack_post", side_effect=AssertionError("should not post in dry-run")):
            state_path = Path(tmp) / "support-watch-state.json"
            result = self.module.run_monitor(args_for(str(state_path), dry_run=True))

        self.assertEqual(result["action"], "would_post")
        self.assertTrue(result["will_post_message"])
        self.assertFalse(state_path.exists())

    def test_dry_run_resolves_public_output_channel_without_posting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME": "all-bugs-production"},
            clear=True,
        ), patch.object(
            self.module.support_core,
            "preview_weekly_support_watch_report",
            return_value={"confidence": "verified", "answer": report_with_findings()},
        ), patch.object(
            self.module.support_core,
            "resolve_slack_channel_id",
            return_value="CBUGS",
        ), patch.object(self.module, "slack_post", side_effect=AssertionError("should not post in dry-run")):
            state_path = Path(tmp) / "support-watch-state.json"
            result = self.module.run_monitor(args_for(str(state_path), dry_run=True))

        self.assertEqual(result["action"], "would_post")
        self.assertEqual(result["output_channel_id"], "CBUGS")
        self.assertEqual(result["output_channel_id_source"], "resolved")
        self.assertFalse(state_path.exists())


if __name__ == "__main__":
    unittest.main()
