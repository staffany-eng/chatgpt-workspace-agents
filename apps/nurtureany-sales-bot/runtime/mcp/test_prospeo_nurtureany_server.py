import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from test_helpers import load_mcp_module


def load_prospeo_module():
    return load_mcp_module("prospeo_nurtureany_server.py", "prospeo_nurtureany_server_under_test")


class ProspeoNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_prospeo_module()

    def scoped_company(self, **overrides):
        company = {
            "company_id": "hubspot-123",
            "name": "Acme Cafe",
            "domain": "acme.example",
            "country": "Singapore",
            "hubspot_scoped": True,
            "scope_source": self.module.SCOPE_SOURCE,
        }
        company.update(overrides)
        return company

    def test_search_caps_companies_candidates_and_does_not_reveal_pii(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            results = [
                {
                    "person": {
                        "person_id": f"person-{index}",
                        "full_name": f"Person {index}",
                        "current_job_title": "Owner",
                        "linkedin_url": f"https://www.linkedin.com/in/person-{index}",
                    },
                    "company": {"name": "Acme", "domain": "acme.example"},
                }
                for index in range(7)
            ]
            return {
                "error": False,
                "free": False,
                "results": results,
                "pagination": {"current_page": 1, "per_page": 25, "total_count": 7},
            }, {"x-ratelimit-remaining-minute": "42"}

        companies = [
            self.scoped_company(company_id=f"hubspot-{index}", name=f"Company {index}", domain=f"company{index}.com")
            for index in range(6)
        ]

        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_account_snapshot", side_effect=[({"used_credits": 10}, "fresh"), ({"used_credits": 15}, "fresh")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.search_prospeo_decision_maker_candidates(
                "ae@staffany.com", companies, limit_per_company=99
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(result["answer"]), self.module.MAX_SEARCH_COMPANIES)
        self.assertEqual(result["credit_report"]["estimated_credits"], 5)
        self.assertEqual(result["credit_report"]["actual_delta_credits"], 5)

        search_calls = [call for call in calls if call[1] == "/search-person"]
        self.assertEqual(len(search_calls), self.module.MAX_SEARCH_COMPANIES)
        for _, path, body in search_calls:
            self.assertEqual(path, "/search-person")
            self.assertEqual(body["page"], 1)
            self.assertEqual(body["filters"]["max_person_per_company"], self.module.MAX_CANDIDATES_PER_COMPANY)
            self.assertIn("person_job_title", body["filters"])
            self.assertIn("person_contact_details", body["filters"])

        for company_result in result["answer"]:
            self.assertEqual(len(company_result["candidates"]), self.module.MAX_CANDIDATES_PER_COMPANY)
            for candidate in company_result["candidates"]:
                self.assertNotIn("email", candidate)
                self.assertNotIn("phone", candidate)
                self.assertIn("person_id", candidate)

    def test_search_free_response_estimates_zero_credits(self):
        def fake_request(method, path, body=None):
            return {
                "error": False,
                "free": True,
                "results": [{"person": {"person_id": "person-1"}, "company": {}}],
                "pagination": {},
            }, {}

        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_account_snapshot", side_effect=[({"used_credits": 10}, "fresh"), ({"used_credits": 10}, "fresh")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.search_prospeo_decision_maker_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["credit_report"]["estimated_credits"], 0)

    def test_reveal_refuses_missing_approval_marker_before_calling_prospeo(self):
        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Prospeo")
        ):
            result = self.module.reveal_prospeo_contact_details(
                "ae@staffany.com", ["person-1"], approval_marker="", scoped_company_ids=["hubspot-123"]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("approval marker", result["answer"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 0)

    def test_reveal_caps_contacts_sets_flags_and_hides_phone_without_flag(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {
                "error": False,
                "total_cost": 1,
                "not_matched": [],
                "invalid_datapoints": [],
                "matched": [
                    {
                        "identifier": "person-1",
                        "person": {
                            "person_id": "person-1",
                            "first_name": "Ada",
                            "last_name": "Ng",
                            "full_name": "Ada Ng",
                            "current_job_title": "Owner",
                            "linkedin_url": "https://linkedin.example/ada",
                            "email": {
                                "status": "VERIFIED",
                                "revealed": True,
                                "email": "ada@example.com",
                                "verification_method": "SMTP",
                            },
                            "mobile": {
                                "status": "VERIFIED",
                                "revealed": True,
                                "mobile": "+6512345678",
                            },
                        },
                        "company": {"name": "Acme Cafe", "domain": "acme.example"},
                    }
                ],
            }, {"x-ratelimit-remaining-minute": "99"}

        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_account_snapshot", side_effect=[({"used_credits": 10}, "fresh"), ({"used_credits": 11}, "fresh")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.reveal_prospeo_contact_details(
                "ae@staffany.com",
                ["person-1", "person-2", "person-3", "person-4"],
                reveal_emails=True,
                reveal_phones=False,
                approval_marker="approved in Slack",
                scoped_company_ids=["hubspot-123"],
            )

        self.assertEqual(result["confidence"], "needs-check")
        method, path, body = calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/bulk-enrich-person")
        self.assertEqual([row["person_id"] for row in body["data"]], ["person-1", "person-2", "person-3"])
        self.assertIs(body["only_verified_email"], True)
        self.assertIs(body["enrich_mobile"], False)

        contact = result["answer"]["contacts"][0]
        self.assertEqual(contact["emails"][0]["address"], "ada@example.com")
        self.assertEqual(contact["phones"], [])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 3)
        self.assertEqual(result["credit_report"]["actual_delta_credits"], 1)
        self.assertEqual(result["credit_report"]["reported_total_cost"], 1)
        self.assertEqual(result["answer"]["hubspot_preview_actions"][0]["source"]["prospeo_person_id"], "person-1")
        self.assertIn("revealed by approval on", result["answer"]["hubspot_preview_actions"][0]["note_summary"])

    def test_reveal_estimates_mobile_credits_only_when_phone_flag_is_true(self):
        response = {
            "error": False,
            "total_cost": 10,
            "matched": [
                {
                    "identifier": "person-1",
                    "person": {
                        "person_id": "person-1",
                        "full_name": "Ada Ng",
                        "current_job_title": "Owner",
                        "mobile": {"status": "VERIFIED", "revealed": True, "mobile": "+6512345678"},
                    },
                    "company": {"name": "Acme Cafe"},
                }
            ],
        }
        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_account_snapshot", side_effect=[({"used_credits": 0}, "fresh"), ({"used_credits": 0}, "fresh")]
        ), patch.object(self.module, "_request_json", return_value=(response, {})):
            result = self.module.reveal_prospeo_contact_details(
                "ae@staffany.com",
                ["person-1", "person-2"],
                reveal_emails=True,
                reveal_phones=True,
                approval_marker="approved in Slack",
                scoped_company_ids=["hubspot-123"],
            )

        self.assertEqual(result["credit_report"]["estimated_credits"], 20)
        self.assertEqual(result["answer"]["contacts"][0]["phones"][0]["number"], "+6512345678")

    def test_missing_key_returns_blocked_without_calling_prospeo(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Prospeo")
        ):
            result = self.module.search_prospeo_decision_maker_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("PROSPEO_API_KEY", result["answer"])

    def test_unscoped_company_input_is_blocked_before_key_or_api_call(self):
        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Prospeo")
        ):
            result = self.module.search_prospeo_decision_maker_candidates(
                "ae@staffany.com", [{"name": "Acme Cafe", "domain": "acme.example"}]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("requires scoped HubSpot company inputs", result["answer"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 0)

    def test_reveal_requires_scoped_company_ids_before_calling_prospeo(self):
        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Prospeo")
        ):
            result = self.module.reveal_prospeo_contact_details(
                "ae@staffany.com",
                ["person-1"],
                approval_marker="approved in Slack",
                scoped_company_ids=[],
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("scoped HubSpot company_ids", result["answer"])

    def test_prospeo_http_errors_return_blocked_with_credit_report(self):
        def fake_request(method, path, body=None):
            raise self.module.ProspeoError("Prospeo API failed: 429 RATE_LIMITED", 429)

        with patch.dict(os.environ, {"PROSPEO_API_KEY": "test-key"}), patch.object(
            self.module, "_account_snapshot", side_effect=[({"used_credits": 10}, "fresh"), ({"used_credits": 10}, "cached")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.search_prospeo_decision_maker_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("429", result["answer"])
        self.assertIn("credit_report", result)

    def test_account_snapshot_summary_and_cached_delta_fallback(self):
        summary = self.module._summarize_account(
            {"response": {"current_plan": "STARTER", "used_credits": 7, "remaining_credits": 43}}
        )

        self.assertEqual(summary["current_plan"], "STARTER")
        self.assertEqual(summary["used_credits"], 7)
        self.assertEqual(summary["remaining_credits"], 43)
        self.assertEqual(self.module._usage_delta(summary, summary), "unavailable")
        self.assertEqual(self.module._usage_delta(summary, {**summary, "used_credits": 10}), 3)


if __name__ == "__main__":
    unittest.main()
