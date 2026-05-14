from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class PsmJiraServerTest(unittest.TestCase):
    def test_profile_env_loads_for_sanitized_mcp_child_env(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".hermes" / "profiles" / "psmopsbot" / ".env"
            env_path.parent.mkdir(parents=True)
            env_path.write_text(
                "\n".join(
                    [
                        "PSM_OPS_JIRA_MODE=thin_poc",
                        "JIRA_BASE_URL=https://staffany.atlassian.net",
                        "JIRA_EMAIL=bot@staffany.com",
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"HOME": tmpdir}, clear=True):
                module = load_mcp_module("psm_jira_server.py", "psm_jira_profile_env_test")
                self.assertEqual(module._jira_mode(), "thin_poc")
                self.assertEqual(os.environ["JIRA_EMAIL"], "bot@staffany.com")

    def setUp(self):
        self.module = load_mcp_module("psm_jira_server.py")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        policy_path = Path(self.tmpdir.name) / "policy.json"
        policy_path.write_text(
            json.dumps(
                {
                    "users": [
                        {
                            "slack_email": "psm@staffany.com",
                            "jira_account_id": "acct-123",
                            "display_name": "Ada PSM",
                            "ps_team": "Ada PSM",
                            "ps_team_option_id": "team-ada",
                            "active": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.env = patch.dict(
            os.environ,
            {
                "JIRA_BASE_URL": "https://staffany.atlassian.net",
                "JIRA_EMAIL": "bot@staffany.com",
                "JIRA_API_TOKEN": "jira-token",
                "PSM_OPS_JIRA_MODE": "full",
                "PSM_OPS_ACCESS_POLICY_PATH": str(policy_path),
                "PSM_OPS_JIRA_SERVICE_DESK_ID": "10",
                "PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION": "101",
                "PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK": "102",
                "PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE": "103",
                "PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE": "104",
                "PSM_OPS_JIRA_FIELD_CUSTOMER": "customfield_10101",
                "PSM_OPS_JIRA_FIELD_STAFFANY_ORGS": "customfield_10102",
                "PSM_OPS_JIRA_FIELD_OWNER_PSM": "customfield_10103",
                "PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE": "customfield_10104",
                "PSM_OPS_JIRA_FIELD_ACTION_TYPE": "customfield_10105",
                "PSM_OPS_JIRA_FIELD_RISK_REASON": "customfield_10106",
                "PSM_OPS_JIRA_FIELD_SOURCE_LINKS": "customfield_10107",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "customfield_10108",
                "PSM_OPS_JIRA_FIELD_PS_TEAM": "customfield_10876",
                "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": "",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def _customer_channel_map(self, entries: list[dict]) -> str:
        path = Path(self.tmpdir.name) / "customer-channel-map.json"
        path.write_text(json.dumps({"channels": entries}), encoding="utf-8")
        return str(path)

    def test_list_my_tasks_is_ps_team_scoped_and_safe(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            self.assertEqual(method, "GET")
            return {
                "issues": [
                    {
                        "key": "PCO-1",
                        "fields": {
                            "summary": "Confirm payroll readiness",
                            "status": {"name": "Open"},
                            "priority": {"name": "High"},
                            "assignee": {"displayName": "Ada PSM"},
                            "customfield_10876": {"value": "Ada PSM", "id": "team-ada"},
                            "duedate": "2026-05-15",
                            "updated": "2026-05-12T00:00:00.000+0000",
                            "issuetype": {"name": "Customer Next Action"},
                            "customfield_10108": "2026-05-13T09:00:00+08:00",
                        },
                    }
                ]
            }

        self.module._request_json = fake_request

        result = self.module.list_my_pco_tasks("psm@staffany.com", "overdue")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("cf%5B10876%5D+%3D+%22Ada+PSM%22", calls[0][1])
        self.assertIn("duedate+%3C+now%28%29", calls[0][1])
        self.assertEqual(result["answer"][0]["issue_key"], "PCO-1")
        self.assertEqual(result["answer"][0]["ps_team"], "Ada PSM")
        self.assertNotIn("description", result["answer"][0])

    def test_draft_requires_no_mutation_and_returns_duplicate_candidates(self):
        def fake_request(method, path, body=None):
            self.assertEqual(method, "GET")
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.draft_pco_task(
            slack_user_email="psm@staffany.com",
            customer="Fei Siong Group",
            summary="Confirm payroll readiness",
            due_date="2026-05-15",
            source_links=["https://customer-360.example/companies/fei-siong-group"],
        )

        self.assertEqual(result["confidence"], "verified")
        draft = result["answer"]["draft"]
        self.assertTrue(draft["approval_required"])
        self.assertEqual(draft["owner_jira_account_id"], "acct-123")
        self.assertEqual(draft["request_type_id"], "101")

    def test_draft_infers_cs_duty_as_ps_team_not_assignee(self):
        def fake_request(method, path, body=None):
            self.assertEqual(method, "GET")
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.draft_pco_task(
            slack_user_email="psm@staffany.com",
            customer="House of Pok",
            summary="March and April payroll import for cs duty",
            due_date="2026-05-25",
            request_type_key="data_hygiene",
        )

        self.assertEqual(result["confidence"], "verified")
        draft = result["answer"]["draft"]
        self.assertEqual(draft["ps_team"], "CS Duty")
        self.assertEqual(draft["owner_jira_account_id"], "acct-123")

    def test_request_values_resolve_ps_team_option_value(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            self.assertEqual(method, "GET")
            self.assertIn("/field", path)
            return {
                "requestTypeFields": [
                    {
                        "fieldId": "customfield_10876",
                        "name": "PS Team",
                        "validValues": [{"value": "12025", "label": "CS Duty"}],
                    }
                ]
            }

        self.module._request_json = fake_request

        values = self.module._request_field_values(
            {
                "summary": "Payroll import",
                "ps_team": "cs duty",
                "request_type_id": "103",
            }
        )

        self.assertEqual(values["customfield_10876"], "12025")

    def test_set_pco_ps_team_maps_cs_duty_to_jira_option(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if path.endswith("/field"):
                return {
                    "requestTypeFields": [
                        {
                            "fieldId": "customfield_10876",
                            "name": "PS Team",
                            "validValues": [{"value": "12025", "label": "CS Duty"}],
                        }
                    ]
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.set_pco_ps_team("PCO-134", "cs duty", "psm@staffany.com")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["ps_team"], "CS Duty")
        self.assertEqual(calls[1][0], "PUT")
        self.assertEqual(calls[1][1], "/rest/api/3/issue/PCO-134")
        self.assertEqual(calls[1][2]["fields"]["customfield_10876"], {"id": "12025"})

    def test_set_pco_assignee_resolves_slack_mention_to_jira_account(self):
        calls = []

        def fake_slack_users():
            return [
                {
                    "id": "U0AMZ85LNAF",
                    "name": "alya",
                    "real_name": "Atalya Ong",
                    "profile": {"email": "atalya@staffany.com", "real_name": "Atalya Ong", "display_name": "Alya"},
                }
            ]

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if path.startswith("/rest/api/3/user/assignable/search?"):
                return [
                    {
                        "accountId": "acct-alya",
                        "displayName": "Atalya Ong",
                        "emailAddress": "atalya@staffany.com",
                        "active": True,
                    }
                ]
            return {}

        self.module._slack_users = fake_slack_users
        self.module._request_json = fake_request

        result = self.module.set_pco_assignee("PCO-135", "<@U0AMZ85LNAF>", "psm@staffany.com")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["assignee"], "Atalya Ong")
        self.assertIn("/rest/api/3/user/assignable/search?", calls[0][1])
        self.assertIn("issueKey=PCO-135", calls[0][1])
        self.assertIn("query=atalya%40staffany.com", calls[0][1])
        self.assertEqual(calls[1][0], "PUT")
        self.assertEqual(calls[1][1], "/rest/api/3/issue/PCO-135/assignee")
        self.assertEqual(calls[1][2], {"accountId": "acct-alya"})

    def test_resolve_slack_user_identity_returns_safe_single_user_fields(self):
        def fake_slack_users():
            return [
                {
                    "id": "U01C0PJD9HQ",
                    "name": "josica.lim",
                    "real_name": "Josica Lim",
                    "profile": {
                        "email": "josica@staffany.com",
                        "real_name": "Josica Lim",
                        "display_name": "Josica",
                    },
                }
            ]

        self.module._slack_users = fake_slack_users

        result = self.module.resolve_slack_user_identity("<@U01C0PJD9HQ>")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["source"], "Slack users.list")
        self.assertEqual(result["answer"]["slack_user_id"], "U01C0PJD9HQ")
        self.assertEqual(result["answer"]["real_name"], "Josica Lim")
        self.assertEqual(result["answer"]["display_name"], "Josica")
        self.assertEqual(result["answer"]["email"], "josica@staffany.com")
        self.assertIn("no bulk Slack export", result["caveat"])

    def test_resolve_slack_user_identity_blocks_ambiguous_short_name(self):
        def fake_slack_users():
            return [
                {
                    "id": "U1",
                    "name": "jo.one",
                    "real_name": "Jo One",
                    "profile": {"email": "jo.one@staffany.com", "display_name": "Jo"},
                },
                {
                    "id": "U2",
                    "name": "jo.two",
                    "real_name": "Jo Two",
                    "profile": {"email": "jo.two@staffany.com", "display_name": "Jo"},
                },
            ]

        self.module._slack_users = fake_slack_users

        result = self.module.resolve_slack_user_identity("Jo")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("No unique Slack user", result["caveat"])

    def test_resolve_customer_channel_org_returns_reviewed_mapping(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001", "FS-002"],
                    "status": "reviewed",
                }
            ]
        )
        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.resolve_customer_channel_org(
                "https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                customer="Fei Siong",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["customer_name"], "Fei Siong Group")
        self.assertEqual(result["answer"]["staffany_orgs"], ["FS-001", "FS-002"])

    def test_resolve_customer_channel_org_blocks_conflicting_customer(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001"],
                    "status": "reviewed",
                }
            ]
        )
        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.resolve_customer_channel_org(
                "https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                customer="Walta Tech",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("maps to Fei Siong Group", result["caveat"])

    def test_set_pco_assignee_blocks_ambiguous_name(self):
        def fake_request(method, path, body=None):
            if path.startswith("/rest/api/3/user/assignable/search?"):
                return [
                    {"accountId": "acct-1", "displayName": "Alya One", "active": True},
                    {"accountId": "acct-2", "displayName": "Alya Two", "active": True},
                ]
            return {}

        self.module._request_json = fake_request
        self.module._slack_users = lambda: []

        result = self.module.set_pco_assignee("PCO-135", "Alya", "psm@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("No unique assignable Jira user", result["caveat"])

    def test_create_requires_approval_marker(self):
        result = self.module.create_approved_pco_task(
            {"customer": "Fei Siong", "summary": "Task", "due_date": "2026-05-15"},
            "yes",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("approval", result["caveat"].lower())

    def test_create_posts_jsm_request_after_approval(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"issueKey": "PCO-123", "requestTypeId": "101"}

        self.module._request_json = fake_request

        result = self.module.create_approved_pco_task(
            {
                "customer": "Fei Siong",
                "summary": "Confirm payroll readiness",
                "due_date": "2026-05-15",
                "priority": "High",
                "action_type": "Customer success",
                "request_type_id": "101",
                "source_links": ["https://c360/fei"],
                "owner_psm": "Ada PSM",
                "owner_jira_account_id": "acct-123",
            },
            "create",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], "/rest/servicedeskapi/request")
        self.assertEqual(calls[0][2]["serviceDeskId"], "10")
        self.assertEqual(calls[0][2]["requestTypeId"], "101")
        self.assertEqual(calls[0][2]["raiseOnBehalfOf"], "acct-123")
        self.assertEqual(calls[1][0], "PUT")
        self.assertEqual(calls[1][1], "/rest/api/3/issue/PCO-123")
        self.assertEqual(calls[1][2]["fields"], {"duedate": "2026-05-15"})

    def test_ps_wee_intake_creates_immediate_ticket_with_slack_trace(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-789", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-789"}
            return {}

        self.module._request_json = fake_request

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
            customer="Fei Siong",
            issue_summary="Payroll readiness unclear",
            known_details="PS asked to raise this first.",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[1][0], "POST")
        self.assertEqual(calls[1][1], "/rest/servicedeskapi/request")
        self.assertEqual(
            calls[1][2]["requestFieldValues"]["summary"],
            "[Needs info] Fei Siong - Payroll readiness unclear",
        )
        self.assertEqual(calls[2][1], "/rest/servicedeskapi/request/PCO-789/comment")
        self.assertIn("Source Slack thread: https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579", calls[2][2]["body"])
        self.assertIn("Known details: PS asked to raise this first.", calls[2][2]["body"])
        self.assertEqual(calls[3][1], "/rest/api/3/issue/PCO-789")
        self.assertEqual(calls[3][2]["update"]["labels"], [{"add": "needs-info"}])
        self.assertIn("Created first so this won't be missed", result["answer"]["slack_reply"])
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-789|PCO-789>", result["answer"]["slack_reply"])

    def test_ps_wee_intake_auto_tags_reviewed_customer_channel_with_blank_customer(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001", "FS-002"],
                    "status": "reviewed",
                }
            ]
        )
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-790", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-790"}
            return {}

        self.module._request_json = fake_request

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "verified")
        request_values = calls[1][2]["requestFieldValues"]
        self.assertEqual(request_values["customfield_10101"], "Fei Siong Group")
        self.assertEqual(request_values["customfield_10102"], "FS-001, FS-002")
        self.assertEqual(request_values["summary"], "[Needs info] Fei Siong Group - Payroll readiness unclear")
        self.assertNotIn("customer/org", result["answer"]["missing_info"])
        self.assertIn("Customer channel: C08SDJR03N1", calls[2][2]["body"])
        self.assertIn("Customer 360 customer key: fei-siong-group", calls[2][2]["body"])

    def test_ps_wee_intake_reviewed_channel_allows_matching_customer(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001"],
                    "status": "reviewed",
                }
            ]
        )
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-791", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-791"}
            return {}

        self.module._request_json = fake_request

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                customer="Fei Siong",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[1][2]["requestFieldValues"]["customfield_10102"], "FS-001")

    def test_ps_wee_intake_blocks_conflicting_customer_channel_mapping(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001"],
                    "status": "reviewed",
                }
            ]
        )
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            return {}

        self.module._request_json = fake_request

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                customer="Walta Tech",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(len(calls), 1)
        self.assertIn("Confirm the customer", result["caveat"])

    def test_ps_wee_intake_blocks_unreviewed_customer_channel_mapping(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "C08SDJR03N1",
                    "channel_name": "cust-fei-siong",
                    "customer_key": "fei-siong-group",
                    "customer_name": "Fei Siong Group",
                    "staffany_orgs": ["FS-001"],
                    "status": "needs_review",
                }
            ]
        )
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            return {}

        self.module._request_json = fake_request

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(len(calls), 1)
        self.assertIn("not reviewed", result["caveat"])

    def test_ps_wee_intake_unmapped_channel_keeps_current_needs_info_behavior(self):
        map_path = self._customer_channel_map(
            [
                {
                    "channel_id": "COTHER123",
                    "channel_name": "cust-other",
                    "customer_key": "other",
                    "customer_name": "Other Customer",
                    "staffany_orgs": ["OTHER"],
                    "status": "reviewed",
                }
            ]
        )
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-792", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-792"}
            return {}

        self.module._request_json = fake_request

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "verified")
        request_values = calls[1][2]["requestFieldValues"]
        self.assertEqual(request_values["summary"], "[Needs info] Unknown customer - Payroll readiness unclear")
        self.assertNotIn("customfield_10102", request_values)
        self.assertIn("customer/org", result["answer"]["missing_info"])

    def test_ps_wee_intake_reuses_existing_ticket_for_same_slack_thread(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            self.assertEqual(method, "GET")
            return {
                "issues": [
                    {
                        "key": "PCO-789",
                        "fields": {
                            "summary": "[Needs info] Fei Siong - Payroll readiness unclear",
                            "status": {"name": "Open"},
                            "priority": {"name": "Medium"},
                        },
                    }
                ]
            }

        self.module._request_json = fake_request

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["existing_ticket"]["issue_key"], "PCO-789")
        self.assertEqual(len(calls), 1)

    def test_append_ps_wee_ticket_update_posts_structured_comment_only(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"id": "comment-790"}

        self.module._request_json = fake_request

        result = self.module.append_ps_wee_ticket_update(
            issue_key="PCO-789",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
            update_summary="PS confirmed impact and affected date range.",
            updated_fields={"impact": "Payroll blocked", "affected date range": "May payroll"},
            evidence_links=["https://example.com/screenshot"],
        )

        self.assertEqual(result["confidence"], "verified")
        body = calls[0][2]["body"]
        self.assertIn("PS WEE Slack ticket update:", body)
        self.assertIn("Source Slack thread: https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579", body)
        self.assertIn("- impact: Payroll blocked", body)
        self.assertIn("- affected date range: May payroll", body)
        self.assertIn("- https://example.com/screenshot", body)
        self.assertFalse(calls[0][2]["public"])

    def test_mark_ps_wee_ticket_ready_comments_and_removes_needs_info_label(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            if path.endswith("/comment"):
                return {"id": "comment-791"}
            return {}

        self.module._request_json = fake_request

        result = self.module.mark_ps_wee_ticket_ready(
            issue_key="PCO-789",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
            ready_summary="Customer, issue, impact, scope, and outcome are now complete.",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("PS WEE ticket ready for triage.", calls[0][2]["body"])
        self.assertEqual(calls[1][1], "/rest/api/3/issue/PCO-789")
        self.assertEqual(calls[1][2]["update"]["labels"], [{"remove": "needs-info"}])
        self.assertTrue(result["answer"]["ready_for_triage"])

    def test_transition_uses_available_transition_to_target_status(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            if method == "GET":
                return {
                    "transitions": [
                        {"id": "31", "name": "Schedule", "to": {"name": "Scheduled"}}
                    ]
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.transition_pco_task("PCO-123", "Scheduled")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[1][2]["transition"]["id"], "31")

    def test_transition_accepts_thin_poc_pending_status_aliases(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            if method == "GET":
                return {
                    "transitions": [
                        {
                            "id": "41",
                            "name": "Pending",
                            "to": {"name": "Pending Customer"},
                        }
                    ]
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.transition_pco_task("PCO-123", "Waiting Customer")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["status"], "Waiting Customer")
        self.assertEqual(calls[1][2]["transition"]["id"], "41")

    def test_public_comment_blocks_by_default(self):
        result = self.module.add_internal_pco_comment(
            "PCO-123",
            "Visible to customer",
            public_comment=True,
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Public", result["caveat"])

    def test_internal_comment_posts_jsm_private_comment(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"id": "comment-1"}

        self.module._request_json = fake_request

        result = self.module.add_internal_pco_comment(
            "PCO-123",
            "Training moved to Friday",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][1], "/rest/servicedeskapi/request/PCO-123/comment")
        self.assertFalse(calls[0][2]["public"])

    def test_set_reminder_updates_due_date_for_automatic_reminders(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {}

        self.module._request_json = fake_request

        result = self.module.set_pco_reminder(
            "PCO-123",
            "2026-05-14T09:00:00+08:00",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "PUT")
        self.assertEqual(
            calls[0][2]["fields"],
            {"duedate": "2026-05-14"},
        )
        self.assertEqual(result["answer"]["due_date"], "2026-05-14")

    def test_due_reminders_use_due_date_one_day_before_and_overdue(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.list_due_pco_reminders(as_of="2026-05-13T01:00:00Z")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("duedate+is+not+EMPTY", calls[0][1])
        self.assertIn("duedate+%3C%3D+%222026-05-14%22", calls[0][1])

    def test_due_reminders_window_uses_upper_bound(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.list_due_pco_reminders(
            as_of="2026-05-13T01:00:00+00:00",
            window_hours=6,
            include_overdue=False,
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("duedate+%3E%3D+%222026-05-13%22", calls[0][1])
        self.assertIn("duedate+%3C%3D+%222026-05-13%22", calls[0][1])

    def test_thin_poc_validate_uses_current_pco_defaults(self):
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_ACCESS_POLICY_PATH": "",
                "PSM_OPS_JIRA_SERVICE_DESK_ID": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE": "",
                "PSM_OPS_JIRA_FIELD_CUSTOMER": "",
                "PSM_OPS_JIRA_FIELD_STAFFANY_ORGS": "",
                "PSM_OPS_JIRA_FIELD_OWNER_PSM": "",
                "PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE": "",
                "PSM_OPS_JIRA_FIELD_ACTION_TYPE": "",
                "PSM_OPS_JIRA_FIELD_RISK_REASON": "",
                "PSM_OPS_JIRA_FIELD_SOURCE_LINKS": "",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "",
            },
            clear=False,
        ):
            def fake_request(method, path, body=None):
                if path == "/rest/api/3/field":
                    return [
                        {"id": "customfield_10667"},
                        {"id": "customfield_10876"},
                    ]
                return {"requestTypeFields": []}

            self.module._request_json = fake_request

            result = self.module.validate_jira_configuration()

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["service_desk_id"], "70")
        self.assertEqual(result["answer"]["request_types"]["customer_next_action"]["id"], "81")
        self.assertFalse(result["answer"]["request_types"]["handoff_package"]["enabled"])
        self.assertEqual(result["answer"]["fields"]["staffany_orgs"], "customfield_10667")
        self.assertEqual(result["answer"]["fields"]["ps_team"], "customfield_10876")

    def test_thin_poc_list_uses_ps_team_without_policy(self):
        calls = []
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_ACCESS_POLICY_PATH": "",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "",
            },
            clear=False,
        ):
            def fake_request(method, path, body=None):
                calls.append((method, path, body))
                if path.startswith("/rest/api/3/user/search?"):
                    return [
                        {
                            "accountId": "acct-from-jira",
                            "displayName": "Ada PSM",
                            "emailAddress": "psm@staffany.com",
                            "active": True,
                        }
                    ]
                if path == "/rest/api/3/field/customfield_10876/context":
                    return {"values": [{"id": "context-1"}]}
                if path.startswith("/rest/api/3/field/customfield_10876/context/context-1/option?"):
                    return {"values": [{"id": "team-ada", "value": "Ada PSM", "disabled": False}], "isLast": True}
                return {"issues": []}

            self.module._request_json = fake_request

            result = self.module.list_my_pco_tasks("<mailto:psm@staffany.com|psm@staffany.com>")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("/rest/api/3/user/search?", calls[0][1])
        self.assertIn("query=psm%40staffany.com", calls[0][1])
        self.assertEqual(result["scope"]["ps_team"], "Ada PSM")
        self.assertIn("cf%5B10876%5D+%3D+%22Ada+PSM%22", calls[-1][1])
        self.assertNotIn("customfield_10108", calls[-1][1])

    def test_thin_poc_resolves_configured_slack_to_jira_email_alias(self):
        calls = []
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_ACCESS_POLICY_PATH": "",
                "PSM_OPS_JIRA_EMAIL_ALIASES": "kai.yi@staffany.com=kaiyi@staffany.com",
            },
            clear=False,
        ), patch.object(self.module, "_slack_users", return_value=[]):
            def fake_request(method, path, body=None):
                calls.append((method, path, body))
                if path.startswith("/rest/api/3/user/search?"):
                    return [
                        {
                            "accountId": "acct-kaiyi",
                            "displayName": "Kaiyi Lee",
                            "emailAddress": "kaiyi@staffany.com",
                            "active": True,
                        }
                    ]
                if path == "/rest/api/3/field/customfield_10876/context":
                    return {"values": [{"id": "context-1"}]}
                if path.startswith("/rest/api/3/field/customfield_10876/context/context-1/option?"):
                    return {"values": [{"id": "team-kaiyi", "value": "Kai Yi", "disabled": False}], "isLast": True}
                return {"issues": []}

            self.module._request_json = fake_request

            result = self.module.list_my_pco_tasks("kai.yi@staffany.com")

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("query=kaiyi%40staffany.com", calls[0][1])
        self.assertEqual(result["scope"]["caller"], "kai.yi@staffany.com")
        self.assertEqual(result["scope"]["ps_team"], "Kai Yi")
        self.assertIn("cf%5B10876%5D+%3D+%22Kai+Yi%22", calls[-1][1])

    def test_thin_poc_slack_roster_corrects_guessed_email_and_matches_ps_team(self):
        calls = []
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_ACCESS_POLICY_PATH": "",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "",
            },
            clear=False,
        ), patch.object(
            self.module,
            "_slack_users",
            return_value=[
                {
                    "id": "U-kaiyi",
                    "name": "kaiyilee",
                    "real_name": "Kai Yi Lee",
                    "profile": {"email": "kaiyi@staffany.com", "real_name": "Kai Yi Lee", "display_name": "Kai Yi"},
                }
            ],
        ):
            def fake_request(method, path, body=None):
                calls.append((method, path, body))
                if path.startswith("/rest/api/3/user/search?"):
                    return [
                        {
                            "accountId": "acct-kaiyi",
                            "displayName": "Kaiyi Lee",
                            "emailAddress": "kaiyi@staffany.com",
                            "active": True,
                        }
                    ]
                if path == "/rest/api/3/field/customfield_10876/context":
                    return {"values": [{"id": "context-1"}]}
                if path.startswith("/rest/api/3/field/customfield_10876/context/context-1/option?"):
                    return {"values": [{"id": "team-kaiyi", "value": "Kai Yi", "disabled": False}], "isLast": True}
                return {"issues": []}

            self.module._request_json = fake_request

            result = self.module.list_my_pco_tasks("kai.yi@staffany.com")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["caller"], "kaiyi@staffany.com")
        self.assertEqual(result["scope"]["ps_team"], "Kai Yi")
        self.assertIn("query=kaiyi%40staffany.com", calls[0][1])
        self.assertIn("cf%5B10876%5D+%3D+%22Kai+Yi%22", calls[-1][1])

    def test_thin_poc_create_retries_summary_only_comments_and_assigns(self):
        calls = []
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_ACCESS_POLICY_PATH": "",
                "PSM_OPS_JIRA_SERVICE_DESK_ID": "",
                "PSM_OPS_JIRA_FIELD_STAFFANY_ORGS": "",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "",
            },
            clear=False,
        ):
            def fake_request(method, path, body=None):
                calls.append((method, path, deepcopy(body)))
                if path == "/rest/servicedeskapi/request" and "customfield_10667" in body["requestFieldValues"]:
                    raise self.module.JiraError("Jira rejected optional field value")
                if path == "/rest/servicedeskapi/request":
                    return {"issueKey": "PCO-456", "requestTypeId": "81"}
                if path.endswith("/comment"):
                    return {"id": "comment-456"}
                return {}

            self.module._request_json = fake_request

            result = self.module.create_approved_pco_task(
                {
                    "customer": "Fei Siong",
                    "summary": "Confirm payroll readiness",
                    "due_date": "2026-05-15",
                    "priority": "High",
                    "action_type": "Customer success",
                    "request_type_id": "81",
                    "source_links": ["https://c360/fei"],
                    "staffany_orgs": ["FS-001"],
                    "owner_psm": "Ada PSM",
                    "owner_jira_account_id": "acct-123",
                    "mode": "thin_poc",
                },
                "create",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][2]["requestFieldValues"]["customfield_10667"], "FS-001")
        self.assertEqual(calls[1][2]["requestFieldValues"], {"summary": "Confirm payroll readiness"})
        self.assertEqual(calls[2][1], "/rest/api/3/issue/PCO-456")
        self.assertEqual(calls[2][2]["fields"], {"duedate": "2026-05-15"})
        self.assertEqual(calls[3][1], "/rest/servicedeskapi/request/PCO-456/comment")
        self.assertEqual(calls[4][1], "/rest/api/3/issue/PCO-456/assignee")
        self.assertIn("Optional PCO request fields were skipped", result["answer"]["warnings"][0])

    def test_thin_poc_reminder_uses_due_date_without_custom_field(self):
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_JIRA_FIELD_REMINDER_AT": "",
            },
            clear=False,
        ):
            calls = []

            def fake_request(method, path, body=None):
                calls.append((method, path, body))
                return {}

            self.module._request_json = fake_request
            result = self.module.set_pco_reminder("PCO-123", "2026-05-14T09:00:00+08:00")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["due_date"], "2026-05-14")
        self.assertEqual(calls[0][2]["fields"], {"duedate": "2026-05-14"})


if __name__ == "__main__":
    unittest.main()
