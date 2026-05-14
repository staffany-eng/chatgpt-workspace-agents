#!/usr/bin/env python3
"""Read-only Google Calendar MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import os
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from google_oauth import (
    access_token as _google_access_token,
    account_email as _google_account_email,
    load_json as _google_load_json,
    profile_file as _google_profile_file,
    refresh_access_token as _google_refresh_access_token,
    request_json as _google_request_json,
    safe_detail as _safe_detail,
)
from profile_env import load_profile_env


load_profile_env()

GOOGLE_CALENDAR_API_BASE_URL = "https://www.googleapis.com/calendar/v3"
GOOGLE_CALENDAR_USER_AGENT = "StaffAny-PSMOps/1.0 (+https://staffany.com)"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_BROAD_SCOPE = "https://www.googleapis.com/auth/calendar"
DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
DEFAULT_CALENDAR_ID = "primary"
GOOGLE_CALENDAR_TIMEOUT_SECONDS = 15
GOOGLE_CALENDAR_RATE_LIMIT_RETRY_SECONDS = int(os.environ.get("GOOGLE_CALENDAR_RATE_LIMIT_RETRY_SECONDS", "65"))
GOOGLE_CALENDAR_RATE_LIMIT_MAX_RETRIES = int(os.environ.get("GOOGLE_CALENDAR_RATE_LIMIT_MAX_RETRIES", "1"))
MAX_CALENDARS = 5
MAX_EVENTS_PER_CALENDAR = 50
DEFAULT_LOOKAHEAD_DAYS = 30
MAX_CONTEXT_WINDOW_DAYS = 31
DEFAULT_CONTEXT_MAX_EVENTS = 10
MAX_SUGGESTED_SLOTS = 5
SLOT_STEP_MINUTES = 30
DEFAULT_SLOT_TIMEZONE = "Asia/Singapore"
VALID_CONTEXT_INTENTS = {"find_existing_followup", "suggest_meeting_slots"}
WEAK_CUSTOMER_QUERY_TOKENS = {
    "calendar",
    "customer",
    "follow",
    "followup",
    "follow-up",
    "jo",
    "jos",
    "meeting",
    "team",
}


mcp = FastMCP(
    "psm_google_calendar",
    instructions=(
        "Read-only Google Calendar event context for PSM Ops Bot. Use only "
        "team@staffany.com, list bounded event metadata, and never mutate calendar data."
    ),
)


class GoogleCalendarError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _account_email() -> str:
    return _google_account_email("GOOGLE_CALENDAR_ACCOUNT_EMAIL", DEFAULT_ACCOUNT_EMAIL)


def _token_file():
    return _google_profile_file("GOOGLE_CALENDAR_TOKEN_FILE", "google-calendar-token.json")


def _client_secret_file():
    return _google_profile_file("GOOGLE_CALENDAR_CLIENT_SECRET_FILE", "google-calendar-client-secret.json")


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "caller_email": (slack_user_email or "").strip().lower(),
        "calendar_account_email": _account_email(),
        "read_only": True,
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": "Google Calendar",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def _access_token() -> str:
    return _google_access_token(
        _token_file(),
        _client_secret_file(),
        {CALENDAR_READONLY_SCOPE, CALENDAR_BROAD_SCOPE},
        GOOGLE_CALENDAR_USER_AGENT,
        GOOGLE_CALENDAR_TIMEOUT_SECONDS,
        "Google Calendar",
        GoogleCalendarError,
    )


def _refresh_access_token(payload: dict[str, Any]) -> str:
    return _google_refresh_access_token(
        payload,
        _token_file(),
        _client_secret_file(),
        GOOGLE_CALENDAR_USER_AGENT,
        GOOGLE_CALENDAR_TIMEOUT_SECONDS,
        "Google Calendar",
        GoogleCalendarError,
    )


def _request_json(path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
    return _google_request_json(
        GOOGLE_CALENDAR_API_BASE_URL,
        path,
        params,
        access_token,
        GOOGLE_CALENDAR_USER_AGENT,
        GOOGLE_CALENDAR_TIMEOUT_SECONDS,
        "Google Calendar",
        GoogleCalendarError,
    )


def _request_post_json(path: str, payload: dict[str, Any], access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{GOOGLE_CALENDAR_API_BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "user-agent": GOOGLE_CALENDAR_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_CALENDAR_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleCalendarError(f"Google Calendar API failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleCalendarError(f"Google Calendar API request timed out or failed: {reason}") from error


def _rfc3339(value: str | None, default: datetime) -> str:
    text = (value or "").strip()
    if not text:
        return default.isoformat().replace("+00:00", "Z")
    if "T" not in text:
        return f"{text}T00:00:00Z"
    if text.endswith("Z"):
        return text
    tail = text[10:]
    if "+" in tail or "-" in tail:
        return text
    return f"{text}Z"


def _parse_time_bound(value: str, label: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise GoogleCalendarError(f"{label} is required for calendar reads.")
    try:
        if "T" not in text:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise GoogleCalendarError(f"{label} must be an ISO date or datetime.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validated_window(start: str, end: str) -> tuple[str, str, datetime, datetime] | None:
    start_dt = _parse_time_bound(start, "start")
    end_dt = _parse_time_bound(end, "end")
    if end_dt <= start_dt:
        raise GoogleCalendarError("end must be after start for calendar reads.")
    if end_dt - start_dt > timedelta(days=MAX_CONTEXT_WINDOW_DAYS):
        raise GoogleCalendarError(f"Calendar read window must be {MAX_CONTEXT_WINDOW_DAYS} days or less.")
    return _rfc3339(start, start_dt), _rfc3339(end, end_dt), start_dt, end_dt


def _calendar_ids(calendar_ids: list[str] | None) -> list[str]:
    configured_default = os.environ.get("GOOGLE_CALENDAR_DEFAULT_CALENDAR_ID", DEFAULT_CALENDAR_ID).strip()
    raw_ids = calendar_ids or [configured_default or DEFAULT_CALENDAR_ID]
    cleaned: list[str] = []
    seen: set[str] = set()
    for calendar_id in raw_ids:
        value = str(calendar_id or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned[:MAX_CALENDARS] or [DEFAULT_CALENDAR_ID]


def _safe_calendar_error(calendar_id: str, error: GoogleCalendarError) -> dict[str, Any]:
    return {
        "calendar_id": calendar_id,
        "status_code": error.status_code,
        "reason": _safe_detail(str(error)),
    }


def _is_rate_limit_error(error: GoogleCalendarError) -> bool:
    if error.status_code not in {403, 429}:
        return False
    message = str(error).lower()
    return any(marker in message for marker in ("quota", "rate limit", "ratelimit", "userratelimitexceeded"))


def _request_events_with_rate_limit_retry(path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
    attempts = max(0, GOOGLE_CALENDAR_RATE_LIMIT_MAX_RETRIES)
    for attempt in range(attempts + 1):
        try:
            return _request_json(path, params, access_token)
        except GoogleCalendarError as error:
            if attempt >= attempts or not _is_rate_limit_error(error):
                raise
            time.sleep(max(0, GOOGLE_CALENDAR_RATE_LIMIT_RETRY_SECONDS))
    raise AssertionError("unreachable")


def _request_freebusy_with_rate_limit_retry(payload: dict[str, Any], access_token: str) -> dict[str, Any]:
    attempts = max(0, GOOGLE_CALENDAR_RATE_LIMIT_MAX_RETRIES)
    for attempt in range(attempts + 1):
        try:
            return _request_post_json("/freeBusy", payload, access_token)
        except GoogleCalendarError as error:
            if attempt >= attempts or not _is_rate_limit_error(error):
                raise
            time.sleep(max(0, GOOGLE_CALENDAR_RATE_LIMIT_RETRY_SECONDS))
    raise AssertionError("unreachable")


def _safe_event(event: dict[str, Any], calendar_id: str) -> dict[str, Any]:
    attendees = event.get("attendees") if isinstance(event.get("attendees"), list) else []
    start = event.get("start") if isinstance(event.get("start"), dict) else {}
    end = event.get("end") if isinstance(event.get("end"), dict) else {}
    return {
        "id": event.get("id") or "",
        "calendar_id": calendar_id,
        "summary": event.get("summary") or "(no title)",
        "start": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
        "location": event.get("location") or "",
        "status": event.get("status") or "",
        "attendee_count": len(attendees),
        "has_conference_link": bool(event.get("hangoutLink") or event.get("conferenceData")),
    }


def _sort_key(event: dict[str, Any]) -> str:
    return str(event.get("start") or "")


def _public_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": event.get("summary") or event.get("title") or "(no title)",
        "start": event.get("start") or "",
        "end": event.get("end") or "",
        "status": event.get("status") or "",
        "attendee_count": int(event.get("attendee_count") or 0),
    }


def _customer_query_is_weak(customer_query: str) -> bool:
    normalized = re.sub(r"[^A-Za-z0-9& ]+", " ", str(customer_query or "")).strip().lower()
    compact = normalized.replace(" ", "")
    if len(compact) < 4:
        return True
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return True
    if len(tokens) == 1 and (len(tokens[0]) <= 3 or tokens[0] in WEAK_CUSTOMER_QUERY_TOKENS):
        return True
    return all(token in WEAK_CUSTOMER_QUERY_TOKENS for token in tokens)


def _validated_attendee_emails(attendee_emails: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_email in attendee_emails or []:
        email = str(raw_email or "").strip().lower()
        if not email or email in seen:
            continue
        if "@" not in email or "." not in email.split("@", 1)[-1]:
            raise GoogleCalendarError("attendee_emails must contain explicit email addresses.")
        seen.add(email)
        cleaned.append(email)
    return cleaned[:MAX_CALENDARS]


def _slot_timezone() -> ZoneInfo:
    return ZoneInfo(DEFAULT_SLOT_TIMEZONE)


def _busy_intervals(payload: dict[str, Any]) -> tuple[list[tuple[datetime, datetime]], int]:
    busy: list[tuple[datetime, datetime]] = []
    blocked_count = 0
    calendars = payload.get("calendars") if isinstance(payload.get("calendars"), dict) else {}
    for calendar_payload in calendars.values():
        if not isinstance(calendar_payload, dict):
            continue
        if calendar_payload.get("errors"):
            blocked_count += 1
            continue
        for interval in calendar_payload.get("busy") or []:
            if not isinstance(interval, dict):
                continue
            try:
                busy.append((_parse_time_bound(str(interval.get("start") or ""), "busy.start"), _parse_time_bound(str(interval.get("end") or ""), "busy.end")))
            except GoogleCalendarError:
                continue
    return busy, blocked_count


def _overlaps_busy(slot_start: datetime, slot_end: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
    return any(slot_start < busy_end and slot_end > busy_start for busy_start, busy_end in busy)


def _suggest_slots(
    start_dt: datetime,
    end_dt: datetime,
    duration_minutes: int,
    busy: list[tuple[datetime, datetime]],
    attendee_count: int,
) -> list[dict[str, Any]]:
    tz = _slot_timezone()
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)
    cursor_day = start_dt.astimezone(tz).date()
    final_day = end_dt.astimezone(tz).date()
    suggestions: list[dict[str, Any]] = []

    while cursor_day <= final_day and len(suggestions) < MAX_SUGGESTED_SLOTS:
        work_start = datetime(cursor_day.year, cursor_day.month, cursor_day.day, 9, 0, tzinfo=tz)
        work_end = datetime(cursor_day.year, cursor_day.month, cursor_day.day, 18, 0, tzinfo=tz)
        slot_start = max(work_start, start_dt.astimezone(tz))
        day_end = min(work_end, end_dt.astimezone(tz))
        minute_offset = slot_start.minute % SLOT_STEP_MINUTES
        if minute_offset:
            slot_start += timedelta(minutes=SLOT_STEP_MINUTES - minute_offset)
        slot_start = slot_start.replace(second=0, microsecond=0)

        while slot_start + duration <= day_end and len(suggestions) < MAX_SUGGESTED_SLOTS:
            slot_end = slot_start + duration
            if not _overlaps_busy(slot_start.astimezone(timezone.utc), slot_end.astimezone(timezone.utc), busy):
                suggestions.append(
                    {
                        "title": "Suggested meeting slot",
                        "start": slot_start.isoformat(),
                        "end": slot_end.isoformat(),
                        "status": "available",
                        "attendee_count": attendee_count,
                    }
                )
            slot_start += step
        cursor_day += timedelta(days=1)

    return suggestions


@mcp.tool()
def read_customer_calendar_context(
    slack_user_email: str,
    intent: str,
    customer_query: str,
    start: str,
    end: str,
    attendee_emails: list[str] | None = None,
    duration_minutes: int | None = None,
) -> dict[str, Any]:
    """Read gated customer scheduling context from team@staffany.com Google Calendar."""

    normalized_intent = str(intent or "").strip()
    base_scope = _scope(
        slack_user_email,
        {
            "intent": normalized_intent,
            "customer_query": str(customer_query or "").strip(),
            "calendar_access_mode": "team_oauth_shared_calendar",
            "safety": "No event mutations, attendee exports, descriptions, raw guest lists, or conference links.",
        },
    )

    if _account_email() != DEFAULT_ACCOUNT_EMAIL:
        return _blocked("Google Calendar connector is restricted to team@staffany.com.", base_scope)
    if normalized_intent not in VALID_CONTEXT_INTENTS:
        return _blocked("intent must be find_existing_followup or suggest_meeting_slots.", base_scope)
    if _customer_query_is_weak(customer_query):
        return _blocked("customer_query is required and must identify a specific customer or thread context.", base_scope)

    try:
        time_min, time_max, start_dt, end_dt = _validated_window(start, end)
    except GoogleCalendarError as error:
        return _blocked(str(error), base_scope)
    base_scope.update(
        {
            "time_min": time_min,
            "time_max": time_max,
        }
    )

    if normalized_intent == "find_existing_followup":
        result = list_google_calendar_events(
            slack_user_email=slack_user_email,
            query=customer_query,
            start=start,
            end=end,
            max_results=DEFAULT_CONTEXT_MAX_EVENTS,
            account_email=DEFAULT_ACCOUNT_EMAIL,
        )
        result_scope = result.get("scope") if isinstance(result.get("scope"), dict) else {}
        blocked = result_scope.get("blocked_calendar_ids") or []
        if isinstance(result.get("answer"), dict):
            return _blocked(str(result["answer"].get("message") or result.get("caveat") or "Calendar lookup blocked."), base_scope)
        events = [_public_event(event) for event in result.get("answer", []) if isinstance(event, dict)]
        base_scope.update(
            {
                "calendars_checked_count": len(result_scope.get("calendar_ids") or []),
                "blocked_calendar_count": len(blocked),
                "event_count": len(events),
            }
        )
        return {
            "answer": events,
            "source": "Google Calendar",
            "scope": base_scope,
            "confidence": "blocked" if blocked else "needs-check",
            "caveat": (
                "One or more selected calendars were not accessible via team@staffany.com; do not conclude no meeting or follow-up for those calendars."
                if blocked
                else "Calendar is scheduling context only. Jira PCO remains task truth and Customer 360 remains customer-context truth."
            ),
        }

    try:
        attendees = _validated_attendee_emails(attendee_emails)
        duration = int(duration_minutes or 0)
    except (GoogleCalendarError, TypeError, ValueError) as error:
        return _blocked(str(error), base_scope)
    if not attendees:
        return _blocked("attendee_emails are required before suggesting meeting slots.", base_scope)
    if duration < 15 or duration > 240:
        return _blocked("duration_minutes must be between 15 and 240.", base_scope)

    base_scope.update({"attendee_count": len(attendees), "duration_minutes": duration})
    try:
        access_token = _access_token()
        payload = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": email} for email in attendees],
        }
        try:
            freebusy = _request_freebusy_with_rate_limit_retry(payload, access_token)
        except GoogleCalendarError as error:
            if error.status_code != 401:
                return _blocked(str(error), base_scope)
            token_payload = _google_load_json(_token_file(), "Google Calendar", GoogleCalendarError)
            access_token = _refresh_access_token(token_payload)
            freebusy = _request_freebusy_with_rate_limit_retry(payload, access_token)
    except GoogleCalendarError as error:
        return _blocked(str(error), base_scope)

    busy, blocked_count = _busy_intervals(freebusy)
    base_scope["blocked_attendee_calendar_count"] = blocked_count
    if blocked_count:
        return _blocked("One or more attendee calendars were inaccessible to team@staffany.com.", base_scope)
    suggestions = _suggest_slots(start_dt, end_dt, duration, busy, len(attendees))
    base_scope["suggested_slot_count"] = len(suggestions)
    return {
        "answer": suggestions,
        "source": "Google Calendar",
        "scope": base_scope,
        "confidence": "needs-check",
        "caveat": "Calendar is scheduling context only. Confirm with attendees before sending invites.",
    }


def list_google_calendar_events(
    slack_user_email: str,
    query: str = "",
    start: str = "",
    end: str = "",
    calendar_ids: list[str] | None = None,
    max_results: int = 20,
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
) -> dict[str, Any]:
    """List bounded read-only Google Calendar events from team@staffany.com."""

    configured_account = _account_email()
    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    selected_calendar_ids = _calendar_ids(calendar_ids)
    query_text = str(query or "").strip()
    now = datetime.now(timezone.utc)
    time_min = _rfc3339(start, now)
    time_max = _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    capped_results = max(1, min(int(max_results or 20), MAX_EVENTS_PER_CALENDAR))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "calendar_access_mode": "team_oauth_shared_calendar",
            "calendar_ids": selected_calendar_ids,
            "time_min": time_min,
            "time_max": time_max,
            "query": query_text,
            "max_events_per_calendar": capped_results,
            "safety": "No event mutations, attendee exports, descriptions, raw guest lists, or conference links.",
        },
    )

    if configured_account != DEFAULT_ACCOUNT_EMAIL or requested_account != DEFAULT_ACCOUNT_EMAIL:
        return _blocked("Google Calendar connector is restricted to team@staffany.com.", scope)

    try:
        access_token = _access_token()
        events: list[dict[str, Any]] = []
        blocked_calendar_ids: list[dict[str, Any]] = []
        for calendar_id in selected_calendar_ids:
            path = f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events"
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": capped_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            if query_text:
                params["q"] = query_text
            try:
                payload = _request_events_with_rate_limit_retry(path, params, access_token)
            except GoogleCalendarError as error:
                if error.status_code != 401:
                    blocked_calendar_ids.append(_safe_calendar_error(calendar_id, error))
                    continue
                token_payload = _google_load_json(_token_file(), "Google Calendar", GoogleCalendarError)
                access_token = _refresh_access_token(token_payload)
                try:
                    payload = _request_events_with_rate_limit_retry(path, params, access_token)
                except GoogleCalendarError as retry_error:
                    blocked_calendar_ids.append(_safe_calendar_error(calendar_id, retry_error))
                    continue
            events.extend(_safe_event(event, calendar_id) for event in payload.get("items", []))
    except GoogleCalendarError as error:
        return _blocked(str(error), scope)

    events.sort(key=_sort_key)
    scope["blocked_calendar_ids"] = blocked_calendar_ids
    return {
        "answer": events,
        "source": "Google Calendar",
        "scope": scope,
        "confidence": "blocked" if blocked_calendar_ids else "needs-check",
        "caveat": (
            "One or more selected calendars were not accessible via team@staffany.com; do not conclude no meeting or follow-up for those calendars."
            if blocked_calendar_ids
            else "Calendar is scheduling context only. Jira PCO remains task truth and Customer 360 remains customer-context truth."
        ),
    }


if __name__ == "__main__":
    mcp.run("stdio")
