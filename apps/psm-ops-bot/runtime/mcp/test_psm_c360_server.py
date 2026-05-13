from __future__ import annotations

import os
import unittest
from unittest.mock import patch

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

    def test_search_customers_uses_internal_bearer_route(self):
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

    def test_ask_customer_context_posts_question(self):
        calls = []

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

        result = self.module.ask_c360_customer_context(
            "fei-siong-group",
            "Where is payroll painful?",
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

    def test_missing_token_blocks(self):
        with patch.dict(os.environ, {"CUSTOMER360_INTERNAL_API_TOKEN": "", "CUSTOMER_360_INTERNAL_API_TOKEN": ""}, clear=False):
            result = self.module.get_c360_account_context("fei-siong-group")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("CUSTOMER360_INTERNAL_API_TOKEN", result["caveat"])


if __name__ == "__main__":
    unittest.main()
