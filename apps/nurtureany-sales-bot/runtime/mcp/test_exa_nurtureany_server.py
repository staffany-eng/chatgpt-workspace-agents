import os
import sys
import unittest
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_helpers import load_mcp_module


def load_exa_module():
    return load_mcp_module("exa_nurtureany_server.py", "exa_nurtureany_server_under_test")


class ExaNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_exa_module()

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

    def test_missing_key_returns_blocked_without_calling_exa(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Exa")
        ):
            result = self.module.search_exa_people_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("EXA_API_KEY", result["answer"])
        self.assertEqual(result["cost_report"]["actual_cost_usd"], 0)

    def test_unscoped_company_input_is_blocked_before_key_or_api_call(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Exa")
        ):
            result = self.module.search_exa_people_candidates(
                "ae@staffany.com", [{"name": "Acme Cafe", "domain": "acme.example"}]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("requires scoped HubSpot company inputs", result["answer"])
        self.assertEqual(result["cost_report"]["actual_cost_usd"], 0)

    def test_search_caps_companies_candidates_and_uses_people_payload_only(self):
        calls = []

        def fake_request(body):
            calls.append(body)
            return {
                "requestId": "exa-req",
                "results": [
                    {
                        "id": f"https://www.linkedin.com/in/person-{index}",
                        "title": f"Person {index} - HR Director - Acme | LinkedIn",
                        "url": f"https://www.linkedin.com/in/person-{index}",
                    }
                    for index in range(7)
                ],
                "costDollars": {"total": 0.007},
            }, {}

        companies = [self.scoped_company(company_id=f"hubspot-{index}", name=f"Company {index}", domain=f"company{index}.com") for index in range(6)]

        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.search_exa_people_candidates(
                "ae@staffany.com",
                companies,
                target_titles=["HR Director", "Head of Operations"],
                limit_per_company=99,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(result["answer"]), self.module.MAX_SEARCH_COMPANIES)
        self.assertEqual(len(calls), self.module.MAX_SEARCH_COMPANIES)
        self.assertAlmostEqual(result["cost_report"]["actual_cost_usd"], 0.035)

        for body in calls:
            self.assertEqual(body["category"], "people")
            self.assertEqual(body["type"], "auto")
            self.assertEqual(body["numResults"], self.module.MAX_CANDIDATES_PER_COMPANY)
            self.assertEqual(body["userLocation"], "SG")
            for forbidden in [
                "contents",
                "includeDomains",
                "excludeDomains",
                "startPublishedDate",
                "endPublishedDate",
                "startCrawlDate",
                "endCrawlDate",
            ]:
                self.assertNotIn(forbidden, body)

        for company_result in result["answer"]:
            self.assertEqual(len(company_result["candidates"]), self.module.MAX_CANDIDATES_PER_COMPANY)
            for candidate in company_result["candidates"]:
                self.assertNotIn("email", candidate)
                self.assertNotIn("phone", candidate)
                self.assertEqual(candidate["source_type"], "linkedin_manual_check")
                self.assertTrue(candidate["decision_maker_match"]["matched"])
                self.assertEqual(candidate["signal_count"], 2)
                self.assertEqual(candidate["confidence_band"], "high")
                self.assertIn("target_title_match", candidate["quality_signals"])
                self.assertIn("linkedin_url_present", candidate["quality_signals"])
                self.assertEqual(candidate["confidence"], "needs-check")
            self.assertEqual(company_result["quality_summary"]["high"], self.module.MAX_CANDIDATES_PER_COMPANY)
            self.assertEqual(
                company_result["review_next_step"],
                "Pass candidates through review_public_enrichment_evidence for HubSpot dedupe before AE handoff.",
            )

    def test_default_titles_are_curated_to_staffany_icp_personas(self):
        titles = self.module._target_titles(None)

        for expected in ["owner", "founder", "ceo", "hr manager", "hr director", "people & culture", "operations manager", "head of operations", "coo", "director of operations"]:
            self.assertIn(expected, titles)
        for generic in ["manager", "director", "general manager", "finance manager", "payroll manager"]:
            self.assertNotIn(generic, titles)

    def test_quality_gate_marks_single_signal_candidates_low_confidence(self):
        candidate = self.module._candidate(
            {
                "id": "https://example.org/people/ada",
                "title": "Ada Ng - HR Director - Acme Cafe",
                "url": "https://example.org/people/ada",
            },
            self.scoped_company(domain="acme.example"),
            ["hr director"],
            1,
        )

        self.assertEqual(candidate["signal_count"], 1)
        self.assertEqual(candidate["confidence_band"], "low")
        self.assertIn("target_title_match", candidate["quality_signals"])
        self.assertIn("no_linkedin_or_company_domain_result_url", candidate["quality_warnings"])

    def test_quality_gate_marks_missing_domain_and_store_manager_noise(self):
        candidate = self.module._candidate(
            {
                "id": "https://www.linkedin.com/in/store-manager",
                "title": "Store Manager - Acme Cafe | LinkedIn",
                "url": "https://www.linkedin.com/in/store-manager",
            },
            self.scoped_company(domain=""),
            ["operations manager"],
            1,
        )

        self.assertEqual(candidate["confidence_band"], "low")
        self.assertIn("missing_company_domain_anchor", candidate["quality_warnings"])
        self.assertIn("weak_store_or_junior_manager_title", candidate["quality_warnings"])

    def test_country_maps_to_user_location(self):
        self.assertEqual(self.module._user_location("Singapore"), "SG")
        self.assertEqual(self.module._user_location("Malaysia"), "MY")
        self.assertEqual(self.module._user_location("Indonesia"), "ID")
        self.assertEqual(self.module._user_location("Thailand"), "SG")

    def test_source_domain_classification(self):
        self.assertEqual(
            self.module._source_type("https://www.linkedin.com/in/ada", ""),
            "linkedin_manual_check",
        )
        self.assertEqual(
            self.module._source_type("https://careers.acme.example/team/ada", "acme.example"),
            "company_public_profile",
        )
        self.assertEqual(
            self.module._source_type("https://example.org/profile/ada", "acme.example"),
            "public_people_result",
        )
        self.assertEqual(
            self.module._source_type("https://www.instagram.com/acme", ""),
            "social_or_gated_manual_check",
        )

    def test_cost_report_maps_exa_cost_dollars(self):
        report = self.module._cost_report(
            [
                {"input_company": {"name": "A"}, "actual_cost_usd": 0.007, "raw_cost_dollars": {"total": 0.007}},
                {"input_company": {"name": "B"}, "actual_cost_usd": 0.005, "raw_cost_dollars": {"total": 0.005}},
            ],
            "ok",
            2,
        )

        self.assertAlmostEqual(report["actual_cost_usd"], 0.012)
        self.assertEqual(report["cost_dollars"]["total"], report["actual_cost_usd"])
        self.assertIn("2 Exa /search", report["estimated_cost_usd"])

    def test_http_errors_return_blocked_with_cost_report(self):
        def fake_request(body):
            raise self.module.ExaError("Exa API failed: 429 quota exceeded", 429)

        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.search_exa_people_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("429", result["answer"])
        self.assertIn("cost_report", result)

    def test_timeout_errors_return_blocked(self):
        def fake_request(body):
            raise self.module.ExaError("Exa API request timed out or failed: timed out")

        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.search_exa_people_candidates(
                "ae@staffany.com", [self.scoped_company()]
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("timed out", result["answer"])


if __name__ == "__main__":
    unittest.main()
