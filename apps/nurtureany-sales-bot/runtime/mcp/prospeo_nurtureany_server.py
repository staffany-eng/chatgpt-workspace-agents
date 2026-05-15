#!/usr/bin/env python3
"""Cost-controlled Prospeo MCP adapter for NurtureAny Sales Bot.

This server exposes only the Prospeo workflows NurtureAny is allowed to use.
Search returns candidate records without email or mobile details. Selected
reveal requires scoped HubSpot company IDs and an explicit approval marker.
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.profile_env import profile_env_value
from nurtureany_common.responses import blocked_response
from nurtureany_common.scoped_company import scoped_company_error as _shared_scoped_company_error
from nurtureany_common.text import clean_domain as _clean_domain


PROSPEO_BASE_URL = "https://api.prospeo.io"
PROSPEO_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
PROSPEO_TIMEOUT_SECONDS = 15
MAX_SEARCH_COMPANIES = 5
MAX_CANDIDATES_PER_COMPANY = 5
MAX_REVEAL_CONTACTS = 3
ACCOUNT_CACHE_TTL_SECONDS = 12
ACCOUNT_MIN_INTERVAL_SECONDS = 12
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
    "hr manager",
    "people manager",
    "operations manager",
    "finance manager",
    "payroll manager",
]


mcp = FastMCP(
    "prospeo_nurtureany",
    instructions=(
        "Cost-controlled Prospeo tools for NurtureAny. Search first, reveal selected "
        "contacts only with approval, and always return credit reporting."
    ),
)


class ProspeoError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_account_cache: dict[str, Any] | None = None
_account_cache_at = 0.0
_account_last_request_at = 0.0


def _token() -> str:
    token = profile_env_value("PROSPEO_API_KEY")
    if not token:
        raise ProspeoError("Missing PROSPEO_API_KEY.")
    return token


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    url = urllib.parse.urljoin(PROSPEO_BASE_URL, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "X-KEY": _token(),
        "accept": "application/json",
        "user-agent": PROSPEO_USER_AGENT,
    }
    if data is not None:
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=PROSPEO_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict) and payload.get("error"):
                raise ProspeoError(_payload_error_message(payload), response.status)
            return payload, _headers(response.headers)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        message = _error_message(error.code, detail)
        raise ProspeoError(message, error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise ProspeoError(f"Prospeo API request timed out or failed: {reason}") from error


def _headers(headers: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _payload_error_message(payload: dict[str, Any]) -> str:
    code = payload.get("error_code") or "ERROR"
    detail = payload.get("filter_error") or payload.get("message") or payload.get("error_message") or payload
    return f"Prospeo API failed: {code} {str(detail)[:300]}"


def _error_message(status_code: int, detail: str) -> str:
    try:
        parsed = json.loads(detail)
        message = _payload_error_message(parsed) if isinstance(parsed, dict) else detail
    except json.JSONDecodeError:
        message = detail
    token = profile_env_value("PROSPEO_API_KEY")
    safe = str(message).replace(token, "[REDACTED_PROSPEO_API_KEY]") if token else str(message)
    return f"Prospeo API failed: {status_code} {safe[:300]}"


def _blocked(message: str, scope: dict[str, Any] | None = None, credit_report: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(
        message,
        "Prospeo",
        scope,
        credit_report=credit_report or _credit_report(0, None, None, {}, "unavailable", "No Prospeo call completed."),
    )


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {"caller_email": (slack_user_email or "").strip().lower()}
    if extra:
        scope.update(extra)
    return scope


def _account_snapshot() -> tuple[dict[str, Any] | None, str]:
    global _account_cache, _account_cache_at, _account_last_request_at

    now = time.monotonic()
    if _account_cache and now - _account_cache_at < ACCOUNT_CACHE_TTL_SECONDS:
        return _account_cache, "cached"
    if _account_cache and now - _account_last_request_at < ACCOUNT_MIN_INTERVAL_SECONDS:
        return _account_cache, "cached-rate-limited"

    try:
        payload, _ = _request_json("GET", "/account-information")
    except ProspeoError as error:
        return None, f"unavailable: {error}"

    _account_cache = _summarize_account(payload)
    _account_cache_at = now
    _account_last_request_at = now
    return _account_cache, "fresh"


def _summarize_account(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        data = payload if isinstance(payload, dict) else {}
    return {
        "current_plan": data.get("current_plan") or "unavailable",
        "remaining_credits": _number(data.get("remaining_credits")),
        "used_credits": _number(data.get("used_credits")),
        "next_quota_renewal_days": _number(data.get("next_quota_renewal_days")),
        "next_quota_renewal_date": data.get("next_quota_renewal_date") or "unavailable",
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
    before_used = _number(before.get("used_credits"))
    after_used = _number(after.get("used_credits"))
    if before_used is None or after_used is None:
        return "unavailable"
    delta = after_used - before_used
    return int(delta) if float(delta).is_integer() else delta


def _rate_limit_remaining(headers: dict[str, str]) -> dict[str, str]:
    keys = [
        "x-ratelimit-remaining",
        "x-ratelimit-remaining-second",
        "x-ratelimit-remaining-minute",
        "x-ratelimit-remaining-day",
        "x-ratelimit-reset",
    ]
    return {key: headers[key] for key in keys if key in headers} or {"status": "unavailable"}


def _credit_report(
    estimated_credits: int | float | str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    headers: dict[str, str],
    reported_total_cost: int | float | str,
    caveat: str,
) -> dict[str, Any]:
    return {
        "estimated_credits": estimated_credits,
        "actual_delta_credits": _usage_delta(before, after),
        "reported_total_cost": reported_total_cost,
        "usage_before": before or "unavailable",
        "usage_after": after or "unavailable",
        "rate_limit_remaining": _rate_limit_remaining(headers),
        "caveat": caveat,
    }


def _company_input(company: dict[str, Any]) -> dict[str, str]:
    return {
        "company_id": str(company.get("company_id") or company.get("id") or "").strip(),
        "name": str(company.get("name") or company.get("company_name") or "").strip(),
        "domain": _clean_domain(str(company.get("domain") or company.get("company_domain") or "").strip()),
        "country": str(company.get("country") or "Singapore").strip() or "Singapore",
    }


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    return _shared_scoped_company_error(companies, "Prospeo paid enrichment", SCOPE_SOURCE, MAX_SEARCH_COMPANIES)


def _has_scoped_company_ids(scoped_company_ids: list[str] | None) -> bool:
    return bool([str(company_id).strip() for company_id in (scoped_company_ids or []) if str(company_id).strip()])


def _search_payload(company: dict[str, str], limit_per_company: int) -> dict[str, Any]:
    company_filter: dict[str, Any] = {}
    if company["domain"]:
        company_filter["websites"] = {"include": [company["domain"]]}
    if company["name"]:
        company_filter["names"] = {"include": [company["name"]]}

    capped_limit = max(1, min(int(limit_per_company), MAX_CANDIDATES_PER_COMPANY))
    return {
        "page": 1,
        "filters": {
            "company": company_filter,
            "person_job_title": {
                "include": DECISION_MAKER_TITLES,
                "match_only_exact_job_titles": False,
            },
            "person_contact_details": {
                "email": ["VERIFIED"],
                "mobile": ["VERIFIED"],
                "operator": "OR",
                "hide_people_with_details_already_revealed": False,
            },
            "max_person_per_company": capped_limit,
        },
    }


def _candidate(result: dict[str, Any], company: dict[str, str], rank: int) -> dict[str, Any]:
    person = result.get("person") if isinstance(result.get("person"), dict) else {}
    result_company = result.get("company") if isinstance(result.get("company"), dict) else {}
    return {
        "rank": rank,
        "input_company": company,
        "person_id": person.get("person_id") or "",
        "full_name": person.get("full_name") or " ".join(
            part for part in [person.get("first_name") or "", person.get("last_name") or ""] if part
        ).strip(),
        "current_job_title": person.get("current_job_title") or "",
        "headline": person.get("headline") or "",
        "linkedin_url": person.get("linkedin_url") or "",
        "result_company_id": result_company.get("company_id") or "",
        "result_company_name": result_company.get("name") or "",
        "result_company_domain": _clean_domain(result_company.get("domain") or result_company.get("website") or ""),
        "contact_detail_filter": "search filtered for verified email or mobile availability; values are not revealed here",
        "confidence": "needs-check",
    }


def _safe_email(person: dict[str, Any]) -> dict[str, Any] | None:
    email = person.get("email") if isinstance(person.get("email"), dict) else None
    if not email:
        return None
    return {
        "address": email.get("email") or "",
        "status": email.get("status") or "",
        "revealed": bool(email.get("revealed")),
        "verification_method": email.get("verification_method") or "",
        "email_mx_provider": email.get("email_mx_provider") or "",
    }


def _safe_mobile(person: dict[str, Any]) -> dict[str, Any] | None:
    mobile = person.get("mobile") if isinstance(person.get("mobile"), dict) else None
    if not mobile:
        return None
    return {
        "number": mobile.get("mobile") or "",
        "national": mobile.get("mobile_national") or "",
        "international": mobile.get("mobile_international") or "",
        "country": mobile.get("mobile_country") or "",
        "country_code": mobile.get("mobile_country_code") or "",
        "status": mobile.get("status") or "",
        "revealed": bool(mobile.get("revealed")),
    }


def _revealed_contact(item: dict[str, Any], reveal_emails: bool, reveal_phones: bool) -> dict[str, Any]:
    person = item.get("person") if isinstance(item.get("person"), dict) else {}
    company = item.get("company") if isinstance(item.get("company"), dict) else {}
    email = _safe_email(person) if reveal_emails else None
    mobile = _safe_mobile(person) if reveal_phones else None
    emails = [email] if email and email.get("address") else []
    phones = [mobile] if mobile and mobile.get("number") else []
    return {
        "identifier": item.get("identifier") or person.get("person_id") or "",
        "person_id": person.get("person_id") or item.get("identifier") or "",
        "full_name": person.get("full_name") or " ".join(
            part for part in [person.get("first_name") or "", person.get("last_name") or ""] if part
        ).strip(),
        "current_job_title": person.get("current_job_title") or "",
        "linkedin_url": person.get("linkedin_url") or "",
        "company_name": company.get("name") or "",
        "company_domain": _clean_domain(company.get("domain") or company.get("website") or ""),
        "emails": emails,
        "phones": phones,
        "hubspot_preview_action": _hubspot_preview_action(item, person, company, emails, phones),
    }


def _hubspot_preview_action(
    item: dict[str, Any],
    person: dict[str, Any],
    company: dict[str, Any],
    emails: list[dict[str, Any]],
    phones: list[dict[str, Any]],
) -> dict[str, Any]:
    full_name = person.get("full_name") or " ".join(
        part for part in [person.get("first_name") or "", person.get("last_name") or ""] if part
    ).strip()
    revealed_on = datetime.now(timezone.utc).date().isoformat()
    field_updates = {
        "firstname": person.get("first_name") or "",
        "lastname": person.get("last_name") or "",
        "jobtitle": person.get("current_job_title") or "",
        "nurtureany_persona": person.get("current_job_title") or "",
        "nurtureany_channel_fit": "prospeo_selected",
        "nurtureany_contact_confidence": "needs_ae_review",
        "nurtureany_last_verified_at": datetime.now(timezone.utc).date().isoformat(),
    }
    if emails:
        field_updates["email"] = emails[0]["address"]
    return {
        "company_id": "",
        "contact_id": "",
        "task": "",
        "note_summary": f"Prospeo candidate, revealed by approval on {revealed_on}.",
        "field_updates": {key: value for key, value in field_updates.items() if value},
        "source": {
            "provider": "Prospeo",
            "prospeo_person_id": person.get("person_id") or item.get("identifier") or "",
            "selected_contact": full_name,
            "company_name": company.get("name") or "",
            "has_email": bool(emails),
            "has_phone": bool(phones),
        },
        "selected": True,
    }


@mcp.tool()
def search_prospeo_decision_maker_candidates(
    slack_user_email: str,
    companies: list[dict[str, Any]],
    limit_per_company: int = MAX_CANDIDATES_PER_COMPANY,
) -> dict[str, Any]:
    """Search Prospeo for decision-maker candidates without revealing email or phone details."""

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
    except ProspeoError as error:
        return _blocked(str(error), scope)

    before, before_status = _account_snapshot()
    candidates_by_company: list[dict[str, Any]] = []
    headers: dict[str, str] = {}
    estimated_credits = 0
    reported_cost: int | float | str = "unavailable"
    capped_limit = max(1, min(int(limit_per_company or MAX_CANDIDATES_PER_COMPANY), MAX_CANDIDATES_PER_COMPANY))

    try:
        for company in selected_companies:
            payload = _search_payload(company, capped_limit)
            response, headers = _request_json("POST", "/search-person", payload)
            results = response.get("results") or []
            if results and not response.get("free"):
                estimated_credits += 1
            candidates = [
                _candidate(result, company, rank)
                for rank, result in enumerate(results[:capped_limit], start=1)
            ]
            candidates_by_company.append(
                {
                    "input_company": company,
                    "free": bool(response.get("free")),
                    "returned_results": len(results),
                    "pagination": response.get("pagination") or {},
                    "candidates": candidates,
                }
            )
    except ProspeoError as error:
        after, _ = _account_snapshot()
        report = _credit_report(
            estimated_credits or "unavailable",
            before,
            after,
            headers,
            reported_cost,
            f"Search stopped early. Usage before status: {before_status}.",
        )
        return _blocked(str(error), scope, report)

    after, after_status = _account_snapshot()
    report = _credit_report(
        estimated_credits,
        before,
        after,
        headers,
        reported_cost,
        f"Search only; no email or phone was revealed. Usage snapshots: before={before_status}, after={after_status}.",
    )
    return {
        "answer": candidates_by_company,
        "source": "Prospeo Search Person",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Candidates require AE review before reveal or HubSpot preview. Email and mobile are not revealed by search.",
        "credit_report": report,
    }


@mcp.tool()
def reveal_prospeo_contact_details(
    slack_user_email: str,
    person_ids: list[str],
    reveal_emails: bool = True,
    reveal_phones: bool = False,
    approval_marker: str = "",
    scoped_company_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Reveal selected Prospeo contact details after explicit approval."""

    clean_ids = [str(person_id).strip() for person_id in (person_ids or []) if str(person_id).strip()]
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
        return _blocked("Prospeo reveal requires scoped HubSpot company_ids from the prior NurtureAny HubSpot-scoped search.", scope)
    if not approval_marker.strip():
        return _blocked("Prospeo reveal requires an approval marker from the Slack thread.", scope)
    if not clean_ids:
        return _blocked("At least one person_id is required.", scope)
    if not reveal_emails and not reveal_phones:
        return _blocked("At least one reveal flag must be true.", scope)
    try:
        _token()
    except ProspeoError as error:
        return _blocked(str(error), scope)

    selected_ids = clean_ids[:MAX_REVEAL_CONTACTS]
    before, before_status = _account_snapshot()
    payload = {
        "only_verified_email": bool(reveal_emails),
        "enrich_mobile": bool(reveal_phones),
        "data": [
            {
                "identifier": person_id,
                "person_id": person_id,
            }
            for person_id in selected_ids
        ],
    }
    headers: dict[str, str] = {}
    try:
        response, headers = _request_json("POST", "/bulk-enrich-person", payload)
    except ProspeoError as error:
        after, _ = _account_snapshot()
        estimate = len(selected_ids) * (10 if reveal_phones else 1)
        report = _credit_report(estimate, before, after, headers, "unavailable", f"Reveal failed. Usage before status: {before_status}.")
        return _blocked(str(error), scope, report)

    contacts = [
        _revealed_contact(contact, bool(reveal_emails), bool(reveal_phones))
        for contact in response.get("matched", [])
    ]
    estimate = len(selected_ids) * (10 if reveal_phones else 1)
    reported_cost = _number(response.get("total_cost"))
    after, after_status = _account_snapshot()
    report = _credit_report(
        estimate,
        before,
        after,
        headers,
        reported_cost if reported_cost is not None else "unavailable",
        f"Selected reveal only. Usage snapshots: before={before_status}, after={after_status}.",
    )
    return {
        "answer": {
            "contacts": contacts,
            "not_matched": response.get("not_matched") or [],
            "invalid_datapoints": response.get("invalid_datapoints") or [],
            "hubspot_preview_actions": [contact["hubspot_preview_action"] for contact in contacts],
            "next_tool": "plan_hubspot_writeback",
            "will_mutate_hubspot": False,
        },
        "source": "Prospeo Bulk Enrich Person",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Selected contact PII may be shown in internal Slack. HubSpot output is preview seed only.",
        "credit_report": report,
    }


@mcp.tool()
def get_prospeo_credit_usage() -> dict[str, Any]:
    """Return summarized Prospeo API credit usage."""

    try:
        _token()
        usage, status = _account_snapshot()
    except ProspeoError as error:
        return _blocked(str(error), {"usage_snapshot": "unavailable"})

    report = _credit_report(
        0,
        usage,
        usage,
        {},
        "unavailable",
        f"Usage lookup status: {status}. Account information may be cached briefly.",
    )
    return {
        "answer": usage or "unavailable",
        "source": "Prospeo Account Information",
        "scope": {"usage_snapshot": status},
        "confidence": "verified" if usage else "blocked",
        "caveat": "Usage is summarized from Prospeo account-information.",
        "credit_report": report,
    }


if __name__ == "__main__":
    mcp.run("stdio")
