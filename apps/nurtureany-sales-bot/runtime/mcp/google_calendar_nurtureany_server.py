#!/usr/bin/env python3
"""Read-only Google Calendar MCP adapter for NurtureAny Sales Bot.

This server exposes only bounded event listing for the StaffAny
team@staffany.com calendar context. It never creates, updates, deletes, invites,
RSVPs, exports attendees, or returns raw guest lists.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
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
STAFFANY_EMAIL_DOMAIN = "staffany.com"


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


def _normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _email_domain(email: str) -> str:
    normalized = _normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[1].strip()


def _hash_email(email: str) -> str:
    normalized = _normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def _normalized_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _seed_calendar_ids(calendar_audit_seed: dict[str, Any]) -> list[str]:
    ids = calendar_audit_seed.get("calendar_ids")
    if not isinstance(ids, list):
        ids = []
    return _calendar_ids(ids)


def _seed_contacts_by_hash(calendar_audit_seed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = calendar_audit_seed.get("contact_match_records")
    if not isinstance(records, list):
        return {}
    contacts: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        email_hash = str(record.get("email_hash") or "").strip()
        if email_hash:
            contacts[email_hash] = record
    return contacts


def _safe_matched_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "contact_id": contact.get("contact_id") or "",
        "display_name": contact.get("display_name") or "",
        "persona": contact.get("persona") or "",
        "buying_role": contact.get("buying_role") or "",
        "is_verified_decision_maker": bool(contact.get("is_verified_decision_maker")),
        "is_role_inferred_decision_maker": bool(contact.get("is_role_inferred_decision_maker")),
        "decision_maker_confidence": contact.get("decision_maker_confidence") or "",
    }


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


def _safe_calendar_error(calendar_id: str, error: GoogleCalendarError) -> dict[str, Any]:
    return {
        "calendar_id": calendar_id,
        "status_code": error.status_code,
        "reason": _safe_detail(str(error)),
    }


def _sort_key(event: dict[str, Any]) -> str:
    return str(event.get("start") or "")


def _datetime_value(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "T" not in text:
        text = f"{text}T00:00:00Z"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _event_times(event: dict[str, Any]) -> tuple[str, str]:
    start = event.get("start") if isinstance(event.get("start"), dict) else {}
    end = event.get("end") if isinstance(event.get("end"), dict) else {}
    return start.get("dateTime") or start.get("date") or "", end.get("dateTime") or end.get("date") or ""


def _title_match_strength(summary: str, company_name: str) -> str:
    normalized_summary = _normalized_words(summary)
    normalized_company = _normalized_words(company_name)
    if normalized_company and normalized_company in normalized_summary:
        return "exact_title_match"
    compact_company = _compact_text(company_name)
    compact_summary = _compact_text(summary)
    if compact_company and compact_company in compact_summary:
        return "fuzzy_title_match"
    return ""


def _audit_event(event: dict[str, Any], calendar_id: str, calendar_audit_seed: dict[str, Any]) -> dict[str, Any]:
    company_name = str(calendar_audit_seed.get("company_name") or "")
    company_domain = str(calendar_audit_seed.get("company_domain") or "").strip().lower()
    company_id = str(calendar_audit_seed.get("company_id") or "")
    contact_by_hash = _seed_contacts_by_hash(calendar_audit_seed)
    attendees = event.get("attendees") if isinstance(event.get("attendees"), list) else []
    summary = event.get("summary") or "(no title)"
    start, end = _event_times(event)

    matched_contacts: list[dict[str, Any]] = []
    seen_contact_ids: set[str] = set()
    staffany_attendee_count = 0
    company_domain_attendee_count = 0
    unknown_external_attendee_count = 0

    for attendee in attendees:
        if not isinstance(attendee, dict):
            continue
        email = _normalize_email(attendee.get("email") or "")
        if not email:
            continue
        domain = _email_domain(email)
        if domain == STAFFANY_EMAIL_DOMAIN:
            staffany_attendee_count += 1
            continue
        matched_contact = contact_by_hash.get(_hash_email(email))
        if matched_contact:
            contact_id = str(matched_contact.get("contact_id") or "")
            if contact_id and contact_id not in seen_contact_ids:
                seen_contact_ids.add(contact_id)
                matched_contacts.append(_safe_matched_contact(matched_contact))
            continue
        if company_domain and domain == company_domain:
            company_domain_attendee_count += 1
        else:
            unknown_external_attendee_count += 1

    account_match_strength: list[str] = []
    if matched_contacts:
        account_match_strength.append("contact_email_match")
    if company_domain_attendee_count:
        account_match_strength.append("company_domain_attendee_match")
    title_strength = _title_match_strength(str(summary), company_name)
    if title_strength:
        account_match_strength.append(title_strength)

    verified_decision_maker_present = any(contact.get("is_verified_decision_maker") for contact in matched_contacts)
    role_inferred_buyer_present = any(contact.get("is_role_inferred_decision_maker") for contact in matched_contacts)
    staffany_only = bool(attendees) and len(attendees) == staffany_attendee_count

    quality_status = "needs-check"
    quality_reasons: list[str] = []
    if staffany_only:
        quality_status = "gap"
        quality_reasons.append("staffany_only_event")
    elif verified_decision_maker_present and unknown_external_attendee_count == 0:
        quality_status = "good"
        quality_reasons.append("verified_decision_maker_attending")
    elif role_inferred_buyer_present:
        quality_status = "needs-check"
        quality_reasons.append("role_inferred_buyer_attending_but_buying_role_not_verified")
    elif matched_contacts:
        quality_status = "gap"
        quality_reasons.append("hubspot_contacts_attending_but_no_buying_relevant_contact")
    elif company_domain_attendee_count or unknown_external_attendee_count:
        quality_status = "needs-check"
        quality_reasons.append("external_attendees_not_linked_to_hubspot_contacts")
    else:
        quality_status = "gap"
        quality_reasons.append("no_external_or_hubspot_linked_attendees")

    if unknown_external_attendee_count and quality_status == "good":
        quality_status = "needs-check"
        quality_reasons.append("unknown_external_attendees_present")

    followup_required = False
    end_dt = _datetime_value(end)
    if end_dt and end_dt < datetime.now(timezone.utc):
        followup_required = True

    return {
        "event_id": event.get("id") or "",
        "calendar_id": calendar_id,
        "summary": summary,
        "start": start,
        "end": end,
        "status": event.get("status") or "",
        "attendee_count": len(attendees),
        "has_conference_link": bool(event.get("hangoutLink") or event.get("conferenceData")),
        "account_match_strength": account_match_strength,
        "quality_status": quality_status,
        "quality_reasons": quality_reasons,
        "right_people_audit": {
            "verified_decision_maker_present": verified_decision_maker_present,
            "role_inferred_buyer_present": role_inferred_buyer_present,
            "matched_hubspot_contact_count": len(matched_contacts),
            "company_domain_attendee_count": company_domain_attendee_count,
            "unknown_external_attendee_count": unknown_external_attendee_count,
            "staffany_attendee_count": staffany_attendee_count,
            "staffany_only": staffany_only,
        },
        "matched_hubspot_contacts": matched_contacts,
        "missing_sales_standard_evidence": list(calendar_audit_seed.get("missing_clean_lead_fields") or []),
        "ic_bant_readiness": calendar_audit_seed.get("ic_bant_readiness") or {},
        "hubspot_followup_check": {
            "required": followup_required,
            "tool": "check_account_followup_status",
            "company_ids": [company_id] if company_id else [],
            "since_at": end if followup_required else "",
            "reason": "Meeting is in the past; check HubSpot WhatsApp, notes, tasks, and meeting logs after the event end time."
            if followup_required
            else "",
        },
    }


def _aggregate_audit_status(events: list[dict[str, Any]], blocked_calendar_ids: list[dict[str, Any]]) -> str:
    if blocked_calendar_ids:
        return "blocked"
    if not events:
        return "no-calendar-follow-up"
    statuses = {str(event.get("quality_status") or "") for event in events}
    if "good" in statuses:
        return "good"
    if "needs-check" in statuses:
        return "needs-check"
    return "gap"


def _audit_confidence(status: str, blocked_calendar_ids: list[dict[str, Any]]) -> str:
    if blocked_calendar_ids or status == "blocked":
        return "blocked"
    if status in {"good", "no-calendar-follow-up"}:
        return "verified"
    return "needs-check"


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
            "safety": "No event mutations, attendee exports, descriptions, or raw guest lists.",
        },
    )

    if requested_account != configured_account:
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
                payload = _request_json(path, params, access_token)
            except GoogleCalendarError as error:
                if error.status_code != 401:
                    blocked_calendar_ids.append(_safe_calendar_error(calendar_id, error))
                    continue
                access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                try:
                    payload = _request_json(path, params, access_token)
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
        "caveat": "One or more selected calendars were not accessible via team@staffany.com; do not conclude no follow-up for those calendars."
        if blocked_calendar_ids
        else "Calendar events are scheduling context only. Match back to scoped HubSpot accounts before acting.",
    }


@mcp.tool()
def audit_google_calendar_meeting_quality(
    slack_user_email: str,
    calendar_audit_seed: dict[str, Any],
    start: str = "",
    end: str = "",
    query: str = "",
    event_id: str = "",
    max_results: int = 20,
) -> dict[str, Any]:
    """Audit whether a scoped account calendar meeting has the right HubSpot-linked people."""

    if not isinstance(calendar_audit_seed, dict):
        return _blocked("Provide a calendar_audit_seed from get_account_context.", _scope(slack_user_email))

    configured_account = _account_email()
    raw_calendar_ids = calendar_audit_seed.get("calendar_ids")
    if not isinstance(raw_calendar_ids, list) or not raw_calendar_ids:
        return _blocked(
            "calendar_audit_seed has no HubSpot owner calendar_ids; owner calendar coverage is blocked.",
            _scope(
                slack_user_email,
                {
                    "company_id": calendar_audit_seed.get("company_id") or "",
                    "company_name": calendar_audit_seed.get("company_name") or "",
                },
            ),
        )

    selected_calendar_ids = _seed_calendar_ids(calendar_audit_seed)
    query_text = str(query or calendar_audit_seed.get("company_name") or "").strip()
    event_id_text = str(event_id or "").strip()
    now = datetime.now(timezone.utc)
    time_min = _rfc3339(start, now)
    time_max = _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    capped_results = max(1, min(int(max_results or 20), MAX_EVENTS_PER_CALENDAR))
    scope = _scope(
        slack_user_email,
        {
            "requested_account_email": DEFAULT_ACCOUNT_EMAIL,
            "calendar_access_mode": "team_oauth_shared_calendar",
            "calendar_ids": selected_calendar_ids,
            "company_id": calendar_audit_seed.get("company_id") or "",
            "company_name": calendar_audit_seed.get("company_name") or "",
            "company_domain": calendar_audit_seed.get("company_domain") or "",
            "owner_email": calendar_audit_seed.get("owner_email") or "",
            "time_min": time_min,
            "time_max": time_max,
            "query": query_text,
            "event_id": event_id_text,
            "max_events_per_calendar": capped_results,
            "safety": "Reads attendee emails internally only for hash matching; returns no raw attendee emails, guest lists, descriptions, or conference links.",
        },
    )

    if configured_account != DEFAULT_ACCOUNT_EMAIL:
        return _blocked("Google Calendar connector is restricted to team@staffany.com.", scope)

    try:
        access_token = _access_token()
        audit_events: list[dict[str, Any]] = []
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
                payload = _request_json(path, params, access_token)
            except GoogleCalendarError as error:
                if error.status_code != 401:
                    blocked_calendar_ids.append(_safe_calendar_error(calendar_id, error))
                    continue
                access_token = _refresh_access_token(_load_json(_token_file()), _token_file())
                try:
                    payload = _request_json(path, params, access_token)
                except GoogleCalendarError as retry_error:
                    blocked_calendar_ids.append(_safe_calendar_error(calendar_id, retry_error))
                    continue

            for event in payload.get("items", []):
                if event_id_text and str(event.get("id") or "") != event_id_text:
                    continue
                audit_event = _audit_event(event, calendar_id, calendar_audit_seed)
                if event_id_text and "event_id_match" not in audit_event["account_match_strength"]:
                    audit_event["account_match_strength"].append("event_id_match")
                if audit_event["account_match_strength"]:
                    audit_events.append(audit_event)
    except GoogleCalendarError as error:
        return _blocked(str(error), scope)

    audit_events.sort(key=_sort_key)
    status = _aggregate_audit_status(audit_events, blocked_calendar_ids)
    confidence = _audit_confidence(status, blocked_calendar_ids)
    scope["blocked_calendar_ids"] = blocked_calendar_ids
    return {
        "answer": {
            "status": status,
            "account": {
                "company_id": calendar_audit_seed.get("company_id") or "",
                "company_name": calendar_audit_seed.get("company_name") or "",
                "company_domain": calendar_audit_seed.get("company_domain") or "",
                "owner_email": calendar_audit_seed.get("owner_email") or "",
                "owner_name": calendar_audit_seed.get("owner_name") or "",
            },
            "calendar_checked": selected_calendar_ids,
            "events": audit_events,
            "missing_sales_standard_evidence": list(calendar_audit_seed.get("missing_clean_lead_fields") or []),
            "ic_bant_readiness": calendar_audit_seed.get("ic_bant_readiness") or {},
        },
        "source": "Google Calendar attendee hash audit + HubSpot calendar_audit_seed",
        "scope": scope,
        "confidence": confidence,
        "caveat": (
            "One or more selected calendars were not accessible via team@staffany.com; do not conclude no calendar follow-up for those calendars."
            if blocked_calendar_ids
            else "Calendar is scheduling context. HubSpot remains source of truth for contacts, buying roles, and follow-up evidence."
        ),
    }


if __name__ == "__main__":
    mcp.run("stdio")
