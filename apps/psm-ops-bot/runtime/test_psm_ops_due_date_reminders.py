from __future__ import annotations

import importlib.util
import os
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
        self.assertIn("Overdue:", output)
        self.assertIn("Due Today:", output)
        self.assertIn("Due Tomorrow:", output)
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-159|PCO-159>", output)
        self.assertNotIn("description", output.lower())
        self.assertNotIn("comment", output.lower())
        self.assertNotIn("transcript", output.lower())

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
                "description": "must not leak",
                "comment": {"comments": ["must not leak"]},
            },
        }

        issue = self.module.safe_issue(raw)

        self.assertEqual(issue["key"], "PCO-159")
        self.assertEqual(issue["ps_team"], "CS Duty")
        self.assertNotIn("description", issue)
        self.assertNotIn("comment", issue)


if __name__ == "__main__":
    unittest.main()
