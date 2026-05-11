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
PUBLIC_EVIDENCE_ITEM_LIMIT = 20
PUBLIC_FETCH_TIMEOUT_SECONDS = 5
PUBLIC_FETCH_MAX_BYTES = 30_000
SNIPPET_CHAR_LIMIT = 420
SIGNAL_EVIDENCE_CHAR_LIMIT = 240
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
        "query_count": 3,
        "max_results": 5,
        "extract_depth": "basic",
        "extract_url_cap": 2,
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
    base = [
        f'"{label}" {country} official website news opening expansion',
        f'"{label}" careers hiring jobs HR {country}',
        f'"{label}" payroll scheduling manpower HR owner founder operations {country}',
    ]
    if domain:
        base.insert(1, f'site:{domain} careers hiring HR payroll scheduling')
    return [re.sub(r"\s+", " ", query).strip() for query in base if query.strip()][: MODE_CONFIGS[_research_mode(mode)]["query_count"]]


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
        company_manual_checks: list[dict[str, Any]] = []

        for result in unique_results:
            source_type = result["source_type"]
            source_url = result["source_url"]
            extract_text = extracted_text_by_url.get(source_url, "")
            fetch_status = "manual_check_only" if result["requires_manual_review"] else ("tavily_extracted" if extract_text else "tavily_search_only")
            signals = extract_company_signals(result, source_type, source_url, extract_text)
            for signal in signals:
                signal["company_id"] = company["company_id"]
                signal["company_name"] = company["name"]
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
            if result["requires_manual_review"]:
                company_manual_checks.append(
                    manual_check_item(company, source_url, result["title"], source_type, "social_gated_or_manual_source")
                )

        company_missing = _missing_evidence(company, company_signal_rows, company_evidence)
        next_tool = "search_exa_people_candidates" if _needs_people_candidates(company_signal_rows) else ""
        game_inputs = game_plan_input(company, company_signal_rows, company_evidence, company_manual_checks, company_missing, next_tool)

        source_evidence.extend(company_evidence[:PUBLIC_EVIDENCE_ITEM_LIMIT])
        company_signals.extend(company_signal_rows[:20])
        manual_check_items.extend(company_manual_checks[:10])
        missing_evidence.extend(company_missing)
        game_plan_inputs.append(game_inputs)
        company_outputs.append(
            {
                "input_company": company,
                "company_signals": company_signal_rows[:20],
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
    urls.sort(key=lambda url: 0 if company_domain and _host(url).endswith(company_domain) else 1)
    return urls[: MODE_CONFIGS[_research_mode(mode)]["extract_url_cap"]]


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
    signal_text = search_text if source_type == "general_web" else text
    lowered = signal_text.lower()
    signal_keywords = {
        "hiring_signal": ("hiring", "vacancy", "recruit", "join our team", "open role", "job opening", "jobs available"),
        "growth_signal": ("new outlet", "opening soon", "grand opening", "new branch", "expanding", "expansion", "launch", "coming soon"),
        "pain_signal": ("manpower", "understaffed", "turnover", "attendance", "payroll", "scheduling", "retention"),
        "news_signal": ("award", "funding", "partnership", "franchise", "announced", "featured"),
        "decision_maker_hint": ("founder", "ceo", "managing director", "general manager", "hr director", "people director"),
    }
    signals = []
    for signal_type, keywords in signal_keywords.items():
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
                        str(item.get("snippet") or (fetched_text if source_type != "general_web" else "") or item.get("title") or ""),
                        SIGNAL_EVIDENCE_CHAR_LIMIT,
                    ),
                    "confidence": "needs-check",
                }
            )
    return signals


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
