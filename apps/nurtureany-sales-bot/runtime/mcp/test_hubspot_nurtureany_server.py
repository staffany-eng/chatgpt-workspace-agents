import importlib.util
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

    def test_plan_hubspot_writeback_preserves_public_source_metadata(self):
        with patch.object(self.module, "_caller_scope", return_value=SCOPE):
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
