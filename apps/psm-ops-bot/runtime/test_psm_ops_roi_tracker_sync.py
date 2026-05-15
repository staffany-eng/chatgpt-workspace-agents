from __future__ import annotations

import importlib.util
import os
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


SCRIPT_PATH = Path(__file__).parent / "scripts" / "psm_ops_roi_tracker_sync.py"


def load_script():
    spec = importlib.util.spec_from_file_location("psm_ops_roi_tracker_sync", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PsmOpsRoiTrackerSyncScriptTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.as_of = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Singapore"))
        self.env = patch.dict(
            os.environ,
            {
                "JIRA_BASE_URL": "https://staffany.atlassian.net",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "fake-token",
                "PSM_OPS_JIRA_PROJECT_KEY": "PCO",
                "PSM_OPS_ROI_JIRA_PROJECT_KEY": "ROI",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_build_jql_scopes_waiting_internal_trackers(self):
        jql = self.module.build_jql()

        self.assertIn("project = PCO", jql)
        self.assertIn('labels = "ps-wee-roi-tracker"', jql)
        self.assertIn('status = "Waiting Internal"', jql)

    def test_sync_is_silent_when_linked_roi_not_done(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            self.assertEqual(method, "GET")
            return {"fields": {"summary": "Invoice check", "status": {"name": "In Progress", "statusCategory": {"key": "indeterminate"}}}}

        self.module._request_json = fake_request

        result = self.module.sync_trackers(
            [
                {
                    "key": "PCO-200",
                    "url": "https://staffany.atlassian.net/browse/PCO-200",
                    "summary": "Dreamus invoice customer loop",
                    "status": "Waiting Internal",
                    "roi_issue_key": "ROI-99",
                }
            ],
            self.as_of,
        )
        output = self.module.format_result(result)

        self.assertEqual(result["changed"], [])
        self.assertTrue(output.startswith("[SILENT] PSM Ops automation:"))
        self.assertEqual(len(calls), 1)

    def test_sync_wakes_tracker_when_linked_roi_done(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/issue/ROI-99"):
                return {"fields": {"summary": "Invoice check", "status": {"name": "Done", "statusCategory": {"key": "done"}}}}
            if method == "POST" and path.endswith("/comment"):
                return {"id": "comment-1"}
            if method == "GET" and path.endswith("/transitions"):
                return {"transitions": [{"id": "31", "name": "Open", "to": {"name": "Open"}}]}
            return {}

        self.module._request_json = fake_request

        result = self.module.sync_trackers(
            [
                {
                    "key": "PCO-200",
                    "url": "https://staffany.atlassian.net/browse/PCO-200",
                    "summary": "Dreamus invoice customer loop",
                    "status": "Waiting Internal",
                    "roi_issue_key": "ROI-99",
                }
            ],
            self.as_of,
        )
        output = self.module.format_result(result)

        self.assertEqual(len(result["changed"]), 1)
        self.assertTrue(output.startswith("PSM Ops automation: ROI tracker sync"))
        self.assertIn("/rest/servicedeskapi/request/PCO-200/comment", [call[1] for call in calls])
        self.assertIn(("POST", "/rest/api/3/issue/PCO-200/transitions", {"transition": {"id": "31"}}), calls)
        self.assertIn(("PUT", "/rest/api/3/issue/PCO-200", {"fields": {"duedate": "2026-05-15"}}), calls)

    def test_missing_link_metadata_is_reported(self):
        result = self.module.sync_trackers(
            [
                {
                    "key": "PCO-201",
                    "url": "https://staffany.atlassian.net/browse/PCO-201",
                    "summary": "Missing ROI link",
                    "status": "Waiting Internal",
                    "roi_issue_key": "",
                }
            ],
            self.as_of,
        )
        output = self.module.format_result(result)

        self.assertEqual(result["changed"], [])
        self.assertEqual(result["blocked"][0]["reason"], "missing linked ROI issue")
        self.assertIn("Needs attention", output)
        self.assertFalse(output.startswith("[SILENT]"))

    def test_safe_tracker_extracts_linked_roi_without_raw_fields(self):
        tracker = self.module.safe_tracker(
            {
                "key": "PCO-202",
                "fields": {
                    "summary": "Dreamus invoice",
                    "status": {"name": "Waiting Internal"},
                    "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "ROI-123"}}],
                    "description": "must not leak",
                    "comment": {"comments": ["must not leak"]},
                },
            }
        )

        self.assertEqual(tracker["roi_issue_key"], "ROI-123")
        self.assertNotIn("description", tracker)
        self.assertNotIn("comment", tracker)


if __name__ == "__main__":
    unittest.main()
