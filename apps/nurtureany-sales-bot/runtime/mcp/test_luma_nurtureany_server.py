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

    def test_list_luma_events_filters_with_luma_event_tags(self):
        calls = []

        def fake_request(path, params=None):
            calls.append((path, params or {}))
            if path == "/v1/calendar/event-tags/list":
                return {
                    "entries": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-appreciation", "name": "Appreciation Afternoon"},
                    ]
                }
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {
                            "event": {
                                "api_id": "evt-sg",
                                "name": "StaffAny Appreciation Afternoon (SG)",
                                "start_at": "2026-05-20T06:00:00Z",
                                "timezone": "Asia/Singapore",
                            }
                        },
                        {
                            "event": {
                                "api_id": "evt-jkt",
                                "name": "StaffAny Appreciation Afternoon (JKT)",
                                "start_at": "2026-06-18T08:00:00Z",
                                "timezone": "Asia/Jakarta",
                            }
                        },
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get" and params.get("id") == "evt-sg":
                return {
                    "api_id": "evt-sg",
                    "name": "StaffAny Appreciation Afternoon (SG)",
                    "tags": [
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-appreciation", "name": "Appreciation Afternoon"},
                    ],
                }
            if path == "/v1/event/get" and params.get("id") == "evt-jkt":
                return {
                    "api_id": "evt-jkt",
                    "name": "StaffAny Appreciation Afternoon (JKT)",
                    "tags": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-appreciation", "name": "Appreciation Afternoon"},
                    ],
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                country="Indonesia",
                event_type="appreciation afternoon",
                max_events=10,
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual([event["event_id"] for event in result["answer"]], ["evt-jkt"])
        event = result["answer"][0]
        self.assertEqual(event["tags"], ["Jakarta", "Appreciation Afternoon"])
        self.assertEqual(event["location_tags"], ["Jakarta"])
        self.assertEqual(event["country_tags"], ["Indonesia"])
        self.assertEqual(event["event_type_tags"], ["Appreciation Afternoon"])
        self.assertEqual(event["tag_match_source"], "luma_event_tags")
        self.assertIn(("/v1/event/get", {"id": "evt-jkt"}), calls)

    def test_location_tag_filter_narrows_indonesia_city_events(self):
        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {
                    "entries": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ]
                }
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {"event": {"api_id": "evt-jkt", "name": "StaffAny HR Happy Hour (JKT)"}},
                        {"event": {"api_id": "evt-bali", "name": "StaffAny HR Happy Hour (Bali)"}},
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get" and params.get("id") == "evt-jkt":
                return {
                    "api_id": "evt-jkt",
                    "name": "StaffAny HR Happy Hour (JKT)",
                    "tags": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            if path == "/v1/event/get" and params.get("id") == "evt-bali":
                return {
                    "api_id": "evt-bali",
                    "name": "StaffAny HR Happy Hour (Bali)",
                    "tags": [
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                country="Indonesia",
                location="Jakarta",
                event_type="hr happy hour",
                max_events=10,
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual([event["event_id"] for event in result["answer"]], ["evt-jkt"])
        self.assertEqual(result["answer"][0]["location_tags"], ["Jakarta"])
        self.assertEqual(result["answer"][0]["country_tags"], ["Indonesia"])
        self.assertEqual(result["scope"]["location_filter"], "Jakarta")

    def test_location_tags_are_tolerated_in_event_type_or_country_inputs(self):
        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {
                    "entries": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ]
                }
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {"event": {"api_id": "evt-jkt", "name": "StaffAny HR Happy Hour (JKT)"}},
                        {"event": {"api_id": "evt-bali", "name": "StaffAny HR Happy Hour (Bali)"}},
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get" and params.get("id") == "evt-jkt":
                return {
                    "api_id": "evt-jkt",
                    "name": "StaffAny HR Happy Hour (JKT)",
                    "tags": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            if path == "/v1/event/get" and params.get("id") == "evt-bali":
                return {
                    "api_id": "evt-bali",
                    "name": "StaffAny HR Happy Hour (Bali)",
                    "tags": [
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            event_type_result = self.module.list_luma_events(
                "ae@staffany.com",
                event_type="Jakarta HR Happy Hour",
                max_events=10,
            )
            country_result = self.module.list_luma_events(
                "ae@staffany.com",
                country="Jakarta",
                event_type="hr happy hour",
                max_events=10,
            )

        self.assertEqual([event["event_id"] for event in event_type_result["answer"]], ["evt-jkt"])
        self.assertEqual(event_type_result["scope"]["location_filter"], "Jakarta")
        self.assertEqual(event_type_result["scope"]["event_type_filter"], "HR Happy Hour")
        self.assertEqual([event["event_id"] for event in country_result["answer"]], ["evt-jkt"])
        self.assertEqual(country_result["scope"]["location_filter"], "Jakarta")
        self.assertEqual(country_result["scope"]["country_filter"], "Indonesia")

    def test_explicit_luma_event_tags_filter_exact_tags(self):
        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {
                    "entries": [
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-sports", "name": "Sports"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ]
                }
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {"event": {"api_id": "evt-sports", "name": "F&B Play Club"}},
                        {"event": {"api_id": "evt-hhh", "name": "StaffAny HR Happy Hour (HHH)"}},
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get" and params.get("id") == "evt-sports":
                return {
                    "api_id": "evt-sports",
                    "name": "F&B Play Club",
                    "url": "https://lu.ma/fnb-play-club",
                    "tags": [
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-sports", "name": "Sports"},
                    ],
                }
            if path == "/v1/event/get" and params.get("id") == "evt-hhh":
                return {
                    "api_id": "evt-hhh",
                    "name": "StaffAny HR Happy Hour (HHH)",
                    "tags": [
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                event_tags=["Singapore", "Sports"],
                max_events=10,
            )

        self.assertEqual([event["event_id"] for event in result["answer"]], ["evt-sports"])
        self.assertEqual(result["scope"]["event_tag_filters"], ["Singapore", "Sports"])
        self.assertEqual(result["answer"][0]["tags"], ["Singapore", "Sports"])
        self.assertEqual(result["answer"][0]["url"], "https://lu.ma/fnb-play-club")

    def test_luma_event_tag_filters_fall_back_to_metadata_as_needs_check(self):
        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {"entries": []}
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {
                            "event": {
                                "api_id": "evt-jkt",
                                "name": "StaffAny Appreciation Afternoon (JKT)",
                                "start_at": "2026-06-18T08:00:00Z",
                                "timezone": "Asia/Jakarta",
                            }
                        }
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get":
                return {
                    "api_id": "evt-jkt",
                    "name": "StaffAny Appreciation Afternoon (JKT)",
                    "timezone": "Asia/Jakarta",
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                country="Indonesia",
                location="Jakarta",
                event_type="appreciation afternoon",
            )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"][0]["tag_match_source"], "inferred_from_event_metadata")
        self.assertEqual(result["answer"][0]["location_tags"], ["Jakarta"])
        self.assertEqual(result["answer"][0]["country_tags"], ["Indonesia"])
        self.assertEqual(result["answer"][0]["event_type_tags"], ["Appreciation Afternoon"])

    def test_tag_filtered_overfetch_sets_truncation_metadata(self):
        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {"entries": []}
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {
                            "event": {
                                "api_id": "evt-1",
                                "name": "StaffAny Appreciation Afternoon (JKT)",
                                "tags": [
                                    {"name": "Jakarta"},
                                    {"name": "Appreciation Afternoon"},
                                ],
                            }
                        },
                        {
                            "event": {
                                "api_id": "evt-2",
                                "name": "StaffAny Appreciation Afternoon (Bali)",
                                "tags": [
                                    {"name": "Bali"},
                                    {"name": "Appreciation Afternoon"},
                                ],
                            }
                        },
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.list_luma_events(
                "ae@staffany.com",
                country="Indonesia",
                event_type="appreciation afternoon",
                max_events=1,
            )

        self.assertEqual(len(result["answer"]), 1)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["confidence"], "needs-check")

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

    def test_event_context_uses_country_and_event_type_tags_before_guest_lookup(self):
        guest_calls = []

        def fake_request(path, params=None):
            if path == "/v1/calendar/event-tags/list":
                return {
                    "entries": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-sg", "name": "Singapore"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ]
                }
            if path == "/v1/calendar/list-events":
                return {
                    "entries": [
                        {"event": {"api_id": "evt-bali", "name": "StaffAny HR Happy Hour (Bali)"}},
                        {"event": {"api_id": "evt-jkt", "name": "StaffAny HR Happy Hour (JKT)"}},
                    ],
                    "has_more": False,
                }
            if path == "/v1/event/get" and params.get("id") == "evt-bali":
                return {
                    "api_id": "evt-bali",
                    "name": "StaffAny HR Happy Hour (Bali)",
                    "tags": [
                        {"api_id": "tag-bali", "name": "Bali"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            if path == "/v1/event/get" and params.get("id") == "evt-jkt":
                return {
                    "api_id": "evt-jkt",
                    "name": "StaffAny HR Happy Hour (JKT)",
                    "tags": [
                        {"api_id": "tag-jkt", "name": "Jakarta"},
                        {"api_id": "tag-hhh", "name": "HR Happy Hour"},
                    ],
                }
            if path == "/v1/event/get-guests":
                guest_calls.append(params["event_id"])
                return {
                    "entries": [
                        {
                            "name": "Owner One",
                            "email": "owner@balibeans.com",
                            "approval_status": "approved",
                            "checked_in_at": "2026-06-18T08:20:00Z",
                        }
                    ],
                    "has_more": False,
                }
            raise AssertionError(f"unexpected call: {path} {params}")

        with patch.dict(os.environ, {"LUMA_API_KEY": "test-key"}), patch.object(
            self.module, "_request_json", side_effect=fake_request
        ):
            result = self.module.get_luma_event_context(
                "ae@staffany.com",
                [self.scoped_company()],
                country="Indonesia",
                location="Jakarta",
                event_type="hr happy hour",
            )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(guest_calls, ["evt-jkt"])
        self.assertEqual(result["answer"][0]["event"]["location_tags"], ["Jakarta"])
        self.assertEqual(result["answer"][0]["event"]["country_tags"], ["Indonesia"])
        self.assertEqual(result["answer"][0]["matched_account_ids"], ["hubspot-123"])

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
