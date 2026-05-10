import importlib.util
import os
import sys
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


def load_lusha_module():
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp

    module_name = "lusha_nurtureany_server_under_test"
    sys.modules.pop(module_name, None)
    path = Path(__file__).with_name("lusha_nurtureany_server.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class LushaNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_lusha_module()

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
            contacts = [
                {
                    "contactId": f"contact-{index}",
                    "name": f"Person {index}",
                    "jobTitle": "Owner",
                    "companyName": "Acme",
                    "hasEmails": True,
                    "hasPhones": True,
                    "hasSocialLink": True,
                }
                for index in range(7)
            ]
            return {"requestId": "req-123", "contacts": contacts, "totalResults": 7}, {
                "x-minute-requests-left": "42"
            }

        companies = [self.scoped_company(company_id=f"hubspot-{index}", name=f"Company {index}", domain=f"company{index}.com") for index in range(6)]

        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_usage_snapshot", side_effect=[({"total_used": 10}, "fresh"), ({"total_used": 10}, "cached")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.search_lusha_decision_maker_candidates(
                "ae@staffany.com", companies, limit_per_company=99
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(result["answer"]), self.module.MAX_SEARCH_COMPANIES)
        self.assertEqual(result["credit_report"]["estimated_credits"], 5)
        self.assertEqual(result["credit_report"]["actual_delta_credits"], 0)

        search_calls = [call for call in calls if call[1] == "/prospecting/contact/search"]
        self.assertEqual(len(search_calls), self.module.MAX_SEARCH_COMPANIES)
        for _, path, body in search_calls:
            self.assertEqual(path, "/prospecting/contact/search")
            self.assertNotIn("revealEmails", body)
            self.assertNotIn("revealPhones", body)
            self.assertEqual(len(body["filters"]["contacts"]["include"]["jobTitles"]), len(self.module.DECISION_MAKER_TITLES))

        for company_result in result["answer"]:
            self.assertEqual(len(company_result["candidates"]), self.module.MAX_CANDIDATES_PER_COMPANY)
            for candidate in company_result["candidates"]:
                self.assertNotIn("email", candidate)
                self.assertNotIn("phone", candidate)
                self.assertTrue(candidate["has_email"])
                self.assertTrue(candidate["has_phone"])

    def test_search_credit_estimate_uses_one_credit_per_25_results_minimum_one(self):
        self.assertEqual(self.module._estimate_search_credits(0), 1)
        self.assertEqual(self.module._estimate_search_credits(1), 1)
        self.assertEqual(self.module._estimate_search_credits(25), 1)
        self.assertEqual(self.module._estimate_search_credits(26), 2)
        self.assertEqual(self.module._estimate_search_credits(51), 3)

    def test_reveal_refuses_missing_approval_marker_before_calling_lusha(self):
        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Lusha")
        ):
            result = self.module.reveal_lusha_contact_details(
                "ae@staffany.com", "req-123", ["contact-1"], approval_marker="", scoped_company_ids=["hubspot-123"]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("approval marker", result["answer"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 0)

    def test_reveal_caps_contacts_sets_flags_and_hides_phone_without_flag(self):
        calls = []

        def fake_request(method, path, body=None):
            calls.append((method, path, body))
            return {
                "requestId": "req-123",
                "contacts": [
                    {
                        "id": "contact-1",
                        "isSuccess": True,
                        "data": {
                            "firstName": "Ada",
                            "lastName": "Ng",
                            "fullName": "Ada Ng",
                            "jobTitle": "Owner",
                            "companyName": "Acme Cafe",
                            "emailAddresses": [
                                {"email": "ada@example.com", "emailType": "work", "emailConfidence": "A"}
                            ],
                            "phoneNumbers": [{"number": "+6512345678", "phoneType": "mobile"}],
                            "socialLinks": {"linkedin": "https://linkedin.example/ada"},
                        },
                    }
                ],
            }, {"x-hourly-requests-left": "99"}

        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_usage_snapshot", side_effect=[({"total_used": 10}, "fresh"), ({"total_used": 11}, "fresh")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.reveal_lusha_contact_details(
                "ae@staffany.com",
                "req-123",
                ["contact-1", "contact-2", "contact-3", "contact-4"],
                reveal_emails=True,
                reveal_phones=False,
                approval_marker="approved in Slack",
                scoped_company_ids=["hubspot-123"],
            )

        self.assertEqual(result["confidence"], "needs-check")
        method, path, body = calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/prospecting/contact/enrich")
        self.assertEqual(body["contactIds"], ["contact-1", "contact-2", "contact-3"])
        self.assertIs(body["revealEmails"], True)
        self.assertIs(body["revealPhones"], False)

        contact = result["answer"]["contacts"][0]
        self.assertEqual(contact["emails"][0]["address"], "ada@example.com")
        self.assertEqual(contact["phones"], [])
        self.assertFalse(result["answer"]["will_mutate_hubspot"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 3)
        self.assertEqual(result["credit_report"]["actual_delta_credits"], 1)
        self.assertEqual(result["answer"]["hubspot_preview_actions"][0]["source"]["lusha_contact_id"], "contact-1")
        self.assertIn("revealed by approval on", result["answer"]["hubspot_preview_actions"][0]["note_summary"])

    def test_reveal_estimates_phone_credits_only_when_phone_flag_is_true(self):
        response = {"requestId": "req-123", "contacts": []}
        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_usage_snapshot", side_effect=[({"total_used": 0}, "fresh"), ({"total_used": 0}, "fresh")]
        ), patch.object(self.module, "_request_json", return_value=(response, {})):
            result = self.module.reveal_lusha_contact_details(
                "ae@staffany.com",
                "req-123",
                ["contact-1", "contact-2"],
                reveal_emails=True,
                reveal_phones=True,
                approval_marker="approved in Slack",
                scoped_company_ids=["hubspot-123"],
            )

        self.assertEqual(result["credit_report"]["estimated_credits"], 12)

    def test_missing_key_returns_blocked_without_calling_lusha(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Lusha")
        ):
            result = self.module.search_lusha_decision_maker_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("LUSHA_API_KEY", result["answer"])

    def test_unscoped_company_input_is_blocked_before_key_or_api_call(self):
        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Lusha")
        ):
            result = self.module.search_lusha_decision_maker_candidates(
                "ae@staffany.com", [{"name": "Acme Cafe", "domain": "acme.example"}]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("requires scoped HubSpot company inputs", result["answer"])
        self.assertEqual(result["credit_report"]["estimated_credits"], 0)

    def test_reveal_requires_scoped_company_ids_before_calling_lusha(self):
        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Lusha")
        ):
            result = self.module.reveal_lusha_contact_details(
                "ae@staffany.com",
                "req-123",
                ["contact-1"],
                approval_marker="approved in Slack",
                scoped_company_ids=[],
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("scoped HubSpot company_ids", result["answer"])

    def test_lusha_http_errors_return_blocked_with_credit_report(self):
        def fake_request(method, path, body=None):
            raise self.module.LushaError("Lusha API failed: 429 quota exceeded", 429)

        with patch.dict(os.environ, {"LUSHA_API_KEY": "test-key"}), patch.object(
            self.module, "_usage_snapshot", side_effect=[({"total_used": 10}, "fresh"), ({"total_used": 10}, "cached")]
        ), patch.object(self.module, "_request_json", side_effect=fake_request):
            result = self.module.search_lusha_decision_maker_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("429", result["answer"])
        self.assertIn("credit_report", result)

    def test_usage_snapshot_summary_and_cached_delta_fallback(self):
        summary = self.module._summarize_usage(
            {"usage": {"bulkCredits": {"used": 7, "remaining": 43, "total": 50}}}
        )

        self.assertEqual(summary["total_used"], 7)
        self.assertEqual(summary["total_remaining"], 43)
        self.assertEqual(summary["total"], 50)
        self.assertEqual(self.module._usage_delta(summary, summary), "unavailable")
        self.assertEqual(self.module._usage_delta(summary, {**summary, "total_used": 10}), 3)


if __name__ == "__main__":
    unittest.main()
