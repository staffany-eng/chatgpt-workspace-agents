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

    def test_request_types_resource_exposes_identity_contract(self):
        module = load_mcp_module("psm_jira_server.py", "psm_jira_resource_test")
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_JIRA_MODE": "thin_poc",
                "PSM_OPS_JIRA_SERVICE_DESK_ID": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE": "",
                "PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE": "",
                "PSM_OPS_JIRA_FIELD_STAFFANY_ORGS": "",
            },
            clear=False,
        ):
            payload = json.loads(module.jira_request_types_resource())

        self.assertEqual(payload["request_types"]["customer_next_action"], "81")
        self.assertEqual(payload["request_types"]["handoff_package"], "disabled_until_request_type_exists")
        self.assertIn("Slack sender user id", payload["caller_identity"]["accepted_values"])
        self.assertIn("do not ask the user for email", payload["caller_identity"]["rule"])

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
                        },
                        {
                            "slack_email": "reporter@staffany.com",
                            "jira_account_id": "acct-reporter",
                            "display_name": "Rina Reporter",
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
                "SLACK_BOT_TOKEN": "xoxb-fake",
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
                "PSM_OPS_ROI_JIRA_PROJECT_KEY": "ROI",
                "PSM_OPS_ROI_JIRA_SERVICE_DESK_ID": "20",
                "PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID": "201",
                "PSM_OPS_ROI_JIRA_FIELD_CUSTOMER": "customfield_20101",
                "PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY": "customfield_20102",
                "PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS": "customfield_20103",
                "PSM_OPS_ROI_JIRA_FIELD_REQUESTER": "customfield_20104",
                "PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL": "customfield_20105",
                "PSM_OPS_ROI_JIRA_FIELD_PRIORITY": "customfield_20106",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def _roi_fields(self, customer_required=True, extra_required=None):
        fields = [
            {"fieldId": "summary", "name": "Summary", "required": True},
            {"fieldId": "description", "name": "Details", "required": True},
            {"fieldId": "customfield_20101", "name": "Customer", "required": customer_required},
            {
                "fieldId": "customfield_20102",
                "name": "Request category",
                "required": True,
                "validValues": [
                    {"value": "BD Ops", "label": "BD Ops"},
                    {"value": "NYSS", "label": "NYSS"},
                    {"value": "RevOps", "label": "RevOps"},
                    {"value": "ROI", "label": "ROI"},
                    {"value": "Billing / invoice", "label": "Billing / invoice"},
                ],
            },
            {"fieldId": "customfield_20103", "name": "Source links", "required": True},
            {"fieldId": "customfield_20104", "name": "Requester", "required": True},
            {"fieldId": "customfield_20105", "name": "Original channel", "required": False},
            {
                "fieldId": "customfield_20106",
                "name": "Priority",
                "required": False,
                "validValues": [{"value": "Medium", "label": "Medium"}, {"value": "High", "label": "High"}],
            },
        ]
        for field_name in extra_required or []:
            fields.append({"fieldId": f"customfield_extra_{len(fields)}", "name": field_name, "required": True})
        return fields

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
        audit_calls = []

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
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
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
        self.assertIn("Source Slack thread: https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579", calls[2][2]["body"])
        self.assertIn("Known details: PS asked to raise this first.", calls[2][2]["body"])
        self.assertEqual(calls[3][1], "/rest/api/3/issue/PCO-789")
        self.assertEqual(calls[3][2]["update"]["labels"], [{"add": "needs-info"}])
        self.assertIn("Created first so this won't be missed", result["answer"]["slack_reply"])
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-789|PCO-789>", result["answer"]["slack_reply"])
        self.assertEqual(audit_calls[0][0], "ticket_created")
        self.assertEqual(audit_calls[0][1]["source_thread_url"], "https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579")
        self.assertEqual(audit_calls[0][1]["issue_key"], "PCO-789")

    def test_ps_wee_intake_reuses_existing_ticket_for_same_slack_thread(self):
        calls = []
        audit_calls = []

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
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["existing_ticket"]["issue_key"], "PCO-789")
        self.assertEqual(len(calls), 1)
        self.assertEqual(audit_calls[0][0], "ticket_reused")
        self.assertEqual(audit_calls[0][1]["issue_key"], "PCO-789")

    def test_roi_intent_routes_aliases_to_roi(self):
        examples = [
            "Create a task for bd ops to send Dreamus invoice",
            "add BD Ops to check the renewal invoice",
            "log nyss ticket for accessible invoice issue",
            "handle n y s s MRR mismatch",
            "create RevOps ticket for HubSpot deal check",
            "put this ROI request on the board",
        ]

        for text in examples:
            with self.subTest(text=text):
                result = self.module.classify_roi_ticket_request(text)
                self.assertEqual(result["confidence"], "verified")
                self.assertTrue(result["answer"]["is_roi_ticket_request"])

    def test_roi_intent_blocks_casual_nyss_question(self):
        result = self.module.classify_roi_ticket_request("@nyss what is the Stripe password")

        self.assertEqual(result["confidence"], "verified")
        self.assertFalse(result["answer"]["is_roi_ticket_request"])
        self.assertFalse(result["answer"]["action_detected"])

    def test_roi_ticket_defaults_requester_to_slack_sender(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path.endswith("/requesttype/201/field"):
                return {"requestTypeFields": self._roi_fields()}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "ROI-123", "requestTypeId": "201"}
            if path.endswith("/comment"):
                return {"id": "comment-roi-123"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_roi_ticket_from_slack(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219139",
            message_text="Create a task for bd ops to send Dreamus invoice",
            customer="Dreamus",
            original_channel="#team-rev-bd-ops",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = calls[2]
        self.assertEqual(create_call[0], "POST")
        self.assertEqual(create_call[1], "/rest/servicedeskapi/request")
        payload = create_call[2]
        self.assertEqual(payload["serviceDeskId"], "20")
        self.assertEqual(payload["requestTypeId"], "201")
        self.assertEqual(payload["raiseOnBehalfOf"], "acct-123")
        values = payload["requestFieldValues"]
        self.assertEqual(values["customfield_20101"], "Dreamus")
        self.assertEqual(values["customfield_20102"], "BD Ops")
        self.assertIn("https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219139", values["customfield_20103"])
        self.assertIn("Ada PSM", values["customfield_20104"])
        self.assertEqual(values["customfield_20105"], "#team-rev-bd-ops")
        self.assertEqual(calls[3][1], "/rest/servicedeskapi/request/ROI-123/comment")
        self.assertIn("Requester: Ada PSM", calls[3][2]["body"])
        self.assertIn("Created ROI ticket", result["answer"]["slack_reply"])
        self.assertEqual(audit_calls[0][0], "roi_ticket_created")
        self.assertEqual(audit_calls[0][1]["issue_key"], "ROI-123")

    def test_roi_ticket_explicit_requester_overrides_sender(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path.endswith("/requesttype/201/field"):
                return {"requestTypeFields": self._roi_fields(customer_required=False)}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "ROI-124", "requestTypeId": "201"}
            if path.endswith("/comment"):
                return {"id": "comment-roi-124"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_roi_ticket_from_slack(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219140",
            message_text="Create RevOps ticket for renewal invoice, requested by reporter@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        payload = calls[2][2]
        self.assertEqual(payload["raiseOnBehalfOf"], "acct-reporter")
        self.assertIn("Rina Reporter", payload["requestFieldValues"]["customfield_20104"])
        self.assertEqual(result["answer"]["requester_source"], "explicit_requester")

    def test_roi_ticket_unresolved_requester_blocks_creation(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            return {}

        self.module._request_json = fake_request

        result = self.module.create_roi_ticket_from_slack(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219141",
            message_text="Create BD Ops ticket for discount approval, reported by unknown@staffany.com",
            customer="Dreamus",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("No active Jira account mapping", result["caveat"])
        self.assertEqual([call for call in calls if call[0] == "POST"], [])

    def test_roi_ticket_missing_required_fields_blocks_with_exact_names(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path.endswith("/requesttype/201/field"):
                return {"requestTypeFields": self._roi_fields(customer_required=True)}
            return {}

        self.module._request_json = fake_request

        result = self.module.create_roi_ticket_from_slack(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219142",
            message_text="Create a task for bd ops to check invoice",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["scope"]["missing_fields"], ["Customer"])
        self.assertIn("Missing required ROI fields: Customer", result["caveat"])
        self.assertEqual([call for call in calls if call[0] == "POST"], [])

    def test_roi_ticket_reuses_existing_same_thread_ticket(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            self.assertEqual(method, "GET")
            return {
                "issues": [
                    {
                        "key": "ROI-555",
                        "fields": {
                            "summary": "Dreamus invoice",
                            "status": {"name": "Open"},
                            "priority": {"name": "Medium"},
                            "reporter": {"displayName": "Rina Reporter"},
                        },
                    }
                ]
            }

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_roi_ticket_from_slack(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219143",
            message_text="Create a task for bd ops to send Dreamus invoice",
            customer="Dreamus",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["existing_ticket"]["issue_key"], "ROI-555")
        self.assertEqual(len(calls), 1)
        self.assertEqual(audit_calls[0][0], "roi_ticket_reused")

    def test_append_ps_wee_ticket_update_posts_structured_comment_only(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {"id": "comment-790"}

        self.module._request_json = fake_request
        self.module._slack_users = lambda: [
            {
                "id": "U03P4FU4CHG",
                "name": "damba",
                "real_name": "Damba CSE",
                "profile": {"email": "damba@staffany.com", "real_name": "Damba CSE", "display_name": "Damba"},
            }
        ]
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.append_ps_wee_ticket_update(
            issue_key="PCO-789",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
            update_summary="PS confirmed impact and affected date range.",
            updated_fields={"impact": "Payroll blocked", "affected date range": "May payroll"},
            evidence_links=["https://example.com/screenshot"],
            slack_poster_name="Damba CSE",
            slack_user_email="damba@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        body = calls[0][2]["body"]
        self.assertIn("PS WEE Slack ticket update:", body)
        self.assertIn("Source Slack thread: https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579", body)
        self.assertIn("Slack poster: Damba CSE <@U03P4FU4CHG> damba@staffany.com", body)
        self.assertIn("- impact: Payroll blocked", body)
        self.assertIn("- affected date range: May payroll", body)
        self.assertIn("- https://example.com/screenshot", body)
        self.assertFalse(calls[0][2]["public"])
        self.assertEqual(audit_calls[0][0], "ticket_update_synced")
        self.assertEqual(audit_calls[0][1]["source_thread_url"], "https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579")

    def test_mark_ps_wee_ticket_ready_comments_and_removes_needs_info_label(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            if path.endswith("/comment"):
                return {"id": "comment-791"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.mark_ps_wee_ticket_ready(
            issue_key="PCO-789",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
            ready_summary="Customer, issue, impact, scope, and outcome are now complete.",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("PS WEE ticket ready for triage.", calls[0][2]["body"])
        self.assertEqual(calls[1][1], "/rest/api/3/issue/PCO-789")
        self.assertEqual(calls[1][2]["update"]["labels"], [{"remove": "needs-info"}])
        self.assertTrue(result["answer"]["ready_for_triage"])
        self.assertEqual(audit_calls[0][0], "ticket_ready")
        self.assertEqual(audit_calls[0][1]["issue_key"], "PCO-789")

    def test_ps_wee_blocked_path_posts_central_audit_when_thread_is_present(self):
        audit_calls = []
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.append_ps_wee_ticket_update(
            issue_key="PCO-789",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
            update_summary="",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(audit_calls[0][0], "blocked")
        self.assertEqual(audit_calls[0][1]["issue_key"], "PCO-789")
        self.assertIn("meaningful update", audit_calls[0][1]["blocked_reason"])

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

    def test_thin_poc_slack_sender_mention_drafts_without_email_prompt(self):
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
                    "id": "U6E68280P",
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

            result = self.module.draft_pco_task(
                slack_user_email="<@U6E68280P>",
                customer="Rock Productions",
                summary="Follow up on PSM home page and What's New",
                due_date="2026-07-15",
            )

        self.assertEqual(result["confidence"], "verified")
        draft = result["answer"]["draft"]
        self.assertEqual(result["scope"]["caller"], "kaiyi@staffany.com")
        self.assertEqual(result["scope"]["ps_team"], "Kai Yi")
        self.assertEqual(draft["owner_jira_account_id"], "acct-kaiyi")
        self.assertEqual(draft["ps_team"], "Kai Yi")

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

    def test_create_blocks_past_due_date_before_jira_write(self):
        calls = []
        with patch.dict(
            os.environ,
            {
                "PSM_OPS_TODAY": "2026-05-14",
                "PSM_OPS_JIRA_MODE": "thin_poc",
            },
            clear=False,
        ):
            def fake_request(method, path, body=None):
                calls.append((method, path, deepcopy(body)))
                return {"issueKey": "PCO-999"}

            self.module._request_json = fake_request

            result = self.module.create_approved_pco_task(
                {
                    "customer": "Rock Productions",
                    "summary": "Follow up with product",
                    "due_date": "2025-07-15",
                    "request_type_id": "81",
                },
                "create",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("before today", result["answer"]["message"])
        self.assertEqual(calls, [])

    def test_today_date_rejects_invalid_timezone(self):
        with patch.dict(os.environ, {"PSM_OPS_TODAY": "", "PSM_OPS_TIMEZONE": "Not/AZone"}, clear=False):
            with self.assertRaises(self.module.JiraError) as raised:
                self.module._today_date()

        self.assertIn("PSM_OPS_TIMEZONE", str(raised.exception))

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
