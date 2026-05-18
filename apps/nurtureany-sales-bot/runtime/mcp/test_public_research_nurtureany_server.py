import os
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from test_helpers import load_mcp_module


def load_public_research_module():
    return load_mcp_module("public_research_nurtureany_server.py", "public_research_nurtureany_server_under_test")


class PublicResearchNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_public_research_module()
        self.research_module = sys.modules[self.module._research_public_company_signals.__module__]

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

    def test_missing_tavily_key_blocks_before_http(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.research_module, "_request_json", side_effect=AssertionError("should not call Tavily")
        ):
            result = self.module.research_public_company_signals("ae@staffany.com", [self.scoped_company()])

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("TAVILY_API_KEY", result["answer"])
        self.assertEqual(result["cost_report"]["actual_cost_usd"], 0)
        self.assertFalse(result["will_mutate_hubspot"])

    def test_unscoped_company_input_blocks_before_key_or_http(self):
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.module, "_token", side_effect=AssertionError("should not read token")
        ), patch.object(
            self.research_module, "_request_json", side_effect=AssertionError("should not call Tavily")
        ):
            result = self.module.research_public_company_signals(
                "ae@staffany.com",
                [{"name": "Acme Cafe", "domain": "acme.example"}],
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("requires scoped HubSpot company inputs", result["answer"])
        self.assertEqual(result["cost_report"]["actual_cost_usd"], 0)

    def test_brand_parent_lookup_allows_identity_search_before_hubspot_rescope(self):
        calls = []

        def fake_request(endpoint, token, body):
            calls.append((endpoint, body))
            self.assertEqual(endpoint, "/search")
            return {
                "results": [
                    {
                        "title": "Supply Chain Administrator | The Better Kompany Pte Ltd",
                        "url": "https://sg.jobstreet.com/job/87884312",
                        "content": "The Better Kompany is a fast-growing F&B group behind brands including Eat 3 Bowls and Super Sushi.",
                        "score": 0.9,
                    },
                    {
                        "title": "e2i Job Listing",
                        "url": "https://event.e2i.com.sg/job-detail/8520/1288",
                        "content": "Company Name | The Better Kompany. F&B Crew (Eat 3 Bowls Kiosk).",
                        "score": 0.8,
                    },
                ]
            }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.research_module, "_request_json", side_effect=fake_request
        ):
            result = self.module.find_brand_parent_candidates(
                "jeffrey@staffany.com",
                "Eat 3 Bowl",
                country="Singapore",
                max_results_per_query=5,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertFalse(result["will_mutate_hubspot"])
        self.assertTrue(all(endpoint == "/search" for endpoint, _body in calls))
        candidates = result["answer"]["parent_candidates"]
        self.assertTrue(candidates)
        self.assertIn("Better Kompany", " ".join(candidates[0]["suggested_hubspot_queries"]))
        self.assertIn("Re-query", result["answer"]["hubspot_next_step"])
        self.assertIn("HubSpot", result["scope"]["safety"])

    def test_dict_wrapped_companies_do_not_crash_before_key_check(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.research_module, "_request_json", side_effect=AssertionError("should not call Tavily")
        ):
            result = self.module.research_public_company_signals(
                "ae@staffany.com",
                {"companies": [self.scoped_company()]},
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("TAVILY_API_KEY", result["answer"])
        self.assertEqual(result["scope"]["requested_company_count"], 1)

    def test_company_query_result_and_cost_caps_are_enforced(self):
        calls = []

        def fake_request(endpoint, token, body):
            calls.append((endpoint, body))
            if endpoint == "/extract":
                return {
                    "results": [
                        {
                            "url": url,
                            "raw_content": "We are hiring for a new outlet and need scheduling support.",
                        }
                        for url in body["urls"]
                    ]
                }
            query = body.get("query", "")
            match = re.search(r'"([^"]+)"', query)
            label = match.group(1) if match else "Company"
            slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "company"
            return {
                "results": [
                    {
                        "title": f"{label} Careers {index}",
                        "url": f"https://{slug}.example/careers/{index}",
                        "content": f"{label} is hiring roles for expansion and payroll operations.",
                        "score": 0.9,
                    }
                    for index in range(10)
                ]
            }

        companies = [
            self.scoped_company(company_id=f"hubspot-{index}", name=f"Company {index}", domain=f"company{index}.example")
            for index in range(6)
        ]

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.research_module, "_request_json", side_effect=fake_request
        ), patch.object(
            self.research_module, "is_public_url", return_value=True
        ):
            result = self.module.research_public_company_signals(
                "ae@staffany.com",
                companies,
                research_mode="standard",
                max_results_per_query=99,
            )

        search_calls = [body for endpoint, body in calls if endpoint == "/search"]
        extract_calls = [body for endpoint, body in calls if endpoint == "/extract"]
        self.assertEqual(len(result["answer"]), self.module.MAX_RESEARCH_COMPANIES)
        self.assertEqual(len(search_calls), self.module.MAX_RESEARCH_COMPANIES * 5)
        self.assertEqual(len(extract_calls), self.module.MAX_RESEARCH_COMPANIES)
        self.assertTrue(result["truncated"])
        self.assertIn("cost_report", result)
        for body in search_calls:
            self.assertEqual(body["search_depth"], "basic")
            self.assertEqual(body["max_results"], 5)
            self.assertFalse(body["include_raw_content"])
        for body in extract_calls:
            self.assertLessEqual(len(body["urls"]), 4)
        for cost in result["cost_report"]["by_company"]:
            self.assertLessEqual(cost["estimated_credits"], cost["credit_cap_for_mode"])
            self.assertEqual(cost["credit_cap_for_mode"], 9)

    def test_social_and_gated_urls_become_manual_check_and_are_not_extracted(self):
        extract_urls = []

        def fake_request(endpoint, token, body):
            if endpoint == "/extract":
                extract_urls.extend(body["urls"])
                return {"results": [{"url": url, "raw_content": "Opening soon and hiring."} for url in body["urls"]]}
            return {
                "results": [
                    {
                        "title": "LinkedIn result",
                        "url": "https://www.linkedin.com/company/acme-cafe",
                        "content": "Founder and owner listed here.",
                    },
                    {
                        "title": "Instagram hiring",
                        "url": "https://www.instagram.com/acmecafe",
                        "content": "New outlet opening soon. Hiring.",
                    },
                    {
                        "title": "Official careers",
                        "url": "https://acme.example/careers",
                        "content": "Careers page hiring baristas.",
                    },
                ]
            }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.research_module, "_request_json", side_effect=fake_request
        ), patch.object(
            self.research_module, "is_public_url", return_value=True
        ):
            result = self.module.research_public_company_signals("ae@staffany.com", [self.scoped_company()])

        manual_types = {item["source_type"] for item in result["manual_check_items"]}
        self.assertIn("linkedin_manual", manual_types)
        self.assertIn("instagram_tiktok_manual", manual_types)
        self.assertEqual(extract_urls, ["https://acme.example/careers"])
        self.assertFalse(result["will_mutate_hubspot"])

    def test_recommends_exa_people_candidates_when_decision_maker_coverage_missing(self):
        def fake_request(endpoint, token, body):
            if endpoint == "/extract":
                return {"results": [{"url": url, "raw_content": "Hiring baristas for a new outlet."} for url in body["urls"]]}
            return {
                "results": [
                    {
                        "title": "Acme Cafe Careers",
                        "url": "https://acme.example/careers",
                        "content": "Hiring baristas for a new outlet.",
                    }
                ]
            }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.research_module, "_request_json", side_effect=fake_request
        ):
            result = self.module.research_public_company_signals("ae@staffany.com", [self.scoped_company()])

        self.assertEqual(result["answer"][0]["recommended_next_tool"], "search_exa_people_candidates")
        self.assertEqual(
            result["game_plan_inputs"][0]["recommended_next_tool"],
            "search_exa_people_candidates",
        )

    def test_opening_hours_directory_copy_does_not_become_growth_signal(self):
        signals = self.research_module.extract_company_signals(
            {
                "title": "Acme Cafe company profile",
                "snippet": "Address, operating status, and opening hours for Acme Cafe.",
            },
            "general_web",
            "https://directory.example/acme-cafe",
            "",
        )

        self.assertNotIn("growth_signal", {signal["signal_type"] for signal in signals})

    def test_generic_web_extract_boilerplate_does_not_create_positive_signal(self):
        signals = self.research_module.extract_company_signals(
            {
                "title": "Acme Cafe company registry profile",
                "snippet": "Official company information, address, and operating status.",
            },
            "general_web",
            "https://directory.example/acme-cafe",
            "Footer links: job opening, new outlet, payroll, expansion.",
        )

        signal_types = {signal["signal_type"] for signal in signals}
        self.assertNotIn("hiring_signal", signal_types)
        self.assertNotIn("growth_signal", signal_types)

    def test_public_extract_promotes_named_founder_candidate_from_general_web_article(self):
        signals = self.research_module.extract_company_signals(
            {
                "title": "Acme Cafe opens a new outlet",
                "snippet": "Acme Cafe opened a new outlet in Singapore.",
            },
            "general_web",
            "https://news.example/acme-cafe-opening",
            "The journey is led by founder, Meisin Tan, who wants to bring local dining memories to the CBD.",
        )
        candidates = self.research_module.extract_public_people_candidates(
            {
                "title": "Acme Cafe opens a new outlet",
                "snippet": "Acme Cafe opened a new outlet in Singapore.",
            },
            "general_web",
            "https://news.example/acme-cafe-opening",
            "The journey is led by founder, Meisin Tan, who wants to bring local dining memories to the CBD.",
        )

        self.assertIn("decision_maker_hint", {signal["signal_type"] for signal in signals})
        self.assertEqual(candidates[0]["name"], "Meisin Tan")
        self.assertEqual(candidates[0]["title"], "Founder")
        self.assertEqual(candidates[0]["source_url"], "https://news.example/acme-cafe-opening")

    def test_public_extract_returns_public_company_email_and_phone_channels(self):
        channels = self.research_module.extract_public_contact_channels(
            {
                "title": "Acme Cafe contact page",
                "snippet": "Contact us for bookings.",
            },
            "company_website",
            "https://acme.example/contact",
            "For reservations WhatsApp +65 8123 4567 or email info@acme.example.",
        )

        values = {channel["value"] for channel in channels}
        self.assertIn("info@acme.example", values)
        self.assertIn("+6581234567", values)
        self.assertTrue(all(channel["usage"].startswith("public company channel") for channel in channels))

    def test_standard_queries_include_contact_channels_and_country_job_boards(self):
        queries = self.research_module.company_queries(self.scoped_company(), "standard")

        joined = "\n".join(queries)
        self.assertEqual(len(queries), 5)
        self.assertIn("contact phone email WhatsApp booking", joined)
        self.assertIn("site:acme.example contact phone email WhatsApp booking careers hiring", joined)
        self.assertIn("JobStreet OR Indeed OR Glints OR MyCareersFuture", joined)

    def test_extract_priority_prefers_official_contact_and_job_board_pages(self):
        urls = [
            "https://news.example/acme-opening",
            "https://sg.jobstreet.com/job/123",
            "https://acme.example/about",
            "https://acme.example/contact-us",
        ]
        ordered = sorted(urls, key=lambda url: self.research_module._extract_priority(url, "acme.example"))

        self.assertEqual(ordered[0], "https://acme.example/contact-us")
        self.assertEqual(ordered[1], "https://acme.example/about")
        self.assertEqual(ordered[2], "https://sg.jobstreet.com/job/123")

    def test_unrelated_tavily_results_are_filtered_before_signals(self):
        def fake_request(endpoint, token, body):
            if endpoint == "/extract":
                return {"results": [{"url": url, "raw_content": "Acme Cafe is hiring for a new outlet."} for url in body["urls"]]}
            return {
                "results": [
                    {
                        "title": "Skrill expands digital payment services",
                        "url": "https://example-news.invalid/skrill-expands",
                        "content": "Skrill is expanding globally with digital wallet adoption.",
                    },
                    {
                        "title": "Acme Cafe Careers",
                        "url": "https://acme.example/careers",
                        "content": "Acme Cafe is hiring for a new outlet.",
                    },
                ]
            }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}), patch.object(
            self.research_module, "_request_json", side_effect=fake_request
        ), patch.object(
            self.research_module, "is_public_url", return_value=True
        ):
            result = self.module.research_public_company_signals("ae@staffany.com", [self.scoped_company()])

        urls = {item["source_url"] for item in result["source_evidence"]}
        self.assertIn("https://acme.example/careers", urls)
        self.assertNotIn("https://example-news.invalid/skrill-expands", urls)
        self.assertTrue(
            all(signal["source_url"] != "https://example-news.invalid/skrill-expands" for signal in result["company_signals"])
        )


if __name__ == "__main__":
    unittest.main()
