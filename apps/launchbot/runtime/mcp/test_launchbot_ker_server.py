from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class LaunchbotKerServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_ker_server.py")

    def test_profile_env_loads_launchbot_dotenv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".hermes" / "profiles" / "launchbot" / ".env"
            env_path.parent.mkdir(parents=True)
            env_path.write_text(
                "\n".join(
                    [
                        "SLACK_BOT_TOKEN=test-bot-token",
                        "JIRA_BASE_URL=https://staffany.atlassian.net",
                        "JIRA_EMAIL=bot@staffany.com",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"HOME": tmpdir}, clear=True):
                module = load_mcp_module("launchbot_ker_server.py", "launchbot_ker_profile_env_test")
                self.assertEqual(os.environ["JIRA_EMAIL"], "bot@staffany.com")
                self.assertEqual(module._configured_channel_ids(), module.DEFAULT_ALLOWED_CHANNELS)

    def test_exposes_read_only_ker_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["find_ker_ticket_from_slack_thread", "lookup_ker_ticket_by_key"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "create", "update", "delete"]:
            self.assertNotIn(forbidden, tool_names)

    def test_unconfigured_channel_blocks_before_network(self):
        with patch.dict(
            os.environ,
            {"SLACK_BOT_TOKEN": "test-bot-token", "LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS": "C123"},
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=AssertionError("should not call Slack")):
            result = self.module.find_ker_ticket_from_slack_thread("C999", "1770000000.000000")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured channel IDs", result["answer"])

    def test_finds_data_blocking_ticket_from_thread_context(self):
        jira_calls = []

        def fake_slack_api(method, params):
            self.assertEqual(method, "conversations.replies")
            self.assertEqual(params["channel"], "C0AJAUNCEL8")
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": "1778123999.615759",
                        "user": "U1",
                        "text": "Labor cost visibility removal - hide salary information from managers",
                    },
                    {
                        "ts": "1778740733.924739",
                        "user": "U2",
                        "text": "data block for salary data. <@U0ASVD79UT1> can find the ticket for this on KER board?",
                    },
                    {
                        "ts": "1778740837.962069",
                        "user": "U3",
                        "text": "I got you <https://staffany.atlassian.net/browse/KER-2109>",
                    },
                ],
            }

        def fake_jira_post(path, body):
            jira_calls.append(body["jql"])
            if "data block" in body["jql"]:
                return {
                    "issues": [
                        {
                            "key": "KER-2109",
                            "_matched_phrases": ["data block"],
                            "fields": {
                                "summary": "Data-blocking PG",
                                "status": {"name": "2 - Scoping / Designing"},
                                "updated": "2026-05-10T18:52:00.531+0800",
                                "assignee": {"displayName": "Product"},
                                "issuetype": {"name": "Story"},
                            },
                        }
                    ]
                }
            return {"issues": []}

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS": "C0AJAUNCEL8",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api), patch.object(
            self.module, "_jira_post", side_effect=fake_jira_post
        ):
            result = self.module.find_ker_ticket_from_slack_thread(
                "C0AJAUNCEL8",
                "1778123999.615759",
                message_ts="1778740733.924739",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(any("data block" in jql for jql in jira_calls))
        self.assertEqual(result["answer"]["top_candidate"]["issue_key"], "KER-2109")
        self.assertIn("<https://staffany.atlassian.net/browse/KER-2109|KER-2109>", result["answer"]["slack_reply"])
        self.assertFalse(result["answer"]["will_mutate_jira"])
        self.assertFalse(result["answer"]["will_post_message"])
        self.assertFalse(result["answer"]["transcript_persisted"])

    def test_lookup_by_key_returns_safe_fields(self):
        def fake_jira_get(path):
            self.assertIn("/rest/api/3/issue/KER-2109", path)
            return {
                "key": "KER-2109",
                "fields": {
                    "summary": "Data-blocking PG",
                    "status": {"name": "2 - Scoping / Designing"},
                    "updated": "2026-05-10T18:52:00.531+0800",
                    "assignee": {"displayName": "Product"},
                    "issuetype": {"name": "Story"},
                },
            }

        with patch.dict(
            os.environ,
            {"JIRA_EMAIL": "bot@staffany.com", "JIRA_API_TOKEN": "jira-token"},
            clear=True,
        ), patch.object(self.module, "_jira_get", side_effect=fake_jira_get):
            result = self.module.lookup_ker_ticket_by_key("ker-2109")

        self.assertEqual(result["confidence"], "verified")
        candidate = result["answer"]["candidate"]
        self.assertEqual(candidate["issue_key"], "KER-2109")
        self.assertNotIn("description", candidate)


if __name__ == "__main__":
    unittest.main()
