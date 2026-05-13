import json
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_helpers import load_mcp_module


def load_hubspot_module():
    return load_mcp_module("hubspot_nurtureany_server.py", "hubspot_nurtureany_server_under_test")


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
            "missing_fields": ["associated contact", "decision maker", "contract end date", "current tools"],
        },
        "contacts": [],
        "deals": [],
        "coverage": {
            "contact_count": 0,
            "decision_maker_count": 0,
            "channel_fit_known_count": 0,
        },
    }


def daily_context(company_id="123", contacts=None):
    context = company_context(company_id)
    context["company"].update(
        {
            "name": f"Account {int(company_id):03d}" if str(company_id).isdigit() else "Bubble Tea Lab",
            "country": "Singapore",
            "industry": "Food & Beverage",
            "current_tools": "legacy scheduler",
            "owner_email": "jeremy.wong@staffany.com",
            "owner_name": "Jeremy Wong",
        }
    )
    context["contacts"] = contacts or []
    return context


def daily_context_index(companies, contacts_by_company=None):
    contacts_by_company = contacts_by_company or {}
    return {
        str(company.get("id") or company.get("company_id") or ""): daily_context(
            str(company.get("id") or company.get("company_id") or ""),
            contacts_by_company.get(str(company.get("id") or company.get("company_id") or ""), []),
        )
        for company in companies
    }


JEREMY_SCOPE = {
    "kind": "ae",
    "email": "jeremy.wong@staffany.com",
    "hubspot_owner_email": "jeremy.wong@staffany.com",
    "countries": ("Singapore",),
    "owner_id": "owner-jeremy",
}


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class OperationLedgerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_hubspot_module()

    def test_operation_checkpoint_persists_and_blocks_side_effect_without_idempotency(self):
        with tempfile.TemporaryDirectory() as ledger_dir, patch.dict(os.environ, {"NURTUREANY_OPERATION_LEDGER_DIR": ledger_dir}):
            written = self.module.record_nurtureany_operation_checkpoint(
                operation_id="thread-123-run",
                slack_thread="C123:1710000000.000100",
                phase="before_send",
                checkpoint="Preview approved; send not repeated yet.",
                approval_marker="APPROVED",
                side_effect="eazybe_send",
            )
            loaded = self.module.read_nurtureany_operation_ledger("thread-123-run")

        self.assertEqual(written["confidence"], "verified")
        self.assertEqual(loaded["answer"]["phase"], "before_send")
        self.assertTrue(loaded["answer"]["can_resume_read_only"])
        self.assertFalse(loaded["answer"]["can_repeat_side_effect"])
        self.assertEqual(loaded["confidence"], "needs-check")

    def test_operation_checkpoint_with_idempotency_allows_repeat_side_effect(self):
        with tempfile.TemporaryDirectory() as ledger_dir, patch.dict(os.environ, {"NURTUREANY_OPERATION_LEDGER_DIR": ledger_dir}):
            self.module.record_nurtureany_operation_checkpoint(
                operation_id="thread-123-run",
                slack_thread="C123:1710000000.000100",
                phase="send_started",
                checkpoint="Eazybe send submitted.",
                approval_marker="APPROVED",
                idempotency_key="eazybe-run-1-msg-1",
                side_effect="eazybe_send",
            )
            loaded = self.module.read_nurtureany_operation_ledger("thread-123-run")

        self.assertTrue(loaded["answer"]["can_repeat_side_effect"])
        self.assertEqual(loaded["confidence"], "verified")


class OwnerWhatsAppSentTodayTest(unittest.TestCase):
    def setUp(self):
        self.module = load_hubspot_module()

    def test_counts_owner_whatsapp_today_with_communications_only_fast_path(self):
        companies = [
            {"id": "company-1", "properties": {"name": "Bubble Tea Lab", "company_country": "Singapore", "hubspot_owner_id": "owner-jeremy"}},
            {"id": "company-2", "properties": {"name": "Noci Bakehouse", "company_country": "Singapore", "hubspot_owner_id": "owner-jeremy"}},
        ]

        communication_rows = [
            {
                "id": "comm-1",
                "properties": {
                    "hs_timestamp": "2026-05-13T02:00:00Z",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_communication_channel_type": "WHATS_APP",
                    "hs_communication_logged_from": "Eazybe",
                },
            },
            {
                "id": "comm-2",
                "properties": {
                    "hs_timestamp": "2026-05-13T03:00:00Z",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_communication_channel_type": "WHATSAPP",
                    "hs_communication_logged_from": "CRM",
                },
            },
            {
                "id": "comm-email",
                "properties": {
                    "hs_timestamp": "2026-05-13T05:00:00Z",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_communication_channel_type": "EMAIL",
                },
            },
        ]

        def fake_object_search(object_type, filters, properties, limit=100, maximum=500, sorts=None):
            self.assertEqual(object_type, "communications")
            self.assertNotIn("hs_communication_body", properties)
            return {"results": communication_rows, "total": 3, "returned_count": 3, "has_more": False, "truncated": False}

        def fake_batch_association_ids(from_type, to_type, ids):
            if from_type == "companies" and to_type == "contacts":
                return {"company-1": ["contact-1"], "company-2": ["contact-2"]}
            if from_type == "companies" and to_type == "deals":
                return {"company-1": [], "company-2": ["deal-2"]}
            if from_type == "communications" and to_type == "companies":
                return {"comm-1": ["company-1"], "comm-2": ["company-2"], "comm-email": []}
            if from_type == "communications" and to_type == "contacts":
                return {"comm-1": ["contact-1"], "comm-2": []}
            if from_type == "communications" and to_type == "deals":
                return {"comm-email": ["deal-2"]}
            return {}

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_owner_by_email", return_value={"id": "owner-jeremy", "email": "jeremy.wong@staffany.com"}
        ), patch.object(self.module, "_object_search", side_effect=fake_object_search), patch.object(
            self.module, "_batch_read", side_effect=AssertionError("fast path should not batch-read historical communications")
        ), patch.object(
            self.module,
            "_company_search",
            return_value={"results": companies, "total": 2, "returned_count": 2, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_batch_association_ids", side_effect=fake_batch_association_ids):
            result = self.module.count_owner_whatsapp_sent_today(
                "kerren.fong@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                for_date="2026-05-13",
                countries=["Singapore"],
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["whatsapp_sent_count"], 2)
        self.assertEqual(result["answer"]["target_account_whatsapp_sent_count"], 2)
        self.assertEqual(result["answer"]["target_account_count_scanned"], 2)
        self.assertEqual(result["answer"]["target_account_count_with_whatsapp"], 2)
        self.assertEqual(result["scope"]["fast_path"], "owner_day_communications_first")
        self.assertEqual({row["object_id"] for row in result["answer"]["sample_evidence"]}, {"comm-1", "comm-2"})


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

    def test_kai_yi_slack_email_alias_is_admin(self):
        with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: ""}):
            scopes = [
                self.module._caller_scope("kai.yi@staffany.com"),
                self.module._caller_scope("leekai.yi@staffany.com"),
            ]

        for scope in scopes:
            self.assertEqual(scope["kind"], "admin")
            self.assertEqual(scope["email"], "kaiyi@staffany.com")
            self.assertIn(scope["requested_email"], {"kai.yi@staffany.com", "leekai.yi@staffany.com"})
            self.assertEqual(scope["countries"], self.module.SUPPORTED_COUNTRIES)

    def test_sarah_ayutania_slack_email_is_indonesia_manager(self):
        with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: ""}):
            scope = self.module._caller_scope("sarah.ayutania@staffany.com")

        self.assertEqual(scope["kind"], "manager")
        self.assertEqual(scope["email"], "sarah.ayutania@staffany.com")
        self.assertEqual(scope["countries"], ("Indonesia",))

    def test_runtime_policy_alias_canonicalizes_admin_email(self):
        policy = {"aliases": [{"email": "kaiy@staffany.com", "alias_for": "kaiyi@staffany.com"}]}
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(policy, handle)
            policy_path = handle.name

        try:
            with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: policy_path}):
                scope = self.module._caller_scope("kaiy@staffany.com")
        finally:
            os.unlink(policy_path)

        self.assertEqual(scope["kind"], "admin")
        self.assertEqual(scope["email"], "kaiyi@staffany.com")
        self.assertEqual(scope["requested_email"], "kaiy@staffany.com")
        self.assertEqual(scope["countries"], self.module.SUPPORTED_COUNTRIES)

    def test_runtime_policy_alias_canonicalizes_sales_rep_email(self):
        policy = {
            "sales_reps": [
                {
                    "slack_email": "rep.slack@staffany.com",
                    "slack_email_aliases": ["rep.alias@staffany.com"],
                    "hubspot_owner_email": "rep.owner@staffany.com",
                    "countries": ["Malaysia"],
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
                scope = self.module._caller_scope("rep.alias@staffany.com")
        finally:
            os.unlink(policy_path)

        owner_by_email.assert_called_once_with("rep.owner@staffany.com")
        self.assertEqual(scope["kind"], "ae")
        self.assertEqual(scope["email"], "rep.slack@staffany.com")
        self.assertEqual(scope["requested_email"], "rep.alias@staffany.com")
        self.assertEqual(scope["countries"], ("Malaysia",))

    def test_luma_company_name_match_does_not_match_single_token_plus_generic_suffix(self):
        self.assertFalse(self.module._luma_company_name_matches("Sundays Beach Club", "Sundays Cafe"))

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

    def test_daily_nurture_rotation_splits_150_accounts_into_30_account_weekday_buckets(self):
        companies = [{"id": str(index), "properties": {"name": f"Account {index:03d}"}} for index in range(150)]

        with patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": companies,
                "total": 150,
                "requested_limit": 150,
                "returned_count": 150,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(self.module, "_daily_nurture_contexts", side_effect=lambda selected, scope: daily_context_index(selected)), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            monday = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                material_registry_rows=[],
            )
            tuesday = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-12",
                material_registry_rows=[],
            )

        monday_ids = monday["answer"]["account_rotation"]["selected_company_ids"]
        tuesday_ids = tuesday["answer"]["account_rotation"]["selected_company_ids"]
        self.assertEqual(len(monday_ids), 30)
        self.assertEqual(len(tuesday_ids), 30)
        self.assertEqual(len(set(monday_ids).intersection(tuesday_ids)), 0)
        self.assertEqual(monday_ids[0], "0")
        self.assertEqual(tuesday_ids[0], "30")

    def test_daily_nurture_expands_all_stakeholder_roles_and_surfaces_missing_roles(self):
        contacts = [
            {
                "contact_id": "dm-1",
                "display_name": "Dana D.",
                "persona": "Founder",
                "buying_role": "DECISION_MAKER",
                "is_verified_decision_maker": True,
            },
            {
                "contact_id": "inf-1",
                "display_name": "Ivan I.",
                "persona": "HR Manager",
                "buying_role": "INFLUENCER",
            },
            {
                "contact_id": "champ-1",
                "display_name": "Cheryl C.",
                "persona": "Implementation Sponsor",
                "buying_role": "CHAMPION",
            },
        ]
        material_rows = [
            {
                "material_id": "mat-1",
                "category": "case_study",
                "title": "F&B case study",
                "url": "https://example.com/case",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "food, beverage",
                "concept_tags": "restaurant",
                "persona_tags": "decision_maker, influencer, champion, hr, ops",
                "valid_from": "2026-01-01",
                "valid_until": "2026-12-31",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "similar F&B operators are tightening labour coverage",
                "owner": "RevOps",
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [{"id": "123", "properties": {"name": "Bubble Tea Lab"}}],
                "total": 1,
                "requested_limit": 1,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_daily_nurture_contexts",
            return_value={"123": daily_context("123", contacts)},
        ), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            result = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                protected_pool_size=1,
                daily_account_count=1,
                material_registry_rows=material_rows,
                include_full_payload=True,
            )

        roles = [message["stakeholder_role"] for message in result["answer"]["messages"]]
        self.assertEqual(sorted(roles), ["champion", "decision_maker", "influencer"])
        self.assertEqual(result["answer"]["message_count"], 3)
        self.assertEqual(result["answer"]["role_gaps"], [])

    def test_daily_nurture_persists_run_payload_for_noon_reminder(self):
        contacts = [
            {
                "contact_id": "dm-1",
                "display_name": "Dana D.",
                "persona": "Founder",
                "buying_role": "DECISION_MAKER",
                "is_verified_decision_maker": True,
            }
        ]
        material_rows = [
            {
                "material_id": "mat-1",
                "category": "case_study",
                "title": "F&B case study",
                "url": "https://example.com/case",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "food, beverage",
                "concept_tags": "restaurant",
                "persona_tags": "decision_maker",
                "valid_until": "2026-12-31",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "similar F&B operators are tightening labour coverage",
            }
        ]

        with tempfile.TemporaryDirectory() as runs_dir, patch.dict(
            os.environ, {"NURTUREANY_DAILY_RUNS_DIR": runs_dir}
        ), patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [{"id": "123", "properties": {"name": "Bubble Tea Lab"}}],
                "total": 1,
                "requested_limit": 1,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_daily_nurture_contexts",
            return_value={"123": daily_context("123", contacts)},
        ), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            result = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                protected_pool_size=1,
                daily_account_count=1,
                material_registry_rows=material_rows,
            )

            persistence = result["answer"]["run_persistence"]
            self.assertTrue(persistence["persisted"])
            persisted = json.loads(Path(persistence["path"]).read_text())

        self.assertEqual(persisted["answer"]["run_id"], result["answer"]["run_id"])
        self.assertEqual(persisted["answer"]["message_count"], 1)
        self.assertEqual(result["answer"]["payload_mode"], "compact_slack_packet")
        self.assertNotIn("messages", result["answer"])
        self.assertIn("slack_review_packet", result["answer"])
        self.assertIn("Daily nurture pack", result["answer"]["slack_review_packet"])
        self.assertEqual(
            persisted["answer"]["messages"][0]["message_id"],
            result["answer"]["sample_accounts"][0]["stakeholder_rows"][0]["message_id"],
        )

    def test_daily_nurture_blocks_do_not_contact_from_eazybe_ready_queue(self):
        contacts = [
            {
                "contact_id": "dm-1",
                "display_name": "Dana D.",
                "persona": "Founder",
                "buying_role": "DECISION_MAKER",
                "is_verified_decision_maker": True,
                "contact_confidence": "dont contact",
                "do_not_contact": True,
                "do_not_contact_basis": "NurtureAny contact field marker",
            }
        ]
        material_rows = [
            {
                "material_id": "mat-1",
                "category": "case_study",
                "title": "F&B case study",
                "url": "https://example.com/case",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "food, beverage",
                "concept_tags": "restaurant",
                "persona_tags": "decision_maker",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "similar F&B operators are tightening labour coverage",
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [{"id": "123", "properties": {"name": "Bubble Tea Lab"}}],
                "total": 1,
                "requested_limit": 1,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_daily_nurture_contexts",
            return_value={"123": daily_context("123", contacts)},
        ), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            result = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                protected_pool_size=1,
                daily_account_count=1,
                material_registry_rows=material_rows,
                include_full_payload=True,
            )

        message = result["answer"]["messages"][0]
        self.assertFalse(message["eazybe_ready"])
        self.assertEqual(message["send_status"], "blocked_do_not_contact")
        self.assertEqual(result["answer"]["eazybe_ready_message_count"], 0)
        self.assertEqual(result["answer"]["material_gaps"][0]["reason"], "contact marked do-not-contact")

    def test_daily_nurture_surfaces_missing_role_gaps(self):
        contacts = [
            {
                "contact_id": "dm-1",
                "display_name": "Dana D.",
                "persona": "Founder",
                "buying_role": "DECISION_MAKER",
                "is_verified_decision_maker": True,
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [{"id": "123", "properties": {"name": "Bubble Tea Lab"}}],
                "total": 1,
                "requested_limit": 1,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_daily_nurture_contexts",
            return_value={"123": daily_context("123", contacts)},
        ), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            result = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                protected_pool_size=1,
                daily_account_count=1,
                material_registry_rows=[],
                include_full_payload=True,
            )

        missing_roles = {gap["role"] for gap in result["answer"]["role_gaps"]}
        self.assertEqual(missing_roles, {"influencer", "champion"})
        self.assertEqual(result["answer"]["message_count"], 1)

    def test_daily_nurture_material_matching_prefers_same_industry_and_ignores_expired(self):
        contacts = [
            {
                "contact_id": "dm-1",
                "display_name": "Dana D.",
                "persona": "Founder",
                "buying_role": "DECISION_MAKER",
                "is_verified_decision_maker": True,
            }
        ]
        material_rows = [
            {
                "material_id": "generic",
                "category": "podcast",
                "title": "Generic ops podcast",
                "url": "https://example.com/generic",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "",
                "concept_tags": "",
                "persona_tags": "",
                "valid_until": "2026-12-31",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "operators are improving hiring rhythm",
            },
            {
                "material_id": "same-industry",
                "category": "case_study",
                "title": "Bubble tea labour coverage",
                "url": "https://example.com/bubble-tea",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "food, beverage",
                "concept_tags": "bubble, tea, restaurant",
                "persona_tags": "decision_maker, founder",
                "valid_until": "2026-12-31",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "bubble tea teams are cutting rota gaps",
            },
            {
                "material_id": "expired",
                "category": "case_study",
                "title": "Expired F&B case",
                "url": "https://example.com/expired",
                "status": "active",
                "country_scope": "Singapore",
                "industry_tags": "food, beverage",
                "valid_until": "2026-01-01",
                "template_name": "nurture_material_share_v1",
                "template_params_schema": "first_name,account_name,material_title,material_url",
                "message_hook": "expired",
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value=JEREMY_SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [{"id": "123", "properties": {"name": "Bubble Tea Lab"}}],
                "total": 1,
                "requested_limit": 1,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_daily_nurture_contexts",
            return_value={"123": daily_context("123", contacts)},
        ), patch.object(
            self.module, "_pre_demo_case_study_matches", return_value=[]
        ):
            result = self.module.build_daily_nurture_plan(
                "jeremy.wong@staffany.com",
                for_date="2026-05-11",
                protected_pool_size=1,
                daily_account_count=1,
                material_registry_rows=material_rows,
                include_full_payload=True,
            )

        message = result["answer"]["messages"][0]
        self.assertEqual(message["material"]["material_id"], "same-industry")
        ignored_ids = {row["material_id"] for row in result["answer"]["material_registry"]["ignored_rows"]}
        self.assertIn("expired", ignored_ids)

    def test_company_summary_includes_owner_email_when_available(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Tang Tea House",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "hs_is_target_account": "true",
                "lifecyclestage": "opportunity",
                "hs_num_decision_makers": "5",
                "hs_num_contacts_with_buying_roles": "7",
            },
        }

        with patch.object(
            self.module,
            "_list_owners",
            return_value=[{"id": "owner-jeremy", "email": "jeremy.wong@staffany.com"}],
        ):
            summary = self.module._summarize_company(company)

        self.assertEqual(summary["owner_id"], "owner-jeremy")
        self.assertEqual(summary["owner_email"], "jeremy.wong@staffany.com")
        self.assertEqual(summary["owner_name"], "jeremy.wong@staffany.com")
        self.assertEqual(summary["account_status"], "prospect")
        self.assertEqual(summary["account_status_source"], "HubSpot company lifecyclestage=opportunity")
        self.assertEqual(summary["decision_maker_count"], 5)
        self.assertIn("hs_num_decision_makers", summary["decision_maker_count_source"])
        self.assertIn("Eazybe", summary["eazybe_note"])
        self.assertNotIn("c360_url", summary)

    def test_customer_company_summary_includes_c360_url(self):
        company = {
            "id": "1991281569",
            "properties": {
                "name": "Fei Siong Group",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-kerren",
                "hs_is_target_account": "true",
                "lifecyclestage": "customer",
            },
        }

        with patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_COMPANY_URL_TEMPLATE": "",
                "NURTUREANY_C360_ORG_URL_TEMPLATE": "",
                "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID": "",
            },
        ), patch.object(
            self.module,
            "_list_owners",
            return_value=[{"id": "owner-kerren", "email": "kerren@staffany.com"}],
        ):
            summary = self.module._summarize_company(company)

        self.assertEqual(summary["account_status"], "customer")
        self.assertEqual(
            summary["c360_url"],
            "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group",
        )
        self.assertEqual(summary["customer360_url"], summary["c360_url"])
        self.assertEqual(summary["customer360_route_key"], "fei-siong-group")

    def test_legacy_c360_template_placeholder_uses_route_key(self):
        with patch.dict(
            os.environ,
            {
                "NURTUREANY_C360_COMPANY_URL_TEMPLATE": "https://c360.test/companies/{hubspot_company_id}",
                "NURTUREANY_C360_ORG_URL_TEMPLATE": "https://c360.test/companies/{hubspot_company_id}/orgs/{organisation_id}",
                "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID": "",
            },
        ):
            c360_url = self.module._render_c360_url("1991281569")

        self.assertEqual(c360_url, "https://c360.test/companies/fei-siong-group")

    def test_c360_sales_packet_missing_token_uses_safe_user_caveat(self):
        company = {"account_status": "customer", "company_id": "1991281569", "name": "Fei Siong Group"}

        with patch.dict(os.environ, {self.module.C360_INTERNAL_API_TOKEN_ENV: ""}):
            result = self.module._fetch_c360_sales_packet(company)

        rendered = json.dumps(result)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "missing_token")
        self.assertEqual(result["caveat"], self.module.C360_SALES_PACKET_UNAVAILABLE_CAVEAT)
        self.assertNotIn(self.module.C360_INTERNAL_API_TOKEN_ENV, rendered)

    def test_c360_sales_packet_uses_numeric_company_id_without_route_key(self):
        company = {"account_status": "customer", "company_id": "9003704457", "name": "Stripes Australia"}
        response = FakeHTTPResponse(
            {"status": "ok", "data": {"segment": "customer_on_staffany_payroll", "account": {"companyName": "Stripes Australia"}}}
        )

        with patch.dict(
            os.environ,
            {
                self.module.C360_INTERNAL_API_TOKEN_ENV: "token",
                "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID": "",
            },
        ), patch.object(self.module.urllib.request, "urlopen", return_value=response) as urlopen:
            result = self.module._fetch_c360_sales_packet(company)

        requested_url = urlopen.call_args.args[0].full_url
        self.assertEqual(result["status"], "ok")
        self.assertIn("/api/companies/9003704457/sales-packet", requested_url)

    def test_c360_sales_packet_ignores_unresolved_template_placeholder(self):
        company = {"account_status": "customer", "company_id": "9003704457", "name": "Stripes Australia"}
        response = FakeHTTPResponse(
            {"status": "ok", "data": {"segment": "customer_on_staffany_payroll", "account": {"companyName": "Stripes Australia"}}}
        )

        with patch.dict(
            os.environ,
            {
                self.module.C360_INTERNAL_API_TOKEN_ENV: "token",
                self.module.C360_SALES_PACKET_URL_TEMPLATE_ENV: "${NURTUREANY_C360_SALES_PACKET_URL_TEMPLATE}",
                "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID": "",
            },
        ), patch.object(self.module.urllib.request, "urlopen", return_value=response) as urlopen:
            result = self.module._fetch_c360_sales_packet(company)

        requested_url = urlopen.call_args.args[0].full_url
        self.assertEqual(result["status"], "ok")
        self.assertIn("/api/companies/9003704457/sales-packet", requested_url)

    def test_c360_packet_link_backfills_company_c360_url(self):
        company = {"company_id": "9003704457", "name": "Stripes Australia"}
        self.module._apply_c360_packet_company_link(
            company,
            {"status": "ok", "packet": {"c360Url": "https://customer-360.test/companies/9003704457"}},
        )

        self.assertEqual(company["c360_url"], "https://customer-360.test/companies/9003704457")
        self.assertEqual(company["customer360_url"], company["c360_url"])

    def test_c360_sales_packet_http_error_uses_safe_user_caveat(self):
        company = {"account_status": "customer", "company_id": "1991281569", "name": "Fei Siong Group"}
        http_error = self.module.urllib.error.HTTPError(
            url="https://c360.test/internal/sales-packet",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"error":"Unauthenticated"}'),
        )

        with patch.dict(os.environ, {self.module.C360_INTERNAL_API_TOKEN_ENV: "token"}), patch.object(
            self.module.urllib.request, "urlopen", side_effect=http_error
        ):
            result = self.module._fetch_c360_sales_packet(company)

        rendered = json.dumps(result)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "http_401")
        self.assertEqual(result["caveat"], self.module.C360_SALES_PACKET_UNAVAILABLE_CAVEAT)
        self.assertEqual(result["diagnostic"], {"http_status": 401})
        self.assertNotIn("Unauthenticated", rendered)
        self.assertNotIn(self.module.C360_INTERNAL_API_TOKEN_ENV, rendered)

    def test_decision_maker_coverage_separates_verified_and_role_candidates(self):
        owner = self.module._safe_contact({"id": "1", "properties": {"jobtitle": "Owner", "hs_buying_role": ""}})
        hr_exec = self.module._safe_contact({"id": "2", "properties": {"jobtitle": "HR Executive", "hs_buying_role": ""}})
        buyer = self.module._safe_contact(
            {"id": "3", "properties": {"jobtitle": "Operations Manager", "hs_buying_role": "DECISION_MAKER"}}
        )

        self.assertTrue(owner["is_role_inferred_decision_maker"])
        self.assertFalse(owner["is_verified_decision_maker"])
        self.assertFalse(hr_exec["is_decision_maker"])
        self.assertTrue(buyer["is_verified_decision_maker"])

        props = {"hs_num_decision_makers": "0", "hs_num_contacts_with_buying_roles": "1"}
        coverage = self.module._decision_maker_coverage(props, [owner, hr_exec], 2)
        self.assertEqual(coverage["status"], "needs-check")
        self.assertEqual(coverage["verified_decision_maker_count"], 0)
        self.assertEqual(coverage["role_inferred_decision_maker_candidate_count"], 1)
        self.assertIn("buying_role_contacts_exist_but_none_are_decision_maker", coverage["issues"])
        self.assertIn("decision maker", self.module._missing_company_fields(props, 2, [owner, hr_exec]))

        verified = self.module._decision_maker_coverage(props, [buyer], 1)
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["verified_decision_maker_count"], 1)

    def test_safe_contact_blocks_do_not_contact_marker_in_name(self):
        contact = self.module._safe_contact(
            {
                "id": "4",
                "properties": {
                    "firstname": "Jeanne (dont contact)",
                    "lastname": "Tan",
                    "jobtitle": "Operations Manager",
                    "hs_buying_role": "",
                },
            }
        )

        self.assertTrue(contact["do_not_contact"])
        self.assertIn("contact name", contact["do_not_contact_basis"])

    def test_decision_maker_rollup_without_associated_contact_is_needs_check(self):
        company = {
            "properties": {
                "industry": "F&B",
                "numberofemployees": "50",
                "current_tools": "Excel",
                "contract_end_date": "2026-12-31",
                "hs_num_decision_makers": "1",
                "hs_num_contacts_with_buying_roles": "1",
            }
        }
        coverage = self.module._decision_maker_coverage(company["properties"], [], 0)
        missing = self.module._clean_lead_missing_fields(company, 0, [])

        self.assertEqual(coverage["status"], "needs-check")
        self.assertIn("company_rollup_has_decision_maker_but_no_associated_contact_returned", coverage["issues"])
        self.assertIn("associated contact", missing)
        self.assertNotIn("decision maker", missing)

    def test_singapore_lead_enrichment_flags_rollup_mismatch_and_phone_gap(self):
        companies = [
            {
                "id": "sg-1",
                "properties": {
                    "name": "Rollup Cafe",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "1",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
            {
                "id": "sg-2",
                "properties": {
                    "name": "Callable Diner",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
        ]
        contacts = [
            {
                "id": "c-1",
                "properties": {
                    "firstname": "Hana",
                    "lastname": "Tan",
                    "jobtitle": "HR Manager",
                    "hs_buying_role": "INFLUENCER",
                    "phone": "+6512345678",
                    "nurtureany_phone_verification_status": "called_connected",
                    "nurtureany_phone_verification_source": "manual_call",
                },
            },
            {
                "id": "c-2",
                "properties": {
                    "firstname": "Dion",
                    "lastname": "Lee",
                    "jobtitle": "Director",
                    "hs_buying_role": "DECISION_MAKER",
                    "phone": "+6599999999",
                    "nurtureany_phone_verification_status": "candidate",
                    "nurtureany_phone_verification_source": "truecaller_manual_lookup",
                },
            },
        ]
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore", "Malaysia")}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": companies,
                "total": 2,
                "requested_limit": 30,
                "returned_count": 2,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module, "_batch_association_ids", return_value={"sg-1": ["c-1"], "sg-2": ["c-2"]}
        ), patch.object(
            self.module, "_batch_read", return_value=contacts
        ), patch.object(
            self.module, "_owner_email_by_id", return_value="jeremy.wong@staffany.com"
        ), patch.object(
            self.module, "_owner_name_by_id", return_value="Jeremy Wong"
        ):
            result = self.module.build_singapore_lead_enrichment_plan("kerren.fong@staffany.com")

        rendered = json.dumps(result)
        self.assertNotIn("+6512345678", rendered)
        self.assertNotIn("+6599999999", rendered)
        self.assertEqual(result["answer"]["accounts"][0]["gap_bucket"], "hubspot_rollup_mismatch")
        self.assertIn("hs_num_decision_makers", result["answer"]["accounts"][0]["hubspot_mismatch_notes"][0]["field_level_reason"])
        self.assertEqual(result["answer"]["buckets"]["needs_manual_truecaller_check"][0]["company_id"], "sg-2")
        self.assertEqual(
            result["answer"]["buckets"]["needs_manual_truecaller_check"][0]["provider_waterfall_next_step"],
            "manual_truecaller_call_outcome",
        )
        self.assertEqual(result["answer"]["counts"]["ready_for_whatsapp_batch"], 0)
        self.assertEqual(result["answer"]["provider_waterfall_policy"]["cost_mode"], "capped_effective")

    def test_singapore_lead_enrichment_compact_output_keeps_slack_summary_small(self):
        companies = [
            {
                "id": "sg-compact",
                "properties": {
                    "name": "Compact Cafe",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            }
        ]
        contacts = [
            {
                "id": "compact-dm",
                "properties": {
                    "firstname": "Cara",
                    "lastname": "Lim",
                    "jobtitle": "Director",
                    "hs_buying_role": "DECISION_MAKER",
                    "phone": "+6511111111",
                    "nurtureany_phone_verification_status": "candidate",
                    "nurtureany_phone_verification_source": "truecaller_manual_lookup",
                    "notes_last_contacted": "Very long HubSpot note should not appear in compact Slack output.",
                },
            }
        ]
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore",)}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": companies,
                "total": 1,
                "requested_limit": 5,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module, "_batch_association_ids", return_value={"sg-compact": ["compact-dm"]}
        ), patch.object(
            self.module, "_batch_read", return_value=contacts
        ):
            result = self.module.build_singapore_lead_enrichment_plan(
                "kerren.fong@staffany.com",
                limit=5,
                output_mode="compact",
            )

        account = result["answer"]["accounts"][0]
        rendered = json.dumps(result)
        self.assertEqual(result["answer"]["output_mode"], "compact")
        self.assertEqual(result["answer"]["top_priority_accounts"][0]["company_id"], "sg-compact")
        self.assertEqual(account["company_id"], "sg-compact")
        self.assertEqual(account["recommended_next_source"], "manual_truecaller_call_outcome")
        self.assertIn("provider_waterfall_policy", account)
        self.assertNotIn("people_candidates", account)
        self.assertNotIn("ranked_people_candidates", account)
        self.assertNotIn("+6511111111", rendered)
        self.assertNotIn("Very long HubSpot note", rendered)

    def test_singapore_lead_enrichment_allows_explicit_sg_non_target_and_skips_non_sg(self):
        companies = {
            "sg-non-target": {
                "id": "sg-non-target",
                "properties": {
                    "name": "Selected SG Customer",
                    "hs_is_target_account": "false",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                },
            },
            "my-target": {
                "id": "my-target",
                "properties": {
                    "name": "KL Cafe",
                    "hs_is_target_account": "true",
                    "company_country": "Malaysia",
                    "hubspot_owner_id": "owner-jeremy",
                },
            },
        }

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore", "Malaysia")}), patch.object(
            self.module, "_get_company", side_effect=lambda company_id: companies[company_id]
        ), patch.object(
            self.module, "_batch_association_ids", return_value={"sg-non-target": []}
        ), patch.object(
            self.module, "_batch_read", return_value=[]
        ), patch.object(
            self.module, "_owner_email_by_id", return_value="jeremy.wong@staffany.com"
        ), patch.object(
            self.module, "_owner_name_by_id", return_value="Jeremy Wong"
        ):
            result = self.module.build_singapore_lead_enrichment_plan(
                "kerren.fong@staffany.com",
                company_ids=["sg-non-target", "my-target"],
            )

        self.assertEqual(result["answer"]["accounts"][0]["company_id"], "sg-non-target")
        self.assertFalse(result["answer"]["accounts"][0]["is_target_account"])
        self.assertEqual(result["skipped_company_ids"], [{"company_id": "my-target", "reason": "not_singapore_company"}])

    def test_singapore_lead_enrichment_title_only_candidate_needs_check(self):
        company = {
            "id": "sg-3",
            "properties": {
                "name": "Owner Bistro",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "0",
            },
        }
        contact = {
            "id": "owner-1",
            "properties": {
                "firstname": "Owen",
                "lastname": "Lim",
                "jobtitle": "Owner",
                "hs_buying_role": "",
                "phone": "+6511111111",
                "nurtureany_phone_verification_status": "called_connected",
                "nurtureany_phone_verification_source": "manual_call",
            },
        }

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore",)}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [company],
                "total": 1,
                "requested_limit": 30,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module, "_batch_association_ids", return_value={"sg-3": ["owner-1"]}
        ), patch.object(
            self.module, "_batch_read", return_value=[contact]
        ):
            result = self.module.build_singapore_lead_enrichment_plan("kerren.fong@staffany.com")

        account = result["answer"]["accounts"][0]
        self.assertEqual(account["gap_bucket"], "missing_decision_maker")
        self.assertEqual(account["recommended_next_source"], "exa_people_candidate_discovery")
        self.assertFalse(account["provider_waterfall_policy"]["paid_step_allowed"])
        self.assertEqual(account["verified_decision_maker_count"], 0)
        self.assertEqual(account["ranked_people_candidates"][0]["decision_maker_status"], "needs-check")

    def test_singapore_lead_enrichment_stale_phone_and_whatsapp_draft_only(self):
        stale_company = {
            "id": "sg-stale",
            "properties": {
                "name": "Stale Phone Cafe",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "1",
            },
        }
        ready_company = {
            "id": "sg-ready",
            "properties": {
                "name": "Ready Ramen",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "1",
            },
        }
        contacts = [
            {
                "id": "stale-dm",
                "properties": {
                    "firstname": "Stella",
                    "lastname": "Ng",
                    "jobtitle": "Director",
                    "hs_buying_role": "DECISION_MAKER",
                    "phone": "+6522222222",
                    "nurtureany_phone_verification_status": "called_connected",
                    "nurtureany_phone_verified_at": "2000-01-01",
                    "nurtureany_phone_verification_source": "manual_call",
                },
            },
            {
                "id": "ready-dm",
                "properties": {
                    "firstname": "Rae",
                    "lastname": "Ho",
                    "jobtitle": "Director",
                    "hs_buying_role": "DECISION_MAKER",
                    "phone": "+6533333333",
                    "nurtureany_phone_verification_status": "called_connected",
                    "nurtureany_phone_verification_source": "manual_call",
                },
            },
            {
                "id": "ready-hr",
                "properties": {
                    "firstname": "Helen",
                    "lastname": "Chua",
                    "jobtitle": "HR Manager",
                    "hs_buying_role": "INFLUENCER",
                },
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore",)}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [stale_company, ready_company],
                "total": 2,
                "requested_limit": 30,
                "returned_count": 2,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_batch_association_ids",
            return_value={"sg-stale": ["stale-dm"], "sg-ready": ["ready-dm", "ready-hr"]},
        ), patch.object(
            self.module, "_batch_read", return_value=contacts
        ):
            result = self.module.build_singapore_lead_enrichment_plan("kerren.fong@staffany.com", batch_size=30)

        by_id = {row["company_id"]: row for row in result["answer"]["accounts"]}
        self.assertEqual(by_id["sg-stale"]["gap_bucket"], "missing_verified_phone")
        self.assertEqual(by_id["sg-stale"]["phone_verification_summary"]["stale_phone_count"], 1)
        self.assertEqual(by_id["sg-stale"]["recommended_next_source"], "manual_truecaller_call_outcome")
        self.assertEqual(by_id["sg-ready"]["gap_bucket"], "nurture_ready")
        self.assertEqual(by_id["sg-ready"]["recommended_next_source"], "whatsapp_batch_draft")
        self.assertFalse(by_id["sg-ready"]["provider_waterfall_policy"]["paid_step_allowed"])
        whatsapp = result["answer"]["ready_for_whatsapp_batch"]
        self.assertTrue(whatsapp["draft_only"])
        self.assertTrue(whatsapp["no_auto_send"])
        self.assertEqual(whatsapp["accounts"][0]["company_id"], "sg-ready")
        self.assertIn("Knowledge / Network / Support", whatsapp["kns_framework"])

    def test_singapore_lead_enrichment_provider_waterfall_policy_cost_effective(self):
        companies = [
            {
                "id": "sg-no-contact",
                "properties": {
                    "name": "No Contact Cafe",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "0",
                },
            },
            {
                "id": "sg-title-only",
                "properties": {
                    "name": "Title Only Bistro",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "0",
                },
            },
            {
                "id": "sg-paid-gap",
                "properties": {
                    "name": "Paid Gap Kitchen",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
            {
                "id": "sg-prospeo-candidate",
                "properties": {
                    "name": "Prospeo Candidate Grill",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
        ]
        contacts = [
            {
                "id": "title-owner",
                "properties": {
                    "firstname": "Tara",
                    "lastname": "Ong",
                    "jobtitle": "Owner",
                    "hs_buying_role": "",
                    "phone": "+6544444444",
                    "nurtureany_phone_verification_status": "called_connected",
                    "nurtureany_phone_verification_source": "manual_call",
                },
            },
            {
                "id": "paid-dm",
                "properties": {
                    "firstname": "Paula",
                    "lastname": "Lim",
                    "jobtitle": "Director",
                    "hs_buying_role": "DECISION_MAKER",
                },
            },
            {
                "id": "prospeo-dm",
                "properties": {
                    "firstname": "Priya",
                    "lastname": "Rao",
                    "jobtitle": "Managing Director",
                    "hs_buying_role": "DECISION_MAKER",
                    "phone": "+6555555555",
                    "nurtureany_phone_verification_status": "candidate",
                    "nurtureany_phone_verification_source": "prospeo_manual",
                },
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Singapore",)}), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": companies,
                "total": 4,
                "requested_limit": 30,
                "returned_count": 4,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_batch_association_ids",
            return_value={
                "sg-no-contact": [],
                "sg-title-only": ["title-owner"],
                "sg-paid-gap": ["paid-dm"],
                "sg-prospeo-candidate": ["prospeo-dm"],
            },
        ), patch.object(
            self.module, "_batch_read", return_value=contacts
        ):
            result = self.module.build_singapore_lead_enrichment_plan("kerren.fong@staffany.com")

        by_id = {row["company_id"]: row for row in result["answer"]["accounts"]}
        self.assertEqual(by_id["sg-no-contact"]["recommended_next_source"], "tavily_public_company_job_board_research")
        self.assertFalse(by_id["sg-no-contact"]["provider_waterfall_policy"]["paid_step_allowed"])

        self.assertEqual(by_id["sg-title-only"]["recommended_next_source"], "exa_people_candidate_discovery")
        self.assertFalse(by_id["sg-title-only"]["provider_waterfall_policy"]["paid_step_allowed"])

        paid_gap = by_id["sg-paid-gap"]
        self.assertEqual(paid_gap["gap_bucket"], "missing_verified_phone")
        self.assertIn("needs_paid_reveal", paid_gap["secondary_buckets"])
        self.assertEqual(paid_gap["recommended_next_source"], "lusha_prospeo_parallel_search_pilot")
        self.assertTrue(paid_gap["provider_waterfall_policy"]["paid_step_allowed"])
        self.assertEqual(paid_gap["provider_waterfall_policy"]["paid_parallel_test"]["providers"], ["lusha", "prospeo"])

        prospeo_candidate = by_id["sg-prospeo-candidate"]
        self.assertEqual(prospeo_candidate["gap_bucket"], "needs_manual_truecaller_check")
        self.assertEqual(prospeo_candidate["phone_verification_summary"]["verified_phone_count"], 0)
        self.assertEqual(prospeo_candidate["recommended_next_source"], "manual_truecaller_call_outcome")

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

    def test_company_context_returns_owner_calendar_and_contact_coverage_sources(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Tunglok Group",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "lifecyclestage": "opportunity",
                "hs_num_decision_makers": "5",
                "hs_num_contacts_with_buying_roles": "7",
            },
        }
        contacts = [
            {
                "id": "contact-1",
                "properties": {
                    "email": "ada@tunglok.com",
                    "firstname": "Ada",
                    "lastname": "Ng",
                    "jobtitle": "Owner",
                    "hs_buying_role": "",
                },
            }
        ]
        with patch.object(self.module, "_get_company", return_value=company), patch.object(
            self.module, "_association_ids", side_effect=[["contact-1"], []]
        ), patch.object(self.module, "_batch_read", side_effect=[contacts, []]), patch.object(
            self.module, "_sales_followup_task_context", return_value={"tasks": [], "signals": {}}
        ), patch.object(
            self.module,
            "_owner_by_id",
            return_value={"id": "owner-jeremy", "email": "jeremy.wong@staffany.com", "firstName": "Jeremy", "lastName": "Wong"},
        ):
            context = self.module._company_context("123", {**SCOPE, "kind": "admin", "countries": ("Singapore",)})

        company_summary = context["company"]
        self.assertEqual(company_summary["owner_name"], "Jeremy Wong")
        self.assertEqual(company_summary["owner_email"], "jeremy.wong@staffany.com")
        self.assertEqual(company_summary["account_status"], "prospect")
        self.assertNotIn("c360_url", company_summary)
        self.assertEqual(company_summary["calendar_scan_instruction"]["calendar_ids"], ["jeremy.wong@staffany.com"])
        audit_seed = company_summary["calendar_audit_seed"]
        self.assertEqual(audit_seed["company_id"], "123")
        self.assertEqual(audit_seed["company_name"], "Tunglok Group")
        self.assertEqual(audit_seed["calendar_ids"], ["jeremy.wong@staffany.com"])
        self.assertEqual(audit_seed["contact_match_records"][0]["email_domain"], "tunglok.com")
        self.assertEqual(audit_seed["contact_match_records"][0]["email_hash"], self.module._hash_email("ada@tunglok.com"))
        self.assertFalse(audit_seed["contact_match_records"][0]["is_verified_decision_maker"])
        self.assertTrue(audit_seed["contact_match_records"][0]["is_role_inferred_decision_maker"])
        self.assertIn("industry", audit_seed["missing_clean_lead_fields"])
        self.assertIn("headcount", audit_seed["missing_clean_lead_fields"])
        self.assertIn("current tools", audit_seed["missing_clean_lead_fields"])
        self.assertIn("contract end date", audit_seed["missing_clean_lead_fields"])
        self.assertNotIn("associated_contact", audit_seed["missing_clean_lead_fields"])
        self.assertNotIn("verified_decision_maker", audit_seed["missing_clean_lead_fields"])
        self.assertNotIn("ada@tunglok.com", json.dumps(audit_seed))
        self.assertEqual(context["coverage"]["decision_maker_count_from_hubspot_property"], 5)
        self.assertEqual(context["coverage"]["decision_maker_count_from_contact_roles"], 0)
        self.assertEqual(context["coverage"]["role_inferred_decision_maker_count"], 1)
        self.assertIn("hs_num_contacts_with_buying_roles", context["coverage"]["sources"]["buying_role_contact_count_source"])

    def test_get_account_context_marks_customer360_link_source_for_customers(self):
        context = {
            "company": {
                "country": "Singapore",
                "missing_fields": [],
                "c360_url": "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group",
            },
            "coverage": {"decision_maker_coverage": {"status": "verified"}},
        }
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin"}), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.get_account_context("kaiyi@staffany.com", "1991281569")

        self.assertIn("Customer 360 link", result["source"])
        self.assertEqual(result["answer"]["company"]["c360_url"], context["company"]["c360_url"])

    def test_payroll_customer_account_packet_suppresses_stale_hubspot_sections(self):
        context = company_context("1991281569")
        context["company"].update(
            {
                "name": "Fei Siong Group",
                "account_status": "customer",
                "owner_name": "Kerren Fong",
                "current_tools": "Infotech",
                "contract_end_date": "2025-10-01",
                "last_activity_at": "2026-05-06T00:00:00.000Z",
                "c360_url": "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group",
            }
        )
        context["deals"] = [{"dealname": "Stale deal"}]
        context["sales_followup_tasks"] = [{"subject": "Open Follow-Up Task"}]
        c360_packet = {
            "status": "ok",
            "packet": {
                "segment": "customer_on_staffany_payroll",
                "c360Url": "https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group",
                "account": {
                    "companyName": "Fei Siong Group",
                    "accountOwner": "Kerren Fong",
                    "psmOwner": "Josica",
                },
                "staffany": {
                    "ownedProducts": ["StaffAny", "Payroll", "EngageAny"],
                    "missingProducts": ["HRAny", "Claims"],
                    "activeUsage": {"summary": "4 mapped StaffAny orgs; 1,486 active headcount"},
                },
                "crossSellSignals": ["Consider missing StaffAny modules: HRAny, Claims"],
                "verifiedPics": [
                    {
                        "name": "Samantha Lin",
                        "title": "Senior VP",
                        "verificationBasis": ["HubSpot operation_pic = Yes"],
                    }
                ],
                "minimalGaps": [],
            },
        }

        packet = self.module._build_account_packet(context, c360_packet)
        rendered = packet["slack_markdown"]

        self.assertEqual(packet["segment"], "customer_on_staffany_payroll")
        self.assertIn("<https://customer-360-qv4r5xkisq-as.a.run.app/companies/fei-siong-group|Fei Siong Group>", rendered)
        self.assertIn("current customer on StaffAny Payroll", rendered)
        self.assertNotIn("Infotech", rendered)
        self.assertNotIn("2025-10-01", rendered)
        self.assertNotIn("Last activity", rendered)
        self.assertNotIn("Deals", rendered)
        self.assertNotIn("Open Follow-Up", rendered)
        self.assertNotIn("IC-BANT", rendered)
        self.assertNotIn("Payroll conversion", rendered)

    def test_non_payroll_customer_account_packet_focuses_payroll_conversion(self):
        context = company_context("8051493928")
        context["company"].update(
            {
                "name": "Rock Productions Pte Ltd",
                "account_status": "customer",
                "owner_name": "Account Owner",
                "current_tools": "Infotech",
                "c360_url": "https://customer-360-qv4r5xkisq-as.a.run.app/companies/rock-productions",
            }
        )
        c360_packet = {
            "status": "ok",
            "packet": {
                "segment": "customer_not_on_staffany_payroll",
                "c360Url": "https://customer-360-qv4r5xkisq-as.a.run.app/companies/rock-productions",
                "account": {
                    "companyName": "Rock Productions Pte Ltd",
                    "accountOwner": "Account Owner",
                    "psmOwner": "PSM",
                },
                "staffany": {
                    "ownedProducts": ["StaffAny"],
                    "activeUsage": {"summary": "1 mapped StaffAny org"},
                },
                "crossSellSignals": ["Payroll conversion opportunity: no StaffAny Payroll evidence in C360"],
                "verifiedPics": [],
                "minimalGaps": ["External HRIS/payroll is not sourced in C360."],
            },
        }

        packet = self.module._build_account_packet(context, c360_packet)
        rendered = packet["slack_markdown"]

        self.assertEqual(packet["segment"], "customer_not_on_staffany_payroll")
        self.assertIn("Payroll conversion hook", rendered)
        self.assertIn("Infotech (Source: HubSpot current_tools)", rendered)
        self.assertNotIn("Deals", rendered)
        self.assertEqual(len(packet["minimal_gaps"]), 1)

    def test_prospect_account_packet_uses_qualification_brief_with_one_gap_line(self):
        context = company_context("123")
        context["company"].update(
            {
                "name": "Noci Bakehouse",
                "account_status": "prospect",
                "industry": "F&B",
                "headcount": "80",
                "current_tools": "Excel",
                "contract_end_date": "2026-11-30",
                "missing_fields": ["decision maker", "associated contact", "channel fit"],
            }
        )

        packet = self.module._build_account_packet(context, {"status": "skipped"})
        rendered = packet["slack_markdown"]

        self.assertEqual(packet["segment"], "prospect")
        self.assertIn("Segment: prospect", rendered)
        self.assertIn("ICP fit: F&B industry, 80 headcount, Singapore", rendered)
        self.assertIn("Current HRIS/payroll: Excel (Source: HubSpot current_tools)", rendered)
        self.assertIn("Next discovery ask", rendered)
        self.assertEqual(len(packet["minimal_gaps"]), 1)
        self.assertNotIn("Other Contacts", rendered)

    def test_find_contact_gaps_propagates_truncation_metadata(self):
        company = {
            "id": "1",
            "properties": {
                "name": "Capped Account",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-1",
                "numberofemployees": "50",
                "industry": "F&B",
                "contract_end_date": "2026-12-31",
                "current_tools": "Excel",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "1",
            },
        }
        contacts = [{"id": "contact-1", "properties": {"jobtitle": "Owner", "hs_buying_role": ""}}]
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": [company],
                "total": 150,
                "requested_limit": 100,
                "returned_count": 100,
                "has_more": True,
                "truncated": True,
            },
        ), patch.object(self.module, "_batch_association_ids", return_value={"1": ["contact-1"]}), patch.object(
            self.module, "_batch_read", return_value=contacts
        ), patch.object(self.module, "_owner_email_by_id", return_value="ae@example.com"), patch.object(
            self.module, "_owner_name_by_id", return_value="AE"
        ):
            result = self.module.find_contact_gaps("kaiyi@staffany.com", limit=100)

        self.assertEqual(result["gap_count"], 1)
        self.assertEqual(result["scored_account_count"], 100)
        self.assertTrue(result["truncated"])
        self.assertIn("Only 100 of 150 scoped accounts were returned", result["caveat"])
        self.assertIn("decision maker", result["answer"][0]["missing_fields"])
        self.assertEqual(result["answer"][0]["role_inferred_decision_maker_candidate_count"], 1)

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

    def test_sales_metric_qo_for_jeremy_in_april_builds_bigquery_sql(self):
        admin_scope = {"kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES, "owner_id": None}
        with patch.object(self.module, "_caller_scope", return_value=admin_scope), patch.object(
            self.module,
            "_owner_by_email",
            return_value={"id": "owner-jeremy", "email": "jeremy.wong@staffany.com", "firstName": "Jeremy", "lastName": "Wong"},
        ):
            result = self.module.build_sales_metric_actuals_query(
                "kaiyi@staffany.com",
                metric="qo_set",
                start_date="2026-04-01",
                end_date="2026-04-30",
                owner_email="jeremy.wong@staffany.com",
            )

        self.assertEqual(result["confidence"], "verified")
        answer = result["answer"]
        self.assertEqual(answer["execute_with"], "staffany_bigquery.execute_sql_readonly")
        self.assertEqual(answer["source_table"], "staffany-warehouse.analytics.fct_sales_points")
        self.assertIn("SUM(qo_set)", answer["sql"])
        self.assertIn("DATE '2026-04-01'", answer["sql"])
        self.assertIn("DATE '2026-04-30'", answer["sql"])
        self.assertIn("'owner-jeremy'", answer["sql"])
        self.assertEqual(result["scope"]["target_owner_email"], "jeremy.wong@staffany.com")

    def test_sales_metric_my_qo_uses_caller_owner_scope(self):
        ae_scope = {
            "kind": "ae",
            "email": "rep@staffany.com",
            "countries": ("Singapore",),
            "owner_id": "owner-ae",
            "hubspot_owner_email": "rep.owner@staffany.com",
        }
        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module,
            "_list_owners",
            return_value=[{"id": "owner-ae", "email": "rep.owner@staffany.com", "firstName": "Rep", "lastName": "Owner"}],
        ), patch.object(
            self.module, "build_friday_sales_review", side_effect=AssertionError("direct QO metric must not call Friday review")
        ):
            result = self.module.build_sales_metric_actuals_query(
                "rep@staffany.com",
                metric="qo",
                start_date="2026-05-01",
                end_date="2026-05-11",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("'owner-ae'", result["answer"]["sql"])
        self.assertEqual(result["scope"]["target_owner_id"], "owner-ae")

    def test_sales_metric_ae_cannot_query_another_owner(self):
        ae_scope = {"kind": "ae", "email": "rep@staffany.com", "countries": ("Singapore",), "owner_id": "owner-ae"}
        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module, "_owner_by_email", return_value={"id": "owner-other", "email": "other@staffany.com"}
        ):
            result = self.module.build_sales_metric_actuals_query(
                "rep@staffany.com",
                metric="qo_set",
                start_date="2026-04-01",
                end_date="2026-04-30",
                owner_email="other@staffany.com",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("another owner's revenue metrics", result["answer"])

    def test_sales_metric_manager_qo_uses_access_policy_team_owner_ids(self):
        policy = {
            "sales_reps": [
                {
                    "slack_email": "sg.rep@staffany.com",
                    "hubspot_owner_email": "sg.owner@staffany.com",
                    "countries": ["Singapore"],
                    "active": True,
                },
                {
                    "slack_email": "id.rep@staffany.com",
                    "hubspot_owner_email": "id.owner@staffany.com",
                    "countries": ["Indonesia"],
                    "active": True,
                },
            ]
        }
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(policy, handle)
            policy_path = handle.name

        def owner_by_email(email):
            return {
                "sg.owner@staffany.com": {"id": "owner-sg", "email": "sg.owner@staffany.com"},
                "id.owner@staffany.com": {"id": "owner-id", "email": "id.owner@staffany.com"},
            }.get(email)

        try:
            with patch.dict(os.environ, {self.module.ACCESS_POLICY_ENV_VAR: policy_path}), patch.object(
                self.module,
                "_caller_scope",
                return_value={"kind": "manager", "email": "kerren.fong@staffany.com", "countries": ("Singapore", "Malaysia"), "owner_id": None},
            ), patch.object(self.module, "_owner_by_email", side_effect=owner_by_email):
                result = self.module.build_sales_metric_actuals_query(
                    "kerren.fong@staffany.com",
                    metric="qo_set",
                    start_date="2026-05-01",
                    end_date="2026-05-11",
                    countries=["Singapore"],
                )
        finally:
            os.unlink(policy_path)

        self.assertEqual(result["confidence"], "verified")
        self.assertIn("'owner-sg'", result["answer"]["sql"])
        self.assertNotIn("'owner-id'", result["answer"]["sql"])

    def test_sales_metric_ambiguous_new_arr_returns_clarification_without_sql(self):
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}):
            result = self.module.build_sales_metric_actuals_query(
                "kaiyi@staffany.com",
                metric="new ARR",
                start_date="2026-05-01",
                end_date="2026-05-11",
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["sql"], "")
        self.assertEqual(
            result["answer"]["clarification_options"],
            ["signed_converted_arr", "paid_converted_arr", "new_mrr_movement_arr"],
        )

    def test_hubspot_revenue_funnel_applies_created_cohort_and_outbound_rules(self):
        deals = [
            {
                "id": "deal-1",
                "properties": {
                    "dealname": "Noci new business",
                    "createdate": "2026-05-03T01:00:00Z",
                    "pipeline": "new-pipe",
                    "dealstage": "qo-stage",
                    "amount": "1000",
                    "appointment_set_channel": "Sales Outbound",
                },
            },
            {
                "id": "deal-2",
                "properties": {
                    "dealname": "Retail signed",
                    "createdate": "2026-05-04T01:00:00Z",
                    "closedate": "2026-05-08T01:00:00Z",
                    "pipeline": "new-pipe",
                    "dealstage": "closed-won",
                    "amount": "3000",
                    "appointment_set_channel": "Sales Outbound",
                },
            },
            {
                "id": "deal-renewal",
                "properties": {
                    "dealname": "Renewal",
                    "createdate": "2026-05-05T01:00:00Z",
                    "pipeline": "renewal-pipe",
                    "dealstage": "closed-won",
                    "amount": "9000",
                    "appointment_set_channel": "Sales Outbound",
                },
            },
        ]
        companies = [
            {"id": "company-1", "properties": {"name": "Noci", "company_country": "Singapore", "numberofemployees": "30", "industry": "Food & Beverage"}},
            {"id": "company-2", "properties": {"name": "Retail Co", "company_country": "Singapore", "numberofemployees": "80", "industry": "Retail"}},
            {"id": "company-3", "properties": {"name": "Old Co", "company_country": "Singapore", "numberofemployees": "80", "industry": "Retail"}},
        ]
        with patch.dict(
            os.environ,
            {
                self.module.REVENUE_FUNNEL_NEW_BUSINESS_PIPELINE_IDS_ENV_VAR: "new-pipe",
                self.module.REVENUE_FUNNEL_RENEWAL_PIPELINE_IDS_ENV_VAR: "renewal-pipe",
                self.module.QO_PIPELINE_IDS_ENV_VAR: "new-pipe",
                self.module.QO_STAGE_IDS_ENV_VAR: "qo-stage",
                self.module.QO_MET_STAGE_IDS_ENV_VAR: "qo-met",
                self.module.CLOSED_WON_STAGE_IDS_ENV_VAR: "closed-won",
            },
        ), patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_deal_search", return_value={"results": deals, "total": 3, "requested_limit": 250, "returned_count": 3, "has_more": False, "truncated": False}
        ), patch.object(
            self.module,
            "_batch_association_ids",
            return_value={"deal-1": ["company-1"], "deal-2": ["company-2"], "deal-renewal": ["company-3"]},
        ), patch.object(self.module, "_batch_read", return_value=companies):
            result = self.module.build_hubspot_revenue_funnel_metrics(
                "kaiyi@staffany.com",
                start_date="2026-05-01",
                end_date="2026-05-31",
                countries=["Singapore"],
                headcount_range=">20",
            )

        self.assertEqual(result["answer"]["summary"]["created_deal_count"], 2)
        self.assertEqual(result["answer"]["summary"]["qo_count"], 2)
        self.assertEqual(result["answer"]["summary"]["signed_deal_count"], 1)
        self.assertEqual(result["answer"]["excluded_counts"]["renewal"], 1)
        self.assertFalse(result["will_mutate_hubspot"])

    def test_ae_coaching_audit_returns_metadata_only_sheet_preview(self):
        companies = [{"id": "company-1", "properties": {"name": "Noci", "hubspot_owner_id": "owner-1"}}]
        activity_index = {
            "company-1": {
                "evidence": [
                    {"object_type": "communication", "timestamp": "2026-05-05T01:30:00Z"},
                    {"object_type": "call", "object_id": "call-1", "owner_id": "owner-1", "timestamp": "2026-05-05T03:00:00Z", "duration_seconds": 90},
                ]
            }
        }
        coverage = {
            "answer": {
                "owners": [
                    {
                        "owner_id": "owner-1",
                        "owner_email": "ae@example.com",
                        "owner_name": "AE",
                        "weekly_account_target": 1,
                        "120_150_accounts_worked": "1/1 worked; target 1/150",
                        "connected_call_count": 12,
                    }
                ]
            },
            "_internal": {
                "companies": companies,
                "company_deal_ids": {},
                "activity_index": activity_index,
                "week": {"week_start": "2026-05-04", "week_end": "2026-05-10"},
            },
            "scope": {"caller_email": "kerren.fong@staffany.com", "countries": ["Singapore"], "week_start": "2026-05-04", "week_end": "2026-05-10"},
            "requested_limit": 1000,
            "has_more": False,
            "truncated": False,
            "confidence": "verified",
        }
        deal_counts = {"configured": True, "by_owner": {"owner-1": {"qos": 2}}, "totals": {}}
        with patch.object(self.module, "_priority_account_coverage", return_value=coverage) as coverage_mock, patch.object(
            self.module, "_deal_counts_for_friday", return_value=deal_counts
        ):
            result = self.module.build_ae_coaching_audit(
                "kerren.fong@staffany.com",
                include_call_content=True,
                limit=1000,
                soft_timeout_seconds=0,
            )

        coverage_kwargs = coverage_mock.call_args.kwargs
        self.assertEqual(coverage_kwargs["limit"], self.module.AE_COACHING_DEFAULT_LIMIT)
        self.assertEqual(coverage_kwargs["soft_timeout_seconds"], self.module.AE_COACHING_DEFAULT_SOFT_TIMEOUT_SECONDS)
        self.assertFalse(result["answer"]["will_mutate_google_sheets"])
        self.assertEqual(result["answer"]["one_on_one_sheet_preview_rows"][0]["QO set"], 2)
        self.assertEqual(result["answer"]["ae_weekly_checks"][0]["call_content_status"], "metadata-only needs-check")
        self.assertEqual(len(result["answer"]["ae_weekly_checks"][0]["long_call_without_appointment_candidates"]), 1)

    def test_ae_coaching_audit_owner_fast_path_returns_preview_without_fanout(self):
        company_data = {
            "results": [{"id": "company-1", "properties": {"name": "Noci", "hubspot_owner_id": "owner-1"}}],
            "total": 1,
            "requested_limit": 150,
            "returned_count": 1,
            "has_more": False,
            "truncated": False,
        }
        calls = [
            {
                "id": "call-1",
                "properties": {
                    "hs_timestamp": "2026-05-05T03:00:00Z",
                    "hubspot_owner_id": "owner-1",
                    "hs_call_status": "COMPLETED",
                    "hs_call_duration": "130000",
                },
            }
        ]
        communications = [
            {
                "id": "comm-1",
                "properties": {
                    "hs_timestamp": "2026-05-05T01:30:00Z",
                    "hubspot_owner_id": "owner-1",
                    "hs_communication_channel_type": "WHATS_APP",
                },
            }
        ]

        def object_search(object_type, *_args, **_kwargs):
            if object_type == "calls":
                return {"results": calls, "total": 1, "requested_limit": 500, "returned_count": 1, "has_more": False, "truncated": False}
            return {"results": communications, "total": 1, "requested_limit": 500, "returned_count": 1, "has_more": False, "truncated": False}

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("owner-1", "ae@example.com")
        ), patch.object(self.module, "_owner_lookup_by_id", return_value={"owner-1": {"id": "owner-1", "email": "ae@example.com", "firstName": "AE"}}), patch.object(
            self.module, "_company_search", return_value=company_data
        ) as company_search_mock, patch.object(
            self.module, "_object_search", side_effect=object_search
        ), patch.object(
            self.module, "_friday_review_stage_config", return_value={"configured": False}
        ), patch.object(
            self.module, "_priority_account_coverage"
        ) as coverage_mock:
            result = self.module.build_ae_coaching_audit(
                "kaiyi@staffany.com",
                countries=["Singapore"],
                owner_email="ae@example.com",
                week_start="2026-05-04",
                week_end="2026-05-10",
                limit=1000,
                soft_timeout_seconds=0,
            )

        coverage_mock.assert_not_called()
        self.assertEqual(company_search_mock.call_args.args[1], self.module.AE_COACHING_DEFAULT_LIMIT)
        self.assertFalse(result["answer"]["will_mutate_google_sheets"])
        self.assertEqual(result["answer"]["ae_weekly_checks"][0]["connected_call_count"], 1)
        self.assertEqual(result["answer"]["one_on_one_sheet_preview_rows"][0]["QO set"], "needs-check")
        self.assertEqual(result["scope"]["owner_scoped_fast_path"], True)

    def test_sales_navigator_queue_is_manual_and_scoped(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Noci",
                "company_country": "Singapore",
                "industry": "Restaurant",
                "hubspot_owner_id": "owner-1",
                "hs_is_target_account": "true",
            },
        }
        contact = {
            "id": "contact-1",
            "properties": {
                "firstname": "Ana",
                "lastname": "Tan",
                "jobtitle": "HR Director",
                "hs_buying_role": "",
            },
        }
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_assert_company_access", return_value=company
        ), patch.object(self.module, "_association_ids", return_value=["contact-1"]), patch.object(self.module, "_batch_read", return_value=[contact]):
            result = self.module.prepare_sales_navigator_decision_maker_queue(
                "kaiyi@staffany.com",
                mode="post_event_top10",
                company_ids=["company-1"],
                countries=["Singapore"],
            )

        self.assertFalse(result["answer"]["linkedin_scraping"])
        self.assertFalse(result["answer"]["sales_navigator_browser_actions"])
        self.assertEqual(result["answer"]["queue"][0]["priority_reason"], "director")
        self.assertEqual(result["answer"]["exa_cost_report"]["status"], "not_called")

    def test_friday_review_returns_hygiene_plus_warehouse_qo_followup_query(self):
        companies = [
            {
                "id": "company-1",
                "properties": {
                    "name": "Account One",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-1",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "0",
                },
            },
            {
                "id": "company-2",
                "properties": {
                    "name": "Account Two",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-1",
                    "hs_num_decision_makers": "1",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
        ]
        coverage = {
            "answer": {
                "owners": [
                    {
                        "owner_id": "owner-1",
                        "owner_email": "ae@example.com",
                        "locked_pool_count": 2,
                        "weekly_account_target": 2,
                        "worked_account_count": 2,
                        "120_150_accounts_worked": "2/2 worked; target 2/150",
                        "coverage_hit_miss": "hit",
                        "double_tapped_account_count": 2,
                        "single_touch_account_count": 0,
                        "untouched_account_count": 0,
                        "stale_account_count": 0,
                        "dirty_account_count": 0,
                        "missing_contact_account_count": 0,
                        "missing_decision_maker_account_count": 0,
                        "role_only_decision_maker_account_count": 0,
                        "decision_maker_needs_check_account_count": 0,
                        "connected_call_count": 40,
                        "40_connected_calls": "40/40",
                        "connected_call_hit_miss": "hit",
                        "warm_activity_points": 1,
                        "friday_correction_needed": False,
                        "main_issue": "operating rhythm on track",
                    }
                ]
            },
            "_internal": {
                "companies": companies,
                "company_deal_ids": {},
                "week": {"week_start": "2026-05-04", "week_end": "2026-05-10"},
            },
            "scope": {"caller_email": "kerren.fong@staffany.com", "countries": ["Singapore"]},
            "total": 2,
            "requested_limit": 1000,
            "returned_count": 2,
            "has_more": False,
            "truncated": False,
            "confidence": "verified",
            "caveat": "ok",
        }
        deal_counts = {
            "configured": True,
            "by_owner": {},
            "totals": {"qos": 0, "qo_met": 0, "qo_met_pct": None, "deals_closed": 0},
            "confidence": "verified",
            "caveat": "",
        }
        with patch.object(self.module, "_priority_account_coverage", return_value=coverage), patch.object(
            self.module, "_deal_counts_for_friday", return_value=deal_counts
        ):
            result = self.module.build_friday_sales_review(
                "kerren.fong@staffany.com",
                countries=["Singapore"],
                week_start="2026-05-04",
                week_end="2026-05-10",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["hygiene_summary"][0]["locked_pool_count"], 2)
        followup = result["answer"]["warehouse_metric_followups"][0]
        self.assertEqual(followup["metric"], "qo_set")
        self.assertIn("fct_sales_points", followup["sql"])
        self.assertIn("'owner-1'", followup["sql"])
        self.assertEqual(followup["execute_with"], "staffany_bigquery.execute_sql_readonly")

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

    def test_followup_status_counts_whatsapp_association_paths_and_omits_bodies(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_associations(from_type, object_id, to_type, limit=20):
            if to_type != "communications":
                return {"ids": [], "truncated": False, "has_more": False}
            if from_type == "companies":
                return {"ids": ["comm-company"], "truncated": False, "has_more": False}
            if from_type == "contacts":
                return {"ids": ["comm-contact"], "truncated": False, "has_more": False}
            if from_type == "deals":
                return {"ids": ["comm-deal"], "truncated": False, "has_more": False}
            return {"ids": [], "truncated": False, "has_more": False}

        def fake_batch_read(object_type, ids, properties):
            self.assertNotIn("hs_communication_body", properties)
            self.assertNotIn("hs_note_body", properties)
            if object_type != "communications":
                return []
            return [
                {
                    "id": activity_id,
                    "properties": {
                        "hs_timestamp": "2026-05-10T10:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_communication_channel_type": "WHATS_APP",
                        "hs_communication_logged_from": "CRM",
                        "hs_communication_body": "raw WhatsApp body must never appear",
                        "phone": "+6512345678",
                        "email": "guest@example.com",
                    },
                }
                for activity_id in ids
            ]

        with patch.object(self.module, "_association_ids_with_metadata", side_effect=fake_associations), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_followup_status(
                company,
                ["contact-1"],
                ["deal-1"],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "followed_up")
        self.assertEqual(result["activity_counts"]["whatsapp_communications"], 3)
        self.assertIn({"object_type": "company", "object_id": "123"}, result["evidence"][0]["associated_via"])
        self.assertNotIn("raw WhatsApp body", json.dumps(result))
        self.assertNotIn("+6512345678", json.dumps(result))
        self.assertNotIn("guest@example.com", json.dumps(result))

    def test_followup_status_completed_task_counts_as_followed_up(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "tasks":
                return {
                    "activity_ids": ["task-1"],
                    "activity_sources": {"task-1": [{"object_type": "company", "object_id": "123"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "tasks":
                return []
            return [
                {
                    "id": "task-1",
                    "properties": {
                        "hs_timestamp": "2026-05-10T10:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "COMPLETED",
                        "hs_task_body": "raw task body must never appear",
                    },
                }
            ]

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "followed_up")
        self.assertEqual(result["activity_counts"]["completed_tasks"], 1)
        self.assertNotIn("raw task body", json.dumps(result))

    def test_followup_status_open_task_counts_as_scheduled(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "tasks":
                return {
                    "activity_ids": ["task-1"],
                    "activity_sources": {"task-1": [{"object_type": "company", "object_id": "123"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "tasks":
                return []
            return [
                {
                    "id": "task-1",
                    "properties": {
                        "hs_timestamp": "2026-05-12T10:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "NOT_STARTED",
                    },
                }
            ]

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "scheduled")
        self.assertEqual(result["activity_counts"]["open_tasks"], 1)

    def test_followup_status_no_activity_returns_not_found(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        with patch.object(
            self.module,
            "_collect_activity_associations",
            return_value={"activity_ids": [], "activity_sources": {}, "truncated": False},
        ), patch.object(self.module, "_batch_read", return_value=[]):
            result = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "not_found")
        self.assertEqual(result["latest_followup_at"], "")

    def test_followup_status_truncated_associations_need_check(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "communications":
                return {
                    "activity_ids": ["comm-1"],
                    "activity_sources": {"comm-1": [{"object_type": "company", "object_id": "123"}]},
                    "truncated": True,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "communications":
                return []
            return [
                {
                    "id": "comm-1",
                    "properties": {
                        "hs_timestamp": "2026-05-10T10:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_communication_channel_type": "WHATS_APP",
                    },
                }
            ]

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "needs_check")
        self.assertEqual(result["confidence"], "needs-check")
        self.assertTrue(result["activity_truncated"])

    def test_followup_status_owner_mismatch_needs_check(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "notes":
                return {
                    "activity_ids": ["note-1"],
                    "activity_sources": {"note-1": [{"object_type": "company", "object_id": "123"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "notes":
                return []
            return [
                {
                    "id": "note-1",
                    "properties": {
                        "hs_timestamp": "2026-05-10T10:00:00Z",
                        "hubspot_owner_id": "owner-other",
                        "hs_note_body": "raw note body must never appear",
                    },
                }
            ]

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-10T09:00:00Z"),
                None,
            )

        self.assertEqual(result["followup_status"], "needs_check")
        self.assertTrue(result["owner_mismatch"])
        self.assertNotIn("raw note body", json.dumps(result))

    def test_check_account_followup_status_blocks_outside_scope_company_ids(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_assert_company_access", side_effect=self.module.ScopeError("Company is outside caller scope.")
        ):
            result = self.module.check_account_followup_status(
                "kerren.fong@staffany.com",
                ["999"],
                "2026-05-10T09:00:00Z",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("outside caller scope", result["answer"])

    def test_check_account_followup_status_batches_activity_lookup(self):
        companies = {
            "123": {
                "id": "123",
                "properties": {
                    "name": "Noci Bakehouse",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-sales",
                },
            },
            "456": {
                "id": "456",
                "properties": {
                    "name": "Bali Buda",
                    "hs_is_target_account": "true",
                    "company_country": "Indonesia",
                    "hubspot_owner_id": "owner-sales",
                },
            },
        }
        association_calls: list[tuple[str, str, tuple[str, ...]]] = []

        def fake_assert_company_access(company_id, scope):
            return companies[str(company_id)]

        def fake_batch_association_ids(from_type, to_type, ids):
            id_tuple = tuple(str(item) for item in ids)
            association_calls.append((from_type, to_type, id_tuple))
            if (from_type, to_type) == ("companies", "contacts"):
                return {"123": ["contact-1"], "456": []}
            if (from_type, to_type) == ("companies", "deals"):
                return {"123": [], "456": ["deal-2"]}
            if to_type == "communications":
                if from_type == "companies":
                    return {"123": ["comm-company"], "456": []}
                if from_type == "contacts":
                    return {"contact-1": ["comm-contact"]}
                if from_type == "deals":
                    return {"deal-2": []}
            if to_type == "tasks":
                if from_type == "companies":
                    return {"123": [], "456": []}
                if from_type == "contacts":
                    return {"contact-1": []}
                if from_type == "deals":
                    return {"deal-2": ["task-deal"]}
            return {str(item): [] for item in ids}

        def fake_batch_read(object_type, ids, properties):
            self.assertNotIn("hs_communication_body", properties)
            self.assertNotIn("hs_note_body", properties)
            if object_type == "communications":
                return [
                    {
                        "id": activity_id,
                        "properties": {
                            "hs_timestamp": "2026-05-10T10:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_communication_channel_type": "WHATS_APP",
                            "hs_communication_body": "raw WhatsApp body must never appear",
                            "phone": "+6512345678",
                        },
                    }
                    for activity_id in ids
                ]
            if object_type == "tasks":
                return [
                    {
                        "id": "task-deal",
                        "properties": {
                            "hs_timestamp": "2026-05-12T10:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_task_status": "NOT_STARTED",
                            "hs_task_body": "raw task body must never appear",
                        },
                    }
                ]
            return []

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_assert_company_access", side_effect=fake_assert_company_access
        ), patch.object(self.module, "_batch_association_ids", side_effect=fake_batch_association_ids), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(
            self.module, "_collect_activity_associations", side_effect=AssertionError("must batch activity lookup")
        ), patch.object(self.module, "_association_ids", side_effect=AssertionError("must batch company associations")):
            result = self.module.check_account_followup_status(
                "kerren.fong@staffany.com",
                ["123", "456"],
                "2026-05-10T09:00:00Z",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["returned_count"], 2)
        by_id = {row["company_id"]: row for row in result["answer"]}
        self.assertEqual(by_id["123"]["followup_status"], "followed_up")
        self.assertEqual(by_id["123"]["activity_counts"]["whatsapp_communications"], 2)
        self.assertEqual(by_id["456"]["followup_status"], "scheduled")
        self.assertEqual(by_id["456"]["activity_counts"]["open_tasks"], 1)
        self.assertIn(("companies", "contacts", ("123", "456")), association_calls)
        self.assertIn(("companies", "communications", ("123", "456")), association_calls)
        self.assertNotIn("raw WhatsApp body", json.dumps(result))
        self.assertNotIn("raw task body", json.dumps(result))
        self.assertNotIn("+6512345678", json.dumps(result))

    def test_event_followup_status_uses_checked_in_luma_and_event_specific_whatsapp(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Bali Buda",
                "domain": "balibuda.com",
                "hs_is_target_account": "true",
                "company_country": "Indonesia",
                "hubspot_owner_id": "owner-sales",
                "type": "CUSTOMER",
            },
        }
        events = [
            {
                "event_id": "evt-old",
                "name": "StaffAny HR Happy Hour Bali",
                "start_at": "2026-04-01T07:00:00Z",
                "end_at": "2026-04-01T10:00:00Z",
                "tags": ["Bali", "HR Happy Hour"],
                "location_tags": ["Bali"],
                "country_tags": ["Indonesia"],
                "event_type_tags": ["HR Happy Hour"],
            },
            {
                "event_id": "evt-new",
                "name": "StaffAny HR Happy Hour Bali",
                "start_at": "2026-05-07T07:00:00Z",
                "end_at": "2026-05-07T10:00:00Z",
                "tags": ["Bali", "HR Happy Hour"],
                "location_tags": ["Bali"],
                "country_tags": ["Indonesia"],
                "event_type_tags": ["HR Happy Hour"],
            },
        ]

        def fake_association_ids(from_type, object_id, to_type, limit=20):
            if from_type == "contacts" and to_type == "companies":
                return ["company-1"]
            if from_type == "companies" and to_type == "contacts":
                return ["contact-1"]
            if from_type == "companies" and to_type == "deals":
                return []
            return []

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "communications":
                return {
                    "activity_ids": ["comm-1"],
                    "activity_sources": {"comm-1": [{"object_type": "company", "object_id": "company-1"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "communications":
                return []
            self.assertIn("hs_communication_body", properties)
            return [
                {
                    "id": "comm-1",
                    "properties": {
                        "hs_timestamp": "2026-05-08T02:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_communication_channel_type": "WHATS_APP",
                        "hs_communication_logged_from": "Eazybe",
                        "hs_communication_body": "Makasih sudah datang di Bali HHH. +628123456789 guest@balibuda.com",
                    },
                }
            ]

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Indonesia",)}), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("", "")
        ), patch.object(self.module, "_list_luma_events_for_followup", return_value=(events, False, False)), patch.object(
            self.module,
            "_list_luma_guests",
            return_value=(
                [
                    {"email": "guest@balibuda.com", "checked_in_at": "2026-05-07T07:30:00Z"},
                    {"email": "noshow@balibuda.com", "checked_in_at": ""},
                ],
                False,
                False,
            ),
        ), patch.object(self.module, "_contact_search_by_email", return_value=[{"id": "contact-1", "properties": {"email": "guest@balibuda.com"}}]), patch.object(
            self.module, "_association_ids", side_effect=fake_association_ids
        ), patch.object(self.module, "_get_company", return_value=company), patch.object(
            self.module, "_collect_activity_associations", side_effect=fake_collect
        ), patch.object(self.module, "_batch_read", side_effect=fake_batch_read), patch.object(
            self.module, "_owner_by_id", return_value={"id": "owner-sales", "email": "rep@staffany.com"}
        ):
            result = self.module.check_event_followup_status(
                "kaiyi@staffany.com",
                event_tags=["Bali", "HR Happy Hour"],
                limit=50,
            )

        self.assertEqual(result["answer"]["event"]["event_id"], "evt-new")
        self.assertEqual(result["answer"]["match_summary"]["attended_guest_count"], 1)
        account = result["answer"]["accounts"][0]
        self.assertEqual(account["followup_status"], "followed_up")
        self.assertEqual(account["owner_email"], "rep@staffany.com")
        self.assertEqual(account["owner_name"], "rep@staffany.com")
        self.assertEqual(account["account_status"], "customer")
        self.assertEqual(account["account_status_source"], "HubSpot company type=CUSTOMER or lifecyclestage=customer")
        self.assertEqual(account["activity_counts"]["event_specific_whatsapp_communications"], 1)
        self.assertEqual(account["evidence"][0]["event_match"], "strong")
        dumped = json.dumps(result)
        self.assertNotIn("Makasih sudah datang", dumped)
        self.assertNotIn("+628123456789", dumped)
        self.assertNotIn("guest@balibuda.com", dumped)

    def test_event_followup_status_marks_generic_whatsapp_as_needs_check(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Bali Buda",
                "domain": "balibuda.com",
                "hs_is_target_account": "true",
                "company_country": "Indonesia",
                "hubspot_owner_id": "owner-sales",
            },
        }

        def fake_association_ids(from_type, object_id, to_type, limit=20):
            if from_type == "companies" and to_type == "contacts":
                return []
            if from_type == "companies" and to_type == "deals":
                return []
            return []

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "communications":
                return {
                    "activity_ids": ["comm-1"],
                    "activity_sources": {"comm-1": [{"object_type": "company", "object_id": "company-1"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            if object_type != "communications" or not ids:
                return []
            return [
                {
                    "id": "comm-1",
                    "properties": {
                        "hs_timestamp": "2026-05-08T02:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_communication_channel_type": "WHATS_APP",
                        "hs_communication_body": "Hi, just checking in about your roster setup.",
                    },
                }
            ]

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Indonesia",)}), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("", "")
        ), patch.object(
            self.module,
            "_single_luma_event",
            return_value={
                "event_id": "evt-1",
                "name": "StaffAny HR Happy Hour Bali",
                "start_at": "2026-05-07T07:00:00Z",
                "end_at": "2026-05-07T10:00:00Z",
                "tags": ["Bali", "HR Happy Hour"],
                "location_tags": ["Bali"],
                "country_tags": ["Indonesia"],
                "event_type_tags": ["HR Happy Hour"],
            },
        ), patch.object(
            self.module, "_list_luma_guests", return_value=([{"company": "Bali Buda", "checked_in_at": "2026-05-07T07:30:00Z"}], False, False)
        ), patch.object(
            self.module, "_resolve_scoped_company_name", return_value={"status": "resolved", "company_id": "company-1"}
        ), patch.object(self.module, "_association_ids", side_effect=fake_association_ids), patch.object(
            self.module, "_get_company", return_value=company
        ), patch.object(
            self.module, "_collect_activity_associations", side_effect=fake_collect
        ), patch.object(self.module, "_batch_read", side_effect=fake_batch_read), patch.object(
            self.module, "_owner_by_id", return_value={"id": "owner-sales", "email": "rep@staffany.com"}
        ):
            result = self.module.check_event_followup_status(
                "kaiyi@staffany.com",
                event_id="evt-1",
                event_tags=["Bali", "HR Happy Hour"],
            )

        account = result["answer"]["accounts"][0]
        self.assertEqual(account["followup_status"], "needs_check")
        self.assertEqual(account["activity_counts"]["generic_whatsapp_communications"], 1)
        self.assertNotIn("checking in about your roster", json.dumps(result))

    def test_event_followup_status_open_event_task_counts_as_scheduled_and_no_activity_not_found(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Bali Buda",
                "domain": "balibuda.com",
                "hs_is_target_account": "true",
                "company_country": "Indonesia",
                "hubspot_owner_id": "owner-sales",
            },
        }
        event_context = {
            "event": {
                "event_id": "evt-1",
                "name": "StaffAny HR Happy Hour Bali",
                "tags": ["Bali", "HR Happy Hour"],
                "location_tags": ["Bali"],
                "event_type_tags": ["HR Happy Hour"],
            }
        }

        def fake_collect_with_task(company_id, contact_ids, deal_ids, object_type):
            if object_type == "tasks":
                return {
                    "activity_ids": ["task-1"],
                    "activity_sources": {"task-1": [{"object_type": "company", "object_id": "company-1"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_task_batch_read(object_type, ids, properties):
            if object_type != "tasks" or not ids:
                return []
            return [
                {
                    "id": "task-1",
                    "properties": {
                        "hs_timestamp": "2026-05-08T02:00:00Z",
                        "hubspot_owner_id": "owner-sales",
                        "hs_task_status": "NOT_STARTED",
                        "hs_task_subject": "WhatsApp follow-up after Bali HHH",
                    },
                }
            ]

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect_with_task), patch.object(
            self.module, "_batch_read", side_effect=fake_task_batch_read
        ), patch.object(self.module, "_owner_by_id", return_value={"id": "owner-sales", "email": "rep@staffany.com"}):
            scheduled = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-07T10:00:00Z"),
                None,
                event_context,
            )

        self.assertEqual(scheduled["followup_status"], "scheduled")
        self.assertEqual(scheduled["activity_counts"]["event_specific_open_tasks"], 1)

        with patch.object(
            self.module,
            "_collect_activity_associations",
            return_value={"activity_ids": [], "activity_sources": {}, "truncated": False},
        ), patch.object(self.module, "_batch_read", return_value=[]), patch.object(
            self.module, "_owner_by_id", return_value={"id": "owner-sales", "email": "rep@staffany.com"}
        ):
            not_found = self.module._account_followup_status(
                company,
                [],
                [],
                self.module._datetime_value("2026-05-07T10:00:00Z"),
                None,
                event_context,
            )

        self.assertEqual(not_found["followup_status"], "not_found")

    def test_event_followup_matching_is_not_sample_capped_and_truncation_needs_check(self):
        guests = [{"checked_in_at": "2026-05-07T07:30:00Z"} for _ in range(1001)]

        def fake_match(guest, scope, countries, owner_id):
            index = fake_match.count
            fake_match.count += 1
            return {
                "company": {
                    "id": f"company-{index}",
                    "properties": {
                        "name": f"Account {index}",
                        "hs_is_target_account": "true",
                        "company_country": "Indonesia",
                        "hubspot_owner_id": "owner-sales",
                    },
                },
                "company_id": f"company-{index}",
                "match_reason": "exact_hubspot_contact_email",
                "match_confidence": "verified",
            }

        fake_match.count = 0
        with patch.object(self.module, "_match_luma_guest_to_company", side_effect=fake_match):
            result = self.module._matched_event_companies(
                guests,
                {**SCOPE, "countries": ("Indonesia",)},
                ["Indonesia"],
                None,
            )

        self.assertEqual(len(result["matches"]), 1001)
        self.assertEqual(result["attended_guest_count"], 1001)

    def test_event_followup_status_truncated_luma_returns_needs_check(self):
        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "countries": ("Indonesia",)}), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("", "")
        ), patch.object(
            self.module,
            "_single_luma_event",
            return_value={
                "event_id": "evt-1",
                "name": "StaffAny HR Happy Hour Bali",
                "start_at": "2026-05-07T07:00:00Z",
                "end_at": "2026-05-07T10:00:00Z",
                "tags": ["Bali", "HR Happy Hour"],
                "location_tags": ["Bali"],
                "country_tags": ["Indonesia"],
                "event_type_tags": ["HR Happy Hour"],
            },
        ), patch.object(self.module, "_list_luma_guests", return_value=([], True, True)):
            result = self.module.check_event_followup_status(
                "kaiyi@staffany.com",
                event_id="evt-1",
                event_tags=["Bali", "HR Happy Hour"],
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertTrue(result["truncated"])

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

    def test_list_sales_followup_tasks_uses_task_search_for_scope_queries(self):
        sentinel = {
            "answer": [],
            "source": "HubSpot task search plus scoped sales-owned task associations",
            "scope": {"caller_email": "kerren.fong@staffany.com"},
            "total": 0,
            "requested_limit": 50,
            "returned_count": 0,
            "has_more": False,
            "truncated": False,
            "task_count": 0,
            "returned_task_count": 0,
            "task_truncated": False,
            "confidence": "verified",
            "caveat": "task search",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("owner-sales", "rep.owner@staffany.com")
        ), patch.object(
            self.module, "_company_context", side_effect=AssertionError("scope task lookup must not fan out per account")
        ), patch.object(
            self.module, "_list_sales_followup_tasks_from_task_search", return_value=sentinel
        ) as task_search:
            result = self.module.list_sales_followup_tasks(
                "kerren.fong@staffany.com",
                owner_email="rep.owner@staffany.com",
                due_start="2026-05-10",
                due_end="2026-05-16",
            )

        self.assertEqual(result, sentinel)
        task_search.assert_called_once()

    def test_list_active_deals_missing_next_meeting_uses_direct_deal_path(self):
        companies = [
            {
                "id": "company-1",
                "properties": {
                    "name": "Noci Bakehouse",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-sales",
                    "hs_is_target_account": "true",
                },
            }
        ]

        def fake_batch_associations(from_type, to_type, ids, deadline=None):
            if (from_type, to_type) == ("companies", "deals"):
                return {"company-1": ["deal-active", "deal-lost"]}
            if (from_type, to_type) == ("deals", "meetings"):
                return {"deal-active": [], "deal-lost": ["meeting-1"]}
            raise AssertionError(f"unexpected association read: {from_type}->{to_type}")

        def fake_batch_read(object_type, ids, properties, deadline=None):
            if object_type == "deals":
                return [
                    {
                        "id": "deal-active",
                        "properties": {
                            "dealname": "Expansion",
                            "dealstage": "appointmentscheduled",
                            "hubspot_owner_id": "owner-sales",
                        },
                    },
                    {
                        "id": "deal-lost",
                        "properties": {
                            "dealname": "Old deal",
                            "dealstage": "closedlost",
                            "hubspot_owner_id": "owner-sales",
                        },
                    },
                ]
            if object_type == "meetings":
                return []
            raise AssertionError(f"unexpected batch read: {object_type}")

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("owner-sales", "rep.owner@staffany.com")
        ), patch.object(
            self.module,
            "_company_search",
            return_value={
                "results": companies,
                "total": 1,
                "requested_limit": 100,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module, "_batch_association_ids", side_effect=fake_batch_associations
        ), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(
            self.module, "build_friday_sales_review", side_effect=AssertionError("deal hygiene must not use Friday review")
        ), patch.object(
            self.module, "audit_priority_account_coverage", side_effect=AssertionError("deal hygiene must not use coverage audit")
        ):
            result = self.module.list_active_deals_missing_next_meeting(
                "kerren.fong@staffany.com",
                countries=["Singapore"],
                owner_email="rep.owner@staffany.com",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["active_deal_count"], 1)
        self.assertEqual(result["missing_next_meeting_count"], 1)
        self.assertEqual(result["answer"][0]["deal_id"], "deal-active")
        self.assertEqual(result["answer"][0]["company_name"], "Noci Bakehouse")

    def test_account_week_activity_counts_connected_calls_and_warm_activity_safely(self):
        company = {"id": "123", "properties": {"hubspot_owner_id": "owner-sales"}}

        def fake_collect(company_id, contact_ids, deal_ids, object_type):
            if object_type == "calls":
                return {
                    "activity_ids": ["call-short", "call-connected", "call-open"],
                    "activity_sources": {"call-connected": [{"object_type": "company", "object_id": "123"}]},
                    "truncated": False,
                }
            if object_type == "meetings":
                return {
                    "activity_ids": ["meeting-warm", "meeting-open"],
                    "activity_sources": {"meeting-warm": [{"object_type": "deal", "object_id": "deal-1"}]},
                    "truncated": False,
                }
            return {"activity_ids": [], "activity_sources": {}, "truncated": False}

        def fake_batch_read(object_type, ids, properties):
            self.assertNotIn("hs_call_body", properties)
            self.assertNotIn("hs_call_recording_url", properties)
            self.assertNotIn("hs_meeting_body", properties)
            if object_type == "calls":
                return [
                    {
                        "id": "call-short",
                        "properties": {
                            "hs_timestamp": "2026-05-04T02:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_call_status": "COMPLETED",
                            "hs_call_duration": "119000",
                            "hs_call_title": "Call +6512345678",
                        },
                    },
                    {
                        "id": "call-connected",
                        "properties": {
                            "hs_timestamp": "2026-05-04T03:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_call_status": "COMPLETED",
                            "hs_call_duration": "180000",
                            "hs_call_title": "Discovery call",
                        },
                    },
                    {
                        "id": "call-open",
                        "properties": {
                            "hs_timestamp": "2026-05-04T04:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_call_status": "SCHEDULED",
                            "hs_call_duration": "300000",
                        },
                    },
                ]
            if object_type == "meetings":
                return [
                    {
                        "id": "meeting-warm",
                        "properties": {
                            "hs_timestamp": "2026-05-04T05:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_meeting_outcome": "COMPLETED",
                            "hs_meeting_title": "Coffee with ops +6512345678",
                        },
                    },
                    {
                        "id": "meeting-open",
                        "properties": {
                            "hs_timestamp": "2026-05-04T06:00:00Z",
                            "hubspot_owner_id": "owner-sales",
                            "hs_meeting_outcome": "SCHEDULED",
                            "hs_meeting_title": "Lunch next week",
                        },
                    },
                ]
            return []

        with patch.object(self.module, "_collect_activity_associations", side_effect=fake_collect), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ):
            result = self.module._account_week_activity(
                company,
                ["contact-1"],
                ["deal-1"],
                self.module._datetime_value("2026-05-04T00:00:00Z"),
                self.module._datetime_value("2026-05-10T23:59:59Z"),
            )

        self.assertEqual(result["counts"]["completed_calls"], 2)
        self.assertEqual(result["counts"]["connected_calls"], 1)
        self.assertEqual(result["counts"]["completed_meetings"], 1)
        self.assertEqual(result["counts"]["warm_activity_points"], 1)
        self.assertEqual(result["counts"]["touches"], 3)
        self.assertNotIn("+6512345678", json.dumps(result))
        self.assertNotIn("body", json.dumps(result).lower())

    def test_priority_account_coverage_reports_hits_misses_stale_dirty_and_truncation(self):
        companies = [
            {
                "id": "1",
                "properties": {
                    "name": "Worked Twice",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-1",
                    "numberofemployees": "50",
                    "industry": "F&B",
                    "contract_end_date": "2026-12-31",
                    "current_tools": "Excel",
                    "notes_last_updated": "2026-05-04T04:00:00Z",
                    "hs_num_decision_makers": "1",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
            {
                "id": "2",
                "properties": {
                    "name": "Single Touch",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-1",
                    "numberofemployees": "20",
                    "industry": "Retail",
                    "contract_end_date": "2026-12-31",
                    "current_tools": "Manual",
                    "notes_last_updated": "2026-05-05T04:00:00Z",
                    "hs_num_decision_makers": "0",
                    "hs_num_contacts_with_buying_roles": "1",
                },
            },
            {
                "id": "3",
                "properties": {
                    "name": "Untouched Dirty",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-1",
                },
            },
        ]

        def fake_company_search(filters, limit, **kwargs):
            self.assertIn({"propertyName": "company_country", "operator": "IN", "values": ["Singapore"]}, filters)
            return {
                "results": companies,
                "total": 4,
                "requested_limit": limit,
                "returned_count": 3,
                "has_more": True,
                "truncated": True,
            }

        def fake_batch_associations(from_type, to_type, ids):
            if from_type == "companies" and to_type == "contacts":
                return {"1": ["contact-1"], "2": ["contact-2"], "3": []}
            if from_type == "companies" and to_type == "deals":
                return {"1": [], "2": [], "3": []}
            if from_type == "companies" and to_type == "tasks":
                return {"1": [], "2": [], "3": ["task-3"]}
            if to_type == "tasks":
                return {}
            return {}

        activity_index = {
            "1": {
                "counts": {
                    "touches": 2,
                    "connected_calls": 1,
                    "warm_activity_points": 1,
                    "whatsapp_communications": 1,
                },
                "latest_activity_at": "2026-05-04T04:00:00Z",
                "truncated": False,
                "weak_evidence": False,
            },
            "2": {
                "counts": {
                    "touches": 1,
                    "connected_calls": 0,
                    "warm_activity_points": 0,
                    "whatsapp_communications": 1,
                },
                "latest_activity_at": "2026-05-05T04:00:00Z",
                "truncated": False,
                "weak_evidence": False,
            },
            "3": {
                "counts": {
                    "touches": 0,
                    "connected_calls": 0,
                    "warm_activity_points": 0,
                    "whatsapp_communications": 0,
                },
                "latest_activity_at": "",
                "truncated": False,
                "weak_evidence": False,
            },
        }
        contacts = [
            {"id": "contact-1", "properties": {"jobtitle": "HR Director", "hs_buying_role": "DECISION_MAKER"}},
            {"id": "contact-2", "properties": {"jobtitle": "Owner", "hs_buying_role": "BUDGET_HOLDER"}},
        ]

        def fake_batch_read(object_type, ids, properties):
            if object_type == "contacts":
                return contacts
            if object_type == "tasks":
                return [
                    {
                        "id": "task-3",
                        "properties": {
                            "hs_timestamp": "2026-05-11T02:00:00Z",
                            "hs_task_subject": "Call +6512345678",
                            "hubspot_owner_id": "owner-1",
                            "hs_task_status": "NOT_STARTED",
                            "hs_task_priority": "HIGH",
                            "hs_task_type": "CALL",
                        },
                    }
                ]
            return []

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(self.module, "_batch_association_ids", side_effect=fake_batch_associations), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(
            self.module,
            "_sales_followup_task_index_for_companies",
            side_effect=AssertionError("coverage must not run owner-wide task search per owner"),
        ), patch.object(self.module, "_week_activity_index_for_companies", return_value=activity_index), patch.object(
            self.module, "_account_week_activity", side_effect=AssertionError("coverage should use batched week activity index")
        ), patch.object(
            self.module,
            "_owner_lookup_by_id",
            return_value={"owner-1": {"id": "owner-1", "email": "ae@example.com", "firstName": "AE"}},
        ), patch.object(self.module, "_owner_email_by_id", return_value="ae@example.com"), patch.object(
            self.module, "_owner_name_by_id", return_value="AE"
        ):
            result = self.module.audit_priority_account_coverage(
                "kerren.fong@staffany.com",
                countries=["Singapore"],
                week_start="2026-05-04",
                week_end="2026-05-10",
            )

        owner = result["answer"]["owners"][0]
        self.assertEqual(owner["worked_account_count"], 2)
        self.assertEqual(owner["double_tapped_account_count"], 1)
        self.assertEqual(owner["single_touch_account_count"], 1)
        self.assertEqual(owner["untouched_account_count"], 1)
        self.assertEqual(owner["stale_account_count"], 1)
        self.assertEqual(owner["dirty_account_count"], 2)
        self.assertEqual(owner["missing_contact_account_count"], 1)
        self.assertEqual(owner["missing_decision_maker_account_count"], 2)
        self.assertEqual(owner["role_only_decision_maker_account_count"], 1)
        self.assertEqual(result["answer"]["summary"]["missing_contact_account_count"], 1)
        self.assertEqual(result["answer"]["summary"]["missing_decision_maker_account_count"], 2)
        self.assertEqual(owner["open_followup_account_count"], 1)
        self.assertEqual(owner["connected_call_count"], 1)
        self.assertTrue(owner["friday_correction_needed"])
        self.assertEqual(result["confidence"], "needs-check")
        self.assertTrue(result["truncated"])
        self.assertNotIn("+6512345678", json.dumps(result))

    def test_sales_followup_task_index_for_company_associations_batches_scoped_tasks(self):
        companies = [
            {"id": "1", "properties": {"hubspot_owner_id": "owner-1"}},
            {"id": "2", "properties": {"hubspot_owner_id": "owner-2"}},
        ]
        contact_index = {"1": ["contact-1"], "2": ["contact-2"]}
        deal_index = {"1": ["deal-1"], "2": []}

        def fake_batch_associations(from_type, to_type, ids):
            if (from_type, to_type) == ("companies", "tasks"):
                return {"1": ["task-direct"], "2": ["task-owner-mismatch"]}
            if (from_type, to_type) == ("contacts", "tasks"):
                return {"contact-1": ["task-contact"], "contact-2": ["task-completed"]}
            if (from_type, to_type) == ("deals", "tasks"):
                return {"deal-1": ["task-deal"]}
            raise AssertionError(f"unexpected association read: {from_type}->{to_type}")

        def fake_batch_read(object_type, ids, properties):
            self.assertEqual(object_type, "tasks")
            self.assertNotIn("hs_task_body", properties)
            return [
                {
                    "id": "task-direct",
                    "properties": {
                        "hs_timestamp": "2026-05-12T00:00:00Z",
                        "hs_task_subject": "Direct task",
                        "hubspot_owner_id": "owner-1",
                        "hs_task_status": "NOT_STARTED",
                    },
                },
                {
                    "id": "task-contact",
                    "properties": {
                        "hs_timestamp": "2026-05-11T00:00:00Z",
                        "hs_task_subject": "Contact task",
                        "hubspot_owner_id": "owner-1",
                        "hs_task_status": "IN_PROGRESS",
                    },
                },
                {
                    "id": "task-deal",
                    "properties": {
                        "hs_timestamp": "2026-05-13T00:00:00Z",
                        "hs_task_subject": "Deal task",
                        "hubspot_owner_id": "owner-1",
                        "hs_task_status": "NOT_STARTED",
                    },
                },
                {
                    "id": "task-owner-mismatch",
                    "properties": {
                        "hs_timestamp": "2026-05-14T00:00:00Z",
                        "hs_task_subject": "Wrong owner",
                        "hubspot_owner_id": "owner-1",
                        "hs_task_status": "NOT_STARTED",
                    },
                },
                {
                    "id": "task-completed",
                    "properties": {
                        "hs_timestamp": "2026-05-15T00:00:00Z",
                        "hs_task_subject": "Done",
                        "hubspot_owner_id": "owner-2",
                        "hs_task_status": "COMPLETED",
                    },
                },
            ]

        with patch.object(self.module, "_batch_association_ids", side_effect=fake_batch_associations), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(self.module, "_task_search", side_effect=AssertionError("task search should not run")):
            result = self.module._sales_followup_task_index_for_company_associations(
                companies,
                contact_index,
                deal_index,
            )

        company_1_tasks = result["tasks_by_company"]["1"]
        self.assertEqual([task["task_id"] for task in company_1_tasks], ["task-contact", "task-direct", "task-deal"])
        self.assertEqual(result["tasks_by_company"]["2"], [])
        self.assertEqual(company_1_tasks[0]["associated_via"], [{"object_type": "contact", "object_id": "contact-1"}])
        self.assertFalse(result["truncated"])

    def test_sales_followup_task_index_returns_partial_on_soft_deadline(self):
        companies = [{"id": "1", "properties": {"hubspot_owner_id": "owner-1"}}]

        with patch.object(self.module, "_batch_read", side_effect=AssertionError("expired deadline should skip task reads")):
            result = self.module._sales_followup_task_index_for_company_associations(
                companies,
                {"1": ["contact-1"]},
                {"1": ["deal-1"]},
                deadline=self.module.time.monotonic() - 1,
            )

        self.assertTrue(result["partial_due_to_soft_timeout"])
        self.assertTrue(result["truncated"])
        self.assertEqual(result["tasks_by_company"], {"1": []})
        self.assertTrue(result["metadata"]["partial_due_to_soft_timeout"])

    def test_ae_can_audit_self_but_not_another_owner(self):
        ae_scope = {"kind": "ae", "email": "ae@staffany.com", "countries": ("Singapore",), "owner_id": "owner-ae"}

        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module, "_owner_by_email", return_value={"id": "owner-other"}
        ), patch.object(self.module, "_company_search", side_effect=AssertionError("blocked owner lookup should not search")):
            blocked = self.module.audit_priority_account_coverage(
                "ae@staffany.com",
                countries=["Singapore"],
                owner_email="other@staffany.com",
            )

        self.assertEqual(blocked["confidence"], "blocked")
        self.assertIn("another owner's target accounts", blocked["answer"])

        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module,
            "_company_search",
            return_value={"results": [], "total": 0, "requested_limit": 1000, "returned_count": 0, "has_more": False, "truncated": False},
        ) as company_search, patch.object(self.module, "_batch_association_ids", return_value={}), patch.object(
            self.module, "_owner_lookup_by_id", return_value={}
        ):
            allowed = self.module.audit_priority_account_coverage("ae@staffany.com", countries=["Singapore"])

        filters = company_search.call_args.args[0]
        self.assertIn({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": "owner-ae"}, filters)
        self.assertEqual(allowed["confidence"], "verified")

    def test_manager_country_scope_is_enforced_for_friday_review(self):
        with patch.object(self.module, "_caller_scope", return_value={"kind": "manager", "email": "sarah@staffany.com", "countries": ("Indonesia",), "owner_id": None}), patch.object(
            self.module,
            "_company_search",
            return_value={"results": [], "total": 0, "requested_limit": 1000, "returned_count": 0, "has_more": False, "truncated": False},
        ) as company_search, patch.object(self.module, "_batch_association_ids", return_value={}), patch.object(
            self.module, "_owner_lookup_by_id", return_value={}
        ), patch.dict(
            os.environ,
            {
                self.module.QO_PIPELINE_IDS_ENV_VAR: "",
                self.module.QO_STAGE_IDS_ENV_VAR: "",
                self.module.QO_MET_STAGE_IDS_ENV_VAR: "",
                self.module.CLOSED_WON_STAGE_IDS_ENV_VAR: "",
            },
        ):
            result = self.module.build_friday_sales_review("sarah@staffany.com")

        filters = company_search.call_args.args[0]
        self.assertIn({"propertyName": "company_country", "operator": "IN", "values": ["Indonesia"]}, filters)
        self.assertEqual(result["scope"]["countries"], ["Indonesia"])
        self.assertEqual(result["confidence"], "needs-check")

    def test_friday_review_blocks_ae_and_missing_stage_config_still_returns_hygiene(self):
        ae_scope = {"kind": "ae", "email": "ae@staffany.com", "countries": ("Singapore",), "owner_id": "owner-ae"}
        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module, "_company_search", side_effect=AssertionError("AE Friday review must stop before HubSpot search")
        ):
            blocked = self.module.build_friday_sales_review("ae@staffany.com", countries=["Singapore"])

        self.assertEqual(blocked["confidence"], "blocked")
        self.assertIn("manager/admin", blocked["answer"])

        coverage = {
            "answer": {
                "owners": [
                    {
                        "owner_id": "owner-1",
                        "owner_email": "ae@example.com",
                        "locked_pool_count": 150,
                        "weekly_account_target": 120,
                        "worked_account_count": 120,
                        "120_150_accounts_worked": "120/150 worked; target 120/150",
                        "coverage_hit_miss": "hit",
                        "connected_call_count": 40,
                        "40_connected_calls": "40/40",
                        "connected_call_hit_miss": "hit",
                        "friday_correction_needed": False,
                        "main_issue": "operating rhythm on track",
                        "double_tapped_account_count": 100,
                        "single_touch_account_count": 20,
                        "untouched_account_count": 30,
                        "stale_account_count": 0,
                        "dirty_account_count": 0,
                        "warm_activity_points": 2,
                    }
                ]
            },
            "source": "coverage",
            "scope": {"caller_email": "kerren.fong@staffany.com", "countries": ["Singapore"]},
            "total": 150,
            "requested_limit": 1000,
            "returned_count": 150,
            "has_more": False,
            "truncated": False,
            "confidence": "verified",
            "caveat": "coverage caveat",
            "_internal": {"companies": [], "company_deal_ids": {}, "week": self.module._week_window("2026-05-04", "2026-05-10")},
        }
        with patch.object(self.module, "_priority_account_coverage", return_value=coverage), patch.object(
            self.module, "_batch_read", side_effect=AssertionError("missing stage config must skip deal read")
        ), patch.dict(
            os.environ,
            {
                self.module.QO_PIPELINE_IDS_ENV_VAR: "",
                self.module.QO_STAGE_IDS_ENV_VAR: "",
                self.module.QO_MET_STAGE_IDS_ENV_VAR: "",
                self.module.CLOSED_WON_STAGE_IDS_ENV_VAR: "",
            },
        ):
            result = self.module.build_friday_sales_review("kerren.fong@staffany.com", countries=["Singapore"])

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["hygiene_summary"][0]["hit_miss"], "hit")
        self.assertIsNone(result["answer"]["funnel_snapshot"]["team_totals"]["qos"])
        self.assertIn("Configure HubSpot pipeline/stage IDs", result["answer"]["support_needed"][0])
        self.assertNotIn("_internal", result)

    def test_manager_chase_plan_builds_copy_ready_drafts_from_coverage_and_selected_slack_context(self):
        coverage = {
            "answer": {
                "owners": [
                    {
                        "owner_id": "owner-1",
                        "owner_email": "jeremy.wong@staffany.com",
                        "owner_name": "Jeremy",
                        "120_150_accounts_worked": "80/150 worked; target 120/150",
                        "40_connected_calls": "12/40",
                        "worked_account_count": 80,
                        "weekly_account_target": 120,
                        "connected_call_count": 12,
                        "single_touch_account_count": 4,
                        "warm_activity_points": 0,
                        "open_followup_accounts": [
                            {
                                "company_id": "123",
                                "name": "Ajumma",
                                "country": "Singapore",
                                "latest_activity_at": "2026-05-10T02:00:00Z",
                                "open_followup_task_count": 1,
                            }
                        ],
                        "untouched_accounts": [],
                        "stale_accounts": [],
                        "dirty_accounts": [],
                    }
                ]
            },
            "scope": {
                "caller_email": "kerren.fong@staffany.com",
                "scope_kind": "manager",
                "countries": ["Singapore", "Malaysia"],
                "week_start": "2026-05-04",
                "week_end": "2026-05-10",
            },
            "has_more": False,
            "truncated": False,
            "confidence": "verified",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_target_owner_id_for_scope", return_value=("321", "jeremy.wong@staffany.com")
        ), patch.object(
            self.module, "_priority_account_coverage", return_value=coverage
        ):
            result = self.module.build_manager_chase_plan(
                "kerren.fong@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                slack_context_summary="Rep needs budget range from Dom before appraisal proposal can move.",
                slack_source_permalink="https://staffany.slack.com/archives/C123/p123",
                limit=3,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["delivery_mode"], "manager_draft_only")
        self.assertFalse(result["answer"]["will_tag_reps"])
        self.assertFalse(result["answer"]["will_send_external_messages"])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        first = result["answer"]["chase_drafts"][0]
        self.assertEqual(first["trigger"], "selected_slack_blocker")
        self.assertIn("give us timeline", first["manager_draft_text"])
        self.assertIn("by EOD today", first["manager_draft_text"])
        self.assertEqual(first["source_permalink"], "https://staffany.slack.com/archives/C123/p123")
        self.assertNotIn("raw Slack transcript", json.dumps(result))
        self.assertNotIn("task body", json.dumps(result).lower())

    def test_manager_chase_plan_blocks_ae_scope(self):
        ae_scope = {"kind": "ae", "email": "ae@staffany.com", "countries": ("Singapore",), "owner_id": "owner-ae"}
        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module, "_priority_account_coverage", side_effect=AssertionError("AE chase plan must stop before coverage")
        ):
            result = self.module.build_manager_chase_plan("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("manager/admin", result["answer"])

    def test_manager_chase_plan_selected_company_uses_context_without_mutation(self):
        context = company_context("123")
        context["company"].update(
            {
                "owner_id": "owner-1",
                "owner_email": "jeremy.wong@staffany.com",
                "owner_name": "Jeremy",
                "country": "Singapore",
                "missing_fields": ["decision maker", "contract end date"],
            }
        )
        context["sales_followup_tasks"] = [
            {
                "task_id": "task-1",
                "due_at": "2026-05-11T02:00:00Z",
                "subject": "Get budget range",
                "owner_id": "owner-1",
                "status": "NOT_STARTED",
                "priority": "HIGH",
                "type": "TODO",
                "associated_via": [{"object_type": "company", "object_id": "123"}],
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.build_manager_chase_plan(
                "kerren.fong@staffany.com",
                company_ids=["https://app.hubspot.com/contacts/123/record/0-2/123"],
                limit=5,
            )

        self.assertEqual(result["answer"]["draft_count"], 2)
        self.assertEqual(result["answer"]["chase_drafts"][0]["trigger"], "open_followup_task")
        self.assertEqual(result["answer"]["chase_drafts"][0]["account"]["company_id"], "123")
        self.assertIn("Get budget range", result["answer"]["chase_drafts"][0]["evidence"])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])

    def test_find_target_accounts_by_luma_match_keys_is_event_first(self):
        calls = []

        def fake_company_search(filters, limit=5, after=None, maximum=None, sorts=None, query=None):
            calls.append({"filters": filters, "limit": limit, "maximum": maximum, "sorts": sorts})
            return {
                "results": [
                    {
                        "id": "company-domain",
                        "properties": {
                            "name": "Noci Bakehouse",
                            "domain": "noci.example",
                            "hs_is_target_account": "true",
                            "company_country": "Singapore",
                            "hubspot_owner_id": "owner-sales",
                            "type": "CUSTOMER",
                        },
                    },
                    {
                        "id": "company-name",
                        "properties": {
                            "name": "Bali Beans",
                            "domain": "balibeans.example",
                            "hs_is_target_account": "true",
                            "company_country": "Singapore",
                            "hubspot_owner_id": "owner-sales",
                            "lifecyclestage": "opportunity",
                        },
                    },
                ],
                "total": 2,
                "requested_limit": limit,
                "returned_count": 2,
                "has_more": False,
                "truncated": False,
            }

        with patch.object(self.module, "_caller_scope", return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com"}), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(
            self.module,
            "_owner_by_id",
            return_value={"id": "owner-sales", "email": "sales.owner@staffany.com", "firstName": "Sales", "lastName": "Owner"},
        ):
            result = self.module.find_target_accounts_by_luma_match_keys(
                "kaiyi@staffany.com",
                email_domains=["noci.example"],
                company_name_candidates=["Bali Beans"],
                countries=["Singapore"],
            )

        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"][0]["luma_match_reasons"], ["exact_email_domain"])
        self.assertEqual(result["answer"][1]["luma_match_reasons"], ["company_name_candidate"])
        self.assertEqual(result["answer"][0]["account_status"], "customer")
        self.assertEqual(result["answer"][1]["account_status"], "prospect")
        self.assertIn("account_status_source", result["answer"][0])
        self.assertEqual(result["answer"][0]["luma_match_key_kinds"], ["exact_email_domain"])
        self.assertEqual(result["answer"][0]["luma_match_key_count"], 1)
        self.assertEqual(result["answer"][0]["owner_email"], "sales.owner@staffany.com")
        self.assertEqual(result["answer"][0]["owner_name"], "Sales Owner")
        self.assertEqual(result["answer"][0]["account_status"], "customer")
        self.assertEqual(result["answer"][1]["account_status"], "prospect")
        self.assertEqual(result["answer"][1]["account_status_source"], "HubSpot company lifecyclestage=opportunity")
        payload = json.dumps(result)
        self.assertNotIn("luma_match_keys", payload)
        self.assertNotIn("current_tools", payload)
        self.assertLess(len(payload), 8_000)
        self.assertIn({"propertyName": "hs_is_target_account", "operator": "EQ", "value": "true"}, calls[0]["filters"])
        self.assertIn({"propertyName": "company_country", "operator": "IN", "values": ["Singapore"]}, calls[0]["filters"])
        self.assertEqual(calls[0]["limit"], self.module.HUBSPOT_SEARCH_TOTAL_LIMIT)
        self.assertEqual(calls[0]["maximum"], self.module.HUBSPOT_SEARCH_TOTAL_LIMIT)
        self.assertEqual(len(calls), 1)
        self.assertNotIn({"propertyName": "domain", "operator": "EQ", "value": "noci.example"}, calls[0]["filters"])
        self.assertNotIn({"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": "Bali Beans"}, calls[0]["filters"])
        self.assertEqual(result["scope"]["scanned_target_account_count"], 2)
        self.assertIn("No raw Luma attendees", result["caveat"])

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

    def test_find_t90_renewal_gaps_filters_renewals_first_and_batches_tasks(self):
        today = self.module.datetime.now(self.module.timezone.utc).date()
        renewal = today + self.module.timedelta(days=30)
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "numberofemployees": "25",
                "industry": "F&B",
                "contract_end_date": renewal.isoformat(),
                "current_tools": "Payboy",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "0",
            },
        }
        calls = []

        def fake_company_search(filters, limit=50, *args, **kwargs):
            calls.append(filters)
            renewal_filters = [item for item in filters if item.get("propertyName") in {"contract_end_date", "current_tool_renewal_date"}]
            if all(item.get("operator") == "NOT_HAS_PROPERTY" for item in renewal_filters):
                return {
                    "results": [],
                    "total": 0,
                    "requested_limit": limit,
                    "returned_count": 0,
                    "has_more": False,
                    "truncated": False,
                }
            renewal_filter = [item for item in renewal_filters if item.get("operator") != "NOT_HAS_PROPERTY"][0]
            if renewal_filter["propertyName"] == "contract_end_date":
                return {
                    "results": [company],
                    "total": 1,
                    "requested_limit": limit,
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                }
            return {
                "results": [],
                "total": 0,
                "requested_limit": limit,
                "returned_count": 0,
                "has_more": False,
                "truncated": False,
            }

        with patch.object(
            self.module,
            "_caller_scope",
            return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES},
        ), patch.object(self.module, "_owner_by_email", return_value={"id": "owner-jeremy"}), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(
            self.module,
            "_sales_followup_task_index_for_companies",
            return_value={
                "tasks_by_company": {"123": []},
                "metadata": {"total": 0, "requested_limit": 100, "returned_count": 0, "has_more": False, "truncated": False},
                "truncated": False,
            },
        ) as task_index, patch.object(
            self.module, "_sales_followup_task_context", side_effect=AssertionError("T-90 scan must not fan out per account")
        ), patch.object(self.module, "_batch_association_ids", return_value={"123": []}), patch.object(
            self.module, "_safe_contact_index", return_value={"123": []}
        ), patch.object(self.module, "_owner_email_by_id", return_value="jeremy.wong@staffany.com"), patch.object(
            self.module, "_owner_name_by_id", return_value="Jeremy Wong"
        ):
            result = self.module.find_t90_renewal_gaps(
                "kaiyi@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                countries=["Singapore"],
            )

        self.assertEqual(len(calls), 2)
        searched_properties = {
            item["propertyName"]
            for filters in calls
            for item in filters
            if item.get("propertyName") in {"contract_end_date", "current_tool_renewal_date"}
        }
        self.assertEqual(searched_properties, {"contract_end_date"})
        task_index.assert_called_once()
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["data_sources"]["source_of_truth"]["renewal_timing"], "HubSpot company contract_end_date")
        self.assertEqual(result["data_sources"]["source_of_truth"]["current_tools"], "HubSpot company current_tools")
        self.assertEqual(result["gap_count"], 1)
        answer = result["answer"]
        self.assertEqual(
            answer["required_output_sections"],
            ["known_t90_contract_end_date_accounts", "missing_contract_end_date_accounts", "completeness"],
        )
        self.assertEqual(answer["counts"]["renewing_account_count"], 1)
        self.assertEqual(answer["counts"]["missing_contract_end_date_account_count"], 0)
        gap = answer["known_t90_contract_end_date_accounts"][0]
        self.assertEqual(gap["company_id"], "123")
        self.assertEqual(gap["days_until_renewal"], 30)
        self.assertEqual(gap["current_tools"], "Payboy")
        self.assertEqual(gap["renewal_source_of_truth"], "contract_end_date")
        self.assertIn("missing decision-maker coverage", gap["gap_reasons"])
        self.assertIn("no open sales-owned follow-up found", " ".join(gap["gap_reasons"]))
        self.assertEqual(result["renewing_account_count"], 1)
        self.assertEqual(result["missing_renewal_date_account_count"], 0)

    def test_find_t90_renewal_gaps_accepts_explicit_date_window(self):
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Indonesia",
                "hubspot_owner_id": "owner-sarah",
                "contract_end_date": "2026-08-31",
                "current_tools": "Talenta",
                "hs_num_decision_makers": "1",
                "hs_num_contacts_with_buying_roles": "1",
            },
        }
        windows = []

        def fake_renewal_window(countries, owner_id, start_date, end_date, limit):
            windows.append((countries, owner_id, start_date.isoformat(), end_date.isoformat(), limit))
            return {
                "results": [company],
                "total": 1,
                "requested_limit": limit,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            }

        with patch.object(
            self.module,
            "_caller_scope",
            return_value={"kind": "manager", "email": "sarah.ayutania@staffany.com", "countries": ("Indonesia",), "owner_id": None},
        ), patch.object(self.module, "_company_search_by_renewal_window", side_effect=fake_renewal_window), patch.object(
            self.module,
            "_company_search_missing_renewal_dates",
            return_value={"results": [], "total": 0, "requested_limit": 250, "returned_count": 0, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_sales_followup_task_index_for_companies") as task_index, patch.object(
            self.module, "_batch_association_ids", return_value={"123": []}
        ), patch.object(self.module, "_safe_contact_index", return_value={"123": []}), patch.object(
            self.module, "_owner_email_by_id", return_value="sarah.ayutania@staffany.com"
        ), patch.object(
            self.module, "_owner_name_by_id", return_value="Sarah Ayutania"
        ):
            result = self.module.find_t90_renewal_gaps(
                "sarah.ayutania@staffany.com",
                countries=["Indonesia"],
                start_date="2026-06-01",
                end_date="2026-08-31",
            )

        task_index.assert_not_called()
        self.assertEqual(windows, [(["Indonesia"], None, "2026-06-01", "2026-08-31", self.module.HUBSPOT_SEARCH_TOTAL_LIMIT)])
        self.assertEqual(result["scope"]["renewal_window_start"], "2026-06-01")
        self.assertEqual(result["scope"]["renewal_window_end"], "2026-08-31")
        self.assertEqual(result["answer"]["known_t90_contract_end_date_accounts"][0]["contract_end_date"], "2026-08-31")
        self.assertEqual(result["answer"]["counts"]["missing_contract_end_date_requested_limit"], 250)

    def test_find_t90_renewal_gaps_excludes_current_tool_date_when_contract_date_outside_window(self):
        today = self.module.datetime.now(self.module.timezone.utc).date()
        renewal = today + self.module.timedelta(days=45)
        outside_contract = today + self.module.timedelta(days=150)
        company = {
            "id": "123",
            "properties": {
                "name": "Noci Bakehouse",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "contract_end_date": outside_contract.isoformat(),
                "current_tool_renewal_date": renewal.isoformat(),
                "current_tools": "Payboy",
                "hs_num_decision_makers": "1",
                "hs_num_contacts_with_buying_roles": "1",
            },
        }

        def fake_company_search(filters, limit=50, *args, **kwargs):
            renewal_filters = [item for item in filters if item.get("propertyName") in {"contract_end_date", "current_tool_renewal_date"}]
            if all(item.get("operator") == "NOT_HAS_PROPERTY" for item in renewal_filters):
                return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}
            renewal_filter = [item for item in renewal_filters if item.get("operator") != "NOT_HAS_PROPERTY"][0]
            if renewal_filter["propertyName"] == "current_tool_renewal_date":
                raise AssertionError("current_tool_renewal_date must not drive T-90 renewal inclusion")
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        with patch.object(
            self.module,
            "_caller_scope",
            return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES},
        ), patch.object(self.module, "_owner_by_email", return_value={"id": "owner-jeremy"}), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(
            self.module,
            "_sales_followup_task_index_for_companies",
            return_value={
                "tasks_by_company": {"123": [{"task_id": "task-1", "due_at": renewal.isoformat()}]},
                "metadata": {"total": 1, "requested_limit": 10000, "returned_count": 1, "has_more": False, "truncated": False},
                "truncated": False,
            },
        ):
            result = self.module.find_t90_renewal_gaps(
                "kaiyi@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                countries=["Singapore"],
            )

        self.assertEqual(result["renewing_account_count"], 0)
        self.assertEqual(result["answer"]["known_t90_contract_end_date_accounts"], [])
        self.assertEqual(result["answer"]["missing_contract_end_date_accounts"], [])

    def test_find_t90_renewal_gaps_lists_missing_contract_end_dates(self):
        missing_company = {
            "id": "456",
            "properties": {
                "name": "Missing Date Cafe",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-jeremy",
                "current_tool_renewal_date": "2026-06-01",
                "current_tools": "Talenta",
                "hs_num_decision_makers": "0",
                "hs_num_contacts_with_buying_roles": "0",
            },
        }

        def fake_company_search(filters, limit=50, *args, **kwargs):
            renewal_filters = [item for item in filters if item.get("propertyName") in {"contract_end_date", "current_tool_renewal_date"}]
            if all(item.get("operator") == "NOT_HAS_PROPERTY" for item in renewal_filters):
                return {
                    "results": [missing_company],
                    "total": 1,
                    "requested_limit": limit,
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                }
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        with patch.object(
            self.module,
            "_caller_scope",
            return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES},
        ), patch.object(self.module, "_owner_by_email", return_value={"id": "owner-jeremy"}), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(
            self.module,
            "_sales_followup_task_index_for_companies",
            return_value={
                "tasks_by_company": {},
                "metadata": {"total": 0, "requested_limit": 10000, "returned_count": 0, "has_more": False, "truncated": False},
                "truncated": False,
            },
        ):
            result = self.module.find_t90_renewal_gaps(
                "kaiyi@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                countries=["Singapore"],
            )

        self.assertEqual(result["renewing_account_count"], 0)
        self.assertEqual(result["missing_contract_end_date_account_count"], 1)
        self.assertEqual(result["missing_renewal_date_account_count"], 1)
        self.assertEqual(result["answer"]["known_t90_contract_end_date_accounts"], [])
        self.assertEqual(result["answer"]["counts"]["missing_contract_end_date_account_count"], 1)
        self.assertEqual(result["answer"]["missing_contract_end_date_accounts"][0]["company_id"], "456")
        missing = result["missing_renewal_date_accounts"][0]
        self.assertEqual(missing["company_id"], "456")
        self.assertEqual(missing["classification_needed"], "missing_contract_end_date")
        self.assertEqual(missing["current_tool_renewal_date"], "2026-06-01")
        self.assertEqual(missing["current_tools"], "Talenta")
        self.assertIn("contract end date", missing["missing_fields"])

    def test_find_t90_renewal_gaps_does_not_cap_missing_contract_end_dates_with_t90_limit(self):
        missing_companies = [
            {
                "id": "456",
                "properties": {
                    "name": "Missing Date Cafe",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "current_tools": "Talenta",
                },
            },
            {
                "id": "789",
                "properties": {
                    "name": "No Contract Bistro",
                    "hs_is_target_account": "true",
                    "company_country": "Singapore",
                    "hubspot_owner_id": "owner-jeremy",
                    "current_tools": "Excel",
                },
            },
        ]
        missing_limits = []

        def fake_company_search(filters, limit=50, *args, **kwargs):
            renewal_filters = [item for item in filters if item.get("propertyName") in {"contract_end_date", "current_tool_renewal_date"}]
            if all(item.get("operator") == "NOT_HAS_PROPERTY" for item in renewal_filters):
                missing_limits.append(limit)
                return {
                    "results": missing_companies,
                    "total": 2,
                    "requested_limit": limit,
                    "returned_count": 2,
                    "has_more": False,
                    "truncated": False,
                }
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        with patch.object(
            self.module,
            "_caller_scope",
            return_value={**SCOPE, "kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES},
        ), patch.object(self.module, "_owner_by_email", return_value={"id": "owner-jeremy"}), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(
            self.module,
            "_sales_followup_task_index_for_companies",
            return_value={
                "tasks_by_company": {},
                "metadata": {"total": 0, "requested_limit": 10000, "returned_count": 0, "has_more": False, "truncated": False},
                "truncated": False,
            },
        ):
            result = self.module.find_t90_renewal_gaps(
                "kaiyi@staffany.com",
                owner_email="jeremy.wong@staffany.com",
                countries=["Singapore"],
                limit=1,
            )

        self.assertEqual(result["requested_limit"], 1)
        self.assertEqual(missing_limits, [self.module.T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT])
        self.assertEqual(
            result["missing_contract_end_date_metadata"]["requested_limit"],
            self.module.T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT,
        )
        self.assertEqual(result["missing_contract_end_date_account_count"], 2)
        self.assertTrue(result["missing_contract_end_date_account_list_complete"])
        self.assertEqual(
            result["answer"]["counts"]["missing_contract_end_date_requested_limit"],
            self.module.T90_MISSING_CONTRACT_END_DATE_DEFAULT_LIMIT,
        )

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

    def test_scan_drive_event_photos_parses_drive_export_metadata(self):
        drive_files = [
            {
                "id": "drive-file-1",
                "name": "2026-05-07T12:52:58.000Z-U6CGABKG9-IMG_1319.jpg",
                "mimeType": "image/jpeg",
                "webViewLink": "https://drive.google.com/file/d/drive-file-1/view",
                "md5Checksum": "abc123",
                "slack_uploader_name": "Uploader One",
            },
            {
                "id": "drive-video-1",
                "name": "2026-05-07T12:52:58.000Z-U6CGABKG9-clip.mp4",
                "mimeType": "video/mp4",
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
            result = self.module.scan_drive_event_photos("kerren.fong@staffany.com", drive_files)

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"]["folder_id"], self.module.DRIVE_ALL_RANDOM_FOLDER_ID)
        self.assertEqual(result["answer"]["photo_count"], 1)
        self.assertEqual(result["answer"]["skipped_non_image_count"], 1)
        photo = result["answer"]["photos"][0]
        self.assertEqual(photo["photo_key"], "drive:drive-file-1")
        self.assertEqual(photo["source_pointer"]["slack_user_id"], "U6CGABKG9")
        self.assertEqual(photo["source_pointer"]["slack_uploader_name"], "Uploader One")
        self.assertEqual(photo["source_pointer"]["original_filename"], "IMG_1319.jpg")
        self.assertEqual(photo["confirmation_request"]["confirmation_owner"], "slack_uploader")
        self.assertEqual(photo["confirmation_request"]["slack_user_id"], "U6CGABKG9")
        self.assertIn("IMG_1319.jpg", photo["confirmation_request"]["prompt"])
        self.assertEqual(result["answer"]["uploader_confirmation_batches"][0]["slack_user_id"], "U6CGABKG9")
        self.assertIn("contact + company", result["answer"]["uploader_confirmation_batches"][0]["prompt"])
        self.assertFalse(photo["hubspot_custom_object_plan"]["nurture_event_photo"]["raw_image_copy"])
        self.assertEqual(photo["hubspot_custom_object_plan"]["objects"]["appearance"], "nurture_person_appearance")

    def test_scan_drive_event_photos_correlates_luma_event_date(self):
        drive_files = [
            {
                "id": "drive-file-1",
                "name": "2026-04-23T06:40:07.000Z-U03T4AQR9RS-IMG_6194.jpg",
                "mimeType": "image/jpeg",
                "slack_uploader_name": "Jan-E",
            }
        ]
        luma_events = [
            {
                "event_id": "evt-1",
                "name": "Singapore HR Happy Hour",
                "start_at": "2026-04-23T10:00:00Z",
                "end_at": "2026-04-23T13:00:00Z",
                "timezone": "Asia/Singapore",
                "url": "https://lu.ma/evt-1",
                "tags": ["Singapore", "HR Happy Hour"],
                "location_tags": ["Singapore"],
                "country_tags": ["Singapore"],
                "event_type_tags": ["HR Happy Hour"],
            },
            {
                "event_id": "evt-2",
                "name": "Jakarta HR Happy Hour",
                "start_at": "2026-04-25T10:00:00Z",
                "timezone": "Asia/Jakarta",
                "tags": ["Jakarta", "HR Happy Hour"],
                "location_tags": ["Jakarta"],
                "country_tags": ["Indonesia"],
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
            result = self.module.scan_drive_event_photos(
                "kerren.fong@staffany.com",
                drive_files,
                luma_events=luma_events,
                luma_event_auto_tag=True,
            )

        photo = result["answer"]["photos"][0]
        event_context = photo["luma_event_context"]
        self.assertEqual(event_context["auto_event_tag_status"], "verified")
        self.assertEqual(event_context["selected_event"]["event_id"], "evt-1")
        self.assertEqual(photo["hubspot_custom_object_plan"]["nurture_event"]["event_name"], "Singapore HR Happy Hour")
        self.assertEqual(photo["hubspot_custom_object_plan"]["nurture_event"]["luma_event_id"], "evt-1")
        self.assertIn("Singapore HR Happy Hour", photo["confirmation_request"]["prompt"])
        self.assertTrue(result["answer"]["luma_event_date_correlation"]["auto_event_tag_only"])
        self.assertFalse(result["answer"]["luma_event_date_correlation"]["person_auto_tag"])

    def test_scan_drive_event_photos_keeps_broad_luma_date_match_as_candidate_only(self):
        drive_files = [
            {
                "id": "drive-file-1",
                "name": "2026-05-13T06:40:07.000Z-U03T4AQR9RS-loco-visit.jpg",
                "mimeType": "image/jpeg",
                "slack_uploader_name": "Jan-E",
            }
        ]
        luma_events = [
            {
                "event_id": "evt-unrelated",
                "name": "Singapore HR Happy Hour",
                "start_at": "2026-05-13T10:00:00Z",
                "timezone": "Asia/Singapore",
                "url": "https://lu.ma/evt-unrelated",
                "tags": ["Singapore", "HR Happy Hour"],
                "location_tags": ["Singapore"],
                "country_tags": ["Singapore"],
                "event_type_tags": ["HR Happy Hour"],
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
            result = self.module.scan_drive_event_photos("kerren.fong@staffany.com", drive_files, luma_events=luma_events)

        photo = result["answer"]["photos"][0]
        self.assertEqual(photo["luma_event_context"]["auto_event_tag_status"], "needs-check")
        self.assertEqual(photo["hubspot_custom_object_plan"]["nurture_event"]["event_name"], "unclassified event photo")
        self.assertNotIn("Singapore HR Happy Hour", photo["confirmation_request"]["prompt"])
        self.assertFalse(result["answer"]["luma_event_date_correlation"]["auto_event_tag_only"])

    def test_propose_photo_people_matches_uses_context_hints_and_scoped_candidates(self):
        company = {
            "id": "company-1",
            "properties": {
                "name": "Shake Shack",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }
        contact = {
            "id": "contact-1",
            "properties": {
                "firstname": "Jane",
                "lastname": "Tan",
                "jobtitle": "Operations Manager",
                "hs_buying_role": "DECISION_MAKER",
            },
        }
        scoped_company = {
            "company_id": "company-1",
            "name": "Shake Shack",
            "country": "Singapore",
            "owner_id": "owner-sales",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_company_search_by_text",
            return_value={"results": [company], "total": 1, "requested_limit": 5, "returned_count": 1, "has_more": False, "truncated": False},
        ), patch.object(
            self.module,
            "_contact_search_by_text",
            return_value={"results": [contact], "total": 1, "requested_limit": 5, "returned_count": 1, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_scoped_contact_companies", return_value=[scoped_company]):
            result = self.module.propose_photo_people_matches(
                "kerren.fong@staffany.com",
                "slack",
                {
                    "channel_id": "C123",
                    "message_ts": "1775725993.303379",
                    "file_id": "F123",
                    "permalink": "https://staffany.slack.com/archives/C123/p1775725993303379",
                },
                context_text="this is Jane Tan from Shake Shack",
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["answer"]["photo_key"], "slack:C123:1775725993.303379:F123")
        self.assertEqual(result["answer"]["hints"]["contact_names"], ["Jane Tan"])
        self.assertEqual(result["answer"]["hints"]["company_names"], ["Shake Shack"])
        candidate = result["answer"]["contact_candidates"][0]
        self.assertEqual(candidate["contact_id"], "contact-1")
        self.assertEqual(candidate["confidence_band"], "high")
        self.assertTrue(candidate["requires_human_confirmation"])
        self.assertEqual(candidate["associated_companies"][0]["company_id"], "company-1")
        self.assertEqual(result["answer"]["confirmation_request"]["confirmation_owner"], "unknown_uploader")
        self.assertIn("confirm", result["answer"]["confirmation_request"]["prompt"])

    def test_propose_photo_people_matches_asks_for_clue_when_image_has_no_context(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_search_by_text", side_effect=AssertionError("no clues means no HubSpot company search")
        ), patch.object(
            self.module, "_contact_search_by_text", side_effect=AssertionError("no clues means no HubSpot contact search")
        ):
            result = self.module.propose_photo_people_matches(
                "kerren.fong@staffany.com",
                "drive",
                {"id": "drive-file-1", "name": "IMG_1319.jpg", "mimeType": "image/jpeg"},
            )

        self.assertEqual(result["answer"]["contact_candidates"], [])
        self.assertEqual(result["answer"]["company_candidates"], [])
        self.assertEqual(result["answer"]["missing_clue_prompt"], "company name?")
        self.assertEqual(result["answer"]["confirmation_request"]["confirmation_owner"], "unknown_uploader")
        self.assertIn("company name?", result["answer"]["confirmation_request"]["prompt"])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])

    def test_plan_event_photo_followup_previews_note_task_and_whatsapp_draft(self):
        admin_scope = {"kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES, "owner_id": None}
        company = {
            "id": "company-1",
            "properties": {
                "name": "Shake Shack",
                "hs_is_target_account": "true",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-sales",
            },
        }

        with patch.object(self.module, "_caller_scope", return_value=admin_scope), patch.object(
            self.module, "_assert_company_access", return_value=company
        ), patch.object(
            self.module,
            "plan_hubspot_writeback",
            return_value={
                "answer": {
                    "preview_id": "preview-1",
                    "actions": [{"company_id": "company-1", "contact_id": "contact-1", "source_type": "event_photo"}],
                    "will_mutate_hubspot": False,
                },
                "confidence": "verified",
            },
        ) as writeback:
            result = self.module.plan_event_photo_followup(
                "kaiyi@staffany.com",
                {
                    "contact_id": "contact-1",
                    "display_name": "Jane T.",
                    "associated_companies": [{"company_id": "company-1", "name": "Shake Shack"}],
                    "photo_key": "slack:C123:1775725993.303379:F123",
                    "source_pointer": {"source_type": "slack", "permalink": "https://staffany.slack.com/archives/C123/p1775725993303379"},
                    "evidence": ["contact name exact match"],
                    "confidence_band": "high",
                },
                event_name="AI Automation Workshop",
            )

        action = writeback.call_args.args[1][0]
        self.assertEqual(action["company_id"], "company-1")
        self.assertEqual(action["contact_id"], "contact-1")
        self.assertEqual(action["source_type"], "event_photo")
        self.assertIn("WhatsApp follow-up", action["task"])
        self.assertIn("manual WhatsApp follow-up", action["note_summary"])
        self.assertIn("AI Automation Workshop", result["answer"]["draft_whatsapp_copy"])
        self.assertIn("T10:00:00+08:00", result["answer"]["whatsapp_followup_task"]["due_at"])
        self.assertEqual(result["answer"]["preview_id"], "preview-1")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertFalse(result["answer"]["whatsapp_auto_send"])

    def test_build_pre_demo_game_plans_caps_selected_accounts_and_marks_missing_evidence(self):
        contexts = []
        for index in range(1, 7):
            context = company_context(str(index))
            context["company"].update(
                {
                    "name": f"Account {index}",
                    "headcount": "80",
                    "industry": "F&B",
                    "contract_end_date": "2026-12-31",
                    "decision_maker_count": 0,
                    "buying_role_contact_count": 0,
                    "sales_followup_task_count": 1,
                }
            )
            contexts.append(context)

        def fake_company_context(company_id, scope):
            return contexts[int(company_id) - 1]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", side_effect=fake_company_context
        ) as company_context_lookup:
            result = self.module.build_pre_demo_game_plans(
                "kerren.fong@staffany.com",
                [
                    "1",
                    "https://app-na2.hubspot.com/contacts/4137076/record/0-2/2",
                    "3",
                    "4",
                    "5",
                    "6",
                ],
            )

        self.assertEqual(company_context_lookup.call_count, 5)
        self.assertEqual(result["returned_count"], 5)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["confidence"], "needs-check")
        first = result["answer"][0]
        self.assertEqual(first["company_id"], "1")
        self.assertEqual(first["static_information"]["number_of_employees"], "80")
        self.assertEqual(first["static_information"]["current_tools"], "current tool needed")
        self.assertIn("pricing needed", first["game_plan_a"]["package_or_pricing"])
        self.assertEqual(len(first["relevant_name_drops"]), 3)
        self.assertNotIn("case-study match needed", first["relevant_name_drops"])
        self.assertEqual(len(first["case_study_matches"]), 3)
        self.assertIn("lead source", first["missing_evidence"])
        self.assertIn("social/gated research stays manual-check", result["caveat"])

    def test_bmc_case_studies_require_full_video_review_metadata(self):
        cases = self.module._load_case_study_catalog()
        bmc_cases = [case for case in cases if case.get("source_type") == "bmc_podcast"]

        self.assertEqual(len(bmc_cases), 21)
        for case in bmc_cases:
            review = case.get("full_video_review") or {}
            evidence_refs = case.get("evidence_refs") or []
            self.assertTrue(case.get("approved_for_name_drops"))
            self.assertEqual(case.get("approval_basis"), "bmc_podcast_full_video_review")
            self.assertEqual(review.get("primary_spoken_source"), "youtube_auto_caption")
            self.assertTrue(review.get("full_transcript_available"))
            self.assertEqual(review.get("reviewer_status"), "full_transcript_reviewed")
            self.assertGreater(review.get("transcript_word_count") or 0, 0)
            self.assertTrue(review.get("first_timestamp"))
            self.assertTrue(review.get("last_timestamp"))
            self.assertEqual(review.get("gaps") or [], [])
            self.assertTrue(case.get("do_not_claim"))
            self.assertTrue(evidence_refs)
            for ref in evidence_refs:
                self.assertRegex(ref.get("timestamp") or "", r"^\d{2}:\d{2}:\d{2}")
                self.assertTrue((ref.get("source_path") or "").startswith("research/raw/online/"))
                self.assertGreater(ref.get("line") or 0, 0)

    def test_find_sales_case_studies_returns_bmc_matches_for_brainstorm_query(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
            result = self.module.find_sales_case_studies(
                "kerren.fong@staffany.com",
                sales_moment="demo",
                query="F&B central kitchen franchise SOP quality control payroll scheduling",
                limit=10,
            )

        matches = result["answer"]["case_study_matches"]
        self.assertFalse(result["will_mutate_hubspot"])
        self.assertNotIn("case-study match needed", result["answer"]["relevant_name_drops"])
        self.assertTrue(any(match.get("source_type") == "bmc_podcast" for match in matches))
        bmc_match = next(match for match in matches if match.get("source_type") == "bmc_podcast")
        self.assertEqual(bmc_match["full_video_review"]["reviewer_status"], "full_transcript_reviewed")
        self.assertTrue(bmc_match["evidence_refs"])

    def test_find_sales_case_studies_returns_needed_when_no_good_match(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
            result = self.module.find_sales_case_studies(
                "kerren.fong@staffany.com",
                sales_moment="pre_demo",
                query="enterprise fintech core banking AML reconciliation",
            )

        self.assertEqual(result["answer"]["case_study_matches"], [])
        self.assertEqual(result["answer"]["relevant_name_drops"], ["case-study match needed"])
        self.assertEqual(result["missing_evidence"], ["case-study match needed"])

    def test_build_pre_demo_game_plans_public_research_default_off(self):
        context = company_context("123")
        context["company"].update({"headcount": "80", "industry": "F&B"})

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["123"])

        self.assertNotIn("public_research", result)
        self.assertNotIn("public_research_signals", result["answer"][0]["research_stalking_signal"])

    def test_build_pre_demo_game_plans_enriches_public_research_without_mutation(self):
        context = company_context("123")
        context["company"].update({"headcount": "80", "industry": "F&B", "name": "Noci Bakehouse"})
        research_row = {
            "input_company": {"company_id": "123"},
            "game_plan_inputs": {
                "public_signals": [{"signal_type": "hiring_signal", "confidence": "needs-check"}],
                "source_evidence_refs": [{"source_type": "company_website", "source_url": "https://noci.example"}],
                "outreach_angles": ["Use hiring as a discovery angle."],
                "manual_checks_needed": [{"source_type": "linkedin_manual", "source_url": "https://linkedin.example"}],
                "recommended_next_tool": "search_exa_people_candidates",
            },
            "missing_evidence": ["Noci Bakehouse: no public decision-maker hint found"],
            "recommended_next_tool": "search_exa_people_candidates",
            "will_mutate_hubspot": False,
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ), patch.object(
            self.module,
            "_public_research_for_game_plan_contexts",
            return_value=({"123": research_row}, {"estimated_credits": 3}, ["Noci Bakehouse: no public decision-maker hint found"]),
        ) as public_research:
            result = self.module.build_pre_demo_game_plans(
                "kerren.fong@staffany.com",
                ["123"],
                include_public_research=True,
                research_mode="light",
            )

        public_research.assert_called_once()
        self.assertFalse(result["public_research"]["will_mutate_hubspot"])
        self.assertEqual(result["public_research"]["research_mode"], "light")
        signal = result["answer"][0]["research_stalking_signal"]
        self.assertEqual(signal["public_research_signals"][0]["signal_type"], "hiring_signal")
        self.assertEqual(signal["recommended_next_tool"], "search_exa_people_candidates")
        self.assertIn("Noci Bakehouse: no public decision-maker hint found", result["missing_evidence"])

    def test_build_pre_demo_game_plans_blocks_when_account_outside_scope(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=None
        ):
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["999"])

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("outside caller scope", result["answer"])

    def test_build_pre_demo_game_plans_does_not_expose_raw_task_body(self):
        context = company_context("123")
        context["company"].update({"headcount": "30", "industry": "Retail"})
        context["sales_followup_tasks"] = [
            {
                "task_id": "task-1",
                "subject": "Safe subject",
                "task_body": "raw task body must never appear",
            }
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["123"])

        self.assertNotIn("raw task body", json.dumps(result))
        self.assertNotIn("Safe subject", json.dumps(result))
        self.assertIn("pricing", result["missing_evidence"])

    def test_build_pre_demo_game_plans_preserves_slack_source_thread(self):
        source_thread_url = "https://staffany.slack.com/archives/C04MSJ1BGF9/p1778471025436219?thread_ts=1776659145.164259&channel=C04MSJ1BGF9"
        context = company_context("32662274616")
        context["company"].update({"name": "Marugame Udon", "headcount": "3000", "industry": "F&B"})

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_context", return_value=context
        ):
            result = self.module.build_pre_demo_game_plans(
                "kerren.fong@staffany.com",
                ["https://app-na2.hubspot.com/contacts/4137076/record/0-2/32662274616"],
                source_slack_thread_url=source_thread_url,
            )

        self.assertEqual(result["source_thread"]["url"], source_thread_url)
        self.assertEqual(result["source_thread"]["source_type"], "slack_thread")
        first = result["answer"][0]
        self.assertEqual(first["source_thread"]["label"], "Source thread")
        self.assertEqual(first["writeback_source_evidence"]["source_url"], source_thread_url)
        self.assertEqual(first["writeback_source_evidence"]["source_type"], "slack_thread")
        self.assertNotIn("Pre-meeting notes can be shared here", json.dumps(result))

    def test_build_pre_demo_game_plans_resolves_exact_scoped_company_name(self):
        search_calls = []

        def fake_company_search(filters, limit=20, after=None, maximum=1000, sorts=None):
            search_calls.append(filters)
            name_filter = next((item for item in filters if item.get("propertyName") == "name"), {})
            if name_filter.get("operator") == "EQ":
                return {
                    "results": [
                        {
                            "id": "123",
                            "properties": {
                                "name": "Noci Bakehouse",
                                "domain": "noci.example",
                                "hs_is_target_account": "true",
                                "company_country": "Singapore",
                                "hubspot_owner_id": "owner-1",
                            },
                        }
                    ],
                    "total": 1,
                    "requested_limit": limit,
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                }
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(self.module, "_company_context", return_value=company_context("123")) as company_context_lookup:
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["Noci Bakehouse"])

        self.assertEqual(result["answer"][0]["company_id"], "123")
        self.assertEqual(result["resolved_matches"][0]["match_type"], "exact")
        self.assertEqual(company_context_lookup.call_args.args[0], "123")
        first_filters = search_calls[0]
        self.assertIn({"propertyName": "hs_is_target_account", "operator": "EQ", "value": "true"}, first_filters)
        self.assertIn({"propertyName": "company_country", "operator": "IN", "values": ["Singapore", "Malaysia"]}, first_filters)

    def test_build_pre_demo_game_plans_resolves_compacted_company_name(self):
        search_values = []

        def fake_company_search(filters, limit=20, after=None, maximum=1000, sorts=None):
            name_filter = next((item for item in filters if item.get("propertyName") == "name"), {})
            search_values.append(name_filter.get("value"))
            if name_filter.get("operator") == "CONTAINS_TOKEN" and name_filter.get("value") == "tunglok":
                return {
                    "results": [
                        {
                            "id": "274349049547",
                            "properties": {
                                "name": "Tunglok Group",
                                "domain": "tunglok.com",
                                "hs_is_target_account": "true",
                                "company_country": "Singapore",
                                "hubspot_owner_id": "owner-jeremy",
                            },
                        }
                    ],
                    "total": 1,
                    "requested_limit": limit,
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                }
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        context = company_context("274349049547")
        context["company"]["name"] = "Tunglok Group"

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(self.module, "_company_context", return_value=context) as company_context_lookup:
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["Tung Lok Group"])

        self.assertEqual(result["answer"][0]["company_id"], "274349049547")
        self.assertEqual(result["resolved_matches"][0]["match_type"], "compact_exact")
        self.assertIn("tunglok", search_values)
        self.assertEqual(company_context_lookup.call_args.args[0], "274349049547")

    def test_build_pre_demo_game_plans_blocks_ambiguous_company_name(self):
        def fake_company_search(filters, limit=20, after=None, maximum=1000, sorts=None):
            name_filter = next((item for item in filters if item.get("propertyName") == "name"), {})
            if name_filter.get("operator") == "CONTAINS_TOKEN":
                return {
                    "results": [
                        {
                            "id": "123",
                            "properties": {
                                "name": "Noci Bakehouse",
                                "domain": "noci.example",
                                "hs_is_target_account": "true",
                                "company_country": "Singapore",
                                "hubspot_owner_id": "owner-1",
                            },
                        },
                        {
                            "id": "456",
                            "properties": {
                                "name": "Noci Bakehouse KL",
                                "domain": "noci-kl.example",
                                "hs_is_target_account": "true",
                                "company_country": "Malaysia",
                                "hubspot_owner_id": "owner-2",
                            },
                        },
                    ],
                    "total": 2,
                    "requested_limit": limit,
                    "returned_count": 2,
                    "has_more": False,
                    "truncated": False,
                }
            return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_company_search", side_effect=fake_company_search
        ), patch.object(self.module, "_company_context", side_effect=AssertionError("ambiguous name must not build a plan")):
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["Noci"])

        self.assertEqual(result["confidence"], "blocked")
        candidates = result["answer"]["ambiguous_matches"][0]["candidates"]
        self.assertEqual([candidate["company_id"] for candidate in candidates], ["123", "456"])
        self.assertIn("ambiguous", result["caveat"])

    def test_build_pre_demo_game_plans_blocks_unknown_company_name(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_company_search",
            return_value={"results": [], "total": 0, "requested_limit": 10, "returned_count": 0, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_company_context", side_effect=AssertionError("unknown name must not build a plan")):
            result = self.module.build_pre_demo_game_plans("kerren.fong@staffany.com", ["No Such Account"])

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"]["not_found"][0]["input"], "No Such Account")
        self.assertIn("no scoped HubSpot target-account match", result["answer"]["not_found"][0]["reason"])

    def test_list_inbound_threads_returns_summaries_only(self):
        thread = {
            "id": "thread-1",
            "status": "OPEN",
            "associatedContactId": "contact-1",
            "latestMessageTimestamp": "2026-05-10T01:00:00Z",
            "threadAssociations": {"associatedTicketId": "ticket-1"},
        }
        access_context = {
            "allowed": True,
            "contact": {"id": "contact-1", "properties": {"email": "buyer@noci.example", "firstname": "Buyer", "jobtitle": "Owner"}},
            "companies": [
                {
                    "id": "company-1",
                    "properties": {
                        "name": "Noci Bakehouse",
                        "domain": "noci.example",
                        "company_country": "Singapore",
                        "hubspot_owner_id": "owner-1",
                        "hs_is_target_account": "true",
                    },
                }
            ],
            "scope_status": "company_scoped",
            "associated_contact_id": "contact-1",
            "associated_ticket_id": "ticket-1",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_conversation_threads",
            return_value={"results": [thread], "requested_limit": 20, "returned_count": 1, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_marketing_access_context_for_thread", return_value=access_context):
            result = self.module.list_inbound_threads("kerren.fong@staffany.com")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["answer"][0]["thread_id"], "thread-1")
        self.assertEqual(result["answer"][0]["contact"]["email_domain"], "noci.example")
        self.assertNotIn("messages", result["answer"][0])
        self.assertIn("Summaries only", result["caveat"])

    def test_get_inbound_thread_context_returns_single_thread_text(self):
        thread = {
            "id": "thread-1",
            "status": "OPEN",
            "associatedContactId": "contact-1",
            "latestMessageTimestamp": "2026-05-10T01:00:00Z",
            "threadAssociations": {"associatedTicketId": "ticket-1"},
        }
        access_context = {
            "allowed": True,
            "contact": {"id": "contact-1", "properties": {"email": "buyer@noci.example"}},
            "companies": [],
            "scope_status": "unresolved_company_scope",
            "associated_contact_id": "contact-1",
            "associated_ticket_id": "ticket-1",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_get", return_value=thread
        ), patch.object(self.module, "_marketing_access_context_for_thread", return_value=access_context), patch.object(
            self.module,
            "_conversation_messages",
            return_value={
                "results": [{"id": "message-1", "direction": "INCOMING", "text": "Can I book a RaD demo?", "attachments": [{}]}],
                "requested_limit": 100,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ):
            result = self.module.get_inbound_thread_context("kerren.fong@staffany.com", "thread-1")

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["full_text_scope"], "single_selected_thread_only")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["answer"]["messages"][0]["text"], "Can I book a RaD demo?")
        self.assertEqual(result["answer"]["messages"][0]["attachment_count"], 1)

    def test_audit_inbound_sla_computes_slack_ack_touch_and_duplicate_group(self):
        thread = {
            "id": "thread-1",
            "status": "OPEN",
            "associatedContactId": "contact-1",
            "createdAt": "2026-05-11T03:54:51Z",
            "latestMessageTimestamp": "2026-05-11T05:03:22Z",
            "latestMessageReceivedTimestamp": "2026-05-11T03:54:51Z",
            "threadAssociations": {"associatedTicketId": "ticket-1"},
        }
        access_context = {
            "allowed": True,
            "contact": {
                "id": "contact-1",
                "properties": {
                    "email": "buyer@noci.example",
                    "firstname": "Buyer",
                    "jobtitle": "Owner",
                    "hs_buying_role": "DECISION_MAKER",
                    "utm_campaign": "rad",
                },
            },
            "companies": [
                {
                    "id": "company-1",
                    "properties": {
                        "name": "Noci Bakehouse",
                        "domain": "noci.example",
                        "company_country": "Singapore",
                        "hubspot_owner_id": "owner-1",
                        "hs_is_target_account": "true",
                        "current_tools": "manual scheduling",
                        "hs_num_decision_makers": "1",
                    },
                }
            ],
            "scope_status": "company_scoped",
            "associated_contact_id": "contact-1",
            "associated_ticket_id": "ticket-1",
        }
        slack_alerts = [
            {
                "alert_id": "1778471691.420279",
                "source": "RaD",
                "alert_time": "2026-05-11T03:54:51Z",
                "owner_tagged_time": "2026-05-11T03:58:22Z",
                "owner_ack_time": "2026-05-11T04:24:39Z",
                "first_customer_touch_time": "2026-05-11T04:46:31Z",
                "outcome_time": "2026-05-11T05:03:22Z",
                "assigned_owner": "Jeremy",
                "status": "set",
                "outcome": "set",
                "associated_contact_id": "contact-1",
            },
            {
                "alert_id": "1778471832.997089",
                "source": "RaD",
                "alert_time": "2026-05-11T03:57:12Z",
                "assigned_owner": "Jeremy",
                "associated_contact_id": "contact-1",
            },
        ]
        activity_snapshot = {
            "first_customer_touch_at": "2026-05-11T04:46:31Z",
            "latest_activity_at": "2026-05-11T05:03:22Z",
            "activity_counts": {"whatsapp_communications": 0, "completed_calls": 1, "notes": 0, "completed_tasks": 0, "meetings": 1},
            "deal_stage_status": "verified",
            "truncated": False,
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_conversation_threads",
            return_value={"results": [thread], "requested_limit": 20, "returned_count": 1, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_marketing_access_context_for_thread", return_value=access_context), patch.object(
            self.module,
            "_conversation_messages",
            return_value={
                "results": [{"id": "message-1", "direction": "INCOMING", "createdAt": "2026-05-11T03:54:51Z", "text": "Can I book a RaD demo?"}],
                "requested_limit": 100,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(self.module, "_inbound_activity_snapshot_for_thread", return_value=activity_snapshot), patch.object(
            self.module, "_owner_email_by_id", return_value="jeremy.wong@staffany.com"
        ):
            result = self.module.audit_inbound_sla("kerren.fong@staffany.com", slack_alerts=slack_alerts)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["rollup"]["row_count"], 2)
        self.assertEqual(result["answer"]["rollup"]["sla_miss_count"], 2)
        first_row = result["answer"]["audit_rows"][0]
        self.assertEqual(first_row["sla_status"], "miss")
        self.assertEqual(first_row["ack_sla_status"], "miss")
        self.assertEqual(first_row["first_touch_sla_status"], "miss")
        self.assertEqual(first_row["duplicate_group"], "contact:contact-1")
        self.assertEqual(first_row["outcome"], "set")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["answer"]["duplicate_summary"][0]["alert_count"], 2)

    def test_audit_inbound_sla_with_slack_only_alerts_skips_hubspot_scan(self):
        slack_alerts = [
            {
                "alert_id": "wa-1054",
                "source": "WhatsApp",
                "alert_time": "2026-05-11T10:54:00+07:00",
                "owner_ack_time": "2026-05-11T11:24:00+07:00",
                "first_customer_touch_time": "2026-05-11T11:46:00+07:00",
                "assigned_owner": "Jeremy",
                "status": "called",
                "outcome": "set",
            },
            {
                "alert_id": "payroll-1131",
                "source": "portal payroll interest",
                "alert_time": "2026-05-11T11:31:00+07:00",
                "owner_ack_time": "2026-05-11T11:46:00+07:00",
                "first_customer_touch_time": "2026-05-11T11:46:00+07:00",
                "assigned_owner": "Jeremy",
                "status": "called",
                "outcome": "set",
            },
        ]

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_conversation_threads"
        ) as conversation_threads:
            result = self.module.audit_inbound_sla("kerren.fong@staffany.com", slack_alerts=slack_alerts)

        conversation_threads.assert_not_called()
        self.assertEqual(result["scope"]["hubspot_match_mode"], "skipped_no_safe_ids")
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["answer"]["audit_rows"][0]["sla_status"], "miss")
        self.assertEqual(result["answer"]["audit_rows"][1]["ack_sla_status"], "miss")
        self.assertEqual(result["answer"]["audit_rows"][1]["first_touch_sla_status"], "pass")
        self.assertEqual(result["confidence"], "needs-check")

    def test_audit_inbound_sla_without_slack_alerts_marks_ack_needs_check(self):
        thread = {
            "id": "thread-1",
            "status": "OPEN",
            "associatedContactId": "contact-1",
            "createdAt": "2026-05-11T03:54:51Z",
            "latestMessageTimestamp": "2026-05-11T04:02:00Z",
            "latestMessageReceivedTimestamp": "2026-05-11T03:54:51Z",
            "threadAssociations": {"associatedTicketId": "ticket-1"},
        }
        access_context = {
            "allowed": True,
            "contact": {"id": "contact-1", "properties": {"email": "buyer@noci.example", "utm_campaign": "rad"}},
            "companies": [
                {
                    "id": "company-1",
                    "properties": {
                        "name": "Noci Bakehouse",
                        "domain": "noci.example",
                        "company_country": "Singapore",
                        "hubspot_owner_id": "owner-1",
                        "hs_is_target_account": "true",
                        "current_tools": "manual scheduling",
                    },
                }
            ],
            "scope_status": "company_scoped",
            "associated_contact_id": "contact-1",
            "associated_ticket_id": "ticket-1",
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_conversation_threads",
            return_value={"results": [thread], "requested_limit": 20, "returned_count": 1, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_marketing_access_context_for_thread", return_value=access_context), patch.object(
            self.module,
            "_conversation_messages",
            return_value={
                "results": [
                    {"id": "message-1", "direction": "INCOMING", "createdAt": "2026-05-11T03:54:51Z", "text": "Can I book a RaD demo?"},
                    {"id": "message-2", "direction": "OUTGOING", "createdAt": "2026-05-11T04:02:00Z", "text": "Calling you now."},
                ],
                "requested_limit": 100,
                "returned_count": 2,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_inbound_activity_snapshot_for_thread",
            return_value={
                "first_customer_touch_at": "",
                "latest_activity_at": "",
                "activity_counts": {"whatsapp_communications": 0, "completed_calls": 0, "notes": 0, "completed_tasks": 0, "meetings": 0},
                "deal_stage_status": "needs-check",
                "truncated": False,
            },
        ), patch.object(self.module, "_owner_email_by_id", return_value="jeremy.wong@staffany.com"):
            result = self.module.audit_inbound_sla("kerren.fong@staffany.com")

        row = result["answer"]["audit_rows"][0]
        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(row["ack_sla_status"], "needs-check")
        self.assertEqual(row["first_touch_sla_status"], "pass")
        self.assertEqual(row["source"], "RaD")
        self.assertIn("deal stage needs-check", row["hubspot_gaps"])

    def test_list_marketing_campaigns_blocks_ae_scope(self):
        ae_scope = {"kind": "ae", "email": "rep@staffany.com", "countries": ("Singapore",), "owner_id": "owner-1"}
        with patch.object(self.module, "_caller_scope", return_value=ae_scope), patch.object(
            self.module, "_marketing_campaign_search", side_effect=AssertionError("AE must not list campaigns")
        ):
            result = self.module.list_marketing_campaigns("rep@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("manager/admin", result["answer"])

    def test_get_campaign_assets_marks_podcast_metrics_needs_check(self):
        campaign = {"id": "campaign-1", "properties": {"hs_name": "Podcast push", "hs_campaign_status": "ACTIVE"}}
        asset_data = {
            "asset_types": ["PODCAST_EPISODE"],
            "assets_by_type": {
                "PODCAST_EPISODE": {
                    "assets": [{"asset_type": "PODCAST_EPISODE", "asset_id": "episode-1", "name": "Founder interview"}],
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                    "metrics_caveat": "No metrics available for this HubSpot campaign asset type.",
                }
            },
            "requested_limit": 50,
            "has_more": False,
            "truncated": False,
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_get_campaign", return_value=campaign
        ), patch.object(self.module, "_campaign_assets", return_value=asset_data):
            result = self.module.get_campaign_assets("kerren.fong@staffany.com", "campaign-1", ["PODCAST_EPISODE"])

        self.assertEqual(result["confidence"], "needs-check")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertIn("Podcast episodes", result["caveat"])
        self.assertEqual(result["answer"]["assets_by_type"]["PODCAST_EPISODE"]["assets"][0]["asset_id"], "episode-1")

    def test_marketing_campaign_attribution_keeps_outcome_summary_when_contact_search_truncated(self):
        campaign = {"id": "campaign-1", "properties": {"hs_name": "Salary Benchmark", "hs_utm": "salary-benchmark"}}
        contacts = [
            {
                "id": f"contact-{index}",
                "properties": {
                    "email": f"buyer{index}@account{index}.example",
                    "recent_conversion_event_name": "Salary Benchmark",
                },
            }
            for index in range(20)
        ]

        companies = [
            {
                "id": f"company-{index}",
                "properties": {
                    "name": f"Account {index}",
                    "domain": f"account{index}.example",
                    "company_country": "Singapore",
                    "hs_is_target_account": "true",
                },
            }
            for index in range(20)
        ]

        def fake_batch_association_ids(object_type, target_type, ids):
            if object_type == "contacts" and target_type == "companies":
                return {contact_id: [f"company-{contact_id.rsplit('-', 1)[-1]}"] for contact_id in ids}
            if object_type == "companies" and target_type == "deals":
                return {
                    company_id: {
                        "company-0": ["deal-qo"],
                        "company-1": ["deal-qo-met"],
                        "company-2": ["deal-closed-won"],
                    }.get(company_id, [])
                    for company_id in ids
                }
            raise AssertionError(f"Unexpected association read: {object_type} -> {target_type}")

        def fake_batch_read(object_type, ids, properties):
            if object_type == "companies":
                company_by_id = {company["id"]: company for company in companies}
                return [company_by_id[company_id] for company_id in ids if company_id in company_by_id]
            if object_type == "deals":
                deal_by_id = {
                    "deal-qo": {"id": "deal-qo", "properties": {"pipeline": "sales", "dealstage": "stage-qo", "dealname": "QO"}},
                    "deal-qo-met": {"id": "deal-qo-met", "properties": {"pipeline": "sales", "dealstage": "stage-qo-met", "dealname": "QO Met"}},
                    "deal-closed-won": {"id": "deal-closed-won", "properties": {"pipeline": "sales", "dealstage": "stage-cw", "dealname": "Won"}},
                }
                return [deal_by_id[deal_id] for deal_id in ids if deal_id in deal_by_id]
            raise AssertionError(f"Unexpected batch read: {object_type}")

        stage_config = {
            "pipeline_ids": ["sales"],
            "qo_stage_ids": ["stage-qo"],
            "qo_met_stage_ids": ["stage-qo-met"],
            "closed_won_stage_ids": ["stage-cw"],
            "configured": True,
            "missing": [],
        }
        contact_data = {
            "results": contacts,
            "searched_properties": ["recent_conversion_event_name"],
            "search_run_count": 1,
            "errors": [],
            "requested_limit": 100,
            "returned_count": 20,
            "has_more": True,
            "truncated": True,
        }

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_marketing_campaign_search", return_value={"results": [campaign], "truncated": False}
        ), patch.object(
            self.module,
            "_campaign_assets",
            return_value={"asset_types": [], "assets_by_type": {}, "requested_limit": 100, "has_more": False, "truncated": False},
        ), patch.object(
            self.module, "_marketing_contact_campaign_search", return_value=contact_data
        ), patch.object(
            self.module, "_batch_association_ids", side_effect=fake_batch_association_ids
        ), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(
            self.module, "_friday_review_stage_config", return_value=stage_config
        ):
            result = self.module.get_marketing_campaign_attribution("kerren.fong@staffany.com", campaign_name="Salary Benchmark")

        summary = result["answer"]["outcome_summary"]
        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(summary["deal_stage_counts"]["qos"], 1)
        self.assertEqual(summary["deal_stage_counts"]["qo_met"], 1)
        self.assertEqual(summary["deal_stage_counts"]["closed_won"], 1)
        self.assertEqual(summary["matched_contact_count"], 20)
        self.assertEqual(len(result["answer"]["matched_contact_samples"]), self.module.MARKETING_ATTRIBUTION_DETAIL_RETURN_LIMIT)
        self.assertNotIn("matched_contacts", result["answer"])
        self.assertIn("contact_source_search_truncated", summary["truncation_reasons"])

    def test_get_marketing_touch_context_combines_scoped_sources_without_mutation(self):
        contact = {
            "id": "contact-1",
            "properties": {
                "email": "buyer@noci.example",
                "recent_conversion_event_name": "NurtureAny Podcast",
            },
        }
        company = {
            "id": "company-1",
            "properties": {
                "name": "Noci Bakehouse",
                "domain": "noci.example",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-1",
                "hs_is_target_account": "true",
                "campaign": "NurtureAny Podcast",
            },
        }
        campaign = {"id": "campaign-1", "properties": {"hs_name": "NurtureAny Podcast"}}

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module,
            "_marketing_access_context_for_contact",
            return_value={"allowed": True, "contact": contact, "companies": [company], "scope_status": "company_scoped"},
        ), patch.object(
            self.module,
            "_conversation_threads",
            return_value={"results": [], "requested_limit": 5, "returned_count": 0, "has_more": False, "truncated": False},
        ), patch.object(self.module, "_marketing_campaign_search", return_value={"results": [campaign], "truncated": False}), patch.object(
            self.module,
            "_campaign_assets",
            return_value={
                "assets_by_type": {"PODCAST_EPISODE": {"assets": [{"asset_id": "episode-1", "name": "Founder interview"}]}},
                "asset_types": ["PODCAST_EPISODE"],
                "truncated": False,
            },
        ):
            result = self.module.get_marketing_touch_context("kerren.fong@staffany.com", contact_id="contact-1")

        self.assertEqual(result["confidence"], "needs-check")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["answer"]["contact"]["email_domain"], "noci.example")
        self.assertEqual(result["answer"]["campaigns"][0]["campaign_id"], "campaign-1")
        self.assertEqual(result["answer"]["podcast_campaign_evidence"][0]["assets"][0]["asset_id"], "episode-1")

    def test_get_marketing_campaign_attribution_counts_scoped_deal_stages(self):
        campaign = {
            "id": "campaign-1",
            "properties": {
                "hs_name": "20251015_2025SalaryBenchmark",
                "hs_utm": "155425489-20251015_2025SalaryBenchmark",
                "hs_start_date": "2025-10-15",
            },
        }
        asset_data = {
            "asset_types": ["FORM"],
            "assets_by_type": {
                "FORM": {
                    "assets": [{"asset_type": "FORM", "asset_id": "form-1", "name": "[MKT] [SG] [25Q3] LeadMagnet_2025 Salary Benchmark Report"}],
                    "returned_count": 1,
                    "has_more": False,
                    "truncated": False,
                }
            },
            "requested_limit": 50,
            "has_more": False,
            "truncated": False,
        }
        contact = {
            "id": "contact-1",
            "properties": {
                "email": "buyer@noci.example",
                "utm_campaign": "155425489-20251015_2025SalaryBenchmark",
            },
        }
        company = {
            "id": "company-1",
            "properties": {
                "name": "Noci Bakehouse",
                "domain": "noci.example",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-1",
                "hs_is_target_account": "true",
            },
        }
        deals = [
            {"id": "deal-1", "properties": {"dealname": "Noci QO", "pipeline": "pipe-1", "dealstage": "qo", "amount": "1000"}},
            {"id": "deal-2", "properties": {"dealname": "Noci won", "pipeline": "pipe-1", "dealstage": "won", "amount": "2000"}},
        ]
        stage_config = {
            "pipeline_ids": {"pipe-1"},
            "qo_stage_ids": {"qo"},
            "qo_met_stage_ids": {"qomet"},
            "closed_won_stage_ids": {"won"},
            "configured": True,
            "required_env": [],
        }

        def fake_batch_association_ids(from_type, to_type, ids):
            if from_type == "contacts" and to_type == "companies":
                return {"contact-1": ["company-1"]}
            if from_type == "companies" and to_type == "deals":
                return {"company-1": ["deal-1", "deal-2"]}
            return {}

        def fake_batch_read(object_type, ids, properties):
            if object_type == "companies":
                return [company]
            if object_type == "deals":
                return deals
            return []

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_get_campaign", return_value=campaign
        ), patch.object(self.module, "_campaign_assets", return_value=asset_data), patch.object(
            self.module,
            "_marketing_contact_campaign_search",
            return_value={
                "results": [contact],
                "searched_properties": list(self.module.MARKETING_ATTRIBUTION_SEARCH_PROPERTIES),
                "search_runs": [{"property": "utm_campaign", "term": "155425489-20251015_2025SalaryBenchmark", "returned_count": 1}],
                "search_run_count": 1,
                "errors": [],
                "requested_limit": 50,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_marketing_access_context_for_contact",
            return_value={"allowed": True, "contact": contact, "companies": [company], "scope_status": "company_scoped"},
        ), patch.object(
            self.module,
            "_association_ids_with_metadata",
            return_value={"ids": ["deal-1", "deal-2"], "has_more": False, "truncated": False, "requested_limit": 100},
        ), patch.object(self.module, "_batch_association_ids", side_effect=fake_batch_association_ids), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(
            self.module, "_friday_review_stage_config", return_value=stage_config
        ):
            result = self.module.get_marketing_campaign_attribution(
                "kerren.fong@staffany.com",
                campaign_id="campaign-1",
                campaign_utm="155425489-20251015_2025SalaryBenchmark",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["answer"]["attribution_search"]["matched_contact_count"], 1)
        self.assertEqual(result["answer"]["attribution_search"]["scoped_company_count"], 1)
        self.assertIn("utm_campaign", result["answer"]["attribution_search"]["searched_properties"])
        self.assertEqual(result["answer"]["deal_stage_counts"]["qos"], 1)
        self.assertEqual(result["answer"]["deal_stage_counts"]["closed_won"], 1)

    def test_get_marketing_campaign_attribution_needs_check_without_stage_config(self):
        campaign = {
            "id": "campaign-1",
            "properties": {
                "hs_name": "20251015_2025SalaryBenchmark",
                "hs_utm": "155425489-20251015_2025SalaryBenchmark",
            },
        }
        contact = {
            "id": "contact-1",
            "properties": {
                "email": "buyer@noci.example",
                "recent_conversion_event_name": "2025 Salary Benchmark Report",
            },
        }
        company = {
            "id": "company-1",
            "properties": {
                "name": "Noci Bakehouse",
                "domain": "noci.example",
                "company_country": "Singapore",
                "hubspot_owner_id": "owner-1",
                "hs_is_target_account": "true",
            },
        }
        stage_config = {
            "pipeline_ids": set(),
            "qo_stage_ids": set(),
            "qo_met_stage_ids": set(),
            "closed_won_stage_ids": set(),
            "configured": False,
            "required_env": [self.module.QO_PIPELINE_IDS_ENV_VAR],
        }

        def fake_batch_association_ids(from_type, to_type, ids):
            if from_type == "contacts" and to_type == "companies":
                return {"contact-1": ["company-1"]}
            if from_type == "companies" and to_type == "deals":
                return {"company-1": ["deal-1"]}
            return {}

        def fake_batch_read(object_type, ids, properties):
            if object_type == "companies":
                return [company]
            if object_type == "deals":
                return [{"id": "deal-1", "properties": {"dealname": "Noci QO", "pipeline": "pipe-1", "dealstage": "qo"}}]
            return []

        with patch.object(self.module, "_caller_scope", return_value=SCOPE), patch.object(
            self.module, "_get_campaign", return_value=campaign
        ), patch.object(
            self.module,
            "_campaign_assets",
            return_value={"asset_types": [], "assets_by_type": {}, "requested_limit": 50, "has_more": False, "truncated": False},
        ), patch.object(
            self.module,
            "_marketing_contact_campaign_search",
            return_value={
                "results": [contact],
                "searched_properties": list(self.module.MARKETING_ATTRIBUTION_SEARCH_PROPERTIES),
                "search_runs": [],
                "search_run_count": 0,
                "errors": [],
                "requested_limit": 50,
                "returned_count": 1,
                "has_more": False,
                "truncated": False,
            },
        ), patch.object(
            self.module,
            "_marketing_access_context_for_contact",
            return_value={"allowed": True, "contact": contact, "companies": [company], "scope_status": "company_scoped"},
        ), patch.object(
            self.module,
            "_association_ids_with_metadata",
            return_value={"ids": ["deal-1"], "has_more": False, "truncated": False, "requested_limit": 100},
        ), patch.object(
            self.module, "_batch_association_ids", side_effect=fake_batch_association_ids
        ), patch.object(
            self.module, "_batch_read", side_effect=fake_batch_read
        ), patch.object(self.module, "_friday_review_stage_config", return_value=stage_config):
            result = self.module.get_marketing_campaign_attribution("kerren.fong@staffany.com", campaign_id="campaign-1")

        self.assertEqual(result["confidence"], "needs-check")
        self.assertFalse(result["answer"]["deal_stage_counts"]["stage_configured"])
        self.assertIn("configured HubSpot pipeline and stage IDs", result["caveat"])

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

    def test_plan_hubspot_writeback_preserves_slack_source_metadata(self):
        admin_scope = {"kind": "admin", "email": "kaiyi@staffany.com", "countries": self.module.SUPPORTED_COUNTRIES, "owner_id": None}
        source_thread_url = "https://staffany.slack.com/archives/C04MSJ1BGF9/p1778471025436219?thread_ts=1776659145.164259&channel=C04MSJ1BGF9"
        with patch.object(self.module, "_caller_scope", return_value=admin_scope), patch.object(
            self.module, "_assert_company_access", return_value={"id": "32662274616", "properties": {"hs_is_target_account": "true", "company_country": "Indonesia"}}
        ):
            result = self.module.plan_hubspot_writeback(
                "kaiyi@staffany.com",
                [
                    {
                        "company_id": "32662274616",
                        "note_summary": "Pre-demo game plan reviewed for Marugame Udon.",
                        "source_evidence": {
                            "source_type": "slack_thread",
                            "source_url": source_thread_url,
                            "provenance_policy": "Link only; raw Slack transcript was not copied into HubSpot.",
                        },
                        "source_type": "slack_thread",
                        "source_url": source_thread_url,
                        "confidence": "needs-check",
                    }
                ],
            )

        action = result["answer"]["actions"][0]
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(action["source_type"], "slack_thread")
        self.assertEqual(action["source_url"], source_thread_url)
        self.assertEqual(action["source_evidence"]["source_url"], source_thread_url)


if __name__ == "__main__":
    unittest.main()
