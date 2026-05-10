import importlib.util
import os
import sys
import tempfile
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

    def test_refuses_non_team_account(self):
        with patch.dict(os.environ, {"GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com"}), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Google")
        ):
            result = self.module.list_google_calendar_events(
                "ae@staffany.com", query="Bali Beans", account_email="other@staffany.com"
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"])

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
