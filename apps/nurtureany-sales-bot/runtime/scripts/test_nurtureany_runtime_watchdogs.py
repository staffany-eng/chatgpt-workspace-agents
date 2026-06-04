import unittest
import importlib.util
from datetime import datetime, timezone
from pathlib import Path


class RuntimeWatchdogScriptTest(unittest.TestCase):
    def test_slack_socket_watchdog_logs_unauthorized_mentions_without_restart_branch(self):
        script = Path(__file__).parents[1] / "check-slack-socket-health.sh"
        text = script.read_text(encoding="utf-8")

        self.assertIn('"Unauthorized user:"', text)
        self.assertIn("slack-ingress:unauthorized-user", text)
        unauthorized_branch_start = text.index('grep -Fq "slack-ingress:unauthorized-user"')
        stale_branch_start = text.index("stale_ts=", unauthorized_branch_start)
        unauthorized_branch = text[unauthorized_branch_start:stale_branch_start]

        self.assertIn('append_watchdog_log "$ingress_out"', unauthorized_branch)
        self.assertNotIn("restart_gateway", unauthorized_branch)

    def test_inbound_monitor_is_internal_read_only_report(self):
        script_path = Path(__file__).with_name("nurtureany_inbound_monitor.py")
        spec = importlib.util.spec_from_file_location("nurtureany_inbound_monitor", script_path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)

        with self.assertRaises(module.MonitorError):
            module._assert_read_only_result({"answer": {"will_mutate_hubspot": True}})
        with self.assertRaises(module.MonitorError):
            module._assert_read_only_result({"answer": {"external_message_sending": True}})

        result = {
            "confidence": "high",
            "answer": {
                "audit_rows": [
                    {
                        "alert_time": "2026-05-17T12:00:00Z",
                        "assigned_owner": "",
                        "first_touch_source": "missing",
                    }
                ]
            },
        }
        actions = module.action_rows_from_result(result, datetime(2026, 5, 17, 12, 12, tzinfo=timezone.utc))
        report = module.format_report(result, actions, {"notified_keys": []}, dry_run=True)

        self.assertIn("NurtureAny automation: HubSpot inbound monitor DRY RUN", report)
        self.assertIn("Source: HubSpot Conversations and CRM activity", report)
        self.assertIn("Internal exception report only", report)


if __name__ == "__main__":
    unittest.main()
