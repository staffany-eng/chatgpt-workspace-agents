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
        self.tools = []

    def tool(self):
        def decorate(func):
            self.tools.append(func)
            return func

        return decorate

    def run(self, *args, **kwargs):
        return None


def load_luma_module():
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp

    module_name = "luma_nurtureany_server_under_test"
    sys.modules.pop(module_name, None)
    path = Path(__file__).with_name("luma_nurtureany_server.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class LumaNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_luma_module()

    def scoped_company(self, **overrides):
        company = {
            "company_id": "hubspot-123",
            "name": "Bali Beans",
            "domain": "balibeans.com",
            "contacts": [{"email": "owner@balibeans.com"}],
            "hubspot_scoped": True,
            "scope_source": self.module.SCOPE_SOURCE,
        }
        company.update(overrides)
        return company

    def test_exposes_read_only_tools_only(self):
        self.assertEqual(
            sorted(tool.__name__ for tool in self.module.mcp.tools),
            ["get_luma_event_context", "list_luma_events"],
        )
        for forbidden in ["add", "update", "invite", "export", "create"]:
            self.assertNotIn(forbidden, " ".join(tool.__name__ for tool in self.module.mcp.tools))

    def test_missing_key_returns_blocked_without_network_call(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "urllib.request.urlopen", side_effect=AssertionError("should not call Luma")
        ):
            result = self.module.list_luma_events("ae@staffany.com", query="Bali")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("LUMA_API_KEY", result["answer"])

    def test_list_luma_events_caps_and_returns_safe_event_fields(self):
        calls = []

        def fake_request(path, params=None):
            calls.append((path, params))
            return {
                "entries": [
                    {
                        "event": {
                            "event_id": "evt-1",
                            "name": "Bali Beans Dinner",
                            "description": "internal planning note",
                            "start_at": "2026-05-01T10:00:00Z",
                            "end_at": "2026-05-01T12:00:00Z",
                            "timezone": "Asia/Singapore",
                            "url": "https://lu.ma/bali",
                        }
                    }
                ],
                "has_more": False,
            }

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                query="Bali",
                start="2026-05-01",
                end="2026-05-02",
                max_events=999,
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["scope"]["requested_limit"], self.module.MAX_EVENTS)
        self.assertEqual(calls[0][0], "/v1/calendar/list-events")
        self.assertEqual(calls[0][1]["pagination_limit"], self.module.MAX_EVENTS)
        event = result["answer"][0]
        self.assertEqual(event["event_id"], "evt-1")
        self.assertEqual(event["name"], "Bali Beans Dinner")
        self.assertNotIn("description", event)

    def test_unscoped_company_context_is_blocked_before_key_or_api_call(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Luma")
        ):
            result = self.module.get_luma_event_context(
                "ae@staffany.com",
                [{"name": "Bali Beans", "domain": "balibeans.com"}],
                event_ids=["evt-1"],
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("requires scoped HubSpot company inputs", result["answer"])

    def test_event_context_paginates_matches_and_does_not_export_raw_attendees(self):
        calls = []

        def fake_request(path, params=None):
            calls.append((path, params))
            if path == "/v1/event/get":
                return {
                    "event_id": "evt-1",
                    "name": "StaffAny Growth Dinner",
                    "start_at": "2026-05-01T10:00:00Z",
                }
            if path == "/v1/event/get-guests" and not params.get("pagination_cursor"):
                return {
                    "entries": [
                        {
                            "name": "Owner One",
                            "email": "owner@balibeans.com",
                            "approval_status": "approved",
                            "checked_in_at": "2026-05-01T10:10:00Z",
                        },
                        {
                            "name": "Ops Two",
                            "email": "ops@kopi.house",
                            "approval_status": "approved",
                        },
                    ],
                    "has_more": True,
                    "next_cursor": "page-2",
                }
            if path == "/v1/event/get-guests" and params.get("pagination_cursor") == "page-2":
                return {
                    "entries": [
                        {
                            "name": "Candidate Three",
                            "email": "person@gmail.com",
                            "approval_status": "waitlist",
                            "registration_answers": [{"question": "Company", "answer": "Bali Beans"}],
                        },
                        {
                            "name": "Unmatched Four",
                            "email": "raw@example.com",
                            "phone_number": "+6512345678",
                            "approval_status": "declined",
                        },
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        companies = [
            self.scoped_company(company_id="hubspot-1"),
            self.scoped_company(
                company_id="hubspot-2",
                name="Kopi House",
                domain="kopi.house",
                contacts=[],
            ),
        ]

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.get_luma_event_context(
                "ae@staffany.com",
                companies,
                event_ids=["evt-1"],
                max_guests_per_event=250,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual([call[1].get("pagination_cursor") for call in calls if call[0] == "/v1/event/get-guests"], ["", "page-2"])
        event_context = result["answer"][0]
        self.assertEqual(event_context["matched_account_ids"], ["hubspot-1", "hubspot-2"])
        self.assertEqual(event_context["total_guest_count"], 4)
        self.assertEqual(event_context["checked_in_count"], 1)
        self.assertEqual(event_context["rsvp_counts"]["approved"], 2)
        self.assertEqual(event_context["rsvp_counts"]["waitlist"], 1)
        self.assertEqual(len(event_context["matches"]), 3)

        by_reason = {match["match_reason"]: match for match in event_context["matches"]}
        self.assertEqual(by_reason["exact_hubspot_contact_email"]["company_id"], "hubspot-1")
        self.assertEqual(by_reason["exact_hubspot_contact_email"]["confidence"], "verified")
        self.assertTrue(by_reason["exact_hubspot_contact_email"]["attended"])
        self.assertEqual(by_reason["exact_email_domain"]["company_id"], "hubspot-2")
        self.assertEqual(by_reason["company_name_candidate"]["confidence"], "needs-check")

        serialized = str(result)
        self.assertNotIn("owner@balibeans.com", serialized)
        self.assertNotIn("ops@kopi.house", serialized)
        self.assertNotIn("raw@example.com", serialized)
        self.assertNotIn("+6512345678", serialized)
        for match in event_context["matches"]:
            self.assertIn("email_hash", match)
            self.assertIn("email_domain", match)
            self.assertNotIn("email", match)
            self.assertNotIn("phone", match)

    def test_guest_cap_sets_truncated_metadata(self):
        def fake_request(path, params=None):
            if path == "/v1/event/get":
                return {"event_id": "evt-1", "name": "StaffAny Growth Dinner"}
            if path == "/v1/event/get-guests":
                return {
                    "entries": [
                        {"name": "One", "email": "one@balibeans.com", "approval_status": "approved"},
                        {"name": "Two", "email": "two@balibeans.com", "approval_status": "approved"},
                    ],
                    "has_more": True,
                    "next_cursor": "page-2",
                }
            raise AssertionError(f"unexpected call: {path}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.get_luma_event_context(
                "ae@staffany.com",
                [self.scoped_company()],
                event_ids=["evt-1"],
                max_guests_per_event=2,
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertTrue(result["truncated"])
        self.assertTrue(result["answer"][0]["truncated"])
        self.assertTrue(result["answer"][0]["has_more"])

    def test_rate_limit_and_timeout_return_blocked(self):
        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module,
            "_request_json",
            side_effect=self.module.LumaError("Luma API rate limited after backoff: 429 quota exceeded", 429),
        ):
            result = self.module.list_luma_events("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("429", result["answer"])

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module,
            "_request_json",
            side_effect=self.module.LumaError("Luma API request timed out or failed: timed out"),
        ):
            result = self.module.list_luma_events("ae@staffany.com")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("timed out", result["answer"])

    def test_api_error_redacts_luma_key(self):
        with patch.dict(os.environ, {"LUMA_API_KEY": "secret-luma-key"}):
            message = self.module._error_message(403, '{"error":{"message":"bad secret-luma-key"}}')

        self.assertIn("[REDACTED_LUMA_API_KEY]", message)
        self.assertNotIn("secret-luma-key", message)


if __name__ == "__main__":
    unittest.main()
