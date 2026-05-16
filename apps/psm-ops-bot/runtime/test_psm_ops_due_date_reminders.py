from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


SCRIPT_PATH = Path(__file__).parent / "scripts" / "psm_ops_due_date_reminders.py"


def load_script():
    spec = importlib.util.spec_from_file_location("psm_ops_due_date_reminders", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PsmOpsDueDateReminderScriptTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.as_of = datetime(2026, 5, 15, 9, 0, tzinfo=ZoneInfo("Asia/Singapore"))
        self.env = patch.dict(
            os.environ,
            {
                "JIRA_BASE_URL": "https://staffany.atlassian.net",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "fake-token",
                "PSM_OPS_JIRA_PROJECT_KEY": "PCO",
                "PSM_OPS_JIRA_FIELD_PS_TEAM": "customfield_10876",
                "PSM_OPS_JIRA_FIELD_SOURCE_LINKS": "",
                "PSM_OPS_REMINDER_MENTION_MAP_PATH": "",
                "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_morning_jql_includes_tomorrow_and_excludes_done(self):
        jql = self.module.build_jql("morning", self.as_of)

        self.assertIn("project = PCO", jql)
        self.assertIn("statusCategory != Done", jql)
        self.assertIn("duedate is not EMPTY", jql)
        self.assertIn('duedate <= "2026-05-16"', jql)

    def test_eod_jql_includes_today_and_overdue_only(self):
        jql = self.module.build_jql("eod", self.as_of)

        self.assertIn("statusCategory != Done", jql)
        self.assertIn('duedate <= "2026-05-15"', jql)
        self.assertNotIn('duedate <= "2026-05-16"', jql)

    def test_format_digest_groups_by_ps_team_and_due_bucket(self):
        issues = [
            {
                "key": "PCO-146",
                "url": "https://staffany.atlassian.net/browse/PCO-146",
                "summary": "Follow up with product",
                "status": "Open",
                "priority": "P3",
                "due_date": "2025-07-15",
                "ps_team": "Kai Yi",
            },
            {
                "key": "PCO-159",
                "url": "https://staffany.atlassian.net/browse/PCO-159",
                "summary": "Tomoro Coffee HRAny duplicate phone",
                "status": "Open",
                "priority": "P3",
                "due_date": "2026-05-15",
                "ps_team": "CS Duty",
            },
            {
                "key": "PCO-160",
                "url": "https://staffany.atlassian.net/browse/PCO-160",
                "summary": "Tomorrow follow-up",
                "status": "Waiting Internal",
                "priority": "P2",
                "due_date": "2026-05-16",
                "ps_team": "CS Duty",
            },
        ]

        output = self.module.format_digest(issues, "morning", self.as_of)

        self.assertTrue(output.startswith("PSM Ops automation:"))
        self.assertIn("PS Team: CS Duty", output)
        self.assertIn("PS Team: Kai Yi", output)
        self.assertIn("*Overdue*", output)
        self.assertIn("*Due Today*", output)
        self.assertIn("*Due Tomorrow*", output)
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-159|PCO-159>", output)
        self.assertNotIn("description", output.lower())
        self.assertNotIn("comment", output.lower())
        self.assertNotIn("transcript", output.lower())

    def test_format_digest_renders_static_ps_team_mentions_and_gaps(self):
        issues = [
            {
                "key": "PCO-159",
                "url": "https://staffany.atlassian.net/browse/PCO-159",
                "summary": "Tomoro Coffee HRAny duplicate phone",
                "status": "Open",
                "priority": "P3",
                "due_date": "2026-05-15",
                "ps_team": "CS Duty",
                "source_links": [],
            },
            {
                "key": "PCO-152",
                "url": "https://staffany.atlassian.net/browse/PCO-152",
                "summary": "Product feedback follow-up",
                "status": "Waiting Internal",
                "priority": "P3",
                "due_date": "2026-05-15",
                "ps_team": "Kai Yi",
                "source_links": [],
            },
            {
                "key": "PCO-170",
                "url": "https://staffany.atlassian.net/browse/PCO-170",
                "summary": "Unmapped team follow-up",
                "status": "Open",
                "priority": "P3",
                "due_date": "2026-05-15",
                "ps_team": "Alya",
                "source_links": [],
            },
        ]
        context = {
            "mentions": {
                "CS Duty": ["<!subteam^S123ABC|cs-duty>"],
                "Kai Yi": ["<@U123ABC>"],
            },
            "customer_channels": {},
            "mention_warning": "",
        }

        output = self.module.format_digest(issues, "eod", self.as_of, context=context)

        self.assertIn("*PS Team: CS Duty* <!subteam^S123ABC|cs-duty>", output)
        self.assertIn("*PS Team: Kai Yi* <@U123ABC>", output)
        self.assertIn("Mention gaps: Alya", output)
        self.assertNotIn("users.list", output)

    def test_customer_channel_renders_only_from_reviewed_source_link_mapping(self):
        issues = [
            {
                "key": "PCO-200",
                "url": "https://staffany.atlassian.net/browse/PCO-200",
                "summary": "Rock Productions follow-up",
                "status": "Open",
                "priority": "P2",
                "due_date": "2026-05-15",
                "ps_team": "Kai Yi",
                "source_links": [
                    "https://staffany.slack.com/archives/C0790P1DQ04/p1778816591550659"
                ],
            },
        ]
        context = {
            "mentions": {"Kai Yi": ["<@U123ABC>"]},
            "customer_channels": {
                "C0790P1DQ04": {
                    "channel_id": "C0790P1DQ04",
                    "channel_name": "proj-cs-rockproductions",
                }
            },
            "mention_warning": "",
        }

        output = self.module.format_digest(issues, "eod", self.as_of, context=context)

        self.assertIn("Source: <https://staffany.slack.com/archives/C0790P1DQ04/p1778816591550659|source thread>", output)
        self.assertIn("Customer team: <#C0790P1DQ04|proj-cs-rockproductions>", output)

    def test_missing_mention_map_is_non_fatal(self):
        mentions, warning = self.module.load_mention_map()

        self.assertEqual(mentions, {})
        self.assertEqual(warning, "")

    def test_invalid_mention_map_disables_mentions_but_keeps_digest(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("{not json")
            map_path = handle.name
        self.addCleanup(lambda: Path(map_path).unlink(missing_ok=True))
        issue = {
            "key": "PCO-159",
            "url": "https://staffany.atlassian.net/browse/PCO-159",
            "summary": "Tomoro Coffee follow-up",
            "status": "Open",
            "priority": "P3",
            "due_date": "2026-05-15",
            "ps_team": "CS Duty",
            "source_links": [],
        }

        with patch.dict(os.environ, {"PSM_OPS_REMINDER_MENTION_MAP_PATH": map_path}, clear=False):
            output = self.module.format_digest([issue], "eod", self.as_of)

        self.assertIn("PCO-159", output)
        self.assertIn("Mention gaps: CS Duty", output)
        self.assertIn("Mention map warning:", output)
        self.assertNotIn("<@", output)
        self.assertNotIn("<!subteam", output)

    def test_malformed_customer_map_does_not_guess_customer_channel(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("{not json")
            map_path = handle.name
        self.addCleanup(lambda: Path(map_path).unlink(missing_ok=True))
        issue = {
            "key": "PCO-200",
            "url": "https://staffany.atlassian.net/browse/PCO-200",
            "summary": "Rock Productions follow-up",
            "status": "Open",
            "priority": "P2",
            "due_date": "2026-05-15",
            "ps_team": "Kai Yi",
            "source_links": [
                "https://staffany.slack.com/archives/C0790P1DQ04/p1778816591550659"
            ],
        }

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            output = self.module.format_digest([issue], "eod", self.as_of)

        self.assertIn("Rock Productions follow-up", output)
        self.assertNotIn("Customer team:", output)
        self.assertNotIn("<#C0790P1DQ04", output)

    def test_loads_reviewed_customer_channel_map_only(self):
        payload = {
            "channels": [
                {
                    "channel_id": "C0790P1DQ04",
                    "channel_name": "proj-cs-rockproductions",
                    "customer_key": "8051493928",
                    "customer_name": "Rock Productions Pte Ltd",
                    "staffany_orgs": ["Rock Productions"],
                    "status": "reviewed",
                },
                {
                    "channel_id": "CUNREVIEWED",
                    "channel_name": "proj-cs-unreviewed",
                    "status": "draft",
                },
            ]
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            map_path = handle.name
        self.addCleanup(lambda: Path(map_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            channels = self.module.load_customer_channel_map()

        self.assertEqual(channels["C0790P1DQ04"]["channel_name"], "proj-cs-rockproductions")
        self.assertNotIn("CUNREVIEWED", channels)

    def test_empty_digest_is_silent(self):
        output = self.module.format_digest([], "eod", self.as_of)

        self.assertTrue(output.startswith("[SILENT] PSM Ops automation:"))
        self.assertIn("no PCO due-date reminders", output)

    def test_safe_issue_uses_safe_fields_only(self):
        raw = {
            "key": "PCO-159",
            "fields": {
                "summary": "Tomoro Coffee HRAny duplicate phone",
                "status": {"name": "Open"},
                "priority": {"name": "P3"},
                "duedate": "2026-05-15",
                "customfield_10876": {"value": "CS Duty"},
                "customfield_12345": "Source: https://staffany.slack.com/archives/C0790P1DQ04/p1778816591550659",
                "description": "must not leak",
                "comment": {"comments": ["must not leak"]},
            },
        }

        with patch.dict(os.environ, {"PSM_OPS_JIRA_FIELD_SOURCE_LINKS": "customfield_12345"}, clear=False):
            issue = self.module.safe_issue(raw)

        self.assertEqual(issue["key"], "PCO-159")
        self.assertEqual(issue["ps_team"], "CS Duty")
        self.assertEqual(
            issue["source_links"],
            ["https://staffany.slack.com/archives/C0790P1DQ04/p1778816591550659"],
        )
        self.assertNotIn("description", issue)
        self.assertNotIn("comment", issue)


if __name__ == "__main__":
    unittest.main()
