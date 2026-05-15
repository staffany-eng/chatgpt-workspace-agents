from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from test_helpers import load_mcp_module


SOURCE_PERMALINK = "https://staffany.slack.com/archives/C01RZ7SHC8K/p1778816627326029"


class LaunchbotProductCommitmentServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_product_commitment_server.py")

    def test_exposes_read_only_commitment_tool_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["check_product_commitment_from_slack_thread"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "create", "update", "delete", "transition", "comment"]:
            self.assertNotIn(forbidden, tool_names)

    def test_unconfigured_channel_blocks_before_network(self):
        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS": "C123",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=AssertionError("should not call Slack")):
            result = self.module.check_product_commitment_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("restricted to configured channel IDs", result["answer"])

    def test_commitment_absent_returns_needs_check_without_mutation(self):
        jira_calls = []

        def fake_slack_api(method, params):
            self.assertEqual(method, "conversations.replies")
            self.assertEqual(params["channel"], "C01RZ7SHC8K")
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": "1778816627.326029",
                        "user": "U1",
                        "text": "is there any plan to build payslip to email function? If so, how long might it take?",
                    },
                    {"ts": "1778817991.306329", "user": "U2", "text": "not committed on roadmap yet iirc <@U0ASVD79UT1> can u check"},
                    {
                        "ts": "1778820070.044149",
                        "user": "U0ASVD79UT1",
                        "bot_id": "B0ATPPEGBCH",
                        "text": "KER found: Status: Backlog. Assignee: unassigned. No fix version.",
                    },
                ],
            }

        def fake_jira_post(path, body):
            jira_calls.append(body["jql"])
            if "payslip" in body["jql"]:
                return {
                    "issues": [
                        {
                            "key": "KER-3001",
                            "_matched_phrases": ["payslip"],
                            "fields": {
                                "summary": "Email payslip to employees",
                                "status": {"name": "Discovery"},
                                "updated": "2026-05-15T12:00:00.000+0800",
                                "assignee": {"displayName": "Product"},
                                "issuetype": {"name": "Idea"},
                                "fixVersions": [],
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
                "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS": "C01RZ7SHC8K",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api), patch.object(
            self.module, "_jira_post", side_effect=fake_jira_post
        ):
            result = self.module.check_product_commitment_from_slack_thread(
                channel_id="C01RZ7SHC8K",
                thread_ts="1778816627.326029",
            )

        answer = result["answer"]
        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(answer["topic"], "payslip-to-email")
        self.assertIn("No committed Jira roadmap evidence found for payslip-to-email yet", answer["slack_reply"])
        self.assertEqual(answer["safe_thread_summaries"], [
            {
                "ts": "1778816627.326029",
                "user_id": "U1",
                "summary": "is there any plan to build payslip to email function? If so, how long might it take?",
            },
            {
                "ts": "1778817991.306329",
                "user_id": "U2",
                "summary": "not committed on roadmap yet iirc <@user> can u check",
            },
        ])
        self.assertNotIn("Backlog", repr(answer["safe_thread_summaries"]))
        self.assertNotIn("status", answer["top_candidate"])
        self.assertNotIn("assignee", answer["top_candidate"])
        self.assertNotIn("updated", answer["top_candidate"])
        self.assertTrue(answer["top_candidate"]["non_commitment_fields_redacted"])
        self.assertTrue(any("payslip" in jql for jql in jira_calls))
        self.assertFalse(answer["will_mutate_jira"])
        self.assertFalse(answer["will_post_message"])
        self.assertFalse(answer["transcript_persisted"])
        self.assertFalse(answer["will_create_intake"])
        self.assertFalse(answer["will_estimate_timeline"])

    def test_fix_version_counts_as_explicit_commitment(self):
        def fake_slack_api(method, params):
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": "1778816627.326029",
                        "user": "U1",
                        "text": "check product commitment for payslip to email",
                    }
                ],
            }

        def fake_jira_post(path, body):
            return {
                "issues": [
                    {
                        "key": "KER-3002",
                        "fields": {
                            "summary": "Payslip to email",
                            "status": {"name": "Committed"},
                            "updated": "2026-05-15T12:00:00.000+0800",
                            "assignee": {"displayName": "Product"},
                            "issuetype": {"name": "Idea"},
                            "fixVersions": [{"name": "Payroll 2605", "releaseDate": "2026-05-31"}],
                        },
                    }
                ]
            }

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS": "C01RZ7SHC8K",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api), patch.object(
            self.module, "_jira_post", side_effect=fake_jira_post
        ):
            result = self.module.check_product_commitment_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        answer = result["answer"]
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(answer["top_candidate"]["issue_key"], "KER-3002")
        self.assertEqual(answer["top_candidate"]["status"], "Committed")
        self.assertNotIn("assignee", answer["top_candidate"])
        self.assertNotIn("updated", answer["top_candidate"])
        self.assertEqual(answer["top_candidate"]["commitment_evidence"][0]["field"], "fixVersions")
        self.assertIn("Commitment evidence found", answer["slack_reply"])

    def test_configured_commitment_field_counts_when_present(self):
        def fake_slack_api(method, params):
            return {
                "ok": True,
                "messages": [
                    {
                        "ts": "1778816627.326029",
                        "user": "U1",
                        "text": "check product commitment for payslip to email",
                    }
                ],
            }

        def fake_jira_post(path, body):
            self.assertIn("customfield_10999", body["fields"])
            return {
                "issues": [
                    {
                        "key": "KER-3003",
                        "fields": {
                            "summary": "Payslip to email",
                            "status": {"name": "Committed"},
                            "updated": "2026-05-15T12:00:00.000+0800",
                            "assignee": {"displayName": "Product"},
                            "issuetype": {"name": "Idea"},
                            "fixVersions": [],
                            "customfield_10999": {"value": "2605H2"},
                        },
                    }
                ]
            }

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS": "C01RZ7SHC8K",
                "LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS": "customfield_10999",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api), patch.object(
            self.module, "_jira_post", side_effect=fake_jira_post
        ):
            result = self.module.check_product_commitment_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "verified")
        evidence = result["answer"]["top_candidate"]["commitment_evidence"]
        self.assertEqual(evidence[0]["field"], "customfield_10999")
        self.assertEqual(evidence[0]["value"], "2605H2")

    def test_no_matching_issue_is_needs_check(self):
        def fake_slack_api(method, params):
            return {
                "ok": True,
                "messages": [
                    {"ts": "1778816627.326029", "user": "U1", "text": "check product commitment for payslip to email"}
                ],
            }

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS": "C01RZ7SHC8K",
            },
            clear=True,
        ), patch.object(self.module, "_slack_api", side_effect=fake_slack_api), patch.object(
            self.module, "_jira_post", return_value={"issues": []}
        ):
            result = self.module.check_product_commitment_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "needs-check")
        self.assertIn("No matching KER/JPD issue found", result["answer"]["slack_reply"])


if __name__ == "__main__":
    unittest.main()
