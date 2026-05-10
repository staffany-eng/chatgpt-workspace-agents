#!/usr/bin/env python3
"""Read-only Luma MCP adapter for NurtureAny Sales Bot.

This server exposes bounded Luma event and guest context only. It never creates
or updates events, sends invites, exports attendee lists, writes Google Sheets,
or mutates HubSpot. Guest matching requires scoped HubSpot company inputs from
NurtureAny before account context is shown.
"""

from __future__ import annotations

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

from nurtureany_common.luma_filters import (
    COUNTRY_TAGS,
    EVENT_TYPE_TAGS,
    LOCATION_TAGS,
    canonical_country as _canonical_country,
    canonical_event_type as _canonical_event_type,
    canonical_location as _canonical_location,
    event_tag_filters as _event_tag_filters,
    resolved_event_filters as _resolved_event_filters,
)
from nurtureany_common.responses import blocked_response
from nurtureany_common.scoped_company import scoped_company_error as _shared_scoped_company_error
from nurtureany_common.text import (
    clean_domain as _clean_domain,
    email_domain as _email_domain,
    hash_email as _hash_email,
    normalize_email as _normalize_email,
    unique_text as _unique_text,
)


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
MATCH_KEY_LIMIT = 250
SCOPE_SOURCE = "hubspot_nurtureany"

GUEST_APPROVAL_STATUSES = (
    "approved",
    "session",
    "pending_approval",
    "invited",
    "declined",
    "waitlist",
)
PERSONAL_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.com.sg",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "me.com",
    "live.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}
COMPANY_QUESTION_MARKERS = (
    "company",
    "organisation",
    "organization",
    "business",
    "brand",
    "outlet",
    "restaurant",
    "employer",
    "workplace",
)
TAG_FIELD_NAMES = ("event_tags", "eventTags", "tags", "tag_ids", "tagIds")


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
    return blocked_response(message, "Luma", scope)


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


def _event_metadata_text(event: dict[str, Any]) -> str:
    fields: list[str] = [
        str(event.get("name") or event.get("title") or ""),
        str(event.get("url") or event.get("event_url") or event.get("eventUrl") or ""),
        str(event.get("timezone") or ""),
        str(event.get("platform") or ""),
    ]
    location = event.get("geo_address_json") or event.get("address") or event.get("location")
    if isinstance(location, (dict, list)):
        fields.append(json.dumps(location, sort_keys=True))
    elif location:
        fields.append(str(location))
    return " ".join(field for field in fields if field)


def _event_tag_names(event: dict[str, Any], tags_by_id: dict[str, str]) -> list[str]:
    raw_tags: list[Any] = []
    for field in TAG_FIELD_NAMES:
        value = event.get(field)
        if isinstance(value, list):
            raw_tags.extend(value)
        elif value:
            raw_tags.append(value)

    names: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, str):
            names.append(tags_by_id.get(tag, tag))
        elif isinstance(tag, dict):
            tag_id = str(tag.get("api_id") or tag.get("id") or "").strip()
            names.append(str(tag.get("name") or tag.get("title") or tags_by_id.get(tag_id, "")).strip())
    return _unique_text(names)


def _inferred_tag_names(event: dict[str, Any]) -> list[str]:
    text = _event_metadata_text(event)
    names: list[str] = []
    event_type = _canonical_event_type(text)
    if event_type:
        names.append(event_type)

    lowered = text.lower()
    if "singapore" in lowered or "(sg)" in lowered or "asia/singapore" in lowered:
        names.append("Singapore")
    if "jakarta" in lowered or "(jkt)" in lowered or "asia/jakarta" in lowered:
        names.append("Jakarta")
    if "bali" in lowered:
        names.append("Bali")
    if "kuala lumpur" in lowered or "(kl)" in lowered or "malaysia" in lowered:
        names.append("Kuala Lumpur")
    return _unique_text(names)


def _event_tag_summary(event: dict[str, Any], tags_by_id: dict[str, str]) -> dict[str, Any]:
    luma_tags = _event_tag_names(event, tags_by_id)
    inferred_tags = _inferred_tag_names(event)
    classifiable_tags = _unique_text(luma_tags + inferred_tags)
    location_tags = _unique_text([location for tag in classifiable_tags if (location := _canonical_location(tag))])
    country_tags = _unique_text([country for tag in classifiable_tags if (country := _canonical_country(tag))])
    event_type_tags = _unique_text([event_type for tag in classifiable_tags if (event_type := _canonical_event_type(tag))])
    if luma_tags:
        source = "luma_event_tags"
    elif inferred_tags:
        source = "inferred_from_event_metadata"
    else:
        source = "none"
    return {
        "tags": luma_tags or inferred_tags,
        "location_tags": location_tags,
        "country_tags": country_tags,
        "event_type_tags": event_type_tags,
        "tag_match_source": source,
    }


def _tag_catalog() -> dict[str, str]:
    payload = _request_json("/v1/calendar/event-tags/list")
    tags: dict[str, str] = {}
    for item in _entries(payload):
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        for key in ("api_id", "id"):
            tag_id = str(item.get(key) or "").strip()
            if tag_id:
                tags[tag_id] = name
    return tags


def _safe_tag_catalog() -> dict[str, str]:
    try:
        return _tag_catalog()
    except LumaError:
        return {}


def _event_detail_payload(event_id: str) -> dict[str, Any]:
    try:
        return _event_payload(_request_json("/v1/event/get", {"id": event_id}))
    except LumaError as error:
        if error.status_code == 400:
            return _event_payload(_request_json("/v1/event/get", {"event_id": event_id}))
        raise


def _safe_event(item: dict[str, Any], tags_by_id: dict[str, str] | None = None) -> dict[str, Any]:
    event = _event_payload(item)
    tag_summary = _event_tag_summary(event, tags_by_id or {})
    return {
        "event_id": _event_id(event),
        "name": event.get("name") or event.get("title") or "",
        "start_at": event.get("start_at") or event.get("startAt") or "",
        "end_at": event.get("end_at") or event.get("endAt") or "",
        "timezone": event.get("timezone") or "",
        "url": event.get("url") or event.get("event_url") or event.get("eventUrl") or "",
        "tags": tag_summary["tags"],
        "location_tags": tag_summary["location_tags"],
        "country_tags": tag_summary["country_tags"],
        "event_type_tags": tag_summary["event_type_tags"],
        "tag_match_source": tag_summary["tag_match_source"],
    }


def _event_matches_query(event: dict[str, Any], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack_values: list[str] = [str(event.get(key) or "") for key in ("name", "url", "event_id")]
    for key in ("tags", "location_tags", "country_tags", "event_type_tags"):
        value = event.get(key)
        if isinstance(value, list):
            haystack_values.extend(str(item) for item in value)
    haystack = " ".join(haystack_values).lower()
    return needle in haystack


def _event_matches_filters(
    event: dict[str, Any],
    query: str,
    country: str,
    event_type: str,
    location: str,
    event_tags: Any = None,
) -> bool:
    if not _event_matches_query(event, query):
        return False
    requested_tags = _event_tag_filters(event_tags, country, event_type, location)
    if requested_tags:
        event_tag_set = {str(tag).strip().lower() for tag in event.get("tags", []) if str(tag or "").strip()}
        if not all(tag.lower() in event_tag_set for tag in requested_tags):
            return False
    filters = _resolved_event_filters(country, event_type, location)
    location_filter = filters["location"]
    if location_filter and location_filter not in event.get("location_tags", []):
        return False
    country_filter = filters["country"]
    if country_filter and country_filter not in event.get("country_tags", []):
        return False
    event_type_filter = filters["event_type"]
    if event_type_filter and event_type_filter not in event.get("event_type_tags", []):
        return False
    return True


def _safe_event_for_list(item: dict[str, Any], tags_by_id: dict[str, str], require_luma_tags: bool) -> dict[str, Any]:
    event = _safe_event(item, tags_by_id)
    if not require_luma_tags or event["tag_match_source"] == "luma_event_tags" or not event["event_id"]:
        return event
    try:
        detailed_event = _safe_event(_event_detail_payload(event["event_id"]), tags_by_id)
        if detailed_event["tag_match_source"] == "luma_event_tags":
            return detailed_event
    except LumaError:
        pass
    return event


def _tag_filtered_with_inference(
    events: list[dict[str, Any]],
    country: str,
    event_type: str,
    location: str,
    event_tags: Any = None,
) -> bool:
    filters = _resolved_event_filters(country, event_type, location)
    if not (filters["country"] or filters["event_type"] or filters["location"] or _event_tag_filters(event_tags, "", "", "")):
        return False
    return any(event.get("tag_match_source") != "luma_event_tags" for event in events)


def _list_events_raw(
    query: str,
    start: str,
    end: str,
    max_events: int,
    country: str = "",
    event_type: str = "",
    location: str = "",
    event_tags: Any = None,
) -> tuple[list[dict[str, Any]], bool, bool]:
    now = datetime.now(timezone.utc)
    after = _rfc3339(start, now)
    before = _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    limit = max(1, min(int(max_events or DEFAULT_EVENT_LIMIT), MAX_EVENTS))
    events: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    filters = _resolved_event_filters(country, event_type, location)
    require_luma_tags = bool(filters["country"] or filters["event_type"] or filters["location"] or _event_tag_filters(event_tags, "", "", ""))
    tags_by_id = _safe_tag_catalog() if require_luma_tags else {}

    while len(events) < limit:
        page_limit = LUMA_PAGE_LIMIT if require_luma_tags else min(LUMA_PAGE_LIMIT, limit - len(events))
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
        page_events = [_safe_event_for_list(item, tags_by_id, require_luma_tags) for item in _entries(payload)]
        events.extend(
            event for event in page_events if _event_matches_filters(event, query, country, event_type, location, event_tags)
        )
        has_more = _has_more(payload)
        cursor = _next_cursor(payload)
        if not has_more or not cursor:
            break

    truncated = len(events) > limit or (has_more and len(events) >= limit)
    return events[:limit], has_more, truncated


def _single_event(event_id: str) -> dict[str, Any]:
    payload = _event_detail_payload(event_id)
    event = _safe_event(payload)
    if not event["event_id"]:
        event["event_id"] = event_id
    return event


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    return _shared_scoped_company_error(companies, "Luma guest matching", SCOPE_SOURCE)


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


def _clean_company_candidate(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or len(text) < 3 or len(text) > 80:
        return ""
    lowered = text.lower()
    if lowered in {"none", "nil", "na", "n/a", "-", "not applicable"}:
        return ""
    if "@" in text or "http://" in lowered or "https://" in lowered:
        return ""
    return text


def _company_answer_candidates(value: Any) -> list[str]:
    candidates: list[str] = []
    if isinstance(value, dict):
        question = str(
            value.get("question")
            or value.get("label")
            or value.get("title")
            or value.get("name")
            or value.get("field")
            or ""
        ).lower()
        answer = value.get("answer") or value.get("value") or value.get("response")
        if question and any(marker in question for marker in COMPANY_QUESTION_MARKERS):
            cleaned = _clean_company_candidate(answer)
            if cleaned:
                candidates.append(cleaned)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                candidates.extend(_company_answer_candidates(nested))
    elif isinstance(value, list):
        for item in value:
            candidates.extend(_company_answer_candidates(item))
    return candidates


def _company_candidate_names_from_guest(guest: dict[str, Any]) -> list[str]:
    raw = [
        guest.get("company"),
        guest.get("company_name"),
        guest.get("companyName"),
        guest.get("organization"),
        guest.get("organisation"),
    ]
    candidates = [_clean_company_candidate(value) for value in raw]
    candidates.extend(_company_answer_candidates(guest.get("registration_answers")))
    candidates.extend(_company_answer_candidates(guest.get("registrationAnswers")))
    return _unique_text([candidate for candidate in candidates if candidate])


def _is_personal_email_domain(domain: str) -> bool:
    return _clean_domain(domain) in PERSONAL_EMAIL_DOMAINS


def _guest_match_keys(guests: list[dict[str, Any]]) -> dict[str, list[str]]:
    domains: list[str] = []
    company_names: list[str] = []
    for guest in guests:
        domain = _email_domain(_guest_email(guest))
        if domain and not _is_personal_email_domain(domain):
            domains.append(domain)
        company_names.extend(_company_candidate_names_from_guest(guest))
    return {
        "email_domains": _unique_text(domains)[:MATCH_KEY_LIMIT],
        "company_name_candidates": _unique_text(company_names)[:MATCH_KEY_LIMIT],
    }


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
    country: str = "",
    event_type: str = "",
    location: str = "",
    event_tags: list[str] | None = None,
) -> dict[str, Any]:
    """List bounded read-only Luma events for account-context planning.

    Optional event_tags filters use exact Luma event tags first. Convenience
    location, country, and event_type filters normalize into event tags where
    possible. Supported event_type values are Sports, Appreciation Afternoon, HR
    Happy Hour, and Leaders Lounge.
    """

    limit = max(1, min(int(max_events or DEFAULT_EVENT_LIMIT), MAX_EVENTS))
    now = datetime.now(timezone.utc)
    filters = _resolved_event_filters(country, event_type, location)
    scope = _scope(
        slack_user_email,
        {
            "query": query,
            "after": _rfc3339(start, now),
            "before": _rfc3339(end, now + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)),
            "requested_limit": limit,
            "event_tag_filters": _event_tag_filters(event_tags, country, event_type, location),
            "location_filter": filters["location"] or location,
            "country_filter": filters["country"] or country,
            "event_type_filter": filters["event_type"],
            "location_tags": list(LOCATION_TAGS),
            "allowed_event_type_tags": list(EVENT_TYPE_TAGS),
            "country_tags": list(COUNTRY_TAGS),
            "safety": "Read-only event list; no invites, RSVP changes, attendee exports, or mutations.",
        },
    )

    try:
        events, has_more, truncated = _list_events_raw(query, start, end, limit, country, event_type, location, event_tags)
    except LumaError as error:
        return _blocked(str(error), scope)

    tag_inference = _tag_filtered_with_inference(events, country, event_type, location, event_tags)
    return {
        "answer": events,
        "source": "Luma",
        "scope": scope,
        "confidence": "needs-check" if truncated or tag_inference else "verified",
        "has_more": has_more,
        "truncated": truncated,
        "caveat": (
            "Luma events are event context only. Use HubSpot scoped accounts before account actions. "
            "When Luma omits tags from list results, tag filters may fall back to event metadata."
        ),
    }


@mcp.tool()
def get_luma_event_match_keys(
    slack_user_email: str,
    event_ids: list[str] | None = None,
    query: str = "",
    start: str = "",
    end: str = "",
    max_guests_per_event: int = MAX_GUESTS_PER_EVENT,
    country: str = "",
    event_type: str = "",
    location: str = "",
    event_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Return safe attendee-derived keys for HubSpot target-account lookup.

    This is the event-first path for broad questions such as "which target
    accounts are attending this event". It returns company domains and company
    name candidates only, not attendee names, emails, phone numbers, raw
    registration answers, or raw guest lists.
    """

    filters = _resolved_event_filters(country, event_type, location)
    scope = _scope(
        slack_user_email,
        {
            "event_ids": [str(event_id).strip() for event_id in (event_ids or []) if str(event_id).strip()],
            "query": query,
            "event_tag_filters": _event_tag_filters(event_tags, country, event_type, location),
            "location_filter": filters["location"] or location,
            "country_filter": filters["country"] or country,
            "event_type_filter": filters["event_type"],
            "max_guests_per_event": max(1, min(int(max_guests_per_event or MAX_GUESTS_PER_EVENT), MAX_GUESTS_PER_EVENT)),
            "safety": "Safe match keys only; do not paste key lists in Slack or expose raw attendees.",
        },
    )

    try:
        selected_event_ids = scope["event_ids"]
        if selected_event_ids:
            events = [_single_event(event_id) for event_id in selected_event_ids[:MAX_EVENTS_FOR_CONTEXT]]
            events_has_more = len(selected_event_ids) > MAX_EVENTS_FOR_CONTEXT
            events_truncated = events_has_more
        else:
            events, events_has_more, events_truncated = _list_events_raw(
                query,
                start,
                end,
                MAX_EVENTS_FOR_CONTEXT,
                country,
                event_type,
                location,
                event_tags,
            )

        answer: list[dict[str, Any]] = []
        any_truncated = events_truncated
        tag_inference = _tag_filtered_with_inference(events, country, event_type, location, event_tags)
        for event in events:
            event_id = event.get("event_id", "")
            if not event_id:
                continue
            guests, guests_has_more, guests_truncated = _list_guests(event_id, scope["max_guests_per_event"])
            counts = _guest_counts(guests)
            keys = _guest_match_keys(guests)
            any_truncated = any_truncated or guests_truncated
            answer.append(
                {
                    "event": event,
                    "match_keys": keys,
                    "total_guest_count": counts["total_guest_count"],
                    "rsvp_counts": counts["rsvp_counts"],
                    "checked_in_count": counts["checked_in_count"],
                    "email_domain_key_count": len(keys["email_domains"]),
                    "company_name_candidate_count": len(keys["company_name_candidates"]),
                    "has_more": guests_has_more,
                    "truncated": guests_truncated,
                }
            )
    except LumaError as error:
        return _blocked(str(error), scope)

    return {
        "answer": answer,
        "source": "Luma",
        "scope": scope,
        "confidence": "needs-check" if any_truncated or tag_inference else "verified",
        "has_more": events_has_more,
        "truncated": any_truncated,
        "caveat": (
            "Use these safe match keys to search HubSpot target accounts, then call "
            "get_luma_event_context with the scoped candidate companies. Do not expose "
            "raw Luma attendees or paste key lists in Slack."
        ),
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
    country: str = "",
    event_type: str = "",
    location: str = "",
    event_tags: list[str] | None = None,
) -> dict[str, Any]:
    """Get bounded Luma RSVP and attendance context for HubSpot-scoped companies.

    Optional event_tags filters use exact Luma event tags first. Convenience
    location, country, and event_type filters normalize into event tags where
    possible. Supported event_type values are Sports, Appreciation Afternoon, HR
    Happy Hour, and Leaders Lounge.
    """

    companies = scoped_companies if isinstance(scoped_companies, list) else []
    company_error = _scoped_company_error(companies)
    filters = _resolved_event_filters(country, event_type, location)
    scope = _scope(
        slack_user_email,
        {
            "scoped_company_count": len(companies),
            "event_ids": [str(event_id).strip() for event_id in (event_ids or []) if str(event_id).strip()],
            "query": query,
            "event_tag_filters": _event_tag_filters(event_tags, country, event_type, location),
            "location_filter": filters["location"] or location,
            "country_filter": filters["country"] or country,
            "event_type_filter": filters["event_type"],
            "location_tags": list(LOCATION_TAGS),
            "allowed_event_type_tags": list(EVENT_TYPE_TAGS),
            "country_tags": list(COUNTRY_TAGS),
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
            events, events_has_more, events_truncated = _list_events_raw(
                query,
                start,
                end,
                MAX_EVENTS_FOR_CONTEXT,
                country,
                event_type,
                location,
                event_tags,
            )

        event_contexts: list[dict[str, Any]] = []
        any_candidate_match = False
        any_truncated = events_truncated
        tag_inference = _tag_filtered_with_inference(events, country, event_type, location, event_tags)
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
        "confidence": "needs-check" if any_candidate_match or any_truncated or tag_inference else "verified",
        "has_more": events_has_more,
        "truncated": any_truncated,
        "caveat": (
            "Attendance means checked_in_at is present. RSVP statuses are not attendance, "
            "and Luma never overrides HubSpot account scope or ownership."
        ),
    }


if __name__ == "__main__":
    mcp.run("stdio")
