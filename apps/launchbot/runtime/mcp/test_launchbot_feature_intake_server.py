from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


SOURCE_PERMALINK = (
    "https://staffany.slack.com/archives/CF8PK6V4J/p1778752831230299"
    "?thread_ts=1778752459.023229&cid=CF8PK6V4J"
)


class LaunchbotFeatureIntakeServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("launchbot_feature_intake_server.py")

    def test_exposes_guarded_feature_intake_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["create_feature_intake_from_slack_thread", "preview_feature_intake_from_slack_thread"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "transition", "delete", "comment"]:
            self.assertNotIn(forbidden, tool_names)

    def test_unconfigured_channel_blocks_before_network(self):
        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS": "C123",
            },
            clear=True,
        ), patch.object(self.module.core, "slack_api", side_effect=AssertionError("should not call Slack")):
            result = self.module.preview_feature_intake_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("configured channel IDs", result["answer"])

    def test_preview_builds_ker_intake_without_mutation(self):
        jira_calls = []

        def fake_slack_api(method, params):
            self.assertEqual(method, "conversations.replies")
            self.assertEqual(params["channel"], "CF8PK6V4J")
            return {
                "ok": True,
                "messages": [
                    {"ts": "1778752459.023229", "user": "U1", "text": "do u want me to upgrade launch bot to intake this"},
                    {"ts": "1778752500.000000", "user": "U1", "text": "cause in my view that should be the new centralized product bot"},
                    {
                        "ts": "1778752831.230299",
                        "user": "U2",
                        "text": "Yeah, inputting new feature request should be automated lol i'm basically recreating this from notes",
                    },
                ],
            }

        def fake_jira_post(path, body):
            jira_calls.append((path, body))
            return {"issues": []}

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS": "CF8PK6V4J",
            },
            clear=True,
        ), patch.object(self.module.core, "slack_api", side_effect=fake_slack_api), patch.object(
            self.module.core, "jira_post", side_effect=fake_jira_post
        ):
            result = self.module.preview_feature_intake_from_slack_thread(slack_permalink=SOURCE_PERMALINK)

        self.assertEqual(result["confidence"], "verified")
        answer = result["answer"]
        self.assertEqual(answer["summary"], "Automate Slack feature request intake into Jira Product Discovery")
        self.assertEqual(answer["proposed_fields"]["project"]["key"], "KER")
        self.assertEqual(answer["proposed_fields"]["issuetype"]["id"], "10043")
        self.assertEqual(answer["proposed_fields"]["customfield_10080"], SOURCE_PERMALINK)
        self.assertEqual(answer["proposed_fields"]["customfield_10081"], [{"id": "11370"}])
        self.assertEqual(answer["proposed_fields"]["customfield_10087"], [{"id": "10091"}])
        self.assertFalse(answer["will_mutate_jira"])
        self.assertFalse(answer["will_post_message"])
        self.assertFalse(answer["transcript_persisted"])
        self.assertIn("Launchbot automation: Previewed KER intake.", answer["slack_reply"])
        self.assertTrue(any("1778752831230299" in body["jql"] for _, body in jira_calls))

    def test_create_requires_explicit_confirmation(self):
        with patch.dict(
            os.environ,
            {"LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS": "CF8PK6V4J"},
            clear=True,
        ), patch.object(self.module.core, "slack_api", side_effect=AssertionError("should not call Slack")):
            result = self.module.create_feature_intake_from_slack_thread(
                slack_permalink=SOURCE_PERMALINK,
                confirmation="yes",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Confirmation must be exactly", result["answer"])

    def test_create_reuses_existing_duplicate_without_posting_issue(self):
        def fake_slack_api(method, params):
            return {
                "ok": True,
                "messages": [
                    {"ts": "1778752459.023229", "user": "U1", "text": "launch bot intake for feature request"},
                    {"ts": "1778752831.230299", "user": "U2", "text": "feature request should be automated"},
                ],
            }

        def fake_jira_post(path, body):
            self.assertEqual(path, "/rest/api/3/search/jql")
            return {
                "issues": [
                    {
                        "key": "KER-2132",
                        "fields": {
                            "summary": "Automate Slack feature request intake into Jira Product Discovery",
                            "status": {"name": "Backlog"},
                            "customfield_10080": SOURCE_PERMALINK,
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
                "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS": "CF8PK6V4J",
            },
            clear=True,
        ), patch.object(self.module.core, "slack_api", side_effect=fake_slack_api), patch.object(
            self.module.core, "jira_post", side_effect=fake_jira_post
        ), patch.object(self.module.core, "jira_get", side_effect=AssertionError("should not fetch myself")):
            result = self.module.create_feature_intake_from_slack_thread(
                slack_permalink=SOURCE_PERMALINK,
                confirmation="create intake",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertFalse(result["answer"]["created"])
        self.assertEqual(result["answer"]["issue"]["issue_key"], "KER-2132")
        self.assertFalse(result["answer"]["will_mutate_jira"])

    def test_create_posts_minimal_ker_payload_after_confirmation(self):
        posted_bodies = []

        def fake_slack_api(method, params):
            return {
                "ok": True,
                "messages": [
                    {"ts": "1778752459.023229", "user": "U1", "text": "Please intake this feature request for bulk shift edits"},
                    {"ts": "1778752831.230299", "user": "U2", "text": "Managers need to edit multiple shifts from notes"},
                ],
            }

        def fake_jira_get(path):
            self.assertEqual(path, "/rest/api/3/myself")
            return {"accountId": "abc-123"}

        def fake_jira_post(path, body):
            if path == "/rest/api/3/search/jql":
                return {"issues": []}
            self.assertEqual(path, "/rest/api/3/issue?notifyUsers=false")
            posted_bodies.append(body)
            return {"key": "KER-3000"}

        with patch.dict(
            os.environ,
            {
                "SLACK_BOT_TOKEN": "test-bot-token",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS": "CF8PK6V4J",
            },
            clear=True,
        ), patch.object(self.module.core, "slack_api", side_effect=fake_slack_api), patch.object(
            self.module.core, "jira_get", side_effect=fake_jira_get
        ), patch.object(self.module.core, "jira_post", side_effect=fake_jira_post):
            result = self.module.create_feature_intake_from_slack_thread(
                slack_permalink=SOURCE_PERMALINK,
                confirmation="create intake",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["created"])
        self.assertEqual(result["answer"]["issue"]["issue_key"], "KER-3000")
        fields = posted_bodies[0]["fields"]
        self.assertEqual(fields["project"]["key"], "KER")
        self.assertEqual(fields["issuetype"]["id"], "10043")
        self.assertEqual(fields["reporter"]["id"], "abc-123")
        self.assertEqual(fields["customfield_10080"], SOURCE_PERMALINK)
        self.assertNotIn("customfield_10081", fields)
        self.assertNotIn("customfield_10087", fields)
        self.assertIn("description", fields)
        self.assertTrue(result["answer"]["will_mutate_jira"])
        self.assertFalse(result["answer"]["will_post_message"])


if __name__ == "__main__":
    unittest.main()
