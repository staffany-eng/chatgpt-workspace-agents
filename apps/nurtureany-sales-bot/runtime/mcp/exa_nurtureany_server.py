#!/usr/bin/env python3
"""LinkedIn-safe Exa People Search MCP adapter for NurtureAny Sales Bot.

This server exposes only public people-discovery search. It does not fetch
profile contents, reveal contact details, mutate HubSpot, or bypass gated
social surfaces. It requires scoped HubSpot company inputs.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.scoped_company import scoped_company_error as _shared_scoped_company_error
from nurtureany_common.text import clean_domain as _clean_domain


EXA_BASE_URL = "https://api.exa.ai"
EXA_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
EXA_TIMEOUT_SECONDS = 15
MAX_SEARCH_COMPANIES = 5
MAX_CANDIDATES_PER_COMPANY = 5
MAX_TARGET_TITLES = 12
SCOPE_SOURCE = "hubspot_nurtureany"

COUNTRY_TO_USER_LOCATION = {
    "singapore": "SG",
    "malaysia": "MY",
    "indonesia": "ID",
}

DEFAULT_DECISION_MAKER_TITLES = [
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
    "exa_nurtureany",
    instructions=(
        "LinkedIn-safe Exa People Search tools for NurtureAny. Search public people "
        "candidates only, return cost reporting, and never reveal contact PII."
    ),
)


class ExaError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _token() -> str:
    token = os.environ.get("EXA_API_KEY", "").strip()
    if not token:
        raise ExaError("Missing EXA_API_KEY.")
    return token


def _request_json(body: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    url = urllib.parse.urljoin(EXA_BASE_URL, "/search")
    data = json.dumps(body).encode("utf-8")
    headers = {
        "x-api-key": _token(),
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": EXA_USER_AGENT,
    }
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=EXA_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return payload, _headers(response.headers)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        message = _error_message(error.code, detail)
        raise ExaError(message, error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise ExaError(f"Exa API request timed out or failed: {reason}") from error


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

    token = os.environ.get("EXA_API_KEY", "").strip()
    safe = str(message).replace(token, "[REDACTED_EXA_API_KEY]") if token else str(message)
    return f"Exa API failed: {status_code} {safe[:300]}"


def _scope(slack_user_email: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {"caller_email": (slack_user_email or "").strip().lower()}
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None, cost_report: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "Exa People Search",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
        "cost_report": cost_report or _cost_report([], "No Exa call completed.", 0),
    }


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else parsed


def _cost_report(company_costs: list[dict[str, Any]], caveat: str, request_count: int) -> dict[str, Any]:
    numeric_costs = [
        _number(item.get("actual_cost_usd"))
        for item in company_costs
        if _number(item.get("actual_cost_usd")) is not None
    ]
    actual_total: int | float | str
    if len(numeric_costs) == len(company_costs):
        total = sum(numeric_costs)
        actual_total = int(total) if float(total).is_integer() else total
    else:
        actual_total = "unavailable"

    return {
        "estimated_cost_usd": f"{request_count} Exa /search request(s); use current Exa dashboard pricing before run.",
        "actual_cost_usd": actual_total,
        "cost_dollars": {
            "total": actual_total,
            "by_company": company_costs,
        },
        "caveat": caveat,
    }


def _cost_item(company: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    cost = payload.get("costDollars") if isinstance(payload, dict) else None
    total = _number((cost or {}).get("total")) if isinstance(cost, dict) else None
    return {
        "input_company": company,
        "actual_cost_usd": total if total is not None else "unavailable",
        "raw_cost_dollars": cost or "unavailable",
    }


def _company_input(company: dict[str, Any]) -> dict[str, str]:
    country = str(company.get("country") or "Singapore").strip() or "Singapore"
    return {
        "company_id": str(company.get("company_id") or company.get("id") or "").strip(),
        "name": str(company.get("name") or company.get("company_name") or "").strip(),
        "domain": _clean_domain(str(company.get("domain") or company.get("company_domain") or "").strip()),
        "country": country,
        "user_location": _user_location(country),
    }


def _scoped_company_error(companies: list[dict[str, Any]]) -> str:
    return _shared_scoped_company_error(companies, "Exa paid enrichment", SCOPE_SOURCE, MAX_SEARCH_COMPANIES)


def _user_location(country: str) -> str:
    return COUNTRY_TO_USER_LOCATION.get(country.strip().lower(), "SG")


def _target_titles(target_titles: list[str] | None) -> list[str]:
    titles = [str(title).strip().lower() for title in (target_titles or []) if str(title).strip()]
    if not titles:
        titles = DEFAULT_DECISION_MAKER_TITLES
    seen: set[str] = set()
    deduped: list[str] = []
    for title in titles:
        if title not in seen:
            seen.add(title)
            deduped.append(title)
    return deduped[:MAX_TARGET_TITLES]


def _query(company: dict[str, str], titles: list[str]) -> str:
    company_label = company["name"] or company["domain"]
    title_text = ", ".join(titles)
    query = f'People who are {title_text} at "{company_label}" in {company["country"]}'
    if company["domain"]:
        query += f" company domain {company['domain']}"
    return query


def _search_payload(query: str, company: dict[str, str], limit: int) -> dict[str, Any]:
    return {
        "query": query,
        "category": "people",
        "type": "auto",
        "numResults": max(1, min(int(limit), MAX_CANDIDATES_PER_COMPANY)),
        "userLocation": company["user_location"],
    }


def _domain(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def _source_type(url: str, company_domain: str) -> str:
    domain = _domain(url)
    if not domain:
        return "unknown"
    if domain.endswith("linkedin.com") or ".linkedin.com" in domain:
        return "linkedin_manual_check"
    if domain.endswith(("instagram.com", "facebook.com", "tiktok.com")) or "google." in domain:
        return "social_or_gated_manual_check"
    if company_domain and (domain == company_domain or domain.endswith(f".{company_domain}")):
        return "company_public_profile"
    return "public_people_result"


def _inferred_name(title: str) -> str:
    clean = title.replace("| LinkedIn", "").replace("| Linkedin", "").strip()
    for separator in (" - ", " | ", " at "):
        if separator in clean:
            first = clean.split(separator, 1)[0].strip()
            return first if first else clean
    return clean


def _inferred_title(title: str) -> str:
    clean = title.replace("| LinkedIn", "").replace("| Linkedin", "").strip()
    if " - " in clean:
        parts = [part.strip() for part in clean.split(" - ") if part.strip()]
        if len(parts) >= 2:
            return parts[1]
    if " at " in clean:
        return clean.split(" at ", 1)[0].strip()
    return ""


def _decision_maker_match(title: str, target_titles: list[str]) -> dict[str, Any]:
    text = title.lower()
    matched = [target for target in target_titles if target in text]
    return {
        "matched": bool(matched),
        "matched_terms": matched,
    }


def _candidate(result: dict[str, Any], company: dict[str, str], target_titles: list[str], rank: int) -> dict[str, Any]:
    title = str(result.get("title") or "").strip()
    url = str(result.get("url") or result.get("id") or "").strip()
    return {
        "rank": rank,
        "input_company": company,
        "exa_result_id": result.get("id") or url,
        "title": title,
        "url": url,
        "source_domain": _domain(url),
        "source_type": _source_type(url, company["domain"]),
        "inferred_name": _inferred_name(title),
        "inferred_title": _inferred_title(title),
        "decision_maker_match": _decision_maker_match(title, target_titles),
        "confidence": "needs-check",
    }


@mcp.tool()
def search_exa_people_candidates(
    slack_user_email: str,
    companies: list[dict[str, Any]],
    target_titles: list[str] | None = None,
    limit_per_company: int = MAX_CANDIDATES_PER_COMPANY,
) -> dict[str, Any]:
    """Search Exa People Search for public decision-maker candidates."""

    titles = _target_titles(target_titles)
    scope = _scope(
        slack_user_email,
        {
            "requested_company_count": len(companies or []),
            "max_company_count": MAX_SEARCH_COMPANIES,
            "max_candidates_per_company": MAX_CANDIDATES_PER_COMPANY,
            "target_titles": titles,
            "safety": "No profile contents, email, phone, or HubSpot mutation.",
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
    except ExaError as error:
        return _blocked(str(error), scope)

    capped_limit = max(1, min(int(limit_per_company or MAX_CANDIDATES_PER_COMPANY), MAX_CANDIDATES_PER_COMPANY))
    candidates_by_company: list[dict[str, Any]] = []
    company_costs: list[dict[str, Any]] = []

    try:
        for company in selected_companies:
            query = _query(company, titles)
            payload = _search_payload(query, company, capped_limit)
            response, _ = _request_json(payload)
            results = response.get("results") or []
            company_costs.append(_cost_item(company, response))
            candidates = [
                _candidate(result, company, titles, rank)
                for rank, result in enumerate(results[:capped_limit], start=1)
            ]
            candidates_by_company.append(
                {
                    "input_company": company,
                    "query": query,
                    "exa_request_id": response.get("requestId") or "",
                    "returned_results": len(results),
                    "candidates": candidates,
                }
            )
    except ExaError as error:
        report = _cost_report(
            company_costs,
            "Search stopped early. Completed responses include Exa costDollars when available.",
            len(selected_companies),
        )
        return _blocked(str(error), scope, report)

    report = _cost_report(
        company_costs,
        "Exa costDollars are returned per response; no Exa Admin API billing lookup is used in V1.",
        len(selected_companies),
    )
    return {
        "answer": candidates_by_company,
        "source": "Exa People Search",
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Public people candidates only. LinkedIn/social URLs are manual-check evidence and were not fetched.",
        "cost_report": report,
    }


if __name__ == "__main__":
    mcp.run("stdio")
