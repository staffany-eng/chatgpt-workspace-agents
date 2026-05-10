#!/usr/bin/env python3
"""Read-only Google Calendar MCP adapter for NurtureAny Sales Bot.

This server exposes only bounded event listing for the StaffAny
team@staffany.com calendar context. It never creates, updates, deletes, invites,
RSVPs, exports attendees, or returns raw guest lists.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


GOOGLE_CALENDAR_API_BASE_URL = "https://www.googleapis.com/calendar/v3"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
CALENDAR_READONLY_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_BROAD_SCOPE = "https://www.googleapis.com/auth/calendar"
DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
DEFAULT_CALENDAR_ID = "primary"
GOOGLE_CALENDAR_TIMEOUT_SECONDS = 15
MAX_CALENDARS = 5
MAX_EVENTS_PER_CALENDAR = 50
DEFAULT_LOOKAHEAD_DAYS = 30


mcp = FastMCP(
    "google_calendar_nurtureany",
    instructions=(
        "Read-only Google Calendar event context for NurtureAny. Use only the "
        "team@staffany.com account, list bounded events, and never mutate calendar data."
    ),
)


class GoogleCalendarError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _account_email() -> str:
    return os.environ.get("GOOGLE_CALENDAR_ACCOUNT_EMAIL", DEFAULT_ACCOUNT_EMAIL).strip().lower() or DEFAULT_ACCOUNT_EMAIL


def _token_file() -> Path:
    raw = os.environ.get("GOOGLE_CALENDAR_TOKEN_FILE", "").strip()
    if raw and not _is_unresolved_env_placeholder(raw):
        return Path(raw).expanduser()
    return Path.home() / ".hermes" / "profiles" / "nurtureanysalesbot" / "google-calendar-token.json"


def _client_secret_file() -> Path:
    raw = os.environ.get("GOOGLE_CALENDAR_CLIENT_SECRET_FILE", "").strip()
    if raw and not _is_unresolved_env_placeholder(raw):
        return Path(raw).expanduser()
    return Path.home() / ".hermes" / "profiles" / "nurtureanysalesbot" / "google-calendar-client-secret.json"


def _is_unresolved_env_placeholder(value: str) -> bool:
    return value.startswith("${") and value.endswith("}")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise GoogleCalendarError(f"Missing Google Calendar OAuth file: {path}") from error
    except json.JSONDecodeError as error:
        raise GoogleCalendarError(f"Invalid Google Calendar OAuth JSON file: {path}") from error


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


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
        "answer": message,
        "source": "Google Calendar",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def _token_scopes(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("scopes") or payload.get("scope") or []
    if isinstance(raw, str):
        return {item.strip() for item in raw.split() if item.strip()}
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    return set()


def _validate_scope(payload: dict[str, Any]) -> None:
    scopes = _token_scopes(payload)
    if scopes and CALENDAR_READONLY_SCOPE not in scopes and CALENDAR_BROAD_SCOPE not in scopes:
        raise GoogleCalendarError("Google Calendar OAuth token is missing a calendar read scope.")


def _client_credentials(payload: dict[str, Any]) -> tuple[str, str]:
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    secret = _load_json(_client_secret_file())
    installed = secret.get("installed") or secret.get("web") or {}
    client_id = str(installed.get("client_id") or "").strip()
    client_secret = str(installed.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise GoogleCalendarError("Google Calendar OAuth client secret file is missing client_id/client_secret.")
    return client_id, client_secret


def _refresh_access_token(payload: dict[str, Any], token_path: Path) -> str:
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise GoogleCalendarError("Google Calendar OAuth token has no refresh_token. Re-run OAuth setup.")

    client_id, client_secret = _client_credentials(payload)
    data = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        str(payload.get("token_uri") or GOOGLE_OAUTH_TOKEN_URL),
        data=data,
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "user-agent": GOOGLE_CALENDAR_USER_AGENT,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_CALENDAR_TIMEOUT_SECONDS) as response:
            refreshed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleCalendarError(f"Google OAuth refresh failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleCalendarError(f"Google OAuth refresh timed out or failed: {reason}") from error

    access_token = str(refreshed.get("access_token") or "").strip()
    if not access_token:
        raise GoogleCalendarError("Google OAuth refresh did not return an access token.")

    merged = dict(payload)
    merged.update(refreshed)
    merged["refresh_token"] = refresh_token
    if not merged.get("type"):
        merged["type"] = "authorized_user"
    _write_json(token_path, merged)
    return access_token


def _access_token() -> str:
    token_path = _token_file()
    payload = _load_json(token_path)
    _validate_scope(payload)
    token = str(payload.get("token") or payload.get("access_token") or "").strip()
    if token:
        return token
    return _refresh_access_token(payload, token_path)


def _safe_detail(detail: str) -> str:
    return detail.replace("\n", " ")[:300]


def _request_json(path: str, params: dict[str, Any], access_token: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = f"{GOOGLE_CALENDAR_API_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "user-agent": GOOGLE_CALENDAR_USER_AGENT,
        },
        method="GET",
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
        "htmlLink": event.get("htmlLink") or "",
        "attendee_count": len(attendees),
        "has_conference_link": bool(event.get("hangoutLink") or event.get("conferenceData")),
    }


def _sort_key(event: dict[str, Any]) -> str:
    return str(event.get("start") or "")


@mcp.tool()
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
    now = datetime.now(timezone.utc)
    time_min = _rfc3339(start, now)
    time_max = _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    capped_results = max(1, min(int(max_results or 20), MAX_EVENTS_PER_CALENDAR))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "calendar_ids": selected_calendar_ids,
            "time_min": time_min,
            "time_max": time_max,
            "query": query,
            "max_events_per_calendar": capped_results,
            "safety": "No event mutations, attendee exports, descriptions, or raw guest lists.",
        },
    )

    if requested_account != configured_account:
        return _blocked("Google Calendar connector is restricted to team@staffany.com.", scope)

    try:
        access_token = _access_token()
        events: list[dict[str, Any]] = []
        for calendar_id in selected_calendar_ids:
            path = f"/calendars/{urllib.parse.quote(calendar_id, safe='')}/events"
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": capped_results,
                "singleEvents": "true",
                "orderBy": "startTime",
                "q": query.strip(),
            }
            try:
                payload = _request_json(path, params, access_token)
            except GoogleCalendarError as error:
                if error.status_code != 401:
                    raise
                access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                payload = _request_json(path, params, access_token)
            events.extend(_safe_event(event, calendar_id) for event in payload.get("items", []))
    except GoogleCalendarError as error:
        return _blocked(str(error), scope)

    events.sort(key=_sort_key)
    return {
        "answer": events,
        "source": "Google Calendar",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Calendar events are scheduling context only. Match back to scoped HubSpot accounts before acting.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
