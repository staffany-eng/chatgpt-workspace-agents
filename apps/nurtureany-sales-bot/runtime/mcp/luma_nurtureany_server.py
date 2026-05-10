#!/usr/bin/env python3
"""Read-only Luma MCP adapter for NurtureAny Sales Bot.

This server exposes bounded Luma event and guest context only. It never creates
or updates events, sends invites, exports attendee lists, writes Google Sheets,
or mutates HubSpot.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP


LUMA_BASE_URL = "https://public-api.luma.com"
LUMA_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
LUMA_TIMEOUT_SECONDS = 15
MAX_EVENTS = 50
DEFAULT_EVENT_LIMIT = 20
MAX_EVENTS_FOR_CONTEXT = 20
LUMA_PAGE_LIMIT = 50
MAX_GUESTS_PER_EVENT = 250
DEFAULT_LOOKAHEAD_DAYS = 90
RATE_LIMIT_BACKOFF_SECONDS = 0.25
SCOPE_SOURCE = "hubspot_nurtureany"

GUEST_APPROVAL_STATUSES = (
    "approved",
    "session",
    "pending_approval",
    "invited",
    "declined",
    "waitlist",
)


mcp = FastMCP(
    "luma_nurtureany",
    instructions=(
        "Read-only Luma event context for NurtureAny. Use HubSpot scoped company "
        "inputs before guest matching, return bounded RSVP/attendance summaries, "
        "and never export raw attendee lists or mutate Luma/HubSpot."
    ),
)


class LumaError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _token() -> str:
    token = os.environ.get("LUMA_API_KEY", "").strip()
    if not token:
        raise LumaError("Missing LUMA_API_KEY.")
    return token


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "caller_email": (slack_user_email or "").strip().lower(),
        "read_only": True,
        "api_scope": "luma_calendar",
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "Luma",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def _request_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = urllib.parse.urljoin(LUMA_BASE_URL, path)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "x-luma-api-key": _token(),
            "accept": "application/json",
            "user-agent": LUMA_USER_AGENT,
        },
        method="GET",
    )

    last_error: LumaError | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=LUMA_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            message = _error_message(error.code, detail)
            if error.code == 429 and attempt == 0:
                last_error = LumaError(f"Luma API rate limited; retried after backoff: {message}", error.code)
                time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                continue
            if error.code == 429 and last_error:
                raise LumaError(f"Luma API rate limited after backoff: {message}", error.code) from error
            raise LumaError(message, error.code) from error
        except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            raise LumaError(f"Luma API request timed out or failed: {reason}") from error

    if last_error:
        raise last_error
    raise LumaError("Luma API request failed.")


def _error_message(status_code: int, detail: str) -> str:
    try:
        parsed = json.loads(detail)
        error = parsed.get("error") or parsed
        if isinstance(error, dict):
            message = error.get("message") or error.get("error") or detail
        else:
            message = detail
    except json.JSONDecodeError:
        message = detail

    token = os.environ.get("LUMA_API_KEY", "").strip()
    safe = str(message).replace(token, "[REDACTED_LUMA_API_KEY]") if token else str(message)
    return f"Luma API failed: {status_code} {safe[:300]}"


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


def _entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("entries", "items", "events", "guests", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _has_more(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return bool(payload.get("has_more") or payload.get("hasMore") or pagination.get("has_more"))


def _next_cursor(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return str(payload.get("next_cursor") or payload.get("nextCursor") or pagination.get("next_cursor") or "").strip()


def _event_payload(item: dict[str, Any]) -> dict[str, Any]:
    event = item.get("event")
    return event if isinstance(event, dict) else item


def _guest_payload(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("guest", "event_guest", "eventGuest"):
        guest = item.get(key)
        if isinstance(guest, dict):
            merged = dict(guest)
            for outer_key in ("approval_status", "checked_in_at", "registered_at", "created_at"):
                if outer_key in item and outer_key not in merged:
                    merged[outer_key] = item[outer_key]
            return merged
    return item


def _event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or event.get("api_id") or event.get("id") or "").strip()


def _safe_event(item: dict[str, Any]) -> dict[str, Any]:
    event = _event_payload(item)
    return {
        "event_id": _event_id(event),
        "name": event.get("name") or event.get("title") or "",
        "start_at": event.get("start_at") or event.get("startAt") or "",
        "end_at": event.get("end_at") or event.get("endAt") or "",
        "timezone": event.get("timezone") or "",
        "url": event.get("url") or event.get("event_url") or event.get("eventUrl") or "",
    }


def _event_matches_query(event: dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(str(event.get(key) or "") for key in ("name", "url", "event_id")).lower()
    return needle in haystack


def _list_events_raw(query: str, start: str, end: str, max_events: int) -> tuple[list[dict[str, Any]], bool, bool]:
    now = datetime.now(timezone.utc)
    after = _rfc3339(start, now)
    before = _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    limit = max(1, min(int(max_events or DEFAULT_EVENT_LIMIT), MAX_EVENTS))
    events: list[dict[str, Any]] = []
    cursor = ""
    has_more = False

    while len(events) < limit:
        page_limit = min(LUMA_PAGE_LIMIT, limit - len(events))
        payload = _request_json(
            "/v1/calendar/list-events",
            {
                "after": after,
                "before": before,
                "pagination_cursor": cursor,
                "pagination_limit": page_limit,
                "sort_column": "start_at",
                "sort_direction": "asc",
                "status": "approved",
            },
        )
        page_events = [_safe_event(item) for item in _entries(payload)]
        events.extend(event for event in page_events if _event_matches_query(event, query))
        has_more = _has_more(payload)
        cursor = _next_cursor(payload)
        if not has_more or not cursor:
            break

    truncated = has_more and len(events) >= limit
    return events[:limit], has_more, truncated


def _single_event(event_id: str) -> dict[str, Any]:
    payload = _request_json("/v1/event/get", {"event_id": event_id})
    event = _safe_event(payload)
    if not event["event_id"]:
        event["event_id"] = event_id
    return event


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _email_domain(email: str) -> str:
    normalized = _normalize_email(email)
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[1]


def _hash_email(email: str) -> str:
    normalized = _normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def _clean_domain(domain: str) -> str:
    text = str(domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.split("/")[0]


def _is_scoped_hubspot_company(company: dict[str, Any]) -> bool:
    company_id = str(company.get("company_id") or company.get("id") or "").strip()
    if not company_id:
        return False
    return company.get("hubspot_scoped") is True or str(company.get("scope_source") or "") == SCOPE_SOURCE


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    unscoped = [
        str(index + 1)
        for index, company in enumerate(companies)
        if not isinstance(company, dict) or not _is_scoped_hubspot_company(company)
    ]
    if not unscoped:
        return ""
    return (
        "Luma guest matching requires scoped HubSpot company inputs from NurtureAny "
        f"with company_id and scope_source={SCOPE_SOURCE}; unscoped input positions: {', '.join(unscoped)}."
    )


def _company_names(company: dict[str, Any]) -> list[str]:
    names = [
        str(company.get("name") or company.get("company_name") or "").strip(),
        str(company.get("display_name") or "").strip(),
    ]
    return [name for name in names if name]


def _company_domains(company: dict[str, Any]) -> set[str]:
    raw: list[Any] = [
        company.get("domain"),
        company.get("company_domain"),
        company.get("website"),
    ]
    if isinstance(company.get("domains"), list):
        raw.extend(company["domains"])
    domains = {_clean_domain(str(value)) for value in raw if str(value or "").strip()}
    return {domain for domain in domains if domain}


def _contact_emails(company: dict[str, Any]) -> set[str]:
    emails: set[str] = set()
    raw = company.get("contact_emails")
    if isinstance(raw, list):
        emails.update(_normalize_email(str(email)) for email in raw if str(email or "").strip())
    contacts = company.get("contacts")
    if isinstance(contacts, list):
        for contact in contacts:
            if isinstance(contact, dict):
                email = _normalize_email(str(contact.get("email") or ""))
                if email:
                    emails.add(email)
    return emails


def _company_index(scoped_companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = []
    for company in scoped_companies:
        index.append(
            {
                "company_id": str(company.get("company_id") or company.get("id") or "").strip(),
                "name": _company_names(company),
                "domains": _company_domains(company),
                "contact_emails": _contact_emails(company),
            }
        )
    return index


def _approval_status(guest: dict[str, Any]) -> str:
    status = str(
        guest.get("approval_status")
        or guest.get("approvalStatus")
        or guest.get("status")
        or guest.get("guest_approval_status")
        or ""
    ).strip()
    return status or "unknown"


def _guest_email(guest: dict[str, Any]) -> str:
    return _normalize_email(str(guest.get("email") or guest.get("guest_email") or guest.get("email_address") or ""))


def _guest_name(guest: dict[str, Any]) -> str:
    name = str(guest.get("name") or guest.get("full_name") or guest.get("fullName") or "").strip()
    if name:
        return name
    first = str(guest.get("first_name") or guest.get("firstName") or "").strip()
    last = str(guest.get("last_name") or guest.get("lastName") or "").strip()
    return " ".join(part for part in (first, last) if part).strip()


def _checked_in_at(guest: dict[str, Any]) -> str:
    return str(guest.get("checked_in_at") or guest.get("checkedInAt") or "").strip()


def _registration_texts(value: Any) -> list[str]:
    texts: list[str] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            texts.append(stripped)
    elif isinstance(value, dict):
        for item in value.values():
            texts.extend(_registration_texts(item))
    elif isinstance(value, list):
        for item in value:
            texts.extend(_registration_texts(item))
    return texts


def _guest_text(guest: dict[str, Any]) -> str:
    fields = [
        _guest_name(guest),
        str(guest.get("company") or ""),
        str(guest.get("company_name") or guest.get("companyName") or ""),
        str(guest.get("organization") or guest.get("organisation") or ""),
    ]
    fields.extend(_registration_texts(guest.get("registration_answers")))
    fields.extend(_registration_texts(guest.get("registrationAnswers")))
    return " ".join(field for field in fields if field).lower()


def _name_match(company_name: str, guest_text: str) -> bool:
    normalized_company = re.sub(r"[^a-z0-9]+", " ", company_name.lower()).strip()
    normalized_guest = re.sub(r"[^a-z0-9]+", " ", guest_text.lower()).strip()
    if not normalized_company or len(normalized_company) < 3:
        return False
    return normalized_company in normalized_guest


def _best_match(guest: dict[str, Any], companies: list[dict[str, Any]]) -> dict[str, Any] | None:
    email = _guest_email(guest)
    domain = _email_domain(email)

    if email:
        for company in companies:
            if email in company["contact_emails"]:
                return {
                    "company_id": company["company_id"],
                    "match_reason": "exact_hubspot_contact_email",
                    "confidence": "verified",
                }

    if domain:
        for company in companies:
            if domain in company["domains"]:
                return {
                    "company_id": company["company_id"],
                    "match_reason": "exact_email_domain",
                    "confidence": "verified",
                }

    guest_text = _guest_text(guest)
    for company in companies:
        for name in company["name"]:
            if _name_match(name, guest_text):
                return {
                    "company_id": company["company_id"],
                    "match_reason": "company_name_candidate",
                    "confidence": "needs-check",
                }
    return None


def _guest_match(guest: dict[str, Any], companies: list[dict[str, Any]]) -> dict[str, Any] | None:
    match = _best_match(guest, companies)
    if not match:
        return None
    email = _guest_email(guest)
    checked_in_at = _checked_in_at(guest)
    return {
        "company_id": match["company_id"],
        "attendee_name": _guest_name(guest),
        "email_domain": _email_domain(email),
        "email_hash": _hash_email(email),
        "approval_status": _approval_status(guest),
        "checked_in_at": checked_in_at,
        "attended": bool(checked_in_at),
        "match_reason": match["match_reason"],
        "confidence": match["confidence"],
    }


def _guest_counts(guests: list[dict[str, Any]]) -> dict[str, Any]:
    approval_counts = {status: 0 for status in GUEST_APPROVAL_STATUSES}
    unknown = 0
    checked_in = 0
    for guest in guests:
        status = _approval_status(guest)
        if status in approval_counts:
            approval_counts[status] += 1
        else:
            unknown += 1
        if _checked_in_at(guest):
            checked_in += 1
    if unknown:
        approval_counts["unknown"] = unknown
    return {
        "total_guest_count": len(guests),
        "rsvp_counts": approval_counts,
        "checked_in_count": checked_in,
    }


def _list_guests(event_id: str, max_guests: int) -> tuple[list[dict[str, Any]], bool, bool]:
    limit = max(1, min(int(max_guests or MAX_GUESTS_PER_EVENT), MAX_GUESTS_PER_EVENT))
    guests: list[dict[str, Any]] = []
    cursor = ""
    has_more = False

    while len(guests) < limit:
        page_limit = min(LUMA_PAGE_LIMIT, limit - len(guests))
        payload = _request_json(
            "/v1/event/get-guests",
            {
                "event_id": event_id,
                "pagination_cursor": cursor,
                "pagination_limit": page_limit,
                "sort_column": "registered_at",
                "sort_direction": "asc",
            },
        )
        guests.extend(_guest_payload(item) for item in _entries(payload))
        has_more = _has_more(payload)
        cursor = _next_cursor(payload)
        if not has_more or not cursor:
            break

    truncated = has_more and len(guests) >= limit
    return guests[:limit], has_more, truncated


@mcp.tool()
def list_luma_events(
    slack_user_email: str,
    query: str = "",
    start: str = "",
    end: str = "",
    max_events: int = DEFAULT_EVENT_LIMIT,
) -> dict[str, Any]:
    """List bounded read-only Luma events for account-context planning."""

    limit = max(1, min(int(max_events or DEFAULT_EVENT_LIMIT), MAX_EVENTS))
    now = datetime.now(timezone.utc)
    scope = _scope(
        slack_user_email,
        {
            "query": query,
            "after": _rfc3339(start, now),
            "before": _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)),
            "requested_limit": limit,
            "safety": "Read-only event list; no invites, RSVP changes, attendee exports, or mutations.",
        },
    )

    try:
        events, has_more, truncated = _list_events_raw(query, start, end, limit)
    except LumaError as error:
        return _blocked(str(error), scope)

    return {
        "answer": events,
        "source": "Luma",
        "scope": scope,
        "confidence": "needs-check" if truncated else "verified",
        "has_more": has_more,
        "truncated": truncated,
        "caveat": "Luma events are event context only. Use HubSpot scoped accounts before account actions.",
    }


@mcp.tool()
def get_luma_event_context(
    slack_user_email: str,
    scoped_companies: list[dict[str, Any]],
    event_ids: list[str] | None = None,
    query: str = "",
    start: str = "",
    end: str = "",
    max_guests_per_event: int = MAX_GUESTS_PER_EVENT,
) -> dict[str, Any]:
    """Get bounded Luma RSVP and attendance context for HubSpot-scoped companies."""

    companies = scoped_companies if isinstance(scoped_companies, list) else []
    company_error = _scoped_company_error(companies)
    scope = _scope(
        slack_user_email,
        {
            "scoped_company_count": len(companies),
            "event_ids": [str(event_id).strip() for event_id in (event_ids or []) if str(event_id).strip()],
            "query": query,
            "max_guests_per_event": max(1, min(int(max_guests_per_event or MAX_GUESTS_PER_EVENT), MAX_GUESTS_PER_EVENT)),
            "safety": "HubSpot scoped companies required; no raw attendee export or Luma/HubSpot mutation.",
        },
    )
    if company_error:
        return _blocked(company_error, scope)

    company_index = _company_index(companies)

    try:
        selected_event_ids = scope["event_ids"]
        if selected_event_ids:
            events = [_single_event(event_id) for event_id in selected_event_ids[:MAX_EVENTS_FOR_CONTEXT]]
            events_has_more = len(selected_event_ids) > MAX_EVENTS_FOR_CONTEXT
            events_truncated = events_has_more
        else:
            events, events_has_more, events_truncated = _list_events_raw(query, start, end, MAX_EVENTS_FOR_CONTEXT)

        event_contexts: list[dict[str, Any]] = []
        any_candidate_match = False
        any_truncated = events_truncated
        for event in events:
            event_id = event.get("event_id", "")
            if not event_id:
                continue
            guests, guests_has_more, guests_truncated = _list_guests(event_id, scope["max_guests_per_event"])
            matches = []
            for guest in guests:
                match = _guest_match(guest, company_index)
                if not match:
                    continue
                if match["confidence"] == "needs-check":
                    any_candidate_match = True
                matches.append(match)

            matched_account_ids = sorted({match["company_id"] for match in matches})
            counts = _guest_counts(guests)
            any_truncated = any_truncated or guests_truncated
            event_contexts.append(
                {
                    "event": event,
                    "matched_account_ids": matched_account_ids,
                    "matches": matches,
                    "total_guest_count": counts["total_guest_count"],
                    "rsvp_counts": counts["rsvp_counts"],
                    "checked_in_count": counts["checked_in_count"],
                    "has_more": guests_has_more,
                    "truncated": guests_truncated,
                }
            )
    except LumaError as error:
        return _blocked(str(error), scope)

    return {
        "answer": event_contexts,
        "source": "Luma",
        "scope": scope,
        "confidence": "needs-check" if any_candidate_match or any_truncated else "verified",
        "has_more": events_has_more,
        "truncated": any_truncated,
        "caveat": (
            "Attendance means checked_in_at is present. RSVP statuses are not attendance, "
            "and Luma never overrides HubSpot account scope or ownership."
        ),
    }


if __name__ == "__main__":
    mcp.run("stdio")
