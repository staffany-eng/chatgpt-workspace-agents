from __future__ import annotations

import os
import sys
import urllib.parse
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_helpers import load_mcp_module


class PsmC360ServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("psm_c360_server.py")
        self.env = patch.dict(
            os.environ,
            {
                "CUSTOMER360_BASE_URL": "https://c360.example",
                "CUSTOMER360_INTERNAL_API_TOKEN": "test-token",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_search_customers_uses_internal_token_header(self):
        calls = []

        def fake_http(method, path, body=None):
            calls.append((method, path, body))
            return {
                "status": "ok",
                "search": {
                    "groups": [
                        {"hubspotCompanyId": "1991281569", "companyName": "Fei Siong"}
                    ]
                },
            }

        self.module._http_json = fake_http

        result = self.module.search_c360_customers("Fei", limit=1)

        self.assertEqual(calls, [("GET", "/api/companies?q=Fei", None)])
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"][0]["companyName"], "Fei Siong")

    def test_headers_use_custom_internal_token_header(self):
        headers = self.module._headers()

        self.assertEqual(headers["X-Customer360-Internal-Token"], "test-token")
        self.assertNotIn("Authorization", headers)

    def test_customer_search_variants_expand_project_channel_hint(self):
        variants = self.module._customer_search_variants("proj-cs-rockproductions")

        self.assertIn("proj-cs-rockproductions", variants)
        self.assertIn("rockproductions", variants)
        self.assertIn("rock productions", variants)
        self.assertIn("rock production", variants)
        self.assertIn("Rock Productions Pte Ltd", variants)

    def test_search_customers_merges_and_dedupes_variant_results(self):
        calls = []

        def fake_http(method, path, body=None):
            calls.append((method, path, body))
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query).get("q", [""])[0]
            if query == "rockproductions":
                groups = [
                    {
                        "customerKey": "rock-productions",
                        "routeKey": "rock-productions",
                        "companyName": "Rock Productions",
                    }
                ]
            elif query == "rock productions":
                groups = [
                    {
                        "routeKey": "rock-productions",
                        "companyName": "Rock Productions Pte Ltd",
                    }
                ]
            elif query == "rock production":
                groups = [
                    {
                        "customerKey": "rock-productions",
                        "companyName": "Rock Productions Pte Ltd",
                        "matchedFields": ["HubSpot company", "StaffAny org"],
                        "orgMatches": [
                            {
                                "matchedValue": "Rock Productions",
                                "matchType": "StaffAny org",
                            }
                        ],
                    }
                ]
            elif query == "Rock Productions Pte Ltd":
                groups = [
                    {
                        "customerKey": "rock-productions",
                        "companyName": "Rock Productions Pte Ltd",
                    }
                ]
            else:
                groups = []
            return {"status": "ok", "search": {"groups": groups}}

        self.module._http_json = fake_http

        result = self.module.search_c360_customers("proj-cs-rockproductions", limit=8)

        self.assertGreaterEqual(len(calls), 4)
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["match_count"], 1)
        self.assertFalse(result["missing_mapping"])
        self.assertEqual(result["answer"][0]["customerKey"], "rock-productions")
        self.assertEqual(
            result["answer"][0]["orgMatches"][0]["matchedValue"],
            "Rock Productions",
        )
        self.assertIn("StaffAny org", result["answer"][0]["matchedFields"])
        self.assertIn("Rock Productions Pte Ltd", result["searched_variants"])

    def test_search_customers_reports_missing_mapping_for_no_match(self):
        def fake_http(method, path, body=None):
            return {"status": "ok", "search": {"groups": []}}

        self.module._http_json = fake_http

        result = self.module.search_c360_customers("proj-cs-rockproductions", limit=8)

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["match_count"], 0)
        self.assertTrue(result["missing_mapping"])
        self.assertIn("rock productions", result["searched_variants"])
        self.assertIn("Customer 360 customer/org mapping", result["caveat"])

    def test_ask_customer_context_posts_question(self):
        calls = []
        audit_calls = []

        def fake_http(method, path, body=None):
            calls.append((method, path, body))
            return {
                "status": "ok",
                "data": {
                    "answer": "Payroll context.",
                    "citationRefs": ["intercom.conversation_parts:1"],
                    "missingData": [],
                },
            }

        self.module._http_json = fake_http
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        result = self.module.ask_c360_customer_context(
            "fei-siong-group",
            "Where is payroll painful?",
            slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
        )

        self.assertEqual(
            calls,
            [
                (
                    "POST",
                    "/api/companies/fei-siong-group/ask",
                    {"question": "Where is payroll painful?"},
                )
            ],
        )
        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["answer"], "Payroll context.")
        self.assertEqual(result["central_copy"]["ok"], True)
        self.assertEqual(audit_calls[0][0], "c360_customer_answer")
        self.assertEqual(audit_calls[0][1]["source_thread_url"], "https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579")

    def test_ask_customer_context_strips_search_group_id_prefix(self):
        calls = []

        def fake_http(method, path, body=None):
            calls.append((method, path, body))
            return {
                "status": "ok",
                "data": {
                    "answer": "Issue history.",
                    "citationRefs": ["intercom.conversation_parts:1"],
                },
            }

        self.module._http_json = fake_http

        result = self.module.ask_c360_customer_context(
            "customer-9003781770",
            "What issues were raised in the past 6 months?",
        )

        self.assertEqual(
            calls,
            [
                (
                    "POST",
                    "/api/companies/9003781770/ask",
                    {"question": "What issues were raised in the past 6 months?"},
                )
            ],
        )
        self.assertEqual(result["scope"]["customer_key"], "9003781770")
        self.assertEqual(result["source"], "Customer 360 /api/companies/9003781770/ask")

    def test_missing_token_blocks(self):
        with patch.dict(os.environ, {"CUSTOMER360_INTERNAL_API_TOKEN": "", "CUSTOMER_360_INTERNAL_API_TOKEN": ""}, clear=False):
            result = self.module.get_c360_account_context("fei-siong-group")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("CUSTOMER360_INTERNAL_API_TOKEN", result["caveat"])

    def test_c360_blocked_posts_central_audit_when_thread_is_present(self):
        audit_calls = []
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        with patch.dict(os.environ, {"CUSTOMER360_INTERNAL_API_TOKEN": "", "CUSTOMER_360_INTERNAL_API_TOKEN": ""}, clear=False):
            result = self.module.get_c360_account_context(
                "fei-siong-group",
                slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1778205303989579",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"]["central_copy"]["ok"], True)
        self.assertEqual(audit_calls[0][0], "c360_blocked")
        self.assertIn("CUSTOMER360_INTERNAL_API_TOKEN", audit_calls[0][1]["blocked_reason"])

    def test_ask_customer_context_aa_channel_redirects_without_calling_c360(self):
        http_calls = []
        audit_calls = []

        def fake_http(method, path, body=None):
            http_calls.append((method, path, body))
            return {"status": "ok", "data": {"answer": "should not be called"}}

        self.module._http_json = fake_http
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        with patch.dict(os.environ, {"PSM_OPS_AA_CHANNEL_ID": "C0B5H2YE5T2"}, clear=False):
            result = self.module.ask_c360_customer_context(
                "customer-7300112790",
                "who is the caterer for the halal catering?",
                slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264188901099",
            )

        self.assertEqual(http_calls, [])
        self.assertTrue(result.get("aa_channel_redirect"))
        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"]["status"], "aa_channel_redirect")
        self.assertIn("create_ps_wee_intake_ticket", result["caveat"])
        self.assertEqual(audit_calls[0][0], "c360_aa_channel_redirect")

    def test_ask_customer_context_aa_channel_redirects_via_thin_poc_fallback(self):
        http_calls = []
        audit_calls = []

        def fake_http(method, path, body=None):
            http_calls.append((method, path, body))
            return {"status": "ok", "data": {"answer": "should not be called"}}

        self.module._http_json = fake_http
        self.module.post_ps_wee_audit = lambda event_type, **kwargs: audit_calls.append((event_type, kwargs)) or {"ok": True}

        with patch.dict(
            os.environ,
            {"PSM_OPS_AA_CHANNEL_ID": "", "PSM_OPS_JIRA_MODE": "thin_poc"},
            clear=False,
        ):
            result = self.module.ask_c360_customer_context(
                "customer-7300112790",
                "who is the caterer?",
                slack_thread_url="https://staffany.slack.com/archives/C0B5H2YE5T2/p1779264188901099",
            )

        self.assertEqual(http_calls, [])
        self.assertTrue(result.get("aa_channel_redirect"))

    def test_ask_customer_context_non_aa_channel_calls_c360_as_usual(self):
        http_calls = []
        self.module._http_json = lambda method, path, body=None: http_calls.append((method, path, body)) or {
            "status": "ok",
            "data": {"answer": "ok"},
        }
        self.module.post_ps_wee_audit = lambda *args, **kwargs: {"ok": True}

        with patch.dict(os.environ, {"PSM_OPS_AA_CHANNEL_ID": "C0B5H2YE5T2"}, clear=False):
            result = self.module.ask_c360_customer_context(
                "customer-7300112790",
                "who is the caterer?",
                slack_thread_url="https://staffany.slack.com/archives/C0B2VT50YT1/p1779264188901099",
            )

        self.assertEqual(len(http_calls), 1)
        self.assertFalse(result.get("aa_channel_redirect"))
        self.assertEqual(result["confidence"], "verified")


if __name__ == "__main__":
    unittest.main()
