import unittest
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


if __name__ == "__main__":
    unittest.main()
