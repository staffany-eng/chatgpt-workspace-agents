#!/usr/bin/env python3
"""Cost-controlled Lusha MCP adapter for NurtureAny Sales Bot.

This server exposes only the Lusha workflows NurtureAny is allowed to use.
It intentionally avoids broad prospecting/enrichment tools that could reveal
contact details or burn credits without an explicit approval marker.
"""

from __future__ import annotations

import json
import math
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.responses import blocked_response
from nurtureany_common.scoped_company import scoped_company_error as _shared_scoped_company_error
from nurtureany_common.text import clean_domain as _clean_domain


LUSHA_BASE_URL = "https://api.lusha.com"
LUSHA_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
LUSHA_TIMEOUT_SECONDS = 15
MAX_SEARCH_COMPANIES = 5
MAX_CANDIDATES_PER_COMPANY = 5
MAX_REVEAL_CONTACTS = 3
USAGE_CACHE_TTL_SECONDS = 12
USAGE_MIN_INTERVAL_SECONDS = 12
SCOPE_SOURCE = "hubspot_nurtureany"

DECISION_MAKER_TITLES = [
    "owner",
    "founder",
    "ceo",
    "chief executive officer",
    "managing director",
    "director",
    "general manager",
    "head of operations",
    "operations director",
    "hr director",
    "people director",
]


mcp = FastMCP(
    "lusha_nurtureany",
    instructions=(
        "Cost-controlled Lusha tools for NurtureAny. Search first, reveal selected "
        "contacts only with approval, and always return credit reporting."
    ),
)


class LushaError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_usage_cache: dict[str, Any] | None = None
_usage_cache_at = 0.0
_usage_last_request_at = 0.0


def _token() -> str:
    token = os.environ.get("LUSHA_API_KEY", "").strip()
    if not token:
        raise LushaError("Missing LUSHA_API_KEY.")
    return token


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    url = urllib.parse.urljoin(LUSHA_BASE_URL, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "api_key": _token(),
        "accept": "application/json",
        "user-agent": LUSHA_USER_AGENT,
    }
    if data is not None:
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=LUSHA_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return payload, _headers(response.headers)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        message = _error_message(error.code, detail)
        raise LushaError(message, error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LushaError(f"Lusha API request timed out or failed: {reason}") from error


def _headers(headers: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


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
    safe = str(message).replace(_token(), "[REDACTED_LUSHA_API_KEY]")
    return f"Lusha API failed: {status_code} {safe[:300]}"


def _blocked(message: str, scope: dict[str, Any] | None = None, credit_report: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(
        message,
        "Lusha",
        scope,
        credit_report=credit_report or _credit_report(0, None, None, {}, "No Lusha call completed."),
    )


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {"caller_email": (slack_user_email or "").strip().lower()}
    if extra:
        scope.update(extra)
    return scope


def _usage_snapshot() -> tuple[dict[str, Any] | None, str]:
    global _usage_cache, _usage_cache_at, _usage_last_request_at

    now = time.monotonic()
    if _usage_cache and now - _usage_cache_at < USAGE_CACHE_TTL_SECONDS:
        return _usage_cache, "cached"
    if _usage_cache and now - _usage_last_request_at < USAGE_MIN_INTERVAL_SECONDS:
        return _usage_cache, "cached-rate-limited"

    try:
        payload, _ = _request_json("GET", "/account/usage")
    except LushaError as error:
        return None, f"unavailable: {error}"

    _usage_cache = _summarize_usage(payload)
    _usage_cache_at = now
    _usage_last_request_at = now
    return _usage_cache, "fresh"


def _summarize_usage(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    categories: dict[str, dict[str, int | float | None]] = {}
    total_used = 0.0
    total_remaining = 0.0
    total_available = 0.0

    for name, values in usage.items():
        if not isinstance(values, dict):
            continue
        used = _number(values.get("used"))
        remaining = _number(values.get("remaining"))
        total = _number(values.get("total"))
        categories[name] = {"used": used, "remaining": remaining, "total": total}
        total_used += used or 0
        total_remaining += remaining or 0
        total_available += total or 0

    return {
        "categories": categories,
        "total_used": int(total_used) if total_used.is_integer() else total_used,
        "total_remaining": int(total_remaining) if total_remaining.is_integer() else total_remaining,
        "total": int(total_available) if total_available.is_integer() else total_available,
    }


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _usage_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> int | float | str:
    if not before or not after:
        return "unavailable"
    if before is after:
        return "unavailable"
    before_used = _number(before.get("total_used"))
    after_used = _number(after.get("total_used"))
    if before_used is None or after_used is None:
        return "unavailable"
    delta = after_used - before_used
    return int(delta) if float(delta).is_integer() else delta


def _rate_limit_remaining(headers: dict[str, str]) -> dict[str, str]:
    keys = [
        "x-daily-requests-left",
        "x-hourly-requests-left",
        "x-minute-requests-left",
        "x-ratelimit-remaining-daily",
        "x-ratelimit-reset-daily",
    ]
    return {key: headers[key] for key in keys if key in headers} or {"status": "unavailable"}


def _credit_report(
    estimated_credits: int | float | str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    headers: dict[str, str],
    caveat: str,
) -> dict[str, Any]:
    return {
        "estimated_credits": estimated_credits,
        "actual_delta_credits": _usage_delta(before, after),
        "usage_before": before or "unavailable",
        "usage_after": after or "unavailable",
        "rate_limit_remaining": _rate_limit_remaining(headers),
        "caveat": caveat,
    }


def _estimate_search_credits(returned_results: int) -> int:
    return max(1, math.ceil(max(returned_results, 0) / 25))


def _company_input(company: dict[str, Any]) -> dict[str, str]:
    return {
        "company_id": str(company.get("company_id") or company.get("id") or "").strip(),
        "name": str(company.get("name") or company.get("company_name") or "").strip(),
        "domain": _clean_domain(str(company.get("domain") or company.get("company_domain") or "").strip()),
        "country": str(company.get("country") or "Singapore").strip() or "Singapore",
    }


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    return _shared_scoped_company_error(companies, "Lusha paid enrichment", SCOPE_SOURCE, MAX_SEARCH_COMPANIES)


def _has_scoped_company_ids(scoped_company_ids: list[str] | None) -> bool:
    return bool([str(company_id).strip() for company_id in (scoped_company_ids or []) if str(company_id).strip()])


def _search_payload(company: dict[str, str], limit_per_company: int) -> dict[str, Any]:
    company_include: dict[str, Any] = {
        "locations": [{"country": company["country"]}],
    }
    if company["domain"]:
        company_include["domains"] = [company["domain"]]
    if company["name"]:
        company_include["names"] = [company["name"]]

    return {
        "includePartialContact": True,
        "excludeDnc": False,
        "pages": {"page": 0, "size": max(10, min(50, int(limit_per_company)))},
        "filters": {
            "contacts": {"include": {"jobTitles": DECISION_MAKER_TITLES}},
            "companies": {"include": company_include},
        },
    }


def _candidate(contact: dict[str, Any], request_id: str, company: dict[str, str], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "input_company": company,
        "request_id": request_id,
        "contact_id": contact.get("contactId") or "",
        "name": contact.get("name") or "",
        "job_title": contact.get("jobTitle") or "",
        "company_id": contact.get("companyId") or "",
        "company_name": contact.get("companyName") or "",
        "company_domain": contact.get("fqdn") or "",
        "is_shown": bool(contact.get("isShown")),
        "has_linkedin_or_social": bool(contact.get("hasSocialLink")),
        "has_email": bool(contact.get("hasEmails")),
        "has_work_email": bool(contact.get("hasWorkEmail")),
        "has_phone": bool(contact.get("hasPhones")),
        "has_mobile_phone": bool(contact.get("hasMobilePhone")),
        "has_direct_phone": bool(contact.get("hasDirectPhone")),
        "confidence": "needs-check",
    }


def _safe_email(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": item.get("email") or item.get("address") or "",
        "type": item.get("emailType") or "",
        "confidence": item.get("emailConfidence") or "",
        "updated_at": item.get("updateDate") or "",
    }


def _safe_phone(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": item.get("number") or "",
        "type": item.get("phoneType") or "",
        "do_not_call": bool(item.get("doNotCall")),
        "updated_at": item.get("updateDate") or "",
    }


def _revealed_contact(item: dict[str, Any], reveal_emails: bool, reveal_phones: bool) -> dict[str, Any]:
    data = item.get("data") or {}
    emails = [_safe_email(email) for email in data.get("emailAddresses", [])] if reveal_emails else []
    phones = [_safe_phone(phone) for phone in data.get("phoneNumbers", [])] if reveal_phones else []
    return {
        "contact_id": item.get("id") or "",
        "is_success": bool(item.get("isSuccess")),
        "full_name": data.get("fullName") or " ".join(
            part for part in [data.get("firstName") or "", data.get("lastName") or ""] if part
        ).strip(),
        "job_title": data.get("jobTitle") or "",
        "company_id": data.get("companyId") or "",
        "company_name": data.get("companyName") or "",
        "linkedin_url": (data.get("socialLinks") or {}).get("linkedin") or "",
        "departments": data.get("departments") or [],
        "seniority": data.get("seniority") or [],
        "location": data.get("location") or {},
        "emails": emails,
        "phones": phones,
        "hubspot_preview_action": _hubspot_preview_action(item, data, emails, phones),
    }


def _hubspot_preview_action(
    item: dict[str, Any],
    data: dict[str, Any],
    emails: list[dict[str, Any]],
    phones: list[dict[str, Any]],
) -> dict[str, Any]:
    full_name = data.get("fullName") or " ".join(
        part for part in [data.get("firstName") or "", data.get("lastName") or ""] if part
    ).strip()
    revealed_on = datetime.now(timezone.utc).date().isoformat()
    field_updates = {
        "firstname": data.get("firstName") or "",
        "lastname": data.get("lastName") or "",
        "jobtitle": data.get("jobTitle") or "",
        "nurtureany_persona": data.get("jobTitle") or "",
        "nurtureany_channel_fit": "lusha_selected",
        "nurtureany_contact_confidence": "needs_ae_review",
        "nurtureany_last_verified_at": datetime.now(timezone.utc).date().isoformat(),
    }
    if emails:
        field_updates["email"] = emails[0]["address"]
    return {
        "company_id": "",
        "contact_id": "",
        "task": "",
        "note_summary": f"Lusha candidate, revealed by approval on {revealed_on}.",
        "field_updates": {key: value for key, value in field_updates.items() if value},
        "source": {
            "provider": "Lusha",
            "lusha_contact_id": item.get("id") or "",
            "selected_contact": full_name,
            "company_name": data.get("companyName") or "",
            "has_email": bool(emails),
            "has_phone": bool(phones),
        },
        "selected": True,
    }


@mcp.tool()
def search_lusha_decision_maker_candidates(
    slack_user_email: str,
    companies: list[dict[str, Any]],
    limit_per_company: int = MAX_CANDIDATES_PER_COMPANY,
) -> dict[str, Any]:
    """Search Lusha for decision-maker candidates without revealing email or phone details."""

    scope = _scope(
        slack_user_email,
        {
            "requested_company_count": len(companies or []),
            "max_company_count": MAX_SEARCH_COMPANIES,
            "max_candidates_per_company": MAX_CANDIDATES_PER_COMPANY,
        },
    )
    raw_companies = [company for company in (companies or [])[:MAX_SEARCH_COMPANIES] if isinstance(company, dict)]
    scoped_error = _scoped_company_error(raw_companies)
    if scoped_error:
        return _blocked(scoped_error, scope)

    selected_companies = [_company_input(company) for company in raw_companies]
    selected_companies = [company for company in selected_companies if company["name"] or company["domain"]]
    if not selected_companies:
        return _blocked("At least one company name or domain is required.", scope)

    try:
        _token()
    except LushaError as error:
        return _blocked(str(error), scope)

    before, before_status = _usage_snapshot()
    candidates_by_company: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    estimated_credits = 0
    capped_limit = max(1, min(int(limit_per_company or MAX_CANDIDATES_PER_COMPANY), MAX_CANDIDATES_PER_COMPANY))

    try:
        for company in selected_companies:
            payload = _search_payload(company, capped_limit)
            response, headers = _request_json("POST", "/prospecting/contact/search", payload)
            request_id = response.get("requestId") or ""
            contacts = response.get("contacts") or []
            estimated_credits += _estimate_search_credits(len(contacts))
            candidates = [
                _candidate(contact, request_id, company, rank)
                for rank, contact in enumerate(contacts[:capped_limit], start=1)
            ]
            candidates_by_company.append(
                {
                    "input_company": company,
                    "request_id": request_id,
                    "returned_results": len(contacts),
                    "total_results": response.get("totalResults"),
                    "candidates": candidates,
                }
            )
    except LushaError as error:
        after, _ = _usage_snapshot()
        report = _credit_report(
            estimated_credits or "unavailable",
            before,
            after,
            headers,
            f"Search stopped early. Usage before status: {before_status}.",
        )
        return _blocked(str(error), scope, report)

    after, after_status = _usage_snapshot()
    report = _credit_report(
        estimated_credits,
        before,
        after,
        headers,
        f"Search only; no email or phone was revealed. Usage snapshots: before={before_status}, after={after_status}.",
    )
    return {
        "answer": candidates_by_company,
        "source": "Lusha Prospecting Contact Search",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Candidates require AE review before reveal or HubSpot preview. Email and phone are not revealed by search.",
        "credit_report": report,
    }


@mcp.tool()
def reveal_lusha_contact_details(
    slack_user_email: str,
    request_id: str,
    contact_ids: list[str],
    reveal_emails: bool = True,
    reveal_phones: bool = False,
    approval_marker: str = "",
    scoped_company_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Reveal selected Lusha contact details after explicit approval."""

    clean_ids = [str(contact_id).strip() for contact_id in (contact_ids or []) if str(contact_id).strip()]
    scope = _scope(
        slack_user_email,
        {
            "requested_contact_count": len(clean_ids),
            "max_contact_count": MAX_REVEAL_CONTACTS,
            "reveal_emails": bool(reveal_emails),
            "reveal_phones": bool(reveal_phones),
        },
    )
    if not _has_scoped_company_ids(scoped_company_ids):
        return _blocked("Lusha reveal requires scoped HubSpot company_ids from the prior NurtureAny HubSpot-scoped search.", scope)
    if not approval_marker.strip():
        return _blocked("Lusha reveal requires an approval marker from the Slack thread.", scope)
    if not request_id.strip():
        return _blocked("Lusha reveal requires the request_id from a prior search.", scope)
    if not clean_ids:
        return _blocked("At least one contact_id is required.", scope)
    if not reveal_emails and not reveal_phones:
        return _blocked("At least one reveal flag must be true.", scope)
    try:
        _token()
    except LushaError as error:
        return _blocked(str(error), scope)

    selected_ids = clean_ids[:MAX_REVEAL_CONTACTS]
    before, before_status = _usage_snapshot()
    payload = {
        "requestId": request_id.strip(),
        "contactIds": selected_ids,
        "revealEmails": bool(reveal_emails),
        "revealPhones": bool(reveal_phones),
    }
    headers: dict[str, str] = {}
    try:
        response, headers = _request_json("POST", "/prospecting/contact/enrich", payload)
    except LushaError as error:
        after, _ = _usage_snapshot()
        estimate = len(selected_ids) * ((1 if reveal_emails else 0) + (5 if reveal_phones else 0))
        report = _credit_report(estimate, before, after, headers, f"Reveal failed. Usage before status: {before_status}.")
        return _blocked(str(error), scope, report)

    contacts = [
        _revealed_contact(contact, bool(reveal_emails), bool(reveal_phones))
        for contact in response.get("contacts", [])
    ]
    estimate = len(selected_ids) * ((1 if reveal_emails else 0) + (5 if reveal_phones else 0))
    after, after_status = _usage_snapshot()
    report = _credit_report(
        estimate,
        before,
        after,
        headers,
        f"Selected reveal only. Usage snapshots: before={before_status}, after={after_status}.",
    )
    return {
        "answer": {
            "request_id": response.get("requestId") or request_id.strip(),
            "contacts": contacts,
            "hubspot_preview_actions": [contact["hubspot_preview_action"] for contact in contacts],
            "next_tool": "plan_hubspot_writeback",
            "will_mutate_hubspot": False,
        },
        "source": "Lusha Prospecting Contact Enrich",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Selected contact PII may be shown in internal Slack. HubSpot output is preview seed only.",
        "credit_report": report,
    }


@mcp.tool()
def get_lusha_credit_usage() -> dict[str, Any]:
    """Return summarized Lusha API credit usage."""

    try:
        _token()
        usage, status = _usage_snapshot()
    except LushaError as error:
        return _blocked(str(error), {"usage_snapshot": "unavailable"})

    report = _credit_report(
        0,
        usage,
        usage,
        {},
        f"Usage lookup status: {status}. Credit Usage API is rate-limited, so values may be cached briefly.",
    )
    return {
        "answer": usage or "unavailable",
        "source": "Lusha Account Usage",
        "scope": {"usage_snapshot": status},
        "confidence": "verified" if usage else "blocked",
        "caveat": "Usage is summarized across returned Lusha credit categories.",
        "credit_report": report,
    }


if __name__ == "__main__":
    mcp.run("stdio")
