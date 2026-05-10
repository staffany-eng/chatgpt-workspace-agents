import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

MCP_DIR = Path(__file__).resolve().parent
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))
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


def load_calendar_module():
    sys.modules["mcp"] = types.ModuleType("mcp")
    sys.modules["mcp.server"] = types.ModuleType("mcp.server")
    fastmcp = types.ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeMCP
    sys.modules["mcp.server.fastmcp"] = fastmcp

    module_name = "google_calendar_nurtureany_server_under_test"
    sys.modules.pop(module_name, None)
    path = Path(__file__).with_name("google_calendar_nurtureany_server.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class GoogleCalendarNurtureAnyServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_calendar_module()

    def audit_seed(self, contact_email="ada@balibeans.com", verified=True, role_inferred=False):
        return {
            "company_id": "company-1",
            "company_name": "Bali Beans",
            "company_domain": "balibeans.com",
            "owner_email": "ae@staffany.com",
            "owner_name": "AE One",
            "calendar_account_email": "team@staffany.com",
            "calendar_ids": ["ae@staffany.com"],
            "missing_clean_lead_fields": ["current tools"],
            "decision_maker_coverage": {"status": "verified" if verified else "needs-check"},
            "ic_bant_readiness": {
                "authority": "verified" if verified else "needs-check",
                "current_tools": "missing",
                "timeline": "verified",
                "stakeholder_map": "verified",
                "need": "needs-check",
            },
            "contact_match_records": [
                {
                    "contact_id": "contact-1",
                    "display_name": "Ada N.",
                    "persona": "Owner",
                    "buying_role": "DECISION_MAKER" if verified else "",
                    "is_verified_decision_maker": verified,
                    "is_role_inferred_decision_maker": role_inferred,
                    "decision_maker_confidence": "verified" if verified else "needs-check" if role_inferred else "",
                    "email_domain": "balibeans.com",
                    "email_hash": self.module._hash_email(contact_email),
                }
            ],
        }

    def test_missing_token_returns_blocked_without_calling_google(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {
                "GOOGLE_CALENDAR_TOKEN_FILE": str(Path(tmpdir) / "missing-token.json"),
                "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
            },
        ), patch.object(self.module, "_request_json", side_effect=AssertionError("should not call Google")):
            result = self.module.list_google_calendar_events("ae@staffany.com", query="Bali Beans")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Missing Google Calendar OAuth file", result["answer"])

    def test_list_caps_scope_and_redacts_private_event_fields(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append((path, params, access_token))
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Bali Beans follow-up",
                        "description": "private note",
                        "start": {"dateTime": "2026-05-12T02:00:00Z"},
                        "end": {"dateTime": "2026-05-12T02:30:00Z"},
                        "attendees": [
                            {"email": "one@example.com"},
                            {"email": "two@example.com"},
                        ],
                        "hangoutLink": "https://meet.google.com/private",
                        "htmlLink": "https://calendar.google.com/event?eid=event-1",
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CALENDAR_TOKEN_FILE": str(token_file),
                    "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.list_google_calendar_events(
                    "ae@staffany.com",
                    query="Bali Beans",
                    start="2026-05-12T00:00:00Z",
                    end="2026-05-13T00:00:00Z",
                    calendar_ids=["cal-1", "cal-2", "cal-3", "cal-4", "cal-5", "cal-6"],
                    max_results=999,
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(calls), self.module.MAX_CALENDARS)
        self.assertEqual(result["scope"]["calendar_account_email"], "team@staffany.com")
        self.assertEqual(result["scope"]["max_events_per_calendar"], self.module.MAX_EVENTS_PER_CALENDAR)
        for _, params, access_token in calls:
            self.assertEqual(access_token, "access-token")
            self.assertEqual(params["q"], "Bali Beans")
            self.assertEqual(params["maxResults"], self.module.MAX_EVENTS_PER_CALENDAR)

        event = result["answer"][0]
        self.assertEqual(event["attendee_count"], 2)
        self.assertTrue(event["has_conference_link"])
        self.assertNotIn("description", event)
        self.assertNotIn("attendees", event)

    def test_calendar_access_failures_are_reported_per_calendar(self):
        def fake_request(path, params, access_token):
            if "jeremy.wong%40staffany.com" in path:
                raise self.module.GoogleCalendarError("Google Calendar API failed: 403 forbidden", 403)
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Tang Tea House follow-up",
                        "start": {"dateTime": "2026-05-12T08:00:00Z"},
                        "end": {"dateTime": "2026-05-12T09:00:00Z"},
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CALENDAR_TOKEN_FILE": str(token_file),
                    "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.list_google_calendar_events(
                    "ae@staffany.com",
                    query="Tang Tea House",
                    calendar_ids=["primary", "jeremy.wong@staffany.com"],
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"][0]["summary"], "Tang Tea House follow-up")
        self.assertEqual(result["scope"]["blocked_calendar_ids"][0]["calendar_id"], "jeremy.wong@staffany.com")
        self.assertIn("not accessible", result["caveat"])

    def test_omits_empty_query_parameter(self):
        captured_params = []

        def fake_request(path, params, access_token):
            captured_params.append(params)
            return {"items": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CALENDAR_TOKEN_FILE": str(token_file),
                    "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.list_google_calendar_events(
                    "ae@staffany.com",
                    query=None,
                    calendar_ids=["jeremy.wong@staffany.com"],
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["scope"]["query"], "")
        self.assertNotIn("q", captured_params[0])

    def test_refuses_non_team_account(self):
        with patch.dict(os.environ, {"GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Google")
        ):
            result = self.module.list_google_calendar_events(
                "ae@staffany.com", query="Bali Beans", account_email="other@staffany.com"
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"])

    def test_audit_marks_verified_decision_maker_attendee_good_without_raw_email(self):
        def fake_request(path, params, access_token):
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Bali Beans intro",
                        "description": "private",
                        "start": {"dateTime": "2026-05-12T08:00:00Z"},
                        "end": {"dateTime": "2026-05-12T09:00:00Z"},
                        "attendees": [
                            {"email": "ada@balibeans.com"},
                            {"email": "ae@staffany.com"},
                        ],
                        "hangoutLink": "https://meet.google.com/private",
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CALENDAR_TOKEN_FILE": str(token_file),
                    "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.audit_google_calendar_meeting_quality(
                    "ae@staffany.com",
                    self.audit_seed(),
                )

        self.assertEqual(result["confidence"], "verified")
        self.assertEqual(result["answer"]["status"], "good")
        event = result["answer"]["events"][0]
        self.assertEqual(event["quality_status"], "good")
        self.assertTrue(event["right_people_audit"]["verified_decision_maker_present"])
        self.assertEqual(event["matched_hubspot_contacts"][0]["display_name"], "Ada N.")
        serialized = json.dumps(result)
        self.assertNotIn("ada@balibeans.com", serialized)
        self.assertNotIn("private", serialized)
        self.assertNotIn("meet.google.com", serialized)
        self.assertNotIn("attendees", serialized)

    def test_audit_role_only_buyer_is_needs_check_not_good(self):
        def fake_request(path, params, access_token):
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Bali Beans intro",
                        "start": {"dateTime": "2026-05-12T08:00:00Z"},
                        "end": {"dateTime": "2026-05-12T09:00:00Z"},
                        "attendees": [{"email": "owner@balibeans.com"}],
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(os.environ, {"GOOGLE_CALENDAR_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ):
                result = self.module.audit_google_calendar_meeting_quality(
                    "ae@staffany.com",
                    self.audit_seed("owner@balibeans.com", verified=False, role_inferred=True),
                )

        self.assertEqual(result["answer"]["events"][0]["quality_status"], "needs-check")
        self.assertEqual(result["confidence"], "needs-check")

    def test_audit_company_domain_without_hubspot_contact_is_needs_check(self):
        def fake_request(path, params, access_token):
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Bali Beans intro",
                        "start": {"dateTime": "2026-05-12T08:00:00Z"},
                        "end": {"dateTime": "2026-05-12T09:00:00Z"},
                        "attendees": [{"email": "unknown@balibeans.com"}],
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(os.environ, {"GOOGLE_CALENDAR_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ):
                result = self.module.audit_google_calendar_meeting_quality("ae@staffany.com", self.audit_seed())

        event = result["answer"]["events"][0]
        self.assertEqual(event["quality_status"], "needs-check")
        self.assertEqual(event["right_people_audit"]["company_domain_attendee_count"], 1)

    def test_audit_staffany_only_event_is_gap(self):
        def fake_request(path, params, access_token):
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Bali Beans prep",
                        "start": {"dateTime": "2026-05-12T08:00:00Z"},
                        "end": {"dateTime": "2026-05-12T09:00:00Z"},
                        "attendees": [{"email": "ae@staffany.com"}, {"email": "manager@staffany.com"}],
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(os.environ, {"GOOGLE_CALENDAR_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ):
                result = self.module.audit_google_calendar_meeting_quality("ae@staffany.com", self.audit_seed())

        self.assertEqual(result["answer"]["status"], "gap")
        self.assertEqual(result["answer"]["events"][0]["quality_status"], "gap")
        self.assertTrue(result["answer"]["events"][0]["right_people_audit"]["staffany_only"])

    def test_audit_inaccessible_calendar_is_blocked(self):
        def fake_request(path, params, access_token):
            raise self.module.GoogleCalendarError("Google Calendar API failed: 403 forbidden", 403)

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"access-token","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(os.environ, {"GOOGLE_CALENDAR_TOKEN_FILE": str(token_file)}), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ):
                result = self.module.audit_google_calendar_meeting_quality("ae@staffany.com", self.audit_seed())

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"]["status"], "blocked")
        self.assertEqual(result["scope"]["blocked_calendar_ids"][0]["calendar_id"], "ae@staffany.com")

    def test_refreshes_token_after_401(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append(access_token)
            if len(calls) == 1:
                raise self.module.GoogleCalendarError("expired", 401)
            return {"items": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            token_file = Path(tmpdir) / "token.json"
            token_file.write_text(
                '{"token":"old-token","refresh_token":"refresh","client_id":"id","client_secret":"secret","scopes":["https://www.googleapis.com/auth/calendar.readonly"]}'
            )
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_CALENDAR_TOKEN_FILE": str(token_file),
                    "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
                },
            ), patch.object(self.module, "_request_json", side_effect=fake_request), patch.object(
                self.module, "_refresh_access_token", return_value="new-token"
            ):
                result = self.module.list_google_calendar_events("ae@staffany.com", query="Bali Beans")

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(calls, ["old-token", "new-token"])


if __name__ == "__main__":
    unittest.main()
