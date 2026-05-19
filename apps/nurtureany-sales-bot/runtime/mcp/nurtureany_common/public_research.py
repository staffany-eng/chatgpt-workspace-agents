"""Shared public company research helpers for NurtureAny.

The module is intentionally read-only. It accepts only scoped HubSpot company
identity fields, sends only those fields to Tavily, and returns reviewable
signals instead of CRM truth.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

from nurtureany_common.text import clean_domain as _clean_domain


TAVILY_BASE_URL = "https://api.tavily.com"
TAVILY_USER_AGENT = "StaffAny-NurtureAny/1.0 public-company-research"
TAVILY_TIMEOUT_SECONDS = 20
SCOPE_SOURCE = "hubspot_nurtureany"
MAX_RESEARCH_COMPANIES = 5
MAX_BRAND_PARENT_SEARCH_RESULTS = 5
MAX_BRAND_PARENT_CANDIDATES = 5
PUBLIC_EVIDENCE_ITEM_LIMIT = 20
PUBLIC_FETCH_TIMEOUT_SECONDS = 5
PUBLIC_FETCH_MAX_BYTES = 30_000
SNIPPET_CHAR_LIMIT = 420
SIGNAL_EVIDENCE_CHAR_LIMIT = 240
PUBLIC_PEOPLE_CANDIDATE_LIMIT = 20
PUBLIC_CONTACT_CHANNEL_LIMIT = 20
PAYG_CREDIT_PRICE_USD = 0.008

FREE_SEARCH_SOURCE_TYPES = (
    "company_website",
    "company_careers",
    "public_job_board",
    "news_article",
    "general_web",
    "linkedin_manual",
    "google_maps_manual",
    "instagram_tiktok_manual",
    "facebook_manual",
    "review_site",
)
FETCHABLE_PUBLIC_SOURCE_TYPES = {"company_website", "company_careers", "public_job_board", "news_article", "general_web", "review_site"}
MANUAL_ONLY_HOST_MARKERS = (
    "linkedin.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "google.com",
    "maps.google.",
)

JOB_BOARD_HOST_MARKERS = (
    "mycareersfuture.gov.sg",
    "jobstreet.",
    "myfuturejobs.gov.my",
    "kalibrr.com",
    "indeed.",
    "glassdoor.",
)
REVIEW_HOST_MARKERS = ("glassdoor.", "tripadvisor.", "burpple.", "hungrygowhere.", "google.")
NEWS_HOST_MARKERS = ("news", "straitstimes.com", "channelnewsasia.com", "businesstimes.com.sg", "techinasia.com")
COUNTRY_JOB_BOARD_QUERIES = {
    "Singapore": "JobStreet OR Indeed OR Glints OR MyCareersFuture",
    "Malaysia": "JobStreet OR Indeed OR Maukerja OR Ricebowl OR MyFutureJobs",
    "Indonesia": "JobStreet OR Glints OR Kalibrr OR Dealls",
}
COMPANY_NAME_STOPWORDS = {
    "and",
    "cafe",
    "co",
    "company",
    "group",
    "holding",
    "holdings",
    "limited",
    "ltd",
    "pte",
    "restaurant",
    "restaurants",
    "sg",
    "singapore",
    "the",
}
PUBLIC_PEOPLE_ROLE_RE = (
    r"founder|co-founder|owner|business owner|ceo|chief executive officer|managing director|"
    r"general manager|operations director|operation director|hr director|people director|"
    r"finance director|admin(?:istrative)? manager"
)
PUBLIC_PERSON_NAME_RE = r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){0,3}"
PUBLIC_PERSON_NAME_STOPWORDS = {
    "Ameising Group",
    "Acme Cafe",
    "Nanyang Style",
    "Grand Opening",
    "Singapore",
}
PUBLIC_EMAIL_RE = r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
PUBLIC_PHONE_RE = r"(?:\+?65|\+?60|\+?62)?[\s().-]*(?:\d[\s().-]*){7,12}\d"

MODE_CONFIGS = {
    "light": {
        "search_depth": "basic",
        "query_count": 2,
        "max_results": 5,
        "extract_depth": "basic",
        "extract_url_cap": 1,
        "search_credit": 1,
        "extract_credit": 1,
    },
    "standard": {
        "search_depth": "basic",
        "query_count": 5,
        "max_results": 5,
        "extract_depth": "basic",
        "extract_url_cap": 4,
        "search_credit": 1,
        "extract_credit": 1,
    },
    "deep": {
        "search_depth": "advanced",
        "query_count": 2,
        "max_results": 8,
        "extract_depth": "basic",
        "extract_url_cap": 4,
        "search_credit": 2,
        "extract_credit": 1,
    },
}


class TavilyError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def research_cost_report(
    company_costs: list[dict[str, Any]] | None = None,
    caveat: str = "No Tavily call completed.",
    mode: str = "standard",
) -> dict[str, Any]:
    costs = company_costs or []
    estimated_credits = sum(int(item.get("estimated_credits") or 0) for item in costs)
    return {
        "mode": _research_mode(mode),
        "estimated_credits": estimated_credits,
        "estimated_cost_usd_payg": round(estimated_credits * PAYG_CREDIT_PRICE_USD, 4),
        "actual_cost_usd": "unavailable" if costs else 0,
        "by_company": costs,
        "credit_assumptions": {
            "basic_search": 1,
            "advanced_search": 2,
            "basic_extract_per_successful_url": 1,
            "payg_credit_price_usd": PAYG_CREDIT_PRICE_USD,
        },
        "caveat": caveat,
    }


def _research_mode(mode: str) -> str:
    normalized = str(mode or "standard").strip().lower()
    return normalized if normalized in MODE_CONFIGS else "standard"


def mode_credit_cap(mode: str) -> int:
    config = MODE_CONFIGS[_research_mode(mode)]
    return (config["query_count"] * config["search_credit"]) + (config["extract_url_cap"] * config["extract_credit"])


def company_input_items(companies: Any) -> list[dict[str, Any]]:
    if companies is None:
        return []
    if hasattr(companies, "model_dump"):
        return company_input_items(companies.model_dump())
    if isinstance(companies, Mapping):
        nested_companies = companies.get("companies")
        if nested_companies is not None and nested_companies is not companies:
            return company_input_items(nested_companies)
        return [dict(companies)]
    if isinstance(companies, Sequence) and not isinstance(companies, (str, bytes, bytearray)):
        items: list[dict[str, Any]] = []
        for company in companies:
            if hasattr(company, "model_dump"):
                company = company.model_dump()
            if isinstance(company, Mapping):
                items.append(dict(company))
        return items
    return []


def clean_company_input(company: dict[str, Any]) -> dict[str, str]:
    return {
        "company_id": str(company.get("company_id") or company.get("id") or "").strip(),
        "name": _short_text(str(company.get("name") or company.get("company_name") or ""), 120),
        "domain": _clean_domain(str(company.get("domain") or company.get("company_domain") or "")),
        "country": _short_text(str(company.get("country") or "Singapore"), 80) or "Singapore",
    }


def _request_json(endpoint: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    url = urllib.parse.urljoin(TAVILY_BASE_URL, endpoint)
    data = json.dumps(body).encode("utf-8")
    headers = {
        "authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": TAVILY_USER_AGENT,
    }
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=TAVILY_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise TavilyError(_error_message(error.code, detail, token), error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise TavilyError(f"Tavily API request timed out or failed: {reason}") from error


def _error_message(status_code: int, detail: str, token: str) -> str:
    safe = str(detail or "")
    if token:
        safe = safe.replace(token, "[REDACTED_TAVILY_API_KEY]")
    try:
        parsed = json.loads(safe)
        error = parsed.get("error") or parsed
        if isinstance(error, dict):
            message = error.get("message") or error.get("detail") or safe
        else:
            message = str(error or safe)
    except json.JSONDecodeError:
        message = safe
    return f"Tavily API failed: {status_code} {message[:300]}"


def search_payload(query: str, mode: str, max_results: int | None = None) -> dict[str, Any]:
    config = MODE_CONFIGS[_research_mode(mode)]
    result_cap = max(1, min(int(max_results or config["max_results"]), config["max_results"]))
    return {
        "query": query,
        "search_depth": config["search_depth"],
        "max_results": result_cap,
        "include_answer": False,
        "include_raw_content": False,
        "include_images": False,
        "topic": "general",
    }


def extract_payload(urls: list[str], mode: str) -> dict[str, Any]:
    config = MODE_CONFIGS[_research_mode(mode)]
    selected = urls[: config["extract_url_cap"]]
    return {
        "urls": selected,
        "extract_depth": config["extract_depth"],
        "format": "markdown",
        "include_images": False,
    }


def company_queries(company: dict[str, str], mode: str) -> list[str]:
    label = company.get("name") or company.get("domain")
    country = company.get("country", "")
    domain = company.get("domain", "")
    job_boards = COUNTRY_JOB_BOARD_QUERIES.get(country, "JobStreet OR Indeed OR Glints")
    base = [
        f'"{label}" {country} official website contact phone email WhatsApp booking',
        f'"{label}" {country} outlet phone email reservation booking',
        f'"{label}" careers hiring jobs HR {country}',
        f'"{label}" {country} {job_boards} HR operations admin jobs',
        f'"{label}" payroll scheduling manpower HR owner founder operations {country}',
        f'"{label}" {country} news opening expansion founder owner',
    ]
    if domain:
        base.insert(1, f'site:{domain} contact phone email WhatsApp booking careers hiring')
    return [re.sub(r"\s+", " ", query).strip() for query in base if query.strip()][: MODE_CONFIGS[_research_mode(mode)]["query_count"]]


def brand_parent_queries(brand_name: str, country: str) -> list[str]:
    brand = _short_text(str(brand_name or "").strip(), 120)
    market = _short_text(str(country or "Singapore").strip(), 80) or "Singapore"
    base = [
        f'"{brand}" "{market}" owner group parent company',
        f'"{brand}" "{market}" "our brands"',
        f'"{brand}" "{market}" "behind" "brand"',
        f'"{brand}" "{market}" "Company Name"',
    ]
    return [re.sub(r"\s+", " ", query).strip() for query in base if brand and query.strip()]


def brand_parent_lookup_cost_report(brand_name: str, country: str, query_count: int, caveat: str = "") -> dict[str, Any]:
    by_lookup = [
        {
            "input_brand": _short_text(str(brand_name or "").strip(), 120),
            "country": _short_text(str(country or "Singapore").strip(), 80) or "Singapore",
            "search_request_count": query_count,
            "extract_url_count": 0,
            "estimated_credits": query_count,
            "credit_cap_for_mode": query_count,
        }
    ] if query_count else []
    return research_cost_report(
        by_lookup,
        caveat or "Estimated from Tavily Search credit rules; no Tavily Extract call is used for brand-parent identity lookup.",
        "light",
    )


def find_brand_parent_candidates(
    brand_name: str,
    token: str,
    country: str = "Singapore",
    max_results_per_query: int | None = None,
) -> dict[str, Any]:
    """Find public parent/group name candidates for an unresolved brand.

    This is an identity-resolution helper only. It does not produce outreach
    research and does not grant account scope. Callers must re-query HubSpot
    with the returned parent/group names and continue only after a scoped
    target account is found.
    """

    brand = _short_text(str(brand_name or "").strip(), 120)
    market = _short_text(str(country or "Singapore").strip(), 80) or "Singapore"
    queries = brand_parent_queries(brand, market)
    source_evidence: list[dict[str, Any]] = []
    candidate_by_key: dict[str, dict[str, Any]] = {}

    for query in queries:
        response = _request_json("/search", token, search_payload(query, "light", max_results_per_query or MAX_BRAND_PARENT_SEARCH_RESULTS))
        for raw_result in response.get("results") or []:
            result = _normalize_brand_parent_search_result(raw_result, query)
            if not _brand_mentioned(result, brand):
                continue
            source_evidence.append(result)
            for candidate in _parent_candidates_from_result(result, brand):
                key = _parent_candidate_key(candidate)
                if not key:
                    continue
                item = candidate_by_key.setdefault(
                    key,
                    {
                        "name": candidate,
                        "confidence": "needs-check",
                        "suggested_hubspot_queries": _suggested_parent_queries(candidate),
                        "evidence": [],
                    },
                )
                if len(item["evidence"]) < 3:
                    item["evidence"].append(
                        {
                            "source_url": result["source_url"],
                            "title": result["title"],
                            "snippet": result["snippet"],
                            "query": result["query"],
                            "source_type": result["source_type"],
                        }
                    )

    candidates = sorted(
        candidate_by_key.values(),
        key=lambda item: (-len(item["evidence"]), _normalize_relevance_text(item["name"])),
    )[:MAX_BRAND_PARENT_CANDIDATES]
    missing_evidence = [] if candidates else [f"No public parent/group candidate found for {brand} in {market}."]
    return {
        "answer": {
            "brand_name": brand,
            "country": market,
            "parent_candidates": candidates,
            "candidate_count": len(candidates),
            "hubspot_next_step": (
                "Re-query the caller's scoped HubSpot target accounts with each suggested_hubspot_queries value. "
                "Continue public news research only after one candidate resolves to a scoped target account."
            ),
        },
        "source_evidence": source_evidence[:PUBLIC_EVIDENCE_ITEM_LIMIT],
        "manual_check_items": [
            {
                "source_type": item["source_type"],
                "source_url": item["source_url"],
                "title": item["title"],
                "reason": "Brand-parent identity evidence; verify against scoped HubSpot before outreach research.",
            }
            for item in source_evidence[:10]
            if item["source_type"] not in FETCHABLE_PUBLIC_SOURCE_TYPES
        ],
        "missing_evidence": missing_evidence,
        "cost_report": brand_parent_lookup_cost_report(
            brand,
            market,
            len(queries),
            "Estimated from Tavily Search credit rules; no Tavily Extract call is used for brand-parent identity lookup.",
        ),
        "confidence": "needs-check" if candidates else "blocked",
        "caveat": (
            "Brand-parent lookup is identity resolution only. Public evidence does not override HubSpot; "
            "HubSpot target-account scope must be re-checked before news research or drafting."
        ),
        "will_mutate_hubspot": False,
    }


def research_public_company_signals(
    companies: Any,
    token: str,
    research_mode: str = "standard",
    max_results_per_query: int | None = None,
) -> dict[str, Any]:
    mode = _research_mode(research_mode)
    raw_companies = company_input_items(companies)[:MAX_RESEARCH_COMPANIES]
    selected_companies = [clean_company_input(company) for company in raw_companies]
    selected_companies = [company for company in selected_companies if company["company_id"] and (company["name"] or company["domain"])]

    company_outputs: list[dict[str, Any]] = []
    source_evidence: list[dict[str, Any]] = []
    company_signals: list[dict[str, Any]] = []
    public_people_candidates: list[dict[str, Any]] = []
    public_contact_channels: list[dict[str, Any]] = []
    game_plan_inputs: list[dict[str, Any]] = []
    manual_check_items: list[dict[str, Any]] = []
    missing_evidence: list[str] = []
    company_costs: list[dict[str, Any]] = []

    for company in selected_companies:
        search_results: list[dict[str, Any]] = []
        queries = company_queries(company, mode)
        for query in queries:
            response = _request_json("/search", token, search_payload(query, mode, max_results_per_query))
            results = response.get("results") or []
            search_results.extend(_normalize_search_result(result, company, query) for result in results)

        unique_results = [
            result
            for result in _dedupe_results(search_results)
            if result.get("company_relevance") != "unrelated"
        ]
        extract_urls = _extractable_urls(unique_results, company, mode)
        extracted_text_by_url = _extract_text(token, extract_urls, mode) if extract_urls else {}

        company_evidence: list[dict[str, Any]] = []
        company_signal_rows: list[dict[str, Any]] = []
        company_people_candidates: list[dict[str, Any]] = []
        company_contact_channels: list[dict[str, Any]] = []
        company_manual_checks: list[dict[str, Any]] = []

        for result in unique_results:
            source_type = result["source_type"]
            source_url = result["source_url"]
            extract_text = extracted_text_by_url.get(source_url, "")
            fetch_status = "manual_check_only" if result["requires_manual_review"] else ("tavily_extracted" if extract_text else "tavily_search_only")
            signals = extract_company_signals(result, source_type, source_url, extract_text)
            people_candidates = extract_public_people_candidates(result, source_type, source_url, extract_text)
            contact_channels = extract_public_contact_channels(result, source_type, source_url, extract_text)
            for signal in signals:
                signal["company_id"] = company["company_id"]
                signal["company_name"] = company["name"]
            for candidate in people_candidates:
                candidate["company_id"] = company["company_id"]
                candidate["company"] = company["name"]
                candidate["company_name"] = company["name"]
            for channel in contact_channels:
                channel["company_id"] = company["company_id"]
                channel["company_name"] = company["name"]
            evidence = {
                "company_id": company["company_id"],
                "company_name": company["name"],
                "source_type": source_type,
                "source_url": source_url,
                "title": result["title"],
                "snippet": result["snippet"],
                "query": result["query"],
                "tavily_score": result.get("score"),
                "company_relevance": result.get("company_relevance"),
                "relevance_reason": result.get("relevance_reason"),
                "fetch_status": fetch_status,
                "signals_found": [signal["signal_type"] for signal in signals],
                "requires_manual_review": result["requires_manual_review"],
            }
            company_evidence.append(evidence)
            company_signal_rows.extend(signals)
            company_people_candidates.extend(people_candidates)
            company_contact_channels.extend(contact_channels)
            if result["requires_manual_review"]:
                company_manual_checks.append(
                    manual_check_item(company, source_url, result["title"], source_type, "social_gated_or_manual_source")
                )

        company_missing = _missing_evidence(company, company_signal_rows, company_evidence)
        next_tool = "search_exa_people_candidates" if _needs_people_candidates(company_signal_rows) else ""
        game_inputs = game_plan_input(company, company_signal_rows, company_evidence, company_manual_checks, company_missing, next_tool)

        source_evidence.extend(company_evidence[:PUBLIC_EVIDENCE_ITEM_LIMIT])
        company_signals.extend(company_signal_rows[:20])
        public_people_candidates.extend(company_people_candidates[:PUBLIC_PEOPLE_CANDIDATE_LIMIT])
        public_contact_channels.extend(company_contact_channels[:PUBLIC_CONTACT_CHANNEL_LIMIT])
        manual_check_items.extend(company_manual_checks[:10])
        missing_evidence.extend(company_missing)
        game_plan_inputs.append(game_inputs)
        company_outputs.append(
            {
                "input_company": company,
                "company_signals": company_signal_rows[:20],
                "public_people_candidates": company_people_candidates[:PUBLIC_PEOPLE_CANDIDATE_LIMIT],
                "public_contact_channels": company_contact_channels[:PUBLIC_CONTACT_CHANNEL_LIMIT],
                "source_evidence": company_evidence[:PUBLIC_EVIDENCE_ITEM_LIMIT],
                "game_plan_inputs": game_inputs,
                "manual_check_items": company_manual_checks[:10],
                "missing_evidence": company_missing,
                "recommended_next_tool": next_tool,
                "will_mutate_hubspot": False,
            }
        )
        company_costs.append(
            {
                "input_company": company,
                "search_request_count": len(queries),
                "extract_url_count": len(extract_urls),
                "estimated_credits": (len(queries) * MODE_CONFIGS[mode]["search_credit"])
                + (len(extract_urls) * MODE_CONFIGS[mode]["extract_credit"]),
                "credit_cap_for_mode": mode_credit_cap(mode),
            }
        )

    deduped_missing = sorted(set(missing_evidence))
    return {
        "answer": company_outputs,
        "company_signals": company_signals[:60],
        "public_people_candidates": public_people_candidates[: MAX_RESEARCH_COMPANIES * PUBLIC_PEOPLE_CANDIDATE_LIMIT],
        "public_contact_channels": public_contact_channels[: MAX_RESEARCH_COMPANIES * PUBLIC_CONTACT_CHANNEL_LIMIT],
        "source_evidence": source_evidence[: MAX_RESEARCH_COMPANIES * PUBLIC_EVIDENCE_ITEM_LIMIT],
        "game_plan_inputs": game_plan_inputs,
        "manual_check_items": manual_check_items[:50],
        "missing_evidence": deduped_missing,
        "cost_report": research_cost_report(
            company_costs,
            "Estimated from Tavily search/extract credit rules; Tavily responses do not expose account billing totals in this adapter.",
            mode,
        ),
        "confidence": "needs-check",
        "caveat": (
            "Public evidence is review-only and never overrides HubSpot. Social/gated sources stay manual-check. "
            "No HubSpot mutation or external message send was performed."
        ),
        "will_mutate_hubspot": False,
    }


def _normalize_search_result(result: dict[str, Any], company: dict[str, str], query: str) -> dict[str, Any]:
    source_url = str(result.get("url") or "").strip()
    source_type = source_type_for_url(source_url, company.get("domain", ""))
    normalized = {
        "source_url": source_url,
        "source_type": source_type,
        "title": _short_text(str(result.get("title") or ""), 180),
        "snippet": _short_text(str(result.get("content") or result.get("snippet") or result.get("description") or ""), SNIPPET_CHAR_LIMIT),
        "query": query,
        "score": result.get("score"),
        "requires_manual_review": source_type not in FETCHABLE_PUBLIC_SOURCE_TYPES or _is_manual_only_host(source_url),
    }
    relevance, reason = _company_relevance(normalized, company)
    normalized["company_relevance"] = relevance
    normalized["relevance_reason"] = reason
    return normalized


def _normalize_brand_parent_search_result(result: dict[str, Any], query: str) -> dict[str, Any]:
    source_url = str(result.get("url") or "").strip()
    return {
        "source_url": source_url,
        "source_type": source_type_for_url(source_url, ""),
        "title": _short_text(str(result.get("title") or ""), 180),
        "snippet": _short_text(str(result.get("content") or result.get("snippet") or result.get("description") or ""), SNIPPET_CHAR_LIMIT),
        "query": query,
        "tavily_score": result.get("score"),
        "requires_manual_review": source_type_for_url(source_url, "") not in FETCHABLE_PUBLIC_SOURCE_TYPES or _is_manual_only_host(source_url),
    }


def _brand_mentioned(result: dict[str, Any], brand_name: str) -> bool:
    brand_text = _normalize_relevance_text(brand_name)
    if not brand_text:
        return False
    haystack = _normalize_relevance_text(
        " ".join(
            str(part or "")
            for part in [
                result.get("title"),
                result.get("snippet"),
                result.get("source_url"),
            ]
        )
    )
    if brand_text in haystack:
        return True
    brand_tokens = _company_name_tokens(brand_name)
    matched = [token for token in brand_tokens if token in haystack]
    return len(matched) >= min(2, len(brand_tokens)) if brand_tokens else False


_PARENT_ENTITY_RE = r"[A-Z0-9][A-Za-z0-9&'().,/ -]{2,100}?(?:Pte\.?\s*Ltd\.?|Private\s+Limited|Sdn\.?\s*Bhd\.?|Group|Holdings?|Kompany|Company)"


def _parent_candidates_from_result(result: dict[str, Any], brand_name: str) -> list[str]:
    title = str(result.get("title") or "")
    snippet = str(result.get("snippet") or "")
    text = html.unescape(f"{title}. {snippet}")
    brand_pattern = re.escape(str(brand_name or "").strip())
    candidates: list[str] = []

    company_label = re.search(r"(?:Company|Employer|Hiring\s+company)\s*[:|]\s*(?P<name>[^|.\n]{2,110})", text, flags=re.I)
    if company_label:
        _append_candidate(candidates, company_label.group("name"))

    patterns = [
        rf"(?P<name>{_PARENT_ENTITY_RE})[^.\n]{{0,180}}(?:our\s+brands?|brands?\s*(?:include|including|like|behind)|behind)[^.\n]{{0,180}}{brand_pattern}",
        rf"{brand_pattern}[^.\n]{{0,180}}(?:owned\s+by|under|part\s+of|from|by|behind)[^.\n]{{0,40}}(?P<name>{_PARENT_ENTITY_RE})",
        rf"(?P<name>{_PARENT_ENTITY_RE})[^.\n]{{0,180}}(?:team\s+behind|behind\s+one|behind\s+some)[^.\n]{{0,180}}{brand_pattern}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            _append_candidate(candidates, match.group("name"))

    normalized_text = _normalize_relevance_text(text)
    if "brand" in normalized_text and _brand_mentioned(result, brand_name):
        title_head = re.split(r"\s+[|-]\s+", title, maxsplit=1)[0]
        if re.search(_PARENT_ENTITY_RE, title_head, flags=re.I):
            _append_candidate(candidates, title_head)
        host_candidate = _candidate_from_host(result.get("source_url", ""))
        if host_candidate:
            _append_candidate(candidates, host_candidate)

    return candidates[:MAX_BRAND_PARENT_CANDIDATES]


def _append_candidate(candidates: list[str], value: str) -> None:
    candidate = _clean_parent_candidate(value)
    if not candidate:
        return
    key = _parent_candidate_key(candidate)
    if key and all(_parent_candidate_key(existing) != key for existing in candidates):
        candidates.append(candidate)


def _clean_parent_candidate(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^(?:Company|Employer|Hiring company)\s*[:|]\s*", "", text, flags=re.I)
    text = text.strip(" -:|,.;")
    text = re.sub(r"\s+(?:in|at)\s+\d{3,}.*$", "", text, flags=re.I)
    text = re.sub(r"\s+-\s+.*$", "", text)
    text = re.sub(r"\s+\|\s+.*$", "", text)
    if not text or len(text) < 3:
        return ""
    return _short_text(text, 120)


def _candidate_from_host(url: str) -> str:
    host = _host(url)
    if not host:
        return ""
    stem = host.split(".")[0]
    if stem.startswith("www"):
        parts = host.split(".")
        stem = parts[1] if len(parts) > 1 else stem
    if not stem or stem in {"facebook", "linkedin", "instagram", "tiktok", "google"}:
        return ""
    spaced = re.sub(r"(?i)^the", "The ", stem)
    spaced = re.sub(r"(?i)(kompany|company|group|holdings?)$", r" \1", spaced)
    spaced = re.sub(r"[-_]+", " ", spaced)
    if len(spaced.split()) == 1 and len(spaced) > 14:
        return ""
    return " ".join(part.capitalize() if part.lower() not in {"pte", "ltd"} else part.upper() for part in spaced.split())


def _parent_candidate_key(value: str) -> str:
    text = _normalize_relevance_text(value)
    text = re.sub(r"\b(?:pte|ltd|private|limited|sdn|bhd|company|co)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace(" ", "")


def _suggested_parent_queries(candidate: str) -> list[str]:
    cleaned = _clean_parent_candidate(candidate)
    if not cleaned:
        return []
    variants = [cleaned]
    without_legal = re.sub(
        r"\b(?:pte\.?\s*ltd\.?|private\s+limited|sdn\.?\s*bhd\.?|ltd\.?|limited)\b\.?",
        "",
        cleaned,
        flags=re.I,
    )
    without_legal = re.sub(r"\s+", " ", without_legal).strip(" -:|,.;")
    without_leading_the = re.sub(r"^the\s+", "", without_legal, flags=re.I).strip()
    for variant in [without_legal, without_leading_the]:
        if variant and all(_normalize_relevance_text(variant) != _normalize_relevance_text(existing) for existing in variants):
            variants.append(variant)
    return variants[:3]


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for result in results:
        url = result.get("source_url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(result)
    return deduped


def _company_relevance(result: dict[str, Any], company: dict[str, str]) -> tuple[str, str]:
    url = str(result.get("source_url") or "")
    host = _host(url)
    company_domain = company.get("domain", "")
    if company_domain and (host == company_domain or host.endswith(f".{company_domain}")):
        return "company_domain", "host_matches_company_domain"

    text = _normalize_relevance_text(
        " ".join(
            str(part or "")
            for part in [
                result.get("title"),
                result.get("snippet"),
                url,
            ]
        )
    )
    name = _normalize_relevance_text(company.get("name", ""))
    if name and len(name) >= 5 and name in text:
        return "company_name", "title_or_snippet_mentions_company_name"

    domain_tokens = _domain_tokens(company_domain)
    for token in domain_tokens:
        if token and token in text:
            return "company_domain_token", "title_or_snippet_mentions_company_domain_token"

    name_tokens = _company_name_tokens(company.get("name", ""))
    matched = [token for token in name_tokens if token in text]
    if len(matched) >= 2:
        return "company_name_tokens", "title_or_snippet_mentions_multiple_company_tokens"
    if len(matched) == 1 and len(matched[0]) >= 6:
        return "company_name_token", "title_or_snippet_mentions_distinctive_company_token"

    return "unrelated", "title_snippet_url_do_not_match_company_identity"


def _normalize_relevance_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def _company_name_tokens(name: str) -> list[str]:
    tokens = []
    for token in _normalize_relevance_text(name).split():
        if len(token) < 3 or token in COMPANY_NAME_STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _domain_tokens(domain: str) -> list[str]:
    host = _clean_domain(domain)
    if not host:
        return []
    stem = host.split(".")[0]
    tokens = [token for token in re.split(r"[^a-z0-9]+", stem.lower()) if len(token) >= 4]
    if stem and len(stem) >= 4:
        tokens.insert(0, stem.lower())
    deduped = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped


def _extractable_urls(results: list[dict[str, Any]], company: dict[str, str], mode: str) -> list[str]:
    urls = []
    for result in results:
        url = result.get("source_url", "")
        if result.get("requires_manual_review"):
            continue
        if not is_public_url(url) or _is_manual_only_host(url):
            continue
        urls.append(url)
    company_domain = company.get("domain", "")
    urls.sort(key=lambda url: _extract_priority(url, company_domain))
    return urls[: MODE_CONFIGS[_research_mode(mode)]["extract_url_cap"]]


def _extract_priority(url: str, company_domain: str) -> tuple[int, str]:
    parsed = urllib.parse.urlparse(url)
    host = _host(url)
    path = parsed.path.lower()
    full = f"{host}{path}".lower()
    if company_domain and host.endswith(company_domain) and any(part in full for part in ("contact", "reservation", "booking", "whatsapp")):
        return (0, url)
    if company_domain and host.endswith(company_domain):
        return (1, url)
    if any(marker in host for marker in JOB_BOARD_HOST_MARKERS):
        return (2, url)
    if any(marker in full for marker in ("contact", "reservation", "booking", "whatsapp", "phone")):
        return (3, url)
    if any(marker in host for marker in NEWS_HOST_MARKERS):
        return (4, url)
    return (5, url)


def _extract_text(token: str, urls: list[str], mode: str) -> dict[str, str]:
    response = _request_json("/extract", token, extract_payload(urls, mode))
    rows = response.get("results") or response.get("successful_results") or []
    text_by_url: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        text = str(row.get("raw_content") or row.get("content") or row.get("text") or "").strip()
        if url and text:
            text_by_url[url] = _short_text(text, 2000)
    return text_by_url


def source_type_for_url(url: str, company_domain: str = "") -> str:
    host = _host(url)
    path = urllib.parse.urlparse(url).path.lower()
    if not host:
        return "general_web"
    if "linkedin.com" in host:
        return "linkedin_manual"
    if "instagram.com" in host or "tiktok.com" in host:
        return "instagram_tiktok_manual"
    if "facebook.com" in host:
        return "facebook_manual"
    if "google.com" in host or "maps.google." in host:
        return "google_maps_manual"
    if any(marker in host for marker in JOB_BOARD_HOST_MARKERS):
        return "public_job_board"
    if any(marker in host for marker in REVIEW_HOST_MARKERS):
        return "review_site"
    if any(marker in host for marker in NEWS_HOST_MARKERS):
        return "news_article"
    if company_domain and (host == company_domain or host.endswith(f".{company_domain}")):
        if any(part in path for part in ("career", "job", "join-us", "work-with-us", "hiring")):
            return "company_careers"
        return "company_website"
    return "general_web"


def manual_check_item(company: dict[str, str], url: str, title: str, source_type: str, reason: str) -> dict[str, Any]:
    return {
        "company_id": company.get("company_id"),
        "company_name": company.get("name"),
        "source_type": source_type,
        "source_url": url,
        "title": _short_text(title, 180),
        "reason": reason,
        "instruction": "Review manually only; do not scrape, use cookies, browser automation, or bypass gated/social surfaces.",
    }


def game_plan_input(
    company: dict[str, str],
    signals: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    manual_checks: list[dict[str, Any]],
    missing_evidence: list[str],
    recommended_next_tool: str = "",
) -> dict[str, Any]:
    return {
        "company_id": company.get("company_id"),
        "company_name": company.get("name"),
        "public_signals": signals[:10],
        "source_evidence_refs": [
            {
                "source_type": item["source_type"],
                "source_url": item["source_url"],
                "title": item["title"],
                "signals_found": item.get("signals_found", []),
            }
            for item in evidence[:10]
        ],
        "outreach_angles": outreach_angles(signals, []),
        "manual_checks_needed": [
            {
                "source_type": item["source_type"],
                "source_url": item["source_url"],
                "reason": item["reason"],
            }
            for item in manual_checks[:6]
        ],
        "missing_evidence": missing_evidence,
        "recommended_next_tool": recommended_next_tool,
        "rule": "Use as research/stalking signal only; HubSpot remains source of truth.",
        "will_mutate_hubspot": False,
    }


def _missing_evidence(company: dict[str, str], signals: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[str]:
    signal_types = {signal.get("signal_type") for signal in signals}
    missing = []
    if not evidence:
        missing.append(f"{company.get('name') or company.get('company_id')}: no public web result returned")
    if "hiring_signal" not in signal_types and "growth_signal" not in signal_types:
        missing.append(f"{company.get('name') or company.get('company_id')}: no hiring/growth signal found")
    if "decision_maker_hint" not in signal_types:
        missing.append(f"{company.get('name') or company.get('company_id')}: no public decision-maker hint found")
    return missing


def _needs_people_candidates(signals: list[dict[str, Any]]) -> bool:
    return not any(signal.get("signal_type") == "decision_maker_hint" for signal in signals)


def is_public_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        if "." not in host:
            return False
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    return True


def _is_manual_only_host(url: str) -> bool:
    host = _host(url)
    return any(marker in host for marker in MANUAL_ONLY_HOST_MARKERS)


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_public_evidence_text(source_type: str, url: str) -> tuple[str, str]:
    if source_type not in FETCHABLE_PUBLIC_SOURCE_TYPES:
        return "", "skipped_manual_source"
    if not url:
        return "", "skipped_no_url"
    if not is_public_url(url) or _is_manual_only_host(url):
        return "", "skipped_unsafe_or_manual_url"
    request = urllib.request.Request(
        url,
        headers={
            "accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
            "user-agent": TAVILY_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=PUBLIC_FETCH_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return "", "skipped_unsupported_content_type"
            raw = response.read(PUBLIC_FETCH_MAX_BYTES + 1)
            status = "fetched_truncated" if len(raw) > PUBLIC_FETCH_MAX_BYTES else "fetched"
            text = html_to_text(raw[:PUBLIC_FETCH_MAX_BYTES].decode("utf-8", errors="replace"))
            return text, status
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return "", f"fetch_failed:{str(error)[:80]}"


def extract_company_signals(item: dict[str, Any], source_type: str, source_url: str, fetched_text: str) -> list[dict[str, Any]]:
    search_text = " ".join(
        str(part or "")
        for part in [
            item.get("title"),
            item.get("snippet"),
            item.get("content"),
            item.get("description"),
        ]
    )
    text = " ".join([search_text, fetched_text])
    # Generic directories often contain unrelated footer/navigation words like
    # "job opening" or "new outlet". Use extracted page text only for sources
    # whose type is already meaningfully tied to the company or market event.
    default_signal_text = search_text if source_type == "general_web" else text
    signal_keywords = {
        "hiring_signal": ("hiring", "vacancy", "recruit", "join our team", "open role", "job opening", "jobs available"),
        "growth_signal": ("new outlet", "opening soon", "grand opening", "new branch", "expanding", "expansion", "launch", "coming soon"),
        "pain_signal": ("manpower", "understaffed", "turnover", "attendance", "payroll", "scheduling", "retention"),
        "news_signal": ("award", "funding", "partnership", "franchise", "announced", "featured"),
        "decision_maker_hint": ("founder", "ceo", "managing director", "general manager", "hr director", "people director"),
    }
    signals = []
    for signal_type, keywords in signal_keywords.items():
        signal_text = text if signal_type == "decision_maker_hint" else default_signal_text
        lowered = signal_text.lower()
        if signal_type == "news_signal" and re.search(r"\bno\s+(recent\s+)?news\b|\bno\s+news\s+articles\b", lowered):
            continue
        matched = [keyword for keyword in keywords if keyword in lowered]
        if matched:
            signals.append(
                {
                    "signal_type": signal_type,
                    "keywords": matched[:5],
                    "source_type": source_type,
                    "source_url": source_url,
                    "evidence": _short_text(
                        str(item.get("snippet") or fetched_text or item.get("title") or ""),
                        SIGNAL_EVIDENCE_CHAR_LIMIT,
                    ),
                    "confidence": "needs-check",
                }
            )
    return signals


def extract_public_people_candidates(
    item: dict[str, Any],
    source_type: str,
    source_url: str,
    fetched_text: str,
) -> list[dict[str, Any]]:
    if source_type not in FETCHABLE_PUBLIC_SOURCE_TYPES or _is_manual_only_host(source_url):
        return []
    text = html.unescape(
        " ".join(
            str(part or "")
            for part in [
                item.get("title"),
                item.get("snippet"),
                fetched_text,
            ]
        )
    )
    if not text:
        return []
    candidates: list[dict[str, Any]] = []
    patterns = (
        rf"\b(?P<title>{PUBLIC_PEOPLE_ROLE_RE})\b[^.\n]{{0,80}}?,\s*(?P<name>{PUBLIC_PERSON_NAME_RE})",
        rf"\b(?P<title>{PUBLIC_PEOPLE_ROLE_RE})\b\s*(?:,|:|-|–|by|is|as)?\s+(?P<name>{PUBLIC_PERSON_NAME_RE})",
        rf"(?P<name>{PUBLIC_PERSON_NAME_RE})\s*(?:,|-|–|\()\s*(?P<title>{PUBLIC_PEOPLE_ROLE_RE})\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            title = _clean_public_person_title(match.group("title"))
            name = _clean_public_person_name(match.group("name"))
            if not name or not title:
                continue
            key = _normalize_relevance_text(f"{name} {title}")
            if any(_normalize_relevance_text(f"{candidate.get('name')} {candidate.get('title')}") == key for candidate in candidates):
                continue
            candidates.append(
                {
                    "name": name,
                    "title": title,
                    "source_type": source_type,
                    "source_url": source_url,
                    "company_match": "needs-check",
                    "confidence_band": "medium",
                    "evidence_refs": [
                        {
                            "source": "public_extract",
                            "url": source_url,
                            "title": _short_text(str(item.get("title") or ""), 180),
                        }
                    ],
                    "warnings": ["public extract candidate; verify current role before HubSpot writeback"],
                }
            )
            if len(candidates) >= PUBLIC_PEOPLE_CANDIDATE_LIMIT:
                return candidates
    return candidates


def extract_public_contact_channels(
    item: dict[str, Any],
    source_type: str,
    source_url: str,
    fetched_text: str,
) -> list[dict[str, Any]]:
    if source_type not in FETCHABLE_PUBLIC_SOURCE_TYPES or _is_manual_only_host(source_url):
        return []
    text = html.unescape(
        " ".join(
            str(part or "")
            for part in [
                item.get("title"),
                item.get("snippet"),
                fetched_text,
            ]
        )
    )
    if not text:
        return []
    channels: list[dict[str, Any]] = []
    for email in re.findall(PUBLIC_EMAIL_RE, text, flags=re.I):
        normalized = email.lower()
        if normalized.endswith((".png", ".jpg", ".jpeg", ".gif")):
            continue
        _append_public_channel(channels, "public_company_email", normalized, source_type, source_url, item)
    for raw_phone in re.findall(PUBLIC_PHONE_RE, text):
        normalized = _clean_public_phone(raw_phone)
        if not normalized:
            continue
        _append_public_channel(channels, "public_company_phone", normalized, source_type, source_url, item)
    return channels[:PUBLIC_CONTACT_CHANNEL_LIMIT]


def _append_public_channel(
    channels: list[dict[str, Any]],
    channel_type: str,
    value: str,
    source_type: str,
    source_url: str,
    item: dict[str, Any],
) -> None:
    key = _normalize_relevance_text(f"{channel_type} {value}")
    if any(_normalize_relevance_text(f"{channel.get('channel_type')} {channel.get('value')}") == key for channel in channels):
        return
    channels.append(
        {
            "channel_type": channel_type,
            "value": value,
            "source_type": source_type,
            "source_url": source_url,
            "title": _short_text(str(item.get("title") or ""), 180),
            "confidence": "needs-check",
            "usage": "public company channel only; not a personal provider reveal",
        }
    )


def _clean_public_phone(value: str) -> str:
    text = re.sub(r"[^\d+]", "", str(value or ""))
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) < 8 or len(digits) > 14:
        return ""
    if len(set(digits)) <= 2:
        return ""
    if text.startswith("+"):
        return text
    if digits.startswith(("65", "60", "62")):
        return f"+{digits}"
    return digits


def _clean_public_person_title(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -:,.()")
    words = []
    for word in text.split():
        lowered = word.lower()
        words.append(lowered.upper() if lowered in {"ceo", "hr"} else lowered.capitalize())
    return _short_text(" ".join(words), 120)


def _clean_public_person_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -:,.()")
    text = re.sub(r"\b(?:of|at|for|the|a|an|is|as|by)\b.*$", "", text, flags=re.I).strip(" -:,.()")
    if not text or len(text) < 3:
        return ""
    if any(_normalize_relevance_text(text) == _normalize_relevance_text(stop) for stop in PUBLIC_PERSON_NAME_STOPWORDS):
        return ""
    if any(token.lower() in COMPANY_NAME_STOPWORDS for token in text.split()):
        return ""
    if len(text.split()) > 4:
        return ""
    return _short_text(text, 120)


def outreach_angles(signals: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[str]:
    signal_types = {signal.get("signal_type") for signal in signals}
    angles = []
    if "hiring_signal" in signal_types:
        angles.append("Use active hiring as the reason to ask about onboarding, scheduling, and HR admin load.")
    if "growth_signal" in signal_types:
        angles.append("Use expansion or new outlet context to ask how they are scaling workforce operations.")
    if "pain_signal" in signal_types:
        angles.append("Use public manpower or operations pain only as a soft discovery prompt, not as a claim.")
    if "news_signal" in signal_types:
        angles.append("Use recent public news as a warm opener, then verify what changed internally.")
    if "decision_maker_hint" in signal_types or any(candidate.get("is_decision_maker") for candidate in candidates):
        angles.append("Review the decision-maker hint before drafting a manual LinkedIn or WhatsApp touch.")
    return angles[:5]


def _host(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _short_text(value: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit].rstrip()
