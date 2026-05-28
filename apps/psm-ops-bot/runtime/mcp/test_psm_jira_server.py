from __future__ import annotations

import json
import os
import tempfile
import unittest
import urllib.parse
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
                "PSM_OPS_TODAY": "2026-05-13",
                "PSM_OPS_ACCESS_POLICY_PATH": str(policy_path),
                "PSM_OPS_JIRA_SERVICE_DESK_ID": "10",
                "PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION": "101",
                "PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK": "102",
                "PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE": "103",
                "PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE": "104",
                "PSM_OPS_JIRA_REQUEST_TYPE_PS_FOLLOW_UP": "123",
                "PSM_OPS_JIRA_REQUEST_TYPE_CS_FOLLOW_UP": "124",
                "PSM_OPS_JIRA_REQUEST_TYPE_ADHOC_OPS": "118",
                "PSM_OPS_JIRA_REQUEST_TYPE_REV_CROSS_SELL": "120",
                "PSM_OPS_JIRA_REQUEST_TYPE_PDT_DISCOVERY": "125",
                "PSM_OPS_JIRA_REQUEST_TYPE_MKT_CLUBANY": "126",
                "PSM_OPS_JIRA_REQUEST_TYPE_FEEDBACK": "122",
                "PSM_OPS_JIRA_REQUEST_TYPE_PHOTO_FOLLOW_UP": "127",
                "PSM_OPS_AA_CHANNEL_ID": "C0B5H2YE5T2",
                "PSM_OPS_JIRA_FIELD_CREATOR": "customfield_10914",
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
                "PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS": "customfield_20100",
                "PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY": "customfield_20102",
                "PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS": "customfield_20103",
                "PSM_OPS_ROI_JIRA_FIELD_REQUESTER": "customfield_20104",
                "PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL": "customfield_20105",
                "PSM_OPS_ROI_JIRA_FIELD_PRIORITY": "customfield_20106",
                "PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": "",
                "ANTHROPIC_API_KEY": "",
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
            {"fieldId": "customfield_20100", "name": "StaffAny Organization", "required": False},
            {
                "fieldId": "customfield_20102",
                "name": "Request category",
                "required": True,
                "validValues": [
                    {"value": "11967", "label": "BD Ops"},
                    {"value": "11968", "label": "NYSS"},
                    {"value": "11969", "label": "RevOps"},
                    {"value": "11970", "label": "ROI"},
                    {"value": "11971", "label": "Billing / invoice"},
                ],
            },
            {"fieldId": "customfield_20103", "name": "Source links", "required": True},
            {"fieldId": "customfield_20104", "name": "Requester", "required": True},
            {"fieldId": "customfield_20105", "name": "Original channel", "required": False},
            {
                "fieldId": "customfield_20106",
                "name": "Priority",
                "required": False,
                "validValues": [{"value": "12001", "label": "Medium"}, {"value": "12002", "label": "High"}],
            },
            {"fieldId": "customfield_20107", "name": "Urgency Impact", "required": False},
        ]
        for field_name in extra_required or []:
            fields.append({"fieldId": f"customfield_extra_{len(fields)}", "name": field_name, "required": True})
        return fields

    def test_roi_urgent_field_defaults_to_no_when_required(self):
        field = {
            "fieldId": "customfield_10833",
            "name": "Urgent?",
            "required": True,
            "validValues": [{"value": "11975", "label": "Yes"}, {"value": "11976", "label": "No"}],
        }

        self.assertEqual(self.module._roi_default_priority_for_field(field), "No")
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

    def test_search_pco_tickets_falls_back_to_keyword_match_when_slack_permalink_misses(self):
        calls = []

        def fake_request(method, path, body=None):
            self.assertEqual(method, "GET")
            jql = urllib.parse.parse_qs(urllib.parse.urlparse(path).query).get("jql", [""])[0]
            calls.append(jql)
            if "text ~ \"salaried\"" in jql and "text ~ \"proration\"" in jql:
                return {
                    "issues": [
                        {
                            "key": "PCO-78",
                            "fields": {
                                "summary": "Salaried Employee  Proration Setup",
                                "status": {"name": "Open"},
                                "priority": {"name": "Medium"},
                                "assignee": {"displayName": "Josica"},
                                "customfield_10876": {"value": "Josica"},
                                "duedate": None,
                                "updated": "2026-05-16T00:00:00.000+0000",
                                "issuetype": {"name": "Task"},
                                "description": "Raw description must never be exposed.",
                                "comment": {"comments": [{"body": "Raw comment"}]},
                            },
                        }
                    ]
                }
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.search_pco_tickets(
            query="Munchi salaried staff proration payroll follow-up",
            slack_thread_url="https://staffany.slack.com/archives/C09139W008K/p1778895345394969?thread_ts=1778146948.007189&cid=C09139W008K",
            customer="Munchi Pancakes",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["resolution"], "auto_match")
        self.assertEqual(result["answer"]["best_match"]["issue_key"], "PCO-78")
        self.assertTrue(any("1778895345394969" in call for call in calls))
        self.assertTrue(any("salaried" in call and "proration" in call for call in calls))
        self.assertEqual(
            set(result["answer"]["best_match"].keys()),
            {
                "issue_key",
                "url",
                "summary",
                "status",
                "request_type",
                "ps_team",
                "due_date",
                "updated",
                "match_score",
                "match_reasons",
            },
        )
        self.assertNotIn("description", result["answer"]["best_match"])
        self.assertNotIn("comment", result["answer"]["best_match"])
        self.assertNotIn("assignee", result["answer"]["best_match"])
        self.assertNotIn("priority", result["answer"]["best_match"])
        self.assertNotIn("reminder_at", result["answer"]["best_match"])

    def test_search_pco_tickets_ambiguous_broad_match_returns_needs_check(self):
        def fake_request(method, path, body=None):
            self.assertEqual(method, "GET")
            jql = urllib.parse.parse_qs(urllib.parse.urlparse(path).query).get("jql", [""])[0]
            if "text ~ \"salaried\"" in jql and "text ~ \"proration\"" in jql:
                return {
                    "issues": [
                        {
                            "key": "PCO-78",
                            "fields": {
                                "summary": "Salaried Employee Proration Setup",
                                "status": {"name": "Open"},
                                "priority": {"name": "Medium"},
                                "assignee": {"displayName": "Josica"},
                                "customfield_10876": {"value": "Josica"},
                                "duedate": None,
                                "updated": "2026-05-16T00:00:00.000+0000",
                                "issuetype": {"name": "Task"},
                            },
                        },
                        {
                            "key": "PCO-179",
                            "fields": {
                                "summary": "Salaried proration follow-up",
                                "status": {"name": "Open"},
                                "priority": {"name": "Medium"},
                                "assignee": {"displayName": "Kai Yi"},
                                "customfield_10876": {"value": "Kai Yi"},
                                "duedate": None,
                                "updated": "2026-05-15T00:00:00.000+0000",
                                "issuetype": {"name": "Task"},
                            },
                        },
                    ]
                }
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.search_pco_tickets(query="salaried proration", customer="Munchi Pancakes")

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["resolution"], "choose_candidate")
        self.assertEqual([issue["issue_key"] for issue in result["answer"]["matches"]], ["PCO-78", "PCO-179"])

    def test_search_pco_tickets_customer_hint_does_not_filter_out_manual_ticket(self):
        calls = []

        def fake_request(method, path, body=None):
            self.assertEqual(method, "GET")
            jql = urllib.parse.parse_qs(urllib.parse.urlparse(path).query).get("jql", [""])[0]
            calls.append(jql)
            if "text ~ \"salaried\"" in jql and "text ~ \"proration\"" in jql:
                return {
                    "issues": [
                        {
                            "key": "PCO-78",
                            "fields": {
                                "summary": "Salaried Employee Proration Setup",
                                "status": {"name": "Open"},
                                "priority": {"name": "Medium"},
                                "assignee": {"displayName": "Josica"},
                                "customfield_10876": {"value": "Josica"},
                                "duedate": None,
                                "updated": "2026-05-16T00:00:00.000+0000",
                                "issuetype": {"name": "Task"},
                            },
                        }
                    ]
                }
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.search_pco_tickets(query="salaried proration", customer="Munchi Pancakes")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["best_match"]["issue_key"], "PCO-78")
        self.assertFalse(any("Munchi" in call for call in calls), "customer hint must not become a hard JQL filter")

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

        self.assertEqual(values["customfield_10876"], {"id": "12025"})

    def test_ps_team_request_value_matches_full_display_name_to_first_name_option(self):
        """`ps_team="Jason Kanggara"` must still match the `Jason` option (token match)."""
        self.module._ps_team_valid_values = lambda request_type_id="": [
            {"value": "12005", "label": "Ega"},
            {"value": "12016", "label": "Jason"},
            {"value": "12017", "label": "Kai Yi"},
        ]
        self.assertEqual(
            self.module._ps_team_request_value("Jason Kanggara", "123"),
            {"id": "12016"},
        )
        # Two-word option should also match a longer display name (substring match).
        self.assertEqual(
            self.module._ps_team_request_value("Kai Yi Lee", "123"),
            {"id": "12017"},
        )
        # Unknown name still returns None so the field is omitted, not sent as garbage.
        self.assertIsNone(self.module._ps_team_request_value("Totally Unknown", "123"))

    def test_ps_team_request_value_prefers_more_specific_match_regardless_of_option_order(self):
        """If both a single-token `Kai` and a multi-word `Kai Yi` exist, target `Kai Yi Lee`
        must resolve to `Kai Yi` even when Jira returns `Kai` first."""
        self.module._ps_team_valid_values = lambda request_type_id="": [
            {"value": "12100", "label": "Kai"},
            {"value": "12017", "label": "Kai Yi"},
        ]
        self.assertEqual(
            self.module._ps_team_request_value("Kai Yi Lee", "123"),
            {"id": "12017"},
        )

    def test_resolve_assets_object_id_returns_numeric_id_on_exact_match(self):
        captured_queries = []

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                captured_queries.append(body.get("qlQuery"))
                return {"values": [{"id": "566", "objectKey": "HC-566", "label": "21 Supermarket"}]}
            return {}

        self.module._request_json = fake_request
        # The resolver returns the numeric ``id`` (used in the composite write key) not the
        # human-readable ``objectKey`` — the CMDB field's write contract needs the former.
        self.assertEqual(self.module._resolve_assets_object_id("21 Supermarket"), "566")
        self.assertEqual(captured_queries, ['Name = "21 Supermarket"'])

    def test_resolve_assets_object_id_returns_none_on_zero_or_ambiguous_matches(self):
        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                # Every strategy returns no usable match: empty for the first lookup,
                # ambiguous (>1) for the second.
                if "Bistro" in body["qlQuery"]:
                    return {"values": []}
                return {"values": [{"id": "1"}, {"id": "2"}]}
            return {}

        self.module._request_json = fake_request
        self.assertIsNone(self.module._resolve_assets_object_id("Bistro Bamboo"))
        self.assertIsNone(self.module._resolve_assets_object_id("Ambiguous Co"))

    def test_resolve_assets_object_id_caches_negative_lookups(self):
        call_count = {"aql": 0}

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                call_count["aql"] += 1
                return {"values": []}
            return {}

        self.module._request_json = fake_request
        # First call fires multiple AQL queries (exact, then like fallback) because none match.
        self.assertIsNone(self.module._resolve_assets_object_id("Totally Unknown"))
        first_call_count = call_count["aql"]
        self.assertGreater(first_call_count, 0)
        # Second call must be served from cache — no additional AQL.
        self.assertIsNone(self.module._resolve_assets_object_id("Totally Unknown"))
        self.assertEqual(call_count["aql"], first_call_count, "negative result should be cached")

    def test_resolve_assets_object_id_escapes_embedded_quotes(self):
        captured = []

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                captured.append(body.get("qlQuery"))
                return {"values": []}
            return {}

        self.module._request_json = fake_request
        self.module._resolve_assets_object_id('A "Tricky" Co')
        # First strategy is exact match; embedded " must be escaped to keep the AQL literal well-formed.
        self.assertEqual(captured[0], 'Name = "A \\"Tricky\\" Co"')

    def test_resolve_assets_object_id_falls_back_to_legal_suffix_stripped_form(self):
        """C360-canonicalised names ("21 Supermarket Pte Ltd") rarely match the Assets
        display name verbatim ("21 Supermarket"). Stripping the legal suffix and retrying
        the exact match should resolve cleanly."""
        queries: list[str] = []

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                q = body["qlQuery"]
                queries.append(q)
                if q == 'Name = "21 Supermarket"':
                    return {"values": [{"id": "566", "objectKey": "HC-566", "label": "21 Supermarket"}]}
                return {"values": []}
            return {}

        self.module._request_json = fake_request
        self.assertEqual(
            self.module._resolve_assets_object_id("21 Supermarket Pte Ltd"),
            "566",
        )
        # Strategy order: exact (miss) -> legal-suffix-stripped exact (hit).
        self.assertEqual(queries[0], 'Name = "21 Supermarket Pte Ltd"')
        self.assertEqual(queries[1], 'Name = "21 Supermarket"')
        self.assertEqual(len(queries), 2, "should stop after the first successful strategy")

    def test_resolve_assets_object_id_falls_back_to_like_substring_match(self):
        """If exact and legal-stripped exact miss, a single substring match should resolve."""
        queries: list[str] = []

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                q = body["qlQuery"]
                queries.append(q)
                if q.startswith("Name like"):
                    return {"values": [{"id": "99", "objectKey": "HC-99", "label": "Acme HQ"}]}
                return {"values": []}
            return {}

        self.module._request_json = fake_request
        self.assertEqual(self.module._resolve_assets_object_id("Acme HQ"), "99")
        self.assertTrue(any(q.startswith("Name like") for q in queries))

    def test_resolve_assets_object_id_does_not_cache_transient_failures(self):
        """A transient Assets/AQL outage must not turn into a process-lifetime false negative.
        After the first call sees only JiraError responses, a follow-up call once Jira
        recovers should re-hit the API and return the real answer."""
        state = {"jira_up": False}
        aql_calls = {"n": 0}

        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                if not state["jira_up"]:
                    raise self.module.JiraError("Jira API unavailable: timed out")
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                aql_calls["n"] += 1
                if not state["jira_up"]:
                    raise self.module.JiraError("Jira API unavailable: timed out")
                return {"values": [{"id": "7", "objectKey": "HC-7", "label": "Recovered Co"}]}
            return {}

        self.module._request_json = fake_request

        # First call during the outage: every strategy hits JiraError → no resolution,
        # and no cache write because all queries failed transiently.
        self.assertIsNone(self.module._resolve_assets_object_id("Recovered Co"))

        # Jira recovers. The next call must re-hit AQL rather than returning a cached None.
        state["jira_up"] = True
        aql_before = aql_calls["n"]
        self.assertEqual(self.module._resolve_assets_object_id("Recovered Co"), "7")
        self.assertGreater(aql_calls["n"], aql_before, "transient failure must not be cached")

    def test_resolve_assets_object_id_rejects_ambiguous_like_match(self):
        """A substring `like` query that returns more than one Assets object should be
        treated as ambiguous and resolve to None — better to omit than guess wrong."""
        def fake_request(method, path, body=None):
            if method == "GET" and path == "/rest/servicedeskapi/assets/workspace":
                return {"values": [{"workspaceId": "ws-1"}]}
            if method == "POST" and "/v1/object/aql" in path:
                q = body["qlQuery"]
                if q.startswith("Name like"):
                    return {"values": [{"id": "1"}, {"id": "2"}]}
                return {"values": []}
            return {}

        self.module._request_json = fake_request
        self.assertIsNone(self.module._resolve_assets_object_id("Generic"))

    def test_create_pco_task_warns_when_staffany_org_does_not_resolve(self):
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
                if path == "/rest/servicedeskapi/request":
                    return {"issueKey": "PCO-901", "requestTypeId": "81"}
                if path.endswith("/comment"):
                    return {"id": "c-901"}
                return {}

            self.module._request_json = fake_request
            self.module._resolve_assets_object_id = lambda name: None  # nothing resolves

            result = self.module.create_approved_pco_task(
                {
                    "customer": "Bistro Bamboo",
                    "summary": "Confirm payroll readiness",
                    "due_date": "2026-05-15",
                    "priority": "High",
                    "action_type": "Customer success",
                    "request_type_id": "81",
                    "source_links": [],
                    "staffany_orgs": ["Bistro Bamboo"],
                    "owner_psm": "Ada PSM",
                    "owner_jira_account_id": "acct-123",
                    "mode": "thin_poc",
                },
                "create",
            )

        self.assertEqual(result["confidence"], "verified")
        # The org field must not be sent at all when nothing resolved — no retry needed.
        request_values = calls[0][2]["requestFieldValues"]
        self.assertNotIn("customfield_10667", request_values)
        # Warning must name the unresolved org so triage knows which one to assign manually.
        warnings = result["answer"]["warnings"]
        self.assertTrue(any("Bistro Bamboo" in w and "no Jira Assets object matched" in w for w in warnings))

    def test_ps_team_issue_value_uses_matched_option_label_when_id_missing(self):
        """When the Jira option carries only `label` (no `value`/`id`), the issue value must
        be the **matched** label, not the raw input the caller passed in."""
        self.module._ps_team_valid_values = lambda request_type_id="": [
            {"label": "Jason"},
        ]
        self.assertEqual(
            self.module._ps_team_issue_value("Jason Kanggara"),
            {"value": "Jason"},
        )

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

    def test_link_pco_to_ker_uses_blocks_direction_for_pco_blocked_by_engineering(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_engineering_issue("PCO-123", "KER-2109")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[0][1], "/rest/api/3/issue/PCO-123?fields=issuelinks")
        self.assertEqual(calls[1][0], "POST")
        self.assertEqual(calls[1][1], "/rest/api/3/issueLink")
        self.assertEqual(calls[1][2]["type"], {"name": "Blocks"})
        self.assertEqual(calls[1][2]["outwardIssue"], {"key": "KER-2109"})
        self.assertEqual(calls[1][2]["inwardIssue"], {"key": "PCO-123"})
        self.assertEqual(result["answer"]["relationship"], "PCO-123 is blocked by KER-2109")
        self.assertFalse(result["answer"]["already_exists"])
        self.assertIn("no raw Jira issue content", result["caveat"])

    def test_link_pco_to_sche_accepts_relates_fallback(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_engineering_issue("PCO-123", "SCHE-19631", "relates to")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[1][2]["type"], {"name": "Relates"})
        self.assertEqual(calls[1][2]["outwardIssue"], {"key": "PCO-123"})
        self.assertEqual(calls[1][2]["inwardIssue"], {"key": "SCHE-19631"})

    def test_link_pco_to_engineering_issue_reports_existing_blocks_link(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET":
                return {
                    "fields": {
                        "issuelinks": [
                            {
                                "type": {"name": "Blocks"},
                                "inwardIssue": {"key": "KER-2109"},
                            }
                        ]
                    }
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_engineering_issue("PCO-123", "KER-2109")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["already_exists"])
        self.assertEqual(len(calls), 1)
        self.assertIn("already existed", result["caveat"])

    def test_link_pco_to_engineering_issue_reports_existing_blocks_link_from_outward_issue(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET":
                return {
                    "fields": {
                        "issuelinks": [
                            {
                                "type": {"name": "Blocks"},
                                "outwardIssue": {"key": "KER-2109"},
                            }
                        ]
                    }
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_engineering_issue("PCO-123", "KER-2109")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["already_exists"])
        self.assertEqual(len(calls), 1)
        self.assertIn("already existed", result["caveat"])

    def test_link_pco_to_engineering_issue_rejects_non_pco_source(self):
        result = self.module.link_pco_to_engineering_issue("KER-2109", "SCHE-19631")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("PCO-123", result["caveat"])

    def test_link_pco_to_engineering_issue_rejects_non_engineering_target(self):
        result = self.module.link_pco_to_engineering_issue("PCO-123", "PCO-456")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("KER-123 or SCHE-123", result["caveat"])

    def test_link_pco_to_pco_issue_creates_relates_link(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_pco_issue("PCO-200", "PCO-150")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[0][1], "/rest/api/3/issue/PCO-200?fields=issuelinks")
        self.assertEqual(calls[1][0], "POST")
        self.assertEqual(calls[1][1], "/rest/api/3/issueLink")
        self.assertEqual(calls[1][2]["type"], {"name": "Relates"})
        self.assertEqual(calls[1][2]["outwardIssue"], {"key": "PCO-200"})
        self.assertEqual(calls[1][2]["inwardIssue"], {"key": "PCO-150"})
        self.assertEqual(result["answer"]["link_type"], "Relates")
        self.assertEqual(result["answer"]["relationship"], "PCO-200 relates to PCO-150")
        self.assertFalse(result["answer"]["already_exists"])

    def test_link_pco_to_pco_issue_short_circuits_when_link_already_exists(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET":
                return {
                    "fields": {
                        "issuelinks": [
                            {
                                "type": {"name": "Relates"},
                                "outwardIssue": {"key": "PCO-150"},
                            }
                        ]
                    }
                }
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_pco_issue("PCO-200", "PCO-150")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["already_exists"])
        self.assertEqual(len(calls), 1)
        self.assertIn("already existed", result["caveat"])

    def test_link_pco_to_pco_issue_treats_jira_duplicate_error_as_existing(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "POST":
                raise self.module.JiraError("Jira API failed: HTTP 400 issue link already exists")
            return {}

        self.module._request_json = fake_request

        result = self.module.link_pco_to_pco_issue("PCO-200", "PCO-150")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["already_exists"])

    def test_link_pco_to_pco_issue_rejects_non_pco_source(self):
        result = self.module.link_pco_to_pco_issue("KER-2109", "PCO-150")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("source_issue_key", result["caveat"])

    def test_link_pco_to_pco_issue_rejects_non_pco_target(self):
        result = self.module.link_pco_to_pco_issue("PCO-200", "SCHE-19631")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("target_issue_key", result["caveat"])

    def test_link_pco_to_pco_issue_rejects_self_link(self):
        result = self.module.link_pco_to_pco_issue("PCO-200", "PCO-200")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("must differ", result["caveat"])

    def test_find_engineering_issue_searches_ker_with_safe_fields_and_compact_variant(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            params = urllib.parse.parse_qs(path.split("?", 1)[1])
            self.assertEqual(params["fields"], ["summary,status,issuetype,updated"])
            self.assertEqual(params["maxResults"], ["5"])
            jql = params["jql"][0]
            self.assertIn('project in ("KER")', jql)
            self.assertIn('text ~ "home page"', jql)
            self.assertIn('text ~ "homepage"', jql)
            return {
                "issues": [
                    {
                        "key": "KER-2117",
                        "fields": {
                            "summary": "StaffAny Homepage",
                            "status": {"name": "Backlog"},
                            "issuetype": {"name": "Feature"},
                            "updated": "2026-05-15T06:00:00.000+0800",
                            "description": "must not be returned",
                            "comment": {"comments": [{"body": "must not be returned"}]},
                            "attachment": [{"filename": "must-not-return.png"}],
                        },
                    }
                ]
            }

        self.module._request_json = fake_request

        result = self.module.find_engineering_issue("home page")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["source"], "Jira Engineering")
        self.assertEqual(result["answer"]["match_count"], 1)
        match = result["answer"]["matches"][0]
        self.assertEqual(
            set(match.keys()),
            {"key", "url", "summary", "status", "issue_type", "updated"},
        )
        self.assertEqual(match["key"], "KER-2117")
        self.assertEqual(match["summary"], "StaffAny Homepage")
        self.assertNotIn("description", match)
        self.assertNotIn("comment", match)
        self.assertNotIn("attachment", match)
        self.assertIn("no descriptions", result["caveat"])

    def test_find_engineering_issue_rejects_non_allowlisted_project(self):
        result = self.module.find_engineering_issue("homepage", ["PCO"])

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("KER, SCHE", result["caveat"])

    def test_find_engineering_issue_caps_results_and_allows_sche(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            params = urllib.parse.parse_qs(path.split("?", 1)[1])
            self.assertEqual(params["maxResults"], ["10"])
            self.assertIn('project in ("KER", "SCHE")', params["jql"][0])
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.find_engineering_issue("release shipment", ["KER", "SCHE"], 99)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["max_results"], 10)

    def test_find_engineering_issue_exact_sche_key_uses_key_lookup_and_auto_scope(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            params = urllib.parse.parse_qs(path.split("?", 1)[1])
            self.assertEqual(params["jql"], ["key = SCHE-19631"])
            return {"issues": []}

        self.module._request_json = fake_request

        result = self.module.find_engineering_issue("SCHE-19631")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["project_keys"], ["SCHE"])

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
            "Fei Siong - Payroll readiness unclear",
        )
        self.assertEqual(calls[2][1], "/rest/servicedeskapi/request/PCO-789/comment")
        self.assertIn("Source Slack thread: https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579", calls[2][2]["body"])
        self.assertIn("Known details: PS asked to raise this first.", calls[2][2]["body"])
        # PS WEE intakes never carry the `needs-info` label.
        label_calls = [c for c in calls if c[1] == "/rest/api/3/issue/PCO-789" and c[2].get("update", {}).get("labels")]
        self.assertEqual(label_calls, [])
        self.assertIn("Created first so this won't be missed", result["answer"]["slack_reply"])
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-789|PCO-789>", result["answer"]["slack_reply"])
        self.assertEqual(audit_calls[0][0], "ticket_created")
        self.assertEqual(audit_calls[0][1]["source_thread_url"], "https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579")
        self.assertEqual(audit_calls[0][1]["issue_key"], "PCO-789")

    def _mock_creator_options(self, request_type_id=""):
        return [
            {"value": "creator-josica", "label": "Josica"},
            {"value": "creator-jason", "label": "Jason"},
            {"value": "creator-ega", "label": "Ega"},
            {"value": "creator-may", "label": "May"},
        ]

    def test_ps_wee_intake_in_aa_channel_defaults_to_feedback_request_type(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-901", "requestTypeId": "122"}
            if path.endswith("/comment"):
                return {"id": "comment-901"}
            return {}

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779100000000000",
            customer="Kopi Janji",
            issue_summary="PSM came back from AA event with selfie",
            creator_slack_user_email="josica@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_call[2]["requestTypeId"], "122")
        self.assertEqual(result["scope"]["request_type_key"], "feedback")
        self.assertEqual(result["scope"]["event"], "AA")

    def test_ps_wee_intake_in_aa_channel_routes_each_new_request_type(self):
        cases = [
            ("ps_follow_up", "123", "Josica", "Josica"),
            ("cs_follow_up", "124", "Ega", "Ega"),
            ("adhoc_ops", "118", "Josica", "PS Ops"),
            ("rev_cross_sell", "120", "Jason", "Jason"),
            ("pdt_discovery", "125", "May", "May"),
            ("mkt_clubany", "126", "Ega", "Ega"),
            ("photo_follow_up", "127", "Jason", "Jason"),
        ]
        for request_type_key, expected_id, creator_name, expected_team in cases:
            with self.subTest(request_type_key=request_type_key):
                calls = []

                def fake_request(method, path, body=None, _expected_id=expected_id):
                    calls.append((method, path, deepcopy(body)))
                    if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                        return {"issues": []}
                    if path == "/rest/servicedeskapi/request":
                        return {"issueKey": f"PCO-{_expected_id}", "requestTypeId": _expected_id}
                    if path.endswith("/comment"):
                        return {"id": "comment-x"}
                    return {}

                self.module._request_json = fake_request
                self.module._creator_valid_values = self._mock_creator_options
                self.module._ps_team_valid_values = lambda request_type_id="", _name=creator_name, _team=expected_team: [
                    {"value": f"opt-{_team.lower().replace(' ', '-')}", "label": _team},
                    {"value": f"opt-{_name.lower()}", "label": _name},
                ]
                self.module._update_issue_labels = lambda *args, **kwargs: None
                self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}
                self.module._caller = lambda email, require_jira_account=True, require_ps_team=False, _name=creator_name: {
                    "slack_email": email,
                    "jira_email": email,
                    "jira_account_id": "",
                    "display_name": _name,
                    "ps_team": "",
                    "ps_team_option_id": "",
                }

                result = self.module.create_ps_wee_intake_ticket(
                    slack_user_email=f"{creator_name.lower()}@staffany.com",
                    slack_thread_url=f"https://staffany.slack.com/archives/C0B5H2YE5T2/p177910{expected_id}000000",
                    customer="Kopi Janji",
                    issue_summary=f"event AA {request_type_key} follow-up",
                    request_type_key=request_type_key,
                    creator_slack_user_email=f"{creator_name.lower()}@staffany.com",
                )

                self.assertEqual(result["confidence"], "verified", msg=result)
                create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
                self.assertEqual(create_call[2]["requestTypeId"], expected_id)
                expected_team_value = f"opt-{expected_team.lower().replace(' ', '-')}"
                self.assertEqual(
                    create_call[2]["requestFieldValues"].get("customfield_10876"),
                    {"id": expected_team_value},
                    msg=f"PS Team auto-route failed for {request_type_key}",
                )

    def test_ps_wee_intake_in_aa_channel_adds_label(self):
        label_calls = []

        def fake_request(method, path, body=None):
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-960", "requestTypeId": "123"}
            if path.endswith("/comment"):
                return {"id": "comment-960"}
            return {}

        def fake_labels(issue_key, add=None, remove=None):
            label_calls.append((issue_key, list(add or []), list(remove or [])))

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = fake_labels
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779100000000010",
            customer="Kopi Janji",
            issue_summary="follow up deep dive",
            request_type_key="ps_follow_up",
            creator_slack_user_email="josica@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        labels_added = [labels for _, labels, _ in label_calls]
        self.assertTrue(any("AA-SG-2026" in batch for batch in labels_added))

    def test_ps_wee_intake_in_aa_channel_uploads_selfies_to_drive_and_jira(self):
        attachment_calls = []
        drive_calls = []

        def fake_request(method, path, body=None):
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-905", "requestTypeId": "122"}
            if path.endswith("/comment"):
                return {"id": "comment-905"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                },
                                {
                                    "id": "F-pdf",
                                    "name": "deck.pdf",
                                    "mimetype": "application/pdf",
                                    "url_private": "https://files.slack.com/deck.pdf",
                                },
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_download(url):
            return b"binary-image-data"

        def fake_attach(issue_key, files):
            attachment_calls.append((issue_key, deepcopy(files)))
            return [{"id": "att-1", "filename": files[0]["name"]}]

        def fake_drive_upload_detailed(images, company, pic):
            drive_calls.append({"images": list(images), "company": company, "pic": pic})
            return {
                "uploaded": [
                    {
                        "drive_file_id": "drive-1",
                        "name": "kopi-janji_andre.jpg",
                        "web_view_link": "https://drive/x",
                    }
                ],
                "drive_status": "ok",
                "drive_reason": "",
                "failure_count": 0,
                "last_error": "",
            }

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = fake_download
        self.module._attach_image_files_to_issue = fake_attach
        self.module.upload_aa_selfies_detailed = fake_drive_upload_detailed
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779160186779359",
            customer="Kopi Janji",
            issue_summary="met Andre at AA",
            request_type_key="ps_follow_up",
            creator_slack_user_email="josica@staffany.com",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(len(attachment_calls), 1)
        self.assertEqual(attachment_calls[0][0], "PCO-905")
        self.assertEqual([f["name"] for f in attachment_calls[0][1]], ["selfie.jpg"])
        self.assertEqual(len(drive_calls), 1)
        only_payload = drive_calls[0]
        self.assertEqual(only_payload["company"], "Kopi Janji")
        self.assertEqual(only_payload["pic"], "Andre")
        self.assertEqual([entry["name"] for entry in only_payload["images"]], ["selfie.jpg"])
        self.assertEqual(len(result["answer"]["attached_images"]), 1)
        self.assertEqual(len(result["answer"]["drive_selfies"]), 1)
        self.assertEqual(result["answer"]["drive_status"], "ok")
        self.assertIn("Saved 1 selfie(s) to Drive.", result["answer"]["slack_reply"])
        self.assertIn("Attached 1 image(s) to Jira.", result["answer"]["slack_reply"])

    def test_ps_wee_intake_in_aa_channel_surfaces_drive_failure_without_blocking(self):
        attachment_calls = []

        def fake_request(method, path, body=None):
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-918", "requestTypeId": "122"}
            if path.endswith("/comment"):
                return {"id": "comment-918"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_attach(issue_key, files):
            attachment_calls.append((issue_key, deepcopy(files)))
            return [{"id": "att-9", "filename": files[0]["name"]}]

        def fake_drive_upload_detailed(images, company, pic):
            return {
                "uploaded": [],
                "drive_status": "upload_failed",
                "drive_reason": "Drive upload failed: 401 Invalid Credentials",
                "failure_count": 1,
                "last_error": "Drive upload failed: 401 Invalid Credentials",
            }

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module._attach_image_files_to_issue = fake_attach
        self.module.upload_aa_selfies_detailed = fake_drive_upload_detailed
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779160186779359",
            customer="Kopi Janji",
            issue_summary="met Andre at AA",
            request_type_key="ps_follow_up",
            creator_slack_user_email="josica@staffany.com",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertEqual(result["answer"]["drive_status"], "upload_failed")
        self.assertEqual(
            result["answer"]["drive_reason"],
            "Drive upload failed: 401 Invalid Credentials",
        )
        self.assertEqual(len(result["answer"]["attached_images"]), 1)
        self.assertIn(
            "Drive selfie upload skipped: Drive upload failed: 401 Invalid Credentials",
            result["answer"]["slack_reply"],
        )
        self.assertIn("Attached 1 image(s) to Jira.", result["answer"]["slack_reply"])

    def test_ps_wee_intake_outside_aa_channel_attaches_images_to_jira_not_drive(self):
        attachment_calls = []

        def fake_request(method, path, body=None):
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-906", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-906"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "evidence.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/evidence.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_attach(issue_key, files):
            attachment_calls.append((issue_key, deepcopy(files)))
            return [{"id": "att-1", "filename": files[0]["name"]}]

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._attach_image_files_to_issue = fake_attach
        def _fail_drive_outside_aa(*_args, **_kwargs):
            raise AssertionError("Drive upload must not be called outside AA channel")
        self.module.upload_aa_selfies = _fail_drive_outside_aa
        self.module.upload_aa_selfies_detailed = _fail_drive_outside_aa
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1779160186779359",
            customer="Some Customer",
            issue_summary="regular intake",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(len(attachment_calls), 1)
        self.assertEqual(attachment_calls[0][0], "PCO-906")
        self.assertEqual(len(result["answer"]["attached_images"]), 1)
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertIn("Attached 1 image(s) from Slack.", result["answer"]["slack_reply"])
        self.assertNotIn("Drive", result["answer"]["slack_reply"])

    def test_ps_wee_intake_in_aa_channel_handles_slack_fetch_failure_without_blocking(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-907", "requestTypeId": "122"}
            if path.endswith("/comment"):
                return {"id": "comment-907"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                raise self.module.JiraError("Slack API failed: ratelimited")
            return {"members": []}

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779160186779359",
            customer="Kopi Janji",
            issue_summary="met Andre at AA",
            creator_slack_user_email="josica@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["attached_images"], [])
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertNotIn("Attached", result["answer"]["slack_reply"])
        self.assertNotIn("Drive", result["answer"]["slack_reply"])

    def test_attach_aa_selfie_to_thread_uploads_trigger_message_images_to_drive(self):
        slack_calls = []
        drive_calls = []

        def fake_slack_json(method, params):
            slack_calls.append((method, dict(params)))
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                },
                                {
                                    "id": "F-pdf",
                                    "name": "deck.pdf",
                                    "mimetype": "application/pdf",
                                    "url_private": "https://files.slack.com/deck.pdf",
                                },
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_download(url):
            return b"binary-image-data"

        def fake_drive_upload(images, company, pic):
            drive_calls.append({"images": list(images), "company": company, "pic": pic})
            return [
                {
                    "drive_file_id": "drive-1",
                    "name": "kopi-janji_andre__F-img.jpg",
                    "web_view_link": "https://drive/x",
                }
            ]

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = fake_download
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": fake_drive_upload(images, company, pic),
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: []

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["image_count"], 1)
        self.assertEqual(result["answer"]["saved_count"], 1)
        self.assertEqual(result["answer"]["drive_status"], "ok")
        self.assertEqual(len(result["answer"]["drive_selfies"]), 1)
        self.assertIn("Saved 1 selfie(s) to Drive.", result["caveat"])
        self.assertEqual(len(drive_calls), 1)
        self.assertEqual(drive_calls[0]["company"], "Kopi Janji")
        self.assertEqual(drive_calls[0]["pic"], "Andre")
        self.assertEqual([entry["name"] for entry in drive_calls[0]["images"]], ["selfie.jpg"])
        self.assertEqual(
            [entry["slack_file_id"] for entry in drive_calls[0]["images"]], ["F-img"]
        )
        self.assertEqual([call[0] for call in slack_calls], ["conversations.history"])

    def test_attach_aa_selfie_to_thread_uses_newest_thread_image_when_parent_permalink_passed(self):
        # Real-world: the Hermes gateway exposes the parent thread permalink
        # to the agent, not the reply's. When the agent forwards that parent
        # URL, the tool must still locate the new selfie by scanning the
        # thread for the most recent image attachment.
        parent_ts = "1779222669.095949"
        reply_ts = "1779222835.114159"
        slack_calls = []
        upload_inputs = []

        def fake_slack_json(method, params):
            slack_calls.append((method, dict(params)))
            if method == "conversations.history":
                # Parent message exists, ts matches request, but has no files.
                return {
                    "messages": [
                        {"ts": parent_ts, "text": "smoke test parent", "files": []}
                    ]
                }
            if method == "conversations.replies":
                return {
                    "messages": [
                        {"ts": parent_ts, "text": "smoke test parent"},
                        {
                            "ts": reply_ts,
                            "thread_ts": parent_ts,
                            "files": [
                                {
                                    "id": "F0B4F0WAVST",
                                    "name": "image.png",
                                    "mimetype": "image/png",
                                    "url_private": "https://files.slack.com/files-pri/T6BS929EZ-F0B4F0WAVST/image.png",
                                }
                            ],
                        },
                    ]
                }
            return {"members": []}

        def fake_drive_upload(images, company, pic):
            upload_inputs.append([entry["slack_file_id"] for entry in images])
            return [
                {
                    "drive_file_id": "drive-newest",
                    "name": "arabica-coffee_khairul__F0B4F0WAVST.png",
                    "web_view_link": "https://drive/x",
                }
            ]

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": fake_drive_upload(images, company, pic),
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: []

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url=f"https://staffany.slack.com/archives/C0B5H2YE5T2/p{parent_ts.replace('.', '')}",
            customer="Arabica Coffee",
            pic="Khairul",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["image_count"], 1)
        self.assertEqual(result["answer"]["saved_count"], 1)
        self.assertEqual(upload_inputs, [["F0B4F0WAVST"]])
        # Calls both APIs: history to try the supplied ts, then replies to
        # scan the thread when the parent has no files.
        self.assertEqual(
            [call[0] for call in slack_calls],
            ["conversations.history", "conversations.replies"],
        )

    def test_attach_aa_selfie_to_thread_falls_back_to_replies_for_thread_reply(self):
        slack_calls = []
        drive_calls = []
        reply_ts = "1779221847.895889"
        parent_ts = "1779221716.687319"

        def fake_slack_json(method, params):
            slack_calls.append((method, dict(params)))
            if method == "conversations.history":
                # Slack's conversations.history does not return thread replies;
                # it returns the next top-level message at or after `oldest`.
                # That message's ts will not match the reply permalink, which
                # is exactly the case that requires the conversations.replies
                # fallback.
                return {
                    "messages": [
                        {"ts": "1779225000.000100", "text": "some unrelated top-level message"}
                    ]
                }
            if method == "conversations.replies":
                return {
                    "messages": [
                        {"ts": parent_ts, "text": "thread parent"},
                        {
                            "ts": reply_ts,
                            "thread_ts": parent_ts,
                            "files": [
                                {
                                    "id": "F-reply-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        },
                        {"ts": "1779222000.000100", "text": "later reply, no files"},
                    ]
                }
            return {"members": []}

        def fake_drive_upload(images, company, pic):
            drive_calls.append({"images": list(images), "company": company, "pic": pic})
            return [
                {
                    "drive_file_id": "drive-reply",
                    "name": "andsoforth_bayu__F-reply-img.jpg",
                    "web_view_link": "https://drive/reply",
                }
            ]

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": fake_drive_upload(images, company, pic),
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: []

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url=f"https://staffany.slack.com/archives/C0B5H2YE5T2/p{reply_ts.replace('.', '')}",
            customer="Andsoforth",
            pic="Bayu",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["image_count"], 1)
        self.assertEqual(result["answer"]["saved_count"], 1)
        self.assertEqual(
            [entry["slack_file_id"] for entry in drive_calls[0]["images"]],
            ["F-reply-img"],
        )
        # First tries conversations.history, then falls back to
        # conversations.replies when the returned ts does not match.
        self.assertEqual(
            [call[0] for call in slack_calls],
            ["conversations.history", "conversations.replies"],
        )
        self.assertEqual(slack_calls[1][1]["ts"], reply_ts)

    def test_attach_aa_selfie_to_thread_returns_needs_check_when_slack_call_fails(self):
        def fake_slack_json(method, params):
            if method == "conversations.history":
                raise self.module.JiraError("Slack API failed: ratelimited")
            self.fail("Slack should not be called again after history failure")

        self.module._request_slack_json = fake_slack_json
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: self.fail(
            "Drive upload should not run when the Slack read failed"
        )
        self.module.aa_drive_configuration_status = lambda: ("ok", "")

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["image_count"], 0)
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertIn("Could not read the AA Slack message", result["caveat"])
        self.assertIn("ratelimited", result["caveat"])

    def test_attach_aa_selfie_to_thread_returns_needs_check_on_partial_ingest(self):
        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-ok",
                                    "name": "first.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/first.jpg",
                                },
                                {
                                    "id": "F-flaky",
                                    "name": "second.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/flaky.jpg",
                                },
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_download(url):
            if "flaky" in url:
                raise RuntimeError("transient Slack download failure")
            return b"binary-image-data"

        def fake_drive_upload(images, company, pic):
            return [
                {
                    "drive_file_id": f"drive-{entry['slack_file_id']}",
                    "name": entry["name"],
                    "web_view_link": "https://drive/x",
                }
                for entry in images
            ]

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = fake_download
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": fake_drive_upload(images, company, pic),
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: []

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["image_count"], 2)
        self.assertEqual(result["answer"]["downloaded_count"], 1)
        self.assertEqual(result["answer"]["saved_count"], 1)
        self.assertEqual(result["answer"]["download_failure_count"], 1)
        self.assertEqual(result["answer"]["drive_failure_count"], 0)
        self.assertIn("Partial AA selfie ingest", result["caveat"])

    def test_attach_aa_selfie_to_thread_blocks_outside_aa_channel(self):
        self.module._request_slack_json = lambda *_args, **_kwargs: self.fail(
            "Slack should not be called when blocking outside AA channel"
        )
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: self.fail(
            "Drive upload should not run outside AA channel"
        )

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1779213672422819",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Event AA channel", result["caveat"])

    def test_attach_aa_selfie_to_thread_reports_missing_token_status(self):
        self.module._request_slack_json = lambda *_args, **_kwargs: self.fail(
            "Slack should not be called when Drive is not configured"
        )
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: self.fail(
            "Drive upload should not run when token is missing"
        )
        self.module.aa_drive_configuration_status = lambda: (
            "missing_token",
            "Drive OAuth token file missing at /nope/drive-token.json.",
        )

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779213672422819",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["drive_status"], "missing_token")
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertIn("Drive OAuth token file missing", result["caveat"])

    def test_attach_aa_selfie_to_thread_returns_verified_when_message_has_no_images(self):
        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {"messages": [{"ts": params["oldest"], "text": "no images here"}]}
            return {"members": []}

        self.module._request_slack_json = fake_slack_json
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: self.fail(
            "Drive upload should not run when there are no images"
        )
        self.module.aa_drive_configuration_status = lambda: ("ok", "")

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Kopi Janji",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["image_count"], 0)
        self.assertEqual(result["answer"]["drive_selfies"], [])
        self.assertIn("No image attachments", result["caveat"])

    def test_attach_aa_selfie_to_thread_attaches_to_all_aa_tickets_in_thread(self):
        attach_payload_calls = []

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                },
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_drive_upload(images, company, pic):
            return [
                {
                    "drive_file_id": "drive-1",
                    "name": "dandy-collection_rohit__F-img.jpg",
                    "web_view_link": "https://drive/x",
                }
            ]

        def fake_attach_payloads(issue_keys, payloads):
            attach_payload_calls.append((list(issue_keys), list(payloads)))
            return {
                key: {
                    "attached": [{"id": f"att-{key}", "filename": "selfie.jpg"}],
                    "errors": [],
                }
                for key in issue_keys
            }

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": fake_drive_upload(images, company, pic),
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: [
            {"issue_key": "PCO-247", "url": "https://staffany.atlassian.net/browse/PCO-247"},
            {"issue_key": "PCO-248", "url": "https://staffany.atlassian.net/browse/PCO-248"},
        ]
        self.module._attach_payloads_to_issues = fake_attach_payloads

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Dandy Collection",
            pic="Rohit",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["saved_count"], 1)
        self.assertEqual(result["answer"]["jira_ticket_count"], 2)
        self.assertEqual(result["answer"]["jira_attached_count"], 2)
        self.assertEqual(sorted(result["answer"]["jira_attachments"].keys()), ["PCO-247", "PCO-248"])
        self.assertEqual(len(attach_payload_calls), 1)
        self.assertEqual(attach_payload_calls[0][0], ["PCO-247", "PCO-248"])
        self.assertIn("Saved 1 selfie(s) to Drive", result["caveat"])
        self.assertIn("attached 2 image(s) across 2 Jira ticket(s)", result["caveat"])

    def test_attach_aa_selfie_to_thread_searches_thread_permalink_variants(self):
        ticket_lookup_args: list[str] = []

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_ticket_lookup(url, _limit):
            ticket_lookup_args.append(url)
            # Only return a hit for the parent-thread variant — proves the
            # tool didn't stop at the reply URL it was handed.
            if url == "https://staffany.slack.com/archives/C0B5H2YE5T2/p1779243840262999":
                return [{"issue_key": "PCO-247", "url": "https://staffany.atlassian.net/browse/PCO-247"}]
            return []

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: {
            "uploaded": [{"drive_file_id": "drive-1", "name": "x.jpg", "web_view_link": "https://drive/x"}],
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = fake_ticket_lookup
        self.module._attach_payloads_to_issues = lambda keys, payloads: {
            key: {"attached": [{"id": f"att-{key}", "filename": "x.jpg"}], "errors": []} for key in keys
        }

        # Reply permalink with thread_ts pointing at the parent — exactly the
        # shape Slack hands the agent for a follow-up selfie reply.
        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779243903073209?thread_ts=1779243840.262999&cid=C0B5H2YE5T2",
            customer="Dandy Collection",
            pic="Rohit",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["jira_ticket_count"], 1)
        self.assertEqual(result["answer"]["jira_attached_count"], 1)
        # Confirms the parent-thread variant was tried, not just the reply URL.
        self.assertIn(
            "https://staffany.slack.com/archives/C0B5H2YE5T2/p1779243840262999",
            ticket_lookup_args,
        )

    def test_attach_aa_selfie_to_thread_surfaces_jira_attach_errors(self):
        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: {
            "uploaded": [{"drive_file_id": "drive-1", "name": "x.jpg", "web_view_link": "https://drive/x"}],
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: [
            {"issue_key": "PCO-500", "url": "https://staffany.atlassian.net/browse/PCO-500"},
        ]
        self.module._attach_payloads_to_issues = lambda keys, payloads: {
            "PCO-500": {
                "attached": [],
                "errors": ["Jira attachment POST failed: 401 Unauthorized"],
            }
        }

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Dandy Collection",
            pic="Rohit",
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["jira_attached_count"], 0)
        self.assertIn(
            "PCO-500: Jira attachment POST failed: 401 Unauthorized",
            result["answer"]["jira_attach_errors"],
        )
        self.assertIn("Jira errors", result["caveat"])

    def test_attach_aa_selfie_to_thread_surfaces_drive_failure_reason(self):
        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        self.module._request_slack_json = fake_slack_json
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: {
            "uploaded": [],
            "drive_status": "upload_failed",
            "drive_reason": "Drive upload failed: 401 Invalid Credentials",
            "failure_count": 1,
            "last_error": "Drive upload failed: 401 Invalid Credentials",
        }
        self.module.aa_drive_configuration_status = lambda: ("ok", "")
        self.module._ticket_by_slack_thread = lambda *args, **kwargs: []

        result = self.module.attach_aa_selfie_to_thread(
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779217695397149",
            customer="Dandy Collection",
            pic="Rohit",
        )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["drive_status"], "upload_failed")
        self.assertEqual(
            result["answer"]["drive_reason"],
            "Drive upload failed: 401 Invalid Credentials",
        )
        # The caveat must include the verbatim Drive reason instead of the
        # old invented "check OAuth token validity" message.
        self.assertIn("Drive upload failed: 401 Invalid Credentials", result["caveat"])

    def test_ps_wee_intake_in_aa_channel_creates_ticket_even_when_creator_no_match(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-999", "requestTypeId": "123"}
            if path.endswith("/comment"):
                return {"id": "comment-999"}
            return {}

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="strangerwhowasnotinvited@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779100000000099",
            customer="Kopi Janji",
            issue_summary="follow up",
            request_type_key="ps_follow_up",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        self.assertNotIn("customfield_10914", create_call[2]["requestFieldValues"], "Creator field should be omitted when no option matches")

    def test_ps_wee_intake_in_aa_channel_overrides_hallucinated_slack_user_email(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-901", "requestTypeId": "123"}
            if path.endswith("/comment"):
                return {"id": "comment-901"}
            return {}

        # Slack conversations.history returns the verified Slack tagger
        # (Ada PSM's real Slack ID) for the trigger message — this is the
        # source of truth the MCP must trust over whatever the agent passes.
        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {"ts": params.get("oldest", ""), "user": "UADAREAL"},
                    ]
                }
            if method == "users.list":
                return {
                    "members": [
                        {
                            "id": "UADAREAL",
                            "real_name": "Ada PSM",
                            "profile": {
                                "email": "psm@staffany.com",
                                "real_name": "Ada PSM",
                            },
                        }
                    ]
                }
            return {}

        def creator_options(request_type_id=""):
            return [
                {"value": "creator-ada", "label": "Ada PSM"},
                {"value": "creator-josica", "label": "Josica"},
            ]
        def ps_team_options(request_type_id=""):
            return [
                {"value": "team-ada", "label": "Ada PSM"},
                {"value": "team-josica", "label": "Josica"},
            ]

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._creator_valid_values = creator_options
        self.module._ps_team_valid_values = ps_team_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        # Agent hallucinates a Slack ID that does not exist (matches the
        # real-prod failure pattern from PCO-291/293 and PCO-298-300). The
        # MCP must re-derive the tagger from the thread permalink and use
        # Ada PSM's verified identity for Creator + PS Team.
        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="U07HALLUC1NAT",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779259580035789",
            customer="Rock Productions",
            issue_summary="Follow up on proper changelog",
            request_type_key="ps_follow_up",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        values = create_call[2]["requestFieldValues"]
        self.assertEqual(
            values.get("customfield_10914"), {"id": "creator-ada"},
            msg=f"AA Creator must come from the verified Slack tagger, not the hallucinated slack_user_email: {values}",
        )
        self.assertEqual(
            values.get("customfield_10876"), {"id": "team-ada"},
            msg=f"AA PS Team must come from the verified Slack tagger: {values}",
        )
        self.assertNotIn("U07HALLUC1NAT", json.dumps(values), "hallucinated Slack ID must never reach Jira")

    def test_ps_wee_intake_in_aa_channel_falls_back_to_supplied_email_when_slack_unreachable(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-902", "requestTypeId": "123"}
            if path.endswith("/comment"):
                return {"id": "comment-902"}
            return {}

        # Slack is unreachable for both conversations.history and the
        # subsequent users.list lookup — the MCP must not block.
        def fake_slack_json(method, params):
            raise self.module.JiraError("slack unreachable")

        def creator_options(request_type_id=""):
            return [{"value": "creator-ada", "label": "Ada PSM"}]
        def ps_team_options(request_type_id=""):
            return [{"value": "team-ada", "label": "Ada PSM"}]

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._creator_valid_values = creator_options
        self.module._ps_team_valid_values = ps_team_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        # Agent supplies a real, policy-mapped email — Slack lookup failures
        # must not regress this path: the agent-supplied email is honored
        # when verification is impossible.
        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779259580035789",
            customer="Rock Productions",
            issue_summary="Follow up on proper changelog",
            request_type_key="ps_follow_up",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        values = create_call[2]["requestFieldValues"]
        self.assertEqual(values.get("customfield_10914"), {"id": "creator-ada"})
        self.assertEqual(values.get("customfield_10876"), {"id": "team-ada"})

    def test_ps_wee_intake_in_aa_channel_ignores_hallucinated_creator_override(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-888", "requestTypeId": "123"}
            if path.endswith("/comment"):
                return {"id": "comment-888"}
            return {}

        # Mock includes "Ada PSM" so the verified Slack tagger has a real
        # Creator + PS Team option to match — otherwise we'd only be testing
        # the silent-omit path, not the override-ignore path.
        def creator_options(request_type_id=""):
            return [
                {"value": "creator-ada", "label": "Ada PSM"},
                {"value": "creator-josica", "label": "Josica"},
            ]
        def ps_team_options(request_type_id=""):
            return [
                {"value": "team-ada", "label": "Ada PSM"},
                {"value": "team-josica", "label": "Josica"},
            ]

        self.module._request_json = fake_request
        self.module._creator_valid_values = creator_options
        self.module._ps_team_valid_values = ps_team_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        # slack_user_email maps to Ada PSM via the access policy. The
        # creator_slack_user_email is a hallucinated Slack ID (the same one
        # that broke PCO-291/293 in prod) — the MCP must ignore it and use
        # the verified tagger identity for both Creator and PS Team fallback.
        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779257813193379",
            customer="Super Loco Group",
            issue_summary="Follow up API access for wall",
            request_type_key="ps_follow_up",
            creator_slack_user_email="U07UTFE8U3X",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        values = create_call[2]["requestFieldValues"]
        self.assertEqual(
            values.get("customfield_10914"), {"id": "creator-ada"},
            msg=f"AA Creator must come from the verified Slack tagger, not the hallucinated override: {values}",
        )
        # PS Team fallback (ps_follow_up isn't in EVENT_AA_PS_TEAM_BY_CATEGORY,
        # so the fallback resolves through the matched creator label /
        # tagger display name → Ada PSM in the policy).
        self.assertEqual(
            values.get("customfield_10876"), {"id": "team-ada"},
            msg=f"AA PS Team must come from the verified Slack tagger: {values}",
        )
        self.assertNotIn("U07UTFE8U3X", json.dumps(values), "hallucinated creator ID must never reach Jira")

    def test_ps_wee_intake_in_aa_channel_strips_any_supplied_due_date(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-777", "requestTypeId": "122"}
            if path.endswith("/comment"):
                return {"id": "comment-777"}
            return {}

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        # Past date (would have triggered the validator) and a future date
        # both must be stripped on AA intakes — triage owns deadlines.
        for supplied_due in ("2025-06-02", "2026-06-02"):
            calls.clear()
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="josica@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779257501716939",
                customer="Playmade",
                issue_summary="HR PIC change Agnes to Roxanne, handover required",
                request_type_key="feedback",
                due_date=supplied_due,
                creator_slack_user_email="josica@staffany.com",
            )

            self.assertEqual(
                result["confidence"], "verified",
                msg=f"AA intake must not block on any supplied due_date ({supplied_due}): {result}",
            )
            create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
            self.assertEqual(len(create_calls), 1, "ticket must still be created")
            duedate_writes = [c for c in calls if c[0] == "PUT" and "duedate" in json.dumps(c[2] or {})]
            self.assertEqual(
                duedate_writes, [],
                msg=f"AA intake must not write due_date to Jira (supplied={supplied_due})",
            )
            slack_reply = result["answer"]["slack_reply"]
            self.assertIn("Created first", slack_reply)
            self.assertNotIn(supplied_due, slack_reply, "AA reply must not echo a stripped date")

    def test_ps_wee_intake_outside_aa_channel_still_blocks_past_due_date(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-778", "requestTypeId": "101"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C9999AAAA00/p1779100000000777",
            customer="Acme",
            issue_summary="non-AA flow",
            due_date="2025-06-02",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("before today", result["answer"]["message"])
        create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
        self.assertEqual(create_calls, [], "non-AA flows must still block past dates before write")

    def test_ps_wee_intake_in_aa_channel_allows_multi_ticket_per_thread(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                if "PS+Follow+Up" in path or "PS%20Follow%20Up" in path:
                    return {"issues": []}
                if "CS+Follow+Up" in path or "CS%20Follow%20Up" in path:
                    return {"issues": []}
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                rtype = (body or {}).get("requestTypeId")
                key = "PCO-PS" if rtype == "123" else "PCO-CS"
                return {"issueKey": key, "requestTypeId": rtype}
            if path.endswith("/comment"):
                return {"id": "comment-x"}
            return {}

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        thread = "https://staffany.slack.com/archives/C0B5H2YE5T2/p1779100000000050"

        first = self.module.create_ps_wee_intake_ticket(
            slack_user_email="josica@staffany.com",
            slack_thread_url=thread,
            customer="Kopi Janji",
            issue_summary="deep dive",
            request_type_key="ps_follow_up",
            creator_slack_user_email="josica@staffany.com",
        )
        second = self.module.create_ps_wee_intake_ticket(
            slack_user_email="josica@staffany.com",
            slack_thread_url=thread,
            customer="Kopi Janji",
            issue_summary="troubleshooting",
            request_type_key="cs_follow_up",
            creator_slack_user_email="josica@staffany.com",
        )

        self.assertEqual(first["confidence"], "verified")
        self.assertEqual(second["confidence"], "verified")
        create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
        self.assertEqual(len(create_calls), 2)
        self.assertEqual(create_calls[0][2]["requestTypeId"], "123")
        self.assertEqual(create_calls[1][2]["requestTypeId"], "124")
        search_calls = [c[1] for c in calls if c[1].startswith("/rest/api/3/search/jql?")]
        self.assertTrue(
            any("PS+Follow+Up" in path or "PS%20Follow%20Up" in path for path in search_calls),
            msg=f"PS Follow Up filter missing from dedupe queries: {search_calls}",
        )
        self.assertTrue(
            any("CS+Follow+Up" in path or "CS%20Follow%20Up" in path for path in search_calls),
            msg=f"CS Follow Up filter missing from dedupe queries: {search_calls}",
        )

    def test_ps_wee_intake_in_aa_channel_allows_multi_customer_same_request_type(self):
        existing_issue = {
            "key": "PCO-264",
            "fields": {
                "summary": "Qiqi - Want to expand more outlets",
                "status": {"name": "Open"},
                "priority": {"name": "Medium"},
            },
        }
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                # Same Slack thread + same request_type returns the prior Qiqi ticket.
                return {"issues": [existing_issue]}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-265", "requestTypeId": "120"}
            if path.endswith("/comment"):
                return {"id": "comment-265"}
            return {}

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="eugene@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779250051395009",
            customer="Lo and Behold",
            issue_summary="Want to expand more outlets",
            request_type_key="rev_cross_sell",
            creator_slack_user_email="eugene@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        # New ticket must be created — dedupe should not collapse Lo and Behold into Qiqi.
        create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
        self.assertEqual(len(create_calls), 1)
        self.assertNotIn("existing_ticket", result["answer"])

    def test_ps_wee_intake_in_aa_channel_reuses_only_when_customer_matches(self):
        existing_issue = {
            "key": "PCO-300",
            "fields": {
                "summary": "Dapur Penyet - Follow up on HRany",
                "status": {"name": "Open"},
                "priority": {"name": "Medium"},
            },
        }
        label_calls = []

        def fake_request(method, path, body=None):
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": [existing_issue]}
            return {}

        def fake_labels(issue_key, add=None, remove=None):
            label_calls.append((issue_key, list(add or []), list(remove or [])))

        self.module._request_json = fake_request
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = fake_labels
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="siti@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779249926878009",
            customer="Dapur Penyet",
            issue_summary="Follow up on HRany",
            request_type_key="rev_cross_sell",
            creator_slack_user_email="siti@staffany.com",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["existing_ticket"]["issue_key"], "PCO-300")
        # AA reuse path must defensively re-apply the AA-SG-2026 label on the existing ticket.
        self.assertTrue(
            any("PCO-300" == key and "AA-SG-2026" in labels for key, labels, _ in label_calls),
            msg=f"AA-SG-2026 label was not re-applied on reuse: {label_calls}",
        )

    def test_ps_wee_intake_outside_aa_channel_does_not_force_event_aa_request_type(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-903", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-903"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1779100000000002",
            customer="Some Customer",
            issue_summary="Regular non-event request",
        )

        self.assertEqual(result["confidence"], "verified")
        create_call = next(c for c in calls if c[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_call[2]["requestTypeId"], "101")
        self.assertEqual(result["scope"]["request_type_key"], "customer_next_action")
        self.assertEqual(result["scope"]["event"], "")

    def test_ps_wee_intake_drops_needs_info_concept_entirely(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-160", "requestTypeId": "101"}
            if path.endswith("/comment"):
                return {"id": "comment-160"}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        # Minimal intake: no customer, no issue_summary, no extra context. PS does not
        # use the needs-info concept, so this still creates cleanly without label/missing-info.
        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="alya@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C01HQMYN4M9/p1778807520894139",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertNotIn("missing_info", result["answer"])
        self.assertNotIn("I still need", result["answer"]["slack_reply"])
        self.assertIn("<https://staffany.atlassian.net/browse/PCO-160|PCO-160>", result["answer"]["slack_reply"])
        for call in calls:
            body = call[2] if isinstance(call[2], dict) else {}
            self.assertNotIn("Missing info", str(body))
            labels = (body.get("update") or {}).get("labels") or []
            self.assertNotIn({"add": "needs-info"}, labels)
        self.assertNotIn("missing_info", audit_calls[0][1])

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
        # Stub Assets resolution: workspace discovery is short-circuited and each supplied
        # name echoes back as its numeric id, so the wire payload uses the composite globalId.
        self.module._assets_workspace_id = lambda: "ws-test"
        self.module._resolve_assets_object_id = lambda name: name

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "verified")
        request_values = calls[1][2]["requestFieldValues"]
        self.assertEqual(request_values["customfield_10101"], "Fei Siong Group")
        self.assertEqual(
            request_values["customfield_10102"],
            [{"id": "ws-test:FS-001"}, {"id": "ws-test:FS-002"}],
        )
        self.assertEqual(request_values["summary"], "Fei Siong Group - Payroll readiness unclear")
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
        self.module._assets_workspace_id = lambda: "ws-test"
        self.module._resolve_assets_object_id = lambda name: name

        with patch.dict(os.environ, {"PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH": map_path}, clear=False):
            result = self.module.create_ps_wee_intake_ticket(
                slack_user_email="psm@staffany.com",
                slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778205303989579",
                customer="Fei Siong",
                issue_summary="Payroll readiness unclear",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(calls[1][2]["requestFieldValues"]["customfield_10102"], [{"id": "ws-test:FS-001"}])

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

    def test_ps_wee_intake_unmapped_channel_creates_ticket_with_unknown_customer(self):
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
        self.assertEqual(request_values["summary"], "Unknown customer - Payroll readiness unclear")
        self.assertNotIn("customfield_10102", request_values)

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
                            "summary": "Fei Siong - Payroll readiness unclear",
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

    def test_roi_intent_defaults_billing_to_pco_tracker_without_action_word(self):
        result = self.module.classify_roi_ticket_request("Dreamus renewal invoice has MRR mismatch")

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["is_roi_ticket_request"])
        self.assertTrue(result["answer"]["pco_tracker_default"])
        self.assertFalse(result["answer"]["requires_action"])
        self.assertEqual(result["answer"]["pco_tracker_reason"], "billing_or_invoice_default")

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
        self.assertEqual(values["customfield_20100"], "Dreamus")
        self.assertEqual(values["customfield_20102"], {"id": "11967"})
        self.assertNotIn("customfield_20107", values)
        self.assertIn("https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219139", values["customfield_20103"])
        self.assertIn("Ada PSM", values["customfield_20104"])
        self.assertEqual(values["customfield_20105"], "#team-rev-bd-ops")
        self.assertEqual(calls[3][1], "/rest/servicedeskapi/request/ROI-123/comment")
        self.assertIn("Requester: Ada PSM", calls[3][2]["body"])
        self.assertIn("Created ROI ticket", result["answer"]["slack_reply"])
        self.assertEqual(audit_calls[0][0], "roi_ticket_created")
        self.assertEqual(audit_calls[0][1]["issue_key"], "ROI-123")

    def test_roi_configured_fields_disambiguate_optional_name_matches(self):
        self.module._request_json = lambda method, path, body=None: {"requestTypeFields": self._roi_fields()}

        result = self.module.validate_roi_jira_configuration()

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("customer", result["answer"]["mapped_fields"])
        self.assertIn("priority", result["answer"]["mapped_fields"])
        self.assertEqual(result["answer"]["configured_field_ids"]["customer"], "customfield_20101")
        self.assertEqual(result["answer"]["configured_field_ids"]["staffany_orgs"], "customfield_20100")
        self.assertEqual(result["answer"]["configured_field_ids"]["priority"], "customfield_20106")

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

    def test_create_or_link_pco_roi_tracker_creates_waiting_internal_tracker(self):
        calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path.endswith("/requesttype/101/field"):
                return {
                    "requestTypeFields": [
                        {
                            "fieldId": "customfield_10876",
                            "name": "PS Team",
                            "validValues": [{"value": "team-ada", "label": "Ada PSM"}],
                        }
                    ]
                }
            if method == "POST" and path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-222", "requestTypeId": "101"}
            if method == "POST" and path.endswith("/comment"):
                return {"id": "comment-222"}
            if method == "GET" and path == "/rest/api/3/issue/PCO-222?fields=issuelinks":
                return {"fields": {"issuelinks": []}}
            if method == "GET" and path == "/rest/api/3/issue/PCO-222/transitions":
                return {"transitions": [{"id": "41", "name": "Waiting Internal", "to": {"name": "Waiting Internal"}}]}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_or_link_pco_roi_tracker(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219144",
            roi_issue_key="ROI-123",
            customer="Dreamus",
            summary="Renewal invoice mismatch",
            original_channel="#team-rev-bd-ops",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["pco_issue_key"], "PCO-222")
        self.assertEqual(result["answer"]["roi_issue_key"], "ROI-123")
        self.assertEqual(result["answer"]["label"], "ps-wee-roi-tracker")
        self.assertIn("ROI remains source of truth", result["caveat"])
        create_payload = next(call[2] for call in calls if call[0] == "POST" and call[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_payload["requestFieldValues"]["summary"], "[Waiting internal] Dreamus - Renewal invoice mismatch")
        label_call = next(call for call in calls if call[0] == "PUT" and call[1] == "/rest/api/3/issue/PCO-222")
        self.assertEqual(label_call[2]["update"]["labels"], [{"add": "ps-wee-roi-tracker"}])
        link_call = next(call for call in calls if call[0] == "POST" and call[1] == "/rest/api/3/issueLink")
        self.assertEqual(link_call[2]["type"], {"name": "Blocks"})
        self.assertEqual(link_call[2]["outwardIssue"], {"key": "ROI-123"})
        self.assertEqual(link_call[2]["inwardIssue"], {"key": "PCO-222"})
        self.assertIn(("POST", "/rest/api/3/issue/PCO-222/transitions", {"transition": {"id": "41"}, "update": {"comment": [{"add": {"body": self.module._adf("PCO customer-loop tracker is waiting on linked ROI issue ROI-123.")}}]}}), calls)
        self.assertEqual(audit_calls[0][0], "roi_tracker_linked")

    def test_create_or_link_pco_roi_tracker_reuses_same_thread_tracker(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {
                    "issues": [
                        {
                            "key": "PCO-333",
                            "fields": {
                                "summary": "Dreamus invoice tracker",
                                "status": {"name": "Waiting Internal"},
                                "priority": {"name": "Medium"},
                                "customfield_10876": {"value": "Ada PSM"},
                            },
                        }
                    ]
                }
            if method == "GET" and path == "/rest/api/3/issue/PCO-333?fields=issuelinks":
                return {"fields": {"issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "ROI-123"}}]}}
            return {}

        self.module._request_json = fake_request
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_or_link_pco_roi_tracker(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1778753307219144",
            roi_issue_key="ROI-123",
            customer="Dreamus",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertTrue(result["answer"]["already_exists"])
        self.assertTrue(result["answer"]["link_already_exists"])
        self.assertEqual([call for call in calls if call[0] == "POST"], [])

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
        self.assertIn("Central PSM Ops digests", result["answer"]["reminder_policy"])
        self.assertIn("No separate Slack thread", result["answer"]["central_digest"])

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

    def test_thin_poc_create_retries_without_staffany_orgs_when_assets_rejects(self):
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
                    raise self.module.JiraError("Jira rejected optional field value", status_code=400)
                if path == "/rest/servicedeskapi/request":
                    return {"issueKey": "PCO-456", "requestTypeId": "81"}
                if path.endswith("/comment"):
                    return {"id": "comment-456"}
                return {}

            self.module._request_json = fake_request
            self.module._assets_workspace_id = lambda: "ws-test"
            self.module._resolve_assets_object_id = lambda name: name

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
        self.assertEqual(calls[0][2]["requestFieldValues"]["customfield_10667"], [{"id": "ws-test:FS-001"}])
        retry_values = calls[1][2]["requestFieldValues"]
        self.assertNotIn("customfield_10667", retry_values)
        self.assertEqual(retry_values["summary"], "Confirm payroll readiness")
        self.assertEqual(calls[2][1], "/rest/api/3/issue/PCO-456")
        self.assertEqual(calls[2][2]["fields"], {"duedate": "2026-05-15"})
        self.assertEqual(calls[3][1], "/rest/servicedeskapi/request/PCO-456/comment")
        self.assertEqual(calls[4][1], "/rest/api/3/issue/PCO-456/assignee")
        self.assertIn("StaffAny Organization was skipped", result["answer"]["warnings"][0])

    def test_thin_poc_create_falls_back_to_summary_only_when_retry_still_fails(self):
        calls = []
        original_ps_team_request_value = self.module._ps_team_request_value
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
                if path == "/rest/servicedeskapi/request" and set(body["requestFieldValues"]) != {"summary"}:
                    raise self.module.JiraError("Jira rejected optional field value", status_code=400)
                if path == "/rest/servicedeskapi/request":
                    return {"issueKey": "PCO-789", "requestTypeId": "81"}
                if path.endswith("/comment"):
                    return {"id": "comment-789"}
                return {}

            self.module._request_json = fake_request
            self.module._assets_workspace_id = lambda: "ws-test"
            self.module._resolve_assets_object_id = lambda name: name
            self.module._ps_team_request_value = lambda label, request_type_id="": {"id": "ps-team-id"}

            try:
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
                        "ps_team": "CS Duty",
                        "owner_psm": "Ada PSM",
                        "owner_jira_account_id": "acct-123",
                        "mode": "thin_poc",
                    },
                    "create",
                )
            finally:
                self.module._ps_team_request_value = original_ps_team_request_value

        self.assertEqual(result["confidence"], "verified")
        create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
        self.assertEqual(len(create_calls), 3)
        self.assertIn("customfield_10667", create_calls[0][2]["requestFieldValues"])
        self.assertNotIn("customfield_10667", create_calls[1][2]["requestFieldValues"])
        self.assertGreater(len(create_calls[1][2]["requestFieldValues"]), 1)
        self.assertEqual(create_calls[2][2]["requestFieldValues"], {"summary": "Confirm payroll readiness"})
        self.assertIn("Optional PCO request fields were skipped", result["answer"]["warnings"][0])

    def test_thin_poc_create_does_not_retry_on_non_400_error(self):
        """Network errors / 5xx must not retry — the original create may have landed."""
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
                if path == "/rest/servicedeskapi/request":
                    raise self.module.JiraError("Jira API unavailable: timed out")
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

        create_calls = [c for c in calls if c[1] == "/rest/servicedeskapi/request"]
        self.assertEqual(len(create_calls), 1, "transient errors must not retry the create")
        self.assertEqual(result["confidence"], "blocked")

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

    def test_classify_no_follow_up_intent_returns_classifier_decision(self):
        captured = []

        def fake_call(model, system, user_text, tools, tool_name, max_tokens=256):
            captured.append({
                "model": model,
                "system": system,
                "user_text": user_text,
                "tools": tools,
                "tool_name": tool_name,
            })
            return {"skip_photo_follow_up": True, "reason": "Message explicitly says 'no follow up needed'."}

        self.module._call_anthropic_messages = fake_call

        skip, reason = self.module._classify_no_follow_up_intent(
            "Met Andre. No follow up needed, just a photo for the record."
        )

        self.assertTrue(skip)
        self.assertIn("no follow up", reason.lower())
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["model"], self.module.NO_FOLLOW_UP_CLASSIFIER_MODEL)
        self.assertEqual(captured[0]["tool_name"], "report_no_follow_up_intent")

    def test_classify_no_follow_up_intent_returns_false_for_negative_decision(self):
        self.module._call_anthropic_messages = lambda *a, **kw: {
            "skip_photo_follow_up": False,
            "reason": "Message has an actionable bullet about expansion.",
        }

        skip, reason = self.module._classify_no_follow_up_intent(
            "Met Andre. Want to expand to more outlets, photo attached."
        )

        self.assertFalse(skip)
        self.assertIn("actionable", reason.lower())

    def test_classify_no_follow_up_intent_rejects_non_boolean_skip_flag(self):
        self.module._call_anthropic_messages = lambda *a, **kw: {
            "skip_photo_follow_up": "false",
            "reason": "string booleans must not suppress a real follow-up ticket",
        }

        skip, reason = self.module._classify_no_follow_up_intent(
            "Met Andre. This should not skip because the tool returned a string."
        )

        self.assertFalse(skip)
        self.assertEqual(reason, "classifier_error: invalid skip_photo_follow_up type")

    def test_audit_requester_identity_preserves_slack_user_id_casing(self):
        self.assertEqual(self.module._audit_requester_identity("U0ABC12345"), "U0ABC12345")
        self.assertEqual(self.module._audit_requester_identity("<@U0ABC12345>"), "U0ABC12345")
        self.assertEqual(self.module._audit_requester_identity("w0abc12345"), "w0abc12345")
        self.assertEqual(self.module._audit_requester_identity("PSM@StaffAny.com"), "psm@staffany.com")

    def test_classify_no_follow_up_intent_empty_text_returns_false_without_calling_api(self):
        def boom(*args, **kwargs):
            self.fail("API must not be called for empty trigger text")

        self.module._call_anthropic_messages = boom

        skip, reason = self.module._classify_no_follow_up_intent("")

        self.assertFalse(skip)
        self.assertEqual(reason, "empty trigger text")

    def test_classify_no_follow_up_intent_defaults_to_false_on_api_failure(self):
        def fail(*args, **kwargs):
            raise self.module.JiraError("ANTHROPIC_API_KEY is not configured for the LLM classifier.")

        self.module._call_anthropic_messages = fail

        skip, reason = self.module._classify_no_follow_up_intent("anything goes here")

        self.assertFalse(skip)
        self.assertIn("classifier_unavailable", reason)

    def test_classify_no_follow_up_intent_defaults_to_false_on_unexpected_error(self):
        def boom(*args, **kwargs):
            raise RuntimeError("network exploded")

        self.module._call_anthropic_messages = boom

        skip, reason = self.module._classify_no_follow_up_intent("anything")

        self.assertFalse(skip)
        self.assertIn("classifier_error", reason)

    def test_ps_wee_intake_in_aa_channel_skips_photo_follow_up_when_classifier_says_skip(self):
        request_calls = []
        classifier_calls = []

        def fake_request(method, path, body=None):
            request_calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                self.fail("photo_follow_up create must be skipped when classifier returns true")
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "user": "U-PSM",
                            "text": "Kindly disregard the photo, just for our archive.",
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        def fake_classifier(text):
            classifier_calls.append(text)
            return True, "Message tells the team to disregard the photo and keep it for archive only."

        audit_calls = []

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._classify_no_follow_up_intent = fake_classifier
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}
        self.module.upload_aa_selfies_detailed = lambda *args, **kwargs: self.fail(
            "Drive upload must not run when photo_follow_up is skipped server-side."
        )
        self.module._attach_image_files_to_issue = lambda *args, **kwargs: self.fail(
            "Jira attach must not run when no ticket was created."
        )

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264818954259",
            customer="Andre Cafe",
            issue_summary="photo follow up",
            request_type_key="photo_follow_up",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["status"], "skipped")
        self.assertEqual(result["answer"]["reason"], "no_follow_up_signal_detected")
        self.assertEqual(result["answer"]["skipped_request_type"], "photo_follow_up")
        self.assertIn("disregard", result["answer"]["classifier_reason"].lower())
        # Classifier consulted with the trigger text (proves fuzzy detection drove the skip,
        # not any hardcoded phrase — the message has no regex-friendly cue).
        self.assertEqual(len(classifier_calls), 1)
        self.assertIn("disregard", classifier_calls[0].lower())
        # No Jira write — we returned before touching Jira.
        self.assertEqual(request_calls, [])
        self.assertTrue(any(event == "photo_follow_up_skipped" for event, _ in audit_calls))
        self.assertEqual(result["scope"]["caller"], "u-psm")
        skipped_audit = next(payload for event, payload in audit_calls if event == "photo_follow_up_skipped")
        self.assertEqual(skipped_audit["requester"], "u-psm")

    def test_ps_wee_intake_in_aa_channel_creates_photo_follow_up_when_classifier_says_no_skip(self):
        request_calls = []

        def fake_request(method, path, body=None):
            request_calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-127", "requestTypeId": "127"}
            if path.endswith("/comment"):
                return {"id": "comment-127"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "user": "U-PSM",
                            "text": "Met Andre at the AA. Looks promising, want to schedule a deep dive.",
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._classify_no_follow_up_intent = lambda text: (False, "Has an actionable follow-up bullet.")
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}
        self.module._download_slack_file = lambda url: b"binary-image-data"
        self.module._attach_image_files_to_issue = lambda issue_key, files: [
            {"id": "att-1", "filename": files[0]["name"]}
        ]
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": [{"drive_file_id": "d-1", "name": "andre.jpg", "web_view_link": "https://drive/x"}],
            "drive_status": "ok",
            "drive_reason": "",
            "failure_count": 0,
            "last_error": "",
        }

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264818954260",
            customer="Andre Cafe",
            issue_summary="photo follow up",
            request_type_key="photo_follow_up",
            pic="Andre",
        )

        self.assertEqual(result["confidence"], "verified")
        # Ticket was created (no skip payload).
        self.assertNotEqual(result["answer"].get("status"), "skipped")
        create_call = next(c for c in request_calls if c[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_call[2]["requestTypeId"], "127")

    def test_ps_wee_intake_in_aa_channel_creates_photo_follow_up_when_classifier_unavailable(self):
        request_calls = []

        def fake_request(method, path, body=None):
            request_calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-127", "requestTypeId": "127"}
            if path.endswith("/comment"):
                return {"id": "comment-127"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "user": "U-PSM",
                            "text": "No follow up needed, just sending the photo for the record.",
                            "files": [
                                {
                                    "id": "F-img",
                                    "name": "selfie.jpg",
                                    "mimetype": "image/jpeg",
                                    "url_private": "https://files.slack.com/selfie.jpg",
                                }
                            ],
                        }
                    ]
                }
            return {"members": []}

        # Simulate the classifier being unavailable (missing API key, network down, etc.).
        def unavailable(*args, **kwargs):
            raise self.module.JiraError("ANTHROPIC_API_KEY is not configured for the LLM classifier.")
        self.module._call_anthropic_messages = unavailable
        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}
        self.module._download_slack_file = lambda url: b"img"
        self.module._attach_image_files_to_issue = lambda issue_key, files: [
            {"id": "att-1", "filename": files[0]["name"]}
        ]
        self.module.upload_aa_selfies_detailed = lambda images, company, pic: {
            "uploaded": [], "drive_status": "ok", "drive_reason": "", "failure_count": 0, "last_error": "",
        }

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264818954262",
            customer="Andre Cafe",
            issue_summary="photo follow up",
            request_type_key="photo_follow_up",
            pic="Andre",
        )

        # Classifier unavailable → default to NOT skip → ticket still creates.
        # This is the load-bearing safety guarantee: LLM downtime cannot silently
        # drop a real follow-up.
        self.assertEqual(result["confidence"], "verified")
        self.assertNotEqual(result["answer"].get("status"), "skipped")
        create_call = next(c for c in request_calls if c[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_call[2]["requestTypeId"], "127")

    def test_ps_wee_intake_non_photo_actionable_creates_via_general_classifier(self):
        request_calls = []
        actionable_calls = []

        def fake_request(method, path, body=None):
            request_calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                return {"issueKey": "PCO-200", "requestTypeId": "120"}
            if path.endswith("/comment"):
                return {"id": "c-200"}
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "user": "U-PSM",
                            "text": "want to expand to more outlets.",
                            "files": [],
                        }
                    ]
                }
            return {"members": []}

        # Non-photo AA types run the general actionable classifier, NOT the
        # photo-specific one.
        def boom(*args, **kwargs):
            self.fail("photo classifier must not run for non-photo request types")
        self.module._classify_no_follow_up_intent = boom

        def fake_actionable(text):
            actionable_calls.append(text)
            return False, "Has an actionable expansion ask."
        self.module._classify_aa_actionable_intent = fake_actionable
        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264818954261",
            customer="Andre Cafe",
            issue_summary="want to expand more outlets",
            request_type_key="rev_cross_sell",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertNotEqual(result["answer"].get("status"), "skipped")
        self.assertEqual(len(actionable_calls), 1)
        self.assertIn("expand", actionable_calls[0].lower())
        create_call = next(c for c in request_calls if c[1] == "/rest/servicedeskapi/request")
        self.assertEqual(create_call[2]["requestTypeId"], "120")

    def test_ps_wee_intake_in_aa_channel_skips_non_actionable_message(self):
        request_calls = []
        audit_calls = []

        def fake_request(method, path, body=None):
            request_calls.append((method, path, deepcopy(body)))
            if method == "GET" and path.startswith("/rest/api/3/search/jql?"):
                return {"issues": []}
            if path == "/rest/servicedeskapi/request":
                self.fail("non-actionable AA message must not create a ticket")
            return {}

        def fake_slack_json(method, params):
            if method == "conversations.history":
                return {
                    "messages": [
                        {
                            "ts": params["oldest"],
                            "user": "U-PSM",
                            "text": "just met the new team at the booth, all good!",
                            "files": [],
                        }
                    ]
                }
            return {"members": []}

        actionable_calls = []

        def fake_actionable(text):
            actionable_calls.append(text)
            return True, "Message only says they met the new team; no follow-up action."

        self.module._request_json = fake_request
        self.module._request_slack_json = fake_slack_json
        self.module._classify_aa_actionable_intent = fake_actionable
        self.module._creator_valid_values = self._mock_creator_options
        self.module._update_issue_labels = lambda *args, **kwargs: None
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264818954263",
            customer="Bean Bros",
            issue_summary="met new team",
            request_type_key="feedback",
        )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["status"], "skipped")
        self.assertEqual(result["answer"]["reason"], "non_actionable_no_follow_up")
        self.assertEqual(result["answer"]["skipped_request_type"], "feedback")
        self.assertIn("met the new team", result["answer"]["classifier_reason"].lower())
        self.assertEqual(len(actionable_calls), 1)
        # No Jira write — returned before touching Jira.
        self.assertEqual(request_calls, [])
        self.assertTrue(any(event == "intake_skipped_non_actionable" for event, _ in audit_calls))

    def test_ps_wee_intake_blocks_photo_follow_up_outside_aa_channel(self):
        def boom_request(*args, **kwargs):
            self.fail("photo_follow_up outside AA must be blocked before any Jira call")

        self.module._request_json = boom_request

        result = self.module.create_ps_wee_intake_ticket(
            slack_user_email="psm@staffany.com",
            slack_thread_url="https://staffany.slack.com/archives/C08SDJR03N1/p1779264818954264",
            customer="Andre Cafe",
            issue_summary="photo follow up",
            request_type_key="photo_follow_up",
        )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("AA-only", result["answer"]["message"])

    def test_classify_aa_actionable_intent_returns_decision(self):
        captured = []

        def fake_call(model, system, user_text, tools, tool_name, max_tokens=256):
            captured.append({"model": model, "tool_name": tool_name})
            return {"should_ticket": False, "reason": "Just met the new team, no action."}

        self.module._call_anthropic_messages = fake_call

        skip, reason = self.module._classify_aa_actionable_intent("met the new team, all good")

        self.assertTrue(skip)
        self.assertIn("met the new team", reason.lower())
        self.assertEqual(captured[0]["model"], self.module.AA_ACTIONABLE_CLASSIFIER_MODEL)
        self.assertEqual(captured[0]["tool_name"], "report_aa_followup_intent")

    def test_classify_aa_actionable_intent_creates_when_actionable(self):
        self.module._call_anthropic_messages = lambda *a, **kw: {
            "should_ticket": True,
            "reason": "Wants to expand to more outlets.",
        }

        skip, reason = self.module._classify_aa_actionable_intent("wants to expand more outlets")

        self.assertFalse(skip)
        self.assertIn("expand", reason.lower())

    def test_classify_aa_actionable_intent_rejects_non_boolean(self):
        self.module._call_anthropic_messages = lambda *a, **kw: {
            "should_ticket": "true",
            "reason": "string booleans must not drive a skip",
        }

        skip, reason = self.module._classify_aa_actionable_intent("anything")

        self.assertFalse(skip)
        self.assertEqual(reason, "classifier_error: invalid should_ticket type")

    def test_classify_aa_actionable_intent_fails_closed_on_outage(self):
        def fail(*args, **kwargs):
            raise self.module.JiraError("ANTHROPIC_API_KEY is not configured for the LLM classifier.")

        self.module._call_anthropic_messages = fail

        skip, reason = self.module._classify_aa_actionable_intent("met new team")

        self.assertFalse(skip)
        self.assertIn("classifier_unavailable", reason)

    def test_classify_aa_actionable_intent_empty_text_skips_api(self):
        def boom(*args, **kwargs):
            self.fail("API must not be called for empty trigger text")

        self.module._call_anthropic_messages = boom

        skip, reason = self.module._classify_aa_actionable_intent("")

        self.assertFalse(skip)
        self.assertEqual(reason, "empty trigger text")

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
