#!/usr/bin/env python3
"""Customer 360 MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env
from psm_slack_notifier import post_ps_wee_audit


load_profile_env()

DEFAULT_C360_BASE_URL = "https://customer-360-qv4r5xkisq-as.a.run.app"
THIN_POC_AA_CHANNEL_ID = "C0B5H2YE5T2"
MAX_CUSTOMER_SEARCH_VARIANTS = 8
CUSTOMER_QUERY_PREFIXES = {
    "proj",
    "project",
    "cs",
    "customer",
    "customers",
    "account",
    "acct",
    "client",
}
COMPACT_COMPANY_SUFFIXES = (
    "productions",
    "production",
    "restaurants",
    "restaurant",
    "services",
    "service",
    "holdings",
    "holding",
    "hospitality",
    "company",
    "group",
    "retail",
    "foods",
    "food",
    "cafe",
    "coffee",
)
COMPANY_ENTITY_SUFFIXES = (
    "pte ltd",
    "private limited",
    "limited",
    "ltd",
)

mcp = FastMCP(
    "psm_c360",
    instructions=(
        "Customer 360 internal API access for PSM Ops Bot. "
        "Use the Customer 360 internal token header; never use personal "
        "Customer 360 session cookies."
    ),
)


class C360Error(RuntimeError):
    pass


def _base_url() -> str:
    return os.environ.get("CUSTOMER360_BASE_URL", DEFAULT_C360_BASE_URL).strip().rstrip("/")


def _token() -> str:
    token = (
        os.environ.get("CUSTOMER360_INTERNAL_API_TOKEN", "").strip()
        or os.environ.get("CUSTOMER_360_INTERNAL_API_TOKEN", "").strip()
    )
    if not token:
        raise C360Error("CUSTOMER360_INTERNAL_API_TOKEN is not configured.")
    return token


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/markdown",
        "X-Customer360-Internal-Token": _token(),
        "Content-Type": "application/json",
    }


def _post_c360_audit(
    event_type: str,
    scope: dict[str, Any],
    *,
    answer: Any = None,
    blocked_reason: str = "",
    source_label: str = "Customer 360 internal API",
) -> dict[str, Any] | None:
    source_thread_url = str((scope or {}).get("slack_thread_url") or "").strip()
    if not source_thread_url:
        return None
    customer = str((scope or {}).get("customer_key") or (scope or {}).get("query") or "")
    return post_ps_wee_audit(
        event_type,
        source_thread_url=source_thread_url,
        customer=customer,
        summary=source_label,
        status="blocked" if blocked_reason else "verified",
        c360_payload={"source": source_label, "scope": scope, "answer": answer},
        blocked_reason=blocked_reason,
        extra={"subsystem": "customer360"},
    )


def _slack_channel_id_from_permalink(slack_thread_url: str) -> str:
    match = re.search(r"/archives/([A-Z0-9]+)/", slack_thread_url or "")
    return match.group(1) if match else ""


def _event_aa_channel_id() -> str:
    value = (os.environ.get("PSM_OPS_AA_CHANNEL_ID") or "").strip()
    if not value and os.environ.get("PSM_OPS_JIRA_MODE", "").strip().lower() == "thin_poc":
        return THIN_POC_AA_CHANNEL_ID
    return value


def _is_event_aa_thread(slack_thread_url: str) -> bool:
    expected = _event_aa_channel_id()
    if not expected:
        return False
    return _slack_channel_id_from_permalink(slack_thread_url) == expected


def _aa_channel_redirect(scope: dict[str, Any], source_label: str) -> dict[str, Any]:
    """AA-channel turns are ticket-first; ask_c360_customer_context must not answer."""
    reason = (
        "AA-channel guard: ask_c360_customer_context is disabled inside the AA channel "
        "because AA turns are always ticket-first. Call create_ps_wee_intake_ticket now; "
        "any C360 wiki context can be added as a Slack reply or Jira comment after the "
        "ticket exists. Even if C360 errors entirely, the AA intake must still create."
    )
    central_copy = _post_c360_audit(
        "c360_aa_channel_redirect",
        scope,
        blocked_reason=reason,
        source_label=source_label,
    )
    answer = {"status": "aa_channel_redirect", "message": reason}
    if central_copy is not None:
        answer["central_copy"] = central_copy
    return {
        "answer": answer,
        "source": source_label,
        "scope": scope,
        "confidence": "blocked",
        "caveat": reason,
        "aa_channel_redirect": True,
    }


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    central_copy = _post_c360_audit("c360_blocked", scope, blocked_reason=message)
    answer = {"status": "blocked", "message": message}
    if central_copy is not None:
        answer["central_copy"] = central_copy
    return {
        "answer": answer,
        "source": "Customer 360 internal API",
        "scope": scope,
        "confidence": "blocked",
        "caveat": message,
    }


def _http_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{_base_url()}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return json.loads(payload)
            return {"status": "ok", "data": payload}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise C360Error(f"Customer 360 API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise C360Error(f"Customer 360 API unavailable: {error.reason}") from error


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_customer_hint(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(r"<[^>|]+\|([^>]+)>", r"\1", cleaned)
    cleaned = re.sub(r"[#`]", "", cleaned)
    return _collapse_spaces(cleaned)


def _customer_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^A-Za-z0-9]+", value.lower()) if token]


def _strip_customer_prefixes(tokens: list[str]) -> list[str]:
    stripped = list(tokens)
    while stripped and stripped[0] in CUSTOMER_QUERY_PREFIXES:
        stripped = stripped[1:]
    return stripped


def _split_compact_customer_name(value: str) -> str:
    compact = re.sub(r"[^a-z0-9]", "", value.lower())
    if not compact:
        return ""

    for suffix in COMPACT_COMPANY_SUFFIXES:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 2:
            prefix = compact[: -len(suffix)]
            return f"{prefix} {suffix}"
    return ""


def _singularize_last_customer_word(value: str) -> str:
    tokens = _customer_tokens(value)
    if not tokens:
        return ""
    last = tokens[-1]
    if len(last) <= 3 or not last.endswith("s") or last.endswith("ss"):
        return ""
    return " ".join([*tokens[:-1], last[:-1]])


def _has_company_entity_suffix(value: str) -> bool:
    normalized = " ".join(_customer_tokens(value))
    return any(normalized.endswith(suffix) for suffix in COMPANY_ENTITY_SUFFIXES)


def _title_company_name(value: str) -> str:
    return " ".join(token.capitalize() for token in _customer_tokens(value))


def _unique_variants(values: list[str]) -> list[str]:
    variants = []
    seen = set()
    for value in values:
        variant = _collapse_spaces(value)
        if not variant:
            continue
        key = variant.lower()
        if key in seen:
            continue
        seen.add(key)
        variants.append(variant)
        if len(variants) >= MAX_CUSTOMER_SEARCH_VARIANTS:
            break
    return variants


def _customer_search_variants(query: str) -> list[str]:
    """Build bounded C360 search variants from Slack/channel/customer hints."""

    cleaned = _clean_customer_hint(query)
    values = [cleaned]
    tokens = _customer_tokens(cleaned)
    stripped_tokens = _strip_customer_prefixes(tokens)
    token_sets = []
    if stripped_tokens and stripped_tokens != tokens:
        token_sets.append(stripped_tokens)
    elif tokens:
        token_sets.append(tokens)

    for candidate_tokens in token_sets:
        compact = "".join(candidate_tokens)
        spaced = " ".join(candidate_tokens)
        values.extend([compact, spaced])

        expanded = ""
        if len(candidate_tokens) == 1:
            expanded = _split_compact_customer_name(candidate_tokens[0])
            if expanded:
                values.append(expanded)
                singular_expanded = _singularize_last_customer_word(expanded)
                if singular_expanded:
                    values.append(singular_expanded)

        company_base = expanded or spaced
        if (
            len(_customer_tokens(company_base)) >= 2
            and not _has_company_entity_suffix(company_base)
        ):
            values.append(f"{_title_company_name(company_base)} Pte Ltd")

    return _unique_variants(values)


def _extract_c360_groups(payload: Any) -> list[Any]:
    if not isinstance(payload, dict):
        return []
    groups = payload.get("search", {}).get("groups", [])
    return groups if isinstance(groups, list) else []


def _normalized_key(value: Any) -> str:
    return " ".join(_customer_tokens(str(value)))


def _canonical_c360_customer_key(value: str) -> str:
    return re.sub(r"^customer-", "", (value or "").strip(), count=1, flags=re.IGNORECASE)


def _group_dedupe_keys(group: Any) -> list[str]:
    if not isinstance(group, dict):
        return [f"payload:{json.dumps(group, sort_keys=True, default=str)}"]

    keys = []
    for key in (
        "customerKey",
        "customer_key",
        "routeKey",
        "route_key",
        "companyKey",
        "company_key",
        "key",
    ):
        value = group.get(key)
        if value:
            keys.append(f"customer:{_normalized_key(value)}")

    hubspot_company_id = group.get("hubspotCompanyId")
    if hubspot_company_id:
        keys.append(f"hubspot:{_normalized_key(hubspot_company_id)}")

    for key in ("companyName", "customerName", "displayName", "name"):
        value = group.get(key)
        if value:
            keys.append(f"name:{_normalized_key(value)}")

    if keys:
        return keys
    return [f"payload:{json.dumps(group, sort_keys=True, default=str)}"]


def _dedupe_c360_groups(groups: list[Any]) -> list[Any]:
    deduped = []
    key_to_index = {}
    seen = set()
    for group in groups:
        keys = _group_dedupe_keys(group)
        if any(key in seen for key in keys):
            duplicate_index = next(
                (key_to_index[key] for key in keys if key in key_to_index),
                None,
            )
            if duplicate_index is not None:
                deduped[duplicate_index] = _merge_c360_groups(
                    deduped[duplicate_index],
                    group,
                )
            continue
        deduped.append(group)
        group_index = len(deduped) - 1
        seen.update(keys)
        for key in keys:
            key_to_index[key] = group_index
    return deduped


def _merge_c360_groups(existing: Any, new_group: Any) -> Any:
    if not isinstance(existing, dict) or not isinstance(new_group, dict):
        return existing

    existing_org_matches = existing.get("orgMatches")
    new_org_matches = new_group.get("orgMatches")
    existing_org_count = len(existing_org_matches) if isinstance(existing_org_matches, list) else 0
    new_org_count = len(new_org_matches) if isinstance(new_org_matches, list) else 0
    prefer_new = new_org_count > existing_org_count
    merged = {**existing, **new_group} if prefer_new else {**new_group, **existing}

    matched_fields = []
    for field in [
        *(existing.get("matchedFields") if isinstance(existing.get("matchedFields"), list) else []),
        *(new_group.get("matchedFields") if isinstance(new_group.get("matchedFields"), list) else []),
    ]:
        if field not in matched_fields:
            matched_fields.append(field)
    if matched_fields:
        merged["matchedFields"] = matched_fields

    org_matches = []
    seen_org_keys = set()
    for item in [
        *(existing_org_matches if isinstance(existing_org_matches, list) else []),
        *(new_org_matches if isinstance(new_org_matches, list) else []),
    ]:
        key = json.dumps(item, sort_keys=True, default=str)
        if key in seen_org_keys:
            continue
        seen_org_keys.add(key)
        org_matches.append(item)
    if org_matches:
        merged["orgMatches"] = org_matches

    return merged


@mcp.tool()
def search_c360_customers(query: str, limit: int = 8, slack_thread_url: str = "") -> dict[str, Any]:
    """Search Customer 360 customers by company, owner, org, or customer key."""

    normalized_query = (query or "").strip()
    search_limit = max(1, min(int(limit or 8), 20))
    searched_variants = _customer_search_variants(normalized_query)
    scope = {
        "query": normalized_query,
        "limit": search_limit,
        "searched_variants": searched_variants,
        "slack_thread_url": (slack_thread_url or "").strip(),
    }
    if not normalized_query:
        return _blocked("Customer search query is required.", scope)

    try:
        groups = []
        for variant in searched_variants:
            encoded = urllib.parse.urlencode({"q": variant})
            payload = _http_json("GET", f"/api/companies?{encoded}")
            groups.extend(_extract_c360_groups(payload))
    except C360Error as error:
        return _blocked(str(error), scope)

    groups = _dedupe_c360_groups(groups)
    missing_mapping = len(groups) == 0
    answer = groups[:search_limit]
    central_copy = _post_c360_audit(
        "c360_search",
        scope,
        answer=answer,
        source_label="Customer 360 /api/companies",
    )
    result = {
        "answer": answer,
        "searched_variants": searched_variants,
        "match_count": len(groups),
        "missing_mapping": missing_mapping,
        "source": "Customer 360 /api/companies",
        "scope": scope,
        "confidence": "needs-check" if missing_mapping else "verified",
        "caveat": (
            "No Customer 360 customer/org mapping found for the searched variants."
            if missing_mapping
            else "All-customer C360 access is enabled for V1; task writes still stay Jira-scoped."
        ),
    }
    if central_copy is not None:
        result["central_copy"] = central_copy
    return result


@mcp.tool()
def get_c360_account_context(customer_key: str, format: str = "markdown", slack_thread_url: str = "") -> dict[str, Any]:
    """Fetch compact Customer 360 account context for one customer key."""

    key = _canonical_c360_customer_key(customer_key)
    output_format = "json" if str(format).lower() == "json" else "markdown"
    scope = {"customer_key": key, "format": output_format, "slack_thread_url": (slack_thread_url or "").strip()}
    if not key:
        return _blocked("Customer key is required.", scope)

    try:
        encoded_key = urllib.parse.quote(key, safe="")
        query = "?format=markdown" if output_format == "markdown" else ""
        payload = _http_json("GET", f"/api/companies/{encoded_key}/context{query}")
    except C360Error as error:
        return _blocked(str(error), scope)

    answer = payload.get("data", payload) if isinstance(payload, dict) else payload
    central_copy = _post_c360_audit(
        "c360_account_context",
        scope,
        answer=answer,
        source_label=f"Customer 360 /api/companies/{key}/context",
    )
    result = {
        "answer": answer,
        "source": f"Customer 360 /api/companies/{key}/context",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Context is compact and cited; raw source packs are not exposed.",
    }
    if central_copy is not None:
        result["central_copy"] = central_copy
    return result


@mcp.tool()
def ask_c360_customer_context(customer_key: str, question: str, slack_thread_url: str = "") -> dict[str, Any]:
    """Ask Customer 360 compiled wiki and account context about one customer."""

    key = _canonical_c360_customer_key(customer_key)
    normalized_question = (question or "").strip()
    scope = {
        "customer_key": key,
        "question_chars": len(normalized_question),
        "slack_thread_url": (slack_thread_url or "").strip(),
    }
    if _is_event_aa_thread(scope["slack_thread_url"]):
        return _aa_channel_redirect(
            scope,
            source_label=f"Customer 360 /api/companies/{key}/ask",
        )
    if not key:
        return _blocked("Customer key is required.", scope)
    if not normalized_question:
        return _blocked("Question is required.", scope)

    try:
        encoded_key = urllib.parse.quote(key, safe="")
        payload = _http_json(
            "POST",
            f"/api/companies/{encoded_key}/ask",
            {"question": normalized_question},
        )
    except C360Error as error:
        return _blocked(str(error), scope)

    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    confidence = "verified"
    caveat = "Answer is constrained to compiled Customer 360 wiki and cited account context."
    if isinstance(data, dict) and data.get("citationRefs") == []:
        confidence = "needs-check"
        caveat = "Customer 360 returned no supporting citation refs for this question."
    central_copy = _post_c360_audit(
        "c360_customer_answer",
        scope,
        answer=data,
        source_label=f"Customer 360 /api/companies/{key}/ask",
    )
    result = {
        "answer": data,
        "source": f"Customer 360 /api/companies/{key}/ask",
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }
    if central_copy is not None:
        result["central_copy"] = central_copy
    return result


if __name__ == "__main__":
    mcp.run("stdio")
