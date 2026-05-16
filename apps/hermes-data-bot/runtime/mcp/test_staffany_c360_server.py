from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from test_helpers import load_mcp_module


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class StaffAnyC360ServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("staffany_c360_server.py")

    def test_exposes_current_customer_tool_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["list_current_customer_orgs"],
        )
        tool_names = " ".join(tool.__name__ for tool in self.module.mcp.tools)
        for forbidden in ["post", "send", "write", "cookie", "session"]:
            self.assertNotIn(forbidden, tool_names)

    def test_missing_token_blocks_without_network(self):
        with patch.dict(os.environ, {"CUSTOMER360_BASE_URL": "https://c360.example"}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call C360")
        ):
            result = self.module.list_current_customer_orgs("2026-05-15", "Indonesia")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("CUSTOMER360_INTERNAL_API_TOKEN", result["answer"])

    def test_missing_as_of_date_blocks_without_network(self):
        with patch.dict(
            os.environ,
            {
                "CUSTOMER360_BASE_URL": "https://c360.example",
                "CUSTOMER360_INTERNAL_API_TOKEN": "test-token",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=AssertionError("should not call C360")):
            result = self.module.list_current_customer_orgs("", "Indonesia")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("as_of_date is required", result["answer"])

    def test_calls_c360_with_custom_header_and_compacts_rows(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse(
                b"""
                {
                  "status": "ok",
                  "data": {
                    "asOfDate": "2026-05-15",
                    "country": "Indonesia",
                    "definition": "Current customer test definition",
                    "rows": [
                      {
                        "customerKey": "316899066558",
                        "hubspotCompanyId": "316899066558",
                        "companyName": "Butter Protein Club",
                        "country": "Indonesia",
                        "renewalBucket": "Will Renew",
                        "renewalAssessment": "Will Renew",
                        "renewalDate": "2026-12-01",
                        "linkedStaffAnyOrgId": "org-jakarta-1",
                        "linkedStaffAnyOrgName": "Butter Protein Club HQ",
                        "mappingStatus": "linked",
                        "c360Url": "https://c360.example/companies/316899066558",
                        "rawIgnored": "do not expose"
                      }
                    ]
                  }
                }
                """
            )

        with patch.dict(
            os.environ,
            {
                "CUSTOMER360_BASE_URL": "https://c360.example/",
                "CUSTOMER360_INTERNAL_API_TOKEN": "test-token",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.module.list_current_customer_orgs("2026-05-15", "Indonesia", limit=99999)

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(captured["timeout"], self.module.CUSTOMER360_TIMEOUT_SECONDS)
        self.assertIn("/api/current-customer-orgs?", captured["url"])
        self.assertIn("asOf=2026-05-15", captured["url"])
        self.assertIn("country=Indonesia", captured["url"])
        self.assertIn(f"limit={self.module.MAX_LIMIT}", captured["url"])
        self.assertEqual(captured["headers"]["X-customer360-internal-token"], "test-token")
        self.assertNotIn("Authorization", captured["headers"])
        self.assertEqual(result["answer"]["definition"], "Current customer test definition")
        self.assertEqual(result["answer"]["staffany_org_ids"], ["org-jakarta-1"])
        self.assertEqual(result["answer"]["mapping_gap_count"], 0)
        self.assertEqual(
            result["answer"]["rows"],
            [
                {
                    "customerKey": "316899066558",
                    "hubspotCompanyId": "316899066558",
                    "companyName": "Butter Protein Club",
                    "country": "Indonesia",
                    "renewalBucket": "Will Renew",
                    "renewalAssessment": "Will Renew",
                    "renewalDate": "2026-12-01",
                    "linkedStaffAnyOrgId": "org-jakarta-1",
                    "linkedStaffAnyOrgName": "Butter Protein Club HQ",
                    "mappingStatus": "linked",
                    "c360Url": "https://c360.example/companies/316899066558",
                }
            ],
        )

    def test_auth_failures_are_blocked_and_token_redacted(self):
        error = self.module.urllib.error.HTTPError(
            "https://c360.example/api/current-customer-orgs",
            401,
            "Unauthorized",
            {},
            io.BytesIO(b"bad test-token"),
        )

        with patch.dict(
            os.environ,
            {
                "CUSTOMER360_BASE_URL": "https://c360.example",
                "CUSTOMER360_INTERNAL_API_TOKEN": "test-token",
            },
            clear=True,
        ), patch("urllib.request.urlopen", side_effect=error):
            result = self.module.list_current_customer_orgs("2026-05-15", "Indonesia")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("[REDACTED_CUSTOMER360_INTERNAL_API_TOKEN]", result["answer"])
        self.assertNotIn("test-token", result["answer"])


if __name__ == "__main__":
    unittest.main()
