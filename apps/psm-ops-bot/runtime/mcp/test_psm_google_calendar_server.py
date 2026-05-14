from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_helpers import load_mcp_module


class PsmGoogleCalendarServerTest(unittest.TestCase):
    def setUp(self):
        self.module = load_mcp_module("psm_google_calendar_server.py")

    def test_missing_token_blocks_without_calling_google(self):
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            os.environ,
            {
                "GOOGLE_CALENDAR_TOKEN_FILE": str(Path(tmpdir) / "missing-token.json"),
                "GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com",
            },
            clear=False,
        ), patch.object(self.module, "_request_json", side_effect=AssertionError("should not call Google")):
            result = self.module.list_google_calendar_events("psm@staffany.com", query="Rock Productions")

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("Missing Google Calendar OAuth file", result["answer"]["message"])

    def test_customer_context_rejects_weak_query_without_calling_google(self):
        with patch.object(self.module, "_access_token", side_effect=AssertionError("should not call Google")):
            blank = self.module.read_customer_calendar_context(
                slack_user_email="psm@staffany.com",
                intent="find_existing_followup",
                customer_query="",
                start="2026-05-14",
                end="2026-05-21",
            )
            jo = self.module.read_customer_calendar_context(
                slack_user_email="psm@staffany.com",
                intent="find_existing_followup",
                customer_query="Jo",
                start="2026-05-14",
                end="2026-05-21",
            )

        self.assertEqual(blank["confidence"], "blocked")
        self.assertEqual(jo["confidence"], "blocked")
        self.assertIn("specific customer", blank["answer"]["message"])
        self.assertIn("specific customer", jo["answer"]["message"])

    def test_customer_context_requires_attendees_for_slot_suggestions_without_calling_google(self):
        with patch.object(self.module, "_access_token", side_effect=AssertionError("should not call Google")):
            result = self.module.read_customer_calendar_context(
                slack_user_email="psm@staffany.com",
                intent="suggest_meeting_slots",
                customer_query="Rock Productions",
                start="2026-05-14",
                end="2026-05-21",
                duration_minutes=30,
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("attendee_emails are required", result["answer"]["message"])

    def test_customer_context_followup_uses_bounded_safe_event_metadata(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append((path, params, access_token))
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Rock Productions follow-up",
                        "description": "private note",
                        "start": {"dateTime": "2026-05-14T03:00:00Z"},
                        "end": {"dateTime": "2026-05-14T03:30:00Z"},
                        "attendees": [
                            {"email": "customer@example.com"},
                            {"email": "psm@staffany.com"},
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
                clear=False,
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.read_customer_calendar_context(
                    slack_user_email="psm@staffany.com",
                    intent="find_existing_followup",
                    customer_query="Rock Productions",
                    start="2026-05-14",
                    end="2026-05-21",
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["q"], "Rock Productions")
        self.assertEqual(calls[0][1]["maxResults"], self.module.DEFAULT_CONTEXT_MAX_EVENTS)
        self.assertEqual(result["scope"]["event_count"], 1)
        event = result["answer"][0]
        self.assertEqual(event["title"], "Rock Productions follow-up")
        self.assertEqual(event["attendee_count"], 2)
        self.assertNotIn("calendar_id", event)
        self.assertNotIn("description", event)
        self.assertNotIn("attendees", event)
        self.assertNotIn("htmlLink", event)
        serialized = json.dumps(result)
        self.assertNotIn("customer@example.com", serialized)
        self.assertNotIn("meet.google.com", serialized)

    def test_customer_context_slot_suggestion_uses_freebusy_without_exposing_attendee_emails(self):
        calls = []

        def fake_freebusy(path, payload, access_token):
            calls.append((path, payload, access_token))
            return {
                "calendars": {
                    "psm@staffany.com": {"busy": []},
                    "cse@staffany.com": {"busy": []},
                }
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
                clear=False,
            ), patch.object(self.module, "_request_post_json", side_effect=fake_freebusy):
                result = self.module.read_customer_calendar_context(
                    slack_user_email="kaiyi@staffany.com",
                    intent="suggest_meeting_slots",
                    customer_query="Rock Productions",
                    start="2026-05-14T01:00:00Z",
                    end="2026-05-14T04:00:00Z",
                    attendee_emails=["psm@staffany.com", "cse@staffany.com"],
                    duration_minutes=30,
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "/freeBusy")
        self.assertEqual(len(calls[0][1]["items"]), 2)
        self.assertGreaterEqual(len(result["answer"]), 1)
        self.assertEqual(result["answer"][0]["attendee_count"], 2)
        serialized = json.dumps(result)
        self.assertNotIn("psm@staffany.com", serialized)
        self.assertNotIn("cse@staffany.com", serialized)

    def test_list_caps_scope_and_omits_private_event_fields(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append((path, params, access_token))
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Rock Productions follow-up",
                        "description": "private note",
                        "start": {"dateTime": "2026-05-14T03:00:00Z"},
                        "end": {"dateTime": "2026-05-14T03:30:00Z"},
                        "attendees": [
                            {"email": "customer@example.com"},
                            {"email": "psm@staffany.com"},
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
                clear=False,
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.list_google_calendar_events(
                    "psm@staffany.com",
                    query="Rock Productions",
                    start="2026-05-14T00:00:00Z",
                    end="2026-05-15T00:00:00Z",
                    calendar_ids=["cal-1", "cal-2", "cal-3", "cal-4", "cal-5", "cal-6"],
                    max_results=999,
                )

        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(len(calls), self.module.MAX_CALENDARS)
        self.assertEqual(result["scope"]["calendar_account_email"], "team@staffany.com")
        self.assertEqual(result["scope"]["max_events_per_calendar"], self.module.MAX_EVENTS_PER_CALENDAR)
        for _, params, access_token in calls:
            self.assertEqual(access_token, "access-token")
            self.assertEqual(params["q"], "Rock Productions")
            self.assertEqual(params["maxResults"], self.module.MAX_EVENTS_PER_CALENDAR)

        event = result["answer"][0]
        self.assertEqual(event["attendee_count"], 2)
        self.assertTrue(event["has_conference_link"])
        self.assertNotIn("description", event)
        self.assertNotIn("attendees", event)
        self.assertNotIn("htmlLink", event)
        serialized = json.dumps(result)
        self.assertNotIn("private note", serialized)
        self.assertNotIn("customer@example.com", serialized)
        self.assertNotIn("meet.google.com", serialized)
        self.assertNotIn("calendar.google.com", serialized)

    def test_refuses_non_team_account(self):
        with patch.dict(os.environ, {"GOOGLE_CALENDAR_ACCOUNT_EMAIL": "team@staffany.com"}, clear=False), patch.object(
            self.module, "_request_json", side_effect=AssertionError("should not call Google")
        ):
            result = self.module.list_google_calendar_events(
                "psm@staffany.com",
                query="Rock Productions",
                account_email="other@staffany.com",
            )

        self.assertEqual(result["confidence"], "blocked")
        self.assertIn("team@staffany.com", result["answer"]["message"])

    def test_calendar_access_failures_are_reported_per_calendar(self):
        def fake_request(path, params, access_token):
            if "owner%40staffany.com" in path:
                raise self.module.GoogleCalendarError("Google Calendar API failed: 403 forbidden", 403)
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Rock Productions follow-up",
                        "start": {"dateTime": "2026-05-14T03:00:00Z"},
                        "end": {"dateTime": "2026-05-14T03:30:00Z"},
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
                clear=False,
            ), patch.object(self.module, "_request_json", side_effect=fake_request):
                result = self.module.list_google_calendar_events(
                    "psm@staffany.com",
                    query="Rock Productions",
                    calendar_ids=["primary", "owner@staffany.com"],
                )

        self.assertEqual(result["confidence"], "blocked")
        self.assertEqual(result["answer"][0]["summary"], "Rock Productions follow-up")
        self.assertEqual(result["scope"]["blocked_calendar_ids"][0]["calendar_id"], "owner@staffany.com")
        self.assertIn("not accessible", result["caveat"])

    def test_rate_limit_is_retried_once_before_blocking(self):
        calls = []

        def fake_request(path, params, access_token):
            calls.append((path, params, access_token))
            if len(calls) == 1:
                raise self.module.GoogleCalendarError(
                    "Google Calendar API failed: 403 Quota exceeded for quota metric 'Queries'",
                    403,
                )
            return {
                "items": [
                    {
                        "id": "event-1",
                        "summary": "Rock Productions follow-up",
                        "start": {"dateTime": "2026-05-14T03:00:00Z"},
                        "end": {"dateTime": "2026-05-14T03:30:00Z"},
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
                clear=False,
            ), patch.object(self.module, "GOOGLE_CALENDAR_RATE_LIMIT_RETRY_SECONDS", 0), patch.object(
                self.module, "_request_json", side_effect=fake_request
            ), patch.object(self.module.time, "sleep") as sleep:
                result = self.module.list_google_calendar_events(
                    "psm@staffany.com",
                    query="Rock Productions",
                )

        self.assertEqual(len(calls), 2)
        sleep.assert_called_once_with(0)
        self.assertEqual(result["confidence"], "needs-check")
        self.assertEqual(result["answer"][0]["summary"], "Rock Productions follow-up")


if __name__ == "__main__":
    unittest.main()
