import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeMCP:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def tool(self):
        def decorate(func):
            return func

        return decorate

    def run(self, *args, **kwargs):
        return None


def load_hubspot_module():
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp

    module_name = "hubspot_nurtureany_server_under_test"
    sys.modules.pop(module_name, None)
    path = Path(__file__).with_name("hubspot_nurtureany_server.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


SCOPE = {
    "kind": "manager",
    "email": "kerren.fong@staffany.com",
    "countries": ("Singapore", "Malaysia"),
    "owner_id": None,
}


def company_context(company_id="123"):
    return {
        "company": {
            "company_id": company_id,
            "name": "Noci Bakehouse",
            "domain": "noci.example",
            "country": "Singapore",
            "enrichment_status": "not_enriched",
            "missing_fields": ["associated contact", "decision maker", "contract/renewal date"],
        },
        "contacts": [],
        "deals": [],
        "coverage": {
            "contact_count": 0,
            "decision_maker_count": 0,
            "channel_fit_known_count": 0,
        },
    }


class HubSpotNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_hubspot_module()

    def test_classified_sales_rep_maps_to_configured_hubspot_owner(self):
        policy = {
            "sales_reps": [
                {
                    "slack_email": "rep.slack@staffany.com",
                    "hubspot_owner_email": "rep.owner@staffany.com",
                    "countries": ["Singapore"],
                    "active": True,
                }
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(policy, handle)
            policy_path = handle.name

        try:
            with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: policy_path}), patch.object(
                self.module, "_owner_by_email", return_value={"id": "owner-rep", "email": "rep.owner@staffany.com"}
            ) as owner_by_email:
                scope = self.module._caller_scope("rep.slack@staffany.com")
        finally:
            os.unlink(policy_path)

        owner_by_email.assert_called_once_with("rep.owner@staffany.com")
        self.assertEqual(scope["kind"], "ae")
        self.assertEqual(scope["owner_id"], "owner-rep")
        self.assertEqual(scope["hubspot_owner_email"], "rep.owner@staffany.com")
        self.assertEqual(scope["countries"], ("Singapore",))

    def test_unclassified_hubspot_owner_is_blocked(self):
        with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: ""}), patch.object(
            self.module, "_owner_by_email", side_effect=AssertionError("unclassified users must not be looked up as AEs")
        ):
            scope = self.module._caller_scope("owner.but.unclassified@staffany.com")

        self.assertEqual(scope["kind"], "blocked")
        self.assertEqual(scope["email"], "owner.but.unclassified@staffany.com")

    def test_company_search_paginates_past_hubspot_page_limit(self):
        calls = []

        def fake_post(path, body):
            calls.append(body)
            if "after" not in body:
                return {
                    "total": 150,
                    "results": [{"id": str(index), "properties": {"name": f"Account {index}"}} for index in range(100)],
                    "paging": {"next": {"after": "100"}},
                }
            return {
                "total": 150,
                "results": [{"id": str(index), "properties": {"name": f"Account {index}"}} for index in range(100, 150)],
            }

        with patch.object(self.module, "_post", side_effect=fake_post):
            result = self.module._company_search([], limit=200)

        self.assertEqual(len(result["results"]), 150)
        self.assertEqual(result["total"], 150)
        self.assertEqual(result["requested_limit"], 200)
        self.assertEqual(result["returned_count"], 150)
        self.assertFalse(result["truncated"])
        self.assertEqual([call["limit"] for call in calls], [100, 100])

    def test_company_search_marks_requested_limit_truncation(self):
        with patch.object(
            self.module,
            "_post",
            return_value={
                "total": 150,
                "results": [{"id": str(index), "properties": {"name": f"Account {index}"}} for index in range(100)],
                "paging": {"next": {"after": "100"}},
            },
        ):
            result = self.module._company_search([], limit=100)

        self.assertEqual(result["returned_count"], 100)
        self.assertTrue(result["has_more"])
        self.assertTrue(result["truncated"])

    def test_score_uses_target_owner_email_without_overwriting_caller_identity(self):
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_owner_by_email", return_value={"id": "owner-jeremy"}
        ), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [],
                "total": 0,
                "requested_limit": 200,
                "returned_count": 0,
                "has_more": False,
                "truncated": False,
            },
        ) as company_search:
            result = self.module.score_nurture_accounts(
                "kaiyi@staffany.com", countries=["Singapore"], limit=200, owner_email="jeremy.wong@staffany.com"
            )

        filters = company_search.call_args.args[0]
        self.assertIn({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "owner-jeremy"}, filters)
        self.assertEqual(result["scope"]["caller_email"], "kaiyi@staffany.com")
        self.assertEqual(result["scope"]["target_owner_email"], "jeremy.wong@staffany.com")
        self.assertEqual(result["scope"]["target_owner_id"], "owner-jeremy")

    def test_find_contact_gaps_propagates_truncation_metadata(self):
        with patch.object(
            self.module,
            "score_nurture_accounts",
            return_value={
                "answer": [
                    {
                        "company_id": "1",
                        "name": "Capped Account",
                        "country": "Singapore",
                        "enrichment_status": "not_enriched",
                        "missing_fields": ["decision maker"],
                    }
                ],
                "source": "HubSpot account context scoring",
                "scope": {"caller_email": "kaiyi@staffany.com"},
                "confidence": "needs-check",
                "total": 150,
                "requested_limit": 100,
                "returned_count": 100,
                "has_more": True,
                "truncated": True,
                "caveat": "Only 100 of 150 scoped accounts were returned.",
            },
        ):
            result = self.module.find_contact_gaps("kaiyi@staffany.com", limit=100)

        self.assertEqual(result["gap_count"], 1)
        self.assertEqual(result["scored_account_count"], 100)
        self.assertTrue(result["truncated"])
        self.assertIn("Only 100 of 150 scoped accounts were returned", result["caveat"])

    def test_explicit_company_ids_outside_scope_are_blocked(self):
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "ae", "owner_id": "owner-ae"}), patch.object(
            self.module, "_company_context", return_value=None
        ):
            result = self.module.score_nurture_accounts("rep@staffany.com", company_ids=["999"], limit=10)

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("outside caller scope", result["answer"])

    def test_admin_roster_audit_lists_owners_and_classification_counts(self):
        owners = [
            {"id": "owner-1", "email": "rep.owner@staffany.com", "firstName": "Rep", "lastName": "Owner"},
            {"id": "owner-2", "email": "unknown@staffany.com", "firstName": "Unknown", "lastName": "Owner"},
        ]

        def fake_company_search(filters, limit=1):
            owner_filter = [item for item in filters if item.get("propertyName") == "hubspot_owner_id"][0]
            country_filter = [item for item in filters if item.get("propertyName") == "company_country"][0]
            total = 3 if owner_filter["value"] == "owner-1" and country_filter["values"] == ["Singapore"] else 0
            return {"results": [], "total": total, "requested_limit": 1, "returned_count": 0, "has_more": bool(total), "truncated": bool(total)}

        policy = {"sales_reps": [{"slack_email": "rep.slack@staffany.com", "hubspot_owner_email": "rep.owner@staffany.com"}]}
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(policy, handle)
            policy_path = handle.name

        try:
            with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: policy_path}), patch.object(
                self.module, "_caller_scope", return_value={"kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES, "owner_id": None}
            ), patch.object(self.module, "_list_owners", return_value=owners), patch.object(
                self.module, "_company_search", side_effect=fake_company_search
            ):
                result = self.module.audit_hubspot_owner_roster("kaiyi@staffany.com", countries=["Singapore"])
        finally:
            os.unlink(policy_path)

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["owner_count"], 2)
        self.assertEqual(result["answer"]["unclassified_count"], 1)
        self.assertEqual(result["answer"]["owners"][0]["classification"], "sales_rep_owner_email")
        self.assertEqual(result["answer"]["owners"][0]["target_account_counts"]["total"], 3)

    def test_roster_audit_is_admin_only(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_list_owners", side_effect=AssertionError("manager should not list owners")
        ):
            result = self.module.audit_hubspot_owner_roster("kerren.fong@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Only admins", result["answer"])

    def test_generate_free_search_tasks_is_scoped_manual_and_free(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=company_context()
        ):
            result = self.module.generate_free_search_tasks(
                "kerren.fong@staffany.com",
                company_ids=["123"],
                source_types=["company_careers", "linkedin_manual"],
                limit=99,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["scope"]["countries"], ["Singapore", "Malaysia"])
        self.assertEqual(len(result["answer"]), 1)
        account = result["answer"][0]
        self.assertEqual(account["company_id"], "123")
        self.assertEqual([task["source_type"] for task in account["tasks"]], ["company_careers", "linkedin_manual"])
        self.assertTrue(all(task["requires_manual_review"] for task in account["tasks"]))
        self.assertTrue(all(task["will_fetch_automatically"] is False for task in account["tasks"]))
        self.assertIn("No paid API", result["caveat"])

    def test_sales_followup_tasks_are_deduped_owner_filtered_and_safe(self):
        company = {"id": "123", "properties": {"hubspot_owner_id": "owner-sales"}}

        def fake_associations(from_type, object_id, to_type, limit=20):
            self.assertEqual(to_type, "tasks")
            if from_type == "companies":
                return {"ids": ["task-1", "task-2"], "truncated": False, "has_more": False}
            if from_type == "contacts":
                return {"ids": ["task-1", "task-3"], "truncated": False, "has_more": False}
            if from_type == "deals":
                return {"ids": ["task-4"], "truncated": True, "has_more": True}
            return {"ids": [], "truncated": False, "has_more": False}

        def fake_batch_read(object_type, ids, properties):
            self.assertEqual(object_type, "tasks")
            self.assertEqual(ids, ["task-1", "task-2", "task-3", "task-4"])
            self.assertNotIn("hs_task_body", properties)
            return [
                {
                    "id": "task-1",
                    "properties": {
                        "hs_timestamp": "2026-05-10T00:00:00Z",
                        "hs_task_subject": "Follow up after demo",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "NOT_STARTED",
                        "hs_task_priority": "HIGH",
                        "hs_task_type": "CALL",
                        "hs_lastmodifieddate": "2026-05-09T00:00:00Z",
                        "hs_task_body": "Should never be returned",
                    },
                },
                {
                    "id": "task-2",
                    "properties": {
                        "hs_timestamp": "2026-05-11T00:00:00Z",
                        "hs_task_subject": "Completed task",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "COMPLETED",
                    },
                },
                {
                    "id": "task-3",
                    "properties": {
                        "hs_timestamp": "2026-05-12T00:00:00Z",
                        "hs_task_subject": "Other owner",
                        "hubspot_owner_id": "owner-other",
                        "hs_task_status": "NOT_STARTED",
                    },
                },
                {
                    "id": "task-4",
                    "properties": {
                        "hs_timestamp": "2026-05-13T00:00:00Z",
                        "hs_task_subject": "Follow up proposal",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "WAITING",
                    },
                },
            ]

        with patch.object(self.module, "_association_ids_with_metadata", side_effect=fake_associations), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._sales_followup_task_context(company, ["contact-1"], ["deal-1"], task_limit=10)

        self.assertEqual([task["task_id"] for task in result["tasks"]], ["task-1", "task-4"])
        self.assertTrue(result["signals"]["sales_followup_task_truncated"])
        self.assertEqual(result["signals"]["sales_followup_task_count"], 2)
        self.assertEqual(result["signals"]["next_sales_followup_due_at"], "2026-05-10T00:00:00Z")
        self.assertNotIn("hs_task_body", result["tasks"][0])
        self.assertIn({"object_type": "company", "object_id": "123"}, result["tasks"][0]["associated_via"])
        self.assertIn({"object_type": "contact", "object_id": "contact-1"}, result["tasks"][0]["associated_via"])

    def test_list_sales_followup_tasks_filters_due_window(self):
        context = company_context()
        context["company"].update(
            {
                "owner_id": "owner-sales",
                "sales_followup_task_truncated": False,
            }
        )
        context["sales_followup_tasks"] = [
            {
                "task_id": "task-1",
                "due_at": "2026-05-10T00:00:00Z",
                "subject": "Due this week",
                "owner_id": "owner-sales",
                "status": "NOT_STARTED",
                "priority": "HIGH",
                "type": "CALL",
                "last_modified_at": "2026-05-09T00:00:00Z",
                "associated_via": [{"object_type": "company", "object_id": "123"}],
            },
            {
                "task_id": "task-2",
                "due_at": "2026-05-20T00:00:00Z",
                "subject": "Outside window",
                "owner_id": "owner-sales",
                "status": "NOT_STARTED",
                "priority": "LOW",
                "type": "TODO",
                "last_modified_at": "2026-05-09T00:00:00Z",
                "associated_via": [{"object_type": "company", "object_id": "123"}],
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.list_sales_followup_tasks(
                "kerren.fong@staffany.com",
                company_ids=["123"],
                due_start="2026-05-10",
                due_end="2026-05-16",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["returned_task_count"], 1)
        self.assertEqual(result["answer"][0]["task_id"], "task-1")
        self.assertEqual(result["answer"][0]["company_name"], "Noci Bakehouse")
        self.assertNotIn("task_body", result["answer"][0])
        self.assertIn("do not create or mutate tasks", result["caveat"])

    def test_list_sales_followup_tasks_uses_task_search_for_owner_due_window(self):
        task = {
            "id": "task-1",
            "properties": {
                "hs_timestamp": "2026-05-11T09:00:00Z",
                "hs_task_subject": "Call Jeremy account",
                "hubspot_owner_id": "owner-sales",
                "hs_task_status": "NOT_STARTED",
                "hs_task_priority": "HIGH",
                "hs_task_type": "CALL",
                "hs_lastmodifieddate": "2026-05-09T00:00:00Z",
            },
        }
        company = {
            "id": "company-1",
            "properties": {
                "name": "Scoped Account",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_owner_by_email", return_value={"id": "owner-sales"}
        ), patch.object(
            self.module,
            "_task_search",
            return_value={
                "results": [task],
                "total": 1,
                "requested_limit": 20,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ) as task_search, patch.object(
            self.module,
            "_task_company_links_for_tasks",
            return_value={
                "task-1": {
                    "company_ids": ["company-1"],
                    "company_sources": {"company-1": [{"object_type": "company", "object_id": "company-1"}]},
                    "truncated": False,
                },
            },
        ), patch.object(self.module, "_batch_read", return_value=[company]), patch.object(
            self.module, "_company_context", side_effect=AssertionError("account-first scan should not run")
        ):
            result = self.module.list_sales_followup_tasks(
                "kaiyi@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                due_start="2026-05-11",
                due_end="2026-05-17",
                limit=4,
            )

        filters = task_search.call_args.args[0]
        self.assertIn({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "owner-sales"}, filters)
        self.assertIn({"propertyName": "hs_timestamp", "operator": "GTE", "value": "2026-05-11T00:00:00Z"}, filters)
        self.assertIn({"propertyName": "hs_timestamp", "operator": "LTE", "value": "2026-05-17T23:59:59Z"}, filters)
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["task_count"], 1)
        self.assertEqual(result["answer"][0]["task_id"], "task-1")
        self.assertEqual(result["answer"][0]["company_name"], "Scoped Account")

    def test_score_uses_sales_followup_task_signals(self):
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [
                    {
                        "id": "123",
                        "properties": {
                            "name": "Noci Bakehouse",
                            "hs_is_target_account": "true",
                            "company_country": "Singapore",
                            "hubspot_owner_id": "owner-sales",
                            "notes_last_updated": "2026-05-09",
                        },
                    }
                ],
                "total": 1,
                "requested_limit": 20,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_sales_followup_task_context",
            return_value={
                "tasks": [],
                "signals": {
                    "sales_followup_task_count": 1,
                    "overdue_sales_followup_task_count": 1,
                    "next_sales_followup_due_at": "2000-01-01T00:00:00Z",
                    "sales_followup_task_truncated": False,
                    "existing_sales_followup_open": True,
                },
            },
        ):
            result = self.module.score_nurture_accounts("kaiyi@staffany.com", countries=["Singapore"])

        account = result["answer"][0]
        self.assertEqual(account["segment"], "Overdue sales follow-up")
        self.assertEqual(account["sales_followup_task_count"], 1)
        self.assertIn("1 overdue sales follow-up task(s)", account["priority_reasons"])

    def test_review_public_evidence_dedupes_candidates_and_omits_phone(self):
        raw_contacts = [
            {
                "id": "contact-1",
                "properties": {
                    "email": "ada@noci.example",
                    "firstname": "Ada",
                    "lastname": "Ng",
                    "jobtitle": "Owner",
                },
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=company_context()
        ), patch.object(self.module, "_raw_contacts_for_company", return_value=raw_contacts), patch.object(
            self.module,
            "_fetch_public_evidence_text",
            return_value=("Join our team. We are hiring a HR manager for a new outlet.", "fetched"),
        ):
            result = self.module.review_public_enrichment_evidence(
                "kerren.fong@staffany.com",
                "123",
                [
                    {
                        "source_type": "company_careers",
                        "url": "https://noci.example/careers",
                        "title": "Careers",
                        "snippet": "Hiring HR manager",
                        "observed_at": "2026-05-09",
                        "contact_candidate": {
                            "name": "Ada Ng",
                            "title": "Owner",
                            "email": "ada@noci.example",
                            "phone": "+6512345678",
                        },
                    }
                ],
            )

        answer = result["answer"]
        self.assertFalse(answer["will_mutate_hubspot"])
        self.assertEqual(answer["dedupe_summary"]["likely_existing_contact_count"], 1)
        candidate = answer["candidate_contacts"][0]
        self.assertEqual(candidate["dedupe"]["matched_contact_id"], "contact-1")
        self.assertEqual(candidate["omitted_fields"], ["phone"])
        self.assertNotIn("phone", candidate)
        self.assertEqual(answer["company_signals"][0]["signal_type"], "hiring_signal")

    def test_review_public_evidence_does_not_fetch_social_or_gated_sources(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=company_context()
        ), patch.object(self.module, "_raw_contacts_for_company", return_value=[]), patch.object(
            self.module.urllib.request, "urlopen", side_effect=AssertionError("should not fetch social URLs")
        ):
            result = self.module.review_public_enrichment_evidence(
                "kerren.fong@staffany.com",
                "123",
                [
                    {
                        "source_type": "instagram_tiktok_manual",
                        "url": "https://www.instagram.com/noci.bakehouse/",
                        "title": "Noci Instagram",
                        "snippet": "New outlet opening soon. Hiring baristas.",
                    }
                ],
            )

        reviewed = result["answer"]["reviewed_evidence"][0]
        self.assertEqual(reviewed["fetch_status"], "skipped_manual_source")
        self.assertIn("hiring_signal", reviewed["signals_found"])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])

    def test_manager_cannot_create_writeback_preview(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_assert_company_access", side_effect=AssertionError("manager preview should stop before company lookup")
        ):
            result = self.module.plan_hubspot_writeback(
                "kerren.fong@staffany.com",
                [{"company_id": "123", "task": "Review public hiring signal"}],
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("read-only", result["answer"])

    def test_plan_hubspot_writeback_preserves_public_source_metadata(self):
        admin_scope = {"kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES, "owner_id": None}
        with patch.object(self.module, "_caller_scope", return_value=admin_scope), patch.object(
            self.module, "_assert_company_access", return_value={"id": "123", "properties": {"hs_is_target_account": "true", "company_country": "Singapore"}}
        ):
            result = self.module.plan_hubspot_writeback(
                "kerren.fong@staffany.com",
                [
                    {
                        "company_id": "123",
                        "task": "Review public hiring signal",
                        "note_summary": "Careers page suggests active hiring.",
                        "field_updates": {"nurtureany_enrichment_status": "needs_review"},
                        "source_evidence": {"title": "Careers", "observed_at": "2026-05-09"},
                        "source_type": "company_careers",
                        "source_url": "https://noci.example/careers",
                        "confidence": "needs-check",
                    }
                ],
            )

        action = result["answer"]["actions"][0]
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(action["source_type"], "company_careers")
        self.assertEqual(action["source_url"], "https://noci.example/careers")
        self.assertEqual(action["source_evidence"]["title"], "Careers")
        self.assertEqual(action["confidence"], "needs-check")


if __name__ == "__main__":
    unittest.main()
