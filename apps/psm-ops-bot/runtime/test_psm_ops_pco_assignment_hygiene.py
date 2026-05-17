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


SCRIPT_PATH = Path(__file__).parent / "scripts" / "psm_ops_pco_assignment_hygiene.py"


def load_script():
    spec = importlib.util.spec_from_file_location("psm_ops_pco_assignment_hygiene", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PsmOpsPcoAssignmentHygieneScriptTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.as_of = datetime(2026, 5, 15, 9, 15, tzinfo=ZoneInfo("Asia/Singapore"))
        self.env = patch.dict(
            os.environ,
            {
                "JIRA_BASE_URL": "https://staffany.atlassian.net",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "fake-token",
                "PSM_OPS_JIRA_PROJECT_KEY": "PCO",
                "PSM_OPS_JIRA_FIELD_PS_TEAM": "customfield_10876",
                "PSM_OPS_REMINDER_MENTION_MAP_PATH": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_hygiene_jql_finds_missing_assignee_ps_team_or_due_date(self):
        jql = self.module.build_jql()

        self.assertIn("project = PCO", jql)
        self.assertIn("statusCategory != Done", jql)
        self.assertIn("assignee is EMPTY", jql)
        self.assertIn("cf[10876] is EMPTY", jql)
        self.assertIn("duedate is EMPTY", jql)

    def test_fetch_hygiene_issues_uses_safe_fields(self):
        calls = []

        def fake_request(path):
            calls.append(path)
            return {"issues": []}

        self.module._request_json = fake_request

        issues = self.module.fetch_hygiene_issues(max_results=500)

        self.assertEqual(issues, [])
        self.assertIn("maxResults=100", calls[0])
        self.assertIn("fields=summary%2Cstatus%2Cpriority%2Cassignee%2Cupdated%2Cduedate%2Cissuetype%2Ccustomfield_10876", calls[0])

    def test_safe_issue_uses_safe_fields_only(self):
        raw = {
            "key": "PCO-201",
            "fields": {
                "summary": "Needs owner cleanup",
                "status": {"name": "Open"},
                "priority": {"name": "P2"},
                "assignee": None,
                "duedate": None,
                "updated": "2026-05-15T01:00:00.000+0000",
                "customfield_10876": {"value": "CS Duty"},
                "description": "must not leak",
                "comment": {"comments": ["must not leak"]},
                "attachment": [{"filename": "must-not-leak.pdf"}],
            },
        }

        issue = self.module.safe_issue(raw)

        self.assertEqual(issue["key"], "PCO-201")
        self.assertEqual(issue["assignee"], "Unassigned")
        self.assertEqual(issue["due_date"], "Not set")
        self.assertEqual(issue["ps_team"], "CS Duty")
        self.assertNotIn("description", issue)
        self.assertNotIn("comment", issue)
        self.assertNotIn("attachment", issue)

    def test_format_digest_groups_lead_triage_and_due_dates(self):
        issues = [
            {
                "key": "PCO-201",
                "url": "https://staffany.atlassian.net/browse/PCO-201",
                "summary": "Missing assignee and due date",
                "status": "Open",
                "priority": "P2",
                "assignee": "Unassigned",
                "due_date": "Not set",
                "ps_team": "CS Duty",
                "updated": "2026-05-15T01:00:00.000+0000",
            },
            {
                "key": "PCO-202",
                "url": "https://staffany.atlassian.net/browse/PCO-202",
                "summary": "Missing PS Team",
                "status": "Waiting Internal",
                "priority": "P3",
                "assignee": "Alya",
                "due_date": "2026-05-16",
                "ps_team": "Not set",
                "updated": "2026-05-15T01:00:00.000+0000",
            },
            {
                "key": "PCO-203",
                "url": "https://staffany.atlassian.net/browse/PCO-203",
                "summary": "Missing due date only",
                "status": "Open",
                "priority": "P3",
                "assignee": "Beng Hui",
                "due_date": "Not set",
                "ps_team": "Kai Yi",
                "updated": "2026-05-15T01:00:00.000+0000",
            },
        ]
        context = {
            "ps_leads": {"Josica": ["<@UJO123>"]},
            "ps_teams": {"CS Duty": ["<!subteam^SCS123|cs-duty>"], "Kai Yi": ["<@UKY123>"]},
            "mention_warning": "",
        }

        output = self.module.format_digest(issues, self.as_of, context=context)

        self.assertTrue(output.startswith("PSM Ops automation: PCO assignment hygiene"))
        self.assertIn("*Needs PS lead triage: Josica* <@UJO123>", output)
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-201|PCO-201>", output)
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-202|PCO-202>", output)
        self.assertIn("*Needs due date by PS Team*", output)
        self.assertIn("*PS Team: CS Duty* <!subteam^SCS123|cs-duty>", output)
        self.assertIn("*PS Team: Kai Yi* <@UKY123>", output)
        self.assertNotIn("description", output.lower())
        self.assertNotIn("comment", output.lower())
        self.assertNotIn("transcript", output.lower())
        self.assertNotIn("attachment", output.lower())

    def test_format_digest_renders_mention_gaps_without_guessing(self):
        issues = [
            {
                "key": "PCO-204",
                "url": "https://staffany.atlassian.net/browse/PCO-204",
                "summary": "Missing everything",
                "status": "Open",
                "priority": "P2",
                "assignee": "Unassigned",
                "due_date": "Not set",
                "ps_team": "CS Duty",
                "updated": "2026-05-15T01:00:00.000+0000",
            }
        ]

        output = self.module.format_digest(issues, self.as_of, context={"ps_leads": {}, "ps_teams": {}, "mention_warning": ""})

        self.assertIn("Lead mention gap: Josica", output)
        self.assertIn("Mention gaps: CS Duty", output)
        self.assertNotIn("<@", output)
        self.assertNotIn("<!subteam", output)
        self.assertNotIn("users.list", output)

    def test_load_mention_map_reads_ps_leads_and_ps_teams(self):
        payload = {
            "ps_leads": {
                "Josica": [{"type": "user", "id": "UJO123", "label": "Josica"}],
            },
            "ps_teams": {
                "CS Duty": [{"type": "usergroup", "id": "SCS123", "handle": "cs-duty"}],
            },
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            map_path = handle.name
        self.addCleanup(lambda: Path(map_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {"PSM_OPS_REMINDER_MENTION_MAP_PATH": map_path}, clear=False):
            ps_teams, ps_leads, warning = self.module.load_mention_map()

        self.assertEqual(warning, "")
        self.assertEqual(ps_leads["Josica"], ["<@UJO123>"])
        self.assertEqual(ps_teams["CS Duty"], ["<!subteam^SCS123|cs-duty>"])

    def test_invalid_mention_map_is_non_fatal(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("{not json")
            map_path = handle.name
        self.addCleanup(lambda: Path(map_path).unlink(missing_ok=True))

        with patch.dict(os.environ, {"PSM_OPS_REMINDER_MENTION_MAP_PATH": map_path}, clear=False):
            ps_teams, ps_leads, warning = self.module.load_mention_map()

        self.assertEqual(ps_teams, {})
        self.assertEqual(ps_leads, {})
        self.assertIn("could not be read", warning)

    def test_empty_digest_is_silent(self):
        output = self.module.format_digest([], self.as_of)

        self.assertTrue(output.startswith("[SILENT] PSM Ops automation:"))
        self.assertIn("no PCO assignment hygiene gaps", output)


if __name__ == "__main__":
    unittest.main()
